from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.db.connection import init_db, check_db_connection
from app.config import settings
from app.scheduler.jobs import run_daily_job

from app.api.auth_router import router as auth_router
from app.api.report_router import router as report_router
from app.api.chat_router import router as chat_router
from app.api.scheduler_router import router as scheduler_router
from app.api.sheets_router import router as sheets_router
from app.api.alert_router import router as alert_router


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

"""
@app.post("/scm/report/run")
async def trigger_report():
    import asyncio
    asyncio.create_task(asyncio.to_thread(run_daily_job))
    logger.info("보고서 수동 실행 트리거 실행")
    return {"status": "triggered", "message": "보고서 생성이 시작되었습니다."}
"""


# CORS (Next.js 관리자 화면 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],   # Next.js 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router)
app.include_router(report_router)
app.include_router(chat_router)
app.include_router(scheduler_router)
app.include_router(sheets_router)
app.include_router(alert_router)


@app.get("/scm/health")
async def health_check():
    return {"status": "ok"}


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