
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.db.connection import get_db
from app.db.repository import upsert_schedule_config, get_schedule_config
from sqlalchemy.orm import Session
from app.api.auth_router import get_current_user, require_admin, TokenData


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
        current_user: Annotated[TokenData, Depends(require_admin)],
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


# 1분 간격 스케줄러

import asyncio
from typing import Any

_sync_scheduler: Any = None

class SyncScheduleRequest(BaseModel):
    interval_seconds: int = 60   # 기본 1분
    is_active: bool = True


@router.get("/sync-config")
async def get_sync_config(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    global _sync_scheduler
    is_running = _sync_scheduler is not None and _sync_scheduler.running
    return {
        "is_active":        is_running,
        "interval_seconds": 60,
        "description":      "Sheets(화면SoT) → DB(실제SoT) 단방향 동기화",
    }


# Sheets→DB 동기화
@router.post("/sync-start")
async def start_sync_schedule(
        req: SyncScheduleRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    global _sync_scheduler
    from app.scheduler.jobs import sync_sheets_to_db_incremental
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    if _sync_scheduler and _sync_scheduler.running:
        _sync_scheduler.shutdown(wait=False)

    _sync_scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    _sync_scheduler.add_job(
        func=sync_sheets_to_db_incremental,
        trigger=IntervalTrigger(seconds=max(30, req.interval_seconds)),
        id="sheets_to_db_sync",
        replace_existing=True,
    )
    _sync_scheduler.start()
    logger.info(f"Sheets→DB 주기 동기화 시작: {req.interval_seconds}초 간격")
    return {"status": "started", "interval_seconds": req.interval_seconds}



@router.post("/sync-stop")
async def stop_sync_schedule(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    global _sync_scheduler
    try:
        if _sync_scheduler and getattr(_sync_scheduler, "running", False):
            _sync_scheduler.shutdown(wait=False)
            _sync_scheduler = None
            logger.info("Sheets→DB 주기 동기화 중지")
            return {"status": "stopped"}
    except Exception as e:
        logger.warning(f"스케줄러 중지 실패(무시): {e}")
        _sync_scheduler = None
    return {"status": "already_stopped"}