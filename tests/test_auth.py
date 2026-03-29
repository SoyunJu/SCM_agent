
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def _mock_user():
    from app.db.models import AdminRole
    u = MagicMock()
    u.id              = 1
    u.username        = "admin"
    u.role            = MagicMock()
    u.role.value      = "superadmin"
    u.is_active       = True
    u.hashed_password = "hashed"
    return u


@pytest.fixture
def client():
    with patch("app.main.check_db_connection", return_value=True), \
            patch("app.main.init_db"), \
            patch("app.main._seed_superadmin"), \
            patch("app.main._warmup_sheets"):
        from app.main import app
        from app.db.connection import get_db
        app.dependency_overrides[get_db] = lambda: MagicMock()
        return TestClient(app, raise_server_exceptions=False)


def test_health_check(client):
    res = client.get("/scm/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_success(client):
    with patch("app.api.auth_router._authenticate_user", return_value=_mock_user()), \
            patch("app.api.auth_router.update_last_login"):
        res = client.post("/scm/auth/login", data={
            "username": "admin",
            "password": "admin1!",
        })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    with patch("app.api.auth_router._authenticate_user", return_value=None):
        res = client.post("/scm/auth/login", data={
            "username": "admin",
            "password": "wrong_password",
        })
    assert res.status_code == 401


def test_protected_route_without_token(client):
    res = client.get("/scm/report/history")
    assert res.status_code == 401


def test_protected_route_with_token(client):
    with patch("app.api.auth_router._authenticate_user", return_value=_mock_user()), \
            patch("app.api.auth_router.update_last_login"):
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
    with patch("app.api.auth_router._authenticate_user", return_value=_mock_user()), \
            patch("app.api.auth_router.update_last_login"):
        login_res = client.post("/scm/auth/login", data={
            "username": "admin",
            "password": "admin1!",
        })
    if login_res.status_code != 200:
        pytest.skip("로그인 실패")

    token = login_res.json()["access_token"]
    with patch("app.api.auth_router.get_admin_user_by_username", return_value=_mock_user()):
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