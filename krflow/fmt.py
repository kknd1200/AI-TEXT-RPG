"""숫자/문자 표시 포맷 (콘솔 · 웹 공용)."""

from __future__ import annotations


def eok(value_mkrw: float | None) -> str:
    """백만원 -> 억원 문자열."""
    if value_mkrw is None:
        return "-"
    v = value_mkrw / 100.0
    if abs(v) >= 1000:
        return f"{v:+,.0f}"
    return f"{v:+,.1f}"


def qty(value: float | None) -> str:
    """주 -> 천주 단위 문자열."""
    if value is None:
        return "-"
    v = value / 1000.0
    if abs(v) >= 1000:
        return f"{v:+,.0f}"
    return f"{v:+,.1f}"


def metric_str(value: float | None, metric: str) -> str:
    return eok(value) if metric == "value" else qty(value)


def metric_unit(metric: str) -> str:
    return "억원" if metric == "value" else "천주"


def price(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}"


def pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}%"


def volume(value: float | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.0f}K"
    return f"{value:,.0f}"


def sign_class(value: float | None) -> str:
    """상승/하락 색상 클래스 (한국식: 상승=빨강, 하락=파랑)."""
    if value is None or value == 0:
        return "flat"
    return "up" if value > 0 else "down"
