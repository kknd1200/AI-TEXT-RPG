"""데이터 소스 공통 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Snapshot


class ProviderError(RuntimeError):
    """데이터 소스에서 데이터를 못 가져왔을 때."""


class Provider(ABC):
    #: CLI 에서 쓰는 식별자
    name: str = "base"
    #: 화면에 띄울 한글 이름
    label: str = ""
    #: 실시간이 아니면 True
    delayed: bool = False
    #: 데이터 성격 설명
    note: str = ""
    #: 이 소스가 안전하게 견딜 수 있는 최소 폴링 주기(초)
    min_interval: float = 5.0

    @abstractmethod
    def fetch(self, market: str = "all") -> Snapshot:
        """market: all | kospi | kosdaq"""

    def close(self) -> None:  # pragma: no cover - 기본 구현은 할 일 없음
        pass

    def __enter__(self) -> "Provider":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
