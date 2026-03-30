from __future__ import annotations

from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import OrderProposal, ProposalStatus
from app.utils.severity import norm, SEVERITY_RANK
from app.db.repository import get_lead_time_for_product


class OrderService:

    # --- GET ---

    @staticmethod
    def list_proposals(
            db: Session, status: str | None, limit: int, offset: int,
            days: int | None = None,
    ) -> dict:
        from datetime import datetime, timedelta
        query = db.query(OrderProposal)
        if status:
            try:
                query = query.filter(OrderProposal.status == ProposalStatus(status.upper()))
            except ValueError:
                pass
        if days is not None:
            cutoff = datetime.now() - timedelta(days=days)
            query = query.filter(OrderProposal.created_at >= cutoff)
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
    def approve(db: Session, proposal_id: int, username: str, user_role: str) -> dict:
        from app.services.slack_service import SlackService
        from fastapi import HTTPException
        p = OrderService._get_or_404(db, proposal_id)

        # 결재 권한 검증
        required = (p.required_role or "ADMIN").upper()
        role     = user_role.upper()
        role_rank = {"READONLY": 0, "ADMIN": 1, "SUPERADMIN": 2}
        if role_rank.get(role, 0) < role_rank.get(required, 1):
            raise HTTPException(
                status_code=403,
                detail=f"이 발주는 {required} 이상만 승인할 수 있습니다. (현재 역할: {role})",
            )

        p.status      = ProposalStatus.APPROVED
        p.approved_by = username
        p.approved_at = datetime.now()
        db.commit()
        db.refresh(p)
        SlackService.update_proposal_resolved(p)
        logger.info(f"[OrderService] 발주 승인: id={proposal_id}, by={username} ({role})")
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
    def reset(db: Session, proposal_id: int, username: str) -> dict:
        p = OrderService._get_or_404(db, proposal_id)
        if p.status == ProposalStatus.PENDING:
            from fastapi import HTTPException
            raise HTTPException(400, "이미 PENDING 상태입니다.")
        p.status      = ProposalStatus.PENDING
        p.approved_by = None
        p.approved_at = None
        db.commit()
        db.refresh(p)
        logger.info(f"[OrderService] 발주 되돌리기: id={proposal_id}, by={username}")
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
    def generate(db: Session, severity_override: str | None, product_code: str | None = None) -> dict:
        from app.db.models import Product, ProductStatus, StockLevel
        from app.db.repository import get_daily_sales_range, get_setting
        from app.ai.anomaly_detector import detect_stock_anomalies
        from app.ai.order_agent import generate_order_proposals
        from app.services.slack_service import SlackService
        from app.notifier.slack_notifier import get_slack_client
        from app.config import settings as app_settings
        from datetime import date, timedelta
        import pandas as pd

        threshold = (
            norm(severity_override)
            if severity_override and norm(severity_override) in SEVERITY_RANK
            else OrderService.get_threshold(db)
        )
        threshold_rank = SEVERITY_RANK[threshold]

        # --- DB에서 분석 데이터 로드 ---
        products = db.query(Product).filter(Product.status == ProductStatus.ACTIVE).all()
        # 특정 상품코드 필터
        if product_code:
            products = [p for p in products if p.code == product_code]
            if not products:
                from fastapi import HTTPException
                raise HTTPException(404, f"상품코드 '{product_code}'를 찾을 수 없습니다.")

        df_master = pd.DataFrame([
            {"상품코드": p.code, "상품명": p.name,
             "카테고리": p.category or "", "안전재고기준": p.safety_stock}
            for p in products
        ]) if products else pd.DataFrame(columns=["상품코드", "상품명", "카테고리", "안전재고기준"])

        stocks = db.query(StockLevel).all()
        df_stock = pd.DataFrame([
            {"상품코드": s.product_code, "현재재고": s.current_stock,
             "입고예정일": str(s.restock_date) if s.restock_date else "",
             "입고예정수량": s.restock_qty or 0}
            for s in stocks
        ]) if stocks else pd.DataFrame(columns=["상품코드", "현재재고", "입고예정일", "입고예정수량"])

        sales_rows = get_daily_sales_range(
            db, start=date.today() - timedelta(days=90), end=date.today()
        )
        df_sales = pd.DataFrame([
            {"날짜": str(s.date), "상품코드": s.product_code,
             "판매수량": s.qty, "매출액": s.revenue, "매입액": s.cost}
            for s in sales_rows
        ]) if sales_rows else pd.DataFrame(
            columns=["날짜", "상품코드", "판매수량", "매출액", "매입액"]
        )

        # --- 이상징후 감지 + 필터 ---
        stock_anomalies = detect_stock_anomalies(df_master, df_stock, df_sales)
        filtered = [
            a for a in stock_anomalies
            if SEVERITY_RANK.get(norm(a.get("severity", "")), -1) >= threshold_rank
        ]
        if not filtered:
            return {"created": 0, "message": f"'{threshold}' 이상 이상징후 없음"}

        proposals_data = generate_order_proposals(filtered, df_master, df_stock, df_sales)

        # --- 결재선 설정 조회 ---
        auto_approve_enabled = get_setting(db, "AUTO_ORDER_APPROVAL",         "false").lower() == "true"
        auto_limit           = float(get_setting(db, "ORDER_AUTO_APPROVE_LIMIT",    "100000"))
        manager_limit        = float(get_setting(db, "ORDER_MANAGER_APPROVAL_LIMIT","1000000"))

        # --- Slack 헤더 메시지 ---
        mode_label = "자동 승인" if auto_approve_enabled else "승인 대기"
        try:
            get_slack_client().chat_postMessage(
                channel=app_settings.slack_channel_id,
                text=f"[SCM] 발주 제안 {len(proposals_data)}건 생성 ({mode_label})",
                blocks=[
                    {"type": "header",
                     "text": {"type": "plain_text", "text": "SCM Agent | 자동 발주 제안"}},
                    {"type": "section",
                     "text": {"type": "mrkdwn",
                              "text": (
                                  f"이상징후 분석 결과 *{len(proposals_data)}건* 발주 제안 생성\n"
                                  f"임계값: *{threshold.upper()}* | 이상항목: {len(filtered)}건 | 모드: *{mode_label}*"
                              )}},
                    {"type": "divider"},
                ],
            )
        except Exception as e:
            logger.warning(f"Slack 헤더 전송 실패(스킵): {e}")


        # --- 발주 제안 저장 ---
        created = 0
        for p_data in proposals_data:
            obj       = OrderProposal(**p_data)
            total_amt = (p_data.get("proposed_qty") or 0) * (p_data.get("unit_price") or 0)

            # 결재선
            if auto_approve_enabled and total_amt < auto_limit:
                # 소액 자동 승인
                obj.status       = ProposalStatus.APPROVED
                obj.required_role = "SYSTEM"
                obj.approved_by  = "SYSTEM"
                obj.approved_at  = datetime.utcnow()
                db.add(obj)
                db.flush()
                try:
                    SlackService.send_auto_approved(obj)
                except Exception as e:
                    logger.warning(f"Slack 자동승인 전송 실패(스킵): {e}")
            elif total_amt >= manager_limit:
                # 고액 → SUPERADMIN 승인 필요
                obj.required_role = "SUPERADMIN"
                db.add(obj)
                db.flush()
                try:
                    SlackService.send_proposal(obj, approval_note="⚠️ 고액 발주 — SUPERADMIN 승인 필요")
                except Exception as e:
                    logger.warning(f"Slack 발송 실패(스킵): {e}")
            else:
                # 중액 → ADMIN 승인 필요
                obj.required_role = "ADMIN"
                db.add(obj)
                db.flush()
                try:
                    SlackService.send_proposal(obj)
                except Exception as e:
                    logger.warning(f"Slack 발송 실패(스킵): {e}")

            created += 1

        db.commit()
        logger.info(f"[OrderService] 발주 제안 생성: {created}건, threshold={threshold}")
        return {
            "created": created,
            "threshold": threshold,
            "auto_approve": auto_approve_enabled,
            "proposals": [OrderService._serialize(p) for p in
                          db.query(OrderProposal).order_by(OrderProposal.created_at.desc()).limit(created).all()],
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
            "approved_at":   p.approved_at.isoformat() if p.approved_at else None,
            "approved_by":   p.approved_by,
            "required_role": p.required_role or "ADMIN",
        }