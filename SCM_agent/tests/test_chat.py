
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    with patch("app.db.connection.check_db_connection", return_value=True), \
            patch("app.db.connection.init_db"), \
            patch("app.main.scheduler") as mock_scheduler:
        mock_scheduler.running = True
        mock_scheduler.get_jobs.return_value = []
        from app.main import app
        return TestClient(app)


@pytest.fixture
def auth_token(client):
    res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "admin1!",
    })
    return res.json()["access_token"]


def test_slack_url_verification(client):
    res = client.post("/scm/chat/slack/webhook", json={
        "type": "url_verification",
        "challenge": "test_challenge_token",
    })
    assert res.status_code == 200
    assert res.json()["challenge"] == "test_challenge_token"

    # 무한 루프 방지
def test_slack_bot_message_ignored(client):
    res = client.post("/scm/chat/slack/webhook", json={
        "type": "event_callback",
        "event": {
            "type": "message",
            "bot_id": "B12345",
            "text": "봇 메시지",
            "channel": "C12345",
            "ts": "1234567890.000001",
        },
    })
    assert res.status_code == 200
    assert res.json()["status"] == "ignored"


def test_slack_webhook_normal_message(client):
    with patch("app.api.chat_router._run_agent_and_reply"), \
            patch("app.api.chat_router.get_slack_client") as mock_slack:
        mock_slack.return_value.chat_postMessage.return_value = {"ok": True}

        res = client.post("/scm/chat/slack/webhook", json={
            "type": "event_callback",
            "event": {
                "type": "message",
                "text": "재고 부족한 상품 알려줘",
                "user": "U12345",
                "channel": "C12345",
                "ts": "1234567890.000001",
            },
        })
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_chat_query_requires_auth(client):
    """인증 없이 챗봇 질의 → 401 확인"""
    res = client.post("/scm/chat/query", json={
        "message": "재고 알려줘",
        "session_id": "test",
        "user_id": "admin",
    })
    assert res.status_code == 401


def test_chat_query_with_auth(client, auth_token):
    """인증 후 챗봇 질의 정상 처리 확인"""
    with patch("app.api.chat_router.run_agent", return_value="재고 부족 상품 없음"):
        res = client.post(
            "/scm/chat/query",
            json={"message": "재고 알려줘", "session_id": "test-001", "user_id": "admin"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert res.status_code == 200
    assert "reply" in res.json()
    assert res.json()["session_id"] == "test-001"