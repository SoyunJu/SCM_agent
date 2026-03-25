"use client";

import { useEffect, useState } from "react";
import { getReportHistory, triggerReport } from "@/lib/api";
import { ReportExecution } from "@/lib/types";
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

    const fetchHistory = () =>
        getReportHistory(20).then((res) => setHistory(res.data.items));

    useEffect(() => { fetchHistory(); }, []);

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
        </div>
    );
}