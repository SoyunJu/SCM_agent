"use client";

import { useEffect, useState } from "react";
import { getAnomalies, resolveAnomaly } from "@/lib/api";
import { AnomalyLog } from "@/lib/types";
import { CheckCircle, Search, Loader2 } from "lucide-react";

const SEVERITY_COLOR: Record<string, string> = {
    critical: "text-red-600 bg-red-50 border-red-200",
    high:     "text-orange-500 bg-orange-50 border-orange-200",
    medium:   "text-yellow-600 bg-yellow-50 border-yellow-200",
    low:      "text-green-600 bg-green-50 border-green-200",
};
const SEVERITY_KOR: Record<string, string> = {
    critical: "긴급", high: "높음", medium: "보통", low: "낮음",
};
const ANOMALY_KOR: Record<string, string> = {
    low_stock: "재고 부족", over_stock: "재고 과잉",
    sales_surge: "판매 급등", sales_drop: "판매 급락",
    long_term_stock: "장기 재고",
};

export default function AnomaliesPage() {
    const [anomalies, setAnomalies]     = useState<AnomalyLog[]>([]);
    const [filtered, setFiltered]       = useState<AnomalyLog[]>([]);
    const [statusFilter, setStatus]     = useState<"unresolved" | "resolved" | "all">("unresolved");
    const [severityFilter, setSeverity] = useState("");
    const [typeFilter, setType]         = useState("");
    const [search, setSearch]           = useState("");
    const [resolving, setResolving]     = useState<number | null>(null);
    const [loading, setLoading]         = useState(false);

    const fetchData = () => {
        const isResolved =
            statusFilter === "unresolved" ? false :
                statusFilter === "resolved"   ? true  : undefined;
        setLoading(true);
        getAnomalies(isResolved, 100)
            .then((res) => setAnomalies(res.data.items))
            .finally(() => setLoading(false));
    };

    useEffect(() => { fetchData(); }, [statusFilter]);

    useEffect(() => {
        let data = [...anomalies];
        if (severityFilter) data = data.filter((a) => a.severity === severityFilter);
        if (typeFilter)     data = data.filter((a) => a.anomaly_type === typeFilter);
        if (search)         data = data.filter((a) =>
            a.product_name.includes(search) || a.product_code.includes(search)
        );
        setFiltered(data);
    }, [anomalies, severityFilter, typeFilter, search]);

    const handleResolve = async (id: number) => {
        setResolving(id);
        try {
            await resolveAnomaly(id);
            fetchData();
        } finally {
            setResolving(null);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-2xl font-bold text-gray-800">이상 징후</h2>
                <p className="text-gray-400 text-sm mt-1">감지된 재고·판매 이상 징후 관리</p>
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

                {/* 상태 필터 — 이슈 8: 해결 옵션 추가 */}
                <select
                    value={statusFilter}
                    onChange={(e) => setStatus(e.target.value as "unresolved" | "resolved" | "all")}
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

                <span className="flex items-center text-sm text-gray-400">총 {filtered.length}건</span>
            </div>

            {/* 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                {loading ? (
                    <div className="flex items-center justify-center py-16">
                        <Loader2 size={28} className="animate-spin text-blue-500" />
                    </div>
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
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${SEVERITY_COLOR[a.severity]}`}>
                                            {SEVERITY_KOR[a.severity]}
                                        </span>
                                    </td>
                                    <td className="px-6 py-3">
                                        <span className={`text-xs font-medium ${a.is_resolved ? "text-green-600" : "text-red-500"}`}>
                                            {a.is_resolved ? "✅ 해결" : "🔴 미해결"}
                                        </span>
                                    </td>
                                    <td className="px-6 py-3 text-gray-400 text-xs">{a.detected_at.slice(0, 16)}</td>
                                    <td className="px-6 py-3">
                                        {!a.is_resolved && (
                                            <button
                                                onClick={() => handleResolve(a.id)}
                                                disabled={resolving === a.id}
                                                className="flex items-center gap-1 text-xs text-green-600 hover:text-green-700 font-medium disabled:opacity-50"
                                            >
                                                <CheckCircle size={13} />
                                                {resolving === a.id ? "처리 중..." : "해결"}
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
        </div>
    );
}
