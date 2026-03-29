"""
Celery 태스크 단위 테스트
- update_state / SessionLocal / _get_cache_ttl / _get_cache_max_age 전부 Mock
- .run() 호출로 Celery 인프라 우회
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch


# ── 공통 patch 컨텍스트 헬퍼 ─────────────────────────────────────────────────
# update_state + _get_cache_ttl + _get_cache_max_age 는 모든 테스트에서 필요
_BASE_PATCHES = [
    "app.celery_app.tasks._get_cache_ttl",
    "app.celery_app.tasks._get_cache_max_age",
]


def _base_mocks():
    """항상 필요한 patch 반환 (dict)"""
    return {
        "ttl":     patch("app.celery_app.tasks._get_cache_ttl",    return_value=7200),
        "max_age": patch("app.celery_app.tasks._get_cache_max_age", return_value=120),
    }


# ── Redis 캐시 히트 ───────────────────────────────────────────────────────────

def test_run_demand_forecast_redis_cache_hit():
    """Redis 캐시 히트 시 분석기·DB 미호출"""
    cached_items = [{"product_code": "P001", "forecast": 10}]

    with patch("app.celery_app.tasks.cache_get", return_value=cached_items), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session, \
            patch("app.celery_app.tasks._get_cache_ttl",    return_value=7200), \
            patch("app.celery_app.tasks._get_cache_max_age", return_value=120):

        from app.celery_app.tasks import run_demand_forecast
        result = run_demand_forecast.run(forecast_days=14)

        assert result["from_cache"] is True
        assert result["items"] == cached_items
        mock_session.assert_not_called()


def test_run_abc_analysis_redis_cache_hit():
    """ABC 분석 Redis 캐시 히트"""
    cached_items = [{"product_code": "P001", "grade": "A"}]

    with patch("app.celery_app.tasks.cache_get", return_value=cached_items), \
            patch("app.celery_app.tasks.SessionLocal"), \
            patch("app.celery_app.tasks._get_cache_ttl",    return_value=7200), \
            patch("app.celery_app.tasks._get_cache_max_age", return_value=120):

        from app.celery_app.tasks import run_abc_analysis_task
        result = run_abc_analysis_task.run(days=90)

        assert result["from_cache"] is True
        assert result["items"] == cached_items


# ── 캐시 미스 → 분석 실행 ────────────────────────────────────────────────────

def test_run_demand_forecast_cache_miss_runs_analysis():
    """캐시 미스 시 분석기 호출 + 결과 저장 확인"""
    expected_items = [{"product_code": "P001", "forecast_qty": 7}]

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached",        return_value=None), \
            patch("app.celery_app.tasks._store_cache") as mock_store, \
            patch("app.celery_app.tasks._get_cache_ttl",    return_value=7200), \
            patch("app.celery_app.tasks._get_cache_max_age", return_value=120), \
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

        # update_state가 task_id=None으로 실패하지 않도록 mock
        from app.celery_app.tasks import run_demand_forecast
        with patch.object(run_demand_forecast, "update_state"):
            result = run_demand_forecast.run(forecast_days=14)

        assert result["from_cache"] is False
        assert result["items"] == expected_items
        mock_store.assert_called_once()


# ── 빈 상품 데이터 ────────────────────────────────────────────────────────────

def test_run_demand_forecast_empty_products():
    """분석 대상 상품 없을 때 빈 items 반환"""
    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached",        return_value=None), \
            patch("app.celery_app.tasks._store_cache"), \
            patch("app.celery_app.tasks._get_cache_ttl",    return_value=7200), \
            patch("app.celery_app.tasks._get_cache_max_age", return_value=120), \
            patch("app.celery_app.tasks._build_dataframes") as mock_build:

        mock_session_cls.return_value = MagicMock()
        mock_build.return_value = (
            pd.DataFrame(columns=["상품코드", "상품명", "카테고리", "안전재고기준"]),
            pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"]),
            pd.DataFrame(columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"]),
        )

        from app.celery_app.tasks import run_demand_forecast
        with patch.object(run_demand_forecast, "update_state"):
            result = run_demand_forecast.run(forecast_days=14)

        assert result["items"] == []
        assert result["from_cache"] is False


# ── 예외 처리 ─────────────────────────────────────────────────────────────────

def test_run_demand_forecast_exception_handled():
    """분석기 예외 → Ignore 발생 확인"""
    from celery.exceptions import Ignore

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached",        return_value=None), \
            patch("app.celery_app.tasks._get_cache_ttl",    return_value=7200), \
            patch("app.celery_app.tasks._get_cache_max_age", return_value=120), \
            patch("app.celery_app.tasks._build_dataframes",
                  side_effect=RuntimeError("DB 연결 실패")):

        mock_session_cls.return_value = MagicMock()

        from app.celery_app.tasks import run_demand_forecast
        with patch.object(run_demand_forecast, "update_state"), \
                pytest.raises(Ignore):
            run_demand_forecast.run(forecast_days=14)


# ── cleanup 태스크 ────────────────────────────────────────────────────────────

def test_run_cleanup_deletes_old_data():
    """cleanup 태스크 정상 완료 확인"""
    with patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.db.repository.delete_old_daily_sales",    return_value=120), \
            patch("app.db.repository.delete_old_analysis_cache", return_value=30), \
            patch("app.db.repository.get_setting",               return_value="365"):

        mock_session_cls.return_value = MagicMock()

        from app.celery_app.tasks import run_cleanup
        result = run_cleanup()

        assert "deleted_sales" in result
        assert "deleted_cache" in result