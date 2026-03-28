from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, Enum, Date, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator
from app.db.connection import Base
import enum

# --- 1. 헬퍼 ---
class UpperCaseEnum(TypeDecorator):
    impl = String(50)
    cache_ok = True

    def __init__(self, enum_class):
        super().__init__()
        self.enum_class = enum_class

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, enum.Enum):
            return value.value.upper()
        return str(value).upper()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return self.enum_class(value.upper())
        except ValueError:
            return value

# --- 2. Enum 정의 ---

class ReportType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MANUAL = "MANUAL"

class ExecutionStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    IN_PROGRESS = "IN_PROGRESS"

class AnomalyType(str, enum.Enum):
    LOW_STOCK = "LOW_STOCK"
    OVER_STOCK = "OVER_STOCK"
    SALES_SURGE = "SALES_SURGE"
    SALES_DROP = "SALES_DROP"
    LONG_TERM_STOCK = "LONG_TERM_STOCK"

class Severity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    CHECK = "CHECK"

class ChatRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"

class ProposalStatus(str, enum.Enum):
    PENDING  = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class AdminRole(str, enum.Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN      = "ADMIN"
    READONLY   = "READONLY"

class ProductStatus(str, enum.Enum):
    ACTIVE   = "ACTIVE"
    INACTIVE = "INACTIVE"
    SAMPLE   = "SAMPLE"

# --- 3. 모델 정의 ---

class ReportExecution(Base):
    __tablename__ = "report_executions"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    executed_at   = Column(DateTime, nullable=False, default=func.now())
    report_type   = Column(UpperCaseEnum(ReportType), nullable=False, default=ReportType.DAILY)
    status        = Column(UpperCaseEnum(ExecutionStatus), nullable=False, default=ExecutionStatus.IN_PROGRESS)
    docs_url      = Column(String(500), nullable=True)
    slack_sent    = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    created_at    = Column(DateTime, nullable=False, default=func.now())

class AnomalyLog(Base):
    __tablename__ = "anomaly_logs"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    detected_at         = Column(DateTime, nullable=False, default=func.now())
    product_code        = Column(String(20), nullable=False)
    product_name        = Column(String(200), nullable=False)
    category            = Column(String(100), nullable=True)
    anomaly_type        = Column(UpperCaseEnum(AnomalyType), nullable=False)
    current_stock       = Column(Integer, nullable=True)
    daily_avg_sales     = Column(Float, nullable=True)
    days_until_stockout = Column(Float, nullable=True)
    severity            = Column(UpperCaseEnum(Severity), nullable=False, default=Severity.MEDIUM)
    is_resolved         = Column(Boolean, nullable=False, default=False)
    created_at          = Column(DateTime, nullable=False, default=func.now())

class ScheduleConfig(Base):
    __tablename__ = "schedule_configs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    job_name        = Column(String(100), nullable=False, unique=True)
    schedule_hour   = Column(Integer, nullable=False, default=0)
    schedule_minute = Column(Integer, nullable=False, default=0)
    timezone        = Column(String(50), nullable=False, default="Asia/Seoul")
    is_active       = Column(Boolean, nullable=False, default=True)
    last_run_at     = Column(DateTime, nullable=True)
    updated_at      = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

class ChatHistory(Base):
    __tablename__ = "chat_histories"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    user_id    = Column(String(100), nullable=False)
    role       = Column(UpperCaseEnum(ChatRole), nullable=False)
    message    = Column(Text, nullable=False)
    tool_used  = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    setting_key   = Column(String(100), nullable=False, unique=True)
    setting_value = Column(String(500), nullable=False)
    description   = Column(String(200), nullable=True)
    updated_at    = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

class OrderProposal(Base):
    __tablename__ = "order_proposals"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    product_code  = Column(String(100), nullable=False)
    product_name  = Column(String(200), nullable=True)
    category      = Column(String(100), nullable=True)
    proposed_qty  = Column(Integer, nullable=False)
    unit_price    = Column(Float, nullable=False, default=0.0)
    reason        = Column(Text, nullable=True)
    status        = Column(UpperCaseEnum(ProposalStatus), nullable=False, default=ProposalStatus.PENDING)
    created_at    = Column(DateTime, nullable=False, default=func.now())
    approved_at   = Column(DateTime, nullable=True)
    approved_by   = Column(String(100), nullable=True)
    slack_ts      = Column(String(50), nullable=True)
    slack_channel = Column(String(50), nullable=True)

class AdminUser(Base):
    __tablename__ = "admin_users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String(50), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(UpperCaseEnum(AdminRole), nullable=False, default=AdminRole.ADMIN)
    slack_user_id   = Column(String(50), nullable=True)
    email           = Column(String(200), nullable=True)
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, nullable=False, default=func.now())
    last_login_at   = Column(DateTime, nullable=True)

class Product(Base):
    __tablename__ = "products"
    code          = Column(String(20),  primary_key=True)
    name          = Column(String(200), nullable=False)
    category      = Column(String(100), nullable=True)
    safety_stock  = Column(Integer,     nullable=False, default=0)
    status        = Column(UpperCaseEnum(ProductStatus), nullable=False, default=ProductStatus.ACTIVE)
    source        = Column(String(50),  nullable=True)
    updated_at    = Column(DateTime,    nullable=False,
                           default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_products_category", "category"),
        Index("ix_products_status",   "status"),
    )

class DailySales(Base):
    __tablename__ = "daily_sales"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    date          = Column(Date,        nullable=False)
    product_code  = Column(String(20),  nullable=False)
    qty           = Column(Integer,     nullable=False, default=0)
    revenue       = Column(Float,       nullable=False, default=0.0)

    __table_args__ = (
        UniqueConstraint("date", "product_code", name="uq_daily_sales_date_code"),
        Index("ix_daily_sales_date",         "date"),
        Index("ix_daily_sales_product_code", "product_code"),
    )

class StockLevel(Base):
    __tablename__ = "stock_levels"

    product_code  = Column(String(20), primary_key=True)
    current_stock = Column(Integer,    nullable=False, default=0)
    restock_date  = Column(Date,       nullable=True)
    restock_qty   = Column(Integer,    nullable=True)
    updated_at    = Column(DateTime,   nullable=False,
                           default=func.now(), onupdate=func.now())

class AnalysisCache(Base):
    __tablename__ = "analysis_cache"

    id            = Column(Integer,     primary_key=True, autoincrement=True)
    analysis_type = Column(String(50),  nullable=False)
    params_hash   = Column(String(64),  nullable=False)
    result_json   = Column(Text,        nullable=False)
    created_at    = Column(DateTime,    nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_analysis_cache_type_hash", "analysis_type", "params_hash"),
    )