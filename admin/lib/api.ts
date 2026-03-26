
import axios from "axios";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const apiClient = axios.create({
    baseURL: BASE_URL,
    headers: { "Content-Type": "application/json" },
});

// req 인터셉터 - add JWT Token
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// res 인터셉터 - 401 시 로그인 페이지 이동
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

// --- Health ---
export const healthCheck = () =>
    apiClient.get("/scm/health");

// --- Anomaly ---------------------------------------------------------------─
export const resolveAnomaly = (id: number) =>
    apiClient.patch(`/scm/report/anomalies/${id}/resolve`);

// --- Scheduler ------------------------------------------------------------─
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
export const getSheetsMaster = () =>
    apiClient.get("/scm/sheets/master");

export const getSheetsSales = (days = 30) =>
    apiClient.get(`/scm/sheets/sales?days=${days}`);

export const getSheetsStock = () =>
    apiClient.get("/scm/sheets/stock");

export const getSalesStats = (period: "daily" | "weekly" | "monthly") =>
    apiClient.get(`/scm/sheets/stats/sales?period=${period}`);

export const getStockStats = () =>
    apiClient.get("/scm/sheets/stats/stock");

// --- PDF ------─
export const getPdfList = () =>
    apiClient.get("/scm/report/pdf-list");

export const getPdfUrl = (filename: string) =>
    `${process.env.NEXT_PUBLIC_API_URL}/scm/report/pdf/${filename}`;

// --- Alerts ---
export const getUnreadCount = () =>
    apiClient.get("/scm/alerts/unread-count");

// --- PDF (인증 포함) ---
export const downloadPdf = async (filename: string): Promise<Blob> => {
    const res = await apiClient.get(`/scm/report/pdf/${filename}`, {
        responseType: "blob",
    });
    return res.data;
};