from __future__ import annotations

import asyncio
import json
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from loguru import logger
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.models import OrderProposal, ProposalStatus, SystemSettings
from app.api.auth_router import get_current_user, require_admin, TokenData

router = APIRouter(prefix="/scm/orders", tags=["orders"])

# --- 심각도 순위 ------------
SEVERITY_RANK: dict[str, int] = {"low": 0, "check":0, "medium": 1, "high": 2, "critical": 3}


def _get_severity_threshold(db: Session) -> str:
    row = db.query(SystemSettings).filter(
        SystemSettings.setting_key == "AUTO_PROPOSAL_SEVERITY"
    ).first()
    if row and row.setting_value.lower() in SEVERITY_RANK:
        return row.setting_value.lower()
    return "medium"


# --- Schemas ------------------

class ProposalUpdate(BaseModel):
    proposed_qty: Optional[int]   = None
    unit_price:   Optional[float] = None


class ProposalOut(BaseModel):
    id:            int
    product_code:  str
    product_name:  Optional[str]
    category:      Optional[str]
    proposed_qty:  int
    unit_price:    float
    reason:        Optional[str]
    status:        str
    created_at:    str
    approved_at:   Optional[str]
    approved_by:   Optional[str]

    @classmethod
    def from_orm(cls, obj: OrderProposal) -> "ProposalOut":
        return cls(
            id=obj.id,
            product_code=obj.product_code,
            product_name=obj.product_name,
            category=obj.category,
            proposed_qty=obj.proposed_qty,
            unit_price=obj.unit_price or 0.0,
            reason=obj.reason,
            status=obj.status.value if obj.status else "pending",
            created_at=obj.created_at.isoformat() if obj.created_at else "",
            approved_at=obj.approved_at.isoformat() if obj.approved_at else None,
            approved_by=obj.approved_by,
        )


# --- Slack Block ------------------------------------------------------------------------------─

def _build_proposal_blocks(p: OrderProposal) -> list[dict]:
    price_str = f"{p.unit_price:,.0f}원" if p.unit_price and p.unit_price > 0 else "미입력"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*[발주제안 #{p.id}]* `{p.product_code}` {p.product_name or ''}\n"
                    f"카테고리: {p.category or '-'} | *제안수량: {p.proposed_qty:,}개* | 단가: {price_str}\n"
                    f"_{p.reason or ''}_"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": f"proposal_actions_{p.id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ 승인"},
                    "style": "primary",
                    "action_id": "approve_proposal",
                    "value": str(p.id),
                    "confirm": {
                        "title": {"type": "plain_text", "text": "승인 확인"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{p.product_code}* {p.proposed_qty:,}개 발주를 승인하시겠습니까?",
                        },
                        "confirm": {"type": "plain_text", "text": "승인"},
                        "deny":    {"type": "plain_text", "text": "취소"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 거절"},
                    "style": "danger",
                    "action_id": "reject_proposal",
                    "value": str(p.id),
                    "confirm": {
                        "title": {"type": "plain_text", "text": "거절 확인"},
                        "text": {"type": "mrkdwn", "text": "이 발주 제안을 거절하시겠습니까?"},
                        "confirm": {"type": "plain_text", "text": "거절"},
                        "deny":    {"type": "plain_text", "text": "취소"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ 수정"},
                    "action_id": "modify_proposal",
                    "value": str(p.id),
                },
            ],
        },
        {"type": "divider"},
    ]


def _build_resolved_blocks(p: OrderProposal) -> list[dict]:
    status_text = "✅ 승인됨" if p.status == ProposalStatus.APPROVED else "❌ 거절됨"
    price_str = f"{p.unit_price:,.0f}원" if p.unit_price and p.unit_price > 0 else "미입력"
    by = p.approved_by or "관리자"
    at = p.approved_at.strftime("%Y-%m-%d %H:%M") if p.approved_at else ""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*[발주제안 #{p.id}]* `{p.product_code}` {p.product_name or ''}\n"
                    f"카테고리: {p.category or '-'} | 수량: {p.proposed_qty:,}개 | 단가: {price_str}\n"
                    f"_{p.reason or ''}_\n"
                    f"*{status_text}* — {by} ({at})"
                ),
            },
        },
        {"type": "divider"},
    ]


# --- 발주 제안 생성 ---------

