"use client";

import { useEffect, useState } from "react";
import {
    getOrders, getProposals, generateProposals,
    approveProposal, rejectProposal, updateProposal,
} from "@/lib/api";
import { OrderItem, OrderProposal } from "@/lib/types";
import {
    Package, Loader2, RefreshCw, ChevronLeft, ChevronRight,
    CheckCircle, XCircle, Pencil, Zap,
} from "lucide-react";

// --- 주문현황 탭 상수 ------------------------------------------------------------------------------------─
const STATUS_TABS = ["전체", "발주완료", "입고중", "입고완료", "반품"] as const;

const STATUS_COLOR: Record<string, string> = {
    발주완료: "text-blue-600 bg-blue-50",
    입고중:   "text-yellow-600 bg-yellow-50",
    입고완료: "text-green-600 bg-green-50",
    반품:     "text-red-500 bg-red-50",
};

const PROPOSAL_STATUS_COLOR: Record<string, string> = {
    pending:  "text-yellow-600 bg-yellow-50",
    approved: "text-green-600 bg-green-50",
    rejected: "text-red-500 bg-red-50",
};
const PROPOSAL_STATUS_LABEL: Record<string, string> = {
    pending: "대기", approved: "승인", rejected: "거절",
};

// --- 주문현황 탭 ---
function OrdersTab() {
    const [orders, setOrders]         = useState<OrderItem[]>([]);
    const [tab, setTab]               = useState<string>("전체");
    const [loading, setLoading]       = useState(false);
    const [page, setPage]             = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [total, setTotal]           = useState(0);
    const [isReadonly, setIsReadonly] = useState(false);
    const [summaryCounts, setSummaryCounts] = useState<Record<string, number>>({});

    // 마운트 시 각 상태별 총계 조회 (필터 변경과 무관하게 고정)
    useEffect(() => {
        const loadCounts = async () => {
            try {
                const statuses = ["발주완료", "입고중", "입고완료", "반품"] as const;
                const results = await Promise.all(
                    statuses.map((s) => getOrders({ status: s, page: 1, page_size: 1 }))
                );
                const counts: Record<string, number> = {};
                statuses.forEach((s, i) => { counts[s] = results[i].data.total ?? 0; });
                setSummaryCounts(counts);
            } catch {
                // 카드 숫자 없이 표시
            }
        };
        loadCounts();
    }, []);

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

    useEffect(() => {
        const role = localStorage.getItem("user_role") ?? "";
        setIsReadonly(role === "readonly");
        setPage(1); }, [tab]);


    useEffect(() => {
        const role = localStorage.getItem("user_role") ?? "";
        setIsReadonly(role === "readonly");
        fetchData(); }, [tab, page]);

    return (
        <div className="space-y-6">
            {/* 상태 카드 */}
            <div className="grid grid-cols-4 gap-4">
                {(["발주완료", "입고중", "입고완료", "반품"] as const).map((s) => (
                    <button
                        key={s}
                        onClick={() => setTab(s)}
                        className={`bg-white rounded-xl border border-gray-100 p-4 shadow-sm text-left transition hover:border-blue-200 ${tab === s ? "border-blue-400 ring-1 ring-blue-400" : ""}`}
                    >
                        <p className="text-xs text-gray-400 mb-1">{s}</p>
                        <p className="text-2xl font-bold text-gray-800">{summaryCounts[s] ?? "-"}</p>
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
                <button onClick={fetchData} disabled={loading} className="ml-auto p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50">
                    <RefreshCw size={15} className={`text-gray-500 ${loading ? "animate-spin" : ""}`} />
                </button>
            </div>

            {/* 페이지네이션 (상단) */}
            {totalPages > 1 && (
                <div className="flex items-center gap-1">
                    <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1 || loading} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
                        <ChevronLeft size={14} />
                    </button>
                    {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map((p) => (
                        <button key={p} onClick={() => setPage(p)}
                                className={`min-w-[30px] h-[30px] rounded-lg text-xs font-medium transition ${page === p ? "bg-blue-600 text-white" : "border border-gray-200 text-gray-600 hover:bg-gray-50"}`}
                        >{p}</button>
                    ))}
                    <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages || loading} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
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
                        <tr><td colSpan={7} className="px-6 py-12 text-center"><Loader2 size={24} className="animate-spin text-blue-500 mx-auto" /></td></tr>
                    ) : orders.length === 0 ? (
                        <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-400"><Package size={32} className="mx-auto mb-2 text-gray-300" />주문 데이터가 없습니다</td></tr>
                    ) : orders.map((order) => (
                        <tr key={order.주문코드} className="hover:bg-gray-50 transition">
                            <td className="px-6 py-3 font-mono text-gray-400 text-xs">{order.주문코드}</td>
                            <td className="px-6 py-3 font-mono text-gray-600">{order.상품코드}</td>
                            <td className="px-6 py-3 text-gray-700">{order.상품명}</td>
                            <td className="px-6 py-3 text-right text-gray-700 font-medium">{order.발주수량.toLocaleString()}</td>
                            <td className="px-6 py-3 text-gray-500">{order.발주일}</td>
                            <td className="px-6 py-3 text-gray-500">{order.예정납기일}</td>
                            <td className="px-6 py-3">
                                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLOR[order.상태] ?? "bg-gray-100 text-gray-500"}`}>{order.상태}</span>
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>

            {/* 페이지네이션 (하단) */}
            {totalPages > 1 && !loading && orders.length > 0 && (
                <div className="flex items-center justify-end gap-1">
                    <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"><ChevronLeft size={14} /></button>
                    <span className="px-3 text-sm text-gray-600">{page} / {totalPages}</span>
                    <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"><ChevronRight size={14} /></button>
                </div>
            )}
        </div>
    );
}

// --- 발주관리 탭 ---
function ProposalsTab() {
    const [proposals, setProposals]   = useState<OrderProposal[]>([]);
    const [total, setTotal]           = useState(0);
    const [statusFilter, setFilter]   = useState<string>("all");
    const [loading, setLoading]       = useState(false);
    const [generating, setGenerating] = useState(false);
    const [msg, setMsg]               = useState("");
    const [editId, setEditId]         = useState<number | null>(null);
    const [editQty, setEditQty]       = useState<string>("");
    const [editPrice, setEditPrice]   = useState<string>("");
    const [isReadonly, setIsReadonly] = useState(false);

    const fetchProposals = async () => {
        setLoading(true);
        try {
            const status = statusFilter === "all" ? undefined : statusFilter;
            const res = await getProposals(status, 50, 0);
            setProposals(res.data.items ?? []);
            setTotal(res.data.total ?? 0);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const role = localStorage.getItem("user_role") ?? "";
        setIsReadonly(role === "readonly");
        fetchProposals(); }, [statusFilter]);


    const handleGenerate = async () => {
        setGenerating(true);
        setMsg("");
        try {
            const res = await generateProposals();
            setMsg(res.data.message ?? "완료");
            fetchProposals();
        } catch (e: any) {
            setMsg(e?.response?.data?.detail ?? "생성 실패");
        } finally {
            setGenerating(false);
        }
    };

    const handleApprove = async (id: number) => {
        await approveProposal(id);
        fetchProposals();
    };

    const handleReject = async (id: number) => {
        await rejectProposal(id);
        fetchProposals();
    };

    const startEdit = (p: OrderProposal) => {
        setEditId(p.id);
        setEditQty(String(p.proposed_qty));
        setEditPrice(String(p.unit_price));
    };

    const saveEdit = async (id: number) => {
        await updateProposal(id, {
            proposed_qty: editQty ? parseInt(editQty, 10) : undefined,
            unit_price:   editPrice ? parseFloat(editPrice) : undefined,
        });
        setEditId(null);
        fetchProposals();
    };

    return (
        <div className="space-y-4">
            {/* 헤더 */}
            <div className="flex items-center gap-3 flex-wrap">
                {!isReadonly && (
                <button
                    onClick={handleGenerate}
                    disabled={generating}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
                >
                    {generating
                        ? <Loader2 size={14} className="animate-spin" />
                        : <Zap size={14} />}
                    발주 제안 생성
                </button>
                )}
                {["all", "pending", "approved", "rejected"].map((s) => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={`px-3 py-1.5 rounded-lg text-sm transition ${statusFilter === s ? "bg-gray-800 text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"}`}
                    >
                        {{ all: "전체", pending: "대기", approved: "승인", rejected: "거절" }[s]}
                    </button>
                ))}
                <span className="text-xs text-gray-400 ml-auto">총 {total}건</span>
                <button onClick={fetchProposals} disabled={loading} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50">
                    <RefreshCw size={15} className={`text-gray-500 ${loading ? "animate-spin" : ""}`} />
                </button>
            </div>

            {msg && (
                <div className="px-4 py-2 rounded-lg bg-blue-50 text-blue-700 text-sm">{msg}</div>
            )}

            {/* 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                    <tr className="bg-gray-50 text-gray-500 text-xs">
                        <th className="px-4 py-3 text-left">상품코드</th>
                        <th className="px-4 py-3 text-left">상품명</th>
                        <th className="px-4 py-3 text-left">카테고리</th>
                        <th className="px-4 py-3 text-right">발주수량</th>
                        <th className="px-4 py-3 text-right">단가</th>
                        <th className="px-4 py-3 text-left">사유</th>
                        <th className="px-4 py-3 text-left">상태</th>
                        <th className="px-4 py-3 text-left">생성일시</th>
                        <th className="px-4 py-3 text-center">액션</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                    {loading ? (
                        <tr><td colSpan={9} className="py-12 text-center"><Loader2 size={24} className="animate-spin text-blue-500 mx-auto" /></td></tr>
                    ) : proposals.length === 0 ? (
                        <tr><td colSpan={9} className="py-12 text-center text-gray-400"><Package size={32} className="mx-auto mb-2 text-gray-300" />발주 제안이 없습니다</td></tr>
                    ) : proposals.map((p) => (
                        <tr key={p.id} className="hover:bg-gray-50 transition">
                            <td className="px-4 py-3 font-mono text-gray-600 text-xs">{p.product_code}</td>
                            <td className="px-4 py-3 text-gray-700">{p.product_name ?? "-"}</td>
                            <td className="px-4 py-3 text-gray-500 text-xs">{p.category ?? "-"}</td>

                            {/* 수량 (인라인 수정) */}
                            <td className="px-4 py-3 text-right">
                                {editId === p.id ? (
                                    <input
                                        type="number" value={editQty}
                                        onChange={(e) => setEditQty(e.target.value)}
                                        className="w-20 text-right border border-blue-300 rounded px-1 py-0.5 text-sm"
                                    />
                                ) : (
                                    <span className="font-medium text-gray-700">{p.proposed_qty.toLocaleString()}</span>
                                )}
                            </td>

                            {/* 단가 (인라인 수정) */}
                            <td className="px-4 py-3 text-right">
                                {editId === p.id ? (
                                    <input
                                        type="number" value={editPrice}
                                        onChange={(e) => setEditPrice(e.target.value)}
                                        className="w-24 text-right border border-blue-300 rounded px-1 py-0.5 text-sm"
                                    />
                                ) : (
                                    <span className="text-gray-600">{p.unit_price > 0 ? p.unit_price.toLocaleString() + "원" : "-"}</span>
                                )}
                            </td>

                            <td className="px-4 py-3 text-gray-400 text-xs max-w-[180px] truncate" title={p.reason ?? ""}>{p.reason ?? "-"}</td>

                            <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PROPOSAL_STATUS_COLOR[p.status] ?? "bg-gray-100 text-gray-500"}`}>
                                        {PROPOSAL_STATUS_LABEL[p.status] ?? p.status}
                                    </span>
                            </td>

                            <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{p.created_at.slice(0, 16).replace("T", " ")}</td>

                            {/* 액션 버튼 */}
                            <td className="px-4 py-3 text-center whitespace-nowrap">
                                {editId === p.id ? (
                                    <div className="flex gap-1 justify-center">
                                        <button onClick={() => saveEdit(p.id)} className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700">저장</button>
                                        <button onClick={() => setEditId(null)} className="px-2 py-1 border border-gray-200 rounded text-xs hover:bg-gray-50">취소</button>
                                    </div>
                                ) : p.status === "pending" && !isReadonly ? (
                                    <div className="flex gap-1 justify-center">
                                        <button onClick={() => startEdit(p)} title="수정" className="p-1 rounded hover:bg-gray-100 text-gray-500"><Pencil size={14} /></button>
                                        <button onClick={() => handleApprove(p.id)} title="승인" className="p-1 rounded hover:bg-green-50 text-green-600"><CheckCircle size={14} /></button>
                                        <button onClick={() => handleReject(p.id)} title="거절" className="p-1 rounded hover:bg-red-50 text-red-500"><XCircle size={14} /></button>
                                    </div>
                                ) : (
                                    <span className="text-gray-300 text-xs">{p.approved_by ?? "-"}</span>
                                )}
                            </td>
                        </tr>
                    ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// --- 메인 페이지 ---
export default function OrdersPage() {
    const [mainTab, setMainTab] = useState<"orders" | "proposals">("orders");

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">주문 관리</h2>
                    <p className="text-gray-400 text-sm mt-1">발주·입고 현황 및 자동 발주 관리</p>
                </div>
            </div>

            {/* 메인 탭 */}
            <div className="flex gap-2 border-b border-gray-100 pb-0">
                {([
                    { key: "orders",    label: "주문현황" },
                    { key: "proposals", label: "발주관리" },
                ] as const).map(({ key, label }) => (
                    <button
                        key={key}
                        onClick={() => setMainTab(key)}
                        className={`px-5 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${
                            mainTab === key
                                ? "border-blue-600 text-blue-600"
                                : "border-transparent text-gray-500 hover:text-gray-700"
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {mainTab === "orders" ? <OrdersTab /> : <ProposalsTab />}
        </div>
    );
}
