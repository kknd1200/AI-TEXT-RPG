"""한국투자증권 KIS Open API provider.

국내주식 '외국인/기관 매매종목 가집계' API 를 호출해 장중 실시간(가집계)
외국인·기관 순매수 현황을 가져온다.

  POST /oauth2/tokenP                                          (접근토큰 발급)
  GET  /uapi/domestic-stock/v1/quotations/foreign-institution-total
       tr_id = FHPTJ04400000

정렬은 서버 파라미터에 의존하지 않고 '전체' 를 받아 클라이언트에서 수행한다.
서버 정렬 파라미터 의미가 문서 개정에 따라 바뀌어도 결과가 흔들리지 않는다.

준비물: https://apiportal.koreainvestment.com 에서 앱키/앱시크릿 발급 후
        .env 에 KIS_APP_KEY / KIS_APP_SECRET 설정.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from ..config import Config, load_config
from ..market import KST, now_kst
from ..models import FlowRow, Snapshot
from .base import Provider, ProviderError

BASE_URLS = {
    "real": "https://openapi.koreainvestment.com:9443",
    "vts": "https://openapivts.koreainvestment.com:29443",
}

TOKEN_PATH = "/oauth2/tokenP"
RANK_PATH = "/uapi/domestic-stock/v1/quotations/foreign-institution-total"
RANK_TR_ID = "FHPTJ04400000"

# FID_INPUT_ISCD: 0000 전체 / 0001 코스피 / 1001 코스닥 / 2001 코스피200
MARKET_CODE = {
    "all": "0000",
    "kospi": "0001",
    "kosdaq": "1001",
    "kospi200": "2001",
}

#: 토큰 발급은 분당 1회 제한이 있어 파일에 캐시한다.
TOKEN_FILE = "kis_token.json"
TOKEN_SAFETY_MARGIN = timedelta(minutes=10)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in ("-", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _pick(item: dict, *keys: str) -> float | None:
    """응답 필드명이 문서 개정으로 바뀌어도 견디도록 후보를 순회한다."""
    for key in keys:
        if key in item:
            value = _to_float(item[key])
            if value is not None:
                return value
    return None


class KisTokenStore:
    """접근토큰 파일 캐시 (프로세스 재시작·다중 실행 사이에서 공유)."""

    def __init__(self, cache_dir: Path, env: str) -> None:
        self.path = Path(cache_dir) / f"{env}_{TOKEN_FILE}"
        self._lock = threading.Lock()

    def read(self, app_key: str) -> str | None:
        with self._lock:
            if not self.path.is_file():
                return None
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if data.get("app_key") != app_key:
                return None
            try:
                expires = datetime.fromisoformat(data["expires_at"])
            except (KeyError, ValueError):
                return None
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=KST)
            if now_kst() >= expires - TOKEN_SAFETY_MARGIN:
                return None
            return data.get("access_token") or None

    def write(self, app_key: str, token: str, expires_at: datetime) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "app_key": app_key,
                "access_token": token,
                "expires_at": expires_at.isoformat(),
            }
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self.path)
            try:
                self.path.chmod(0o600)
            except OSError:  # pragma: no cover - 플랫폼 차이
                pass


class KisProvider(Provider):
    name = "kis"
    label = "한국투자증권 KIS Open API"
    delayed = False
    note = "장중 가집계(잠정치) · 장 마감 후 확정치와 다를 수 있음"
    min_interval = 3.0

    def __init__(self, config: Config | None = None, session: requests.Session | None = None) -> None:
        self.config = config or load_config()
        if not self.config.has_kis:
            raise ProviderError(
                "KIS_APP_KEY / KIS_APP_SECRET 이 설정되지 않았습니다. "
                ".env 파일이나 환경변수로 지정하세요 (.env.example 참고)."
            )
        self.base_url = BASE_URLS[self.config.kis_env]
        self.session = session or requests.Session()
        self._tokens = KisTokenStore(self.config.ensure_cache_dir(), self.config.kis_env)
        self._token: str | None = None

    # ------------------------------------------------------------------ auth
    def access_token(self, force: bool = False) -> str:
        if not force:
            if self._token:
                return self._token
            cached = self._tokens.read(self.config.kis_app_key)
            if cached:
                self._token = cached
                return cached

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.kis_app_key,
            "appsecret": self.config.kis_app_secret,
        }
        try:
            resp = self.session.post(
                self.base_url + TOKEN_PATH,
                json=payload,
                headers={"content-type": "application/json"},
                timeout=self.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"KIS 토큰 발급 요청 실패: {exc}") from exc

        if resp.status_code != 200:
            raise ProviderError(
                f"KIS 토큰 발급 실패 (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise ProviderError(f"KIS 토큰 응답에 access_token 이 없습니다: {data}")

        expires_at = self._parse_expiry(data)
        self._tokens.write(self.config.kis_app_key, token, expires_at)
        self._token = token
        return token

    @staticmethod
    def _parse_expiry(data: dict) -> datetime:
        raw = data.get("access_token_token_expired")
        if raw:
            try:
                return datetime.strptime(str(raw), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
            except ValueError:
                pass
        seconds = _to_float(data.get("expires_in")) or 60 * 60 * 24
        return now_kst() + timedelta(seconds=seconds)

    # ----------------------------------------------------------------- fetch
    def _request_rank(self, market_code: str, token: str) -> dict:
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.config.kis_app_key,
            "appsecret": self.config.kis_app_secret,
            "tr_id": RANK_TR_ID,
            "custtype": "P",
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "V",
            "FID_COND_SCR_DIV_CODE": "16449",
            "FID_INPUT_ISCD": market_code,
            "FID_DIV_CLS_CODE": "0",
            "FID_RANK_SORT_CLS_CODE": "0",
            "FID_ETC_CLS_CODE": "0",  # 0=전체(외국인·기관 모두 내려받아 로컬 정렬)
        }
        try:
            resp = self.session.get(
                self.base_url + RANK_PATH,
                headers=headers,
                params=params,
                timeout=self.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"KIS 수급 조회 요청 실패: {exc}") from exc

        if resp.status_code == 401:
            raise _Unauthorized(resp.text[:200])
        if resp.status_code != 200:
            raise ProviderError(
                f"KIS 수급 조회 실패 (HTTP {resp.status_code}): {resp.text[:200]}"
            )
        return resp.json()

    def fetch(self, market: str = "all") -> Snapshot:
        market_code = MARKET_CODE.get(market)
        if market_code is None:
            raise ProviderError(f"지원하지 않는 시장 구분입니다: {market}")

        token = self.access_token()
        try:
            data = self._request_rank(market_code, token)
        except _Unauthorized:
            # 토큰이 만료·폐기된 경우 한 번만 재발급 후 재시도
            token = self.access_token(force=True)
            data = self._request_rank(market_code, token)

        rt_cd = str(data.get("rt_cd", "0"))
        if rt_cd != "0":
            raise ProviderError(
                f"KIS 응답 오류 (rt_cd={rt_cd}): {data.get('msg1') or data.get('msg_cd')}"
            )

        rows = parse_rank_response(data, market)
        if not rows:
            raise ProviderError(
                "KIS 응답에 종목이 없습니다. 장 시작 전이거나 휴장일일 수 있습니다."
            )

        return Snapshot(
            rows=rows,
            source=self.name,
            as_of=now_kst(),
            market=market,
            delayed=self.delayed,
            note=self.note,
            meta={"env": self.config.kis_env, "tr_id": RANK_TR_ID},
        )

    def close(self) -> None:
        self.session.close()


class _Unauthorized(Exception):
    """내부용: 401 을 만나면 토큰 재발급 경로로 보낸다."""


def parse_rank_response(data: dict, market: str = "all") -> list[FlowRow]:
    """KIS 매매 가집계 응답 -> FlowRow 목록.

    금액 필드(`*_tr_pbmn`)는 KIS 규격상 백만원 단위이며, 본 모듈의 내부
    단위와 동일하므로 변환 없이 그대로 쓴다.
    """
    output = data.get("output") or data.get("output1") or data.get("output2") or []
    if isinstance(output, dict):
        output = [output]

    rows: list[FlowRow] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        code = str(item.get("mksc_shrn_iscd") or item.get("stck_shrn_iscd") or "").strip()
        name = str(item.get("hts_kor_isnm") or item.get("prdt_abrv_name") or "").strip()
        if not code:
            continue

        change = _pick(item, "prdy_vrss")
        sign = str(item.get("prdy_vrss_sign") or "").strip()
        # KIS 등락 부호: 1 상한 2 상승 3 보합 4 하한 5 하락
        if change is not None and sign in ("4", "5"):
            change = -abs(change)

        rows.append(
            FlowRow(
                code=code,
                name=name or code,
                market=market,
                price=_pick(item, "stck_prpr"),
                change=change,
                change_pct=_pick(item, "prdy_ctrt"),
                volume=_pick(item, "acml_vol"),
                foreign_qty=_pick(item, "frgn_ntby_qty", "frgn_ntby_qty_icdc") or 0.0,
                foreign_value=_pick(item, "frgn_ntby_tr_pbmn", "frgn_ntby_pbmn") or 0.0,
                inst_qty=_pick(item, "orgn_ntby_qty", "orgn_ntby_qty_icdc") or 0.0,
                inst_value=_pick(item, "orgn_ntby_tr_pbmn", "orgn_ntby_pbmn") or 0.0,
            )
        )
    return rows
