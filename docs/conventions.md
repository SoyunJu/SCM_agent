# SCM Agent — 코딩 컨벤션 및 설계 규칙

> 이 문서는 프로젝트 전반에 걸쳐 반드시 지켜야 할 규칙을 정의합니다.
> 새로운 코드를 작성하거나 수정할 때 반드시 참조하세요.

---

## 1. Severity (심각도) 규칙

### 값 정의

모든 곳에서 **UPPERCASE** 고정:

```python
class Severity(str, enum.Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"
    CHECK    = "CHECK"
```

### Python: `norm()` 헬퍼 반드시 사용

**파일**: `app/utils/severity.py`

```python
from app.utils.severity import norm, rank, SEVERITY_RANK

# 비교 시
norm(item.get("severity"))           # → "CRITICAL" (str이든 enum이든 처리)
rank(item.get("severity"))           # → 3 (정렬용 숫자)

# 잘못된 방법 (사용 금지)
str(Severity.LOW)                    # → "Severity.LOW" (버그!)
item["severity"].lower()             # → 불일치 위험
```

`norm()` 구현:
```python
def norm(v: object) -> str:
    if v is None: return ""
    if hasattr(v, "value"): return str(v.value).upper()
    return str(v).upper()
```

### TypeScript: `normSev()` 헬퍼 사용

**파일**: `admin/lib/severity.ts`

```typescript
import { normSev, SEVERITY_KOR, SEVERITY_COLOR } from "@/lib/severity";

normSev(item.severity)               // → "CRITICAL"
SEVERITY_KOR["CRITICAL"]            // → "긴급"
SEVERITY_COLOR["HIGH"]              // → "text-orange-600 bg-orange-50"
```

### 금지 패턴

```python
# Python — 금지
if severity.lower() == "critical": ...    # norm() 사용
str(Severity.LOW)                         # norm() 사용
{"critical": ..., "high": ...}            # 소문자 키 금지
```

```typescript
// TypeScript — 금지
p.severity === "critical"               // normSev() 사용
```

---

## 2. Enum 값 규칙

모든 enum 값은 UPPERCASE로 고정하며, 비교 시 항상 대문자로 비교합니다.

| Enum | 값 |
|------|-----|
| `Severity` | `LOW \| MEDIUM \| HIGH \| CRITICAL \| CHECK` |
| `ProposalStatus` | `PENDING \| APPROVED \| REJECTED` |
| `AdminRole` | `SUPERADMIN \| ADMIN \| READONLY` |
| `ProductStatus` | `ACTIVE \| INACTIVE \| SAMPLE` |
| `ReportType` | `DAILY \| WEEKLY \| MANUAL` |
| `ExecutionStatus` | `SUCCESS \| FAILURE \| IN_PROGRESS` |
| `AnomalyType` | `LOW_STOCK \| OVER_STOCK \| SALES_SURGE \| SALES_DROP \| LONG_TERM_STOCK` |

### AdminRole 입력 처리

사용자 입력(문자열)을 enum으로 변환할 때 반드시 `.upper()` 적용:

```python
AdminRole(body.role.upper())    # "admin" → AdminRole.ADMIN
```

---

## 3. RBAC (역할 기반 접근 제어) 규칙

### 권한 체계

| 역할 | 조회 | 보고서 생성 | 발주 승인 | 이상징후 해결 | 계정 관리 |
|------|------|-----------|---------|------------|---------|
| `READONLY` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `ADMIN` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `SUPERADMIN` | ✅ | ✅ | ✅ | ✅ | ✅ |

### 백엔드 구현

```python
# 의존성 주입으로 권한 확인
from app.api.auth_router import require_admin, require_superadmin

@router.post("/run")
async def run_report(current_user = Depends(require_admin)):
    ...
```

### 프론트엔드 구현

```typescript
const role = localStorage.getItem("user_role") ?? "readonly";
const isReadonly = role === "readonly";

// 버튼 숨김
{!isReadonly && <button onClick={handleAction}>보고서 생성</button>}

// 탭 숨김 (관리자 탭)
{role === "superadmin" && <TabItem href="/dashboard/admin">관리자 관리</TabItem>}
```

---

## 4. API 경로 규칙

- 모든 엔드포인트는 `/scm/` prefix를 가집니다
- RESTful 명사형 경로 사용

