# SCM Agent — 대용량 데이터 처리 아키텍처 설계 핸드오프

> 작성일: 2026-03-28
> 대상: 5단계 구현 담당자 (또는 미래의 나)
> 현황: 1~4단계 이슈 수정 완료. 본 문서는 5단계(대용량 데이터 + Celery 전환) 설계 결정을 기록한다.

---

## 1. 배경 및 문제 정의

### 현재 구조의 한계

| 병목 | 원인 | 증상 |
|------|------|------|
| 뷰 로딩 느림 | API 요청마다 Sheets 전체 로드 → pandas 메모리 필터 | 50 건 페이지 반환에 1~3초 소요 |
| SoT 반영 지연 | Redis TTL 5분 고정, write 후 캐시 삭제만(재워밍 없음) | 수정 후 최대 5분간 구버전 데이터 노출 |
| 100k 상품마스터 불가 | `get_all_records()` = 시트 전체 로드, Sheets 셀 한도 1000만 | 대용량 Excel 업로드 시 타임아웃 |
| 분석 느림 | demand/turnover가 iterrows로 상품별 전체 sales 재필터 (O n×m) | 1만 상품 기준 demand 계산 10초+ |
| daily job이 API 차단 | APScheduler 인프로세스 실행, 동기 크롤러 직렬 3~5분 | 새벽 job 중 모든 API 응답 차단 |

---

## 2. 최종 확정 아키텍처

### 핵심 원칙

```
[데이터 입력]                [저장/처리]                   [API 서빙]
─────────────────────────────────────────────────────────────────────
크롤러 (aiohttp) ──┐
Excel 업로드 API ──┼──→ MariaDB (primary SoT) ──→ DB 쿼리 → 응답
Sheets 편집(운영자) ┘         │
    ↑ sync job 15분 주기       │
    └── Google Sheets          ↓
        (편집 UI 유지)    RabbitMQ → Celery Worker
                               (demand / turnover / ABC)
                                         ↓
                               analysis_cache (DB + Redis 30분 TTL)
                                         │
                               /stats/* 캐시 HIT → <100ms 응답

이상징후: API 트리거 → DB 쿼리 → vectorized pandas → 즉시 반환
```

### 결정 요약

| 영역 | 결정 | 비고 |
|------|------|------|
| **SoT** | MariaDB primary + Sheets 편집 UI 병행 | Hybrid A2 |
| **원본 데이터 읽기** | DB 직접 쿼리 (인덱스) | Sheets/Redis 캐시 제거 |
| **분석 결과 캐시** | Redis 30~60분 TTL + DB analysis_cache | 이상징후만 on-demand |
| **태스크 큐 브로커** | **RabbitMQ** (AMQP) | AWS 전환 시 Amazon MQ로 URL만 교체 |
| **Celery Result Backend** | **MariaDB** (`celery_taskmeta` 자동 생성) | Redis 의존도 최소화 |
| **스케줄러** | APScheduler 제거 → **Celery Beat 완전 교체** | |
| **크롤러** | aiohttp + asyncio.Semaphore(3) 병렬 | 3~5분 → 30~60초 |
| **Analyzer** | demand/turnover vectorized + Celery task | stock_analyzer는 in-process 유지 |
| **대용량 write** | INSERT ... ON DUPLICATE KEY UPDATE, 1000건 배치 | |
| **데이터 보존기간** | `system_settings` DB 키로 관리, 설정 UI에서 수정 가능 | |
| **CHECK 상태** | REVIEW → CHECK 리네임, 미취급/재등록 버튼 추가 | |

---

## 3. 신규 DB 테이블 (4개, 기존 테이블 변경 없음)

### 3-1. `products` — 상품마스터 미러

