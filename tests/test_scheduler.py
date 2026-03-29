"""
스케줄러 jobs.py 단위 테스트
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import pandas as pd


def _empty_df(*cols):
    return pd.DataFrame(columns=list(cols))


def test_run_daily_job_success():
    """일일 작업 정상 완료 — 예외 없이 실행되면 통과"""

    with patch("app.scheduler.jobs._get_crawled_df") as mock_crawl, \
            patch("app.sheets.writer.upsert_master_from_excel"), \
            patch("app.sheets.writer.write_stock_upsert"), \
            patch("app.scheduler.jobs.os.path.exists", return_value=False), \
            patch("app.scheduler.jobs.read_product_master") as mock_master, \
            patch("app.scheduler.jobs.read_sales") as mock_sales, \
            patch("app.scheduler.jobs.read_stock") as mock_stock, \
            patch("app.scheduler.jobs.SyncService") as mock_sync, \
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
            patch("app.scheduler.jobs.notify_daily_report", return_value=True), \
            patch("app.scheduler.jobs.notify_anomaly_alert"), \
            patch("app.scheduler.jobs.SessionLocal") as mock_session, \
            patch("app.scheduler.jobs.create_report_execution") as mock_create, \
            patch("app.scheduler.jobs.update_report_execution"), \
            patch("app.scheduler.jobs.update_last_run"):

        mock_crawl.return_value = _empty_df("상품코드", "상품명", "카테고리", "가격", "재고여부")
        mock_master.return_value = pd.DataFrame({
            "상품코드": ["P001"], "상품명": ["테스트"],
            "카테고리": ["카테고리1"], "안전재고기준": [10],
        })
        mock_sales.return_value = _empty_df("날짜", "상품코드", "판매수량", "매출액")
        mock_stock.return_value = _empty_df("상품코드", "현재재고", "입고예정일", "입고예정수량")
        mock_pdf.return_value = Path("reports/daily_report_test.pdf")

        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(id=1)
        mock_sync.sync_all_from_sheets.return_value = None

        from app.scheduler.jobs import run_daily_job
        run_daily_job()   # 예외 없이 완료되면 통과


def test_run_daily_job_failure_handled():
    """_get_crawled_df 실패 시 FAILURE 상태로 기록되고 예외 미전파"""

    with patch("app.scheduler.jobs._get_crawled_df",
               side_effect=Exception("크롤링 실패")), \
            patch("app.scheduler.jobs.SessionLocal") as mock_session, \
            patch("app.scheduler.jobs.create_report_execution") as mock_create, \
            patch("app.scheduler.jobs.update_report_execution") as mock_update, \
            patch("app.scheduler.jobs.update_last_run"):

        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_create.return_value = MagicMock(id=1)

        from app.scheduler.jobs import run_daily_job
        run_daily_job()   # 예외가 밖으로 나오면 안 됨

        # FAILURE 상태로 update_report_execution 호출됐는지 확인
        assert mock_update.called
        call_kwargs = mock_update.call_args.kwargs
        assert call_kwargs["status"].value.lower() == "failure"