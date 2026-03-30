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



@celery_app.task(bind=True, name="app.celery_app.tasks.run_proactive_order")
def run_proactive_order(self):

    logger.info("[선제발주] 태스크 시작")
    db = SessionLocal()
    try:
        self.update_state(state=states.STARTED, meta={"status": "수요예측 캐시 조회 중"})

        from app.db.sync import make_params_hash
        from app.db.repository import get_analysis_cache, get_setting
        from app.db.models import AnomalyLog, AnomalyType, OrderProposal, ProposalStatus
        from app.cache.redis_client import cache_get
        import json

        # 수요예측 캐시 조회
        params_hash = make_params_hash({"forecast_days": 14, "category": None})
        cache_key   = f"analysis:demand:{params_hash}"
        cached      = cache_get(cache_key)
        if cached is None:
            hit    = get_analysis_cache(db, "demand", params_hash, max_age_minutes=1440)
            cached = json.loads(hit.result_json)["items"] if hit else None

        if not cached:
            logger.warning("[선제발주] 수요예측 캐시 없음 — 태스크 종료")
            return {"skipped": True, "reason": "수요예측 캐시 없음"}

        # 재고 부족 예상 상품 필터 (shortage > 0)
        shortage_items = [i for i in cached if (i.get("shortage") or 0) > 0]
        if not shortage_items:
            logger.info("[선제발주] 재고 부족 예상 상품 없음")
            return {"created": 0, "reason": "부족 예상 상품 없음"}

        # 미해결 LOW_STOCK 이상징후 있는 상품 제외
        existing_codes = {
            r.product_code
            for r in db.query(AnomalyLog.product_code)
            .filter(
                AnomalyLog.anomaly_type == AnomalyType.LOW_STOCK,
                AnomalyLog.is_resolved  == False,
                )
            .all()
        }

        # PENDING 발주 제안 있는 상품 제외
        pending_codes = {
            r.product_code
            for r in db.query(OrderProposal.product_code)
            .filter(OrderProposal.status == ProposalStatus.PENDING)
            .all()
        }

        target_items = [
            i for i in shortage_items
            if i.get("product_code") not in existing_codes
               and i.get("product_code") not in pending_codes
        ]

        if not target_items:
            logger.info("[선제발주] 신규 선제 발주 대상 없음 (기존 이상징후/제안 존재)")
            return {"created": 0, "reason": "모두 기존 처리 중"}

        # 발주 제안 생성
        from datetime import datetime
        import math

        threshold_days = int(get_setting(db, "PROACTIVE_ORDER_DAYS", "7"))
        created        = 0
        proposals      = []

        for item in target_items:
            shortage    = item.get("shortage", 0)
            daily_avg   = item.get("daily_avg", 0)
            # 7일 이내 소진 예상만 선제 발주
            days_left   = item.get("current_stock", 0) / daily_avg if daily_avg > 0 else 999
            if days_left > threshold_days:
                continue

            proposed_qty = max(1, shortage)
            proposal = OrderProposal(
                product_code = item.get("product_code", ""),
                product_name = item.get("product_name", ""),
                category     = item.get("category", ""),
                proposed_qty = proposed_qty,
                unit_price   = 0.0,  # 단가 미확정
                reason       = (
                    f"[선제발주] 14일 예측 부족분 {shortage}개 / "
                    f"현재재고 {item.get('current_stock', 0)}개 / "
                    f"잔여 {days_left:.1f}일 예상"
                ),
                status = ProposalStatus.PENDING,
            )
            db.add(proposal)
            proposals.append(proposal)
            created += 1

        if created > 0:
            db.commit()
            logger.info(f"[선제발주] 발주 제안 {created}건 생성 완료")

            #  Slack 보고
            try:
                from app.notifier.slack_notifier import get_slack_client
                from app.config import settings as app_settings

                lines = [f"• {p.product_name} ({p.product_code}) | 예측 부족분: {p.proposed_qty}개" for p in proposals[:10]]
                if created > 10:
                    lines.append(f"... 외 {created - 10}건")

                get_slack_client().chat_postMessage(
                    channel=app_settings.slack_channel_id,
                    text=f"📦 선제 발주 제안 {created}건 생성",
                    blocks=[
                        {"type": "header", "text": {"type": "plain_text", "text": "SCM Agent | 선제 발주 제안"}},
                        {"type": "section", "text": {"type": "mrkdwn",
                                                     "text": f"수요예측 기반 *{created}건* 선제 발주 제안이 생성되었습니다.\n발주관리 탭에서 검토 후 승인해주세요."}},
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
                    ],
                )
            except Exception as e:
                logger.warning(f"[선제발주] Slack 보고 실패(스킵): {e}")

        return {"created": created, "skipped": len(target_items) - created}

    except Exception as exc:
        logger.error(f"[선제발주] 태스크 실패: {exc}")
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()
    finally:
        db.close()