```sql
CREATE TABLE products (
    code          VARCHAR(50)  PRIMARY KEY,
    name          VARCHAR(255) NOT NULL DEFAULT '데이터 없음',
    category      VARCHAR(100) NOT NULL DEFAULT 'Default',
    safety_stock  INT          NOT NULL DEFAULT 10,
    status        ENUM('active','inactive','sample') NOT NULL DEFAULT 'active',
    -- active: 정상 취급
    -- inactive: 미취급 (단종, 판매 중지)
    -- sample: 시증 상품 (재고/판매 분석 제외)
    source        VARCHAR(50),   -- 'crawl' | 'excel' | 'sheets'
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_products_category (category),
    INDEX ix_products_name     (name),
    INDEX ix_products_status   (status)
);
```

### 3-2. `daily_sales` — 일별판매 미러

```sql
CREATE TABLE daily_sales (
    id           BIGINT      AUTO_INCREMENT PRIMARY KEY,
    date         DATE        NOT NULL,
    product_code VARCHAR(50) NOT NULL,
    qty          INT         NOT NULL DEFAULT 0,
    revenue      BIGINT      NOT NULL DEFAULT 0,
    UNIQUE INDEX uq_daily_sales (date, product_code),
    INDEX ix_daily_sales_date (date),
    INDEX ix_daily_sales_code (product_code)
);
```

> 보존기간: `DATA_RETENTION_SALES_DAYS` (기본 365일). Celery Beat cleanup task가 매일 02:00 삭제.

### 3-3. `stock_levels` — 재고현황 미러

```sql
CREATE TABLE stock_levels (
    product_code   VARCHAR(50) PRIMARY KEY,
    current_stock  INT         NOT NULL DEFAULT 0,
    restock_date   DATE,
    restock_qty    INT         DEFAULT 0,
    updated_at     DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 3-4. `analysis_cache` — 분석 결과 영속 캐시

```sql
CREATE TABLE analysis_cache (
    id             INT          AUTO_INCREMENT PRIMARY KEY,
    analysis_type  VARCHAR(50)  NOT NULL,  -- 'demand' | 'turnover' | 'abc'
    params_hash    CHAR(64)     NOT NULL,  -- sha256(정렬된 파라미터 JSON)
    result_json    LONGTEXT     NOT NULL,
    created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX uq_analysis_cache (analysis_type, params_hash),
    INDEX ix_analysis_cache_type    (analysis_type),
    INDEX ix_analysis_cache_created (created_at)
);
```

---

## 4. 신규 파일 및 변경 파일

### 4-1. 신규 생성

| 경로 | 역할 |
|------|------|
| `app/celery_app/__init__.py` | 패키지 |
| `app/celery_app/celery.py` | Celery 앱 인스턴스 + 설정 (broker, result_backend, 직렬화 등) |
| `app/celery_app/tasks.py` | `@shared_task` 함수: demand/turnover/abc/daily_job/crawler/cleanup |
| `app/celery_app/beat_schedule.py` | `CELERYBEAT_SCHEDULE` 정의 (APScheduler 대체) |
| `app/db/sync.py` | Sheets/Excel DataFrame → DB bulk upsert 함수 |
| `app/api/task_router.py` | `GET /scm/tasks/{task_id}/status` (task 진행상태 polling) |
| `app/api/product_router.py` | `PATCH /scm/products/{code}/status` (미취급/재등록) |

### 4-2. 수정

| 경로 | 주요 변경 내용 |
|------|--------------|
| `app/db/models.py` | `Product`, `DailySale`, `StockLevel`, `AnalysisCache` 클래스 추가. `AnomalyLog.severity`에 `check` 추가 |
| `app/db/repository.py` | bulk insert 함수, product status CRUD, DB 기반 페이지네이션 쿼리 |
| `app/main.py` | APScheduler import/start 제거. Celery 라우터 등록 |
| `app/api/sheets_router.py` | 모든 엔드포인트 읽기 경로를 DB 쿼리로 전환. Excel 업로드 엔드포인트 추가 |
| `app/scheduler/jobs.py` | `run_daily_job()` 함수는 유지 (Celery task가 래핑). sync_to_db 호출 추가 |
| `app/analyzer/demand_forecaster.py` | `iterrows` 제거 → `groupby` 사전집계 dict 활용 |
| `app/analyzer/turnover_analyzer.py` | `iterrows` 제거 → `np.select` vectorized 등급 계산 |
| `app/analyzer/stock_analyzer.py` | `vectorized` 조건 필터. `inactive`/`sample` 상품 분석 제외. `CHECK` severity 반영 |
| `app/crawler/scraper.py` | `requests` → `aiohttp.ClientSession` + `asyncio.Semaphore(3)` per domain |
| `docker-compose.yml` | `rabbitmq`, `celery-worker`, `celery-beat` 서비스 추가. `api`에서 APScheduler 제거 |
| `requirements.txt` | `celery[amqp]`, `aiohttp`, `kombu` 추가 |

---

## 5. Celery 설정 핵심

```python
# app/celery_app/celery.py
celery_app.conf.update(
    broker_url          = "amqp://guest:guest@rabbitmq:5672//",
    result_backend      = "db+mysql+pymysql://user:pass@db:3306/scm_db",
    task_serializer     = "json",
    result_serializer   = "json",
    accept_content      = ["json"],
    timezone            = "Asia/Seoul",
    enable_utc          = False,
    task_track_started  = True,
    task_acks_late      = True,          # worker 재시작 시 메시지 유실 방지
    worker_prefetch_multiplier = 1,      # 공정한 작업 분배
)
```

### Celery Beat 스케줄 (APScheduler 완전 대체)

```python
# app/celery_app/beat_schedule.py
CELERYBEAT_SCHEDULE = {
    "daily-report":    { "task": "run_daily_job",    "schedule": crontab(hour=0,  minute=0) },
    "daily-crawler":   { "task": "run_crawler",      "schedule": crontab(hour=23, minute=0) },
    "cleanup-data":    { "task": "cleanup_old_data", "schedule": crontab(hour=2,  minute=0) },
}
```

### Task 상태 흐름

```
API /stats/demand 요청
  │
  ├─ Redis 캐시 HIT (30분 TTL)? → 즉시 반환
  │
  ├─ DB analysis_cache 존재 (30분 이내)? → Redis 워밍 후 반환
  │
  └─ 없음 → celery_app.send_task("run_demand_analysis", kwargs={...})
              → {"task_id": "abc-123"} 반환
              → 프론트: GET /scm/tasks/abc-123/status polling
              → PENDING | STARTED | SUCCESS | FAILURE
              → SUCCESS 시 result(items) 포함 반환
