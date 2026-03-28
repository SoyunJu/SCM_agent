# SCM Agent — 시스템 아키텍처

---

## 전체 데이터 흐름

```
[데이터 입력]
──────────────────────────────────────────────────
Google Sheets (운영자 직접 편집)
Excel 업로드 (POST /scm/sheets/upload-excel)
Web Crawler  (aiohttp, 야간 자동 실행)
                    │
                    ▼
[캐싱 레이어]
──────────────────────────────────────────────────
Redis (sheets:{sheet_name}, TTL 300초)
   ↑ cache miss 시 gspread API 호출 후 저장
   ↓ cache hit 시 즉시 반환
                    │
                    ▼
[처리 레이어]
──────────────────────────────────────────────────
pandas 분석 (stock_analyzer, sales_analyzer 등)
LLM (OpenAI GPT-4o-mini) 인사이트 생성
                    │
                    ▼
[저장 레이어]
──────────────────────────────────────────────────
MariaDB (anomaly_logs, order_proposals, report_executions 등)
Google Sheets 역방향 동기화 (분석결과, 주문관리 시트)
                    │
                    ▼
[출력 채널]
──────────────────────────────────────────────────
REST API  → Next.js 관리자 UI (localhost:3001)
SSE       → 실시간 알림 (GET /scm/alerts/stream)
Slack     → 채널 메시지 + 인터랙티브 버튼
Email     → SMTP 알림 (Gmail)
PDF       → 일별 보고서 파일 (/reports/*.pdf)
```

---

## 서비스 구성 (docker-compose)

| 서비스 | 역할 | 의존성 |
|--------|------|--------|
| `api` | FastAPI 백엔드 (포트 8000) | db, redis |
| `frontend` | Next.js 관리자 UI (포트 3001) | api |
| `db` | MariaDB 11.3 (포트 3307) | — |
| `redis` | Redis 7, 캐시 + Celery 결과 저장 (포트 6379) | — |
| `rabbitmq` | RabbitMQ 3.12, Celery 메시지 브로커 (포트 5672/15672) | — |
| `celery-worker` | Celery 워커 (concurrency=2) | rabbitmq, db, redis |
| `celery-beat` | Celery 주기 스케줄러 | rabbitmq, db |
| `crawler` | 웹 크롤러 독립 프로세스 | db, redis |

---

## 모듈 구조

```
app/
├── api/            # FastAPI 라우터 (13개)
├── analyzer/       # 데이터 분석 로직
│   ├── abc_analyzer.py       — ABC 재고 분류
│   ├── demand_forecaster.py  — 수요 예측
│   ├── sales_analyzer.py     — 판매 이상징후
│   ├── stock_analyzer.py     — 재고 이상징후
│   └── turnover_analyzer.py  — 재고 회전율
├── ai/             # LLM / AI 모듈
│   ├── agent.py              — LangChain 에이전트 루프
│   ├── insight_generator.py  — 일별 인사이트 생성
│   ├── order_agent.py        — 발주 제안 생성
│   ├── sentiment_analyzer.py — KR-FinBert 감성 분석
│   └── tools.py              — LangChain 툴 정의
├── cache/          # Redis 클라이언트 래퍼
├── celery_app/     # Celery 앱 + 태스크 정의
├── crawler/        # 웹 스크래퍼 (BeautifulSoup)
├── db/             # SQLAlchemy 모델 + Repository
├── notifier/       # Slack/Email 알림 발송
├── report/         # PDF 보고서 생성 (ReportLab)
├── scheduler/      # 일일 작업 오케스트레이션
├── sheets/         # gspread 클라이언트 + reader/writer
├── utils/          # 헬퍼 유틸리티
└── main.py         # FastAPI 앱 진입점, lifespan 훅
```

---

## 주요 워크플로우

### 1. 일일 스케줄 작업 (`run_daily_job`)

```
[1/7] Google Sheets 동기화 (크롤 데이터 + Excel 반영)
[2/7] 재고/판매 이상징후 분석
[3/7] 주문 데이터 동기화
[4/7] 판매 이상징후 감성 분석 (KR-FinBert)
[5/7] AI 인사이트 생성 (GPT-4o-mini)
[6/7] PDF 보고서 생성 (ReportLab)
[7/7] Slack + 이메일 알림 발송
        │
        ├─ 이상징후 → AnomalyLog DB 저장
        ├─ CRITICAL/HIGH → SSE 브로드캐스트 (실시간 알림)
        └─ Sheets 분석결과 탭 업데이트
```

### 2. 이상징후 탐지 → 알림

```
stock_analyzer / sales_analyzer
    → anomalies 리스트 (severity: CRITICAL|HIGH|MEDIUM|LOW|CHECK)
    → DB: AnomalyLog 저장
    → CRITICAL/HIGH: sync_broadcast_alert() → SSE 클라이언트
    → notify_anomaly_alert() → Slack DM + 채널 메시지
```

### 3. 발주 제안 흐름

```
POST /scm/orders/proposals/generate
    → order_agent.py: LLM이 이상징후 분석 후 수량/단가 산출
    → DB: OrderProposal 저장 (status=PENDING)
    → Slack: 인터랙티브 메시지 발송 (승인/거절 버튼)

Slack 버튼 클릭 → /scm/slack/interactions
    → ProposalStatus 업데이트 (APPROVED | REJECTED)
    → 담당자 DM 발송

또는 관리자 UI에서 직접 승인/거절
    → PATCH /scm/orders/proposals/{id}/approve
```

### 4. 사용자 채팅 쿼리

```
POST /scm/chat/query
    → LangChain 에이전트 루프 (app/ai/agent.py)
    → 툴 실행 (tools.py: get_stock_status, get_sales_trend 등)
    → GPT-4o-mini 응답 생성
    → ChatHistory DB 저장
```

---

## 캐싱 전략

| 캐시 키 | 내용 | TTL |
|---------|------|-----|
| `sheets:상품마스터` | 상품마스터 DataFrame | 300초 |
| `sheets:일별판매` | 일별판매 DataFrame | 300초 |
| `sheets:재고현황` | 재고현황 DataFrame | 300초 |
| `crawler:results` | 크롤링 결과 | 캐시 있는 동안 재사용 |

- 쓰기(write) 후 반드시 `cache_delete(f"sheets:{sheet_name}")` 호출
- `cache_get` / `cache_set` / `cache_delete`: `app/cache/redis_client.py`

---

## 앱 시작 시 초기화 순서 (`lifespan`)

```python
1. check_db_connection()          # DB 연결 확인
2. init_db()                      # 테이블 자동 생성 (create_all)
3. _seed_superadmin()             # 슈퍼어드민 자동 생성
4. set_main_loop(loop)            # SSE 이벤트 루프 등록
5. _warmup_sheets() (비동기)      # 시트 캐시 워밍업 + DB 초기 동기화
```
