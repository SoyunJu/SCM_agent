
import pandas as pd
from loguru import logger
from app.sheets.client import get_spreadsheet


def _worksheet_to_df(sheet_name: str) -> pd.DataFrame:

    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet(sheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)     # 데이트폼 변환
        logger.info(f"시트 읽기 완료: [{sheet_name}] {len(df)}행")
        return df
    except Exception as e:
        logger.error(f"시트 읽기 실패 [{sheet_name}]: {e}")
        raise


def read_product_master() -> pd.DataFrame:
    return _worksheet_to_df("상품마스터")


def read_sales() -> pd.DataFrame:
    return _worksheet_to_df("일별판매")


def read_stock() -> pd.DataFrame:
    return _worksheet_to_df("재고현황")


def read_analysis_result() -> pd.DataFrame:
    return _worksheet_to_df("분석결과")