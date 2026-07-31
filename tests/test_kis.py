import json
from datetime import timedelta

import pytest

from krflow.config import Config
from krflow.market import now_kst
from krflow.providers.kis import KisProvider, KisTokenStore, parse_rank_response
from krflow.providers.base import ProviderError

# 실제 KIS 응답 형태를 본뜬 픽스처
SAMPLE = {
    "rt_cd": "0",
    "msg1": "정상처리 되었습니다.",
    "output": [
        {
            "hts_kor_isnm": "삼성전자",
            "mksc_shrn_iscd": "005930",
            "stck_prpr": "74,500",
            "prdy_vrss": "1,200",
            "prdy_vrss_sign": "2",
            "prdy_ctrt": "1.64",
            "acml_vol": "12,345,678",
            "frgn_ntby_qty": "1,234,567",
            "frgn_ntby_tr_pbmn": "92,000",
            "orgn_ntby_qty": "-234,567",
            "orgn_ntby_tr_pbmn": "-17,500",
        },
        {
            "hts_kor_isnm": "SK하이닉스",
            "mksc_shrn_iscd": "000660",
            "stck_prpr": "198000",
            "prdy_vrss": "3500",
            "prdy_vrss_sign": "5",
            "prdy_ctrt": "-1.74",
            "acml_vol": "3,210,000",
            "frgn_ntby_qty": "-50,000",
            "frgn_ntby_tr_pbmn": "-9,900",
            "orgn_ntby_qty": "120,000",
            "orgn_ntby_tr_pbmn": "23,760",
        },
        {"hts_kor_isnm": "코드없음", "mksc_shrn_iscd": ""},  # 무시돼야 함
    ],
}


def test_parse_basic_fields():
    rows = parse_rank_response(SAMPLE, market="kospi")
    assert len(rows) == 2

    samsung = rows[0]
    assert samsung.code == "005930"
    assert samsung.name == "삼성전자"
    assert samsung.market == "kospi"
    assert samsung.price == 74500
    assert samsung.volume == 12345678
    assert samsung.foreign_qty == 1234567
    assert samsung.foreign_value == 92000
    assert samsung.inst_qty == -234567
    assert samsung.inst_value == -17500
    assert samsung.both_value == 74500


def test_parse_applies_negative_sign_for_falling_stock():
    rows = parse_rank_response(SAMPLE)
    hynix = rows[1]
    # prdy_vrss_sign=5(하락)이면 전일대비는 음수로 정규화된다
    assert hynix.change == -3500
    assert hynix.change_pct == -1.74


def test_parse_handles_output1_key_and_dict_output():
    rows = parse_rank_response({"output1": SAMPLE["output"][0]})
    assert len(rows) == 1 and rows[0].code == "005930"


def test_parse_missing_optional_fields_defaults_to_zero():
    rows = parse_rank_response({"output": [{"mksc_shrn_iscd": "123456"}]})
    assert rows[0].name == "123456"
    assert rows[0].foreign_value == 0.0
    assert rows[0].price is None


# ------------------------------------------------------------------ 토큰 캐시


def test_token_store_roundtrip(tmp_path):
    store = KisTokenStore(tmp_path, "real")
    store.write("key", "tok", now_kst() + timedelta(hours=6))
    assert store.read("key") == "tok"


def test_token_store_rejects_other_app_key(tmp_path):
    store = KisTokenStore(tmp_path, "real")
    store.write("key", "tok", now_kst() + timedelta(hours=6))
    assert store.read("다른키") is None


def test_token_store_treats_near_expiry_as_stale(tmp_path):
    store = KisTokenStore(tmp_path, "real")
    store.write("key", "tok", now_kst() + timedelta(minutes=2))
    assert store.read("key") is None


def test_token_store_ignores_corrupt_file(tmp_path):
    store = KisTokenStore(tmp_path, "real")
    store.path.write_text("not json", encoding="utf-8")
    assert store.read("key") is None


# ----------------------------------------------------------------- provider


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeSession:
    """토큰 발급 -> 401 -> 재발급 -> 성공 시나리오를 재현한다."""

    def __init__(self, get_responses):
        self.get_responses = list(get_responses)
        self.post_calls = 0
        self.get_calls = []

    def post(self, url, **kwargs):
        self.post_calls += 1
        return FakeResponse(
            payload={
                "access_token": f"token-{self.post_calls}",
                "expires_in": 86400,
            }
        )

    def get(self, url, **kwargs):
        self.get_calls.append(kwargs)
        return self.get_responses.pop(0)

    def close(self):
        pass


def make_config(tmp_path):
    return Config(kis_app_key="k", kis_app_secret="s", kis_env="real", cache_dir=tmp_path)


def test_fetch_returns_snapshot(tmp_path):
    session = FakeSession([FakeResponse(payload=SAMPLE)])
    provider = KisProvider(config=make_config(tmp_path), session=session)
    snapshot = provider.fetch("kospi")

    assert snapshot.source == "kis"
    assert snapshot.market == "kospi"
    assert snapshot.delayed is False
    assert len(snapshot) == 2
    # 시장 코드가 요청 파라미터로 전달됐는지
    assert session.get_calls[0]["params"]["FID_INPUT_ISCD"] == "0001"
    # 전체(0)로 받아 클라이언트에서 정렬한다
    assert session.get_calls[0]["params"]["FID_ETC_CLS_CODE"] == "0"


def test_fetch_retries_once_on_401(tmp_path):
    session = FakeSession([FakeResponse(status_code=401, text="expired"), FakeResponse(payload=SAMPLE)])
    provider = KisProvider(config=make_config(tmp_path), session=session)
    snapshot = provider.fetch("all")

    assert len(snapshot) == 2
    assert session.post_calls == 2  # 최초 발급 + 재발급
    assert session.get_calls[1]["headers"]["authorization"] == "Bearer token-2"


def test_fetch_raises_on_error_rt_cd(tmp_path):
    session = FakeSession([FakeResponse(payload={"rt_cd": "1", "msg1": "권한 없음"})])
    provider = KisProvider(config=make_config(tmp_path), session=session)
    with pytest.raises(ProviderError, match="권한 없음"):
        provider.fetch("all")


def test_fetch_raises_on_unknown_market(tmp_path):
    provider = KisProvider(config=make_config(tmp_path), session=FakeSession([]))
    with pytest.raises(ProviderError, match="시장 구분"):
        provider.fetch("nasdaq")


def test_missing_credentials_raise():
    with pytest.raises(ProviderError, match="KIS_APP_KEY"):
        KisProvider(config=Config(kis_app_key="", kis_app_secret=""))


def test_token_is_reused_across_fetches(tmp_path):
    session = FakeSession([FakeResponse(payload=SAMPLE), FakeResponse(payload=SAMPLE)])
    provider = KisProvider(config=make_config(tmp_path), session=session)
    provider.fetch("all")
    provider.fetch("all")
    assert session.post_calls == 1
