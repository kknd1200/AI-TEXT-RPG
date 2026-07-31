"""키움증권 REST API provider.

'외국인기관매매상위요청'(api-id `ka90009`) 을 호출해 외국인·기관 순매수/순매도
상위 종목을 가져온다.

  POST /oauth2/token          (접근토큰 발급, grant_type=client_credentials)
  POST /api/dostk/rkinfo      (api-id: ka90009)

주의: 구버전 **키움 OpenAPI+ (OCX/COM)** 와는 다른 물건이다. 이 provider 는
openapi.kiwoom.com 포털에서 발급하는 **앱키/시크릿키 기반 REST API** 전용이며,
운영체제 제약 없이 서버에서 24시간 돌릴 수 있다.

응답 구조: 한 행(row)에 '외국인 순매도 / 외국인 순매수 / 기관 순매도 / 기관 순매수'
네 갈래의 N위 종목이 나란히 담겨 온다. 이를 종목코드 기준으로 합쳐 FlowRow 로
정규화한다. 순매도 목록의 값은 서버가 부호를 어떻게 주든 음수로 고정한다.
"""

from __future__ import annotations

import json
import re
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
    "real": "https://api.kiwoom.com",
    "mock": "https://mockapi.kiwoom.com",
}

TOKEN_PATH = "/oauth2/token"
RANK_PATH = "/api/dostk/rkinfo"
RANK_API_ID = "ka90009"

# mrkt_tp: 000 전체 / 001 코스피 / 101 코스닥
MARKET_CODE = {"all": "000", "kospi": "001", "kosdaq": "101"}
MARKET_OF_CODE = {"000": "all", "001": "kospi", "101": "kosdaq"}

# amt_qty_tp: 1 금액 / 2 수량
AMT = "1"
QTY = "2"

TOKEN_FILE = "kiwoom_token.json"
TOKEN_SAFETY_MARGIN = timedelta(minutes=10)

#: 응답 목록이 담기는 키 후보
LIST_KEYS = ("frgnr_orgn_trde_upper", "frgn_orgn_trde_upper", "output")

#: (투자자, 매매구분) -> 필드 접두어 후보
GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("foreign", "buy", ("for_netprps", "frgn_netprps", "frgnr_netprps")),
    ("foreign", "sell", ("for_netslmt", "frgn_netslmt", "frgnr_netslmt")),
    ("inst", "buy", ("orgn_netprps", "org_netprps")),
    ("inst", "sell", ("orgn_netslmt", "org_netslmt")),
)

#: ka90009 의 금액 필드는 백만원 단위 — 내부 단위와 동일하므로 변환하지 않는다.
AMOUNT_UNIT_MKRW = 1.0

_NON_DIGIT = re.compile(r"\D")


