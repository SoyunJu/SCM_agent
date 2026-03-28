"use client";

import { useEffect, useRef, useState } from "react";
import { getSheetsMaster, getSheetsSales, getSheetsStock, updateProductStatus, uploadExcel } from "@/lib/api";
import { RefreshCw, Loader2, ArrowUp, ChevronLeft, ChevronRight, Upload } from "lucide-react";
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
    const [totalPages, setTotalPages] = useState(1);
    const [total, setTotal]       = useState(0);
    const topRef                  = useRef<HTMLDivElement>(null);
    const [isReadonly, setIsReadonly] = useState(false);

    // 상품 상태 변경
    const [statusChanging, setStatusChanging] = useState<string | null>(null);

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
                const res = await getSheetsMaster(page, 50);
                setData(res.data.items ?? []);
                setTotalPages(res.data.total_pages ?? 1);
                setTotal(res.data.total ?? 0);
            } else if (tab === "일별판매") {
                const res = await getSheetsSales(days, page, 50);
                setData(res.data.items ?? []);
                setTotalPages(res.data.total_pages ?? 1);
                setTotal(res.data.total ?? 0);
            } else {
                const res = await getSheetsStock(page, 50);
                setData(res.data.items ?? []);
                setTotalPages(res.data.total_pages ?? 1);
                setTotal(res.data.total ?? 0);
            }
        } finally {
            setLoad(false);
        }
    };

    useEffect(() => {
        const role = localStorage.getItem("user_role") ?? "";
        setIsReadonly(role === "readonly");
        setPage(1);
    }, [tab, days]);

    useEffect(() => {
        const role = localStorage.getItem("user_role") ?? "";
        setIsReadonly(role === "readonly");
        fetchData();
    }, [tab, days, page]);

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
                            {isMasterTab && <th className="px-5 py-3 text-left whitespace-nowrap">상태</th>}
                            {isMasterTab && !isReadonly && <th className="px-5 py-3 text-left whitespace-nowrap">상태 변경</th>}
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
        </div>
    );
}
