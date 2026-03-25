
from sqlalchemy.orm import Session
from sqlalchemy import desc
from loguru import logger
from typing import Optional
from datetime import datetime

from app.db.models import (
    ReportExecution, AnomalyLog, ScheduleConfig, ChatHistory,
    ReportType, ExecutionStatus, AnomalyType, Severity, ChatRole
)


# ### Report ##############################

def create_report_execution(
        db: Session,
        report_type: ReportType = ReportType.DAILY
) -> ReportExecution:

    record = ReportExecution(report_type=report_type)
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(f"보고서 실행 이력 생성: id={record.id}, type={report_type}")
    return record


def update_report_execution(
        db: Session,
        record_id: int,
        status: ExecutionStatus,
        docs_url: Optional[str] = None,
        slack_sent: bool = False,
        error_message: Optional[str] = None,
) -> Optional[ReportExecution]:

    record = db.query(ReportExecution).filter(ReportExecution.id == record_id).first()
    if not record:
        logger.warning(f"보고서 이력 없음: id={record_id}")
        return None
    record.status = status
    record.docs_url = docs_url
    record.slack_sent = slack_sent
    record.error_message = error_message
    db.commit()
    db.refresh(record)
    logger.info(f"보고서 실행 이력 업데이트: id={record_id}, status={status}")
    return record


def get_report_executions(db: Session, limit: int = 20) -> list[ReportExecution]:
    return db.query(ReportExecution).order_by(desc(ReportExecution.created_at)).limit(limit).all()


# ##### Anomaly ###############

def create_anomaly_log(
        db: Session,
        product_code: str,
        product_name: str,
        anomaly_type: AnomalyType,
        severity: Severity,
        current_stock: Optional[int] = None,
        daily_avg_sales: Optional[float] = None,
        days_until_stockout: Optional[float] = None,
) -> AnomalyLog:

    record = AnomalyLog(
        product_code=product_code,
        product_name=product_name,
        anomaly_type=anomaly_type,
        severity=severity,
        current_stock=current_stock,
        daily_avg_sales=daily_avg_sales,
        days_until_stockout=days_until_stockout,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(f"이상 징후 저장: {product_code} / {anomaly_type} / {severity}")
    return record


def get_anomaly_logs(
        db: Session,
        is_resolved: Optional[bool] = None,
        limit: int = 50
) -> list[AnomalyLog]:

    query = db.query(AnomalyLog)
    if is_resolved is not None:
        query = query.filter(AnomalyLog.is_resolved == is_resolved)
    return query.order_by(desc(AnomalyLog.created_at)).limit(limit).all()


def resolve_anomaly(db: Session, anomaly_id: int) -> Optional[AnomalyLog]:

    record = db.query(AnomalyLog).filter(AnomalyLog.id == anomaly_id).first()
    if not record:
        logger.warning(f"이상 징후 없음: id={anomaly_id}")
        return None
    record.is_resolved = True
    db.commit()
    db.refresh(record)
    logger.info(f"이상 징후 해결 처리: id={anomaly_id}")
    return record


# ##### Schedule #####################

def get_schedule_config(db: Session, job_name: str) -> Optional[ScheduleConfig]:
    return db.query(ScheduleConfig).filter(ScheduleConfig.job_name == job_name).first()


def upsert_schedule_config(
        db: Session,
        job_name: str,
        schedule_hour: int,
        schedule_minute: int,
        timezone: str = "Asia/Seoul",
        is_active: bool = True,
) -> ScheduleConfig:

    record = get_schedule_config(db, job_name)
    if record:
        record.schedule_hour = schedule_hour
        record.schedule_minute = schedule_minute
        record.timezone = timezone
        record.is_active = is_active
    else:
        record = ScheduleConfig(
            job_name=job_name,
            schedule_hour=schedule_hour,
            schedule_minute=schedule_minute,
            timezone=timezone,
            is_active=is_active,
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(f"스케줄 설정 저장: {job_name} {schedule_hour:02d}:{schedule_minute:02d}")
    return record


def update_last_run(db: Session, job_name: str) -> None:

    record = get_schedule_config(db, job_name)
    if record:
        record.last_run_at = datetime.now()
        db.commit()


# ###### ChatHistory ############################

def save_chat_message(
        db: Session,
        session_id: str,
        user_id: str,
        role: ChatRole,
        message: str,
        tool_used: Optional[str] = None,
) -> ChatHistory:

    record = ChatHistory(
        session_id=session_id,
        user_id=user_id,
        role=role,
        message=message,
        tool_used=tool_used,
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