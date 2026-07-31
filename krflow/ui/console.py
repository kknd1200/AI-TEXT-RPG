"""rich 기반 터미널 대시보드."""

from __future__ import annotations

import shutil
import time
from datetime import datetime

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .. import fmt
from ..market import phase_label
from ..models import MARKET_LABEL, Snapshot
from ..providers.base import Provider, ProviderError
from ..ranking import INVESTOR_LABEL, METRIC_LABEL, SIDE_LABEL, rank, totals

# 한국식 색상: 상승/순매수 = 빨강, 하락/순매도 = 파랑
UP = "bold red"
DOWN = "bold blue"
FLAT = "dim white"


def _colored(value: float | None, text: str) -> Text:
    if value is None or value == 0:
        return Text(text, style=FLAT)
    return Text(text, style=UP if value > 0 else DOWN)


def _terminal_width() -> int:
    return shutil.get_terminal_size(fallback=(100, 24)).columns


def build_table(
    snapshot: Snapshot,
    *,
    investor: str,
    metric: str,
    side: str,
    top: int,
    width: int | None = None,
) -> Table:
    rows = rank(
        snapshot.rows,
        investor=investor,
        metric=metric,
        side=side,
        top=top,
        market=snapshot.market,
    )

    # 시세를 제공하지 않는 소스(네이버 등)에서는 가격 열을 통째로 뺀다.
    # 터미널이 좁으면 종목명이 뭉개지지 않도록 부가 열부터 순서대로 버린다.
    available = (width or _terminal_width()) - 4  # 패널 테두리·여백
    has_price = any(row.price is not None for row in rows) and available >= 84
    has_code = available >= 62

    table = Table(
        expand=True,
        header_style="bold cyan",
        border_style="grey37",
        row_styles=["", "on grey11"],
        pad_edge=False,
        padding=(0, 1),
    )
    table.add_column("#", justify="right", width=3, style="dim")
    table.add_column("종목", justify="left", min_width=12, ratio=3, no_wrap=True, overflow="ellipsis")
    if has_code:
        table.add_column("코드", justify="left", width=6, style="dim")
    if has_price:
        table.add_column("현재가", justify="right", width=9)
        table.add_column("등락률", justify="right", width=7)
    # 단위는 헤더 줄에 한 번만 표시해 열 폭을 아낀다.
    table.add_column("외국인", justify="right", min_width=9)
    table.add_column("기관", justify="right", min_width=9)
    table.add_column("합계", justify="right", min_width=9)

    if not rows:
        table.add_row(*(["-", "조건에 맞는 종목이 없습니다"] + [""] * (len(table.columns) - 2)))
        return table

    for idx, row in enumerate(rows, start=1):
        f_val = row.metric("foreign", metric)
        i_val = row.metric("inst", metric)
        b_val = row.metric("both", metric)
        highlight = "bold" if idx <= 3 else ""

        cells = [str(idx), Text(row.name, style=highlight)]
        if has_code:
            cells.append(row.code)
        if has_price:
            cells += [fmt.price(row.price), _colored(row.change_pct, fmt.pct(row.change_pct))]
        cells += [
            _colored(f_val, fmt.metric_str(f_val, metric)),
            _colored(i_val, fmt.metric_str(i_val, metric)),
            _colored(b_val, fmt.metric_str(b_val, metric)),
        ]
        table.add_row(*cells)

    summary = totals(rows)
    unit_fn = fmt.eok if metric == "value" else fmt.qty
    table.add_section()
    footer = ["", Text("합계", style="bold")]
    if has_code:
        footer.append("")
    if has_price:
        footer += ["", ""]
    footer += [
        _colored(summary[f"foreign_{metric}"], unit_fn(summary[f"foreign_{metric}"])),
        _colored(summary[f"inst_{metric}"], unit_fn(summary[f"inst_{metric}"])),
        _colored(summary[f"both_{metric}"], unit_fn(summary[f"both_{metric}"])),
    ]
    table.add_row(*footer)
    return table


