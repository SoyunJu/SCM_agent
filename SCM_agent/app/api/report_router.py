
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
import asyncio

from app.api.auth_router import get_current_user, TokenData
from app.db.connection import get_db
from app.db.repository import get_report_executions, get_anomaly_logs
from app.db.models import AnomalyType
from app.scheduler.jobs import run_daily_job
from loguru import logger
from sqlalchemy.orm import Session

router = APIRouter(prefix="/scm/report", tags=["report"])


@router.post("/run")
async def trigger_report(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):

    asyncio.create_task(asyncio.to_thread(run_daily_job))
    logger.info(f"보고서 수동 트리거: {current_user.username}")
    return {"status": "triggered", "message": "보고서 생성이 시작되었습니다."}



@router.get("/history")
async def get_history(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        limit: int = 20,
        db: Session = Depends(get_db),
):

    records = get_report_executions(db, limit=limit)
    return {
        "total": len(records),
        "items": [
            {
                "id": r.id,
                "executed_at": str(r.executed_at),
                "report_type": r.report_type,
                "status": r.status,
                "slack_sent": r.slack_sent,
                "error_message": r.error_message,
                "created_at": str(r.created_at),
            }
            for r in records
        ],
    }


@router.get("/anomalies")
async def get_anomalies(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        is_resolved: bool | None = None,
        limit: int = 50,
        db: Session = Depends(get_db),
):

    records = get_anomaly_logs(db, is_resolved=is_resolved, limit=limit)
    return {
        "total": len(records),
        "items": [
            {
                "id": r.id,
                "detected_at": str(r.detected_at),
                "product_code": r.product_code,
                "product_name": r.product_name,
                "anomaly_type": r.anomaly_type,
                "current_stock": r.current_stock,
                "daily_avg_sales": r.daily_avg_sales,
                "days_until_stockout": r.days_until_stockout,
                "severity": r.severity,
                "is_resolved": r.is_resolved,
            }
            for r in records
        ],
    }