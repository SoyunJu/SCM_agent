"use client";

import { useEffect, useState } from "react";
import { getReportStatus } from "@/lib/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSchedulerConfig, updateSchedulerConfig, getSchedulerStatus, triggerReport, apiClient } from "@/lib/api";
import { ScheduleConfig } from "@/lib/types";
import {
    Clock, Play, RefreshCw, Save, Loader2,
    CheckCircle2, XCircle, Activity, CalendarClock, Zap,
} from "lucide-react";


const BEAT_LABELS: Record<string, { label: string; desc: string }> = {
    "daily-report":      { label: "일일 보고서",       desc: "매일 00:00 자동 실행" },
    "daily-crawler":     { label: "크롤러",             desc: "매일 23:00 자동 실행" },
    "cleanup-data":      { label: "데이터 정리",        desc: "매일 02:00 자동 실행" },
    "sync-sheets-to-db": { label: "Sheets→DB 동기화",  desc: "1분 주기 자동 실행" },
};

export default function SchedulerPage() {
    const qc = useQueryClient();

    const [hour,      setHour]      = useState(0);
    const [minute,    setMinute]    = useState(0);
    const [isActive,  setIsActive]  = useState(true);
    const [message,   setMessage]   = useState("");
    const [isReadonly, setIsReadonly] = useState(false);

    useEffect(() => {
        setIsReadonly(localStorage.getItem("user_role") === "readonly");
    }, []);

    const flash = (m: string) => {
        setMessage(m);
        setTimeout(() => setMessage(""), 5000);
    };

    // ── 데이터 조회 ──────────────────────────────────────────────────────────
    const { data: config } = useQuery<ScheduleConfig>({
        queryKey: ["schedulerConfig"],
        queryFn:  () => getSchedulerConfig().then((r) => r.data as ScheduleConfig),
    });

    useEffect(() => {
        if (!config) return;
        setHour(config.schedule_hour);
        setMinute(config.schedule_minute);
        setIsActive(config.is_active);
    }, [config]);

    const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
        queryKey:        ["schedulerStatus"],
        queryFn:         () => getSchedulerStatus().then((r) => r.data),
        refetchInterval: 10_000,   // 10초마다 자동 갱신
    });

    // ── Mutations ────────────────────────────────────────────────────────────
    const saveMutation = useMutation({
        mutationFn: () => updateSchedulerConfig({
            schedule_hour: hour, schedule_minute: minute,
            timezone: "Asia/Seoul", is_active: isActive,
        }),
        onSuccess: () => {
            flash("✅ 스케줄이 업데이트되었습니다.");
            qc.invalidateQueries({ queryKey: ["schedulerStatus"] });
        },
        onError: () => flash("❌ 스케줄 업데이트에 실패했습니다."),
    });

    const triggerMutation = useMutation({
        mutationFn: () => triggerReport(),
        onSuccess:  () => flash("✅ 보고서 생성이 시작되었습니다. Slack을 확인하세요."),
        onError:    () => flash("❌ 보고서 생성 실패"),
    });

    const syncMutation = useMutation({
        mutationFn: () => apiClient.post("/scm/sheets/sync"),
        onSuccess:  () => flash("✅ 데이터 동기화가 시작되었습니다."),
        onError:    () => flash("❌ 동기화 실패"),
    });

    // ── 파생 상태 ─────────────────────────────────────────────────────────────
    const workers: { name: string; status: string; active_tasks: number }[] =
        status?.workers ?? [];
    const onlineCount = workers.filter((w) => w.status === "online").length;
    const beatSchedule: Record<string, string> = status?.beat_schedule ?? {};
    const hasError = status?.error;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">스케줄 관리</h2>
                    <p className="text-gray-400 text-sm mt-1"> 보고서 생성 | 데이터 동기화 </p>
                </div>
                <button
                    onClick={() => refetchStatus()}
                    disabled={statusLoading}
                    className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 transition"
                    title="상태 새로고침"
                >
                    <RefreshCw size={15} className={`text-gray-500 ${statusLoading ? "animate-spin" : ""}`} />
                </button>
            </div>

            {message && (
                <div className="px-4 py-2.5 rounded-lg bg-blue-50 text-blue-700 text-sm">
                    {message}
                </div>
            )}

            {/* ── 상단 2열 그리드 ─────────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                {/* Worker 상태 카드 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Activity size={15} className="text-blue-500" />
                        Celery Worker
                    </h3>

                    {hasError ? (
                        <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">
                            <XCircle size={14} />
                            Worker에 연결할 수 없습니다. RabbitMQ 및 Worker 상태를 확인하세요.
                        </div>
                    ) : statusLoading ? (
                        <div className="flex items-center gap-2 text-sm text-gray-400">
                            <Loader2 size={13} className="animate-spin" /> 상태 조회 중...
                        </div>
                    ) : workers.length === 0 ? (
                        <div className="flex items-center gap-2 text-sm text-red-500 bg-red-50 px-3 py-2 rounded-lg">
                            <XCircle size={14} />
                            실행 중인 Worker가 없습니다.
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {/* 요약 뱃지 */}
                            <div className="flex items-center gap-2 mb-3">
                                <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
                                    onlineCount > 0
                                        ? "bg-green-50 text-green-700"
                                        : "bg-red-50 text-red-600"
                                }`}>
                                    {onlineCount > 0
                                        ? <CheckCircle2 size={12} />
                                        : <XCircle size={12} />}
                                    {onlineCount > 0 ? `${onlineCount}개 온라인` : "오프라인"}
                                </span>
                                <span className="text-xs text-gray-400">
                                    {workers.reduce((s, w) => s + w.active_tasks, 0)}개 작업 처리 중
                                </span>
                            </div>

                            {/* Worker 목록 */}
                            {workers.map((w) => (
                                <div key={w.name}
                                     className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg text-sm">
                                    <div className="flex items-center gap-2 min-w-0">
                                        <span className={`w-2 h-2 rounded-full shrink-0 ${
                                            w.status === "online" ? "bg-green-500" : "bg-red-400"
                                        }`} />
                                        <span className="text-gray-600 truncate font-mono text-xs">
                                            {w.name.split("@")[0]}
                                        </span>
                                    </div>
                                    <span className="text-xs text-gray-400 shrink-0 ml-2">
                                        {w.active_tasks > 0
                                            ? <span className="text-blue-600 font-medium">처리 중 {w.active_tasks}건</span>
                                            : "대기 중"}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Beat 스케줄 카드 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <CalendarClock size={15} className="text-purple-500" />
                        Beat 스케줄
                    </h3>

                    {Object.keys(beatSchedule).length === 0 ? (
                        <p className="text-sm text-gray-400">Beat 스케줄 정보를 불러올 수 없습니다.</p>
                    ) : (
                        <div className="space-y-2">
                            {Object.entries(beatSchedule).map(([key, schedule]) => {
                                const info = BEAT_LABELS[key] ?? { label: key, desc: schedule };
                                return (
                                    <div key={key}
                                         className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-gray-700">{info.label}</p>
                                            <p className="text-xs text-gray-400 mt-0.5">{info.desc}</p>
                                        </div>
                                        <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full shrink-0 ml-2 font-mono">
                                            {schedule}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* 마지막 실행 */}
                    {config?.last_run_at && (
                        <div className="mt-4 pt-3 border-t border-gray-100 flex justify-between text-xs text-gray-400">
                            <span>마지막 보고서 실행</span>
                            <span>{config.last_run_at.slice(0, 19)}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── 스케줄 설정 + 즉시 실행 ─────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                {/* 스케줄 설정 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Clock size={15} className="text-gray-500" />
                        일일 보고서 스케줄
                    </h3>
                    <div className="space-y-4">
                        <div className="flex gap-4 items-end">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">시 (0~23)</label>
                                <input
                                    type="number" min={0} max={23}
                                    value={hour}
                                    onChange={(e) => setHour(Number(e.target.value))}
                                    disabled={isReadonly}
                                    className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">분 (0~59)</label>
                                <input
                                    type="number" min={0} max={59}
                                    value={minute}
                                    onChange={(e) => setMinute(Number(e.target.value))}
                                    disabled={isReadonly}
                                    className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
                                />
                            </div>
                            <p className="text-sm text-gray-500 pb-2">
                                → 매일 <strong className="text-gray-800">
                                {String(hour).padStart(2, "0")}:{String(minute).padStart(2, "0")}
                            </strong>
                            </p>
                        </div>

                        <div className="flex items-center gap-2">
                            <input
                                type="checkbox" id="is_active"
                                checked={isActive}
                                onChange={(e) => setIsActive(e.target.checked)}
                                disabled={isReadonly}
                                className="w-4 h-4 rounded"
                            />
                            <label htmlFor="is_active" className="text-sm text-gray-700">스케줄 활성화</label>
                        </div>

                        {!isReadonly && (
                            <button
                                onClick={() => saveMutation.mutate()}
                                disabled={saveMutation.isPending}
                                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                            >
                                {saveMutation.isPending
                                    ? <Loader2 size={14} className="animate-spin" />
                                    : <Save size={14} />}
                                {saveMutation.isPending ? "저장 중..." : "저장"}
                            </button>
                        )}
                    </div>
                </div>

                {/* 즉시 실행 */}
                {!isReadonly && (
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                        <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                            <Zap size={15} className="text-yellow-500" />
                            즉시 실행
                        </h3>
                        <div className="space-y-3">
                            {/* 보고서 생성 — 관리자만 */}
                            {!isReadonly && (
                                <button
                                    onClick={() => triggerMutation.mutate()}
                                    disabled={triggerMutation.isPending}
                                    className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition disabled:opacity-50"
                                >
                                    {triggerMutation.isPending
                                        ? <Loader2 size={14} className="animate-spin" />
                                        : <Play size={14} />}
                                    {triggerMutation.isPending ? "생성 중..." : "보고서 즉시 생성"}
                                </button>
                            )}
                            {/* 동기화 — 항상 노출 */}
                            <button
                                onClick={() => syncMutation.mutate()}
                                disabled={syncMutation.isPending}
                                className="w-full flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-700 px-4 py-2.5 rounded-lg text-sm font-medium transition disabled:opacity-50"
                            >
                                {syncMutation.isPending
                                    ? <Loader2 size={14} className="animate-spin" />
                                    : <RefreshCw size={14} />}
                                {syncMutation.isPending ? "동기화 중..." : "Sheets → DB 동기화"}
                            </button>
                            {!isReadonly && (
                                <p className="text-xs text-gray-400 text-center">
                                    보고서 생성 결과는 완료 후 상태가 업데이트됩니다.
                                </p>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}