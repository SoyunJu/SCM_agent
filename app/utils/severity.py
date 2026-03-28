"""severity 값 정규화 헬퍼.

DB / Enum / 문자열 등 어떤 형태로 오더라도 대문자 str 로 반환한다.
  norm(Severity.LOW)  → "LOW"
  norm("low")         → "LOW"
  norm("CRITICAL")    → "CRITICAL"
"""

from __future__ import annotations

# 심각도 순위 (대문자 키로 통일)
SEVERITY_RANK: dict[str, int] = {
    "LOW":      0,
    "CHECK":    0,
    "MEDIUM":   1,
    "HIGH":     2,
    "CRITICAL": 3,
}


def norm(v: object) -> str:
    """어떤 형태의 severity 값도 대문자 문자열로 정규화한다."""
    if v is None:
        return ""
    # str enum (class Severity(str, Enum)) 또는 일반 str → .upper() 호출
    if hasattr(v, "value"):
        return str(v.value).upper()     # Severity.LOW.value == "LOW"
    return str(v).upper()


def rank(v: object) -> int:
    """severity 값의 순위를 반환한다. 알 수 없으면 -1."""
    return SEVERITY_RANK.get(norm(v), -1)
