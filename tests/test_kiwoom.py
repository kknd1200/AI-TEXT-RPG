import pytest

from krflow.config import Config
from krflow.providers.base import ProviderError
from krflow.providers.kiwoom import (
    KiwoomProvider,
    KiwoomTokenStore,
    _to_float,
    normalize_code,
    parse_rank_response,
)
from krflow.market import now_kst
from datetime import timedelta

# ka90009 응답 형태를 본뜬 픽스처.
# 한 행에 외인/기관 × 순매수/순매도 네 갈래의 N위 종목이 나란히 담긴다.
SAMPLE = {
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
    "frgnr_orgn_trde_upper": [
        {
            "for_netprps_stk_cd": "005930",
            "for_netprps_stk_nm": "삼성전자",
            "for_netprps_amt": "+000092000",
            "for_netprps_qty": "+0001234567",
            "for_netslmt_stk_cd": "035720",
            "for_netslmt_stk_nm": "카카오",
            "for_netslmt_amt": "31500",  # 부호 없이 와도 순매도로 해석
            "for_netslmt_qty": "700000",
            "orgn_netprps_stk_cd": "000660",
            "orgn_netprps_stk_nm": "SK하이닉스",
            "orgn_netprps_amt": "23760",
            "orgn_netprps_qty": "120000",
            "orgn_netslmt_stk_cd": "005930",
            "orgn_netslmt_stk_nm": "삼성전자",
            "orgn_netslmt_amt": "--17500",
            "orgn_netslmt_qty": "-234567",
        },
        {
            "for_netprps_stk_cd": "A000660",  # 접두 문자가 붙어 오는 경우
            "for_netprps_stk_nm": "SK하이닉스",
            "for_netprps_amt": "9900",
            "for_netprps_qty": "50000",
            "for_netslmt_stk_cd": "",
            "orgn_netprps_stk_cd": "035720",
            "orgn_netprps_stk_nm": "카카오",
            "orgn_netprps_amt": "4100",
            "orgn_netprps_qty": "90000",
            "orgn_netslmt_stk_cd": "",
        },
    ],
}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+000012345", 12345.0),
        ("--1,234", -1234.0),
        ("  -12 ", -12.0),
        ("0", 0.0),
        ("", None),
        ("-", None),
        (1234, 1234.0),
    ],
)
def test_to_float_handles_kiwoom_number_strings(raw, expected):
    assert _to_float(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("005930", "005930"), ("A005930", "005930"), ("005930_AL", "005930"), ("", ""), ("12", "")],
)
def test_normalize_code(raw, expected):
    assert normalize_code(raw) == expected


def test_parse_merges_four_lists_by_code():
    rows = {row.code: row for row in parse_rank_response(SAMPLE, market="kospi")}
    assert set(rows) == {"005930", "035720", "000660"}


def test_parse_signs_net_buy_positive_and_net_sell_negative():
    rows = {row.code: row for row in parse_rank_response(SAMPLE)}

    samsung = rows["005930"]
    assert samsung.name == "삼성전자"
    assert samsung.foreign_value == 92000  # 외국인 순매수 -> 양수
    assert samsung.foreign_qty == 1234567
    assert samsung.inst_value == -17500  # 기관 순매도 -> 음수
    assert samsung.inst_qty == -234567
    assert samsung.both_value == 74500

    # 부호 없이 온 순매도 값도 음수로 고정된다
    kakao = rows["035720"]
    assert kakao.foreign_value == -31500
    assert kakao.foreign_qty == -700000
    assert kakao.inst_value == 4100  # 기관은 순매수 쪽 목록에 있었다


def test_parse_normalizes_prefixed_codes():
    rows = {row.code: row for row in parse_rank_response(SAMPLE)}
    # 'A000660' 과 '000660' 이 같은 종목으로 합쳐진다
    hynix = rows["000660"]
    assert hynix.foreign_value == 9900
    assert hynix.inst_value == 23760


def test_parse_skips_empty_codes():
    rows = parse_rank_response({"frgnr_orgn_trde_upper": [{"for_netprps_stk_cd": ""}]})
    assert rows == []


