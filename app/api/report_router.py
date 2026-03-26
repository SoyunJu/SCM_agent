from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import os

from app.api.auth_router import get_current_user, TokenData
from app.db.connection import get_db
from app.db.models import ReportExecution
from app.db.repository import (
    get_report_executions, get_report_execution_by_id,
    get_anomaly_logs, resolve_anomaly,
    create_report_execution, update_report_execution,
)
from app.db.models import ExecutionStatus, ReportType
from app.scheduler.jobs import run_daily_job
from loguru import logger
from sqlalchemy.orm import Session

router = APIRouter(prefix="/scm/report", tags=["report"])


class ReportRequest(BaseModel):
    severity_filter: list[str] | None = None   # ["critical", "high"]
    category_filter: list[str] | None = None   # ["Fiction", "Music"]


@router.post("/run")
async def trigger_report(
        req: ReportRequest = Body(default_factory=ReportRequest),
        current_user: Annotated[TokenData, Depends(get_current_user)] = None,
        db: Session = Depends(get_db),
):
    record = create_report_execution(db, report_type=ReportType.MANUAL)

    async def _run():
        from app.db.connection import SessionLocal
        job_db = SessionLocal()
        try:
            await asyncio.to_thread(
                run_daily_job,
                record.id,
                req.severity_filter,
                req.category_filter,
            )
        except Exception as e:
            update_report_execution(job_db, record.id, ExecutionStatus.FAILURE, error_message=str(e))
        finally:
            job_db.close()

    asyncio.create_task(_run())
    logger.info(f"보고서 수동 트리거: user={current_user.username}, id={record.id}, filters={req}")
    return {
        "status": "triggered",
        "execution_id": record.id,
        "message": "보고서 생성이 시작되었습니다.",
    }


@router.get("/status/{execution_id}")
async def get_report_status(
        execution_id: int,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    record = get_report_execution_by_id(db, execution_id)
    if not record:
        raise HTTPException(status_code=404, detail="실행 이력을 찾을 수 없습니다.")
    return {
        "id":            record.id,
        "status":        record.status,
        "error_message": record.error_message,
        "executed_at":   str(record.executed_at),
    }


@router.get("/history")
async def get_history(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        limit: int = 5,
        offset: int = 0,
        period: str | None = None,
        status: str | None = None,
        db: Session = Depends(get_db),
):
    records = get_report_executions(db, limit=500)

    if period:
        now = datetime.now()
        cutoff_map = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1), "monthly": timedelta(days=30)}
        cutoff = now - cutoff_map.get(period, timedelta(days=1))
        records = [r for r in records if r.created_at and r.created_at >= cutoff]

    if status and status != "all":
        records = [r for r in records if r.status.value == status]

    total = len(records)
    records = records[offset: offset + limit]

    return {
        "total":  total,
        "offset": offset,
        "limit":  limit,
        "items": [
            {
                "id": r.id, "executed_at": str(r.executed_at),
                "report_type": r.report_type, "status": r.status,
                "slack_sent": r.slack_sent, "error_message": r.error_message,
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
    return {"deleted": True, "id": record_id}


@router.delete("/pdf/{filename}")
async def delete_pdf(
        filename: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")
    pdf_path = Path("reports") / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    os.remove(pdf_path)
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
                "id": r.id, "detected_at": str(r.detected_at),
                "product_code": r.product_code, "product_name": r.product_name,
                "category": r.category,
                "anomaly_type": r.anomaly_type, "current_stock": r.current_stock,
                "daily_avg_sales": r.daily_avg_sales, "days_until_stockout": r.days_until_stockout,
                "severity": r.severity, "is_resolved": r.is_resolved,
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
    return {"id": record.id, "is_resolved": record.is_resolved}


@router.get("/pdf/{filename}")
async def download_pdf(
        filename: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    pdf_path = Path("reports") / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF 파일을 찾을 수 없습니다.")
    return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=filename)


@router.get("/pdf-list")
async def list_pdfs(current_user: Annotated[TokenData, Depends(get_current_user)]):
    reports_dir = Path("reports")
    if not reports_dir.exists():
        return {"items": []}
    files = sorted(reports_dir.glob("*.pdf"), reverse=True)
    return {
        "items": [
            {"filename": f.name, "size_kb": round(f.stat().st_size / 1024, 1), "created_at": str(f.stat().st_mtime)}
            for f in files
        ]
    }
