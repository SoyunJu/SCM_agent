
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Float, Enum
)
from sqlalchemy.sql import func
from app.db.connection import Base
import enum


# #####  Enum  ####################

class ReportType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


class ExecutionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    IN_PROGRESS = "in_progress"


class AnomalyType(str, enum.Enum):
    LOW_STOCK = "low_stock"           # 재고 부족
    OVER_STOCK = "over_stock"         # 재고 과잉
    SALES_SURGE = "sales_surge"       # 판매 급등
    SALES_DROP = "sales_drop"         # 판매 급락
    LONG_TERM_STOCK = "long_term_stock"  # 장기 재고


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


# ####### Table Model ###########################

class ReportExecution(Base):

    __tablename__ = "report_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    executed_at = Column(DateTime, nullable=False, default=func.now())
    report_type = Column(Enum(ReportType), nullable=False, default=ReportType.DAILY)
    status = Column(Enum(ExecutionStatus), nullable=False, default=ExecutionStatus.IN_PROGRESS)
    docs_url = Column(String(500), nullable=True)        # Google Docs URL
    slack_sent = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())


class AnomalyLog(Base):

    __tablename__ = "anomaly_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime, nullable=False, default=func.now())
    product_code = Column(String(20), nullable=False)
    product_name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    anomaly_type = Column(Enum(AnomalyType), nullable=False)
    current_stock = Column(Integer, nullable=True)
    daily_avg_sales = Column(Float, nullable=True)        # 일평균 판매량
    days_until_stockout = Column(Float, nullable=True)    # 소진 예상일
    severity = Column(Enum(Severity), nullable=False, default=Severity.MEDIUM)
    is_resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=func.now())


class ScheduleConfig(Base):

    __tablename__ = "schedule_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False, unique=True)
    schedule_hour = Column(Integer, nullable=False, default=0)
    schedule_minute = Column(Integer, nullable=False, default=0)
    timezone = Column(String(50), nullable=False, default="Asia/Seoul")
    is_active = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class ChatHistory(Base):

    __tablename__ = "chat_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)      # Slack thread_ts 등
    user_id = Column(String(100), nullable=False)         # Slack user_id
    role = Column(Enum(ChatRole), nullable=False)
    message = Column(Text, nullable=False)
    tool_used = Column(String(100), nullable=True)        # used LangChain Tool
    created_at = Column(DateTime, nullable=False, default=func.now())