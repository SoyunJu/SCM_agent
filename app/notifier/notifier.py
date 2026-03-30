
from pathlib import Path
from loguru import logger


def _get_channel(db=None) -> str:
    if db is None:
        return "slack"
    try:
        from app.db.repository import get_setting
        return get_setting(db, "ALERT_CHANNEL", "slack")
    except Exception:
        return "slack"


def _get_min_severity(db=None) -> str:
    if db is None:
        return "high"
    try:
        from app.db.repository import get_setting
        return get_setting(db, "ALERT_MIN_SEVERITY", "high")
    except Exception:
        return "high"


def _get_admin_slack_ids(db) -> list[str]:
    if db is None:
        return []
    try:
        from app.db.models import AdminUser
        users = db.query(AdminUser).filter(
            AdminUser.is_active == True,
            AdminUser.slack_user_id.isnot(None),
            AdminUser.slack_user_id != "",
            ).all()
        return [u.slack_user_id for u in users]
    except Exception as e:
        logger.warning(f"관리자 Slack ID 조회 실패: {e}")
        return []


_SEVERITY_RANK = {"LOW": 0, "CHECK": 0, "REVIEW": 1, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _should_alert(severity: str, min_severity: str) -> bool:
    s = severity.upper() if severity else ""
    m = min_severity.upper() if min_severity else ""
    return _SEVERITY_RANK.get(s, 0) >= _SEVERITY_RANK.get(m, 2)


def mention_user(
        user_id:    str,
        message:    str,
        channel_id: str | None = None,
) -> bool:

    from app.notifier.slack_notifier import send_message
    return send_message(text=f"<@{user_id}> {message}", channel_id=channel_id)


def notify_daily_report(
        report_date:         str,
        total_products:      int,
        stock_anomaly_count: int,
        sales_anomaly_count: int,
        risk_level:          str,
        pdf_path:            Path | None = None,
        db=None,
) -> None:

    channel = _get_channel(db)
    logger.info(f"일일 보고서 알림 발송: channel={channel}")

    if channel in ("slack", "both"):
        try:
            from app.notifier.slack_notifier import send_daily_report_notification, send_message

            # 1. 채널 전송 (PDF 포함)
            if pdf_path:
                send_daily_report_notification(
                    report_date=report_date,
                    total_products=total_products,
                    stock_anomaly_count=stock_anomaly_count,
                    sales_anomaly_count=sales_anomaly_count,
                    risk_level=risk_level,
                    pdf_path=pdf_path,
                )
            else:
                send_message(
                    f"일일 보고서 완료 (PDF 생성 실패)\n"
                    f"총 {total_products}개 상품 | 재고이상 {stock_anomaly_count}건 | "
                    f"판매이상 {sales_anomaly_count}건\n위험도: {risk_level.upper()}"
                )

            # 2. slack_user_id 설정된 관리자에게 DM 발송
            admin_ids = _get_admin_slack_ids(db)
            if admin_ids:
                dm_text = (
                    f"📋 *일일 보고서 ({report_date})*\n"
                    f"총 {total_products}개 상품 | 재고이상 {stock_anomaly_count}건 | "
                    f"판매이상 {sales_anomaly_count}건 | 위험도: {risk_level.upper()}"
                )
                for uid in admin_ids:
                    send_message(text=dm_text, channel_id=uid)
                logger.info(f"관리자 DM 발송: {len(admin_ids)}명")

        except Exception as e:
            logger.error(f"Slack 일일 보고서 발송 실패: {e}")

    if channel in ("email", "both"):
        try:
            from app.notifier.email_notifier import send_daily_report_email
            from app.db.repository import list_admin_users  # 추가
            admin_emails = []
            if db:
                try:
                    from app.db.connection import SessionLocal
                    _db = db if hasattr(db, "query") else SessionLocal()
                    admins = list_admin_users(_db)
                    admin_emails = [a.email for a in admins if a.email and a.is_active]
                except Exception:
                    pass
            send_daily_report_email(
                report_date=report_date,
                total_products=total_products,
                stock_anomaly_count=stock_anomaly_count,
                sales_anomaly_count=sales_anomaly_count,
                risk_level=risk_level,
                pdf_path=pdf_path,
                to=admin_emails if admin_emails else None,
            )
        except Exception as e:
            logger.error(f"이메일 일일 보고서 발송 실패: {e}")


def notify_anomaly_alert(
        product_name: str,
        anomaly_type: str,
        severity:     str,
        message:      str,
        db=None,
) -> None:

    min_severity = _get_min_severity(db)
    if not _should_alert(severity, min_severity):
        return

    channel = _get_channel(db)
    logger.info(f"이상 징후 알림: {product_name} ({severity}), channel={channel}")

    if channel in ("slack", "both"):
        try:
            from app.notifier.slack_notifier import send_message

            admin_ids = _get_admin_slack_ids(db)
            mention_str = " ".join(f"<@{uid}>" for uid in admin_ids) + " " if admin_ids else ""

            send_message(
                f"{mention_str}🔴 [{severity.upper()}] {product_name} - {anomaly_type}\n{message}"
            )
        except Exception as e:
            logger.error(f"Slack 알림 발송 실패: {e}")

    if channel in ("email", "both"):
        try:
            from app.notifier.email_notifier import send_daily_report_email
        except Exception as e:
            logger.error(f"이메일 알림 발송 실패: {e}")



def notify_anomaly_batch(
        items: list,
        db=None,
        sev_str_fn=None,
) -> None:
    """이상징후 다건을 묶어서 Slack 1회 발송"""
    if not items:
        return

    def _s(v) -> str:
        if sev_str_fn:
            return sev_str_fn(v)
        s = str(v)
        return s.split(".")[-1].upper() if "." in s else s.upper()

    min_severity = _get_min_severity(db)
    # 임계값 이상인 것만 필터
    filtered = [i for i in items if _should_alert(_s(i.get("severity", "")), min_severity)]
    if not filtered:
        return

    channel = _get_channel(db)
    top_sev  = "CRITICAL" if any(_s(i.get("severity", "")) == "CRITICAL" for i in filtered) else "HIGH"
    icon     = "🔴" if top_sev == "CRITICAL" else "🟠"

    logger.info(f"[배치알림] {len(filtered)}건 — channel={channel}, top={top_sev}")

    if channel in ("slack", "both"):
        try:
            from app.notifier.slack_notifier import get_slack_client
            from app.config import settings as app_settings

            admin_ids   = _get_admin_slack_ids(db)
            mention_str = " ".join(f"<@{uid}>" for uid in admin_ids) + " " if admin_ids else ""

            # 헤더 블록
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{icon} SCM Agent | 긴급 이상징후 {len(filtered)}건"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"{mention_str}*{len(filtered)}건*의 이상징후가 감지되었습니다."},
                },
                {"type": "divider"},
            ]

            # 건별 섹션 (최대 10건, 초과 시 생략)
            for item in filtered[:10]:
                sev  = _s(item.get("severity", ""))
                atype = _s(item.get("anomaly_type", ""))
                sev_icon = "🔴" if sev == "CRITICAL" else "🟠"
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"{sev_icon} *{item.get('product_name', '')}* "
                            f"`{item.get('product_code', '')}` — {atype} / {sev}"
                        ),
                    },
                })

            if len(filtered) > 10:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"외 {len(filtered) - 10}건 추가 감지"}],
                })

            get_slack_client().chat_postMessage(
                channel=app_settings.slack_channel_id,
                text=f"{icon} 긴급 이상징후 {len(filtered)}건 감지",
                blocks=blocks,
            )
            logger.info(f"[배치알림] Slack 발송 완료: {len(filtered)}건")
        except Exception as e:
            logger.error(f"[배치알림] Slack 발송 실패: {e}")


