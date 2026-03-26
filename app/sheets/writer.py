
import pandas as pd
import gspread
from loguru import logger
from datetime import date, timedelta
from app.sheets.client import get_spreadsheet


def _clear_and_write(worksheet: gspread.Worksheet, df: pd.DataFrame) -> None:
    worksheet.clear()
    df = df.fillna("")
    data = [df.columns.tolist()] + df.values.tolist()
    worksheet.update(data, value_input_option="USER_ENTERED")


def write_product_master(df_crawled: pd.DataFrame) -> None:
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("상품마스터")

        df = df_crawled[["상품코드", "상품명", "카테고리"]].copy()
        df["안전재고기준"] = 10
        _clear_and_write(ws, df)
        logger.info(f"시트1(상품마스터) 갱신 완료: {len(df)}행")
    except Exception as e:
        logger.error(f"시트1 갱신 실패: {e}")
        raise


def write_stock_upsert(df_crawled: pd.DataFrame) -> None:
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("재고현황")
        existing = ws.get_all_records()

        crawled_codes = set(df_crawled["상품코드"].tolist())

        if existing:
            existing_codes = {r["상품코드"] for r in existing}
            new_codes = crawled_codes - existing_codes
        else:
            existing_codes = set()
            new_codes = crawled_codes

        if not new_codes:
            logger.info("시트3(재고현황) 신규 상품 없음 - 업데이트 스킵")
            return

        # 신규 상품만 append
        default_restock = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
        new_rows = [
            [code, 0, default_restock, 100]
            for code in sorted(new_codes)
        ]

        if not existing:
            df_new = pd.DataFrame(new_rows, columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"])
            _clear_and_write(ws, df_new)
        else:
            ws.append_rows(new_rows, value_input_option="USER_ENTERED")

        logger.info(f"시트3(재고현황) 신규 상품 {len(new_rows)}개 추가")
    except Exception as e:
        logger.error(f"시트3 upsert 실패: {e}")
        raise


def write_sales(df_sales: pd.DataFrame) -> None:
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("일별판매")
        existing = ws.get_all_records()
        today_str = date.today().strftime("%Y-%m-%d")

        if existing:
            # 오늘 날짜 기존 데이터 제거 후 새 데이터 append
            existing_df = pd.DataFrame(existing)
            if "날짜" in existing_df.columns:
                existing_df = existing_df[existing_df["날짜"].astype(str) != today_str]

            combined = pd.concat([existing_df, df_sales], ignore_index=True)
            _clear_and_write(ws, combined)
        else:
            _clear_and_write(ws, df_sales)

        logger.info(f"시트2(일별판매) 갱신 완료: {len(df_sales)}행 추가")
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