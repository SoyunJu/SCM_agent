
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

apiClient.interceptors.response.use(
    (res) => res,
    (err) => {
        if (err.response?.status === 401) {
            localStorage.removeItem("access_token");
            window.location.href = "/login";
        }
        return Promise.reject(err);
    }
);

// --- Auth ---
export const login = async (username: string, password: string) => {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    const res = await apiClient.post("/scm/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    return res.data;
};

// --- Report ---
export const triggerReport = () =>
    apiClient.post("/scm/report/run");

export const getReportHistory = (limit = 20) =>
    apiClient.get(`/scm/report/history?limit=${limit}`);

export const getAnomalies = (isResolved?: boolean, limit = 50) => {
    const params = new URLSearchParams();
    if (isResolved !== undefined) params.append("is_resolved", String(isResolved));
    params.append("limit", String(limit));
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

// --- Health ---
export const healthCheck = () =>
    apiClient.get("/scm/health");

// --- Anomaly ---
export const resolveAnomaly = (id: number) =>
    apiClient.patch(`/scm/report/anomalies/${id}/resolve`);

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

// --- Sheets ---
export const getSheetsMaster = (page = 1, pageSize = 50, search?: string) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (search) params.append("search", search);
    return apiClient.get(`/scm/sheets/master?${params}`);
};

export const getSheetsSales = (days = 30) =>
    apiClient.get(`/scm/sheets/sales?days=${days}`);

export const getSheetsStock = () =>
    apiClient.get("/scm/sheets/stock");

export const getSalesStats = (period: "daily" | "weekly" | "monthly") =>
    apiClient.get(`/scm/sheets/stats/sales?period=${period}`);

export const getStockStats = () =>
    apiClient.get("/scm/sheets/stats/stock");

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

// --- Orders ---
export const getOrders = (params?: { status?: string; days?: number; page?: number; page_size?: number }) => {
    const p = new URLSearchParams();
    if (params?.status) p.append("status", params.status);
    if (params?.days) p.append("days", String(params.days));
    if (params?.page) p.append("page", String(params.page));
    if (params?.page_size) p.append("page_size", String(params.page_size));
    return apiClient.get(`/scm/sheets/orders?${p}`);
};

