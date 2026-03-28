from celery import Celery
from app.config import settings

celery_app = Celery("scm_agent")

celery_app.conf.update(
    broker_url              = settings.rabbitmq_url,
    result_backend          = (
        f"db+mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    ),
    task_serializer         = "json",
    result_serializer       = "json",
    accept_content          = ["json"],
    task_acks_late          = True,           # 워커 재시작 시 메시지 유실 방지
    worker_prefetch_multiplier = 1,           # 공정 분배
    timezone                = "Asia/Seoul",
    enable_utc              = False,
    task_track_started      = True,
    result_expires          = 86400,          # 24시간 후 결과 삭제
)

# schedule 별도 임포트
from app.celery_app.beat_schedule import BEAT_SCHEDULE  # noqa: E402
celery_app.conf.beat_schedule = BEAT_SCHEDULE
