from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import ReportExecution, ReportType, ExecutionStatus
from app.db.repository import (
    create_report_execution, update_report_execution,
    get_report_executions, get_report_execution_by_id,
)


class ReportService:

    # --- TRIGGER ---
    @staticmethod
    def trigger(
            db: Session,
            username: str,
            severity_filter: list[str] | None = None,
            category_filter: list[str] | None = None,
    ) -> dict:
        record = create_report_execution(db, report_type=ReportType.MANUAL, triggered_by=username)

        async def _run():
            from app.db.connection import SessionLocal
            from app.scheduler.jobs import run_daily_job
            job_db = SessionLocal()
            try:
                await asyncio.to_thread(
                    run_daily_job, record.id, severity_filter, category_filter
                )
            except Exception as e:
                update_report_execution(job_db, record.id, ExecutionStatus.FAILURE, error_message=str(e))
            finally:
                job_db.close()

        asyncio.create_task(_run())
        logger.info(f"[ReportService] 보고서 트리거: user={username}, id={record.id}")
        return {"status": "triggered", "execution_id": record.id}


    # --- GET STATUS ---
    @staticmethod
    def get_status(db: Session, execution_id: int) -> dict:
        from fastapi import HTTPException
        record = get_report_execution_by_id(db, execution_id)
        if not record:
            raise HTTPException(404, "실행 이력을 찾을 수 없습니다.")

        status = record.status
        if record.status == ExecutionStatus.IN_PROGRESS and record.created_at:
            if (datetime.utcnow() - record.created_at).total_seconds() > 600:
                update_report_execution(db, record.id, ExecutionStatus.FAILURE, error_message="실행 시간 초과 (10분)")
                status = ExecutionStatus.FAILURE

        return {
            "id":            record.id,
            "status":        status,
            "error_message": record.error_message,
            "docs_url":      record.docs_url,
        }


    # --- GET HISTORY ---
    @staticmethod
    def get_history(
            db: Session, limit: int, offset: int,
            period: str | None, status: str | None,
    ) -> dict:
        records = get_report_executions(db, limit=500)
        if period:
            cutoff_map = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1), "monthly": timedelta(days=30)}
            cutoff = datetime.now() - cutoff_map.get(period, timedelta(days=1))
            records = [r for r in records if r.created_at and r.created_at >= cutoff]
        if status and status != "all":
            records = [r for r in records if r.status.value == status]

        total   = len(records)
        records = records[offset:offset + limit]
        return {
            "total": total, "offset": offset, "limit": limit,
            "items": [
                {
                    "id":           r.id,
                    "executed_at":  str(r.executed_at)[:19] if r.executed_at else "",
                    "report_type":  r.report_type.value if hasattr(r.report_type, "value") else str(r.report_type),
                    "status":       r.status.value if hasattr(r.status, "value") else str(r.status),
                    "slack_sent":   r.slack_sent,
                    "email_sent":   getattr(r, "email_sent", False),
                    "triggered_by": getattr(r, "triggered_by", None),
                    "created_at":   str(r.created_at)[:19] if r.created_at else "",
                }
                for r in records
            ],
        }


    @staticmethod
    def list_pdfs() -> dict:
        from pathlib import Path
        reports_dir = Path("reports")
        if not reports_dir.exists():
            return {"items": [], "total": 0}
        try:
            files = sorted(reports_dir.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)
            return {
                "items": [
                    {
                        "filename":   f.name,
                        "size_kb":    round(f.stat().st_size / 1024, 1),
                        "created_at": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                    }
                    for f in files
                ],
                "total": len(files),
            }
        except Exception as e:
            logger.warning(f"PDF 목록 조회 실패: {e}")
            return {"items": [], "total": 0}