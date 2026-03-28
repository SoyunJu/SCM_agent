from sqlalchemy.orm import Session
from sqlalchemy import desc
from loguru import logger
from typing import Optional, Any
from datetime import datetime, timedelta
from app.db.models import AdminUser, AdminRole

from app.db.models import (
    ReportExecution, AnomalyLog, ScheduleConfig, ChatHistory, SystemSettings,
    ReportType, ExecutionStatus, AnomalyType, Severity, ChatRole
)


# --- Report ---------------

def create_report_execution(db: Session, report_type: ReportType = ReportType.DAILY) -> ReportExecution:
    record = ReportExecution(report_type=report_type)
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(f"보고서 실행 이력 생성: id={record.id}, type={report_type}")
    return record


def update_report_execution(
        db: Session, record_id: int, status: ExecutionStatus,
        docs_url: Optional[str] = None, slack_sent: bool = False,
        error_message: Optional[str] = None,
) -> Optional[ReportExecution]:
    record = db.query(ReportExecution).filter(ReportExecution.id == record_id).first()
    if not record:
        return None
    record.status        = status
    record.docs_url      = docs_url
    record.slack_sent    = slack_sent
    record.error_message = error_message
    db.commit()
    db.refresh(record)
    return record


def get_report_executions(db: Session, limit: int = 20) -> list[ReportExecution]:
    return db.query(ReportExecution).order_by(desc(ReportExecution.created_at)).limit(limit).all()


def get_report_execution_by_id(db: Session, record_id: int) -> Optional[ReportExecution]:
    return db.query(ReportExecution).filter(ReportExecution.id == record_id).first()


# --- Anomaly ------------─