@router.post("/proposals/generate")
async def generate_proposals(
        db: Session = Depends(get_db),
        _: dict = Depends(require_admin),
):
    try:
        from app.sheets.reader import read_product_master, read_sales, read_stock
        from app.ai.anomaly_detector import detect_stock_anomalies
        from app.ai.order_agent import generate_order_proposals
        from app.notifier.slack_notifier import get_slack_client, send_blocks
        from app.config import settings as app_settings

        threshold = _get_severity_threshold(db)
        threshold_rank = SEVERITY_RANK[threshold]
        logger.info(f"발주 제안 생성 — 심각도 임계값: {threshold} (rank≥{threshold_rank})")

        df_master, df_stock, df_sales = await asyncio.to_thread(
            lambda: (read_product_master(), read_stock(), read_sales())
        )

        stock_anomalies = detect_stock_anomalies(df_master, df_stock, df_sales)
        filtered = [
            a for a in stock_anomalies
            if SEVERITY_RANK.get(str(a.get("severity", "")).lower(), -1) >= threshold_rank
        ]

        if not filtered:
            return {"created": 0, "message": f"'{threshold}' 이상 이상징후 없음"}

        proposals_data = generate_order_proposals(filtered, df_master, df_stock, df_sales)

        created = 0
        slack_client = get_slack_client()
        channel = app_settings.slack_channel_id

        # --- 헤더 ---------------------------------------------------------------------------------
        header_blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "SCM Agent | 자동 발주 제안"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"이상징후 분석 결과 *{len(proposals_data)}건*의 발주 제안이 생성되었습니다.\n"
                        f"임계값: *{threshold.upper()}* 이상 | "
                        f"이상항목: {len(filtered)}건 → 제안: {len(proposals_data)}건"
                    ),
                },
            },
            {"type": "divider"},
        ]
        try:
            slack_client.chat_postMessage(
                channel=channel,
                text=f"[SCM_Agent] 발주 제안 {len(proposals_data)}건 생성",
                blocks=header_blocks,
            )
        except Exception as e:
            logger.warning(f"Slack 헤더 전송 실패(스킵): {e}")

        # --- 제안별 개별 메시지 전송 ---------------------------------------------------------------
        for p_data in proposals_data:
            obj = OrderProposal(**p_data)
            db.add(obj)
            db.flush()  # id 확보

            # Slack 메시지 전송 (ts 저장용)
            try:
                resp = slack_client.chat_postMessage(
                    channel=channel,
                    text=f"발주제안 #{obj.id} | {obj.product_code} {obj.product_name} {obj.proposed_qty:,}개",
                    blocks=_build_proposal_blocks(obj),
                )
                obj.slack_ts      = resp["ts"]
                obj.slack_channel = channel
            except Exception as e:
                logger.warning(f"Slack 제안 메시지 전송 실패(스킵): {e}")

            created += 1

        db.commit()
        return {"created": created, "message": f"{created}건 발주 제안 생성 완료"}

    except Exception as e:
        logger.error(f"발주 제안 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 목록 조회 ---------------

@router.get("/proposals")
def list_proposals(
        status: Optional[str] = Query(None),
        limit:  int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        _: TokenData = Depends(get_current_user),
):
    q = db.query(OrderProposal)
    if status:
        try:
            q = q.filter(OrderProposal.status == ProposalStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"잘못된 status: {status}")
    total = q.count()
    items = q.order_by(OrderProposal.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [ProposalOut.from_orm(r) for r in items],
    }


# --- 승인 ---------------------─

@router.patch("/proposals/{proposal_id}/approve")
def approve_proposal(
        proposal_id: int,
        db: Session = Depends(get_db),
        current_user: TokenData = Depends(require_admin),
):
    obj = _get_or_404(db, proposal_id)
    obj.status      = ProposalStatus.APPROVED
    obj.approved_at = datetime.now()
    obj.approved_by = current_user.username
    db.commit()
    _update_slack_message(obj)
    return ProposalOut.from_orm(obj)


# --- 거절 ---------------------─

@router.patch("/proposals/{proposal_id}/reject")
def reject_proposal(
        proposal_id: int,
        db: Session = Depends(get_db),
        current_user: TokenData = Depends(require_admin),
):
    obj = _get_or_404(db, proposal_id)
    obj.status      = ProposalStatus.REJECTED
    obj.approved_at = datetime.now()
    obj.approved_by = current_user.username
    db.commit()
    _update_slack_message(obj)
    return ProposalOut.from_orm(obj)


# --- 수정 ---------------------─

@router.put("/proposals/{proposal_id}")
def update_proposal(
        proposal_id: int,
        body: ProposalUpdate,
        db: Session = Depends(get_db),
        _: dict = Depends(require_admin),
):
    obj = _get_or_404(db, proposal_id)
    if body.proposed_qty is not None:
        obj.proposed_qty = body.proposed_qty
    if body.unit_price is not None:
        obj.unit_price = body.unit_price
    db.commit()
    # pending 상태면 수정 내용을 Slack 메시지에도 반영
    if obj.status == ProposalStatus.PENDING:
        _update_slack_message_pending(obj)
    return ProposalOut.from_orm(obj)


# --- 심각도 임계값 조회 ---

@router.get("/proposals/threshold")
def get_threshold(
        db: Session = Depends(get_db),
        _: TokenData = Depends(get_current_user),
):
    return {
        "threshold": _get_severity_threshold(db),
        "options": list(SEVERITY_RANK.keys()),
    }


# --- 헬퍼 ---------------

def _get_or_404(db: Session, proposal_id: int) -> OrderProposal:
    obj = db.query(OrderProposal).filter(OrderProposal.id == proposal_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    return obj


def _update_slack_message(obj: OrderProposal) -> None:
    if not obj.slack_ts or not obj.slack_channel:
        return
    try:
        from app.notifier.slack_notifier import get_slack_client
        get_slack_client().chat_update(
            channel=obj.slack_channel,
            ts=obj.slack_ts,
            text=f"발주제안 #{obj.id} — {obj.status.value}",
            blocks=_build_resolved_blocks(obj),
        )
    except Exception as e:
        logger.warning(f"Slack 메시지 업데이트 실패(스킵): {e}")


def _update_slack_message_pending(obj: OrderProposal) -> None:
    if not obj.slack_ts or not obj.slack_channel:
        return
    try:
        from app.notifier.slack_notifier import get_slack_client
        get_slack_client().chat_update(
            channel=obj.slack_channel,
            ts=obj.slack_ts,
            text=f"발주제안 #{obj.id} | {obj.product_code} {obj.proposed_qty:,}개 (수정됨)",
            blocks=_build_proposal_blocks(obj),
        )
    except Exception as e:
        logger.warning(f"Slack 메시지 업데이트 실패(스킵): {e}")
