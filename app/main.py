from fastapi import FastAPI
from contextlib import asynccontextmanager
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.db.connection import init_db, check_db_connection
from app.config import settings
from app.scheduler.jobs import run_daily_job


scheduler = AsyncIOScheduler(timezone=settings.timezone)

def _setup_scheduler() -> None:
    scheduler.add_job(
        func=run_daily_job,
        trigger=CronTrigger(
            hour=settings.schedule_hour,
            minute=settings.schedule_minute,
            timezone=pytz.timezone(settings.timezone),
        ),
        id="daily_report",
        name="일일 현황 보고서 자동 생성",
        replace_existing=True,
        misfire_grace_time=3600,    # 1시간 내 실행 못 하면 즉시 실행
        coalesce=True,              # 밀린 작업 중복 실행 방지
    )
    logger.info(
        f"스케줄 등록 완료: 매일 {settings.schedule_hour:02d}:{settings.schedule_minute:02d} ({settings.timezone})"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("################## SCM Agent 서버 시작 ##################")
    check_db_connection()
    init_db()
    yield
    # 서버 종료 시
    logger.info("################## SCM Agent 서버 종료 ##################")


app = FastAPI(
    title="SCM Agent API",
    description="쇼핑몰 재고·판매 데이터 자동 분석 에이전트",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/scm/health")
async def health_check():
    return {"status": "ok"}


@app.post("/scm/report/run")
async def trigger_report():
    import asyncio
    asyncio.create_task(asyncio.to_thread(run_daily_job))
    logger.info("보고서 수동 실행 트리거 실행")
    return {"status": "triggered", "message": "보고서 생성이 시작되었습니다."}


@app.get("/scm/scheduler/status")
async def scheduler_status():
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