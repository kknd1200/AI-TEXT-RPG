"""Provider 레지스트리."""

from __future__ import annotations

from ..config import Config
from .base import Provider, ProviderError

PROVIDER_NAMES = ("kis", "naver", "krx", "mock")

DESCRIPTIONS = {
    "kis": "한국투자증권 KIS Open API · 실시간 가집계 · 앱키 필요",
    "naver": "네이버 금융 스크래핑 · 장중 갱신 · 키 불필요",
    "krx": "KRX 일별 확정치 (pykrx) · 실시간 아님 · 검증용",
    "mock": "오프라인 데모 데이터 · 네트워크 불필요",
}


def create(name: str, config: Config | None = None, **kwargs) -> Provider:
    name = (name or "").lower()
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
    """가능한 가장 좋은 소스를 자동 선택: KIS -> 네이버."""
    if config is not None and config.has_kis:
        return create("kis", config=config, **kwargs)
    try:
        return create("kis", config=config, **kwargs)
    except ProviderError:
        return create("naver", config=config, **kwargs)


__all__ = ["Provider", "ProviderError", "create", "create_auto", "PROVIDER_NAMES", "DESCRIPTIONS"]
