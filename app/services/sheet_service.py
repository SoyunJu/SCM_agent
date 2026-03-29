
# 데이터 조회/필터/페이징/CSV다운로드/통계 분석 전담

from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.sheets.reader import read_product_master, read_sales, read_stock
from app.sheets.writer import write_order_proposals


class SheetService:

    # ── Helper ──────────────────────────────────────

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

    # ── 조회 ──────────────────────────────────────

    @staticmethod
    def get_categories(db: Session) -> list[str]:
        from app.db.models import Product
        rows = (
            db.query(Product.category)
            .filter(Product.category.isnot(None), Product.category != "")
            .distinct()
            .order_by(Product.category)
            .all()
        )
        return [r.category for r in rows if r.category]


    @staticmethod
    def get_master(
            db: Session,
            page: int, page_size: int,
            search: str | None, category: str | None, download: bool,
    ):
        from app.db.repository import get_products_paginated

        result = get_products_paginated(
            db, page=page, page_size=page_size,
            search=search, category=category,
        )

        items = [
            {
                "상품코드":     p.code,
                "상품명":       p.name,
                "카테고리":     p.category or "",
                "안전재고기준": p.safety_stock,
                "상태":         p.status.value.lower(),
            }
            for p in result["items"]
        ]

        if download:
            return SheetService._to_csv(pd.DataFrame(items), "master.csv")

        return {
            "total":       result["total"],
            "page":        result["page"],
            "page_size":   result["page_size"],
            "total_pages": max(1, (result["total"] + page_size - 1) // page_size),
            "items":       items,
        }


    @staticmethod
    def get_sales(
            db: Session,
            days: int, page: int, page_size: int,
            search: str | None, category: str | None, download: bool,
    ):
        """DB daily_sales + products JOIN 기반 조회"""
        from app.db.models import DailySales, Product

        cutoff = date.today() - timedelta(days=days)

        query = (
            db.query(DailySales, Product)
            .outerjoin(Product, DailySales.product_code == Product.code)
            .filter(DailySales.date >= cutoff)
        )
        if search:
            query = query.filter(
                DailySales.product_code.contains(search) |
                Product.name.contains(search)
            )
        if category:
            query = query.filter(Product.category == category)

        total = query.count()
        rows  = (
            query.order_by(DailySales.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = [
            {
                "날짜":       str(sale.date),
                "상품코드":   sale.product_code,
                "상품명":     prod.name   if prod else "",
                "카테고리":   prod.category if prod else "",
                "판매수량":   sale.qty,
                "매출액":     sale.revenue,
                "매입액":     sale.cost,
                "차액(수익)": sale.revenue - sale.cost,
            }
            for sale, prod in rows
        ]

        if download:
            return SheetService._to_csv(pd.DataFrame(items), "sales.csv")

        return {
            "total":       total,
            "page":        page,
            "page_size":   page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "items":       items,
        }


    @staticmethod
    def get_stock(
            db: Session,
            page: int, page_size: int,
            search: str | None, category: str | None, download: bool,
    ):
        """DB stock_levels + products JOIN 기반 조회"""
        from app.db.models import StockLevel, Product

        query = (
            db.query(StockLevel, Product)
            .outerjoin(Product, StockLevel.product_code == Product.code)
        )
        if search:
            query = query.filter(
                StockLevel.product_code.contains(search) |
                Product.name.contains(search)
            )
        if category:
            query = query.filter(Product.category == category)

        total = query.count()
        rows  = (
            query.order_by(StockLevel.current_stock.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = [
            {
                "상품코드":     sl.product_code,
                "상품명":       prod.name     if prod else "",
                "카테고리":     prod.category if prod else "",
                "현재재고":     sl.current_stock,
                "안전재고":     prod.safety_stock if prod else 0,
                "입고예정일":   str(sl.restock_date) if sl.restock_date else "",
                "입고예정수량": sl.restock_qty or 0,
            }
            for sl, prod in rows
        ]

        if download:
            return SheetService._to_csv(pd.DataFrame(items), "stock.csv")

        return {
            "total":       total,
            "page":        page,
            "page_size":   page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "items":       items,
        }


    @staticmethod
    def get_orders(
            db: Session,
            status: str | None, days: int,
            page: int, page_size: int,
    ) -> dict:
        from app.services.order_service import OrderService
        offset = (page - 1) * page_size
        return OrderService.list_proposals(db, status, limit=page_size, offset=offset, days=days)


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
        from app.db.models import ProductStatus
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