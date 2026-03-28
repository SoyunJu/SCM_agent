# SCM Agent — 개발 핸드오프

> 작성일: 2026-03-28
> 대상: 다음 개발자 (또는 미래의 나)
> 현황: Phase 1~4 완료. Phase 5 설계 문서 작성 완료, 미구현.

---

## 1. 현재 상태 요약

### 완료된 작업 (Phase 1~4)

| 단계 | 주요 내용 |
|------|-----------|
| Phase 1~3 | 기본 파이프라인 구축 — Sheets 수집, 분석, Slack 알림, PDF 보고서, LLM 채팅 |
| Phase 4 | 다수의 버그 수정 및 기능 완성 (아래 상세) |

### Phase 4에서 수정된 핵심 이슈들

**RBAC 및 권한**
- `READONLY` 계정이 관리자 탭 진입 후 500 에러 → 403 반환 + 프론트 버튼/탭 조건부 숨김
- 역할(role) 대소문자 불일치 → `AdminRole(body.role.upper())` 적용
- 관리자 관리 탭: SUPERADMIN만 접근 가능하도록 수정

**Severity UPPERCASE 통일**
- DB/API/프론트 전반 severity 값을 UPPERCASE로 고정
- Python: `app/utils/severity.py`의 `norm()` 헬퍼 생성 (enum `.value` 버그 방지)
- TypeScript: `admin/lib/severity.ts`의 `normSev()` 헬퍼 생성
- 영향 파일: `sheets_router.py`, `order_router.py`, `admin_router.py`, `alert_router.py`, `order_agent.py`, `notifier.py`, `email_notifier.py`, `slack_notifier.py`, `report/template.py`, 프론트 전체

**발주 관리**
- `ProposalStatus.PENDING.value = "PENDING"` (대문자)인데 프론트가 `"pending"` 비교 → 액션 버튼 미노출 수정
- status 필터 버튼: `"pending"` → `"PENDING"` (전체 대문자)
- 발주 제안 생성 시 severity 임계값 선택 가능하도록 수정

**스케줄러 404**
- `scheduler_router.py` 존재했으나 `main.py`에 등록 누락 → 등록 추가

**DB 동기화 미동작**
- `app/db/sync.py`의 bulk upsert 함수가 정의만 되고 호출 안 됨
- `_sync_sheets_to_db()` 함수 추가 → `sync_sheets_only()` 및 앱 시작(`lifespan`) 시 호출

**CSV 다운로드 한글 깨짐**
- `StringIO` + `encoding="utf-8-sig"` → 파라미터 무시됨
- `BytesIO` + 명시적 BOM(`b'\xef\xbb\xbf'`) 방식으로 수정 (3곳)

**검색 미동작 (일별판매/재고현황)**
- 백엔드 엔드포인트에 `search` 파라미터 누락 → 추가
- 프론트 API 함수 및 호출부에도 search 파라미터 전달하도록 수정

**로딩 속도**
- `sheets/page.tsx`: `useEffect` + manual fetch → `useQuery` (staleTime: 30초) 전환
- 탭 전환 시 불필요한 리페치 제거

**페이지네이션 기본값 10으로 수정 안 됨**
- `page_size` 기본값 50 → 10으로 변경
- `get_anomaly_logs()` API 시그니처 변경 (`limit=` → `page_size=`) 및 3곳 호출부 일괄 수정

**기타**
- 대시보드 미해결 이상징후: 10건 제한 누락 → `page_size=10` 적용
- 보고서 실행 결과 실패로 표시 문제: 응답 구조 파싱 오류 수정
- ABC 분석 차트, 판매 추이 단위 표기 (천/만 원)
- 상품마스터 인라인 편집 모달 추가

---

## 2. 현재 알려진 미해결 문제

| 이슈 | 원인 | 해결 방법 |
|------|------|----------|
| **이메일 발송 실패** (530 Authentication Required) | Gmail App Password 미설정 | `.env`의 `SMTP_PASSWORD`를 Gmail App Password로 변경 (코드 수정 불필요) |
| **Slack 인터랙티브 버튼** (발주 승인/거절) | `SLACK_SIGNING_SECRET` 환경변수 또는 Slack App Request URL 설정 미완 | Slack App 설정에서 Interactivity Request URL을 `https://{server}/scm/slack/interactions`로 지정 |
| **SSE 실시간 알림** 프론트 수신 여부 불확실 | 동작 확인 안 됨 | `GET /scm/alerts/stream` 엔드포인트 + `admin/lib/useAlerts.ts` 훅은 구현됨. 네트워크 레벨 디버깅 필요 |

---

## 3. 핵심 설계 결정 (변경하면 안 되는 것들)

### 3-1. Severity 대소문자

모든 severity 값은 **UPPERCASE**. `"critical"`, `"low"` 등 소문자 사용 금지.

```python
# 비교 시 항상 norm() 사용
from app.utils.severity import norm
if norm(item["severity"]) == "CRITICAL": ...
```

```typescript
// 비교 시 normSev() 사용
import { normSev } from "@/lib/severity";
if (normSev(item.severity) === "CRITICAL") ...
```

### 3-2. ProposalStatus 대소문자

`PENDING | APPROVED | REJECTED` — 대문자 고정.

프론트에서 `p.status === "PENDING"` 으로 비교해야 액션 버튼이 표시됨.

### 3-3. API Prefix

모든 엔드포인트는 `/scm/` prefix. 새 라우터 추가 시 반드시 적용.

