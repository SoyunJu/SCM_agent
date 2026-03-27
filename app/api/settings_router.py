from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from loguru import logger

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.db.repository import get_setting, upsert_setting
from app.api.order_router import router as order_router



router = APIRouter(prefix="/scm/settings", tags=["settings"])

# 전체 설정 목록과 기본값/설명
DEFAULT_SETTINGS: dict[str, tuple[str, str]] = {
    "SAFETY_STOCK_DAYS":      ("7",   "안전재고 = 일평균판매량 × N일"),
    "SAFETY_STOCK_DEFAULT":   ("10",  "판매 데이터 없을 때 기본 안전재고"),
    "CHAT_HISTORY_DAYS":      ("7",   "챗봇 히스토리 보관/로드 일수"),
    "LOW_STOCK_CRITICAL_DAYS":("1",   "긴급 경보 소진예상일 기준 (이하)"),
    "LOW_STOCK_HIGH_DAYS":    ("3",   "높음 경보 소진예상일 기준 (이하)"),
    "LOW_STOCK_MEDIUM_DAYS":  ("7",   "보통 경보 소진예상일 기준 (이하)"),
    "SALES_SURGE_THRESHOLD":  ("50",  "판매 급등 기준 (%)"),
    "SALES_DROP_THRESHOLD":   ("50",  "판매 급락 기준 (%)"),
    "SHEETS_CACHE_TTL":       ("300", "Google Sheets 캐시 유효 시간 (초)"),
    "ALERT_CHANNEL":      ("slack", "알림 채널 (slack | email | both)"),
    "ALERT_MIN_SEVERITY": ("high",  "알림 최소 심각도 (low | medium | high | critical)"),
    "AUTO_ORDER_MIN_SEVERITY":    ("high",     "자동발주 에이전트 실행 최소 심각도 (low | medium | high | critical)"),
}


@router.get("")
async def get_settings(
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):

    items = []
    for key, (default_val, description) in DEFAULT_SETTINGS.items():
        current_val = get_setting(db, key, default_val)
        items.append({
            "key":         key,
            "value":       current_val,
            "default":     default_val,
            "description": description,
        })
    return {"items": items}


@router.put("")
async def save_settings(
        body: dict,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):

    saved = 0
    for key, value in body.items():
        if key in DEFAULT_SETTINGS:
            _, description = DEFAULT_SETTINGS[key]
            upsert_setting(db, key, str(value), description)
            saved += 1
    logger.info(f"시스템 설정 저장: {saved}개, user={current_user.username}")
    return {"saved": saved}
