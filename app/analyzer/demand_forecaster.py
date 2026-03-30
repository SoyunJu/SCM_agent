import pandas as pd
from loguru import logger


# 변경 : 7일 이상이면 계산, 3~6일은 단순 비교
def _calc_trend(series: pd.Series) -> str:
    if len(series) < 3:
        return "unknown"
    if len(series) < 7:
        mid    = len(series) // 2
        recent = series.iloc[mid:].mean()
        prev   = series.iloc[:mid].mean()
    else:
        half   = min(7, len(series) // 2)
        recent = series.iloc[-half:].mean()
        prev   = series.iloc[-half*2:-half].mean()
    if prev == 0:
        return "stable"
    change = (recent - prev) / prev * 100
    if change >= 10:    return "up"
    elif change <= -10: return "down"
    return "stable"


def _forecast_from_group(group: pd.DataFrame, forecast_days: int) -> tuple[float, int, str]:
    daily = (
        group.groupby("날짜")["판매수량"]
        .sum()
        .reset_index()
        .sort_values("날짜")
    )
    daily["ma7"]  = daily["판매수량"].rolling(window=7, min_periods=1).mean()
    daily_avg     = round(float(daily["ma7"].iloc[-1]), 2)
    forecast_qty  = int(daily_avg * forecast_days)
    trend         = _calc_trend(daily["판매수량"])
    return daily_avg, forecast_qty, trend



def run_demand_forecast_all(
        df_master: pd.DataFrame,
        df_sales: pd.DataFrame,
        df_stock: pd.DataFrame,
        forecast_days: int = 14,
) -> list[dict]:

    logger.info(f"[수요예측] 분석 시작 — 예측 기간: {forecast_days}일, 대상 상품: {len(df_master)}개")

    if df_master.empty:
        logger.warning("[수요예측] 분석 대상 상품 없음")
        return []

    df_sales = df_sales.copy()
    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])

    # 상품 코드 → 재고
    stock_map: dict[str, int] = {}
    if not df_stock.empty and "상품코드" in df_stock.columns and "현재재고" in df_stock.columns:
        df_stock = df_stock.copy()
        df_stock["현재재고"] = pd.to_numeric(df_stock["현재재고"], errors="coerce").fillna(0).astype(int)
        stock_map = dict(zip(df_stock["상품코드"].astype(str), df_stock["현재재고"]))

    # 상품코드별 그룹화 (O(m) 1회)
    # 이후 각 상품 조회는 O(1) → 전체 O(n+m) 달성
    sales_by_code: dict[str, pd.DataFrame] = {
        str(code): group.copy()
        for code, group in df_sales.groupby("상품코드")
    }

    results = []
    for row in df_master.itertuples(index=False):
        code  = str(row.상품코드)
        group = sales_by_code.get(code)

        if group is None or group.empty:
            daily_avg, forecast_qty, trend = 0.0, 0, "stable"
        else:
            try:
                daily_avg, forecast_qty, trend = _forecast_from_group(group, forecast_days)
            except Exception as exc:
                logger.warning(f"[수요예측] 상품 {code} 계산 실패 (기본값 사용): {exc}")
                daily_avg, forecast_qty, trend = 0.0, 0, "stable"

        current_stock = stock_map.get(code, 0)
        shortage      = max(0, forecast_qty - current_stock)

        results.append({
            "product_code":  code,
            "product_name":  str(getattr(row, "상품명", "")),
            "category":      str(getattr(row, "카테고리", "")),
            "daily_avg":     daily_avg,
            "forecast_qty":  forecast_qty,
            "forecast_days": forecast_days,
            "trend":         trend,
            "current_stock": current_stock,
            "shortage":      shortage,
            "sufficient":    current_stock >= forecast_qty,
        })

    results.sort(key=lambda x: (x["sufficient"], -x["shortage"]))
    shortage_cnt = sum(1 for r in results if not r["sufficient"])
    logger.info(f"[수요예측] 분석 완료 — 재고 부족 {shortage_cnt}건 / 전체 {len(results)}건")
    return results
