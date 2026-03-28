"use client";

import { Loader2 } from "lucide-react";

interface LoadingSpinnerProps {
    size?: number;
    /** py-20 + 중앙 정렬로 페이지 전체 로딩 표시 */
    fullPage?: boolean;
    className?: string;
}

export function LoadingSpinner({ size, fullPage, className }: LoadingSpinnerProps) {
    const iconSize = size ?? (fullPage ? 32 : 28);
    return (
        <div className={`flex items-center justify-center ${fullPage ? "py-20" : "py-16"} ${className ?? ""}`}>
            <Loader2 size={iconSize} className="animate-spin text-blue-500" />
        </div>
    );
}
