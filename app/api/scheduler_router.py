from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scm/scheduler", tags=["scheduler"])


# ── Pydantic 스키마 ────────────────────────────────────────────────────────

class ScheduleUpdateRequest(BaseModel):
    schedule_hour:   int
    schedule_minute: int
    timezone:        str  = "Asia/Seoul"
    is_active:       bool = True


class SyncScheduleRequest(BaseModel):
    interval_seconds: int  = 60
    is_active:        bool = True


# ── 보고서 생성 스케줄 ─────────────────────────────────────────────────────

@router.get("/config")
async def get_config(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    return SchedulerService.get_config(db)


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

    return SchedulerService.update_config(
        db, req.schedule_hour, req.schedule_minute,
        req.timezone, req.is_active, current_user.username,
    )


@router.get("/status")
async def scheduler_status(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    return SchedulerService.get_status()


@router.post("/trigger")
async def trigger_daily_report(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    """보고서 즉시 실행 (Celery task 발행)"""
    try:
        return SchedulerService.trigger_daily_report()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Sheets→DB 동기화 ───────────────────────────────────────────────────────

@router.get("/sync-config")
async def get_sync_config(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    return SchedulerService.get_sync_config()


@router.post("/sync-start")
async def start_sync_schedule(
        req: SyncScheduleRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    return SchedulerService.start_sync(req.interval_seconds)


@router.post("/sync-stop")
async def stop_sync_schedule(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    return SchedulerService.stop_sync()