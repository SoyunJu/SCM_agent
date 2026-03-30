"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    Truck, Plus, Pencil, Trash2, CheckCircle, XCircle,
    PackageCheck, AlertTriangle, Loader2, RefreshCw, X,
} from "lucide-react";
import {
    getSuppliers, createSupplier, updateSupplier, deleteSupplier,
    getInspections, createInspection, completeInspection,
    mapProductSupplier,
} from "@/lib/api";
import { Supplier, ReceivingInspection } from "@/lib/types";

// ── 상수 ──────────────────────────────────────────────────────────────────────
const INSP_STATUS_LABEL: Record<string, string> = {
    PENDING: "검수 대기", PARTIAL: "부분 입고", COMPLETED: "입고 완료", RETURNED: "반품",
};
const INSP_STATUS_COLOR: Record<string, string> = {
    PENDING:   "bg-yellow-50 text-yellow-700",
    PARTIAL:   "bg-blue-50 text-blue-700",
    COMPLETED: "bg-green-50 text-green-700",
    RETURNED:  "bg-red-50 text-red-600",
};

// ── 공급업체 등록/수정 모달 ──────────────────────────────────────────────────
function SupplierModal({
                           initial, onClose, onSave,
                       }: {
    initial?: Supplier | null;
    onClose: () => void;
    onSave:  (data: object) => void;
}) {
    const [form, setForm] = useState({
        name:           initial?.name           ?? "",
        contact:        initial?.contact        ?? "",
        email:          initial?.email          ?? "",
        phone:          initial?.phone          ?? "",
        lead_time_days: String(initial?.lead_time_days ?? 14),
    });
    const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

    return (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-base font-semibold text-gray-800">
                        {initial ? "공급업체 수정" : "공급업체 등록"}
                    </h3>
                    <button onClick={onClose}><X size={16} className="text-gray-400" /></button>
                </div>

                {[
                    { label: "업체명 *", key: "name",           type: "text"   },
                    { label: "담당자",   key: "contact",        type: "text"   },
                    { label: "이메일",   key: "email",          type: "email"  },
                    { label: "연락처",   key: "phone",          type: "text"   },
                    { label: "리드타임(일)", key: "lead_time_days", type: "number" },
                ].map(({ label, key, type }) => (
                    <div key={key}>
                        <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
                        <input
                            type={type}
                            value={(form as any)[key]}
                            onChange={(e) => set(key, e.target.value)}
                            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                        />
                    </div>
                ))}

                <div className="flex gap-2 pt-2">
                    <button
                        onClick={() => onSave({
                            ...form,
                            lead_time_days: Number(form.lead_time_days) || 14,
                        })}
                        disabled={!form.name.trim()}
                        className="flex-1 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition"
                    >
                        저장
                    </button>
                    <button
                        onClick={onClose}
                        className="flex-1 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition"
                    >
                        취소
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── 입고 검수 완료 모달 ──────────────────────────────────────────────────────
function InspectionCompleteModal({
                                     inspection, onClose, onComplete,
                                 }: {
    inspection: ReceivingInspection;
    onClose:    () => void;
    onComplete: (data: object) => void;
}) {
    const [received, setReceived] = useState(String(inspection.ordered_qty));
    const [defect,   setDefect]   = useState("0");
    const [returnQ,  setReturnQ]  = useState("0");
    const [note,     setNote]     = useState("");

    const good = Math.max(0, Number(received) - Number(defect) - Number(returnQ));

    return (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-base font-semibold text-gray-800">입고 검수 완료</h3>
                    <button onClick={onClose}><X size={16} className="text-gray-400" /></button>
                </div>

                <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-600">
                    <p className="font-medium">{inspection.product_name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">발주수량: {inspection.ordered_qty}개</p>
                </div>

                {[
                    { label: "실입고 수량",  val: received, set: setReceived },
                    { label: "불량 수량",    val: defect,   set: setDefect   },
                    { label: "반품 수량",    val: returnQ,  set: setReturnQ  },
                ].map(({ label, val, set }) => (
                    <div key={label}>
                        <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
                        <input
                            type="number" min="0" value={val}
                            onChange={(e) => set(e.target.value)}
                            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                        />
                    </div>
                ))}

                <div className="bg-blue-50 rounded-lg p-3 text-sm">
                    <span className="text-blue-700 font-medium">양품 수량: {good}개</span>
                    <span className="text-blue-400 text-xs ml-2">(재고에 반영됩니다)</span>
                </div>

                <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">비고</label>
                    <textarea
                        value={note} onChange={(e) => setNote(e.target.value)}
                        rows={2}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
                    />
                </div>

                <div className="flex gap-2 pt-2">
                    <button
                        onClick={() => onComplete({
                            received_qty: Number(received),
                            defect_qty:   Number(defect),
                            return_qty:   Number(returnQ),
                            note:         note || null,
                        })}
                        className="flex-1 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition"
                    >
                        검수 완료
                    </button>
                    <button
                        onClick={onClose}
                        className="flex-1 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition"
                    >
                        취소
                    </button>
                </div>
            </div>
        </div>
    );
}

// ── 메인 페이지 ──────────────────────────────────────────────────────────────
export default function SuppliersPage() {
    const qc  = useQueryClient();
    const [tab, setTab]             = useState<"suppliers" | "inspections">("suppliers");
    const [supplierModal, setSupplierModal] = useState<"create" | Supplier | null>(null);
    const [completeTarget, setCompleteTarget] = useState<ReceivingInspection | null>(null);
    const [inspFilter, setInspFilter]         = useState("");

    // ── queries ──
    const { data: suppliers = [], isLoading: loadingS, refetch: refetchS } = useQuery({
        queryKey: ["suppliers"],
        queryFn:  () => getSuppliers().then((r) => r.data as Supplier[]),
    });

    const { data: inspData, isLoading: loadingI, refetch: refetchI } = useQuery({
        queryKey: ["inspections", inspFilter],
        queryFn:  () => getInspections(inspFilter || undefined).then((r) => r.data),
    });
    const inspections: ReceivingInspection[] = inspData?.items ?? [];

    // ── mutations ──
    const mutCreateS = useMutation({
        mutationFn: (d: object) => createSupplier(d as any),
        onSuccess:  () => { qc.invalidateQueries({ queryKey: ["suppliers"] }); setSupplierModal(null); },
    });
    const mutUpdateS = useMutation({
        mutationFn: ({ id, d }: { id: number; d: object }) => updateSupplier(id, d),
        onSuccess:  () => { qc.invalidateQueries({ queryKey: ["suppliers"] }); setSupplierModal(null); },
    });
    const mutDeleteS = useMutation({
        mutationFn: (id: number) => deleteSupplier(id),
        onSuccess:  () => qc.invalidateQueries({ queryKey: ["suppliers"] }),
    });
    const mutComplete = useMutation({
        mutationFn: ({ id, d }: { id: number; d: object }) => completeInspection(id, d as any),
        onSuccess:  () => { qc.invalidateQueries({ queryKey: ["inspections"] }); setCompleteTarget(null); },
    });

    const handleSaveSupplier = (data: object) => {
        if (supplierModal === "create") {
            mutCreateS.mutate(data);
        } else if (supplierModal && typeof supplierModal === "object") {
            mutUpdateS.mutate({ id: (supplierModal as Supplier).id, d: data });
        }
    };

    return (
        <div className="space-y-5">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">공급업체 관리</h2>
                    <p className="text-gray-400 text-sm mt-1">공급업체 등록 · 입고 검수 · 납기 추적</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => (tab === "suppliers" ? refetchS() : refetchI())}
                        className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition"
                    >
                        <RefreshCw size={15} className="text-gray-500" />
                    </button>
                    {tab === "suppliers" && (
                        <button
                            onClick={() => setSupplierModal("create")}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition"
                        >
                            <Plus size={14} /> 공급업체 등록
                        </button>
                    )}
                </div>
            </div>

            {/* 탭 */}
            <div className="flex gap-1 border-b border-gray-100">
                {[
                    { key: "suppliers",   label: "공급업체 목록" },
                    { key: "inspections", label: "입고 검수"     },
                ].map(({ key, label }) => (
                    <button
                        key={key}
                        onClick={() => setTab(key as any)}
                        className={`px-4 py-2.5 text-sm font-medium border-b-2 transition ${
                            tab === key
                                ? "border-blue-500 text-blue-600"
                                : "border-transparent text-gray-400 hover:text-gray-600"
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* ── 탭 1: 공급업체 목록 ── */}
            {tab === "suppliers" && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                    {loadingS ? (
                        <div className="py-20 flex justify-center">
                            <Loader2 className="animate-spin text-blue-500" />
                        </div>
                    ) : suppliers.length === 0 ? (
                        <div className="py-20 text-center text-gray-400 text-sm">
                            등록된 공급업체가 없습니다.
                        </div>
                    ) : (
                        <table className="w-full text-sm">
                            <thead>
                            <tr className="bg-gray-50 text-gray-500 text-xs">
                                <th className="px-5 py-3 text-left">업체명</th>
                                <th className="px-5 py-3 text-left">담당자</th>
                                <th className="px-5 py-3 text-left">연락처</th>
                                <th className="px-5 py-3 text-right">리드타임</th>
                                <th className="px-5 py-3 text-right">매핑 상품</th>
                                <th className="px-5 py-3 text-right">납기 준수율</th>
                                <th className="px-5 py-3 text-right">평균 지연</th>
                                <th className="px-5 py-3 text-center">상태</th>
                                <th className="px-5 py-3 text-center">액션</th>
                            </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                            {suppliers.map((s) => (
                                <tr key={s.id} className="hover:bg-gray-50 transition">
                                    <td className="px-5 py-3 font-medium text-gray-800">{s.name}</td>
                                    <td className="px-5 py-3 text-gray-500">{s.contact ?? "-"}</td>
                                    <td className="px-5 py-3 text-gray-500">{s.phone ?? "-"}</td>
                                    <td className="px-5 py-3 text-right text-gray-600">{s.lead_time_days}일</td>
                                    <td className="px-5 py-3 text-right text-gray-600">{s.mapped_products}개</td>
                                    <td className="px-5 py-3 text-right">
                                        {s.on_time_rate != null ? (
                                            <span className={`font-medium ${
                                                s.on_time_rate >= 90 ? "text-green-600"
                                                    : s.on_time_rate >= 70 ? "text-yellow-600"
                                                        : "text-red-500"
                                            }`}>
                                                {s.on_time_rate}%
                                            </span>
                                        ) : <span className="text-gray-300">-</span>}
                                    </td>
                                    <td className="px-5 py-3 text-right">
                                        {s.avg_delay_days != null ? (
                                            <span className={s.avg_delay_days > 0 ? "text-red-500" : "text-green-600"}>
                                                {s.avg_delay_days > 0 ? `+${s.avg_delay_days}일` : `${s.avg_delay_days}일`}
                                            </span>
                                        ) : <span className="text-gray-300">-</span>}
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                            s.is_active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-400"
                                        }`}>
                                            {s.is_active ? "활성" : "비활성"}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                        <div className="flex items-center justify-center gap-1">
                                            <button
                                                onClick={() => setSupplierModal(s)}
                                                className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition"
                                            >
                                                <Pencil size={13} />
                                            </button>
                                            <button
                                                onClick={() => {
                                                    if (confirm(`'${s.name}' 공급업체를 삭제(또는 비활성화)하시겠습니까?`))
                                                        mutDeleteS.mutate(s.id);
                                                }}
                                                className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition"
                                            >
                                                <Trash2 size={13} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}

            {/* ── 탭 2: 입고 검수 ── */}
            {tab === "inspections" && (
                <div className="space-y-4">
                    {/* 필터 */}
                    <div className="flex items-center gap-3">
                        <select
                            value={inspFilter}
                            onChange={(e) => setInspFilter(e.target.value)}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                        >
                            <option value="">전체 상태</option>
                            <option value="PENDING">검수 대기</option>
                            <option value="PARTIAL">부분 입고</option>
                            <option value="COMPLETED">입고 완료</option>
                            <option value="RETURNED">반품</option>
                        </select>
                        <span className="ml-auto text-xs text-gray-400">총 {inspData?.total ?? 0}건</span>
                    </div>

                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                        {loadingI ? (
                            <div className="py-20 flex justify-center">
                                <Loader2 className="animate-spin text-blue-500" />
                            </div>
                        ) : inspections.length === 0 ? (
                            <div className="py-20 text-center text-gray-400 text-sm">
                                검수 이력이 없습니다.
                            </div>
                        ) : (
                            <table className="w-full text-sm">
                                <thead>
                                <tr className="bg-gray-50 text-gray-500 text-xs">
                                    <th className="px-5 py-3 text-left">상품명</th>
                                    <th className="px-5 py-3 text-left">상품코드</th>
                                    <th className="px-5 py-3 text-right">발주수량</th>
                                    <th className="px-5 py-3 text-right">입고수량</th>
                                    <th className="px-5 py-3 text-right">불량</th>
                                    <th className="px-5 py-3 text-right">반품</th>
                                    <th className="px-5 py-3 text-right">양품</th>
                                    <th className="px-5 py-3 text-center">상태</th>
                                    <th className="px-5 py-3 text-left">검수자</th>
                                    <th className="px-5 py-3 text-center">액션</th>
                                </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                {inspections.map((insp) => (
                                    <tr key={insp.id} className="hover:bg-gray-50 transition">
                                        <td className="px-5 py-3 text-gray-700 max-w-[160px] truncate">
                                            {insp.product_name ?? "-"}
                                        </td>
                                        <td className="px-5 py-3 font-mono text-xs text-gray-500">
                                            {insp.product_code}
                                        </td>
                                        <td className="px-5 py-3 text-right text-gray-600">{insp.ordered_qty}</td>
                                        <td className="px-5 py-3 text-right text-gray-600">{insp.received_qty}</td>
                                        <td className="px-5 py-3 text-right">
                                            {insp.defect_qty > 0
                                                ? <span className="text-red-500">{insp.defect_qty}</span>
                                                : <span className="text-gray-300">-</span>}
                                        </td>
                                        <td className="px-5 py-3 text-right">
                                            {insp.return_qty > 0
                                                ? <span className="text-orange-500">{insp.return_qty}</span>
                                                : <span className="text-gray-300">-</span>}
                                        </td>
                                        <td className="px-5 py-3 text-right font-medium text-green-700">
                                            {insp.good_qty > 0 ? insp.good_qty : <span className="text-gray-300">-</span>}
                                        </td>
                                        <td className="px-5 py-3 text-center">
                                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                                INSP_STATUS_COLOR[insp.status] ?? "bg-gray-100 text-gray-500"
                                            }`}>
                                                {INSP_STATUS_LABEL[insp.status] ?? insp.status}
                                            </span>
                                        </td>
                                        <td className="px-5 py-3 text-xs text-gray-400">
                                            {insp.inspected_by ?? "-"}
                                        </td>
                                        <td className="px-5 py-3 text-center">
                                            {(insp.status === "PENDING" || insp.status === "PARTIAL") && (
                                                <button
                                                    onClick={() => setCompleteTarget(insp)}
                                                    className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-green-50 text-green-700 hover:bg-green-100 transition font-medium"
                                                >
                                                    <PackageCheck size={12} /> 검수 완료
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            )}

            {/* 공급업체 모달 */}
            {supplierModal && (
                <SupplierModal
                    initial={supplierModal === "create" ? null : supplierModal as Supplier}
                    onClose={() => setSupplierModal(null)}
                    onSave={handleSaveSupplier}
                />
            )}

            {/* 검수 완료 모달 */}
            {completeTarget && (
                <InspectionCompleteModal
                    inspection={completeTarget}
                    onClose={() => setCompleteTarget(null)}
                    onComplete={(d) => mutComplete.mutate({ id: completeTarget.id, d })}
                />
            )}
        </div>
    );
}