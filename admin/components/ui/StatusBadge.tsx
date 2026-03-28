"use client";

// ── severity (이상 징후 심각도) ──
const SEVERITY_CLS: Record<string, string> = {
    critical: "text-red-600 bg-red-50 border-red-200",
    high:     "text-orange-500 bg-orange-50 border-orange-200",
    medium:   "text-yellow-600 bg-yellow-50 border-yellow-200",
    check:    "text-blue-500 bg-blue-50 border-blue-200",
    low:      "text-green-600 bg-green-50 border-green-200",
};
const SEVERITY_KOR: Record<string, string> = {
    critical: "긴급", high: "높음", medium: "보통", check: "확인", low: "낮음",
};

interface StatusBadgeProps {
    value: string;
    /** severity: 이상 징후 심각도 스타일 적용, plain: className만 적용 */
    variant?: "severity" | "plain";
    className?: string;
    /** label 오버라이드 (variant=plain 에서 주로 사용) */
    label?: string;
}

export function StatusBadge({ value, variant = "plain", className, label }: StatusBadgeProps) {
    if (variant === "severity") {
        const cls   = SEVERITY_CLS[value] ?? "bg-gray-100 text-gray-600 border-gray-200";
        const text  = label ?? SEVERITY_KOR[value] ?? value;
        return (
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${cls} ${className ?? ""}`}>
                {text}
            </span>
        );
    }

    return (
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${className ?? ""}`}>
            {label ?? value}
        </span>
    );
}
