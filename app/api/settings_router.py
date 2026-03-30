from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/scm/settings", tags=["settings"])


@router.get("")
async def get_settings(
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SettingsService.get_all(db)


@router.put("")
async def save_settings(
        body: dict,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SettingsService.save(db, body, current_user.username)


from pydantic import BaseModel as PydanticBase

class CategoryLeadTimeBody(PydanticBase):
    category:       str
    lead_time_days: int

@router.get("/category-lead-times")
async def get_category_lead_times(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    from app.db.repository import get_category_lead_times
    rows = get_category_lead_times(db)
    return {"items": [{"category": r.category, "lead_time_days": r.lead_time_days} for r in rows]}

@router.put("/category-lead-times")
async def upsert_category_lead_time(
        body: CategoryLeadTimeBody,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    from app.db.repository import upsert_category_lead_time
    row = upsert_category_lead_time(db, body.category, body.lead_time_days)
    return {"category": row.category, "lead_time_days": row.lead_time_days}

@router.delete("/category-lead-times/{category}")
async def delete_category_lead_time(
        category: str,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    from app.db.repository import delete_category_lead_time
    ok = delete_category_lead_time(db, category)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(404, f"카테고리 '{category}' 리드타임 설정이 없습니다.")
    return {"deleted": category}