def _to_float(value: Any) -> float | None:
    """'+000012345', '--1,234', '  -12 ' 같은 키움식 숫자 문자열을 숫자로."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace(" ", "")
    if not text:
        return None
    negative = text.startswith("-")
    text = text.lstrip("+-")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def normalize_code(raw: Any) -> str:
    """'A005930', '005930_AL' 등에서 6자리 종목코드만 뽑는다."""
    digits = _NON_DIGIT.sub("", str(raw or ""))
    return digits[:6] if len(digits) >= 6 else ""


def _field(item: dict, prefixes: tuple[str, ...], suffix: str) -> Any:
    for prefix in prefixes:
        key = f"{prefix}_{suffix}"
        if key in item:
            return item[key]
    return None


class KiwoomTokenStore:
    """접근토큰 파일 캐시. 발급 호출에 제한이 있어 재시작 사이에도 공유한다."""

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
            return data.get("token") or None

    def write(self, app_key: str, token: str, expires_at: datetime) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(
                    {"app_key": app_key, "token": token, "expires_at": expires_at.isoformat()}
                ),
                encoding="utf-8",
            )
            tmp.replace(self.path)
            try:
                self.path.chmod(0o600)
            except OSError:  # pragma: no cover - 플랫폼 차이
                pass


class _Unauthorized(Exception):
    """내부용: 401 이면 토큰 재발급 경로로 보낸다."""


class KiwoomProvider(Provider):
    name = "kiwoom"
    label = "키움증권 REST API"
    delayed = False
    note = "장중 집계 · 외국인기관매매상위(ka90009)"
    min_interval = 3.0

    def __init__(
        self,
        config: Config | None = None,
        session: requests.Session | None = None,
        include_qty: bool = True,
    ) -> None:
        self.config = config or load_config()
        if not self.config.has_kiwoom:
            raise ProviderError(
                "KIWOOM_APP_KEY / KIWOOM_APP_SECRET 이 설정되지 않았습니다. "
                ".env 파일이나 환경변수로 지정하세요 (.env.example 참고)."
            )
        self.base_url = BASE_URLS[self.config.kiwoom_env]
        self.session = session or requests.Session()
        self._tokens = KiwoomTokenStore(self.config.ensure_cache_dir(), self.config.kiwoom_env)
        self._token: str | None = None
        # 금액 정렬 응답과 수량 정렬 응답을 합쳐 두 지표를 모두 채운다.
        self.include_qty = include_qty

    # ------------------------------------------------------------------ auth
    def access_token(self, force: bool = False) -> str:
        if not force:
            if self._token:
                return self._token
            cached = self._tokens.read(self.config.kiwoom_app_key)
            if cached:
                self._token = cached
                return cached

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.config.kiwoom_app_key,
            "secretkey": self.config.kiwoom_app_secret,
        }
        try:
            resp = self.session.post(
                self.base_url + TOKEN_PATH,
                json=payload,
                headers={"Content-Type": "application/json;charset=UTF-8"},
                timeout=self.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"키움 토큰 발급 요청 실패: {exc}") from exc

        if resp.status_code != 200:
            raise ProviderError(
                f"키움 토큰 발급 실패 (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        if str(data.get("return_code", "0")) not in ("0", "None"):
            raise ProviderError(f"키움 토큰 발급 거부: {data.get('return_msg') or data}")

        token = data.get("token") or data.get("access_token")
        if not token:
            raise ProviderError(f"키움 토큰 응답에 token 이 없습니다: {data}")

        self._tokens.write(self.config.kiwoom_app_key, token, _parse_expiry(data))
        self._token = token
        return token

    # ----------------------------------------------------------------- fetch
    def _request_rank(self, market_code: str, amt_qty_tp: str, token: str) -> dict:
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token}",
            "cont-yn": "N",
            "next-key": "",
            "api-id": RANK_API_ID,
        }
        body = {
            "mrkt_tp": market_code,
            "amt_qty_tp": amt_qty_tp,
            "qry_dt_tp": "1",  # 조회일자 포함(당일)
            "stex_tp": "3",  # 3=통합(KRX+NXT)
        }
        try:
            resp = self.session.post(
                self.base_url + RANK_PATH,
                headers=headers,
                json=body,
                timeout=self.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"키움 수급 조회 요청 실패: {exc}") from exc

        if resp.status_code == 401:
            raise _Unauthorized(resp.text[:200])
        if resp.status_code != 200:
            raise ProviderError(
                f"키움 수급 조회 실패 (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        code = str(data.get("return_code", "0"))
        if code not in ("0", "None"):
            raise ProviderError(
                f"키움 응답 오류 (return_code={code}): {data.get('return_msg') or ''}"
            )
        return data

    def _call(self, market_code: str, amt_qty_tp: str) -> dict:
        token = self.access_token()
        try:
            return self._request_rank(market_code, amt_qty_tp, token)
        except _Unauthorized:
            token = self.access_token(force=True)
            return self._request_rank(market_code, amt_qty_tp, token)

    def fetch(self, market: str = "all") -> Snapshot:
        market_code = MARKET_CODE.get(market)
        if market_code is None:
            raise ProviderError(f"지원하지 않는 시장 구분입니다: {market}")

        by_amount = parse_rank_response(self._call(market_code, AMT), market)
        merged = {row.code: row for row in by_amount}

        if self.include_qty:
            for row in parse_rank_response(self._call(market_code, QTY), market):
                existing = merged.get(row.code)
                if existing is None:
                    merged[row.code] = row
                else:
                    # 금액은 금액 정렬 응답에서, 수량은 수량 정렬 응답에서 취한다.
                    merged[row.code] = FlowRow(
                        code=existing.code,
                        name=existing.name or row.name,
                        market=existing.market,
                        foreign_value=existing.foreign_value,
                        inst_value=existing.inst_value,
                        foreign_qty=row.foreign_qty or existing.foreign_qty,
                        inst_qty=row.inst_qty or existing.inst_qty,
                    )

        if not merged:
            raise ProviderError(
                "키움 응답에 종목이 없습니다. 장 시작 전이거나 휴장일일 수 있습니다."
            )

        return Snapshot(
            rows=list(merged.values()),
            source=self.name,
            as_of=now_kst(),
            market=market,
            delayed=self.delayed,
            note=self.note,
            meta={"env": self.config.kiwoom_env, "api_id": RANK_API_ID},
        )

    def close(self) -> None:
        self.session.close()


def _parse_expiry(data: dict) -> datetime:
    raw = str(data.get("expires_dt") or "").strip()
    if len(raw) == 14 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=KST)
        except ValueError:
            pass
    seconds = _to_float(data.get("expires_in")) or 60 * 60 * 24
    return now_kst() + timedelta(seconds=seconds)


def parse_rank_response(data: dict, market: str = "all") -> list[FlowRow]:
    """ka90009 응답 -> FlowRow 목록.

    한 행에 담긴 네 갈래(외인 순매수/순매도, 기관 순매수/순매도)를 풀어
    종목코드 기준으로 합친다. 순매도는 부호를 음수로 고정한다.
    """
    listing: list = []
    for key in LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            listing = value
            break
        if isinstance(value, dict):
            listing = [value]
            break

    acc: dict[str, dict[str, Any]] = {}
    for item in listing:
        if not isinstance(item, dict):
            continue
        for investor, side, prefixes in GROUPS:
            code = normalize_code(_field(item, prefixes, "stk_cd"))
            if not code:
                continue
            name = str(_field(item, prefixes, "stk_nm") or "").strip()
            amount = _to_float(_field(item, prefixes, "amt"))
            quantity = _to_float(_field(item, prefixes, "qty"))
            sign = 1.0 if side == "buy" else -1.0

            entry = acc.setdefault(
                code,
                {
                    "name": "",
                    "foreign_value": 0.0,
                    "foreign_qty": 0.0,
                    "inst_value": 0.0,
                    "inst_qty": 0.0,
                },
            )
            if name and not entry["name"]:
                entry["name"] = name
            if amount is not None:
                entry[f"{investor}_value"] = sign * abs(amount) * AMOUNT_UNIT_MKRW
            if quantity is not None:
                entry[f"{investor}_qty"] = sign * abs(quantity)

    return [
        FlowRow(
            code=code,
            name=entry["name"] or code,
            market=market,
            foreign_value=entry["foreign_value"],
            foreign_qty=entry["foreign_qty"],
            inst_value=entry["inst_value"],
            inst_qty=entry["inst_qty"],
        )
        for code, entry in acc.items()
    ]
