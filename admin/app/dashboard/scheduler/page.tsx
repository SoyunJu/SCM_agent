"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSchedulerConfig, updateSchedulerConfig, getSchedulerStatus, triggerReport, apiClient } from "@/lib/api";
import { ScheduleConfig } from "@/lib/types";
import { Clock, Play, RefreshCw, Save, Loader2 } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

export default function SchedulerPage() {
    const qc = useQueryClient();

    const [hour, setHour]         = useState(0);
    const [minute, setMinute]     = useState(0);
    const [isActive, setIsActive] = useState(true);
    const [message, setMessage]   = useState("");
    const [isReadonly, setIsReadonly] = useState(false);

    useEffect(() => {
        setIsReadonly(localStorage.getItem("user_role") === "readonly");
    }, []);

    const flash = (m: string) => {
        setMessage(m);
        setTimeout(() => setMessage(""), 4000);
    };

    const { data: config, isLoading: configLoading } = useQuery<ScheduleConfig>({
        queryKey: ["schedulerConfig"],
        queryFn:  () => getSchedulerConfig().then((r) => r.data as ScheduleConfig),
    });

    // 초기값 세팅
    useEffect(() => {
        if (!config) return;
        setHour(config.schedule_hour);
        setMinute(config.schedule_minute);
        setIsActive(config.is_active);
    }, [config]);

    const { data: status, isLoading: statusLoading } = useQuery({
        queryKey: ["schedulerStatus"],
        queryFn:  () => getSchedulerStatus().then((r) => r.data),
    });

    const saveMutation = useMutation({
        mutationFn: () => updateSchedulerConfig({ schedule_hour: hour, schedule_minute: minute, timezone: "Asia/Seoul", is_active: isActive }),
        onSuccess:  () => {
            flash("✅ 스케줄이 업데이트되었습니다.");
            qc.invalidateQueries({ queryKey: ["schedulerStatus"] });
        },
        onError: () => flash("❌ 스케줄 업데이트에 실패했습니다."),
    });

    const triggerMutation = useMutation({
        mutationFn: () => triggerReport(),
        onSuccess:  () => flash("✅ 보고서 생성이 시작되었습니다. Slack을 확인하세요."),
        onError:    () => flash("❌ 실행에 실패했습니다."),
    });

    const syncMutation = useMutation({
        mutationFn: () => apiClient.post("/scm/sheets/sync"),
        onSuccess:  () => flash("✅ 데이터 동기화가 시작되었습니다."),
        onError:    () => flash("❌ 동기화 실패"),
    });

    if (configLoading || statusLoading) return <LoadingSpinner fullPage />;

    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h2 className="text-2xl font-bold text-gray-800">스케줄 관리</h2>
                <p className="text-gray-400 text-sm mt-1">자동 보고서 생성 스케줄 설정</p>
            </div>

            {message && (
                <p className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">{message}</p>
            )}

            {/* 현재 상태 */}
            {status && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                        <Clock size={15} /> 스케줄러 상태
                    </h3>
                    <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                            <span className="text-gray-500">실행 상태</span>
                            <span className={`font-medium ${status.running ? "text-green-600" : "text-red-500"}`}>
                                {status.running ? "🟢 실행 중" : "🔴 중지"}
                            </span>
                        </div>
                        {status.jobs?.[0] && (
                            <div className="flex justify-between">
                                <span className="text-gray-500">다음 실행</span>
                                <span className="text-gray-700 font-medium">{status.jobs[0].next_run?.slice(0, 19)}</span>
                            </div>
                        )}
                        {config?.last_run_at && (
                            <div className="flex justify-between">
                                <span className="text-gray-500">마지막 실행</span>
                                <span className="text-gray-700">{config.last_run_at.slice(0, 19)}</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 스케줄 설정 */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <h3 className="font-semibold text-gray-700 mb-4">스케줄 설정</h3>
                <div className="space-y-4">
                    <div className="flex gap-4 items-end">
                        <div>
                            <label className="block text-xs text-gray-500 mb-1">시 (0~23)</label>
                            <input
                                type="number" min={0} max={23}
                                value={hour}
                                onChange={(e) => setHour(Number(e.target.value))}
                                className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <div>
                            <label className="block text-xs text-gray-500 mb-1">분 (0~59)</label>
                            <input
                                type="number" min={0} max={59}
                                value={minute}
                                onChange={(e) => setMinute(Number(e.target.value))}
                                className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <p className="text-sm text-gray-500 pb-2">
                            → 매일 <strong>{String(hour).padStart(2, "0")}:{String(minute).padStart(2, "0")}</strong> 실행
                        </p>
                    </div>

                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox" id="is_active"
                            checked={isActive}
                            onChange={(e) => setIsActive(e.target.checked)}
                            className="w-4 h-4 rounded"
                        />
                        <label htmlFor="is_active" className="text-sm text-gray-700">스케줄 활성화</label>
                    </div>

                    <div className="flex gap-3 pt-2">
                        {!isReadonly && (
                            <button
                                onClick={() => saveMutation.mutate()}
                                disabled={saveMutation.isPending}
                                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                            >
                                {saveMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                                {saveMutation.isPending ? "저장 중..." : "저장"}
                            </button>
                        )}
                        {!isReadonly && (
                            <button
                                onClick={() => triggerMutation.mutate()}
                                disabled={triggerMutation.isPending}
                                className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                            >
                                {triggerMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                                {triggerMutation.isPending ? "실행 중..." : "보고서 즉시 생성"}
                            </button>
                        )}
                        <button
                            onClick={() => syncMutation.mutate()}
                            disabled={syncMutation.isPending}
                            className="flex items-center gap-2 bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                        >
                            <RefreshCw size={14} className={syncMutation.isPending ? "animate-spin" : ""} />
                            {syncMutation.isPending ? "동기화 중..." : "데이터만 동기화"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
