from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session



_BATCH = 1000


def _batched(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


# 상품 마스터
def bulk_upsert_daily_sales(db: Session, records: list[dict]) -> dict:
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    sql = text("""
               INSERT INTO daily_sales (date, product_code, qty, revenue, cost)
               VALUES (:date, :product_code, :qty, :revenue, :cost)
                   ON DUPLICATE KEY UPDATE
                                        qty     = VALUES(qty),
                                        revenue = VALUES(revenue),
                                        cost    = VALUES(cost)
               """)

    total = 0
    for batch in _batched(records, _BATCH):
        params = []
        for r in batch:
            raw_date = r.get("date")
            if isinstance(raw_date, str):
                try:
                    raw_date = date.fromisoformat(raw_date)
                except ValueError:
                    continue
            params.append({
                "date":         raw_date,
                "product_code": r["product_code"],
                "qty":          int(r.get("qty", 0)),
                "revenue":      float(r.get("revenue", 0.0)),
                "cost":         float(r.get("cost", 0.0)),
            })
        if not params:
            continue
        db.execute(sql, params)
        db.commit()
        total += len(params)

    logger.info(f"일별매출 업데이트 성공: total={total}")
    return {"inserted": total, "updated": 0, "skipped": len(records) - total}



# 재고
def bulk_upsert_stock_levels(db: Session, records: list[dict]) -> dict:
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    sql = text("""
               INSERT INTO stock_levels (product_code, current_stock, restock_date, restock_qty, updated_at)
               VALUES (:product_code, :current_stock, :restock_date, :restock_qty, NOW())
                   ON DUPLICATE KEY UPDATE
                                        current_stock = VALUES(current_stock),
                                        restock_date  = VALUES(restock_date),
                                        restock_qty   = VALUES(restock_qty),
                                        updated_at    = NOW()
               """)

    total = 0
    for batch in _batched(records, _BATCH):
        params = []
        for r in batch:
            restock = r.get("restock_date")
            if isinstance(restock, str) and restock:
                try:
                    restock = date.fromisoformat(restock)
                except ValueError:
                    restock = None
            params.append({
                "product_code":  r["product_code"],
                "current_stock": int(r.get("current_stock", 0)),
                "restock_date":  restock,
                "restock_qty":   int(r.get("restock_qty", 0)) if r.get("restock_qty") else None,
            })
        if not params:
            continue
        db.execute(sql, params)
        db.commit()
        total += len(params)

    logger.info(f"재고 현황 업데이트 성공: total={total}")
    return {"inserted": total, "updated": 0, "skipped": len(records) - total}



def bulk_upsert_products(db: Session, records: list[dict]) -> dict:
    """상품마스터 DataFrame → products 테이블 upsert."""
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    sql = text("""
               INSERT INTO products
                   (code, name, category, safety_stock, status, source, updated_at)
               VALUES
                   (:code, :name, :category, :safety_stock, :status, :source, NOW())
                   ON DUPLICATE KEY UPDATE
                                        name         = VALUES(name),
                                        category     = VALUES(category),
                                        source       = VALUES(source),
                                        updated_at   = NOW()
               """)

    total = 0
    for batch in _batched(records, _BATCH):
        params = [
            {
                "code":         r["code"],
                "name":         r.get("name", ""),
                "category":     r.get("category"),
                "safety_stock": int(r.get("safety_stock", 0)),
                "status":       r.get("status", "active"),
                "source":       r.get("source", "sheets"),
            }
            for r in batch
            if r.get("code")
        ]
        if not params:
            continue
        db.execute(sql, params)
        db.commit()
        total += len(params)

    logger.info(f"[sync] products upsert: total={total}")
    return {"inserted": total, "updated": 0, "skipped": len(records) - total}



def get_last_sync_date(db: Session, sync_type: str) -> str | None:
    from app.db.repository import get_setting
    return get_setting(db, f"LAST_SYNC_{sync_type.upper()}", None)


# 마지막 동기화 날짜 저장
def set_last_sync_date(db: Session, sync_type: str, date_str: str) -> None:
    from app.db.models import SystemSettings
    row = db.query(SystemSettings).filter(
        SystemSettings.setting_key == f"LAST_SYNC_{sync_type.upper()}"
    ).first()
    if row:
        row.setting_value = date_str
    else:
        db.add(SystemSettings(
            setting_key   = f"LAST_SYNC_{sync_type.upper()}",
            setting_value = date_str,
            description   = f"{sync_type} 마지막 동기화 날짜",
        ))
    db.commit()


# watermark 기반 증분 upsert
def incremental_upsert_daily_sales(db: Session, records: list[dict]) -> dict:
    if not records:
        return {"inserted": 0, "skipped": 0}

    last_date = get_last_sync_date(db, "SALES")
    if last_date:
        records = [r for r in records if str(r.get("date", "")) > last_date]

    if not records:
        return {"inserted": 0, "skipped": 0}

    result   = bulk_upsert_daily_sales(db, records)
    max_date = max(str(r.get("date", "")) for r in records)
    set_last_sync_date(db, "SALES", max_date)
    return result


# 헬퍼
def make_params_hash(params: dict) -> str:
    serialized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
