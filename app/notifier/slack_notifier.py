
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from loguru import logger
from app.config import settings


_client: WebClient | None = None


def get_slack_client() -> WebClient:
    global _client
    if _client is None:
        _client = WebClient(token=settings.slack_bot_token)
    return _client


def send_message(text: str, channel_id: str | None = None) -> bool:

    channel = channel_id or settings.slack_channel_id
    try:
        client = get_slack_client()
        client.chat_postMessage(channel=channel, text=text)
        logger.info(f"Slack 메시지 전송 완료: {channel}")
        return True
    except SlackApiError as e:
        logger.error(f"Slack 메시지 전송 실패: {e.response['error']}")
        return False
    except Exception as e:
        logger.error(f"Slack 메시지 전송 실패 (알 수 없는 오류): {e}")
        return False


def send_blocks(blocks: list[dict], text: str = "", channel_id: str | None = None) -> bool:

    channel = channel_id or settings.slack_channel_id
    try:
        client = get_slack_client()
        client.chat_postMessage(
            channel=channel,
            text=text,
            blocks=blocks,
        )
        logger.info(f"Slack 블록 메시지 전송 완료: {channel}")
        return True
    except SlackApiError as e:
        logger.error(f"Slack 블록 메시지 전송 실패: {e.response['error']}")
        return False
    except Exception as e:
        logger.error(f"Slack 블록 메시지 전송 실패 (알 수 없는 오류): {e}")
        return False


def send_pdf(pdf_path: Path, title: str = "일일 현황 보고서", channel_id: str | None = None) -> bool:

    channel = channel_id or settings.slack_channel_id
    if not pdf_path.exists():
        logger.error(f"PDF 파일 없음: {pdf_path}")
        return False
    try:
        client = get_slack_client()
        with open(pdf_path, "rb") as f:
            client.files_upload_v2(
                channel=channel,
                file=f,
                filename=pdf_path.name,
                title=title,
            )
        logger.info(f"Slack PDF 전송 완료: {pdf_path.name}")
        return True
    except SlackApiError as e:
        logger.error(f"Slack PDF 전송 실패: {e.response['error']}")
        return False
    except Exception as e:
        logger.error(f"Slack PDF 전송 실패 (알 수 없는 오류): {e}")
        return False


def send_daily_report_notification(
        report_date: str,
        total_products: int,
        stock_anomaly_count: int,
        sales_anomaly_count: int,
        risk_level: str,
        pdf_path: Path,
) -> bool:

    # 위험도별 이모지
    risk_emoji = {
        "low":      "🟢",
        "medium":   "🟡",
        "high":     "🟠",
        "critical": "🔴",
    }.get(risk_level, "⚪")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f" 일일 재고 현황 보고서 - {report_date}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*전체 상품*\n{total_products}개"},
                {"type": "mrkdwn", "text": f"*위험도*\n{risk_emoji} {risk_level.upper()}"},
                {"type": "mrkdwn", "text": f"*재고 이상*\n{stock_anomaly_count}건"},
                {"type": "mrkdwn", "text": f"*판매 이상*\n{sales_anomaly_count}건"},
            ],
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "📎 아래 PDF 보고서를 확인하세요 | SCM Agent 자동 생성",
                }
            ],
        },
    ]

    msg_ok = send_blocks(
        blocks=blocks,
        text=f"[SCM Agent] 일일 보고서 - {report_date} | 위험도: {risk_level.upper()}",
    )

    pdf_ok = send_pdf(pdf_path=pdf_path, title=f"일일 현황 보고서 {report_date}")

    return msg_ok and pdf_ok