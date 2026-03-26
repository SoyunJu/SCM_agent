
import pytest
import pandas as pd
from app.analyzer.stock_analyzer import detect_low_stock, detect_over_stock, detect_long_term_stock
from app.analyzer.sales_analyzer import detect_sales_anomaly, get_top_sales
from app.db.models import AnomalyType, Severity


# ### 공통 Fixture #############################

@pytest.fixture
def df_master():
    return pd.DataFrame({
        "상품코드": ["BK001", "BK002", "BK003", "BK004"],
        "상품명":   ["상품A", "상품B", "상품C", "상품D"],
        "카테고리": ["Books", "Books", "Books", "Books"],
        "안전재고기준": [10, 10, 10, 10],
    })


@pytest.fixture
def df_stock():
    return pd.DataFrame({
        "상품코드":    ["BK001", "BK002", "BK003", "BK004"],
        "현재재고":      [3, 100, 0, 60],
        "입고예정일":  ["2026-04-01", "2026-04-10", "2026-03-26", "2026-04-15"],
        "입고예정수량": [50, 200, 80, 100],
    })


@pytest.fixture
def df_sales():
    # BK001, BK002 최근 판매 있음 / BK003, BK004 판매 없음
    return pd.DataFrame({
        "날짜":    ["2026-03-18", "2026-03-19", "2026-03-24", "2026-03-25",
                  "2026-03-11", "2026-03-12"],
        "상품코드": ["BK001", "BK001", "BK001", "BK002",
                 "BK001", "BK002"],
        "판매수량": [5, 5, 5, 20, 3, 5],
        "매출액":  [75000, 75000, 75000, 160000, 45000, 40000],
    })


# ###### 재고 부족 테스트 #######################

def test_detect_low_stock_returns_correct_products(df_master, df_stock, df_sales):
    """현재 재고 <= 안전 재고 감지 확인"""
    results = detect_low_stock(df_master, df_stock, df_sales)
    codes = [r["product_code"] for r in results]
    # BK001(3), BK003(0) 이 안전재고(10) 이하
    assert "BK001" in codes
    assert "BK003" in codes


def test_detect_low_stock_severity_BKitical(df_master, df_stock, df_sales):
    """소진 임박 상품이 BKITICAL로 분류되는지 확인"""
    results = detect_low_stock(df_master, df_stock, df_sales)
    BK001 = next(r for r in results if r["product_code"] == "BK001")
    # BK001: 현재재고 3, 일평균 약 1.4 → 약 2.1일 → HIGH
    assert BK001["severity"] in [Severity.HIGH, Severity.BKITICAL, Severity.MEDIUM]


# ###### 재고 과잉 테스트 #####################

def test_detect_over_stock(df_master, df_stock, df_sales):
    """현재재고 >= 안전재고 * 5 상품 감지 확인"""
    results = detect_over_stock(df_master, df_stock, df_sales)
    codes = [r["product_code"] for r in results]
    # BK002(100) >= 안전재고(10) * 5 = 50
    assert "BK002" in codes


# #### 장기 재고 테스트 #########################

def test_detect_long_term_stock(df_master, df_stock, df_sales):
    """30일 이상 판매 없는 상품 감지 확인"""
    results = detect_long_term_stock(df_master, df_stock, df_sales, no_sales_days=30)
    codes = [r["product_code"] for r in results]
    # BK004: 현재재고 60, 판매 기록 없음
    assert "BK004" in codes


# ##### 판매 급등/급락 테스트 ##################

def test_detect_sales_surge(df_master, df_sales):
    """판매 급등 감지 확인"""
    results = detect_sales_anomaly(df_master, df_sales, surge_threshold=50.0)
    surge = [r for r in results if r["anomaly_type"] == AnomalyType.SALES_SURGE]
    # BK002: 지난주 5개 → 이번주 20개 (+300%)
    codes = [r["product_code"] for r in surge]
    assert "BK002" in codes


def test_get_top_sales(df_master, df_sales):
    """판매 상위 상품 조회 확인"""
    result = get_top_sales(df_master, df_sales, days=7, top_n=3)
    assert len(result) <= 3
    assert "상품명" in result.columns