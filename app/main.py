
from fastapi import FastAPI
from contextlib import asynccontextmanager
from loguru import logger
from app.db.connection import init_db, check_db_connection


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