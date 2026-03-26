from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from loguru import logger
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.models import OrderProposal, ProposalStatus
from app.api.auth_router import get_current_user

router = APIRouter(prefix="/scm/orders", tags=["orders"])


class ProposalUpdate(BaseModel):
    proposed_qty: Optional[int] = None
    unit_price:   Optional[float] = None


class ProposalOut(BaseModel):
    id:           int
    product_code: str
    product_name: Optional[str]
    category:     Optional[str]
    proposed_qty: int
    unit_price:   float
    reason:       Optional[str]
    status:       str
    created_at:   str
    approved_at:  Optional[str]
    approved_by:  Optional[str]

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



@router.get("/proposals")
def list_proposals(
        status: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_user),
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


@router.post("/proposals/generate")
async def generate_proposals(
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_user),
):

    try:
        from app.sheets.reader import read_product_master, read_sales, read_stock
        from app.ai.anomaly_detector import detect_stock_anomalies
        from app.ai.order_agent import generate_order_proposals
        from app.slack.notifier import send_slack_message
        from app.config import settings

        df_master, df_stock, df_sales = await asyncio.to_thread(
            lambda: (read_product_master(), read_stock(), read_sales())
        )

        stock_anomalies = detect_stock_anomalies(df_stock, df_sales)
        high_anomalies = [
            a for a in stock_anomalies
            if str(a.get("severity", "")).lower() in ("high", "critical")
        ]

        if not high_anomalies:
            return {"created": 0, "message": "높음 이상 이상징후 없음"}

        proposals_data = generate_order_proposals(high_anomalies, df_master, df_stock, df_sales)

        created = 0
        slack_lines = ["*[SCM] 자동 발주 제안 생성*"]
        for p in proposals_data:
            obj = OrderProposal(**p)
            db.add(obj)
            db.flush()
            created += 1
            slack_lines.append(
                f"• `{p['product_code']}` {p['product_name']} — {p['proposed_qty']:,}개 제안"
            )
        db.commit()

        # Slack 알림
        try:
            slack_lines.append(f"\n관리자 화면에서 승인/수정하세요.")
            await asyncio.to_thread(
                send_slack_message,
                settings.slack_channel_id,
                "\n".join(slack_lines),
            )
        except Exception as e:
            logger.warning(f"Slack 알림 실패(스킵): {e}")

        return {"created": created, "message": f"{created}건 발주 제안 생성 완료"}

    except Exception as e:
        logger.error(f"발주 제안 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/proposals/{proposal_id}/approve")
def approve_proposal(
        proposal_id: int,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user),
):
    obj = db.query(OrderProposal).filter(OrderProposal.id == proposal_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    from datetime import datetime
    obj.status = ProposalStatus.APPROVED
    obj.approved_at = datetime.now()
    obj.approved_by = current_user.get("sub", "admin")
    db.commit()
    return ProposalOut.from_orm(obj)


@router.patch("/proposals/{proposal_id}/reject")
def reject_proposal(
        proposal_id: int,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user),
):
    obj = db.query(OrderProposal).filter(OrderProposal.id == proposal_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    from datetime import datetime
    obj.status = ProposalStatus.REJECTED
    obj.approved_at = datetime.now()
    obj.approved_by = current_user.get("sub", "admin")
    db.commit()
    return ProposalOut.from_orm(obj)


@router.put("/proposals/{proposal_id}")
def update_proposal(
        proposal_id: int,
        body: ProposalUpdate,
        db: Session = Depends(get_db),
        _: dict = Depends(get_current_user),
):
    obj = db.query(OrderProposal).filter(OrderProposal.id == proposal_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="제안을 찾을 수 없습니다")
    if body.proposed_qty is not None:
        obj.proposed_qty = body.proposed_qty
    if body.unit_price is not None:
        obj.unit_price = body.unit_price
    db.commit()
    return ProposalOut.from_orm(obj)
