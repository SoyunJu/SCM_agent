from typing import Annotated

from loguru import logger
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scm/scheduler", tags=["scheduler"])


# --- Pydantic 스키마 ---

class ScheduleUpdateRequest(BaseModel):
    schedule_hour:   int
    schedule_minute: int
    timezone:        str  = "Asia/Seoul"
    is_active:       bool = True

class SyncConfigRequest(BaseModel):
    enabled: bool


# --- 보고서 생성 스케줄 ---

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
    try:
        from app.celery_app.celery import celery_app
        inspect = celery_app.control.inspect(timeout=2.0)
        active  = inspect.active()
        stats   = inspect.stats()

        workers = []
        if stats:
            for w_name, w_stat in stats.items():
                active_tasks = active.get(w_name, []) if active else []
                workers.append({
                    "name":         w_name,
                    "status":       "online",
                    "active_tasks": len(active_tasks),
                })

        # beat_schedule을 파일에서 직접 읽기 (api 컨테이너에서도 접근 가능)
        beat_schedule = {}
        try:
            from app.celery_app.beat_schedule import BEAT_SCHEDULE
            from celery.schedules import crontab
            from datetime import timedelta

            for k, v in BEAT_SCHEDULE.items():
                sched = v.get("schedule")
                if isinstance(sched, crontab):
                    h = str(sched.hour).replace("{", "").replace("}", "")
                    m = str(sched.minute).replace("{", "").replace("}", "")
                    beat_schedule[k] = f"매일 {h.zfill(2)}:{m.zfill(2)}"
                elif isinstance(sched, timedelta):
                    minutes = int(sched.total_seconds() // 60)
                    beat_schedule[k] = f"매 {minutes}분"
                else:
                    beat_schedule[k] = str(sched)
        except Exception as be:
            logger.warning(f"Beat 스케줄 읽기 실패: {be}")

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


@router.post("/trigger")
async def trigger_daily_report(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        return SchedulerService.trigger_daily_report()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))



# --- Sheets→DB 동기화 ---

@router.get("/sync-config")
async def get_sync_config(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    return SchedulerService.get_sync_config(db)


@router.put("/sync-config")
async def update_sync_config(
        req: SyncConfigRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SchedulerService.update_sync_config(db, req.enabled, current_user.username)


@router.post("/sync-trigger")
async def trigger_sync(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        return SchedulerService.trigger_sync()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-stop")
async def stop_sync_schedule(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    return SchedulerService.stop_sync()


@router.post("/trigger-crawler")
async def trigger_crawler(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        return SchedulerService.trigger_crawler()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-cleanup")
async def trigger_cleanup(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        return SchedulerService.trigger_cleanup()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-demand-forecast")
async def trigger_demand_forecast(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        from app.celery_app.tasks import run_demand_forecast
        result = run_demand_forecast.delay()
        return {"status": "triggered", "task_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-turnover-analysis")
async def trigger_turnover_analysis(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        from app.celery_app.tasks import run_turnover_analysis
        result = run_turnover_analysis.delay()
        return {"status": "triggered", "task_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-abc-analysis")
async def trigger_abc_analysis(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        from app.celery_app.tasks import run_abc_analysis_task
        result = run_abc_analysis_task.delay()
        return {"status": "triggered", "task_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/trigger-proactive-order")
async def trigger_proactive_order(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        from app.celery_app.tasks import run_proactive_order
        result = run_proactive_order.delay()
        return {"status": "triggered", "task_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 안전재고 재계산 트리거
@router.post("/trigger-safety-stock-recalc")
async def trigger_safety_stock_recalc(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        from app.celery_app.tasks import run_safety_stock_recalc
        result = run_safety_stock_recalc.delay()
        return {"status": "triggered", "task_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
