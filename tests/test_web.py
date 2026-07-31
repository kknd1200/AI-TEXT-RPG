import json

import pytest

from krflow.models import FlowRow, Snapshot
from krflow.market import now_kst
from krflow.providers.base import Provider, ProviderError
from krflow.ui.web import SnapshotCache, build_payload


def snapshot(rows=None):
    return Snapshot(
        rows=rows
        if rows is not None
        else [
            FlowRow(
                code="005930",
                name="삼성전자",
                market="kospi",
                price=74500,
                change_pct=1.64,
                foreign_value=92000,
                inst_value=-17500,
                foreign_qty=1_234_567,
                inst_qty=-234_567,
            ),
            FlowRow(code="000660", name="SK하이닉스", market="kospi", foreign_value=-9900, inst_value=23760),
        ],
        source="test",
        as_of=now_kst(),
        market="kospi",
    )


def test_payload_formats_rows_and_directions():
    payload = build_payload(snapshot(), None, investor="both", metric="value", side="buy", top=10)

    assert payload["ok"] is True
    assert payload["unit"] == "억원"
    first = payload["rows"][0]
    assert first["name"] == "삼성전자"
    assert first["price"] == "74,500"
    assert first["changePct"] == "+1.64%"
    assert first["changeDir"] == "up"
    assert first["foreign"] == "+920.0"  # 92,000 백만원 -> 920 억원
    assert first["instDir"] == "down"


def test_payload_qty_metric_switches_unit():
    payload = build_payload(snapshot(), None, investor="foreign", metric="qty", side="buy", top=5)
    assert payload["unit"] == "천주"
    assert payload["rows"][0]["foreign"] == "+1,235"


def test_payload_without_snapshot_is_not_ok():
    payload = build_payload(None, "네트워크 오류", investor="both", metric="value", side="buy", top=5)
    assert payload["ok"] is False
    assert payload["error"] == "네트워크 오류"
    assert payload["rows"] == []


def test_payload_is_json_serializable():
    payload = build_payload(snapshot(), None, investor="both", metric="value", side="buy", top=5)
    json.dumps(payload, ensure_ascii=False)


def test_payload_rejects_invalid_investor():
    with pytest.raises(ValueError):
        build_payload(snapshot(), None, investor="alien", metric="value", side="buy", top=5)


class CountingProvider(Provider):
    name = "counting"
    label = "counting"
    min_interval = 0.0

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def fetch(self, market="all"):
        self.calls += 1
        if self.fail:
            raise ProviderError("소스 장애")
        return snapshot()


def test_cache_serves_within_ttl():
    provider = CountingProvider()
    cache = SnapshotCache(provider, "kospi", ttl=60)
    cache.get()
    cache.get()
    assert provider.calls == 1


def test_cache_refetches_after_ttl():
    provider = CountingProvider()
    cache = SnapshotCache(provider, "kospi", ttl=0)
    cache.get()
    cache.get()
    assert provider.calls == 2


def test_cache_reports_error_without_raising():
    cache = SnapshotCache(CountingProvider(fail=True), "kospi", ttl=60)
    snap, error = cache.get()
    assert snap is None
    assert "소스 장애" in error


def test_cache_keeps_last_good_snapshot_on_later_failure():
    provider = CountingProvider()
    cache = SnapshotCache(provider, "kospi", ttl=0)
    cache.get()
    provider.fail = True
    snap, error = cache.get()
    assert snap is not None  # 직전 데이터 유지
    assert "소스 장애" in error


# ------------------------------------------------------------------- 콘솔 UI


def test_console_table_drops_columns_on_narrow_terminals():
    from krflow.ui.console import build_table

    kwargs = dict(investor="both", metric="value", side="buy", top=5)
    wide = build_table(snapshot(), width=140, **kwargs)
    narrow = build_table(snapshot(), width=80, **kwargs)
    tiny = build_table(snapshot(), width=50, **kwargs)

    headers = lambda t: [c.header for c in t.columns]  # noqa: E731
    assert "현재가" in headers(wide) and "코드" in headers(wide)
    assert "현재가" not in headers(narrow) and "코드" in headers(narrow)
    assert "코드" not in headers(tiny)
    # 수급 열은 어떤 폭에서도 유지된다
    for table in (wide, narrow, tiny):
        assert {"외국인", "기관", "합계"} <= set(headers(table))


def test_console_table_hides_price_when_source_has_none():
    from krflow.ui.console import build_table

    rows = [FlowRow(code="005930", name="삼성전자", market="kospi", foreign_value=100)]
    table = build_table(
        snapshot(rows), investor="foreign", metric="value", side="buy", top=5, width=160
    )
    assert "현재가" not in [c.header for c in table.columns]


def test_console_table_handles_empty_result():
    from krflow.ui.console import build_table

    table = build_table(
        snapshot([]), investor="both", metric="value", side="buy", top=5, width=120
    )
    assert table.row_count == 1
