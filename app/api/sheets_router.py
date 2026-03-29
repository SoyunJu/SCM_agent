from __future__ import annotations

import os
import tempfile
from typing import Annotated, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.db.repository import get_setting
from app.services.sheet_service import SheetService
from app.services.sync_service import SyncService
from app.sheets.writer import upsert_master_from_excel, write_sales, upsert_stock_from_excel

router = APIRouter(prefix="/scm/sheets", tags=["sheets"])

_REQUIRED_COLS: dict[str, list[str]] = {
    "master": ["상품코드"],
    "sales":  ["상품코드", "날짜", "판매수량"],
    "stock":  ["상품코드", "현재재고"],
}


# ── 상품 수정 ──────────────────────────────────────────────────────────────

class ProductUpdate(BaseModel):
    name:         Optional[str] = None
    category:     Optional[str] = None
    safety_stock: Optional[int] = None
    status:       Optional[str] = None


@router.put("/products/{code}")
async def update_product(
        code: str,
        body: ProductUpdate,
        _: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    try:
        return SheetService.update_product(db, code.strip(), body.model_dump(exclude_none=True))
    except ValueError as e:
        status_code = 400 if "유효하지 않은" in str(e) else 404
        raise HTTPException(status_code, str(e))
    except Exception as exc:
        logger.error(f"[상품수정] 실패: code={code}, error={exc}")
        raise HTTPException(status_code=500, detail=f"상품 수정 중 오류 발생: {exc}")


# ── 조회 ───────────────────────────────────────────────────────────────────

@router.get("/categories")
async def get_categories(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    try:
        return {"items": SheetService.get_categories(db)}
    except Exception as e:
        logger.error(f"카테고리 조회 실패: {e}")
        return {"items": []}


@router.get("/master")
async def get_master(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        page: int = 1, page_size: int = 50,
        search: str | None = None, category: str | None = None,
        status: str | None = None,
        download: bool = False,
        db: Session = Depends(get_db),
):
    try:
        return SheetService.get_master(db, page, page_size, search, category, download, status)
    except Exception as e:
        logger.error(f"상품마스터 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}


@router.get("/sales")
async def get_sales(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
        days: int = 30, page: int = 1, page_size: int = 50,
        category: str | None = None, search: str | None = None, download: bool = False,
):
    try:
        return SheetService.get_sales(db, days, page, page_size, search, category, download)
    except Exception as e:
        logger.error(f"일별판매 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}


@router.get("/stock")
async def get_stock(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
        page: int = 1, page_size: int = 50,
        category: str | None = None, search: str | None = None, download: bool = False,
):
    try:
        return SheetService.get_stock(db, page, page_size, search, category, download)
    except Exception as e:
        logger.error(f"재고현황 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}


@router.get("/orders")
async def get_orders(
        current_user: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
        status: str | None = None, days: int = 90,
        page: int = 1, page_size: int = 50,
):
    try:
        return SheetService.get_orders(db, status, days, page, page_size)
    except Exception as e:
        logger.error(f"주문 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}


# ── 통계 ───────────────────────────────────────────────────────────────────

@router.get("/stats/sales")
async def get_sales_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
        period: str = "daily", category: str | None = None,
):
    try:
        return SheetService.get_sales_stats(db, period, category)
    except Exception as e:
        logger.error(f"판매통계 조회 실패: {e}")
        return {"items": []}



@router.get("/stats/stock")
async def get_stock_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        category: str | None = None,
        page: int = 1,
        page_size: int = 50,
        db: Session = Depends(get_db),
):
    try:
        return SheetService.get_stock_stats(db, category, page, page_size)
    except Exception as e:
        logger.error(f"재고통계 조회 실패: {e}")
        return {"total_anomalies": 0, "severity_counts": {}, "stock_items": [],
                "total": 0, "page": 1, "page_size": page_size, "total_pages": 1}



@router.get("/stats/abc")
async def get_abc_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
        days: int = 90, category: str | None = None,
):
    try:
        return SheetService.get_abc_stats(db, days, category)
    except Exception as e:
        logger.error(f"ABC분석 조회 실패: {e}")
        return {"items": []}



@router.get("/stats/demand")
async def get_demand_forecast(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
        forecast_days: int = 14, page: int = 1,
        page_size: int = 50, category: str | None = None,
):
    try:
        return SheetService.get_demand_stats(db, forecast_days, page, page_size, category)
    except Exception as e:
        logger.error(f"수요예측 조회 실패: {e}")
        return {"total": 0, "items": []}


@router.get("/stats/turnover")
async def get_turnover_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
        days: int = 30, page: int = 1,
        page_size: int = 50, category: str | None = None,
):
    try:
        return SheetService.get_turnover_stats(db, days, page, page_size, category)
    except Exception as e:
        logger.error(f"회전율 조회 실패: {e}")
        return {"total": 0, "items": []}


# ── 동기화 / 업로드 ────────────────────────────────────────────────────────

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


@router.post("/upload-excel")
async def upload_excel(
        current_user: Annotated[TokenData, Depends(require_admin)],
        file: UploadFile = File(...),
        sheet_type: str  = Form(...),
        db: Session      = Depends(get_db),
):
    if sheet_type not in _REQUIRED_COLS:
        raise HTTPException(400, "sheet_type은 master | sales | stock 중 하나여야 합니다.")

    fname = (file.filename or "").lower()
    if not (fname.endswith(".xlsx") or fname.endswith(".xls")):
        raise HTTPException(400, "xlsx 또는 xls 파일만 허용됩니다.")

    contents = await file.read()
    max_mb   = int(get_setting(db, "EXCEL_MAX_SIZE_MB", "50"))
    if len(contents) > max_mb * 1024 * 1024:
        raise HTTPException(400, f"파일 크기가 {max_mb}MB를 초과합니다.")

    suffix   = ".xlsx" if fname.endswith(".xlsx") else ".xls"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        df = pd.read_excel(tmp_path, dtype={"상품코드": str})
        df.columns = df.columns.str.strip()

        missing = [c for c in _REQUIRED_COLS[sheet_type] if c not in df.columns]
        if missing:
            raise HTTPException(422, f"필수 컬럼 누락: {missing}")
        if len(df) == 0:
            raise HTTPException(422, "파일에 데이터 행이 없습니다.")

        db_result = {"inserted": 0, "updated": 0, "skipped": 0}

        if sheet_type == "master":
            upsert_master_from_excel(df)
            db_result = SyncService.sync_master(db, df)

        elif sheet_type == "sales":
            if "날짜" in df.columns:
                df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce").dt.strftime("%Y-%m-%d")
            write_sales(df)
            db_result = SyncService.sync_sales(db, df)

        else:  # stock
            upsert_stock_from_excel(df)
            db_result = SyncService.sync_stock(db, df)

        total = len(df)
        logger.info(f"엑셀 업로드: type={sheet_type}, rows={total}, db={db_result}, user={current_user.username}")
        return {
            "status":     "success",
            "sheet_type": sheet_type,
            "total":      total,
            "inserted":   db_result.get("inserted", 0),
            "updated":    db_result.get("updated", 0),
            "skipped":    db_result.get("skipped", 0),
            "message":    f"{sheet_type} {total}건 처리 완료",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"엑셀 업로드 실패: {e}")
        raise HTTPException(500, f"업로드 처리 중 오류: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)