from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.api.auth_router import TokenData, get_current_user, require_admin
from app.cache.redis_client import cache_get
from app.db.connection import SessionLocal, get_db
from app.db.sync import make_params_hash
from sqlalchemy.orm import Session

router = APIRouter(prefix="/scm/sheets", tags=["sheets"])

ANALYSIS_CACHE_TTL = 60 * 30   # Redis 30분


# 데이터 조회(DB)
@router.get("/master")
async def get_master(
        current_user: Annotated[TokenData, Depends(require_admin)],
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        category: str | None = None,
        db: Session = Depends(get_db),
):
    try:
        from app.db.repository import get_products_paginated
        page_size = min(page_size, 200)
        result = get_products_paginated(db, page=page, page_size=page_size,
                                        search=search, category=category)
        return {
            "total":       result["total"],
            "page":        result["page"],
            "page_size":   result["page_size"],
            "total_pages": max(1, (result["total"] + page_size - 1) // page_size),
            "items": [
                {
                    "상품코드":     p.code,
                    "상품명":       p.name,
                    "카테고리":     p.category or "",
                    "안전재고기준": p.safety_stock,
                    "상태":        p.status.value,
                    "updated_at":  str(p.updated_at),
                }
                for p in result["items"]
            ],
        }
    except Exception as exc:
        logger.error(f"[상품마스터] 조회 실패: {exc}")
        raise HTTPException(status_code=500, detail=f"상품 마스터 조회 중 오류 발생: {exc}")


@router.get("/sales")
async def get_sales(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30,
        page: int = 1,
        page_size: int = 50,
        db: Session = Depends(get_db),
):
    try:
        from app.db.repository import get_daily_sales_range
        page_size   = min(page_size, 200)
        end         = date.today()
        start       = end - timedelta(days=days)
        all_sales   = get_daily_sales_range(db, start=start, end=end)

        total       = len(all_sales)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page_items  = all_sales[(page - 1) * page_size : page * page_size]

        return {
            "total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages,
            "items": [
                {
                    "날짜":    str(s.date),
                    "상품코드": s.product_code,
                    "판매수량": s.qty,
                    "매출액":  s.revenue,
                }
                for s in page_items
            ],
        }
    except Exception as exc:
        logger.error(f"[일별매출] 조회 실패: {exc}")
        raise HTTPException(status_code=500, detail=f"일별 매출 조회 중 오류 발생: {exc}")


@router.get("/stock")
async def get_stock(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        page: int = 1,
        page_size: int = 50,
        db: Session = Depends(get_db),
):
    try:
        from app.db.repository import get_all_stock_levels
        page_size  = min(page_size, 200)
        all_stocks = get_all_stock_levels(db)

        total       = len(all_stocks)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page_items  = all_stocks[(page - 1) * page_size : page * page_size]

        return {
            "total": total, "page": page, "page_size": page_size,
            "total_pages": total_pages,
            "items": [
                {
                    "상품코드":     s.product_code,
                    "현재재고":     s.current_stock,
                    "입고예정일":   str(s.restock_date) if s.restock_date else "",
                    "입고예정수량": s.restock_qty or 0,
                    "updated_at":  str(s.updated_at),
                }
                for s in page_items
            ],
        }
    except Exception as exc:
        logger.error(f"[재고현황] 조회 실패: {exc}")
        raise HTTPException(status_code=500, detail=f"재고 현황 조회 중 오류 발생: {exc}")



# 분석 (캐시 → Celery)
def _dispatch_or_cache(analysis_type: str, params: dict, task_func, cache_key: str):

    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug(f"[{analysis_type}] Redis 캐시 히트")
        return {"from_cache": True, "items": cached}

    task = task_func.delay(**params)
    logger.info(f"[{analysis_type}] 태스크 발행 — task_id={task.id}")
    return {"task_id": task.id, "status": "queued", "message": "분석 요청이 접수되었습니다."}


@router.get("/stats/demand")
async def get_demand_forecast(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        forecast_days: int = 14,
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
):
    try:
        from app.celery_app.tasks import run_demand_forecast
        params_hash = make_params_hash({"forecast_days": forecast_days, "category": category})
        cache_key   = f"analysis:demand:{params_hash}"
        result      = _dispatch_or_cache(
            "수요예측",
            {"forecast_days": forecast_days, "category": category},
            run_demand_forecast,
            cache_key,
        )

        if "task_id" in result:
            return result

        # 페이지네이션
        items       = result["items"]
        page_size   = min(page_size, 200)
        total       = len(items)
        start       = (page - 1) * page_size
        return {
            "forecast_days": forecast_days,
            "from_cache":    True,
            "total": total,  "page": page, "page_size": page_size,
            "total_pages":   max(1, (total + page_size - 1) // page_size),
            "items":         items[start : start + page_size],
        }
    except Exception as exc:
        logger.error(f"[수요예측] 엔드포인트 오류: {exc}")
        raise HTTPException(status_code=500, detail=f"수요 예측 처리 중 오류 발생: {exc}")


@router.get("/stats/turnover")
async def get_turnover_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 30,
        page: int = 1,
        page_size: int = 50,
        category: str | None = None,
):
    try:
        from app.celery_app.tasks import run_turnover_analysis
        params_hash = make_params_hash({"days": days, "category": category})
        cache_key   = f"analysis:turnover:{params_hash}"
        result      = _dispatch_or_cache(
            "회전율",
            {"days": days, "category": category},
            run_turnover_analysis,
            cache_key,
        )

        if "task_id" in result:
            return result

        items     = result["items"]
        page_size = min(page_size, 200)
        total     = len(items)
        start     = (page - 1) * page_size
        return {
            "days":        days,
            "from_cache":  True,
            "total": total, "page": page, "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "items":       items[start : start + page_size],
        }
    except Exception as exc:
        logger.error(f"[회전율] 엔드포인트 오류: {exc}")
        raise HTTPException(status_code=500, detail=f"재고 회전율 처리 중 오류 발생: {exc}")


@router.get("/stats/abc")
async def get_abc_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        days: int = 90,
):
    try:
        from app.celery_app.tasks import run_abc_analysis_task
        params_hash = make_params_hash({"days": days})
        cache_key   = f"analysis:abc:{params_hash}"
        result      = _dispatch_or_cache(
            "ABC분석",
            {"days": days},
            run_abc_analysis_task,
            cache_key,
        )

        if "task_id" in result:
            return result

        return {"days": days, "from_cache": True, "items": result["items"]}
    except Exception as exc:
        logger.error(f"[ABC분석] 엔드포인트 오류: {exc}")
        raise HTTPException(status_code=500, detail=f"ABC 분석 처리 중 오류 발생: {exc}")


