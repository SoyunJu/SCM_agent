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