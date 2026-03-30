// admin/lib/useAlerts.ts
"use client";

import {useCallback, useEffect, useRef, useState} from "react";
import {AlertMessage} from "./types";

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
                const data: any = JSON.parse(e.data);

                if (data.type === "connected") return;

                // 배치 알림 처리 — 묶음을 하나의 알림으로 표시
                if (data.type === "critical_anomaly_batch") {
                    const batchAlert: AlertMessage = {
                        type: "critical_anomaly_batch",
                        severity: data.severity ?? "HIGH",
                        product_code: "",
                        product_name: `긴급 이상징후 ${data.count}건`,
                        anomaly_type: "",
                        message: data.items
                            ?.slice(0, 3)
                            .map((i: any) => `${i.product_name}(${i.anomaly_type})`)
                            .join(", ") + (data.count > 3 ? ` 외 ${data.count - 3}건` : ""),
                    };
                    setAlerts((prev) => [batchAlert, ...prev].slice(0, 20));
                    setUnread((n) => n + 1);
                    if (Notification.permission === "granted") {
                        new Notification(`🔴 SCM Agent 긴급 알림 ${data.count}건`, {
                            body: batchAlert.message,
                            icon: "/favicon.ico",
                        });
                    }
                    return;
                }

                // 단건 알림 (기존)
                const alert: AlertMessage = data;
                setAlerts((prev) => [alert, ...prev].slice(0, 20));
                const sev = (alert.severity ?? "").toUpperCase();
                if (sev === "CRITICAL" || sev === "HIGH") {
                    setUnread((n) => n + 1);
                    if (Notification.permission === "granted") {
                        new Notification(`🔴 SCM Agent 긴급 알림`, {
                            body: alert.message,
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