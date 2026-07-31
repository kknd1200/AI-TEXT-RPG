"""KRX(pykrx) provider — 일별 확정 수급.

장 마감 후 확정치를 확인하거나, 실시간 소스 값을 검증할 때 쓴다.
실시간이 아니므로 `delayed=True`.

  pip install "krflow[krx]"   또는   pip install pykrx
"""

from __future__ import annotations

import importlib.util
from datetime import datetime

from ..market import last_business_day, now_kst, yyyymmdd
from ..models import FlowRow, Snapshot
from .base import Provider, ProviderError


def pykrx_installed() -> bool:
    return importlib.util.find_spec("pykrx") is not None

MARKET_ARG = {"all": "ALL", "kospi": "KOSPI", "kosdaq": "KOSDAQ"}

# pykrx 가 돌려주는 컬럼명 후보 (버전에 따라 표기가 조금씩 다르다)
QTY_COLS = ("순매수거래량", "순매수수량")
VALUE_COLS = ("순매수거래대금", "순매수대금")
NAME_COLS = ("종목명",)


def _column(df, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in df.columns:
            return name
    return None


class KrxProvider(Provider):
    name = "krx"
    label = "KRX 일별 확정 수급 (pykrx)"
    delayed = True
    note = "거래소 확정치 · 실시간 아님(해당 영업일 종가 기준)"
    min_interval = 60.0

    def __init__(self, date: str | None = None) -> None:
        if not pykrx_installed():
            raise ProviderError(
                "pykrx 가 설치되어 있지 않습니다. `pip install pykrx` 로 설치하세요."
            )
        self.date = date or yyyymmdd(last_business_day())

    def fetch(self, market: str = "all") -> Snapshot:
        from pykrx import stock

        arg = MARKET_ARG.get(market)
        if arg is None:
            raise ProviderError(f"지원하지 않는 시장 구분입니다: {market}")

        try:
            foreign = stock.get_market_net_purchases_of_equities(
                self.date, self.date, arg, "외국인"
            )
            inst = stock.get_market_net_purchases_of_equities(
                self.date, self.date, arg, "기관합계"
            )
        except Exception as exc:  # pykrx 는 다양한 예외를 던진다
            raise ProviderError(f"KRX 조회 실패: {exc}") from exc

        rows = build_rows(foreign, inst, market)
        if not rows:
            raise ProviderError(
                f"{self.date} 자 KRX 수급 데이터가 비어 있습니다 (휴장일일 수 있음)."
            )

        return Snapshot(
            rows=rows,
            source=self.name,
            as_of=_as_of(self.date),
            market=market,
            delayed=self.delayed,
            note=f"{self.date} 확정치 · {self.note}",
            meta={"date": self.date},
        )


def build_rows(foreign_df, inst_df, market: str) -> list[FlowRow]:
    """pykrx DataFrame 두 장을 FlowRow 로 합친다 (금액 원 -> 백만원)."""
    f_qty_col = _column(foreign_df, QTY_COLS)
    f_val_col = _column(foreign_df, VALUE_COLS)
    i_qty_col = _column(inst_df, QTY_COLS)
    i_val_col = _column(inst_df, VALUE_COLS)
    name_col = _column(foreign_df, NAME_COLS) or _column(inst_df, NAME_COLS)

    codes = set(foreign_df.index) | set(inst_df.index)
    rows: list[FlowRow] = []
    for code in codes:
        f = foreign_df.loc[code] if code in foreign_df.index else None
        i = inst_df.loc[code] if code in inst_df.index else None
        source = f if f is not None else i

        name = str(source[name_col]) if name_col and source is not None else str(code)
        rows.append(
            FlowRow(
                code=str(code),
                name=name,
                market=market,
                foreign_qty=float(f[f_qty_col]) if f is not None and f_qty_col else 0.0,
                foreign_value=(float(f[f_val_col]) / 1e6) if f is not None and f_val_col else 0.0,
                inst_qty=float(i[i_qty_col]) if i is not None and i_qty_col else 0.0,
                inst_value=(float(i[i_val_col]) / 1e6) if i is not None and i_val_col else 0.0,
            )
        )
    return rows


def _as_of(date: str) -> datetime:
    try:
        parsed = datetime.strptime(date, "%Y%m%d")
    except ValueError:
        return now_kst()
    return parsed.replace(hour=15, minute=30, tzinfo=now_kst().tzinfo)
