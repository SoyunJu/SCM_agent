"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getSettings, saveSettings } from "@/lib/api";
import { Loader2, Save, RotateCcw } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";

interface SettingItem {
    key: string;
    value: string;
    default: string;
    description: string;
}

// ── 라벨 ──────────────────────────────────────────────────────────────────────
const LABELS: Record<string, string> = {
    SAFETY_STOCK_DAYS:             "안전재고 보유 기준 (일)",
    SAFETY_STOCK_DEFAULT:          "안전재고 기본값 (판매 없을 때)",
    CHAT_HISTORY_DAYS:             "챗봇 히스토리 보관 일수",
    LOW_STOCK_CRITICAL_DAYS:       "긴급 경보 소진예상일 기준",
    LOW_STOCK_HIGH_DAYS:           "높음 경보 소진예상일 기준",
    LOW_STOCK_MEDIUM_DAYS:         "보통 경보 소진예상일 기준",
    SALES_SURGE_THRESHOLD:         "판매 급등 기준 (%)",
    SALES_DROP_THRESHOLD:          "판매 급락 기준 (%)",
    SHEETS_CACHE_TTL:              "Google Sheets 캐시 시간 (초)",
    ALERT_CHANNEL:                 "알림 채널",
    ALERT_MIN_SEVERITY:            "알림 최소 심각도",
    AUTO_ORDER_MIN_SEVERITY:       "자동발주 에이전트 최소 심각도",
    DATA_RETENTION_SALES_DAYS:     "매출 데이터 보존 기간 (일)",
    DATA_RETENTION_STOCK_DAYS:     "재고 스냅샷 보존 기간 (일)",
    DATA_RETENTION_ANALYSIS_HOURS: "분석 캐시 보존 기간 (시간)",
    EXCEL_MAX_SIZE_MB:             "엑셀 업로드 최대 크기 (MB)",
    DEFAULT_PAGE_SIZE:             "테이블 기본 페이지 크기",
};

// ── Select 옵션 ────────────────────────────────────────────────────────────────
const SELECT_OPTIONS: Record<string, { value: string; label: string }[]> = {
    ALERT_CHANNEL: [
        { value: "slack",  label: "Slack만" },
        { value: "email",  label: "이메일만" },
        { value: "both",   label: "Slack + 이메일" },
    ],
    ALERT_MIN_SEVERITY: [
        { value: "low",      label: "낮음 이상" },
        { value: "medium",   label: "보통 이상" },
        { value: "high",     label: "높음 이상" },
        { value: "critical", label: "긴급만" },
    ],
    AUTO_ORDER_MIN_SEVERITY: [
        { value: "low",      label: "낮음 이상 (모두)" },
        { value: "medium",   label: "보통 이상" },
        { value: "high",     label: "높음 이상 (권장)" },
        { value: "critical", label: "긴급만" },
    ],
    DEFAULT_PAGE_SIZE: [
        { value: "10",  label: "10건" },
        { value: "25",  label: "25건" },
        { value: "50",  label: "50건 (기본)" },
        { value: "100", label: "100건" },
    ],
    AUTO_ORDER_APPROVAL: [
        { value: "false", label: "승인 대기 (관리자 확인 후 처리)" },
        { value: "true",  label: "자동 승인 (즉시 처리, 주의)" },
    ],
};

// ── 그룹 정의 (title + tab 귀속) ───────────────────────────────────────────────
const GROUPS: { title: string; tab: string; keys: string[] }[] = [
    { title: "안전재고 설정",    tab: "재고",      keys: ["SAFETY_STOCK_DAYS", "SAFETY_STOCK_DEFAULT"] },
    { title: "이상 징후 임계값", tab: "이상징후",  keys: ["LOW_STOCK_CRITICAL_DAYS", "LOW_STOCK_HIGH_DAYS", "LOW_STOCK_MEDIUM_DAYS", "SALES_SURGE_THRESHOLD", "SALES_DROP_THRESHOLD"] },
    { title: "알림 설정",        tab: "알림·발주", keys: ["ALERT_CHANNEL", "ALERT_MIN_SEVERITY"] },
    { title: "발주 설정", tab: "알림·발주", keys: ["AUTO_ORDER_MIN_SEVERITY", "AUTO_ORDER_APPROVAL"] },
    { title: "시스템 설정",      tab: "시스템",    keys: ["CHAT_HISTORY_DAYS", "SHEETS_CACHE_TTL", "EXCEL_MAX_SIZE_MB", "DEFAULT_PAGE_SIZE"] },
    { title: "데이터 보존 설정", tab: "데이터",    keys: ["DATA_RETENTION_SALES_DAYS", "DATA_RETENTION_STOCK_DAYS", "DATA_RETENTION_ANALYSIS_HOURS"] },
];

