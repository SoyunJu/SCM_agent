"use client";

import { useEffect, useState } from "react";
import { getAnomalies } from "@/lib/api";
import { AnomalyLog } from "@/lib/types";

const SEVERITY_COLOR: Record<string, string> = {
    critical: "text-red-600 bg-red-50 border-red-100",
    high:     "text-orange-500 bg-orange-50 border-orange-100",
    medium:   "text-yellow-600 bg-yellow-50 border-yellow-100",
    low:      "text-green-600 bg-green-50 border-green-100",
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
    const [anomalies, setAnomalies] = useState<AnomalyLog[]>([]);
    const [filter, setFilter]       = useState<"unresolved" | "all">("unresolved");

    useEffect(() => {
        const isResolved = filter === "unresolved" ? false : undefined;
        getAnomalies(isResolved, 50).then((res) => setAnomalies(res.data.items));
    }, [filter]);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">이상 징후</h2>
                    <p className="text-gray-400 text-sm mt-1">감지된 재고·판매 이상 징후 목록</p>
                </div>
                <div className="flex gap-2">
                    {(["unresolved", "all"] as const).map((f) => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                                filter === f
                                    ? "bg-blue-600 text-white"
                                    : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                            }`}
                        >
                            {f === "unresolved" ? "미해결" : "전체"}
                        </button>
                    ))}
                </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                    <tr className="bg-gray-50 text-gray-500 text-xs">
                        <th className="px-6 py-3 text-left">상품코드</th>
                        <th className="px-6 py-3 text-left">상품명</th>
                        <th className="px-6 py-3 text-left">유형</th>
                        <th className="px-6 py-3 text-left">현재고</th>
                        <th className="px-6 py-3 text-left">소진예상</th>
                        <th className="px-6 py-3 text-left">심각도</th>
                        <th className="px-6 py-3 text-left">상태</th>
                        <th className="px-6 py-3 text-left">감지일시</th>
                    </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                    {anomalies.length === 0 ? (
                        <tr>
                            <td colSpan={8} className="px-6 py-10 text-center text-gray-400">
                                이상 징후 없음
                            </td>
                        </tr>
                    ) : (
                        anomalies.map((a) => (
                            <tr key={a.id} className="hover:bg-gray-50 transition">
                                <td className="px-6 py-3 font-mono text-gray-600">{a.product_code}</td>
                                <td className="px-6 py-3 text-gray-700">{a.product_name}</td>
                                <td className="px-6 py-3 text-gray-600">{ANOMALY_KOR[a.anomaly_type] ?? a.anomaly_type}</td>
                                <td className="px-6 py-3 text-gray-600">{a.current_stock ?? "-"}</td>
                                <td className="px-6 py-3 text-gray-600">
                                    {a.days_until_stockout && a.days_until_stockout < 999
                                        ? `${a.days_until_stockout}일`
                                        : "-"}
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
                                <td className="px-6 py-3 text-gray-400">{a.detected_at.slice(0, 16)}</td>
                            </tr>
                        ))
                    )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}