# 안전재고 재계산
@celery_app.task(bind=True, name="app.celery_app.tasks.run_safety_stock_recalc")
def run_safety_stock_recalc(self):

    logger.info("[안전재고재계산] 태스크 시작")
    db = SessionLocal()
    try:
        self.update_state(state=states.STARTED, meta={"status": "판매 데이터 로딩 중"})

        from datetime import date, timedelta
        from app.db.repository import get_daily_sales_range, get_setting
        from app.db.models import Product, ProductStatus
        import math

        safety_days     = int(get_setting(db, "DEFAULT_SAFETY_STOCK_DAYS", "7"))
        safety_default  = int(get_setting(db, "SAFETY_STOCK_DEFAULT_MIN",  "10"))
        change_threshold = float(get_setting(db, "SAFETY_STOCK_CHANGE_THRESHOLD", "0.1"))  # 10% 이상 변화 시 알림

        # 최근 30일 판매 데이터
        sales = get_daily_sales_range(
            db,
            start=date.today() - timedelta(days=30),
            end=date.today(),
        )

        if not sales:
            logger.warning("[안전재고재계산] 판매 데이터 없음 — 종료")
            return {"updated": 0, "reason": "판매 데이터 없음"}

        # 상품코드별 일평균 판매량 계산
        from collections import defaultdict
        sales_map: dict[str, list[float]] = defaultdict(list)
        for s in sales:
            sales_map[s.product_code].append(s.qty)

        avg_map: dict[str, float] = {
            code: sum(qtys) / 30  # 30일 기준
            for code, qtys in sales_map.items()
        }

        # 활성 상품 조회
        products = db.query(Product).filter(
            Product.status == ProductStatus.ACTIVE
        ).all()

        updated       = 0
        big_changes   = []  # 10% 이상 변화 상품

        for product in products:
            avg = avg_map.get(product.code, 0.0)
            new_safety = max(
                math.ceil(avg * safety_days),
                safety_default,
            ) if avg > 0 else safety_default

            old_safety = product.safety_stock or 0

            # 변화 없으면 스킵
            if new_safety == old_safety:
                continue

            # 변화율 계산
            change_rate = abs(new_safety - old_safety) / max(old_safety, 1)

            product.safety_stock = new_safety
            updated += 1

            if change_rate >= change_threshold:
                big_changes.append({
                    "code":       product.code,
                    "name":       product.name,
                    "old":        old_safety,
                    "new":        new_safety,
                    "change_pct": round(change_rate * 100, 1),
                })

        if updated > 0:
            db.commit()
            logger.info(f"[안전재고재계산] {updated}건 업데이트 완료 (10%+ 변화: {len(big_changes)}건)")

        # Slack 보고
        if big_changes:
            try:
                from app.notifier.slack_notifier import get_slack_client
                from app.config import settings as app_settings

                lines = [
                    f"• {i['name']} ({i['code']}) | {i['old']}개 → {i['new']}개 ({'+' if i['new'] > i['old'] else ''}{i['change_pct']}%)"
                    for i in big_changes[:10]
                ]
                if len(big_changes) > 10:
                    lines.append(f"... 외 {len(big_changes) - 10}건")

                get_slack_client().chat_postMessage(
                    channel=app_settings.slack_channel_id,
                    text=f"🔄 안전재고 자동 재계산 완료: {updated}건 업데이트",
                    blocks=[
                        {"type": "header", "text": {"type": "plain_text", "text": "SCM Agent | 안전재고 재계산"}},
                        {"type": "section", "text": {"type": "mrkdwn",
                                                     "text": f"*{updated}건* 안전재고 업데이트 / 대폭 변화 *{len(big_changes)}건*\n기준: 최근 30일 일평균 × {safety_days}일"}},
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
                    ],
                )
            except Exception as e:
                logger.warning(f"[안전재고재계산] Slack 보고 실패(스킵): {e}")

        return {"updated": updated, "big_changes": len(big_changes)}

    except Exception as exc:
        logger.error(f"[안전재고재계산] 태스크 실패: {exc}")
        self.update_state(state=states.FAILURE, meta={"error": str(exc)})
        raise Ignore()
    finally:
        db.close()