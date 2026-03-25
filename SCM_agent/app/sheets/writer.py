
import pandas as pd
import gspread
from loguru import logger
from app.sheets.client import get_spreadsheet


def _clear_and_write(worksheet: gspread.Worksheet, df: pd.DataFrame) -> None:
    # 시트 초기화
    worksheet.clear()
    # NaN → 빈 문자열 변환 (Sheets API NaN 미지원 -> 오류 방지)
    df = df.fillna("")
    data = [df.columns.tolist()] + df.values.tolist()
    worksheet.update(data, value_input_option="USER_ENTERED")


def write_product_master(df_crawled: pd.DataFrame) -> None:

    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("상품마스터")

        df = df_crawled[["상품코드", "상품명", "카테고리"]].copy()
        df["안전재고기준"] = 10   # TODO : 하드코딩 말고 안전재고 기준 설정

        _clear_and_write(ws, df)
        logger.info(f"시트1(상품마스터) 갱신 완료: {len(df)}행")
    except Exception as e:
        logger.error(f"시트1 갱신 실패: {e}")
        raise


def write_sales(df_sales: pd.DataFrame) -> None:

    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("일별판매")
        _clear_and_write(ws, df_sales)
        logger.info(f"시트2(일별판매) 갱신 완료: {len(df_sales)}행")
    except Exception as e:
        logger.error(f"시트2 갱신 실패: {e}")
        raise


def write_stock(df_stock: pd.DataFrame) -> None:

    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("재고현황")
        _clear_and_write(ws, df_stock)
        logger.info(f"시트3(재고현황) 갱신 완료: {len(df_stock)}행")
    except Exception as e:
        logger.error(f"시트3 갱신 실패: {e}")
        raise


def write_analysis_result(df_result: pd.DataFrame) -> None:

    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("분석결과")
        _clear_and_write(ws, df_result)
        logger.info(f"시트4(분석결과) 갱신 완료: {len(df_result)}행")
    except Exception as e:
        logger.error(f"시트4 갱신 실패: {e}")
        raise