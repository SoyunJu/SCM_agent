"use client";

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getAnomalies, resolveAnomaly } from "@/lib/api";
import { getDefaultPageSize } from "@/lib/utils";
import {
    AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight,
    Loader2, X, ShieldCheck,
} from "lucide-react";

// ── 상수 ─────────────────────────────────────────────────────────────────────
const SEVERITY_COLOR: Record<string, string> = {
    CRITICAL: "bg-red-100 text-red-700",
    HIGH:     "bg-orange-100 text-orange-600",
    MEDIUM:   "bg-yellow-100 text-yellow-700",
    LOW:      "bg-green-100 text-green-700",
    CHECK:    "bg-blue-100 text-blue-600",
};
const ANOMALY_KOR: Record<string, string> = {
    LOW_STOCK:       "재고 부족",
    OVER_STOCK:      "과재고",
    SALES_SURGE:     "판매 급등",
    SALES_DROP:      "판매 급락",
    LONG_TERM_STOCK: "장기 재고",
};
const SEVERITY_KOR: Record<string, string> = {
    CRITICAL: "긴급", HIGH: "높음", MEDIUM: "보통", LOW: "낮음", CHECK: "확인",
};

// 유형별 처리 방법 제안
const RESOLVE_GUIDE: Record<string, { title: string; steps: string[] }> = {
    LOW_STOCK: {
        title: "재고 부족 처리 방법",
        steps: [
            "발주 관리 탭에서 발주 제안 생성을 통해 자동 발주 수량을 산출하세요.",
            "긴급 발주가 필요한 경우 공급업체에 즉시 연락하세요.",
            "리드타임 동안 판매 가능 수량을 조정하는 것을 검토하세요.",
        ],
    },
    OVER_STOCK: {
        title: "과재고 처리 방법",
        steps: [
            "프로모션 또는 할인 행사를 통해 재고를 소진하세요.",
            "다른 판매 채널(온라인/오프라인)로 재고를 분산 이동하세요.",
            "향후 발주 수량을 줄이도록 안전재고 기준을 재검토하세요.",
        ],
    },
    LONG_TERM_STOCK: {
        title: "장기 재고 처리 방법",
        steps: [
            "판매 가능 여부를 확인하고 가격을 인하하여 판매를 유도하세요.",
            "공급업체 반품이 가능한지 확인하세요.",
            "폐기 또는 기부 처리가 필요한 경우 승인 절차를 진행하세요.",
        ],
    },
    SALES_SURGE: {
        title: "판매 급등 처리 방법",
        steps: [
            "현재 재고 수준이 수요를 충족할 수 있는지 즉시 확인하세요.",
            "재고 부족이 예상되면 긴급 발주를 진행하세요.",
            "급등 원인(이벤트, 시즌 등)을 파악하여 향후 수요를 예측하세요.",
        ],
    },
    SALES_DROP: {
        title: "판매 급락 처리 방법",
        steps: [
            "판매 채널 오류나 상품 노출 이상 여부를 먼저 확인하세요.",
            "경쟁사 가격 변동 또는 대체 상품 등장 여부를 조사하세요.",
            "마케팅 프로모션 또는 가격 조정을 통한 수요 회복을 검토하세요.",
        ],
    },
};