def build_header(
    snapshot: Snapshot,
    *,
    investor: str,
    metric: str,
    side: str,
    provider_label: str,
    error: str | None = None,
) -> Text:
    header = Text()
    header.append("실시간 수급 상위  ", style="bold white")
    header.append(f"{MARKET_LABEL.get(snapshot.market, snapshot.market)}", style="bold yellow")
    header.append(" · ")
    header.append(INVESTOR_LABEL[investor], style="bold yellow")
    header.append(" · ")
    header.append(SIDE_LABEL[side], style="bold yellow")
    header.append(f" · {METRIC_LABEL[metric]} 기준", style="dim")
    header.append(f" (단위: {fmt.metric_unit(metric)})\n", style="dim")

    header.append(f"소스: {provider_label}", style="cyan")
    header.append(f"  |  장 상태: {phase_label()}", style="cyan")
    header.append(f"  |  갱신: {snapshot.as_of.strftime('%Y-%m-%d %H:%M:%S')} KST", style="cyan")
    if snapshot.delayed:
        header.append("  |  [지연]", style="bold magenta")
    if snapshot.note:
        header.append(f"\n{snapshot.note}", style="dim italic")
    if error:
        header.append(f"\n갱신 실패(직전 데이터 표시 중): {error}", style="bold red")
    return header


def render(
    snapshot: Snapshot,
    *,
    investor: str,
    metric: str,
    side: str,
    top: int,
    provider_label: str,
    error: str | None = None,
) -> Panel:
    return Panel(
        Group(
            build_header(
                snapshot,
                investor=investor,
                metric=metric,
                side=side,
                provider_label=provider_label,
                error=error,
            ),
            build_table(snapshot, investor=investor, metric=metric, side=side, top=top),
        ),
        border_style="cyan",
        title="krflow",
        subtitle="Ctrl+C 로 종료",
    )


def print_once(
    snapshot: Snapshot,
    *,
    investor: str,
    metric: str,
    side: str,
    top: int,
    provider_label: str,
    console: Console | None = None,
) -> None:
    console = console or Console()
    console.print(
        render(
            snapshot,
            investor=investor,
            metric=metric,
            side=side,
            top=top,
            provider_label=provider_label,
        )
    )


def watch(
    provider: Provider,
    *,
    market: str,
    investor: str,
    metric: str,
    side: str,
    top: int,
    interval: float,
    console: Console | None = None,
    max_cycles: int | None = None,
    sleeper=time.sleep,
) -> int:
    """주기적으로 갱신하며 대시보드를 그린다. 반환값은 종료 코드."""
    console = console or Console()
    interval = max(interval, provider.min_interval)

    snapshot: Snapshot | None = None
    error: str | None = None
    cycles = 0

    with Live(console=console, screen=False, refresh_per_second=4, transient=False) as live:
        while True:
            started = datetime.now()
            try:
                snapshot = provider.fetch(market)
                error = None
            except ProviderError as exc:
                error = str(exc)
                if snapshot is None:
                    live.update(Panel(Text(f"데이터 조회 실패: {exc}", style="bold red")))
                    console.print()
                    return 1
            except Exception as exc:  # 네트워크 계층의 예기치 못한 예외도 루프를 죽이지 않는다
                error = f"{type(exc).__name__}: {exc}"
                if snapshot is None:
                    live.update(Panel(Text(f"데이터 조회 실패: {error}", style="bold red")))
                    return 1

            live.update(
                render(
                    snapshot,
                    investor=investor,
                    metric=metric,
                    side=side,
                    top=top,
                    provider_label=f"{provider.label} ({provider.name})",
                    error=error,
                )
            )

            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                return 0

            elapsed = (datetime.now() - started).total_seconds()
            try:
                sleeper(max(0.0, interval - elapsed))
            except KeyboardInterrupt:
                return 0
