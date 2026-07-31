from datetime import datetime

import pytest

from krflow import fmt
from krflow.bot import render
from krflow.bot.store import DEFAULT_SETTINGS, ChatStore
from krflow.bot.telegram import (
    TelegramBot,
    TelegramClient,
    TelegramError,
    _due_daily_slot,
    _within_session,
)
from krflow.config import parse_chat_ids
from krflow.market import KST, now_kst
from krflow.models import FlowRow, Snapshot
from krflow.providers.base import Provider, ProviderError

CHAT = 12345


def sample_snapshot():
    return Snapshot(
        rows=[
            FlowRow(
                code="005930",
                name="삼성전자",
                market="kospi",
                foreign_value=92000,
                inst_value=-17500,
                foreign_qty=1_234_567,
                inst_qty=-234_567,
            ),
            FlowRow(
                code="000660",
                name="SK하이닉스",
                market="kospi",
                foreign_value=-9900,
                inst_value=23760,
            ),
            FlowRow(
                code="373220",
                name="LG에너지솔루션",
                market="kospi",
                foreign_value=48000,
                inst_value=12000,
            ),
        ],
        source="kiwoom",
        as_of=now_kst(),
        market="all",
    )


class StubProvider(Provider):
    name = "stub"
    label = "테스트 소스"
    min_interval = 0.0

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def fetch(self, market="all"):
        self.calls += 1
        if self.fail:
            raise ProviderError("소스 장애")
        return sample_snapshot()


class FakeClient:
    """TelegramClient 대역 — 보낸 메시지를 기록만 한다."""

    def __init__(self):
        self.sent = []
        self.edited = []
        self.answered = []
        self.fail_edit = False

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append({"chat_id": chat_id, "text": text, "markup": reply_markup})
        return {"message_id": len(self.sent)}

    def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
        if self.fail_edit:
            raise TelegramError("message is not modified")
        self.edited.append({"chat_id": chat_id, "message_id": message_id, "text": text})

    def answer_callback_query(self, callback_id, text=""):
        self.answered.append({"id": callback_id, "text": text})

    def set_my_commands(self, commands):
        pass

    def get_me(self):
        return {"username": "krflow_test_bot"}


@pytest.fixture
def bot(tmp_path):
    client = FakeClient()
    provider = StubProvider()
    store = ChatStore(tmp_path / "state.json")
    return TelegramBot(client, provider, store, allowed_chat_ids={CHAT}, interval=0)


def message(text, chat_id=CHAT):
    return {"message": {"chat": {"id": chat_id}, "text": text}}


def callback(data, chat_id=CHAT, callback_id="cb1"):
    return {
        "callback_query": {
            "id": callback_id,
            "data": data,
            "message": {"message_id": 7, "chat": {"id": chat_id}},
        }
    }


# ----------------------------------------------------------------- 표시 포맷


def test_display_width_counts_hangul_as_two():
    assert fmt.display_width("삼성") == 4
    assert fmt.display_width("SK") == 2
    assert fmt.display_width("SK하이닉스") == 10  # 영문 2 + 한글 4자 × 2


def test_pad_aligns_by_display_width():
    assert fmt.display_width(fmt.pad("삼성전자", 10)) == 10
    assert fmt.display_width(fmt.pad("SK", 10, "right")) == 10
    assert fmt.pad("SK", 6, "right").endswith("SK")


def test_ellipsis_truncates_long_names():
    out = fmt.ellipsis("LG에너지솔루션", 10)
    assert out.endswith("…")
    assert fmt.display_width(out) <= 10


def test_rendered_table_rows_have_equal_width():
    text = render.render_snapshot(sample_snapshot(), DEFAULT_SETTINGS)
    body = text.split("<pre>")[1].split("</pre>")[0]
    widths = {fmt.display_width(line) for line in body.splitlines()}
    assert len(widths) == 1  # 헤더·구분선·데이터·합계 모두 같은 폭


def test_render_marks_selected_buttons():
    kb = render.keyboard({**DEFAULT_SETTINGS, "investor": "foreign"})
    labels = [b["text"] for row in kb["inline_keyboard"] for b in row]
    assert "● 외국인" in labels
    assert "기관" in labels  # 선택 안 된 항목은 표시 없음


def test_render_snapshot_reports_error_when_no_data():
    text = render.render_snapshot(None, DEFAULT_SETTINGS, error="네트워크 오류")
    assert "네트워크 오류" in text


# --------------------------------------------------------------------- 권한


def test_unknown_chat_is_denied_and_told_its_id(bot):
    bot.handle_update(message("/top", chat_id=999))
    assert bot.provider.calls == 0
    assert "999" in bot.client.sent[0]["text"]


def test_callback_from_unknown_chat_is_denied(bot):
    bot.handle_update(callback("s:investor:foreign", chat_id=999))
    assert bot.client.answered[0]["text"] == "권한이 없습니다."
    assert bot.client.edited == []


def test_parse_chat_ids_accepts_negative_group_ids():
    assert parse_chat_ids("123, -456; 789") == {123, -456, 789}
    assert parse_chat_ids("") == set()
    assert parse_chat_ids("abc,12") == {12}


