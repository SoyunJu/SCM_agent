import asyncio
import os
from datetime import date

import pandas as pd
from loguru import logger

from app.ai.insight_generator import generate_daily_insight
from app.ai.sentiment_analyzer import batch_analyze_sales_anomalies
from app.analyzer.sales_analyzer import run_sales_analysis
from app.analyzer.stock_analyzer import run_stock_analysis
from app.cache.redis_client import cache_get, cache_delete
from app.crawler.excel_parser import parse_stock_sheet, parse_sales_sheet
from app.crawler.order_scraper import generate_orders
from app.crawler.scraper import crawl_all_sites
from app.db.connection import SessionLocal
from app.db.models import ReportType, ExecutionStatus, AnomalyType, Severity
from app.db.repository import (
    create_report_execution, update_report_execution,
    create_anomaly_log, update_last_run, get_setting,
)
from app.services.sync_service import SyncService
from app.notifier.notifier import notify_daily_report, notify_anomaly_alert
from app.report.pdf_generator import generate_daily_pdf
from app.sheets.reader import read_product_master, read_sales, read_stock
from app.sheets.writer import (
    write_stock_upsert, write_sales, upsert_master_from_excel, upsert_stock_from_excel, write_orders,
    write_analysis_result,
)

EXCEL_PATH = os.getenv("EXCEL_PATH", "./sample_data.xlsx")


def _sync_excel_to_sheets(excel_path: str) -> None:
    df_sales_excel = parse_sales_sheet(excel_path)
    write_sales(df_sales_excel)
    upsert_master_from_excel(df_sales_excel)
    try:
        df_stock_excel = parse_stock_sheet(excel_path)
        upsert_stock_from_excel(df_stock_excel)
        upsert_master_from_excel(df_stock_excel)
    except Exception as e:
        logger.warning(f"엑셀 재고 파싱 스킵: {e}")


def _get_crawled_df() -> pd.DataFrame:
    cached = cache_get("crawler:results")
    if cached:
        logger.info("Redis에서 크롤 결과 로드")
        return pd.DataFrame(cached)
    logger.info("Redis 캐시 없음 — 직접 크롤링")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return crawl_all_sites(books_pages=3, webscraper_pages=2, scrapingcourse_pages=2)


def _sync_sheets_to_db() -> None:
    from app.services.sync_service import SyncService
    db = SessionLocal()
    try:
        SyncService.sync_all_from_sheets(db)
    finally:
        db.close()


# 수동 동기화
def sync_sheets_only() -> dict:
    logger.info("===== Sheets 동기화 시작 =====")
    df_crawled = _get_crawled_df()
    if not df_crawled.empty:
        # 마스터 먼저 upsert
        upsert_master_from_excel(df_crawled)
        # 재고현황 upsert
        write_stock_upsert(df_crawled)
    if os.path.exists(EXCEL_PATH):
        _sync_excel_to_sheets(EXCEL_PATH)
    # Redis 캐시 무효화
    for sheet_name in ["상품마스터", "일별판매", "재고현황"]:
        cache_delete(f"sheets:{sheet_name}")
    # Sheets → DB 동기화
    _sync_sheets_to_db()
    logger.info("===== Sheets 동기화 완료 =====")
    return {"crawled": len(df_crawled) if not df_crawled.empty else 0}


def sync_sheets_to_db_incremental() -> dict:
    logger.info("===== [1분주기] Sheets → DB 동기화 시작 =====")
    result = {"products": 0, "sales": 0, "stock": 0, "error": None}
    db = SessionLocal()
    try:
        for sheet_name in ["상품마스터", "일별판매", "재고현황"]:
            cache_delete(f"sheets:{sheet_name}")

        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()

        if not df_master.empty:
            products = [
                {
                    "code":         str(r.get("상품코드", "")),
                    "name":         str(r.get("상품명", "")),
                    "category":     r.get("카테고리"),
                    "safety_stock": int(r.get("안전재고기준", 0) or 0),
                    "source":       "sheets",
                }
                for r in df_master.to_dict("records")
                if r.get("상품코드")
            ]
            res = bulk_upsert_products(db, products)
            result["products"] = res.get("inserted", 0) + res.get("updated", 0)

        if not df_sales.empty:
            sales = [
                {
                    "date":         str(r.get("날짜", "")),
                    "product_code": str(r.get("상품코드", "")),
                    "qty":          int(r.get("판매수량", 0) or 0),
                    "revenue":      float(r.get("매출액", 0) or 0),
                    "cost":         float(r.get("매입액", 0) or 0),
                }
                for r in df_sales.to_dict("records")
                if r.get("상품코드") and r.get("날짜")
            ]
            res = bulk_upsert_daily_sales(db, sales)
            result["sales"] = res.get("inserted", 0) + res.get("updated", 0)

        if not df_stock.empty:
            stock = [
                {
                    "product_code":  str(r.get("상품코드", "")),
                    "current_stock": int(r.get("현재재고", 0) or 0),
                    "restock_date":  r.get("입고예정일") or None,
                    "restock_qty":   r.get("입고예정수량"),
                }
                for r in df_stock.to_dict("records")
                if r.get("상품코드")
            ]
            res = bulk_upsert_stock_levels(db, stock)
            result["stock"] = res.get("inserted", 0) + res.get("updated", 0)

        logger.info(f"[1분주기] DB 동기화 완료: {result}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[1분주기] DB 동기화 실패: {e}")
    finally:
        db.close()
    return result


