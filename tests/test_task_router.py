# ── tests/test_task_router.py ─────────────────────────────────────────────────
"""
태스크 상태 폴링 엔드포인트 단위 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from fastapi import FastAPI
    from app.api.task_router import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _auth_override():
    from app.api.auth_router import TokenData
    return TokenData(username="tester", role="admin")


@pytest.fixture(autouse=True)
def override_auth(client):
    from fastapi import FastAPI
    from app.api.auth_router import get_current_user
    # TestClient app에 의존성 오버라이드 적용
    client.app.dependency_overrides[get_current_user] = _auth_override


def test_task_status_pending():
    """PENDING 상태 태스크 응답 형식 검증"""
    mock_result = MagicMock()
    mock_result.state  = "PENDING"
    mock_result.result = None
    mock_result.info   = None

    with patch("app.celery_app.celery.celery_app.AsyncResult", return_value=mock_result):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.api.task_router import router
        from app.api.auth_router import get_current_user

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = _auth_override

        c = TestClient(app)
        resp = c.get("/scm/tasks/fake-task-id/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "PENDING"
        assert body["task_id"] == "fake-task-id"
        assert "message" in body


def test_task_status_success():
    """SUCCESS 상태 시 result 포함 확인"""
    mock_result = MagicMock()
    mock_result.state  = "SUCCESS"
    mock_result.result = {"items": [{"product_code": "P001"}], "from_cache": False}
    mock_result.info   = None

    with patch("app.celery_app.celery.celery_app.AsyncResult", return_value=mock_result):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.api.task_router import router
        from app.api.auth_router import get_current_user

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = _auth_override

        c = TestClient(app)
        resp = c.get("/scm/tasks/fake-task-id/status")
        body = resp.json()
        assert body["state"] == "SUCCESS"
        assert "result" in body


def test_task_status_failure():
    """FAILURE 상태 시 error 포함 확인"""
    mock_result = MagicMock()
    mock_result.state  = "FAILURE"
    mock_result.result = "DB 연결 실패"
    mock_result.info   = {"error": "DB 연결 실패"}

    with patch("app.celery_app.celery.celery_app.AsyncResult", return_value=mock_result):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.api.task_router import router
        from app.api.auth_router import get_current_user

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = _auth_override

        c = TestClient(app)
        resp = c.get("/scm/tasks/fake-task-id/status")
        body = resp.json()
        assert body["state"] == "FAILURE"
        assert "error" in body
