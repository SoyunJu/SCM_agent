
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from loguru import logger

from app.api.auth_router import get_current_user, TokenData
from app.db.connection import get_db
from app.db.models import AdminRole, AdminUser
from app.db.repository import (
    list_admin_users, create_admin_user, update_admin_user,
    delete_admin_user, get_admin_user_by_username,
)

router     = APIRouter(prefix="/scm/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- 권한 체크 dependency ---
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


class AdminUserOut(BaseModel):
    id:            int
    username:      str
    role:          str
    slack_user_id: Optional[str]
    email:         Optional[str]
    is_active:     bool
    created_at:    str
    last_login_at: Optional[str]


def _to_out(user: AdminUser) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        role=user.role.value,
        slack_user_id=user.slack_user_id,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        last_login_at=user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_at else None,
    )


# --- 엔드포인트 ---

@router.get("/users")
async def get_admin_users(
        _: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    users = list_admin_users(db)
    return {"items": [_to_out(u) for u in users]}


@router.post("/users", status_code=201)
async def add_admin_user(
        body: AdminUserCreate,
        _: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    # 중복 확인 (비활성 포함)
    if db.query(AdminUser).filter(AdminUser.username == body.username).first():
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명입니다.")
    try:
        role_enum = AdminRole(body.role.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 역할입니다: {body.role}")

    user = create_admin_user(
        db,
        username=body.username,
        hashed_password=pwd_context.hash(body.password),
        role=role_enum,
        slack_user_id=body.slack_user_id,
        email=body.email,
    )
    logger.info(f"관리자 추가: {user.username} ({user.role.value})")
    return _to_out(user)


@router.put("/users/{user_id}")
async def edit_admin_user(
        user_id: int,
        body: AdminUserUpdate,
        _: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    role_enum = None
    if body.role is not None:
        try:
            role_enum = AdminRole(body.role.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 역할입니다: {body.role}")

    user = update_admin_user(
        db, user_id,
        role=role_enum,
        slack_user_id=body.slack_user_id,
        email=body.email,
        is_active=body.is_active,
    )
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    logger.info(f"관리자 수정: {user.username}")
    return _to_out(user)


@router.delete("/users/{user_id}", status_code=204)
async def remove_admin_user(
        user_id: int,
        current_user: Annotated[TokenData, Depends(require_superadmin)],
        db: Session = Depends(get_db),
):
    me = get_admin_user_by_username(db, current_user.username)
    if me and me.id == user_id:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없습니다.")
    if not delete_admin_user(db, user_id):
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    logger.info(f"관리자 삭제: id={user_id}")


@router.get("/me")
async def get_my_profile(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    user = get_admin_user_by_username(db, current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return _to_out(user)


@router.put("/me/profile")
async def update_my_profile(
        body: MyProfileUpdate,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    user = get_admin_user_by_username(db, current_user.username)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    update_admin_user(db, user.id, email=body.email, slack_user_id=body.slack_user_id)
    logger.info(f"프로필 수정: {current_user.username}")
    return {"message": "프로필이 수정되었습니다."}


@router.put("/me/password")
async def change_my_password(
        body: PasswordChange,
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    user = get_admin_user_by_username(db, current_user.username)
    if not user or not pwd_context.verify(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
    update_admin_user(db, user.id, hashed_password=pwd_context.hash(body.new_password))
    logger.info(f"비밀번호 변경: {current_user.username}")
    return {"message": "비밀번호가 변경되었습니다."}
