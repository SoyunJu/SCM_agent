"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import {
    LayoutDashboard, AlertTriangle, FileText,
    MessageSquare, LogOut, Bell, Database,
    Calendar, BarChart2, X,
} from "lucide-react";
import { useAlerts } from "@/lib/useAlerts";
import { AlertMessage } from "@/lib/types";

const NAV_ITEMS = [
    { href: "/dashboard",             icon: LayoutDashboard, label: "대시보드"    },
    { href: "/dashboard/anomalies",   icon: AlertTriangle,   label: "이상 징후"   },
    { href: "/dashboard/reports",     icon: FileText,        label: "보고서"      },
    { href: "/dashboard/stats",       icon: BarChart2,       label: "통계"        },
    { href: "/dashboard/sheets",      icon: Database,        label: "데이터 시트" },
    { href: "/dashboard/scheduler",   icon: Calendar,        label: "스케줄 관리" },
    { href: "/dashboard/chat",        icon: MessageSquare,   label: "AI 챗봇"     },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const router              = useRouter();
    const pathname            = usePathname();
    const { alerts, unreadCount, clearUnread } = useAlerts();
    const [showAlerts, setShowAlerts] = useState(false);

    useEffect(() => {
        if (!localStorage.getItem("access_token")) router.push("/login");
    }, [router]);

    const handleLogout = () => {
        localStorage.removeItem("access_token");
        router.push("/login");
    };

    const toggleAlerts = () => {
        setShowAlerts((v) => !v);
        if (!showAlerts) clearUnread();
    };

    return (
        <div className="flex min-h-screen bg-gray-50">
            {/* 사이드바 */}
            <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
                <div className="p-6 border-b border-gray-100">
                    <h1 className="text-lg font-bold text-gray-800">SCM Agent</h1>
                    <p className="text-xs text-gray-400 mt-0.5">재고·판매 분석</p>
                </div>

                <nav className="flex-1 p-4 space-y-1">
                    {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
                        const active = pathname === href;
                        return (
                            <Link key={href} href={href}
                                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                                      active ? "bg-blue-50 text-blue-600 font-medium" : "text-gray-600 hover:bg-gray-100"
                                  }`}
                            >
                                <Icon size={16} />
                                {label}
                            </Link>
                        );
                    })}
                </nav>

                <div className="p-4 border-t border-gray-100">
                    <button onClick={handleLogout}
                            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-500 hover:bg-gray-100 w-full transition"
                    >
                        <LogOut size={16} />
                        로그아웃
                    </button>
                </div>
            </aside>

            {/* 메인 */}
            <div className="flex-1 flex flex-col">
                {/* 상단 바 */}
                <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-end px-8 gap-4">
                    <div className="relative">
                        <button onClick={toggleAlerts}
                                className="relative p-2 rounded-lg hover:bg-gray-100 transition"
                        >
                            <Bell size={18} className="text-gray-500" />
                            {unreadCount > 0 && (
                                <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-bold">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
                            )}
                        </button>

                        {/* 알림 드롭다운 */}
                        {showAlerts && (
                            <div className="absolute right-0 top-12 w-80 bg-white border border-gray-200 rounded-xl shadow-lg z-50">
                                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                                    <span className="text-sm font-semibold text-gray-700">실시간 알림</span>
                                    <button onClick={() => setShowAlerts(false)}>
                                        <X size={14} className="text-gray-400" />
                                    </button>
                                </div>
                                <div className="max-h-72 overflow-y-auto">
                                    {alerts.length === 0 ? (
                                        <p className="text-center text-gray-400 text-sm py-6">알림 없음</p>
                                    ) : (
                                        alerts.map((a, i) => (
                                            <div key={i} className={`px-4 py-3 border-b border-gray-50 text-sm ${
                                                a.severity === "critical" ? "bg-red-50" : "bg-orange-50"
                                            }`}>
                                                <p className="font-medium text-gray-700">{a.message}</p>
                                                <p className="text-xs text-gray-400 mt-0.5">
                                                    {a.product_code} | {a.anomaly_type}
                                                </p>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </header>

                <main className="flex-1 p-8 overflow-auto">{children}</main>
            </div>
        </div>
    );
}