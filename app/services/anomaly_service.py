from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from app.db.repository import get_anomaly_logs, resolve_anomaly
from app.utils.severity import norm


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
                    "detected_at":         str(r.detected_at),
                    "product_code":        r.product_code,
                    "product_name":        r.product_name,
                    "category":            r.category,
                    "anomaly_type":        r.anomaly_type.value  if hasattr(r.anomaly_type,  "value") else str(r.anomaly_type),
                    "current_stock":       r.current_stock,
                    "daily_avg_sales":     r.daily_avg_sales,
                    "days_until_stockout": r.days_until_stockout,
                    "severity":            r.severity.value if hasattr(r.severity, "value") else str(r.severity),
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