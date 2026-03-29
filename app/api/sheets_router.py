from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.services.sheet_service import SheetService
from app.services.sync_service import SyncService

router = APIRouter(prefix="/scm/sheets", tags=["sheets"])


class ProductUpdate(BaseModel):
    name:          Optional[str] = None
    category:      Optional[str] = None
    safety_stock:  Optional[int] = None
    status:        Optional[str] = None



@router.get("/categories")
async def get_categories(current_user: Annotated[TokenData, Depends(get_current_user)]):
    try:
        return {"items": SheetService.get_categories()}
    except Exception as e:
        logger.error(f"카테고리 조회 실패: {e}")
        return {"items": []}

@router.get("/master")
async def get_master(
        current_user: Annotated[TokenData, Depends(require_admin)],
        page: int = 1, page_size: int = 50,
        search: str | None = None, category: str | None = None, download: bool = False,
):
    try:
        return SheetService.get_master(page, page_size, search, category, download)
    except Exception as e:
        logger.error(f"상품마스터 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}

@router.get("/sales")
async def get_sales(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30, page: int = 1, page_size: int = 50,
        category: str | None = None, search: str | None = None, download: bool = False,
):
    try:
        return SheetService.get_sales(days, page, page_size, search, category, download)
    except Exception as e:
        logger.error(f"일별판매 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}

@router.get("/stock")
async def get_stock(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        page: int = 1, page_size: int = 50,
        category: str | None = None, search: str | None = None, download: bool = False,
):
    try:
        return SheetService.get_stock(page, page_size, search, category, download)
    except Exception as e:
        logger.error(f"재고현황 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}

@router.get("/orders")
async def get_orders(
        current_user: Annotated[TokenData, Depends(require_admin)],
        status: str | None = None, days: int = 90,
        page: int = 1, page_size: int = 50,
):
    try:
        return SheetService.get_orders(status, days, page, page_size)
    except Exception as e:
        logger.error(f"주문 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}

@router.get("/stats/sales")
async def get_sales_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        period: str = "daily", category: str | None = None,
):
    try:
        return SheetService.get_sales_stats(period, category)
    except Exception as e:
        logger.error(f"판매통계 조회 실패: {e}")
        return {"items": []}

@router.get("/stats/stock")
async def get_stock_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        category: str | None = None,
):
    try:
        return SheetService.get_stock_stats(category)
    except Exception as e:
        logger.error(f"재고통계 조회 실패: {e}")
        return {"total_anomalies": 0, "severity_counts": {}, "stock_items": []}

@router.get("/stats/abc")
async def get_abc_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 90, category: str | None = None,
):
    try:
        return SheetService.get_abc_stats(days, category)
    except Exception as e:
        logger.error(f"ABC분석 조회 실패: {e}")
        return {"items": []}

@router.get("/stats/demand")
async def get_demand_forecast(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        forecast_days: int = 14, page: int = 1,
        page_size: int = 50, category: str | None = None,
):
    try:
        return SheetService.get_demand_stats(forecast_days, page, page_size, category)
    except Exception as e:
        logger.error(f"수요예측 조회 실패: {e}")
        return {"total": 0, "items": []}

@router.get("/stats/turnover")
async def get_turnover_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30, page: int = 1,
        page_size: int = 50, category: str | None = None,
):
    try:
        return SheetService.get_turnover_stats(days, page, page_size, category)
    except Exception as e:
        logger.error(f"회전율 조회 실패: {e}")
        return {"total": 0, "items": []}

@router.post("/sync")
async def sync_sheets(
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    try:
        SyncService.sync_all_from_sheets(db)
        return {"status": "ok", "message": "동기화가 완료되었습니다."}
    except Exception as e:
        logger.error(f"동기화 실패: {e}")
        raise HTTPException(500, f"동기화 실패: {e}")