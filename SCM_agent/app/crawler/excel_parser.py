
import pandas as pd
from loguru import logger


def parse_stock_sheet(file_path: str) -> pd.DataFrame:

    try:
        df = pd.read_excel(file_path, sheet_name="재고현황", dtype={"상품코드": str})
        df.columns = df.columns.str.strip()
        df["입고예정일"] = pd.to_datetime(df["입고예정일"]).dt.strftime("%Y-%m-%d")
        logger.info(f"재고현황 시트 파싱 완료: {len(df)}행")
        return df
    except Exception as e:
        logger.error(f"재고현황 시트 파싱 실패: {e}")
        raise


def parse_sales_sheet(file_path: str) -> pd.DataFrame:

    try:
        df = pd.read_excel(file_path, sheet_name="일별판매", dtype={"상품코드": str})
        df.columns = df.columns.str.strip()
        df["날짜"] = pd.to_datetime(df["날짜"]).dt.strftime("%Y-%m-%d")
        logger.info(f"일별판매 시트 파싱 완료: {len(df)}행")
        return df
    except Exception as e:
        logger.error(f"일별판매 시트 파싱 실패: {e}")
        raise