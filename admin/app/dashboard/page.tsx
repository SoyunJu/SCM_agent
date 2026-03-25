"use client";

import { useEffect, useState } from "react";
import {
    getAnomalies, getReportHistory, triggerReport,
    getSalesStats, getStockStats,
} from "@/lib/api";
import { AnomalyLog, ReportExecution, SalesStatItem } from "@/lib/types";
import { AlertTriangle, Package, TrendingUp, FileText, Play, RefreshCw } from "lucide-react";
import {
    LineChart, Line, BarChart, Bar,
    XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, Legend,
} from "recharts";

const SEVERITY_COLOR: Record<string, string> = {
    critical: "text-red-600 bg-red-50",
    high:     "text-orange-500 bg-orange-50",
    medium:   "text-yellow-500 bg-yellow-50",
    low:      "text-green-600 bg-green-50",
};
const SEVERITY_KOR: Record<string, string> = {
    critical: "긴급", high: "높음", medium: "보통", low: "낮음",
};
const ANOMALY_KOR: Record<string, string> = {
    low_stock: "재고 부족", over_stock: "재고 과잉",
    sales_surge: "판매 급등", sales_drop: "판매 급락",
    long_term_stock: "장기 재고",
};

export default function DashboardPage() {
    const [anomalies, setAnomalies]     = useState<AnomalyLog[]>([]);
    const [history, setHistory]         = useState<ReportExecution[]>([]);
    const [salesStats, setSalesStats]   = useState<SalesStatItem[]>([]);
    const [stockStats, setStockStats]   = useState<any>(null);
    const [period, setPeriod]           = useState<"daily"|"weekly"|"monthly">("daily");
    const [triggering, setTriggering]   = useState(false);
    const [message, setMessage]         = useState("");
    const [loading, setLoading]         = useState(true);

    const fetchAll = async () => {
        setLoading(true);
        try {
            const [anomRes, histRes, statsRes, stockRes] = await Promise.all([
                getAnomalies(false, 10),
                getReportHistory(5),
                getSalesStats(period),
                getStockStats(),
            ]);
            setAnomalies(anomRes.data.items);
            setHistory(histRes.data.items);
            setSalesStats(statsRes.data.items);
            setStockStats(stockRes.data);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchAll(); }, []);

    useEffect(() => {
        getSalesStats(period).then((res) => setSalesStats(res.data.items));
    }, [period]);

    const handleTrigger = async () => {
        setTriggering(true);
        setMessage("");
        try {
            await triggerReport();
            setMessage("✅ 보고서 생성이 시작되었습니다.");
        } catch {
            setMessage("❌ 보고서 생성에 실패했습니다.");
        } finally {
            setTriggering(false);
        }
    };

    const critical  = anomalies.filter((a) => a.severity === "critical").length;
    const high      = anomalies.filter((a) => a.severity === "high").length;
    const lastRun   = history[0];

    return (
        <div className="space-y-6">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">대시보드</h2>
                    <p className="text-gray-400 text-sm mt-1">재고·판매 현황 요약</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={fetchAll} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition">
                        <RefreshCw size={15} className="text-gray-500" />
                    </button>
                    <button
                        onClick={handleTrigger}
                        disabled={triggering}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                    >
                        <Play size={14} />
                        {triggering ? "생성 중..." : "보고서 즉시 생성"}
                    </button>
                </div>
            </div>

            {message && (
                <p className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">{message}</p>
            )}

            {/* 통계 카드 */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: "미해결 이상 징후", value: anomalies.length, icon: AlertTriangle, color: "text-orange-500" },
                    { label: "긴급",            value: critical,          icon: Package,       color: "text-red-500"    },
                    { label: "높음",            value: high,              icon: TrendingUp,    color: "text-orange-400" },
                    { label: "최근 보고서",
                        value: lastRun?.status === "success" ? "성공" : lastRun?.status ?? "-",
                        icon: FileText, color: "text-blue-500" },
                ].map(({ label, value, icon: Icon, color }) => (
                    <div key={label} className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs text-gray-400">{label}</span>
                            <Icon size={16} className={color} />
                        </div>
                        <p className="text-2xl font-bold text-gray-800">{value}</p>
                    </div>
                ))}
            </div>

            {/* 판매 통계 그래프 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-gray-700">판매 추이</h3>
                    <div className="flex gap-1">
                        {(["daily","weekly","monthly"] as const).map((p) => (
                            <button
                                key={p}
                                onClick={() => setPeriod(p)}
                                className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                                    period === p
                                        ? "bg-blue-600 text-white"
                                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                                }`}
                            >
                                {{ daily: "일별", weekly: "주별", monthly: "월별" }[p]}
                            </button>
                        ))}
                    </div>
                </div>
                {salesStats.length === 0 ? (
                    <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
                        데이터 없음
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={220}>
                        <LineChart data={salesStats}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                            <XAxis dataKey="날짜" tick={{ fontSize: 11 }} />
                            <YAxis yAxisId="qty" orientation="left" tick={{ fontSize: 11 }} />
                            <YAxis yAxisId="rev" orientation="right" tick={{ fontSize: 11 }} />
                            <Tooltip />
                            <Legend />
                            <Line yAxisId="qty" type="monotone" dataKey="판매수량" stroke="#3b82f6" strokeWidth={2} dot={false} name="판매수량" />
                            <Line yAxisId="rev" type="monotone" dataKey="매출액" stroke="#10b981" strokeWidth={2} dot={false} name="매출액" />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </div>

            {/* 재고 현황 그래프 */}
            {stockStats && (
                <div className="grid grid-cols-2 gap-4">
                    {/* 심각도별 이상 징후 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="font-semibold text-gray-700 mb-4">심각도별 이상 징후</h3>
                        <ResponsiveContainer width="100%" height={180}>
                            <BarChart data={[
                                { name: "긴급", count: stockStats.severity_counts?.critical ?? 0, fill: "#ef4444" },
                                { name: "높음", count: stockStats.severity_counts?.high ?? 0,     fill: "#f97316" },
                                { name: "보통", count: stockStats.severity_counts?.medium ?? 0,   fill: "#eab308" },
                                { name: "낮음", count: stockStats.severity_counts?.low ?? 0,      fill: "#22c55e" },
                            ]}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                <Tooltip />
                                <Bar dataKey="count" name="건수" radius={[4, 4, 0, 0]}>
                                    {[
                                        { fill: "#ef4444" }, { fill: "#f97316" },
                                        { fill: "#eab308" }, { fill: "#22c55e" },
                                    ].map((entry, i) => (
                                        <rect key={i} fill={entry.fill} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    {/* 상품별 재고 TOP 10 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="font-semibold text-gray-700 mb-4">상품별 재고 TOP 10</h3>
                        <ResponsiveContainer width="100%" height={180}>
                            <BarChart
                                data={stockStats.stock_items?.slice(0, 10) ?? []}
                                layout="vertical"
                            >
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis type="number" tick={{ fontSize: 10 }} />
                                <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 10 }} width={50} />
                                <Tooltip />
                                <Bar dataKey="현재재고" fill="#3b82f6" radius={[0, 4, 4, 0]} name="현재재고" />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* 미해결 이상 징후 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
                <div className="px-6 py-4 border-b border-gray-100">
                    <h3 className="font-semibold text-gray-700">미해결 이상 징후 (최근 10건)</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                        <tr className="bg-gray-50 text-gray-500 text-xs">
                            <th className="px-6 py-3 text-left">상품코드</th>
                            <th className="px-6 py-3 text-left">상품명</th>
                            <th className="px-6 py-3 text-left">유형</th>
                            <th className="px-6 py-3 text-left">심각도</th>
                            <th className="px-6 py-3 text-left">감지일시</th>
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                        {anomalies.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="px-6 py-8 text-center text-gray-400">이상 징후 없음</td>
                            </tr>
                        ) : (
                            anomalies.map((a) => (
                                <tr key={a.id} className="hover:bg-gray-50 transition">
                                    <td className="px-6 py-3 font-mono text-gray-600">{a.product_code}</td>
                                    <td className="px-6 py-3 text-gray-700">{a.product_name}</td>
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
        </div>
    );
}