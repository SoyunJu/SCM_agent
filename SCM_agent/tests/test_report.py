
import pytest
from datetime import date
from pathlib import Path
from app.report.template import build_daily_report_html
from app.report.pdf_generator import generate_daily_pdf


@pytest.fixture
def sample_insight():
    return {
        "overall_summary": "재고 부족 2건, 판매 급등 1건이 감지되었습니다.",
        "key_issues": ["CR001 재고 소진 임박", "CR002 판매 급등"],
        "recommendations": ["CR001 긴급 발주 필요", "CR002 재고 확보 검토"],
        "risk_level": "high",
    }


@pytest.fixture
def sample_stock_anomalies():
    return [
        {
            "product_code": "CR001",
            "product_name": "테스트 상품A",
            "anomaly_type": "low_stock",
            "current_stock": 3,
            "safety_stock": 10,
            "daily_avg_sales": 2.5,
            "days_until_stockout": 1.2,
            "severity": "critical",
        }
    ]


@pytest.fixture
def sample_sales_anomalies():
    return [
        {
            "product_code": "CR002",
            "product_name": "테스트 상품B",
            "anomaly_type": "sales_surge",
            "change_rate": 80.0,
            "severity": "high",
            "sentiment": {"label": "긍정", "score": 0.91},
        }
    ]


def test_build_html_contains_key_sections(
        sample_insight, sample_stock_anomalies, sample_sales_anomalies
):

    html = build_daily_report_html(
        report_date=date.today(),
        total_products=60,
        stock_anomalies=sample_stock_anomalies,
        sales_anomalies=sample_sales_anomalies,
        insight=sample_insight,
    )
    assert "일일 재고 현황 보고서" in html
    assert "테스트 상품A" in html
    assert "테스트 상품B" in html
    assert "CR001 긴급 발주 필요" in html


def test_generate_pdf_creates_file(
        sample_insight, sample_stock_anomalies, sample_sales_anomalies
):

    pdf_path = generate_daily_pdf(
        report_date=date.today(),
        total_products=60,
        stock_anomalies=sample_stock_anomalies,
        sales_anomalies=sample_sales_anomalies,
        insight=sample_insight,
    )
    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    # 테스트 후 파일 정리
    pdf_path.unlink(missing_ok=True)