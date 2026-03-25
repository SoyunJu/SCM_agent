
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

        # Mock
@pytest.fixture
def client():
    with patch("app.db.connection.check_db_connection", return_value=True), \
            patch("app.db.connection.init_db"), \
            patch("app.main.scheduler") as mock_scheduler:
        mock_scheduler.running = True
        mock_scheduler.get_jobs.return_value = []
        from app.main import app
        return TestClient(app)


def test_health_check(client):
    res = client.get("/scm/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_success(client):
    res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "admin1!",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "wrong_password",
    })
    assert res.status_code == 401


def test_protected_route_without_token(client):
    res = client.get("/scm/report/history")
    assert res.status_code == 401


def test_protected_route_with_token(client):
    # 로그인
    login_res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "admin1!",
    })
    token = login_res.json()["access_token"]

    # 보호 엔드포인트 접근
    with patch("app.api.report_router.get_report_executions", return_value=[]):
        res = client.get(
            "/scm/report/history",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200


def test_token_refresh(client):
    login_res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "admin1!",
    })
    token = login_res.json()["access_token"]

    res = client.post(
        "/scm/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_invalid_token(client):
    res = client.get(
        "/scm/report/history",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert res.status_code == 401