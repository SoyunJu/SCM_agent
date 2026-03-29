from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.services.order_service import OrderService

router = APIRouter(prefix="/scm/orders", tags=["orders"])


class ProposalUpdate(BaseModel):
    proposed_qty: Optional[int]   = None
    unit_price:   Optional[float] = None

class GenerateRequest(BaseModel):
    severity_override: Optional[str] = None
    product_code:      Optional[str] = None


@router.get("/proposals")
def list_proposals(
        status: Optional[str] = Query(None),
        limit:  int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        days:   Optional[int] = Query(None, ge=1, description="최근 N일 이내 생성된 발주만 조회"),
        db: Session = Depends(get_db),
        _: TokenData = Depends(get_current_user),
):
    return OrderService.list_proposals(db, status, limit, offset, days)   # ← days 전달


@router.get("/proposals/threshold")
def get_threshold(
        db: Session = Depends(get_db),
        _:  TokenData = Depends(get_current_user),
):
    return {"threshold": OrderService.get_threshold(db), "options": ["LOW","MEDIUM","HIGH","CRITICAL"]}


@router.post("/proposals/generate")
async def generate_proposals(
        body: GenerateRequest = GenerateRequest(),
        db: Session = Depends(get_db),
        _: TokenData = Depends(require_admin),
):
    try:
        return OrderService.generate(db, body.severity_override, body.product_code)
    except Exception as e:
        logger.error(f"발주 제안 생성 실패: {e}")
        from fastapi import HTTPException
        raise HTTPException(500, str(e))


@router.patch("/proposals/{proposal_id}/approve")
def approve_proposal(
        proposal_id: int,
        db: Session = Depends(get_db),
        current_user: TokenData = Depends(require_admin),
):
    return OrderService.approve(db, proposal_id, current_user.username)


@router.patch("/proposals/{proposal_id}/reject")
def reject_proposal(
        proposal_id: int,
        db: Session = Depends(get_db),
        current_user: TokenData = Depends(require_admin),
):
    return OrderService.reject(db, proposal_id, current_user.username)


@router.patch("/proposals/{proposal_id}/reset")
def reset_proposal(
        proposal_id: int,
        db: Session = Depends(get_db),
        current_user: TokenData = Depends(require_admin),
):
    return OrderService.reset(db, proposal_id, current_user.username)


@router.put("/proposals/{proposal_id}")
def update_proposal(
        proposal_id: int,
        body: ProposalUpdate,
        db: Session = Depends(get_db),
        _:  TokenData = Depends(require_admin),
):
    return OrderService.update(db, proposal_id, body.proposed_qty, body.unit_price)