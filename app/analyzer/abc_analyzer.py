import math
import pandas as pd
from loguru import logger


def run_abc_analysis(df_master: pd.DataFrame, df_sales: pd.DataFrame, days: int = 90) -> list[dict]:
    """
    매출 기여도 기준 ABC 분류
    A: 누적 매출 0~70%  (핵심 상품)
    B: 누적 매출 70~90% (중요 상품)
    C: 누적 매출 90~100%(저기여 상품)
    """
    logger.info(f"ABC 분석 시작 (기간: {days}일)")

    try:
        df_sales = df_sales.copy()
        df_sales["날짜"] = pd.to_datetime(df_sales["날짜"], errors="coerce")
        df_sales = df_sales.dropna(subset=["날짜"])

        cutoff = df_sales["날짜"].max() - pd.Timedelta(days=days)
        df_period = df_sales[df_sales["날짜"] >= cutoff].copy()

        if df_period.empty:
            logger.warning("ABC 분석: 기간 내 판매 데이터 없음")
            return []

        df_period["매출액"] = pd.to_numeric(df_period["매출액"], errors="coerce").fillna(0)

        agg = (
            df_period.groupby("상품코드")["매출액"]
            .sum()
            .reset_index()
            .rename(columns={"매출액": "매출합계"})
            .sort_values("매출합계", ascending=False)
        )

        total_sales = agg["매출합계"].sum()
        if total_sales <= 0:
            logger.warning("ABC 분석: 총 매출액이 0")
            return []

        agg["누적매출"] = agg["매출합계"].cumsum()
        agg["누적비율"] = (agg["누적매출"] / total_sales * 100).round(2)

        def _grade(cum_pct: float) -> str:
            if cum_pct <= 70:
                return "A"
            elif cum_pct <= 90:
                return "B"
            return "C"

        agg["등급"] = agg["누적비율"].apply(_grade)

        # 상품명/카테고리 병합
        cols = ["상품코드", "상품명"]
        if "카테고리" in df_master.columns:
            cols.append("카테고리")
        df = agg.merge(df_master[cols], on="상품코드", how="left")

        a_cnt = int((df["등급"] == "A").sum())
        b_cnt = int((df["등급"] == "B").sum())
        c_cnt = int((df["등급"] == "C").sum())
        logger.info(f"ABC 분석 완료: A={a_cnt} B={b_cnt} C={c_cnt}")

        result = df.to_dict(orient="records")

        #  NaN / Inf sanitize (JSON 직렬화 오류 방지)
        clean = []
        for row in result:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    clean_row[k] = None
                else:
                    clean_row[k] = v
            clean.append(clean_row)

        return clean

    except Exception as e:
        logger.error(f"ABC 분석 오류: {e}")
        return []
