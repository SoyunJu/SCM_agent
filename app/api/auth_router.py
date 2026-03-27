
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.db.connection import get_db
from app.db.repository import get_admin_user_by_username, update_last_login


router = APIRouter(prefix="/scm/auth", tags=["auth"])

# ### config ######################
pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/scm/auth/login")


# 스키마
class Token(BaseModel):
    access_token: str
    token_type:   str
    expires_in:   int     # 초 단위


class TokenData(BaseModel):
    username: str
    role:     str = "admin"   # JWT payload에서 파싱


# Utils
def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


# JWT token
def _create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _authenticate_user(db: Session, username: str, password: str):
    user = get_admin_user_by_username(db, username)
    if not user:
        return None
    if not pwd_context.verify(password, user.hashed_password):
        return None
    return user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 인증 정보입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        role: str = payload.get("role", "admin")
        return TokenData(username=username, role=role)
    except JWTError:
        logger.warning("JWT 토큰 검증 실패")
        raise credentials_exception


@router.post("/login", response_model=Token)
async def login(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: Session = Depends(get_db),
):
    user = _authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"로그인 실패: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = _create_access_token(data={"sub": user.username, "role": user.role.value})
    update_last_login(db, user.id)
    logger.info(f"로그인 성공: {user.username} ({user.role.value})")
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    user = get_admin_user_by_username(db, current_user.username)
    role = user.role.value if user else current_user.role
    access_token = _create_access_token(data={"sub": current_user.username, "role": role})
    logger.info(f"토큰 갱신: {current_user.username}")
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get("/me")
async def get_me(current_user: Annotated[TokenData, Depends(get_current_user)]):
    return {"username": current_user.username, "role": current_user.role}



def require_admin(
        current_user: Annotated[TokenData, Depends(get_current_user)],
) -> TokenData:
    if current_user.role == "readonly":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="읽기 전용 계정은 이 작업을 수행할 수 없습니다.",
        )
    return current_user