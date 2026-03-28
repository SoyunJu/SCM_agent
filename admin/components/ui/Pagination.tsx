"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
    page: number;
    totalPages: number;
    onPageChange: (page: number) => void;
    disabled?: boolean;
    className?: string;
}

export function Pagination({ page, totalPages, onPageChange, disabled, className }: PaginationProps) {
    if (totalPages <= 1) return null;

    const pages = Array.from({ length: totalPages }, (_, i) => i + 1)
        .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
        .reduce<(number | "…")[]>((acc, p, idx, arr) => {
            if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("…");
            acc.push(p);
            return acc;
        }, []);

    return (
        <div className={`flex items-center gap-1 ${className ?? ""}`}>
            <button
                onClick={() => onPageChange(Math.max(1, page - 1))}
                disabled={page === 1 || disabled}
                className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 transition"
            >
                <ChevronLeft size={14} />
            </button>
            {pages.map((p, i) =>
                p === "…" ? (
                    <span key={`e-${i}`} className="px-1 text-gray-400 text-xs">…</span>
                ) : (
                    <button
                        key={p}
                        onClick={() => onPageChange(p as number)}
                        disabled={disabled}
                        className={`min-w-[30px] h-[30px] rounded-lg text-xs font-medium transition ${
                            page === p
                                ? "bg-blue-600 text-white"
                                : "border border-gray-200 text-gray-600 hover:bg-gray-50"
                        }`}
                    >
                        {p}
                    </button>
                )
            )}
            <button
                onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                disabled={page === totalPages || disabled}
                className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-40 transition"
            >
                <ChevronRight size={14} />
            </button>
        </div>
    );
}
