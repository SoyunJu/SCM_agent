"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { AlertMessage } from "./types";

export function useAlerts() {
    const [alerts, setAlerts]       = useState<AlertMessage[]>([]);
    const [unreadCount, setUnread]  = useState(0);
    const esRef                     = useRef<EventSource | null>(null);

    const connect = useCallback(() => {
        const token = localStorage.getItem("access_token");
        if (!token) return;

        const url = `${process.env.NEXT_PUBLIC_API_URL}/scm/alerts/stream`;
        const es  = new EventSource(`${url}?token=${token}`);
        esRef.current = es;

        es.onmessage = (e) => {
            try {
                const data: AlertMessage = JSON.parse(e.data);
                if (data.type === "connected") return;

                setAlerts((prev) => [data, ...prev].slice(0, 20));
                if (["CRITICAL", "HIGH"].includes(data.severity?.toUpperCase() ?? "")) {
                    setUnread((n) => n + 1);

                    // 브라우저 푸시 알림
                    if (Notification.permission === "granted") {
                        new Notification(`🔴 SCM Agent 긴급 알림`, {
                            body: data.message,
                            icon: "/favicon.ico",
                        });
                    }
                }
            } catch {}
        };

        es.onerror = () => {
            es.close();
            // 5초 후 재연결
            setTimeout(connect, 5000);
        };
    }, []);

    useEffect(() => {
        // 브라우저 푸시 알림 권한 요청
        if (typeof Notification !== "undefined" && Notification.permission === "default") {
            Notification.requestPermission();
        }
        connect();
        return () => esRef.current?.close();
    }, [connect]);

    const clearUnread = () => setUnread(0);

    return { alerts, unreadCount, clearUnread };
}