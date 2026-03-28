
import os
import tempfile
from typing import Annotated, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_router import get_current_user, require_admin, TokenData
from app.db.connection import get_db
from app.db.repository import get_setting
from app.db.models import Product, ProductStatus
from app.sheets.reader import read_product_master, read_sales, read_stock
from app.sheets.writer import upsert_master_from_excel, write_sales, upsert_stock_from_excel

router = APIRouter(prefix="/scm/sheets", tags=["sheets"])


class ProductUpdate(BaseModel):
    name:          Optional[str] = None
    category:      Optional[str] = None
    safety_stock:  Optional[int] = None
    status:        Optional[str] = None


@router.put("/products/{code}")
async def update_product(
        code: str,
        body: ProductUpdate,
        _: Annotated[TokenData, Depends(require_admin)],
        db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.code == code).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"상품을 찾을 수 없습니다: {code}")
    if body.name is not None:
        product.name = body.name
    if body.category is not None:
        product.category = body.category
    if body.safety_stock is not None:
        product.safety_stock = body.safety_stock
    if body.status is not None:
        try:
            product.status = ProductStatus(body.status.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"유효하지 않은 상태값: {body.status}")
    db.commit()
    db.refresh(product)
    return {
        "code": product.code,
        "name": product.name,
        "category": product.category,
        "safety_stock": product.safety_stock,
        "status": product.status.value.lower(),
    }


@router.get("/categories")
async def get_categories(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """상품마스터의 고유 카테고리 목록 반환."""
    try:
        df = read_product_master()
        col = next((c for c in ["카테고리", "category"] if c in df.columns), None)
        if col is None:
            return {"items": []}
        cats = sorted(df[col].dropna().unique().tolist())
        return {"items": [c for c in cats if c]}
    except Exception as e:
        logger.error(f"카테고리 목록 조회 실패: {e}")
        return {"items": []}


@router.get("/master")
async def get_master(
        current_user: Annotated[TokenData, Depends(require_admin)],
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        category: str | None = None,
        download: bool = False,
):

    try:
        df = read_product_master()

        # 검색 필터
        if search:
            mask = (
                    df["상품명"].str.contains(search, case=False, na=False) |
                    df["상품코드"].str.contains(search, case=False, na=False)
            )
            df = df[mask]

        # 카테고리 필터
        if category:
            col = next((c for c in ["카테고리", "category"] if c in df.columns), None)
            if col:
                df = df[df[col] == category]

        # 다운로드 요청: CSV 반환 (UTF-8 BOM으로 Excel 한글 정상 표시)
        if download:
            import io
            buf = io.BytesIO()
            buf.write(b'\xef\xbb\xbf')  # UTF-8 BOM
            df.to_csv(buf, index=False, encoding="utf-8")
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="text/csv; charset=utf-8-sig",
                headers={"Content-Disposition": 'attachment; filename="master.csv"'},
            )

        page_size = min(page_size, 200)   # 최대 200건 제한
        total = len(df)
        total_pages = max(1, (total + page_size - 1) // page_size)

        # 페이징
        start = (page - 1) * page_size
        end   = start + page_size
        page_df = df.iloc[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "items": page_df.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"상품마스터 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size,
                "total_pages": 0, "items": [], "error": str(e)}


@router.get("/sales")
async def get_sales(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30,
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
        search: str | None = None,
        download: bool = False,
):

    try:
        import pandas as pd
        df = read_sales()
        df["날짜"] = pd.to_datetime(df["날짜"])
        cutoff = df["날짜"].max() - pd.Timedelta(days=days)
        df = df[df["날짜"] >= cutoff].copy()

        if search and "상품코드" in df.columns:
            mask = df["상품코드"].astype(str).str.contains(search, case=False, na=False)
            if "상품명" in df.columns:
                mask = mask | df["상품명"].astype(str).str.contains(search, case=False, na=False)
            df = df[mask]

        if category and "카테고리" in df.columns:
            df = df[df["카테고리"] == category]

        df["날짜"] = df["날짜"].dt.strftime("%Y-%m-%d")

        if download:
            import io
            buf = io.BytesIO()
            buf.write(b'\xef\xbb\xbf')
            df.to_csv(buf, index=False, encoding="utf-8")
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="text/csv; charset=utf-8-sig",
                headers={"Content-Disposition": 'attachment; filename="sales.csv"'},
            )

        page_size   = min(page_size, 200)
        total       = len(df)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        page_df     = df.iloc[start:start + page_size]

        return {
            "total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages,
            "items": page_df.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"일별판매 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size,
                "total_pages": 0, "items": [], "error": str(e)}


