# docs/handoff.md

# SCM Agent — 개발 핸드오프

> 작성일: 2026-03-29
> 대상: 다음 개발자 (또는 미래의 나)
> 현황: Phase 1~4 완료 + Service Layer 리팩토링 완료. Phase 5 설계 완료, 미구현.

---

## 1. 현재 상태 요약

| 단계 | 주요 내용 | 상태 |
|------|-----------|------|
| Phase 1~3 | 기본 파이프라인, Sheets 수집, 분석, Slack 알림, PDF 보고서, LLM 채팅 | ✅ 완료 |
| Phase 4 | 버그 수정, RBAC, Celery Beat 도입, 대시보드 완성 | ✅ 완료 |
| 리팩토링 | Service Layer 도입 — Router/Service/Repository 3계층 분리 | ✅ 완료 |
| Phase 5 | MariaDB SoT 전환, 대용량 처리 | 🔧 설계 완료, 미구현 |

---

## 2. 리팩토링 완료 내용 (Service Layer)

기존 라우터에 비즈니스 로직이 집중되던 모놀리식 구조를 3계층으로 분리했습니다.
```
Before: Router (300~400줄, 비즈니스 로직 포함)
After:  Router (50~80줄, 위임만) → Service (비즈니스 로직) → Repository/DB
```
### 신규 생성 파일

| 파일 | 역할 |
|------|------|
| `app/services/sync_service.py` | Sheets/Excel → DB 동기화 전담. `SyncService.sync_all_from_sheets()` |
| `app/services/sheet_service.py` | 데이터 조회/필터/페이징/CSV 다운로드/통계 분석 전담. `SheetService` |
| `app/services/order_service.py` | 발주 제안 CRUD + 승인/거절 워크플로우. `OrderService` |
| `app/services/report_service.py` | 보고서 트리거/상태 폴링/이력/PDF 관리. `ReportService` |
| `app/services/anomaly_service.py` | 이상징후 조회/해결 처리. `AnomalyService` |
| `app/services/slack_service.py` | Slack 메시지 발송/업데이트 전담. `SlackService` |

### 영향받은 파일

| 파일 | 변경 내용 |
|------|----------|
| `app/api/sheets_router.py` | 비즈니스 로직 전부 제거 → `SheetService`/`SyncService` 위임 |
| `app/api/order_router.py` | `OrderService` 위임 |
| `app/api/report_router.py` | `ReportService`/`AnomalyService` 위임 |
| `app/scheduler/jobs.py` | `_sync_sheets_to_db()` → `SyncService.sync_all_from_sheets()` 래퍼로 교체 |
| `app/main.py` | `_warmup_sheets()` 내 jobs 의존성 제거 → `SyncService` 직접 호출 |
| `app/db/sync.py` | `bulk_upsert_products()` 함수 추가 |

---

## 3. CSV 컬럼 변경 (Sheets ↔ DB 정합성)

Google Sheets 3개 시트의 컬럼이 확장되었습니다. DB 스키마도 함께 변경되었습니다.

### 상품마스터
현재 상태를 완전히 파악했습니다. 신규 handoff 문서를 작성합니다.
markdown# docs/handoff.md

# SCM Agent — 개발 핸드오프

> 작성일: 2026-03-29
> 대상: 다음 개발자 (또는 미래의 나)
> 현황: Phase 1~4 완료 + Service Layer 리팩토링 완료. Phase 5 설계 완료, 미구현.

---

## 1. 현재 상태 요약

| 단계 | 주요 내용 | 상태 |
|------|-----------|------|
| Phase 1~3 | 기본 파이프라인, Sheets 수집, 분석, Slack 알림, PDF 보고서, LLM 채팅 | ✅ 완료 |
| Phase 4 | 버그 수정, RBAC, Celery Beat 도입, 대시보드 완성 | ✅ 완료 |
| 리팩토링 | Service Layer 도입 — Router/Service/Repository 3계층 분리 | ✅ 완료 |
| Phase 5 | MariaDB SoT 전환, 대용량 처리 | 🔧 설계 완료, 미구현 |

---

## 2. 리팩토링 완료 내용 (Service Layer)

기존 라우터에 비즈니스 로직이 집중되던 모놀리식 구조를 3계층으로 분리했습니다.
```
Before: Router (300~400줄, 비즈니스 로직 포함)
After:  Router (50~80줄, 위임만) → Service (비즈니스 로직) → Repository/DB
```

### 신규 생성 파일

| 파일 | 역할 |
|------|------|
| `app/services/sync_service.py` | Sheets/Excel → DB 동기화 전담. `SyncService.sync_all_from_sheets()` |
| `app/services/sheet_service.py` | 데이터 조회/필터/페이징/CSV 다운로드/통계 분석 전담. `SheetService` |
| `app/services/order_service.py` | 발주 제안 CRUD + 승인/거절 워크플로우. `OrderService` |
| `app/services/report_service.py` | 보고서 트리거/상태 폴링/이력/PDF 관리. `ReportService` |
| `app/services/anomaly_service.py` | 이상징후 조회/해결 처리. `AnomalyService` |
| `app/services/slack_service.py` | Slack 메시지 발송/업데이트 전담. `SlackService` |

