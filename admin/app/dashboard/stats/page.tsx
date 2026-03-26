"use client";

import { useEffect, useState } from "react";
import { getSalesStats, getStockStats, getAbcStats, getDemandForecast, getTurnoverStats } from "@/lib/api";
import { SalesStatItem, StockItem } from "@/lib/types";
import {
    LineChart, Line, BarChart, Bar,
    XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";

const PERIOD_LABELS = { daily: "일별", weekly: "주별", monthly: "월별" };
const PIE_COLORS    = ["#ef4444", "#f97316", "#eab308", "#22c55e"];

// ABC 등급별 색상
const ABC_COLOR: Record<string, string> = {
    A: "#22c55e",
    B: "#eab308",
    C: "#9ca3af",
};
const ABC_BG: Record<string, string> = {
    A: "bg-green-50 text-green-700",
    B: "bg-yellow-50 text-yellow-700",
    C: "bg-gray-100 text-gray-600",
};

// 회전율 등급별 색상
const TURNOVER_COLOR: Record<string, string> = {
    "우수":     "#22c55e",
    "보통":     "#3b82f6",
    "주의":     "#ef4444",
    "데이터없음": "#9ca3af",
};
const TURNOVER_BG: Record<string, string> = {
    "우수":     "bg-green-50 text-green-700",
    "보통":     "bg-blue-50 text-blue-700",
    "주의":     "bg-red-50 text-red-600",
    "데이터없음": "bg-gray-100 text-gray-500",
};

// 추세 아이콘
function TrendIcon({ trend }: { trend: string }) {
    if (trend === "up")   return <TrendingUp   size={14} className="text-red-500" />;
    if (trend === "down") return <TrendingDown size={14} className="text-blue-500" />;
    return <Minus size={14} className="text-gray-400" />;
}

type TabType = "sales" | "stock" | "abc" | "demand" | "turnover";

const TAB_LABELS: Record<TabType, string> = {
    sales:    "판매 통계",
    stock:    "재고 통계",
    abc:      "ABC 분석",
    demand:   "수요 예측",
    turnover: "재고 회전율",
};

export default function StatsPage() {
    const [tab, setTab]             = useState<TabType>("sales");
    const [period, setPeriod]       = useState<"daily" | "weekly" | "monthly">("daily");
    const [salesData, setSalesData] = useState<SalesStatItem[]>([]);
    const [stockStats, setStockStats] = useState<any>(null);
    const [abcData, setAbcData]     = useState<any[]>([]);
    const [demandData, setDemandData] = useState<any[]>([]);
    const [turnoverData, setTurnoverData] = useState<any[]>([]);
    const [loading, setLoading]     = useState(false);

    // 판매 통계
    useEffect(() => {
        if (tab !== "sales") return;
        getSalesStats(period).then((res) => setSalesData(res.data.items));
    }, [period, tab]);

    // 재고 통계
    useEffect(() => {
        if (tab !== "stock" || stockStats) return;
        getStockStats().then((res) => setStockStats(res.data));
    }, [tab]);

    // ABC 분석
    useEffect(() => {
        if (tab !== "abc" || abcData.length) return;
        setLoading(true);
        getAbcStats().then((res) => setAbcData(res.data.items ?? [])).finally(() => setLoading(false));
    }, [tab]);

    // 수요 예측
    useEffect(() => {
        if (tab !== "demand" || demandData.length) return;
        setLoading(true);
        getDemandForecast().then((res) => setDemandData(res.data.items ?? [])).finally(() => setLoading(false));
    }, [tab]);

    // 재고 회전율
    useEffect(() => {
        if (tab !== "turnover" || turnoverData.length) return;
        setLoading(true);
        getTurnoverStats().then((res) => setTurnoverData(res.data.items ?? [])).finally(() => setLoading(false));
    }, [tab]);

    const pieData = stockStats
        ? [
            { name: "긴급", value: stockStats.severity_counts.critical },
            { name: "높음", value: stockStats.severity_counts.high },
            { name: "보통", value: stockStats.severity_counts.medium },
            { name: "낮음", value: stockStats.severity_counts.low },
        ].filter((d) => d.value > 0)
        : [];

    // ABC 요약
    const abcSummary = ["A", "B", "C"].map((g) => ({
        grade: g,
        count: abcData.filter((i) => i.등급 === g).length,
        ratio: abcData.filter((i) => i.등급 === g).reduce((s: number, i: any) => s + (i.매출비율 ?? 0), 0).toFixed(1),
    }));

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold text-gray-800">통계</h2>
                <p className="text-gray-400 text-sm mt-1">판매량·재고 현황 분석</p>
            </div>

            {/* 탭 */}
            <div className="flex gap-2 flex-wrap">
                {(Object.keys(TAB_LABELS) as TabType[]).map((t) => (
                    <button key={t} onClick={() => setTab(t)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                                tab === t ? "bg-blue-600 text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                            }`}
                    >
                        {TAB_LABELS[t]}
                    </button>
                ))}
            </div>

            {/* ── 판매 통계 ── */}
            {tab === "sales" && (
                <div className="space-y-6">
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
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">{PERIOD_LABELS[period]} 판매수량</h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={salesData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="날짜" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                                <YAxis tick={{ fontSize: 10 }} />
                                <Tooltip formatter={(v: any) => [Number(v).toLocaleString() + "개", "판매수량"]} labelStyle={{ fontSize: 11 }} />
                                <Bar dataKey="판매수량" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">{PERIOD_LABELS[period]} 매출액</h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <LineChart data={salesData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="날짜" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                                <Tooltip formatter={(v: any) => [Number(v).toLocaleString() + "원", "매출액"]} labelStyle={{ fontSize: 11 }} />
                                <Line dataKey="매출액" stroke="#6366f1" strokeWidth={2} dot={false} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* ── 재고 통계 ── */}
            {tab === "stock" && stockStats && (
                <div className="grid grid-cols-2 gap-6">
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">이상 징후 심각도 분포</h3>
                        {pieData.length === 0 ? (
                            <p className="text-center text-gray-400 text-sm py-10">이상 징후 없음</p>
                        ) : (
                            <ResponsiveContainer width="100%" height={240}>
                                <PieChart>
                                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                                         label={({ name, value }) => `${name}: ${value}`}>
                                        {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                                    </Pie>
                                    <Legend /><Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                        <h3 className="text-sm font-semibold text-gray-700 mb-4">상품별 현재 재고 (상위 10)</h3>
                        <ResponsiveContainer width="100%" height={240}>
                            <BarChart data={stockStats.stock_items.slice(0, 10)} layout="vertical">
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis type="number" tick={{ fontSize: 10 }} />
                                <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 9 }} width={50} />
                                <Tooltip formatter={(v: any) => [Number(v).toLocaleString() + "개", "현재재고"]} labelStyle={{ fontSize: 11 }} />
                                <Bar dataKey="현재재고" fill="#10b981" radius={[0, 3, 3, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* ── ABC 분석 ── */}
            {tab === "abc" && (
                <div className="space-y-6">
                    {loading ? (
                        <div className="flex justify-center py-16"><Loader2 size={28} className="animate-spin text-blue-500" /></div>
                    ) : (
                        <>
                            {/* 요약 카드 */}
                            <div className="grid grid-cols-3 gap-4">
                                {abcSummary.map(({ grade, count, ratio }) => (
                                    <div key={grade} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className={`px-2.5 py-0.5 rounded-full text-sm font-bold ${ABC_BG[grade]}`}>
                                                등급 {grade}
                                            </span>
                                            <span className="text-xs text-gray-400">{count}개 상품</span>
                                        </div>
                                        <p className="text-2xl font-bold text-gray-800">{ratio}%</p>
                                        <p className="text-xs text-gray-400 mt-0.5">매출 기여도</p>
                                    </div>
                                ))}
                            </div>

                            {/* 차트 (상위 20개) */}
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                <h3 className="text-sm font-semibold text-gray-700 mb-4">상품별 매출 기여 (상위 20)</h3>
                                <ResponsiveContainer width="100%" height={320}>
                                    <BarChart data={abcData.slice(0, 20)} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                        <XAxis type="number" tick={{ fontSize: 10 }}
                                               tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`} />
                                        <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 9 }} width={60} />
                                        <Tooltip
                                            formatter={(v: any) => [Number(v).toLocaleString() + "원", "매출합계"]}
                                            labelStyle={{ fontSize: 11 }}
                                        />
                                        <Bar dataKey="매출합계" radius={[0, 3, 3, 0]}>
                                            {abcData.slice(0, 20).map((item: any, i: number) => (
                                                <Cell key={i} fill={ABC_COLOR[item.등급] ?? "#9ca3af"} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </>
                    )}
                </div>
            )}

            {/* ── 수요 예측 ── */}
            {tab === "demand" && (
                <div className="space-y-4">
                    {loading ? (
                        <div className="flex justify-center py-16"><Loader2 size={28} className="animate-spin text-blue-500" /></div>
                    ) : (
                        <>
                            <div className="flex items-center gap-3 text-sm text-gray-500">
                                <span className="px-2 py-0.5 bg-red-50 text-red-600 rounded-full text-xs font-medium">재고 부족</span>
                                <span>예측 기간 14일 기준 · 7일 이동평균</span>
                            </div>
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead>
                                    <tr className="bg-gray-50 text-gray-500 text-xs">
                                        <th className="px-5 py-3 text-left">상품코드</th>
                                        <th className="px-5 py-3 text-left">상품명</th>
                                        <th className="px-5 py-3 text-right">현재재고</th>
                                        <th className="px-5 py-3 text-right">예측수요</th>
                                        <th className="px-5 py-3 text-right">부족수량</th>
                                        <th className="px-5 py-3 text-center">추세</th>
                                        <th className="px-5 py-3 text-center">상태</th>
                                    </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                    {demandData.map((item: any, i: number) => (
                                        <tr key={i} className="hover:bg-gray-50 transition">
                                            <td className="px-5 py-3 font-mono text-gray-600 text-xs">{item.product_code}</td>
                                            <td className="px-5 py-3 text-gray-700">{item.product_name || "-"}</td>
                                            <td className="px-5 py-3 text-right text-gray-600">{item.current_stock.toLocaleString()}</td>
                                            <td className="px-5 py-3 text-right text-gray-600">{item.forecast_qty.toLocaleString()}</td>
                                            <td className="px-5 py-3 text-right">
                                                {item.shortage > 0
                                                    ? <span className="text-red-500 font-medium">{item.shortage.toLocaleString()}</span>
                                                    : <span className="text-gray-300">-</span>
                                                }
                                            </td>
                                            <td className="px-5 py-3 text-center">
                                                <div className="flex justify-center">
                                                    <TrendIcon trend={item.trend} />
                                                </div>
                                            </td>
                                            <td className="px-5 py-3 text-center">
                                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                                        item.sufficient ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"
                                                    }`}>
                                                        {item.sufficient ? "충분" : "부족"}
                                                    </span>
                                            </td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    )}
                </div>
            )}

            {/* ── 재고 회전율 ── */}
            {tab === "turnover" && (
                <div className="space-y-6">
                    {loading ? (
                        <div className="flex justify-center py-16"><Loader2 size={28} className="animate-spin text-blue-500" /></div>
                    ) : (
                        <>
                            {/* 차트 (체류일수 있는 상위 15개) */}
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                <h3 className="text-sm font-semibold text-gray-700 mb-4">
                                    상품별 체류일수 (30일 기준)
                                    <span className="ml-2 text-xs font-normal text-gray-400">낮을수록 우수</span>
                                </h3>
                                <ResponsiveContainer width="100%" height={320}>
                                    <BarChart
                                        data={turnoverData.filter((i: any) => i.체류일수 !== null).slice(0, 15)}
                                        layout="vertical"
                                    >
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                        <XAxis type="number" tick={{ fontSize: 10 }} unit="일" />
                                        <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 9 }} width={60} />
                                        <Tooltip
                                            formatter={(v: any) => [`${v}일`, "체류일수"]}
                                            labelStyle={{ fontSize: 11 }}
                                        />
                                        <Bar dataKey="체류일수" radius={[0, 3, 3, 0]}>
                                            {turnoverData
                                                .filter((i: any) => i.체류일수 !== null)
                                                .slice(0, 15)
                                                .map((item: any, i: number) => (
                                                    <Cell key={i} fill={TURNOVER_COLOR[item.등급] ?? "#9ca3af"} />
                                                ))
                                            }
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>

                            {/* 테이블 */}
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead>
                                    <tr className="bg-gray-50 text-gray-500 text-xs">
                                        <th className="px-5 py-3 text-left">상품코드</th>
                                        <th className="px-5 py-3 text-left">상품명</th>
                                        <th className="px-5 py-3 text-right">기간판매량</th>
                                        <th className="px-5 py-3 text-right">현재재고</th>
                                        <th className="px-5 py-3 text-right">회전율</th>
                                        <th className="px-5 py-3 text-right">체류일수</th>
                                        <th className="px-5 py-3 text-center">등급</th>
                                    </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                    {turnoverData.map((item: any, i: number) => (
                                        <tr key={i} className="hover:bg-gray-50 transition">
                                            <td className="px-5 py-3 font-mono text-gray-600 text-xs">{item.상품코드}</td>
                                            <td className="px-5 py-3 text-gray-700">{item.상품명 || "-"}</td>
                                            <td className="px-5 py-3 text-right text-gray-600">{item.기간판매량.toLocaleString()}</td>
                                            <td className="px-5 py-3 text-right text-gray-600">{item.현재재고.toLocaleString()}</td>
                                            <td className="px-5 py-3 text-right text-gray-600">{item.회전율}</td>
                                            <td className="px-5 py-3 text-right text-gray-600">
                                                {item.체류일수 !== null ? `${item.체류일수}일` : "-"}
                                            </td>
                                            <td className="px-5 py-3 text-center">
                                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TURNOVER_BG[item.등급] ?? "bg-gray-100 text-gray-500"}`}>
                                                        {item.등급}
                                                    </span>
                                            </td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