@router.get("/stock")
async def get_stock(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
        search: str | None = None,
        download: bool = False,
):

    try:
        df = read_stock()

        if search and "상품코드" in df.columns:
            mask = df["상품코드"].astype(str).str.contains(search, case=False, na=False)
            if "상품명" in df.columns:
                mask = mask | df["상품명"].astype(str).str.contains(search, case=False, na=False)
            df = df[mask]

        if category and "카테고리" in df.columns:
            df = df[df["카테고리"] == category]

        if download:
            import io
            buf = io.BytesIO()
            buf.write(b'\xef\xbb\xbf')
            df.to_csv(buf, index=False, encoding="utf-8")
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="text/csv; charset=utf-8-sig",
                headers={"Content-Disposition": 'attachment; filename="stock.csv"'},
            )

        page_size   = min(page_size, 200)
        total       = len(df)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        page_df     = df.iloc[start:start + page_size]

        return {
            "total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages,
            "items": page_df.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"재고현황 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size,
                "total_pages": 0, "items": [], "error": str(e)}


@router.get("/stats/sales")
async def get_sales_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        period: str = "daily",  # daily | weekly | monthly
):

    try:
        import pandas as pd
        df = read_sales()
        df["날짜"] = pd.to_datetime(df["날짜"])

        if period == "daily":
            cutoff = df["날짜"].max() - pd.Timedelta(days=29)
            df = df[df["날짜"] >= cutoff]
            agg = (
                df.groupby("날짜")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index()
                .sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "weekly":
            cutoff = df["날짜"].max() - pd.Timedelta(weeks=12)
            df = df[df["날짜"] >= cutoff]
            df["주"] = df["날짜"].dt.to_period("W").dt.start_time
            agg = (
                df.groupby("주")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index()
                .rename(columns={"주": "날짜"})
                .sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "monthly":
            df["월"] = df["날짜"].dt.to_period("M").dt.start_time
            agg = (
                df.groupby("월")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index()
                .rename(columns={"월": "날짜"})
                .sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m")

        else:
            return {"error": "period는 daily/weekly/monthly 중 하나여야 합니다."}

        return {
            "period": period,
            "items": agg.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"판매 통계 조회 실패: {e}")
        return {"period": period, "items": [], "error": str(e)}




@router.get("/stats/stock")
async def get_stock_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
):
    try:
        import pandas as pd
        from app.db.connection import SessionLocal
        from app.db.repository import get_anomaly_logs

        df_stock  = read_stock()
        df_master = read_product_master()

        df = df_master.merge(df_stock, on="상품코드", how="left")

        df["현재재고"] = pd.to_numeric(df["현재재고"], errors="coerce").fillna(0).astype(int)

        # 재고 > 0 인 상품만 TOP 20
        stock_items = (
            df[df["현재재고"] > 0]
            .nlargest(20, "현재재고")[["상품코드", "상품명", "현재재고"]]
            .to_dict(orient="records")
        )

        db = SessionLocal()
        try:
            result = get_anomaly_logs(db, is_resolved=False, page=1, page_size=200)
            records = result["items"]
        finally:
            db.close()

        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "CHECK": 0}
        for r in records:
            sev = r.severity.value   # already uppercase from UpperCaseEnum
            if sev in severity_counts:
                severity_counts[sev] += 1

        return {
            "stock_items": stock_items,
            "severity_counts": severity_counts,
            "total_anomalies": len(records),
        }
    except Exception as e:
        logger.error(f"재고 통계 조회 실패: {e}")
        return {"stock_items": [], "severity_counts": {}, "error": str(e)}





@router.post("/sync")
async def sync_sheets(
        current_user: Annotated[TokenData, Depends(require_admin)],
):

    import asyncio
    from app.scheduler.jobs import sync_sheets_only

    asyncio.create_task(asyncio.to_thread(sync_sheets_only))
    logger.info(f"Sheets 동기화 트리거: {current_user.username}")
    return {"status": "triggered", "message": "데이터 동기화가 시작되었습니다."}



@router.get("/orders")
async def get_orders(
        current_user: Annotated[TokenData, Depends(require_admin)],
        status: str | None = None,
        days: int = 90,
        page: int = 1,
        page_size: int = 50,
):

    try:
        import pandas as pd
        from app.sheets.reader import read_orders
        df = read_orders()
        if df.empty:
            return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": []}

        if "발주일" in df.columns:
            df["발주일"] = pd.to_datetime(df["발주일"], errors="coerce")
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df["발주일"] >= cutoff].copy()
            df["발주일"] = df["발주일"].dt.strftime("%Y-%m-%d")

        if status:
            df = df[df["상태"] == status]

        total       = len(df)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        page_df     = df.iloc[start: start + page_size]

        return {
            "total": total, "page": page,
            "page_size": page_size, "total_pages": total_pages,
            "items": page_df.to_dict(orient="records"),
        }
    except Exception as e:
        logger.error(f"주문 조회 실패: {e}")
        return {"total": 0, "page": 1, "page_size": page_size, "total_pages": 0, "items": [], "error": str(e)}



