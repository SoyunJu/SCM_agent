"use client";

import {useCallback, useState} from "react";
import {useQuery, useQueryClient} from "@tanstack/react-query";
import {autoResolveAnomaly, getAnomalies, resolveAnomaly} from "@/lib/api";
import {getDefaultPageSize} from "@/lib/utils";
import {AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Loader2, ShieldCheck, Tag, X, Zap,} from "lucide-react";

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

// 자동처리 유형 분류
const ORDER_TYPES    = ["LOW_STOCK", "SALES_SURGE"];
const DISCOUNT_TYPES = ["OVER_STOCK", "LONG_TERM_STOCK", "SALES_DROP"];

// 유형별 가이드
const RESOLVE_GUIDE: Record<string, { title: string; steps: string[] }> = {
    LOW_STOCK: {
        title: "재고 부족 — 자동 발주 처리",
        steps: [
            "일평균 판매량 기준으로 발주 수량을 자동 산출합니다.",
            "발주 제안이 즉시 승인 처리됩니다.",
            "기존 대기 중인 발주 제안이 있으면 처리되지 않습니다.",
        ],
    },
    SALES_SURGE: {
        title: "판매 급등 — 긴급 발주 처리",
        steps: [
            "급등 일평균 판매량 × 리드타임(14일) 기준으로 수량을 산출합니다.",
            "발주 제안이 즉시 승인 처리됩니다.",
            "기존 대기 중인 발주 제안이 있으면 처리되지 않습니다.",
        ],
    },
    OVER_STOCK: {
        title: "과재고 — 할인 판매 처리",
        steps: [
            "안전재고 초과분 수량을 최대 할인율로 판매 처리합니다.",
            "매입단가 기준 최대 할인율이 자동 산출됩니다.",
            "판매 이력이 구글 시트에 기록됩니다.",
        ],
    },
    LONG_TERM_STOCK: {
        title: "장기 재고 — 할인 판매 처리",
        steps: [
            "안전재고 초과분 수량을 최대 할인율로 판매 처리합니다.",
            "판매 이력이 없으면 기본 30% 할인율이 적용됩니다.",
            "판매 이력이 구글 시트에 기록됩니다.",
        ],
    },
    SALES_DROP: {
        title: "판매 급락 — 할인 판매 처리",
        steps: [
            "안전재고 초과분 수량을 최대 할인율로 판매 처리합니다.",
            "매입단가 기준 최대 할인율이 자동 산출됩니다.",
            "판매 이력이 구글 시트에 기록됩니다.",
        ],
    },
};

// ── 결과 표시 컴포넌트 ────────────────────────────────────────────────────────
function ActionResult({ result, anomalyType }: { result: any; anomalyType: string }) {
    if (!result) return null;

    if (ORDER_TYPES.includes(anomalyType)) {
        return (
            <div className="mt-3 p-3 bg-green-50 rounded-lg border border-green-100 text-xs space-y-1">
                <p className="font-semibold text-green-700">✅ 발주 자동 승인 완료</p>
                <p className="text-green-600">제안 ID: #{result.proposal_id}</p>
                <p className="text-green-600">발주 수량: {result.proposed_qty?.toLocaleString()}개</p>
                <p className="text-green-600">
                    단가: {result.unit_price > 0 ? `${result.unit_price?.toLocaleString()}원` : "단가 정보 없음"}
                </p>
                <p className="text-gray-500 mt-1">{result.reason}</p>
            </div>
        );
    }

    if (DISCOUNT_TYPES.includes(anomalyType)) {
        return (
            <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-100 text-xs space-y-1">
                <p className="font-semibold text-blue-700">✅ 할인 판매 처리 완료</p>
                <p className="text-blue-600">처리 수량: {result.over_qty?.toLocaleString()}개</p>
                <p className="text-blue-600">최대 할인율: {result.max_discount}%</p>
                {result.unit_sell > 0 && (
                    <p className="text-blue-600">
                        할인가: {Math.round(result.unit_sell * (1 - result.max_discount / 100)).toLocaleString()}원
                    </p>
                )}
                {!result.sheet_ok && (
                    <p className="text-amber-600 mt-1">
                        ⚠️ 시트 기록 실패 (해결 처리는 완료됨): {result.sheet_error}
                    </p>
                )}
            </div>
        );
    }

    return null;
}