def create_anomaly_log(
        db: Session, product_code: str, product_name: str,
        anomaly_type: AnomalyType, severity: Severity,
        category: Optional[str] = None,
        current_stock: Optional[int] = None,
        daily_avg_sales: Optional[float] = None,
        days_until_stockout: Optional[float] = None,
) -> AnomalyLog:
    record = AnomalyLog(
        product_code=product_code, product_name=product_name,
        category=category, anomaly_type=anomaly_type, severity=severity,
        current_stock=current_stock, daily_avg_sales=daily_avg_sales,
        days_until_stockout=days_until_stockout,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_anomaly_logs(
        db: Session,
        is_resolved: Optional[bool] = None,
        anomaly_type: Optional[str] = None,
        severity: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
) -> dict:
    query = db.query(AnomalyLog)
    if is_resolved is not None:
        query = query.filter(AnomalyLog.is_resolved == is_resolved)
    if anomaly_type:
        query = query.filter(AnomalyLog.anomaly_type == anomaly_type)
    if severity:
        query = query.filter(AnomalyLog.severity == severity)

    total = query.count()
    items = query.order_by(desc(AnomalyLog.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {"total": total, "page": page, "page_size": page_size, "total_pages": total_pages, "items": items}


def resolve_anomaly(db: Session, anomaly_id: int) -> Optional[AnomalyLog]:
    record = db.query(AnomalyLog).filter(AnomalyLog.id == anomaly_id).first()
    if not record:
        return None
    record.is_resolved = True
    db.commit()
    db.refresh(record)
    return record


# --- Schedule ------------

def get_schedule_config(db: Session, job_name: str) -> Optional[ScheduleConfig]:
    return db.query(ScheduleConfig).filter(ScheduleConfig.job_name == job_name).first()


def upsert_schedule_config(
        db: Session, job_name: str, schedule_hour: int, schedule_minute: int,
        timezone: str = "Asia/Seoul", is_active: bool = True,
) -> ScheduleConfig:
    record = get_schedule_config(db, job_name)
    if record:
        record.schedule_hour   = schedule_hour
        record.schedule_minute = schedule_minute
        record.timezone        = timezone
        record.is_active       = is_active
    else:
        record = ScheduleConfig(
            job_name=job_name, schedule_hour=schedule_hour,
            schedule_minute=schedule_minute, timezone=timezone, is_active=is_active,
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_last_run(db: Session, job_name: str) -> None:
    record = get_schedule_config(db, job_name)
    if record:
        record.last_run_at = datetime.now()
        db.commit()


# --- ChatHistory ------─

def save_chat_message(
        db: Session, session_id: str, user_id: str, role: ChatRole,
        message: str, tool_used: Optional[str] = None,
) -> ChatHistory:
    record = ChatHistory(
        session_id=session_id, user_id=user_id,
        role=role, message=message, tool_used=tool_used,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_chat_history(db: Session, session_id: str) -> list[ChatHistory]:
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.created_at)
        .all()
    )


def get_chat_history_recent(db: Session, session_id: str, days: int = 7) -> list[ChatHistory]:
    cutoff = datetime.now() - timedelta(days=days)
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .filter(ChatHistory.created_at >= cutoff)
        .order_by(ChatHistory.created_at)
        .all()
    )


# --- SystemSettings ---

def get_setting(db: Session, key: str, default: Any = None) -> str:
    record = db.query(SystemSettings).filter(SystemSettings.setting_key == key).first()
    if record:
        return record.setting_value
    return str(default) if default is not None else ""


def upsert_setting(
        db: Session, key: str, value: str, description: Optional[str] = None
) -> SystemSettings:
    record = db.query(SystemSettings).filter(SystemSettings.setting_key == key).first()
    if record:
        record.setting_value = value
        if description:
            record.description = description
    else:
        record = SystemSettings(setting_key=key, setting_value=value, description=description)
        db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_all_settings(db: Session) -> list[SystemSettings]:
    return db.query(SystemSettings).all()


# --- User ---

def get_admin_user_by_username(db: Session, username: str) -> AdminUser | None:
    return (
        db.query(AdminUser)
        .filter(AdminUser.username == username, AdminUser.is_active == True)
        .first()
    )


def list_admin_users(db: Session) -> list[AdminUser]:
    return db.query(AdminUser).order_by(AdminUser.created_at).all()


def create_admin_user(
        db: Session,
        username: str,
        hashed_password: str,
        role: AdminRole = AdminRole.ADMIN,
        slack_user_id: str | None = None,
        email: str | None = None,
) -> AdminUser:
    record = AdminUser(
        username=username,
        hashed_password=hashed_password,
        role=role,
        slack_user_id=slack_user_id,
        email=email,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_admin_user(
        db: Session,
        user_id: int,
        role: AdminRole | None = None,
        slack_user_id: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
        hashed_password: str | None = None,
) -> AdminUser | None:
    record = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not record:
        return None
    if role            is not None: record.role            = role
    if slack_user_id   is not None: record.slack_user_id   = slack_user_id
    if email           is not None: record.email           = email
    if is_active       is not None: record.is_active       = is_active
    if hashed_password is not None: record.hashed_password = hashed_password
    db.commit()
    db.refresh(record)
    return record


def delete_admin_user(db: Session, user_id: int) -> bool:
    record = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True


def update_last_login(db: Session, user_id: int) -> None:
    from datetime import datetime
    record = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if record:
        record.last_login_at = datetime.now()
        db.commit()


# --- DB SoT 변경 ---
from app.db.models import Product, ProductStatus, DailySales, StockLevel, AnalysisCache
from sqlalchemy import and_
from datetime import date as date_type, timedelta


# --- Product ---
def get_products_paginated(
        db: Session,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[ProductStatus] = None,
) -> dict:
    query = db.query(Product)
    if search:
        query = query.filter(Product.name.contains(search))
    if category:
        query = query.filter(Product.category == category)
    if status:
        query = query.filter(Product.status == status)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_product_by_code(db: Session, code: str) -> Optional[Product]:
    return db.query(Product).filter(Product.code == code).first()


def update_product_status(db: Session, code: str, status: ProductStatus) -> Optional[Product]:
    record = get_product_by_code(db, code)
    if not record:
        return None
    record.status = status
    db.commit()
    db.refresh(record)
    return record


def get_active_product_codes(db: Session) -> list[str]:
    rows = db.query(Product.code).filter(Product.status == ProductStatus.ACTIVE).all()
    return [r.code for r in rows]


# --- DailySales ---
def get_daily_sales_range(
        db: Session,
        start: date_type,
        end: date_type,
        product_codes: Optional[list[str]] = None,
) -> list[DailySales]:
    query = db.query(DailySales).filter(
        and_(DailySales.date >= start, DailySales.date <= end)
    )
    if product_codes:
        query = query.filter(DailySales.product_code.in_(product_codes))
    return query.all()


# --- StockLevel ---
def get_stock_level(db: Session, product_code: str) -> Optional[StockLevel]:
    return db.query(StockLevel).filter(StockLevel.product_code == product_code).first()


def get_all_stock_levels(db: Session) -> list[StockLevel]:
    return db.query(StockLevel).all()


# --- AnalysisCache ---
def get_analysis_cache(
        db: Session, analysis_type: str, params_hash: str, max_age_minutes: int = 30
) -> Optional[AnalysisCache]:
    cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
    return (
        db.query(AnalysisCache)
        .filter(
            AnalysisCache.analysis_type == analysis_type,
            AnalysisCache.params_hash   == params_hash,
            AnalysisCache.created_at    >= cutoff,
            )
        .order_by(desc(AnalysisCache.created_at))
        .first()
    )


def upsert_analysis_cache(
        db: Session, analysis_type: str, params_hash: str, result_json: str
) -> AnalysisCache:
    # 기존 data del -> new insert
    db.query(AnalysisCache).filter(
        AnalysisCache.analysis_type == analysis_type,
        AnalysisCache.params_hash   == params_hash,
        ).delete()
    record = AnalysisCache(
        analysis_type=analysis_type,
        params_hash=params_hash,
        result_json=result_json,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def delete_old_analysis_cache(db: Session, older_than_hours: int = 24) -> int:
    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    deleted = db.query(AnalysisCache).filter(AnalysisCache.created_at < cutoff).delete()
    db.commit()
    return deleted


def delete_old_daily_sales(db: Session, older_than_days: int = 365) -> int:
    cutoff = datetime.now().date() - timedelta(days=older_than_days)
    deleted = db.query(DailySales).filter(DailySales.date < cutoff).delete()
    db.commit()
    return deleted
