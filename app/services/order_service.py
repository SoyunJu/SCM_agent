from __future__ import annotations

from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import OrderProposal, ProposalStatus
from app.utils.severity import norm, SEVERITY_RANK


class OrderService:

    # --- GET ---

    @staticmethod
    def list_proposals(
            db: Session, status: str | None, limit: int, offset: int,
    ) -> dict:
        query = db.query(OrderProposal)
        if status:
            try:
                query = query.filter(OrderProposal.status == ProposalStatus(status.upper()))
            except ValueError:
                pass
        total = query.count()
        items = query.order_by(OrderProposal.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total, "offset": offset, "limit": limit,
            "items": [OrderService._serialize(p) for p in items],
        }

    @staticmethod
    def get_threshold(db: Session) -> str:
        from app.db.models import SystemSettings
        row = db.query(SystemSettings).filter(
            SystemSettings.setting_key == "AUTO_ORDER_MIN_SEVERITY"
        ).first()
        return norm(row.setting_value) if row and norm(row.setting_value) in SEVERITY_RANK else "MEDIUM"

    # --- PATCH ---

    @staticmethod
    def approve(db: Session, proposal_id: int, username: str) -> dict:
        from app.services.slack_service import SlackService
        p = OrderService._get_or_404(db, proposal_id)
        p.status      = ProposalStatus.APPROVED
        p.approved_by = username
        p.approved_at = datetime.utcnow()
        db.commit()
        db.refresh(p)
        SlackService.update_proposal_resolved(p)
        logger.info(f"[OrderService] 발주 승인: id={proposal_id}, by={username}")
        return OrderService._serialize(p)

    @staticmethod
    def reject(db: Session, proposal_id: int, username: str) -> dict:
        from app.services.slack_service import SlackService
        p = OrderService._get_or_404(db, proposal_id)
        p.status      = ProposalStatus.REJECTED
        p.approved_by = username
        p.approved_at = datetime.utcnow()
        db.commit()
        db.refresh(p)
        SlackService.update_proposal_resolved(p)
        logger.info(f"[OrderService] 발주 거절: id={proposal_id}, by={username}")
        return OrderService._serialize(p)

    @staticmethod
    def update(db: Session, proposal_id: int,
               proposed_qty: int | None, unit_price: float | None) -> dict:
        from app.services.slack_service import SlackService
        p = OrderService._get_or_404(db, proposal_id)
        if proposed_qty is not None:
            p.proposed_qty = proposed_qty
        if unit_price is not None:
            p.unit_price = unit_price
        db.commit()
        db.refresh(p)
        # PENDING 상태일 때만 Slack 메시지 수정 반영
        if p.status == ProposalStatus.PENDING:
            SlackService.update_proposal_pending(p)
        return OrderService._serialize(p)

    # --- CREATE ---

    @staticmethod
    def generate(db: Session, severity_override: str | None) -> dict:
        from app.sheets.reader import read_product_master, read_sales, read_stock
        from app.ai.anomaly_detector import detect_stock_anomalies
        from app.ai.order_agent import generate_order_proposals
        from app.services.slack_service import SlackService
        from app.notifier.slack_notifier import get_slack_client
        from app.config import settings as app_settings

        threshold = (
            norm(severity_override)
            if severity_override and norm(severity_override) in SEVERITY_RANK
            else OrderService.get_threshold(db)
        )
        threshold_rank = SEVERITY_RANK[threshold]

        df_master, df_stock, df_sales = read_product_master(), read_stock(), read_sales()
        stock_anomalies = detect_stock_anomalies(df_master, df_stock, df_sales)
        filtered = [
            a for a in stock_anomalies
            if SEVERITY_RANK.get(norm(a.get("severity", "")), -1) >= threshold_rank
        ]
        if not filtered:
            return {"created": 0, "message": f"'{threshold}' 이상 이상징후 없음"}

        proposals_data = generate_order_proposals(filtered, df_master, df_stock, df_sales)

        # Slack 헤더 메시지
        try:
            get_slack_client().chat_postMessage(
                channel=app_settings.slack_channel_id,
                text=f"[SCM] 발주 제안 {len(proposals_data)}건 생성",
                blocks=[
                    {"type": "header",
                     "text": {"type": "plain_text", "text": "SCM Agent | 자동 발주 제안"}},
                    {"type": "section",
                     "text": {"type": "mrkdwn",
                              "text": (
                                  f"이상징후 분석 결과 *{len(proposals_data)}건* 발주 제안 생성\n"
                                  f"임계값: *{threshold.upper()}* | 이상항목: {len(filtered)}건"
                              )}},
                    {"type": "divider"},
                ],
            )
        except Exception as e:
            logger.warning(f"Slack 헤더 전송 실패(스킵): {e}")

        created = 0
        for p_data in proposals_data:
            obj = OrderProposal(**p_data)
            db.add(obj)
            db.flush()   # id 확보
            try:
                SlackService.send_proposal(obj)
            except Exception as e:
                logger.warning(f"Slack 발송 실패(스킵): {e}")
            created += 1

        db.commit()
        logger.info(f"[OrderService] 발주 제안 {created}건 생성, 임계값={threshold}")
        return {
            "created":   created,
            "threshold": threshold,
            "proposals": [
                OrderService._serialize(p)
                for p in db.query(OrderProposal)
                .order_by(OrderProposal.id.desc())
                .limit(created)
                .all()
            ],
        }

    # --- HELPER ---

    @staticmethod
    def _get_or_404(db: Session, proposal_id: int) -> OrderProposal:
        from fastapi import HTTPException
        p = db.query(OrderProposal).filter(OrderProposal.id == proposal_id).first()
        if not p:
            raise HTTPException(404, "발주 제안을 찾을 수 없습니다.")
        return p

    @staticmethod
    def _get_threshold(db: Session) -> str:
        return OrderService.get_threshold(db)

    @staticmethod
    def _serialize(p: OrderProposal) -> dict:
        return {
            "id":           p.id,
            "product_code": p.product_code,
            "product_name": p.product_name,
            "category":     p.category,
            "proposed_qty": p.proposed_qty,
            "unit_price":   p.unit_price or 0.0,
            "reason":       p.reason,
            "status":       p.status.value if p.status else "PENDING",
            "created_at":   p.created_at.isoformat() if p.created_at else "",
            "approved_at":  p.approved_at.isoformat() if p.approved_at else None,
            "approved_by":  p.approved_by,
        }


    @staticmethod
    def list_proposals(
            db: Session, status: str | None, limit: int, offset: int,
            days: int | None = None,    # ← 추가
    ) -> dict:
        from datetime import datetime, timedelta
        query = db.query(OrderProposal)
        if status:
            try:
                query = query.filter(OrderProposal.status == ProposalStatus(status.upper()))
            except ValueError:
                pass
        if days is not None:            # ← 추가
            cutoff = datetime.now() - timedelta(days=days)
            query = query.filter(OrderProposal.created_at >= cutoff)
        total = query.count()
        items = query.order_by(OrderProposal.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total, "offset": offset, "limit": limit,
            "items": [OrderService._serialize(p) for p in items],
        }