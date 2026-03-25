
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from loguru import logger
import sys


class Settings(BaseSettings):
    # Google API
    google_service_account_json: str
    spreadsheet_id: str

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 1000

    # HuggingFace
    hf_model_name: str = "snunlp/KR-FinBert-SC"

    # Slack
    slack_bot_token: str = ""
    slack_channel_id: str = ""
    slack_signing_secret: str = ""

    # MariaDB
    db_host: str = "localhost"
    db_port: int = 3307
    db_name: str = "scm_agent"
    db_user: str = "scm_user"
    db_password: str = ""
    db_root_password: str = ""

    # JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Admin
    admin_username: str = "admin"
    admin_password: str = "admin1!"

    # Scheduler
    schedule_hour: int = 0
    schedule_minute: int = 0
    timezone: str = "Asia/Seoul"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

# Logger
logger.remove()
logger.add(
    sys.stdout,
    level=settings.log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> - {message}"
)
logger.add(
    "logs/scm_agent_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level=settings.log_level,
    encoding="utf-8"
)