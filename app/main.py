from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import asyncio
import logging

from app.db.connection import init_db, check_db_connection
from app.config import settings

from app.api.auth_router                import router as auth_router
from app.api.report_router              import router as report_router
from app.api.chat_router                import router as chat_router
from app.api.sheets_router              import router as sheets_router
from app.api.alert_router               import router as alert_router
from app.api.settings_router            import router as settings_router
from app.api.order_router               import router as order_router
from app.api.admin_router               import router as admin_router
from app.api.slack_interactions_router  import router as slack_interactions_router
from app.api.supplier_router import router as supplier_router
from app.api.product_router    import router as product_router
from app.api.task_router       import router as task_router
from app.api.scheduler_router  import router as scheduler_router



# 노이즈 쿼리 제거
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("################## SCM Agent 서버 시작 ##################")
    check_db_connection()
    init_db()
    _seed_superadmin()

    loop = asyncio.get_running_loop()
    from app.api.alert_router import set_main_loop
    set_main_loop(loop)

    # 시트 캐시 워밍업
    async def _warmup():
        try:
            await loop.run_in_executor(None, _warmup_sheets)
        except Exception:
            pass

    loop.create_task(_warmup())

    yield
    logger.info("################## SCM Agent 서버 종료 ##################")


def _seed_superadmin() -> None:
    import hashlib
    from app.db.connection import SessionLocal
    from app.db.repository import get_admin_user_by_username, create_admin_user
    from app.db.models import AdminRole
    from passlib.context import CryptContext

    db = SessionLocal()
    try:
        existing = get_admin_user_by_username(db, settings.admin_username)
        if not existing:
            ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            sha256_pw = hashlib.sha256(settings.admin_password.encode()).hexdigest()
            create_admin_user(
                db,
                username=settings.admin_username,
                hashed_password=ctx.hash(sha256_pw),
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
        from app.services.sync_service import SyncService
        from app.db.connection import SessionLocal
        db = SessionLocal()
        try:
            SyncService.sync_all_from_sheets(db)
            logger.info("DB 초기 동기화 완료")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"DB 초기 동기화 실패(무시): {e}")



app = FastAPI(
    title="SCM Agent API",
    description="쇼핑몰 재고·판매 데이터 자동 분석 에이전트",
    version="0.3.0",
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
app.include_router(sheets_router)
app.include_router(alert_router)
app.include_router(settings_router)
app.include_router(slack_interactions_router)
app.include_router(order_router)
app.include_router(admin_router)
app.include_router(task_router)
app.include_router(product_router)
app.include_router(scheduler_router)
app.include_router(supplier_router)


@app.get("/scm/health")
async def health_check():
    return {"status": "ok"}

