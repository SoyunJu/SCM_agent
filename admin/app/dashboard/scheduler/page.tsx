"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
    getSchedulerConfig, updateSchedulerConfig,
    getSchedulerStatus, triggerReport, getReportStatus, apiClient,
} from "@/lib/api";
import { ScheduleConfig } from "@/lib/types";
import {
    Clock, Play, RefreshCw, Save, Loader2,
    CheckCircle2, XCircle, Activity, CalendarClock,
    Zap, AlertTriangle, CheckCheck,
} from "lucide-react";

// ── Beat 스케줄 한글 라벨 ──────────────────────────────────────────────────
const BEAT_LABELS: Record<string, { label: string; desc: string }> = {
    "daily-report":      { label: "일일 보고서",      desc: "매일 00:00 자동 실행" },
    "daily-crawler":     { label: "크롤러",            desc: "매일 23:00 자동 실행" },
    "cleanup-data":      { label: "데이터 정리",       desc: "매일 02:00 자동 실행" },
    "sync-sheets-to-db": { label: "Sheets→DB 동기화", desc: "1분 주기 자동 실행"  },
};

// 보고서 생성 폴링 최대 횟수 (2초 × 150 = 5분)
const MAX_POLL = 150;

// ── 메시지 표시 유형 ──────────────────────────────────────────────────────
type MsgType = "info" | "success" | "error" | "warning";

