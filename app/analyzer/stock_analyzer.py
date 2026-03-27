import pandas as pd
from loguru import logger
from typing import TypedDict
from app.db.models import AnomalyType, Severity


class StockAnomaly(TypedDict):
    product_code: str
    product_name: str
    category: str
    anomaly_type: str
    current_stock: int
    safety_stock: int
    daily_avg_sales: float
    days_until_stockout: float
    restock_date: str
    severity: str


def _clean_name(value) -> str:
    s = str(value).strip()
    if s in ("", "nan", "None", "NaN"):
        return "데이터 없음"
    return s


def _clean_category(value) -> str:
    s = str(value).strip()
    if s in ("", "nan", "None", "NaN"):
        return "Default"
    return s


def _calc_severity_low_stock(
        days_until_stockout: float,
        critical_days: int = 1,
        high_days: int = 3,
        medium_days: int = 7,
) -> Severity:
    if days_until_stockout <= critical_days:
        return Severity.CRITICAL
    elif days_until_stockout <= high_days:
        return Severity.HIGH
    elif days_until_stockout <= medium_days:
        return Severity.MEDIUM
    return Severity.LOW


def _calc_safety_stock(daily_avg: float, safety_stock_days: int = 7, safety_stock_default: int = 10) -> int:
    if daily_avg > 0:
        return max(round(daily_avg * safety_stock_days), safety_stock_default)
    return safety_stock_default


def detect_low_stock(
        df_master: pd.DataFrame,
        df_stock: pd.DataFrame,
        df_sales: pd.DataFrame,
        days: int = 7,
        safety_stock_days: int = 7,
        safety_stock_default: int = 10,
        critical_days: int = 1,
        high_days: int = 3,
        medium_days: int = 7,
) -> list[StockAnomaly]:
    results = []

    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    avg_sales = (
        df_sales[df_sales["날짜"] >= cutoff]
        .groupby("상품코드")["판매수량"].sum().div(days).reset_index()
        .rename(columns={"판매수량": "일평균판매량"})
    )

    df = df_master.merge(df_stock, on="상품코드", how="left")
    df = df.merge(avg_sales, on="상품코드", how="left")
    df["일평균판매량"] = df["일평균판매량"].fillna(0).astype(float)
    df["현재재고"]    = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0)
    df["안전재고기준"] = df["일평균판매량"].apply(
        lambda x: _calc_safety_stock(x, safety_stock_days, safety_stock_default)
    )

    df = df[df["상품코드"].isin(df_stock["상품코드"])]
    for _, row in df[df["현재재고"] <= df["안전재고기준"]].iterrows():
        avg   = row["일평균판매량"]
        stock = row["현재재고"]

        if avg > 0:
            days_out = round(stock / avg, 1)
            severity = _calc_severity_low_stock(days_out, critical_days, high_days, medium_days)
        elif stock == 0:
            # 재고=0, 판매이력 없음 → 확인필요
            days_out = 0.0
            severity = Severity.CHECK
        else:
            # 재고 있지만 판매이력 없음 → 낮음
            days_out = 999.0
            severity = Severity.LOW

        results.append(StockAnomaly(
            product_code=str(row["상품코드"]),
            product_name=_clean_name(row["상품명"]),
            category=_clean_category(row.get("카테고리", "")),
            anomaly_type=AnomalyType.LOW_STOCK,
            current_stock=int(stock),
            safety_stock=int(row["안전재고기준"]),
            daily_avg_sales=round(avg, 2),
            days_until_stockout=days_out,
            restock_date=str(row.get("입고예정일", "")),
            severity=severity,
        ))

    logger.info(f"재고 부족 감지: {len(results)}개 상품")
    return results


def detect_over_stock(
        df_master: pd.DataFrame,
        df_stock: pd.DataFrame,
        df_sales: pd.DataFrame,
        days: int = 7,
        over_ratio: float = 5.0,
        safety_stock_days: int = 7,
        safety_stock_default: int = 10,
) -> list[StockAnomaly]:
    results = []

    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    avg_sales = (
        df_sales[df_sales["날짜"] >= cutoff]
        .groupby("상품코드")["판매수량"].sum().div(days).reset_index()
        .rename(columns={"판매수량": "일평균판매량"})
    )

    df = df_master.merge(df_stock, on="상품코드", how="left")
    df = df.merge(avg_sales, on="상품코드", how="left")
    df["일평균판매량"] = df["일평균판매량"].fillna(0)
    df["현재재고"]    = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0)
    df["안전재고기준"] = df["일평균판매량"].apply(
        lambda x: _calc_safety_stock(x, safety_stock_days, safety_stock_default)
    )

    for _, row in df[df["현재재고"] >= df["안전재고기준"] * over_ratio].iterrows():
        avg   = row["일평균판매량"]
        stock = row["현재재고"]
        results.append(StockAnomaly(
            product_code=str(row["상품코드"]),
            product_name=_clean_name(row["상품명"]),
            category=_clean_category(row.get("카테고리", "")),
            anomaly_type=AnomalyType.OVER_STOCK,
            current_stock=int(stock),
            safety_stock=int(row["안전재고기준"]),
            daily_avg_sales=round(avg, 2),
            days_until_stockout=round(stock / avg, 1) if avg > 0 else 999.0,
            restock_date=str(row.get("입고예정일", "")),
            severity=Severity.LOW,
        ))

    logger.info(f"재고 과잉 감지: {len(results)}개 상품")
    return results


def detect_long_term_stock(
        df_master: pd.DataFrame,
        df_stock: pd.DataFrame,
        df_sales: pd.DataFrame,
        no_sales_days: int = 30,
) -> list[StockAnomaly]:
    results = []

    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=no_sales_days)
    recent_sold = set(df_sales[df_sales["날짜"] >= cutoff]["상품코드"].unique())

    df = df_master.merge(df_stock, on="상품코드", how="left")
    df["현재재고"] = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0)

    for _, row in df[(df["현재재고"] > 0) & (~df["상품코드"].isin(recent_sold))].iterrows():
        results.append(StockAnomaly(
            product_code=str(row["상품코드"]),
            product_name=_clean_name(row["상품명"]),
            category=_clean_category(row.get("카테고리", "")),
            anomaly_type=AnomalyType.LONG_TERM_STOCK,
            current_stock=int(row["현재재고"]),
            safety_stock=10,
            daily_avg_sales=0.0,
            days_until_stockout=999.0,
            restock_date=str(row.get("입고예정일", "")),
            severity=Severity.LOW,
        ))

    logger.info(f"장기 재고 감지: {len(results)}개 상품")
    return results


def run_stock_analysis(
        df_master: pd.DataFrame,
        df_stock: pd.DataFrame,
        df_sales: pd.DataFrame,
        safety_stock_days: int = 7,
        safety_stock_default: int = 10,
        critical_days: int = 1,
        high_days: int = 3,
        medium_days: int = 7,
) -> list[StockAnomaly]:
    logger.info("################## 재고 분석 시작 ##################")
    results = []
    results.extend(detect_low_stock(
        df_master, df_stock, df_sales,
        safety_stock_days=safety_stock_days, safety_stock_default=safety_stock_default,
        critical_days=critical_days, high_days=high_days, medium_days=medium_days,
    ))
    results.extend(detect_over_stock(
        df_master, df_stock, df_sales,
        safety_stock_days=safety_stock_days, safety_stock_default=safety_stock_default,
    ))
    results.extend(detect_long_term_stock(df_master, df_stock, df_sales))
    logger.info(f"################## 재고 분석 완료: 총 {len(results)}개 ##################")
    return results
