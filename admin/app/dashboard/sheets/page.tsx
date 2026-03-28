"use client";

import { useEffect, useRef, useState } from "react";
import { getSheetsMaster, getSheetsSales, getSheetsStock, updateProductStatus, updateProduct, uploadExcel } from "@/lib/api";
import { getDefaultPageSize } from "@/lib/utils";
import { RefreshCw, Loader2, ArrowUp, ChevronLeft, ChevronRight, Upload, Pencil, X, Check } from "lucide-react";
import { ProductStatus } from "@/lib/types";

const TABS = ["상품마스터", "일별판매", "재고현황"] as const;
type Tab = typeof TABS[number];

const STATUS_LABEL: Record<ProductStatus, string> = {
    active:   "활성",
    inactive: "비활성",
    sample:   "샘플",
};
const STATUS_BG: Record<ProductStatus, string> = {
    active:   "bg-green-50 text-green-700",
    inactive: "bg-gray-100 text-gray-500",
    sample:   "bg-blue-50 text-blue-600",
};
// 허용 전환 대상 목록
const STATUS_TRANSITIONS: Record<ProductStatus, ProductStatus[]> = {
    active:   ["inactive", "sample"],
    inactive: ["active"],
    sample:   ["active"],
};

export default function SheetsPage() {
    const [tab, setTab]           = useState<Tab>("상품마스터");
    const [data, setData]         = useState<any[]>([]);
    const [loading, setLoad]      = useState(false);
    const [days, setDays]         = useState(30);
    const [page, setPage]         = useState(1);
    const [pageSize, setPageSize] = useState(getDefaultPageSize);
    const [totalPages, setTotalPages] = useState(1);
    const [total, setTotal]       = useState(0);
    const topRef                  = useRef<HTMLDivElement>(null);
    const [isReadonly, setIsReadonly] = useState(false);

    // 상품 상태 변경
    const [statusChanging, setStatusChanging] = useState<string | null>(null);

    // 상품 편집 모달
    const [editRow, setEditRow] = useState<any | null>(null);
    const [editValues, setEditValues] = useState<{ name: string; category: string; safety_stock: string; status: string }>({ name: "", category: "", safety_stock: "", status: "" });
    const [editSaving, setEditSaving] = useState(false);

    // Excel 업로드
    const [uploadFile, setUploadFile]       = useState<File | null>(null);
    const [uploadSheetType, setUploadSheetType] = useState<"master" | "sales" | "stock">("master");
    const [uploading, setUploading]         = useState(false);
    const [uploadMsg, setUploadMsg]         = useState("");
    const fileInputRef                      = useRef<HTMLInputElement>(null);

    const fetchData = async () => {
        setLoad(true);
        try {
            if (tab === "상품마스터") {
                const res = await getSheetsMaster(page, pageSize);
                setData(res.data.items ?? []);
                setTotalPages(res.data.total_pages ?? 1);
                setTotal(res.data.total ?? 0);
            } else if (tab === "일별판매") {
                const res = await getSheetsSales(days, page, pageSize);
                setData(res.data.items ?? []);
                setTotalPages(res.data.total_pages ?? 1);
                setTotal(res.data.total ?? 0);
            } else {
                const res = await getSheetsStock(page, pageSize);
                setData(res.data.items ?? []);
                setTotalPages(res.data.total_pages ?? 1);
                setTotal(res.data.total ?? 0);
            }
        } finally {
            setLoad(false);
        }
    };

    useEffect(() => {
        setIsReadonly(localStorage.getItem("user_role") === "readonly");
        fetchData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tab, days, page, pageSize]);

    const scrollToTop = () => topRef.current?.scrollIntoView({ behavior: "smooth" });

    const handleStatusChange = async (productCode: string, newStatus: ProductStatus) => {
        setStatusChanging(productCode);
        try {
            await updateProductStatus(productCode, newStatus);
            // 로컬 상태 즉시 반영
            setData((prev) =>
                prev.map((row) =>
                    row["상품코드"] === productCode || row["product_code"] === productCode
                        ? { ...row, status: newStatus }
                        : row
                )
            );
        } finally {
            setStatusChanging(null);
        }
    };

    const handleUpload = async () => {
        if (!uploadFile) return;
        setUploading(true);
        setUploadMsg("");
        try {
            const res = await uploadExcel(uploadFile, uploadSheetType);
            const { inserted, updated } = res.data;
            setUploadMsg(`✅ 업로드 완료 — 신규 ${inserted}건, 수정 ${updated}건`);
            setUploadFile(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
            fetchData();
        } catch (err: any) {
            const detail = err.response?.data?.detail ?? "업로드 실패";
            setUploadMsg(`❌ ${detail}`);
        } finally {
            setUploading(false);
            setTimeout(() => setUploadMsg(""), 6000);
        }
    };

    const openEdit = (row: any) => {
        setEditRow(row);
        setEditValues({
            name:          row["상품명"]    ?? row["name"]          ?? "",
            category:      row["카테고리"] ?? row["category"]       ?? "",
            safety_stock:  String(row["안전재고"] ?? row["safety_stock"] ?? "0"),
            status:        row["status"]    ?? "active",
        });
    };

    const saveEdit = async () => {
        if (!editRow) return;
        const code: string = editRow["상품코드"] ?? editRow["product_code"] ?? "";
        setEditSaving(true);
        try {
            await updateProduct(code, {
                name:         editValues.name || undefined,
                category:     editValues.category || undefined,
                safety_stock: editValues.safety_stock ? Number(editValues.safety_stock) : undefined,
                status:       editValues.status || undefined,
            });
            setData((prev) =>
                prev.map((r) =>
                    (r["상품코드"] ?? r["product_code"]) === code
                        ? { ...r, 상품명: editValues.name, 카테고리: editValues.category, status: editValues.status }
                        : r
                )
            );
            setEditRow(null);
        } finally {
            setEditSaving(false);
        }
    };

    // 상품마스터 탭 전용: status 컬럼 제외하고 일반 컬럼만 표시
    const isMasterTab = tab === "상품마스터";
    const allColumns  = data.length > 0 ? Object.keys(data[0]) : [];
    const columns     = isMasterTab
        ? allColumns.filter((c) => c !== "status")
        : allColumns;

    return (
        <div className="space-y-5" ref={topRef}>
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">데이터 조회</h2>
                    <p className="text-gray-400 text-sm mt-1">Google Sheets 원본 데이터</p>
                </div>
                {!isReadonly && (
                    <button onClick={fetchData} className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition">
                        <RefreshCw size={15} className={`text-gray-500 ${loading ? "animate-spin" : ""}`} />
                    </button>
                )}
            </div>

            {/* Excel 업로드 (관리자만) */}
            {!isReadonly && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
                    <p className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                        <Upload size={14} /> Excel 업로드
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                        <select
                            value={uploadSheetType}
                            onChange={(e) => setUploadSheetType(e.target.value as "master" | "sales" | "stock")}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none"
                        >
                            <option value="master">상품마스터</option>
                            <option value="sales">일별판매</option>
                            <option value="stock">재고현황</option>
                        </select>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                            className="text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:border file:border-gray-200 file:rounded-lg file:text-sm file:bg-white file:text-gray-600 hover:file:bg-gray-50"
                        />
                        <button
                            onClick={handleUpload}
                            disabled={!uploadFile || uploading}
                            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded-lg text-sm font-medium transition disabled:opacity-50"
                        >
                            {uploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                            {uploading ? "업로드 중..." : "업로드"}
                        </button>
                    </div>
                    {uploadMsg && (
                        <p className="mt-2 text-sm text-gray-600 bg-gray-50 px-3 py-1.5 rounded-lg">{uploadMsg}</p>
                    )}
                </div>
            )}

            {/* 탭 */}
            <div className="flex gap-2 flex-wrap">
                {TABS.map((t) => (
                    <button
                        key={t}
                        onClick={() => { setTab(t); setPage(1); }}
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
                        onChange={(e) => { setDays(Number(e.target.value)); setPage(1); }}
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
                            {isMasterTab && <th className="px-5 py-3 text-left whitespace-nowrap">상태</th>}
                            {isMasterTab && !isReadonly && <th className="px-5 py-3 text-left whitespace-nowrap">상태 변경</th>}
                            {isMasterTab && !isReadonly && <th className="px-5 py-3 text-left whitespace-nowrap">편집</th>}
                        </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                        {data.map((row, i) => {
                            const productCode: string = row["상품코드"] ?? row["product_code"] ?? "";
                            const currentStatus: ProductStatus = (row["status"] as ProductStatus) ?? "active";
                            return (
                                <tr key={i} className="hover:bg-gray-50 transition">
                                    {columns.map((col) => (
                                        <td key={col} className="px-5 py-2.5 text-gray-700 whitespace-nowrap">
                                            {String(row[col] ?? "-")}
                                        </td>
                                    ))}
                                    {isMasterTab && (
                                        <td className="px-5 py-2.5 whitespace-nowrap">
                                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BG[currentStatus] ?? "bg-gray-100 text-gray-500"}`}>
                                                {STATUS_LABEL[currentStatus] ?? currentStatus}
                                            </span>
                                        </td>
                                    )}
                                    {isMasterTab && !isReadonly && (
                                        <td className="px-5 py-2.5 whitespace-nowrap">
                                            <div className="flex items-center gap-1">
                                                {statusChanging === productCode ? (
                                                    <Loader2 size={13} className="animate-spin text-blue-500" />
                                                ) : (
                                                    STATUS_TRANSITIONS[currentStatus]?.map((s) => (
                                                        <button
                                                            key={s}
                                                            onClick={() => handleStatusChange(productCode, s)}
                                                            className="px-2 py-0.5 rounded text-xs border border-gray-200 text-gray-600 hover:bg-gray-100 transition"
                                                        >
                                                            {STATUS_LABEL[s]}
                                                        </button>
                                                    ))
                                                )}
                                            </div>
                                        </td>
                                    )}
                                    {isMasterTab && !isReadonly && (
                                        <td className="px-5 py-2.5 whitespace-nowrap">
                                            <button
                                                onClick={() => openEdit(row)}
                                                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition"
                                            >
                                                <Pencil size={13} />
                                            </button>
                                        </td>
                                    )}
                                </tr>
                            );
                        })}
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

            {/* 상품 편집 모달 */}
            {editRow && (
                <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
                        <div className="flex items-center justify-between mb-5">
                            <h3 className="text-lg font-semibold text-gray-800">상품 편집</h3>
                            <button onClick={() => setEditRow(null)} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400"><X size={16} /></button>
                        </div>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">상품코드</label>
                                <p className="text-sm text-gray-700">{editRow["상품코드"] ?? editRow["product_code"]}</p>
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">상품명</label>
                                <input type="text" value={editValues.name} onChange={(e) => setEditValues((v) => ({ ...v, name: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">카테고리</label>
                                <input type="text" value={editValues.category} onChange={(e) => setEditValues((v) => ({ ...v, category: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">안전재고</label>
                                <input type="number" value={editValues.safety_stock} onChange={(e) => setEditValues((v) => ({ ...v, safety_stock: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
                            </div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1">상태</label>
                                <select value={editValues.status} onChange={(e) => setEditValues((v) => ({ ...v, status: e.target.value }))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400">
                                    <option value="active">활성</option>
                                    <option value="inactive">비활성</option>
                                    <option value="sample">샘플</option>
                                </select>
                            </div>
                        </div>
                        <div className="flex justify-end gap-2 mt-6">
                            <button onClick={() => setEditRow(null)} className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition">취소</button>
                            <button onClick={saveEdit} disabled={editSaving} className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition">
                                {editSaving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                                저장
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
