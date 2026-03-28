from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import TokenData, get_current_user, require_admin
from app.db.connection import get_db
from app.db.models import ProductStatus

router = APIRouter(prefix="/scm/products", tags=["products"])

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


class StatusUpdateRequest(BaseModel):
    status: Literal["active", "inactive", "sample"]


@router.get("/{code}")
async def get_product(
        code: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    try:
        from app.db.repository import get_product_by_code
        product = get_product_by_code(db, code.strip())
        if not product:
            raise HTTPException(status_code=404, detail=f"상품을 찾을 수 없습니다: {code}")

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
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[상품조회] 실패: code={code}, error={exc}")
        raise HTTPException(status_code=500, detail=f"상품 조회 중 오류 발생: {exc}")



@router.patch("/{code}/status")
async def update_product_status(
        code: str,
        body: StatusUpdateRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    try:
        from app.db.repository import get_product_by_code, update_product_status

        code = code.strip()
        product = get_product_by_code(db, code)
        if not product:
            raise HTTPException(status_code=404, detail=f"상품을 찾을 수 없습니다: {code}")

        new_status = ProductStatus(body.status)

        if product.status == new_status:
            return {
                "code":    code,
                "status":  new_status.value,
                "message": f"이미 '{_STATUS_KO[new_status]}' 상태입니다.",
                "changed": False,
            }

        allowed = _STATUS_TRANSITIONS.get(product.status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{product.status.value}' → '{new_status.value}' 전환은 허용되지 않습니다. "
                    f"가능한 전환: {[s.value for s in allowed]}"
                ),
            )

        prev_status = product.status
        updated = update_product_status(db, code, new_status)
        if not updated:
            raise HTTPException(status_code=500, detail="상품 상태 업데이트에 실패했습니다.")

        logger.info(
            f"[상품상태변경] code={code}, "
            f"{prev_status.value} → {new_status.value}, "
            f"by={current_user.username}"
        )

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

        return {
            "code":       code,
            "prev_status": prev_status.value,
            "status":     new_status.value,
            "status_label": _STATUS_KO[new_status],
            "message":    f"상품 상태가 '{_STATUS_KO[new_status]}'으로 변경되었습니다.",
            "changed":    True,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[상품상태변경] 실패: code={code}, body={body}, error={exc}")
        raise HTTPException(status_code=500, detail=f"상품 상태 변경 중 오류 발생: {exc}")