```

---

## 6. 데이터 흐름별 동시성 처리

| 시나리오 | 처리 방법 |
|---------|----------|
| Excel 동시 업로드 | `asyncio.Semaphore(1)` per upload type (master/sales/stock) |
| Sheets 동시 쓰기 | `threading.Lock` per sheet name (기존 유지) |
| DB bulk upsert 동시 | `INSERT ... ON DUPLICATE KEY UPDATE` (DB atomic 보장) |
| Celery task 중복 실행 | `params_hash` 기반 중복 enqueue 방지 (동일 파라미터 task 1개 제한) |
| 크롤러 병렬 fetch | `asyncio.Semaphore(3)` per domain |
| analysis_cache 동시 write | DB UNIQUE constraint (`analysis_type`, `params_hash`) |
| Celery worker 다중 인스턴스 | `task_acks_late=True` + `worker_prefetch_multiplier=1` |

---

## 7. API 읽기 경로 변경 요약

| 엔드포인트 | 변경 전 | 변경 후 |
|-----------|---------|---------|
| `GET /scm/sheets/master` | Sheets → Redis → pandas filter | `SELECT * FROM products WHERE ...` |
| `GET /scm/sheets/sales` | Sheets → Redis → pandas date filter | `SELECT * FROM daily_sales WHERE date >= ?` |
| `GET /scm/sheets/stock` | Sheets → Redis → pandas | `SELECT sl.*, p.* FROM stock_levels JOIN products` |
| `GET /scm/sheets/stats/demand` | on-demand 계산 (느림) | Redis HIT → 즉시 / MISS → Celery task |
| `GET /scm/sheets/stats/turnover` | on-demand 계산 (느림) | 동일 |
| `GET /scm/sheets/stats/abc` | on-demand 계산 | 동일 |

`sheets:{name}` Redis 캐시 키 제거. Redis는 `analysis:{type}:{hash}` 키에만 사용.

---

## 8. Analyzer 개선 요점

### demand_forecaster.py — iterrows 제거

```python
# 현재 (느림): 상품별로 df_sales 전체 재필터 O(n × m)
for _, row in df_master.iterrows():
    code = row["상품코드"]
    product_sales = df_sales[df_sales["상품코드"] == code]  # 매번 전체 스캔

