from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import TokenData, get_current_user, require_admin
from app.db.connection import get_db
from app.services.supplier_service import SupplierService

router = APIRouter(prefix="/scm/suppliers", tags=["suppliers"])


# ── 요청 스키마 ───────────────────────────────────────────────────────────────

class SupplierCreateRequest(BaseModel):
    name:           str
    contact:        str | None = None
    email:          str | None = None
    phone:          str | None = None
    lead_time_days: int = 14

class SupplierUpdateRequest(BaseModel):
    name:           str | None = None
    contact:        str | None = None
    email:          str | None = None
    phone:          str | None = None
    lead_time_days: int | None = None
    is_active:      bool | None = None

class ProductMapRequest(BaseModel):
    product_code: str
    unit_price:   float | None = None

class InspectionCompleteRequest(BaseModel):
    received_qty: int
    defect_qty:   int = 0
    return_qty:   int = 0
    note:         str | None = None


# ── 공급업체 CRUD ─────────────────────────────────────────────────────────────

@router.get("")
def list_suppliers(
        active_only: bool = False,
        current_user: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return SupplierService.list_suppliers(db, active_only=active_only)


@router.get("/{supplier_id}")
def get_supplier(
        supplier_id: int,
        current_user: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return SupplierService.get_supplier(db, supplier_id)


@router.post("", status_code=201)
def create_supplier(
        body: SupplierCreateRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SupplierService.create_supplier(db, body.model_dump())


@router.patch("/{supplier_id}")
def update_supplier(
        supplier_id: int,
        body: SupplierUpdateRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SupplierService.update_supplier(db, supplier_id, body.model_dump(exclude_none=True))


@router.delete("/{supplier_id}")
def delete_supplier(
        supplier_id: int,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SupplierService.delete_supplier(db, supplier_id)


# ── 상품-공급업체 매핑 ────────────────────────────────────────────────────────

@router.post("/{supplier_id}/products")
def map_product(
        supplier_id: int,
        body: ProductMapRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SupplierService.map_product(
        db, body.product_code, supplier_id, body.unit_price
    )


@router.get("/products/{product_code}/supplier")
def get_product_supplier(
        product_code: str,
        current_user: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    result = SupplierService.get_product_supplier(db, product_code)
    if not result:
        raise HTTPException(404, f"{product_code}에 매핑된 공급업체가 없습니다.")
    return result


# ── 납기 이력 ─────────────────────────────────────────────────────────────────

@router.get("/{supplier_id}/delivery-history")
def get_delivery_history(
        supplier_id: int,
        limit: int = 50,
        current_user: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return SupplierService.list_delivery_history(db, supplier_id=supplier_id, limit=limit)


@router.get("/{supplier_id}/stats")
def get_supplier_stats(
        supplier_id: int,
        current_user: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return SupplierService.get_supplier_stats(db, supplier_id)


# ── 입고 검수 ─────────────────────────────────────────────────────────────────

@router.get("/inspections")
def list_inspections(
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        current_user: TokenData = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return SupplierService.list_inspections(db, status=status, limit=limit, offset=offset)


@router.post("/inspections/from-proposal/{order_proposal_id}", status_code=201)
def create_inspection(
        order_proposal_id: int,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SupplierService.create_inspection(db, order_proposal_id, current_user.username)


@router.patch("/inspections/{inspection_id}/complete")
def complete_inspection(
        inspection_id: int,
        body: InspectionCompleteRequest,
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    return SupplierService.complete_inspection(
        db,
        inspection_id  = inspection_id,
        received_qty   = body.received_qty,
        defect_qty     = body.defect_qty,
        return_qty     = body.return_qty,
        note           = body.note,
        username       = current_user.username,
    )