interface Msg {
    text: string;
    type: MsgType;
}

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

    // ── 로컬 상태 ─────────────────────────────────────────────────────────
    const [hour,      setHour]      = useState(0);
    const [minute,    setMinute]    = useState(0);
    const [isActive,  setIsActive]  = useState(true);
    const [isReadonly, setIsReadonly] = useState(false);

    // 메시지 (보고서 / 동기화 / 저장 각각 독립)
    const [reportMsg, setReportMsg] = useState<Msg | null>(null);
    const [syncMsg,   setSyncMsg]   = useState<Msg | null>(null);
    const [saveMsg,   setSaveMsg]   = useState<Msg | null>(null);

    // 보고서 폴링 상태
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

    const {
        data: status,
        isLoading: statusLoading,
        refetch: refetchStatus,
    } = useQuery({
        queryKey:        ["schedulerStatus"],
        queryFn:         () => getSchedulerStatus().then((r) => r.data),
        refetchInterval: 10_000,   // 10초 자동 갱신
    });

    // ── Mutations ─────────────────────────────────────────────────────────

    const saveMutation = useMutation({
        mutationFn: () => updateSchedulerConfig({
            schedule_hour:   hour,
            schedule_minute: minute,
            timezone:        "Asia/Seoul",
            is_active:       isActive,
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

    // ── 보고서 생성 + 폴링 ─────────────────────────────────────────────────

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

                    if (statusStr === "success") {
                        setReportMsg({ text: "보고서 생성이 완료되었습니다.", type: "success" });
                    } else {
                        setReportMsg({
                            text: `보고서 생성 실패: ${error_message ?? "알 수 없는 오류"}`,
                            type: "error",
                        });
                    }
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
            if (execution_id) {
                startPolling(execution_id);
            } else {
                setReportMsg({ text: "보고서 생성이 요청되었습니다.", type: "success" });
                setTimeout(() => setReportMsg(null), 4000);
            }
        },
        onError: () => {
            setReportMsg({ text: "보고서 생성 요청에 실패했습니다.", type: "error" });
            setTimeout(() => setReportMsg(null), 4000);
        },
    });

    // ── Sheets → DB 동기화 ──────────────────────────────────────────────────

    const syncMutation = useMutation({
        mutationFn: () => apiClient.post("/scm/sheets/sync"),
        onMutate: () => {
            setSyncMsg({ text: "동기화 요청 중...", type: "info" });
        },
        onSuccess: () => {
            setSyncMsg({ text: "Sheets→DB 동기화가 시작되었습니다.", type: "success" });
            setTimeout(() => setSyncMsg(null), 5000);
        },
        onError: () => {
            setSyncMsg({ text: "동기화 요청에 실패했습니다.", type: "error" });
            setTimeout(() => setSyncMsg(null), 4000);
        },
    });

    // ── 파생 상태 ──────────────────────────────────────────────────────────
    const workers: { name: string; status: string; active_tasks: number }[] =
        status?.workers ?? [];
    const onlineCount  = workers.filter((w) => w.status === "online").length;
    const activeTasks  = workers.reduce((s, w) => s + w.active_tasks, 0);
    const beatSchedule: Record<string, string> = status?.beat_schedule ?? {};
    const hasConnError = !!status?.error;
    const isReportBusy = triggerMutation.isPending || reportPolling;

    // ── 렌더 ───────────────────────────────────────────────────────────────
    return (
        <div className="space-y-6">

            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">데이터 동기화</h2>
                    <p className="text-gray-400 text-sm mt-1">
                        데이터 동기화 | 보고서 생성
                    </p>
                </div>
                <button
                    onClick={() => refetchStatus()}
                    disabled={statusLoading}
                    title="상태 새로고침"
                    className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 transition"
                >
                    <RefreshCw size={15} className={`text-gray-500 ${statusLoading ? "animate-spin" : ""}`} />
                </button>
            </div>

            {/* ── 상단 2열: Worker 상태 + Beat 스케줄 ─────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                {/* Worker 상태 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Activity size={15} className="text-blue-500" />
                        Celery Worker
                    </h3>

                    {hasConnError ? (
                        <div className="flex items-center gap-2 text-sm text-amber-600 bg-amber-50 px-3 py-2.5 rounded-lg">
                            <AlertTriangle size={14} className="shrink-0" />
                            Worker에 연결할 수 없습니다. RabbitMQ 및 Worker 상태를 확인하세요.
                        </div>
                    ) : statusLoading ? (
                        <div className="flex items-center gap-2 text-sm text-gray-400 py-2">
                            <Loader2 size={13} className="animate-spin" /> 상태 조회 중...
                        </div>
                    ) : workers.length === 0 ? (
                        <div className="flex items-center gap-2 text-sm text-red-500 bg-red-50 px-3 py-2.5 rounded-lg">
                            <XCircle size={14} className="shrink-0" />
                            실행 중인 Worker가 없습니다.
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {/* 요약 뱃지 */}
                            <div className="flex items-center gap-2">
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
                                {activeTasks > 0 && (
                                    <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full font-medium">
                                        처리 중 {activeTasks}건
                                    </span>
                                )}
                            </div>

                            {/* Worker 목록 */}
                            <div className="space-y-1.5">
                                {workers.map((w) => (
                                    <div key={w.name}
                                         className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <span className={`w-2 h-2 rounded-full shrink-0 ${
                                                w.status === "online" ? "bg-green-500" : "bg-red-400"
                                            }`} />
                                            <span className="text-xs text-gray-600 font-mono truncate">
                                                {w.name.split("@")[0]}
                                            </span>
                                        </div>
                                        <span className="text-xs shrink-0 ml-2">
                                            {w.active_tasks > 0
                                                ? <span className="text-blue-600 font-medium">처리 중 {w.active_tasks}건</span>
                                                : <span className="text-gray-400">대기 중</span>}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Beat 스케줄 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <CalendarClock size={15} className="text-purple-500" />
                        Beat 스케줄
                    </h3>

                    {Object.keys(beatSchedule).length === 0 ? (
                        <p className="text-sm text-gray-400 py-2">Beat 스케줄 정보를 불러올 수 없습니다.</p>
                    ) : (
                        <div className="space-y-1.5">
                            {Object.entries(beatSchedule).map(([key, schedule]) => {
                                const info = BEAT_LABELS[key] ?? { label: key, desc: schedule };
                                return (
                                    <div key={key}
                                         className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-gray-700">{info.label}</p>
                                            <p className="text-xs text-gray-400 mt-0.5">{info.desc}</p>
                                        </div>
                                        <span className="text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full shrink-0 ml-2 font-mono whitespace-nowrap">
                                            {schedule}
                                        </span>
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

            {/* ── 하단 2열: 스케줄 설정 + 즉시 실행 ──────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                {/* 스케줄 설정 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Clock size={15} className="text-gray-500" />
                        일일 보고서 스케줄
                    </h3>

                    <div className="space-y-4">
                        <div className="flex gap-4 items-end flex-wrap">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">시 (0~23)</label>
                                <input
                                    type="number" min={0} max={23}
                                    value={hour}
                                    onChange={(e) => setHour(Number(e.target.value))}
                                    disabled={isReadonly}
                                    className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:cursor-not-allowed"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">분 (0~59)</label>
                                <input
                                    type="number" min={0} max={59}
                                    value={minute}
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
                                type="checkbox" id="is_active"
                                checked={isActive}
                                onChange={(e) => setIsActive(e.target.checked)}
                                disabled={isReadonly}
                                className="w-4 h-4 rounded disabled:cursor-not-allowed"
                            />
                            <label htmlFor="is_active" className={`text-sm ${isReadonly ? "text-gray-400" : "text-gray-700"}`}>
                                스케줄 활성화
                            </label>
                        </div>

                        {/* 저장 버튼 + 메시지 — 관리자만 */}
                        {!isReadonly ? (
                            <div className="space-y-2">
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
                                {saveMsg && (
                                    <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${MSG_STYLE[saveMsg.type]}`}>
                                        {MSG_ICON[saveMsg.type]}
                                        {saveMsg.text}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <p className="text-xs text-gray-400">
                                스케줄 수정은 관리자 이상 권한이 필요합니다.
                            </p>
                        )}
                    </div>
                </div>

                {/* 즉시 실행 — 항상 노출, 권한별 분기 */}
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                        <Zap size={15} className="text-yellow-500" />
                        즉시 실행
                    </h3>

                    <div className="space-y-3">

                        {/* 보고서 즉시 생성 — 관리자만 */}
                        {!isReadonly ? (
                            <div className="space-y-2">
                                <button
                                    onClick={() => triggerMutation.mutate()}
                                    disabled={isReportBusy}
                                    className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition disabled:opacity-60"
                                >
                                    {isReportBusy
                                        ? <Loader2 size={14} className="animate-spin" />
                                        : <Play size={14} />}
                                    {reportPolling
                                        ? "생성 중..."
                                        : triggerMutation.isPending
                                            ? "요청 중..."
                                            : "보고서 즉시 생성"}
                                </button>
                                {/* 보고서 진행 상태 메시지 */}
                                {reportMsg && (
                                    <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${MSG_STYLE[reportMsg.type]}`}>
                                        {MSG_ICON[reportMsg.type]}
                                        {reportMsg.text}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-xs text-gray-400 bg-gray-50 px-3 py-2.5 rounded-lg">
                                보고서 생성은 관리자 이상 권한이 필요합니다.
                            </div>
                        )}

                        {/* 구분선 */}
                        <div className="border-t border-gray-100" />

                        {/* Sheets → DB 동기화 — 권한 무관 항상 노출 */}
                        <div className="space-y-2">
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
                            {/* 동기화 상태 메시지 */}
                            {syncMsg && (
                                <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${MSG_STYLE[syncMsg.type]}`}>
                                    {MSG_ICON[syncMsg.type]}
                                    {syncMsg.text}
                                </div>
                            )}
                        </div>

                    </div>
                </div>
            </div>

        </div>
    );
}