// ── 해결 확인 모달 ────────────────────────────────────────────────────────────
function ResolveModal({
                          anomaly,
                          onConfirm,
                          onCancel,
                          resolving,
                      }: {
    anomaly: any;
    onConfirm: () => void;
    onCancel: () => void;
    resolving: boolean;
}) {
    const typeKey = (anomaly.anomaly_type as string)?.toUpperCase();
    const guide   = RESOLVE_GUIDE[typeKey] ?? {
        title: "처리 방법",
        steps: ["해당 이상징후를 검토 후 적절한 조치를 취하세요."],
    };

    return (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
                {/* 모달 헤더 */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                    <div className="flex items-center gap-2">
                        <ShieldCheck size={18} className="text-blue-600" />
                        <h3 className="font-semibold text-gray-800">이상징후 해결 처리</h3>
                    </div>
                    <button onClick={onCancel} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
                        <X size={16} />
                    </button>
                </div>

                {/* 이상징후 요약 */}
                <div className="px-6 py-4 bg-gray-50 border-b border-gray-100">
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-700">
                            {anomaly.product_name}
                            <span className="text-gray-400 ml-1 font-normal font-mono text-xs">
                                ({anomaly.product_code})
                            </span>
                        </span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_COLOR[anomaly.severity?.toUpperCase()] ?? "bg-gray-100 text-gray-500"}`}>
                            {SEVERITY_KOR[anomaly.severity?.toUpperCase()] ?? anomaly.severity}
                        </span>
                    </div>
                    <p className="text-xs text-gray-500">
                        유형: {ANOMALY_KOR[typeKey] ?? anomaly.anomaly_type}
                        {anomaly.current_stock != null && ` · 현재재고: ${anomaly.current_stock}개`}
                        {anomaly.days_until_stockout != null && anomaly.days_until_stockout < 999 &&
                            ` · 소진예상: ${anomaly.days_until_stockout.toFixed(1)}일`}
                    </p>
                </div>

                {/* 처리 방법 제안 */}
                <div className="px-6 py-4">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                        {guide.title}
                    </p>
                    <ol className="space-y-2">
                        {guide.steps.map((step, i) => (
                            <li key={i} className="flex gap-2.5 text-sm text-gray-700">
                                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-blue-100 text-blue-600 text-xs font-bold flex items-center justify-center mt-0.5">
                                    {i + 1}
                                </span>
                                {step}
                            </li>
                        ))}
                    </ol>
                </div>

                {/* 액션 버튼 */}
                <div className="px-6 py-4 border-t border-gray-100 flex gap-2 justify-end">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition"
                    >
                        취소
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={resolving}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50"
                    >
                        {resolving
                            ? <Loader2 size={13} className="animate-spin" />
                            : <CheckCircle2 size={13} />}
                        해결 완료 처리
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function AnomaliesPage() {
    const qc = useQueryClient();

    const [page,     setPage]     = useState(1);
    const [pageSize]              = useState(getDefaultPageSize);
    const [showResolved, setShowResolved] = useState(false);
    const [severityFilter, setSeverityFilter] = useState("");
    const [typeFilter,     setTypeFilter]     = useState("");

    // 해결 모달
    const [selectedAnomaly, setSelectedAnomaly] = useState<any | null>(null);
    const [resolving, setResolving] = useState(false);

    const queryKey = ["anomalies", page, pageSize, showResolved, severityFilter, typeFilter];

    const { data, isLoading, refetch } = useQuery({
        queryKey,
        queryFn: () => {
            const params = new URLSearchParams({
                page:      String(page),
                page_size: String(pageSize),
            });
            if (!showResolved) params.append("is_resolved", "false");
            if (severityFilter) params.append("severity", severityFilter);
            if (typeFilter)     params.append("anomaly_type", typeFilter);
            return getAnomalies(
                showResolved ? undefined : false,
                pageSize,
                page,
            ).then(r => r.data);
        },
        staleTime: 30_000,
        placeholderData: (prev) => prev,
    });

    const items      = data?.items      ?? [];
    const total      = data?.total      ?? 0;
    const totalPages = data?.total_pages ?? 1;

    const handleResolveConfirm = useCallback(async () => {
        if (!selectedAnomaly) return;
        setResolving(true);
        try {
            await resolveAnomaly(selectedAnomaly.id);
            setSelectedAnomaly(null);
            qc.invalidateQueries({ queryKey: ["anomalies"] });
        } finally {
            setResolving(false);
        }
    }, [selectedAnomaly, qc]);

    return (
        <div className="space-y-5">

            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">이상 징후</h2>
                    <p className="text-gray-400 text-sm mt-1">재고·판매 이상 감지 목록 및 처리 관리</p>
                </div>
                <span className="text-sm text-gray-500">총 <strong>{total}</strong>건</span>
            </div>

            {/* 필터 바 */}
            <div className="flex flex-wrap gap-2 items-center bg-white px-4 py-3 rounded-xl border border-gray-100 shadow-sm">
                {/* 해결 여부 토글 */}
                <button
                    onClick={() => { setShowResolved(v => !v); setPage(1); }}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                        showResolved
                            ? "bg-gray-800 text-white"
                            : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                    }`}
                >
                    {showResolved ? "전체" : "미해결만"}
                </button>

                {/* 심각도 필터 */}
                <select
                    value={severityFilter}
                    onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
                    className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                >
                    <option value="">전체 심각도</option>
                    {["CRITICAL", "HIGH", "MEDIUM", "LOW", "CHECK"].map(s => (
                        <option key={s} value={s}>{SEVERITY_KOR[s]}</option>
                    ))}
                </select>

                {/* 유형 필터 */}
                <select
                    value={typeFilter}
                    onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
                    className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                >
                    <option value="">전체 유형</option>
                    {Object.entries(ANOMALY_KOR).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                    ))}
                </select>

                {/* 페이지 크기 */}
                <select
                    value={pageSize}
                    onChange={() => setPage(1)}
                    className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none ml-auto"
                >
                    {[25, 50, 100].map(n => <option key={n} value={n}>{n}건</option>)}
                </select>
            </div>

            {/* 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
                {isLoading ? (
                    <div className="flex justify-center py-16">
                        <Loader2 size={28} className="animate-spin text-blue-500" />
                    </div>
                ) : items.length === 0 ? (
                    <div className="py-16 text-center">
                        <AlertTriangle size={32} className="mx-auto text-gray-200 mb-3" />
                        <p className="text-gray-400 text-sm">이상 징후가 없습니다.</p>
                    </div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                        <tr className="bg-gray-50 text-gray-500 text-xs">
                            <th className="px-5 py-3 text-left whitespace-nowrap">감지일시</th>
                            <th className="px-5 py-3 text-left whitespace-nowrap">상품코드</th>
                            <th className="px-5 py-3 text-left whitespace-nowrap">상품명</th>
                            <th className="px-5 py-3 text-left whitespace-nowrap">카테고리</th>
                            <th className="px-5 py-3 text-left whitespace-nowrap">유형</th>
                            <th className="px-5 py-3 text-right whitespace-nowrap">현재재고</th>
                            <th className="px-5 py-3 text-right whitespace-nowrap">소진예상</th>
                            <th className="px-5 py-3 text-center whitespace-nowrap">심각도</th>
                            <th className="px-5 py-3 text-center whitespace-nowrap">상태</th>
                            <th className="px-5 py-3 text-center whitespace-nowrap">처리</th>
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                        {items.map((a: any) => {
                            const typeKey  = (a.anomaly_type_kor ? null : a.anomaly_type?.toUpperCase());
                            const typeLabel = a.anomaly_type_kor ?? ANOMALY_KOR[a.anomaly_type?.toUpperCase()] ?? a.anomaly_type;
                            const sevKey   = a.severity?.toUpperCase();
                            const sevLabel = a.severity_kor ?? SEVERITY_KOR[sevKey] ?? a.severity;
                            const days     = a.days_until_stockout;

                            return (
                                <tr key={a.id} className={`hover:bg-gray-50 transition ${a.is_resolved ? "opacity-50" : ""}`}>
                                    <td className="px-5 py-3 text-gray-400 whitespace-nowrap text-xs">
                                        {(a.detected_at ?? "").slice(0, 16)}
                                    </td>
                                    <td className="px-5 py-3 font-mono text-gray-600 text-xs whitespace-nowrap">
                                        {a.product_code}
                                    </td>
                                    <td className="px-5 py-3 text-gray-700 max-w-[160px] truncate">
                                        {a.product_name}
                                    </td>
                                    <td className="px-5 py-3 text-gray-500 text-xs">
                                        {a.category || "-"}
                                    </td>
                                    <td className="px-5 py-3 text-gray-600 whitespace-nowrap text-xs">
                                        {typeLabel}
                                    </td>
                                    <td className="px-5 py-3 text-right text-gray-600">
                                        {a.current_stock != null ? a.current_stock.toLocaleString() : "-"}
                                    </td>
                                    <td className="px-5 py-3 text-right text-gray-600 whitespace-nowrap">
                                        {days != null && days < 999
                                            ? `${days.toFixed(1)}일`
                                            : "-"}
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_COLOR[sevKey] ?? "bg-gray-100 text-gray-500"}`}>
                                            {sevLabel}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                        {a.is_resolved ? (
                                            <span className="flex items-center justify-center gap-1 text-xs text-green-600">
                                                <CheckCircle2 size={13} /> 해결됨
                                            </span>
                                        ) : (
                                            <span className="text-xs text-gray-400">미해결</span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                        {!a.is_resolved && (
                                            <button
                                                onClick={() => setSelectedAnomaly(a)}
                                                className="px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 transition whitespace-nowrap"
                                            >
                                                처리
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                        </tbody>
                    </table>
                )}
            </div>

            {/* 페이징 */}
            {totalPages > 1 && (
                <div className="flex items-center justify-end gap-1">
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1 || isLoading}
                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
                    >
                        <ChevronLeft size={14} />
                    </button>
                    <span className="px-3 text-sm text-gray-600">{page} / {totalPages}</span>
                    <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages || isLoading}
                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
                    >
                        <ChevronRight size={14} />
                    </button>
                </div>
            )}

            {/* 해결 확인 모달 */}
            {selectedAnomaly && (
                <ResolveModal
                    anomaly={selectedAnomaly}
                    onConfirm={handleResolveConfirm}
                    onCancel={() => setSelectedAnomaly(null)}
                    resolving={resolving}
                />
            )}
        </div>
    );
}