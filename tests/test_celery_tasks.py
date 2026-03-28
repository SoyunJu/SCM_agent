# ── tests/test_celery_tasks.py ────────────────────────────────────────────────
"""
Celery 태스크 단위 테스트
- DB 및 분석기는 Mock 처리
- 캐시 히트/미스 분기, 예외 처리 검증
"""
import json
import pytest
from unittest.mock import MagicMock, patch


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def sample_products():
    p = MagicMock()
    p.code, p.name, p.category, p.safety_stock = "P001", "상품A", "카테고리1", 10
    return [p]


@pytest.fixture
def sample_sales():
    s = MagicMock()
    s.date, s.product_code, s.qty, s.revenue = "2026-03-01", "P001", 5, 50000.0
    return [s]


@pytest.fixture
def sample_stocks():
    s = MagicMock()
    s.product_code, s.current_stock, s.restock_date, s.restock_qty = "P001", 100, None, None
    return [s]


# ── 캐시 히트 테스트 ──────────────────────────────────────────────────────────

def test_run_demand_forecast_redis_cache_hit():
    """Redis 캐시 히트 시 분석기 호출 없이 즉시 반환"""
    cached_items = [{"product_code": "P001", "forecast": 10}]

    with patch("app.celery_app.tasks.cache_get", return_value=cached_items), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session:

        from app.celery_app.tasks import run_demand_forecast
        result = run_demand_forecast(forecast_days=14)

        assert result["from_cache"] is True
        assert result["items"] == cached_items
        mock_session.assert_not_called()   # DB 세션 불필요


def test_run_abc_analysis_redis_cache_hit():
    """ABC 분석 Redis 캐시 히트"""
    cached_items = [{"product_code": "P001", "grade": "A"}]

    with patch("app.celery_app.tasks.cache_get", return_value=cached_items), \
            patch("app.celery_app.tasks.SessionLocal"):

        from app.celery_app.tasks import run_abc_analysis_task
        result = run_abc_analysis_task(days=90)

        assert result["from_cache"] is True
        assert result["items"] == cached_items


# ── 캐시 미스 → 분석 실행 테스트 ─────────────────────────────────────────────

def test_run_demand_forecast_cache_miss_runs_analysis(
        sample_products, sample_sales, sample_stocks
):
    """캐시 미스 시 분석기 호출 및 결과 캐시 저장 확인"""
    expected_items = [{"product_code": "P001", "forecast_qty": 7}]

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached", return_value=None), \
            patch("app.celery_app.tasks._build_dataframes") as mock_build, \
            patch("app.celery_app.tasks._store_cache") as mock_store, \
            patch("app.analyzer.demand_forecaster.run_demand_forecast_all",
                  return_value=expected_items):

        import pandas as pd
        mock_build.return_value = (
            pd.DataFrame([{"상품코드": "P001", "상품명": "상품A", "카테고리": "카테고리1", "안전재고기준": 10}]),
            pd.DataFrame([{"날짜": "2026-03-01", "상품코드": "P001", "판매수량": 5, "매출액": 50000}]),
            pd.DataFrame([{"상품코드": "P001", "현재재고": 100, "입고예정일": "", "입고예정수량": 0}]),
        )
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value = mock_db

        from app.celery_app.tasks import run_demand_forecast
        result = run_demand_forecast(forecast_days=14)

        assert result["from_cache"] is False
        assert result["items"] == expected_items
        mock_store.assert_called_once()


# ── 빈 상품 데이터 테스트 ────────────────────────────────────────────────────

def test_run_demand_forecast_empty_products():
    """분석 대상 상품 없을 때 빈 items 반환"""
    import pandas as pd

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached", return_value=None), \
            patch("app.celery_app.tasks._build_dataframes") as mock_build, \
            patch("app.celery_app.tasks._store_cache"):

        mock_build.return_value = (
            pd.DataFrame(columns=["상품코드", "상품명", "카테고리", "안전재고기준"]),  # 빈 마스터
            pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"]),
            pd.DataFrame(columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"]),
        )
        mock_session_cls.return_value = MagicMock()

        from app.celery_app.tasks import run_demand_forecast
        result = run_demand_forecast(forecast_days=14)

        assert result["items"] == []
        assert result["from_cache"] is False


# ── 예외 처리 테스트 ─────────────────────────────────────────────────────────

def test_run_demand_forecast_exception_handled():
    """분석기 예외 발생 시 Ignore로 처리 (태스크 밖으로 예외 전파 안 됨)"""
    from celery.exceptions import Ignore

    with patch("app.celery_app.tasks.cache_get", return_value=None), \
            patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.celery_app.tasks._get_cached", return_value=None), \
            patch("app.celery_app.tasks._build_dataframes",
                  side_effect=RuntimeError("DB 연결 실패")):

        mock_session_cls.return_value = MagicMock()

        from app.celery_app.tasks import run_demand_forecast
        with pytest.raises(Ignore):
            run_demand_forecast(forecast_days=14)


def test_run_cleanup_deletes_old_data():
    """cleanup 태스크 — 삭제 건수 반환 및 예외 없이 완료"""
    with patch("app.celery_app.tasks.SessionLocal") as mock_session_cls, \
            patch("app.db.repository.delete_old_daily_sales", return_value=120) as mock_sales_del, \
            patch("app.db.repository.delete_old_analysis_cache", return_value=30) as mock_cache_del, \
            patch("app.db.repository.get_setting", return_value="365"):

        mock_session_cls.return_value = MagicMock()

        from app.celery_app.tasks import run_cleanup
        result = run_cleanup()

        assert "deleted_sales" in result
        assert "deleted_cache" in result
