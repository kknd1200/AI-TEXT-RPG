"""한국거래소 영업시간 관련 유틸 (KST 기준)."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _kst():
    """Asia/Seoul 시간대. 시간대 DB가 없으면 고정 오프셋으로 대체한다.

    윈도우에는 시스템 tz 데이터베이스가 없어 `tzdata` 패키지가 필요한데,
    설치가 누락돼도 프로그램이 죽지 않게 한다. 한국은 서머타임을 쓰지
    않으므로 UTC+9 고정 오프셋으로도 동작에 차이가 없다.
    """
    try:
        return ZoneInfo("Asia/Seoul")
    except (ZoneInfoNotFoundError, KeyError, ModuleNotFoundError):
        return timezone(timedelta(hours=9), "KST")


KST = _kst()

OPEN = time(9, 0)
CLOSE = time(15, 30)
# 시간외 단일가까지 (18:00) 는 수급 집계가 갱신되지 않으므로 참고용
AFTER_HOURS_END = time(18, 0)

PHASE_LABEL = {
    "pre": "장 시작 전",
    "open": "장중",
    "after": "장 마감",
    "closed": "휴장",
}


def now_kst() -> datetime:
    return datetime.now(KST)


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def is_weekend(dt: datetime | None = None) -> bool:
    dt = to_kst(dt or now_kst())
    return dt.weekday() >= 5


def market_phase(dt: datetime | None = None) -> str:
    """장 상태를 반환한다: pre | open | after | closed.

    공휴일 휴장은 반영하지 않는다(거래소 휴장일 캘린더가 필요).
    주말만 'closed' 로 처리하고, 공휴일에는 'pre'/'after' 로 보이지만
    데이터가 갱신되지 않는 것으로 사용자가 알 수 있다.
    """
    dt = to_kst(dt or now_kst())
    if is_weekend(dt):
        return "closed"
    t = dt.time()
    if t < OPEN:
        return "pre"
    if t <= CLOSE:
        return "open"
    return "after"


def phase_label(dt: datetime | None = None) -> str:
    return PHASE_LABEL[market_phase(dt)]


def is_open(dt: datetime | None = None) -> bool:
    return market_phase(dt) == "open"


def last_business_day(dt: datetime | None = None) -> datetime:
    """직전(또는 당일) 영업일을 반환. 공휴일은 고려하지 않는다."""
    dt = to_kst(dt or now_kst())
    if dt.time() < OPEN:
        dt = dt - timedelta(days=1)
    while dt.weekday() >= 5:
        dt = dt - timedelta(days=1)
    return dt


def yyyymmdd(dt: datetime | None = None) -> str:
    return to_kst(dt or now_kst()).strftime("%Y%m%d")
