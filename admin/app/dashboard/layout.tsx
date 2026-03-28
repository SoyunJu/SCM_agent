"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import {
    LayoutDashboard, AlertTriangle, FileText,
    MessageSquare, LogOut, Bell, Database,
    Calendar, BarChart2, ShoppingCart, Settings, Users, X,
    ChevronLeft, ChevronRight,
} from "lucide-react";
import { useAlerts } from "@/lib/useAlerts";

const NAV_ITEMS = [
    { href: "/dashboard",             icon: LayoutDashboard, label: "대시보드",    adminOnly: false },
    { href: "/dashboard/anomalies",   icon: AlertTriangle,   label: "이상 징후",   adminOnly: false },
    { href: "/dashboard/reports",     icon: FileText,        label: "보고서",      adminOnly: false },
    { href: "/dashboard/stats",       icon: BarChart2,       label: "통계",        adminOnly: false },
    { href: "/dashboard/sheets",      icon: Database,        label: "데이터 시트", adminOnly: false },
    { href: "/dashboard/orders",      icon: ShoppingCart,    label: "발주 관리",   adminOnly: false },
    { href: "/dashboard/scheduler",   icon: Calendar,        label: "스케줄 관리", adminOnly: false },
    { href: "/dashboard/chat",        icon: MessageSquare,   label: "AI 챗봇",     adminOnly: false },
    { href: "/dashboard/settings",    icon: Settings,        label: "설정",        adminOnly: false },
    { href: "/dashboard/admin-users", icon: Users,           label: "관리자 관리", adminOnly: true  },
];

const ROLE_BADGE: Record<string, { label: string; cls: string }> = {
    superadmin: { label: "슈퍼관리자", cls: "bg-purple-100 text-purple-700" },
    admin:      { label: "관리자",     cls: "bg-blue-100 text-blue-700"     },
    readonly:   { label: "읽기전용",   cls: "bg-gray-100 text-gray-500"     },
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const router   = useRouter();
    const pathname = usePathname();
    const { alerts, unreadCount, clearUnread } = useAlerts();

    const [showAlerts, setShowAlerts] = useState(false);
    const [userRole, setUserRole]     = useState<string>("");
    const [username, setUsername]     = useState<string>("");
    const [collapsed, setCollapsed]   = useState(false);

    // 사이드바 접힘 상태 localStorage 복원
    useEffect(() => {
        setCollapsed(localStorage.getItem("sidebar_collapsed") === "true");
    }, []);

    useEffect(() => {
        const token = localStorage.getItem("access_token");
        if (!token) { router.push("/login"); return; }

        // 역할 정보 로드 (로그인 시 저장된 값 우선, 없으면 API 조회)
        const cachedRole = localStorage.getItem("user_role") ?? "";
        const cachedName = localStorage.getItem("username") ?? "";
        if (cachedRole) {
            setUserRole(cachedRole);
            setUsername(cachedName);
        } else {
            fetch(`${process.env.NEXT_PUBLIC_API_URL ?? ""}/scm/auth/me`, {
                headers: { Authorization: `Bearer ${token}` },
            })
                .then((r) => r.json())
                .then((data) => {
                    setUserRole(data.role ?? "admin");
                    setUsername(data.username ?? "");
                    localStorage.setItem("user_role", data.role ?? "admin");
                    localStorage.setItem("username", data.username ?? "");
                })
                .catch(() => { router.push("/login"); });
        }
    }, [router]);

    const visibleNavItems = NAV_ITEMS.filter(
        (item) => !item.adminOnly || userRole === "admin" || userRole === "superadmin"
    );

    const toggleSidebar = () => {
        setCollapsed((v) => {
            localStorage.setItem("sidebar_collapsed", String(!v));
            return !v;
        });
    };

    const handleLogout = () => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("user_role");
        localStorage.removeItem("username");
        router.push("/login");
    };

    const toggleAlerts = () => {
        setShowAlerts((v) => !v);
        if (!showAlerts) clearUnread();
    };

    const badge = ROLE_BADGE[userRole];

    return (
        <div className="flex min-h-screen bg-gray-50">
            {/* 사이드바 */}
            <aside className={`${collapsed ? "w-14" : "w-56"} bg-white border-r border-gray-200 flex flex-col transition-all duration-200 shrink-0`}>
                {/* 헤더 + 토글 버튼 */}
                <div className={`flex items-center border-b border-gray-100 ${collapsed ? "justify-center p-3" : "justify-between p-4 pl-5"}`}>
                    {!collapsed && (
                        <div>
                            <h1 className="text-base font-bold text-gray-800">SCM Agent</h1>
                            <p className="text-xs text-gray-400">재고·판매 분석</p>
                        </div>
                    )}
                    <button
                        onClick={toggleSidebar}
                        className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition"
                        title={collapsed ? "사이드바 펼치기" : "사이드바 접기"}
                    >
                        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                    </button>
                </div>

                <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto overflow-x-hidden">
                    {visibleNavItems.map(({ href, icon: Icon, label }) => {
                        const active = pathname === href;
                        return (
                            <Link key={href} href={href}
                                  title={collapsed ? label : undefined}
                                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                                      active
                                          ? "bg-blue-50 text-blue-600 font-medium"
                                          : "text-gray-600 hover:bg-gray-100"
                                  } ${collapsed ? "justify-center" : ""}`}
                            >
                                <Icon size={16} className="shrink-0" />
                                {!collapsed && <span className="truncate">{label}</span>}
                            </Link>
                        );
                    })}
                </nav>

                {/* 사용자 정보 + 로그아웃 */}
                <div className="p-2 border-t border-gray-100 space-y-0.5">
                    {badge && !collapsed && (
                        <div className="px-3 py-1.5">
                            <p className="text-xs text-gray-500 font-medium truncate">{username}</p>
                            <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium mt-0.5 ${badge.cls}`}>
                                {badge.label}
                            </span>
                        </div>
                    )}
                    <button onClick={handleLogout}
                            title={collapsed ? "로그아웃" : undefined}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-500 hover:bg-gray-100 w-full transition ${collapsed ? "justify-center" : ""}`}
                    >
                        <LogOut size={16} className="shrink-0" />
                        {!collapsed && "로그아웃"}
                    </button>
                </div>
            </aside>

            {/* 메인 */}
            <div className="flex-1 flex flex-col">
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
