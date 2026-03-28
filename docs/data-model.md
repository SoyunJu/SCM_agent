# SCM Agent — 데이터 모델

---

## Google Sheets 컬럼 정의

### 상품마스터 (Product Master)

| 컬럼명 (Sheets) | 타입 | 설명 | DB 필드 (products) |
|----------------|------|------|-------------------|
| `상품코드` | string | 고유 식별자 (PK) | `code` |
| `상품명` | string | 상품 이름 | `name` |
| `카테고리` | string | 분류 (예: 상의, 하의, 아우터) | `category` |
| `안전재고기준` | integer | 안전재고 수량 임계값 | `safety_stock` |

### 일별판매 (Daily Sales)

| 컬럼명 (Sheets) | 타입 | 설명 | DB 필드 (daily_sales) |
|----------------|------|------|----------------------|
| `날짜` | string | 판매일 (YYYY-MM-DD) | `date` |
| `상품코드` | string | 상품 식별자 | `product_code` |
| `판매수량` | integer | 해당일 판매 수량 | `qty` |
| `매출액` | float | 해당일 매출 금액 (원) | `revenue` |

### 재고현황 (Stock Status)

| 컬럼명 (Sheets) | 타입 | 설명 | DB 필드 (stock_levels) |
|----------------|------|------|----------------------|
| `상품코드` | string | 상품 식별자 (PK) | `product_code` |
| `현재재고` | integer | 현재 재고 수량 | `current_stock` |
| `입고예정일` | string | 입고 예정 날짜 (YYYY-MM-DD, 선택) | `restock_date` |
| `입고예정수량` | integer | 입고 예정 수량 (선택) | `restock_qty` |

### 분석결과 (Analysis Results) — 앱이 자동 생성

이상징후 분석 결과를 기록. JSON 직렬화된 컬럼 포함.

### 주문관리 (Order Management) — 앱이 자동 생성

| 컬럼명 | 설명 |
|--------|------|
| `주문코드` | 발주 고유 코드 |
| `상품코드` | 상품 식별자 |
| `상품명` | 상품 이름 |
| `발주수량` | 발주 수량 |
| `발주일` | 발주 날짜 |
| `예정납기일` | 납기 예정일 |
| `상태` | 주문 상태 |

---

## MariaDB 테이블 정의

### products

```sql
CREATE TABLE products (
    code         VARCHAR(100)  NOT NULL  PRIMARY KEY,
    name         VARCHAR(255)  NOT NULL,
    category     VARCHAR(100)  DEFAULT NULL,
    safety_stock INTEGER       NOT NULL DEFAULT 0,
    status       ENUM('ACTIVE','INACTIVE','SAMPLE') DEFAULT 'ACTIVE',
    source       VARCHAR(50)   DEFAULT 'sheets',
    updated_at   DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_status (status)
);
```

### daily_sales

```sql
CREATE TABLE daily_sales (
    id           INTEGER  AUTO_INCREMENT PRIMARY KEY,
    date         DATE     NOT NULL,
    product_code VARCHAR(100) NOT NULL,
    qty          INTEGER  NOT NULL DEFAULT 0,
    revenue      FLOAT    NOT NULL DEFAULT 0,
    UNIQUE KEY uq_date_code (date, product_code),
    INDEX idx_date (date),
    INDEX idx_product_code (product_code)
);
```

### stock_levels

