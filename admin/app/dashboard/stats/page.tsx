"use client";

import {useEffect, useState} from "react";
import {
    getAbcStats,
    getDemandForecast,
    getSalesStats,
    getSheetCategories,
    getStockStats,
    getTaskStatus,
    getTurnoverStats,
} from "@/lib/api";
import {getDefaultPageSize} from "@/lib/utils";
import {SalesStatItem} from "@/lib/types";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import {ChevronLeft, ChevronRight, Loader2, Minus, Search, TrendingDown, TrendingUp, X,} from "lucide-react";

// ── 상수 ──────────────────────────────────────────────────────────────────────
const PERIOD_LABELS = { daily: "일별", weekly: "주별", monthly: "월별" };
const PIE_COLORS    = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6"];

const ABC_BG: Record<string, string> = {
    A: "bg-green-50 text-green-700",
    B: "bg-yellow-50 text-yellow-700",
    C: "bg-gray-100 text-gray-600",
};
const ABC_COLOR: Record<string, string> = {
    A: "#22c55e", B: "#eab308", C: "#9ca3af",
};
const TURNOVER_BG: Record<string, string> = {
    "우수":      "bg-green-50 text-green-700",
    "보통":      "bg-blue-50 text-blue-700",
    "주의":      "bg-red-50 text-red-600",
    "데이터없음": "bg-gray-100 text-gray-500",
};

// ── 공통 컴포넌트 ──────────────────────────────────────────────────────────────

function TrendIcon({ trend }: { trend: string }) {
    if (trend === "up")   return <TrendingUp   size={14} className="text-red-500" />;
    if (trend === "down") return <TrendingDown size={14} className="text-blue-500" />;
    return <Minus size={14} className="text-gray-400" />;
}

function Pagination({
                        current, total, onPageChange,
                    }: {
    current: number; total: number; onPageChange: (p: number) => void;
}) {
    if (total <= 1) return null;
    const pages = Array.from({ length: total }, (_, i) => i + 1)
        .filter((p) => p === 1 || p === total || Math.abs(p - current) <= 1)
        .reduce<(number | "…")[]>((acc, p, idx, arr) => {
            if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("…");
            acc.push(p);
            return acc;
        }, []);

    return (
        <div className="flex items-center justify-end gap-1 mt-4">
            <button
                onClick={() => onPageChange(current - 1)}
                disabled={current === 1}
                className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 transition"
            >
                <ChevronLeft size={14} />
            </button>
            {pages.map((p, i) =>
                p === "…" ? (
                    <span key={`e-${i}`} className="px-1 text-gray-400 text-xs">…</span>
                ) : (
                    <button
                        key={p}
                        onClick={() => onPageChange(p as number)}
                        className={`min-w-[30px] h-[30px] rounded-lg text-xs font-medium transition ${
                            current === p
                                ? "bg-blue-600 text-white"
                                : "border border-gray-200 text-gray-600 hover:bg-gray-50"
                        }`}
                    >
                        {p}
                    </button>
                )
            )}
            <button
                onClick={() => onPageChange(current + 1)}
                disabled={current === total}
                className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 transition"
            >
                <ChevronRight size={14} />
            </button>
        </div>
    );
}

// 검색 입력 컴포넌트
function SearchInput({
                         value, onChange, onClear, placeholder = "상품코드 / 상품명 검색",
                     }: {
    value: string;
    onChange: (v: string) => void;
    onClear: () => void;
    placeholder?: string;
}) {
    return (
        <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-1.5 bg-white min-w-52">
            <Search size={13} className="text-gray-400 shrink-0" />
            <input
                type="text"
                placeholder={placeholder}
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="text-sm outline-none w-full"
            />
            {value && (
                <button onClick={onClear} className="text-gray-400 hover:text-gray-600">
                    <X size={12} />
                </button>
            )}
        </div>
    );
}

