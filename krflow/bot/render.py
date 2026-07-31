"""텔레그램 메시지 렌더링 (HTML parse_mode).

모바일 화면에 맞춰 고정폭 <pre> 블록으로 표를 그린다. 한글이 전각이라
`fmt.pad` 로 표시 폭 기준 정렬을 맞춘다.
"""

from __future__ import annotations

from html import escape

from .. import fmt
from ..market import phase_label
from ..models import MARKET_LABEL, Snapshot
from ..ranking import INVESTOR_LABEL, METRIC_LABEL, SIDE_LABEL, rank, totals

NAME_WIDTH = 10
#: 숫자 열의 최소 폭. 실제 값이 더 길면 아래에서 넓혀 잡는다.
MIN_NUM_WIDTH = 7

HELP = """<b>krflow 수급 봇</b>

/top — 현재 설정으로 수급 상위 조회
/watch <i>분</i> — 장중에 N분마다 자동 전송 (예: <code>/watch 5</code>)
/stop — 자동 전송 해제
/daily <i>on|off</i> — 장 시작(09:05)·마감(15:35) 요약
/status — 현재 설정과 구독 상태
/help — 이 도움말

조회 조건은 메시지 아래 버튼으로 바꿉니다.
표시 단위는 금액=억원, 수량=천주이며 순매수는 +, 순매도는 - 입니다."""


def _table(rows, metric: str) -> str:
    summary = totals(rows)
    cells = [
        [fmt.metric_str(row.metric(who, metric), metric) for who in ("foreign", "inst", "both")]
        for row in rows
    ]
    footer_cells = [fmt.metric_str(summary[f"{who}_{metric}"], metric) for who in ("foreign", "inst", "both")]

    # 큰 값(조 단위 금액, 억 주 단위 수량)에서도 열이 밀리지 않게 실제 폭에 맞춘다.
    num_width = max(
        MIN_NUM_WIDTH,
        max(
            (fmt.display_width(text) + 1 for text in [*sum(cells, []), *footer_cells]),
            default=MIN_NUM_WIDTH,
        ),
    )

    def line(rank: str, name: str, values: list[str]) -> str:
        return (
            fmt.pad(rank, 2, "right")
            + " "
            + fmt.pad(name, NAME_WIDTH)
            + "".join(fmt.pad(text, num_width, "right") for text in values)
        )

    rule = "─" * (2 + 1 + NAME_WIDTH + num_width * 3)
    lines = [line("#", "종목", ["외인", "기관", "합계"]), rule]
    for idx, values in enumerate(cells, start=1):
        lines.append(line(str(idx), rows[idx - 1].name, values))
    lines.append(rule)
    lines.append(line("", "합계", footer_cells))
    return "\n".join(lines)


def render_snapshot(
    snapshot: Snapshot | None,
    settings: dict,
    *,
    error: str | None = None,
    title_prefix: str = "",
) -> str:
    if snapshot is None:
        return f"⚠️ 데이터를 가져오지 못했습니다.\n<code>{escape(error or '알 수 없는 오류')}</code>"

    investor = settings["investor"]
    metric = settings["metric"]
    side = settings["side"]
    market = settings["market"]

    ranked = rank(
        snapshot.rows,
        investor=investor,
        metric=metric,
        side=side,
        top=int(settings["top"]),
        market=market if market in ("kospi", "kosdaq") else snapshot.market,
    )

    icon = "📈" if side == "buy" else "📉"
    head = (
        f"{icon} <b>{escape(title_prefix)}{MARKET_LABEL.get(market, market)} · "
        f"{INVESTOR_LABEL[investor]} {SIDE_LABEL[side]}</b>"
    )
    meta = (
        f"<i>{METRIC_LABEL[metric]} 기준 ({fmt.metric_unit(metric)}) · "
        f"{snapshot.as_of.strftime('%m-%d %H:%M')} KST · {phase_label()} · "
        f"{escape(snapshot.source)}{' · 지연' if snapshot.delayed else ''}</i>"
    )

    if not ranked:
        body = "조건에 맞는 종목이 없습니다."
        return f"{head}\n{meta}\n\n{body}"

    parts = [head, meta, "", f"<pre>{escape(_table(ranked, metric))}</pre>"]
    if error:
        parts.append(f"<i>⚠️ 갱신 실패, 직전 데이터입니다: {escape(error)}</i>")
    return "\n".join(parts)


def render_status(settings: dict, watch_minutes: int, daily: bool, provider_label: str) -> str:
    watch = f"{watch_minutes}분마다" if watch_minutes > 0 else "꺼짐"
    return (
        "<b>현재 설정</b>\n"
        f"· 시장: {MARKET_LABEL.get(settings['market'], settings['market'])}\n"
        f"· 투자자: {INVESTOR_LABEL[settings['investor']]}\n"
        f"· 정렬: {SIDE_LABEL[settings['side']]} ({METRIC_LABEL[settings['metric']]})\n"
        f"· 표시 개수: {settings['top']}\n"
        f"· 자동 전송: {watch}\n"
        f"· 장 시작/마감 요약: {'켜짐' if daily else '꺼짐'}\n"
        f"· 데이터 소스: {escape(provider_label)}"
    )


# ------------------------------------------------------------------- 인라인 키보드

BUTTONS = {
    "investor": [("외국인", "foreign"), ("기관", "inst"), ("합산", "both")],
    "side": [("순매수", "buy"), ("순매도", "sell")],
    "market": [("전체", "all"), ("코스피", "kospi"), ("코스닥", "kosdaq")],
    "metric": [("금액", "value"), ("수량", "qty")],
}


def keyboard(settings: dict) -> dict:
    """현재 선택에 ● 표시를 붙인 인라인 키보드."""

    def row(field: str) -> list[dict]:
        return [
            {
                "text": ("● " if settings.get(field) == value else "") + label,
                "callback_data": f"s:{field}:{value}",
            }
            for label, value in BUTTONS[field]
        ]

    tops = [
        {
            "text": ("● " if int(settings.get("top", 10)) == n else "") + f"{n}위",
            "callback_data": f"s:top:{n}",
        }
        for n in (5, 10, 20)
    ]

    return {
        "inline_keyboard": [
            row("investor"),
            row("side") + row("metric"),
            row("market"),
            tops + [{"text": "🔄", "callback_data": "r"}],
        ]
    }