@router.get("/stats/abc")
async def get_abc_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 90,
):
    try:
        import pandas as pd
        from app.analyzer.abc_analyzer import run_abc_analysis

        df_master = read_product_master()
        df_sales  = read_sales()
        items     = run_abc_analysis(df_master, df_sales, days=days)
        return {"days": days, "items": items}
    except Exception as e:
        logger.error(f"ABC 분석 조회 실패: {e}")
        return {"days": days, "items": [], "error": str(e)}


@router.get("/stats/demand")
async def get_demand_forecast(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        forecast_days: int = 14,
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
):
    try:
        page_size = min(page_size, 200)
        from app.analyzer.demand_forecaster import run_demand_forecast_all

        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()
        items     = run_demand_forecast_all(df_master, df_sales, df_stock, forecast_days=forecast_days)

        categories = sorted({i.get("category", "") for i in items if i.get("category")})

        if category:
            items = [i for i in items if i.get("category") == category]

        total       = len(items)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        page_items  = items[start:start + page_size]

        return {
            "forecast_days": forecast_days,
            "categories": categories,
            "total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages,
            "items": page_items,
        }
    except Exception as e:
        logger.error(f"수요 예측 조회 실패: {e}")
        return {"forecast_days": forecast_days, "categories": [], "total": 0,
                "page": 1, "page_size": page_size, "total_pages": 0,
                "items": [], "error": str(e)}


@router.get("/stats/turnover")
async def get_turnover_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30,
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
):
    try:
        page_size = min(page_size, 200)
        from app.analyzer.turnover_analyzer import calc_inventory_turnover

        df_master = read_product_master()
        df_sales  = read_sales()
        df_stock  = read_stock()
        items     = calc_inventory_turnover(df_master, df_sales, df_stock, days=days)

        categories = sorted({i.get("카테고리", "") for i in items if i.get("카테고리")})

        if category:
            items = [i for i in items if i.get("카테고리") == category]

        total       = len(items)
        total_pages = max(1, (total + page_size - 1) // page_size)
        start       = (page - 1) * page_size
        page_items  = items[start:start + page_size]

        return {
            "days": days,
            "categories": categories,
            "total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages,
            "items": page_items,
        }
    except Exception as e:
        logger.error(f"재고 회전율 조회 실패: {e}")
        return {"days": days, "categories": [], "total": 0,
                "page": 1, "page_size": page_size, "total_pages": 0,
                "items": [], "error": str(e)}


# --- 엑셀 업로드 ---

_REQUIRED_COLS: dict[str, list[str]] = {
    "master": ["상품코드"],
    "sales":  ["상품코드", "날짜", "판매수량"],
    "stock":  ["상품코드", "현재재고"],
}


@router.post("/upload-excel")
async def upload_excel(
        current_user: Annotated[TokenData, Depends(require_admin)],
        file: UploadFile = File(...),
        sheet_type: str  = Form(...),
        db: Session      = Depends(get_db),
):

    # 1. sheet_type 검증
    if sheet_type not in _REQUIRED_COLS:
        raise HTTPException(400, "sheet_type은 master | sales | stock 중 하나여야 합니다.")

    # 2. 확장자 검증
    fname = (file.filename or "").lower()
    if not (fname.endswith(".xlsx") or fname.endswith(".xls")):
        raise HTTPException(400, "xlsx 또는 xls 파일만 허용됩니다.")

    # 3. 파일 읽기 + 크기 검증
    contents = await file.read()
    max_mb   = int(get_setting(db, "EXCEL_MAX_SIZE_MB", "50"))
    if len(contents) > max_mb * 1024 * 1024:
        raise HTTPException(400, f"파일 크기가 {max_mb} MB를 초과합니다. (현재: {len(contents) / 1024 / 1024:.1f} MB)")

    # 4. 임시 파일 파싱
    suffix = ".xlsx" if fname.endswith(".xlsx") else ".xls"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        df = pd.read_excel(tmp_path, dtype={"상품코드": str})
        df.columns = df.columns.str.strip()

        # 5. 필수 컬럼 검증
        missing = [c for c in _REQUIRED_COLS[sheet_type] if c not in df.columns]
        if missing:
            raise HTTPException(422, f"필수 컬럼 누락: {missing}")

        total = len(df)
        if total == 0:
            raise HTTPException(422, "파일에 데이터 행이 없습니다.")

        # 6. Google Sheets 반영
        if sheet_type == "master":
            upsert_master_from_excel(df)
        elif sheet_type == "sales":
            if "날짜" in df.columns:
                df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce").dt.strftime("%Y-%m-%d")
            write_sales(df)
        else:  # stock
            upsert_stock_from_excel(df)

        logger.info(f"엑셀 업로드 완료: sheet_type={sheet_type}, rows={total}, user={current_user.username}")
        return {
            "sheet_type": sheet_type,
            "total":      total,
            "inserted":   total,
            "updated":    0,
            "message":    f"{sheet_type} {total}건 처리 완료",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"엑셀 업로드 처리 실패: {e}")
        raise HTTPException(500, f"업로드 처리 중 오류: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)