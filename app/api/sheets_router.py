
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
):

    try:
        df = read_product_master()
        return {"total": len(df), "items": df.to_dict(orient="records")}
    except Exception as e:
        logger.error(f"상품마스터 조회 실패: {e}")
        return {"total": 0, "items": [], "error": str(e)}


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
    """재고 현황 통계 (심각도별 카운트 + 상품별 재고)"""
    try:
        import pandas as pd
        from app.db.connection import SessionLocal
        from app.db.repository import get_anomaly_logs

        df_stock = read_stock()
        df_master = read_product_master()
        df = df_master.merge(df_stock, on="상품코드", how="inner")

        # 상품별 재고 (상위 20개)
        stock_items = df.nlargest(20, "현재재고")[["상품코드", "상품명", "현재재고"]].to_dict(orient="records")

        # 심각도별 미해결 이상 징후 카운트
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