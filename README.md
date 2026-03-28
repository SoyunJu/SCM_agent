# SCM Agent

쇼핑몰 공급망(Supply Chain) 자동 분석·관리 플랫폼.
Google Sheets 재고·판매 데이터를 기반으로 이상징후를 탐지하고, 발주 제안을 생성하며, Slack과 이메일로 보고서를 자동 발송합니다.

---

## 기능

- **이상징후 탐지** — 재고 부족, 과재고, 판매 급등·급락 자동 감지 (심각도 5단계)
- **AI 발주 제안** — LLM이 이상징후를 분석해 발주 수량·단가 산출, 관리자 승인 워크플로우
- **일별 보고서** — PDF 자동 생성 후 Slack 채널 및 이메일 발송
- **통계 분석** — ABC 분류, 수요 예측, 재고 회전율, 판매 추이 차트
- **AI 채팅** — 자연어로 재고·판매 데이터 실시간 조회 (GPT-4o-mini + LangChain)
- **Slack 인터랙션** — Slack에서 발주 승인/거절 버튼으로 즉시 처리

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI, Python 3.11, SQLAlchemy 2.0 |
| Database | MariaDB 11.3 |
| Cache / Queue | Redis 7, Celery 5.3, RabbitMQ 3.12 |
| Frontend | Next.js (TypeScript), React Query v5 |
| AI / 분석 | OpenAI GPT-4o-mini, LangChain, HuggingFace KR-FinBert |
| 연동 | Google Sheets (gspread), Slack SDK, Gmail SMTP |
| 인프라 | Docker + docker-compose |

---

## 빠른 시작

### 1. 자격증명 준비

```bash
# Google Service Account JSON
mkdir -p credentials
cp /path/to/service-account.json ./credentials/service_account.json

# 환경변수 파일
cp .env.example .env
# .env 편집: SPREADSHEET_ID, OPENAI_API_KEY, SLACK_BOT_TOKEN 등 필수값 입력
```

### 2. 실행

```bash
docker-compose up -d --build
```

### 3. 접속

| 서비스 | URL | 기본 계정 |
|--------|-----|----------|
| 관리자 UI | http://localhost:3001 | admin / admin1! |
| API | http://localhost:8000 | — |
| API 문서 | http://localhost:8000/docs | — |
| RabbitMQ UI | http://localhost:15672 | guest / guest |

자세한 설정은 [`docs/setup.md`](./docs/setup.md) 참조.

---

## 프로젝트 구조

```
SCM_agent/
├── app/                    # FastAPI 백엔드
│   ├── api/                # 라우터 (13개)
│   ├── analyzer/           # 분석 모듈 (ABC, 수요예측, 재고, 판매, 회전율)
│   ├── ai/                 # LLM 에이전트, 발주 제안, 감성 분석
│   ├── db/                 # ORM 모델, Repository, Sheets→DB 동기화
│   ├── notifier/           # Slack / Email 알림
│   ├── report/             # PDF 보고서 생성
│   ├── scheduler/          # 일일 작업 오케스트레이터
│   ├── sheets/             # Google Sheets 읽기/쓰기 + Redis 캐시
│   ├── utils/              # severity 헬퍼 등 공통 유틸
│   └── main.py             # 앱 진입점
├── admin/                  # Next.js 관리자 프론트엔드
├── docs/                   # 프로젝트 문서
├── scripts/                # 유틸리티 스크립트
├── tests/                  # 테스트
├── docker-compose.yml
└── .env.example
```

---

## 문서

| 문서 | 내용 |
|------|------|
| [docs/overview.md](./docs/overview.md) | 프로젝트 소개, 기술 스택, 단계 현황 |
| [docs/setup.md](./docs/setup.md) | 환경 설정 및 실행 가이드 |
| [docs/architecture.md](./docs/architecture.md) | 시스템 구조, 데이터 흐름, 서비스 구성 |
| [docs/conventions.md](./docs/conventions.md) | 코딩 컨벤션 (Severity 규칙, RBAC, CSV 인코딩 등) |
| [docs/api.md](./docs/api.md) | API 엔드포인트 전체 레퍼런스 |
| [docs/data-model.md](./docs/data-model.md) | DB 스키마, Sheets 컬럼 매핑, Enum 정의 |
| [docs/handoff.md](./docs/handoff.md) | 개발 현황, 미해결 이슈, 다음 작업 안내 |
| [docs/architecture-handoff.md](./docs/architecture-handoff.md) | Phase 5 대용량 처리 + Celery 설계 |

---

## 개발 현황

| Phase | 내용 | 상태 |
|-------|------|------|
| 1~3 | 기본 파이프라인, Slack 알림, LLM 채팅 | 완료 |
| 4 | 버그 수정, RBAC, 대시보드 완성 | 완료 |
| 5 | MariaDB SoT 전환, Celery 도입, 대용량 처리 | 설계 완료, 미구현 |
