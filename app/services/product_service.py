from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import ProductStatus

_STATUS_KO = {
    ProductStatus.ACTIVE:   "판매중",
    ProductStatus.INACTIVE: "단종/판매중지",
    ProductStatus.SAMPLE:   "샘플",
}

_STATUS_TRANSITIONS: dict[ProductStatus, list[ProductStatus]] = {
    ProductStatus.ACTIVE:   [ProductStatus.INACTIVE, ProductStatus.SAMPLE],
    ProductStatus.INACTIVE: [ProductStatus.ACTIVE],
    ProductStatus.SAMPLE:   [ProductStatus.ACTIVE],
}


class ProductService:

    @staticmethod
    def get_product(db: Session, code: str) -> dict:
        """상품 단건 조회"""
        from app.db.repository import get_product_by_code
        product = get_product_by_code(db, code.strip())
        if not product:
            raise ValueError(f"상품을 찾을 수 없습니다: {code}")
        return {
            "code":         product.code,
            "name":         product.name,
            "category":     product.category or "",
            "safety_stock": product.safety_stock,
            "status":       product.status.value,
            "status_label": _STATUS_KO.get(product.status, ""),
            "source":       product.source or "",
            "updated_at":   str(product.updated_at),
        }

    @staticmethod
    def change_status(db: Session, code: str, new_status: ProductStatus, username: str) -> dict:
        """상품 상태 변경 + 캐시 무효화"""
        from app.db.repository import get_product_by_code, update_product_status

        product = get_product_by_code(db, code)
        if not product:
            raise ValueError(f"상품을 찾을 수 없습니다: {code}")

        if product.status == new_status:
            return {
                "code":    code,
                "status":  new_status.value,
                "message": f"이미 '{_STATUS_KO[new_status]}' 상태입니다.",
                "changed": False,
            }

        allowed = _STATUS_TRANSITIONS.get(product.status, [])
        if new_status not in allowed:
            raise PermissionError(
                f"'{product.status.value}' → '{new_status.value}' 전환은 허용되지 않습니다. "
                f"가능한 전환: {[s.value for s in allowed]}"
            )

        prev_status = product.status
        updated = update_product_status(db, code, new_status)
        if not updated:
            raise RuntimeError("상품 상태 업데이트에 실패했습니다.")

        logger.info(
            f"[상품상태변경] code={code}, "
            f"{prev_status.value} → {new_status.value}, "
            f"by={username}"
        )

        # 분석 캐시 무효화
        ProductService._invalidate_analysis_cache()

        return {
            "code":        code,
            "prev_status": prev_status.value,
            "status":      new_status.value,
            "status_label": _STATUS_KO[new_status],
            "message":     f"상품 상태가 '{_STATUS_KO[new_status]}'으로 변경되었습니다.",
            "changed":     True,
        }

    @staticmethod
    def _invalidate_analysis_cache() -> None:
        """분석 캐시 무효화 (실패해도 무시)"""
        try:
            from app.cache.redis_client import get_redis
            redis = get_redis()
            for pattern in ("analysis:demand:*", "analysis:turnover:*", "analysis:abc:*"):
                keys = redis.keys(pattern)
                if keys:
                    redis.delete(*keys)
                    logger.debug(f"[상품상태변경] 분석 캐시 무효화: {pattern} ({len(keys)}건)")
        except Exception as cache_exc:
            logger.warning(f"[상품상태변경] 캐시 무효화 실패 (무시): {cache_exc}")