# 변경 (빠름): 루프 전에 1회 groupby → dict 캐시 O(m + n)
sales_by_code = {
    code: grp.sort_values("날짜")
    for code, grp in df_sales.groupby("상품코드")
}
for _, row in df_master.iterrows():
    code = row["상품코드"]
    product_sales = sales_by_code.get(code, empty_df)  # O(1) lookup
```

### turnover_analyzer.py — iterrows → np.select

```python
# 현재: iterrows에서 if/elif로 등급 계산
# 변경: vectorized
conditions = [df["체류일수"] <= 30, df["체류일수"] <= 90]
choices    = ["우수", "보통"]
df["등급"] = np.select(conditions, choices, default="주의")
```

### stock_analyzer.py — inactive 상품 분석 제외

```python
# products 테이블 status를 분석 전 조인하여 inactive/sample 제외
df = df[df["status"] == "active"]
```

---

## 9. CHECK 상태 + 미취급/재등록

### severity 리네임

```sql
-- 기존 REVIEW → CHECK
ALTER TABLE anomaly_logs
  MODIFY COLUMN severity ENUM('low','check','medium','high','critical') NOT NULL DEFAULT 'medium';
```

### products.status 의미

| 값 | 의미 | 분석 포함 여부 | CHECK 이상징후 시 표시 버튼 |
|----|------|--------------|--------------------------|
| `active` | 정상 취급 중 | ✅ | 미취급 / 시증상품 |
| `inactive` | 미취급 (단종, 판매 중지) | ❌ | 재등록 |
| `sample` | 시증 상품 | ❌ | 재등록 |

### 신규 API

```
PATCH /scm/products/{code}/status
Body: { "status": "inactive" | "active" | "sample" }
응답: { "code": "P001", "status": "inactive", "updated_at": "..." }
```

---

## 10. Excel 업로드 API

```
POST /scm/sheets/upload-excel
Content-Type: multipart/form-data

Fields:
  file: (xlsx 파일)
  sheet_type: "master" | "sales" | "stock"

처리 흐름:
  1. pandas read_excel → 컬럼 검증
  2. sync.py로 DB bulk upsert (1000건 배치)
  3. writer.py로 Sheets upsert (편집 UI 동기화)
  4. Redis analysis cache invalidate

응답:
  { "status": "success", "inserted": 8200, "updated": 1800, "skipped": 0 }
```

---

## 11. 데이터 보존기간 설정

`system_settings` 테이블에 추가될 키 (기존 settings 시스템 재활용):

| 키 | 기본값 | 설명 |
|----|--------|------|
| `DATA_RETENTION_SALES_DAYS` | `365` | daily_sales 보존 일수 |
| `DATA_RETENTION_STOCK_DAYS` | `180` | stock_levels 이력 보존 일수 (현재는 최신 1건이라 미해당) |
| `DATA_RETENTION_ANALYSIS_HOURS` | `24` | analysis_cache 보존 시간 |

- 기존 `/scm/settings` UI에서 수정 가능 (기존 settings 연동)
- Celery Beat `cleanup-data` task (매일 02:00)가 보존기간 초과 레코드 삭제

---

## 12. docker-compose 변경

추가 서비스:
```yaml
rabbitmq:
  image: rabbitmq:3.12-management
  ports:
    - "5672:5672"
    - "15672:15672"   # RabbitMQ 관리 UI
  environment:
    RABBITMQ_DEFAULT_USER: guest
    RABBITMQ_DEFAULT_PASS: guest

