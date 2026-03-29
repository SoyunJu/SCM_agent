"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    getSchedulerConfig, updateSchedulerConfig,
    getSchedulerStatus, triggerReport, getReportStatus,
    triggerCrawler, triggerCleanup, triggerSync,
    triggerDemandForecast, triggerTurnoverAnalysis, triggerAbcAnalysis,
} from "@/lib/api";
import { ScheduleConfig } from "@/lib/types";
import {
    Clock, Play, RefreshCw, Save, Loader2,
    CheckCircle2, XCircle, Activity, CalendarClock,
    Zap, AlertTriangle, CheckCheck,
} from "lucide-react";

// ── Beat 스케줄 한글 라벨 + 즉시 실행 task key ────────────────────────────
const BEAT_LABELS: Record<string, { label: string }> = {
    "daily-report":       { label: "보고서 생성"      },
    "daily-crawler":      { label: "크롤러 실행"       },
    "cleanup-data":       { label: "데이터 정리"       },
    "sync-sheets-to-db":  { label: "Sheets→DB 동기화" },
    "demand-forecast":    { label: "수요 예측 분석"    },
    "turnover-analysis":  { label: "재고 회전율 분석"  },
    "abc-analysis":       { label: "ABC 분석"          },
};

// Beat 항목별 즉시 실행 API 매핑
type TriggerKey =
    | "daily-report" | "daily-crawler" | "cleanup-data" | "sync-sheets-to-db"
    | "demand-forecast" | "turnover-analysis" | "abc-analysis";

const BEAT_TRIGGER_FN: Record<TriggerKey, () => Promise<any>> = {
    "daily-report":      () => triggerReport(),
    "daily-crawler":     () => triggerCrawler(),
    "cleanup-data":      () => triggerCleanup(),
    "sync-sheets-to-db": () => triggerSync(),
    "demand-forecast":   () => triggerDemandForecast(),
    "turnover-analysis": () => triggerTurnoverAnalysis(),
    "abc-analysis":      () => triggerAbcAnalysis(),
};

const MAX_POLL = 150;

type MsgType = "info" | "success" | "error" | "warning";
interface Msg { text: string; type: MsgType; }

const MSG_STYLE: Record<MsgType, string> = {
    info:    "bg-blue-50 text-blue-700 border border-blue-100",
    success: "bg-green-50 text-green-700 border border-green-100",
    error:   "bg-red-50 text-red-600 border border-red-100",
    warning: "bg-amber-50 text-amber-700 border border-amber-100",
};
const MSG_ICON: Record<MsgType, React.ReactNode> = {
    info:    <Loader2 size={14} className="animate-spin shrink-0" />,
    success: <CheckCheck size={14} className="shrink-0" />,
    error:   <XCircle size={14} className="shrink-0" />,
    warning: <AlertTriangle size={14} className="shrink-0" />,
};

