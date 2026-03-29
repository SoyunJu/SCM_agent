import asyncio
import os
from loguru import logger

from app.crawler.scraper import crawl_all_sites
from app.crawler.excel_parser import parse_sales_sheet, parse_stock_sheet
from app.cache.redis_client import cache_set

EXCEL_PATH = os.getenv("EXCEL_PATH", "./sample_data.xlsx")
CACHE_TTL  = 86400  # 24시간


def run_crawler_job() -> None:
    logger.info("===== 크롤링 시작 =====")

    try:
        df_crawled = crawl_all_sites(books_pages=3, webscraper_pages=2, scrapingcourse_pages=2)
        if not df_crawled.empty:
            cache_set("crawler:results", df_crawled.to_dict(orient="records"), ttl=CACHE_TTL)
            logger.info(f"크롤링 결과 Redis 저장: {len(df_crawled)}개 상품")
        else:
            logger.warning("크롤링 결과 없음")
    except Exception as e:
        logger.error(f"크롤링 실패: {e}")

    if os.path.exists(EXCEL_PATH):
        try:
            df_sales = parse_sales_sheet(EXCEL_PATH)
            cache_set("excel:sales", df_sales.to_dict(orient="records"), ttl=CACHE_TTL)
            logger.info(f"엑셀 판매 데이터 Redis 저장: {len(df_sales)}행")
        except Exception as e:
            logger.warning(f"엑셀 판매 캐싱 실패: {e}")

        try:
            df_stock = parse_stock_sheet(EXCEL_PATH)
            cache_set("excel:stock", df_stock.to_dict(orient="records"), ttl=CACHE_TTL)
            logger.info(f"엑셀 재고 데이터 Redis 저장: {len(df_stock)}행")
        except Exception as e:
            logger.warning(f"엑셀 재고 캐싱 실패: {e}")

    logger.info("===== 크롤링 완료 =====")


if __name__ == "__main__":
    run_crawler_job()