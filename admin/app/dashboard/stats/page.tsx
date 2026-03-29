"use client";

import {useEffect, useState} from "react";
import {
    getAbcStats,
    getDemandForecast,
    getSalesStats,
    getSheetCategories,
    getStockStats,
    getTaskStatus,
    getTurnoverStats
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
import {ChevronLeft, ChevronRight, Loader2, Minus, Search, TrendingDown, TrendingUp, X} from "lucide-react";

// ── 상수 및 스타일 설정 ──
const PERIOD_LABELS = { daily: "일별", weekly: "주별", monthly: "월별" };
const PIE_COLORS    = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6"];
const ABC_COLOR: Record<string, string> = { A: "#22c55e", B: "#eab308", C: "#9ca3af" };
const ABC_BG: Record<string, string> = {
    A: "bg-green-50 text-green-700",
    B: "bg-yellow-50 text-yellow-700",
    C: "bg-gray-100 text-gray-600",
};
const TURNOVER_COLOR: Record<string, string> = {
    "우수": "#22c55e", "보통": "#3b82f6", "주의": "#ef4444", "데이터없음": "#9ca3af",
};
const TURNOVER_BG: Record<string, string> = {
    "우수": "bg-green-50 text-green-700",
    "보통": "bg-blue-50 text-blue-700",
    "주의": "bg-red-50 text-red-600",
    "데이터없음": "bg-gray-100 text-gray-500",
};

// ── 공통 컴포넌트: 추세 아이콘 ──
function TrendIcon({ trend }: { trend: string }) {
    if (trend === "up")   return <TrendingUp   size={14} className="text-red-500" />;
    if (trend === "down") return <TrendingDown size={14} className="text-blue-500" />;
    return <Minus size={14} className="text-gray-400" />;
}

// ── 공통 컴포넌트: 페이지네이션 ──
function Pagination({ current, total, onPageChange }: { current: number, total: number, onPageChange: (p: number) => void }) {
    if (total <= 1) return null;
    const pages = Array.from({ length: total }, (_, i) => i + 1)
        .filter((p) => p === 1 || p === total || Math.abs(p - current) <= 1)
        .reduce<(number | "…")[]>((acc, p, idx, arr) => {
            if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("…");
            acc.push(p); return acc;
        }, []);

    return (
        <div className="flex items-center justify-end gap-1 mt-4">
            <button onClick={() => onPageChange(current - 1)} disabled={current === 1} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
                <ChevronLeft size={14} />
            </button>
            {pages.map((p, i) => p === "…"
                ? <span key={`e-${i}`} className="px-1 text-gray-400 text-xs">…</span>
                : <button key={p} onClick={() => onPageChange(p as number)}
                          className={`min-w-[30px] h-[30px] rounded-lg text-xs font-medium transition ${current === p ? "bg-blue-600 text-white" : "border border-gray-200 text-gray-600 hover:bg-gray-50"}`}>{p}</button>
            )}
            <button onClick={() => onPageChange(current + 1)} disabled={current === total} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
                <ChevronRight size={14} />
            </button>
        </div>
    );
}

// ── 분석 태스크 폴링 로직 ──
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

type TabType = "sales" | "stock" | "abc" | "demand" | "turnover";
const TAB_LABELS: Record<TabType, string> = {
    sales: "판매 통계", stock: "재고 통계", abc: "ABC 분석", demand: "수요 예측", turnover: "재고 회전율",
};

export default function StatsPage() {
    const [tab, setTab] = useState<TabType>("sales");
    const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("daily");
    const [loading, setLoading] = useState(false);
    const [taskMsg, setTaskMsg] = useState("");
    const [allCategories, setAllCategories] = useState<string[]>([]);

    // 데이터 상태
    const [salesData, setSalesData] = useState<SalesStatItem[]>([]);
    const [stockStats, setStockStats] = useState<any>(null);
    const [abcData, setAbcData] = useState<any[]>([]);

    // 수요 예측/회전율 페이징 상태
    const [demandData, setDemandData] = useState<any[]>([]);
    const [demandPage, setDemandPage] = useState(1);
    const [demandPageSize, setDemandPageSize] = useState(getDefaultPageSize);
    const [demandTotalPages, setDemandTotalPages] = useState(1);
    const [demandTotal, setDemandTotal] = useState(0);

    const [turnoverData, setTurnoverData] = useState<any[]>([]);
    const [turnoverPage, setTurnoverPage] = useState(1);
    const [turnoverPageSize, setTurnoverPageSize] = useState(getDefaultPageSize);
    const [turnoverTotalPages, setTurnoverTotalPages] = useState(1);
    const [turnoverTotal, setTurnoverTotal] = useState(0);

    // 필터 상태
    const [salesCategory, setSalesCategory] = useState("");
    const [stockCategory, setStockCategory] = useState("");
    const [abcCategory, setAbcCategory] = useState("");
    const [demandCategory, setDemandCategory] = useState("");
    const [turnoverCategory, setTurnoverCategory] = useState("");
    const [demandSearch, setDemandSearch] = useState<string>("");
    const [turnoverSearch, setTurnoverSearch] = useState<string>("");

    // 카테고리 로드
    useEffect(() => {
        getSheetCategories().then((r) => setAllCategories(r.data.items ?? [])).catch(() => {});
    }, []);

    // 통합 데이터 로드
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            setTaskMsg("");
            try {
                if (tab === "sales") {
                    const res = await getSalesStats(period, salesCategory || undefined);
                    setSalesData(res.data.items ?? []);
                } else if (tab === "stock") {
                    const res = await getStockStats(stockCategory || undefined);
                    setStockStats(res.data);
                } else if (tab === "abc") {
                    const res = await getAbcStats(90, abcCategory || undefined);
                    const data = res.data?.task_id ? await resolveAnalysis(res) : res.data;
                    setAbcData(data?.items ?? []);
                } else if (tab === "demand") {
                    const res = await getDemandForecast(14, demandPage, demandPageSize, demandCategory || undefined);
                    if (res.data?.task_id) setTaskMsg("수요 분석 중...");
                    const data = res.data?.task_id ? await resolveAnalysis(res) : res.data;
                    setDemandData(data?.items ?? []);
                    setDemandTotalPages(data?.total_pages ?? 1);
                    setDemandTotal(data?.total ?? 0);
                } else if (tab === "turnover") {
                    const res = await getTurnoverStats(30, turnoverPage, turnoverPageSize, turnoverCategory || undefined);
                    if (res.data?.task_id) setTaskMsg("회전율 계산 중...");
                    const data = res.data?.task_id ? await resolveAnalysis(res) : res.data;
                    setTurnoverData(data?.items ?? []);
                    setTurnoverTotalPages(data?.total_pages ?? 1);
                    setTurnoverTotal(data?.total ?? 0);
                }
            } catch (err) {
                console.error("Fetch Error:", err);
            } finally {
                setLoading(false);
                setTaskMsg("");
            }
        };
        fetchData();
    }, [tab, period, salesCategory, stockCategory, abcCategory, demandPage, demandPageSize, demandCategory, turnoverPage, turnoverPageSize, turnoverCategory]);

    // 차트용 파이 데이터 가공
    const pieData = stockStats ? [
        { name: "긴급", value: stockStats.severity_counts?.CRITICAL ?? 0 },
        { name: "높음", value: stockStats.severity_counts?.HIGH     ?? 0 },
        { name: "보통", value: stockStats.severity_counts?.MEDIUM   ?? 0 },
        { name: "낮음", value: stockStats.severity_counts?.LOW      ?? 0 },
        { name: "확인", value: stockStats.severity_counts?.CHECK    ?? 0 },
    ].filter(d => d.value > 0) : [];

    const abcSummary = ["A", "B", "C"].map(g => ({
        grade: g,
        count: abcData.filter(i => i.등급 === g).length,
        ratio: abcData.filter(i => i.등급 === g).reduce((s, i) => s + (i.매출비율 ?? 0), 0).toFixed(1),
    }));

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">통계 분석</h2>
                    <p className="text-gray-400 text-sm mt-1">실시간 판매 및 재고 지표</p>
                </div>
                {taskMsg && (
                    <div className="flex items-center gap-2 text-xs text-blue-600 bg-blue-50 px-3 py-1.5 rounded-full animate-pulse">
                        <Loader2 size={12} className="animate-spin" /> {taskMsg}
                    </div>
                )}
            </div>

            {/* 탭 네비게이션 */}
            <div className="flex gap-2 flex-wrap border-b border-gray-100 pb-4">
                {(Object.keys(TAB_LABELS) as TabType[]).map((t) => (
                    <button key={t} onClick={() => setTab(t)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                                tab === t ? "bg-blue-600 text-white shadow-md" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                            }`}
                    >
                        {TAB_LABELS[t]}
                    </button>
                ))}
            </div>

            {/* ── 판매 통계 ── */}
            {tab === "sales" && (
                <div className="space-y-6">
                    <div className="flex justify-between items-center">
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
                        <select value={salesCategory} onChange={(e) => setSalesCategory(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none bg-white">
                            <option value="">전체 카테고리</option>
                            {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                    <div className="grid grid-cols-1 gap-6">
                        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                            <h3 className="text-sm font-semibold text-gray-700 mb-4">{PERIOD_LABELS[period]} 판매수량</h3>
                            <ResponsiveContainer width="100%" height={260}>
                                <BarChart data={salesData}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                                    <XAxis dataKey="날짜" tick={{ fontSize: 10 }} />
                                    <YAxis tick={{ fontSize: 10 }} />
                                    <Tooltip />
                                    <Bar dataKey="판매수량" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            )}

            {/* ── 재고 통계 ── */}
            {tab === "stock" && (
                <div className="space-y-4">
                    <div className="flex justify-end">
                        <select value={stockCategory} onChange={(e) => setStockCategory(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none bg-white">
                            <option value="">전체 카테고리</option>
                            {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                    {loading ? <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div> : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                <h3 className="text-sm font-semibold text-gray-700 mb-4">심각도별 분포</h3>
                                {pieData.length === 0 ? <p className="text-center text-gray-400 py-10">데이터 없음</p> : (
                                    <ResponsiveContainer width="100%" height={240}>
                                        <PieChart>
                                            <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                                                {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                                            </Pie>
                                            <Legend /><Tooltip />
                                        </PieChart>
                                    </ResponsiveContainer>
                                )}
                            </div>
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
                                <h3 className="text-sm font-semibold text-gray-700 mb-4">상품별 현재 재고 (Top 10)</h3>
                                <ResponsiveContainer width="100%" height={240}>
                                    <BarChart data={stockStats?.stock_items?.slice(0, 10) || []} layout="vertical">
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
                                        <XAxis type="number" tick={{ fontSize: 10 }} />
                                        <YAxis dataKey="상품코드" type="category" tick={{ fontSize: 9 }} width={60} />
                                        <Tooltip />
                                        <Bar dataKey="현재재고" fill="#10b981" radius={[0, 4, 4, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ── ABC 분석 ── */}
            {tab === "abc" && (
                <div className="space-y-6">
                    <div className="flex justify-end">
                        <select value={abcCategory} onChange={(e) => setAbcCategory(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none bg-white">
                            <option value="">전체 카테고리</option>
                            {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                    {loading ? <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div> : (
                        <>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {abcSummary.map(({ grade, count, ratio }) => (
                                    <div key={grade} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${ABC_BG[grade]}`}>등급 {grade}</span>
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
                                            {abcData.slice(0, 20).map((item, i) => <Cell key={i} fill={ABC_COLOR[item.등급] || "#9ca3af"} />)}
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
                    <div className="flex items-center gap-3 flex-wrap">
                        <span
                            className="px-2 py-0.5 bg-red-50 text-red-600 rounded-full text-xs font-medium">재고 부족</span>
                        <span className="text-sm text-gray-500">예측 기간 14일 기준 · 7일 이동평균</span>

                        {/* 회전율 필터 */}
                        <div className="flex items-center gap-3 flex-wrap">

                            {/* 검색 */}
                            <div
                                className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-1.5 bg-white min-w-48">
                                <Search size={13} className="text-gray-400 shrink-0"/>
                                <input
                                    type="text"
                                    placeholder="상품코드 / 상품명 검색"
                                    value={turnoverSearch}
                                    onChange={(e) => {
                                        setTurnoverSearch(e.target.value);
                                        setTurnoverPage(1);
                                    }}
                                    className="text-sm outline-none w-full"
                                />
                                {turnoverSearch && (
                                    <button onClick={() => {
                                        setTurnoverSearch("");
                                        setTurnoverPage(1);
                                    }} className="text-gray-400 hover:text-gray-600">
                                        <X size={12}/>
                                    </button>
                                )}
                            </div>

                            {/* 카테고리 */}
                            {turnoverCategories.length > 0 && (
                                <select
                                    value={turnoverCategory}
                                    onChange={(e) => {
                                        setTurnoverCategory(e.target.value);
                                        setTurnoverPage(1);
                                    }}
                                    className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                                >
                                    <option value="">전체 카테고리</option>
                                    {turnoverCategories.map((c) => <option key={c} value={c}>{c}</option>)}
                                </select>
                            )}
                            <span className="ml-auto text-xs text-gray-400">총 {turnoverTotal}건</span>
                            <select
                                value={turnoverPageSize}
                                onChange={(e) => {
                                    setTurnoverPageSize(Number(e.target.value));
                                    setTurnoverPage(1);
                                }}
                                className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none"
                            >
                                {[10, 25, 50, 100].map((n) => <option key={n} value={n}>{n}건</option>)}
                            </select>
                        </div>
                    {loading ? <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div> : (
                        <>
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-gray-50 text-gray-500 text-xs text-left">
                                    <tr>
                                        <th className="px-5 py-3">상품코드</th>
                                        <th className="px-5 py-3">상품명</th>
                                        <th className="px-5 py-3 text-right">현재재고</th>
                                        <th className="px-5 py-3 text-right">예측수요</th>
                                        <th className="px-5 py-3 text-right">부족분</th>
                                        <th className="px-5 py-3 text-center">추세</th>
                                    </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">

                                    {(() => {
                                        const filteredDemand = demandSearch
                                            ? demandData.filter((item: any) =>
                                                (item.product_code ?? "").toLowerCase().includes(demandSearch.toLowerCase()) ||
                                                (item.product_name ?? "").toLowerCase().includes(demandSearch.toLowerCase())
                                            )
                                            : demandData;

                                        return filteredDemand.length === 0 ? (
                                            <tr>
                                                <td colSpan={7}
                                                    className="px-5 py-10 text-center text-gray-400 text-sm">
                                                    {demandSearch ? `"${demandSearch}" 검색 결과 없음` : "데이터 없음"}
                                                </td>
                                            </tr>
                                        ) : (
                                            filteredDemand.map((item: any, i: number) => (
                                                <tr key={i} className="hover:bg-gray-50 transition">
                                            <td className="px-5 py-3 font-mono text-xs">{item.product_code}</td>
                                            <td className="px-5 py-3 truncate max-w-[180px]">{item.product_name}</td>
                                            <td className="px-5 py-3 text-right">{item.current_stock?.toLocaleString()}</td>
                                            <td className="px-5 py-3 text-right">{item.forecast_qty?.toLocaleString()}</td>
                                            <td className="px-5 py-3 text-right text-red-500 font-semibold">{item.shortage > 0 ? item.shortage.toLocaleString() : "-"}</td>
                                            <td className="px-5 py-3 flex justify-center"><TrendIcon trend={item.trend} /></td>
                                        </tr>
                                            ))
                                        );
                                    })()}
                                    </tbody>
                                </table>
                            </div>
                            <Pagination current={demandPage} total={demandTotalPages} onPageChange={setDemandPage} />
                        </>
                    )}
                </div>
            )}

            {/* ── 재고 회전율 ── */}
            {tab === "turnover" && (
                <div className="space-y-4">
                    <div className="flex items-center gap-3 bg-white p-4 rounded-xl border border-gray-100">
                        <span className="text-sm font-semibold text-gray-700 mr-auto">재고 회전 효율 <span className="text-xs font-normal text-gray-400 ml-2">Total {turnoverTotal}</span></span>
                        <select value={turnoverCategory} onChange={(e) => { setTurnoverCategory(e.target.value); setTurnoverPage(1); }} className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                            <option value="">전체 카테고리</option>
                            {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <select value={turnoverPageSize} onChange={(e) => { setTurnoverPageSize(Number(e.target.value)); setTurnoverPage(1); }} className="border border-gray-200 rounded-lg px-2 py-1 text-xs">
                            {[10, 25, 50].map(n => <option key={n} value={n}>{n}건씩</option>)}
                        </select>
                    </div>
                    {loading ? <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-blue-500" /></div> : (
                        <>
                            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead className="bg-gray-50 text-gray-500 text-xs text-left">
                                    <tr>
                                        <th className="px-5 py-3">상품코드</th>
                                        <th className="px-5 py-3">상품명</th>
                                        <th className="px-5 py-3 text-right">회전율</th>
                                        <th className="px-5 py-3 text-right">체류일수</th>
                                        <th className="px-5 py-3 text-center">등급</th>
                                    </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-50">
                                    {turnoverData.map((item, i) => (
                                        <tr key={i} className="hover:bg-gray-50 transition">
                                            <td className="px-5 py-3 font-mono text-xs">{item.상품코드}</td>
                                            <td className="px-5 py-3 truncate max-w-[180px]">{item.상품명}</td>
                                            <td className="px-5 py-3 text-right font-medium text-blue-600">{item.회전율}</td>
                                            <td className="px-5 py-3 text-right">{item.체류일수}일</td>
                                            <td className="px-5 py-3 text-center">
                                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TURNOVER_BG[item.등급] || "bg-gray-100 text-gray-500"}`}>{item.등급}</span>
                                            </td>
                                        </tr>
                                    ))}
                                    </tbody>
                                </table>
                            </div>
                            <Pagination current={turnoverPage} total={turnoverTotalPages} onPageChange={setTurnoverPage} />
                        </>
                    )}
                </div>
            )}
        </div>
    );
}