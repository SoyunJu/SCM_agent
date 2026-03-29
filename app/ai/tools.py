
from langchain.tools import StructuredTool
from langchain.pydantic_v1 import BaseModel, Field
from loguru import logger


class SingleStrInput(BaseModel):
    input: str = Field(default="", description="입력값")


# --- 재고 부족 조회 ---
def _get_low_stock(input: str = "") -> str:
    try:
        from datetime import date, timedelta
        from app.db.connection import SessionLocal
        from app.db.models import Product, ProductStatus, StockLevel
        from app.db.repository import get_daily_sales_range, get_setting
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
        import pandas as pd

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
            # 상품명 JOIN
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
            lines.append(
                f"• {str(r.date)} "
                f"| 판매: {int(r.판매수량)}개 "
                f"| 매출: {int(r.매출액):,}원"
            )
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
            "low_stock": "재고 부족", "over_stock": "재고 과잉",
            "sales_surge": "판매 급등", "sales_drop": "판매 급락",
            "long_term_stock": "장기 재고",
        }
        SEVERITY_KOR = {
            "LOW": "낮음", "MEDIUM": "보통",
            "HIGH": "높음", "CRITICAL": "긴급", "CHECK": "확인",
        }

        label = "미해결" if status == "unresolved" else "전체"
        lines = [f"⚠️ 이상 징후 {label} {len(records)}건:"]
        for r in records:
            atype        = ANOMALY_KOR.get(r.anomaly_type.value, r.anomaly_type.value)
            sev          = SEVERITY_KOR.get(r.severity.value, r.severity.value)
            resolved_str = "✅ 해결" if r.is_resolved else "🔴 미해결"
            lines.append(
                f"• [{sev}] {r.product_name} ({r.product_code}) "
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


# ── Tool 등록 ──────────────────────────────────────────────────────────────

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
    description="이상 징후 목록 조회(DB). 입력: unresolved(미해결) 또는 all(전체). 사용 예: 이상 징후 알려줘, 미해결 이상 있어?",
    args_schema=SingleStrInput,
)

generate_report = StructuredTool.from_function(
    func=_generate_report,
    name="generate_report",
    description="일일 보고서 즉시 생성 및 Slack 전송 트리거. 사용 예: 지금 보고서 만들어줘, 리포트 생성해",
    args_schema=SingleStrInput,
)