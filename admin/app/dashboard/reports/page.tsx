"use client";

import { useEffect, useState } from "react";
import {getReportHistory, triggerReport, getPdfList, getPdfUrl, downloadPdf} from "@/lib/api";
import { ReportExecution, PdfFile } from "@/lib/types";
import { Play, CheckCircle, XCircle, Clock } from "lucide-react";


const STATUS_INFO: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    success:     { label: "성공",    icon: <CheckCircle size={14} />, color: "text-green-600" },
    failure:     { label: "실패",    icon: <XCircle size={14} />,     color: "text-red-500"   },
    in_progress: { label: "진행 중", icon: <Clock size={14} />,       color: "text-blue-500"  },
};

export default function ReportsPage() {
    const [history, setHistory]       = useState<ReportExecution[]>([]);
    const [triggering, setTriggering] = useState(false);
    const [message, setMessage]       = useState("");
    const [pdfs, setPdfs]             = useState<PdfFile[]>([]);
    const [previewUrl, setPreview]    = useState<string | null>(null);
    const [blobUrls, setBlobUrls]     = useState<Record<string, string>>({});

    // PDF blob URL 가져오기 (인증 포함)
    const getPdfBlob = async (filename: string): Promise<string> => {
        if (blobUrls[filename]) return blobUrls[filename];
        const blob = await downloadPdf(filename);
        const url = URL.createObjectURL(blob);
        setBlobUrls((prev) => ({ ...prev, [filename]: url }));
        return url;
    };

    const handlePreview = async (filename: string) => {
        const currentUrl = getPdfUrl(filename);
        if (previewUrl === currentUrl) {
            setPreview(null);
            return;
        }
        const blobUrl = await getPdfBlob(filename);
        setPreview(blobUrl);
    };

    const handleDownload = async (filename: string) => {
        const blobUrl = await getPdfBlob(filename);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = filename;
        a.click();
    };


    const fetchHistory = () =>
        getReportHistory(20).then((res) => setHistory(res.data.items));

    useEffect(() => {
        fetchHistory();
        getPdfList().then((res) => setPdfs(res.data.items ?? []));
    }, []);

    const handleTrigger = async () => {
        setTriggering(true);
        setMessage("");
        try {
            await triggerReport();
            setMessage("✅ 보고서 생성이 시작되었습니다.");
            setTimeout(fetchHistory, 3000);
        } catch {
            setMessage("❌ 보고서 생성이 실패했습니다.");
        } finally {
            setTriggering(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">보고서 이력</h2>
                    <p className="text-gray-400 text-sm mt-1">자동/수동 보고서 생성 이력</p>
                </div>
                <button
                    onClick={handleTrigger}
                    disabled={triggering}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                >
                    <Play size={14} />
                    {triggering ? "생성 중..." : "즉시 생성"}
                </button>
            </div>

            {message && (
                <p className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">{message}</p>
            )}

            {/* 보고서 이력 테이블 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
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
                            <td colSpan={6} className="px-6 py-10 text-center text-gray-400">
                                이력 없음
                            </td>
                        </tr>
                    ) : (
                        history.map((r) => {
                            const statusInfo = STATUS_INFO[r.status];
                            return (
                                <tr key={r.id} className="hover:bg-gray-50 transition">
                                    <td className="px-6 py-3 text-gray-400">#{r.id}</td>
                                    <td className="px-6 py-3 text-gray-700">{r.executed_at.slice(0, 16)}</td>
                                    <td className="px-6 py-3 text-gray-600">{r.report_type}</td>
                                    <td className="px-6 py-3">
                                            <span className={`flex items-center gap-1 text-xs font-medium ${statusInfo?.color}`}>
                                                {statusInfo?.icon}
                                                {statusInfo?.label}
                                            </span>
                                    </td>
                                    <td className="px-6 py-3 text-xs">
                                        {r.slack_sent ? "✅ 전송됨" : "—"}
                                    </td>
                                    <td className="px-6 py-3 text-gray-400 text-xs max-w-xs truncate">
                                        {r.error_message ?? "—"}
                                    </td>
                                </tr>
                            );
                        })
                    )}
                    </tbody>
                </table>
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
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => handlePreview(pdf.filename)}
                                        className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg text-xs font-medium transition"
                                    >
                                        {previewUrl ? "닫기" : "미리보기"}
                                    </button>

                                    <button
                                        onClick={() => handleDownload(pdf.filename)}
                                        className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg text-xs font-medium transition"
                                    >
                                        다운로드
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
                    <iframe
                        src={previewUrl}
                        className="w-full rounded-lg border border-gray-200"
                        style={{ height: "800px" }}
                    />
                </div>
            )}
        </div>
    );
}