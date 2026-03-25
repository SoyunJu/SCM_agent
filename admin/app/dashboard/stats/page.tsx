"use client";

import { useEffect, useState } from "react";
import { getSalesStats, getStockStats } from "@/lib/api";
import { SalesStatItem, StockItem } from "@/lib/types";
import {
    LineChart, Line, BarChart, Bar,
    XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";

const PERIOD_LABELS = { daily: "일별", weekly: "주별", monthly: "월별" };
const PIE_COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e"];

export default function StatsPage() {
    const [period, setPeriod]           = useState<"daily" | "weekly" | "monthly">("daily");
    const [salesData, setSalesData]     = useState<SalesStatItem[]>([]);
    const [stockStats, setStockStats]   = useState<any>(null);
    const [tab, setTab]                 = useState<"sales" | "stock">("sales");

    useEffect(() => {
        getSalesStats(period).then((res) => setSalesData(res.data.items));
    }, [period]);

    useEffect(() => {
        getStockStats().then((res) => setStockStats(res.data));
    }, []);

    const pieData = stockStats
        ? [
            { name: "긴급", value: stockStats.severity_counts.critical },
            { name: "높음", value: stockStats.severity_counts.high },
            { name: "보통", value: stockStats.severity_counts.medium },
            { name: "낮음", value: stockStats.severity_counts.low },
        ].filter((d) => d.value > 0)
        : [];

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold text-gray-800">통계</h2>
                <p className="text-gray-400 text-sm mt-1">판매량·재고 현황 분석</p>
            </div>

            {/* 탭 */}
            <div className="flex gap-2">
                {(["sales", "stock"] as const).map((t) => (
                    <button key={t} onClick={() => setTab(t)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                                tab === t ? "bg-blue-600 text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                            }`}
                    >
                        {t === "sales" ? "판매 통계" : "재고 통계"}
                    </button>
                ))}
            </div>

            {tab === "sales" && (
                <div className="space-y-6">
                    {/* 기간 선택 */}
                    <div className="flex gap-2">
                        {(["daily", "weekly", "monthly"] as const).map((p) => (
                            <button key={p} onClick={() => setPeriod(p)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                                        period === p ? "bg-blue-100 text-blue-600" : "bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                                    }`}
                            >
                                {PERIOD_LABELS[p]}
                            </button>
                        ))}
                    </div>

                    {/* 판매수량 차트 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">
                            {PERIOD_LABELS[period]} 판매수량
                        </h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={salesData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="날짜" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                                <YAxis tick={{ fontSize: 10 }} />
                                <Tooltip
                                    formatter={(v: any) => [Number(v).toLocaleString() + "개", "판매수량"]}
                                    labelStyle={{ fontSize: 11 }}
                                />
                                <Bar dataKey="판매수량" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    {/* 매출액 차트 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">
                            {PERIOD_LABELS[period]} 매출액
                        </h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <LineChart data={salesData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="날짜" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                                <Tooltip
                                    formatter={(v: any) => [Number(v).toLocaleString() + "원", "매출액"]}
                                    labelStyle={{ fontSize: 11 }}
                                />
                                <Line dataKey="매출액" stroke="#6366f1" strokeWidth={2} dot={false} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {tab === "stock" && stockStats && (
                <div className="grid grid-cols-2 gap-6">
                    {/* 심각도 파이 차트 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">
                            이상 징후 심각도 분포
                        </h3>
                        {pieData.length === 0 ? (
                            <p className="text-center text-gray-400 text-sm py-10">이상 징후 없음</p>
                        ) : (
                            <ResponsiveContainer width="100%" height={240}>
                                <PieChart>
                                    <Pie data={pieData} dataKey="value" nameKey="name"
                                         cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}
                                    >
                                        {pieData.map((_, i) => (
                                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <Legend />
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        )}
                    </div>

                    {/* 상품별 재고 바 차트 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">
                            상품별 현재 재고 (상위 10)
                        </h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart
                                data={stockStats.stock_items.slice(0, 10)}
                                layout="vertical"
                            >
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis type="number" tick={{ fontSize: 10 }} />
                                <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 9 }} width={50} />
                                <Tooltip
                                    formatter={(v: any) => [Number(v).toLocaleString() + "개", "현재재고"]}
                                    labelStyle={{ fontSize: 11 }}
                                />
                                <Bar dataKey="현재재고" fill="#10b981" radius={[0, 3, 3, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}
        </div>
    );
}