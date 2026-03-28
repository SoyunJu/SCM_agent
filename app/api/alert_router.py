from fastapi.responses import StreamingResponse
from typing import Annotated
from loguru import logger
import asyncio
import json

from app.api.auth_router import get_current_user, TokenData
from fastapi import APIRouter, Depends, Query
from jose import JWTError, jwt
from app.config import settings

router = APIRouter(prefix="/scm/alerts", tags=["alerts"])

_alert_queues: list[asyncio.Queue] = []


async def broadcast_alert(alert: dict) -> None:

    for q in _alert_queues:
        await q.put(alert)
    logger.info(f"알림 브로드캐스트: {alert.get('type')} - {alert.get('message')}")


@router.get("/stream")
async def alert_stream(
        token: str = Query(..., description="JWT 토큰"),
):

    # 토큰 검증
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if not username:
            raise ValueError("Invalid token")
    except (JWTError, ValueError):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    queue: asyncio.Queue = asyncio.Queue()
    _alert_queues.append(queue)
    logger.info(f"SSE 구독 연결: user={username}")

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE 연결 성공'})}\n\n"
            while True:
                try:
                    alert = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(alert, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _alert_queues:
                _alert_queues.remove(queue)
            logger.info(f"SSE 구독 해제: user={username}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/unread-count")
async def get_unread_count(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):

    try:
        from app.db.connection import SessionLocal
        from app.db.repository import get_anomaly_logs

        db = SessionLocal()
        try:
            result = get_anomaly_logs(db, is_resolved=False, page=1, page_size=200)
            records = result["items"]
        finally:
            db.close()

        critical = sum(1 for r in records if r.severity.value == "CRITICAL")
        high     = sum(1 for r in records if r.severity.value == "HIGH")
        return {"critical": critical, "high": high, "total": critical + high}
    except Exception as e:
        return {"critical": 0, "high": 0, "total": 0, "error": str(e)}


_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def sync_broadcast_alert(alert: dict) -> None:
    if _main_loop and _main_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_alert(alert), _main_loop)
    else:
        logger.warning("메인 루프 미등록 또는 미실행 — SSE 알림 스킵")