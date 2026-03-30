import pandas as pd
from loguru import logger
from typing import TypedDict
from app.db.models import AnomalyType, Severity


class SalesAnomaly(TypedDict):
    product_code:        str
    product_name:        str
    category:            str
    anomaly_type:        str
    this_week_sales:     float
    last_week_sales:     float
    change_rate:         float
    severity:            str
    current_stock:       int
    daily_avg_sales:     float
    days_until_stockout: float


def _calc_severity_by_rate(change_rate: float, anomaly_type: AnomalyType) -> Severity:
    if anomaly_type == AnomalyType.SALES_SURGE:
        if change_rate >= 100: return Severity.CRITICAL
        if change_rate >= 70:  return Severity.HIGH
        return Severity.MEDIUM
    else:
        if change_rate <= -80: return Severity.CRITICAL
        if change_rate <= -60: return Severity.HIGH
        return Severity.MEDIUM


def detect_sales_anomaly(
        df_master: pd.DataFrame,
        df_sales: pd.DataFrame,
        surge_threshold: float = 50.0,
        drop_threshold: float = -50.0,
        df_stock: pd.DataFrame | None = None,
) -> list[SalesAnomaly]:
    results = []

    # 재고 맵 구성
    stock_map: dict[str, int] = {}
    if df_stock is not None and not df_stock.empty:
        stock_map = dict(zip(
            df_stock["상품코드"].astype(str),
            df_stock["현재재고"].fillna(0).astype(int)
        ))

    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    latest_date = df_sales["날짜"].max()

    this_week = df_sales[df_sales["날짜"] >= latest_date - pd.Timedelta(days=6)]
    last_week = df_sales[
        (df_sales["날짜"] >= latest_date - pd.Timedelta(days=13)) &
        (df_sales["날짜"] <= latest_date - pd.Timedelta(days=7))
        ]

    this_agg = this_week.groupby("상품코드")["판매수량"].sum().reset_index().rename(columns={"판매수량": "이번주"})
    last_agg = last_week.groupby("상품코드")["판매수량"].sum().reset_index().rename(columns={"판매수량": "지난주"})

    df = df_master.merge(this_agg, on="상품코드", how="left").merge(last_agg, on="상품코드", how="left")
    df["이번주"] = df["이번주"].fillna(0)
    df["지난주"] = df["지난주"].fillna(0)
    df = df[df["지난주"] > 0].copy()
    df["변화율"] = ((df["이번주"] - df["지난주"]) / df["지난주"] * 100).round(1)

    for _, row in df[df["변화율"] >= surge_threshold].iterrows():
        code          = str(row["상품코드"])
    current_stock = stock_map.get(code, 0)
    this_week     = float(row["이번주"])
    daily_avg     = round(this_week / 7, 1)
    days_stockout = round(current_stock / daily_avg, 1) if daily_avg > 0 else 999.0
    results.append(SalesAnomaly(
        product_code=code, product_name=str(row["상품명"]),
        category=str(row.get("카테고리", "")),
        anomaly_type=AnomalyType.SALES_SURGE,
        this_week_sales=this_week, last_week_sales=float(row["지난주"]),
        change_rate=float(row["변화율"]),
        severity=_calc_severity_by_rate(row["변화율"], AnomalyType.SALES_SURGE),
        current_stock=current_stock,
        daily_avg_sales=daily_avg,
        days_until_stockout=days_stockout,
    ))

    for _, row in df[df["변화율"] <= drop_threshold].iterrows():
        code          = str(row["상품코드"])
        current_stock = stock_map.get(code, 0)
        last_week     = float(row["지난주"])
        daily_avg     = round(last_week / 7, 1)
        days_stockout = round(current_stock / daily_avg, 1) if daily_avg > 0 else 999.0
        results.append(SalesAnomaly(
            product_code=code, product_name=str(row["상품명"]),
            category=str(row.get("카테고리", "")),
            anomaly_type=AnomalyType.SALES_DROP,
            this_week_sales=float(row["이번주"]), last_week_sales=last_week,
            change_rate=float(row["변화율"]),
            severity=_calc_severity_by_rate(row["변화율"], AnomalyType.SALES_DROP),
            current_stock=current_stock,
            daily_avg_sales=daily_avg,
            days_until_stockout=days_stockout,
        ))

    logger.info(f"판매 급등/급락 감지: {len(results)}건")
    return results


def run_sales_analysis(
        df_master: pd.DataFrame,
        df_sales: pd.DataFrame,
        surge_threshold: float = 50.0,
        drop_threshold: float = 50.0,
        df_stock: pd.DataFrame | None = None,
) -> list[SalesAnomaly]:
    logger.info("################## 판매 분석 시작 ##################")
    results = detect_sales_anomaly(df_master, df_sales,
                                   surge_threshold=surge_threshold,
                                   drop_threshold=-drop_threshold,
                                   df_stock=df_stock)
    logger.info(f"################## 판매 분석 완료: 총 {len(results)}개 ##################")
    return results



def get_top_sales(df_master, df_sales, days=7, top_n=5):
    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    agg = (
        df_sales[df_sales["날짜"] >= cutoff]
        .groupby("상품코드").agg(판매수량합계=("판매수량", "sum"), 매출액합계=("매출액", "sum"))
        .reset_index().sort_values("판매수량합계", ascending=False).head(top_n)
    )
    df = agg.merge(df_master[["상품코드", "상품명", "카테고리"]], on="상품코드", how="left")
    return df[["상품코드", "상품명", "카테고리", "판매수량합계", "매출액합계"]]


def get_sales_trend(df_sales, product_code, days=30):
    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    return (
        df_sales[(df_sales["상품코드"] == product_code) & (df_sales["날짜"] >= cutoff)]
        .groupby("날짜").agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
        .reset_index().sort_values("날짜")
    )
