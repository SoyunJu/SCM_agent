from __future__ import annotations

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.db.sync import bulk_upsert_products, bulk_upsert_daily_sales, bulk_upsert_stock_levels
from app.sheets.reader import read_product_master, read_sales, read_stock


class SyncService:


    @staticmethod
    def sync_master(db: Session, df: pd.DataFrame) -> dict:
        CATEGORY_MAP = {
            "Accessories": "액세서리",
            "Bottoms":     "하의",
            "Tops":        "상의",
            "Outerwear":   "아우터",
            "Luggage":     "기타",
            "General":      "일반",
        }
        records = [
            {
                "code":         str(r.get("상품코드", "")),
                "name":         str(r.get("상품명", "")),
                "category":     CATEGORY_MAP.get(r.get("카테고리"), r.get("카테고리")),
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
            # 시트 캐시 무효화
            from app.cache.redis_client import cache_delete, get_redis
            for sheet in ["상품마스터", "일별판매", "재고현황"]:
                cache_delete(f"sheets:{sheet}")

            SyncService.sync_master(db, read_product_master())
            SyncService.sync_sales(db,  read_sales())
            SyncService.sync_stock(db,  read_stock())

            # 분석 캐시 무효화 (데이터 변경 반영)
            try:
                get_redis().delete(*get_redis().keys("analysis:*") or ["__dummy__"])
            except Exception:
                pass
            from app.db.repository import delete_old_analysis_cache
            delete_old_analysis_cache(db, older_than_hours=0)  # 전체 삭제

            logger.info("[SyncService] Sheets→DB 전체 동기화 + 분석캐시 무효화 완료")
        except Exception as e:
            logger.error(f"[SyncService] 전체 동기화 실패: {e}")
            raise


    # db->sheets 역방향 동기화
    @staticmethod
    def sync_db_to_sheets(db: Session) -> dict:
        import pandas as pd
        from app.db.models import Product, ProductStatus, StockLevel, DailySales
        from app.sheets.writer import _clear_and_write
        from app.sheets.client import get_spreadsheet as _gs

        result = {}

        try:
            # 상품마스터
            products = db.query(Product).filter(Product.status != ProductStatus.SAMPLE).all()
            df_master = pd.DataFrame([
                {
                    "상품코드":     p.code,
                    "상품명":       p.name,
                    "카테고리":     p.category or "Default",
                    "안전재고기준": p.safety_stock,
                }
                for p in products
            ])
            if not df_master.empty:
                ws = _gs().worksheet("상품마스터")
                _clear_and_write(ws, df_master)
                result["master"] = len(df_master)
                logger.info(f"[SyncService] DB→Sheets 상품마스터: {len(df_master)}건")
        except Exception as e:
            logger.error(f"[SyncService] DB→Sheets 상품마스터 실패: {e}")
            result["master_error"] = str(e)

        try:
            # 재고현황
            from datetime import date
            stocks = db.query(StockLevel).all()
            df_stock = pd.DataFrame([
                {
                    "상품코드":     s.product_code,
                    "현재재고":     s.current_stock,
                    "입고예정일":   str(s.restock_date) if s.restock_date else str(date.today()),
                    "입고예정수량": s.restock_qty or 0,
                }
                for s in stocks
            ])
            if not df_stock.empty:
                ws = _gs().worksheet("재고현황")
                _clear_and_write(ws, df_stock)
                result["stock"] = len(df_stock)
                logger.info(f"[SyncService] DB→Sheets 재고현황: {len(df_stock)}건")
        except Exception as e:
            logger.error(f"[SyncService] DB→Sheets 재고현황 실패: {e}")
            result["stock_error"] = str(e)

        try:
            # 일별판매 (최근 90일만)
            from datetime import date, timedelta
            from sqlalchemy import and_
            cutoff = date.today() - timedelta(days=90)
            sales  = db.query(DailySales).filter(DailySales.date >= cutoff).order_by(DailySales.date.asc()).all()
            df_sales = pd.DataFrame([
                {
                    "날짜":    str(s.date),
                    "상품코드": s.product_code,
                    "판매수량": s.qty,
                    "매출액":   s.revenue,
                    "매입액":   s.cost or 0,
                }
                for s in sales
            ])
            if not df_sales.empty:
                ws = _gs().worksheet("일별판매")
                _clear_and_write(ws, df_sales)
                result["sales"] = len(df_sales)
                logger.info(f"[SyncService] DB→Sheets 일별판매: {len(df_sales)}건")
        except Exception as e:
            logger.error(f"[SyncService] DB→Sheets 일별판매 실패: {e}")
            result["sales_error"] = str(e)

        logger.info(f"[SyncService] DB→Sheets 전체 완료: {result}")
        return result