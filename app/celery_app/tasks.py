from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
from celery import states
from celery.exceptions import Ignore
from loguru import logger

from app.celery_app.celery import celery_app
from app.cache.redis_client import cache_get, cache_set
from app.db.connection import SessionLocal
from app.db.sync import make_params_hash

def _get_cache_ttl(db) -> int:
    from app.db.repository import get_setting
    return int(get_setting(db, "ANALYSIS_CACHE_REDIS_MINUTES", "120")) * 60


def _get_cache_max_age(db) -> int:
    from app.db.repository import get_setting
    return int(get_setting(db, "ANALYSIS_CACHE_DB_MINUTES", "120"))


def _get_cached(cache_key: str, analysis_type: str, params_hash: str, db) -> list | None:
    from app.db.repository import get_analysis_cache

    redis_hit = cache_get(cache_key)
    if redis_hit is not None:
        logger.debug(f"[{analysis_type}] Redis 캐시 히트")
        return redis_hit

    db_hit = get_analysis_cache(db, analysis_type, params_hash, max_age_minutes=_get_cache_max_age(db))
    if db_hit:
        items = json.loads(db_hit.result_json).get("items", [])
        cache_set(cache_key, items, ttl=_get_cache_ttl(db))
        logger.debug(f"[{analysis_type}] DB 캐시 히트 → Redis 워밍업")
        return items

    return None


def _store_cache(cache_key: str, analysis_type: str, params_hash: str, items: list, db) -> None:
    from app.db.repository import upsert_analysis_cache

    payload = json.dumps({"items": items}, ensure_ascii=False, default=str)
    try:
        upsert_analysis_cache(db, analysis_type, params_hash, payload)
    except Exception as exc:
        logger.warning(f"[{analysis_type}] DB 캐시 저장 실패 (Redis만 유지): {exc}")
    cache_set(cache_key, items, ttl=_get_cache_ttl(db))



# --- 헬퍼 ---

def _build_dataframes(db) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from app.db.models import Product, ProductStatus
    from app.db.repository import get_daily_sales_range, get_all_stock_levels

    # 상품 마스터 (active 상품만)
    products = (
        db.query(Product)
        .filter(Product.status == ProductStatus.ACTIVE)
        .all()
    )
    df_master = pd.DataFrame([
        {
            "상품코드":     p.code,
            "상품명":       p.name,
            "카테고리":     p.category or "",
            "안전재고기준": p.safety_stock,
        }
        for p in products
    ])

    # 일별 매출 (최근 90일)
    sales_start = date.today() - timedelta(days=90)
    sales = get_daily_sales_range(db, start=sales_start, end=date.today())
    df_sales = pd.DataFrame([
        {
            "날짜":    str(s.date),
            "상품코드": s.product_code,
            "판매수량": s.qty,
            "매출액":  s.revenue,
        }
        for s in sales
    ]) if sales else pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"])

    # 재고
    stocks = get_all_stock_levels(db)
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


def _get_cached(cache_key: str, analysis_type: str, params_hash: str, db):
    from app.db.repository import get_analysis_cache

    redis_hit = cache_get(cache_key)
    if redis_hit is not None:
        logger.debug(f"[{analysis_type}] Redis 캐시 히트")
        return redis_hit

    db_hit = get_analysis_cache(db, analysis_type, params_hash, max_age_minutes=ANALYSIS_CACHE_MAX_AGE)
    if db_hit:
        items = json.loads(db_hit.result_json).get("items", [])
        cache_set(cache_key, items, ttl=ANALYSIS_CACHE_TTL)
        logger.debug(f"[{analysis_type}] DB 캐시 히트 → Redis 워밍업")
        return items

    return None


