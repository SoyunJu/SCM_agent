
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from loguru import logger

from app.config import settings

router = APIRouter(prefix="/scm/auth", tags=["auth"])

# ### config ######################
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/scm/auth/login")


# 스키마
class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int     # 초 단위


class TokenData(BaseModel):
    username: str


# Utils
def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

    # JWT token
def _create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _authenticate_user(username: str, password: str) -> bool:
    if username != settings.admin_username:
        return False
    return password == settings.admin_password      # TODO : 단순 비교 말고 해시 비교


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효하지 않은 인증 정보입니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return TokenData(username=username)
    except JWTError:
        logger.warning("JWT 토큰 검증 실패")
        raise credentials_exception


@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):

    if not _authenticate_user(form_data.username, form_data.password):
        logger.warning(f"로그인 실패: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = _create_access_token(data={"sub": form_data.username})
    logger.info(f"로그인 성공: {form_data.username}")
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: Annotated[TokenData, Depends(get_current_user)]):

    access_token = _create_access_token(data={"sub": current_user.username})
    logger.info(f"토큰 갱신: {current_user.username}")
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get("/me")
async def get_me(current_user: Annotated[TokenData, Depends(get_current_user)]):
    return {"username": current_user.username}