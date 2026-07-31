"""여러 소비자(웹 탭·텔레그램 채팅)가 붙어도 소스는 주기당 한 번만 호출한다."""

from __future__ import annotations

import threading
import time

from .models import Snapshot
from .providers.base import Provider, ProviderError


class SnapshotCache:
    def __init__(self, provider: Provider, market: str, ttl: float) -> None:
        self.provider = provider
        self.market = market
        self.ttl = max(ttl, provider.min_interval)
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._fetched_at = 0.0
        self._error: str | None = None

    def get(self, force: bool = False) -> tuple[Snapshot | None, str | None]:
        with self._lock:
            fresh = self._snapshot is not None and (time.monotonic() - self._fetched_at) < self.ttl
            if fresh and not force:
                return self._snapshot, self._error
            try:
                self._snapshot = self.provider.fetch(self.market)
                self._error = None
            except Exception as exc:
                # 소스가 죽어도 서비스는 살아 있어야 하므로 직전 스냅샷을 유지한다.
                self._error = (
                    str(exc) if isinstance(exc, ProviderError) else f"{type(exc).__name__}: {exc}"
                )
            self._fetched_at = time.monotonic()
            return self._snapshot, self._error
