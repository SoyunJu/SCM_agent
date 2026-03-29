
# 데이터 조회/필터/페이징/CSV다운로드/통계 분석 전담

from __future__ import annotations

import io
import pandas as pd
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.sheets.reader import read_product_master, read_sales, read_stock, read_orders


class SheetService:

    # Helper

    @staticmethod
    def _paginate(df: pd.DataFrame, page: int, page_size: int) -> dict:
        page_size   = min(page_size, 200)
        total       = len(df)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        return {
            "total": total, "page": page,
            "page_size": page_size, "total_pages": total_pages,
            "items": df.iloc[start:start + page_size].to_dict(orient="records"),
        }

    @staticmethod
    def _to_csv(df: pd.DataFrame, filename: str) -> StreamingResponse:
        buf = io.BytesIO()
        buf.write(b'\xef\xbb\xbf')
        df.to_csv(buf, index=False, encoding="utf-8")
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @staticmethod
    def _search_filter(df: pd.DataFrame, search: str | None) -> pd.DataFrame:
        if not search:
            return df
        mask = df["상품코드"].astype(str).str.contains(search, case=False, na=False)
        if "상품명" in df.columns:
            mask = mask | df["상품명"].astype(str).str.contains(search, case=False, na=False)
        return df[mask]

    @staticmethod
    def _category_filter(df: pd.DataFrame, category: str | None) -> pd.DataFrame:
        if not category:
            return df
        col = next((c for c in ["카테고리", "category"] if c in df.columns), None)
        return df[df[col] == category] if col else df

    # --- GET ---

    @staticmethod
    def get_categories() -> list[str]:
        df  = read_product_master()
        col = next((c for c in ["카테고리", "category"] if c in df.columns), None)
        if not col:
            return []
        return sorted(c for c in df[col].dropna().unique() if c)

    @staticmethod
    def get_master(
            page: int, page_size: int,
            search: str | None, category: str | None, download: bool,
    ):
        df = read_product_master()
        df = SheetService._search_filter(df, search)
        df = SheetService._category_filter(df, category)
        if download:
            return SheetService._to_csv(df, "master.csv")
        return SheetService._paginate(df, page, page_size)

    @staticmethod
    def get_sales(
            days: int, page: int, page_size: int,
            search: str | None, category: str | None, download: bool,
    ):
        df = read_sales()
        df["날짜"] = pd.to_datetime(df["날짜"])
        df = df[df["날짜"] >= df["날짜"].max() - pd.Timedelta(days=days)].copy()
        df = SheetService._search_filter(df, search)
        df = SheetService._category_filter(df, category)
        df["날짜"] = df["날짜"].dt.strftime("%Y-%m-%d")
        if download:
            return SheetService._to_csv(df, "sales.csv")
        return SheetService._paginate(df, page, page_size)

    @staticmethod
    def get_stock(
            page: int, page_size: int,
            search: str | None, category: str | None, download: bool,
    ):
        df = read_stock()
        df = SheetService._search_filter(df, search)
        df = SheetService._category_filter(df, category)
        if download:
            return SheetService._to_csv(df, "stock.csv")
        return SheetService._paginate(df, page, page_size)

    @staticmethod
    def get_orders(
            status: str | None, days: int, page: int, page_size: int,
    ) -> dict:
        df = read_orders()
        if df.empty:
            return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}
        if "발주일" in df.columns:
            df["발주일"] = pd.to_datetime(df["발주일"], errors="coerce")
            df = df[df["발주일"] >= pd.Timestamp.now() - pd.Timedelta(days=days)].copy()
            df["발주일"] = df["발주일"].dt.strftime("%Y-%m-%d")
        if status:
            df = df[df["상태"] == status]
        return SheetService._paginate(df, page, page_size)


    # --- 통계 ---

    @staticmethod
    def get_sales_stats(period: str, category: str | None = None) -> dict:
        df = read_sales()
        df["날짜"] = pd.to_datetime(df["날짜"])
        if category:
            df = SheetService._category_filter(df, category)

        if period == "daily":
            cutoff = df["날짜"].max() - pd.Timedelta(days=29)
            agg = (
                df[df["날짜"] >= cutoff]
                .groupby("날짜").agg(판매수량=("판매수량","sum"), 매출액=("매출액","sum"))
                .reset_index().sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "weekly":
            cutoff = df["날짜"].max() - pd.Timedelta(weeks=12)
            df = df[df["날짜"] >= cutoff]
            df["주"] = df["날짜"].dt.to_period("W").dt.start_time
            agg = (
                df.groupby("주").agg(판매수량=("판매수량","sum"), 매출액=("매출액","sum"))
                .reset_index().rename(columns={"주":"날짜"}).sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "monthly":
            df["월"] = df["날짜"].dt.to_period("M").dt.start_time
            agg = (
                df.groupby("월").agg(판매수량=("판매수량","sum"), 매출액=("매출액","sum"))
                .reset_index().rename(columns={"월":"날짜"}).sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m")
        else:
            return {"error": "period는 daily/weekly/monthly 중 하나"}

        return {"period": period, "items": agg.to_dict(orient="records")}

    @staticmethod
    def get_stock_stats(category: str | None = None) -> dict:
        from app.analyzer.stock_analyzer import run_stock_analysis
        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()
        if category:
            df_master = SheetService._category_filter(df_master, category)

        anomalies = run_stock_analysis(df_master, df_stock, df_sales)
        from app.utils.severity import norm
        severity_counts: dict[str, int] = {}
        for a in anomalies:
            sev = norm(a.get("severity", ""))
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        df_stock_filtered = SheetService._category_filter(df_stock, category)
        stock_items = (
            df_stock_filtered.sort_values("현재재고", ascending=False)
            .to_dict(orient="records")
            if not df_stock_filtered.empty else []
        )
        return {
            "total_anomalies": len(anomalies),
            "severity_counts": severity_counts,
            "stock_items":     stock_items,
        }

    @staticmethod
    def get_abc_stats(days: int, category: str | None = None) -> dict:
        from app.analyzer.abc_analyzer import run_abc_analysis
        df_master = read_product_master()
        df_sales  = read_sales()
        if category:
            df_master = SheetService._category_filter(df_master, category)
        return {"days": days, "items": run_abc_analysis(df_master, df_sales, days=days)}

    @staticmethod
    def get_demand_stats(
            forecast_days: int, page: int, page_size: int, category: str | None,
    ) -> dict:
        from app.analyzer.demand_forecaster import run_demand_forecast_all   # ← 수정
        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()
        items = run_demand_forecast_all(df_master, df_sales, df_stock, forecast_days=forecast_days)
        categories = sorted({i.get("category","") for i in items if i.get("category")})
        if category:
            items = [i for i in items if i.get("category") == category]
        total       = len(items)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        return {
            "forecast_days": forecast_days,
            "categories":    categories,
            "total": total, "page": page,
            "page_size": page_size, "total_pages": total_pages,
            "items": items[start:start + page_size],
        }

    @staticmethod
    def get_turnover_stats(
            days: int, page: int, page_size: int, category: str | None,
    ) -> dict:
        from app.analyzer.turnover_analyzer import calc_inventory_turnover
        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()
        items = calc_inventory_turnover(df_master, df_sales, df_stock, days=days)
        categories = sorted({i.get("카테고리","") for i in items if i.get("카테고리")})
        if category:
            items = [i for i in items if i.get("카테고리") == category]
        total       = len(items)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        return {
            "days": days,
            "categories":    categories,
            "total": total, "page": page,
            "page_size": page_size, "total_pages": total_pages,
            "items": items[start:start + page_size],
        }


    @staticmethod
    def update_product(db: Session, code: str, body_dict: dict) -> dict:
        """상품 정보 수정 (name/category/safety_stock/status)"""
        from app.db.models import Product, ProductStatus
        from app.db.repository import get_product_by_code

        product = get_product_by_code(db, code)
        if not product:
            raise ValueError(f"상품을 찾을 수 없습니다: {code}")

        if body_dict.get("name")         is not None: product.name = body_dict["name"]
        if body_dict.get("category")     is not None: product.category = body_dict["category"]
        if body_dict.get("safety_stock") is not None: product.safety_stock = body_dict["safety_stock"]
        if body_dict.get("status")       is not None:
            try:
                product.status = ProductStatus(body_dict["status"].upper())
            except ValueError:
                raise ValueError(f"유효하지 않은 상태값: {body_dict['status']}")

        db.commit()
        db.refresh(product)
        return {
            "code":         product.code,
            "name":         product.name,
            "category":     product.category,
            "safety_stock": product.safety_stock,
            "status":       product.status.value.lower(),
        }