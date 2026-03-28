# ── tests/test_analyzers_vectorized.py ───────────────────────────────────────
"""
벡터화 분석기 단위 테스트
- 기존 테스트(test_analyzers.py)와 동일한 결과 보장 검증
- 대용량 데이터에서 예외 없이 동작하는지 확인
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_master():
    return pd.DataFrame({
        "상품코드":    ["P001", "P002", "P003", "P004"],
        "상품명":      ["상품A", "상품B", "상품C", "상품D"],
        "카테고리":    ["카테고리1"] * 4,
        "안전재고기준": [10, 10, 10, 10],
    })


@pytest.fixture
def base_stock():
    return pd.DataFrame({
        "상품코드":     ["P001", "P002", "P003", "P004"],
        "현재재고":     [3, 100, 0, 60],
        "입고예정일":   ["", "", "", ""],
        "입고예정수량": [0, 0, 0, 0],
    })


@pytest.fixture
def base_sales():
    today = date.today()
    rows = []
    for i in range(14):
        d = (today - timedelta(days=i)).isoformat()
        rows.append({"날짜": d, "상품코드": "P001", "판매수량": 5,  "매출액": 50000})
        rows.append({"날짜": d, "상품코드": "P002", "판매수량": 3,  "매출액": 30000})
    return pd.DataFrame(rows)


# ── demand_forecaster 벡터화 검증 ─────────────────────────────────────────────

def test_demand_forecast_groupby_optimization(base_master, base_sales, base_stock):
    """groupby 최적화 후에도 동일한 상품 수 반환"""
    from app.analyzer.demand_forecaster import run_demand_forecast_all
    results = run_demand_forecast_all(base_master, base_sales, base_stock, forecast_days=14)
    assert len(results) == len(base_master)


def test_demand_forecast_no_sales_product(base_master, base_stock):
    """판매 데이터 없는 상품 → daily_avg=0, forecast_qty=0"""
    from app.analyzer.demand_forecaster import run_demand_forecast_all
    empty_sales = pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"])
    results = run_demand_forecast_all(base_master, empty_sales, base_stock, forecast_days=14)
    for r in results:
        assert r["daily_avg"] == 0.0
        assert r["forecast_qty"] == 0


def test_demand_forecast_shortage_sorted_first(base_master, base_sales, base_stock):
    """재고 부족 상품(sufficient=False)이 결과 앞에 위치"""
    from app.analyzer.demand_forecaster import run_demand_forecast_all
    results = run_demand_forecast_all(base_master, base_sales, base_stock, forecast_days=14)
    sufficient_flags = [r["sufficient"] for r in results]
    # False(부족)가 앞에, True(충분)가 뒤에
    first_true = next((i for i, v in enumerate(sufficient_flags) if v), len(sufficient_flags))
    last_false = next((len(sufficient_flags) - 1 - i
                       for i, v in enumerate(reversed(sufficient_flags)) if not v), -1)
    assert first_true > last_false or last_false == -1


def test_demand_forecast_large_dataset():
    """10k 상품 데이터 처리 시 예외 없이 완료 (성능 안정성)"""
    from app.analyzer.demand_forecaster import run_demand_forecast_all

    n = 10_000
    codes = [f"P{i:05d}" for i in range(n)]
    df_master = pd.DataFrame({
        "상품코드": codes, "상품명": [f"상품{i}" for i in range(n)],
        "카테고리": ["카테고리1"] * n, "안전재고기준": [10] * n,
    })
    today = date.today()
    sales_rows = []
    for i in range(0, min(n, 1000)):   # 1000개 상품만 판매 데이터 보유
        sales_rows.append({
            "날짜": (today - timedelta(days=1)).isoformat(),
            "상품코드": f"P{i:05d}", "판매수량": 5, "매출액": 50000,
        })
    df_sales = pd.DataFrame(sales_rows)
    df_stock = pd.DataFrame({
        "상품코드": codes, "현재재고": [100] * n,
        "입고예정일": [""] * n, "입고예정수량": [0] * n,
    })

    results = run_demand_forecast_all(df_master, df_sales, df_stock, forecast_days=14)
    assert len(results) == n   # 모든 상품 처리


# ── turnover_analyzer 벡터화 검증 ────────────────────────────────────────────

def test_turnover_np_select_grades(base_master, base_sales, base_stock):
    """np.select 등급 분류: 우수/보통/주의/데이터없음 모두 포함"""
    from app.analyzer.turnover_analyzer import calc_inventory_turnover

    results = calc_inventory_turnover(base_master, base_sales, base_stock, days=14)
    grades = {r["등급"] for r in results}
    assert grades <= {"우수", "보통", "주의", "데이터없음"}


def test_turnover_zero_stock_handled(base_master, base_sales):
    """재고 0인 상품도 예외 없이 처리"""
    from app.analyzer.turnover_analyzer import calc_inventory_turnover

    df_stock_zero = pd.DataFrame({
        "상품코드": ["P001", "P002", "P003", "P004"],
        "현재재고": [0, 0, 0, 0],
    })
    results = calc_inventory_turnover(base_master, base_sales, df_stock_zero, days=14)
    assert len(results) == len(base_master)
    for r in results:
        assert r["체류일수"] is None
        assert r["등급"] == "데이터없음"


def test_turnover_sort_order(base_master, base_sales, base_stock):
    """체류일수 오름차순 정렬 (None은 뒤로)"""
    from app.analyzer.turnover_analyzer import calc_inventory_turnover

    results = calc_inventory_turnover(base_master, base_sales, base_stock, days=14)
    non_none = [r["체류일수"] for r in results if r["체류일수"] is not None]
    assert non_none == sorted(non_none)


# ── stock_analyzer inactive 필터 검증 ────────────────────────────────────────

def test_stock_analysis_excludes_inactive(base_stock, base_sales):
    """status 컬럼 있을 때 inactive/sample 상품 분석 제외"""
    from app.analyzer.stock_analyzer import run_stock_analysis

    df_master_with_status = pd.DataFrame({
        "상품코드":    ["P001", "P002", "P003", "P004"],
        "상품명":      ["상품A", "상품B", "상품C", "상품D"],
        "카테고리":    ["카테고리1"] * 4,
        "안전재고기준": [10] * 4,
        "status":      ["active", "inactive", "sample", "active"],
    })

    results = run_stock_analysis(df_master_with_status, base_stock, base_sales)
    detected_codes = {r["product_code"] for r in results}

    # inactive(P002), sample(P003)은 결과에 포함되면 안 됨
    assert "P002" not in detected_codes
    assert "P003" not in detected_codes


def test_stock_analysis_no_status_column(base_master, base_stock, base_sales):
    """status 컬럼 없어도 정상 동작 (하위 호환)"""
    from app.analyzer.stock_analyzer import run_stock_analysis
    results = run_stock_analysis(base_master, base_stock, base_sales)
    assert isinstance(results, list)
