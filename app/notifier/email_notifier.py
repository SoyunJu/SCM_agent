# app/notifier/email_notifier.py

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from loguru import logger
from app.config import settings


def _get_recipients(override: list[str] | None = None) -> list[str]:
    """ALERT_EMAIL_TO 쉼표 구분 파싱. override 있으면 우선 사용"""
    if override:
        return override
    raw = settings.alert_email_to.strip()
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def send_email(
        subject:    str,
        body_html:  str,
        to:         list[str] | None = None,
        attachment: Path | None = None,
) -> bool:
    """SMTP 이메일 발송. attachment는 선택적 파일 첨부(PDF 등)"""
    recipients = _get_recipients(to)
    if not recipients:
        logger.warning("이메일 발송 스킵: 수신자 없음 (ALERT_EMAIL_TO 미설정)")
        return False
    if not settings.smtp_host:
        logger.warning("이메일 발송 스킵: SMTP_HOST 미설정")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"]    = settings.smtp_from or settings.smtp_user
        msg["To"]      = ", ".join(recipients)

        msg.attach(MIMEText(body_html, "html", "utf-8"))

        if attachment and attachment.exists():
            with open(attachment, "rb") as f:
                part = MIMEApplication(f.read(), Name=attachment.name)
            part["Content-Disposition"] = f'attachment; filename="{attachment.name}"'
            msg.attach(part)

        smtp_cls = smtplib.SMTP
        with smtp_cls(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], recipients, msg.as_string())

        logger.info(f"이메일 발송 완료: {recipients}")
        return True
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")
        return False


def send_daily_report_email(
        report_date:        str,
        total_products:     int,
        stock_anomaly_count: int,
        sales_anomaly_count: int,
        risk_level:         str,
        pdf_path:           Path | None = None,
) -> bool:

    risk_color = {
        "low":      "#22c55e",
        "medium":   "#eab308",
        "high":     "#f97316",
        "critical": "#ef4444",
    }.get(risk_level, "#6b7280")

    body = f"""
    <html><body style="font-family:sans-serif;color:#374151;padding:24px;">
      <h2 style="margin-bottom:4px;">📦 SCM Agent 일일 보고서</h2>
      <p style="color:#6b7280;margin-top:0;">{report_date}</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
      <table style="border-collapse:collapse;width:100%;max-width:400px;">
        <tr>
          <td style="padding:8px 16px 8px 0;color:#6b7280;">전체 상품</td>
          <td style="padding:8px 0;font-weight:600;">{total_products}개</td>
        </tr>
        <tr>
          <td style="padding:8px 16px 8px 0;color:#6b7280;">재고 이상</td>
          <td style="padding:8px 0;font-weight:600;">{stock_anomaly_count}건</td>
        </tr>
        <tr>
          <td style="padding:8px 16px 8px 0;color:#6b7280;">판매 이상</td>
          <td style="padding:8px 0;font-weight:600;">{sales_anomaly_count}건</td>
        </tr>
        <tr>
          <td style="padding:8px 16px 8px 0;color:#6b7280;">위험도</td>
          <td style="padding:8px 0;font-weight:600;color:{risk_color};">{risk_level.upper()}</td>
        </tr>
      </table>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
      <p style="color:#9ca3af;font-size:12px;">SCM Agent 자동 생성 보고서</p>
    </body></html>
    """
    return send_email(
        subject=f"[SCM Agent] 일일 보고서 - {report_date} | 위험도: {risk_level.upper()}",
        body_html=body,
        attachment=pdf_path,
    )


def send_alert_email(
        product_name: str,
        anomaly_type: str,
        severity:     str,
        message:      str,
) -> bool:

    severity_color = {
        "critical": "#ef4444",
        "high":     "#f97316",
        "medium":   "#eab308",
        "low":      "#22c55e",
    }.get(severity, "#6b7280")

    body = f"""
    <html><body style="font-family:sans-serif;color:#374151;padding:24px;">
      <h2 style="color:{severity_color};">🔴 SCM 이상 징후 감지</h2>
      <p><strong>상품:</strong> {product_name}</p>
      <p><strong>유형:</strong> {anomaly_type}</p>
      <p><strong>심각도:</strong> <span style="color:{severity_color};font-weight:600;">{severity.upper()}</span></p>
      <p><strong>내용:</strong> {message}</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;">
      <p style="color:#9ca3af;font-size:12px;">SCM Agent 자동 알림</p>
    </body></html>
    """
    return send_email(
        subject=f"[SCM Agent] {severity.upper()} 이상 징후 - {product_name}",
        body_html=body,
    )
