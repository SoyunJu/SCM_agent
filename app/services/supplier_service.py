from __future__ import annotations

from datetime import datetime, date
from loguru import logger
from sqlalchemy.orm import Session

from app.db.models import (
    Supplier, ProductSupplier, SupplierDeliveryHistory,
    ReceivingInspection, StockLevel, OrderProposal, ProposalStatus,
)


class SupplierService:

    # ── 공급업체 CRUD ─────────────────────────────────────────────────────────

    @staticmethod
    def list_suppliers(db: Session, active_only: bool = False) -> list[dict]:
        query = db.query(Supplier)
        if active_only:
            query = query.filter(Supplier.is_active == True)
        suppliers = query.order_by(Supplier.name).all()
        return [SupplierService._serialize_supplier(s, db) for s in suppliers]

    @staticmethod
    def get_supplier(db: Session, supplier_id: int) -> dict:
        s = SupplierService._get_or_404(db, supplier_id)
        return SupplierService._serialize_supplier(s, db)

    @staticmethod
    def create_supplier(db: Session, data: dict) -> dict:
        supplier = Supplier(
            name           = data["name"],
            contact        = data.get("contact"),
            email          = data.get("email"),
            phone          = data.get("phone"),
            lead_time_days = int(data.get("lead_time_days", 14)),
        )
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        logger.info(f"[공급업체] 등록: {supplier.name} (id={supplier.id})")
        return SupplierService._serialize_supplier(supplier, db)

    @staticmethod
    def update_supplier(db: Session, supplier_id: int, data: dict) -> dict:
        s = SupplierService._get_or_404(db, supplier_id)
        for field in ("name", "contact", "email", "phone", "lead_time_days", "is_active"):
            if field in data and data[field] is not None:
                setattr(s, field, data[field])
        db.commit()
        db.refresh(s)
        logger.info(f"[공급업체] 수정: id={supplier_id}")
        return SupplierService._serialize_supplier(s, db)

    @staticmethod
    def delete_supplier(db: Session, supplier_id: int) -> dict:
        s = SupplierService._get_or_404(db, supplier_id)
        # 매핑된 상품 있으면 비활성화만
        mappings = db.query(ProductSupplier).filter(
            ProductSupplier.supplier_id == supplier_id
        ).count()
        if mappings > 0:
            s.is_active = False
            db.commit()
            return {"id": supplier_id, "deleted": False, "deactivated": True,
                    "message": f"매핑된 상품 {mappings}건으로 인해 비활성화 처리되었습니다."}
        db.delete(s)
        db.commit()
        return {"id": supplier_id, "deleted": True}

    # ── 상품-공급업체 매핑 ────────────────────────────────────────────────────

    @staticmethod
    def map_product(db: Session, product_code: str, supplier_id: int,
                    unit_price: float | None = None) -> dict:
        # 공급업체 존재 확인
        SupplierService._get_or_404(db, supplier_id)

        existing = db.query(ProductSupplier).filter(
            ProductSupplier.product_code == product_code
        ).first()
        if existing:
            existing.supplier_id = supplier_id
            if unit_price is not None:
                existing.unit_price = unit_price
        else:
            db.add(ProductSupplier(
                product_code=product_code,
                supplier_id=supplier_id,
                unit_price=unit_price,
            ))

        # Product.lead_time_days를 공급업체 리드타임으로 동기화
        from app.db.models import Product
        product = db.query(Product).filter(Product.code == product_code).first()
        if product:
            supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
            if supplier and product.lead_time_days is None:
                # 상품별 설정 없을 때만 공급업체 리드타임 적용
                product.lead_time_days = supplier.lead_time_days

        db.commit()
        logger.info(f"[공급업체] 상품 매핑: {product_code} → supplier_id={supplier_id}")
        return {"product_code": product_code, "supplier_id": supplier_id, "unit_price": unit_price}

    @staticmethod
    def get_product_supplier(db: Session, product_code: str) -> dict | None:
        row = db.query(ProductSupplier, Supplier).join(
            Supplier, ProductSupplier.supplier_id == Supplier.id
        ).filter(ProductSupplier.product_code == product_code).first()
        if not row:
            return None
        ps, s = row
        return {
            "product_code":    ps.product_code,
            "supplier_id":     s.id,
            "supplier_name":   s.name,
            "lead_time_days":  s.lead_time_days,
            "unit_price":      ps.unit_price,
        }

    # ── 납기 이력 ─────────────────────────────────────────────────────────────

    @staticmethod
    def list_delivery_history(db: Session, supplier_id: int | None = None,
                              limit: int = 50) -> list[dict]:
        query = db.query(SupplierDeliveryHistory)
        if supplier_id:
            query = query.filter(SupplierDeliveryHistory.supplier_id == supplier_id)
        rows = query.order_by(SupplierDeliveryHistory.created_at.desc()).limit(limit).all()
        return [
            {
                "id":                r.id,
                "supplier_id":       r.supplier_id,
                "order_proposal_id": r.order_proposal_id,
                "expected_date":     str(r.expected_date),
                "actual_date":       str(r.actual_date) if r.actual_date else None,
                "delay_days":        r.delay_days,
                "on_time":           (r.delay_days or 0) <= 0 if r.actual_date else None,
            }
            for r in rows
        ]

    @staticmethod
    def get_supplier_stats(db: Session, supplier_id: int) -> dict:
        """납기 지연율, 평균 지연일수 계산"""
        SupplierService._get_or_404(db, supplier_id)
        rows = db.query(SupplierDeliveryHistory).filter(
            SupplierDeliveryHistory.supplier_id == supplier_id,
            SupplierDeliveryHistory.actual_date.isnot(None),
            ).all()
        if not rows:
            return {"total": 0, "on_time_rate": None, "avg_delay_days": None}

        total      = len(rows)
        delayed    = sum(1 for r in rows if (r.delay_days or 0) > 0)
        avg_delay  = round(sum(r.delay_days or 0 for r in rows) / total, 1)
        return {
            "total":          total,
            "delayed":        delayed,
            "on_time_rate":   round((total - delayed) / total * 100, 1),
            "avg_delay_days": avg_delay,
        }

    # ── 입고 검수 ─────────────────────────────────────────────────────────────

    @staticmethod
    def list_inspections(db: Session, status: str | None = None,
                         limit: int = 50, offset: int = 0) -> dict:
        query = db.query(ReceivingInspection)
        if status:
            query = query.filter(ReceivingInspection.status == status.upper())
        total = query.count()
        items = query.order_by(ReceivingInspection.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "items": [SupplierService._serialize_inspection(r) for r in items],
        }

    @staticmethod
    def create_inspection(db: Session, order_proposal_id: int, username: str) -> dict:
        """발주 제안 기반 입고 검수 생성"""
        proposal = db.query(OrderProposal).filter(
            OrderProposal.id == order_proposal_id
        ).first()
        if not proposal:
            from fastapi import HTTPException
            raise HTTPException(404, "발주 제안을 찾을 수 없습니다.")

        # 중복 검수 방지
        existing = db.query(ReceivingInspection).filter(
            ReceivingInspection.order_proposal_id == order_proposal_id,
            ReceivingInspection.status.notin_(["COMPLETED", "RETURNED"]),
            ).first()
        if existing:
            from fastapi import HTTPException
            raise HTTPException(400, f"이미 진행 중인 검수가 있습니다. (id={existing.id})")

        # 공급업체 조회
        ps = db.query(ProductSupplier).filter(
            ProductSupplier.product_code == proposal.product_code
        ).first()

        inspection = ReceivingInspection(
            order_proposal_id = order_proposal_id,
            supplier_id       = ps.supplier_id if ps else None,
            product_code      = proposal.product_code,
            product_name      = proposal.product_name,
            ordered_qty       = proposal.proposed_qty,
            status            = "PENDING",
        )
        db.add(inspection)
        db.commit()
        db.refresh(inspection)
        logger.info(f"[입고검수] 생성: id={inspection.id}, product={proposal.product_code}")
        return SupplierService._serialize_inspection(inspection)

    @staticmethod
    def complete_inspection(db: Session, inspection_id: int,
                            received_qty: int, defect_qty: int,
                            return_qty: int, note: str | None,
                            username: str) -> dict:
        """입고 검수 완료 처리 + 재고 반영 + Sheets 업데이트 + 납기 이력 기록"""
        insp = db.query(ReceivingInspection).filter(
            ReceivingInspection.id == inspection_id
        ).first()
        if not insp:
            from fastapi import HTTPException
            raise HTTPException(404, "검수 이력을 찾을 수 없습니다.")

        good_qty = received_qty - defect_qty - return_qty

        # 상태 결정
        if return_qty >= received_qty:
            new_status = "RETURNED"
        elif received_qty < insp.ordered_qty:
            new_status = "PARTIAL"
        else:
            new_status = "COMPLETED"

        insp.received_qty  = received_qty
        insp.defect_qty    = defect_qty
        insp.return_qty    = return_qty
        insp.status        = new_status
        insp.note          = note
        insp.inspected_by  = username
        insp.inspected_at  = datetime.utcnow()

        # 재고 반영 (양품만)
        if good_qty > 0:
            stock = db.query(StockLevel).filter(
                StockLevel.product_code == insp.product_code
            ).first()
            if stock:
                stock.current_stock = (stock.current_stock or 0) + good_qty
            else:
                db.add(StockLevel(
                    product_code  = insp.product_code,
                    current_stock = good_qty,
                ))

        db.commit()
        db.refresh(insp)

        # 납기 이력 기록
        if insp.supplier_id and insp.order_proposal_id:
            SupplierService._record_delivery(db, insp)

        # Sheets 재고현황 업데이트
        if good_qty > 0:
            try:
                SupplierService._sync_stock_to_sheets(insp.product_code, good_qty, db)
            except Exception as e:
                logger.warning(f"[입고검수] Sheets 재고 업데이트 실패(스킵): {e}")

        logger.info(
            f"[입고검수] 완료: id={inspection_id}, "
            f"product={insp.product_code}, "
            f"received={received_qty}, defect={defect_qty}, good={good_qty}"
        )
        return SupplierService._serialize_inspection(insp)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _record_delivery(db: Session, insp: ReceivingInspection) -> None:
        """납기 이력 기록 및 지연일수 계산"""
        proposal = db.query(OrderProposal).filter(
            OrderProposal.id == insp.order_proposal_id
        ).first()
        if not proposal:
            return

        # 예상 납기일 = 발주 승인일 + 공급업체 리드타임
        supplier = db.query(Supplier).filter(
            Supplier.id == insp.supplier_id
        ).first()
        lead_time = supplier.lead_time_days if supplier else 14
        base_date = proposal.approved_at.date() if proposal.approved_at else proposal.created_at.date()
        from datetime import timedelta
        expected_date = base_date + timedelta(days=lead_time)
        actual_date   = insp.inspected_at.date()
        delay_days    = (actual_date - expected_date).days

        db.add(SupplierDeliveryHistory(
            supplier_id       = insp.supplier_id,
            order_proposal_id = insp.order_proposal_id,
            expected_date     = expected_date,
            actual_date       = actual_date,
            delay_days        = delay_days,
        ))
        db.commit()

    @staticmethod
    def _sync_stock_to_sheets(product_code: str, added_qty: int, db: Session) -> None:
        """입고 완료 후 재고현황 Sheets 업데이트"""
        from app.sheets.client import get_spreadsheet

        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("재고현황")
        records = ws.get_all_records()

        for i, row in enumerate(records, start=2):  # header=1행
            if str(row.get("상품코드", "")) == product_code:
                current = int(row.get("현재재고", 0) or 0)
                ws.update_cell(i, 2, current + added_qty)  # 현재재고 컬럼
                logger.info(f"[Sheets] 재고현황 업데이트: {product_code} {current} → {current + added_qty}")
                return

        logger.warning(f"[Sheets] 재고현황에 {product_code} 없음 — 업데이트 스킵")

    @staticmethod
    def _get_or_404(db: Session, supplier_id: int) -> Supplier:
        from fastapi import HTTPException
        s = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        if not s:
            raise HTTPException(404, f"공급업체를 찾을 수 없습니다. id={supplier_id}")
        return s

    @staticmethod
    def _serialize_supplier(s: Supplier, db: Session) -> dict:
        # 매핑 상품 수
        mapped = db.query(ProductSupplier).filter(
            ProductSupplier.supplier_id == s.id
        ).count()
        # 납기 통계
        stats = SupplierService.get_supplier_stats(db, s.id)
        return {
            "id":             s.id,
            "name":           s.name,
            "contact":        s.contact,
            "email":          s.email,
            "phone":          s.phone,
            "lead_time_days": s.lead_time_days,
            "is_active":      s.is_active,
            "mapped_products":s.id and mapped,
            "on_time_rate":   stats["on_time_rate"],
            "avg_delay_days": stats["avg_delay_days"],
            "created_at":     str(s.created_at),
        }

    @staticmethod
    def _serialize_inspection(r: ReceivingInspection) -> dict:
        return {
            "id":                r.id,
            "order_proposal_id": r.order_proposal_id,
            "supplier_id":       r.supplier_id,
            "product_code":      r.product_code,
            "product_name":      r.product_name,
            "ordered_qty":       r.ordered_qty,
            "received_qty":      r.received_qty,
            "defect_qty":        r.defect_qty,
            "return_qty":        r.return_qty,
            "good_qty":          r.received_qty - r.defect_qty - r.return_qty,
            "status":            r.status,
            "note":              r.note,
            "inspected_by":      r.inspected_by,
            "inspected_at":      r.inspected_at.isoformat() if r.inspected_at else None,
            "created_at":        r.created_at.isoformat() if r.created_at else None,
        }