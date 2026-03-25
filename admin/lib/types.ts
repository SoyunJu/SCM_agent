
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