# ------------------------------------------------------------------ 명령어


def test_top_command_sends_table_with_keyboard(bot):
    bot.handle_update(message("/top"))
    sent = bot.client.sent[-1]
    assert "<pre>" in sent["text"]
    assert "삼성전자" in sent["text"]
    assert sent["markup"]["inline_keyboard"]


def test_help_command(bot):
    bot.handle_update(message("/help"))
    assert "/watch" in bot.client.sent[0]["text"]


def test_group_chat_command_suffix_is_stripped(bot):
    bot.handle_update(message("/top@krflow_test_bot"))
    assert "<pre>" in bot.client.sent[-1]["text"]


def test_unknown_command_is_answered(bot):
    bot.handle_update(message("/nope"))
    assert "모르는 명령" in bot.client.sent[0]["text"]


def test_plain_text_is_ignored(bot):
    bot.handle_update(message("안녕"))
    assert bot.client.sent == []


def test_watch_command_registers_and_stop_clears(bot):
    bot.handle_update(message("/watch 5"))
    assert bot.store.watch_minutes(CHAT) == 5

    bot.handle_update(message("/stop"))
    assert bot.store.watch_minutes(CHAT) == 0


def test_watch_rejects_non_numeric_and_clamps(bot):
    bot.handle_update(message("/watch 다섯"))
    assert bot.store.watch_minutes(CHAT) == 0

    bot.handle_update(message("/watch 9999"))
    assert bot.store.watch_minutes(CHAT) == 240


def test_daily_command_toggles(bot):
    bot.handle_update(message("/daily on"))
    assert bot.store.daily_enabled(CHAT) is True

    bot.handle_update(message("/daily off"))
    assert bot.store.daily_enabled(CHAT) is False


def test_status_command_shows_settings(bot):
    bot.handle_update(message("/watch 3"))
    bot.handle_update(message("/status"))
    text = bot.client.sent[-1]["text"]
    assert "3분마다" in text
    assert "테스트 소스" in text


# -------------------------------------------------------------- 인라인 버튼


def test_callback_updates_setting_and_edits_message(bot):
    bot.handle_update(callback("s:investor:foreign"))
    assert bot.store.settings(CHAT)["investor"] == "foreign"
    assert bot.client.edited[-1]["message_id"] == 7


def test_callback_rejects_invalid_value(bot):
    bot.handle_update(callback("s:investor:alien"))
    assert bot.store.settings(CHAT)["investor"] == "both"
    assert bot.client.answered[-1]["text"] == "알 수 없는 설정입니다."
    assert bot.client.edited == []


def test_callback_top_is_clamped(bot):
    bot.handle_update(callback("s:top:9999"))
    assert bot.store.settings(CHAT)["top"] == 50


def test_refresh_callback_edits_without_changing_settings(bot):
    before = bot.store.settings(CHAT)
    bot.handle_update(callback("r"))
    assert bot.store.settings(CHAT) == before
    assert bot.client.edited


def test_unchanged_edit_error_is_swallowed(bot):
    bot.client.fail_edit = True
    bot.handle_update(callback("r"))  # 예외가 새어나오면 실패
    assert bot.client.answered


def test_settings_change_reflected_in_next_render(bot):
    bot.handle_update(callback("s:side:sell"))
    text = bot.client.edited[-1]["text"]
    assert "순매도 상위" in text


# --------------------------------------------------------------- 스케줄러


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


@pytest.mark.parametrize(
    "when,expected",
    [
        ("2026-07-31 08:49", False),
        ("2026-07-31 08:50", True),
        ("2026-07-31 12:00", True),
        ("2026-07-31 15:40", True),
        ("2026-07-31 15:41", False),
        ("2026-08-01 12:00", False),  # 토요일
    ],
)
def test_within_session(when, expected):
    assert _within_session(at(when)) is expected


@pytest.mark.parametrize(
    "when,expected",
    [
        ("2026-07-31 09:04", None),
        ("2026-07-31 09:05", "open"),
        ("2026-07-31 09:35", "open"),  # 유예 시간 안이면 따라잡는다
        ("2026-07-31 09:36", None),
        ("2026-07-31 15:35", "close"),
        ("2026-08-01 09:05", None),  # 주말
    ],
)
def test_due_daily_slot(when, expected):
    slot = _due_daily_slot(at(when))
    assert (slot[0] if slot else None) == expected


def test_scheduler_sends_watch_only_when_due(bot):
    bot.store.set_watch(CHAT, 5)
    now = at("2026-07-31 10:00")

    assert bot.scheduler_tick(now, now_ts=1000.0) == 1
    # 5분이 지나지 않았으면 다시 보내지 않는다
    assert bot.scheduler_tick(now, now_ts=1100.0) == 0
    assert bot.scheduler_tick(now, now_ts=1000.0 + 301) == 1


def test_scheduler_skips_watch_outside_session(bot):
    bot.store.set_watch(CHAT, 5)
    assert bot.scheduler_tick(at("2026-07-31 20:00"), now_ts=1000.0) == 0


