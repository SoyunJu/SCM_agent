"use client";

import { useEffect, useState } from "react";
import { getSchedulerConfig, updateSchedulerConfig, getSchedulerStatus, triggerReport } from "@/lib/api";
import { ScheduleConfig } from "@/lib/types";
import { Clock, Play, Save } from "lucide-react";

export default function SchedulerPage() {
    const [config, setConfig]         = useState<ScheduleConfig | null>(null);
    const [status, setStatus]         = useState<any>(null);
    const [hour, setHour]             = useState(0);
    const [minute, setMinute]         = useState(0);
    const [isActive, setIsActive]     = useState(true);
    const [saving, setSaving]         = useState(false);
    const [triggering, setTriggering] = useState(false);
    const [message, setMessage]       = useState("");

    useEffect(() => {
        Promise.all([getSchedulerConfig(), getSchedulerStatus()]).then(([cfg, sts]) => {
            const c = cfg.data;
            setConfig(c);
            setHour(c.schedule_hour);
            setMinute(c.schedule_minute);
            setIsActive(c.is_active);
            setStatus(sts.data);
        });
    }, []);

    const handleSave = async () => {
        setSaving(true);
        setMessage("");
        try {
            await updateSchedulerConfig({
                schedule_hour: hour,
                schedule_minute: minute,
                timezone: "Asia/Seoul",
                is_active: isActive,
            });
            setMessage("✅ 스케줄이 업데이트되었습니다.");
            const res = await getSchedulerStatus();
            setStatus(res.data);
        } catch {
            setMessage("❌ 스케줄 업데이트에 실패했습니다.");
        } finally {
            setSaving(false);
        }
    };

    const handleTrigger = async () => {
        setTriggering(true);
        setMessage("");
        try {
            await triggerReport();
            setMessage("✅ 보고서 생성이 시작되었습니다. Slack을 확인하세요.");
        } catch {
            setMessage("❌ 실행에 실패했습니다.");
        } finally {
            setTriggering(false);
        }
    };

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
                        <Clock size={15} />
                        스케줄러 상태
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
                            → 매일 <strong>{String(hour).padStart(2,"0")}:{String(minute).padStart(2,"0")}</strong> 실행
                        </p>
                    </div>

                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="is_active"
                            checked={isActive}
                            onChange={(e) => setIsActive(e.target.checked)}
                            className="w-4 h-4 rounded"
                        />
                        <label htmlFor="is_active" className="text-sm text-gray-700">스케줄 활성화</label>
                    </div>

                    <div className="flex gap-3 pt-2">
                        <button
                            onClick={handleSave}
                            disabled={saving}
                            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                        >
                            <Save size={14} />
                            {saving ? "저장 중..." : "저장"}
                        </button>
                        <button
                            onClick={handleTrigger}
                            disabled={triggering}
                            className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                        >
                            <Play size={14} />
                            {triggering ? "실행 중..." : "즉시 실행"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}