export default function SchedulerPage() {
    const qc = useQueryClient();

    const [hour,       setHour]      = useState(0);
    const [minute,     setMinute]    = useState(0);
    const [isActive,   setIsActive]  = useState(true);
    const [isReadonly, setIsReadonly] = useState(false);

    const [reportMsg, setReportMsg] = useState<Msg | null>(null);
    const [saveMsg,   setSaveMsg]   = useState<Msg | null>(null);
    // Beat 항목별 메시지/로딩 상태
    const [beatMsg,      setBeatMsg]      = useState<Record<string, Msg | null>>({});
    const [beatLoading,  setBeatLoading]  = useState<Record<string, boolean>>({});

    const [reportPolling, setReportPolling] = useState(false);
    const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);
    const pollCountRef = useRef(0);

    useEffect(() => {
        setIsReadonly(localStorage.getItem("user_role") === "readonly");
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, []);

    // ── React Query ────────────────────────────────────────────────────────

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
        refetchInterval: 10_000,
    });

    // ── Mutations ──────────────────────────────────────────────────────────

    const saveMutation = useMutation({
        mutationFn: () => updateSchedulerConfig({
            schedule_hour: hour, schedule_minute: minute,
            timezone: "Asia/Seoul", is_active: isActive,
        }),
        onSuccess: () => {
            setSaveMsg({ text: "스케줄이 저장되었습니다.", type: "success" });
            setTimeout(() => setSaveMsg(null), 4000);
            qc.invalidateQueries({ queryKey: ["schedulerStatus"] });
        },
        onError: () => {
            setSaveMsg({ text: "스케줄 저장에 실패했습니다.", type: "error" });
            setTimeout(() => setSaveMsg(null), 4000);
        },
    });

    // ── 보고서 폴링 ────────────────────────────────────────────────────────

    const startPolling = (executionId: number) => {
        pollCountRef.current = 0;
        setReportPolling(true);
        setReportMsg({ text: "보고서 생성 중...", type: "info" });

        pollRef.current = setInterval(async () => {
            pollCountRef.current += 1;
            try {
                const res = await getReportStatus(executionId);
                const { status: s, error_message } = res.data;
                const statusStr = (s as string).toLowerCase();

                if (statusStr !== "in_progress") {
                    clearInterval(pollRef.current!);
                    setReportPolling(false);
                    setReportMsg(
                        statusStr === "success"
                            ? { text: "보고서 생성이 완료되었습니다.", type: "success" }
                            : { text: `보고서 생성 실패: ${error_message ?? "알 수 없는 오류"}`, type: "error" }
                    );
                    qc.invalidateQueries({ queryKey: ["schedulerStatus"] });
                    setTimeout(() => setReportMsg(null), 6000);

                } else if (pollCountRef.current >= MAX_POLL) {
                    clearInterval(pollRef.current!);
                    setReportPolling(false);
                    setReportMsg({ text: "시간 초과. 보고서 탭에서 결과를 확인하세요.", type: "warning" });
                    setTimeout(() => setReportMsg(null), 6000);
                }
            } catch {
                clearInterval(pollRef.current!);
                setReportPolling(false);
                setReportMsg({ text: "상태 확인 중 오류가 발생했습니다.", type: "error" });
                setTimeout(() => setReportMsg(null), 4000);
            }
        }, 2000);
    };

    const triggerMutation = useMutation({
        mutationFn: () => triggerReport(),
        onSuccess: (res) => {
            const execution_id = res.data?.execution_id;
            if (execution_id) startPolling(execution_id);
            else {
                setReportMsg({ text: "보고서 생성이 요청되었습니다.", type: "success" });
                setTimeout(() => setReportMsg(null), 4000);
            }
        },
        onError: () => {
            setReportMsg({ text: "보고서 생성 요청에 실패했습니다.", type: "error" });
            setTimeout(() => setReportMsg(null), 4000);
        },
    });

    // ── Beat 항목 즉시 실행 ────────────────────────────────────────────────

    const handleBeatTrigger = async (key: string) => {
        const fn = BEAT_TRIGGER_FN[key as TriggerKey];
        if (!fn) return;

        // 일일 보고서는 기존 triggerMutation 사용 (폴링 포함)
        if (key === "daily-report") {
            triggerMutation.mutate();
            return;
        }

        setBeatLoading((prev) => ({ ...prev, [key]: true }));
        setBeatMsg((prev) => ({ ...prev, [key]: { text: "실행 요청 중...", type: "info" } }));
        try {
            await fn();
            setBeatMsg((prev) => ({ ...prev, [key]: { text: "태스크가 시작되었습니다.", type: "success" } }));
        } catch {
            setBeatMsg((prev) => ({ ...prev, [key]: { text: "실행 요청에 실패했습니다.", type: "error" } }));
        } finally {
            setBeatLoading((prev) => ({ ...prev, [key]: false }));
            setTimeout(() => setBeatMsg((prev) => ({ ...prev, [key]: null })), 4000);
        }
    };

    // ── 파생 상태 ──────────────────────────────────────────────────────────

    const workers: { name: string; status: string; active_tasks: number }[] = status?.workers ?? [];
    const onlineCount  = workers.filter((w) => w.status === "online").length;
    const activeTasks  = workers.reduce((s, w) => s + w.active_tasks, 0);
    const beatSchedule: Record<string, string> = status?.beat_schedule ?? {};
    const hasConnError = !status?.workers && !!status?.error;
    const isReportBusy = reportPolling || triggerMutation.isPending;

    return (
        <div className="space-y-5">

            {/* 헤더 */}
            <div>
                <h2 className="text-2xl font-bold text-gray-800">스케줄 관리</h2>
                <p className="text-gray-400 text-sm mt-1">Celery Worker / Beat 상태 및 스케줄 설정</p>
            </div>

            {/* ── 상단: Worker 상태 + Beat 스케줄 ────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                {/* Worker 상태 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2">
                            <Activity size={15} className="text-gray-500" /> Celery Worker
                        </h3>
                        <button
                            onClick={() => refetchStatus()}
                            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition"
                        >
                            <RefreshCw size={13} />
                        </button>
                    </div>

                    {statusLoading ? (
                        <div className="flex justify-center py-6"><Loader2 className="animate-spin text-blue-500" /></div>
                    ) : hasConnError ? (
                        <div className="flex items-center gap-2 text-red-500 text-sm py-2">
                            <XCircle size={14} /> Celery 연결 실패
                        </div>
                    ) : (
                        <>
                            <div className="flex gap-4 mb-4">
                                <div className="flex-1 bg-gray-50 rounded-lg p-3 text-center">
                                    <p className="text-2xl font-bold text-gray-800">{onlineCount}</p>
                                    <p className="text-xs text-gray-400 mt-0.5">온라인 워커</p>
                                </div>
                                <div className="flex-1 bg-gray-50 rounded-lg p-3 text-center">
                                    <p className="text-2xl font-bold text-blue-600">{activeTasks}</p>
                                    <p className="text-xs text-gray-400 mt-0.5">실행 중 태스크</p>
                                </div>
                            </div>
                            <div className="space-y-1.5">
                                {workers.length === 0 ? (
                                    <p className="text-sm text-gray-400 py-2">연결된 워커 없음</p>
                                ) : workers.map((w) => (
                                    <div key={w.name} className="flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded-lg">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <span className="w-2 h-2 rounded-full bg-green-400 shrink-0" />
                                            <span className="text-xs text-gray-600 truncate font-mono">{w.name}</span>
                                        </div>
                                        <span className="text-xs text-gray-400 shrink-0 ml-2">
                                            활성 {w.active_tasks}개
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>

                {/* Beat 스케줄 + 즉시 실행 버튼 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <CalendarClock size={15} className="text-gray-500" /> Beat 스케줄
                    </h3>

                    {Object.keys(beatSchedule).length === 0 ? (
                        <p className="text-sm text-gray-400 py-2">Beat 스케줄 정보를 불러올 수 없습니다.</p>
                    ) : (
                        <div className="space-y-2">
                            {Object.entries(beatSchedule).map(([key, schedule]) => {
                                const info    = BEAT_LABELS[key] ?? { label: key };
                                const loading = beatLoading[key] ?? false;
                                const msg     = beatMsg[key] ?? null;
                                const canRun  = !isReadonly && !!BEAT_TRIGGER_FN[key as TriggerKey];

                                return (
                                    <div key={key} className="flex flex-col gap-1">
                                        <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                                            <div className="min-w-0">
                                                <p className="text-sm font-medium text-gray-700">{info.label}</p>
                                                <p className="text-xs text-gray-400 mt-0.5">{schedule as string}</p>
                                            </div>
                                            {canRun && (
                                                <button
                                                    onClick={() => handleBeatTrigger(key)}
                                                    disabled={loading || (key === "daily-report" && isReportBusy)}
                                                    className="ml-3 shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-white border border-gray-200 text-gray-600 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 transition disabled:opacity-50"
                                                >
                                                    {loading || (key === "daily-report" && isReportBusy)
                                                        ? <Loader2 size={11} className="animate-spin" />
                                                        : <Play size={11} />}
                                                    즉시 실행
                                                </button>
                                            )}
                                        </div>
                                        {/* 항목별 메시지 */}
                                        {msg && (
                                            <div className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg ${MSG_STYLE[msg.type]}`}>
                                                {MSG_ICON[msg.type]} {msg.text}
                                            </div>
                                        )}
                                        {/* 보고서 항목이면 reportMsg 표시 */}
                                        {key === "daily-report" && reportMsg && (
                                            <div className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg ${MSG_STYLE[reportMsg.type]}`}>
                                                {MSG_ICON[reportMsg.type]} {reportMsg.text}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {config?.last_run_at && (
                        <div className="mt-4 pt-3 border-t border-gray-100 flex justify-between text-xs text-gray-400">
                            <span>마지막 보고서 실행</span>
                            <span>{config.last_run_at.slice(0, 19)}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* ── 하단: 스케줄 설정 + Sheets 동기화 ──────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                {/* 스케줄 설정 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Clock size={15} className="text-gray-500" /> 일일 보고서 스케줄
                    </h3>
                    <div className="space-y-4">
                        <div className="flex gap-4 items-end flex-wrap">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">시 (0~23)</label>
                                <input
                                    type="number" min={0} max={23} value={hour}
                                    onChange={(e) => setHour(Number(e.target.value))}
                                    disabled={isReadonly}
                                    className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:cursor-not-allowed"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">분 (0~59)</label>
                                <input
                                    type="number" min={0} max={59} value={minute}
                                    onChange={(e) => setMinute(Number(e.target.value))}
                                    disabled={isReadonly}
                                    className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:cursor-not-allowed"
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
                                type="checkbox" id="is_active" checked={isActive}
                                onChange={(e) => setIsActive(e.target.checked)}
                                disabled={isReadonly}
                                className="w-4 h-4 rounded disabled:cursor-not-allowed"
                            />
                            <label htmlFor="is_active" className={`text-sm ${isReadonly ? "text-gray-400" : "text-gray-700"}`}>
                                스케줄 활성화
                            </label>
                        </div>

                        {!isReadonly ? (
                            <div className="space-y-2">
                                <button
                                    onClick={() => saveMutation.mutate()}
                                    disabled={saveMutation.isPending}
                                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                                >
                                    {saveMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                                    {saveMutation.isPending ? "저장 중..." : "저장"}
                                </button>
                                {saveMsg && (
                                    <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${MSG_STYLE[saveMsg.type]}`}>
                                        {MSG_ICON[saveMsg.type]} {saveMsg.text}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <p className="text-xs text-gray-400">스케줄 수정은 관리자 이상 권한이 필요합니다.</p>
                        )}
                    </div>
                </div>

                {/* Sheets → DB 동기화 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Zap size={15} className="text-yellow-500" /> Sheets → DB 동기화
                    </h3>
                    <p className="text-xs text-gray-400 mb-4">
                        Google Sheets 데이터를 MariaDB에 수동으로 즉시 반영합니다.
                        자동 동기화는 Beat 스케줄에서 실행됩니다.
                    </p>
                    <div className="space-y-2">
                        <button
                            onClick={() => handleBeatTrigger("sync-sheets-to-db")}
                            disabled={beatLoading["sync-sheets-to-db"]}
                            className="w-full flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-700 px-4 py-2.5 rounded-lg text-sm font-medium transition disabled:opacity-50"
                        >
                            {beatLoading["sync-sheets-to-db"]
                                ? <Loader2 size={14} className="animate-spin" />
                                : <RefreshCw size={14} />}
                            {beatLoading["sync-sheets-to-db"] ? "동기화 중..." : "Sheets → DB 즉시 동기화"}
                        </button>
                        {beatMsg["sync-sheets-to-db"] && (
                            <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${MSG_STYLE[beatMsg["sync-sheets-to-db"]!.type]}`}>
                                {MSG_ICON[beatMsg["sync-sheets-to-db"]!.type]}
                                {beatMsg["sync-sheets-to-db"]!.text}
                            </div>
                        )}
                    </div>
                </div>

            </div>
        </div>
    );
}