
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from loguru import logger
import asyncio
import json

from app.api.auth_router import get_current_user, TokenData
from app.sheets.reader import read_product_master, read_sales, read_stock

router = APIRouter(prefix="/scm/sheets", tags=["sheets"])


@router.get("/master")
async def get_master(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
):

    try:
        page_size = min(page_size, 200)   # 최대 200건 제한
        df = read_product_master()

        # 검색 필터
        if search:
            mask = (
                    df["상품명"].str.contains(search, case=False, na=False) |
                    df["상품코드"].str.contains(search, case=False, na=False)
            )
            df = df[mask]

        total = len(df)
        total_pages = max(1, (total + page_size - 1) // page_size)

        # 페이징
        start = (page - 1) * page_size
        end   = start + page_size
        page_df = df.iloc[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "items": page_df.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"상품마스터 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size,
                "total_pages": 0, "items": [], "error": str(e)}


@router.get("/sales")
async def get_sales(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30,
):

    try:
        import pandas as pd
        df = read_sales()
        df["날짜"] = pd.to_datetime(df["날짜"])
        cutoff = df["날짜"].max() - pd.Timedelta(days=days)
        df = df[df["날짜"] >= cutoff].copy()
        df["날짜"] = df["날짜"].dt.strftime("%Y-%m-%d")
        return {"total": len(df), "items": df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"일별판매 조회 실패: {e}")
        return {"total": 0, "items": [], "error": str(e)}


@router.get("/stock")
async def get_stock(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):

    try:
        df = read_stock()
        return {"total": len(df), "items": df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"재고현황 조회 실패: {e}")
        return {"total": 0, "items": [], "error": str(e)}


@router.get("/stats/sales")
async def get_sales_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        period: str = "daily",  # daily | weekly | monthly
):

    try:
        import pandas as pd
        df = read_sales()
        df["날짜"] = pd.to_datetime(df["날짜"])

        if period == "daily":
            cutoff = df["날짜"].max() - pd.Timedelta(days=29)
            df = df[df["날짜"] >= cutoff]
            agg = (
                df.groupby("날짜")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index()
                .sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "weekly":
            cutoff = df["날짜"].max() - pd.Timedelta(weeks=12)
            df = df[df["날짜"] >= cutoff]
            df["주"] = df["날짜"].dt.to_period("W").dt.start_time
            agg = (
                df.groupby("주")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index()
                .rename(columns={"주": "날짜"})
                .sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "monthly":
            df["월"] = df["날짜"].dt.to_period("M").dt.start_time
            agg = (
                df.groupby("월")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index()
                .rename(columns={"월": "날짜"})
                .sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m")

        else:
            return {"error": "period는 daily/weekly/monthly 중 하나여야 합니다."}

        return {
            "period": period,
            "items": agg.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"판매 통계 조회 실패: {e}")
        return {"period": period, "items": [], "error": str(e)}


@router.get("/stats/stock")
async def get_stock_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    try:
        import pandas as pd
        from app.db.connection import SessionLocal
        from app.db.repository import get_anomaly_logs

        df_stock  = read_stock()
        df = df_master.merge(df_stock, on="상품코드", how="left")

        df["현재재고"] = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0).astype(int)

        stock_items = (
            df[df["현재재고"] > 0]
            .nlargest(20, "현재재고")[["상품코드", "상품명", "현재재고"]]
            .to_dict(orient="records")
        )

        db = SessionLocal()
        try:
            records = get_anomaly_logs(db, is_resolved=False, limit=200)
        finally:
            db.close()

        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in records:
            sev = r.severity.value
            if sev in severity_counts:
                severity_counts[sev] += 1

        return {
            "stock_items": stock_items,
            "severity_counts": severity_counts,
            "total_anomalies": len(records),
        }
    except Exception as e:
        logger.error(f"재고 통계 조회 실패: {e}")
        return {"stock_items": [], "severity_counts": {}, "error": str(e)}




@router.post("/sync")
async def sync_sheets(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):

    import asyncio
    from app.scheduler.jobs import sync_sheets_only

    asyncio.create_task(asyncio.to_thread(sync_sheets_only))
    logger.info(f"Sheets 동기화 트리거: {current_user.username}")
    return {"status": "triggered", "message": "데이터 동기화가 시작되었습니다."}



@router.get("/orders")
async def get_orders(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        status: str | None = None,
        days: int = 90,
        page: int = 1,
        page_size: int = 50,
):

    try:
        import pandas as pd
        from app.sheets.reader import read_orders
        df = read_orders()
        if df.empty:
            return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}

        if "발주일" in df.columns:
            df["발주일"] = pd.to_datetime(df["발주일"], errors="coerce")
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df["발주일"] >= cutoff].copy()
            df["발주일"] = df["발주일"].dt.strftime("%Y-%m-%d")

        if status:
            df = df[df["상태"] == status]

        total       = len(df)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        page_df     = df.iloc[start: start + page_size]

        return {
            "total": total, "page": page,
            "page_size": page_size, "total_pages": total_pages,
            "items": page_df.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"주문 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": [], "error": str(e)}



@router.get("/stats/abc")
async def get_abc_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 90,
):
    try:
        import pandas as pd
        from app.analyzer.abc_analyzer import run_abc_analysis

        df_master = read_product_master()
        df_sales  = read_sales()
        items     = run_abc_analysis(df_master, df_sales, days=days)
        return {"days": days, "items": items}
    except Exception as e:
        logger.error(f"ABC 분석 조회 실패: {e}")
        return {"days": days, "items": [], "error": str(e)}


@router.get("/stats/demand")
async def get_demand_forecast(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        forecast_days: int = 14,
):
    try:
        from app.analyzer.demand_forecaster import run_demand_forecast_all

        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()
        items     = run_demand_forecast_all(df_master, df_sales, df_stock, forecast_days=forecast_days)
        return {"forecast_days": forecast_days, "items": items}
    except Exception as e:
        logger.error(f"수요 예측 조회 실패: {e}")
        return {"forecast_days": forecast_days, "items": [], "error": str(e)}


@router.get("/stats/turnover")
async def get_turnover_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30,
):
    try:
        from app.analyzer.turnover_analyzer import calc_inventory_turnover

        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()
        items     = calc_inventory_turnover(df_master, df_sales, df_stock, days=days)
        return {"days": days, "items": items}
    except Exception as e:
        logger.error(f"재고 회전율 조회 실패: {e}")
        return {"days": days, "items": [], "error": str(e)}