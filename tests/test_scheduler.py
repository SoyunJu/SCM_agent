
import pytest
from unittest.mock import patch, MagicMock


def test_run_daily_job_success():

    with patch("app.scheduler.jobs.crawl_books") as mock_crawl, \
            patch("app.scheduler.jobs.write_product_master"), \
            patch("app.scheduler.jobs.os.path.exists", return_value=False), \
            patch("app.scheduler.jobs.read_product_master") as mock_master, \
            patch("app.scheduler.jobs.read_sales") as mock_sales, \
            patch("app.scheduler.jobs.read_stock") as mock_stock, \
            patch("app.scheduler.jobs.run_stock_analysis", return_value=[]), \
            patch("app.scheduler.jobs.run_sales_analysis", return_value=[]), \
            patch("app.scheduler.jobs.batch_analyze_sales_anomalies", return_value=[]), \
            patch("app.scheduler.jobs.generate_daily_insight", return_value={
                "overall_summary": "테스트 요약",
                "key_issues": [],
                "recommendations": [],
                "risk_level": "low",
            }), \
            patch("app.scheduler.jobs.generate_daily_pdf") as mock_pdf, \
            patch("app.scheduler.jobs.send_daily_report_notification", return_value=True), \
            patch("app.scheduler.jobs.SessionLocal") as mock_session, \
            patch("app.scheduler.jobs.create_report_execution") as mock_create, \
            patch("app.scheduler.jobs.update_report_execution"), \
            patch("app.scheduler.jobs.update_last_run"):

        import pandas as pd
        from pathlib import Path

        mock_crawl.return_value = pd.DataFrame({
            "상품코드": ["CR001"], "상품명": ["테스트"], "카테고리": ["Books"], "가격": [10.0], "재고여부": [1]
        })
        mock_master.return_value = pd.DataFrame({"상품코드": ["CR001"], "상품명": ["테스트"], "카테고리": ["Books"], "안전재고기준": [10]})
        mock_sales.return_value = pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"])
        mock_stock.return_value = pd.DataFrame(columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"])
        mock_pdf.return_value = Path("reports/daily_report_test.pdf")

        # DB Mock
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(id=1)

        from app.scheduler.jobs import run_daily_job
        run_daily_job()   # 예외 없이 완료되면 통과


def test_run_daily_job_failure_handled():

    with patch("app.scheduler.jobs.crawl_books", side_effect=Exception("크롤링 실패")), \
            patch("app.scheduler.jobs.SessionLocal") as mock_session, \
            patch("app.scheduler.jobs.create_report_execution") as mock_create, \
            patch("app.scheduler.jobs.update_report_execution") as mock_update:

        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(id=1)

        from app.scheduler.jobs import run_daily_job
        run_daily_job()   # 예외가 밖으로 나오면 안 됨

        # FAILURE 상태로 업데이트 됐는지 확인
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["status"].value == "failure"