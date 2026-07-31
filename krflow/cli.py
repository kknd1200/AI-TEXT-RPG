"""krflow CLI — 국내장 외국인/기관 수급 상위 종목."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import __version__
from .config import load_config, parse_chat_ids
from .models import MARKETS
from .providers import DESCRIPTIONS, PROVIDER_NAMES, ProviderError, create, create_auto
from .ranking import INVESTORS, METRICS, SIDES, rank


def _common_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--market", choices=MARKETS, default="all", help="시장 구분 (기본: all)")
    parser.add_argument(
        "--investor", choices=INVESTORS, default="both", help="투자자 구분 (기본: both)"
    )
    parser.add_argument("--metric", choices=METRICS, default="value", help="정렬 기준 (기본: value)")
    parser.add_argument("--side", choices=SIDES, default="buy", help="순매수/순매도 (기본: buy)")
    parser.add_argument("--top", type=int, default=20, help="표시 종목 수 (기본: 20)")
    parser.add_argument(
        "--min-abs",
        type=float,
        default=0.0,
        help="최소 |순매수| 값(금액=백만원, 수량=주). 잡음 종목 제거용",
    )


def _provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=("auto",) + PROVIDER_NAMES,
        default="auto",
        help="데이터 소스 (기본: auto = 키움 → KIS → 네이버 순으로 자동 선택)",
    )
    parser.add_argument("--env-file", default=".env", help="설정 파일 경로 (기본: .env)")
    parser.add_argument("--date", help="krx provider 전용: 조회일 YYYYMMDD")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="krflow",
        description="국내 증시 외국인·기관 실시간 수급 상위 종목 모니터",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시:\n"
            "  krflow watch --provider kiwoom --investor both --top 20 --interval 10\n"
            "  krflow once --provider naver --market kosdaq --side sell\n"
            "  krflow serve --port 8765\n"
            "  krflow bot --provider kiwoom            # 텔레그램 봇\n"
            "  krflow watch --provider mock            # 키/네트워크 없이 데모\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"krflow {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    watch = sub.add_parser("watch", help="터미널에서 주기적으로 갱신하며 보기")
    _provider_args(watch)
    _common_query_args(watch)
    watch.add_argument("--interval", type=float, default=10.0, help="갱신 주기(초, 기본: 10)")
    watch.add_argument("--cycles", type=int, help="N회 갱신 후 종료 (테스트용)")

    once = sub.add_parser("once", help="한 번만 조회 (출력/저장)")
    _provider_args(once)
    _common_query_args(once)
    once.add_argument("--json", dest="json_path", help="결과를 JSON 파일로 저장 ('-' 는 표준출력)")
    once.add_argument("--csv", dest="csv_path", help="결과를 CSV 파일로 저장 ('-' 는 표준출력)")
    once.add_argument(
        "--diagnose",
        action="store_true",
        help="응답 필드가 파서와 맞는지 점검 (값이 0으로만 나올 때 사용)",
    )
    once.add_argument(
        "--dump-raw",
        help="소스 응답 원본을 JSON 파일로 저장 (앱키·토큰은 포함되지 않음)",
    )

    serve = sub.add_parser("serve", help="브라우저 대시보드 실행")
    _provider_args(serve)
    _common_query_args(serve)
    serve.add_argument("--interval", type=float, default=10.0, help="소스 갱신 주기(초, 기본: 10)")
    serve.add_argument("--host", default="127.0.0.1", help="바인드 주소 (기본: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8765, help="포트 (기본: 8765)")

    bot = sub.add_parser("bot", help="텔레그램 봇 실행 (대화형, 계속 켜둬야 함)")
    _provider_args(bot)
    bot.add_argument("--market", choices=MARKETS, default="all", help="시장 구분 (기본: all)")
    bot.add_argument("--interval", type=float, default=30.0, help="소스 갱신 주기(초, 기본: 30)")
    bot.add_argument("--state", help="구독 상태 저장 경로 (기본: ~/.krflow/telegram_state.json)")
    bot.add_argument("--polls", type=int, help="N회 폴링 후 종료 (테스트용)")
    bot.add_argument(
        "--port",
        type=int,
        help="헬스체크 HTTP 포트. 생략하면 환경변수 $PORT 를 쓴다 (PaaS 배포용)",
    )
    bot.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="수신한 메시지·버튼을 화면에 출력 (버튼이 안 먹을 때 원인 확인용)",
    )

    push = sub.add_parser("push", help="텔레그램으로 1회 전송 후 종료 (cron/GitHub Actions용)")
    _provider_args(push)
    _common_query_args(push)
    push.add_argument("--chat-id", help="받을 chat_id (쉼표 구분). 생략 시 허용 목록 전체")
    push.add_argument("--title", default="", help="제목 앞에 붙일 문구 (예: '장 마감 · ')")

    sub.add_parser("providers", help="사용 가능한 데이터 소스 목록")

    return parser


def _make_provider(args, config):
    if args.provider == "auto":
        return create_auto(config=config, date=getattr(args, "date", None))
    return create(args.provider, config=config, date=getattr(args, "date", None))


def _cmd_providers(config) -> int:
    print("사용 가능한 데이터 소스:\n")
    for name in PROVIDER_NAMES:
        mark = ""
        if name == "kiwoom":
            mark = "  [키 설정됨]" if config.has_kiwoom else "  [KIWOOM_APP_KEY 미설정]"
        if name == "kis":
            mark = "  [키 설정됨]" if config.has_kis else "  [KIS_APP_KEY 미설정]"
        if name == "krx":
            from .providers.krx import pykrx_installed

            mark = "  [설치됨]" if pykrx_installed() else "  [pykrx 미설치]"
        print(f"  {name:<7} {DESCRIPTIONS[name]}{mark}")
    print("\nauto    : 키움 → KIS → 네이버 순으로 자동 선택")
    print(
        "텔레그램  : "
        + ("봇 토큰 설정됨" if config.has_telegram else "TELEGRAM_BOT_TOKEN 미설정")
        + f" · 허용 chat_id {len(config.telegram_allowed_chat_ids)}개"
    )
    return 0


def _write_json(path: str, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path == "-":
        print(text)
    else:
        Path(path).write_text(text, encoding="utf-8")
        print(f"JSON 저장: {path}", file=sys.stderr)


FIELDS = [
    "rank",
    "code",
    "name",
    "market",
    "price",
    "change_pct",
    "foreign_qty",
    "foreign_value",
    "inst_qty",
    "inst_value",
    "both_qty",
    "both_value",
]


def _write_csv(path: str, rows) -> None:
    handle = sys.stdout if path == "-" else open(path, "w", encoding="utf-8-sig", newline="")
    try:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            record = row.to_dict()
            record["rank"] = idx
            writer.writerow({key: record.get(key) for key in FIELDS})
    finally:
        if handle is not sys.stdout:
            handle.close()
            print(f"CSV 저장: {path}", file=sys.stderr)


def _report_raw(provider, args) -> None:
    """--diagnose / --dump-raw 처리. 응답 본문만 다루므로 앱키는 새지 않는다."""
    raw = getattr(provider, "last_raw", None)
    if not raw:
        print(
            f"'{provider.name}' 는 원본 응답 저장을 지원하지 않습니다 "
            "(kiwoom / kis 에서 사용하세요).",
            file=sys.stderr,
        )
        return

    if args.dump_raw:
        Path(args.dump_raw).write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"원본 응답 저장: {args.dump_raw}", file=sys.stderr)

    if args.diagnose:
        try:
            from .providers.kiwoom import diagnose
        except ImportError:  # pragma: no cover
            return
        for label, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            print(f"\n===== 진단: {label} 응답 =====")
            print(diagnose(payload))


def _cmd_once(args, config) -> int:
    from rich.console import Console

    from .ui import console as ui_console

    provider = _make_provider(args, config)
    try:
        snapshot = provider.fetch(args.market)
    finally:
        provider.close()

    if args.dump_raw or args.diagnose:
        _report_raw(provider, args)

    ranked = rank(
        snapshot.rows,
        investor=args.investor,
        metric=args.metric,
        side=args.side,
        top=args.top,
        market=args.market,
        min_abs=args.min_abs,
    )

    if args.json_path:
        _write_json(
            args.json_path,
            {
                **{k: v for k, v in snapshot.to_dict().items() if k != "rows"},
                "query": {
                    "investor": args.investor,
                    "metric": args.metric,
                    "side": args.side,
                    "top": args.top,
                },
                "rows": [r.to_dict() for r in ranked],
            },
        )
    if args.csv_path:
        _write_csv(args.csv_path, ranked)

    if not args.json_path and not args.csv_path:
        ui_console.print_once(
            snapshot,
            investor=args.investor,
            metric=args.metric,
            side=args.side,
            top=args.top,
            provider_label=f"{provider.label} ({provider.name})",
            console=Console(),
        )
    return 0


def _cmd_watch(args, config) -> int:
    from .ui import console as ui_console

    provider = _make_provider(args, config)
    try:
        return ui_console.watch(
            provider,
            market=args.market,
            investor=args.investor,
            metric=args.metric,
            side=args.side,
            top=args.top,
            interval=args.interval,
            max_cycles=args.cycles,
        )
    except KeyboardInterrupt:
        return 0
    finally:
        provider.close()


def _cmd_serve(args, config) -> int:
    from .ui import web

    provider = _make_provider(args, config)
    return web.serve(
        provider,
        market=args.market,
        investor=args.investor,
        metric=args.metric,
        side=args.side,
        top=args.top,
        interval=args.interval,
        host=args.host,
        port=args.port,
    )


TELEGRAM_SETUP_HINT = (
    "오류: TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다.\n"
    "  1) 텔레그램에서 @BotFather 에게 /newbot 을 보내 토큰을 받으세요.\n"
    "  2) .env 또는 환경변수에 TELEGRAM_BOT_TOKEN=... 을 넣고 다시 실행하세요."
)


def _cmd_push(args, config) -> int:
    from .bot import render
    from .bot.telegram import TelegramClient, TelegramError

    if not config.has_telegram:
        print(TELEGRAM_SETUP_HINT, file=sys.stderr)
        return 1

    chats = (
        parse_chat_ids(args.chat_id) if args.chat_id else set(config.telegram_allowed_chat_ids)
    )
    if not chats:
        print(
            "오류: 받을 chat_id 가 없습니다. --chat-id 로 주거나 "
            "TELEGRAM_ALLOWED_CHAT_IDS 를 설정하세요.",
            file=sys.stderr,
        )
        return 1

    provider = _make_provider(args, config)
    try:
        snapshot = provider.fetch(args.market)
    finally:
        provider.close()

    settings = {
        "investor": args.investor,
        "side": args.side,
        "metric": args.metric,
        "market": args.market,
        "top": args.top,
    }
    # 1회 전송이라 버튼을 눌러도 받아줄 프로세스가 없다 — 키보드는 붙이지 않는다.
    text = render.render_snapshot(snapshot, settings, title_prefix=args.title)

    client = TelegramClient(config.telegram_token, timeout=config.request_timeout)
    failures = 0
    for chat_id in sorted(chats):
        try:
            client.send_message(chat_id, text)
            print(f"전송 완료: chat_id={chat_id}")
        except TelegramError as exc:
            print(f"전송 실패 (chat_id={chat_id}): {exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def _cmd_bot(args, config) -> int:
    from .bot.health import resolve_port, start_health_server
    from .bot.telegram import run_bot

    if not config.has_telegram:
        print(TELEGRAM_SETUP_HINT, file=sys.stderr)
        return 1

    port = resolve_port(args.port)
    if port:
        start_health_server(port)
        print(f"헬스체크 포트 {port} 열림")

    provider = _make_provider(args, config)
    return run_bot(
        provider,
        config,
        market=args.market,
        interval=args.interval,
        state_path=args.state,
        max_polls=args.polls,
        verbose=args.verbose,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(getattr(args, "env_file", ".env"))

    try:
        if args.command == "providers":
            return _cmd_providers(config)
        if args.command == "once":
            return _cmd_once(args, config)
        if args.command == "watch":
            return _cmd_watch(args, config)
        if args.command == "serve":
            return _cmd_serve(args, config)
        if args.command == "bot":
            return _cmd_bot(args, config)
        if args.command == "push":
            return _cmd_push(args, config)
    except ProviderError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0

    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
