"""Provider 레지스트리."""

from __future__ import annotations

from ..config import Config
from .base import Provider, ProviderError

PROVIDER_NAMES = ("kiwoom", "kis", "naver", "krx", "mock")

DESCRIPTIONS = {
    "kiwoom": "키움증권 REST API · 실시간 집계 · 앱키 필요",
    "kis": "한국투자증권 KIS Open API · 실시간 가집계 · 앱키 필요",
    "naver": "네이버 금융 스크래핑 · 장중 갱신 · 키 불필요",
    "krx": "KRX 일별 확정치 (pykrx) · 실시간 아님 · 검증용",
    "mock": "오프라인 데모 데이터 · 네트워크 불필요",
}

#: auto 가 시도하는 순서
AUTO_ORDER = ("kiwoom", "kis", "naver")


def create(name: str, config: Config | None = None, **kwargs) -> Provider:
    name = (name or "").lower()
    if name == "kiwoom":
        from .kiwoom import KiwoomProvider

        return KiwoomProvider(config=config)
    if name == "kis":
        from .kis import KisProvider

        return KisProvider(config=config)
    if name == "naver":
        from .naver import NaverProvider

        return NaverProvider(config=config)
    if name == "krx":
        from .krx import KrxProvider

        return KrxProvider(date=kwargs.get("date"))
    if name == "mock":
        from .mock import MockProvider

        return MockProvider(seed=kwargs.get("seed"))
    raise ProviderError(
        f"알 수 없는 provider: {name!r} (사용 가능: {', '.join(PROVIDER_NAMES)})"
    )


def create_auto(config: Config | None = None, **kwargs) -> Provider:
    """설정된 키에 따라 가장 좋은 소스를 고른다: 키움 -> KIS -> 네이버."""
    last_error: ProviderError | None = None
    for name in AUTO_ORDER:
        try:
            return create(name, config=config, **kwargs)
        except ProviderError as exc:
            last_error = exc
    raise last_error or ProviderError("사용 가능한 데이터 소스가 없습니다.")


__all__ = [
    "Provider",
    "ProviderError",
    "create",
    "create_auto",
    "PROVIDER_NAMES",
    "DESCRIPTIONS",
    "AUTO_ORDER",
]
