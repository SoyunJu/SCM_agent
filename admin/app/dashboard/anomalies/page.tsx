"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAnomalies, resolveAnomaly } from "@/lib/api";
import { AnomalyLog } from "@/lib/types";
import { CheckCircle, Search } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Pagination } from "@/components/ui/Pagination";

const ANOMALY_KOR: Record<string, string> = {
    low_stock: "재고 부족", over_stock: "재고 과잉",
    sales_surge: "판매 급등", sales_drop: "판매 급락",
    long_term_stock: "장기 재고",
};

export default function AnomaliesPage() {
    const qc = useQueryClient();

    const [statusFilter, setStatus]     = useState<"unresolved" | "resolved" | "all">("unresolved");
    const [severityFilter, setSeverity] = useState("");
    const [typeFilter, setType]         = useState("");
    const [search, setSearch]           = useState("");
    const [page, setPage]               = useState(1);
    const [pageSize, setPageSize]       = useState(50);

    const isResolved =
        statusFilter === "unresolved" ? false :
        statusFilter === "resolved"   ? true  : undefined;

    const { data, isLoading } = useQuery({
        queryKey: ["anomalies", statusFilter, page, pageSize],
        queryFn:  () => getAnomalies(isResolved, pageSize, page, pageSize).then((r) => r.data as {
            items: AnomalyLog[];
            total: number;
            total_pages: number;
            page: number;
        }),
    });

    const anomalies  = data?.items ?? [];
    const total      = data?.total ?? 0;
    const totalPages = data?.total_pages ?? 1;

    // 클라이언트 사이드 필터 (심각도, 유형, 검색)
    const filtered = useMemo(() => {
        let d = anomalies;
        if (severityFilter) d = d.filter((a) => a.severity === severityFilter);
        if (typeFilter)     d = d.filter((a) => a.anomaly_type === typeFilter);
        if (search)         d = d.filter((a) =>
            a.product_name.includes(search) || a.product_code.includes(search)
        );
        return d;
    }, [anomalies, severityFilter, typeFilter, search]);

    const resolveMutation = useMutation({
        mutationFn: (id: number) => resolveAnomaly(id),
        onSuccess:  () => qc.invalidateQueries({ queryKey: ["anomalies"] }),
    });

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold text-gray-800">이상 징후</h2>
                <p className="text-gray-400 text-sm mt-1">감지된 재고/판매 이상 징후 관리</p>
            </div>

            {/* 필터 바 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3">
                <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 flex-1 min-w-48">
                    <Search size={14} className="text-gray-400" />
                    <input
                        type="text"
                        placeholder="상품명 / 상품코드 검색"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="text-sm outline-none w-full"
                    />
                </div>

                <select
                    value={statusFilter}
                    onChange={(e) => { setStatus(e.target.value as typeof statusFilter); setPage(1); }}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-600 outline-none"
                >
                    <option value="unresolved">미해결</option>
                    <option value="resolved">해결됨</option>
                    <option value="all">전체</option>
                </select>

                <select
                    value={severityFilter}
                    onChange={(e) => setSeverity(e.target.value)}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-600 outline-none"
                >
                    <option value="">전체 심각도</option>
                    <option value="critical">긴급</option>
                    <option value="high">높음</option>
                    <option value="medium">보통</option>
                    <option value="check">확인</option>
                    <option value="low">낮음</option>
                </select>

                <select
                    value={typeFilter}
                    onChange={(e) => setType(e.target.value)}
                    className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-600 outline-none"
                >
                    <option value="">전체 유형</option>
                    <option value="low_stock">재고 부족</option>
                    <option value="over_stock">재고 과잉</option>
                    <option value="sales_surge">판매 급등</option>
                    <option value="sales_drop">판매 급락</option>
                    <option value="long_term_stock">장기 재고</option>
                </select>
            </div>

            {/* 페이지네이션 (상단) + 총 건수 */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">총 {total}건</span>
                    <select
                        value={pageSize}
                        onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                        className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none"
                    >
                        {[10, 25, 50, 100].map((n) => (
                            <option key={n} value={n}>{n}건</option>
                        ))}
                    </select>
                </div>
                <Pagination page={page} totalPages={totalPages} onPageChange={setPage} disabled={isLoading} />
            </div>

            {/* 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                {isLoading ? (
                    <LoadingSpinner />
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                        <tr className="bg-gray-50 text-gray-500 text-xs">
                            <th className="px-6 py-3 text-left">상품코드</th>
                            <th className="px-6 py-3 text-left">상품명</th>
                            <th className="px-6 py-3 text-left">카테고리</th>
                            <th className="px-6 py-3 text-left">유형</th>
                            <th className="px-6 py-3 text-left">현재고</th>
                            <th className="px-6 py-3 text-left">소진예상</th>
                            <th className="px-6 py-3 text-left">심각도</th>
                            <th className="px-6 py-3 text-left">상태</th>
                            <th className="px-6 py-3 text-left">감지일시</th>
                            <th className="px-6 py-3 text-left">처리</th>
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                        {filtered.length === 0 ? (
                            <tr>
                                <td colSpan={10} className="px-6 py-10 text-center text-gray-400">이상 징후 없음</td>
                            </tr>
                        ) : (
                            filtered.map((a) => (
                                <tr key={a.id} className="hover:bg-gray-50 transition">
                                    <td className="px-6 py-3 font-mono text-gray-600">{a.product_code}</td>
                                    <td className="px-6 py-3 text-gray-700">{a.product_name}</td>
                                    <td className="px-6 py-3 text-gray-500">{a.category || "-"}</td>
                                    <td className="px-6 py-3 text-gray-600">{ANOMALY_KOR[a.anomaly_type] ?? a.anomaly_type}</td>
                                    <td className="px-6 py-3 text-gray-600">{a.current_stock ?? "-"}</td>
                                    <td className="px-6 py-3 text-gray-600">
                                        {a.days_until_stockout && a.days_until_stockout < 999 ? `${a.days_until_stockout}일` : "-"}
                                    </td>
                                    <td className="px-6 py-3">
                                        <StatusBadge value={a.severity} variant="severity" />
                                    </td>
                                    <td className="px-6 py-3">
                                        <span className={`text-xs font-medium ${a.is_resolved ? "text-green-600" : "text-red-500"}`}>
                                            {a.is_resolved ? "해결" : "미해결"}
                                        </span>
                                    </td>
                                    <td className="px-6 py-3 text-gray-400 text-xs">{a.detected_at.slice(0, 16)}</td>
                                    <td className="px-6 py-3">
                                        {!a.is_resolved && (
                                            <button
                                                onClick={() => resolveMutation.mutate(a.id)}
                                                disabled={resolveMutation.isPending}
                                                className="flex items-center gap-1 text-xs text-green-600 hover:text-green-700 font-medium disabled:opacity-50"
                                            >
                                                <CheckCircle size={13} />
                                                {resolveMutation.isPending ? "처리 중..." : "해결"}
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))
                        )}
                        </tbody>
                    </table>
                )}
            </div>

            {/* 페이지네이션 (하단) */}
            <div className="flex justify-end">
                <Pagination page={page} totalPages={totalPages} onPageChange={setPage} disabled={isLoading} />
            </div>
        </div>
    );
}