celery-worker:
  build: .
  command: celery -A app.celery_app.celery worker --loglevel=info --concurrency=2
  environment:
    - TZ=Asia/Seoul
  depends_on: [rabbitmq, db]

celery-beat:
  build: .
  command: celery -A app.celery_app.celery beat --loglevel=info
  environment:
    - TZ=Asia/Seoul
  depends_on: [rabbitmq, db]
```

`api` 서비스: APScheduler 관련 코드 제거 (`main.py`에서 `scheduler.start()` 삭제)

---

## 13. 신규 패키지

```
celery[amqp]==5.3.*      # Celery + AMQP(RabbitMQ)
aiohttp==3.9.*           # 비동기 크롤러
kombu==5.3.*             # Celery 의존 (자동 설치)
```

환경변수 추가:
```env
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
CELERY_RESULT_BACKEND=db+mysql+pymysql://scm_user:password@db:3306/scm_db
DATA_RETENTION_SALES_DAYS=365
DATA_RETENTION_STOCK_DAYS=180
DATA_RETENTION_ANALYSIS_HOURS=24
```

---

## 14. 구현 순서

| 순서 | 작업 | 선행 조건 |
|------|------|---------|
| 5-1 | DB 테이블 4개 CREATE + `AnomalyLog.severity` CHECK 추가 | 없음 |
| 5-2 | `app/db/sync.py` 작성 (bulk upsert 함수) | 5-1 |
| 5-3 | Celery 앱 설정 + RabbitMQ docker-compose + APScheduler 제거 | 없음 |
| 5-4 | Celery Beat 스케줄 (`beat_schedule.py`) + `main.py` 정리 | 5-3 |
| 5-5 | Celery tasks.py (daily_job/crawler/demand/turnover/abc/cleanup) | 5-2, 5-3 |
| 5-6 | `sheets_router.py` DB 쿼리 전환 + `/tasks/{id}/status` 라우터 | 5-1, 5-5 |
| 5-7 | Excel 업로드 API | 5-2 |
| 5-8 | analyzer vectorize (demand/turnover/stock) | 5-1 |
| 5-9 | `products.status` + 미취급/재등록 API | 5-1 |
| 5-10 | 크롤러 aiohttp 비동기 전환 | 5-3 (Celery task 내에서 실행) |
| 5-11 | 보존기간 settings 키 + cleanup task | 5-5 |
| 5-12 | 프론트엔드: CHECK 버튼, 보존기간 설정 UI, task polling | 5-6, 5-9 |

---

## 15. AWS / k8s 전환 시 고려사항

| 컴포넌트 | 로컬(현재) | AWS 전환 시 |
|---------|----------|-----------|
| RabbitMQ | docker-compose | Amazon MQ for RabbitMQ (connection URL만 교체, 코드 무변경) |
| MariaDB | docker-compose | RDS for MariaDB |
| Redis | docker-compose | ElastiCache for Redis |
| Celery Worker | docker-compose | ECS Task / k8s Deployment |
| Celery Beat | docker-compose | ECS Task / k8s CronJob |
| API | docker-compose | ECS Service / k8s Deployment |

k8s 배포 시 RabbitMQ는 [RabbitMQ Cluster Operator](https://www.rabbitmq.com/kubernetes/operator/operator-overview) 또는 Bitnami Helm chart 사용.

---

*문서 끝. 구현 시작 전 5-1(DB 마이그레이션) 먼저 적용할 것.*
