// app/layout.tsx
"use client";

import {useEffect, useState} from "react";
import {usePathname, useRouter} from "next/navigation";
import Link from "next/link";
import {
    AlertTriangle,
    BarChart2,
    Bell,
    Calendar,
    ChevronLeft,
    ChevronRight,
    Database,
    FileText,
    LayoutDashboard,
    LogOut,
    MessageSquare,
    Pencil,
    Settings,
    ShoppingCart,
    Truck,
    Users,
    X,
} from "lucide-react";
import {useAlerts} from "@/lib/useAlerts";
import {changeMyPassword, getMyAdminProfile, markAlertsRead, updateMyProfile} from "@/lib/api";

const NAV_ITEMS = [
    { href: "/dashboard",             icon: LayoutDashboard, label: "대시보드",    adminOnly: false },
    { href: "/dashboard/anomalies",   icon: AlertTriangle,   label: "이상 징후",   adminOnly: false },
    { href: "/dashboard/reports",     icon: FileText,        label: "보고서",      adminOnly: false },
    { href: "/dashboard/stats",       icon: BarChart2,       label: "통계",        adminOnly: false },
    { href: "/dashboard/sheets",      icon: Database,        label: "데이터 시트", adminOnly: false },
    { href: "/dashboard/orders",      icon: ShoppingCart,    label: "발주 관리",   adminOnly: false },
    { href: "/dashboard/suppliers",   icon: Truck,           label: "공급업체",     adminOnly: false },
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

/** JWT payload에서 role/username 추출 (API 호출 없이 즉시) */
function decodeJwtPayload(token: string): { role: string; username: string } | null {
    try {
        const parts = token.split(".");
        if (parts.length !== 3) return null;
        const payload = JSON.parse(atob(parts[1]));
        return { role: payload.role ?? "", username: payload.sub ?? "" };
    } catch {
        return null;
    }
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const router   = useRouter();
    const pathname = usePathname();
    const { alerts, unreadCount, clearUnread } = useAlerts();

    const [showAlerts, setShowAlerts]   = useState(false);
    const [userRole, setUserRole]       = useState<string>("");
    const [username, setUsername]       = useState<string>("");
    const [collapsed, setCollapsed]     = useState(false);
    const [showProfile, setShowProfile] = useState(false);

    // 프로필 편집 상태
    const [profileEmail,    setProfileEmail]    = useState("");
    const [profileSlack,    setProfileSlack]    = useState("");
    const [currentPw,       setCurrentPw]       = useState("");
    const [newPw,           setNewPw]           = useState("");
    const [profileMsg,      setProfileMsg]      = useState("");
    const [profileSaving,   setProfileSaving]   = useState(false);

    // 사이드바 접힘 상태 localStorage 복원
    useEffect(() => {
        setCollapsed(localStorage.getItem("sidebar_collapsed") === "true");
    }, []);

    useEffect(() => {
        const token = localStorage.getItem("access_token");
        if (!token) { router.push("/login"); return; }

        // JWT payload에서 role/username 직접 추출 (API 호출 불필요)
        const decoded = decodeJwtPayload(token);
        if (decoded && decoded.role) {
            const role = decoded.role.toLowerCase();
            setUserRole(role);
            setUsername(decoded.username);
            localStorage.setItem("user_role", role);
            localStorage.setItem("username", decoded.username);
        } else {
            // JWT 디코딩 실패 시 localStorage fallback
            const cachedRole = localStorage.getItem("user_role") ?? "";
            const cachedName = localStorage.getItem("username") ?? "";
            if (cachedRole) {
                setUserRole(cachedRole);
                setUsername(cachedName);
            } else {
                router.push("/login");
            }
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
        window.location.href = "/login";
    };

    const toggleAlerts = async () => {
        setShowAlerts((v) => !v);
        if (!showAlerts) {
            clearUnread();
            try {
                await markAlertsRead();
            } catch {
            }
        }
    };

    const openProfile = async () => {
        setProfileMsg("");
        setCurrentPw(""); setNewPw("");
        try {
            const res = await getMyAdminProfile();
            setProfileEmail(res.data.email ?? "");
            setProfileSlack(res.data.slack_user_id ?? "");
        } catch {
            setProfileEmail(""); setProfileSlack("");
        }
        setShowProfile(true);
    };

    const handleSaveProfile = async () => {
        setProfileSaving(true);
        setProfileMsg("");
        try {
            await updateMyProfile({ email: profileEmail || undefined, slack_user_id: profileSlack || undefined });
            if (currentPw && newPw) {
                await changeMyPassword({ current_password: currentPw, new_password: newPw });
            }
            setProfileMsg("✅ 저장되었습니다.");
            setCurrentPw(""); setNewPw("");
        } catch (e: any) {
            setProfileMsg(`❌ ${e?.response?.data?.detail ?? "저장 실패"}`);
        } finally {
            setProfileSaving(false);
        }
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
                    {collapsed ? (
                        <button
                            onClick={openProfile}
                            title={`${username} (${badge?.label ?? userRole}) — 프로필 편집`}
                            className="flex justify-center w-full py-1.5 hover:bg-gray-100 rounded-lg transition"
                        >
                            <Pencil size={14} className="text-gray-400" />
                        </button>
                    ) : (
                        <button
                            onClick={openProfile}
                            className="w-full px-3 py-1.5 rounded-lg hover:bg-gray-100 transition text-left group"
                        >
                            <div className="flex items-center justify-between">
                                <p className="text-xs text-gray-700 font-medium truncate">{username || "-"}</p>
                                <Pencil size={12} className="text-gray-300 group-hover:text-gray-500 shrink-0 ml-1" />
                            </div>
                            {badge && (
                                <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium mt-0.5 ${badge.cls}`}>
                                    {badge.label}
                                </span>
                            )}
                        </button>
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
            <div className="flex-1 flex flex-col min-w-0">
                <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-end px-4 md:px-8 gap-4 shrink-0">
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
                                    <div className="flex items-center gap-2">
                                        {alerts.length > 0 && (
                                            <button
                                                onClick={async () => {
                                                    clearUnread();
                                                    try { await markAlertsRead(); } catch {}
                                                    setShowAlerts(false);
                                                }}
                                                className="text-xs text-blue-500 hover:underline"
                                            >
                                                모두 읽음
                                            </button>
                                        )}
                                        <button onClick={() => setShowAlerts(false)}>
                                            <X size={14} className="text-gray-400" />
                                        </button>
                                    </div>
                                </div>
                                <div className="max-h-80 overflow-y-auto divide-y divide-gray-50">
                                    {alerts.length === 0 ? (
                                        <p className="text-center text-gray-400 text-sm py-6">알림 없음</p>
                                    ) : (
                                        alerts.map((a: any, i: number) => {
                                            const sev = (a.severity ?? "").toUpperCase();
                                            const bgColor = sev === "CRITICAL" ? "bg-red-50"
                                                : sev === "HIGH" ? "bg-orange-50"
                                                    : "bg-gray-50";
                                            const isBatch = a.type === "critical_anomaly_batch";
                                            return (
                                                <div key={i} className={`px-4 py-3 text-sm ${bgColor}`}>
                                                    <p className="font-medium text-gray-700">{a.message}</p>
                                                    {isBatch ? (
                                                        <p className="text-xs text-gray-400 mt-0.5">
                                                            {a.items?.slice(0, 2).map((it: any) =>
                                                                `${it.product_name}(${it.anomaly_type})`
                                                            ).join(", ")}
                                                            {(a.count ?? 0) > 2 && ` 외 ${a.count - 2}건`}
                                                        </p>
                                                    ) : (
                                                        <p className="text-xs text-gray-400 mt-0.5">
                                                            {a.product_code} | {a.anomaly_type}
                                                        </p>
                                                    )}
                                                </div>
                                            );
                                        })
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </header>

                <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-auto min-w-0">{children}</main>
            </div>

            {/* 프로필 편집 모달 */}
            {showProfile && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-5">
                        <div className="flex items-center justify-between">
                            <h2 className="text-lg font-bold text-gray-800">내 프로필 편집</h2>
                            <button onClick={() => setShowProfile(false)}>
                                <X size={18} className="text-gray-400" />
                            </button>
                        </div>

                        <div className="space-y-3">
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">계정 ID</label>
                                <p className="text-sm text-gray-700 font-medium">{username}</p>
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">이메일</label>
                                <input
                                    type="email"
                                    value={profileEmail}
                                    onChange={(e) => setProfileEmail(e.target.value)}
                                    placeholder="example@email.com"
                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">Slack User ID</label>
                                <input
                                    type="text"
                                    value={profileSlack}
                                    onChange={(e) => setProfileSlack(e.target.value)}
                                    placeholder="U0XXXXXXX"
                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                        </div>

                        <hr className="border-gray-100" />

                        <div className="space-y-3">
                            <p className="text-xs font-medium text-gray-500">비밀번호 변경 (선택)</p>
                            <input
                                type="password"
                                value={currentPw}
                                onChange={(e) => setCurrentPw(e.target.value)}
                                placeholder="현재 비밀번호"
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <input
                                type="password"
                                value={newPw}
                                onChange={(e) => setNewPw(e.target.value)}
                                placeholder="새 비밀번호"
                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>

                        {profileMsg && (
                            <p className="text-sm">{profileMsg}</p>
                        )}

                        <div className="flex gap-2 justify-end">
                            <button
                                onClick={() => setShowProfile(false)}
                                className="px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg transition"
                            >
                                취소
                            </button>
                            <button
                                onClick={handleSaveProfile}
                                disabled={profileSaving}
                                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition disabled:opacity-50"
                            >
                                {profileSaving ? "저장 중..." : "저장"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
