import pytest

from krflow.config import Config
from krflow.providers.base import ProviderError
from krflow.providers.naver import NaverProvider, merge_legs, parse_deal_rank

# 네이버 금융 '투자자별 매매상위' 표 구조를 본뜬 픽스처
BUY_HTML = """
<html><body>
<table class="type_2">
  <tr><th>종목명</th><th>거래량</th><th>거래대금</th></tr>
  <tr><td class="no">1</td>
      <td><a href="/item/main.naver?code=005930">삼성전자</a></td>
      <td>1,500,000</td><td>111,750</td></tr>
  <tr><td class="no">2</td>
      <td><a href="/item/main.naver?code=000660">SK하이닉스</a></td>
      <td>300,000</td><td>59,400</td></tr>
  <tr><td colspan="4">&nbsp;</td></tr>
</table>
</body></html>
"""

SELL_HTML = """
<html><body>
<table class="type_2">
  <tr><th>종목명</th><th>거래량</th><th>거래대금</th></tr>
  <tr><td class="no">1</td>
      <td><a href="/item/main.naver?code=005930">삼성전자</a></td>
      <td>500,000</td><td>37,250</td></tr>
  <tr><td class="no">2</td>
      <td><a href="/item/main.naver?code=035420">NAVER</a></td>
      <td>100,000</td><td>18,650</td></tr>
</table>
</body></html>
"""


def test_parse_deal_rank_extracts_code_name_and_numbers():
    legs = parse_deal_rank(BUY_HTML)
    assert len(legs) == 2
    by_code = {leg.code: leg for leg in legs}
    assert by_code["005930"].name == "삼성전자"
    assert by_code["005930"].qty == 1_500_000
    assert by_code["005930"].value == 111_750


def test_parse_deal_rank_ignores_rows_without_stock_link():
    assert parse_deal_rank("<table><tr><td>합계</td><td>1,000</td></tr></table>") == []


def test_parse_deal_rank_dedupes_same_code_keeping_first():
    html = BUY_HTML + BUY_HTML.replace("1,500,000", "9,999,999")
    by_code = {leg.code: leg for leg in parse_deal_rank(html)}
    assert by_code["005930"].qty == 1_500_000


def test_merge_legs_computes_net_buy_minus_sell():
    merged = merge_legs(parse_deal_rank(BUY_HTML), parse_deal_rank(SELL_HTML))

    name, qty, value = merged["005930"]
    assert name == "삼성전자"
    assert qty == 1_000_000  # 1,500,000 매수 - 500,000 매도
    assert value == 74_500

    # 매수 표에만 있는 종목은 전량 순매수
    assert merged["000660"][1] == 300_000
    # 매도 표에만 있는 종목은 전량 순매도(음수)
    assert merged["035420"][1] == -100_000
    assert merged["035420"][2] == -18_650


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.encoding = None
        self.apparent_encoding = "euc-kr"


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.requests.append(params)
        key = (params["investor_gubun"], params["type"], params["sosok"])
        return FakeResponse(self.pages.get(key, "<html></html>"))

    def close(self):
        pass


def build_session():
    return FakeSession(
        {
            ("9000", "buy", "01"): BUY_HTML,  # 외국인 매수
            ("9000", "sell", "01"): SELL_HTML,  # 외국인 매도
            ("1000", "buy", "01"): SELL_HTML,  # 기관 매수 (반대로 배치)
            ("1000", "sell", "01"): BUY_HTML,  # 기관 매도
        }
    )


def test_fetch_kospi_builds_rows_for_both_investors():
    session = build_session()
    provider = NaverProvider(config=Config(), session=session)
    snapshot = provider.fetch("kospi")

    rows = {row.code: row for row in snapshot.rows}
    assert set(rows) == {"005930", "000660", "035420"}

    samsung = rows["005930"]
    assert samsung.market == "kospi"
    assert samsung.foreign_qty == 1_000_000
    assert samsung.inst_qty == -1_000_000  # 매수/매도 표를 뒤집어 넣었으므로 부호 반대
    assert samsung.both_qty == 0

    # 투자자 2종 x 매수/매도 2종 = 4회 요청
    assert len(session.requests) == 4


def test_fetch_uses_both_markets_when_all():
    session = build_session()
    provider = NaverProvider(config=Config(), session=session)
    provider.fetch("all")
    sosoks = {req["sosok"] for req in session.requests}
    assert sosoks == {"01", "02"}


def test_fetch_rejects_unknown_market():
    provider = NaverProvider(config=Config(), session=build_session())
    with pytest.raises(ProviderError, match="시장 구분"):
        provider.fetch("nyse")


def test_fetch_raises_when_nothing_parsed():
    session = FakeSession({})
    provider = NaverProvider(config=Config(), session=session)
    with pytest.raises(ProviderError, match="파싱하지 못했습니다"):
        provider.fetch("kospi")


def test_http_error_becomes_provider_error():
    class ErrorSession(FakeSession):
        def get(self, url, params=None, timeout=None):
            return FakeResponse("", status_code=503)

    provider = NaverProvider(config=Config(), session=ErrorSession({}))
    with pytest.raises(ProviderError, match="503"):
        provider.fetch("kospi")
