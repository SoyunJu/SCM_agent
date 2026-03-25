
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