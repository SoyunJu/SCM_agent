
import pandas as pd
from loguru import logger
from typing import TypedDict
from app.db.models import AnomalyType, Severity


class StockAnomaly(TypedDict):
    product_code: str
    product_name: str
    anomaly_type: str
    current_stock: int
    safety_stock: int
    daily_avg_sales: float
    days_until_stockout: float
    restock_date: str
    severity: str


def _calc_severity_low_stock(days_until_stockout: float) -> Severity:
    """
    - 1일 이하  : CRITICAL
    - 3일 이하  : HIGH
    - 7일 이하  : MEDIUM
    - 그 이상   : LOW
    """
    if days_until_stockout <= 1:
        return Severity.CRITICAL
    elif days_until_stockout <= 3:
        return Severity.HIGH
    elif days_until_stockout <= 7:
        return Severity.MEDIUM
    else:
        return Severity.LOW


def detect_low_stock(
        df_master: pd.DataFrame,
        df_stock: pd.DataFrame,
        df_sales: pd.DataFrame,
        days: int = 7,
) -> list[StockAnomaly]:

    results = []


    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    recent_sales = df_sales[df_sales["날짜"] >= cutoff]
    # 최근 N일 일평균 판매량 계산
    avg_sales = (
        recent_sales.groupby("상품코드")["판매수량"]
        .sum()
        .div(days)
        .reset_index()
        .rename(columns={"판매수량": "일평균판매량"})
    )

    # 마스터 + 재고 + 판매 병합
    df = df_master.merge(df_stock, on="상품코드", how="left")
    df = df.merge(avg_sales, on="상품코드", how="left")
    df["일평균판매량"] = df["일평균판매량"].fillna(0)
    df["현재재고"] = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0)
    df["안전재고기준"] = pd.to_numeric(df["안전재고기준"], errors="coerce").fillna(10)

    df = df[df["상품코드"].isin(df_stock["상품코드"])]
    low_stock = df[df["현재재고"] <= df["안전재고기준"]]

    for _, row in low_stock.iterrows():
        avg = row["일평균판매량"]
        stock = row["현재재고"]

        # 소진 예상일 계산 (판매 없으면 999일)
        days_until_stockout = round(stock / avg, 1) if avg > 0 else 999.0

        severity = _calc_severity_low_stock(days_until_stockout)

        results.append(StockAnomaly(
            product_code=str(row["상품코드"]),
            product_name=str(row["상품명"]),
            anomaly_type=AnomalyType.LOW_STOCK,
            current_stock=int(stock),
            safety_stock=int(row["안전재고기준"]),
            daily_avg_sales=round(avg, 2),
            days_until_stockout=days_until_stockout,
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
) -> list[StockAnomaly]:

    results = []

    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    recent_sales = df_sales[df_sales["날짜"] >= cutoff]
    avg_sales = (
        recent_sales.groupby("상품코드")["판매수량"]
        .sum()
        .div(days)
        .reset_index()
        .rename(columns={"판매수량": "일평균판매량"})
    )

    df = df_master.merge(df_stock, on="상품코드", how="left")
    df = df.merge(avg_sales, on="상품코드", how="left")
    df["일평균판매량"] = df["일평균판매량"].fillna(0)
    df["현재재고"] = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0)
    df["안전재고기준"] = pd.to_numeric(df["안전재고기준"], errors="coerce").fillna(10)

    over_stock = df[df["현재재고"] >= df["안전재고기준"] * over_ratio]

    for _, row in over_stock.iterrows():
        avg = row["일평균판매량"]
        stock = row["현재재고"]
        days_until_stockout = round(stock / avg, 1) if avg > 0 else 999.0

        results.append(StockAnomaly(
            product_code=str(row["상품코드"]),
            product_name=str(row["상품명"]),
            anomaly_type=AnomalyType.OVER_STOCK,
            current_stock=int(stock),
            safety_stock=int(row["안전재고기준"]),
            daily_avg_sales=round(avg, 2),
            days_until_stockout=days_until_stockout,
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
    recent_sold_codes = set(
        df_sales[df_sales["날짜"] >= cutoff]["상품코드"].unique()
    )

    df = df_master.merge(df_stock, on="상품코드", how="left")
    df["현재재고"] = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0)

    long_term = df[
        (df["현재재고"] > 0) &
        (~df["상품코드"].isin(recent_sold_codes))
        ]

    for _, row in long_term.iterrows():
        results.append(StockAnomaly(
            product_code=str(row["상품코드"]),
            product_name=str(row["상품명"]),
            anomaly_type=AnomalyType.LONG_TERM_STOCK,
            current_stock=int(row["현재재고"]),
            safety_stock=int(row.get("안전재고기준", 10)),
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
) -> list[StockAnomaly]:
    logger.info("################## 재고 분석 시작 ##################")
    results = []
    results.extend(detect_low_stock(df_master, df_stock, df_sales))
    results.extend(detect_over_stock(df_master, df_stock, df_sales))
    results.extend(detect_long_term_stock(df_master, df_stock, df_sales))
    logger.info(f"################## 재고 분석 완료: 총 {len(results)}개 이상 징후 ##################")
    return results