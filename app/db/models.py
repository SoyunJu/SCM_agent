from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, Enum, Date, UniqueConstraint, Index, ForeignKey
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
    email_sent    = Column(Boolean, nullable=False, default=False)
    triggered_by  = Column(String(100), nullable=True)
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

    __table_args__ = (
        Index("ix_anomaly_product_code",  "product_code"),
        Index("ix_anomaly_is_resolved",   "is_resolved"),
        Index("ix_anomaly_type_resolved", "anomaly_type", "is_resolved"),  # 미해결 타입별 조회
        Index("ix_anomaly_detected_at",   "detected_at"),
    )

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

    __table_args__ = (
        Index("ix_chat_session_id",  "session_id"),
        Index("ix_chat_user_id",     "user_id"),
        Index("ix_chat_created_at",  "created_at"),
    )

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
    required_role = Column(String(20), nullable=False, default="ADMIN")
    created_at    = Column(DateTime, nullable=False, default=func.now())
    approved_at   = Column(DateTime, nullable=True)
    approved_by   = Column(String(100), nullable=True)
    slack_ts      = Column(String(50), nullable=True)
    slack_channel = Column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_proposal_status",     "status"),
        Index("ix_proposal_created_at", "created_at"),
        Index("ix_proposal_product",    "product_code"),
    )

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
    lead_time_days = Column(Integer,    nullable=True,  default=None)
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

    id           = Column(Integer, primary_key=True, autoincrement=True)
    date         = Column(Date, nullable=False)
    product_code = Column(String(100), nullable=False)
    qty          = Column(Integer, nullable=False, default=0)
    revenue      = Column(Float, nullable=False, default=0)
    cost         = Column(Float, nullable=False, default=0)   # ← 추가: 매입액

    __table_args__ = (
        UniqueConstraint("date", "product_code", name="uq_daily_sales_date_product"),
        Index("idx_date", "date"),
        Index("idx_product_code", "product_code"),
        Index("idx_date_product_code", "date", "product_code"),
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


class Supplier(Base):
    """공급업체 마스터"""
    __tablename__ = "suppliers"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    name           = Column(String(200), nullable=False, unique=True)
    contact        = Column(String(100), nullable=True)   # 담당자명
    email          = Column(String(200), nullable=True)
    phone          = Column(String(50),  nullable=True)
    lead_time_days = Column(Integer,     nullable=False, default=14)
    is_active      = Column(Boolean,     nullable=False, default=True)
    created_at     = Column(DateTime,    nullable=False, default=func.now())
    updated_at     = Column(DateTime,    nullable=False, default=func.now(), onupdate=func.now())


class ProductSupplier(Base):
    """상품-공급업체 1:1 매핑"""
    __tablename__ = "product_suppliers"

    product_code = Column(String(20),  ForeignKey("products.code", ondelete="CASCADE"), primary_key=True)
    supplier_id  = Column(Integer,     ForeignKey("suppliers.id",  ondelete="CASCADE"), nullable=False)
    unit_price   = Column(Float,       nullable=True)    # 공급업체별 매입단가
    updated_at   = Column(DateTime,    nullable=False, default=func.now(), onupdate=func.now())


class SupplierDeliveryHistory(Base):
    """납기 이력 (발주 대비 실제 납기 추적)"""
    __tablename__ = "supplier_delivery_history"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    supplier_id       = Column(Integer,  ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    order_proposal_id = Column(Integer,  ForeignKey("order_proposals.id", ondelete="SET NULL"), nullable=True)
    expected_date     = Column(Date,     nullable=False)   # 예상 납기일
    actual_date       = Column(Date,     nullable=True)    # 실제 입고일
    delay_days        = Column(Integer,  nullable=True)    # 지연일수 (음수=조기납품)
    created_at        = Column(DateTime, nullable=False, default=func.now())


class ReceivingInspection(Base):
    """입고 검수 이력"""
    __tablename__ = "receiving_inspections"

    id                = Column(Integer,     primary_key=True, autoincrement=True)
    order_proposal_id = Column(Integer,     ForeignKey("order_proposals.id", ondelete="SET NULL"), nullable=True)
    supplier_id       = Column(Integer,     ForeignKey("suppliers.id",       ondelete="SET NULL"), nullable=True)
    product_code      = Column(String(20),  nullable=False)
    product_name      = Column(String(200), nullable=True)
    ordered_qty       = Column(Integer,     nullable=False)
    received_qty      = Column(Integer,     nullable=False, default=0)
    defect_qty        = Column(Integer,     nullable=False, default=0)
    return_qty        = Column(Integer,     nullable=False, default=0)
    status            = Column(String(20),  nullable=False, default="PENDING")
    # PENDING / PARTIAL(부분입고) / COMPLETED(완료) / RETURNED(반품)
    note              = Column(Text,        nullable=True)
    inspected_by      = Column(String(100), nullable=True)
    inspected_at      = Column(DateTime,    nullable=True)
    created_at        = Column(DateTime,    nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_receiving_product_code", "product_code"),
        Index("ix_receiving_status",       "status"),
    )


class AlertHistory(Base):
    """SSE/Slack/Email 알림 발송 이력"""
    __tablename__ = "alert_history"

    id           = Column(Integer,     primary_key=True, autoincrement=True)
    alert_type   = Column(String(50),  nullable=False)   # anomaly / daily_report / proactive_order 등
    channel      = Column(String(20),  nullable=False)   # slack / email / sse / both
    severity     = Column(String(20),  nullable=True)
    product_code = Column(String(20),  nullable=True)
    product_name = Column(String(200), nullable=True)
    message      = Column(Text,        nullable=True)
    is_read      = Column(Boolean,     nullable=False, default=False)
    created_at   = Column(DateTime,    nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_alert_history_created_at", "created_at"),
        Index("ix_alert_history_is_read",    "is_read"),
    )


class CategoryLeadTime(Base):
    """카테고리별 리드타임 설정"""
    __tablename__ = "category_lead_times"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    category       = Column(String(100), nullable=False, unique=True)
    lead_time_days = Column(Integer,     nullable=False, default=14)
    updated_at     = Column(DateTime,    nullable=False, default=func.now(), onupdate=func.now())