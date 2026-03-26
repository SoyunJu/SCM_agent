
export interface ReportExecution {
    id: number;
    executed_at: string;
    report_type: "daily" | "weekly" | "manual";
    status: "success" | "failure" | "in_progress";
    slack_sent: boolean;
    error_message: string | null;
    created_at: string;
}

export interface AnomalyLog {
    id: number;
    detected_at: string;
    product_code: string;
    product_name: string;
    category?: string;
    anomaly_type: "low_stock" | "over_stock" | "sales_surge" | "sales_drop" | "long_term_stock";
    current_stock: number | null;
    daily_avg_sales: number | null;
    days_until_stockout: number | null;
    severity: "low" | "medium" | "high" | "critical";
    is_resolved: boolean;
}

export interface ChatMessage {
    role: "user" | "assistant";
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
