# app/analyzer/abc_analyzer.py

import pandas as pd
from loguru import logger


def run_abc_analysis(
        df_master: pd.DataFrame,
        df_sales: pd.DataFrame,
        days: int = 90,
) -> list[dict]:
    """
    매출 기여도 기준 ABC 분석
    A: 누적 매출 상위 70%
    B: 누적 매출 70~90%
    C: 누적 매출 90~100%
    """
    logger.info(f"ABC 분석 시작 (기간: {days}일)")

    df_sales = df_sales.copy()
    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])
    cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
    df_filtered = df_sales[df_sales["날짜"] >= cutoff]

    # 상품별 매출 합계
    agg = (
        df_filtered.groupby("상품코드")
        .agg(매출합계=("매출액", "sum"), 판매수량합계=("판매수량", "sum"))
        .reset_index()
        .sort_values("매출합계", ascending=False)
    )

    if agg.empty:
        logger.warning("ABC 분석: 판매 데이터 없음")
        return []

    total = agg["매출합계"].sum()
    agg["매출비율"] = (agg["매출합계"] / total * 100).round(2)
    agg["누적비율"] = agg["매출비율"].cumsum().round(2)

    def _grade(cumul: float) -> str:
        if cumul <= 70:
            return "A"
        elif cumul <= 90:
            return "B"
        return "C"

    agg["등급"] = agg["누적비율"].apply(_grade)

    # 상품명/카테고리 병합
    df = agg.merge(
        df_master[["상품코드", "상품명", "카테고리"]],
        on="상품코드", how="left",
    )

    logger.info(f"ABC 분석 완료: A={len(df[df['등급']=='A'])} B={len(df[df['등급']=='B'])} C={len(df[df['등급']=='C'])}")
    return df[["상품코드", "상품명", "카테고리", "매출합계", "판매수량합계", "매출비율", "누적비율", "등급"]].to_dict(orient="records")