### 영향받은 파일

| 파일 | 변경 내용 |
|------|----------|
| `app/api/sheets_router.py` | 비즈니스 로직 전부 제거 → `SheetService`/`SyncService` 위임 |
| `app/api/order_router.py` | `OrderService` 위임 |
| `app/api/report_router.py` | `ReportService`/`AnomalyService` 위임 |
| `app/scheduler/jobs.py` | `_sync_sheets_to_db()` → `SyncService.sync_all_from_sheets()` 래퍼로 교체 |
| `app/main.py` | `_warmup_sheets()` 내 jobs 의존성 제거 → `SyncService` 직접 호출 |
| `app/db/sync.py` | `bulk_upsert_products()` 함수 추가 |

---

## 3. CSV 컬럼 변경 (Sheets ↔ DB 정합성)

Google Sheets 3개 시트의 컬럼이 확장되었습니다. DB 스키마도 함께 변경되었습니다.

### 상품마스터
```
상품코드 | 상품명 | 카테고리 | 안전재고기준 | 현재재고(추가)
```

### 일별판매
```
날짜 | 상품코드 | 상품명(추가) | 카테고리(추가) | 판매수량 | 단가(추가) | 매출액 | 매입액(추가) | 차액(수익)(추가)
```

### 재고현황
```
상품코드 | 상품명(추가) | 카테고리(추가) | 현재재고 | 안전재고(추가) | 입고예정일 | 입고예정수량
```

### DB 변경사항 (직접 실행 필요 시)
```sql
-- daily_sales 테이블에 매입액 컬럼 추가
ALTER TABLE daily_sales
  ADD COLUMN cost FLOAT NOT NULL DEFAULT 0 AFTER revenue;
```

---

## 4. 현재 알려진 미해결 문제

| 이슈 | 원인 | 해결 방법 |
|------|------|----------|
| **이메일 발송 실패** (530 Authentication Required) | Gmail App Password 미설정 | `.env`의 `SMTP_PASSWORD`를 Gmail App Password로 변경 (코드 수정 불필요) |
| **Slack 인터랙티브 버튼** (발주 승인/거절) | Slack App Interactivity Request URL 미설정 | Slack App → Interactivity & Shortcuts → Request URL: `https://{서버}/scm/slack/interactions` |
| **SSE 실시간 알림** 수신 여부 불확실 | 네트워크 레벨 미확인 | `GET /scm/alerts/stream` + `admin/lib/useAlerts.ts` 구현됨. 브라우저 네트워크 탭에서 EventStream 확인 필요 |

---

## 5. 핵심 설계 규칙 (변경하면 안 되는 것들)

### 5-1. Severity — UPPERCASE 고정
```python
# Python: norm() 헬퍼 필수
from app.utils.severity import norm
if norm(item["severity"]) == "CRITICAL": ...
```
```typescript
// TypeScript: normSev() 헬퍼 필수
import { normSev } from "@/lib/severity";
if (normSev(item.severity) === "CRITICAL") ...
```

### 5-2. ProposalStatus — UPPERCASE 고정

`PENDING | APPROVED | REJECTED` — 대문자 고정.
프론트에서 `p.status === "PENDING"` 비교 시에만 액션 버튼이 표시됨.

### 5-3. API Prefix

모든 엔드포인트는 `/scm/` prefix. 새 라우터 추가 시 반드시 적용.

### 5-4. CSV 인코딩

한글 포함 CSV 생성 시 반드시 `BytesIO` + UTF-8 BOM.
```python
buf = io.BytesIO()
buf.write(b'\xef\xbb\xbf')   # UTF-8 BOM
df.to_csv(buf, index=False, encoding="utf-8")
```

### 5-5. DB 동기화 — SyncService 경유 필수
```python
# 올바른 방법
from app.services.sync_service import SyncService
SyncService.sync_all_from_sheets(db)   # 전체
SyncService.sync_sales(db, df)         # 부분

# 금지 — bulk_upsert_* 직접 호출 시 매핑 로직 중복 발생
from app.db.sync import bulk_upsert_daily_sales  # ← 사용 금지
```

### 5-6. React Query 필수
```typescript
// 올바른 방법
const { data } = useQuery({ queryKey: [...], queryFn: () => ... });

// 금지
useEffect(() => { fetch(...).then(...) }, []);
```

---

## 6. 코드베이스 주요 파일 지도

### 백엔드 진입점

| 파일 | 역할 |
|------|------|
| `app/main.py` | FastAPI 앱 + 라우터 등록 + lifespan (워밍업/초기 동기화) |
| `app/config.py` | 전체 환경변수 (Pydantic Settings) |
| `app/db/models.py` | 모든 DB 테이블 + Enum 정의 |
| `app/db/repository.py` | DB CRUD 함수 모음 |
| `app/db/sync.py` | bulk upsert 함수 (products/daily_sales/stock_levels) |

