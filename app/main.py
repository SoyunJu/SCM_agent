from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import asyncio
import logging

from app.db.connection import init_db, check_db_connection
from app.config import settings
from app.scheduler.jobs import run_daily_job

from app.api.auth_router      import router as auth_router
from app.api.report_router    import router as report_router
from app.api.chat_router      import router as chat_router
from app.api.scheduler_router import router as scheduler_router
from app.api.sheets_router    import router as sheets_router
from app.api.alert_router     import router as alert_router
from app.api.settings_router  import router as settings_router
from app.api.order_router import router as order_router
from app.api.admin_router import router as admin_router
from app.api.slack_interactions_router import router as slack_interactions_router


scheduler = AsyncIOScheduler(timezone=settings.timezone)

# 노이즈 쿼리 제거
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

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
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info(f"스케줄 등록: 매일 {settings.schedule_hour:02d}:{settings.schedule_minute:02d} ({settings.timezone})")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("################## SCM Agent 서버 시작 ##################")
    check_db_connection()
    init_db()
    _seed_superadmin()
    _setup_scheduler()
    scheduler.start()

    # 메인 이벤트 루프 등록 (스레드 → SSE 알림 브릿지)
    loop = asyncio.get_running_loop()

    from app.api.alert_router import set_main_loop
    set_main_loop(loop)

    # 시트 캐시 워밍업 (백그라운드)
    async def _warmup():
        try:
            await loop.run_in_executor(None, _warmup_sheets)
        except Exception:
            pass

    loop.create_task(_warmup())

    yield

    scheduler.shutdown(wait=False)
    logger.info("################## SCM Agent 서버 종료 ##################")


def _seed_superadmin() -> None:
    from app.db.connection import SessionLocal
    from app.db.repository import get_admin_user_by_username, create_admin_user
    from app.db.models import AdminRole
    from passlib.context import CryptContext

    db = SessionLocal()
    try:
        existing = get_admin_user_by_username(db, settings.admin_username)
        if not existing:
            ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            create_admin_user(
                db,
                username=settings.admin_username,
                hashed_password=ctx.hash(settings.admin_password),
                role=AdminRole.SUPERADMIN,
            )
            logger.info(f"슈퍼어드민 자동 생성: {settings.admin_username}")
        else:
            logger.info(f"슈퍼어드민 이미 존재: {settings.admin_username}")
    except Exception as e:
        logger.warning(f"슈퍼어드민 seed 실패(무시): {e}")
    finally:
        db.close()



def _warmup_sheets() -> None:
    try:
        from app.sheets.reader import read_product_master, read_sales, read_stock
        read_product_master()
        read_sales()
        read_stock()
        logger.info("시트 캐시 워밍업 완료")
    except Exception as e:
        logger.warning(f"캐시 워밍업 실패(무시): {e}")



app = FastAPI(
    title="SCM Agent API",
    description="쇼핑몰 재고·판매 데이터 자동 분석 에이전트",
    version="0.1.2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(report_router)
app.include_router(chat_router)
app.include_router(scheduler_router)
app.include_router(sheets_router)
app.include_router(alert_router)
app.include_router(settings_router)
app.include_router(slack_interactions_router)
app.include_router(order_router)
app.include_router(admin_router)


@app.get("/scm/health")
async def health_check():
    return {"status": "ok"}


@app.get("/scm/scheduler/status")
async def scheduler_status():
    jobs = scheduler.get_jobs()
    return {
        "running": scheduler.running,
        "jobs": [{"id": j.id, "name": j.name, "next_run": str(j.next_run_time)} for j in jobs],
    }
