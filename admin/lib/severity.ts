/** severity 값 정규화 헬퍼 (프론트엔드) */

export const SEVERITY_KOR: Record<string, string> = {
  CRITICAL: "긴급",
  HIGH:     "높음",
  MEDIUM:   "보통",
  CHECK:    "확인",
  LOW:      "낮음",
};

export const SEVERITY_COLOR: Record<string, string> = {
  CRITICAL: "text-red-600 bg-red-50",
  HIGH:     "text-orange-500 bg-orange-50",
  MEDIUM:   "text-yellow-500 bg-yellow-50",
  CHECK:    "text-blue-500 bg-blue-50",
  LOW:      "text-green-600 bg-green-50",
};

export const SEVERITY_BAR_COLOR: string[] = ["#ef4444", "#f97316", "#eab308", "#22c55e"];

/** 어떤 형태로 오든 대문자로 정규화 */
export const normSev = (v?: string | null): string => (v ?? "").toUpperCase();
