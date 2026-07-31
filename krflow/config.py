"""설정 로딩: 환경변수 + .env 파일."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENV_FILE = ".env"


def _cache_dir() -> Path:
    base = os.environ.get("KRFLOW_HOME")
    if base:
        return Path(base).expanduser()
    return Path.home() / ".krflow"


def load_env_file(path: str | Path = DEFAULT_ENV_FILE) -> dict[str, str]:
    """아주 단순한 .env 파서 (KEY=VALUE, # 주석, 따옴표 제거)."""
    p = Path(path)
    if not p.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


@dataclass
class Config:
    kis_app_key: str = ""
    kis_app_secret: str = ""
    kis_env: str = "real"  # real | vts
    request_timeout: float = 10.0
    cache_dir: Path = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.cache_dir is None:
            self.cache_dir = _cache_dir()
        self.cache_dir = Path(self.cache_dir)

    @property
    def has_kis(self) -> bool:
        return bool(self.kis_app_key and self.kis_app_secret)

    def ensure_cache_dir(self) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir


def load_config(env_file: str | Path = DEFAULT_ENV_FILE) -> Config:
    """.env 를 읽고 실제 환경변수로 덮어쓴다(환경변수 우선)."""
    merged = {**load_env_file(env_file), **os.environ}

    def get(key: str, default: str = "") -> str:
        return str(merged.get(key, default) or default).strip()

    timeout_raw = get("KRFLOW_TIMEOUT", "10")
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 10.0

    kis_env = get("KIS_ENV", "real").lower()
    if kis_env not in ("real", "vts"):
        kis_env = "real"

    return Config(
        kis_app_key=get("KIS_APP_KEY"),
        kis_app_secret=get("KIS_APP_SECRET"),
        kis_env=kis_env,
        request_timeout=timeout,
    )