# --- ETC ---

    # 판매 통계 (DB)
@router.get("/stats/sales")
async def get_sales_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        period: str = "daily",
        db: Session = Depends(get_db),
):

    try:
        import pandas as pd
        from app.db.repository import get_daily_sales_range

        end    = date.today()
        start  = end - timedelta(days=365)
        sales  = get_daily_sales_range(db, start=start, end=end)

        if not sales:
            return {"period": period, "items": []}

        df = pd.DataFrame([
            {"날짜": s.date, "판매수량": s.qty, "매출액": s.revenue}
            for s in sales
        ])
        df["날짜"] = pd.to_datetime(df["날짜"])

        if period == "daily":
            cutoff = df["날짜"].max() - pd.Timedelta(days=29)
            df     = df[df["날짜"] >= cutoff]
            agg    = (
                df.groupby("날짜")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index().sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "weekly":
            cutoff = df["날짜"].max() - pd.Timedelta(weeks=12)
            df     = df[df["날짜"] >= cutoff]
            df["주"] = df["날짜"].dt.to_period("W").dt.start_time
            agg    = (
                df.groupby("주")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index().rename(columns={"주": "날짜"}).sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m-%d")

        elif period == "monthly":
            df["월"] = df["날짜"].dt.to_period("M").dt.start_time
            agg    = (
                df.groupby("월")
                .agg(판매수량=("판매수량", "sum"), 매출액=("매출액", "sum"))
                .reset_index().rename(columns={"월": "날짜"}).sort_values("날짜")
            )
            agg["날짜"] = agg["날짜"].dt.strftime("%Y-%m")

        else:
            raise HTTPException(status_code=400, detail="period는 daily/weekly/monthly 중 하나여야 합니다.")

        return {"period": period, "items": agg.to_dict(orient="records")}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[판매통계] 조회 실패: {exc}")
        raise HTTPException(status_code=500, detail=f"판매 통계 조회 중 오류 발생: {exc}")



@router.get("/stats/stock")
async def get_stock_stats(
        current_user: Annotated[TokenData, Depends(get_current_user)],
        db: Session = Depends(get_db),
):
    try:
        from app.db.repository import get_all_stock_levels, get_anomaly_logs

        stocks = get_all_stock_levels(db)
        stock_items = sorted(
            [{"상품코드": s.product_code, "현재재고": s.current_stock} for s in stocks if s.current_stock > 0],
            key=lambda x: x["현재재고"], reverse=True
        )[:20]

        records        = get_anomaly_logs(db, is_resolved=False, limit=200)
        severity_counts = {"critical": 0, "high": 0, "check": 0, "medium": 0, "low": 0}
        for r in records:
            sev = r.severity.value
            if sev in severity_counts:
                severity_counts[sev] += 1

        return {
            "stock_items":     stock_items,
            "severity_counts": severity_counts,
            "total_anomalies": len(records),
        }
    except Exception as exc:
        logger.error(f"[재고통계] 조회 실패: {exc}")
        raise HTTPException(status_code=500, detail=f"재고 통계 조회 중 오류 발생: {exc}")



    # DB 동기화
@router.post("/sync")
async def sync_sheets(
        current_user: Annotated[TokenData, Depends(require_admin)],
):
    try:
        from app.celery_app.tasks import run_crawler
        task = run_crawler.delay()
        logger.info(f"[동기화] DB 동기화 시작: user={current_user.username}, task_id={task.id}")
        return {"status": "triggered", "task_id": task.id, "message": "데이터 동기화가 시작되었습니다."}
    except Exception as exc:
        logger.error(f"[동기화] DB 동기화 작업 실패: {exc}")
        raise HTTPException(status_code=500, detail=f"동기화 작업 중 오류 발생: {exc}")


    # 파일 업로드 처리
import tempfile
import os
from fastapi import UploadFile, File, Form

_ALLOWED_EXTENSIONS = {".xlsx"}
_MAX_FILE_SIZE = 50 * 1024 * 1024   # 50 MB


def _validate_excel_file(file: UploadFile) -> None:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. xlsx 파일만 허용됩니다. (받은 확장자: {ext or '없음'})"
        )


def _parse_master_sheet(file_path: str) -> list[dict]:
    import pandas as pd

    try:
        df = pd.read_excel(file_path, sheet_name="상품마스터", dtype={"상품코드": str})
    except Exception:
        try:
            df = pd.read_excel(file_path, sheet_name=0, dtype={"상품코드": str})
        except Exception as exc:
            raise ValueError(f"엑셀 파일을 읽을 수 없습니다: {exc}")

    df.columns = df.columns.str.strip()

    if "상품코드" not in df.columns or "상품명" not in df.columns:
        raise ValueError("필수 컬럼 누락: '상품코드', '상품명' 컬럼이 있어야 합니다.")

    df = df.dropna(subset=["상품코드"])
    df["상품코드"] = df["상품코드"].astype(str).str.strip()
    df = df[df["상품코드"] != ""]

    records = []
    for _, row in df.iterrows():
        status = str(row.get("상태", "active")).strip().lower()
        if status not in ("active", "inactive", "sample"):
            status = "active"
        records.append({
            "code":         str(row["상품코드"]),
            "name":         str(row.get("상품명", "")),
            "category":     str(row.get("카테고리", "")) if pd.notna(row.get("카테고리")) else None,
            "safety_stock": int(row.get("안전재고기준", 0)) if pd.notna(row.get("안전재고기준")) else 0,
            "status":       status,
            "source":       "excel",
        })
    return records



def _parse_sales_for_db(file_path: str) -> list[dict]:
    from app.crawler.excel_parser import parse_sales_sheet

    df = parse_sales_sheet(file_path)

    required = {"날짜", "상품코드", "판매수량"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"일별판매 시트 필수 컬럼 누락: {missing}")

    df["상품코드"] = df["상품코드"].astype(str).str.strip()
    df = df.dropna(subset=["날짜", "상품코드"])

    return [
        {
            "date":         str(row["날짜"]),
            "product_code": str(row["상품코드"]),
            "qty":          int(row.get("판매수량", 0)),
            "revenue":      float(row.get("매출액", 0.0)) if pd.notna(row.get("매출액")) else 0.0,
        }
        for _, row in df.iterrows()
    ]


def _parse_stock_for_db(file_path: str) -> list[dict]:
    import pandas as pd
    from app.crawler.excel_parser import parse_stock_sheet

    df = parse_stock_sheet(file_path)

    if "상품코드" not in df.columns or "현재재고" not in df.columns:
        raise ValueError("재고현황 시트 필수 컬럼 누락: '상품코드', '현재재고'")

    df["상품코드"] = df["상품코드"].astype(str).str.strip()
    df = df.dropna(subset=["상품코드"])

    return [
        {
            "product_code":  str(row["상품코드"]),
            "current_stock": int(row.get("현재재고", 0)) if pd.notna(row.get("현재재고")) else 0,
            "restock_date":  str(row["입고예정일"]) if pd.notna(row.get("입고예정일")) else None,
            "restock_qty":   int(row["입고예정수량"]) if pd.notna(row.get("입고예정수량")) else None,
        }
        for _, row in df.iterrows()
    ]


@router.post("/upload-excel")
async def upload_excel(
        current_user: Annotated[TokenData, Depends(require_admin)],
        file: UploadFile = File(...),
        sheet_type: str  = Form(...),   # master / sales / stock
        db: Session = Depends(get_db),
):

    if sheet_type not in ("master", "sales", "stock"):
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 sheet_type입니다: '{sheet_type}'. master / sales / stock 중 하나여야 합니다."
        )

    try:
        _validate_excel_file(file)
    except HTTPException:
        raise

    # 파일 크기 확인
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"파일 크기 초과: 최대 50MB 허용 (받은 크기: {len(content) / 1024 / 1024:.1f}MB)"
        )

    # 임시 파일에 저장 후 파싱
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        logger.info(
            f"[Excel업로드] 파일 수신: filename={file.filename}, "
            f"sheet_type={sheet_type}, size={len(content)}bytes, user={current_user.username}"
        )

        from app.db.sync import bulk_upsert_products, bulk_upsert_daily_sales, bulk_upsert_stock_levels

        if sheet_type == "master":
            records = _parse_master_sheet(tmp_path)
            result  = bulk_upsert_products(db, records)

        elif sheet_type == "sales":
            records = _parse_sales_for_db(tmp_path)
            result  = bulk_upsert_daily_sales(db, records)

        else:  # stock
            records = _parse_stock_for_db(tmp_path)
            result  = bulk_upsert_stock_levels(db, records)

        logger.info(
            f"[Excel업로드] 완료: sheet_type={sheet_type}, "
            f"total={len(records)}, result={result}"
        )
        return {
            "status":     "success",
            "sheet_type": sheet_type,
            "total":      len(records),
            **result,
        }

    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning(f"[Excel업로드] 파싱 오류: {exc}")
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(f"[Excel업로드] 처리 실패: {exc}")
        raise HTTPException(status_code=500, detail=f"Excel 업로드 처리 중 오류 발생: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as clean_exc:
                logger.warning(f"[Excel업로드] 임시 파일 삭제 실패 : {clean_exc}")
