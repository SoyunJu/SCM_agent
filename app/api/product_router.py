from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import TokenData, get_current_user, require_admin
from app.db.connection import get_db
from app.db.models import ProductStatus
from app.services.product_service import ProductService

router = APIRouter(prefix="/scm/products", tags=["products"])


class StatusUpdateRequest(BaseModel):
    status: Literal["active", "inactive", "sample"]


@router.get("/{code}")
async def get_product(
        code: str,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    try:
        return ProductService.get_product(db, code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"상품 조회 중 오류 발생: {exc}")


@router.patch("/{code}/status")
async def update_product_status(
        code: str,
        body: StatusUpdateRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    try:
        new_status = ProductStatus(body.status)
        return ProductService.change_status(db, code.strip(), new_status, current_user.username)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"상품 상태 변경 중 오류 발생: {exc}")




class LeadTimeUpdateRequest(BaseModel):
    lead_time_days: int | None = None

@router.patch("/{code}/lead-time")
async def update_lead_time(
        code: str,
        body: LeadTimeUpdateRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    try:
        return ProductService.update_lead_time(db, code.strip(), body.lead_time_days, current_user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"리드타임 설정 중 오류: {exc}")