// ── 해결 모달 ────────────────────────────────────────────────────────────────
function ResolveModal({
                          anomaly,
                          onClose,
                          onResolved,
                      }: {
    anomaly: any;
    onClose: () => void;
    onResolved: () => void;
}) {
    const [autoLoading,   setAutoLoading]   = useState(false);
    const [manualLoading, setManualLoading] = useState(false);
    const [actionResult,  setActionResult]  = useState<any>(null);
    const [errorMsg,      setErrorMsg]      = useState<string | null>(null);
    const [done,          setDone]          = useState(false);

    const typeKey  = (anomaly.anomaly_type as string)?.toUpperCase();
    const canAuto  = ORDER_TYPES.includes(typeKey) || DISCOUNT_TYPES.includes(typeKey);
    const guide    = RESOLVE_GUIDE[typeKey] ?? {
        title: "처리 방법",
        steps: ["해당 이상징후를 검토 후 적절한 조치를 취하세요."],
    };

    const autoIcon = ORDER_TYPES.includes(typeKey)
        ? <Zap size={14} />
        : <Tag size={14} />;
    const autoLabel = ORDER_TYPES.includes(typeKey)
        ? "발주 자동 처리"
        : "할인 판매 자동 처리";

    // 자동 처리
    const handleAutoResolve = async () => {
        setAutoLoading(true);
        setErrorMsg(null);
        try {
            const res = await autoResolveAnomaly(anomaly.id);
            setActionResult(res.data);
            setDone(true);
            onResolved();
        } catch (e: any) {
            const detail = e?.response?.data?.detail ?? "자동 처리에 실패했습니다.";
            setErrorMsg(detail);
        } finally {
            setAutoLoading(false);
        }
    };

    // 직접 해결
    const handleManualResolve = async () => {
        setManualLoading(true);
        setErrorMsg(null);
        try {
            await resolveAnomaly(anomaly.id);
            setDone(true);
            onResolved();
        } catch (e: any) {
            const detail = e?.response?.data?.detail ?? "처리에 실패했습니다.";
            setErrorMsg(detail);
        } finally {
            setManualLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
                {/* 헤더 */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                    <div className="flex items-center gap-2">
                        <ShieldCheck size={18} className="text-blue-600" />
                        <h3 className="font-semibold text-gray-800">이상징후 처리</h3>
                    </div>
                    <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
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
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_COLOR[typeKey] ?? "bg-gray-100 text-gray-500"}`}>
                            {SEVERITY_KOR[typeKey] ?? anomaly.severity}
                        </span>
                    </div>
                    <p className="text-xs text-gray-500">
                        유형: {ANOMALY_KOR[typeKey] ?? anomaly.anomaly_type}
                        {anomaly.current_stock != null && ` · 현재재고: ${anomaly.current_stock}개`}
                        {anomaly.days_until_stockout != null && anomaly.days_until_stockout < 999 &&
                            ` · 소진예상: ${anomaly.days_until_stockout.toFixed(1)}일`}
                    </p>
                </div>

                {/* 처리 가이드 */}
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

                    {/* 처리 결과 */}
                    {actionResult && <ActionResult result={actionResult} anomalyType={typeKey} />}

                    {/* 에러 메시지 */}
                    {errorMsg && (
                        <p className="mt-3 text-xs text-red-500 bg-red-50 px-3 py-2 rounded-lg">
                            ❌ {errorMsg}
                        </p>
                    )}
                </div>

                {/* 액션 버튼 */}
                <div className="px-6 py-4 border-t border-gray-100">
                    {done ? (
                        /* 처리 완료 후 닫기만 */
                        <button
                            onClick={onClose}
                            className="w-full px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition"
                        >
                            닫기
                        </button>
                    ) : (
                        <div className="flex gap-2 justify-end">
                            <button
                                onClick={onClose}
                                className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition"
                            >
                                취소
                            </button>
                            {/* 직접 해결 */}
                            <button
                                onClick={handleManualResolve}
                                disabled={manualLoading || autoLoading}
                                className="flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition disabled:opacity-50"
                            >
                                {manualLoading
                                    ? <Loader2 size={13} className="animate-spin" />
                                    : <CheckCircle2 size={13} />}
                                직접 해결
                            </button>
                            {/* 자동 처리 */}
                            {canAuto && (
                                <button
                                    onClick={handleAutoResolve}
                                    disabled={autoLoading || manualLoading}
                                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition disabled:opacity-50"
                                >
                                    {autoLoading
                                        ? <Loader2 size={13} className="animate-spin" />
                                        : autoIcon}
                                    {autoLabel}
                                </button>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function AnomaliesPage() {
    const qc = useQueryClient();

    const [page,           setPage]           = useState(1);
    const [pageSize]                          = useState(getDefaultPageSize);
    // "all" | "unresolved" | "resolved"
    const [resolvedFilter, setResolvedFilter] = useState<"all" | "unresolved" | "resolved">("unresolved");
    const [severityFilter, setSeverityFilter] = useState("");
    const [typeFilter,     setTypeFilter]     = useState("");
    const [selectedAnomaly, setSelectedAnomaly] = useState<any | null>(null);

    // resolvedFilter → is_resolved 변환
    const isResolved =
        resolvedFilter === "unresolved" ? false :
            resolvedFilter === "resolved"   ? true  : undefined;

    const queryKey = ["anomalies", page, pageSize, resolvedFilter, severityFilter, typeFilter];

    const { data, isLoading } = useQuery({
        queryKey,
        queryFn: () =>
            getAnomalies(
                isResolved,
                pageSize,
                page,
                severityFilter || undefined,
                typeFilter     || undefined,
            ).then(r => r.data),
        staleTime: 30_000,
        placeholderData: (prev) => prev,
    });

    const items      = data?.items      ?? [];
    const total      = data?.total      ?? 0;
    const totalPages = data?.total_pages ?? 1;

    const handleResolved = useCallback(() => {
        qc.invalidateQueries({ queryKey: ["anomalies"] });
    }, [qc]);

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
                {/* 해결 여부 드롭다운 */}
                <select
                    value={resolvedFilter}
                    onChange={(e) => { setResolvedFilter(e.target.value as any); setPage(1); }}
                    className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                >
                    <option value="unresolved">미해결</option>
                    <option value="resolved">해결됨</option>
                    <option value="all">전체</option>
                </select>

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

                {/* 필터 초기화 */}
                {(severityFilter || typeFilter || resolvedFilter !== "unresolved") && (
                    <button
                        onClick={() => { setSeverityFilter(""); setTypeFilter(""); setResolvedFilter("unresolved"); setPage(1); }}
                        className="px-2.5 py-1.5 rounded-lg text-xs text-gray-400 border border-gray-200 hover:bg-gray-50 transition"
                    >
                        초기화
                    </button>
                )}

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
                            const tk       = (a.anomaly_type as string)?.toUpperCase();
                            const typeLabel = a.anomaly_type_kor ?? ANOMALY_KOR[tk] ?? a.anomaly_type;
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
                                        {a.category || "—"}
                                    </td>
                                    <td className="px-5 py-3 whitespace-nowrap text-xs">
                                        <span className="text-gray-600">{typeLabel}</span>
                                        {(tk === "SALES_SURGE" || tk === "SALES_DROP") && a.change_rate != null && (
                                            <span className={`ml-1.5 font-semibold ${
                                                a.change_rate > 0 ? "text-red-500" : "text-blue-500"
                                            }`}>
                                                {a.change_rate > 0 ? `+${a.change_rate}%` : `${a.change_rate}%`}
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-5 py-3 text-right text-gray-600">
                                        {a.current_stock != null ? a.current_stock.toLocaleString() : "—"}
                                    </td>
                                    <td className="px-5 py-3 text-right text-gray-600 whitespace-nowrap">
                                        {days != null && days < 999 ? `${days.toFixed(1)}일` : "—"}
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

            {/* 모달 */}
            {selectedAnomaly && (
                <ResolveModal
                    anomaly={selectedAnomaly}
                    onClose={() => setSelectedAnomaly(null)}
                    onResolved={handleResolved}
                />
            )}
        </div>
    );
}