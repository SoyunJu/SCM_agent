
from langchain.tools import StructuredTool
from langchain.pydantic_v1 import BaseModel, Field
from loguru import logger
from app.sheets.reader import read_product_master, read_sales, read_stock
from app.analyzer.stock_analyzer import detect_low_stock, detect_over_stock
from app.analyzer.sales_analyzer import get_top_sales, get_sales_trend, detect_sales_anomaly


class SingleStrInput(BaseModel):
    input: str = Field(default="", description="입력값")


def _get_low_stock(input: str = "") -> str:
    try:
        df_master = read_product_master()
        df_stock  = read_stock()
        df_sales  = read_sales()
        results   = detect_low_stock(df_master, df_stock, df_sales)

        if not results:
            return "현재 재고 부족 상품이 없습니다."

        lines = [f" 재고 부족 상품 {len(results)}건:"]
        for r in results:
            days = r["days_until_stockout"]
            days_str = f"{days}일 후 소진 예상" if days < 999 else "판매 없음"
            lines.append(
                f"• [{r['severity'].upper()}] {r['product_name']} ({r['product_code']}) "
                f"| 현재 재고: {r['current_stock']}개 | {days_str}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_low_stock Tool 오류: {e}")
        return f"재고 조회 중 오류 발생: {e}"


def _get_top_sales(input: str = "7") -> str:
    try:
        days_int  = int(input.strip()) if input.strip().isdigit() else 7
        df_master = read_product_master()
        df_sales  = read_sales()
        result    = get_top_sales(df_master, df_sales, days=days_int, top_n=5)

        if result.empty:
            return f"최근 {days_int}일 판매 데이터가 없습니다."

        lines = [f"📈 최근 {days_int}일 판매 TOP {len(result)}:"]
        for i, (_, row) in enumerate(result.iterrows(), 1):
            lines.append(
                f"{i}. {row['상품명']} ({row['상품코드']}) "
                f"| 판매수량: {int(row['판매수량합계'])}개 "
                f"| 매출: {int(row['매출액합계']):,}원"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_top_sales Tool 오류: {e}")
        return f"판매 조회 중 오류 발생: {e}"


def _get_stock_by_product(input: str = "") -> str:
    try:
        product_name = input.strip()
        if not product_name:
            return "상품명 또는 상품코드를 입력해주세요."

        df_master = read_product_master()
        df_stock  = read_stock()

        mask = (
                df_master["상품명"].str.contains(product_name, case=False, na=False) |
                df_master["상품코드"].str.contains(product_name, case=False, na=False)
        )
        matched = df_master[mask]

        if matched.empty:
            return f"'{product_name}' 에 해당하는 상품을 찾을 수 없습니다."

        df = matched.merge(df_stock, on="상품코드", how="left")
        lines = [f" '{product_name}' 검색 결과 {len(df)}건:"]
        for _, row in df.iterrows():
            stock   = int(row.get("현재재고", 0)) if str(row.get("현재재고", "")) != "nan" else 0
            restock = row.get("입고예정일", "-")
            lines.append(
                f"• {row['상품명']} ({row['상품코드']}) "
                f"| 현재재고: {stock}개 | 입고예정: {restock}"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_stock_by_product Tool 오류: {e}")
        return f"상품 재고 조회 중 오류 발생: {e}"


def _get_sales_trend(input: str = "") -> str:
    try:
        parts        = input.strip().split()
        product_code = parts[0] if parts else ""
        days_int     = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30

        if not product_code:
            return "상품코드를 입력해주세요. 예: 'CR001 30'"

        df_sales = read_sales()
        trend    = get_sales_trend(df_sales, product_code, days=days_int)

        if trend.empty:
            return f"{product_code} 상품의 최근 {days_int}일 판매 데이터가 없습니다."

        lines = [f"📊 {product_code} 최근 {days_int}일 판매 트렌드:"]
        for _, row in trend.iterrows():
            lines.append(
                f"• {str(row['날짜'])[:10]} "
                f"| 판매: {int(row['판매수량'])}개 "
                f"| 매출: {int(row['매출액']):,}원"
            )
        total_qty = int(trend["판매수량"].sum())
        total_rev = int(trend["매출액"].sum())
        lines.append(f"합계: 판매 {total_qty}개 | 매출 {total_rev:,}원")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"get_sales_trend Tool 오류: {e}")
        return f"판매 트렌드 조회 중 오류 발생: {e}"


def _get_anomalies(input: str = "unresolved") -> str:
    try:
        from app.db.connection import SessionLocal
        from app.db.repository import get_anomaly_logs

        status = input.strip() if input.strip() else "unresolved"
        db = SessionLocal()
        try:
            is_resolved = False if status == "unresolved" else None
            records = get_anomaly_logs(db, is_resolved=is_resolved, limit=20)
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
            "low": "낮음", "medium": "보통",
            "high": "높음", "critical": "긴급",
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


def _generate_report(input: str = "") -> str:
    try:
        import threading
        from app.scheduler.jobs import run_daily_job
        thread = threading.Thread(target=run_daily_job, daemon=True)
        thread.start()
        logger.info("보고서 생성 트리거 (Tool)")
        return "보고서 생성을 시작했습니다. 완료되면 Slack으로 전송됩니다."
    except Exception as e:
        logger.error(f"generate_report Tool 오류: {e}")
        return f"보고서 생성 트리거 중 오류 발생: {e}"


# ########### Tool List ##########################
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