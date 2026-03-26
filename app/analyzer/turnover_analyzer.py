# app/analyzer/turnover_analyzer.py

import pandas as pd
from loguru import logger


def calc_inventory_turnover(
        df_master: pd.DataFrame,
        df_sales: pd.DataFrame,
        df_stock: pd.DataFrame,
        days: int = 30,
) -> list[dict]:
    """
    재고 회전율 = 기간 판매량 / 현재재고
    체류일수  = days / 회전율  (회전율 0이면 None)
    등급: 체류일수 7이하=우수, 30이하=보통, 초과=주의
    """
    logger.info(f"재고 회전율 분석 시작 (기간: {days}일)")

    df_sales = df_sales.copy()
    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    df_filtered = df_sales[df_sales["날짜"] >= cutoff]

    # 기간 판매량 집계
    agg = (
        df_filtered.groupby("상품코드")
        .agg(기간판매량=("판매수량", "sum"))
        .reset_index()
    )

    # 재고현황 준비
    df_stock = df_stock.copy()
    if "현재재고" in df_stock.columns:
        df_stock["현재재고"] = pd.to_numeric(df_stock["현재재고"], errors="coerce").fillna(0).astype(int)

    # 마스터 기준 병합
    df = df_master.merge(agg,     on="상품코드", how="left")
    df = df.merge(df_stock[["상품코드", "현재재고"]], on="상품코드", how="left")
    df["기간판매량"] = df["기간판매량"].fillna(0).astype(int)
    df["현재재고"]   = df["현재재고"].fillna(0).astype(int)

    results = []
    for _, row in df.iterrows():
        sales = int(row["기간판매량"])
        stock = int(row["현재재고"])

        if stock > 0:
            turnover    = round(sales / stock, 2)
            stay_days   = round(days / turnover, 1) if turnover > 0 else None
        else:
            turnover  = round(float(sales), 2)   # 재고 0이면 판매량 = 회전율로 표시
            stay_days = None

        if stay_days is None:
            grade = "데이터없음"
        elif stay_days <= 7:
            grade = "우수"
        elif stay_days <= 30:
            grade = "보통"
        else:
            grade = "주의"

        results.append({
            "상품코드":   str(row["상품코드"]),
            "상품명":    str(row.get("상품명", "")),
            "카테고리":  str(row.get("카테고리", "")),
            "기간판매량": sales,
            "현재재고":  stock,
            "회전율":    turnover,
            "체류일수":  stay_days,
            "등급":      grade,
        })

    # 체류일수 오름차순 (None은 뒤로)
    results.sort(key=lambda x: (x["체류일수"] is None, x["체류일수"] or 0))
    logger.info(f"재고 회전율 분석 완료: {len(results)}건")
    return results
