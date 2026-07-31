"""수급 상위 종목 랭킹 로직."""

from __future__ import annotations

from .models import FlowRow, Snapshot

INVESTORS = ("foreign", "inst", "both")
INVESTOR_LABEL = {
    "foreign": "외국인",
    "inst": "기관",
    "both": "외국인+기관",
}

METRICS = ("value", "qty")
METRIC_LABEL = {"value": "순매수 금액", "qty": "순매수 수량"}

SIDES = ("buy", "sell")
SIDE_LABEL = {"buy": "순매수 상위", "sell": "순매도 상위"}


def rank(
    rows: list[FlowRow],
    *,
    investor: str = "both",
    metric: str = "value",
    side: str = "buy",
    top: int = 20,
    market: str = "all",
    min_abs: float = 0.0,
    exclude_codes: set[str] | None = None,
) -> list[FlowRow]:
    """조건에 맞춰 정렬된 상위 종목을 돌려준다.

    side="buy"  -> 순매수(값이 큰 순)
    side="sell" -> 순매도(값이 작은 순, 즉 음수가 큰 순)
    min_abs 는 |지표| 하한선으로 잡음 종목을 걸러낸다.
    """
    if side not in SIDES:
        raise ValueError(f"unknown side: {side}")
    if top <= 0:
        raise ValueError("top must be positive")

    exclude_codes = exclude_codes or set()
    picked = []
    for row in rows:
        if row.code in exclude_codes:
            continue
        if market != "all" and row.market not in ("all", market):
            continue
        value = row.metric(investor, metric)
        if abs(value) < min_abs:
            continue
        # 순매수 화면엔 순매수만, 순매도 화면엔 순매도만 남긴다.
        if side == "buy" and value <= 0:
            continue
        if side == "sell" and value >= 0:
            continue
        picked.append((value, row))

    picked.sort(key=lambda pair: pair[0], reverse=(side == "buy"))
    return [row for _, row in picked[:top]]


def rank_snapshot(snapshot: Snapshot, **kwargs) -> list[FlowRow]:
    kwargs.setdefault("market", snapshot.market)
    return rank(snapshot.rows, **kwargs)


def totals(rows: list[FlowRow]) -> dict[str, float]:
    """표시된 종목들의 합계 (하단 요약줄용)."""
    return {
        "foreign_value": sum(r.foreign_value for r in rows),
        "inst_value": sum(r.inst_value for r in rows),
        "both_value": sum(r.both_value for r in rows),
        "foreign_qty": sum(r.foreign_qty for r in rows),
        "inst_qty": sum(r.inst_qty for r in rows),
        "both_qty": sum(r.both_qty for r in rows),
    }


def describe(investor: str, metric: str, side: str, market: str) -> str:
    from .models import MARKET_LABEL

    return (
        f"{MARKET_LABEL.get(market, market)} · {INVESTOR_LABEL[investor]} "
        f"{SIDE_LABEL[side]} ({METRIC_LABEL[metric]} 기준)"
    )
