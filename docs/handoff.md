## 1. 현재 상태 요약

| 단계 | 주요 내용 |
|------|-----------|
| Phase 1~3 | 기본 파이프라인 구축 |
| Phase 4 | 버그 수정, RBAC, 대시보드 완성 |
| **리팩토링** | **Service Layer 도입 — Router/Service/Repository 3계층 분리** |
| Phase 5 | MariaDB SoT 전환, Celery 도입 (설계 완료, 미구현) |

## 5. 코드베이스 주요 파일 지도 (업데이트)

### 신규: Services 레이어

| 파일 | 역할 |
|------|------|
| `app/services/sync_service.py` | Sheets/Excel → DB 동기화 전담. `SyncService` |
| `app/services/sheet_service.py` | 데이터 조회/필터/페이징/통계 전담. `SheetService` |
| `app/services/order_service.py` | 발주 제안 CRUD + 승인 워크플로우. `OrderService` |
| `app/services/report_service.py` | 보고서 트리거/상태/이력/PDF. `ReportService` |
| `app/services/anomaly_service.py` | 이상징후 조회/해결. `AnomalyService` |

### 라우터 (얇아진 버전)

| 파일 | 현재 역할 |
|------|----------|
| `app/api/sheets_router.py` | HTTP 파라미터 수신 → `SheetService`/`SyncService` 위임 |
| `app/api/order_router.py` | HTTP 파라미터 수신 → `OrderService` 위임 |
| `app/api/report_router.py` | HTTP 파라미터 수신 → `ReportService`/`AnomalyService` 위임 |