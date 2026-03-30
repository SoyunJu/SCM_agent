
import asyncio
import os
from datetime import date, timedelta

import pandas as pd
from loguru import logger

from app.ai.insight_generator import generate_daily_insight
from app.ai.sentiment_analyzer import batch_analyze_sales_anomalies
from app.analyzer.sales_analyzer import run_sales_analysis
from app.analyzer.stock_analyzer import run_stock_analysis
from app.crawler.order_scraper import generate_orders
from app.crawler.scraper import crawl_all_sites
from app.db.connection import SessionLocal
from app.db.models import ReportType, ExecutionStatus, AnomalyType, Severity
from app.db.repository import (
    create_report_execution, update_report_execution,
    upsert_anomaly_log, update_last_run, get_setting,
)
from app.notifier.notifier import notify_daily_report
from app.report.pdf_generator import generate_daily_pdf
from app.services.sync_service import SyncService
from app.sheets.writer import write_orders, write_analysis_result

EXCEL_PATH = os.getenv("EXCEL_PATH", "./sample_data.xlsx")


# --- 크롤 결과 조회 (Redis 캐시 우선) ---
def _get_crawled_df() -> pd.DataFrame:
    from app.cache.redis_client import cache_get
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


# --- DB에서 분석용 DataFrame 조립 ---
def _load_dataframes_from_db(db) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """DB에서 df_master / df_sales / df_stock 조립 (status 컬럼 포함 → analyzer 자동 필터)"""
    from app.db.models import Product, StockLevel
    from app.db.repository import get_daily_sales_range

    products = db.query(Product).all()
    df_master = pd.DataFrame([
        {
            "상품코드":     p.code,
            "상품명":       p.name,
            "카테고리":     p.category or "",
            "안전재고기준": p.safety_stock,
            "status":       p.status.value.lower(),  # "ACTIVE" → "active"
        }
        for p in products
    ]) if products else pd.DataFrame(columns=["상품코드", "상품명", "카테고리", "안전재고기준", "status"])

    sales_rows = get_daily_sales_range(db, start=date.today() - timedelta(days=90), end=date.today())
    df_sales = pd.DataFrame([
        {
            "날짜":    str(s.date),
            "상품코드": s.product_code,
            "판매수량": s.qty,
            "매출액":  s.revenue,
        }
        for s in sales_rows
    ]) if sales_rows else pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"])

    stocks = db.query(StockLevel).all()
    df_stock = pd.DataFrame([
        {
            "상품코드":     s.product_code,
            "현재재고":     s.current_stock,
            "입고예정일":   str(s.restock_date) if s.restock_date else "",
            "입고예정수량": s.restock_qty or 0,
        }
        for s in stocks
    ]) if stocks else pd.DataFrame(columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"])

    return df_master, df_sales, df_stock


# --- Celery task에서 호출하는 수동/주기 동기화 ---
def sync_sheets_only() -> dict:
    """크롤러 결과 + Excel → Sheets → DB 전체 동기화"""
    logger.info("===== Sheets 동기화 시작 =====")
    from app.sheets.writer import write_stock_upsert, upsert_master_from_excel
    from app.sheets.writer import write_sales

    df_crawled = _get_crawled_df()
    if not df_crawled.empty:
        upsert_master_from_excel(df_crawled)
        write_stock_upsert(df_crawled)

    if os.path.exists(EXCEL_PATH):
        from app.crawler.excel_parser import parse_sales_sheet, parse_stock_sheet
        df_sales_excel = parse_sales_sheet(EXCEL_PATH)
        write_sales(df_sales_excel)
        upsert_master_from_excel(df_sales_excel)
        try:
            df_stock_excel = parse_stock_sheet(EXCEL_PATH)
            from app.sheets.writer import upsert_stock_from_excel
            upsert_stock_from_excel(df_stock_excel)
            upsert_master_from_excel(df_stock_excel)
        except Exception as e:
            logger.warning(f"엑셀 재고 파싱 스킵: {e}")

    db = SessionLocal()
    try:
        SyncService.sync_all_from_sheets(db)
    finally:
        db.close()

    logger.info("===== Sheets 동기화 완료 =====")
    return {"crawled": len(df_crawled) if not df_crawled.empty else 0}


# --- Celery Beat 주기 동기화 ---
def sync_sheets_to_db_incremental() -> dict:
    logger.info("===== Sheets → DB 증분 동기화 시작 =====")
    db = SessionLocal()
    try:
        from app.sheets.reader import read_product_master, read_sales, read_stock
        from app.db.sync import incremental_upsert_daily_sales

        result = {}

        # 상품마스터: 항상 전체 upsert
        result["master"] = SyncService.sync_master(db, read_product_master())

        # 일별판매: watermark 기반 증분
        all_sales = read_sales()
        result["sales"] = incremental_upsert_daily_sales(db, [
            {"date": r.get("날짜"), "product_code": r.get("상품코드"),
             "qty": r.get("판매수량", 0), "revenue": r.get("매출액", 0),
             "cost": r.get("매입액", 0)}
            for r in all_sales.to_dict("records")
        ])

        # 재고현황: 항상 전체 upsert
        result["stock"] = SyncService.sync_stock(db, read_stock())

        logger.info(f"===== Sheets → DB 증분 동기화 완료: {result} =====")
        return result
    except Exception as e:
        logger.error(f"Sheets → DB 증분 동기화 실패: {e}")
        return {"error": str(e)}
    finally:
        db.close()


# --- 일일 보고서 메인 ---
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

        # --- 1. Sheets 동기화 스킵 (Beat 15분 주기 동기화에 위임) ---
        logger.info("[1/7] Sheets 동기화 스킵 (Beat 자동 동기화 사용)")

        # --- 2. DB에서 분석 데이터 로드 ---
        logger.info("[2/7] 재고/판매 분석")
        df_master, df_sales, df_stock = _load_dataframes_from_db(db)

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

        # --- 3. 주문 동기화 ---
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

        # --- 4. 감성 분석 (CRITICAL/HIGH 상위 20건만) ---
        logger.info("[4/7] 감성 분석")
        high_sales = [
            a for a in sales_anomalies
            if str(a.get("severity", "")).upper() in ("CRITICAL", "HIGH")
        ][:20]
        if high_sales:
            analyzed = batch_analyze_sales_anomalies(high_sales)
            analyzed_map = {a.get("product_code"): a for a in analyzed}
            sales_anomalies = [
                analyzed_map.get(a.get("product_code"), a)
                for a in sales_anomalies
            ]
            logger.info(f"[4/7] 감성 분석 완료: {len(high_sales)}건")
        else:
            logger.info("[4/7] 감성 분석 대상 없음 — 스킵")

        # 심각도/카테고리 필터
        filtered_stock = [
            a for a in stock_anomalies
            if (not severity_filter or a.get("severity") in severity_filter)
               and (not category_filter or a.get("category") in category_filter)
        ]
        filtered_sales = [
            a for a in sales_anomalies
            if (not severity_filter or a.get("severity") in severity_filter)
               and (not category_filter or a.get("category") in category_filter)
        ]

        # --- 5. 인사이트 생성 ---
        logger.info("[5/7] 인사이트 생성")
        insight = generate_daily_insight(
            stock_anomalies=list(filtered_stock),
            sales_anomalies=list(filtered_sales),
            total_products=len(df_master),
        )

        # --- 6. DB 저장 ---
        for item in filtered_stock:   # stock_anomalies → filtered_stock
            try:
                raw_type = str(item["anomaly_type"])
                if "." in raw_type: raw_type = raw_type.split(".")[-1]
                raw_sev  = str(item["severity"])
                if "." in raw_sev:  raw_sev  = raw_sev.split(".")[-1]
                upsert_anomaly_log(
                    db=db,
                    product_code=item["product_code"],
                    product_name=item.get("product_name", ""),
                    category=item.get("category"),
                    anomaly_type=AnomalyType(raw_type.upper()),
                    severity=Severity(raw_sev.upper()),
                    current_stock=item.get("current_stock"),
                    daily_avg_sales=item.get("daily_avg_sales"),
                    days_until_stockout=item.get("days_until_stockout"),
                )
            except Exception as upsert_err:
                logger.warning(f"[jobs] stock anomaly upsert 스킵: {item.get('product_code')} — {upsert_err}")
        for item in filtered_sales:
            try:
                raw_type = str(item["anomaly_type"])
                if "." in raw_type: raw_type = raw_type.split(".")[-1]
                raw_sev  = str(item["severity"])
                if "." in raw_sev:  raw_sev  = raw_sev.split(".")[-1]
                upsert_anomaly_log(
                    db=db,
                    product_code=item["product_code"],
                    product_name=item.get("product_name", ""),
                    category=item.get("category"),
                    anomaly_type=AnomalyType(raw_type.upper()),
                    severity=Severity(raw_sev.upper()),
                    current_stock=item.get("current_stock"),
                    daily_avg_sales=item.get("daily_avg_sales"),
                    days_until_stockout=item.get("days_until_stockout"),
                )
            except Exception as upsert_err:
                logger.warning(f"[jobs] sales anomaly upsert 스킵: {item.get('product_code')} — {upsert_err}")

        # --- SSE + 이상징후 알림 ---
        all_anomalies = list(filtered_stock) + list(filtered_sales)

        def _sev_str(v) -> str:
            s = str(v)
            return s.split(".")[-1].upper() if "." in s else s.upper()

        critical_items = [
            i for i in all_anomalies
            if _sev_str(i.get("severity", "")) in ("CRITICAL", "HIGH")
        ]

        if critical_items:
            # SSE — 묶음으로 1번만 전송
            try:
                from app.api.alert_router import sync_broadcast_alert
                batch_payload = {
                    "type":     "critical_anomaly_batch",
                    "count":    len(critical_items),
                    "severity": "CRITICAL" if any(
                        _sev_str(i.get("severity", "")) == "CRITICAL"
                        for i in critical_items
                    ) else "HIGH",
                    "items": [
                        {
                            "product_code": i.get("product_code", ""),
                            "product_name": i.get("product_name", ""),
                            "anomaly_type": _sev_str(i.get("anomaly_type", "")),
                            "severity":     _sev_str(i.get("severity", "")),
                        }
                        for i in critical_items
                    ],
                    "message": f"긴급 이상징후 {len(critical_items)}건 감지",
                }
                sync_broadcast_alert(batch_payload)
            except Exception as e:
                logger.warning(f"SSE 배치 알림 실패(스킵): {e}")

            # Slack — 묶음으로 1번만 발송
            try:
                from app.notifier.notifier import notify_anomaly_batch
                notify_anomaly_batch(critical_items, db=db, sev_str_fn=_sev_str)
            except Exception as e:
                logger.warning(f"Slack 배치 알림 실패(스킵): {e}")

        # --- 7. PDF 보고서 생성 ---
        logger.info("[6/7] PDF 보고서 생성")
        pdf_path = None
        pdf_ok   = False
        try:
            filtered_product_codes = set(
                [a.get("product_code") for a in filtered_stock + filtered_sales]
            )
            display_total = (
                len(set(df_master["상품코드"]).intersection(
                    df_master[df_master["카테고리"].isin(category_filter)]["상품코드"]
                ))
                if category_filter else len(df_master)
            )
            pdf_path = generate_daily_pdf(
                report_date=date.today(),
                total_products=display_total,
                stock_anomalies=[dict(a) for a in filtered_stock],
                sales_anomalies=filtered_sales,
                insight=insight,
            )
            pdf_ok = True
        except Exception as pdf_err:
            logger.error(f"PDF 생성 실패: {pdf_err}")

        # --- 8. Slack + 이메일 발송 ---
        slack_ok = False
        email_ok = False
        if pdf_ok:
            logger.info("[7/7] 알림 발송")
            try:
                notify_daily_report(
                    report_date=date.today().strftime("%Y-%m-%d"),
                    anomaly_count=len(filtered_stock) + len(filtered_sales),
                    top_products=[
                        a.get("product_name", a.get("product_code", ""))
                        for a in (filtered_stock + filtered_sales)[:5]
                    ],
                    pdf_path=pdf_path,
                    db=db,
                )
                slack_ok = True
            except Exception as notify_err:
                logger.warning(f"알림 발송 실패(스킵): {notify_err}")

            # 이메일 발송 결과 별도 추적
            try:
                from app.notifier.email_notifier import send_daily_report_email
                email_ok = send_daily_report_email(
                    report_date=date.today().strftime("%Y-%m-%d"),
                    anomaly_count=len(filtered_stock) + len(filtered_sales),
                    top_products=[
                        a.get("product_name", a.get("product_code", ""))
                        for a in (filtered_stock + filtered_sales)[:5]
                    ],
                    pdf_path=pdf_path,
                )
            except Exception as email_err:
                logger.warning(f"이메일 발송 실패(스킵): {email_err}")
        else:
            logger.info("[7/7] 알림 발송 건너뜀 (PDF 생성 실패)")

        # --- 분석결과 시트 기록 ---
        try:
            df_analysis = pd.DataFrame(all_anomalies)
            if not df_analysis.empty:
                write_analysis_result(df_analysis)
        except Exception as e:
            logger.warning(f"분석결과 시트 기록 실패(스킵): {e}")

        update_report_execution(
            db=db, record_id=execution_id,
            status=ExecutionStatus.SUCCESS,
            slack_sent=slack_ok,
            email_sent=email_ok,
        )
        update_last_run(db, "daily_report")
        logger.info("========== 보고서 생성 작업 완료 ==========")

    except Exception as e:
        logger.error(f"보고서 생성 작업 실패: {e}")
        update_report_execution(db=db, record_id=execution_id, status=ExecutionStatus.FAILURE, error_message=str(e))
    finally:
        db.close()