def test_scheduler_sends_daily_summary_once(bot):
    bot.store.set_daily(CHAT, True)
    now = at("2026-07-31 09:05")

    assert bot.scheduler_tick(now, now_ts=1000.0) == 1
    assert "장 시작" in bot.client.sent[-1]["text"]
    # 같은 슬롯에서 두 번 보내지 않는다
    assert bot.scheduler_tick(at("2026-07-31 09:20"), now_ts=2000.0) == 0
    # 마감 슬롯은 별개
    assert bot.scheduler_tick(at("2026-07-31 15:35"), now_ts=3000.0) == 1
    assert "장 마감" in bot.client.sent[-1]["text"]


def test_scheduler_skips_daily_when_disabled(bot):
    assert bot.scheduler_tick(at("2026-07-31 09:05"), now_ts=1000.0) == 0


def test_scheduler_ignores_chats_removed_from_allowlist(bot):
    bot.store.set_watch(CHAT, 1)
    bot.allowed = set()
    assert bot.scheduler_tick(at("2026-07-31 10:00"), now_ts=1000.0) == 0


def test_provider_failure_does_not_crash_bot(tmp_path):
    client = FakeClient()
    store = ChatStore(tmp_path / "state.json")
    bot = TelegramBot(
        client, StubProvider(fail=True), store, allowed_chat_ids={CHAT}, interval=0
    )
    bot.handle_update(message("/top"))
    assert "소스 장애" in client.sent[-1]["text"]


# ------------------------------------------------------------------- 저장소


def test_store_persists_across_instances(tmp_path):
    path = tmp_path / "state.json"
    first = ChatStore(path)
    first.update_settings(CHAT, investor="inst", top=20)
    first.set_watch(CHAT, 7)

    second = ChatStore(path)
    assert second.settings(CHAT)["investor"] == "inst"
    assert second.settings(CHAT)["top"] == 20
    assert second.watch_minutes(CHAT) == 7


def test_store_ignores_unknown_setting_keys(tmp_path):
    store = ChatStore(tmp_path / "s.json")
    store.update_settings(CHAT, hacked="yes")
    assert "hacked" not in store.settings(CHAT)


def test_store_recovers_from_corrupt_file(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{{{ not json", encoding="utf-8")
    store = ChatStore(path)
    assert store.settings(CHAT)["investor"] == "both"


def test_store_daily_marks_are_trimmed(tmp_path):
    store = ChatStore(tmp_path / "s.json")
    for day in range(20):
        assert store.claim_daily(CHAT, f"2026{day:04d}-open") is True
    # 최근 것만 남아 파일이 무한정 커지지 않는다
    assert store.claim_daily(CHAT, "20260000-open") is True


# ------------------------------------------------------------------ 클라이언트


class RecordingSession:
    def __init__(self, payload=None):
        self.payload = payload or {"ok": True, "result": []}
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append({"url": url, "json": json, "timeout": timeout})

        class R:
            status_code = 200

            def json(_self):
                return self.payload

        return R()


def test_client_get_updates_separates_poll_timeout_from_http_timeout():
    session = RecordingSession()
    client = TelegramClient("TOKEN", session=session, timeout=10)
    client.get_updates(offset=5, poll_timeout=25)

    post = session.posts[0]
    assert post["url"].endswith("/botTOKEN/getUpdates")
    assert post["json"]["timeout"] == 25  # 텔레그램 롱폴링 대기
    assert post["timeout"] == 35  # requests HTTP 타임아웃
    assert post["json"]["offset"] == 5


def test_client_raises_on_not_ok():
    session = RecordingSession({"ok": False, "description": "Unauthorized"})
    client = TelegramClient("TOKEN", session=session)
    with pytest.raises(TelegramError, match="Unauthorized"):
        client.get_me()


def test_client_requires_token():
    with pytest.raises(TelegramError):
        TelegramClient("")


def test_client_send_message_uses_html_mode():
    session = RecordingSession({"ok": True, "result": {}})
    client = TelegramClient("TOKEN", session=session)
    client.send_message(1, "<b>hi</b>", {"inline_keyboard": []})
    assert session.posts[0]["json"]["parse_mode"] == "HTML"
    assert session.posts[0]["json"]["reply_markup"] == {"inline_keyboard": []}


def test_table_widens_columns_for_huge_numbers():
    huge = Snapshot(
        rows=[
            FlowRow(code="005930", name="삼성전자", market="kospi",
                    foreign_value=1_500_000, inst_value=-400_000),
        ],
        source="stub",
        as_of=now_kst(),
        market="all",
    )
    text = render.render_snapshot(huge, DEFAULT_SETTINGS)
    body = text.split("<pre>")[1].split("</pre>")[0]
    lines = body.splitlines()
    # 값이 커져도 모든 행의 폭이 같고, 숫자끼리 붙지 않는다
    assert len({fmt.display_width(line) for line in lines}) == 1
    assert "+15,000-4,000" not in body  # 열이 붙어버리면 실패
