from __future__ import annotations

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.db.sync import bulk_upsert_products, bulk_upsert_daily_sales, bulk_upsert_stock_levels
from app.sheets.reader import read_product_master, read_sales, read_stock


class SyncService:


    @staticmethod
    def sync_master(db: Session, df: pd.DataFrame) -> dict:
        records = [
            {
                "code":         str(r.get("상품코드", "")),
                "name":         str(r.get("상품명", "")),
                "category":     r.get("카테고리"),
                "safety_stock": int(r.get("안전재고기준", 0) or 0),
                "source":       "sheets",
            }
            for r in df.to_dict("records")
            if r.get("상품코드")
        ]
        result = bulk_upsert_products(db, records)
        logger.info(f"[SyncService] products 동기화: {result}")
        return result


    @staticmethod
    def sync_sales(db: Session, df: pd.DataFrame) -> dict:
        records = [
            {
                "date":         str(r.get("날짜", "")),
                "product_code": str(r.get("상품코드", "")),
                "qty":          int(r.get("판매수량", 0) or 0),
                "revenue":      float(r.get("매출액", 0) or 0),
                "cost":         float(r.get("매입액", 0) or 0),
            }
            for r in df.to_dict("records")
            if r.get("상품코드") and r.get("날짜")
        ]
        result = bulk_upsert_daily_sales(db, records)
        logger.info(f"[SyncService] daily_sales 동기화: {result}")
        return result


    @staticmethod
    def sync_stock(db: Session, df: pd.DataFrame) -> dict:
        records = [
            {
                "product_code":  str(r.get("상품코드", "")),
                "current_stock": int(r.get("현재재고", 0) or 0),
                "restock_date":  r.get("입고예정일") or None,
                "restock_qty":   r.get("입고예정수량"),
            }
            for r in df.to_dict("records")
            if r.get("상품코드")
        ]
        result = bulk_upsert_stock_levels(db, records)
        logger.info(f"[SyncService] stock_levels 동기화: {result}")
        return result


    #  Sheets → DB 전체 동기화
    @staticmethod
    def sync_all_from_sheets(db: Session) -> None:
        try:
            SyncService.sync_master(db, read_product_master())
            SyncService.sync_sales(db,  read_sales())
            SyncService.sync_stock(db,  read_stock())
            logger.info("[SyncService] Sheets→DB 전체 동기화 완료")
        except Exception as e:
            logger.error(f"[SyncService] 전체 동기화 실패: {e}")
            raise