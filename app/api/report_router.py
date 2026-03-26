
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import os

from app.api.auth_router import get_current_user, TokenData
from app.db.connection import get_db
from app.db.models import ReportExecution
from app.db.repository import (
    get_report_executions,
    get_anomaly_logs,
    resolve_anomaly,
)
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
        period: str | None = None,   # daily | weekly | monthly
        status: str | None = None,   # success | failure | in_progress
        db: Session = Depends(get_db),
):

    records = get_report_executions(db, limit=100)

    # 기간 필터
    if period:
        now = datetime.now()
        if period == "daily":
            cutoff = now - timedelta(days=1)
        elif period == "weekly":
            cutoff = now - timedelta(weeks=1)
        elif period == "monthly":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = None
        if cutoff:
            records = [r for r in records if r.created_at and r.created_at >= cutoff]

    # 상태 필터
    if status and status != "all":
        records = [r for r in records if r.status.value == status]

    records = records[:limit]

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


@router.delete("/history/{record_id}")
async def delete_report_history(
        record_id: int,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):

    record = db.query(ReportExecution).filter(ReportExecution.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없습니다.")
    db.delete(record)
    db.commit()
    logger.info(f"보고서 이력 삭제: id={record_id}, user={current_user.username}")
    return {"deleted": True, "id": record_id}


@router.delete("/pdf/{filename}")
async def delete_pdf(
        filename: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):

    # 경로 순회 공격 방지
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")
    pdf_path = Path("reports") / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    os.remove(pdf_path)
    logger.info(f"PDF 삭제: {filename}, user={current_user.username}")
    return {"deleted": True, "filename": filename}


@router.get("/anomalies")
async def get_anomalies(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        is_resolved: bool | None = None,
        anomaly_type: str | None = None,
        severity: str | None = None,
        limit: int = 50,
        db: Session = Depends(get_db),
):

    records = get_anomaly_logs(db, is_resolved=is_resolved, limit=limit)

    if anomaly_type:
        records = [r for r in records if r.anomaly_type.value == anomaly_type]
    if severity:
        records = [r for r in records if r.severity.value == severity]

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


@router.patch("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly_endpoint(
        anomaly_id: int,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):

    record = resolve_anomaly(db, anomaly_id)
    if not record:
        raise HTTPException(status_code=404, detail="이상 징후를 찾을 수 없습니다.")
    logger.info(f"이상 징후 해결: id={anomaly_id}, user={current_user.username}")
    return {"id": record.id, "is_resolved": record.is_resolved}


@router.get("/pdf/{filename}")
async def download_pdf(
        filename: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):

    pdf_path = Path("reports") / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없습니다.")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
    )


@router.get("/pdf-list")
async def list_pdfs(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):

    reports_dir = Path("reports")
    if not reports_dir.exists():
        return {"items": []}
    files = sorted(reports_dir.glob("*.pdf"), reverse=True)
    return {
        "items": [
            {
                "filename": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "created_at": str(Path(f).stat().st_mtime),
            }
            for f in files
        ]
    }