
import requests
from bs4 import BeautifulSoup
import pandas as pd
from loguru import logger
import time

# 크롤링 사이트
SITES = {
    "books":    "https://books.toscrape.com",
    "webscraper": "https://webscraper.io/test-sites/e-commerce/allinone",
    "scrapingcourse": "https://www.scrapingcourse.com/ecommerce",
}

CRAWL_DELAY = 1   # 사이트 부하 방지 딜레이(초)


#  books.toscrape.com

def _crawl_books(max_pages: int = 5) -> pd.DataFrame:

    records = []
    url = "https://books.toscrape.com/catalogue/page-1.html"
    base = "https://books.toscrape.com/catalogue/"

    for page in range(1, max_pages + 1):
        logger.info(f"[books] 크롤링 중: {page}/{max_pages} 페이지")
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"[books] 페이지 요청 실패: {e}")
            break

        soup = BeautifulSoup(res.text, "html.parser")

        for idx, article in enumerate(soup.select("article.product_pod")):
            try:
                title       = article.select_one("h3 a")["title"]
                detail_path = article.select_one("h3 a")["href"].replace("../", "")
                detail_url  = base + detail_path
                price       = float(
                    article.select_one("p.price_color").text.strip()
                    .replace("Â£", "").replace("£", "")
                )
                in_stock    = 1 if "In stock" in article.select_one("p.availability").text else 0
                product_code = f"BK{str((page-1)*20+idx+1).zfill(3)}"

                # 상세 페이지에서 카테고리 파싱
                category = _get_books_category(detail_url)
                time.sleep(0.3)

                records.append({
                    "상품코드": product_code,
                    "상품명":   title,
                    "카테고리": category,
                    "가격":     price,
                    "재고여부": in_stock,
                    "출처":     "books.toscrape.com",
                })
            except Exception as e:
                logger.warning(f"[books] 상품 파싱 실패 (p={page}, i={idx}): {e}")

        next_btn = soup.select_one("li.next a")
        if next_btn:
            url = base + next_btn["href"]
        else:
            break
        time.sleep(CRAWL_DELAY)

    df = pd.DataFrame(records)
    logger.info(f"[books] 크롤링 완료: {len(df)}개")
    return df


def _get_books_category(detail_url: str) -> str:

    try:
        res  = requests.get(detail_url, timeout=8)
        soup = BeautifulSoup(res.text, "html.parser")
        # breadcrumb: Home > 카테고리 > 상품명
        breadcrumbs = soup.select("ul.breadcrumb li")
        if len(breadcrumbs) >= 3:
            return breadcrumbs[2].get_text(strip=True)
        return "Books"
    except Exception:
        return "Books"


#  webscraper.io 이커머스

def _crawl_webscraper(max_pages: int = 3) -> pd.DataFrame:

    records = []
    base_url = "https://webscraper.io/test-sites/e-commerce/allinone"

    # 카테고리 목록 수집
    try:
        res  = requests.get(base_url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        categories = [
            (a.get_text(strip=True), base_url + a["href"].replace("/test-sites/e-commerce/allinone", ""))
            for a in soup.select("a.category-link")
        ]
        if not categories:
            # 사이드바 방식
            categories = [
                (a.get_text(strip=True), "https://webscraper.io" + a["href"])
                for a in soup.select(".sidebar-nav a")
                if a.get("href", "").startswith("/test-sites")
            ]
    except Exception as e:
        logger.error(f"[webscraper] 카테고리 수집 실패: {e}")
        return pd.DataFrame()

    for cat_name, cat_url in categories[:5]:   # 최대 5개 카테고리
        for page in range(1, max_pages + 1):
            page_url = f"{cat_url}?page={page}" if page > 1 else cat_url
            try:
                res  = requests.get(page_url, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")
                items = soup.select(".thumbnail")
                if not items:
                    break

                for idx, item in enumerate(items):
                    try:
                        name  = item.select_one(".title")
                        price = item.select_one(".price")
                        if not name or not price:
                            continue
                        product_code = f"WS{str(len(records)+1).zfill(4)}"
                        records.append({
                            "상품코드": product_code,
                            "상품명":   name.get_text(strip=True),
                            "카테고리": cat_name,
                            "가격":     float(price.get_text(strip=True).replace("$", "")),
                            "재고여부": 1,
                            "출처":     "webscraper.io",
                        })
                    except Exception as e:
                        logger.warning(f"[webscraper] 상품 파싱 실패: {e}")
                time.sleep(CRAWL_DELAY)
            except Exception as e:
                logger.error(f"[webscraper] 페이지 요청 실패: {e}")
                break

    df = pd.DataFrame(records)
    logger.info(f"[webscraper] 크롤링 완료: {len(df)}개")
    return df


#  scrapingcourse.com

def _crawl_scrapingcourse(max_pages: int = 3) -> pd.DataFrame:

    records = []
    base_url = "https://www.scrapingcourse.com/ecommerce"

    for page in range(1, max_pages + 1):
        page_url = f"{base_url}/page/{page}/" if page > 1 else base_url + "/"
        logger.info(f"[scrapingcourse] 크롤링 중: {page}/{max_pages} 페이지")
        try:
            res  = requests.get(page_url, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            items = soup.select("li.product")
            if not items:
                break

            for idx, item in enumerate(items):
                try:
                    name  = item.select_one("h2.woocommerce-loop-product__title")
                    price = item.select_one("span.woocommerce-Price-amount")
                    cat_el = item.select_one(".product-category")
                    if not name or not price:
                        continue

                    price_text = price.get_text(strip=True).replace("$", "").replace(",", "")
                    product_code = f"SC{str(len(records)+1).zfill(4)}"
                    records.append({
                        "상품코드": product_code,
                        "상품명":   name.get_text(strip=True),
                        "카테고리": cat_el.get_text(strip=True) if cat_el else "General",
                        "가격":     float(price_text),
                        "재고여부": 1,
                        "출처":     "scrapingcourse.com",
                    })
                except Exception as e:
                    logger.warning(f"[scrapingcourse] 상품 파싱 실패: {e}")

            time.sleep(CRAWL_DELAY)
        except requests.RequestException as e:
            logger.error(f"[scrapingcourse] 페이지 요청 실패: {e}")
            break

    df = pd.DataFrame(records)
    logger.info(f"[scrapingcourse] 크롤링 완료: {len(df)}개")
    return df


#  통합 크롤링

def crawl_books(max_pages: int = 5) -> pd.DataFrame:
    return _crawl_books(max_pages)


def crawl_all_sites(
        books_pages: int = 3,
        webscraper_pages: int = 2,
        scrapingcourse_pages: int = 2,
) -> pd.DataFrame:

    logger.info("===== 전체 사이트 크롤링 시작 =====")
    dfs = []

    df_books = _crawl_books(books_pages)
    if not df_books.empty:
        dfs.append(df_books)

    df_ws = _crawl_webscraper(webscraper_pages)
    if not df_ws.empty:
        dfs.append(df_ws)

    df_sc = _crawl_scrapingcourse(scrapingcourse_pages)
    if not df_sc.empty:
        dfs.append(df_sc)

    if not dfs:
        logger.warning("크롤링 결과 없음")
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"===== 전체 크롤링 완료: 총 {len(combined)}개 상품 =====")
    return combined