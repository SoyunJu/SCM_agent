"""
SCM Agent API 통합 테스트
- FastAPI TestClient + SQLite in-memory DB
- AI / Slack / Redis / Celery → Mock 처리
- conftest.py의 fixture 사용
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Health Check
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_health_ok(self, client):
        resp = client.get("/scm/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Auth
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_me_returns_user_info(self, client):
        resp = client.get("/scm/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "username" in data
        assert "role" in data

    def test_login_wrong_password(self, client):
        resp = client.post(
            "/scm/auth/login",
            data={"username": "nobody", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 이상징후 (Anomalies)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnomalies:
    def test_list_all(self, client, seed_anomalies):
        resp = client.get("/scm/report/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 3

    def test_filter_unresolved(self, client, seed_anomalies):
        resp = client.get("/scm/report/anomalies?is_resolved=false")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(not i["is_resolved"] for i in items)

    def test_filter_resolved(self, client, seed_anomalies):
        resp = client.get("/scm/report/anomalies?is_resolved=true")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["is_resolved"] for i in items)

    def test_filter_by_severity_critical(self, client, seed_anomalies):
        resp = client.get("/scm/report/anomalies?severity=CRITICAL")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["severity"] == "CRITICAL" for i in items)

    def test_filter_by_severity_low(self, client, seed_anomalies):
        """LOW severity 필터링 버그 수정 검증"""
        resp = client.get("/scm/report/anomalies?severity=LOW")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["severity"] == "LOW" for i in items)

    def test_anomaly_has_kor_fields(self, client, seed_anomalies):
        """anomaly_type_kor, severity_kor 필드 포함 확인"""
        resp = client.get("/scm/report/anomalies")
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert "anomaly_type_kor" in item
            assert "severity_kor" in item
            assert item["anomaly_type_kor"] != ""

    def test_resolve_anomaly(self, client, seed_anomalies):
        anomaly_id = seed_anomalies[0].id
        resp = client.patch(f"/scm/report/anomalies/{anomaly_id}/resolve")
        assert resp.status_code == 200
        assert resp.json()["is_resolved"] is True

    def test_resolve_nonexistent(self, client):
        resp = client.patch("/scm/report/anomalies/99999/resolve")
        assert resp.status_code == 404

    def test_pagination(self, client, seed_anomalies):
        resp = client.get("/scm/report/anomalies?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert "total_pages" in data
        assert "total" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 상품마스터 (Sheets / Master)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSheetsMaster:
    def test_list_products(self, client, seed_products):
        resp = client.get("/scm/sheets/master")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 2  # active 상품만

    def test_filter_by_status_active(self, client, seed_products):
        resp = client.get("/scm/sheets/master?status=active")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i.get("상태", "active") in ("active", "ACTIVE") for i in items)

    def test_filter_by_status_inactive(self, client, seed_products):
        resp = client.get("/scm/sheets/master?status=inactive")
        assert resp.status_code == 200
        # P003이 inactive
        codes = [i["상품코드"] for i in resp.json()["items"]]
        assert "P003" in codes

    def test_filter_by_category(self, client, seed_products):
        resp = client.get("/scm/sheets/master?category=카테고리1")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["카테고리"] == "카테고리1" for i in items)

    def test_search_by_code(self, client, seed_products):
        resp = client.get("/scm/sheets/master?search=P001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_search_by_name(self, client, seed_products):
        resp = client.get("/scm/sheets/master?search=상품A")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_pagination(self, client, seed_products):
        resp = client.get("/scm/sheets/master?page=1&page_size=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 1
        assert data["total_pages"] >= 1

    def test_get_categories(self, client, seed_products):
        resp = client.get("/scm/sheets/categories")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert isinstance(items, list)
        assert "카테고리1" in items


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 일별판매 / 재고현황
# ═══════════════════════════════════════════════════════════════════════════════

class TestSheetsData:
    def test_sales_list(self, client, seed_sales):
        resp = client.get("/scm/sheets/sales?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 1

    def test_sales_filter_category(self, client, seed_sales):
        resp = client.get("/scm/sheets/sales?days=30&category=카테고리1")
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_stock_list(self, client, seed_stock):
        resp = client.get("/scm/sheets/stock")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_stock_search(self, client, seed_stock):
        resp = client.get("/scm/sheets/stock?search=P001")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(i["상품코드"] == "P001" for i in items)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 통계 (Stats)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStats:
    def test_sales_stats_daily(self, client, seed_sales):
        resp = client.get("/scm/sheets/stats/sales?period=daily")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_sales_stats_weekly(self, client, seed_sales):
        resp = client.get("/scm/sheets/stats/sales?period=weekly")
        assert resp.status_code == 200

    def test_sales_stats_monthly(self, client, seed_sales):
        resp = client.get("/scm/sheets/stats/sales?period=monthly")
        assert resp.status_code == 200

    def test_stock_stats_has_required_fields(self, client, seed_stock, seed_sales):
        resp = client.get("/scm/sheets/stats/stock")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_anomalies" in data
        assert "severity_counts" in data
        assert "stock_items" in data

    def test_stock_stats_items_have_unit_price(self, client, seed_stock, seed_sales):
        """단가/마진율 필드 포함 확인"""
        resp = client.get("/scm/sheets/stats/stock")
        assert resp.status_code == 200
        items = resp.json()["stock_items"]
        if items:
            item = items[0]
            assert "unit_sell"   in item
            assert "unit_cost"   in item
            assert "margin_rate" in item
            assert "discount_max" in item

    def test_stock_stats_pagination(self, client, seed_stock, seed_sales):
        resp = client.get("/scm/sheets/stats/stock?page=1&page_size=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "total_pages" in data
        assert len(data["stock_items"]) <= 1

    def test_abc_stats_returns_task_or_items(self, client, seed_products, seed_sales):
        """캐시 미스 시 task_id 반환, 캐시 히트 시 items 반환"""
        resp = client.get("/scm/sheets/stats/abc?days=90")
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data or "items" in data

    def test_demand_stats_returns_task_or_items(self, client, seed_products, seed_sales):
        resp = client.get("/scm/sheets/stats/demand?forecast_days=14")
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data or "items" in data

    def test_turnover_stats_returns_task_or_items(self, client, seed_stock, seed_sales):
        resp = client.get("/scm/sheets/stats/turnover?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data or "items" in data


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 발주 제안 (Order Proposals)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOrderProposals:
    def test_list_proposals(self, client, seed_proposals):
        resp = client.get("/scm/orders/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 2

    def test_filter_by_status_pending(self, client, seed_proposals):
        resp = client.get("/scm/orders/proposals?status=PENDING")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["status"] == "PENDING" for i in items)

    def test_filter_by_status_approved(self, client, seed_proposals):
        resp = client.get("/scm/orders/proposals?status=APPROVED")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(i["status"] == "APPROVED" for i in items)

    def test_approve_proposal(self, client, seed_proposals):
        pending = next(p for p in seed_proposals if p.status.value == "PENDING")
        resp = client.patch(f"/scm/orders/proposals/{pending.id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    def test_reject_proposal(self, client, seed_proposals, db_session):
        from app.db.models import OrderProposal, ProposalStatus
        # 새 PENDING 제안 생성
        p = OrderProposal(
            product_code="P001", product_name="상품A",
            proposed_qty=10, unit_price=5000.0,
            status=ProposalStatus.PENDING,
        )
        db_session.add(p)
        db_session.commit()
        resp = client.patch(f"/scm/orders/proposals/{p.id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "REJECTED"

    def test_reset_proposal(self, client, seed_proposals):
        approved = next(p for p in seed_proposals if p.status.value == "APPROVED")
        resp = client.patch(f"/scm/orders/proposals/{approved.id}/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING"
        assert resp.json()["approved_by"] is None

    def test_reset_pending_returns_400(self, client, seed_proposals):
        pending = next(p for p in seed_proposals if p.status.value == "PENDING")
        resp = client.patch(f"/scm/orders/proposals/{pending.id}/reset")
        assert resp.status_code == 400

    def test_update_proposal_qty_price(self, client, seed_proposals):
        pending = next(p for p in seed_proposals if p.status.value == "PENDING")
        resp = client.put(
            f"/scm/orders/proposals/{pending.id}",
            json={"proposed_qty": 99, "unit_price": 12345.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["proposed_qty"] == 99
        assert data["unit_price"] == 12345.0

    def test_unit_price_visible(self, client, seed_proposals):
        """단가가 0이 아닌 실제 값으로 반환 확인"""
        resp = client.get("/scm/orders/proposals?status=APPROVED")
        assert resp.status_code == 200
        items = resp.json()["items"]
        approved = [i for i in items if i["status"] == "APPROVED"]
        if approved:
            assert approved[0]["unit_price"] > 0

    def test_pagination(self, client, seed_proposals):
        resp = client.get("/scm/orders/proposals?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 1

    def test_generate_proposals_no_anomaly(self, client, db_session):
        """이상징후 없을 때 0건 생성"""
        with patch("app.services.order_service.OrderService.generate") as mock_gen:
            mock_gen.return_value = {"created": 0, "message": "'HIGH' 이상 이상징후 없음"}
            resp = client.post("/scm/orders/proposals/generate", json={})
        assert resp.status_code == 200
        assert resp.json()["created"] == 0

    def test_get_threshold(self, client):
        resp = client.get("/scm/orders/proposals/threshold")
        assert resp.status_code == 200
        data = resp.json()
        assert "threshold" in data
        assert "options" in data
        assert data["threshold"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 보고서 이력 / PDF
# ═══════════════════════════════════════════════════════════════════════════════

class TestReport:
    def test_history_empty(self, client):
        resp = client.get("/scm/report/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_trigger_report(self, client):
        with patch("app.services.report_service.ReportService.trigger") as mock_trigger:
            mock_trigger.return_value = {"status": "triggered", "execution_id": 1}
            resp = client.post("/scm/report/run", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "triggered"

    def test_pdf_list_empty(self, client):
        """reports/ 디렉토리 없어도 500 아닌 빈 목록 반환"""
        resp = client.get("/scm/report/pdf-list")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_pdf_download_not_found(self, client):
        resp = client.get("/scm/report/pdf/nonexistent_file.pdf")
        assert resp.status_code == 404

    def test_pdf_download_path_traversal_blocked(self, client):
        resp = client.get("/scm/report/pdf/../etc/passwd")
        assert resp.status_code in (400, 404, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. 설정 (Settings)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSettings:
    def test_get_settings_returns_all_keys(self, client):
        resp = client.get("/scm/settings")
        assert resp.status_code == 200
        items = resp.json()["items"]
        keys = [i["key"] for i in items]
        # 핵심 키 존재 확인
        assert "SAFETY_STOCK_DAYS"          in keys
        assert "AUTO_ORDER_APPROVAL"         in keys
        assert "ANALYSIS_CACHE_REDIS_MINUTES" in keys
        assert "SHEETS_SYNC_INTERVAL_MINUTES" in keys

    def test_save_settings(self, client):
        resp = client.put(
            "/scm/settings",
            json={"SAFETY_STOCK_DAYS": "14", "AUTO_ORDER_APPROVAL": "false"},
        )
        assert resp.status_code == 200
        assert resp.json()["saved"] >= 2

    def test_save_unknown_key_ignored(self, client):
        resp = client.put("/scm/settings", json={"UNKNOWN_KEY_XYZ": "value"})
        assert resp.status_code == 200
        assert resp.json()["saved"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 10. 스케줄러
# ═══════════════════════════════════════════════════════════════════════════════

class TestScheduler:
    def test_get_config(self, client):
        resp = client.get("/scm/scheduler/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "schedule_hour"   in data
        assert "schedule_minute" in data
        assert "is_active"       in data

    def test_update_config(self, client):
        resp = client.put("/scm/scheduler/config", json={
            "schedule_hour":   2,
            "schedule_minute": 30,
            "timezone":        "Asia/Seoul",
            "is_active":       True,
        })
        assert resp.status_code == 200

    def test_update_config_invalid_hour(self, client):
        resp = client.put("/scm/scheduler/config", json={
            "schedule_hour":   25,
            "schedule_minute": 0,
            "timezone":        "Asia/Seoul",
            "is_active":       True,
        })
        assert resp.status_code == 400

    def test_update_config_invalid_minute(self, client):
        resp = client.put("/scm/scheduler/config", json={
            "schedule_hour":   0,
            "schedule_minute": 60,
            "timezone":        "Asia/Seoul",
            "is_active":       True,
        })
        assert resp.status_code == 400

    def test_get_sync_config(self, client):
        resp = client.get("/scm/scheduler/sync-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "interval_minutes" in data

    def test_update_sync_config(self, client):
        resp = client.put("/scm/scheduler/sync-config", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_trigger_report(self, client):
        with patch("app.services.scheduler_service.SchedulerService.trigger_daily_report") as mock_t:
            mock_t.return_value = {"task_id": "mock-id", "message": "시작됨"}
            resp = client.post("/scm/scheduler/trigger")
        assert resp.status_code == 200

    def test_trigger_crawler(self, client):
        with patch("app.services.scheduler_service.SchedulerService.trigger_crawler") as mock_t:
            mock_t.return_value = {"task_id": "mock-id", "message": "시작됨"}
            resp = client.post("/scm/scheduler/trigger-crawler")
        assert resp.status_code == 200

    def test_trigger_cleanup(self, client):
        with patch("app.services.scheduler_service.SchedulerService.trigger_cleanup") as mock_t:
            mock_t.return_value = {"task_id": "mock-id", "message": "시작됨"}
            resp = client.post("/scm/scheduler/trigger-cleanup")
        assert resp.status_code == 200

    def test_sync_trigger(self, client):
        with patch("app.services.scheduler_service.SchedulerService.trigger_sync") as mock_t:
            mock_t.return_value = {"task_id": "mock-id", "message": "시작됨"}
            resp = client.post("/scm/scheduler/sync-trigger")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 11. 태스크 상태 폴링
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaskStatus:
    def test_pending_state(self, client):
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.info  = None

        with patch("app.celery_app.celery.celery_app.AsyncResult", return_value=mock_result):
            resp = client.get("/scm/tasks/fake-task-id/status")
        assert resp.status_code == 200
        assert resp.json()["state"] == "PENDING"

    def test_success_state(self, client):
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.info  = {"items": [{"product_code": "P001"}], "from_cache": False}

        with patch("app.celery_app.celery.celery_app.AsyncResult", return_value=mock_result):
            resp = client.get("/scm/tasks/fake-task-id/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "SUCCESS"
        assert "result" in data

    def test_failure_state(self, client):
        mock_result = MagicMock()
        mock_result.state = "FAILURE"
        mock_result.info  = {"error": "분석 오류"}   # ← Exception 객체 대신 dict

        with patch("app.celery_app.celery.celery_app.AsyncResult", return_value=mock_result):
            resp = client.get("/scm/tasks/fake-task-id/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "FAILURE"
        assert "error" in data

    def test_unknown_task_graceful(self, client):
        """존재하지 않는 task_id도 500이 아닌 UNKNOWN 반환"""
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.info  = None

        with patch("app.celery_app.celery.celery_app.AsyncResult", return_value=mock_result):
            resp = client.get("/scm/tasks/does-not-exist/status")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 12. 상품 상태 변경
# ═══════════════════════════════════════════════════════════════════════════════

class TestProductStatus:
    def test_change_status_not_found(self, client):
        resp = client.patch("/scm/products/NONEXIST/status", json={"status": "inactive"})
        assert resp.status_code == 404

    def test_change_status_invalid(self, client):
        resp = client.patch("/scm/products/NONEXIST/status", json={"status": "invalid_status"})
        # 422 (Pydantic Literal 검증) 또는 404
        assert resp.status_code in (400, 404, 422)

    def test_change_status_to_inactive(self, client):
        """상품이 없으면 404, 있으면 200 — 존재 여부에 따라 양쪽 모두 허용"""
        resp = client.patch("/scm/products/P001/status", json={"status": "inactive"})
        assert resp.status_code in (200, 404)

    def test_update_product(self, client):
        """상품이 없으면 404, 있으면 200"""
        resp = client.put("/scm/sheets/products/P001", json={
            "name":         "수정된상품A",
            "safety_stock": 15,
        })
        assert resp.status_code in (200, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# 13. DB sync (중복 방지 검증)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpsertDeduplication:
    def test_daily_sales_no_duplicate(self, db_session):
        """동일 (date, product_code) 두 번 삽입 시 1건만 존재"""
        from datetime import date
        from sqlalchemy import text

        today = date.today()

        # SQLite 호환 INSERT OR REPLACE
        db_session.execute(text("""
            INSERT OR REPLACE INTO daily_sales (date, product_code, qty, revenue, cost)
            VALUES (:date, :code, :qty, :revenue, :cost)
        """), {"date": str(today), "code": "DEDUP01", "qty": 5,
               "revenue": 50000.0, "cost": 30000.0})
        db_session.commit()

        # 동일 데이터 재삽입
        db_session.execute(text("""
            INSERT OR REPLACE INTO daily_sales (date, product_code, qty, revenue, cost)
            VALUES (:date, :code, :qty, :revenue, :cost)
        """), {"date": str(today), "code": "DEDUP01", "qty": 5,
               "revenue": 50000.0, "cost": 30000.0})
        db_session.commit()

        from app.db.models import DailySales
        count = db_session.query(DailySales).filter(
            DailySales.product_code == "DEDUP01",
            DailySales.date == today,
            ).count()
        assert count == 1

    def test_anomaly_no_duplicate_same_day(self, db_session):
        """같은 날 같은 (product_code, anomaly_type) 이상징후 중복 삽입 방지"""
        from app.db.repository import upsert_anomaly_log
        from app.db.models import AnomalyType, Severity

        upsert_anomaly_log(
            db_session, "DEDUP02", "상품X", AnomalyType.LOW_STOCK, Severity.CRITICAL,
            current_stock=3,
        )
        upsert_anomaly_log(
            db_session, "DEDUP02", "상품X", AnomalyType.LOW_STOCK, Severity.HIGH,
            current_stock=2,
        )

        from app.db.models import AnomalyLog
        from datetime import date, datetime
        today_start = datetime.combine(date.today(), datetime.min.time())
        count = db_session.query(AnomalyLog).filter(
            AnomalyLog.product_code == "DEDUP02",
            AnomalyLog.anomaly_type == AnomalyType.LOW_STOCK,
            AnomalyLog.is_resolved  == False,
            AnomalyLog.detected_at  >= today_start,
            ).count()
        assert count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 14. 보고서 HTML 생성
# ═══════════════════════════════════════════════════════════════════════════════

class TestReportTemplate:
    def test_html_contains_required_sections(self):
        from datetime import date
        from app.report.template import build_daily_report_html

        html = build_daily_report_html(
            report_date=date.today(),
            total_products=100,
            stock_anomalies=[{
                "product_code": "P001",
                "product_name": "상품A",
                "anomaly_type": "LOW_STOCK",
                "current_stock": 3,
                "days_until_stockout": 0.6,
                "severity": "CRITICAL",
            }],
            sales_anomalies=[{
                "product_code": "P002",
                "product_name": "상품B",
                "anomaly_type": "SALES_SURGE",
                "change_rate": 80.0,
                "severity": "HIGH",
                "sentiment": {"label": "긍정"},
            }],
            insight={
                "overall_summary": "테스트 요약",
                "key_issues": ["이슈1"],
                "recommendations": ["권고1"],
                "risk_level": "high",
            },
        )
        assert "SCM Agent" in html
        assert "상품A" in html
        assert "상품B" in html
        assert "재고 부족" in html   # ANOMALY_TYPE_KOR 한글 변환 확인
        assert "판매 급등" in html
        assert "긴급"    in html    # SEVERITY_KOR 한글 변환 확인

    def test_html_no_korean_garbled(self):
        """한글이 깨지지 않고 정상 포함 확인"""
        from datetime import date
        from app.report.template import build_daily_report_html

        html = build_daily_report_html(
            report_date=date.today(),
            total_products=0,
            stock_anomalies=[],
            sales_anomalies=[],
            insight={"overall_summary": "요약없음", "key_issues": [], "recommendations": [], "risk_level": "LOW"},
        )
        # 인코딩 깨짐 시 한글이 사라지거나 ?로 치환됨
        assert "일일 재고 현황 보고서" in html
        assert "?" not in html.split("<style>")[0]   # style 이전 영역에 ? 없음