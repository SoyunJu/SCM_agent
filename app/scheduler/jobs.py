import os
import pandas as pd
from datetime import date
from loguru import logger

from app.sheets.reader import read_product_master, read_sales, read_stock
from app.crawler.scraper import crawl_all_sites
from app.crawler.excel_parser import parse_stock_sheet, parse_sales_sheet
from app.crawler.order_scraper import generate_orders
from app.sheets.writer import (
    write_product_master, write_stock_upsert, write_sales, write_stock,
    upsert_master_from_excel, upsert_stock_from_excel, write_orders,
    write_analysis_result,
)
from app.analyzer.stock_analyzer import run_stock_analysis
from app.analyzer.sales_analyzer import run_sales_analysis
from app.ai.sentiment_analyzer import batch_analyze_sales_anomalies
from app.ai.insight_generator import generate_daily_insight
from app.report.pdf_generator import generate_daily_pdf
from app.notifier.slack_notifier import send_daily_report_notification
from app.db.connection import SessionLocal
from app.db.repository import (
    create_report_execution, update_report_execution,
    create_anomaly_log, update_last_run, get_setting,
)
from app.db.models import ReportType, ExecutionStatus, AnomalyType, Severity
from app.cache.redis_client import cache_get

EXCEL_PATH = os.getenv("EXCEL_PATH", "./sample_data.xlsx")


def _sync_excel_to_sheets(excel_path: str) -> None:
    df_sales_excel = parse_sales_sheet(excel_path)
    write_sales(df_sales_excel)
    upsert_master_from_excel(df_sales_excel)
    try:
        df_stock_excel = parse_stock_sheet(excel_path)
        upsert_stock_from_excel(df_stock_excel)
    except Exception as e:
        logger.warning(f"엑셀 재고 파싱 스킵: {e}")


def _get_crawled_df() -> pd.DataFrame:
    cached = cache_get("crawler:results")
    if cached:
        logger.info("Redis에서 크롤 결과 로드")
        return pd.DataFrame(cached)
    logger.info("Redis 캐시 없음 — 직접 크롤링")
    return crawl_all_sites(books_pages=3, webscraper_pages=2, scrapingcourse_pages=2)


def sync_sheets_only() -> dict:
    logger.info("===== Sheets 동기화 시작 =====")
    df_crawled = _get_crawled_df()
    if not df_crawled.empty:
        write_product_master(df_crawled)
        write_stock_upsert(df_crawled)
    if os.path.exists(EXCEL_PATH):
        _sync_excel_to_sheets(EXCEL_PATH)
    logger.info("===== Sheets 동기화 완료 =====")
    return {"crawled": len(df_crawled) if not df_crawled.empty else 0}


