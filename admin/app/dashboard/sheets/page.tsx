"use client";

import { useEffect, useRef, useState } from "react";
import { getSheetsMaster, getSheetsSales, getSheetsStock } from "@/lib/api";
import { RefreshCw, Loader2, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";

const TABS = ["상품마스터", "일별판매", "재고현황"] as const;
type Tab = typeof TABS[number];

export default function SheetsPage() {
    const [tab, setTab]           = useState<Tab>("상품마스터");
    const [data, setData]         = useState<any[]>([]);
    const [loading, setLoad]      = useState(false);
    const [days, setDays]         = useState(30);
    const [page, setPage]         = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [total, setTotal]       = useState(0);
    const topRef                  = useRef<HTMLDivElement>(null);

    const fetchData = async () => {
        setLoad(true);
        try {
            if (tab === "상품마스터") {
                const res = await getSheetsMaster(page, 50);
                setData(res.data.items ?? []);
                setTotalPages(res.data.total_pages ?? 1);
                setTotal(res.data.total ?? 0);
            } else if (tab === "일별판매") {
                const res = await getSheetsSales(days);
                setData(res.data.items ?? []);
                setTotalPages(1);
                setTotal(res.data.total ?? 0);
            } else {
                const res = await getSheetsStock();
                setData(res.data.items ?? []);
                setTotalPages(1);
                setTotal(res.data.total ?? 0);
            }
        } finally {
            setLoad(false);
        }
    };

    // 탭/일수 바뀌면 page 리셋
    useEffect(() => { setPage(1); }, [tab, days]);
    useEffect(() => { fetchData(); }, [tab, days, page]);

    const scrollToTop = () => topRef.current?.scrollIntoView({ behavior: "smooth" });

    const columns = data.length > 0 ? Object.keys(data[0]) : [];

    return (
        <div className="space-y-5" ref={topRef}>
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">데이터 조회</h2>
                    <p className="text-gray-400 text-sm mt-1">Google Sheets 원본 데이터</p>
                </div>
                <button onClick={fetchData} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition">
                    <RefreshCw size={15} className={`text-gray-500 ${loading ? "animate-spin" : ""}`} />
                </button>
            </div>

            {/* 탭 */}
            <div className="flex gap-2 flex-wrap">
                {TABS.map((t) => (
                    <button
                        key={t}
                        onClick={() => setTab(t)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                            tab === t ? "bg-blue-600 text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                        }`}
                    >
                        {t}
                    </button>
                ))}
                {tab === "일별판매" && (
                    <select
                        value={days}
                        onChange={(e) => setDays(Number(e.target.value))}
                        className="ml-2 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                    >
                        <option value={7}>최근 7일</option>
                        <option value={30}>최근 30일</option>
                        <option value={90}>최근 90일</option>
                    </select>
                )}
            </div>

            {/* 페이지네이션 (상단) + 총 건수 */}
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">총 {total}건</span>
                {totalPages > 1 && (
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page === 1 || loading}
                            className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 transition"
                        >
                            <ChevronLeft size={14} />
                        </button>
                        {Array.from({ length: totalPages }, (_, i) => i + 1)
                            .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
                            .reduce<(number | "…")[]>((acc, p, idx, arr) => {
                                if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("…");
                                acc.push(p);
                                return acc;
                            }, [])
                            .map((p, i) =>
                                p === "…" ? (
                                    <span key={`ellipsis-${i}`} className="px-1 text-gray-400 text-xs">…</span>
                                ) : (
                                    <button
                                        key={p}
                                        onClick={() => setPage(p as number)}
                                        className={`min-w-[30px] h-[30px] rounded-lg text-xs font-medium transition ${
                                            page === p
                                                ? "bg-blue-600 text-white"
                                                : "border border-gray-200 text-gray-600 hover:bg-gray-50"
                                        }`}
                                    >
                                        {p}
                                    </button>
                                )
                            )
                        }
                        <button
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page === totalPages || loading}
                            className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 transition"
                        >
                            <ChevronRight size={14} />
                        </button>
                    </div>
                )}
            </div>

            {/* 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                {loading ? (
                    <div className="flex items-center justify-center py-16">
                        <Loader2 size={28} className="animate-spin text-blue-500" />
                    </div>
                ) : data.length === 0 ? (
                    <div className="py-12 text-center text-gray-400 text-sm">데이터 없음</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                        <tr className="bg-gray-50 text-gray-500 text-xs">
                            {columns.map((col) => (
                                <th key={col} className="px-5 py-3 text-left whitespace-nowrap">{col}</th>
                            ))}
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                        {data.map((row, i) => (
                            <tr key={i} className="hover:bg-gray-50 transition">
                                {columns.map((col) => (
                                    <td key={col} className="px-5 py-2.5 text-gray-700 whitespace-nowrap">
                                        {String(row[col] ?? "-")}
                                    </td>
                                ))}
                            </tr>
                        ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* 맨위로 버튼 */}
            <div className="flex justify-end">
                <button
                    onClick={scrollToTop}
                    className="flex items-center gap-1 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs font-medium transition"
                >
                    <ArrowUp size={13} /> ▲
                </button>
            </div>
        </div>
    );
}
