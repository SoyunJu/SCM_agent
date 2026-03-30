"""
Slack Interactive Components 핸들러
- 버튼 클릭: approve_proposal / reject_proposal / modify_proposal
- 모달 제출: modify_proposal_modal (수량/단가 수정)
Slack App 설정: Interactivity & Shortcuts → Request URL = https://<your-domain>/scm/slack/interactions
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.connection import get_db
from app.db.models import OrderProposal, ProposalStatus
from app.notifier.slack_notifier import get_slack_client

router = APIRouter(prefix="/scm/slack", tags=["slack"])


# --- 서명 검증 ---

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


# --- 메인 엔드포인트 ---------------------------------------------------------------------------------------

@router.post("/interactions")
async def slack_interactions(
        request: Request,
        db: Session = Depends(get_db),
):
    raw_body = await request.body()

    # 서명 검증
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if settings.slack_signing_secret and not _verify_slack_signature(raw_body, timestamp, signature):
        raise HTTPException(status_code=403, detail="Slack 서명 검증 실패")

    form_data = urllib.parse.parse_qs(raw_body.decode("utf-8"))
    payload_str = form_data.get("payload", ["{}"])[0]
    payload: dict = json.loads(payload_str)

    ptype = payload.get("type")

    if ptype == "block_actions":
        return await _handle_block_actions(payload, db)

    if ptype == "view_submission":
        return await _handle_view_submission(payload, db)

    # 그 외 타입은 200 응답만
    return Response(status_code=200)


# --- block_actions 처리 ---------------------------------------------------------------------------------─

async def _handle_block_actions(payload: dict, db: Session) -> Response:
    actions: list[dict] = payload.get("actions", [])
    if not actions:
        return Response(status_code=200)

    action    = actions[0]
    action_id = action.get("action_id", "")
    value     = action.get("value", "")

    user_id   = payload.get("user", {}).get("id", "unknown")
    user_name = payload.get("user", {}).get("name", user_id)

    try:
        proposal_id = int(value)
    except (ValueError, TypeError):
        logger.warning(f"Slack 인터랙션: 잘못된 proposal_id={value}")
        return Response(status_code=200)

    obj = db.query(OrderProposal).filter(OrderProposal.id == proposal_id).first()
    if not obj:
        _slack_ephemeral(payload, f"발주제안 #{proposal_id}을(를) 찾을 수 없습니다.")
        return Response(status_code=200)

    if action_id == "approve_proposal":
        return _process_approve(obj, user_id, user_name, db, payload)

    if action_id == "reject_proposal":
        return _process_reject(obj, user_id, user_name, db, payload)

    if action_id == "modify_proposal":
        return _open_modify_modal(obj, payload)

    return Response(status_code=200)


def _process_approve(
        obj: OrderProposal, user_id: str, user_name: str,
        db: Session, payload: dict,
) -> Response:
    if obj.status != ProposalStatus.PENDING:
        _slack_ephemeral(payload, f"발주제안 #{obj.id}은 이미 {obj.status.value} 상태입니다.")
        return Response(status_code=200)

    # Slack 사용자 → AdminUser 역할 조회
    from app.db.models import AdminUser
    slack_user = db.query(AdminUser).filter(AdminUser.slack_user_id == user_id).first()
    user_role  = slack_user.role.value if slack_user else "ADMIN"
    required   = (obj.required_role or "ADMIN").upper()
    role_rank  = {"READONLY": 0, "ADMIN": 1, "SUPERADMIN": 2}
    if role_rank.get(user_role.upper(), 0) < role_rank.get(required, 1):
        _slack_ephemeral(payload, f"⚠️ 이 발주는 {required} 이상만 승인 가능합니다. (현재: {user_role})")
        return Response(status_code=200)

    obj.status      = ProposalStatus.APPROVED
    obj.approved_at = datetime.now()
    obj.approved_by = user_name
    db.commit()
    _update_message_resolved(obj, payload)
    logger.info(f"[Slack] 발주제안 #{obj.id} 승인 — {user_name} ({user_role})")
    return Response(status_code=200)


def _process_reject(
        obj: OrderProposal, user_id: str, user_name: str,
        db: Session, payload: dict,
) -> Response:
    if obj.status != ProposalStatus.PENDING:
        _slack_ephemeral(payload, f"발주제안 #{obj.id}은 이미 {obj.status.value} 상태입니다.")
        return Response(status_code=200)

    obj.status      = ProposalStatus.REJECTED
    obj.approved_at = datetime.now()
    obj.approved_by = user_name
    db.commit()
    _update_message_resolved(obj, payload)
    logger.info(f"[Slack] 발주제안 #{obj.id} 거절 — {user_name}")
    return Response(status_code=200)


def _open_modify_modal(obj: OrderProposal, payload: dict) -> Response:
    trigger_id = payload.get("trigger_id", "")
    if not trigger_id:
        return Response(status_code=200)

    try:
        get_slack_client().views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "callback_id": "modify_proposal_modal",
                "private_metadata": json.dumps({
                    "proposal_id":   obj.id,
                    "slack_channel": obj.slack_channel or "",
                    "slack_ts":      obj.slack_ts or "",
                }),
                "title": {"type": "plain_text", "text": "발주 수량/단가 수정"},
                "submit": {"type": "plain_text", "text": "저장"},
                "close":  {"type": "plain_text", "text": "취소"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*#{obj.id}* `{obj.product_code}` {obj.product_name or ''}\n"
                                f"현재: {obj.proposed_qty:,}개 / {obj.unit_price or 0:,.0f}원"
                            ),
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "qty_block",
                        "label": {"type": "plain_text", "text": "발주 수량"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "qty_input",
                            "initial_value": str(obj.proposed_qty),
                            "placeholder": {"type": "plain_text", "text": "숫자 입력"},
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "price_block",
                        "label": {"type": "plain_text", "text": "단가 (원)"},
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "price_input",
                            "initial_value": str(int(obj.unit_price)) if obj.unit_price else "0",
                            "placeholder": {"type": "plain_text", "text": "숫자 입력 (선택)"},
                        },
                    },
                ],
            },
        )
    except Exception as e:
        logger.error(f"Slack 모달 열기 실패: {e}")
    return Response(status_code=200)


# --- view_submission 처리 ------------------------------------------------------------------------------─

async def _handle_view_submission(payload: dict, db: Session) -> Response:
    callback_id = payload.get("view", {}).get("callback_id", "")
    if callback_id != "modify_proposal_modal":
        return Response(status_code=200)

    # private_metadata에서 proposal_id 파싱
    try:
        meta = json.loads(payload["view"].get("private_metadata", "{}"))
        proposal_id = int(meta["proposal_id"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return Response(status_code=200)

    values = payload["view"]["state"]["values"]
    qty_str   = values.get("qty_block",   {}).get("qty_input",   {}).get("value", "")
    price_str = values.get("price_block", {}).get("price_input", {}).get("value", "")

    # 입력값 검증
    errors: dict[str, str] = {}
    try:
        new_qty = int(qty_str) if qty_str else None
        if new_qty is not None and new_qty <= 0:
            errors["qty_block"] = "1 이상의 수량을 입력하세요."
    except ValueError:
        errors["qty_block"] = "숫자만 입력하세요."

    if errors:
        return Response(
            content=json.dumps({"response_action": "errors", "errors": errors}),
            media_type="application/json",
        )

    obj = db.query(OrderProposal).filter(OrderProposal.id == proposal_id).first()
    if not obj:
        return Response(status_code=200)

    user_name = payload.get("user", {}).get("name", "unknown")

    if new_qty is not None:
        obj.proposed_qty = new_qty
    try:
        new_price = float(price_str) if price_str else None
        if new_price is not None:
            obj.unit_price = new_price
    except ValueError:
        pass  # 단가 파싱 실패는 스킵

    db.commit()
    logger.info(f"[Slack] 발주제안 #{obj.id} 수정 — qty={obj.proposed_qty}, price={obj.unit_price} by {user_name}")

    # Slack 메시지 갱신 (버튼 유지)
    if obj.slack_ts and obj.slack_channel:
        try:
            from app.api.order_router import _build_proposal_blocks
            get_slack_client().chat_update(
                channel=obj.slack_channel,
                ts=obj.slack_ts,
                text=f"발주제안 #{obj.id} | {obj.product_code} {obj.proposed_qty:,}개 (수정됨 by {user_name})",
                blocks=_build_proposal_blocks(obj),
            )
        except Exception as e:
            logger.warning(f"Slack 메시지 갱신 실패(스킵): {e}")

    # 모달 닫기 (아무것도 반환 안 하면 자동 닫힘)
    return Response(status_code=200)


# --- 헬퍼 ---

def _update_message_resolved(obj: OrderProposal, payload: dict) -> None:
    """승인/거절 후 Slack 원본 메시지를 상태 표시로 교체"""
    if not obj.slack_ts or not obj.slack_channel:
        return
    try:
        from app.api.order_router import _build_resolved_blocks
        get_slack_client().chat_update(
            channel=obj.slack_channel,
            ts=obj.slack_ts,
            text=f"발주제안 #{obj.id} — {obj.status.value}",
            blocks=_build_resolved_blocks(obj),
        )
    except Exception as e:
        logger.warning(f"Slack 메시지 업데이트 실패(스킵): {e}")


def _slack_ephemeral(payload: dict, text: str) -> None:
    """클릭한 사람에게만 보이는 임시 메시지"""
    try:
        channel = payload.get("channel", {}).get("id", "")
        user_id = payload.get("user", {}).get("id", "")
        if channel and user_id:
            get_slack_client().chat_postEphemeral(
                channel=channel,
                user=user_id,
                text=text,
            )
    except Exception as e:
        logger.warning(f"Ephemeral 메시지 실패(스킵): {e}")
