from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
from loguru import logger

# 도메인별 동시 요청 limit
_SEMAPHORE_LIMIT = 3
# 요청 타임아웃
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)
# 사이트별 딜레이(sec)
_CRAWL_DELAY = 0.5


# 헬퍼
async def _fetch(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url: str,
) -> str | None:

    async with semaphore:       # 동시 요청 제한
        try:
            async with session.get(url, timeout=_REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                return await resp.text()
        except asyncio.TimeoutError:
            logger.warning(f"[크롤러] 요청 타임아웃: {url}")
        except aiohttp.ClientResponseError as exc:
            logger.warning(f"[크롤러] HTTP 오류 {exc.status}: {url}")
        except aiohttp.ClientError as exc:
            logger.warning(f"[크롤러] 연결 오류: {url} — {exc}")
        except Exception as exc:
            logger.warning(f"[크롤러] 예기치 않은 오류: {url} — {exc}")
    return None



# books.toscrape.com
async def _get_books_category_async(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        detail_url: str,
) -> str:
    html = await _fetch(session, semaphore, detail_url)
    if not html:
        return "Books"
    try:
        soup = BeautifulSoup(html, "html.parser")
        breadcrumbs = soup.select("ul.breadcrumb li")
        if len(breadcrumbs) >= 3:
            return breadcrumbs[2].get_text(strip=True)
    except Exception:
        pass
    return "Books"


async def _crawl_books_async(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        max_pages: int = 5,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    base    = "https://books.toscrape.com/catalogue/"
    url     = f"{base}page-1.html"

    for page in range(1, max_pages + 1):
        logger.info(f"[books] 크롤링 중: {page}/{max_pages} 페이지")
        html = await _fetch(session, semaphore, url)
        if html is None:
            logger.warning(f"[books] 페이지 응답 없음, 중단: {page}페이지")
            break

        soup = BeautifulSoup(html, "html.parser")

        # 카테고리 파싱
        detail_urls = []
        article_data = []
        for idx, article in enumerate(soup.select("article.product_pod")):
            try:
                title       = article.select_one("h3 a")["title"]
                detail_path = article.select_one("h3 a")["href"].replace("../", "")
                price       = float(
                    article.select_one("p.price_color").text.strip()
                    .replace("Â£", "").replace("£", "")
                )
                in_stock    = 1 if "In stock" in article.select_one("p.availability").text else 0
                product_code = f"BK{str((page - 1) * 20 + idx + 1).zfill(3)}"
                detail_urls.append(base + detail_path)
                article_data.append((product_code, title, price, in_stock))
            except Exception as exc:
                logger.warning(f"[books] 상품 파싱 실패 (p={page}, i={idx}): {exc}")

        categories = await asyncio.gather(
            *[_get_books_category_async(session, semaphore, u) for u in detail_urls],
            return_exceptions=True,
        )

        for (product_code, title, price, in_stock), cat in zip(article_data, categories):
            records.append({
                "상품코드": product_code,
                "상품명":   title,
                "카테고리": cat if isinstance(cat, str) else "Books",
                "가격":     price,
                "재고여부": in_stock,
                "출처":     "books.toscrape.com",
            })

        next_btn = soup.select_one("li.next a")
        if next_btn:
            url = base + next_btn["href"]
        else:
            break
        await asyncio.sleep(_CRAWL_DELAY)

    df = pd.DataFrame(records)
    logger.info(f"[books] 크롤링 완료: {len(df)}개")
    return df



# webscraper.io
async def _crawl_webscraper_async(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        max_pages: int = 3,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    base_url = "https://webscraper.io/test-sites/e-commerce/allinone"

    html = await _fetch(session, semaphore, base_url)
    if html is None:
        logger.error("[webscraper] 메인 페이지 접근 실패")
        return pd.DataFrame()

    soup = BeautifulSoup(html, "html.parser")
    categories = [
        (a.get_text(strip=True), "https://webscraper.io" + a["href"])
        for a in soup.select(".sidebar-nav a")
        if a.get("href", "").startswith("/test-sites")
    ]
    if not categories:
        logger.warning("[webscraper] 카테고리 목록 비어 있음")
        return pd.DataFrame()

    for cat_name, cat_url in categories[:5]:
        for page in range(1, max_pages + 1):
            page_url = f"{cat_url}?page={page}" if page > 1 else cat_url
            html = await _fetch(session, semaphore, page_url)
            if html is None:
                break

            soup  = BeautifulSoup(html, "html.parser")
            items = soup.select(".thumbnail")
            if not items:
                break

            for item in items:
                try:
                    name  = item.select_one(".title")
                    price = item.select_one(".price")
                    if not name or not price:
                        continue
                    records.append({
                        "상품코드": f"WS{str(len(records) + 1).zfill(4)}",
                        "상품명":   name.get_text(strip=True),
                        "카테고리": cat_name,
                        "가격":     float(price.get_text(strip=True).replace("$", "")),
                        "재고여부": 1,
                        "출처":     "webscraper.io",
                    })
                except Exception as exc:
                    logger.warning(f"[webscraper] 상품 파싱 실패: {exc}")
            await asyncio.sleep(_CRAWL_DELAY)

    df = pd.DataFrame(records)
    logger.info(f"[webscraper] 크롤링 완료: {len(df)}개")
    return df



# scrapingcourse.com
async def _crawl_scrapingcourse_async(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        max_pages: int = 3,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    base_url = "https://www.scrapingcourse.com/ecommerce"

    for page in range(1, max_pages + 1):
        page_url = f"{base_url}/page/{page}/" if page > 1 else f"{base_url}/"
        logger.info(f"[scrapingcourse] 크롤링 중: {page}/{max_pages} 페이지")
        html = await _fetch(session, semaphore, page_url)
        if html is None:
            logger.warning(f"[scrapingcourse] 페이지 응답 없음, 중단: {page}페이지")
            break

        soup  = BeautifulSoup(html, "html.parser")
        items = soup.select("li.product")
        if not items:
            break

        for item in items:
            try:
                name   = item.select_one("h2.woocommerce-loop-product__title")
                price  = item.select_one("span.woocommerce-Price-amount")
                cat_el = item.select_one(".product-category")
                if not name or not price:
                    continue
                price_text = price.get_text(strip=True).replace("$", "").replace(",", "")
                records.append({
                    "상품코드": f"SC{str(len(records) + 1).zfill(4)}",
                    "상품명":   name.get_text(strip=True),
                    "카테고리": cat_el.get_text(strip=True) if cat_el else "General",
                    "가격":     float(price_text),
                    "재고여부": 1,
                    "출처":     "scrapingcourse.com",
                })
            except Exception as exc:
                logger.warning(f"[scrapingcourse] 상품 파싱 실패: {exc}")
        await asyncio.sleep(_CRAWL_DELAY)

    df = pd.DataFrame(records)
    logger.info(f"[scrapingcourse] 크롤링 완료: {len(df)}개")
    return df



# async 통합
async def crawl_all_sites_async(
        books_pages: int = 3,
        webscraper_pages: int = 2,
        scrapingcourse_pages: int = 2,
) -> pd.DataFrame:

    logger.info("===== 비동기 전체 사이트 크롤링 시작 =====")

    # 부하 방지
    sem_books  = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    sem_ws     = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    sem_sc     = asyncio.Semaphore(_SEMAPHORE_LIMIT)

    connector = aiohttp.TCPConnector(limit=10, force_close=True)
    headers   = {"User-Agent": "Mozilla/5.0 (SCM-Agent/3.0; research crawler)"}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        results = await asyncio.gather(
            _crawl_books_async(session, sem_books, books_pages),
            _crawl_webscraper_async(session, sem_ws, webscraper_pages),
            _crawl_scrapingcourse_async(session, sem_sc, scrapingcourse_pages),
            return_exceptions=True,
        )

    dfs = []
    site_names = ["books", "webscraper", "scrapingcourse"]
    for name, result in zip(site_names, results):
        if isinstance(result, Exception):
            logger.error(f"[{name}] 크롤링 실패 (건너뜀): {result}")
        elif isinstance(result, pd.DataFrame) and not result.empty:
            dfs.append(result)

    if not dfs:
        logger.warning("[크롤러] 모든 사이트 크롤링 실패 — 빈 결과 반환")
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"===== 비동기 크롤링 완료: 총 {len(combined)}개 상품 =====")
    return combined


# 동기화
def crawl_all_sites(
        books_pages: int = 3,
        webscraper_pages: int = 2,
        scrapingcourse_pages: int = 2,
) -> pd.DataFrame:

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    crawl_all_sites_async(books_pages, webscraper_pages, scrapingcourse_pages),
                )
                return future.result()
        else:
            return asyncio.run(
                crawl_all_sites_async(books_pages, webscraper_pages, scrapingcourse_pages)
            )
    except Exception as exc:
        logger.error(f"[크롤러] 동기화 실패: {exc}")
        return pd.DataFrame()



def crawl_books(max_pages: int = 5) -> pd.DataFrame:
    return asyncio.run(_crawl_books_single(max_pages))


async def _crawl_books_single(max_pages: int) -> pd.DataFrame:
    sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    async with aiohttp.ClientSession() as session:
        return await _crawl_books_async(session, sem, max_pages)
