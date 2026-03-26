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
        db: Session, is_resolved: Optional[bool] = None, limit: int = 50
) -> list[AnomalyLog]:
    query = db.query(AnomalyLog)
    if is_resolved is not None:
        query = query.filter(AnomalyLog.is_resolved == is_resolved)
    return query.order_by(desc(AnomalyLog.created_at)).limit(limit).all()


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