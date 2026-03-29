
from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.db.repository import upsert_schedule_config, get_schedule_config

router = APIRouter(prefix="/scm/scheduler", tags=["scheduler"])

_sync_scheduler: Any = None


class ScheduleUpdateRequest(BaseModel):
    schedule_hour:   int
    schedule_minute: int
    timezone:        str  = "Asia/Seoul"
    is_active:       bool = True


class SyncScheduleRequest(BaseModel):
    interval_seconds: int  = 60
    is_active:        bool = True



# 보고서 생성 스케줄
@router.get("/config")
async def get_config(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    record = get_schedule_config(db, "daily_report")
    if not record:
        return {
            "job_name":       "daily_report",
            "schedule_hour":  0,
            "schedule_minute": 0,
            "timezone":       "Asia/Seoul",
            "is_active":      True,
            "last_run_at":    None,
        }
    return {
        "job_name":        record.job_name,
        "schedule_hour":   record.schedule_hour,
        "schedule_minute": record.schedule_minute,
        "timezone":        record.timezone,
        "is_active":       record.is_active,
        "last_run_at":     str(record.last_run_at) if record.last_run_at else None,
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

    upsert_schedule_config(
        db=db,
        job_name="daily_report",
        schedule_hour=req.schedule_hour,
        schedule_minute=req.schedule_minute,
        timezone=req.timezone,
        is_active=req.is_active,
    )
    logger.info(f"스케줄 설정 저장: {req.schedule_hour:02d}:{req.schedule_minute:02d} by {current_user.username}")

    # 실패시 다음 스케줄에 재시도
    try:
        from app.celery_app.celery import celery_app
        from celery.schedules import crontab
        celery_app.conf.beat_schedule["daily-report"]["schedule"] = crontab(
            hour=req.schedule_hour,
            minute=req.schedule_minute,
        )
        logger.info(f"Celery Beat 스케줄 즉시 반영 완료")
    except Exception as e:
        logger.warning(f"Celery Beat 즉시 반영 실패 (재시작 후 적용): {e}")

    return {
        "message":         "스케줄이 업데이트되었습니다.",
        "schedule_hour":   req.schedule_hour,
        "schedule_minute": req.schedule_minute,
        "timezone":        req.timezone,
        "is_active":       req.is_active,
    }


@router.get("/status")
async def scheduler_status(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    try:
        from app.celery_app.celery import celery_app
        inspect = celery_app.control.inspect(timeout=2.0)
        active  = inspect.active()   # {worker: [task, ...]}
        stats   = inspect.stats()    # {worker: {...}}

        workers = []
        if stats:
            for w_name, w_stat in stats.items():
                active_tasks = active.get(w_name, []) if active else []
                workers.append({
                    "name":         w_name,
                    "status":       "online",
                    "active_tasks": len(active_tasks),
                })

        beat_schedule = {}
        try:
            beat_schedule = {
                k: str(v.get("schedule"))
                for k, v in celery_app.conf.beat_schedule.items()
            }
        except Exception:
            pass

        return {
            "workers":       workers,
            "worker_count":  len(workers),
            "beat_schedule": beat_schedule,
            "broker":        celery_app.conf.broker_url,
        }
    except Exception as e:
        logger.warning(f"Celery 상태 조회 실패: {e}")
        return {
            "workers":      [],
            "worker_count": 0,
            "beat_schedule": {},
            "error":        str(e),
        }



# 시트 -> DB 동기화
@router.get("/sync-config")
async def get_sync_config(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    global _sync_scheduler
    is_running = False
    try:
        if _sync_scheduler:
            is_running = getattr(_sync_scheduler, "running", False)
    except Exception:
        pass
    return {
        "is_active":        is_running,
        "interval_seconds": 60,
        "description":      "Sheets(화면SoT) → DB(실제SoT) 단방향 동기화",
    }


# 동기화 시작
@router.post("/sync-start")
async def start_sync_schedule(
        req: SyncScheduleRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    global _sync_scheduler
    from app.scheduler.jobs import sync_sheets_to_db_incremental

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        if _sync_scheduler and getattr(_sync_scheduler, "running", False):
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
    except ImportError:
        logger.warning("apscheduler 미설치 — Celery Beat sync task 사용 권장")
        return {"status": "unavailable", "message": "apscheduler 미설치. Celery Beat의 sync-db task를 사용하세요."}


# 동기화 중지
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