def run_daily_job(
        execution_id: int | None = None,
        severity_filter: list[str] | None = None,
        category_filter: list[str] | None = None,
) -> None:
    logger.info("========== 보고서 생성 작업 시작 ==========")
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
            upsert_master_from_excel(df_crawled)   # 마스터 선행
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

        # --- 6. 인사이트 생성 ---
        logger.info("[5/7] 인사이트 생성")
        insight = generate_daily_insight(
            stock_anomalies=list(stock_anomalies),
            sales_anomalies=list(sales_anomalies),
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

        # --- 7. DB 저장 ---
        for item in stock_anomalies:
            create_anomaly_log(
                db=db,
                product_code=item["product_code"],
                product_name=item.get("product_name", ""),
                category=item.get("category"),
                anomaly_type=AnomalyType(str(item["anomaly_type"]).upper()),
                severity=Severity(str(item["severity"]).upper()),
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

        # --- SSE + 이상징후 알림 ---
        all_anomalies = list(stock_anomalies) + list(sales_anomalies)
        critical_items = [
            i for i in all_anomalies
            if str(i.get("severity", "")).upper() in ("CRITICAL", "HIGH")
        ]

        if critical_items:
            from app.api.alert_router import sync_broadcast_alert
            for item in critical_items:
                sync_broadcast_alert({
                    "type":         "critical_anomaly",
                    "severity":     str(item.get("severity", "")),
                    "product_code": item.get("product_code", ""),
                    "product_name": item.get("product_name", ""),
                    "anomaly_type": str(item.get("anomaly_type", "")),
                    "message":      f"[긴급] {item.get('product_name')} - {item.get('anomaly_type')}",
                })
                notify_anomaly_alert(
                    product_name=item.get("product_name", ""),
                    anomaly_type=str(item.get("anomaly_type", "")),
                    severity=str(item.get("severity", "")),
                    message=f"{item.get('product_name')} ({item.get('product_code')}) 이상 감지",
                    db=db,
                )

        # --- 8. PDF 보고서 생성 ---
        logger.info("[6/7] PDF 보고서 생성")
        pdf_path = None
        pdf_ok   = False
        try:
            pdf_path = generate_daily_pdf(
                report_date=date.today(),
                total_products=len(df_master),
                stock_anomalies=[dict(a) for a in filtered_stock],
                sales_anomalies=filtered_sales,
                insight=insight,
            )
            pdf_ok = True
        except Exception as pdf_err:
            logger.error(f"PDF 생성 실패: {pdf_err}")

        # --- 9. Slack + 이메일 발송 ---
        slack_ok = False
        if pdf_ok:
            logger.info("[7/7] 알림 발송")
            try:
                notify_daily_report(
                    report_date=date.today().strftime("%Y-%m-%d"),
                    total_products=len(df_master),
                    stock_anomaly_count=len(stock_anomalies),
                    sales_anomaly_count=len(sales_anomalies),
                    risk_level=insight.get("risk_level", "medium"),
                    pdf_path=pdf_path,
                    db=db,
                )
                slack_ok = True
            except Exception as notify_err:
                logger.warning(f"알림 발송 실패(스킵): {notify_err}")
        else:
            logger.info("[7/7] 알림 발송 건너뜀 (PDF 생성 실패)")

        # --- 분석결과 시트 기록 ---
        try:
            df_analysis = pd.DataFrame(all_anomalies)
            if not df_analysis.empty:
                write_analysis_result(df_analysis)
        except Exception as e:
            logger.warning(f"분석결과 시트 기록 실패(스킵): {e}")

        # --- Sheets → DB 최종 동기화 ---
        _sync_sheets_to_db()

        update_report_execution(db=db, record_id=execution_id, status=ExecutionStatus.SUCCESS, slack_sent=slack_ok)
        update_last_run(db, "daily_report")
        logger.info("========== 보고서 생성 작업 완료 ==========")

    except Exception as e:
        logger.error(f"보고서 생성 작업 실패: {e}")
        update_report_execution(db=db, record_id=execution_id, status=ExecutionStatus.FAILURE, error_message=str(e))
    finally:
        db.close()