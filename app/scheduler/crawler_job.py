import asyncio
import os
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.crawler.scraper import crawl_all_sites
from app.crawler.excel_parser import parse_sales_sheet, parse_stock_sheet
from app.cache.redis_client import cache_set

EXCEL_PATH = os.getenv("EXCEL_PATH", "./sample_data.xlsx")
SCHEDULE_HOUR   = int(os.getenv("CRAWLER_SCHEDULE_HOUR", "23"))
SCHEDULE_MINUTE = int(os.getenv("CRAWLER_SCHEDULE_MINUTE", "0"))
CACHE_TTL = 86400  # 24시간


def run_crawler_job() -> None:
    logger.info("===== [크롤러 컨테이너] 크롤링 시작 =====")
    try:
        df_crawled = crawl_all_sites(
            books_pages=3,
            webscraper_pages=2,
            scrapingcourse_pages=2,
        )
        if not df_crawled.empty:
            cache_set("crawler:results", df_crawled.to_dict(orient="records"), ttl=CACHE_TTL)
            logger.info(f"크롤링 결과 Redis 저장 완료: {len(df_crawled)}개 상품")
        else:
            logger.warning("크롤링 결과 없음")
    except Exception as e:
        logger.error(f"크롤링 실패: {e}")

    # 엑셀 판매 데이터도 캐싱
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

    logger.info("===== [크롤러 컨테이너] 완료 =====")


if __name__ == "__main__":
    # 최초 즉시 실행
    run_crawler_job()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_crawler_job,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="crawler_job",
        name="크롤링 전용 작업",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"크롤러 스케줄 등록: 매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d}")

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
