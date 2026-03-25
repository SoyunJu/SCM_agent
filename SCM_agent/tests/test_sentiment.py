
import pytest
from app.ai.sentiment_analyzer import (
    analyze_sentiment,
    analyze_sales_anomaly_sentiment,
    batch_analyze_sales_anomalies,
)


def test_analyze_sentiment_returns_label():
    result = analyze_sentiment("매출이 크게 증가하여 긍정적인 신호입니다.")
    assert "label" in result
    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0


def test_analyze_sentiment_negative():
    result = analyze_sentiment("판매량이 급락하여 재고 손실 우려가 큽니다.")
    assert "label" in result


def test_analyze_sales_anomaly_surge():
    result = analyze_sales_anomaly_sentiment(
        product_name="테스트 상품A",
        anomaly_type="sales_surge",
        change_rate=80.0,
    )
    assert "interpretation" in result
    assert "급등" in result["interpretation"]


def test_analyze_sales_anomaly_drop():
    result = analyze_sales_anomaly_sentiment(
        product_name="테스트 상품B",
        anomaly_type="sales_drop",
        change_rate=-60.0,
    )
    assert "급락" in result["interpretation"]


def test_batch_analyze():

    anomalies = [
        {
            "product_code": "BK001",
            "product_name": "상품A",
            "anomaly_type": "sales_surge",
            "change_rate": 75.0,
            "severity": "high",
        },
        {
            "product_code": "BK002",
            "product_name": "상품B",
            "anomaly_type": "sales_drop",
            "change_rate": -55.0,
            "severity": "medium",
        },
    ]
    results = batch_analyze_sales_anomalies(anomalies)
    assert len(results) == 2
    assert "sentiment" in results[0]
    assert "sentiment" in results[1]