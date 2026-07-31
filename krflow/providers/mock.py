"""오프라인 데모/테스트용 provider.

네트워크나 앱키 없이 UI·랭킹 로직을 확인할 때 쓴다.
매 호출마다 값이 조금씩 흔들려 실시간 갱신처럼 보인다.
"""

from __future__ import annotations

import random

from ..market import now_kst
from ..models import FlowRow, Snapshot
from .base import Provider

UNIVERSE = [
    ("005930", "삼성전자", "kospi", 74_500),
    ("000660", "SK하이닉스", "kospi", 198_000),
    ("373220", "LG에너지솔루션", "kospi", 402_000),
    ("207940", "삼성바이오로직스", "kospi", 812_000),
    ("005380", "현대차", "kospi", 241_000),
    ("000270", "기아", "kospi", 112_500),
    ("068270", "셀트리온", "kospi", 178_000),
    ("035420", "NAVER", "kospi", 186_500),
    ("035720", "카카오", "kospi", 44_150),
    ("105560", "KB금융", "kospi", 76_800),
    ("055550", "신한지주", "kospi", 51_200),
    ("012330", "현대모비스", "kospi", 236_500),
    ("051910", "LG화학", "kospi", 372_000),
    ("006400", "삼성SDI", "kospi", 358_000),
    ("028260", "삼성물산", "kospi", 148_000),
    ("247540", "에코프로비엠", "kosdaq", 187_300),
    ("086520", "에코프로", "kosdaq", 92_400),
    ("091990", "셀트리온헬스케어", "kosdaq", 71_800),
    ("196170", "알테오젠", "kosdaq", 312_500),
    ("328130", "루닛", "kosdaq", 58_900),
    ("058470", "리노공업", "kosdaq", 214_000),
    ("357780", "솔브레인", "kosdaq", 268_000),
]


class MockProvider(Provider):
    name = "mock"
    label = "데모 데이터 (오프라인)"
    delayed = True
    note = "가상 데이터입니다. 실제 시장과 무관합니다."
    min_interval = 0.5

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def fetch(self, market: str = "all") -> Snapshot:
        rows = []
        for code, name, mkt, base_price in UNIVERSE:
            if market != "all" and mkt != market:
                continue
            rnd = self._random
            change_pct = rnd.uniform(-4.5, 4.5)
            price = round(base_price * (1 + change_pct / 100), -1)
            scale = base_price / 1000

            foreign_qty = rnd.gauss(0, 120_000)
            inst_qty = rnd.gauss(0, 90_000)
            rows.append(
                FlowRow(
                    code=code,
                    name=name,
                    market=mkt,
                    price=price,
                    change=price - base_price,
                    change_pct=change_pct,
                    volume=abs(rnd.gauss(3_000_000, 1_500_000)),
                    foreign_qty=foreign_qty,
                    foreign_value=foreign_qty * scale / 1000,
                    inst_qty=inst_qty,
                    inst_value=inst_qty * scale / 1000,
                )
            )

        return Snapshot(
            rows=rows,
            source=self.name,
            as_of=now_kst(),
            market=market,
            delayed=self.delayed,
            note=self.note,
        )
