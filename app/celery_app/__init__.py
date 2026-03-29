from celery import Celery
from app.config import settings

celery_app = Celery(
    "scm_agent",
    include=["app.celery_app.tasks"],   # tasks.py 자동 등록
)

celery_app.conf.update(
    broker_url              = settings.rabbitmq_url,
    result_backend          = (
        f"db+mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    ),
    task_serializer         = "json",
    result_serializer       = "json",
    accept_content          = ["json"],
    task_acks_late          = True,
    worker_prefetch_multiplier = 1,
    timezone                = "Asia/Seoul",
    enable_utc              = False,
    task_track_started      = True,
    result_expires          = 86400,
)

from app.celery_app.beat_schedule import BEAT_SCHEDULE  # noqa: E402
celery_app.conf.beat_schedule = BEAT_SCHEDULE