const SETTING_TABS = ["전체", "재고", "이상징후", "알림·발주", "시스템", "데이터"] as const;
type SettingTab = typeof SETTING_TABS[number];

// ── 컴포넌트 ───────────────────────────────────────────────────────────────────
export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState<SettingTab>("전체");
    const [values, setValues]       = useState<Record<string, string>>({});
    const [message, setMessage]     = useState("");
    const [isReadonly, setIsReadonly] = useState(false);

    useEffect(() => {
        setIsReadonly(localStorage.getItem("user_role") === "readonly");
    }, []);

    const { data: settings = [], isLoading } = useQuery<SettingItem[]>({
        queryKey: ["settings"],
        queryFn:  () => getSettings().then((r) => r.data.items),
    });

    // 최초 로드 시 values 초기화
    useEffect(() => {
        if (settings.length === 0) return;
        const init: Record<string, string> = {};
        settings.forEach((s) => { init[s.key] = s.value; });
        setValues(init);
    }, [settings]);

    const saveMutation = useMutation({
        mutationFn: () => saveSettings(values),
        onSuccess:  () => {
            // 기본 페이지 크기를 localStorage에 캐싱 → 각 페이지 초기화 시 사용
            if (values["DEFAULT_PAGE_SIZE"]) {
                localStorage.setItem("scm_default_page_size", values["DEFAULT_PAGE_SIZE"]);
            }
            setMessage("✅ 설정이 저장되었습니다. 다음 분석부터 적용됩니다.");
            setTimeout(() => setMessage(""), 4000);
        },
        onError: () => {
            setMessage("❌ 저장에 실패했습니다.");
            setTimeout(() => setMessage(""), 4000);
        },
    });

    const handleReset = (key: string) => {
        const item = settings.find((s) => s.key === key);
        if (item) setValues((prev) => ({ ...prev, [key]: item.default }));
    };

    // 탭에 따른 그룹 필터
    const visibleGroups = activeTab === "전체"
        ? GROUPS
        : GROUPS.filter((g) => g.tab === activeTab);

    if (isLoading) return <LoadingSpinner fullPage />;

    return (
        <div className="space-y-6 max-w-2xl">
            {/* 헤더 */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">시스템 설정</h2>
                    <p className="text-gray-400 text-sm mt-1">분석 임계값 및 동작 설정 (저장 후 다음 실행부터 적용)</p>
                </div>
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
            </div>

            {message && (
                <p className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">{message}</p>
            )}

            {/* 세부 탭 */}
            <div className="flex gap-1 flex-wrap border-b border-gray-100 pb-0">
                {SETTING_TABS.map((t) => (
                    <button
                        key={t}
                        onClick={() => setActiveTab(t)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition -mb-px ${
                            activeTab === t
                                ? "border-blue-600 text-blue-600"
                                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                        }`}
                    >
                        {t}
                    </button>
                ))}
            </div>

            {/* 설정 그룹 */}
            {visibleGroups.map((group) => (
                <div key={group.title} className="bg-white rounded-xl border border-gray-100 shadow-sm">
                    <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                        <h3 className="font-semibold text-gray-700">{group.title}</h3>
                        <span className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">{group.tab}</span>
                    </div>
                    <div className="divide-y divide-gray-50">
                        {group.keys.map((key) => {
                            const item = settings.find((s) => s.key === key);
                            if (!item) return null;
                            const isSelect  = key in SELECT_OPTIONS;
                            const isChanged = values[key] !== item.default;
                            return (
                                <div key={key} className="px-6 py-4 flex items-center justify-between gap-4">
                                    <div className="flex-1">
                                        <p className="text-sm font-medium text-gray-700">{LABELS[key] ?? key}</p>
                                        <p className="text-xs text-gray-400 mt-0.5">{item.description}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {isSelect ? (
                                            <select
                                                value={values[key] ?? item.value}
                                                onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                                                disabled={isReadonly}
                                                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed"
                                            >
                                                {SELECT_OPTIONS[key].map((opt) => (
                                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                ))}
                                            </select>
                                        ) : (
                                            <input
                                                type="number"
                                                value={values[key] ?? item.value}
                                                onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                                                disabled={isReadonly}
                                                className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed"
                                            />
                                        )}
                                        {isChanged && (
                                            <>
                                                <button
                                                    onClick={() => handleReset(key)}
                                                    title={`기본값: ${item.default}`}
                                                    className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition"
                                                >
                                                    <RotateCcw size={13} />
                                                </button>
                                                <span className="text-xs text-gray-400">기본: {item.default}</span>
                                            </>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}
        </div>
    );
}