// ── 분석 태스크 폴링 ──────────────────────────────────────────────────────────
async function resolveAnalysis(apiRes: any): Promise<any> {
    if (!apiRes.data?.task_id) return apiRes.data;
    let data = apiRes.data;
    while (data.state !== "SUCCESS" && data.state !== "FAILURE") {
        await new Promise((r) => setTimeout(r, 1500));
        const poll = await getTaskStatus(data.task_id);
        data = poll.data;
    }
    if (data.state === "FAILURE") throw new Error(data.error ?? "분석 실패");
    return data.result;
}

// ── 할인율 계산 헬퍼 ──────────────────────────────────────────────────────────
function calcDiscount(revenue: number, cost: number, qty: number): {
    unitSell: number; unitCost: number; marginRate: number; discountRate: number;
} {
    const unitSell = qty > 0 ? revenue / qty : 0;
    const unitCost = qty > 0 ? cost    / qty : 0;
    const marginRate   = unitSell > 0 ? ((unitSell - unitCost) / unitSell) * 100 : 0;
    // 최대 할인 가능 비율 = 마진율 (원가 이하로 내리지 않는 기준)
    const discountRate = marginRate > 0 ? marginRate : 0;
    return { unitSell, unitCost, marginRate, discountRate };
}

// ── 탭 타입 ──────────────────────────────────────────────────────────────────
type TabType = "sales" | "stock" | "abc" | "demand" | "turnover";
const TAB_LABELS: Record<TabType, string> = {
    sales:    "판매 통계",
    stock:    "재고 통계",
    abc:      "ABC 분석",
    demand:   "수요 예측",
    turnover: "재고 회전율",
};

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function StatsPage() {
    const [tab, setTab]     = useState<TabType>("sales");
    const [loading, setLoading] = useState(false);
    const [taskMsg, setTaskMsg] = useState("");

    // 공통 카테고리
    const [allCategories, setAllCategories] = useState<string[]>([]);

    // 판매 통계
    const [period, setPeriod]     = useState<"daily" | "weekly" | "monthly">("daily");
    const [salesData, setSalesData] = useState<SalesStatItem[]>([]);
    const [salesCategory, setSalesCategory] = useState("");

    // 재고 통계
    const [stockStats, setStockStats] = useState<any>(null);
    const [stockPage, setStockPage] = useState(1);
    const [stockPageSize, setStockPageSize] = useState(getDefaultPageSize);
    const [stockTotalPages, setStockTotalPages] = useState(1);
    const [stockTotal, setStockTotal] = useState(0);
    const [stockCategory, setStockCategory] = useState("");
    const [stockSearch,   setStockSearch]   = useState("");

    // ABC 분석
    const [abcData, setAbcData]         = useState<any[]>([]);
    const [abcCategory, setAbcCategory] = useState("");

    // 수요 예측
    const [demandData, setDemandData]               = useState<any[]>([]);
    const [demandPage, setDemandPage]               = useState(1);
    const [demandPageSize, setDemandPageSize]       = useState(getDefaultPageSize);
    const [demandTotalPages, setDemandTotalPages]   = useState(1);
    const [demandTotal, setDemandTotal]             = useState(0);
    const [demandCategory, setDemandCategory]       = useState("");
    const [demandCategories, setDemandCategories]   = useState<string[]>([]);
    const [demandSearch, setDemandSearch]           = useState("");

    // 재고 회전율
    const [turnoverData, setTurnoverData]             = useState<any[]>([]);
    const [turnoverPage, setTurnoverPage]             = useState(1);
    const [turnoverPageSize, setTurnoverPageSize]     = useState(getDefaultPageSize);
    const [turnoverTotalPages, setTurnoverTotalPages] = useState(1);
    const [turnoverTotal, setTurnoverTotal]           = useState(0);
    const [turnoverCategory, setTurnoverCategory]     = useState("");
    const [turnoverCategories, setTurnoverCategories] = useState<string[]>([]);
    const [turnoverSearch, setTurnoverSearch]         = useState("");

    // ── 카테고리 목록 초기 로드 ──────────────────────────────────────────────
    useEffect(() => {
        getSheetCategories().then((r) => setAllCategories(r.data.items ?? [])).catch(() => {});
    }, []);

    // ── 통합 데이터 로드 ─────────────────────────────────────────────────────
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setTaskMsg("");
            try {
                if (tab === "sales") {
                    const res = await getSalesStats(period, salesCategory || undefined);
                    setSalesData(res.data.items ?? []);

                } else if (tab === "stock") {
                    const res = await getStockStats(stockCategory || undefined, stockSearch || undefined, stockPage, stockPageSize);
                    setStockStats(res.data);
                    setStockTotal(res.data.total ?? 0);
                    setStockTotalPages(res.data.total_pages ?? 1);

                } else if (tab === "abc") {
                    const res  = await getAbcStats(90, abcCategory || undefined);
                    const data = res.data?.task_id ? await resolveAnalysis(res) : res.data;
                    setAbcData(data?.items ?? []);

                } else if (tab === "demand") {
                    const res  = await getDemandForecast(14, demandPage, demandPageSize, demandCategory || undefined);
                    if (res.data?.task_id) setTaskMsg("수요 분석 중...");
                    const data = res.data?.task_id ? await resolveAnalysis(res) : res.data;
                    setDemandData(data?.items ?? []);
                    setDemandTotalPages(data?.total_pages ?? 1);
                    setDemandTotal(data?.total ?? 0);
                    if (data?.categories?.length) setDemandCategories(data.categories);

                } else if (tab === "turnover") {
                    const res  = await getTurnoverStats(30, turnoverPage, turnoverPageSize, turnoverCategory || undefined);
                    if (res.data?.task_id) setTaskMsg("회전율 계산 중...");
                    const data = res.data?.task_id ? await resolveAnalysis(res) : res.data;
                    setTurnoverData(data?.items ?? []);
                    setTurnoverTotalPages(data?.total_pages ?? 1);
                    setTurnoverTotal(data?.total ?? 0);
                    if (data?.categories?.length) setTurnoverCategories(data.categories);
                }
            } catch (err) {
                console.error("StatsPage fetchData error:", err);
            } finally {
                setLoading(false);
                setTaskMsg("");
            }
        };
        fetchData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        tab, period,
        salesCategory, stockCategory, stockSearch, stockPage, stockPageSize,
        abcCategory,
        demandPage, demandPageSize, demandCategory,
        turnoverPage, turnoverPageSize, turnoverCategory,
    ]);

    // ── 파생 데이터 ──────────────────────────────────────────────────────────
    const pieData = stockStats
        ? [
            { name: "긴급", value: stockStats.severity_counts?.CRITICAL ?? 0 },
            { name: "높음", value: stockStats.severity_counts?.HIGH     ?? 0 },
            { name: "보통", value: stockStats.severity_counts?.MEDIUM   ?? 0 },
            { name: "낮음", value: stockStats.severity_counts?.LOW      ?? 0 },
            { name: "확인", value: stockStats.severity_counts?.CHECK    ?? 0 },
        ].filter((d) => d.value > 0)
        : [];

    const abcSummary = ["A", "B", "C"].map((g) => ({
        grade: g,
        count: abcData.filter((i) => i.등급 === g).length,
        ratio: abcData.filter((i) => i.등급 === g)
            .reduce((s: number, i: any) => s + (i.매출비율 ?? 0), 0)
            .toFixed(1),
    }));

    // 클라이언트 사이드 검색 필터
    const filteredDemand = demandSearch
        ? demandData.filter((item: any) =>
            (item.product_code ?? "").toLowerCase().includes(demandSearch.toLowerCase()) ||
            (item.product_name ?? "").toLowerCase().includes(demandSearch.toLowerCase())
        )
        : demandData;

    const filteredTurnover = turnoverSearch
        ? turnoverData.filter((item: any) =>
            (item.상품코드 ?? "").toLowerCase().includes(turnoverSearch.toLowerCase()) ||
            (item.상품명  ?? "").toLowerCase().includes(turnoverSearch.toLowerCase())
        )
        : turnoverData;

    // ── 재고현황 매입/할인 데이터 (stock_items에 cost 포함 시) ────────────────
    const stockItemsWithDiscount = (stockStats?.stock_items ?? []).map((item: any) => ({
        ...item,
        unitSell: item.unit_sell ?? 0,
        unitCost: item.unit_cost ?? 0,
        marginRate: item.margin_rate ?? 0,
        discountRate: item.discount_max ?? 0,
    }));

    // ── 렌더 ─────────────────────────────────────────────────────────────────
    return (
        <div className="space-y-6">

            {/* 헤더 */}
            <div className="flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">통계 분석</h2>
                    <p className="text-gray-400 text-sm mt-1">판매·재고 현황 분석</p>
                </div>
                {taskMsg && (
                    <div className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 px-3 py-1.5 rounded-full">
                        <Loader2 size={12} className="animate-spin" /> {taskMsg}
                    </div>
                )}
            </div>

            {/* 탭 */}
            <div className="flex gap-2 flex-wrap border-b border-gray-100 pb-4">
                {(Object.keys(TAB_LABELS) as TabType[]).map((t) => (
                    <button
                        key={t}
                        onClick={() => setTab(t)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                            tab === t
                                ? "bg-blue-600 text-white shadow-sm"
                                : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                        }`}
                    >
                        {TAB_LABELS[t]}
                    </button>
                ))}
            </div>

            {/* ──────────────────────────────────────────────────────── 판매 통계 */}
            {tab === "sales" && (
                <div className="space-y-6">
                    <div className="flex justify-between items-center flex-wrap gap-3">
                        <div className="flex gap-2">
                            {(["daily", "weekly", "monthly"] as const).map((p) => (
                                <button
                                    key={p}
                                    onClick={() => setPeriod(p)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                                        period === p
                                            ? "bg-blue-100 text-blue-600"
                                            : "bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                                    }`}
                                >
                                    {PERIOD_LABELS[p]}
                                </button>
                            ))}
                        </div>
                        <select
                            value={salesCategory}
                            onChange={(e) => setSalesCategory(e.target.value)}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none bg-white"
                        >
                            <option value="">전체 카테고리</option>
                            {allCategories.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>

                    {loading ? (
                        <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div>
                    ) : (
                        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                            <h3 className="text-sm font-semibold text-gray-700 mb-4">{PERIOD_LABELS[period]} 판매수량</h3>
                            <ResponsiveContainer width="100%" height={260}>
                                <BarChart data={salesData}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                                    <XAxis dataKey="날짜" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                                    <YAxis tick={{ fontSize: 10 }} />
                                    <Tooltip />
                                    <Bar dataKey="판매수량" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </div>
            )}

            {/* ──────────────────────────────────────────────────────── 재고 통계 */}
            {tab === "stock" && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2 justify-end">
                        {/* 검색창 */}
                        <input
                            type="text"
                            value={stockSearch}
                            onChange={(e) => { setStockSearch(e.target.value); setStockPage(1); setStockStats(null); }}
                            placeholder="상품코드 / 상품명 검색"
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-300 w-52"
                        />
                        <select
                            value={stockCategory}
                            onChange={(e) => { setStockCategory(e.target.value); setStockPage(1); setStockStats(null); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none bg-white"
                        >
                            <option value="">전체 카테고리</option>
                            {allCategories.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                        {(stockSearch || stockCategory) && (
                            <button
                                onClick={() => { setStockSearch(""); setStockCategory(""); setStockPage(1); setStockStats(null); }}
                                className="px-2.5 py-1.5 rounded-lg text-xs text-gray-400 border border-gray-200 hover:bg-gray-50 transition"
                            >
                                초기화
                            </button>
                        )}
                        <select
                            value={stockPageSize}
                            onChange={(e) => { setStockPageSize(Number(e.target.value)); setStockPage(1); }}
                            className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none"
                        >
                            {[10, 25, 50, 100].map((n) => (
                                <option key={n} value={n}>{n}건</option>
                            ))}
                        </select>
                    </div>

                    {loading ? (
                        <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div>
                    ) : (
                        <>
                            {/* 차트 2열 */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                    <h3 className="text-sm font-semibold text-gray-700 mb-4">심각도별 분포</h3>
                                    {pieData.length === 0 ? (
                                        <p className="text-center text-gray-400 py-10 text-sm">데이터 없음</p>
                                    ) : (
                                        <ResponsiveContainer width="100%" height={240}>
                                            <PieChart>
                                                <Pie
                                                    data={pieData}
                                                    dataKey="value"
                                                    nameKey="name"
                                                    cx="50%" cy="50%"
                                                    outerRadius={80}
                                                    label={({ name, value }) => `${name}: ${value}`}
                                                >
                                                    {pieData.map((_, i) => (
                                                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Legend /><Tooltip />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    )}
                                </div>

                                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                    <h3 className="text-sm font-semibold text-gray-700 mb-4">상품별 현재 재고 (Top 10)</h3>
                                    <ResponsiveContainer width="100%" height={240}>
                                        <BarChart
                                            data={(stockStats?.stock_items ?? []).slice(0, 10)}
                                            layout="vertical"
                                        >
                                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
                                            <XAxis type="number" tick={{ fontSize: 10 }} />
                                            <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 9 }} width={60} />
                                            <Tooltip />
                                            <Bar dataKey="현재재고" fill="#10b981" radius={[0, 4, 4, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            {/* ── 매입액 / 할인율 참고 테이블 ── */}
                            {stockItemsWithDiscount.length > 0 && (
                                <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                                    <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                                        <div>
                                            <h3 className="text-sm font-semibold text-gray-700">재고 상품 단가 / 할인율 참고</h3>
                                            <p className="text-xs text-gray-400 mt-0.5">
                                                매입단가 기반 최대 할인 가능 비율 (원가 손실 없는 기준)
                                            </p>
                                        </div>
                                    </div>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                            <tr className="bg-gray-50 text-gray-500 text-xs">
                                                <th className="px-5 py-3 text-left whitespace-nowrap">상품코드</th>
                                                <th className="px-5 py-3 text-left whitespace-nowrap">상품명</th>
                                                <th className="px-5 py-3 text-right whitespace-nowrap">현재재고</th>
                                                <th className="px-5 py-3 text-right whitespace-nowrap">평균 판매단가</th>
                                                <th className="px-5 py-3 text-right whitespace-nowrap">평균 매입단가</th>
                                                <th className="px-5 py-3 text-right whitespace-nowrap">마진율</th>
                                                <th className="px-5 py-3 text-right whitespace-nowrap">최대 할인 가능</th>
                                                <th className="px-5 py-3 text-center whitespace-nowrap">할인 여력</th>
                                            </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-50">
                                            {stockItemsWithDiscount.map((item: any, i: number) => {
                                                const margin   = item.marginRate;
                                                const discount = item.discountRate;
                                                const marginColor =
                                                    margin >= 30 ? "text-green-600"
                                                        : margin >= 15 ? "text-blue-600"
                                                            : margin >= 0  ? "text-amber-600"
                                                                : "text-red-500";
                                                const discountBadge =
                                                    discount >= 30 ? "bg-green-50 text-green-700"
                                                        : discount >= 15 ? "bg-blue-50 text-blue-700"
                                                            : discount > 0   ? "bg-amber-50 text-amber-700"
                                                                : "bg-gray-100 text-gray-400";
                                                const discountLabel =
                                                    discount >= 30 ? "여유"
                                                        : discount >= 15 ? "보통"
                                                            : discount > 0   ? "타이트"
                                                                : "할인불가";

                                                return (
                                                    <tr key={i} className="hover:bg-gray-50 transition">
                                                        <td className="px-5 py-2.5 font-mono text-xs text-gray-600">
                                                            {item.상품코드}
                                                        </td>
                                                        <td className="px-5 py-2.5 text-gray-700 max-w-[160px] truncate">
                                                            {item.상품명 ?? "-"}
                                                        </td>
                                                        <td className="px-5 py-2.5 text-right text-gray-700">
                                                            {(item.현재재고 ?? 0).toLocaleString()}
                                                        </td>
                                                        <td className="px-5 py-2.5 text-right text-gray-700">
                                                            {item.unitSell > 0 ? `${Math.round(item.unitSell).toLocaleString()}원` : "-"}
                                                        </td>
                                                        <td className="px-5 py-2.5 text-right text-gray-700">
                                                            {item.unitCost > 0 ? `${Math.round(item.unitCost).toLocaleString()}원` : "-"}
                                                        </td>
                                                        <td className={`px-5 py-2.5 text-right font-medium ${marginColor}`}>
                                                            {margin !== 0 ? `${margin.toFixed(1)}%` : "-"}
                                                        </td>
                                                        <td className={`px-5 py-2.5 text-right font-semibold ${marginColor}`}>
                                                            {discount > 0 ? `최대 ${discount.toFixed(1)}%` : "-"}
                                                        </td>
                                                        <td className="px-5 py-2.5 text-center">
                                                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${discountBadge}`}>
                                                                {discountLabel}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                            </tbody>
                                            {stockTotalPages > 1 && (
                                                <Pagination
                                                    current={stockPage}
                                                    total={stockTotalPages}
                                                    onPageChange={(p) => { setStockPage(p); }}
                                                />
                                            )}
                                        </table>
                                    </div>
                                    <div className="px-5 py-3 bg-gray-50 border-t border-gray-100">
                                        <p className="text-xs text-gray-400">
                                            * 평균 단가는 일별판매 데이터의 매출액/매입액 ÷ 판매수량으로 산출됩니다.
                                            매입액 데이터가 없는 경우 "-"로 표시됩니다.
                                        </p>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* ──────────────────────────────────────────────────────── ABC 분석 */}
            {tab === "abc" && (
                <div className="space-y-6">
                    <div className="flex justify-end">
                        <select
                            value={abcCategory}
                            onChange={(e) => { setAbcCategory(e.target.value); setAbcData([]); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none bg-white"
                        >
                            <option value="">전체 카테고리</option>
                            {allCategories.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>

                    {loading ? (
                        <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div>
                    ) : (
                        <>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {abcSummary.map(({ grade, count, ratio }) => (
                                    <div key={grade} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${ABC_BG[grade]}`}>
                                                등급 {grade}
                                            </span>
                                            <span className="text-xs text-gray-400">{count}개 품목</span>
                                        </div>
                                        <p className="text-2xl font-bold text-gray-800">{ratio}%</p>
                                        <p className="text-xs text-gray-400 mt-0.5">매출 기여 비중</p>
                                    </div>
                                ))}
                            </div>
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                <h3 className="text-sm font-semibold text-gray-700 mb-4">매출 합계 (상위 20)</h3>
                                <ResponsiveContainer width="100%" height={320}>
                                    <BarChart data={abcData.slice(0, 20)} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
                                        <XAxis type="number" tick={{ fontSize: 10 }} />
                                        <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 9 }} width={70} />
                                        <Tooltip />
                                        <Bar dataKey="매출합계" radius={[0, 4, 4, 0]}>
                                            {abcData.slice(0, 20).map((item, i) => (
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

            {/* ──────────────────────────────────────────────────────── 수요 예측 */}
            {tab === "demand" && (
                <div className="space-y-4">

                    {/* 필터 바 */}
                    <div className="flex items-center gap-3 flex-wrap">
                        <span className="px-2 py-0.5 bg-red-50 text-red-600 rounded-full text-xs font-medium shrink-0">
                            재고 부족
                        </span>
                        <span className="text-sm text-gray-500 shrink-0">예측 14일 · 7일 이동평균</span>

                        {/* 검색 */}
                        <SearchInput
                            value={demandSearch}
                            onChange={(v) => { setDemandSearch(v); setDemandPage(1); }}
                            onClear={() => { setDemandSearch(""); setDemandPage(1); }}
                        />

                        {/* 카테고리 */}
                        {demandCategories.length > 0 && (
                            <select
                                value={demandCategory}
                                onChange={(e) => { setDemandCategory(e.target.value); setDemandPage(1); }}
                                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                            >
                                <option value="">전체 카테고리</option>
                                {demandCategories.map((c) => <option key={c} value={c}>{c}</option>)}
                            </select>
                        )}

                        <span className="ml-auto text-xs text-gray-400 shrink-0">총 {demandTotal}건</span>
                        <select
                            value={demandPageSize}
                            onChange={(e) => { setDemandPageSize(Number(e.target.value)); setDemandPage(1); }}
                            className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none"
                        >
                            {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}건</option>)}
                        </select>
                    </div>

                    {loading ? (
                        <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div>
                    ) : (
                        <>
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                    <tr className="bg-gray-50 text-gray-500 text-xs text-left">
                                        <th className="px-5 py-3 whitespace-nowrap">상품코드</th>
                                        <th className="px-5 py-3 whitespace-nowrap">상품명</th>
                                        <th className="px-5 py-3 text-right whitespace-nowrap">현재재고</th>
                                        <th className="px-5 py-3 text-right whitespace-nowrap">예측수요</th>
                                        <th className="px-5 py-3 text-right whitespace-nowrap">부족분</th>
                                        <th className="px-5 py-3 text-center whitespace-nowrap">추세</th>
                                        <th className="px-5 py-3 text-center whitespace-nowrap">상태</th>
                                    </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                    {filteredDemand.length === 0 ? (
                                        <tr>
                                            <td colSpan={7} className="px-5 py-10 text-center text-gray-400 text-sm">
                                                {demandSearch ? `"${demandSearch}" 검색 결과 없음` : "데이터 없음"}
                                            </td>
                                        </tr>
                                    ) : filteredDemand.map((item: any, i: number) => (
                                        <tr key={i} className="hover:bg-gray-50 transition">
                                            <td className="px-5 py-3 font-mono text-xs text-gray-600">
                                                {item.product_code}
                                            </td>
                                            <td className="px-5 py-3 text-gray-700 max-w-[180px] truncate">
                                                {item.product_name ?? "-"}
                                            </td>
                                            <td className="px-5 py-3 text-right text-gray-600">
                                                {(item.current_stock ?? 0).toLocaleString()}
                                            </td>
                                            <td className="px-5 py-3 text-right text-gray-600">
                                                {(item.forecast_qty ?? 0).toLocaleString()}
                                            </td>
                                            <td className="px-5 py-3 text-right">
                                                {item.shortage > 0
                                                    ? <span className="text-red-500 font-semibold">{item.shortage.toLocaleString()}</span>
                                                    : <span className="text-gray-300">-</span>}
                                            </td>
                                            <td className="px-5 py-3 text-center">
                                                <div className="flex justify-center">
                                                    <TrendIcon trend={item.trend} />
                                                </div>
                                            </td>
                                            <td className="px-5 py-3 text-center">
                                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                                    item.sufficient
                                                        ? "bg-green-50 text-green-700"
                                                        : "bg-red-50 text-red-600"
                                                }`}>
                                                    {item.sufficient ? "충분" : "부족"}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            </div>
                            <Pagination
                                current={demandPage}
                                total={demandTotalPages}
                                onPageChange={setDemandPage}
                            />
                        </>
                    )}
                </div>
            )}

            {/* ──────────────────────────────────────────────────────── 재고 회전율 */}
            {tab === "turnover" && (
                <div className="space-y-4">

                    {/* 필터 바 */}
                    <div className="flex items-center gap-3 flex-wrap bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
                        <span className="text-sm font-semibold text-gray-700 shrink-0">
                            재고 회전 효율
                        </span>
                        <span className="text-xs text-gray-400">총 {turnoverTotal}건</span>

                        {/* 검색 */}
                        <SearchInput
                            value={turnoverSearch}
                            onChange={(v) => { setTurnoverSearch(v); setTurnoverPage(1); }}
                            onClear={() => { setTurnoverSearch(""); setTurnoverPage(1); }}
                        />

                        {/* 카테고리 */}
                        <select
                            value={turnoverCategory}
                            onChange={(e) => { setTurnoverCategory(e.target.value); setTurnoverPage(1); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                        >
                            <option value="">전체 카테고리</option>
                            {(turnoverCategories.length > 0 ? turnoverCategories : allCategories).map((c) => (
                                <option key={c} value={c}>{c}</option>
                            ))}
                        </select>

                        <select
                            value={turnoverPageSize}
                            onChange={(e) => { setTurnoverPageSize(Number(e.target.value)); setTurnoverPage(1); }}
                            className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none ml-auto"
                        >
                            {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}건</option>)}
                        </select>
                    </div>

                    {loading ? (
                        <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div>
                    ) : (
                        <>
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                    <tr className="bg-gray-50 text-gray-500 text-xs text-left">
                                        <th className="px-5 py-3 whitespace-nowrap">상품코드</th>
                                        <th className="px-5 py-3 whitespace-nowrap">상품명</th>
                                        <th className="px-5 py-3 text-right whitespace-nowrap">기간판매량</th>
                                        <th className="px-5 py-3 text-right whitespace-nowrap">현재재고</th>
                                        <th className="px-5 py-3 text-right whitespace-nowrap">회전율</th>
                                        <th className="px-5 py-3 text-right whitespace-nowrap">체류일수</th>
                                        <th className="px-5 py-3 text-center whitespace-nowrap">등급</th>
                                    </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                    {filteredTurnover.length === 0 ? (
                                        <tr>
                                            <td colSpan={7} className="px-5 py-10 text-center text-gray-400 text-sm">
                                                {turnoverSearch ? `"${turnoverSearch}" 검색 결과 없음` : "데이터 없음"}
                                            </td>
                                        </tr>
                                    ) : filteredTurnover.map((item: any, i: number) => (
                                        <tr key={i} className="hover:bg-gray-50 transition">
                                            <td className="px-5 py-3 font-mono text-xs text-gray-600">
                                                {item.상품코드}
                                            </td>
                                            <td className="px-5 py-3 text-gray-700 max-w-[180px] truncate">
                                                {item.상품명 ?? "-"}
                                            </td>
                                            <td className="px-5 py-3 text-right text-gray-600">
                                                {(item.기간판매량 ?? 0).toLocaleString()}
                                            </td>
                                            <td className="px-5 py-3 text-right text-gray-600">
                                                {(item.현재재고 ?? 0).toLocaleString()}
                                            </td>
                                            <td className="px-5 py-3 text-right font-medium text-blue-600">
                                                {item.회전율 ?? "-"}
                                            </td>
                                            <td className="px-5 py-3 text-right text-gray-600">
                                                {item.체류일수 != null ? `${item.체류일수}일` : "-"}
                                            </td>
                                            <td className="px-5 py-3 text-center">
                                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                                    TURNOVER_BG[item.등급] ?? "bg-gray-100 text-gray-500"
                                                }`}>
                                                    {item.등급}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            </div>
                            <Pagination
                                current={turnoverPage}
                                total={turnoverTotalPages}
                                onPageChange={setTurnoverPage}
                            />
                        </>
                    )}
                </div>
            )}

        </div>
    );
}