### Service Layer (핵심)

| 파일 | 주요 메서드 |
|------|------------|
| `app/services/sync_service.py` | `sync_all_from_sheets()`, `sync_master()`, `sync_sales()`, `sync_stock()` |
| `app/services/sheet_service.py` | `get_master()`, `get_sales()`, `get_stock()`, `get_sales_stats()`, `get_stock_stats()`, `get_abc_stats()`, `get_demand_stats()`, `get_turnover_stats()` |
| `app/services/order_service.py` | `generate()`, `approve()`, `reject()`, `update()`, `list_proposals()` |
| `app/services/report_service.py` | `trigger()`, `get_status()`, `get_history()`, `list_pdfs()`, `delete_pdf()` |
| `app/services/anomaly_service.py` | `list_anomalies()`, `resolve()` |
| `app/services/slack_service.py` | `send_proposal()`, `update_proposal_resolved()`, `update_proposal_pending()` |

### 분석 파이프라인

| 파일 | 역할 |
|------|------|
| `app/scheduler/jobs.py` | 일일 작업 오케스트레이터 (`run_daily_job` 7단계) |
| `app/celery_app/tasks.py` | Celery 태스크 정의 |
| `app/celery_app/beat_schedule.py` | Beat 스케줄 (daily-report, sync-db, cleanup-data 등) |
| `app/analyzer/stock_analyzer.py` | 재고 이상징후 탐지 |
| `app/analyzer/sales_analyzer.py` | 판매 이상징후 탐지 |
| `app/ai/order_agent.py` | 발주 제안 생성 (매입단가 기반 단가 계산) |

### 공통 유틸

| 파일 | 역할 |
|------|------|
| `app/utils/severity.py` | `norm()`, `SEVERITY_RANK` |
| `app/cache/redis_client.py` | `cache_get`, `cache_set`, `cache_delete` |
| `app/sheets/reader.py` | Sheets 읽기 + Redis 캐시 |
| `app/sheets/writer.py` | Sheets 쓰기 + 캐시 무효화 |

### 프론트엔드 주요 파일

| 파일 | 역할 |
|------|------|
| `admin/lib/api.ts` | 전체 API 클라이언트 함수 |
| `admin/lib/severity.ts` | `normSev()`, `SEVERITY_KOR`, `SEVERITY_COLOR` |
| `admin/lib/useAlerts.ts` | SSE 실시간 알림 훅 |
| `admin/app/dashboard/layout.tsx` | 공통 레이아웃 + SSE 알림 수신 |
| `admin/app/dashboard/scheduler/page.tsx` | Celery Worker/Beat 상태 시각화 + 보고서 폴링 |
| `admin/app/dashboard/stats/page.tsx` | 통계 탭 (수요예측/회전율 검색 포함) |

---

## 7. 개발 환경 및 주의사항
```bash
# 전체 Docker
docker-compose up -d --build

# 코드 변경 후 반드시 재빌드
docker-compose up -d --build --force-recreate

# 백엔드만 (로컬)
uvicorn app.main:app --reload --port 8000

# Celery Worker (로컬, 별도 터미널)
celery -A app.celery_app.celery worker --loglevel=info

# Celery Beat (로컬, 별도 터미널)
celery -A app.celery_app.celery beat --loglevel=info

# Redis 캐시 초기화
docker exec -it scm_agent-redis-1 redis-cli FLUSHALL
```

---

## 8. 테스트
```bash
pytest tests/
pytest tests/test_analyzers_vectorized.py -v
```

현재 커버리지: 분석 모듈, Celery 태스크, 라우터 단위 테스트 위주.
API 통합 테스트 미작성.

---

## 9. 다음 작업 — Phase 5

상세 설계: [`architecture-handoff.md`](./architecture-handoff.md)

### 핵심 변경 방향
```
현재: Google Sheets → Redis → pandas 분석 → 응답
목표: MariaDB (SoT) → DB 직접 쿼리 → 응답
       + Celery Beat 분석 캐시
       + aiohttp 비동기 크롤러
```

### 구현 우선순위

| 순서 | 작업 | 예상 난이도 |
|------|------|------------|
| 5-1 | `SheetService` 읽기 경로를 Sheets → DB 쿼리로 전환 | 중 |
| 5-2 | Celery task에서 분석 결과 `analysis_cache` 저장 | 중 |
| 5-3 | demand/turnover analyzer vectorize (`iterrows` 제거) | 하 |
| 5-4 | 크롤러 `aiohttp` 비동기 전환 | 하 |
| 5-5 | 프론트 데이터 보존기간 설정 UI | 하 |

> Phase 5 구현 전 반드시: Google Sheets에 실제 데이터 입력 후 `POST /scm/sheets/sync` 동기화 확인.
