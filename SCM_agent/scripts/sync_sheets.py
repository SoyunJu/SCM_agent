
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from app.crawler.scraper import crawl_books
from app.crawler.excel_parser import parse_stock_sheet, parse_sales_sheet
from app.sheets.writer import write_product_master, write_sales, write_stock

EXCEL_PATH = "./sample_data.xlsx"


def sync_all():
    logger.info("===== Sheets 동기화 시작 =====")

    logger.info("[1/3] books.toscrape.com 크롤링")
    df_crawled = crawl_books(max_pages=3)
    write_product_master(df_crawled)

    logger.info("[2/3] 엑셀 재고현황 파싱")
    df_stock = parse_stock_sheet(EXCEL_PATH)
    write_stock(df_stock)

    logger.info("[3/3] 엑셀 일별판매 파싱")
    df_sales = parse_sales_sheet(EXCEL_PATH)
    write_sales(df_sales)

    logger.info("===== Sheets 동기화 완료 =====")


if __name__ == "__main__":
    sync_all()