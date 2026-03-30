from fastapi.responses import StreamingResponse
from typing import Annotated
from loguru import logger
import asyncio
import json

from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, TokenData
from fastapi import APIRouter, Depends, Query
from jose import JWTError, jwt
from app.config import settings

router = APIRouter(prefix="/scm/alerts", tags=["alerts"])

_alert_queues: list[asyncio.Queue] = []
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop
    logger.info(f"SSE 메인 루프 등록 완료: {loop}")


async def broadcast_alert(alert: dict) -> None:
    if "severity" in alert:
        alert = {**alert, "severity": str(alert["severity"]).upper()}

    if not _alert_queues:
        logger.warning("SSE 구독자 없음 — 브로드캐스트 스킵")
        return

    for q in _alert_queues:
        await q.put(alert)
    logger.info(f"SSE 브로드캐스트 완료: {len(_alert_queues)}명 → {alert.get('type')} / {alert.get('severity')}")


def sync_broadcast_alert(alert: dict) -> None:
    if _main_loop is None:
        logger.warning("SSE 메인 루프 미등록 — 브로드캐스트 스킵")
        return
    if not _main_loop.is_running():
        logger.warning("SSE 메인 루프 미실행 — 브로드캐스트 스킵")
        return
    future = asyncio.run_coroutine_threadsafe(broadcast_alert(alert), _main_loop)
    try:
        future.result(timeout=5)   # 5초 내 완료 확인
    except Exception as e:
        logger.error(f"SSE 브로드캐스트 실패: {e}")


@router.get("/stream")
async def alert_stream(
        token: str = Query(..., description="JWT 토큰"),
):
    # 토큰 검증
    try:
        payload  = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if not username:
            raise ValueError("Invalid token")
    except (JWTError, ValueError):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    queue: asyncio.Queue = asyncio.Queue()
    _alert_queues.append(queue)
    logger.info(f"SSE 구독 연결: user={username}, 총 구독자={len(_alert_queues)}")

    async def event_generator():
        try:
            # 연결 확인 메시지
            yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE 연결 성공', 'user': username})}\n\n"
            while True:
                try:
                    alert = await asyncio.wait_for(queue.get(), timeout=25)
                    payload_str = json.dumps(alert, ensure_ascii=False)
                    logger.info(f"SSE 전송: user={username}, data={payload_str[:80]}")
                    yield f"data: {payload_str}\n\n"
                except asyncio.TimeoutError:
                    # keepalive — 브라우저 연결 유지 (30초마다)
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            logger.info(f"SSE 연결 종료: user={username}")
        finally:
            if queue in _alert_queues:
                _alert_queues.remove(queue)
            logger.info(f"SSE 구독 해제: user={username}, 남은 구독자={len(_alert_queues)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",        # nginx 버퍼링 비활성화
            "Connection":         "keep-alive",
            "Transfer-Encoding":  "chunked",
        },
    )


@router.get("/unread-count")
async def get_unread_count(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    try:
        from app.db.connection import SessionLocal
        from app.db.repository import get_anomaly_logs
        from app.utils.severity import norm

        db = SessionLocal()
        try:
            result  = get_anomaly_logs(db, is_resolved=False, page=1, page_size=500)
            records = result["items"]
        finally:
            db.close()

        critical = sum(1 for r in records if norm(r.severity) == "CRITICAL")
        high     = sum(1 for r in records if norm(r.severity) == "HIGH")
        return {"critical": critical, "high": high, "total": critical + high}
    except Exception as e:
        logger.error(f"미읽음 카운트 조회 실패: {e}")
        return {"critical": 0, "high": 0, "total": 0, "error": str(e)}


# SSE 수동 테스트용 엔드포인트 (개발용)
@router.post("/test-broadcast")
async def test_broadcast(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    await broadcast_alert({
        "type":         "critical_anomaly",
        "severity":     "CRITICAL",
        "product_code": "TEST001",
        "product_name": "SSE 테스트 상품",
        "anomaly_type": "LOW_STOCK",
        "message":      "[테스트] SSE 알림이 정상 동작합니다.",
    })
    return {"status": "broadcast sent", "subscribers": len(_alert_queues)}


@router.get("/history")
async def get_alert_history(
        limit:  int  = 50,
        unread: bool = False,
        current_user: Annotated[TokenData, Depends(get_current_user)] = None,
        db: Session = Depends(get_db),
):
    """알림 이력 조회"""
    from app.db.repository import get_alert_history
    rows = get_alert_history(db, limit=limit, unread=unread)
    return {
        "items": [
            {
                "id":           r.id,
                "alert_type":   r.alert_type,
                "channel":      r.channel,
                "severity":     r.severity,
                "product_code": r.product_code,
                "product_name": r.product_name,
                "message":      r.message,
                "is_read":      r.is_read,
                "created_at":   r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.patch("/history/read-all")
async def mark_all_read(
        current_user: Annotated[TokenData, Depends(get_current_user)] = None,
        db: Session = Depends(get_db),
):
    """알림 이력 전체 읽음 처리"""
    from app.db.repository import mark_alerts_read
    count = mark_alerts_read(db)
    return {"marked": count}