def _store_cache(cache_key: str, analysis_type: str, params_hash: str, items: list, db) -> None:
    from app.db.repository import upsert_analysis_cache

    payload = json.dumps({"items": items}, ensure_ascii=False, default=str)
    try:
        upsert_analysis_cache(db, analysis_type, params_hash, payload)
    except Exception as exc:
        logger.warning(f"[{analysis_type}] DB 캐시 저장 실패 (Redis만 유지): {exc}")
    cache_set(cache_key, items, ttl=ANALYSIS_CACHE_TTL)



# --- 분석 ---

    # 수요 예측
@celery_app.task(bind=True, name="app.celery_app.tasks.run_demand_forecast")
def run_demand_forecast(self, forecast_days: int = 14, category: str | None = None):

    params_hash = make_params_hash({"forecast_days": forecast_days, "category": category})
    cache_key   = f"analysis:demand:{params_hash}"

    db = SessionLocal()
    try:
        cached = _get_cached(cache_key, "demand", params_hash, db)
        if cached is not None:
            return {"items": cached, "from_cache": True}

        logger.info(f"[수요예측] 분석 시작 — forecast_days={forecast_days}, category={category}")
        self.update_state(state=states.STARTED, meta={"status": "데이터 로딩 중"})

        df_master, df_sales, df_stock = _build_dataframes(db)
        if df_master.empty:
            logger.warning("[수요예측] 분석 대상 상품 없음 — 빈 결과 반환")
            return {"items": [], "from_cache": False}

        from app.analyzer.demand_forecaster import run_demand_forecast_all
        items = run_demand_forecast_all(df_master, df_sales, df_stock, forecast_days=forecast_days)

        if category:
            items = [i for i in items if i.get("category") == category]

        _store_cache(cache_key, "demand", params_hash, items, db)
        logger.info(f"[수요예측] 분석 완료 — {len(items)}개 상품")
        return {"items": items, "from_cache": False}

    except Exception as exc:
        logger.error(f"[수요예측] 태스크 실패: {exc}")
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()
    finally:
        db.close()


    # 회전율
@celery_app.task(bind=True, name="app.celery_app.tasks.run_turnover_analysis")
def run_turnover_analysis(self, days: int = 30, category: str | None = None):

    params_hash = make_params_hash({"days": days, "category": category})
    cache_key   = f"analysis:turnover:{params_hash}"

    db = SessionLocal()
    try:
        cached = _get_cached(cache_key, "turnover", params_hash, db)
        if cached is not None:
            return {"items": cached, "from_cache": True}

        logger.info(f"[회전율] 분석 시작 — days={days}, category={category}")
        self.update_state(state=states.STARTED, meta={"status": "데이터 로딩 중"})

        df_master, df_sales, df_stock = _build_dataframes(db)
        if df_master.empty:
            logger.warning("[회전율] 분석 대상 상품 없음 — 빈 결과 반환")
            return {"items": [], "from_cache": False}

        from app.analyzer.turnover_analyzer import calc_inventory_turnover
        items = calc_inventory_turnover(df_master, df_sales, df_stock, days=days)

        if category:
            items = [i for i in items if i.get("카테고리") == category]

        _store_cache(cache_key, "turnover", params_hash, items, db)
        logger.info(f"[회전율] 분석 완료 — {len(items)}개 상품")
        return {"items": items, "from_cache": False}

    except Exception as exc:
        logger.error(f"[회전율] 태스크 실패: {exc}")
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()
    finally:
        db.close()


    # ABC 분석
