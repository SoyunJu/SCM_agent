
import re
import hmac
import hashlib
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from loguru import logger
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, TokenData
from app.config import settings
from app.notifier.slack_notifier import get_slack_client
from app.ai.agent import run_agent
from app.db.connection import get_db
from app.db.repository import get_chat_history_recent

router = APIRouter(prefix="/scm/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    user_id: str = "api_user"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


def _verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if abs(time.time() - int(timestamp)) > 300:
        logger.warning("Slack 서명 검증 실패: 타임스탬프 만료")
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        base.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _run_agent_and_reply(
        user_message: str,
        user_id: str,
        channel_id: str,
        thread_ts: str,
) -> None:
    try:
        reply = run_agent(
            message=user_message,
            session_id=thread_ts,
            user_id=user_id,
        )
        get_slack_client().chat_postMessage(
            channel=channel_id,
            text=reply,
            thread_ts=thread_ts,
        )
        logger.info(f"Slack Agent 답장 완료: channel={channel_id}")
    except Exception as e:
        logger.error(f"Slack Agent 실행 오류: {e}")


@router.get("/history")
async def get_history(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        session_id: str,
        days: int = 7,
        db: Session = Depends(get_db),
):

    records = get_chat_history_recent(db, session_id, days)
    return {
        "session_id": session_id,
        "items": [
            {
                "role": r.role.value,
                "message": r.message,
                "created_at": str(r.created_at),
            }
            for r in records
        ],
    }


@router.post("/slack/webhook")
async def slack_webhook(request: Request, background_tasks: BackgroundTasks):

    body = await request.body()
    payload = await request.json()

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if settings.slack_signing_secret and not _verify_slack_signature(body, timestamp, signature):
        logger.warning("Slack 서명 검증 실패")
        raise HTTPException(status_code=403, detail="서명 검증 실패")

    event = payload.get("event", {})
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return {"status": "ignored"}

    user_message = event.get("text", "").strip()
    user_id      = event.get("user", "unknown")
    channel_id   = event.get("channel", "")
    thread_ts    = event.get("thread_ts") or event.get("ts", "")

    if not user_message:
        return {"status": "empty_message"}

    user_message = re.sub(r"<@[A-Z0-9]+>", "", user_message).strip()
    if not user_message:
        return {"status": "empty_after_mention_strip"}

    logger.info(f"Slack 메시지 수신: user={user_id}, msg={user_message[:50]}")

    try:
        get_slack_client().chat_postMessage(
            channel=channel_id,
            text="분석 중입니다. 잠시만 기다려주세요...",
            thread_ts=thread_ts,
        )
    except Exception as e:
        logger.warning(f"처리 중 메시지 전송 실패: {e}")

    background_tasks.add_task(
        _run_agent_and_reply,
        user_message=user_message,
        user_id=user_id,
        channel_id=channel_id,
        thread_ts=thread_ts,
    )

    return {"status": "ok"}


@router.post("/query", response_model=ChatResponse)
async def chat_query(
        req: ChatRequest,
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    logger.info(f"챗봇 질의: user={current_user.username}, msg={req.message[:50]}")
    reply = run_agent(
        message=req.message,
        session_id=req.session_id,
        user_id=current_user.username,
    )
    return ChatResponse(reply=reply, session_id=req.session_id)
