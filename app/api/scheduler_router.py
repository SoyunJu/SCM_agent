
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.api.auth_router import get_current_user, TokenData
from app.db.connection import get_db
from app.db.repository import upsert_schedule_config, get_schedule_config
from sqlalchemy.orm import Session

router = APIRouter(prefix="/scm/scheduler", tags=["scheduler"])


class ScheduleUpdateRequest(BaseModel):
    schedule_hour: int
    schedule_minute: int
    timezone: str = "Asia/Seoul"
    is_active: bool = True


@router.get("/config")
async def get_config(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):

    record = get_schedule_config(db, "daily_report")
    if not record:
        return {
            "job_name": "daily_report",
            "schedule_hour": 0,
            "schedule_minute": 0,
            "timezone": "Asia/Seoul",
            "is_active": True,
            "last_run_at": None,
        }
    return {
        "job_name": record.job_name,
        "schedule_hour": record.schedule_hour,
        "schedule_minute": record.schedule_minute,
        "timezone": record.timezone,
        "is_active": record.is_active,
        "last_run_at": str(record.last_run_at) if record.last_run_at else None,
    }


@router.put("/config")
async def update_config(
        req: ScheduleUpdateRequest,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):

    if not (0 <= req.schedule_hour <= 23):
        raise HTTPException(status_code=400, detail="schedule_hour는 0~23 사이여야 합니다.")
    if not (0 <= req.schedule_minute <= 59):
        raise HTTPException(status_code=400, detail="schedule_minute는 0~59 사이여야 합니다.")

    # DB 저장
    upsert_schedule_config(
        db=db,
        job_name="daily_report",
        schedule_hour=req.schedule_hour,
        schedule_minute=req.schedule_minute,
        timezone=req.timezone,
        is_active=req.is_active,
    )

    try:
        from app.main import scheduler
        from apscheduler.triggers.cron import CronTrigger
        import pytz
        from app.scheduler.jobs import run_daily_job

        scheduler.reschedule_job(
            job_id="daily_report",
            trigger=CronTrigger(
                hour=req.schedule_hour,
                minute=req.schedule_minute,
                timezone=pytz.timezone(req.timezone),
            ),
        )
        logger.info(f"스케줄 수정 완료: {req.schedule_hour:02d}:{req.schedule_minute:02d}")
    except Exception as e:
        logger.warning(f"APScheduler 즉시 반영 실패 (재시작 후 적용): {e}")

    return {
        "message": "스케줄이 업데이트되었습니다.",
        "schedule_hour": req.schedule_hour,
        "schedule_minute": req.schedule_minute,
        "timezone": req.timezone,
        "is_active": req.is_active,
    }


@router.get("/status")
async def scheduler_status(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    try:
        from app.main import scheduler
        jobs = scheduler.get_jobs()
        return {
            "running": scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time),
                }
                for job in jobs
            ],
        }
    except Exception as e:
        return {"running": False, "jobs": [], "error": str(e)}