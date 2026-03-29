from __future__ import annotations

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