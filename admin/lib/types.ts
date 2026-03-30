
export interface ReportExecution {
    id: number;
    executed_at: string;
    report_type: "daily" | "weekly" | "manual";
    status: "success" | "failure" | "in_progress";
    slack_sent: boolean;
    email_sent:    boolean;
    triggered_by:  string | null;
    error_message: string | null;
    created_at: string;
}

export interface AnomalyLog {
    id: number;
    detected_at: string;
    product_code: string;
    product_name: string;
    category?: string;
    anomaly_type: "LOW_STOCK" | "OVER_STOCK" | "SALES_SURGE" | "SALES_DROP" | "LONG_TERM_STOCK";
    current_stock: number | null;
    daily_avg_sales: number | null;
    days_until_stockout: number | null;
    severity: "LOW" | "CHECK" | "MEDIUM" | "HIGH" | "CRITICAL";
    is_resolved: boolean;
}

export interface ChatMessage {
    role: "USER" | "ASSISTANT";
    content: string;
    timestamp: Date;
}

export interface ScheduleConfig {
    job_name: string;
    schedule_hour: number;
    schedule_minute: number;
    timezone: string;
    is_active: boolean;
    last_run_at: string | null;
}

export interface SalesStatItem {
    날짜: string;
    판매수량: number;
    매출액: number;
}

export interface StockItem {
    상품코드: string;
    상품명: string;
    현재재고: number;
}

export interface PdfFile {
    filename: string;
    size_kb: number;
    created_at: string;
}

export interface AlertMessage {
    type: string;
    severity: string;
    product_code: string;
    product_name: string;
    anomaly_type: string;
    message: string;
}

export interface SystemSetting {
    key: string;
    value: string;
    default: string;
    description: string;
}

export interface OrderItem {
    주문코드: string;
    상품코드: string;
    상품명: string;
    발주수량: number;
    발주일: string;
    예정납기일: string;
    상태: "발주완료" | "입고중" | "입고완료" | "반품";
}

export interface OrderProposal {
    id: number;
    product_code: string;
    product_name: string | null;
    category: string | null;
    proposed_qty: number;
    unit_price: number;
    reason: string | null;
    status: "PENDING" | "APPROVED" | "REJECTED";
    required_role: "SYSTEM" | "ADMIN" | "SUPERADMIN";
    created_at: string;
    approved_at: string | null;
    approved_by: string | null;
}


export interface TaskStatusResponse {
    task_id: string;
    state: "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "REVOKED";
    message: string;
    result?: { items: any[]; from_cache: boolean; total?: number; total_pages?: number };
    error?: string;
    progress?: string;
}

export type ProductStatus = "active" | "inactive" | "sample";

export interface Product {
    product_code: string;
    product_name: string;
    category: string;
    status: ProductStatus;
    lead_time_days: number | null;
}

export interface AdminUser {
    id:            number;
    username:      string;
    role:          "superadmin" | "admin" | "readonly";
    slack_user_id: string | null;
    email:         string | null;
    is_active:     boolean;
    created_at:    string;
    last_login_at: string | null;
}

export interface Supplier {
    id:              number;
    name:            string;
    contact:         string | null;
    email:           string | null;
    phone:           string | null;
    lead_time_days:  number;
    is_active:       boolean;
    mapped_products: number;
    on_time_rate:    number | null;
    avg_delay_days:  number | null;
    created_at:      string;
}

export interface ReceivingInspection {
    id:                number;
    order_proposal_id: number | null;
    supplier_id:       number | null;
    product_code:      string;
    product_name:      string | null;
    ordered_qty:       number;
    received_qty:      number;
    defect_qty:        number;
    return_qty:        number;
    good_qty:          number;
    status:            "PENDING" | "PARTIAL" | "COMPLETED" | "RETURNED";
    note:              string | null;
    inspected_by:      string | null;
    inspected_at:      string | null;
    created_at:        string;
}