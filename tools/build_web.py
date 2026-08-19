#!/usr/bin/env python3
"""웹판을 파일 하나로 묶는다.

data/ 의 JSON과 web/ 의 CSS·JS를 HTML 하나에 인라인해서 web/tamer.html 을 만든다.
결과물은 외부 요청이 필요 없으므로(글꼴만 있으면 더 예쁘게 나올 뿐) 휴대폰에
파일 하나만 옮겨 두면 오프라인에서도 돌아간다.

    python3 tools/build_web.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web"

TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#12100E">
<meta name="description" content="몬스터를 잡고 기르고 합치는 턴제 텍스트 RPG. 132종, 6속성.">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>엘리멘탈 테이머</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap">
<style>
__CSS__
</style>
</head>
<body>
<div id="app"></div>
<div id="toast" role="status" aria-live="polite"></div>
<script>
const D = __DATA__;
</script>
<script>
__GAME__
</script>
<script>
__UI__
</script>
</body>
</html>
"""


def load_data() -> dict:
    passives = json.loads((DATA / "passives.json").read_text(encoding="utf-8"))
    items = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
    return {
        "roster": json.loads((DATA / "roster.json").read_text(encoding="utf-8")),
        "passives": passives["passives"],
        "slots": passives["slots"],
        "items": items["items"],
        "drops": {k: v for k, v in items["drops"].items() if not k.startswith("_")},
        "world": json.loads((DATA / "world.json").read_text(encoding="utf-8")),
        "balance": json.loads((DATA / "rules" / "balance.json").read_text(encoding="utf-8")),
    }


def strip_comments(payload):
    """설명용 _comment 키는 실행에 쓰이지 않으니 결과물에서 뺀다."""
    if isinstance(payload, dict):
        return {k: strip_comments(v) for k, v in payload.items() if k != "_comment"}
    if isinstance(payload, list):
        return [strip_comments(v) for v in payload]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=WEB / "tamer.html")
    args = parser.parse_args()

    payload = json.dumps(strip_comments(load_data()), ensure_ascii=False, separators=(",", ":"))
    html = (
        TEMPLATE
        .replace("__CSS__", (WEB / "game.css").read_text(encoding="utf-8"))
        .replace("__DATA__", payload)
        .replace("__GAME__", (WEB / "game.js").read_text(encoding="utf-8"))
        .replace("__UI__", (WEB / "ui.js").read_text(encoding="utf-8"))
    )
    args.out.write_text(html, encoding="utf-8")
    print(f"{args.out}  {len(html.encode()) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