```sql
CREATE TABLE stock_levels (
    product_code  VARCHAR(100) NOT NULL PRIMARY KEY,
    current_stock INTEGER      NOT NULL DEFAULT 0,
    restock_date  DATE         DEFAULT NULL,
    restock_qty   INTEGER      DEFAULT NULL,
    updated_at    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### anomaly_logs

```sql
CREATE TABLE anomaly_logs (
    id                  INTEGER AUTO_INCREMENT PRIMARY KEY,
    detected_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    product_code        VARCHAR(100),
    product_name        VARCHAR(255),
    category            VARCHAR(100),
    anomaly_type        ENUM('LOW_STOCK','OVER_STOCK','SALES_SURGE','SALES_DROP','LONG_TERM_STOCK'),
    current_stock       INTEGER,
    daily_avg_sales     FLOAT,
    days_until_stockout FLOAT,
    severity            ENUM('LOW','MEDIUM','HIGH','CRITICAL','CHECK'),
    is_resolved         BOOLEAN DEFAULT FALSE,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_severity (severity),
    INDEX idx_is_resolved (is_resolved)
);
```

### order_proposals

```sql
CREATE TABLE order_proposals (
    id           INTEGER AUTO_INCREMENT PRIMARY KEY,
    product_code VARCHAR(100),
    product_name VARCHAR(255),
    category     VARCHAR(100),
    proposed_qty INTEGER,
    unit_price   FLOAT,
    reason       TEXT,
    status       ENUM('PENDING','APPROVED','REJECTED') DEFAULT 'PENDING',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_at  DATETIME,
    approved_by  VARCHAR(100),
    slack_ts     VARCHAR(100),
    slack_channel VARCHAR(100),
    INDEX idx_status (status)
);
```

### admin_users

```sql
CREATE TABLE admin_users (
    id              INTEGER AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role            ENUM('SUPERADMIN','ADMIN','READONLY') DEFAULT 'ADMIN',
    slack_user_id   VARCHAR(100),
    email           VARCHAR(255),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at   DATETIME
);
```

### report_executions

```sql
CREATE TABLE report_executions (
    id            INTEGER AUTO_INCREMENT PRIMARY KEY,
    executed_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    report_type   ENUM('DAILY','WEEKLY','MANUAL'),
    status        ENUM('SUCCESS','FAILURE','IN_PROGRESS'),
    docs_url      VARCHAR(500),
    slack_sent    BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### schedule_config

```sql
CREATE TABLE schedule_config (
    id              INTEGER AUTO_INCREMENT PRIMARY KEY,
    job_name        VARCHAR(100) NOT NULL UNIQUE,
    schedule_hour   INTEGER,
    schedule_minute INTEGER,
    timezone        VARCHAR(50) DEFAULT 'Asia/Seoul',
    is_active       BOOLEAN DEFAULT TRUE,
    last_run_at     DATETIME,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### system_settings

```sql
CREATE TABLE system_settings (
    id            INTEGER AUTO_INCREMENT PRIMARY KEY,
    setting_key   VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT,
    description   VARCHAR(500),
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### chat_history

```sql
CREATE TABLE chat_history (
    id         INTEGER AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255),
    user_id    VARCHAR(100),
    role       ENUM('USER','ASSISTANT'),
    message    TEXT,
    tool_used  VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id)
);
```

### analysis_cache

```sql
CREATE TABLE analysis_cache (
    id            INTEGER AUTO_INCREMENT PRIMARY KEY,
    analysis_type VARCHAR(100) NOT NULL,
    params_hash   CHAR(64) NOT NULL,     -- SHA256
    result_json   LONGTEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_type_hash (analysis_type, params_hash)
);
```

---

## Enum 전체 목록

| Enum 클래스 | 값 |
|------------|-----|
| `Severity` | `LOW \| MEDIUM \| HIGH \| CRITICAL \| CHECK` |
| `AnomalyType` | `LOW_STOCK \| OVER_STOCK \| SALES_SURGE \| SALES_DROP \| LONG_TERM_STOCK` |
| `ProposalStatus` | `PENDING \| APPROVED \| REJECTED` |
| `AdminRole` | `SUPERADMIN \| ADMIN \| READONLY` |
| `ProductStatus` | `ACTIVE \| INACTIVE \| SAMPLE` |
| `ReportType` | `DAILY \| WEEKLY \| MANUAL` |
| `ExecutionStatus` | `SUCCESS \| FAILURE \| IN_PROGRESS` |
| `ChatRole` | `USER \| ASSISTANT` |

> 모든 Enum 값은 **UPPERCASE** 고정. 비교 시 반드시 대소문자 정규화 적용 (`conventions.md` 참조).

---

## 이상징후 심각도 기준

재고 이상징후:

| 심각도 | 조건 |
|--------|------|
| `CRITICAL` | 잔여 재고일 < `LOW_STOCK_CRITICAL_DAYS` (기본 1일) |
| `HIGH` | 잔여 재고일 < `LOW_STOCK_HIGH_DAYS` (기본 3일) |
| `MEDIUM` | 잔여 재고일 < `LOW_STOCK_MEDIUM_DAYS` (기본 7일) |
| `LOW` | 안전재고 기준 미달이지만 여유 있음 |

판매 이상징후:

| 심각도 | 조건 |
|--------|------|
| `HIGH` | 전주 대비 판매량 변동 > `SALES_SURGE_THRESHOLD` (기본 50%) |
| `MEDIUM` | 전주 대비 판매량 변동 > 30% |

잔여 재고일 계산:
```
days_until_stockout = current_stock / daily_avg_sales
```
