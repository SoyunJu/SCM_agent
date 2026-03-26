"""
주문 데이터 수집/생성기.
Mock 발주 데이터 생성.
"""

import random
import requests
from datetime import date, timedelta
from loguru import logger


STATUSES  = ["발주완료", "입고중", "입고완료", "반품"]
WEIGHTS   = [0.30, 0.40, 0.25, 0.05]


def _fetch_fakestoreapi_count() -> int:

    try:
        res = requests.get("https://fakestoreapi.com/carts", timeout=5)
        return len(res.json())
    except Exception:
        return 20


def generate_orders(product_codes: list[str], count: int | None = None) -> list[dict]:

    if not product_codes:
        logger.warning("상품코드 없음 - 주문 데이터 생성 스킵")
        return []

    if count is None:
        count = _fetch_fakestoreapi_count()
        logger.info(f"FakeStoreAPI 기준 주문 {count}건 생성")

    today = date.today()
    orders = []

    for i in range(count):
        product_code = random.choice(product_codes)
        order_date   = today - timedelta(days=random.randint(0, 60))
        lead_days    = random.randint(3, 21)
        delivery_date = order_date + timedelta(days=lead_days)
        status       = random.choices(STATUSES, weights=WEIGHTS)[0]

        if status == "입고완료" and delivery_date > today:
            delivery_date = today - timedelta(days=random.randint(1, 5))

        orders.append({
            "주문코드":   f"ORD{order_date.strftime('%Y%m')}{i + 1:04d}",
            "상품코드":   product_code,
            "상품명":     "",          # writer에서 master join으로 채움
            "발주수량":   random.randint(5, 200),
            "발주일":     order_date.strftime("%Y-%m-%d"),
            "예정납기일": delivery_date.strftime("%Y-%m-%d"),
            "상태":       status,
        })

    logger.info(f"주문 Mock 데이터 생성 완료: {len(orders)}건")
    return orders
