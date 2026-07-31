"""수급 데이터 공통 모델.

단위 규약 (모든 provider 는 이 단위로 정규화해서 반환한다):
  * 수량(qty)   : 주
  * 금액(value) : 백만원
  * 순매수는 양수, 순매도는 음수.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

# 시장 구분 코드 (CLI/provider 공통)
MARKETS = ("all", "kospi", "kosdaq")

MARKET_LABEL = {
    "all": "전체",
    "kospi": "코스피",
    "kosdaq": "코스닥",
}


@dataclass(frozen=True)
class FlowRow:
    """한 종목의 투자자별 순매수 현황."""

    code: str
    name: str
    market: str = "all"

    price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: float | None = None

    foreign_qty: float = 0.0
    foreign_value: float = 0.0
    inst_qty: float = 0.0
    inst_value: float = 0.0

    # 개인/기타는 제공하는 소스에서만 채워진다.
    retail_qty: float | None = None
    retail_value: float | None = None

    @property
    def both_qty(self) -> float:
        """외국인 + 기관 합산 순매수 수량."""
        return self.foreign_qty + self.inst_qty

    @property
    def both_value(self) -> float:
        """외국인 + 기관 합산 순매수 금액(백만원)."""
        return self.foreign_value + self.inst_value

    def metric(self, investor: str, metric: str) -> float:
        """정렬/표시에 쓸 값을 꺼낸다.

        investor: foreign | inst | both
        metric:   value | qty
        """
        if investor not in ("foreign", "inst", "both"):
            raise ValueError(f"unknown investor: {investor}")
        if metric not in ("value", "qty"):
            raise ValueError(f"unknown metric: {metric}")
        return float(getattr(self, f"{investor}_{metric}"))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["both_qty"] = self.both_qty
        d["both_value"] = self.both_value
        return d


@dataclass
class Snapshot:
    """특정 시점에 한 provider 가 가져온 전체 종목 수급 스냅샷."""

    rows: list[FlowRow]
    source: str
    as_of: datetime
    market: str = "all"
    #: 실시간이 아니라 지연/일별 확정치인 경우 True
    delayed: bool = False
    #: 화면에 같이 띄울 데이터 성격 설명 (예: "장중 가집계")
    note: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "as_of": self.as_of.isoformat(),
            "market": self.market,
            "delayed": self.delayed,
            "note": self.note,
            "meta": self.meta,
            "rows": [r.to_dict() for r in self.rows],
        }