```
/scm/auth/login
/scm/sheets/master
/scm/sheets/sales
/scm/sheets/stock
/scm/orders/proposals
/scm/orders/proposals/{id}/approve
/scm/report/run
/scm/report/history
/scm/alerts/stream
/scm/scheduler/config
/scm/admin/users
/scm/health
```

---

## 5. CSV 다운로드 규칙

한글이 포함된 CSV는 반드시 `BytesIO` + UTF-8 BOM을 사용합니다.

```python
# 올바른 방법
import io
buf = io.BytesIO()
buf.write(b'\xef\xbb\xbf')          # UTF-8 BOM (Excel에서 한글 깨짐 방지)
df.to_csv(buf, index=False, encoding="utf-8")
buf.seek(0)
return StreamingResponse(
    buf,
    media_type="text/csv; charset=utf-8-sig",
    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
)

# 잘못된 방법 (사용 금지)
buf = io.StringIO()
df.to_csv(buf, index=False, encoding="utf-8-sig")  # encoding 파라미터 무시됨
```

---

## 6. 프론트엔드 데이터 페칭 규칙

### React Query 사용 필수

직접 `useEffect` + `fetch`/`axios` 패턴은 사용하지 않습니다.

```typescript
// 올바른 방법
import { useQuery, useQueryClient } from "@tanstack/react-query";

const { data, isLoading } = useQuery({
    queryKey: ["sheets-master", page, search, category],
    queryFn: () => getSheetsMaster(page, 50, search, category).then(r => r.data),
    staleTime: 30_000,           // 30초 캐시
    keepPreviousData: true,      // 페이지 전환 시 이전 데이터 유지
});

// 쓰기 후 캐시 무효화
const qc = useQueryClient();
await someWriteApi();
qc.invalidateQueries({ queryKey: ["sheets-master"] });

// 잘못된 방법 (사용 금지)
useEffect(() => {
    fetch("/api/...").then(...)
}, []);
```

---

## 7. Google Sheets 동기화 규칙

### 쓰기 후 캐시 삭제 필수

```python
from app.cache.redis_client import cache_delete

def write_something_to_sheets():
    # ... gspread 쓰기 작업 ...
    cache_delete("sheets:상품마스터")    # 반드시 삭제
```

### Redis 캐시 키 패턴

```
sheets:상품마스터
sheets:일별판매
sheets:재고현황
crawler:results
```

---

## 8. DB 동기화 규칙

Google Sheets → MariaDB 동기화는 `SyncService`를 통해 일원화됩니다.
```python
# 올바른 방법 — 어디서든 SyncService 호출
from app.services.sync_service import SyncService
SyncService.sync_all_from_sheets(db)   # 전체 동기화
SyncService.sync_sales(db, df)         # 일별판매만
SyncService.sync_stock(db, df)         # 재고현황만

# 잘못된 방법 (사용 금지) — bulk_upsert 직접 호출
from app.db.sync import bulk_upsert_daily_sales
bulk_upsert_daily_sales(db, records)   # ← 매핑 로직 중복 발생
```

동기화 실행 시점:
- 앱 시작 시: `lifespan` → `_warmup_sheets` → `SyncService.sync_all_from_sheets`
- 수동 동기화: `POST /scm/sheets/sync` → `SyncService.sync_all_from_sheets`
- 일일 스케줄: `jobs.py` → `_sync_sheets_to_db` (SyncService 래퍼)
- 엑셀 업로드: `upload_excel` → `SyncService.sync_master/sales/stock`

---

## 9. 로깅 규칙

**Loguru** 사용, `print()` 사용 금지.

```python
from loguru import logger

logger.info("작업 시작")
logger.warning("비중요 실패 (스킵)")
logger.error("중요 오류 발생")
```

SQLAlchemy 쿼리 로그는 `logging.WARNING`으로 억제 (`main.py` 참조).

---

## 10. 에러 처리 규칙

- 외부 서비스(Slack, Email, PDF 생성) 실패 시 `logger.warning()` + 계속 진행
- DB 작업 실패는 `logger.error()` + 상태 업데이트 (`ExecutionStatus.FAILURE`)
- API 라우터에서 예상 가능한 에러는 `HTTPException` 사용

```python
# 비중요 작업 (스킵 허용)
try:
    notify_slack(...)
except Exception as e:
    logger.warning(f"Slack 알림 실패(스킵): {e}")

# 중요 작업
try:
    bulk_upsert_products(db, products)
except Exception as e:
    logger.error(f"DB 동기화 실패: {e}")
    raise
```
