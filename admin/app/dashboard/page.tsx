"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
    getAnomalies, getReportHistory, triggerReport,
    getSalesStats, getStockStats, getReportStatus,
} from "@/lib/api";
import { AnomalyLog, ReportExecution, SalesStatItem } from "@/lib/types";
import { AlertTriangle, Package, TrendingUp, FileText, Play, RefreshCw, Loader2 } from "lucide-react";
import {
    LineChart, Line, BarChart, Bar, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, Legend,
} from "recharts";

const SEVERITY_COLOR: Record<string, string> = {
    CRITICAL: "text-red-600 bg-red-50",
    HIGH:     "text-orange-500 bg-orange-50",
    MEDIUM:   "text-yellow-500 bg-yellow-50",
    CHECK:    "text-blue-500 bg-blue-50",
    LOW:      "text-green-600 bg-green-50",
};
const SEVERITY_KOR: Record<string, string> = {
    CRITICAL: "긴급", HIGH: "높음", MEDIUM: "보통", CHECK: "확인", LOW: "낮음",
};
const ANOMALY_KOR: Record<string, string> = {
    low_stock: "재고 부족", over_stock: "재고 과잉",
    sales_surge: "판매 급등", sales_drop: "판매 급락",
    long_term_stock: "장기 재고",
};
const BAR_COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e"];
const MAX_POLL = 150;

