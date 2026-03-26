"use client";

import { useEffect, useRef, useState } from "react";
import {
    deletePdf, downloadPdf, getPdfList,
    getReportHistory, triggerReport, getReportStatus, getAnomalies,
} from "@/lib/api";
import { PdfFile, ReportExecution } from "@/lib/types";
import {
    CheckCircle, Clock, ChevronLeft, ChevronRight,
    Eye, EyeOff, Loader2, Play, Trash2, XCircle, Filter,
} from "lucide-react";

const STATUS_INFO: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    success:     { label: "성공",    icon: <CheckCircle size={14} />, color: "text-green-600" },
    failure:     { label: "실패",    icon: <XCircle size={14} />,     color: "text-red-500"   },
    in_progress: { label: "진행 중", icon: <Clock size={14} />,       color: "text-blue-500"  },
};

const SEVERITIES = ["critical", "high", "medium", "low"] as const;
const SEVERITY_KOR: Record<string, string> = {
    critical: "긴급", high: "높음", medium: "보통", low: "낮음",
};
const PAGE_SIZE = 5;
const MAX_POLL = 150;

export default function ReportsPage() {
    const [history, setHistory]       = useState<ReportExecution[]>([]);
    const [historyTotal, setHistoryTotal] = useState(0);
    const [historyPage, setHistoryPage]   = useState(0); // offset = page * PAGE_SIZE
    const [triggering, setTriggering] = useState(false);
    const [polling, setPolling]       = useState(false);
    const [message, setMessage]       = useState("");
    const [pdfs, setPdfs]             = useState<PdfFile[]>([]);
    const [previewFilename, setPreviewFilename] = useState<string | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [blobUrls, setBlobUrls]     = useState<Record<string, string>>({});
    const [loading, setLoading]       = useState(true);
    const [deleting, setDeleting]     = useState<string | null>(null);

    // 필터 상태
    const [showFilter, setShowFilter]     = useState(false);
    const [severityFilter, setSeverityFilter] = useState<string[]>([]);
    const [categoryFilter, setCategoryFilter] = useState<string[]>([]);
    const [categories, setCategories]     = useState<string[]>([]);

    const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollCountRef = useRef(0);

    const fetchHistory = async (page = historyPage) => {
        const res = await getReportHistory(PAGE_SIZE, page * PAGE_SIZE);
        setHistory(res.data.items ?? []);
        setHistoryTotal(res.data.total ?? 0);
    };

    const fetchAll = async () => {
        setLoading(true);
        try {
            await Promise.all([fetchHistory(0), getPdfList().then((r) => setPdfs(r.data.items ?? []))]);
            setHistoryPage(0);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAll();
        // 카테고리 목록 수집
        getAnomalies(undefined, 200).then((res) => {
            const cats = Array.from(new Set((res.data.items ?? []).map((a: any) => a.category).filter(Boolean))) as string[];
            setCategories(cats);
        });
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, []);

    useEffect(() => {
        fetchHistory(historyPage);
    }, [historyPage]);

    const startPolling = (executionId: number) => {
        pollCountRef.current = 0;
        setPolling(true);
        pollRef.current = setInterval(async () => {
            pollCountRef.current += 1;
            try {
                const res = await getReportStatus(executionId);
                const { status, error_message } = res.data;
                if (status !== "in_progress") {
                    clearInterval(pollRef.current!);
                    setPolling(false);
                    if (status === "success") {
                        setMessage("✅ 보고서 생성이 완료되었습니다.");
                        fetchAll();
                    } else {
                        setMessage(`❌ 실패: ${error_message ?? "알 수 없는 오류"}`);
                    }
                } else if (pollCountRef.current >= MAX_POLL) {
                    clearInterval(pollRef.current!);
                    setPolling(false);
                    setMessage("⏱ 시간 초과. 새로 고침해주세요.");
                    fetchHistory(0);
                }
            } catch {
                clearInterval(pollRef.current!);
                setPolling(false);
            }
        }, 2000);
    };

    const handleTrigger = async () => {
        setTriggering(true);
        setMessage("");
        try {
            const res = await triggerReport({
                severity_filter: severityFilter.length ? severityFilter : null,
                category_filter: categoryFilter.length ? categoryFilter : null,
            });
            const { execution_id } = res.data;
            setMessage("⏳ 보고서 생성 중...");
            startPolling(execution_id);
        } catch {
            setMessage("❌ 보고서 생성 요청에 실패했습니다.");
        } finally {
            setTriggering(false);
        }
    };

    const toggleSeverity = (s: string) =>
        setSeverityFilter((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

    const toggleCategory = (c: string) =>
        setCategoryFilter((prev) => prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]);

    const getPdfBlob = async (filename: string): Promise<string> => {
        if (blobUrls[filename]) return blobUrls[filename];
        const blob = await downloadPdf(filename);
        const url = URL.createObjectURL(blob);
        setBlobUrls((prev) => ({ ...prev, [filename]: url }));
        return url;
    };

    const handlePreview = async (filename: string) => {
        if (previewFilename === filename) { setPreviewFilename(null); setPreviewUrl(null); return; }
        const url = await getPdfBlob(filename);
        setPreviewFilename(filename); setPreviewUrl(url);
    };

    const handleDownload = async (filename: string) => {
        const url = await getPdfBlob(filename);
        const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
    };

    const handleDeletePdf = async (filename: string) => {
        if (!confirm(`"${filename}"을(를) 삭제하시겠습니까?`)) return;
        setDeleting(filename);
        try {
            await deletePdf(filename);
            if (previewFilename === filename) { setPreviewFilename(null); setPreviewUrl(null); }
            setPdfs((prev) => prev.filter((p) => p.filename !== filename));
        } catch { alert("삭제에 실패했습니다."); }
        finally { setDeleting(null); }
    };

    const totalPages = Math.max(1, Math.ceil(historyTotal / PAGE_SIZE));

    return (
        <div className="space-y-6">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">보고서 이력</h2>
                    <p className="text-gray-400 text-sm mt-1">자동/수동 보고서 생성 이력</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => setShowFilter((v) => !v)}
                            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition ${
                                showFilter ? "border-blue-400 text-blue-600 bg-blue-50" : "border-gray-200 text-gray-600 hover:bg-gray-50"
                            }`}
                    >
                        <Filter size={14} />
                        필터 {(severityFilter.length + categoryFilter.length) > 0 &&
                        <span className="bg-blue-500 text-white text-xs rounded-full px-1.5">
                                {severityFilter.length + categoryFilter.length}
                            </span>}
                    </button>
                    <button onClick={handleTrigger} disabled={triggering || polling}
                            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                    >
                        {polling ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                        {polling ? "생성 중..." : "즉시 생성"}
                    </button>
                </div>
            </div>

            {/* 필터 패널 */}
            {showFilter && (
                <div className="bg-white rounded-xl border border-blue-100 shadow-sm p-5 space-y-4">
                    <div>
                        <p className="text-xs font-semibold text-gray-500 mb-2">심각도 (선택하지 않으면 전체)</p>
                        <div className="flex gap-2 flex-wrap">
                            {SEVERITIES.map((s) => (
                                <button key={s} onClick={() => toggleSeverity(s)}
                                        className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                                            severityFilter.includes(s)
                                                ? "bg-blue-600 text-white border-blue-600"
                                                : "border-gray-200 text-gray-600 hover:bg-gray-50"
                                        }`}
                                >
                                    {SEVERITY_KOR[s]}
                                </button>
                            ))}
                        </div>
                    </div>
                    {categories.length > 0 && (
                        <div>
                            <p className="text-xs font-semibold text-gray-500 mb-2">카테고리</p>
                            <div className="flex gap-2 flex-wrap">
                                {categories.map((c) => (
                                    <button key={c} onClick={() => toggleCategory(c)}
                                            className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
                                                categoryFilter.includes(c)
                                                    ? "bg-blue-600 text-white border-blue-600"
                                                    : "border-gray-200 text-gray-600 hover:bg-gray-50"
                                            }`}
                                    >
                                        {c}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                    {(severityFilter.length > 0 || categoryFilter.length > 0) && (
                        <button onClick={() => { setSeverityFilter([]); setCategoryFilter([]); }}
                                className="text-xs text-gray-400 hover:text-gray-600">초기화</button>
                    )}
                </div>
            )}

            {message && <p className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">{message}</p>}

            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 size={32} className="animate-spin text-blue-500" />
                </div>
            ) : (
                <>
                    {/* 보고서 이력 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
                        {/* 페이지네이션 상단 */}
                        <div className="flex items-center justify-between px-6 py-3 border-b border-gray-100">
                            <p className="text-sm text-gray-500">총 <span className="font-semibold">{historyTotal}</span>건</p>
                            <div className="flex items-center gap-1">
                                <button onClick={() => setHistoryPage((p) => Math.max(0, p - 1))}
                                        disabled={historyPage === 0}
                                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
                                    <ChevronLeft size={14} />
                                </button>
                                <span className="px-3 text-sm text-gray-600">{historyPage + 1} / {totalPages}</span>
                                <button onClick={() => setHistoryPage((p) => Math.min(totalPages - 1, p + 1))}
                                        disabled={historyPage >= totalPages - 1}
                                        className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40">
                                    <ChevronRight size={14} />
                                </button>
                            </div>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                <tr className="bg-gray-50 text-gray-500 text-xs">
                                    <th className="px-6 py-3 text-left">ID</th>
                                    <th className="px-6 py-3 text-left">실행일시</th>
                                    <th className="px-6 py-3 text-left">유형</th>
                                    <th className="px-6 py-3 text-left">상태</th>
                                    <th className="px-6 py-3 text-left">Slack</th>
                                    <th className="px-6 py-3 text-left">오류</th>
                                </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                {history.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} className="px-6 py-10 text-center text-gray-400">이력 없음</td>
                                    </tr>
                                ) : (
                                    history.map((r) => {
                                        const s = STATUS_INFO[r.status];
                                        return (
                                            <tr key={r.id} className="hover:bg-gray-50 transition">
                                                <td className="px-6 py-3 text-gray-400">#{r.id}</td>
                                                <td className="px-6 py-3 text-gray-700">{r.executed_at.slice(0, 16)}</td>
                                                <td className="px-6 py-3 text-gray-600">{r.report_type}</td>
                                                <td className="px-6 py-3">
                                                    <span className={`flex items-center gap-1 text-xs font-medium ${s?.color}`}>
                                                        {s?.icon}{s?.label}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-3 text-xs">{r.slack_sent ? "✅ 전송됨" : "—"}</td>
                                                <td className="px-6 py-3 text-gray-400 text-xs max-w-xs truncate">{r.error_message ?? "—"}</td>
                                            </tr>
                                        );
                                    })
                                )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* PDF 목록 */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
                        <div className="px-6 py-4 border-b border-gray-100">
                            <h3 className="font-semibold text-gray-700">생성된 PDF 보고서</h3>
                        </div>
                        <div className="divide-y divide-gray-50">
                            {pdfs.length === 0 ? (
                                <p className="px-6 py-8 text-center text-gray-400 text-sm">생성된 PDF 없음</p>
                            ) : (
                                pdfs.map((pdf) => (
                                    <div key={pdf.filename} className="flex items-center justify-between px-6 py-3">
                                        <div>
                                            <p className="text-sm text-gray-700 font-medium">{pdf.filename}</p>
                                            <p className="text-xs text-gray-400">{pdf.size_kb} KB</p>
                                        </div>
                                        <div className="flex gap-2 items-center">
                                            <button onClick={() => handlePreview(pdf.filename)}
                                                    className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs font-medium transition">
                                                {previewFilename === pdf.filename ? <><EyeOff size={12} /> 닫기</> : <><Eye size={12} /> 미리보기</>}
                                            </button>
                                            <button onClick={() => handleDownload(pdf.filename)}
                                                    className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg text-xs font-medium transition">
                                                다운로드
                                            </button>
                                            <button onClick={() => handleDeletePdf(pdf.filename)}
                                                    disabled={deleting === pdf.filename}
                                                    className="flex items-center gap-1 px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-500 rounded-lg text-xs font-medium transition disabled:opacity-50">
                                                {deleting === pdf.filename ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                                                삭제
                                            </button>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* PDF 미리보기 */}
                    {previewUrl && (
                        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
                            <div className="flex items-center justify-between mb-3">
                                <p className="text-sm font-medium text-gray-700">{previewFilename}</p>
                                <button onClick={() => { setPreviewFilename(null); setPreviewUrl(null); }}
                                        className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs transition">닫기</button>
                            </div>
                            <iframe src={previewUrl} className="w-full rounded-lg border border-gray-200" style={{ height: "800px" }} />
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
