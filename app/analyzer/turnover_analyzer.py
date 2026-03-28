import numpy as np
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
    체류일수   = days / 회전율  (회전율 0 또는 재고 0이면 None)
    등급: 체류일수 7이하=우수, 30이하=보통, 초과=주의, None=데이터없음
    """
    logger.info(f"[회전율] 분석 시작 — 기간: {days}일, 대상: {len(df_master)}개 상품")

    if df_master.empty:
        logger.warning("[회전율] 분석 대상 상품 없음")
        return []

    df_sales = df_sales.copy()
    df_sales["날짜"] = pd.to_datetime(df_sales["날짜"])

    if not df_sales.empty:
        cutoff      = df_sales["날짜"].max() - pd.Timedelta(days=days)
        df_filtered = df_sales[df_sales["날짜"] >= cutoff]
        agg = (
            df_filtered.groupby("상품코드")
            .agg(기간판매량=("판매수량", "sum"))
            .reset_index()
        )
    else:
        agg = pd.DataFrame(columns=["상품코드", "기간판매량"])

    # 재고현황
    df_stock = df_stock.copy()
    if "현재재고" in df_stock.columns:
        df_stock["현재재고"] = pd.to_numeric(df_stock["현재재고"], errors="coerce").fillna(0).astype(int)

    # 마스터 기준 병합
    df = df_master.merge(agg, on="상품코드", how="left")
    if "현재재고" in df_stock.columns:
        df = df.merge(df_stock[["상품코드", "현재재고"]], on="상품코드", how="left")
    else:
        df["현재재고"] = 0

    df["기간판매량"] = df["기간판매량"].fillna(0).astype(int)
    df["현재재고"]   = df["현재재고"].fillna(0).astype(int)

    # numpy 벡터 연산
    has_stock   = df["현재재고"] > 0
    has_sales   = df["기간판매량"] > 0

    df["회전율"] = np.where(
        has_stock,
        (df["기간판매량"] / df["현재재고"]).round(2),
        df["기간판매량"].astype(float),   # 재고 0이면 판매량 그대로
    )
    df["체류일수"] = np.where(
        has_stock & (df["회전율"] > 0),
        (days / df["회전율"]).round(1),
        np.nan,
        )

    # 등급 분류
    grade_conditions = [
        df["체류일수"].isna(),
        df["체류일수"] <= 7,
        df["체류일수"] <= 30,
        ]
    grade_choices = ["데이터없음", "우수", "보통"]
    df["등급"] = np.select(grade_conditions, grade_choices, default="주의")

    # 결과
    results = []
    for row in df.itertuples(index=False):
        stay = None if pd.isna(row.체류일수) else float(row.체류일수)
        results.append({
            "상품코드":   str(row.상품코드),
            "상품명":    str(getattr(row, "상품명", "")),
            "카테고리":  str(getattr(row, "카테고리", "")),
            "기간판매량": int(row.기간판매량),
            "현재재고":  int(row.현재재고),
            "회전율":    float(row.회전율),
            "체류일수":  stay,
            "등급":      str(row.등급),
        })

    results.sort(key=lambda x: (x["체류일수"] is None, x["체류일수"] or 0))
    logger.info(f"[회전율] 분석 완료 — {len(results)}건")
    return results
