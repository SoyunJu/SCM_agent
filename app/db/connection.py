
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from loguru import logger
from app.config import settings


DATABASE_URL = (
    f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    f"?charset=utf8mb4"
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping    = True,     # 연결 유효성 자동 확인 (dead connection 방지)
    pool_recycle     = 1800,     # 30분마다 커넥션 재생성 (MySQL wait_timeout 대비)
    pool_size        = 10,       # 기본 커넥션 풀 크기
    max_overflow     = 20,       # 피크 시 추가 허용 커넥션 (총 30개까지)
    pool_timeout     = 30,       # 커넥션 획득 대기 최대 30초
    pool_use_lifo    = True,     # LIFO: 최근 사용 커넥션 재사용 → DB 부하 분산
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

    # 최초 1회
def init_db():
    try:
        from app.db import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("################## DB 테이블 초기화 완료 ##################")
    except Exception as e:
        logger.error(f"################## DB 테이블 초기화 실패: {e} ##################")
        raise


def check_db_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("################## DB 연결 성공 ##################")
        return True
    except Exception as e:
        logger.error(f"################## DB 연결 실패: {e} ##################")
        return False