import math
from loguru import logger

LEAD_TIME_DAYS = 14          # 리드타임(일)
SAFETY_STOCK_DAYS = 7        # 안전재고 일수


def generate_order_proposals(
        stock_anomalies: list[dict],
        df_master,
        df_stock,
        df_sales,
) -> list[dict]:

    proposals: list[dict] = []

    # 상품코드 -> 현재 재고
    stock_map: dict[str, int] = {}
    if df_stock is not None and not df_stock.empty and "상품코드" in df_stock.columns:
        import pandas as pd
        df_stock = df_stock.copy()
        df_stock["현재재고"] = pd.to_numeric(df_stock["현재재고"], errors="coerce").fillna(0).astype(int)
        stock_map = dict(zip(df_stock["상품코드"].astype(str), df_stock["현재재고"]))

    # 상품코드 → 일평균 판매량
    avg_sales_map: dict[str, float] = {}
    if df_sales is not None and not df_sales.empty and "상품코드" in df_sales.columns and "판매수량" in df_sales.columns:
        import pandas as pd
        df_sales = df_sales.copy()
        df_sales["판매수량"] = pd.to_numeric(df_sales["판매수량"], errors="coerce").fillna(0)
        grp = df_sales.groupby("상품코드")["판매수량"].mean()
        avg_sales_map = grp.to_dict()

    # 상품코드 → 카테고리
    category_map: dict[str, str] = {}
    if df_master is not None and not df_master.empty and "상품코드" in df_master.columns:
        cat_col = next((c for c in ["카테고리", "분류", "category"] if c in df_master.columns), None)
        if cat_col:
            category_map = dict(zip(df_master["상품코드"].astype(str), df_master[cat_col].fillna("")))

    for anomaly in stock_anomalies:
        severity = str(anomaly.get("severity", "")).lower()
        if severity not in ("high", "critical"):
            continue

        code = str(anomaly.get("product_code", anomaly.get("상품코드", "")))
        name = str(anomaly.get("product_name", anomaly.get("상품명", "")))
        current_stock = int(stock_map.get(code, anomaly.get("current_stock", 0) or 0))
        avg_sales = float(avg_sales_map.get(code, anomaly.get("daily_avg_sales", 1) or 1))

        # 발주 수량 = ceil(안전재고 + 리드타임 소비량 - 현재재고)
        safety_stock = math.ceil(avg_sales * SAFETY_STOCK_DAYS)
        lead_demand  = math.ceil(avg_sales * LEAD_TIME_DAYS)
        proposed_qty = max(1, math.ceil(safety_stock + lead_demand - current_stock))

        reason = (
            f"현재재고 {current_stock}개, 일평균판매 {avg_sales:.1f}개, "
            f"리드타임 {LEAD_TIME_DAYS}일 기준 발주 수량 산출"
        )

        proposals.append({
            "product_code": code,
            "product_name": name,
            "category": category_map.get(code, ""),
            "proposed_qty": proposed_qty,
            "unit_price": 0.0,
            "reason": reason,
        })
        logger.info(f"[발주제안] {code} {name}: {proposed_qty}개 ({reason})")

    return proposals
