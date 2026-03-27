# app/analyzer/demand_forecaster.py

import pandas as pd
from loguru import logger


def _calc_trend(series: pd.Series) -> str:
    """최근 7일 vs 이전 7일 비교로 추세 판단"""
    if len(series) < 14:
        return "stable"
    recent = series.iloc[-7:].mean()
    prev   = series.iloc[-14:-7].mean()
    if prev == 0:
        return "stable"
    change = (recent - prev) / prev * 100
    if change >= 10:
        return "up"
    elif change <= -10:
        return "down"
    return "stable"


def forecast_demand(
        df_sales: pd.DataFrame,
        product_code: str,
        forecast_days: int = 14,
) -> dict:

    df = df_sales[df_sales["상품코드"] == product_code].copy()
    df["날짜"] = pd.to_datetime(df["날짜"])
    df = df.sort_values("날짜")

    if df.empty:
        return {
            "product_code":  product_code,
            "daily_avg":     0.0,
            "forecast_qty":  0,
            "forecast_days": forecast_days,
            "trend":         "stable",
        }

    # 일별 판매량 집계 후 7일 이동평균
    daily = df.groupby("날짜")["판매수량"].sum().reset_index().sort_values("날짜")
    daily["ma7"] = daily["판매수량"].rolling(window=7, min_periods=1).mean()

    daily_avg    = round(float(daily["ma7"].iloc[-1]), 2)
    forecast_qty = int(daily_avg * forecast_days)
    trend        = _calc_trend(daily["판매수량"])

    return {
        "product_code":  product_code,
        "daily_avg":     daily_avg,
        "forecast_qty":  forecast_qty,
        "forecast_days": forecast_days,
        "trend":         trend,
    }


def run_demand_forecast_all(
        df_master: pd.DataFrame,
        df_sales: pd.DataFrame,
        df_stock: pd.DataFrame,
        forecast_days: int = 14,
) -> list[dict]:

    logger.info(f"수요 예측 시작 (예측기간: {forecast_days}일, 상품수: {len(df_master)})")

    df_sales = df_sales.copy()
    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])

    # 재고현황 코드→재고 매핑
    stock_map = {}
    if not df_stock.empty and "상품코드" in df_stock.columns and "현재재고" in df_stock.columns:
        df_stock = df_stock.copy()
        df_stock["현재재고"] = pd.to_numeric(df_stock["현재재고"], errors="coerce").fillna(0).astype(int)
        stock_map = dict(zip(df_stock["상품코드"].astype(str), df_stock["현재재고"]))

    results = []
    for _, row in df_master.iterrows():
        code   = str(row["상품코드"])
        result = forecast_demand(df_sales, code, forecast_days)

        current_stock = stock_map.get(code, 0)
        shortage      = max(0, result["forecast_qty"] - current_stock)
        sufficient    = current_stock >= result["forecast_qty"]

        results.append({
            **result,
            "product_name":  str(row.get("상품명", "")) or "데이터 없음",
            "category":      str(row.get("카테고리", "")) or "Default",
            "current_stock": current_stock,
            "shortage":      shortage,
            "sufficient":    sufficient,
        })

    # 재고 부족 우선 정렬
    results.sort(key=lambda x: (x["sufficient"], -x["shortage"]))
    logger.info(f"수요 예측 완료: 부족 {sum(1 for r in results if not r['sufficient'])}건")
    return results
