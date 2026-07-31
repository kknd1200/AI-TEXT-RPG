"""네이버 금융 '투자자별 매매상위' 스크래핑 provider.

앱키 없이 쓸 수 있는 무료 소스. 네이버는 투자자별 *매수 상위* 와 *매도 상위*
를 따로 제공하므로, 두 표를 종목코드로 조인해 순매수(매수-매도) 를 계산한다.

  https://finance.naver.com/sise/sise_deal_rank.naver
      ?investor_gubun=1000&type=buy&sosok=01&page=1

  investor_gubun : 1000=기관, 9000=외국인
  type           : buy | sell
  sosok          : 01=코스피, 02=코스닥

주의: 공식 API 가 아니라 HTML 구조에 의존한다. 네이버가 페이지를 바꾸면
`--debug-dump` 로 원본 HTML 을 받아 파서를 조정해야 한다. 상위 N개 표만
제공하므로 전체 종목이 아닌 '상위권'만 커버한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from ..config import Config, load_config
from ..market import now_kst
from ..models import FlowRow, Snapshot
from .base import Provider, ProviderError

URL = "https://finance.naver.com/sise/sise_deal_rank.naver"
REFERER = "https://finance.naver.com/sise/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

INVESTOR_GUBUN = {"inst": "1000", "foreign": "9000"}
SOSOK = {"kospi": "01", "kosdaq": "02"}
SOSOK_MARKET = {"01": "kospi", "02": "kosdaq"}

CODE_RE = re.compile(r"code=(\d{6})")
NUM_RE = re.compile(r"-?[\d,]+(?:\.\d+)?")

#: 네이버 매매상위 표의 거래대금 열은 백만원 단위로 표기된다.
VALUE_UNIT_MKRW = 1.0


@dataclass
class _Leg:
    """한 종목의 매수 또는 매도 한쪽 집계."""

    code: str
    name: str
    qty: float
    value: float


def _parse_number(text: str) -> float | None:
    match = NUM_RE.search(text.replace("\xa0", " "))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_deal_rank(html: str) -> list[_Leg]:
    """매매상위 HTML 한 페이지에서 (종목, 거래량, 거래대금) 을 뽑는다."""
    soup = BeautifulSoup(html, "html.parser")
    legs: dict[str, _Leg] = {}

    for tr in soup.find_all("tr"):
        link = tr.find("a", href=CODE_RE)
        if link is None:
            continue
        match = CODE_RE.search(link.get("href", ""))
        if not match:
            continue
        code = match.group(1)
        name = link.get_text(strip=True)
        if not name:
            continue

        # 종목명 셀 '이후'의 숫자 셀만 모은다. 앞쪽 순위 열(<td class="no">1</td>)
        # 을 거래량으로 오인하지 않기 위한 처리.
        numbers: list[float] = []
        seen_link = False
        for td in tr.find_all("td"):
            if not seen_link:
                if td.find("a", href=CODE_RE) is not None:
                    seen_link = True
                continue
            value = _parse_number(td.get_text(strip=True))
            if value is not None:
                numbers.append(value)

        if not numbers:
            continue
        qty = numbers[0]
        value = numbers[1] if len(numbers) > 1 else 0.0
        # 같은 종목이 중복돼 나오면 첫 행(상위)을 유지한다.
        legs.setdefault(code, _Leg(code=code, name=name, qty=qty, value=value * VALUE_UNIT_MKRW))

    return list(legs.values())


def merge_legs(buys: list[_Leg], sells: list[_Leg]) -> dict[str, tuple[str, float, float]]:
    """매수/매도 표를 조인해 code -> (name, 순매수수량, 순매수금액)."""
    merged: dict[str, tuple[str, float, float]] = {}
    names = {leg.code: leg.name for leg in list(sells) + list(buys)}
    codes = {leg.code for leg in buys} | {leg.code for leg in sells}
    buy_map = {leg.code: leg for leg in buys}
    sell_map = {leg.code: leg for leg in sells}

    for code in codes:
        buy = buy_map.get(code)
        sell = sell_map.get(code)
        net_qty = (buy.qty if buy else 0.0) - (sell.qty if sell else 0.0)
        net_value = (buy.value if buy else 0.0) - (sell.value if sell else 0.0)
        merged[code] = (names.get(code, code), net_qty, net_value)
    return merged


class NaverProvider(Provider):
    name = "naver"
    label = "네이버 금융 (투자자별 매매상위)"
    delayed = False
    note = "장중 갱신 · 매수/매도 상위표 조인으로 계산한 근사 순매수"
    min_interval = 15.0  # 스크래핑이므로 과도한 폴링 금지

    def __init__(self, config: Config | None = None, session: requests.Session | None = None) -> None:
        self.config = config or load_config()
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Referer": REFERER})
        self.last_html: dict[str, str] = {}

    def _get(self, investor: str, side: str, sosok: str) -> str:
        params = {
            "investor_gubun": INVESTOR_GUBUN[investor],
            "type": side,
            "sosok": sosok,
            "page": "1",
        }
        try:
            resp = self.session.get(URL, params=params, timeout=self.config.request_timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"네이버 금융 요청 실패: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"네이버 금융 응답 오류 (HTTP {resp.status_code})")
        resp.encoding = resp.apparent_encoding or "euc-kr"
        html = resp.text
        self.last_html[f"{investor}_{side}_{sosok}"] = html
        return html

    def _fetch_sosok(self, sosok: str) -> dict[str, FlowRow]:
        market = SOSOK_MARKET[sosok]
        per_investor: dict[str, dict[str, tuple[str, float, float]]] = {}
        for investor in ("foreign", "inst"):
            buys = parse_deal_rank(self._get(investor, "buy", sosok))
            sells = parse_deal_rank(self._get(investor, "sell", sosok))
            per_investor[investor] = merge_legs(buys, sells)

        codes = set(per_investor["foreign"]) | set(per_investor["inst"])
        rows: dict[str, FlowRow] = {}
        for code in codes:
            f_name, f_qty, f_value = per_investor["foreign"].get(code, (code, 0.0, 0.0))
            i_name, i_qty, i_value = per_investor["inst"].get(code, (code, 0.0, 0.0))
            rows[code] = FlowRow(
                code=code,
                name=f_name if f_name != code else i_name,
                market=market,
                foreign_qty=f_qty,
                foreign_value=f_value,
                inst_qty=i_qty,
                inst_value=i_value,
            )
        return rows

    def fetch(self, market: str = "all") -> Snapshot:
        if market == "all":
            targets = list(SOSOK.values())
        elif market in SOSOK:
            targets = [SOSOK[market]]
        else:
            raise ProviderError(f"지원하지 않는 시장 구분입니다: {market}")

        rows: dict[str, FlowRow] = {}
        for sosok in targets:
            rows.update(self._fetch_sosok(sosok))

        if not rows:
            raise ProviderError(
                "네이버 금융에서 종목을 파싱하지 못했습니다. 휴장일이거나 "
                "페이지 구조가 바뀌었을 수 있습니다 (--debug-dump 로 확인)."
            )

        return Snapshot(
            rows=list(rows.values()),
            source=self.name,
            as_of=now_kst(),
            market=market,
            delayed=self.delayed,
            note=self.note,
            meta={"pages": len(targets) * 4},
        )

    def close(self) -> None:
        self.session.close()
