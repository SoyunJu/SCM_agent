import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    # app.main이 import한 심볼 기준으로 patch
    with patch("app.main.check_db_connection", return_value=True), \
            patch("app.main.init_db"), \
            patch("app.main._seed_superadmin"), \
            patch("app.main._warmup_sheets"):

        from app.main import app
        from app.db.connection import get_db
        app.dependency_overrides[get_db] = lambda: MagicMock()

        # context manager → lifespan이 patch 범위 안에서 실행됨
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


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
    if login_res.status_code != 200:
        pytest.skip("로그인 실패")
    token = login_res.json()["access_token"]

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
    if login_res.status_code != 200:
        pytest.skip("로그인 실패")
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