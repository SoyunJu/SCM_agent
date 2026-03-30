from langchain.tools import StructuredTool
from langchain.pydantic_v1 import BaseModel, Field
from loguru import logger


class SingleStrInput(BaseModel):
    input: str = Field(default="", description="입력값")


# ── Read Tools ────────────────────────────────────────────────────────────────

# --- 재고 부족 조회 ---
def _get_low_stock(input: str = "") -> str:
    try:
        from datetime import date, timedelta
        from app.db.connection import SessionLocal
        from app.db.models import Product, ProductStatus, StockLevel
        from app.db.repository import get_daily_sales_range
        from app.analyzer.stock_analyzer import detect_low_stock
        import pandas as pd

        db = SessionLocal()
        try:
            products = db.query(Product).filter(Product.status == ProductStatus.ACTIVE).all()
            stocks   = db.query(StockLevel).all()
            sales    = get_daily_sales_range(db, start=date.today() - timedelta(days=30), end=date.today())

            df_master = pd.DataFrame([
                {"상품코드": p.code, "상품명": p.name, "카테고리": p.category or "", "안전재고기준": p.safety_stock}
                for p in products
            ]) if products else pd.DataFrame(columns=["상품코드", "상품명", "카테고리", "안전재고기준"])

            df_stock = pd.DataFrame([
                {"상품코드": s.product_code, "현재재고": s.current_stock,
                 "입고예정일": str(s.restock_date) if s.restock_date else "", "입고예정수량": s.restock_qty or 0}
                for s in stocks
            ]) if stocks else pd.DataFrame(columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"])

            df_sales = pd.DataFrame([
                {"날짜": str(s.date), "상품코드": s.product_code, "판매수량": s.qty, "매출액": s.revenue}
                for s in sales
            ]) if sales else pd.DataFrame(columns=["날짜", "상품코드", "판매수량", "매출액"])
        finally:
            db.close()

        results = detect_low_stock(df_master, df_stock, df_sales)
        if not results:
            return "현재 재고 부족 상품이 없습니다."

        lines = [f"재고 부족 상품 {len(results)}건:"]
        for r in results:
            days     = r["days_until_stockout"]
            days_str = f"{days}일 후 소진 예상" if days < 999 else "판매 없음"
            lines.append(
                f"• [{r['severity'].upper()}] {r['product_name']} ({r['product_code']}) "
                f"| 현재 재고: {r['current_stock']}개 | {days_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_low_stock Tool 오류: {e}")
        return f"재고 조회 중 오류 발생: {e}"


# --- 판매 상위 상품 조회 ---
def _get_top_sales(input: str = "7") -> str:
    try:
        from datetime import date, timedelta
        from app.db.connection import SessionLocal
        from app.db.models import Product, DailySales
        from sqlalchemy import func

        days_int = int(input.strip()) if input.strip().isdigit() else 7
        cutoff   = date.today() - timedelta(days=days_int)

        db = SessionLocal()
        try:
            rows = (
                db.query(
                    DailySales.product_code,
                    func.sum(DailySales.qty).label("판매수량합계"),
                    func.sum(DailySales.revenue).label("매출액합계"),
                )
                .filter(DailySales.date >= cutoff)
                .group_by(DailySales.product_code)
                .order_by(func.sum(DailySales.qty).desc())
                .limit(5)
                .all()
            )
            codes    = [r.product_code for r in rows]
            products = db.query(Product).filter(Product.code.in_(codes)).all()
            name_map = {p.code: p.name for p in products}
        finally:
            db.close()

        if not rows:
            return f"최근 {days_int}일 판매 데이터가 없습니다."

        lines = [f"📈 최근 {days_int}일 판매 TOP {len(rows)}:"]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"{i}. {name_map.get(r.product_code, r.product_code)} ({r.product_code}) "
                f"| 판매수량: {int(r.판매수량합계)}개 "
                f"| 매출: {int(r.매출액합계):,}원"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_top_sales Tool 오류: {e}")
        return f"판매 조회 중 오류 발생: {e}"


# --- 상품별 재고 조회 ---
def _get_stock_by_product(input: str = "") -> str:
    try:
        from app.db.connection import SessionLocal
        from app.db.models import Product, StockLevel, ProductStatus

        product_name = input.strip()
        if not product_name:
            return "상품명 또는 상품코드를 입력해주세요."

        db = SessionLocal()
        try:
            rows = (
                db.query(Product, StockLevel)
                .outerjoin(StockLevel, Product.code == StockLevel.product_code)
                .filter(Product.status == ProductStatus.ACTIVE)
                .filter(
                    Product.name.contains(product_name) |
                    Product.code.contains(product_name)
                )
                .all()
            )
        finally:
            db.close()

        if not rows:
            return f"'{product_name}' 에 해당하는 상품을 찾을 수 없습니다."

        lines = [f"'{product_name}' 검색 결과 {len(rows)}건:"]
        for prod, sl in rows:
            stock   = sl.current_stock if sl else 0
            restock = str(sl.restock_date) if sl and sl.restock_date else "-"
            lines.append(
                f"• {prod.name} ({prod.code}) "
                f"| 현재재고: {stock}개 | 입고예정: {restock}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_stock_by_product Tool 오류: {e}")
        return f"상품 재고 조회 중 오류 발생: {e}"


# --- 판매 트렌드 조회 ---
def _get_sales_trend(input: str = "") -> str:
    try:
        from datetime import date, timedelta
        from app.db.connection import SessionLocal
        from app.db.models import DailySales
        from sqlalchemy import func

        parts        = input.strip().split()
        product_code = parts[0] if parts else ""
        days_int     = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30

        if not product_code:
            return "상품코드를 입력해주세요. 예: 'CR001 30'"

        cutoff = date.today() - timedelta(days=days_int)

        db = SessionLocal()
        try:
            rows = (
                db.query(
                    DailySales.date,
                    func.sum(DailySales.qty).label("판매수량"),
                    func.sum(DailySales.revenue).label("매출액"),
                )
                .filter(DailySales.product_code == product_code, DailySales.date >= cutoff)
                .group_by(DailySales.date)
                .order_by(DailySales.date)
                .all()
            )
        finally:
            db.close()

        if not rows:
            return f"{product_code} 상품의 최근 {days_int}일 판매 데이터가 없습니다."

        lines = [f"📊 {product_code} 최근 {days_int}일 판매 트렌드:"]
        for r in rows:
            lines.append(f"• {str(r.date)} | 판매: {int(r.판매수량)}개 | 매출: {int(r.매출액):,}원")
        total_qty = sum(int(r.판매수량) for r in rows)
        total_rev = sum(int(r.매출액) for r in rows)
        lines.append(f"합계: 판매 {total_qty}개 | 매출 {total_rev:,}원")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_sales_trend Tool 오류: {e}")
        return f"판매 트렌드 조회 중 오류 발생: {e}"


# --- 이상 징후 조회 ---
def _get_anomalies(input: str = "unresolved") -> str:
    try:
        from app.db.connection import SessionLocal
        from app.db.repository import get_anomaly_logs

        status = input.strip() if input.strip() else "unresolved"
        db = SessionLocal()
        try:
            is_resolved = False if status == "unresolved" else None
            result  = get_anomaly_logs(db, is_resolved=is_resolved, page=1, page_size=20)
            records = result["items"]
        finally:
            db.close()

        if not records:
            return "현재 감지된 이상 징후가 없습니다."

        ANOMALY_KOR = {
            "LOW_STOCK": "재고 부족", "OVER_STOCK": "재고 과잉",
            "SALES_SURGE": "판매 급등", "SALES_DROP": "판매 급락",
            "LONG_TERM_STOCK": "장기 재고",
        }
        SEVERITY_KOR = {
            "LOW": "낮음", "MEDIUM": "보통",
            "HIGH": "높음", "CRITICAL": "긴급", "CHECK": "확인",
        }

        label = "미해결" if status == "unresolved" else "전체"
        lines = [f"⚠️ 이상 징후 {label} {len(records)}건:"]
        for r in records:
            atype_key    = r.anomaly_type.value if hasattr(r.anomaly_type, "value") else str(r.anomaly_type)
            sev_key      = r.severity.value if hasattr(r.severity, "value") else str(r.severity)
            atype        = ANOMALY_KOR.get(atype_key, atype_key)
            sev          = SEVERITY_KOR.get(sev_key, sev_key)
            resolved_str = "✅ 해결" if r.is_resolved else "🔴 미해결"
            lines.append(
                f"• [id:{r.id}] [{sev}] {r.product_name} ({r.product_code}) "
                f"| {atype} | {resolved_str} | {str(r.detected_at)[:16]}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_anomalies Tool 오류: {e}")
        return f"이상 징후 조회 중 오류 발생: {e}"


# --- 보고서 즉시 생성 ---
def _generate_report(input: str = "") -> str:
    try:
        import threading
        from app.scheduler.jobs import run_daily_job
        thread = threading.Thread(target=run_daily_job, daemon=True)
        thread.start()
        logger.info("보고서 생성 트리거 (Tool)")
        return "보고서 생성을 시작했습니다. 완료되면 Slack으로 알림됩니다."
    except Exception as e:
        logger.error(f"generate_report Tool 오류: {e}")
        return f"보고서 생성 트리거 중 오류 발생: {e}"


# --- 수요예측 결과 조회 ---
def _get_demand_forecast(input: str = "") -> str:
    try:
        from app.db.connection import SessionLocal
        from app.db.repository import get_analysis_cache
        from app.db.sync import make_params_hash
        from app.cache.redis_client import cache_get
        import json

        params_hash = make_params_hash({"forecast_days": 14, "category": None})
        cache_key   = f"analysis:demand:{params_hash}"

        # Redis 먼저
        cached = cache_get(cache_key)
        if cached is None:
            db = SessionLocal()
            try:
                hit = get_analysis_cache(db, "demand", params_hash, max_age_minutes=1440)
                cached = json.loads(hit.result_json)["items"] if hit else None
            finally:
                db.close()

        if not cached:
            return "수요예측 캐시가 없습니다. 스케줄 탭에서 '수요 예측 분석' 즉시 실행 후 다시 시도해주세요."

        # 재고 부족 예상 상품만 필터
        shortage_items = [i for i in cached if i.get("shortage", 0) > 0]
        if not shortage_items:
            return "14일 내 재고 부족 예상 상품이 없습니다."

        shortage_items.sort(key=lambda x: x.get("shortage", 0), reverse=True)
        lines = [f"📉 14일 내 재고 부족 예상 {len(shortage_items)}건 (부족분 큰 순):"]
        for item in shortage_items[:10]:
            lines.append(
                f"• {item.get('product_name', '')} ({item.get('product_code', '')}) "
                f"| 현재재고: {item.get('current_stock', 0)}개 "
                f"| 예측수요: {item.get('forecast_qty', 0)}개 "
                f"| 부족분: {item.get('shortage', 0)}개 "
                f"| 추세: {item.get('trend', '-')}"
            )
        if len(shortage_items) > 10:
            lines.append(f"... 외 {len(shortage_items) - 10}건")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_demand_forecast Tool 오류: {e}")
        return f"수요예측 조회 중 오류 발생: {e}"


# ── Write Tools ───────────────────────────────────────────────────────────────

# --- 이상징후 기반 발주 자동 승인 ---
def _approve_anomaly_orders(input: str = "") -> str:
    """
    입력: 상품코드(쉼표 구분) 또는 빈값(전체 CRITICAL/HIGH LOW_STOCK 대상)
    동작: 해당 상품의 미해결 LOW_STOCK/SALES_SURGE 이상징후 → 발주 제안 생성 + 즉시 승인
    """
    try:
        from datetime import datetime
        from app.db.connection import SessionLocal
        from app.db.models import AnomalyLog, AnomalyType, OrderProposal, ProposalStatus
        from app.services.anomaly_service import AnomalyService

        db = SessionLocal()
        try:
            # 대상 상품코드 파싱
            target_codes = [c.strip() for c in input.split(",") if c.strip()] if input.strip() else []

            # 처리 대상 이상징후 조회 (LOW_STOCK / SALES_SURGE, 미해결)
            query = db.query(AnomalyLog).filter(
                AnomalyLog.is_resolved == False,
                AnomalyLog.anomaly_type.in_([AnomalyType.LOW_STOCK, AnomalyType.SALES_SURGE]),
                )
            if target_codes:
                query = query.filter(AnomalyLog.product_code.in_(target_codes))

            anomalies = query.all()
            if not anomalies:
                return "처리 대상 이상징후(재고부족/판매급등)가 없습니다."

            results   = []
            processed = 0
            skipped   = 0

            for anomaly in anomalies:
                try:
                    result = AnomalyService.auto_resolve(
                        db, anomaly.id, username="SCM-Agent"
                    )
                    proposal_id = result.get("proposal_id")
                    if proposal_id:
                        results.append(
                            f"✅ {anomaly.product_name} ({anomaly.product_code}) "
                            f"→ 발주 제안 #{proposal_id} 자동 승인"
                        )
                    else:
                        results.append(
                            f"✅ {anomaly.product_name} ({anomaly.product_code}) → 해결 처리"
                        )
                    processed += 1
                except Exception as e:
                    results.append(
                        f"⚠️ {anomaly.product_name} ({anomaly.product_code}) → 스킵: {e}"
                    )
                    skipped += 1

            lines = [f"발주 자동 처리 완료: {processed}건 성공 / {skipped}건 스킵"]
            lines.extend(results)
            logger.info(f"[Tool] approve_anomaly_orders: {processed}건 처리")
            return "\n".join(lines)

        finally:
            db.close()

    except Exception as e:
        logger.error(f"approve_anomaly_orders Tool 오류: {e}")
        return f"발주 자동 처리 중 오류 발생: {e}"


# --- 이상징후 해결 처리 ---
def _resolve_anomaly(input: str = "") -> str:
    """
    입력: anomaly id (숫자) 또는 상품코드
    동작: 해당 이상징후를 해결 처리 (발주 없이 단순 resolve)
    """
    try:
        from app.db.connection import SessionLocal
        from app.db.models import AnomalyLog
        from app.db.repository import resolve_anomaly

        target = input.strip()
        if not target:
            return "이상징후 ID 또는 상품코드를 입력해주세요. 예: '123' 또는 'P001'"

        db = SessionLocal()
        try:
            # ID로 시도
            if target.isdigit():
                anomaly = db.query(AnomalyLog).filter(
                    AnomalyLog.id == int(target)
                ).first()
                if not anomaly:
                    return f"ID {target}에 해당하는 이상징후가 없습니다."
                targets = [anomaly]
            else:
                # 상품코드로 미해결 전체
                targets = db.query(AnomalyLog).filter(
                    AnomalyLog.product_code == target,
                    AnomalyLog.is_resolved == False,
                    ).all()
                if not targets:
                    return f"상품코드 '{target}'의 미해결 이상징후가 없습니다."

            resolved = []
            for a in targets:
                resolve_anomaly(db, a.id)
                resolved.append(f"✅ [id:{a.id}] {a.product_name} ({a.product_code}) 해결 처리")

            logger.info(f"[Tool] resolve_anomaly: {len(resolved)}건")
            return f"이상징후 해결 처리 완료 {len(resolved)}건:\n" + "\n".join(resolved)

        finally:
            db.close()

    except Exception as e:
        logger.error(f"resolve_anomaly Tool 오류: {e}")
        return f"이상징후 해결 처리 중 오류 발생: {e}"


# --- 발주 제안 생성 (승인 없이) ---
def _generate_order_proposals(input: str = "") -> str:
    """
    입력: severity (LOW/MEDIUM/HIGH/CRITICAL) 또는 빈값(설정값 사용)
    동작: 현재 이상징후 기반 발주 제안 생성 (PENDING 상태, 승인 필요)
    """
    try:
        from app.db.connection import SessionLocal
        from app.services.order_service import OrderService

        severity = input.strip().upper() if input.strip() else None
        db = SessionLocal()
        try:
            result = OrderService.generate(db, severity_override=severity)
            created = result.get("created", 0)
            if created == 0:
                return result.get("message", "생성된 발주 제안이 없습니다.")

            lines = [
                f"📦 발주 제안 {created}건 생성 완료 (승인 대기)",
                f"임계값: {result.get('threshold', '-')} | 자동승인: {'예' if result.get('auto_approve') else '아니오'}",
            ]
            for p in result.get("proposals", [])[:5]:
                lines.append(
                    f"• {p.get('product_name', '')} ({p.get('product_code', '')}) "
                    f"| {p.get('proposed_qty', 0)}개 "
                    f"@ {p.get('unit_price', 0):,.0f}원"
                )
            if created > 5:
                lines.append(f"... 외 {created - 5}건")
            logger.info(f"[Tool] generate_order_proposals: {created}건")
            return "\n".join(lines)
        finally:
            db.close()

    except Exception as e:
        logger.error(f"generate_order_proposals Tool 오류: {e}")
        return f"발주 제안 생성 중 오류 발생: {e}"


# ── Tool 등록 ──────────────────────────────────────────────────────────────────

get_low_stock = StructuredTool.from_function(
    func=_get_low_stock,
    name="get_low_stock",
    description="재고 부족 상품 목록 조회. 현재 재고가 안전재고 기준 이하인 상품 반환. 사용 예: 재고 부족한 상품, 긴급 발주 필요한 상품",
    args_schema=SingleStrInput,
)

get_top_sales_tool = StructuredTool.from_function(
    func=_get_top_sales,
    name="get_top_sales_tool",
    description="최근 N일 판매 상위 상품 조회. 입력: 조회 기간(일, 기본 7). 사용 예: 많이 팔린 상품, 판매 상위 상품, 인기 상품",
    args_schema=SingleStrInput,
)

get_stock_by_product = StructuredTool.from_function(
    func=_get_stock_by_product,
    name="get_stock_by_product",
    description="특정 상품의 현재 재고 조회. 입력: 상품명 또는 상품코드(부분 일치). 사용 예: CR001 재고 얼마야, 상품명으로 재고 검색",
    args_schema=SingleStrInput,
)

get_sales_trend_tool = StructuredTool.from_function(
    func=_get_sales_trend,
    name="get_sales_trend_tool",
    description="특정 상품의 기간별 판매 트렌드 조회. 입력: '상품코드 기간(일)' 형식. 예: CR001 30",
    args_schema=SingleStrInput,
)

get_anomalies = StructuredTool.from_function(
    func=_get_anomalies,
    name="get_anomalies",
    description="이상 징후 목록 조회. 입력: unresolved(미해결, 기본값) 또는 all(전체). 결과에 id 포함. 사용 예: 이상 징후 알려줘, 미해결 이상 있어?",
    args_schema=SingleStrInput,
)

generate_report = StructuredTool.from_function(
    func=_generate_report,
    name="generate_report",
    description="일일 보고서 즉시 생성 및 Slack 전송 트리거. 사용 예: 지금 보고서 만들어줘, 리포트 생성해",
    args_schema=SingleStrInput,
)

get_demand_forecast_tool = StructuredTool.from_function(
    func=_get_demand_forecast,
    name="get_demand_forecast_tool",
    description="14일 수요예측 기반 재고 부족 예상 상품 조회. 사용 예: 다음 주 재고 위험 상품, 수요 예측 결과, 미리 발주해야 할 상품",
    args_schema=SingleStrInput,
)

approve_anomaly_orders = StructuredTool.from_function(
    func=_approve_anomaly_orders,
    name="approve_anomaly_orders",
    description=(
        "이상징후(재고부족/판매급등) 기반 발주를 자동 생성하고 즉시 승인 처리. "
        "입력: 상품코드 쉼표 구분(예: P001,P002) 또는 빈값(전체 대상). "
        "사용 예: 긴급 재고 발주해줘, P001 발주 처리해, 재고 부족 상품 전부 발주"
    ),
    args_schema=SingleStrInput,
)

resolve_anomaly_tool = StructuredTool.from_function(
    func=_resolve_anomaly,
    name="resolve_anomaly_tool",
    description=(
        "이상징후를 해결 처리. 발주 없이 단순 완료 처리. "
        "입력: 이상징후 id(숫자) 또는 상품코드. "
        "사용 예: 이상징후 123번 해결해줘, P001 이상징후 닫아줘"
    ),
    args_schema=SingleStrInput,
)

generate_order_proposals = StructuredTool.from_function(
    func=_generate_order_proposals,
    name="generate_order_proposals",
    description=(
        "발주 제안 생성 (승인 없이 PENDING 상태로 생성). "
        "입력: 심각도 필터(LOW/MEDIUM/HIGH/CRITICAL) 또는 빈값(설정값). "
        "사용 예: 발주 제안 만들어줘, HIGH 이상 발주 제안 생성"
    ),
    args_schema=SingleStrInput,
)