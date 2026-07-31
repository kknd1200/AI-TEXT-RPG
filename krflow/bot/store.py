"""텔레그램 채팅별 설정·구독 상태 영속화 (JSON 파일)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    "investor": "both",
    "side": "buy",
    "metric": "value",
    "market": "all",
    "top": 10,
}

SETTING_KEYS = tuple(DEFAULT_SETTINGS)


class ChatStore:
    """채팅방 하나당 설정 + 자동 전송 구독 상태를 보관한다."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {"chats": {}}
        self._load()

    # ------------------------------------------------------------ 파일 입출력
    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(loaded, dict) and isinstance(loaded.get("chats"), dict):
            self._data = loaded

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def _chat(self, chat_id: int) -> dict[str, Any]:
        chats = self._data.setdefault("chats", {})
        return chats.setdefault(
            str(chat_id),
            {
                "settings": dict(DEFAULT_SETTINGS),
                "watch_minutes": 0,
                "last_watch_sent": 0.0,
                "daily": False,
                "daily_marks": [],
            },
        )

    # -------------------------------------------------------------- 설정 조회
    def settings(self, chat_id: int) -> dict[str, Any]:
        with self._lock:
            stored = self._chat(chat_id)["settings"]
            return {**DEFAULT_SETTINGS, **stored}

    def update_settings(self, chat_id: int, **changes) -> dict[str, Any]:
        with self._lock:
            chat = self._chat(chat_id)
            for key, value in changes.items():
                if key in SETTING_KEYS:
                    chat["settings"][key] = value
            self._save()
            return {**DEFAULT_SETTINGS, **chat["settings"]}

    # -------------------------------------------------------- 주기 전송 구독
    def set_watch(self, chat_id: int, minutes: int) -> None:
        with self._lock:
            chat = self._chat(chat_id)
            chat["watch_minutes"] = max(0, int(minutes))
            chat["last_watch_sent"] = 0.0
            self._save()

    def watch_minutes(self, chat_id: int) -> int:
        with self._lock:
            return int(self._chat(chat_id).get("watch_minutes", 0))

    def due_watchers(self, now_ts: float) -> list[int]:
        """지금 자동 전송을 보내야 할 채팅 목록."""
        with self._lock:
            due = []
            for raw_id, chat in self._data.get("chats", {}).items():
                minutes = int(chat.get("watch_minutes", 0))
                if minutes <= 0:
                    continue
                last = float(chat.get("last_watch_sent", 0.0))
                if now_ts - last >= minutes * 60:
                    due.append(int(raw_id))
            return due

    def mark_watch_sent(self, chat_id: int, now_ts: float) -> None:
        with self._lock:
            self._chat(chat_id)["last_watch_sent"] = float(now_ts)
            self._save()

    # ------------------------------------------------------ 장 시작/마감 요약
    def set_daily(self, chat_id: int, enabled: bool) -> None:
        with self._lock:
            self._chat(chat_id)["daily"] = bool(enabled)
            self._save()

    def daily_enabled(self, chat_id: int) -> bool:
        with self._lock:
            return bool(self._chat(chat_id).get("daily", False))

    def daily_chats(self) -> list[int]:
        with self._lock:
            return [
                int(raw_id)
                for raw_id, chat in self._data.get("chats", {}).items()
                if chat.get("daily")
            ]

    def claim_daily(self, chat_id: int, mark: str) -> bool:
        """이 채팅에 대해 `mark`(예: '20260731-open')를 처음 소비하면 True.

        같은 마크로 두 번 호출하면 False — 중복 전송을 막는다.
        """
        with self._lock:
            chat = self._chat(chat_id)
            marks = chat.setdefault("daily_marks", [])
            if mark in marks:
                return False
            marks.append(mark)
            # 최근 것만 남긴다 (파일이 무한정 커지지 않도록)
            del marks[:-10]
            self._save()
            return True

    def known_chats(self) -> list[int]:
        with self._lock:
            return [int(raw_id) for raw_id in self._data.get("chats", {})]