### 3-4. CSV 인코딩

한글 포함 CSV 생성 시 `BytesIO` + UTF-8 BOM 필수. `StringIO` 사용 시 한글 깨짐.

### 3-5. React Query

프론트 데이터 페칭은 `useQuery` 사용. 직접 `useEffect` + `fetch` 패턴 금지.

자세한 컨벤션은 [`conventions.md`](./conventions.md) 참조.

---

## 4. 다음 작업: Phase 5

Phase 5 상세 설계는 [`architecture-handoff.md`](./architecture-handoff.md) 참조.

### 핵심 변경 방향

```
현재: Google Sheets → Redis → pandas 분석
목표: MariaDB(primary SoT) → DB 쿼리 → 응답
       + Celery Beat (APScheduler 대체)
       + aiohttp 비동기 크롤러
```

### 구현 우선순위

1. **DB 테이블 정비** — `products`, `daily_sales`, `stock_levels`, `analysis_cache` 테이블이 이미 생성됨. 인덱스 확인 및 데이터 마이그레이션 스크립트 작성
2. **sheets_router.py DB 쿼리 전환** — 가장 체감 효과 큰 작업 (로딩 속도 개선)
3. **Celery Beat 도입** — `app/celery_app/` 폴더 구조 이미 존재하지만 미구현 상태
4. **크롤러 aiohttp 전환** — `app/crawler/scraper.py`의 `requests` → `aiohttp`

### 구현 전 필수 사전 작업

- Google Sheets에 의미있는 테스트 데이터 삽입 (현재 대부분 0건)
- `docker-compose up -d --build` 후 DB 동기화 확인

---

## 5. 코드베이스 주요 파일 지도

### 백엔드 진입점

| 파일 | 역할 |
|------|------|
| `app/main.py` | FastAPI 앱 + 라우터 등록 + 시작 훅 |
| `app/config.py` | 전체 환경변수 설정 (Pydantic Settings) |
| `app/db/models.py` | 모든 DB 테이블 + Enum 정의 |
| `app/db/repository.py` | DB CRUD 함수 모음 |
| `app/db/sync.py` | Sheets → DB bulk upsert |

### 핵심 분석 파이프라인

| 파일 | 역할 |
|------|------|
| `app/scheduler/jobs.py` | 일일 작업 오케스트레이터 (`run_daily_job`) |
| `app/analyzer/stock_analyzer.py` | 재고 이상징후 탐지 |
| `app/analyzer/sales_analyzer.py` | 판매 이상징후 탐지 |
| `app/ai/order_agent.py` | LLM 기반 발주 제안 생성 |
| `app/ai/insight_generator.py` | 일별 인사이트 생성 |

### 공통 유틸리티

| 파일 | 역할 |
|------|------|
| `app/utils/severity.py` | `norm()`, `rank()`, `SEVERITY_RANK` |
| `app/cache/redis_client.py` | `cache_get`, `cache_set`, `cache_delete` |
| `app/sheets/reader.py` | Google Sheets 읽기 + Redis 캐시 |
| `app/sheets/writer.py` | Google Sheets 쓰기 + 캐시 무효화 |

### 프론트엔드 주요 파일

| 파일 | 역할 |
|------|------|
| `admin/lib/api.ts` | 전체 API 클라이언트 함수 |
| `admin/lib/severity.ts` | `normSev()`, `SEVERITY_KOR`, `SEVERITY_COLOR` |
| `admin/app/dashboard/layout.tsx` | 공통 레이아웃 + SSE 알림 |
| `admin/app/dashboard/page.tsx` | 메인 대시보드 |
| `admin/app/dashboard/sheets/page.tsx` | 데이터 시트 뷰 (React Query 기반) |
| `admin/app/dashboard/orders/page.tsx` | 발주 관리 |

---

## 6. 환경별 주의사항

### 로컬 개발

```bash
# 백엔드만 실행
uvicorn app.main:app --reload --port 8000

# 프론트만 실행
cd admin && npm run dev

# 전체 Docker
docker-compose up -d --build
```

### 코드 변경 후 반드시

```bash
# Docker 이미지 재빌드 필수 (캐시 무효화 포함)
docker-compose up -d --build --force-recreate
```

### Redis 캐시 수동 초기화

```bash
docker exec -it scm_agent-redis-1 redis-cli FLUSHALL
```

---

## 7. 테스트

```bash
# 단위 테스트
pytest tests/

# 특정 테스트만
pytest tests/test_analyzers_vectorized.py -v
```

현재 테스트 커버리지: 분석 모듈(stock/sales analyzer) 위주. API 통합 테스트 미작성.

---

## 8. 문서 목록

| 문서 | 내용 |
|------|------|
| [`overview.md`](./overview.md) | 프로젝트 소개, 기술 스택, 단계 현황 |
| [`setup.md`](./setup.md) | 로컬/Docker 환경 설정 가이드 |
| [`architecture.md`](./architecture.md) | 시스템 구조, 데이터 흐름, 워크플로우 |
| [`conventions.md`](./conventions.md) | 코딩 컨벤션 및 설계 규칙 |
| [`api.md`](./api.md) | API 엔드포인트 레퍼런스 |
| [`data-model.md`](./data-model.md) | DB 모델, Sheets 컬럼 매핑, Enum 목록 |
| [`architecture-handoff.md`](./architecture-handoff.md) | Phase 5 상세 설계 (대용량 + Celery) |