export default function DashboardPage() {
    const router = useRouter();
    const [anomalies, setAnomalies]   = useState<AnomalyLog[]>([]);
    const [history, setHistory]       = useState<ReportExecution[]>([]);
    const [salesStats, setSalesStats] = useState<SalesStatItem[]>([]);
    const [stockStats, setStockStats] = useState<any>(null);
    const [period, setPeriod]         = useState<"daily" | "weekly" | "monthly">("daily");
    const [triggering, setTriggering] = useState(false);
    const [polling, setPolling]       = useState(false);
    const [message, setMessage]       = useState("");
    const [loading, setLoading]       = useState(true);
    const [isReadonly, setIsReadonly] = useState(false);
    const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollCountRef = useRef(0);

    const fetchAll = async () => {
        setLoading(true);
        try {
            const [anomRes, histRes, statsRes, stockRes] = await Promise.all([
                getAnomalies(false, 200),
                getReportHistory(5),
                getSalesStats(period),
                getStockStats(),
            ]);
            setAnomalies(anomRes.data.items ?? []);
            setHistory(histRes.data.items ?? []);
            setSalesStats(statsRes.data.items ?? []);
            setStockStats(stockRes.data);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        setIsReadonly(localStorage.getItem("user_role") === "readonly");
        fetchAll();
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, []);

    useEffect(() => {
        getSalesStats(period).then((res) => setSalesStats(res.data.items ?? []));
    }, [period]);

    const startPolling = (executionId: number) => {
        pollCountRef.current = 0;
        setPolling(true);
        pollRef.current = setInterval(async () => {
            pollCountRef.current += 1;
            try {
                const res = await getReportStatus(executionId);
                const { status, error_message } = res.data;
                const s = (status as string).toLowerCase();
                if (s !== "in_progress") {
                    clearInterval(pollRef.current!);
                    setPolling(false);
                    if (s === "success") {
                        setMessage("✅ 보고서 생성이 완료되었습니다.");
                        fetchAll();
                    } else {
                        setMessage(`❌ 보고서 생성 실패: ${error_message ?? "알 수 없는 오류"}`);
                    }
                } else if (pollCountRef.current >= MAX_POLL) {
                    clearInterval(pollRef.current!);
                    setPolling(false);
                    setMessage("⏱ 시간 초과. 새로 고침해주세요.");
                }
            } catch {
                clearInterval(pollRef.current!);
                setPolling(false);
                setMessage("❌ 상태 확인 중 오류가 발생했습니다.");
            }
        }, 2000);
    };

    const handleTrigger = async () => {
        setTriggering(true);
        setMessage("");
        try {
            const res = await triggerReport();
            const { execution_id } = res.data;
            setMessage("⏳ 보고서 생성 중...");
            startPolling(execution_id);
        } catch {
            setMessage("❌ 보고서 생성에 실패했습니다.");
        } finally {
            setTriggering(false);
        }
    };

    const lastRun = history[0];
    const severityCounts = anomalies.reduce<Record<string, number>>((acc, a) => {
        const sev = (typeof a.severity === "string" ? a.severity : (a.severity as any)?.value ?? "").toUpperCase();
        acc[sev] = (acc[sev] ?? 0) + 1;
        return acc;
    }, {});

    const severityCards = [
        { label: "미해결 이상 징후", value: anomalies.length,           icon: AlertTriangle, color: "text-orange-500" },
        { label: "긴급",            value: severityCounts.CRITICAL ?? 0, icon: Package,       color: "text-red-500"    },
        { label: "높음",            value: severityCounts.HIGH ?? 0,     icon: TrendingUp,    color: "text-orange-400" },
        { label: "최근 보고서",
            value: lastRun?.status === "success" ? "성공" : lastRun?.status ?? "-",
            icon: FileText, color: "text-blue-500" },
    ];
    const severityBarData = [
        { name: "긴급", count: severityCounts.CRITICAL ?? 0 },
        { name: "높음", count: severityCounts.HIGH ?? 0 },
        { name: "보통", count: severityCounts.MEDIUM ?? 0 },
        { name: "낮음", count: severityCounts.LOW ?? 0 },
    ];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">대시보드</h2>
                    <p className="text-gray-400 text-sm mt-1">재고·판매 현황 요약</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={fetchAll} disabled={loading} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition disabled:opacity-50">
                        <RefreshCw size={15} className={`text-gray-500 ${loading ? "animate-spin" : ""}`} />
                    </button>
                    {!isReadonly && (
                    <button
                        onClick={handleTrigger}
                        disabled={triggering || polling}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                    >
                        {polling ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                        {polling ? "생성 중..." : triggering ? "요청 중..." : "보고서 즉시 생성"}
                    </button>
                    )}
                </div>
            </div>

            {message && (
                <p className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">{message}</p>
            )}

            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 size={32} className="animate-spin text-blue-500" />
                </div>
            ) : (
                <>
                    {/* 통계 카드 */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        {severityCards.map(({ label, value, icon: Icon, color }) => (
                            <div key={label} className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
                                <div className="flex items-center justify-between mb-3">
                                    <span className="text-xs text-gray-400">{label}</span>
                                    <Icon size={16} className={color} />
                                </div>
                                <p className="text-2xl font-bold text-gray-800">{value}</p>
                            </div>
                        ))}
                    </div>

                    {/* 판매 추이 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="font-semibold text-gray-700">판매 추이</h3>
                            <div className="flex gap-1">
                                {(["daily", "weekly", "monthly"] as const).map((p) => (
                                    <button key={p} onClick={() => setPeriod(p)}
                                            className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                                                period === p ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                            }`}
                                    >
                                        {{ daily: "일별", weekly: "주별", monthly: "월별" }[p]}
                                    </button>
                                ))}
                            </div>
                        </div>
                        {salesStats.length === 0 ? (
                            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">데이터 없음</div>
                        ) : (
                            <ResponsiveContainer width="100%" height={220}>
                                <LineChart data={salesStats}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="날짜" tick={{ fontSize: 11 }} />
                                    <YAxis yAxisId="qty" orientation="left" tick={{ fontSize: 11 }} />
                                    <YAxis yAxisId="rev" orientation="right" tick={{ fontSize: 11 }}
                                               tickFormatter={(v: number) => v >= 10000 ? `${(v / 10000).toFixed(0)}만` : v.toLocaleString()} />
                                    <Tooltip formatter={(v: any, name: any): any =>
                                        name === "매출액" ? [`${Number(v).toLocaleString()}원`, name] : [v, name]
                                    } />
                                    <Legend />
                                    <Line yAxisId="qty" type="monotone" dataKey="판매수량" stroke="#3b82f6" strokeWidth={2} dot={false} name="판매수량" />
                                    <Line yAxisId="rev" type="monotone" dataKey="매출액" stroke="#10b981" strokeWidth={2} dot={false} name="매출액" />
                                </LineChart>
                            </ResponsiveContainer>
                        )}
                    </div>

                    {/* 재고 차트 */}
                    {stockStats && (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                <h3 className="font-semibold text-gray-700 mb-4">심각도별 이상 징후</h3>
                                <ResponsiveContainer width="100%" height={180}>
                                    <BarChart
                                        data={severityBarData}
                                        onClick={() => router.push("/dashboard/anomalies")}
                                        style={{ cursor: "pointer" }}
                                    >
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                                        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                        <Tooltip />
                                        <Bar dataKey="count" name="건수" radius={[4, 4, 0, 0]}>
                                            {severityBarData.map((_, i) => (
                                                <Cell key={i} fill={BAR_COLORS[i]} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>

                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                <h3 className="font-semibold text-gray-700 mb-4">상품별 재고 TOP 10</h3>
                                {(stockStats.stock_items?.length ?? 0) === 0 ? (
                                    <div className="h-[180px] flex items-center justify-center text-gray-400 text-sm">데이터 없음</div>
                                ) : (
                                    <ResponsiveContainer width="100%" height={180}>
                                        <BarChart
                                            data={stockStats.stock_items?.slice(0, 10) ?? []}
                                            layout="vertical"
                                            onClick={() => router.push("/dashboard/sheets")}
                                            style={{ cursor: "pointer" }}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                            <XAxis type="number" tick={{ fontSize: 10 }} />
                                            <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 10 }} width={60} />
                                            <Tooltip />
                                            <Bar dataKey="현재재고" fill="#3b82f6" radius={[0, 4, 4, 0]} name="현재재고" />
                                        </BarChart>
                                    </ResponsiveContainer>
                                )}
                            </div>
                        </div>
                    )}

                    {/* 이상 징후 테이블 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
                        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                            <h3 className="font-semibold text-gray-700">미해결 이상 징후 (최근 10건)</h3>
                            <button onClick={() => router.push("/dashboard/anomalies")}
                                    className="text-xs text-blue-500 hover:underline">전체 보기</button>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                <tr className="bg-gray-50 text-gray-500 text-xs">
                                    <th className="px-6 py-3 text-left">상품코드</th>
                                    <th className="px-6 py-3 text-left">상품명</th>
                                    <th className="px-6 py-3 text-left">카테고리</th>
                                    <th className="px-6 py-3 text-left">재고수</th>
                                    <th className="px-6 py-3 text-left">유형</th>
                                    <th className="px-6 py-3 text-left">심각도</th>
                                    <th className="px-6 py-3 text-left">감지일시</th>
                                </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                {anomalies.length === 0 ? (
                                    <tr>
                                        <td colSpan={7} className="px-6 py-8 text-center text-gray-400">이상 징후 없음</td>
                                    </tr>
                                ) : (
                                    anomalies.map((a) => (
                                        <tr key={a.id}
                                            onClick={() => router.push("/dashboard/anomalies")}
                                            className="hover:bg-gray-50 transition cursor-pointer"
                                        >
                                            <td className="px-6 py-3 font-mono text-gray-600">{a.product_code}</td>
                                            <td className="px-6 py-3 text-gray-700">{a.product_name}</td>
                                            <td className="px-6 py-3 text-gray-500">{a.category || "-"}</td>
                                            <td className="px-6 py-3 text-gray-600">{a.current_stock ?? "-"}</td>
                                            <td className="px-6 py-3 text-gray-600">{ANOMALY_KOR[a.anomaly_type] ?? a.anomaly_type}</td>
                                            <td className="px-6 py-3">
                                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_COLOR[a.severity]}`}>
                                                    {SEVERITY_KOR[a.severity]}
                                                </span>
                                            </td>
                                            <td className="px-6 py-3 text-gray-400">{a.detected_at.slice(0, 16)}</td>
                                        </tr>
                                    ))
                                )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
