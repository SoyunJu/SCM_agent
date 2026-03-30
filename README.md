# SCM Agent

**쇼핑몰 공급망을 스스로 감지하고, 판단하고, 처리하는 자율 SCM 자동화 플랫폼입니다.**

---

단순한 대시보드가 아닙니다.

재고가 줄어들기 시작하면 스스로 감지하고, 발주 수량을 계산하고, 결재선에 따라 자동 승인하거나 담당자에게 알립니다. AI 챗봇에게 "긴급 재고 부족 상품 발주해줘"라고 말하면 — 조회, 제안, 승인까지 직접 처리합니다.

이상징후 탐지, 수요 예측, 선제 발주, 공급업체 납기 추적, 입고 검수까지 SCM의 반복 업무를 자동화하는 것이 목표입니다.

---

## 목차

1. [이 프로젝트가 하는 일](#1-이-프로젝트가-하는-일)
2. [기술 스택](#2-기술-스택)
3. [빠른 시작](#3-빠른-시작)
4. [주요 기능](#4-주요-기능)
5. [자동화 스케줄](#5-자동화-스케줄)
6. [AI Agent 기능](#6-ai-agent-기능)
7. [프로젝트 구조](#7-프로젝트-구조)
8. [환경변수 설정](#8-환경변수-설정)
9. [테스트](#9-테스트)
10. [API 문서](#10-api-문서)

---

## 1. 이 프로젝트가 하는 일

Google Sheets를 데이터 소스로 사용하는 쇼핑몰의 공급망 운영을 자동화합니다.

| 무엇을 | 어떻게 |
|--------|--------|
| 재고 이상 감지 | 재고 부족·과잉·장기재고를 자동 탐지하고 심각도(CRITICAL/HIGH/MEDIUM/LOW)로 분류 |
| 판매 이상 감지 | 전주 대비 판매량 50% 이상 급등·급락 자동 감지 |
| 수요 예측 | 최근 30일 일평균 판매량 기반 14일 수요 예측 및 부족분 계산 |
| 선제 발주 | 재고 소진 7일 전 자동 발주 제안 생성 — 이상징후 발생 전에 먼저 대응 |
| 발주 결재선 | 금액 기준 자동승인/ADMIN/SUPERADMIN 3단계 분기 |
| 공급업체 관리 | 납기 준수율·평균 지연일수 자동 집계, 입고 검수 후 재고 자동 반영 |
| 일일 보고서 | PDF 생성 + Slack/Email 자동 발송, 감성 분석 포함 |
| AI 챗봇 | 자연어로 발주 처리, 이상징후 해결, 재고 조회까지 직접 실행 |

---

## 2. 기술 스택

**Backend**
- FastAPI · Python 3.11
- MariaDB · SQLAlchemy · Redis · Celery · RabbitMQ
- LangChain · OpenAI GPT · HuggingFace (감성 분석)
- Google Sheets API · gspread

**Frontend**
- Next.js 14 (App Router) · TypeScript
- React Query · Tailwind CSS · Recharts · lucide-react

**Infrastructure**
- Docker / Docker Compose
- Celery Beat (스케줄러) · Celery Worker
- SSE (Server-Sent Events) 실시간 알림

---

## 3. 빠른 시작

### 사전 요구사항

- Docker Desktop
- Google Sheets API 서비스 계정 (JSON 키 파일)
- OpenAI API Key

### 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/SoyunJu/SCM_agent.git
cd SCM_agent

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 및 DB 설정 입력

# 3. Google Sheets 서비스 계정 키 파일 배치
# credentials.json 파일을 프로젝트 루트에 위치

# 4. 전체 실행
docker-compose up -d --build
```

접속 주소:
- 관리자 대시보드: `http://localhost:3001`
- API 문서 (Swagger): `http://localhost:8000/docs`

### Google Sheets 구조

이 프로젝트는 아래 3개 시트가 있는 Google Spreadsheet를 데이터 소스로 사용합니다.

| 시트명 | 필수 컬럼 |
|--------|----------|
| 상품마스터 | 상품코드, 상품명, 카테고리, 안전재고기준 |
| 일별판매 | 날짜, 상품코드, 판매수량, 매출액, 매입액 |
| 재고현황 | 상품코드, 현재재고, 입고예정일, 입고예정수량 |

---

## 4. 주요 기능

### 이상징후 탐지 및 자동 처리

5가지 이상징후를 자동 감지하고 심각도에 따라 처리합니다.

| 유형 | 조건 | 심각도 |
|------|------|--------|
| 재고 부족 (LOW_STOCK) | 1일치 이하 재고 | CRITICAL |
| 재고 부족 (LOW_STOCK) | 3일치 이하 재고 | HIGH |
| 재고 부족 (LOW_STOCK) | 7일치 이하 재고 | MEDIUM |
| 판매 급등 (SALES_SURGE) | 전주 대비 100% 이상 | CRITICAL |
| 판매 급등 (SALES_SURGE) | 전주 대비 70% 이상 | HIGH |
| 판매 급락 (SALES_DROP) | 전주 대비 50% 이상 감소 | MEDIUM |
| 재고 과잉 (OVER_STOCK) | 안전재고 기준 초과 | LOW |
| 장기 재고 (LONG_TERM_STOCK) | 장기 미판매 | LOW |

LOW_STOCK·SALES_SURGE → 발주 자동 생성 / OVER_STOCK·SALES_DROP → 할인 판매 시트 기록

### 발주 승인 워크플로우

금액 기준으로 결재선이 자동 분기됩니다.

```
총 발주 금액
  < ORDER_AUTO_APPROVE_LIMIT (기본 100,000원) → SYSTEM 자동 승인
  < ORDER_MANAGER_APPROVAL_LIMIT (기본 1,000,000원) → ADMIN 승인 필요
  그 이상 → SUPERADMIN 승인 필요
```

Slack 버튼 클릭으로도 승인·거절이 가능하며, 역할 검증이 적용됩니다.

### 선제 발주 (Proactive Ordering)

이상징후가 발생하기 전에 먼저 대응합니다.

```
매일 01:00 수요 예측 분석 완료
  → 01:10 안전재고 자동 재계산
  → 01:15 잔여 재고 7일 이하 예상 상품 자동 발주 제안 생성
           (기존 미해결 이상징후 상품, 기존 PENDING 발주 상품 중복 제외)
```

### 공급업체 관리 및 입고 검수

- 공급업체별 납기 준수율·평균 지연일수 자동 집계
- 발주 승인 후 입고 검수 생성 → 실입고·불량·반품 수량 기록
- 입고 완료 시 DB 재고 자동 반영 + Google Sheets 재고현황 자동 업데이트

### 실시간 알림 (SSE + Slack + Email)

CRITICAL/HIGH 이상징후 감지 시 묶음 알림을 동시에 전송합니다.

```
ALERT_CHANNEL 설정에 따라:
  slack → Slack 채널 블록 메시지
  email → 담당자 이메일
  sse   → 브라우저 실시간 알림 (벨 아이콘)
  both  → 전부 동시 발송
```

알림 이력은 DB에 저장되어 대시보드에서 조회·읽음 처리가 가능합니다.

---

## 5. 자동화 스케줄

Celery Beat가 아래 스케줄을 자동 실행합니다.

| 스케줄명 | 실행 시각 | 동작 |
|----------|----------|------|
| daily-report | 매일 00:00 | 일일 보고서 생성 + PDF + Slack/Email 발송 |
| demand-forecast | 매일 01:00 | 14일 수요 예측 분석 |
| safety-stock-recalc | 매일 01:10 | 안전재고 자동 재계산 |
| proactive-order | 매일 01:15 | 선제 발주 제안 생성 |
| turnover-analysis | 매일 01:30 | 재고 회전율 분석 |
| cleanup-data | 매일 02:00 | 오래된 데이터 정리 |
| abc-analysis | 매일 02:30 | ABC 등급 분석 |
| sync-sheets-to-db | 15분마다 | Google Sheets → DB 증분 동기화 |
| daily-crawler | 매일 23:00 | 크롤러 실행 |

모든 스케줄은 관리자 대시보드에서 즉시 실행이 가능합니다.

---

## 6. AI Agent 기능

LangChain ReAct Agent 기반으로 자연어 명령을 실제 작업으로 처리합니다.

### Read Tools (조회)

| Tool | 동작 |
|------|------|
| `get_low_stock` | 재고 부족 상품 목록 조회 |
| `get_top_sales_tool` | 최근 N일 판매 상위 상품 조회 |
| `get_stock_by_product` | 상품별 현재 재고 조회 |
| `get_sales_trend_tool` | 상품별 판매 트렌드 조회 |
| `get_anomalies` | 이상징후 목록 조회 (id 포함) |
| `get_demand_forecast_tool` | 14일 수요 예측 결과 조회 |
| `generate_report` | 일일 보고서 즉시 생성 트리거 |

### Write Tools (실행)

| Tool | 동작 |
|------|------|
| `approve_anomaly_orders` | 이상징후 기반 발주 자동 생성 + 즉시 승인 |
| `resolve_anomaly_tool` | 이상징후 해결 처리 |
| `generate_order_proposals` | 발주 제안 생성 (승인 대기) |

**대화 예시:**

```
사용자: "긴급 재고 부족 상품 전부 발주해줘"
Agent:  → get_anomalies("unresolved") 호출
        → approve_anomaly_orders("") 호출
        → "LOW_STOCK 상품 7건 발주 자동 승인 완료했습니다" 응답

사용자: "다음 주 재고 위험 상품 알려줘"
Agent:  → get_demand_forecast_tool() 호출
        → "14일 내 재고 부족 예상 35건 (부족분 큰 순): ..." 응답
```

역할별 일일 사용 한도가 적용됩니다 (SUPERADMIN 무제한 / ADMIN 50회 / READONLY 10회).

---

## 7. 프로젝트 구조

```
SCM_agent/
├── app/                          # FastAPI 백엔드
│   ├── api/                      # 라우터 (auth, sheets, orders, alerts, suppliers...)
│   ├── ai/                       # LangChain Agent, Tools, 감성 분석
│   ├── analyzer/                 # 재고·판매·수요·회전율·ABC 분석기
│   ├── celery_app/               # Celery Tasks, Beat Schedule
│   ├── crawler/                  # 데이터 크롤러 및 Excel 파서
│   ├── db/                       # SQLAlchemy 모델, Repository, Sync
│   ├── notifier/                 # Slack, Email, SSE 알림
│   ├── report/                   # PDF 보고서 생성
│   ├── scheduler/                # Jobs (일일 보고서 메인 로직)
│   ├── services/                 # 비즈니스 서비스 레이어
│   └── sheets/                   # Google Sheets Reader/Writer
│
├── admin/                        # Next.js 14 프론트엔드
│   ├── app/dashboard/            # 대시보드 페이지들
│   │   ├── anomalies/            # 이상징후 탭
│   │   ├── orders/               # 발주 관리 탭
│   │   ├── suppliers/            # 공급업체 탭
│   │   ├── stats/                # 통계 탭 (수요예측, 회전율, ABC)
│   │   ├── reports/              # 보고서 탭
│   │   ├── sheets/               # 데이터 시트 탭
│   │   ├── scheduler/            # 스케줄 관리 탭
│   │   ├── chat/                 # AI 챗봇 탭
│   │   └── settings/             # 설정 탭
│   └── lib/                      # API 클라이언트, Types, Hooks
│
├── prompts/                      # Agent 프롬프트 템플릿
├── tests/                        # pytest 테스트
└── docker-compose.yml
```

---

## 8. 환경변수 설정

```env
# DB
DB_HOST=db
DB_PORT=3306
DB_NAME=scm_db
DB_USER=scm_user
DB_PASSWORD=your_password
DB_ROOT_PASSWORD=your_root_password

# Redis / RabbitMQ
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

# Google Sheets
SPREADSHEET_ID=your_spreadsheet_id
GOOGLE_CREDENTIALS_PATH=credentials.json

# OpenAI
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini

# Slack
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_SIGNING_SECRET=your_signing_secret
SLACK_CHANNEL_ID=your_channel_id

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# JWT
JWT_SECRET_KEY=your_secret_key

# 발주 결재선 (선택 — 기본값 있음)
ORDER_AUTO_APPROVE_LIMIT=100000
ORDER_MANAGER_APPROVAL_LIMIT=1000000

# 선제 발주 임계값 (선택)
PROACTIVE_ORDER_DAYS=7
```

---

## 9. 테스트

```bash
# 전체 테스트 실행
docker exec scm_agent pytest tests/ -v

# 커버리지 포함
docker exec scm_agent pytest tests/ --cov=app --cov-report=term-missing
```

SQLite in-memory + StaticPool으로 MariaDB 없이 테스트가 실행됩니다.

---

## 10. API 문서

서버 실행 후 Swagger UI에서 전체 API를 확인할 수 있습니다.

```
http://localhost:8000/docs
```

주요 엔드포인트:

| 그룹 | 경로 | 설명 |
|------|------|------|
| 인증 | `POST /scm/auth/login` | JWT 로그인 |
| 이상징후 | `GET /scm/anomalies` | 이상징후 목록 조회 |
| 발주 | `POST /scm/orders/proposals/generate` | 발주 제안 생성 |
| 발주 | `PATCH /scm/orders/proposals/{id}/approve` | 발주 승인 |
| 공급업체 | `GET /scm/suppliers` | 공급업체 목록 |
| 공급업체 | `PATCH /scm/suppliers/inspections/{id}/complete` | 입고 검수 완료 |
| 보고서 | `POST /scm/report/run` | 보고서 즉시 생성 |
| 스케줄 | `POST /scm/scheduler/trigger-proactive-order` | 선제 발주 즉시 실행 |
| 챗봇 | `POST /scm/chat/query` | AI Agent 질의 |
| 알림 | `GET /scm/alerts/stream` | SSE 스트림 연결 |

---

## 라이선스

MIT License
````