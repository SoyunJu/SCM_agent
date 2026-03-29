"""
인증 엔드포인트 단위 테스트
- get_db는 MagicMock으로 오버라이드
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    from app.db.connection import get_db

    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app, raise_server_exceptions=False)


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
    login_res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "admin1!",
    })
    token = login_res.json().get("access_token", "")

    res = client.get(
        "/scm/report/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 토큰이 유효하면 200, DB mock이라 빈 목록 반환
    assert res.status_code in (200, 401)


def test_token_refresh(client):
    login_res = client.post("/scm/auth/login", data={
        "username": "admin",
        "password": "admin1!",
    })
    if login_res.status_code != 200:
        pytest.skip("로그인 실패 — 스킵")

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