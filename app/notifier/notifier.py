from loguru import logger


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

def _get_channel(db=None) -> str:
    try:
        if db is None:
            return "slack"
        from app.db.repository import get_setting
        return get_setting(db, "ALERT_CHANNEL", "slack")
    except Exception:
        return "slack"


def _get_min_severity(db=None) -> str:
    try:
        if db is None:
            return "HIGH"
        from app.db.repository import get_setting
        return get_setting(db, "ALERT_MIN_SEVERITY", "HIGH")
    except Exception:
        return "HIGH"


def _should_alert(severity: str, min_severity: str) -> bool:
    rank = {"LOW": 0, "CHECK": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    return rank.get(severity.upper(), 0) >= rank.get(min_severity.upper(), 2)


def _get_admin_slack_ids(db) -> list[str]:
    try:
        from app.db.models import AdminUser
        users = db.query(AdminUser).filter(
            AdminUser.is_active == True,
            AdminUser.slack_user_id.isnot(None),
            AdminUser.slack_user_id != "",
            ).all()
        return [u.slack_user_id for u in users]
    except Exception:
        return []


def _save_history(db, alert_type: str, channel: str, message: str,
                  severity: str | None = None,
                  product_code: str | None = None,
                  product_name: str | None = None) -> None:
    if db is None:
        return
    try:
        from app.db.repository import save_alert_history
        save_alert_history(
            db, alert_type=alert_type, channel=channel, message=message,
            severity=severity, product_code=product_code, product_name=product_name,
        )
    except Exception as e:
        logger.warning(f"[알림이력] 저장 실패(스킵): {e}")


def _send_mention(user_id: str, message: str, channel_id: str | None = None) -> None:
    from app.notifier.slack_notifier import send_message
    return send_message(text=f"<@{user_id}> {message}", channel_id=channel_id)


# ── 일일 보고서 알림 ──────────────────────────────────────────────────────────

def notify_daily_report(
        report_date: str,
        anomaly_count: int,
        top_products: list[str],
        pdf_path: str | None = None,
        pdf_bytes: bytes | None = None,
        db=None,
) -> None:
    channel = _get_channel(db)
    logger.info(f"일일 보고서 알림 발송: channel={channel}")

    if channel in ("slack", "both"):
        try:
            from app.notifier.slack_notifier import send_daily_report_notification, send_message
            send_daily_report_notification(
                report_date=report_date,
                anomaly_count=anomaly_count,
                top_products=top_products,
            )
            if pdf_path:
                from app.notifier.slack_notifier import send_pdf_file
                send_pdf_file(pdf_path)

            if db:
                admin_ids = _get_admin_slack_ids(db)
                for uid in admin_ids:
                    dm_text = (
                        f"📊 [{report_date}] 일일 보고서 생성 완료\n"
                        f"이상징후 {anomaly_count}건 | 주요상품: {', '.join(top_products[:3])}"
                    )
                    try:
                        send_message(text=dm_text, channel_id=uid)
                    except Exception as e:
                        logger.warning(f"DM 발송 실패(스킵): {e}")
        except Exception as e:
            logger.error(f"Slack 일일 보고서 알림 실패: {e}")

    if channel in ("email", "both"):
        try:
            from app.notifier.email_notifier import send_daily_report_email
            admin_emails = []
            if db:
                from app.db.models import AdminUser
                admins = db.query(AdminUser).filter(AdminUser.is_active == True).all()
                admin_emails = [a.email for a in admins if a.email and a.is_active]
            send_daily_report_email(
                report_date=report_date,
                anomaly_count=anomaly_count,
                top_products=top_products,
                pdf_bytes=pdf_bytes,
                to=admin_emails if admin_emails else None,
            )
        except Exception as e:
            logger.error(f"Email 일일 보고서 알림 실패: {e}")

    # SSE는 일일 보고서에 별도 push 없음 (보고서 탭 자동 갱신으로 대체)
    _save_history(db, alert_type="daily_report", channel=channel,
                  message=f"[{report_date}] 이상징후 {anomaly_count}건")


# ── 이상징후 단건 알림 ────────────────────────────────────────────────────────

def notify_anomaly_alert(
        product_name: str,
        anomaly_type: str,
        severity:     str,
        message:      str,
        product_code: str | None = None,
        db=None,
) -> None:
    min_severity = _get_min_severity(db)
    if not _should_alert(severity, min_severity):
        return

    channel = _get_channel(db)
    logger.info(f"이상징후 알림: {product_name} ({severity}), channel={channel}")

    if channel in ("slack", "both"):
        try:
            from app.notifier.slack_notifier import send_message
            admin_ids   = _get_admin_slack_ids(db) if db else []
            mention_str = " ".join(f"<@{uid}>" for uid in admin_ids) + " " if admin_ids else ""
            send_message(
                f"{mention_str}🔴 [{severity.upper()}] {product_name} - {anomaly_type}\n{message}"
            )
        except Exception as e:
            logger.error(f"Slack 이상징후 알림 실패: {e}")

    if channel in ("email", "both"):
        # 단건 이상징후는 email 발송 생략 (배치로 처리)
        pass

    if channel in ("sse", "both"):
        try:
            from app.api.alert_router import sync_broadcast_alert
            sync_broadcast_alert({
                "type":         "critical_anomaly",
                "severity":     severity.upper(),
                "product_code": product_code or "",
                "product_name": product_name,
                "anomaly_type": anomaly_type,
                "message":      message,
            })
        except Exception as e:
            logger.warning(f"SSE 이상징후 알림 실패(스킵): {e}")

    _save_history(db, alert_type="anomaly", channel=channel, message=message,
                  severity=severity, product_code=product_code, product_name=product_name)


# ── 이상징후 배치 알림 (묶음) ─────────────────────────────────────────────────

def notify_anomaly_batch(
        items: list,
        db=None,
        sev_str_fn=None,
) -> None:
    if not items:
        return

    def _s(v) -> str:
        if sev_str_fn:
            return sev_str_fn(v)
        s = str(v)
        return s.split(".")[-1].upper() if "." in s else s.upper()

    min_severity = _get_min_severity(db)
    filtered = [i for i in items if _should_alert(_s(i.get("severity", "")), min_severity)]
    if not filtered:
        return

    channel  = _get_channel(db)
    top_sev  = "CRITICAL" if any(_s(i.get("severity", "")) == "CRITICAL" for i in filtered) else "HIGH"
    icon     = "🔴" if top_sev == "CRITICAL" else "🟠"
    batch_msg = f"긴급 이상징후 {len(filtered)}건 감지"

    logger.info(f"[배치알림] {len(filtered)}건 — channel={channel}, top={top_sev}")

    if channel in ("slack", "both"):
        try:
            from app.notifier.slack_notifier import get_slack_client
            from app.config import settings as app_settings

            admin_ids   = _get_admin_slack_ids(db) if db else []
            mention_str = " ".join(f"<@{uid}>" for uid in admin_ids) + " " if admin_ids else ""

            blocks = [
                {"type": "header",
                 "text": {"type": "plain_text", "text": f"{icon} SCM Agent | 긴급 이상징후 {len(filtered)}건"}},
                {"type": "section",
                 "text": {"type": "mrkdwn",
                          "text": f"{mention_str}*{len(filtered)}건*의 이상징후가 감지되었습니다."}},
                {"type": "divider"},
            ]
            for item in filtered[:10]:
                sev   = _s(item.get("severity", ""))
                atype = _s(item.get("anomaly_type", ""))
                sev_icon = "🔴" if sev == "CRITICAL" else "🟠"
                blocks.append({"type": "section", "text": {"type": "mrkdwn",
                                                           "text": f"{sev_icon} *{item.get('product_name', '')}* `{item.get('product_code', '')}` — {atype} / {sev}"}})
            if len(filtered) > 10:
                blocks.append({"type": "context",
                               "elements": [{"type": "mrkdwn", "text": f"외 {len(filtered) - 10}건 추가 감지"}]})

            get_slack_client().chat_postMessage(
                channel=app_settings.slack_channel_id,
                text=f"{icon} 긴급 이상징후 {len(filtered)}건 감지",
                blocks=blocks,
            )
        except Exception as e:
            logger.error(f"[배치알림] Slack 발송 실패: {e}")

    if channel in ("sse", "both"):
        try:
            from app.api.alert_router import sync_broadcast_alert
            sync_broadcast_alert({
                "type":    "critical_anomaly_batch",
                "count":   len(filtered),
                "severity": top_sev,
                "items": [
                    {"product_code": i.get("product_code", ""),
                     "product_name": i.get("product_name", ""),
                     "anomaly_type": _s(i.get("anomaly_type", "")),
                     "severity":     _s(i.get("severity", ""))}
                    for i in filtered
                ],
                "message": batch_msg,
            })
        except Exception as e:
            logger.warning(f"[배치알림] SSE 발송 실패(스킵): {e}")

    _save_history(db, alert_type="anomaly_batch", channel=channel,
                  message=batch_msg, severity=top_sev)