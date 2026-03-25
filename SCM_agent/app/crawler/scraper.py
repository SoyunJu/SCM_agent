
import requests
from bs4 import BeautifulSoup
import pandas as pd
from loguru import logger
import time

    # 크롤링 페이지
BASE_URL = "https://books.toscrape.com/catalogue/"
START_URL = "https://books.toscrape.com/catalogue/page-1.html"

# 상품코드 prefix (크롤링 식별용)
CRAWL_CODE_PREFIX = "CR"

def crawl_books(max_pages: int = 5) -> pd.DataFrame:

    records = []
    url = START_URL

    for page in range(1, max_pages + 1):
        logger.info(f"크롤링 중: {page}/{max_pages} 페이지")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"페이지 요청 실패 ({url}): {e}")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select("article.product_pod")

        for idx, article in enumerate(articles):
            try:
                # 상품명
                title = article.select_one("h3 a")["title"]

                # 상품 상세 URL
                detail_path = article.select_one("h3 a")["href"]
                detail_url = BASE_URL + detail_path.replace("../", "")

                # 가격
                price_text = article.select_one("p.price_color").text.strip()
                price = float(price_text.replace("Â£", "").replace("£", ""))

                # 재고 여부
                availability = article.select_one("p.availability").text.strip()
                in_stock = 1 if availability == "In stock" else 0

                # 상품코드 생성 (페이지번호 + 인덱스)
                product_code = f"{CRAWL_CODE_PREFIX}{str((page - 1) * 20 + idx + 1).zfill(3)}"

                # 카테고리 (Default)
                category = "Books"

                records.append({
                    "상품코드": product_code,
                    "상품명": title,
                    "카테고리": category,
                    "가격": price,
                    "재고여부": in_stock,
                })

            except Exception as e:
                logger.warning(f"상품 파싱 실패 (page={page}, idx={idx}): {e}")
                continue

        # 다음 페이지 URL
        next_btn = soup.select_one("li.next a")
        if next_btn:
            next_path = next_btn["href"]
            url = BASE_URL + next_path
        else:
            logger.info("마지막 페이지 도달")
            break

        # API 호출 간격 (과부하 방지)
        time.sleep(1)

    df = pd.DataFrame(records)
    logger.info(f"크롤링 완료: 총 {len(df)}개 상품")
    return df

    # 상세 페이지 크롤러 / TODO
def crawl_book_categories(max_pages: int = 5) -> pd.DataFrame:

    base_df = crawl_books(max_pages)
    logger.info("카테고리 상세 크롤링 시작 (느릴 수 있음)")

    categories = []
    for _, row in base_df.iterrows():
        try:
            code = row["상품코드"]
            # 상세 페이지 URL 재구성 생략, 기본 카테고리 유지
            categories.append("Books")
            time.sleep(0.3)
        except Exception as e:
            logger.warning(f"카테고리 조회 실패 ({code}): {e}")
            categories.append("Books")

    base_df["카테고리"] = categories
    return base_df