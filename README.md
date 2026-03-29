# SCM Agent

> 쇼핑몰 공급망 자동화 플랫폼 — 재고·판매 이상징후 탐지부터 발주 자동처리, AI 보고서까지

---

## 주요 기능

- **이상징후 자동 처리** — 재고부족·판매급등 시 발주 제안 자동 생성·승인, 과재고·판매급락 시 최대 할인율 산출 후 판매 처리
- **AI 발주 제안** — 일평균 판매량·리드타임 기반 발주 수량 산출, 관리자 승인/거절/되돌리기 워크플로우
- **일별 보고서 자동화** — Celery Beat 기반 PDF 생성 + Slack·이메일 자동 발송
- **통계 분석** — ABC 분류, 수요 예측, 재고 회전율, 판매 추이 (상품코드·상품명 검색 지원)
- **AI 채팅** — 자연어로 재고·판매 데이터 실시간 조회 (GPT-4o-mini + LangChain)

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 |
| Database | MariaDB 11.3, Redis 7 |
| Task Queue | Celery 5.3, RabbitMQ 3.12 |
| Frontend | Next.js 14 (TypeScript), React Query v5 |
| AI | OpenAI GPT-4o-mini, LangChain, HuggingFace KR-FinBert |
| 외부 연동 | Google Sheets API, Slack SDK, Gmail SMTP |
| 인프라 | Docker, docker-compose, GitHub Actions CI |

---

## 아키텍처
```
Google Sheets ──► Celery Beat (15분)──► MariaDB (SoT)
                                            │
                  FastAPI (REST API) ◄──────┘
                       │
          ┌────────────┼────────────┐
       Slack        PDF 보고서    Next.js 관리자 UI
```

**3계층 구조:** Router (위임) → Service (비즈니스 로직) → Repository (DB)

---

## 실행
```bash
# 1. 환경변수 설정
cp .env.example .env   # SPREADSHEET_ID, OPENAI_API_KEY, SLACK_BOT_TOKEN 등 입력

# 2. Google Service Account 키 배치
cp service-account.json ./credentials/service_account.json

# 3. 실행
docker-compose up -d --build
```

| 서비스 | URL | 계정 |
|--------|-----|------|
| 관리자 UI | http://localhost:3001 | admin / admin1! |
| API 문서 | http://localhost:8000/docs | — |

---

## 프로젝트 구조
```
SCM_agent/
├── app/
│   ├── api/           # REST API 라우터
│   ├── services/      # 비즈니스 로직 (Service Layer)
│   ├── db/            # ORM 모델, Repository
│   ├── analyzer/      # 재고·판매 이상징후 분석
│   ├── ai/            # LLM 에이전트, 발주 제안
│   ├── celery_app/    # Celery 태스크 + Beat 스케줄
│   ├── notifier/      # Slack · Email 알림
│   └── report/        # PDF 보고서 생성
├── admin/             # Next.js 관리자 프론트엔드
├── tests/             # 단위 + 통합 테스트 (75개)
├── docs/              # 설계 문서 및 가정 사항
└── docker-compose.yml
```

---

## 개발 현황

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 – 3 | 데이터 수집, 이상징후 탐지, Slack 알림, LLM 채팅 | ✅ |
| 4 | RBAC, Celery Beat, Service Layer 리팩토링 | ✅ |
| 5 | MariaDB SoT 전환, Celery 고도화, CI/CD (커버리지 51%) | ✅ |
| 고도화 | 이상징후 자동처리, 재고통계 검색, Beat 분석 스케줄 | ✅ |

> 가정 사항: [`docs/assumptions.md`](./docs/assumptions.md)