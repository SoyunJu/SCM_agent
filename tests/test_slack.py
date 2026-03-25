
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from app.notifier.slack_notifier import send_message, send_pdf, send_daily_report_notification


@pytest.fixture
def mock_slack_client():
    with patch("app.notifier.slack_notifier.get_slack_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


def test_send_message_success(mock_slack_client):
    mock_slack_client.chat_postMessage.return_value = {"ok": True}
    result = send_message("테스트 메시지", channel_id="C0TEST")
    assert result is True
    mock_slack_client.chat_postMessage.assert_called_once()


def test_send_message_failure(mock_slack_client):
    from slack_sdk.errors import SlackApiError
    mock_slack_client.chat_postMessage.side_effect = SlackApiError(
        message="channel_not_found",
        response={"ok": False, "error": "channel_not_found"},
    )
    result = send_message("테스트 메시지", channel_id="C0INVALID")
    assert result is False


def test_send_pdf_file_not_found(mock_slack_client):
    result = send_pdf(Path("reports/nonexistent.pdf"))
    assert result is False


def test_send_daily_report_notification(mock_slack_client, tmp_path):
    # 임시 PDF 파일 생성
    pdf_file = tmp_path / "daily_report_test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")

    mock_slack_client.chat_postMessage.return_value = {"ok": True}
    mock_slack_client.files_upload_v2.return_value = {"ok": True}

    result = send_daily_report_notification(
        report_date="2026-03-25",
        total_products=60,
        stock_anomaly_count=2,
        sales_anomaly_count=1,
        risk_level="high",
        pdf_path=pdf_file,
    )
    assert result is True
    mock_slack_client.chat_postMessage.assert_called_once()
    mock_slack_client.files_upload_v2.assert_called_once()