@celery_app.task(bind=True, name="app.celery_app.tasks.run_abc_analysis_task")
def run_abc_analysis_task(self, days: int = 90):

    params_hash = make_params_hash({"days": days})
    cache_key   = f"analysis:abc:{params_hash}"

    db = SessionLocal()
    try:
        cached = _get_cached(cache_key, "abc", params_hash, db)
        if cached is not None:
            return {"items": cached, "from_cache": True}

        logger.info(f"[ABC분석] 분석 시작 — days={days}")
        self.update_state(state=states.STARTED, meta={"status": "데이터 로딩 중"})

        df_master, df_sales, _ = _build_dataframes(db)
        if df_master.empty:
            logger.warning("[ABC분석] 분석 대상 상품 없음 — 빈 결과 반환")
            return {"items": [], "from_cache": False}

        from app.analyzer.abc_analyzer import run_abc_analysis
        items = run_abc_analysis(df_master, df_sales, days=days)

        _store_cache(cache_key, "abc", params_hash, items, db)
        logger.info(f"[ABC분석] 분석 완료 — {len(items)}개 상품")
        return {"items": items, "from_cache": False}

    except Exception as exc:
        logger.error(f"[ABC분석] 태스크 실패: {exc}")
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()
    finally:
        db.close()



# --- 스케줄 ---

@celery_app.task(bind=True, name="app.celery_app.tasks.run_daily_report")
def run_daily_report(self):

    logger.info("[Daily Report] 보고서 생성 시작")
    try:
        self.update_state(state=states.STARTED, meta={"status": "일일 보고서 생성 중"})
        from app.scheduler.jobs import run_daily_job
        run_daily_job()   # 내부에서 DB 세션 · execution 이력 관리
        logger.info("[Daily Report] 보고서 생성 완료")
        return {"status": "success"}
    except Exception as exc:
        logger.error(f"[Daily Report] 보고서 생성 실패: {exc}")
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()


    # 크롤러
@celery_app.task(bind=True, name="app.celery_app.tasks.run_crawler")
def run_crawler(self):
    logger.info("[크롤러] 태스크 시작")
    try:
        self.update_state(state=states.STARTED, meta={"status": "크롤링 중"})
        from app.scheduler.jobs import sync_sheets_only
        result = sync_sheets_only()
        logger.info(f"[크롤러] 태스크 완료 — crawled={result.get('crawled', 0)}")
        return result
    except Exception as exc:
        logger.error(f"[크롤러] 태스크 실패: {exc}")
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()


@celery_app.task(name="app.celery_app.tasks.run_cleanup")
def run_cleanup():

    logger.info("[데이터정리] 태스크 시작")
    db = SessionLocal()
    try:
        from app.db.repository import (
            delete_old_daily_sales, delete_old_analysis_cache, get_setting
        )
        sales_days     = int(get_setting(db, "DATA_RETENTION_SALES_DAYS",    "365"))
        analysis_hours = int(get_setting(db, "DATA_RETENTION_ANALYSIS_HOURS", "24"))

        deleted_sales    = delete_old_daily_sales(db, older_than_days=sales_days)
        deleted_cache    = delete_old_analysis_cache(db, older_than_hours=analysis_hours)

        logger.info(
            f"[데이터정리] 완료 — 매출 {deleted_sales}건, 분석캐시 {deleted_cache}건 삭제 "
            f"(보존 기준: 매출 {sales_days}일, 캐시 {analysis_hours}시간)"
        )
        return {"deleted_sales": deleted_sales, "deleted_cache": deleted_cache}
    except Exception as exc:
        logger.error(f"[데이터정리] 태스크 실패: {exc}")
        raise
    finally:
        db.close()


# 시트 -> DB 동기화
@celery_app.task(name="app.celery_app.tasks.run_sync_sheets_to_db")
def run_sync_sheets_to_db():
    db = SessionLocal()
    try:
        from app.db.repository import get_setting
        enabled = get_setting(db, "SHEETS_SYNC_ENABLED", "true").lower()
        if enabled != "true":
            logger.info("[Sync] SHEETS_SYNC_ENABLED=false — 동기화 skip")
            return {"skipped": True}
    finally:
        db.close()

    logger.info("[Sync] Sheets→DB 동기화 시작")
    try:
        from app.scheduler.jobs import sync_sheets_to_db_incremental
        result = sync_sheets_to_db_incremental()
        logger.info(f"[Sync] 완료: {result}")
        return result
    except Exception as exc:
        logger.error(f"[Sync] 태스크 실패: {exc}")
        raise