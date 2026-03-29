from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.services.report_service  import ReportService
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/scm/report", tags=["report"])


class ReportRequest(BaseModel):
    severity_filter: list[str] | None = None
    category_filter: list[str] | None = None


# --- 보고서 ---

@router.post("/run")
async def trigger_report(
        req: ReportRequest = Body(default_factory=ReportRequest),
        current_user: Annotated[TokenData, Depends(get_current_user)] = None,
        db: Session = Depends(get_db),
):
    return ReportService.trigger(
        db, current_user.username, req.severity_filter, req.category_filter
    )


@router.get("/status/{execution_id}")
async def get_report_status(
        execution_id: int,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    return ReportService.get_status(db, execution_id)


@router.get("/history")
async def get_history(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        limit:  int = 5, offset: int = 0,
        period: str | None = None, status: str | None = None,
        db: Session = Depends(get_db),
):
    return ReportService.get_history(db, limit, offset, period, status)


@router.delete("/history/{record_id}")
async def delete_report_history(
        record_id: int,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    return ReportService.delete_history(db, record_id)


# --- PDF ---

@router.get("/pdf-list")
async def list_pdfs(current_user: Annotated[TokenData, Depends(get_current_user)]):
    return ReportService.list_pdfs()


@router.get("/pdf/{filename}")
async def download_pdf(
        filename: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "잘못된 파일명입니다.")
    pdf_path = Path("reports") / filename
    if not pdf_path.exists():
        raise HTTPException(404, "PDF 파일을 찾을 수 없습니다.")
    return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=filename)


@router.delete("/pdf/{filename}")
async def delete_pdf(
        filename: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    return ReportService.delete_pdf(filename)


# --- 이상징후 ---

@router.get("/anomalies")
async def get_anomalies(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        is_resolved:  bool | None = None,
        anomaly_type: str | None = None,
        severity:     str | None = None,
        page:      int = 1,
        page_size: int = 50,
        db: Session = Depends(get_db),
):
    return AnomalyService.list_anomalies(
        db, is_resolved, anomaly_type, severity, page, page_size
    )


@router.patch("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(
        anomaly_id: int,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    return AnomalyService.resolve(db, anomaly_id)