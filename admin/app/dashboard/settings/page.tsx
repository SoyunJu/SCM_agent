"use client";

import { useEffect, useState } from "react";
import { getSettings, saveSettings } from "@/lib/api";
import { Loader2, Save, RotateCcw } from "lucide-react";

interface SettingItem {
    key: string;
    value: string;
    default: string;
    description: string;
}

const LABELS: Record<string, string> = {
    SAFETY_STOCK_DAYS:       "안전재고 보유 기준 (일)",
    SAFETY_STOCK_DEFAULT:    "안전재고 기본값 (판매 없을 때)",
    CHAT_HISTORY_DAYS:       "챗봇 히스토리 보관 일수",
    LOW_STOCK_CRITICAL_DAYS: "긴급 경보 소진예상일 기준",
    LOW_STOCK_HIGH_DAYS:     "높음 경보 소진예상일 기준",
    LOW_STOCK_MEDIUM_DAYS:   "보통 경보 소진예상일 기준",
    SALES_SURGE_THRESHOLD:   "판매 급등 기준 (%)",
    SALES_DROP_THRESHOLD:    "판매 급락 기준 (%)",
    SHEETS_CACHE_TTL:        "Google Sheets 캐시 시간 (초)",
};

const GROUPS = [
    {
        title: "안전재고 설정",
        keys: ["SAFETY_STOCK_DAYS", "SAFETY_STOCK_DEFAULT"],
    },
    {
        title: "이상 징후 임계값",
        keys: ["LOW_STOCK_CRITICAL_DAYS", "LOW_STOCK_HIGH_DAYS", "LOW_STOCK_MEDIUM_DAYS",
            "SALES_SURGE_THRESHOLD", "SALES_DROP_THRESHOLD"],
    },
    {
        title: "시스템 설정",
        keys: ["CHAT_HISTORY_DAYS", "SHEETS_CACHE_TTL"],
    },
];

export default function SettingsPage() {
    const [settings, setSettings] = useState<SettingItem[]>([]);
    const [values, setValues]     = useState<Record<string, string>>({});
    const [loading, setLoading]   = useState(true);
    const [saving, setSaving]     = useState(false);
    const [message, setMessage]   = useState("");

    useEffect(() => {
        getSettings().then((res) => {
            const items: SettingItem[] = res.data.items;
            setSettings(items);
            const init: Record<string, string> = {};
            items.forEach((s) => { init[s.key] = s.value; });
            setValues(init);
        }).finally(() => setLoading(false));
    }, []);

    const handleSave = async () => {
        setSaving(true);
        setMessage("");
        try {
            await saveSettings(values);
            setMessage("✅ 설정이 저장되었습니다. 다음 분석부터 적용됩니다.");
        } catch {
            setMessage("❌ 저장에 실패했습니다.");
        } finally {
            setSaving(false);
            setTimeout(() => setMessage(""), 4000);
        }
    };

    const handleReset = (key: string) => {
        const item = settings.find((s) => s.key === key);
        if (item) setValues((prev) => ({ ...prev, [key]: item.default }));
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 size={32} className="animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-2xl">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">시스템 설정</h2>
                    <p className="text-gray-400 text-sm mt-1">분석 임계값 및 동작 설정 (저장 후 다음 실행부터 적용)</p>
                </div>
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50"
                >
                    {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                    {saving ? "저장 중..." : "저장"}
                </button>
            </div>

            {message && (
                <p className="text-sm text-gray-600 bg-gray-100 px-4 py-2 rounded-lg">{message}</p>
            )}

            {GROUPS.map((group) => (
                <div key={group.title} className="bg-white rounded-xl border border-gray-100 shadow-sm">
                    <div className="px-6 py-4 border-b border-gray-100">
                        <h3 className="font-semibold text-gray-700">{group.title}</h3>
                    </div>
                    <div className="divide-y divide-gray-50">
                        {group.keys.map((key) => {
                            const item = settings.find((s) => s.key === key);
                            if (!item) return null;
                            return (
                                <div key={key} className="px-6 py-4 flex items-center justify-between gap-4">
                                    <div className="flex-1">
                                        <p className="text-sm font-medium text-gray-700">{LABELS[key] ?? key}</p>
                                        <p className="text-xs text-gray-400 mt-0.5">{item.description}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="number"
                                            value={values[key] ?? item.value}
                                            onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                                            className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-blue-400"
                                        />
                                        {values[key] !== item.default && (
                                            <button
                                                onClick={() => handleReset(key)}
                                                title={`기본값: ${item.default}`}
                                                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition"
                                            >
                                                <RotateCcw size={13} />
                                            </button>
                                        )}
                                        {values[key] !== item.default && (
                                            <span className="text-xs text-gray-400">기본: {item.default}</span>
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
