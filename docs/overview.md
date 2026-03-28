# SCM Agent — 프로젝트 개요

> 버전: 0.3.0 | 상태: Phase 4 완료 / Phase 5 설계 완료

---

## 무엇인가

**SCM Agent**는 쇼핑몰 공급망(Supply Chain)을 자동 분석·관리하는 지능형 에이전트 플랫폼입니다.
Google Sheets에 기록된 재고·판매 데이터를 주기적으로 수집·분석하고, 이상징후를 감지하여 Slack 알림과 PDF 보고서를 자동 발송합니다.

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **이상징후 탐지** | 재고 부족·과재고·판매 급등·급락을 자동 감지 (심각도: CRITICAL/HIGH/MEDIUM/LOW/CHECK) |
| **AI 발주 제안** | LLM이 이상징후를 분석해 발주 수량·단가를 자동 산출, 관리자 승인 워크플로우 제공 |
| **일별 보고서** | 분석 결과를 PDF로 생성, Slack 채널 및 이메일로 자동 발송 |
| **채팅 질의** | 자연어로 재고·판매 데이터 조회 (LangChain + GPT-4o-mini) |
| **Slack 인터랙션** | Slack에서 발주 승인/거절 버튼 클릭으로 실시간 처리 |
| **통계 분석** | ABC 분류, 수요 예측, 재고 회전율, 판매 추이 차트 |

---

## 기술 스택

### Backend
| 항목 | 기술 |
|------|------|
| 프레임워크 | FastAPI 0.111.0 (ASGI) |
| 서버 | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| DB | MariaDB 11.3 |
| 캐시 | Redis 7 |
| 태스크 큐 | Celery 5.3 + RabbitMQ 3.12 |
| 언어 | Python 3.11 |

### Frontend
| 항목 | 기술 |
|------|------|
| 프레임워크 | Next.js (App Router) |
| 언어 | TypeScript |
| HTTP 클라이언트 | Axios + React Query v5 |
| 포트 | 3001 |

### AI / 분석
| 항목 | 기술 |
|------|------|
| LLM | OpenAI GPT-4o-mini |
| 에이전트 | LangChain 0.2 |
| 한국어 NLP | HuggingFace KR-FinBert-SC |
| 데이터 처리 | pandas 2.2 |

### 인프라 / 연동
| 항목 | 기술 |
|------|------|
| 컨테이너 | Docker + docker-compose |
| Sheets 연동 | gspread 6.1 + Google Service Account |
| 문서 생성 | ReportLab + xhtml2pdf |
| 알림 | slack-sdk 3.27 |
| 이메일 | SMTP (Gmail) |

---

## 프로젝트 단계

| 단계 | 내용 | 상태 |
|------|------|------|
| Phase 1 | 기본 데이터 수집·분석 파이프라인 | 완료 |
| Phase 2 | Slack 알림 + 발주 제안 워크플로우 | 완료 |
| Phase 3 | AI 채팅 에이전트 + PDF 보고서 | 완료 |
| Phase 4 | 버그 수정 + RBAC + 대시보드 완성 | 완료 |
| Phase 5 | 대용량 처리 (MariaDB SoT + Celery 전환) | 설계 완료, 미구현 |

Phase 5 상세 설계는 [`architecture-handoff.md`](./architecture-handoff.md) 참조.