def test_parse_accepts_alternate_field_prefixes():
    payload = {
        "output": [
            {
                "frgn_netprps_stk_cd": "005930",
                "frgn_netprps_stk_nm": "삼성전자",
                "frgn_netprps_amt": "100",
            }
        ]
    }
    rows = parse_rank_response(payload)
    assert rows[0].code == "005930" and rows[0].foreign_value == 100


# ----------------------------------------------------------------- provider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or "{}"

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.token_calls = 0

    def post(self, url, headers=None, json=None, timeout=None):
        if url.endswith("/oauth2/token"):
            self.token_calls += 1
            return FakeResponse(
                payload={
                    "return_code": 0,
                    "token": f"tok-{self.token_calls}",
                    "expires_dt": "20991231235959",
                }
            )
        self.calls.append({"headers": headers, "body": json})
        return self.responses.pop(0)

    def close(self):
        pass


def make_config(tmp_path):
    return Config(kiwoom_app_key="k", kiwoom_app_secret="s", cache_dir=tmp_path)


def test_fetch_merges_amount_and_quantity_calls(tmp_path):
    session = FakeSession([FakeResponse(payload=SAMPLE), FakeResponse(payload=SAMPLE)])
    provider = KiwoomProvider(config=make_config(tmp_path), session=session)
    snapshot = provider.fetch("kospi")

    assert snapshot.source == "kiwoom"
    assert len(snapshot) == 3
    # 금액 정렬(1) + 수량 정렬(2) 두 번 호출한다
    assert [call["body"]["amt_qty_tp"] for call in session.calls] == ["1", "2"]
    assert session.calls[0]["body"]["mrkt_tp"] == "001"
    assert session.calls[0]["headers"]["api-id"] == "ka90009"


def test_fetch_single_call_when_qty_disabled(tmp_path):
    session = FakeSession([FakeResponse(payload=SAMPLE)])
    provider = KiwoomProvider(config=make_config(tmp_path), session=session, include_qty=False)
    provider.fetch("all")
    assert len(session.calls) == 1
    assert session.calls[0]["body"]["mrkt_tp"] == "000"


def test_fetch_retries_once_on_401(tmp_path):
    session = FakeSession(
        [FakeResponse(status_code=401), FakeResponse(payload=SAMPLE), FakeResponse(payload=SAMPLE)]
    )
    provider = KiwoomProvider(config=make_config(tmp_path), session=session)
    snapshot = provider.fetch("all")

    assert len(snapshot) == 3
    assert session.token_calls == 2
    assert session.calls[1]["headers"]["authorization"] == "Bearer tok-2"


def test_fetch_raises_on_error_return_code(tmp_path):
    session = FakeSession([FakeResponse(payload={"return_code": 3, "return_msg": "권한 없음"})])
    provider = KiwoomProvider(config=make_config(tmp_path), session=session)
    with pytest.raises(ProviderError, match="권한 없음"):
        provider.fetch("all")


def test_fetch_rejects_unknown_market(tmp_path):
    provider = KiwoomProvider(config=make_config(tmp_path), session=FakeSession([]))
    with pytest.raises(ProviderError, match="시장 구분"):
        provider.fetch("nasdaq")


def test_missing_credentials_raise():
    with pytest.raises(ProviderError, match="KIWOOM_APP_KEY"):
        KiwoomProvider(config=Config())


def test_token_cached_across_fetches(tmp_path):
    session = FakeSession([FakeResponse(payload=SAMPLE)] * 4)
    provider = KiwoomProvider(config=make_config(tmp_path), session=session)
    provider.fetch("all")
    provider.fetch("all")
    assert session.token_calls == 1


def test_token_store_roundtrip_and_expiry(tmp_path):
    store = KiwoomTokenStore(tmp_path, "real")
    store.write("key", "tok", now_kst() + timedelta(hours=5))
    assert store.read("key") == "tok"

    store.write("key", "tok", now_kst() + timedelta(minutes=1))
    assert store.read("key") is None
