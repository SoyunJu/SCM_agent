
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
    pool_pre_ping=True,       # 연결 자동 확인
    pool_recycle=3600,        # 1시간마다 커넥션 재생성
    echo=(settings.app_env == "development"),  # dev 환경에서 SQL 로그 출력
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