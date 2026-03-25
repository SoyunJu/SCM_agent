"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import {
    LayoutDashboard, AlertTriangle, FileText,
    MessageSquare, LogOut
} from "lucide-react";

const NAV_ITEMS = [
    { href: "/dashboard",           icon: LayoutDashboard, label: "대시보드"    },
    { href: "/dashboard/anomalies", icon: AlertTriangle,   label: "이상 징후"   },
    { href: "/dashboard/reports",   icon: FileText,        label: "보고서 이력" },
    { href: "/dashboard/chat",      icon: MessageSquare,   label: "SCM 챗봇"     },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const router   = useRouter();
    const pathname = usePathname();

    useEffect(() => {
        if (!localStorage.getItem("access_token")) {
            router.push("/login");
        }
    }, [router]);

    const handleLogout = () => {
        localStorage.removeItem("access_token");
        router.push("/login");
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
                            <Link
                                key={href}
                                href={href}
                                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
                                    active
                                        ? "bg-blue-50 text-blue-600 font-medium"
                                        : "text-gray-600 hover:bg-gray-100"
                                }`}
                            >
                                <Icon size={16} />
                                {label}
                            </Link>
                        );
                    })}
                </nav>

                <div className="p-4 border-t border-gray-100">
                    <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-500 hover:bg-gray-100 w-full transition"
                    >
                        <LogOut size={16} />
                        로그아웃
                    </button>
                </div>
            </aside>

            {/* 메인 컨텐츠 */}
            <main className="flex-1 p-8 overflow-auto">{children}</main>
        </div>
    );
}