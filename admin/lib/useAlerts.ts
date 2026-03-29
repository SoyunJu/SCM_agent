// admin/lib/useAlerts.ts
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { AlertMessage } from "./types";

export function useAlerts() {
    const [alerts, setAlerts]      = useState<AlertMessage[]>([]);
    const [unreadCount, setUnread] = useState(0);
    const esRef                    = useRef<EventSource | null>(null);

    const connect = useCallback(() => {
        const token = localStorage.getItem("access_token");
        if (!token) return;

        const url = `${process.env.NEXT_PUBLIC_API_URL}/scm/alerts/stream`;
        const es  = new EventSource(`${url}?token=${token}`);
        esRef.current = es;

        es.onopen = () => {
            console.log("[SSE] 연결 성공");
        };

        es.onmessage = (e) => {
            try {
                const data: AlertMessage = JSON.parse(e.data);

                // 연결 확인 메시지는 무시 (알림창에 노출 X)
                if (data.type === "connected") return;

                // 알림 목록에 추가 (최대 20개)
                setAlerts((prev) => [data, ...prev].slice(0, 20));

                // severity UPPERCASE 정규화 후 비교 (백엔드는 UPPERCASE로 전송)
                const sev = (data.severity ?? "").toUpperCase();
                if (sev === "CRITICAL" || sev === "HIGH") {
                    setUnread((n) => n + 1);

                    // 브라우저 푸시 알림
                    if (Notification.permission === "granted") {
                        new Notification(`🔴 SCM Agent 긴급 알림`, {
                            body: data.message,
                            icon: "/favicon.ico",
                        });
                    }
                }
            } catch (err) {
                console.error("[SSE] 파싱 오류:", err);
            }
        };

        es.onerror = () => {
            console.error("[SSE] 연결 오류 — 5초 후 재연결");
            es.close();
            setTimeout(connect, 5000);
        };
    }, []);

    useEffect(() => {
        if (typeof Notification !== "undefined" && Notification.permission === "default") {
            Notification.requestPermission();
        }
        connect();
        return () => esRef.current?.close();
    }, [connect]);

    const clearUnread = () => setUnread(0);

    return { alerts, unreadCount, clearUnread };
}