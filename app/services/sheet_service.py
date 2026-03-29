
# 데이터 조회/필터/페이징/CSV다운로드/통계 분석 전담

from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session



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
    def get_sales_stats(
            db: Session,
            period: str, category: str | None = None,
    ) -> dict:
        from datetime import date, timedelta
        from sqlalchemy import func
        from app.db.models import DailySales, Product

        # category 필터가 있으면 products JOIN 필요
        if category:
            query = (
                db.query(
                    DailySales.date,
                    func.sum(DailySales.qty).label("판매수량"),
                    func.sum(DailySales.revenue).label("매출액"),
                )
                .join(Product, DailySales.product_code == Product.code, isouter=True)
                .filter(Product.category == category)
            )
        else:
            query = db.query(
                DailySales.date,
                func.sum(DailySales.qty).label("판매수량"),
                func.sum(DailySales.revenue).label("매출액"),
            )

        today = date.today()

        if period == "daily":
            cutoff = today - timedelta(days=29)
            rows = (
                query.filter(DailySales.date >= cutoff)
                .group_by(DailySales.date)
                .order_by(DailySales.date)
                .all()
            )
            items = [
                {"날짜": str(r.date), "판매수량": r.판매수량 or 0, "매출액": r.매출액 or 0}
                for r in rows
            ]

        elif period == "weekly":
            cutoff = today - timedelta(weeks=12)
            rows = (
                query.filter(DailySales.date >= cutoff)
                .group_by(DailySales.date)
                .order_by(DailySales.date)
                .all()
            )
            # 주 단위 집계 (Monday 기준)
            weekly: dict[str, dict] = {}
            for r in rows:
                week_start = r.date - timedelta(days=r.date.weekday())
                key = str(week_start)
                if key not in weekly:
                    weekly[key] = {"날짜": key, "판매수량": 0, "매출액": 0}
                weekly[key]["판매수량"] += r.판매수량 or 0
                weekly[key]["매출액"]   += r.매출액   or 0
            items = sorted(weekly.values(), key=lambda x: x["날짜"])

        elif period == "monthly":
            rows = (
                query
                .group_by(DailySales.date)
                .order_by(DailySales.date)
                .all()
            )
            # 월 단위 집계 (YYYY-MM)
            monthly: dict[str, dict] = {}
            for r in rows:
                key = r.date.strftime("%Y-%m")
                if key not in monthly:
                    monthly[key] = {"날짜": key, "판매수량": 0, "매출액": 0}
                monthly[key]["판매수량"] += r.판매수량 or 0
                monthly[key]["매출액"]   += r.매출액   or 0
            items = sorted(monthly.values(), key=lambda x: x["날짜"])

        else:
            return {"error": "period는 daily/weekly/monthly 중 하나"}

        return {"period": period, "items": items}


    @staticmethod
    def get_stock_stats(
            db: Session,
            category: str | None = None,
    ) -> dict:
        from app.db.models import StockLevel, Product
        from app.analyzer.stock_analyzer import run_stock_analysis
        from app.utils.severity import norm

        query = (
            db.query(StockLevel, Product)
            .outerjoin(Product, StockLevel.product_code == Product.code)
        )
        if category:
            query = query.filter(Product.category == category)

        rows = query.order_by(StockLevel.current_stock.desc()).all()

        stock_items = [
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

        # 이상징후 분석
        import pandas as pd
        all_products = db.query(Product).all()
        all_stock    = db.query(StockLevel).all()

        df_master = pd.DataFrame([
            {"상품코드": p.code, "상품명": p.name, "카테고리": p.category or "", "안전재고기준": p.safety_stock}
            for p in all_products
        ]) if all_products else pd.DataFrame()

        df_stock = pd.DataFrame([
            {"상품코드": s.product_code, "현재재고": s.current_stock,
             "입고예정일": str(s.restock_date) if s.restock_date else "",
             "입고예정수량": s.restock_qty or 0}
            for s in all_stock
        ]) if all_stock else pd.DataFrame()

        # 판매 데이터 조회
        from app.db.repository import get_daily_sales_range
        from datetime import date, timedelta
        sales_rows = get_daily_sales_range(
            db,
            start=date.today() - timedelta(days=30),
            end=date.today(),
        )
        df_sales = pd.DataFrame([
            {"날짜": str(s.date), "상품코드": s.product_code, "판매수량": s.qty, "매출액": s.revenue}
            for s in sales_rows
        ]) if sales_rows else pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"])

        anomalies = run_stock_analysis(df_master, df_stock, df_sales) if not df_master.empty else []

        severity_counts: dict[str, int] = {}
        for a in anomalies:
            sev = norm(a.get("severity", ""))
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "total_anomalies": len(anomalies),
            "severity_counts": severity_counts,
            "stock_items":     stock_items,
        }

    # abc 분석
    @staticmethod
    def get_abc_stats(
            db: Session,
            days: int, category: str | None = None,
    ) -> dict:
        from app.db.sync import make_params_hash
        from app.cache.redis_client import cache_get, cache_set
        from app.db.repository import get_analysis_cache

        params_hash = make_params_hash({"days": days, "category": category})
        cache_key   = f"analysis:abc:{params_hash}"

        # Redis HIT
        cached = cache_get(cache_key)
        if cached is not None:
            return {"days": days, "items": cached, "from_cache": True}

        # DB analysis_cache HIT
        db_hit = get_analysis_cache(db, "abc", params_hash, max_age_minutes=30)
        if db_hit:
            import json
            items = json.loads(db_hit.result_json).get("items", [])
            cache_set(cache_key, items, ttl=60 * 30)
            return {"days": days, "items": items, "from_cache": True}

        # MISS → Celery task 발행
        from app.celery_app.celery import celery_app
        task = celery_app.send_task(
            "app.celery_app.tasks.run_abc_analysis_task",
            kwargs={"days": days},
        )
        return {"task_id": task.id, "status": "PENDING", "from_cache": False}


    # 수요 예측
    @staticmethod
    def get_demand_stats(
            db: Session,
            forecast_days: int, page: int, page_size: int,
            category: str | None,
    ) -> dict:
        from app.db.sync import make_params_hash
        from app.cache.redis_client import cache_get, cache_set
        from app.db.repository import get_analysis_cache

        params_hash = make_params_hash({"forecast_days": forecast_days, "category": category})
        cache_key   = f"analysis:demand:{params_hash}"

        # Redis HIT
        cached = cache_get(cache_key)
        if cached is not None:
            items = cached if category is None else [i for i in cached if i.get("category") == category]
            total       = len(items)
            total_pages = max(1, (total + page_size - 1) // page_size)
            start       = (page - 1) * page_size
            return {
                "forecast_days": forecast_days,
                "categories":    sorted({i.get("category", "") for i in cached if i.get("category")}),
                "total":         total,
                "page":          page,
                "page_size":     page_size,
                "total_pages":   total_pages,
                "items":         items[start:start + page_size],
                "from_cache":    True,
            }

        # DB analysis_cache HIT
        db_hit = get_analysis_cache(db, "demand", params_hash, max_age_minutes=30)
        if db_hit:
            import json
            all_items = json.loads(db_hit.result_json).get("items", [])
            cache_set(cache_key, all_items, ttl=60 * 30)
            items = all_items if category is None else [i for i in all_items if i.get("category") == category]
            total       = len(items)
            total_pages = max(1, (total + page_size - 1) // page_size)
            start       = (page - 1) * page_size
            return {
                "forecast_days": forecast_days,
                "categories":    sorted({i.get("category", "") for i in all_items if i.get("category")}),
                "total":         total,
                "page":          page,
                "page_size":     page_size,
                "total_pages":   total_pages,
                "items":         items[start:start + page_size],
                "from_cache":    True,
            }

        # MISS → Celery task 발행
        from app.celery_app.celery import celery_app
        task = celery_app.send_task(
            "app.celery_app.tasks.run_demand_forecast",
            kwargs={"forecast_days": forecast_days, "category": category},
        )
        return {"task_id": task.id, "status": "PENDING", "from_cache": False}



    # --- 재고 회전율 (캐시 → Celery task) ---
    @staticmethod
    def get_turnover_stats(
            db: Session,
            days: int, page: int, page_size: int,
            category: str | None,
    ) -> dict:
        from app.db.sync import make_params_hash
        from app.cache.redis_client import cache_get, cache_set
        from app.db.repository import get_analysis_cache

        params_hash = make_params_hash({"days": days, "category": category})
        cache_key   = f"analysis:turnover:{params_hash}"

        # Redis HIT
        cached = cache_get(cache_key)
        if cached is not None:
            items = cached if category is None else [i for i in cached if i.get("카테고리") == category]
            total       = len(items)
            total_pages = max(1, (total + page_size - 1) // page_size)
            start       = (page - 1) * page_size
            return {
                "days":        days,
                "categories":  sorted({i.get("카테고리", "") for i in cached if i.get("카테고리")}),
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": total_pages,
                "items":       items[start:start + page_size],
                "from_cache":  True,
            }

        # DB analysis_cache HIT
        db_hit = get_analysis_cache(db, "turnover", params_hash, max_age_minutes=30)
        if db_hit:
            import json
            all_items = json.loads(db_hit.result_json).get("items", [])
            cache_set(cache_key, all_items, ttl=60 * 30)
            items = all_items if category is None else [i for i in all_items if i.get("카테고리") == category]
            total       = len(items)
            total_pages = max(1, (total + page_size - 1) // page_size)
            start       = (page - 1) * page_size
            return {
                "days":        days,
                "categories":  sorted({i.get("카테고리", "") for i in all_items if i.get("카테고리")}),
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": total_pages,
                "items":       items[start:start + page_size],
                "from_cache":  True,
            }

        # MISS → Celery task 발행
        from app.celery_app.celery import celery_app
        task = celery_app.send_task(
            "app.celery_app.tasks.run_turnover_analysis",
            kwargs={"days": days, "category": category},
        )
        return {"task_id": task.id, "status": "PENDING", "from_cache": False}


    @staticmethod
    def update_product(db: Session, code: str, body_dict: dict) -> dict:
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