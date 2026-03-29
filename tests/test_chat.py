import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    with patch("app.main.check_db_connection", return_value=True), \
            patch("app.main.init_db"), \
            patch("app.main._seed_superadmin"), \
            patch("app.main._warmup_sheets"):

        from app.main import app
        from app.db.connection import get_db
        app.dependency_overrides[get_db] = lambda: MagicMock()

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture
def auth_token(client):
    res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "admin1!",
    })
    if res.status_code != 200:
        pytest.skip("로그인 실패")
    return res.json()["access_token"]


def test_slack_url_verification(client):
    res = client.post("/scm/chat/slack/webhook", json={
        "type": "url_verification",
        "challenge": "test_challenge_token",
    })
    assert res.status_code == 200
    assert res.json()["challenge"] == "test_challenge_token"


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
    res = client.post("/scm/chat/query", json={
        "message": "재고 알려줘",
        "session_id": "test",
        "user_id": "admin",
    })
    assert res.status_code == 401


def test_chat_query_with_auth(client, auth_token):
    with patch("app.api.chat_router.run_agent", return_value="재고 부족 상품 없음"):
        res = client.post(
            "/scm/chat/query",
            json={"message": "재고 알려줘", "session_id": "test-001", "user_id": "admin"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert res.status_code == 200
    assert "reply" in res.json()
    assert res.json()["session_id"] == "test-001"