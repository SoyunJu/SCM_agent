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
def bulk_upsert_products(db: Session, records: list[dict]) -> dict:
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    inserted = updated = 0
    sql = text("""
               INSERT INTO products (code, name, category, safety_stock, status, source, updated_at)
               VALUES (:code, :name, :category, :safety_stock, :status, :source, NOW())
                   ON DUPLICATE KEY UPDATE
                                        name          = VALUES(name),
                                        category      = VALUES(category),
                                        safety_stock  = VALUES(safety_stock),
                                        status        = VALUES(status),
                                        source        = VALUES(source),
                                        updated_at    = NOW()
               """)

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
        result = db.execute(sql, params)

        inserted += sum(1 for _ in range(result.rowcount) if result.rowcount > 0)
        db.commit()

    logger.info(f"데이터 입력 성공: total={len(records)}")
    return {"inserted": inserted, "updated": updated, "skipped": 0}



# 일별 매출
def bulk_upsert_daily_sales(db: Session, records: list[dict]) -> dict:
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    sql = text("""
               INSERT INTO daily_sales (date, product_code, qty, revenue, cost)
               VALUES (:date, :product_code, :qty, :revenue)
                   ON DUPLICATE KEY UPDATE qty=VALUES(qty), revenue=VALUES(revenue), cost=VALUES(cost)
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



# 헬퍼
def make_params_hash(params: dict) -> str:
    serialized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()
