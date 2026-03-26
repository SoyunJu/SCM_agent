import os
import pandas as pd
from loguru import logger
from app.sheets.client import get_spreadsheet
from app.cache.redis_client import cache_get, cache_set

SHEETS_CACHE_TTL = int(os.getenv("SHEETS_CACHE_TTL", "300"))


def _worksheet_to_df(sheet_name: str) -> pd.DataFrame:
    cache_key = f"sheets:{sheet_name}"

    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug(f"캐시 히트: [{sheet_name}]")
        return pd.DataFrame(cached)

    spreadsheet = get_spreadsheet()
    ws   = spreadsheet.worksheet(sheet_name)
    data = ws.get_all_records()
    df   = pd.DataFrame(data)
    logger.info(f"시트 읽기 완료: [{sheet_name}] {len(df)}행")

    cache_set(cache_key, df.to_dict(orient="records"), ttl=SHEETS_CACHE_TTL)
    return df


def read_product_master() -> pd.DataFrame:
    return _worksheet_to_df("상품마스터")


def read_sales() -> pd.DataFrame:
    return _worksheet_to_df("일별판매")


def read_stock() -> pd.DataFrame:
    return _worksheet_to_df("재고현황")


def read_analysis_result() -> pd.DataFrame:
    return _worksheet_to_df("분석결과")


def read_orders() -> pd.DataFrame:
    try:
        return _worksheet_to_df("주문관리")
    except Exception as e:
        logger.warning(f"주문관리 시트 읽기 실패 (없을 수 있음): {e}")
        return pd.DataFrame(columns=["주문코드", "상품코드", "상품명", "발주수량", "발주일", "예정납기일", "상태"])
