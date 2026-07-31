"""텔레그램 봇 (Bot API long polling).

외부 봇 라이브러리 없이 requests 만으로 getUpdates 롱폴링을 돈다.
  · 명령어 + 인라인 버튼으로 조회 조건 전환
  · /watch N — 장중 N분마다 자동 전송
  · /daily on — 장 시작(09:05)·마감(15:35) 요약 자동 전송

봇 토큰은 @BotFather 에서 발급하고, 허용 chat_id 를 반드시 지정한다
(지정하지 않으면 아무나 이 봇으로 내 계정 데이터를 조회할 수 있다).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

import requests

from ..cache import SnapshotCache
from ..config import Config
from ..market import is_weekend, now_kst
from ..models import MARKETS
from ..providers.base import Provider
from ..ranking import INVESTORS, METRICS, SIDES
from . import render
from .store import ChatStore

API_BASE = "https://api.telegram.org"

COMMANDS = [
    {"command": "top", "description": "수급 상위 종목 조회"},
    {"command": "watch", "description": "N분마다 자동 전송 (예: /watch 5)"},
    {"command": "stop", "description": "자동 전송 해제"},
    {"command": "daily", "description": "장 시작/마감 요약 on|off"},
    {"command": "status", "description": "현재 설정 보기"},
    {"command": "help", "description": "도움말"},
]

#: 장 시작/마감 요약을 보내는 시각 (KST) 과 제목
DAILY_SLOTS = (
    ((9, 5), "open", "장 시작 · "),
    ((15, 35), "close", "장 마감 · "),
)
#: 예정 시각을 놓쳤을 때 따라잡기를 허용하는 최대 지연(분)
DAILY_GRACE_MIN = 30


#: 내용이 같으면 텔레그램이 editMessageText 를 이 사유로 거절한다.
NOT_MODIFIED = "message is not modified"

#: 같은 봇 토큰으로 getUpdates 를 두 군데서 돌리면 나오는 코드.
CONFLICT = 409


class TelegramError(RuntimeError):
    def __init__(self, message: str, description: str = "", error_code: int | None = None):
        super().__init__(message)
        self.description = description
        self.error_code = error_code


class TelegramClient:
    """Bot API 얇은 래퍼."""

    def __init__(
        self,
        token: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
        api_base: str = API_BASE,
    ) -> None:
        if not token:
            raise TelegramError("TELEGRAM_BOT_TOKEN 이 비어 있습니다.")
        self.url = f"{api_base}/bot{token}"
        self.session = session or requests.Session()
        self.timeout = timeout

    def call(self, method: str, payload: dict | None = None, http_timeout: float | None = None):
        """Bot API 호출. `payload` 는 그대로 JSON 본문이 된다.

        HTTP 타임아웃을 별도 인자로 둔 이유: getUpdates 의 `timeout` 필드는
        텔레그램 쪽 롱폴링 대기 시간이라 requests 타임아웃과 이름이 겹친다.
        """
        try:
            resp = self.session.post(
                f"{self.url}/{method}",
                json=payload or {},
                timeout=http_timeout or self.timeout,
            )
        except requests.RequestException as exc:
            raise TelegramError(f"{method} 요청 실패: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:
            raise TelegramError(f"{method} 응답 파싱 실패 (HTTP {resp.status_code})") from exc

        if not data.get("ok"):
            description = str(data.get("description") or "")
            raise TelegramError(
                f"{method} 실패: {description or data}",
                description=description,
                error_code=data.get("error_code"),
            )
        return data.get("result")

    def get_me(self):
        return self.call("getMe")

    def get_updates(self, offset: int, poll_timeout: int = 25):
        return self.call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": poll_timeout,
                "allowed_updates": ["message", "callback_query"],
            },
            http_timeout=poll_timeout + 10,
        )

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self.call("sendMessage", payload)

    def edit_message_text(
        self, chat_id: int, message_id: int, text: str, reply_markup: dict | None = None
    ):
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self.call("editMessageText", payload)

    def answer_callback_query(self, callback_id: str, text: str = ""):
        return self.call(
            "answerCallbackQuery", {"callback_query_id": callback_id, "text": text}
        )

    def set_my_commands(self, commands: list[dict]):
        return self.call("setMyCommands", {"commands": commands})


class TelegramBot:
    def __init__(
        self,
        client: TelegramClient,
        provider: Provider,
        store: ChatStore,
        *,
        market: str = "all",
        allowed_chat_ids: set[int] | None = None,
        interval: float = 30.0,
        verbose: bool = False,
    ) -> None:
        self.client = client
        self.provider = provider
        self.store = store
        self.market = market
        self.allowed = set(allowed_chat_ids or ())
        self.cache = SnapshotCache(provider, market, interval)
        self.verbose = verbose
        self._offset = 0
        self._stop = threading.Event()

    def _log(self, message: str) -> None:
        print(f"[{now_kst().strftime('%H:%M:%S')}] {message}")

    def _debug(self, message: str) -> None:
        if self.verbose:
            self._log(message)

    # ---------------------------------------------------------------- 권한
    def is_allowed(self, chat_id: int) -> bool:
        return chat_id in self.allowed

    def _deny(self, chat_id: int) -> None:
        self.client.send_message(
            chat_id,
            "🔒 이 봇은 등록된 사용자만 쓸 수 있습니다.\n\n"
            f"이 대화의 chat_id 는 <code>{chat_id}</code> 입니다.\n"
            "<code>.env</code> 의 <code>TELEGRAM_ALLOWED_CHAT_IDS</code> 에 추가하고 "
            "봇을 다시 시작하세요.",
        )

    # ------------------------------------------------------------- 데이터
    def _snapshot_message(self, chat_id: int, *, force: bool = False, title_prefix: str = ""):
        settings = self.store.settings(chat_id)
        snapshot, error = self.cache.get(force=force)
        text = render.render_snapshot(
            snapshot, settings, error=error, title_prefix=title_prefix
        )
        return text, render.keyboard(settings)

    # ------------------------------------------------------------ 업데이트
    def handle_update(self, update: dict) -> None:
        if "callback_query" in update:
            query = update["callback_query"]
            self._debug(f"버튼 수신: data={query.get('data')!r}")
            self._handle_callback(query)
        elif "message" in update:
            message = update["message"]
            self._debug(f"메시지 수신: {str(message.get('text'))[:40]!r}")
            self._handle_message(message)
        else:
            self._debug(f"처리하지 않는 업데이트: {sorted(update)}")

    def _handle_message(self, message: dict) -> None:
        chat_id = (message.get("chat") or {}).get("id")
        if chat_id is None:
            return
        if not self.is_allowed(chat_id):
            self._deny(chat_id)
            return

        text = str(message.get("text") or "").strip()
        if not text.startswith("/"):
            return

        parts = text.split()
        # 그룹방에서는 /top@내봇 형태로 온다
        command = parts[0].split("@", 1)[0].lower()
        args = parts[1:]

        if command in ("/start", "/help"):
            self.client.send_message(chat_id, render.HELP)
            if command == "/start":
                self._send_snapshot(chat_id)
            return

        if command == "/top":
            self._send_snapshot(chat_id, force=True)
            return

        if command == "/watch":
            self._cmd_watch(chat_id, args)
            return

        if command == "/stop":
            self.store.set_watch(chat_id, 0)
            self.client.send_message(chat_id, "⏹ 자동 전송을 껐습니다.")
            return

        if command == "/daily":
            self._cmd_daily(chat_id, args)
            return

        if command == "/status":
            self.client.send_message(
                chat_id,
                render.render_status(
                    self.store.settings(chat_id),
                    self.store.watch_minutes(chat_id),
                    self.store.daily_enabled(chat_id),
                    f"{self.provider.label} ({self.provider.name})",
                ),
            )
            return

        self.client.send_message(chat_id, "모르는 명령입니다. /help 를 보내보세요.")

    def _cmd_watch(self, chat_id: int, args: list[str]) -> None:
        if not args:
            self.client.send_message(
                chat_id, "사용법: <code>/watch 5</code> (5분마다). 끄려면 /stop"
            )
            return
        try:
            minutes = int(args[0])
        except ValueError:
            self.client.send_message(chat_id, "분 단위 숫자를 넣어주세요. 예: <code>/watch 5</code>")
            return
        if minutes <= 0:
            self.store.set_watch(chat_id, 0)
            self.client.send_message(chat_id, "⏹ 자동 전송을 껐습니다.")
            return
        minutes = max(1, min(minutes, 240))
        self.store.set_watch(chat_id, minutes)
        self.client.send_message(
            chat_id,
            f"⏱ 장중에 <b>{minutes}분</b>마다 보내드립니다. (끄기: /stop)",
        )

    def _cmd_daily(self, chat_id: int, args: list[str]) -> None:
        choice = (args[0].lower() if args else "")
        if choice in ("on", "켜기", "true", "1"):
            self.store.set_daily(chat_id, True)
            self.client.send_message(
                chat_id, "🔔 장 시작(09:05)·마감(15:35) 요약을 보내드립니다."
            )
        elif choice in ("off", "끄기", "false", "0"):
            self.store.set_daily(chat_id, False)
            self.client.send_message(chat_id, "🔕 장 시작/마감 요약을 껐습니다.")
        else:
            self.client.send_message(chat_id, "사용법: <code>/daily on</code> 또는 <code>/daily off</code>")

    def _handle_callback(self, callback: dict) -> None:
        callback_id = callback.get("id", "")
        message = callback.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        message_id = message.get("message_id")
        data = str(callback.get("data") or "")

        if chat_id is None:
            return
        if not self.is_allowed(chat_id):
            self.client.answer_callback_query(callback_id, "권한이 없습니다.")
            return

        is_refresh = not data.startswith("s:")
        notice = "새로고침"
        if not is_refresh:
            _, _, rest = data.partition(":")
            field, _, value = rest.partition(":")
            if self._apply_setting(chat_id, field, value):
                notice = "적용했습니다"
            else:
                self.client.answer_callback_query(callback_id, "알 수 없는 설정입니다.")
                return

        # 버튼의 로딩 표시가 남지 않도록, 느릴 수 있는 조회보다 먼저 응답한다.
        self.client.answer_callback_query(callback_id, notice)

        # 새로고침 버튼은 캐시를 건너뛰고 실제로 다시 가져온다.
        text, keyboard = self._snapshot_message(chat_id, force=is_refresh)
        try:
            self.client.edit_message_text(chat_id, message_id, text, keyboard)
        except TelegramError as exc:
            if NOT_MODIFIED in exc.description:
                return  # 값이 그대로면 수정할 게 없다
            # 메시지가 너무 오래돼 수정이 안 되는 경우 등 — 새 메시지로라도 답한다.
            self._log(f"메시지 수정 실패, 새 메시지로 보냅니다: {exc}")
            try:
                self.client.send_message(chat_id, text, keyboard)
            except TelegramError as send_exc:
                self._log(f"새 메시지 전송도 실패: {send_exc}")

    def _apply_setting(self, chat_id: int, field: str, value: str) -> bool:
        allowed = {
            "investor": INVESTORS,
            "side": SIDES,
            "metric": METRICS,
            "market": MARKETS,
        }
        if field in allowed:
            if value not in allowed[field]:
                return False
            self.store.update_settings(chat_id, **{field: value})
            return True
        if field == "top":
            try:
                top = int(value)
            except ValueError:
                return False
            self.store.update_settings(chat_id, top=max(1, min(top, 50)))
            return True
        return False

    def _send_snapshot(self, chat_id: int, *, force: bool = False, title_prefix: str = "") -> None:
        text, keyboard = self._snapshot_message(
            chat_id, force=force, title_prefix=title_prefix
        )
        self.client.send_message(chat_id, text, keyboard)

    # ------------------------------------------------------------- 스케줄러
    def scheduler_tick(self, now: datetime | None = None, now_ts: float | None = None) -> int:
        """주기 전송과 장 시작/마감 요약을 처리한다. 보낸 메시지 수를 반환."""
        now = now or now_kst()
        now_ts = time.time() if now_ts is None else now_ts
        sent = 0

        # 1) 주기 전송 — 장중에만
        if _within_session(now):
            for chat_id in self.store.due_watchers(now_ts):
                if not self.is_allowed(chat_id):
                    continue
                try:
                    self._send_snapshot(chat_id)
                    sent += 1
                except TelegramError:
                    pass
                finally:
                    self.store.mark_watch_sent(chat_id, now_ts)

        # 2) 장 시작/마감 요약
        slot = _due_daily_slot(now)
        if slot is not None:
            key, prefix = slot
            mark = f"{now.strftime('%Y%m%d')}-{key}"
            for chat_id in self.store.daily_chats():
                if not self.is_allowed(chat_id):
                    continue
                if not self.store.claim_daily(chat_id, mark):
                    continue
                try:
                    self._send_snapshot(chat_id, force=True, title_prefix=prefix)
                    sent += 1
                except TelegramError:
                    pass
        return sent

    def _scheduler_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scheduler_tick()
            except Exception:  # 스케줄러는 어떤 예외로도 죽지 않는다
                pass
            self._stop.wait(30)

    # ----------------------------------------------------------------- 실행
    def run(self, poll_timeout: int = 25, max_polls: int | None = None) -> int:
        try:
            me = self.client.get_me()
            print(f"텔레그램 봇 시작: @{me.get('username')} (소스: {self.provider.label})")
        except TelegramError as exc:
            print(f"봇 시작 실패: {exc}")
            return 1

        try:
            self.client.set_my_commands(COMMANDS)
        except TelegramError:
            pass

        if not self.allowed:
            print(
                "경고: TELEGRAM_ALLOWED_CHAT_IDS 가 비어 있습니다. "
                "봇에 아무 메시지나 보내면 chat_id 를 알려줍니다."
            )

        scheduler = threading.Thread(target=self._scheduler_loop, daemon=True)
        scheduler.start()

        polls = 0
        try:
            while max_polls is None or polls < max_polls:
                polls += 1
                try:
                    updates = self.client.get_updates(self._offset, poll_timeout) or []
                except TelegramError as exc:
                    if exc.error_code == CONFLICT:
                        # 같은 토큰으로 봇이 두 군데서 돌면 업데이트가 나뉘어
                        # 버튼이 먹통처럼 보인다. 조용히 재시도하면 안 된다.
                        print(
                            "\n⚠️  같은 봇 토큰으로 다른 곳에서 이미 실행 중입니다.\n"
                            "   다른 터미널 창이나 서버에서 돌고 있는 krflow bot 을 끄세요.\n"
                            "   (둘이 번갈아 메시지를 가져가서 버튼이 안 먹는 것처럼 보입니다.)\n"
                        )
                    else:
                        print(f"폴링 실패, 5초 후 재시도: {exc}")
                    if self._stop.wait(5):
                        break
                    continue

                if updates:
                    self._debug(f"업데이트 {len(updates)}건 수신")

                for update in updates:
                    self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
                    try:
                        self.handle_update(update)
                    except TelegramError as exc:
                        print(f"업데이트 처리 실패: {exc}")
                    except Exception as exc:  # 한 메시지 때문에 봇이 죽지 않도록
                        print(f"업데이트 처리 중 오류: {type(exc).__name__}: {exc}")
        except KeyboardInterrupt:
            print("\n종료합니다.")
        finally:
            self._stop.set()
            self.provider.close()
        return 0


def _within_session(now: datetime) -> bool:
    """주기 전송을 보낼 시간대인가 (평일 08:50~15:40)."""
    if is_weekend(now):
        return False
    minutes = now.hour * 60 + now.minute
    return 8 * 60 + 50 <= minutes <= 15 * 60 + 40


def _due_daily_slot(now: datetime) -> tuple[str, str] | None:
    """지금이 장 시작/마감 요약을 보낼 시간대면 (키, 제목 접두어)."""
    if is_weekend(now):
        return None
    minutes = now.hour * 60 + now.minute
    for (hour, minute), key, prefix in DAILY_SLOTS:
        target = hour * 60 + minute
        if target <= minutes <= target + DAILY_GRACE_MIN:
            return key, prefix
    return None


def run_bot(
    provider: Provider,
    config: Config,
    *,
    market: str = "all",
    interval: float = 30.0,
    state_path=None,
    max_polls: int | None = None,
    verbose: bool = False,
) -> int:
    client = TelegramClient(config.telegram_token, timeout=config.request_timeout)
    store = ChatStore(state_path or (config.ensure_cache_dir() / "telegram_state.json"))
    bot = TelegramBot(
        client,
        provider,
        store,
        market=market,
        allowed_chat_ids=config.telegram_allowed_chat_ids,
        interval=interval,
        verbose=verbose,
    )
    return bot.run(max_polls=max_polls)
