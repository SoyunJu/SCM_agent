import hashlib

from loguru import logger
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.models import AdminRole
from app.db.repository import (
    list_admin_users, create_admin_user, update_admin_user, delete_admin_user,
    get_admin_user_by_username,
)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _parse_role(role_str: str) -> AdminRole:
    """role 문자열 → AdminRole Enum 변환. 실패 시 ValueError"""
    try:
        return AdminRole(role_str.upper())
    except ValueError:
        raise ValueError(f"유효하지 않은 역할입니다: {role_str}")


def _hash_password(plain: str) -> str:
    """sha256 → bcrypt 이중 해싱"""
    sha256_pw = hashlib.sha256(plain.encode()).hexdigest()
    return _pwd_context.hash(sha256_pw)


def _verify_password(plain: str, hashed: str) -> bool:
    """입력된 평문 비밀번호와 저장된 해시 비교"""
    sha256_pw = hashlib.sha256(plain.encode()).hexdigest()
    return _pwd_context.verify(sha256_pw, hashed)


def _to_out(user) -> dict:
    return {
        "id":            user.id,
        "username":      user.username,
        "role":          user.role.value,
        "slack_user_id": user.slack_user_id,
        "email":         user.email,
        "is_active":     user.is_active,
        "created_at":    user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "last_login_at": user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_at else None,
    }


class AdminService:

    @staticmethod
    def list_users(db: Session) -> dict:
        users = list_admin_users(db)
        return {"items": [_to_out(u) for u in users]}

    @staticmethod
    def create_user(db: Session, username: str, password: str, role: str,
                    slack_user_id: str | None, email: str | None) -> dict:
        role_enum = _parse_role(role)
        user = create_admin_user(
            db,
            username=username,
            hashed_password=_hash_password(password),
            role=role_enum,
            slack_user_id=slack_user_id,
            email=email,
        )
        logger.info(f"관리자 추가: {user.username} ({user.role.value})")
        return _to_out(user)

    @staticmethod
    def update_user(db: Session, user_id: int, role: str | None,
                    slack_user_id: str | None, email: str | None,
                    is_active: bool | None) -> dict:
        role_enum = _parse_role(role) if role is not None else None
        user = update_admin_user(
            db, user_id,
            role=role_enum,
            slack_user_id=slack_user_id,
            email=email,
            is_active=is_active,
        )
        if not user:
            raise LookupError("사용자를 찾을 수 없습니다.")
        logger.info(f"관리자 수정: {user.username}")
        return _to_out(user)

    @staticmethod
    def delete_user(db: Session, user_id: int, requester_username: str) -> None:
        me = get_admin_user_by_username(db, requester_username)
        if me and me.id == user_id:
            raise PermissionError("자기 자신은 삭제할 수 없습니다.")
        if not delete_admin_user(db, user_id):
            raise LookupError("사용자를 찾을 수 없습니다.")
        logger.info(f"관리자 삭제: id={user_id}")

    @staticmethod
    def get_me(db: Session, username: str) -> dict:
        user = get_admin_user_by_username(db, username)
        if not user:
            raise LookupError("사용자를 찾을 수 없습니다.")
        return _to_out(user)

    @staticmethod
    def update_my_profile(db: Session, user_id: int, email: str | None,
                          slack_user_id: str | None, username: str) -> dict:
        update_admin_user(db, user_id, email=email, slack_user_id=slack_user_id)
        logger.info(f"프로필 수정: {username}")
        return {"message": "프로필이 수정되었습니다."}

    @staticmethod
    def change_password(db: Session, username: str,
                        current_password: str, new_password: str) -> dict:
        """현재 비밀번호 검증 후 새 비밀번호로 변경"""
        user = get_admin_user_by_username(db, username)
        if not user:
            raise LookupError("사용자를 찾을 수 없습니다.")
        if not _verify_password(current_password, user.hashed_password):
            raise ValueError("현재 비밀번호가 올바르지 않습니다.")
        update_admin_user(db, user.id, hashed_password=_hash_password(new_password))
        logger.info(f"비밀번호 변경: {username}")
        return {"message": "비밀번호가 변경되었습니다."}