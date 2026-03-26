"use client";

import { useEffect, useState } from "react";
import { getOrders } from "@/lib/api";
import { OrderItem } from "@/lib/types";
import { Package, Loader2, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";

const STATUS_TABS = ["전체", "발주완료", "입고중", "입고완료", "반품"] as const;

const STATUS_COLOR: Record<string, string> = {
    발주완료: "text-blue-600 bg-blue-50",
    입고중:   "text-yellow-600 bg-yellow-50",
    입고완료: "text-green-600 bg-green-50",
    반품:     "text-red-500 bg-red-50",
};

export default function OrdersPage() {
    const [orders, setOrders]         = useState<OrderItem[]>([]);
    const [tab, setTab]               = useState<string>("전체");
    const [loading, setLoading]       = useState(false);
    const [page, setPage]             = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [total, setTotal]           = useState(0);

    const fetchData = async () => {
        setLoading(true);
        try {
            const status = tab === "전체" ? undefined : tab;
            const res = await getOrders({ status, page, page_size: 50 });
            setOrders(res.data.items ?? []);
            setTotalPages(res.data.total_pages ?? 1);
            setTotal(res.data.total ?? 0);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { setPage(1); }, [tab]);
    useEffect(() => { fetchData(); }, [tab, page]);

    const countByStatus = STATUS_TABS.slice(1).reduce<Record<string, number>>((acc, s) => {
        acc[s] = orders.filter((o) => o.상태 === s).length;
        return acc;
    }, {});

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">주문 관리</h2>
                    <p className="text-gray-400 text-sm mt-1">발주·입고 현황 (Google Sheets 주문관리 시트)</p>
                </div>
                <button onClick={fetchData} disabled={loading} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition disabled:opacity-50">
                    <RefreshCw size={15} className={`text-gray-500 ${loading ? "animate-spin" : ""}`} />
                </button>
            </div>

            {/* 상태 카드 */}
            <div className="grid grid-cols-4 gap-4">
                {(["발주완료", "입고중", "입고완료", "반품"] as const).map((s) => (
                    <button
                        key={s}
                        onClick={() => setTab(s)}
                        className={`bg-white rounded-xl border border-gray-100 p-4 shadow-sm text-left transition hover:border-blue-200 ${tab === s ? "border-blue-400 ring-1 ring-blue-400" : ""}`}
                    >
                        <p className="text-xs text-gray-400 mb-1">{s}</p>
                        <p className="text-2xl font-bold text-gray-800">{countByStatus[s] ?? "-"}</p>
                    </button>
                ))}
            </div>

            {/* 탭 필터 */}
            <div className="flex gap-2 flex-wrap">
                {STATUS_TABS.map((t) => (
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
                <span className="flex items-center text-xs text-gray-400 ml-2">총 {total}건</span>
            </div>

            {/* 페이지네이션 (상단) */}
            {totalPages > 1 && (
                <div className="flex items-center gap-1">
                    <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1 || loading}
                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
                    >
                        <ChevronLeft size={14} />
                    </button>
                    {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map((p) => (
                        <button
                            key={p}
                            onClick={() => setPage(p)}
                            className={`min-w-[30px] h-[30px] rounded-lg text-xs font-medium transition ${
                                page === p ? "bg-blue-600 text-white" : "border border-gray-200 text-gray-600 hover:bg-gray-50"
                            }`}
                        >
                            {p}
                        </button>
                    ))}
                    <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages || loading}
                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
                    >
                        <ChevronRight size={14} />
                    </button>
                </div>
            )}

            {/* 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                    <tr className="bg-gray-50 text-gray-500 text-xs">
                        <th className="px-6 py-3 text-left">주문코드</th>
                        <th className="px-6 py-3 text-left">상품코드</th>
                        <th className="px-6 py-3 text-left">상품명</th>
                        <th className="px-6 py-3 text-right">발주수량</th>
                        <th className="px-6 py-3 text-left">발주일</th>
                        <th className="px-6 py-3 text-left">예정납기일</th>
                        <th className="px-6 py-3 text-left">상태</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                    {loading ? (
                        <tr>
                            <td colSpan={7} className="px-6 py-12 text-center">
                                <Loader2 size={24} className="animate-spin text-blue-500 mx-auto" />
                            </td>
                        </tr>
                    ) : orders.length === 0 ? (
                        <tr>
                            <td colSpan={7} className="px-6 py-12 text-center text-gray-400">
                                <Package size={32} className="mx-auto mb-2 text-gray-300" />
                                주문 데이터가 없습니다
                            </td>
                        </tr>
                    ) : (
                        orders.map((order) => (
                            <tr key={order.주문코드} className="hover:bg-gray-50 transition">
                                <td className="px-6 py-3 font-mono text-gray-400 text-xs">{order.주문코드}</td>
                                <td className="px-6 py-3 font-mono text-gray-600">{order.상품코드}</td>
                                <td className="px-6 py-3 text-gray-700">{order.상품명}</td>
                                <td className="px-6 py-3 text-right text-gray-700 font-medium">
                                    {order.발주수량.toLocaleString()}
                                </td>
                                <td className="px-6 py-3 text-gray-500">{order.발주일}</td>
                                <td className="px-6 py-3 text-gray-500">{order.예정납기일}</td>
                                <td className="px-6 py-3">
                                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLOR[order.상태] ?? "bg-gray-100 text-gray-500"}`}>
                                            {order.상태}
                                        </span>
                                </td>
                            </tr>
                        ))
                    )}
                    </tbody>
                </table>
            </div>

            {/* 페이지네이션 (하단) */}
            {totalPages > 1 && !loading && orders.length > 0 && (
                <div className="flex items-center justify-end gap-1">
                    <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
                    >
                        <ChevronLeft size={14} />
                    </button>
                    <span className="px-3 text-sm text-gray-600">{page} / {totalPages}</span>
                    <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
                    >
                        <ChevronRight size={14} />
                    </button>
                </div>
            )}
        </div>
    );
}