def run_daily_job(
        execution_id: int | None = None,
        severity_filter: list[str] | None = None,
        category_filter: list[str] | None = None,
) -> None:
    logger.info("========== 일일 스케줄 작업 시작 ==========")
    db = SessionLocal()

    if execution_id is None:
        execution = create_report_execution(db, ReportType.DAILY)
        execution_id = execution.id
    else:
        from app.db.repository import get_report_execution_by_id
        execution = get_report_execution_by_id(db, execution_id)
        if not execution:
            execution = create_report_execution(db, ReportType.MANUAL)
            execution_id = execution.id

    try:
        # --- 런타임 설정 ---
        safety_stock_days    = int(get_setting(db, "SAFETY_STOCK_DAYS", "7"))
        safety_stock_default = int(get_setting(db, "SAFETY_STOCK_DEFAULT", "10"))
        critical_days        = int(get_setting(db, "LOW_STOCK_CRITICAL_DAYS", "1"))
        high_days            = int(get_setting(db, "LOW_STOCK_HIGH_DAYS", "3"))
        medium_days          = int(get_setting(db, "LOW_STOCK_MEDIUM_DAYS", "7"))
        surge_threshold      = float(get_setting(db, "SALES_SURGE_THRESHOLD", "50"))
        drop_threshold       = float(get_setting(db, "SALES_DROP_THRESHOLD", "50"))

        # --- 1. Sheets 동기화 ---
        logger.info("[1/7] Sheets 동기화")
        df_crawled = _get_crawled_df()
        if not df_crawled.empty:
            write_product_master(df_crawled)
            write_stock_upsert(df_crawled)
        if os.path.exists(EXCEL_PATH):
            _sync_excel_to_sheets(EXCEL_PATH)

        # --- 2. 데이터 읽기 ---
        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()

        # --- 3. 분석 ---
        logger.info("[2/7] 재고/판매 분석")
        stock_anomalies = run_stock_analysis(
            df_master, df_stock, df_sales,
            safety_stock_days=safety_stock_days,
            safety_stock_default=safety_stock_default,
            critical_days=critical_days,
            high_days=high_days,
            medium_days=medium_days,
        )
        sales_anomalies = run_sales_analysis(
            df_master, df_sales,
            surge_threshold=surge_threshold,
            drop_threshold=drop_threshold,
        )

        # --- 4. 주문 동기화 ---
        logger.info("[3/7] 주문 데이터 동기화")
        try:
            product_codes = df_master["상품코드"].tolist()
            orders = generate_orders(product_codes)
            if orders:
                name_map = dict(zip(df_master["상품코드"], df_master["상품명"]))
                for o in orders:
                    o["상품명"] = name_map.get(o["상품코드"], "")
                write_orders(pd.DataFrame(orders))
        except Exception as e:
            logger.warning(f"주문 동기화 실패(스킵): {e}")

        # --- 5. 감성 분석 ---
        logger.info("[4/7] 감성 분석")
        sales_anomalies = batch_analyze_sales_anomalies(sales_anomalies)

        # --- 6. AI 인사이트 + PDF ---
        logger.info("[5/7] AI 인사이트")
        insight = generate_daily_insight(
            stock_anomalies=stock_anomalies,
            sales_anomalies=sales_anomalies,
            total_products=len(df_master),
        )

        # 심각도/카테고리 필터 적용 (선택적)
        filtered_stock = [
            a for a in stock_anomalies
            if (not severity_filter or a["severity"] in severity_filter)
               and (not category_filter or a.get("category") in category_filter)
        ]
        filtered_sales = [
            a for a in sales_anomalies
            if (not severity_filter or a["severity"] in severity_filter)
               and (not category_filter or a.get("category") in category_filter)
        ]

        logger.info("[6/7] PDF 보고서 생성")
        pdf_path = generate_daily_pdf(
            report_date=date.today(),
            total_products=len(df_master),
            stock_anomalies=[dict(a) for a in filtered_stock],
            sales_anomalies=filtered_sales,
            insight=insight,
        )

        # --- 7. Slack ---
        logger.info("[7/7] Slack 전송")
        slack_ok = send_daily_report_notification(
            report_date=date.today().strftime("%Y-%m-%d"),
            total_products=len(df_master),
            stock_anomaly_count=len(stock_anomalies),
            sales_anomaly_count=len(sales_anomalies),
            risk_level=insight.get("risk_level", "medium"),
            pdf_path=pdf_path,
        )

        # --- 분석결과 시트 기록 ---
        try:
            df_analysis = pd.DataFrame(list(stock_anomalies) + list(sales_anomalies))
            if not df_analysis.empty:
                write_analysis_result(df_analysis)
        except Exception as e:
            logger.warning(f"분석결과 시트 기록 실패(스킵): {e}")

        # --- DB 저장 ---
        for item in stock_anomalies:
            create_anomaly_log(
                db=db,
                product_code=item["product_code"],
                product_name=item["product_name"],
                category=item.get("category"),
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
                category=item.get("category"),
                anomaly_type=AnomalyType(item["anomaly_type"]),
                severity=Severity(item["severity"]),
            )

        # --- SSE 알림 ---
        critical_items = [
            i for i in list(stock_anomalies) + list(sales_anomalies)
            if str(i.get("severity", "")) in ("critical", "high")
        ]
        if critical_items:
            from app.api.alert_router import sync_broadcast_alert
            from app.notifier.slack_notifier import send_message

            for item in critical_items:
                sync_broadcast_alert({
                    "type":         "critical_anomaly",
                    "severity":     str(item.get("severity", "")),
                    "product_code": item.get("product_code", ""),
                    "product_name": item.get("product_name", ""),
                    "anomaly_type": str(item.get("anomaly_type", "")),
                    "message":      f"[긴급] {item.get('product_name')} - {item.get('anomaly_type')}",
                })

            send_message(
                f"🔴 긴급 이상 징후 {len(critical_items)}건!\n"
                + "\n".join(
                    f"• {i.get('product_name')} ({i.get('product_code')})"
                    for i in critical_items[:5]
                )
            )

        update_report_execution(db=db, record_id=execution_id, status=ExecutionStatus.SUCCESS, slack_sent=slack_ok)
        update_last_run(db, "daily_report")
        logger.info("========== 일일 스케줄 작업 완료 ==========")

    except Exception as e:
        logger.error(f"일일 스케줄 작업 실패: {e}")
        update_report_execution(db=db, record_id=execution_id, status=ExecutionStatus.FAILURE, error_message=str(e))
    finally:
        db.close()
