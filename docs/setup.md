# SCM Agent — 환경 설정 가이드

---

## 사전 요구사항

- Docker & docker-compose
- Google Cloud 프로젝트 + Service Account (Sheets/Drive API 활성화)
- OpenAI API Key
- Slack App (Bot Token + Signing Secret)
- Gmail App Password (2FA 활성화 필요)

---

## 1. 자격증명 파일 준비

### Google Service Account

```bash
mkdir -p credentials
# Google Cloud Console에서 다운로드한 JSON 파일을 아래 경로에 복사
cp /path/to/service-account.json ./credentials/service_account.json
```

Service Account에 대상 스프레드시트의 **편집자** 권한을 부여해야 합니다.

---

## 2. `.env` 파일 설정

`.env.example`을 복사하여 편집합니다.

```bash
cp .env.example .env
```

### 필수 환경 변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `SPREADSHEET_ID` | Google Sheets 스프레드시트 ID | `15u-8kSlYojiNDa_Q7GXtC9gb-Nm1Xc3T5SMayynTjjI` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | 서비스 계정 JSON 경로 | `./credentials/service_account.json` |
| `OPENAI_API_KEY` | OpenAI API 키 | `sk-...` |
| `SLACK_BOT_TOKEN` | Slack Bot OAuth Token | `xoxb-...` |
| `SLACK_CHANNEL_ID` | 알림을 받을 Slack 채널 ID | `C0XXXXXXXX` |
| `SLACK_SIGNING_SECRET` | Slack 요청 검증용 서명 시크릿 | `abc123...` |
| `DB_PASSWORD` | MariaDB 사용자 비밀번호 | `yourpassword` |
| `DB_ROOT_PASSWORD` | MariaDB root 비밀번호 | `yourrootpassword` |
| `JWT_SECRET_KEY` | JWT 서명 키 (임의의 긴 문자열) | `supersecretkey` |

### 이메일 설정 (선택)

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `SMTP_HOST` | SMTP 서버 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 포트 | `587` |
| `SMTP_USER` | 발신 이메일 주소 | `youremail@gmail.com` |
| `SMTP_PASSWORD` | **Gmail App Password** (계정 비밀번호 아님) | `xxxx xxxx xxxx xxxx` |
| `ALERT_EMAIL_TO` | 수신 이메일 (콤마 구분) | `admin@company.com` |

> Gmail을 사용할 경우 Google 계정 → 보안 → 앱 비밀번호에서 App Password를 생성해야 합니다.

### 스케줄러 설정 (선택)

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `SCHEDULE_HOUR` | `0` | 일별 보고서 실행 시간 (시) |
| `SCHEDULE_MINUTE` | `0` | 일별 보고서 실행 시간 (분) |
| `TIMEZONE` | `Asia/Seoul` | 시간대 |
| `CRAWLER_SCHEDULE_HOUR` | `23` | 크롤러 실행 시간 |

---

## 3. Docker 실행

```bash
# 전체 스택 빌드 및 실행
docker-compose up -d --build

# 로그 확인
docker-compose logs -f api

# 중지
docker-compose down
```

### 서비스 포트 정리

| 서비스 | 포트 | 용도 |
|--------|------|------|
| `api` | 8000 | FastAPI 백엔드 |
| `frontend` | 3001 | Next.js 관리자 UI |
| `db` | 3307 | MariaDB (외부 접속용) |
| `redis` | 6379 | 캐시 |
| `rabbitmq` | 5672 | Celery 브로커 |
| `rabbitmq` | 15672 | RabbitMQ 관리 UI (guest/guest) |

---

## 4. 초기 접속

브라우저에서 `http://localhost:3001`로 접속합니다.

**기본 슈퍼어드민 계정** (앱 최초 실행 시 자동 생성):

| 항목 | 값 |
|------|----|
| ID | `admin` |
| PW | `admin1!` |

> 운영 환경에서는 반드시 비밀번호를 변경하세요 (관리자 관리 → 내 계정 수정).

---

## 5. Google Sheets 구조

스프레드시트에 다음 시트(탭)가 존재해야 합니다:

| 시트명 | 역할 |
|--------|------|
| `상품마스터` | 상품 기본 정보 |
| `일별판매` | 날짜별 판매 실적 |
| `재고현황` | 현재 재고 수량 |
| `분석결과` | 분석 결과 자동 기록 (앱이 생성) |
| `주문관리` | 발주 내역 (앱이 생성) |

각 시트의 컬럼 정의는 [`data-model.md`](./data-model.md)를 참조하세요.

---

## 6. 디렉터리 구조 (런타임 생성)

```
/reports/   — 생성된 PDF 보고서 저장
/logs/      — 일별 로그 파일 (scm_agent_YYYY-MM-DD.log)
```

Docker volume으로 호스트에 마운트되어 컨테이너 재시작 후에도 유지됩니다.
