from __future__ import annotations

from datetime import date, timedelta

from loguru import logger
from sqlalchemy.orm import Session

from app.db.repository import get_anomaly_logs, resolve_anomaly
from app.utils.severity import norm


ANOMALY_KOR = {
    "LOW_STOCK":       "재고 부족",
    "OVER_STOCK":      "과잉 재고",
    "SALES_SURGE":     "판매 급등",
    "SALES_DROP":      "판매 급락",
    "LONG_TERM_STOCK": "장기 재고",
}

SEVERITY_KOR = {
    "CRITICAL": "긴급",
    "HIGH":     "높음",
    "MEDIUM":   "보통",
    "LOW":      "낮음",
    "CHECK":    "확인필요",
}

# 발주 자동처리 대상 유형
_ORDER_TYPES    = {"LOW_STOCK", "SALES_SURGE"}
# 할인 판매 자동처리 대상 유형
_DISCOUNT_TYPES = {"OVER_STOCK", "LONG_TERM_STOCK", "SALES_DROP"}

# SALES_SURGE 긴급 발주 리드타임 (일)
_SURGE_LEAD_TIME = 14


class AnomalyService:

    @staticmethod
    def list_anomalies(
            db: Session,
            is_resolved: bool | None,
            anomaly_type: str | None,
            severity: str | None,
            page: int,
            page_size: int,
    ) -> dict:
        result = get_anomaly_logs(
            db,
            is_resolved=is_resolved,
            anomaly_type=anomaly_type,
            severity=severity,
            page=page,
            page_size=page_size,
        )
        return {
            "total":       result["total"],
            "page":        result["page"],
            "page_size":   result["page_size"],
            "total_pages": result["total_pages"],
            "items": [
                {
                    "id":                  r.id,
                    "detected_at":         str(r.detected_at)[:19],
                    "product_code":        r.product_code,
                    "product_name":        r.product_name,
                    "category":            r.category or "",
                    "anomaly_type":        r.anomaly_type.value if hasattr(r.anomaly_type, "value") else str(r.anomaly_type),
                    "anomaly_type_kor":    ANOMALY_KOR.get(
                        r.anomaly_type.value if hasattr(r.anomaly_type, "value") else str(r.anomaly_type),
                        r.anomaly_type.value if hasattr(r.anomaly_type, "value") else str(r.anomaly_type)
                    ),
                    "severity":            r.severity.value if hasattr(r.severity, "value") else str(r.severity),
                    "severity_kor":        SEVERITY_KOR.get(
                        r.severity.value if hasattr(r.severity, "value") else str(r.severity), ""
                    ),
                    "current_stock":       r.current_stock,
                    "daily_avg_sales":     round(r.daily_avg_sales, 1) if r.daily_avg_sales is not None else None,
                    "days_until_stockout": round(r.days_until_stockout, 1) if r.days_until_stockout is not None else None,
                    "is_resolved":         r.is_resolved,
                }
                for r in result["items"]
            ],
        }

    @staticmethod
    def resolve(db: Session, anomaly_id: int) -> dict:
        from fastapi import HTTPException
        record = resolve_anomaly(db, anomaly_id)
        if not record:
            raise HTTPException(404, "이상 징후를 찾을 수 없습니다.")
        logger.info(f"[AnomalyService] 이상징후 해결 처리: id={anomaly_id}")
        return {"id": record.id, "is_resolved": record.is_resolved}

    # ── 자동 처리 ─────────────────────────────────────────────────────────────
    @staticmethod
    def auto_resolve(db: Session, anomaly_id: int, username: str) -> dict:

        from fastapi import HTTPException
        from app.db.models import AnomalyLog

        record = db.query(AnomalyLog).filter(AnomalyLog.id == anomaly_id).first()
        if not record:
            raise HTTPException(404, "이상 징후를 찾을 수 없습니다.")
        if record.is_resolved:
            raise HTTPException(400, "이미 해결된 이상징후입니다.")

        anomaly_type = (
            record.anomaly_type.value
            if hasattr(record.anomaly_type, "value")
            else str(record.anomaly_type)
        ).upper()

        if anomaly_type in _ORDER_TYPES:
            result = AnomalyService._auto_resolve_order(db, record, username, anomaly_type)
        elif anomaly_type in _DISCOUNT_TYPES:
            result = AnomalyService._auto_resolve_discount(db, record)
        else:
            raise HTTPException(400, f"자동 처리 미지원 유형: {anomaly_type}")

        # resolve
        resolved = resolve_anomaly(db, anomaly_id)
        if not resolved:
            raise HTTPException(500, "resolve 처리에 실패했습니다.")

        logger.info(f"[AnomalyService] auto_resolve 완료: id={anomaly_id}, type={anomaly_type}")
        return {"id": anomaly_id, "anomaly_type": anomaly_type, "is_resolved": True, **result}


    # ── CASE 1 : LOW_STOCK / SALES_SURGE ─────────────────────────────────────
    @staticmethod
    def _auto_resolve_order(
            db: Session, record, username: str, anomaly_type: str
    ) -> dict:
        import math
        from datetime import datetime
        from fastapi import HTTPException
        from app.db.models import OrderProposal, ProposalStatus, Product, StockLevel
        from app.db.repository import get_daily_sales_range

        # 기존 PENDING 발주 제안 존재 확인
        existing_pending = (
            db.query(OrderProposal)
            .filter(
                OrderProposal.product_code == record.product_code,
                OrderProposal.status == ProposalStatus.PENDING,
                )
            .first()
        )
        if existing_pending:
            raise HTTPException(
                409,
                f"이미 대기 중인 발주 제안이 있습니다. (제안 ID: {existing_pending.id})"
            )

        # 상품 정보 조회
        product = db.query(Product).filter(Product.code == record.product_code).first()
        if not product:
            raise HTTPException(404, f"상품을 찾을 수 없습니다: {record.product_code}")

        stock = db.query(StockLevel).filter(
            StockLevel.product_code == record.product_code
        ).first()
        current_stock = stock.current_stock if stock else 0

        # 90일 판매 이력으로 일평균 판매량 + 평균 매입단가 산출
        sales_rows = get_daily_sales_range(
            db,
            start=date.today() - timedelta(days=90),
            end=date.today(),
        )
        sales_rows = [s for s in sales_rows if s.product_code == record.product_code]

        total_qty  = sum(s.qty  for s in sales_rows) or 0
        total_cost = sum(s.cost for s in sales_rows) or 0.0
        days_cnt   = len(sales_rows) or 1
        avg_sales  = total_qty / days_cnt  # 일평균 판매량
        unit_price = round(total_cost / total_qty, 0) if total_qty > 0 else 0.0

        safety_stock = product.safety_stock or math.ceil(avg_sales * 7)

        # 수량 산출 분기
        if anomaly_type == "LOW_STOCK":
            # 안전재고(7일치) + 리드타임(14일치) - 현재재고
            lead_demand  = math.ceil(avg_sales * 14)
            proposed_qty = max(1, math.ceil(safety_stock + lead_demand - current_stock))
            reason = (
                f"[재고부족 자동발주] 현재재고 {current_stock}개 / "
                f"일평균 {avg_sales:.1f}개 / 리드타임 14일"
            )
        else:
            # SALES_SURGE: 급등 판매량 × 리드타임
            # daily_avg_sales가 급등 이후 평균이므로 그대로 사용
            surge_avg    = record.daily_avg_sales or avg_sales
            proposed_qty = max(1, math.ceil(surge_avg * _SURGE_LEAD_TIME))
            reason = (
                f"[판매급등 긴급발주] 급등 일평균 {surge_avg:.1f}개 / "
                f"리드타임 {_SURGE_LEAD_TIME}일"
            )

        # 발주 제안 생성 + 즉시 APPROVED
        proposal = OrderProposal(
            product_code = record.product_code,
            product_name = record.product_name,
            category     = record.category,
            proposed_qty = proposed_qty,
            unit_price   = unit_price,
            reason       = reason,
            status       = ProposalStatus.APPROVED,
            approved_by  = username,
            approved_at  = datetime.utcnow(),
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)

        # Slack 알림 (실패해도 처리 계속)
        try:
            from app.services.slack_service import SlackService
            SlackService.send_auto_approved(proposal)
        except Exception as e:
            logger.warning(f"[auto_resolve] Slack 알림 실패(스킵): {e}")

        logger.info(
            f"[auto_resolve] 발주 자동승인: {record.product_code} "
            f"{proposed_qty}개 @ {unit_price:,.0f}원 (proposal_id={proposal.id})"
        )
        return {
            "action":       "order_approved",
            "proposal_id":  proposal.id,
            "proposed_qty": proposed_qty,
            "unit_price":   unit_price,
            "reason":       reason,
        }

    # ── CASE 2 : OVER_STOCK / LONG_TERM_STOCK / SALES_DROP ───────────────────
    @staticmethod
    def _auto_resolve_discount(db: Session, record) -> dict:
        import math
        from fastapi import HTTPException
        from app.db.models import Product, StockLevel
        from app.db.repository import get_daily_sales_range
        from app.sheets.writer import append_discount_sales

        # 상품 정보 조회
        product = db.query(Product).filter(Product.code == record.product_code).first()
        if not product:
            raise HTTPException(404, f"상품을 찾을 수 없습니다: {record.product_code}")

        stock = db.query(StockLevel).filter(
            StockLevel.product_code == record.product_code
        ).first()
        current_stock = stock.current_stock if stock else 0
        safety_stock  = product.safety_stock or 0

        # 과재고 수량 산출
        over_qty = current_stock - safety_stock
        if over_qty <= 0:
            raise HTTPException(
                400,
                f"현재재고({current_stock})가 안전재고({safety_stock}) 이하입니다. 처리 대상이 아닙니다."
            )

        # 90일 판매 이력으로 단가 산출
        sales_rows = get_daily_sales_range(
            db,
            start=date.today() - timedelta(days=90),
            end=date.today(),
        )
        sales_rows = [s for s in sales_rows if s.product_code == record.product_code]

        total_qty  = sum(s.qty     for s in sales_rows) or 0
        total_rev  = sum(s.revenue for s in sales_rows) or 0.0
        total_cost = sum(s.cost    for s in sales_rows) or 0.0

        if total_qty > 0:
            unit_sell = round(total_rev  / total_qty, 0)
            unit_cost = round(total_cost / total_qty, 0)
        else:
            # 판매 이력 없음 (LONG_TERM_STOCK 등) → 단가 산출 불가, 기본값 사용
            unit_sell = 0.0
            unit_cost = 0.0

        # 최대 할인율 산출
        if unit_sell > 0 and unit_sell > unit_cost:
            max_discount = round((unit_sell - unit_cost) / unit_sell * 100, 1)
        else:
            # 단가 정보 없으면 기본 20% 할인
            max_discount = 20.0

        # 구글 시트 일별판매에 append (실패해도 resolve는 계속)
        sheet_ok = True
        sheet_err = ""
        try:
            append_discount_sales(
                product_code = record.product_code,
                product_name = record.product_name or "",
                over_qty     = over_qty,
                unit_sell    = unit_sell,
                unit_cost    = unit_cost,
                max_discount = max_discount,
            )
        except Exception as e:
            sheet_ok  = False
            sheet_err = str(e)
            logger.warning(f"[auto_resolve] 시트 append 실패(resolve는 계속): {e}")

        logger.info(
            f"[auto_resolve] 할인판매 처리: {record.product_code} "
            f"over_qty={over_qty} discount={max_discount}% sheet_ok={sheet_ok}"
        )
        return {
            "action":       "discount_sales",
            "over_qty":     over_qty,
            "unit_sell":    unit_sell,
            "unit_cost":    unit_cost,
            "max_discount": max_discount,
            "sheet_ok":     sheet_ok,
            "sheet_error":  sheet_err if not sheet_ok else None,
        }