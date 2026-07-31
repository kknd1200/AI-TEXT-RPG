import json
from datetime import datetime

import pytest

from krflow import market
from krflow.cli import main
from krflow.config import Config, load_config
from krflow.market import KST, market_phase, last_business_day, yyyymmdd
from krflow.providers import ProviderError, create, create_auto


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


@pytest.mark.parametrize(
    "when,expected",
    [
        ("2026-07-31 08:59", "pre"),  # 금요일 개장 직전
        ("2026-07-31 09:00", "open"),
        ("2026-07-31 15:30", "open"),
        ("2026-07-31 15:31", "after"),
        ("2026-08-01 11:00", "closed"),  # 토요일
        ("2026-08-02 11:00", "closed"),  # 일요일
    ],
)
def test_market_phase(when, expected):
    assert market_phase(at(when)) == expected


def test_last_business_day_skips_weekend():
    # 일요일 정오 -> 직전 금요일
    assert yyyymmdd(last_business_day(at("2026-08-02 12:00"))) == "20260731"


def test_last_business_day_before_open_uses_previous_day():
    # 금요일 개장 전 -> 목요일
    assert yyyymmdd(last_business_day(at("2026-07-31 07:00"))) == "20260730"


def test_naive_datetime_is_treated_as_kst():
    assert market.to_kst(datetime(2026, 7, 31, 10, 0)).tzinfo == KST


# --------------------------------------------------------------------- config


def test_load_config_prefers_env_over_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('KIS_APP_KEY="from-file"\nKIS_APP_SECRET=secret\n# 주석\n', encoding="utf-8")
    monkeypatch.setenv("KIS_APP_KEY", "from-env")

    config = load_config(env_file)
    assert config.kis_app_key == "from-env"
    assert config.kis_app_secret == "secret"
    assert config.has_kis


def test_load_config_missing_file_is_fine(tmp_path, monkeypatch):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    config = load_config(tmp_path / "nope.env")
    assert not config.has_kis
    assert config.kis_env == "real"


def test_invalid_kis_env_falls_back_to_real(tmp_path):
    (tmp_path / ".env").write_text("KIS_ENV=weird\n", encoding="utf-8")
    assert load_config(tmp_path / ".env").kis_env == "real"


# ------------------------------------------------------------------ providers


def test_create_unknown_provider_raises():
    with pytest.raises(ProviderError, match="알 수 없는 provider"):
        create("bloomberg")


def test_create_auto_falls_back_to_naver_without_keys():
    provider = create_auto(config=Config(kis_app_key="", kis_app_secret=""))
    assert provider.name == "naver"


def test_mock_provider_is_deterministic_with_seed():
    a = create("mock", seed=7).fetch("all")
    b = create("mock", seed=7).fetch("all")
    assert [r.foreign_value for r in a.rows] == [r.foreign_value for r in b.rows]


def test_mock_provider_market_filter():
    snapshot = create("mock", seed=1).fetch("kosdaq")
    assert snapshot.rows and all(r.market == "kosdaq" for r in snapshot.rows)


# ------------------------------------------------------------------------ CLI


def test_cli_providers_command(capsys):
    assert main(["providers"]) == 0
    assert "kis" in capsys.readouterr().out


def test_cli_once_json_to_stdout(capsys):
    assert main(["once", "--provider", "mock", "--top", "3", "--json", "-"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "mock"
    assert len(payload["rows"]) <= 3
    assert payload["query"]["investor"] == "both"


def test_cli_once_csv_to_file(tmp_path, capsys):
    out = tmp_path / "flow.csv"
    assert main(["once", "--provider", "mock", "--top", "5", "--csv", str(out)]) == 0
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    assert lines[0].startswith("rank,code,name")
    assert len(lines) >= 2


def test_cli_once_renders_table_without_export(capsys):
    assert main(["once", "--provider", "mock", "--top", "2"]) == 0
    assert "수급 상위" in capsys.readouterr().out


def test_cli_reports_provider_error(capsys):
    assert main(["once", "--provider", "kis", "--env-file", "/nonexistent"]) == 1
    assert "KIS_APP_KEY" in capsys.readouterr().err


def test_cli_rejects_bad_choice():
    with pytest.raises(SystemExit):
        main(["once", "--provider", "mock", "--market", "nasdaq"])


def test_cli_watch_stops_after_cycles():
    assert main(["watch", "--provider", "mock", "--cycles", "2", "--interval", "0"]) == 0
