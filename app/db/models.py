from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, Enum, Date, UniqueConstraint, Index
from sqlalchemy.sql import func
from app.db.connection import Base
import enum


class ReportType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


class ExecutionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    IN_PROGRESS = "in_progress"


class AnomalyType(str, enum.Enum):
    LOW_STOCK = "low_stock"
    OVER_STOCK = "over_stock"
    SALES_SURGE = "sales_surge"
    SALES_DROP = "sales_drop"
    LONG_TERM_STOCK = "long_term_stock"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ReportExecution(Base):
    __tablename__ = "report_executions"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    executed_at   = Column(DateTime, nullable=False, default=func.now())
    report_type   = Column(Enum(ReportType), nullable=False, default=ReportType.DAILY)
    status        = Column(Enum(ExecutionStatus), nullable=False, default=ExecutionStatus.IN_PROGRESS)
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
    anomaly_type        = Column(Enum(AnomalyType), nullable=False)
    current_stock       = Column(Integer, nullable=True)
    daily_avg_sales     = Column(Float, nullable=True)
    days_until_stockout = Column(Float, nullable=True)
    severity            = Column(Enum(Severity), nullable=False, default=Severity.MEDIUM)
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
    role       = Column(Enum(ChatRole), nullable=False)
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



class ProposalStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OrderProposal(Base):
    __tablename__ = "order_proposals"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    product_code  = Column(String(100), nullable=False)
    product_name  = Column(String(200), nullable=True)
    category      = Column(String(100), nullable=True)
    proposed_qty  = Column(Integer, nullable=False)
    unit_price    = Column(Float, nullable=False, default=0.0)
    reason        = Column(Text, nullable=True)
    status        = Column(Enum(ProposalStatus), nullable=False, default=ProposalStatus.PENDING)
    created_at    = Column(DateTime, nullable=False, default=func.now())
    approved_at   = Column(DateTime, nullable=True)
    approved_by   = Column(String(100), nullable=True)
    slack_ts      = Column(String(50), nullable=True)
    slack_channel = Column(String(50), nullable=True)



class AdminRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN      = "admin"
    READONLY   = "readonly"


class AdminUser(Base):
    __tablename__ = "admin_users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String(50), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(Enum(AdminRole), nullable=False, default=AdminRole.ADMIN)
    slack_user_id   = Column(String(50), nullable=True)    # Slack Member ID (예: U012ABCDE)
    email           = Column(String(200), nullable=True)
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, nullable=False, default=func.now())
    last_login_at   = Column(DateTime, nullable=True)


class Severity(str, enum.Enum):
    LOW      = "low"
    CHECK   = "check"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class ProductStatus(str, enum.Enum):
    ACTIVE   = "active"
    INACTIVE = "inactive"
    SAMPLE   = "sample"


class Product(Base):
    """상품 마스터 미러 (100k+ 지원)"""
    __tablename__ = "products"

    code          = Column(String(20),  primary_key=True)
    name          = Column(String(200), nullable=False)
    category      = Column(String(100), nullable=True)
    safety_stock  = Column(Integer,     nullable=False, default=0)
    status        = Column(Enum(ProductStatus), nullable=False, default=ProductStatus.ACTIVE)
    source        = Column(String(50),  nullable=True)   # "sheets" | "excel"
    updated_at    = Column(DateTime,    nullable=False,
                           default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_products_category", "category"),
        Index("ix_products_status",   "status"),
    )


class DailySales(Base):
    """일별 매출 미러"""
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
    """재고 스냅샷 (상품별 최신 1건)"""
    __tablename__ = "stock_levels"

    product_code  = Column(String(20), primary_key=True)
    current_stock = Column(Integer,    nullable=False, default=0)
    restock_date  = Column(Date,       nullable=True)
    restock_qty   = Column(Integer,    nullable=True)
    updated_at    = Column(DateTime,   nullable=False,
                           default=func.now(), onupdate=func.now())


class AnalysisCache(Base):
    """분석 결과 캐시 (중복 계산 방지)"""
    __tablename__ = "analysis_cache"

    id            = Column(Integer,     primary_key=True, autoincrement=True)
    analysis_type = Column(String(50),  nullable=False)
    params_hash   = Column(String(64),  nullable=False)   # SHA256(params)
    result_json   = Column(Text,        nullable=False)
    created_at    = Column(DateTime,    nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_analysis_cache_type_hash", "analysis_type", "params_hash"),
    )