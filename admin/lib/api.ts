import axios from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const apiClient = axios.create({
    baseURL: BASE_URL,
    headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// 403 알럿 중복 방지 (5초 쿨다운)
let _403lastShown = 0;

apiClient.interceptors.response.use(
    (res) => res,
    (err) => {
        if (err.response?.status === 401) {
            localStorage.removeItem("access_token");
            window.location.href = "/login";
        }
        if (err.response?.status === 403) {
            const now = Date.now();
            if (now - _403lastShown > 5000) {
                _403lastShown = now;
                console.warn("[SCM] 권한이 없습니다.");
            }
        }
        return Promise.reject(err);
    }
);

// --- Auth ---
export const login = async (username: string, password: string) => {
    const res = await apiClient.post("/scm/auth/login",
        new URLSearchParams({ username, password }),
        { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    );
    if (res.data.access_token) {
        // role 저장
        const meRes = await apiClient.get("/scm/auth/me", {
            headers: { Authorization: `Bearer ${res.data.access_token}` },
        });
        localStorage.setItem("user_role", (meRes.data.role ?? "admin").toLowerCase());
        localStorage.setItem("username", meRes.data.username ?? username);
    }
    return res.data;
};


// --- Report ---
export const triggerReport = (filters?: { severity_filter?: string[] | null; category_filter?: string[] | null }) =>
    apiClient.post("/scm/report/run", filters ?? {});

export const getReportHistory = (limit = 5, offset = 0) =>
    apiClient.get(`/scm/report/history?limit=${limit}&offset=${offset}`);

export const getAnomalies = (
    isResolved?: boolean,
    pageSize = 50,
    page = 1,
    severity?: string,
    anomalyType?: string,
) => {
    const params = new URLSearchParams();
    if (isResolved !== undefined) params.append("is_resolved", String(isResolved));
    if (severity)    params.append("severity",     severity);
    if (anomalyType) params.append("anomaly_type", anomalyType);
    params.append("page",      String(page));
    params.append("page_size", String(pageSize));
    return apiClient.get(`/scm/report/anomalies?${params}`);
};

// --- Chat ---
export const chatQuery = (message: string, sessionId: string) =>
    apiClient.post("/scm/chat/query", {
        message,
        session_id: sessionId,
        user_id: "admin",
    });

export const getChatHistory = (sessionId: string, days = 7) =>
    apiClient.get(`/scm/chat/history?session_id=${encodeURIComponent(sessionId)}&days=${days}`);

// --- Order Proposals ---
export const getProposals = (status?: string, limit = 50, page = 1) => {
    const p = new URLSearchParams();
    if (status && status !== "all") p.append("status", status);
    p.append("limit",  String(limit));
    p.append("offset", String((page - 1) * limit));
    return apiClient.get(`/scm/orders/proposals?${p}`);
};

export const generateProposals = (severityOverride?: string) =>
    apiClient.post("/scm/orders/proposals/generate",
        severityOverride ? { severity_override: severityOverride } : {}
    );

export const generateProposalsForProduct = (productCode: string, severityOverride?: string) =>
    apiClient.post("/scm/orders/proposals/generate",
        { severity_override: severityOverride ?? "LOW", product_code: productCode }
    );

export const approveProposal = (id: number) =>
    apiClient.patch(`/scm/orders/proposals/${id}/approve`);

export const rejectProposal = (id: number) =>
    apiClient.patch(`/scm/orders/proposals/${id}/reject`);

export const resetProposal = (id: number) =>
    apiClient.patch(`/scm/orders/proposals/${id}/reset`);

export const updateProposal = (id: number, data: { proposed_qty?: number; unit_price?: number }) =>
    apiClient.put(`/scm/orders/proposals/${id}`, data);


// --- Health ---
export const healthCheck = () =>
    apiClient.get("/scm/health");

// --- Anomaly ---
export const resolveAnomaly = (id: number) =>
    apiClient.patch(`/scm/report/anomalies/${id}/resolve`);

export const autoResolveAnomaly = (id: number) =>
    apiClient.post(`/scm/report/anomalies/${id}/auto-resolve`);

// --- Scheduler ---
export const getSchedulerConfig = () =>
    apiClient.get("/scm/scheduler/config");

export const updateSchedulerConfig = (data: {
    schedule_hour: number;
    schedule_minute: number;
    timezone: string;
    is_active: boolean;
}) => apiClient.put("/scm/scheduler/config", data);

export const getSchedulerStatus = () =>
    apiClient.get("/scm/scheduler/status");

export const triggerCrawler = () =>
    apiClient.post("/scm/scheduler/trigger-crawler");

export const triggerCleanup = () =>
    apiClient.post("/scm/scheduler/trigger-cleanup");

export const triggerSync = () =>
    apiClient.post("/scm/scheduler/sync-trigger");

export const triggerDemandForecast = () =>
    apiClient.post("/scm/scheduler/trigger-demand-forecast");

export const triggerTurnoverAnalysis = () =>
    apiClient.post("/scm/scheduler/trigger-turnover-analysis");

export const triggerAbcAnalysis = () =>
    apiClient.post("/scm/scheduler/trigger-abc-analysis");

export const triggerProactiveOrder = () =>
    apiClient.post("/scm/scheduler/trigger-proactive-order");

export const triggerSafetyStockRecalc = () =>
    apiClient.post("/scm/scheduler/trigger-safety-stock-recalc");

export const syncDbToSheets = () =>
    apiClient.post("/scm/scheduler/sync-db-to-sheets");

// --- Sheets ---
export const getSheetCategories = () =>
    apiClient.get("/scm/sheets/categories");

export const getSheetsMaster = (
    page = 1, pageSize = 50,
    search?: string, category?: string,
    status?: string,
) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search)   params.append("search", search);
    if (category) params.append("category", category);
    if (status)   params.append("status", status);
    return apiClient.get(`/scm/sheets/master?${params}`);
};

export const getSheetsSales = (days = 30, page = 1, pageSize = 50, category?: string, search?: string) => {
    const params = new URLSearchParams({ days: String(days), page: String(page), page_size: String(pageSize) });
    if (category) params.append("category", category);
    if (search)   params.append("search", search);
    return apiClient.get(`/scm/sheets/sales?${params}`);
};

export const getSheetsStock = (page = 1, pageSize = 50, category?: string, search?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (category) params.append("category", category);
    if (search)   params.append("search", search);
    return apiClient.get(`/scm/sheets/stock?${params}`);
};


// 현재 필터 기준 CSV blob 다운로드
export const downloadSheetCsv = async (
    type: "master" | "sales" | "stock",
    filters: { search?: string; category?: string; days?: number },
    filename: string,
) => {
    const typeMap = { master: "master", sales: "sales", stock: "stock" };
    const params = new URLSearchParams({ download: "true" });
    if (filters.search)   params.append("search",   filters.search);
    if (filters.category) params.append("category", filters.category);
    if (filters.days)     params.append("days",     String(filters.days));

    const res = await apiClient.get(`/scm/sheets/${typeMap[type]}?${params}`, {
        responseType: "blob",
    });
    const blob = new Blob([res.data], { type: "text/csv;charset=utf-8-sig;" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
};


export const getSalesStats = (period: "daily" | "weekly" | "monthly", category?: string) => {
    const params = new URLSearchParams({ period });
    if (category) params.append("category", category);
    return apiClient.get(`/scm/sheets/stats/sales?${params}`);
};

export const getStockStats = (
    category?: string,
    search?: string,
    page = 1,
    pageSize = 50,
) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (category) params.append("category", category);
    if (search)   params.append("search",   search);
    return apiClient.get(`/scm/sheets/stats/stock?${params}`);
};

export const getAbcStats = (days = 90, category?: string) => {
    const params = new URLSearchParams({ days: String(days) });
    if (category) params.append("category", category);
    return apiClient.get(`/scm/sheets/stats/abc?${params}`);
};

// --- PDF ---
export const getPdfList = () =>
    apiClient.get("/scm/report/pdf-list");

export const getPdfUrl = (filename: string) =>
    `${process.env.NEXT_PUBLIC_API_URL}/scm/report/pdf/${filename}`;

export const downloadPdf = async (filename: string): Promise<Blob> => {
    const res = await apiClient.get(`/scm/report/pdf/${filename}`, {
        responseType: "blob",
    });
    return res.data;
};

export const deletePdf = (filename: string) =>
    apiClient.delete(`/scm/report/pdf/${filename}`);

// --- Alerts ---
export const getUnreadCount = () =>
    apiClient.get("/scm/alerts/unread-count");

// --- Report Status Polling ---
export const getReportStatus = (executionId: number) =>
    apiClient.get(`/scm/report/status/${executionId}`);

// --- Settings ---
export const getSettings = () =>
    apiClient.get("/scm/settings");

export const saveSettings = (values: Record<string, string>) =>
    apiClient.put("/scm/settings", values);

export const updateLeadTime = (code: string, leadTimeDays: number | null) =>
    apiClient.patch(`/scm/products/${code}/lead-time`, { lead_time_days: leadTimeDays });

// --- Orders ---
export const getOrders = (params?: {
    status?:    string;
    days?:      number;
    page?:      number;
    page_size?: number;
}) => {
    const p = new URLSearchParams();
    if (params?.status)    p.append("status",    params.status);
    if (params?.days)      p.append("days",      String(params.days));
    if (params?.page)      p.append("page",      String(params.page));
    if (params?.page_size) p.append("page_size", String(params.page_size));
    return apiClient.get(`/scm/sheets/orders?${p}`);
};

// --- Admin Users ---
export const getAdminUsers = () =>
    apiClient.get("/scm/admin/users");

export const createAdminUser = (data: {
    username:       string;
    password:       string;
    role:           string;
    slack_user_id?: string;
    email?:         string;
}) => apiClient.post("/scm/admin/users", data);

export const updateAdminUser = (id: number, data: {
    role?:          string;
    slack_user_id?: string;
    email?:         string;
    is_active?:     boolean;
}) => apiClient.put(`/scm/admin/users/${id}`, data);

export const deleteAdminUser = (id: number) =>
    apiClient.delete(`/scm/admin/users/${id}`);

export const changeMyPassword = (data: {
    current_password: string;
    new_password:     string;
}) => apiClient.put("/scm/admin/me/password", data);

export const getMyAdminProfile = () =>
    apiClient.get("/scm/admin/me");

export const updateMyProfile = (data: { email?: string; slack_user_id?: string }) =>
    apiClient.put("/scm/admin/me/profile", data);

export const getDemandForecast = (forecastDays = 14, page = 1, pageSize = 50, category?: string, search?: string) => {
    const params = new URLSearchParams({ forecast_days: String(forecastDays), page: String(page), page_size: String(pageSize) });
    if (category) params.append("category", category);
    if (search)   params.append("search",   search);
    return apiClient.get(`/scm/sheets/stats/demand?${params}`);
};

export const getTurnoverStats = (days = 30, page = 1, pageSize = 50, category?: string, search?: string) => {
    const params = new URLSearchParams({ days: String(days), page: String(page), page_size: String(pageSize) });
    if (category) params.append("category", category);
    if (search)   params.append("search",   search);
    return apiClient.get(`/scm/sheets/stats/turnover?${params}`);
};

// --- Task Polling ---
export const getTaskStatus = (taskId: string) =>
    apiClient.get(`/scm/tasks/${taskId}/status`);

// --- Product Status ---
export const updateProductStatus = (code: string, status: string) =>
    apiClient.patch(`/scm/products/${code}/status`, { status });

export const updateProduct = (code: string, data: {
    name?: string; category?: string; safety_stock?: number; status?: string;
}) => apiClient.put(`/scm/sheets/products/${code}`, data);

// --- Excel Upload ---
export const uploadExcel = (file: File, sheetType: "master" | "sales" | "stock") => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("sheet_type", sheetType);
    return apiClient.post("/scm/sheets/upload-excel", fd, {
        headers: { "Content-Type": "multipart/form-data" },
    });
};

// --- Suppliers ---
export const getSuppliers        = (activeOnly = false) =>
    apiClient.get(`/scm/suppliers?active_only=${activeOnly}`);

export const createSupplier      = (data: {
    name: string; contact?: string; email?: string; phone?: string; lead_time_days?: number;
}) => apiClient.post("/scm/suppliers", data);

export const updateSupplier      = (id: number, data: object) =>
    apiClient.patch(`/scm/suppliers/${id}`, data);

export const deleteSupplier      = (id: number) =>
    apiClient.delete(`/scm/suppliers/${id}`);

export const getSupplierStats    = (id: number) =>
    apiClient.get(`/scm/suppliers/${id}/stats`);

export const getDeliveryHistory  = (id: number) =>
    apiClient.get(`/scm/suppliers/${id}/delivery-history`);

export const mapProductSupplier  = (supplierId: number, productCode: string, unitPrice?: number) =>
    apiClient.post(`/scm/suppliers/${supplierId}/products`, {
        product_code: productCode, unit_price: unitPrice ?? null,
    });

export const getProductSupplier  = (productCode: string) =>
    apiClient.get(`/scm/suppliers/products/${productCode}/supplier`);

// --- Receiving Inspections ---
export const getInspections      = (status?: string, limit = 50, offset = 0) =>
    apiClient.get(`/scm/suppliers/inspections?${status ? `status=${status}&` : ""}limit=${limit}&offset=${offset}`);

export const createInspection    = (proposalId: number) =>
    apiClient.post(`/scm/suppliers/inspections/from-proposal/${proposalId}`);

export const completeInspection  = (id: number, data: {
    received_qty: number; defect_qty?: number; return_qty?: number; note?: string;
}) => apiClient.patch(`/scm/suppliers/inspections/${id}/complete`, data);

// --- Alert History ---
export const getAlertHistory = (limit = 50, unread = false) =>
    apiClient.get(`/scm/alerts/history?limit=${limit}&unread=${unread}`);

export const markAlertsRead = () =>
    apiClient.patch("/scm/alerts/history/read-all");

// --- AI Limit ---
export const getAiLimitStatus = () =>
    apiClient.get("/scm/chat/limit-status");

// --- 리드 타임 ---
export const getCategoryLeadTimes = () =>
    apiClient.get("/scm/settings/category-lead-times");

export const upsertCategoryLeadTime = (category: string, lead_time_days: number) =>
    apiClient.put("/scm/settings/category-lead-times", { category, lead_time_days });

export const deleteCategoryLeadTime = (category: string) =>
    apiClient.delete(`/scm/settings/category-lead-times/${encodeURIComponent(category)}`);

export const invalidateDashboardCache = () =>
    apiClient.post("/scm/sheets/invalidate-cache");