import threading
import pandas as pd
import gspread
from loguru import logger
from datetime import date, timedelta
from app.sheets.client import get_spreadsheet
from app.cache.redis_client import cache_delete

# 시트별 쓰기 동시 호출 방지
_sheet_locks: dict[str, threading.Lock] = {}
_sheet_locks_guard = threading.Lock()


def _get_lock(sheet_name: str) -> threading.Lock:
    with _sheet_locks_guard:
        if sheet_name not in _sheet_locks:
            _sheet_locks[sheet_name] = threading.Lock()
        return _sheet_locks[sheet_name]


def _clear_and_write(worksheet: gspread.Worksheet, df: pd.DataFrame) -> None:
    worksheet.clear()
    df = df.fillna("")
    worksheet.update([df.columns.tolist()] + df.values.tolist(), value_input_option="USER_ENTERED")


def _invalidate(sheet_name: str) -> None:
    cache_delete(f"sheets:{sheet_name}")


def write_product_master(df_crawled: pd.DataFrame) -> None:
    with _get_lock("상품마스터"):
        try:
            ws = get_spreadsheet().worksheet("상품마스터")
            df = df_crawled[["상품코드", "상품명", "카테고리"]].copy()
            df["안전재고기준"] = 10
            _clear_and_write(ws, df)
            _invalidate("상품마스터")
            logger.info(f"상품마스터 갱신: {len(df)}행")
        except Exception as e:
            logger.error(f"상품마스터 갱신 실패: {e}")
            raise


def upsert_master_from_excel(df_sales: pd.DataFrame) -> None:
    with _get_lock("상품마스터"):
        try:
            spreadsheet = get_spreadsheet()
            ws = spreadsheet.worksheet("상품마스터")
            existing = ws.get_all_records()
            existing_codes = {r["상품코드"] for r in existing} if existing else set()

            # 상품명 컬럼 없을 경우 방어
            if "상품명" not in df_sales.columns:
                df_sales = df_sales.copy()
                df_sales["상품명"] = ""

            new_products = (
                df_sales[~df_sales["상품코드"].isin(existing_codes)]
                [["상품코드", "상품명"]]
                .drop_duplicates("상품코드")
            )
            if new_products.empty:
                return

            new_products = new_products.copy()
            new_products["카테고리"] = ""
            new_products["안전재고기준"] = 10
            rows = new_products[["상품코드", "상품명", "카테고리", "안전재고기준"]].values.tolist()
            ws.append_rows(rows, value_input_option="USER_ENTERED")
            _invalidate("상품마스터")
            logger.info(f"상품마스터 신규 추가: {len(rows)}건")
        except Exception as e:
            logger.error(f"상품마스터 upsert 실패: {e}")



def write_stock_upsert(df_crawled: pd.DataFrame) -> None:
    with _get_lock("재고현황"):
        try:
            ws       = get_spreadsheet().worksheet("재고현황")
            existing = ws.get_all_records()
            crawled_codes = set(df_crawled["상품코드"].tolist())
            existing_codes = {r["상품코드"] for r in existing} if existing else set()
            new_codes = crawled_codes - existing_codes
            if not new_codes:
                return

            default_restock = (date.today() + timedelta(days=14)).strftime("%Y-%m-%d")
            new_rows = [[code, 0, default_restock, 100] for code in sorted(new_codes)]
            if not existing:
                _clear_and_write(ws, pd.DataFrame(new_rows, columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"]))
            else:
                ws.append_rows(new_rows, value_input_option="USER_ENTERED")
            _invalidate("재고현황")
            logger.info(f"재고현황: 신규 {len(new_rows)}개 추가")
        except Exception as e:
            logger.error(f"재고현황 upsert 실패: {e}")
            raise


def upsert_stock_from_excel(df_stock_excel: pd.DataFrame) -> None:
    with _get_lock("재고현황"):
        try:
            ws       = get_spreadsheet().worksheet("재고현황")
            existing = ws.get_all_records()
            excel_codes    = set(df_stock_excel["상품코드"].astype(str).tolist())
            existing_codes = {str(r["상품코드"]) for r in existing} if existing else set()
            new_codes = excel_codes - existing_codes
            if not new_codes:
                return

            new_df = df_stock_excel[df_stock_excel["상품코드"].astype(str).isin(new_codes)]
            cols   = [c for c in ["상품코드", "현재재고", "입고예정일", "입고예정수량"] if c in new_df.columns]
            new_df = new_df[cols].fillna("")
            if not existing:
                _clear_and_write(ws, new_df)
            else:
                ws.append_rows(new_df.values.tolist(), value_input_option="USER_ENTERED")
            _invalidate("재고현황")
            logger.info(f"재고현황: 엑셀 신규 {len(new_df)}개 추가")
        except Exception as e:
            logger.error(f"재고현황 Excel upsert 실패: {e}")
            raise


def write_sales(df_sales: pd.DataFrame) -> None:
    with _get_lock("일별판매"):
        try:
            ws       = get_spreadsheet().worksheet("일별판매")
            existing = ws.get_all_records()
            if existing:
                existing_df = pd.DataFrame(existing)
                if "날짜" in existing_df.columns and "날짜" in df_sales.columns:
                    # 중복 insert 방지
                    incoming_dates = set(df_sales["날짜"].astype(str).unique())
                    existing_df = existing_df[~existing_df["날짜"].astype(str).isin(incoming_dates)]
                combined = pd.concat([existing_df, df_sales], ignore_index=True)
                _clear_and_write(ws, combined)
            else:
                _clear_and_write(ws, df_sales)
            _invalidate("일별판매")
            logger.info(f"일별판매 갱신: {len(df_sales)}행 추가")
        except Exception as e:
            logger.error(f"일별판매 갱신 실패: {e}")
            raise


def write_stock(df_stock: pd.DataFrame) -> None:
    with _get_lock("재고현황"):
        try:
            _clear_and_write(get_spreadsheet().worksheet("재고현황"), df_stock)
            _invalidate("재고현황")
            logger.info(f"재고현황 갱신: {len(df_stock)}행")
        except Exception as e:
            logger.error(f"재고현황 갱신 실패: {e}")
            raise


def write_orders(df_orders: pd.DataFrame) -> None:
    with _get_lock("주문관리"):
        try:
            spreadsheet = get_spreadsheet()
            try:
                ws = spreadsheet.worksheet("주문관리")
            except Exception:
                ws = spreadsheet.add_worksheet(title="주문관리", rows=1000, cols=10)
            _clear_and_write(ws, df_orders)
            _invalidate("주문관리")
            logger.info(f"주문관리 갱신: {len(df_orders)}행")
        except Exception as e:
            logger.error(f"주문관리 갱신 실패: {e}")
            raise


def write_analysis_result(df_result: pd.DataFrame) -> None:
    import json

    with _get_lock("분석결과"):
        try:
            df_clean = df_result.copy()
            for col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(
                    lambda x: json.dumps(x, ensure_ascii=False)
                    if isinstance(x, (dict, list)) else x
                )

            spreadsheet = get_spreadsheet()
            ws = spreadsheet.worksheet("분석결과")
            _clear_and_write(ws, df_clean)
            _invalidate("분석결과")
            logger.info(f"분석결과 갱신 완료: {len(df_result)}행")
        except Exception as e:
            logger.error(f"분석결과 갱신 실패: {e}")
            raise
