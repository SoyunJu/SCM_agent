# 경로: C:/workspace/SCM_agent/app/scheduler/jobs.py

from datetime import date
from loguru import logger
from app.sheets.reader import read_product_master, read_sales, read_stock
from app.crawler.scraper import crawl_books
from app.crawler.excel_parser import parse_stock_sheet, parse_sales_sheet
from app.sheets.writer import write_product_master, write_sales, write_stock
from app.analyzer.stock_analyzer import run_stock_analysis
from app.analyzer.sales_analyzer import run_sales_analysis
from app.ai.sentiment_analyzer import batch_analyze_sales_anomalies
from app.ai.insight_generator import generate_daily_insight
from app.report.pdf_generator import generate_daily_pdf
from app.notifier.slack_notifier import send_daily_report_notification
from app.db.connection import SessionLocal
from app.db.repository import (
    create_report_execution,
    update_report_execution,
    create_anomaly_log,
    update_last_run,
)
from app.db.models import ReportType, ExecutionStatus, AnomalyType, Severity
from app.config import settings
import os

EXCEL_PATH = os.getenv("EXCEL_PATH", "./sample_data.xlsx")


def run_daily_job() -> None:

    logger.info("========== 일일 스케줄 작업 시작 ==========")
    db = SessionLocal()
    # 실행 이력 생성 (IN_PROGRESS)
    execution = create_report_execution(db, ReportType.DAILY)

    try:
        # 1. Sheets 동기화
        logger.info("[1/6] Sheets 동기화 시작")
        df_crawled = crawl_books(max_pages=3)
        write_product_master(df_crawled)

        if os.path.exists(EXCEL_PATH):
            df_stock = parse_stock_sheet(EXCEL_PATH)
            df_sales_excel = parse_sales_sheet(EXCEL_PATH)
            write_stock(df_stock)
            write_sales(df_sales_excel)
        else:
            logger.warning(f"엑셀 파일 없음 ({EXCEL_PATH}), Sheets 기존 데이터 사용")

        #  2. 데이터 read
        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()

        # 3. 분석
        logger.info("[2/6] 재고/판매 분석")
        stock_anomalies = run_stock_analysis(df_master, df_stock, df_sales)
        sales_anomalies = run_sales_analysis(df_master, df_sales)

        #  4. 감성 분석
        logger.info("[3/6] 감성 분석")
        sales_anomalies = batch_analyze_sales_anomalies(sales_anomalies)

        #  5. AI 인사이트
        logger.info("[4/6] AI 인사이트 생성")
        insight = generate_daily_insight(
            stock_anomalies=stock_anomalies,
            sales_anomalies=sales_anomalies,
            total_products=len(df_master),
        )

        #  6. PDF 생성
        logger.info("[5/6] PDF 보고서 생성")
        pdf_path = generate_daily_pdf(
            report_date=date.today(),
            total_products=len(df_master),
            stock_anomalies=[dict(a) for a in stock_anomalies],
            sales_anomalies=sales_anomalies,
            insight=insight,
        )

        #  7. Slack 전송
        logger.info("[6/6] Slack 전송")
        slack_ok = send_daily_report_notification(
            report_date=date.today().strftime("%Y-%m-%d"),
            total_products=len(df_master),
            stock_anomaly_count=len(stock_anomalies),
            sales_anomaly_count=len(sales_anomalies),
            risk_level=insight.get("risk_level", "medium"),
            pdf_path=pdf_path,
        )

        # 8. DB 이력 저장 （이상 징후）
        for item in stock_anomalies:
            create_anomaly_log(
                db=db,
                product_code=item["product_code"],
                product_name=item["product_name"],
                anomaly_type=AnomalyType(item["anomaly_type"]),
                severity=Severity(item["severity"]),
                current_stock=item.get("current_stock"),
                daily_avg_sales=item.get("daily_avg_sales"),
                days_until_stockout=item.get("days_until_stockout"),
            )
        for item in sales_anomalies:
            create_anomaly_log(
                db=db,
                product_code=item["product_code"],
                product_name=item["product_name"],
                anomaly_type=AnomalyType(item["anomaly_type"]),
                severity=Severity(item["severity"]),
            )

         # 9. 긴급 이상 징후 알림 (CRITICAL/HIGH)
        critical_items = [
            i for i in stock_anomalies + sales_anomalies
            if i.get("severity") in ("critical", "high", Severity.CRITICAL, Severity.HIGH)
        ]
        if critical_items:
            import asyncio
            from app.api.alert_router import broadcast_alert
            from app.notifier.slack_notifier import send_message

            for item in critical_items:
                alert = {
                    "type": "critical_anomaly",
                    "severity": str(item.get("severity", "")),
                    "product_code": item.get("product_code", ""),
                    "product_name": item.get("product_name", ""),
                    "anomaly_type": str(item.get("anomaly_type", "")),
                    "message": f"[긴급] {item.get('product_name')} - {item.get('anomaly_type')}",
                }
                # SSE 브로드캐스트
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(broadcast_alert(alert))
                except Exception as e:
                    logger.warning(f"SSE 알림 전송 실패: {e}")

            # Slack 긴급 메시지
            send_message(
                f"🔴 긴급 이상 징후 {len(critical_items)}건 감지!\n"
                + "\n".join(
                    f"• {i.get('product_name')} ({i.get('product_code')}) - {i.get('anomaly_type')}"
                    for i in critical_items[:5]
                )
            )

        # 실행 이력 성공 업데이트
        update_report_execution(
            db=db,
            record_id=execution.id,
            status=ExecutionStatus.SUCCESS,
            slack_sent=slack_ok,
        )

        update_last_run(db, "daily_report")
        logger.info("========== 일일 스케줄 작업 완료 ==========")

    except Exception as e:
        logger.error(f"일일 스케줄 작업 실패: {e}")
        update_report_execution(
            db=db,
            record_id=execution.id,
            status=ExecutionStatus.FAILURE,
            error_message=str(e),
        )
    finally:
        db.close()