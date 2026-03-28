# SCM Agent — API 레퍼런스

> Base URL: `http://localhost:8000`
> 모든 엔드포인트 prefix: `/scm/`
> 인증: `Authorization: Bearer {JWT_TOKEN}` 헤더

---

## 인증 (Auth)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `POST` | `/scm/auth/login` | 공개 | 로그인 (Form: username, password) → `access_token` |
| `GET` | `/scm/auth/me` | 인증 | 현재 사용자 정보 (username, role) |

---

## 데이터 시트 (Sheets)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/sheets/categories` | 인증 | 카테고리 목록 |
| `GET` | `/scm/sheets/master` | 인증 | 상품마스터 조회 (page, page_size, search, category, download) |
| `GET` | `/scm/sheets/sales` | 인증 | 일별판매 조회 (days, page, page_size, search, category, download) |
| `GET` | `/scm/sheets/stock` | 인증 | 재고현황 조회 (page, page_size, search, category, download) |
| `GET` | `/scm/sheets/orders` | 인증 | 주문 목록 (status, days, page, page_size) |
| `POST` | `/scm/sheets/upload-excel` | ADMIN | Excel 파일 업로드 (multipart: file, sheet_type) |
| `POST` | `/scm/sheets/sync` | ADMIN | Google Sheets → DB 수동 동기화 |
| `PUT` | `/scm/sheets/products/{code}` | ADMIN | 상품 정보 수정 (name, category, safety_stock, status) |

### 통계 분석

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/sheets/stats/sales` | 인증 | 판매 통계 (period: daily\|weekly\|monthly) |
| `GET` | `/scm/sheets/stats/stock` | 인증 | 재고 통계 (severity별 카운트, 심각 상품 목록) |
| `GET` | `/scm/sheets/stats/abc` | 인증 | ABC 분류 결과 (days=90) |
| `GET` | `/scm/sheets/stats/demand` | 인증 | 수요 예측 (forecast_days, page, page_size, category) |
| `GET` | `/scm/sheets/stats/turnover` | 인증 | 재고 회전율 (days, page, page_size, category) |

---

## 보고서 (Report)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `POST` | `/scm/report/run` | ADMIN | 보고서 즉시 생성 (severity_filter, category_filter) → `execution_id` |
| `GET` | `/scm/report/status/{execution_id}` | 인증 | 보고서 실행 상태 폴링 |
| `GET` | `/scm/report/history` | 인증 | 실행 이력 (limit, offset) |
| `GET` | `/scm/report/anomalies` | 인증 | 이상징후 목록 (is_resolved, page, page_size) |
| `PATCH` | `/scm/report/anomalies/{id}/resolve` | ADMIN | 이상징후 해결 처리 |
| `GET` | `/scm/report/pdf-list` | 인증 | 생성된 PDF 목록 |
| `GET` | `/scm/report/pdf/{filename}` | 인증 | PDF 파일 다운로드 |
| `DELETE` | `/scm/report/pdf/{filename}` | ADMIN | PDF 파일 삭제 |

---

## 발주 관리 (Orders)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/orders/proposals` | 인증 | 발주 제안 목록 (status, limit, offset) |
| `POST` | `/scm/orders/proposals/generate` | ADMIN | 발주 제안 생성 (severity_override: LOW\|MEDIUM\|HIGH\|CRITICAL) |
| `PUT` | `/scm/orders/proposals/{id}` | ADMIN | 발주 제안 수정 (proposed_qty, unit_price) |
| `PATCH` | `/scm/orders/proposals/{id}/approve` | ADMIN | 발주 승인 |
| `PATCH` | `/scm/orders/proposals/{id}/reject` | ADMIN | 발주 거절 |

---

## 채팅 (Chat)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `POST` | `/scm/chat/query` | 인증 | 자연어 질의 (message, session_id, user_id) |
| `GET` | `/scm/chat/history` | 인증 | 대화 이력 (session_id, days) |

---

## 알림 (Alerts)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/alerts/stream` | 인증 | SSE 실시간 알림 스트림 |
| `GET` | `/scm/alerts/unread-count` | 인증 | 미읽음 알림 수 |

---

## 스케줄러 (Scheduler)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/scheduler/config` | ADMIN | 스케줄 설정 조회 |
| `PUT` | `/scm/scheduler/config` | ADMIN | 스케줄 설정 수정 (schedule_hour, schedule_minute, timezone, is_active) |
| `GET` | `/scm/scheduler/status` | ADMIN | 스케줄러 실행 상태 |

---

## 설정 (Settings)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/settings` | ADMIN | 전체 설정 조회 (key-value) |
| `PUT` | `/scm/settings` | ADMIN | 설정 일괄 저장 |

주요 설정 키:

| 키 | 기본값 | 설명 |
|----|--------|------|
| `SAFETY_STOCK_DAYS` | `7` | 안전재고 기준일 |
| `SAFETY_STOCK_DEFAULT` | `10` | 기본 안전재고 수량 |
| `LOW_STOCK_CRITICAL_DAYS` | `1` | 재고 CRITICAL 임계일 |
| `LOW_STOCK_HIGH_DAYS` | `3` | 재고 HIGH 임계일 |
| `LOW_STOCK_MEDIUM_DAYS` | `7` | 재고 MEDIUM 임계일 |
| `SALES_SURGE_THRESHOLD` | `50` | 판매 급등 임계값 (%) |
| `SALES_DROP_THRESHOLD` | `50` | 판매 급락 임계값 (%) |

---

## 관리자 계정 (Admin)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/admin/users` | SUPERADMIN | 계정 목록 |
| `POST` | `/scm/admin/users` | SUPERADMIN | 계정 생성 (username, password, role) |
| `PUT` | `/scm/admin/users/{id}` | SUPERADMIN | 계정 수정 (role, email, slack_user_id, is_active) |
| `DELETE` | `/scm/admin/users/{id}` | SUPERADMIN | 계정 삭제 |
| `GET` | `/scm/admin/me` | 인증 | 내 프로필 조회 |
| `PUT` | `/scm/admin/me/profile` | 인증 | 내 프로필 수정 (email, slack_user_id) |
| `PUT` | `/scm/admin/me/password` | 인증 | 비밀번호 변경 (current_password, new_password) |

---

## 상품 (Product)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `PATCH` | `/scm/products/{code}/status` | ADMIN | 상품 상태 변경 (ACTIVE\|INACTIVE\|SAMPLE) |

---

## 태스크 (Task)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/tasks/{task_id}/status` | 인증 | Celery 비동기 작업 상태 조회 |

---

## Slack 인터랙션

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `POST` | `/scm/slack/interactions` | Slack 서명 | Slack 인터랙티브 버튼 처리 (발주 승인/거절) |
| `POST` | `/scm/slack/commands` | Slack 서명 | Slack 슬래시 커맨드 처리 |

---

## 헬스 체크

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| `GET` | `/scm/health` | 공개 | 서버 상태 확인 → `{"status": "ok"}` |

---

## 공통 응답 형식

### 페이지네이션

```json
{
    "items": [...],
    "total": 150,
    "page": 1,
    "page_size": 50
}
```

### 에러

```json
{
    "detail": "에러 메시지"
}
```

HTTP 상태 코드:
- `401` Unauthorized: 토큰 없음/만료 → 자동 로그인 페이지 이동
- `403` Forbidden: 권한 부족
- `404` Not Found: 리소스 없음
- `422` Unprocessable Entity: 입력값 검증 실패
