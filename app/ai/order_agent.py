import math

from loguru import logger

from app.utils.severity import norm, SEVERITY_RANK


# 디폴트 config
_DEFAULT_LEAD_TIME_DAYS = 14
_DEFAULT_SAFETY_STOCK_DAYS = 7


def _get_global_settings() -> tuple[int, int, str]:
    try:
        from app.db.connection import SessionLocal
        from app.db.repository import get_setting
        db = SessionLocal()
        try:
            lead_time    = int(get_setting(db, "DEFAULT_LEAD_TIME_DAYS",    str(_DEFAULT_LEAD_TIME_DAYS)))
            safety_days  = int(get_setting(db, "DEFAULT_SAFETY_STOCK_DAYS", str(_DEFAULT_SAFETY_STOCK_DAYS)))
            min_severity = norm(get_setting(db, "AUTO_ORDER_MIN_SEVERITY", "HIGH"))
            return lead_time, safety_days, min_severity
        finally:
            db.close()
    except Exception:
        return _DEFAULT_LEAD_TIME_DAYS, _DEFAULT_SAFETY_STOCK_DAYS, "HIGH"


# 상품별 리드타임
def _get_lead_time_map() -> dict[str, int]:
    try:
        from app.db.connection import SessionLocal
        from app.db.models import Product
        db = SessionLocal()
        try:
            rows = db.query(Product.code, Product.lead_time_days).filter(
                Product.lead_time_days.isnot(None)
            ).all()
            return {r.code: r.lead_time_days for r in rows}
        finally:
            db.close()
    except Exception:
        return {}


def generate_order_proposals(
        stock_anomalies: list[dict],
        df_master,
        df_stock,
        df_sales,
) -> list[dict]:

    proposals: list[dict] = []
    global_lead_time, safety_stock_days, min_sev = _get_global_settings()
    lead_time_map = _get_lead_time_map()  # 상품별 개별 리드타임
    min_level     = SEVERITY_RANK.get(min_sev, 2)

    # 상품코드 → 현재 재고
    stock_map: dict[str, int] = {}
    if df_stock is not None and not df_stock.empty and "상품코드" in df_stock.columns:
        import pandas as pd
        df_stock = df_stock.copy()
        df_stock["현재재고"] = pd.to_numeric(df_stock["현재재고"], errors="coerce").fillna(0).astype(int)
        stock_map = dict(zip(df_stock["상품코드"].astype(str), df_stock["현재재고"]))

    # 상품코드 → 일평균 판매량 + 평균 매입단가
    avg_sales_map:  dict[str, float] = {}
    unit_price_map: dict[str, float] = {}
    if df_sales is not None and not df_sales.empty and "상품코드" in df_sales.columns:
        import pandas as pd
        df_sales = df_sales.copy()
        df_sales["판매수량"] = pd.to_numeric(df_sales["판매수량"], errors="coerce").fillna(0)
        df_sales["매출액"]   = pd.to_numeric(df_sales.get("매출액",   0), errors="coerce").fillna(0)
        df_sales["매입액"]   = pd.to_numeric(df_sales.get("매입액",   0), errors="coerce").fillna(0)

        grp = df_sales.groupby("상품코드").agg(
            avg_qty=   ("판매수량", "mean"),
            total_qty= ("판매수량", "sum"),
            total_rev= ("매출액",   "sum"),
            total_cost=("매입액",   "sum"),
        )
        avg_sales_map = grp["avg_qty"].to_dict()

        for code, row in grp.iterrows():
            tq, tc, tr = row["total_qty"], row["total_cost"], row["total_rev"]
            if tq > 0 and tc > 0:
                unit_price_map[code] = round(tc / tq, 0)
            elif tq > 0 and tr > 0:
                unit_price_map[code] = round(tr / tq, 0)
            else:
                unit_price_map[code] = 0.0

    # 상품코드 → 카테고리
    category_map: dict[str, str] = {}
    if df_master is not None and not df_master.empty and "상품코드" in df_master.columns:
        cat_col = next((c for c in ["카테고리", "분류", "category"] if c in df_master.columns), None)
        if cat_col:
            category_map = dict(zip(df_master["상품코드"].astype(str), df_master[cat_col].fillna("")))

    for anomaly in stock_anomalies:
        severity  = norm(anomaly.get("severity", ""))
        sev_level = SEVERITY_RANK.get(severity, 0)
        if sev_level < min_level:
            continue

        code = str(anomaly.get("product_code", anomaly.get("상품코드", "")))
        name = str(anomaly.get("product_name", anomaly.get("상품명", "")))

        current_stock = int(stock_map.get(code, anomaly.get("current_stock", 0) or 0))
        avg_sales     = float(avg_sales_map.get(code, anomaly.get("daily_avg_sales", 1) or 1))

        # 리드타임: 상품별 설정 > 전역 설정
        lead_time    = lead_time_map.get(code, global_lead_time)
        safety_stock = math.ceil(avg_sales * safety_stock_days)
        lead_demand  = math.ceil(avg_sales * lead_time)
        proposed_qty = max(1, math.ceil(safety_stock + lead_demand - current_stock))

        unit_price = unit_price_map.get(code, 0.0)
        reason = (
                f"재고 {current_stock}개 / 일평균 {avg_sales:.1f}개 / "
                f"리드타임 {lead_time}일"
                + (" (상품별 설정)" if code in lead_time_map else " (전역 설정)")
        )

        proposals.append({
            "product_code": code,
            "product_name": name,
            "category":     category_map.get(code, ""),
            "proposed_qty": proposed_qty,
            "unit_price":   unit_price,
            "reason":       reason,
        })
        logger.info(f"[발주제안] {code} {name}: {proposed_qty}개 @ {unit_price:,.0f}원 (리드타임 {lead_time}일)")

    return proposals