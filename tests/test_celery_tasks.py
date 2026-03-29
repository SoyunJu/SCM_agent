"""
Celery 태스크 단위 테스트
- DB 및 분석기는 Mock 처리
- update_state / task_id Mock 추가
- 캐시 히트/미스 분기, 예외 처리 검증
"""
import json
import pytest
from unittest.mock import MagicMock, patch


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    db = MagicMock()
    # get_setting 호출 시 기본값 반환
    from app.db.repository import get_setting
    return db


def _mock_task_self():
    """Celery self mock — update_state + request.id 포함"""
    mock_self = MagicMock()
    mock_self.request.id = "test-task-id-1234"
    return mock_self


# ── 캐시 히트 테스트 ──────────────────────────────────────────────────────────

def test_run_demand_forecast_redis_cache_hit():
    """Redis 캐시 히트 시 분석기 호출 없이 즉시 반환"""
    cached_items = [{"product_code": "P001", "forecast": 10}]

    with patch("app.celery_app.tasks.cache_get", return_value=cached_items), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session, \
            patch("app.celery_app.tasks._get_cache_ttl", return_value=7200), \
            patch("app.celery_app.tasks._get_cache_max_age", return_value=120):

        from app.celery_app.tasks import run_demand_forecast

        # task.run() 직접 호출 (Celery 인프라 우회)
        result = run_demand_forecast.run(forecast_days=14)

        assert result["from_cache"] is True
        assert result["items"] == cached_items
        mock_session.assert_not_called()


def test_run_abc_analysis_redis_cache_hit():
    """ABC 분석 Redis 캐시 히트"""
    cached_items = [{"product_code": "P001", "grade": "A"}]

    with patch("app.celery_app.tasks.cache_get", return_value=cached_items), \
            patch("app.celery_app.tasks.SessionLocal"), \
            patch("app.celery_app.tasks._get_cache_ttl", return_value=7200), \
            patch("app.celery_app.tasks._get_cache_max_age", return_value=120):

        from app.celery_app.tasks import run_abc_analysis_task
        result = run_abc_analysis_task.run(days=90)

        assert result["from_cache"] is True
        assert result["items"] == cached_items


# ── 캐시 미스 → 분석 실행 테스트 ──────────────────────────────────────────────

def test_run_demand_forecast_cache_miss_runs_analysis():
    """캐시 미스 시 분석기 호출 및 결과 캐시 저장 확인"""
    import pandas as pd
    expected_items = [{"product_code": "P001", "forecast_qty": 7}]

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached", return_value=None), \
            patch("app.celery_app.tasks._store_cache") as mock_store, \
            patch("app.celery_app.tasks._build_dataframes") as mock_build, \
            patch("app.analyzer.demand_forecaster.run_demand_forecast_all",
                  return_value=expected_items):

        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_build.return_value = (
            pd.DataFrame([{"상품코드": "P001", "상품명": "상품A",
                           "카테고리": "카테고리1", "안전재고기준": 10}]),
            pd.DataFrame([{"날짜": "2026-03-01", "상품코드": "P001",
                           "판매수량": 5, "매출액": 50000}]),
            pd.DataFrame([{"상품코드": "P001", "현재재고": 100,
                           "입고예정일": "", "입고예정수량": 0}]),
        )

        from app.celery_app.tasks import run_demand_forecast
        result = run_demand_forecast.run(forecast_days=14)

        assert result["from_cache"] is False
        assert result["items"] == expected_items
        mock_store.assert_called_once()


# ── 빈 상품 데이터 테스트 ─────────────────────────────────────────────────────

def test_run_demand_forecast_empty_products():
    """분석 대상 상품 없을 때 빈 items 반환"""
    import pandas as pd

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached", return_value=None), \
            patch("app.celery_app.tasks._build_dataframes") as mock_build, \
            patch("app.celery_app.tasks._store_cache"):

        mock_session_cls.return_value = MagicMock()
        mock_build.return_value = (
            pd.DataFrame(columns=["상품코드", "상품명", "카테고리", "안전재고기준"]),
            pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"]),
            pd.DataFrame(columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"]),
        )

        from app.celery_app.tasks import run_demand_forecast
        result = run_demand_forecast.run(forecast_days=14)

        assert result["items"] == []
        assert result["from_cache"] is False


# ── 예외 처리 테스트 ──────────────────────────────────────────────────────────

def test_run_demand_forecast_exception_handled():
    """분석기 예외 발생 시 Ignore로 처리"""
    from celery.exceptions import Ignore

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached", return_value=None), \
            patch("app.celery_app.tasks._build_dataframes",
                  side_effect=RuntimeError("DB 연결 실패")):

        mock_session_cls.return_value = MagicMock()

        from app.celery_app.tasks import run_demand_forecast
        with pytest.raises(Ignore):
            run_demand_forecast.run(forecast_days=14)


# ── cleanup 태스크 ────────────────────────────────────────────────────────────

def test_run_cleanup_deletes_old_data():
    """cleanup 태스크 — 삭제 건수 반환 및 예외 없이 완료"""
    with patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.db.repository.delete_old_daily_sales", return_value=120), \
            patch("app.db.repository.delete_old_analysis_cache", return_value=30), \
            patch("app.db.repository.get_setting", return_value="365"):

        mock_session_cls.return_value = MagicMock()

        from app.celery_app.tasks import run_cleanup
        result = run_cleanup()

        assert "deleted_sales" in result
        assert "deleted_cache" in result