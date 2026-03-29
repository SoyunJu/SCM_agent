from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, TokenData
from app.db.connection import get_db
from app.db.models import AdminUser
from app.db.repository import get_admin_user_by_username
from app.services.admin_service import AdminService

router = APIRouter(prefix="/scm/admin", tags=["admin"])


# --- 권한 체크  ---
def require_superadmin(current_user: Annotated[TokenData, Depends(get_current_user)]) -> TokenData:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="슈퍼어드민 권한이 필요합니다.")
    return current_user


# --- Pydantic 스키마 ---
class AdminUserCreate(BaseModel):
    username:       str
    password:       str
    role:           str           = "admin"
    slack_user_id:  Optional[str] = None
    email:          Optional[str] = None


class AdminUserUpdate(BaseModel):
    role:           Optional[str]  = None
    slack_user_id:  Optional[str]  = None
    email:          Optional[str]  = None
    is_active:      Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password:     str


class MyProfileUpdate(BaseModel):
    email:         Optional[str] = None
    slack_user_id: Optional[str] = None


# --- 엔드포인트 ---

@router.get("/users")
async def get_admin_users(
        _: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    return AdminService.list_users(db)


@router.post("/users", status_code=201)
async def add_admin_user(
        body: AdminUserCreate,
        _: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    # 중복 확인 (비활성 포함) — DB 직접 조회는 라우터에서 허용 (단순 존재 검증)
    from app.db.models import AdminUser as AdminUserModel
    if db.query(AdminUserModel).filter(AdminUserModel.username == body.username).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명입니다.")
    try:
        return AdminService.create_user(
            db, body.username, body.password, body.role,
            body.slack_user_id, body.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{user_id}")
async def edit_admin_user(
        user_id: int,
        body: AdminUserUpdate,
        _: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    try:
        return AdminService.update_user(
            db, user_id, body.role, body.slack_user_id, body.email, body.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/users/{user_id}", status_code=204)
async def remove_admin_user(
        user_id: int,
        current_user: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    try:
        AdminService.delete_user(db, user_id, current_user.username)
    except PermissionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/me")
async def get_my_profile(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    try:
        return AdminService.get_me(db, current_user.username)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/me/profile")
async def update_my_profile(
        body: MyProfileUpdate,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    user = get_admin_user_by_username(db, current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return AdminService.update_my_profile(
        db, user.id, body.email, body.slack_user_id, current_user.username,
    )


@router.put("/me/password")
async def change_my_password(
        body: PasswordChange,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    try:
        return AdminService.change_password(
            db, current_user.username, body.current_password, body.new_password,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))