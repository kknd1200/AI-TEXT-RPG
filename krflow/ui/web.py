"""브라우저용 대시보드 (표준 라이브러리 http.server 기반).

  krflow serve --provider kis --port 8765

/            대시보드 HTML (외부 의존성 없음)
/api/snapshot?market=&investor=&metric=&side=&top=   랭킹 JSON
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import fmt
from ..market import phase_label
from ..models import MARKET_LABEL, Snapshot
from ..providers.base import Provider, ProviderError
from ..ranking import INVESTOR_LABEL, METRIC_LABEL, SIDE_LABEL, rank, totals


class SnapshotCache:
    """여러 브라우저 탭이 붙어도 소스는 주기당 한 번만 호출한다."""

    def __init__(self, provider: Provider, market: str, ttl: float) -> None:
        self.provider = provider
        self.market = market
        self.ttl = max(ttl, provider.min_interval)
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._fetched_at = 0.0
        self._error: str | None = None

    def get(self) -> tuple[Snapshot | None, str | None]:
        with self._lock:
            fresh = self._snapshot is not None and (time.monotonic() - self._fetched_at) < self.ttl
            if fresh:
                return self._snapshot, self._error
            try:
                self._snapshot = self.provider.fetch(self.market)
                self._error = None
            except Exception as exc:
                # 소스가 죽어도 서버는 살아 있어야 하므로 직전 스냅샷을 유지한다.
                self._error = (
                    str(exc) if isinstance(exc, ProviderError) else f"{type(exc).__name__}: {exc}"
                )
            self._fetched_at = time.monotonic()
            return self._snapshot, self._error


def build_payload(
    snapshot: Snapshot | None,
    error: str | None,
    *,
    investor: str,
    metric: str,
    side: str,
    top: int,
) -> dict:
    if snapshot is None:
        return {"ok": False, "error": error or "데이터 없음", "rows": []}

    ranked = rank(
        snapshot.rows,
        investor=investor,
        metric=metric,
        side=side,
        top=top,
        market=snapshot.market,
    )
    summary = totals(ranked)
    unit = fmt.metric_unit(metric)

    return {
        "ok": True,
        "error": error,
        "source": snapshot.source,
        "asOf": snapshot.as_of.strftime("%Y-%m-%d %H:%M:%S"),
        "phase": phase_label(),
        "delayed": snapshot.delayed,
        "note": snapshot.note,
        "unit": unit,
        "title": (
            f"{MARKET_LABEL.get(snapshot.market, snapshot.market)} · "
            f"{INVESTOR_LABEL[investor]} {SIDE_LABEL[side]} · {METRIC_LABEL[metric]} 기준"
        ),
        "totals": {
            "foreign": fmt.metric_str(summary[f"foreign_{metric}"], metric),
            "inst": fmt.metric_str(summary[f"inst_{metric}"], metric),
            "both": fmt.metric_str(summary[f"both_{metric}"], metric),
        },
        "rows": [
            {
                "rank": idx,
                "code": row.code,
                "name": row.name,
                "market": MARKET_LABEL.get(row.market, row.market),
                "price": fmt.price(row.price),
                "changePct": fmt.pct(row.change_pct),
                "changeDir": fmt.sign_class(row.change_pct),
                "foreign": fmt.metric_str(row.metric("foreign", metric), metric),
                "foreignDir": fmt.sign_class(row.metric("foreign", metric)),
                "inst": fmt.metric_str(row.metric("inst", metric), metric),
                "instDir": fmt.sign_class(row.metric("inst", metric)),
                "both": fmt.metric_str(row.metric("both", metric), metric),
                "bothDir": fmt.sign_class(row.metric("both", metric)),
            }
            for idx, row in enumerate(ranked, start=1)
        ],
    }


def make_handler(cache: SnapshotCache, defaults: dict, refresh: float):
    class Handler(BaseHTTPRequestHandler):
        server_version = "krflow"

        def log_message(self, *args) -> None:  # 요청 로그 억제
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 규약
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                html = PAGE.replace("__REFRESH_MS__", str(int(refresh * 1000)))
                html = html.replace("__DEFAULTS__", json.dumps(defaults, ensure_ascii=False))
                self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
                return

            if parsed.path == "/api/snapshot":
                query = parse_qs(parsed.query)

                def one(key: str, fallback: str) -> str:
                    return (query.get(key) or [fallback])[0]

                try:
                    top = int(one("top", str(defaults["top"])))
                except ValueError:
                    top = defaults["top"]

                snapshot, error = cache.get()
                try:
                    payload = build_payload(
                        snapshot,
                        error,
                        investor=one("investor", defaults["investor"]),
                        metric=one("metric", defaults["metric"]),
                        side=one("side", defaults["side"]),
                        top=max(1, min(top, 100)),
                    )
                except ValueError as exc:
                    payload = {"ok": False, "error": str(exc), "rows": []}

                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return

            self._send(404, b"not found", "text/plain; charset=utf-8")

    return Handler


def serve(
    provider: Provider,
    *,
    market: str,
    investor: str,
    metric: str,
    side: str,
    top: int,
    interval: float,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> int:
    cache = SnapshotCache(provider, market, interval)
    defaults = {
        "investor": investor,
        "metric": metric,
        "side": side,
        "top": top,
        "market": market,
    }
    handler = make_handler(cache, defaults, refresh=max(interval, provider.min_interval))
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"krflow 대시보드: http://{host}:{port}  (소스: {provider.label}, Ctrl+C 종료)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        httpd.server_close()
        provider.close()
    return 0


PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>krflow · 실시간 수급 상위</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #0f1116; --panel: #171a21; --line: #262b36;
    --text: #e6e8ee; --muted: #8b93a7;
    --up: #ff5252; --down: #4d8bff; --flat: #8b93a7;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg:#f6f7f9; --panel:#fff; --line:#e3e6ec; --text:#171a21; --muted:#6b7280; }
  }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px; background:var(--bg); color:var(--text);
         font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", sans-serif; }
  .wrap { max-width: 1100px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
  .controls { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
  select, input { background:var(--panel); color:var(--text); border:1px solid var(--line);
                  border-radius:8px; padding:7px 10px; font-size:13px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden; }
  .scroll { overflow-x:auto; }
  table { border-collapse: collapse; width:100%; font-size:13px; min-width:720px; }
  th, td { padding:9px 12px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }
  th { background:transparent; color:var(--muted); font-weight:600; font-size:12px; text-align:right; }
  th:nth-child(1), td:nth-child(1) { text-align:right; width:44px; color:var(--muted); }
  th:nth-child(2), td:nth-child(2) { text-align:left; }
  th:nth-child(3), td:nth-child(3) { text-align:left; color:var(--muted); }
  tbody tr:hover { background: rgba(127,127,127,.08); }
  tfoot td { font-weight:700; border-top:2px solid var(--line); border-bottom:none; }
  .up { color: var(--up); } .down { color: var(--down); } .flat { color: var(--flat); }
  .status { display:flex; flex-wrap:wrap; gap:12px; align-items:center;
            font-size:12px; color:var(--muted); margin-top:12px; }
  .dot { width:8px; height:8px; border-radius:50%; background:#3ddc84; display:inline-block; margin-right:6px; }
  .err { color:var(--up); }
  .badge { border:1px solid var(--line); border-radius:999px; padding:2px 8px; }
</style>
</head>
<body>
<div class="wrap">
  <h1 id="title">실시간 수급 상위</h1>
  <div class="sub" id="note"></div>

  <div class="controls">
    <select id="investor">
      <option value="both">외국인+기관</option>
      <option value="foreign">외국인</option>
      <option value="inst">기관</option>
    </select>
    <select id="side">
      <option value="buy">순매수 상위</option>
      <option value="sell">순매도 상위</option>
    </select>
    <select id="metric">
      <option value="value">금액 기준</option>
      <option value="qty">수량 기준</option>
    </select>
    <select id="top">
      <option value="10">10위</option>
      <option value="20">20위</option>
      <option value="30">30위</option>
      <option value="50">50위</option>
    </select>
  </div>

  <div class="panel scroll">
    <table>
      <thead>
        <tr>
          <th>#</th><th>종목</th><th>코드</th><th>현재가</th><th>등락률</th>
          <th id="h-foreign">외국인</th><th id="h-inst">기관</th><th id="h-both">합계</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
      <tfoot id="foot"></tfoot>
    </table>
  </div>

  <div class="status">
    <span><span class="dot"></span><span id="asof">불러오는 중…</span></span>
    <span class="badge" id="phase"></span>
    <span class="badge" id="source"></span>
    <span class="err" id="error"></span>
  </div>
</div>

<script>
const DEFAULTS = __DEFAULTS__;
const REFRESH_MS = __REFRESH_MS__;

function selectValue(el, value) {
  // CLI 로 준 값(예: --top 5)이 목록에 없으면 항목을 추가해 준다.
  if (![...el.options].some(o => o.value === value)) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = el.id === "top" ? value + "위" : value;
    el.insertBefore(opt, el.firstChild);
  }
  el.value = value;
}

for (const key of ["investor", "side", "metric", "top"]) {
  const el = document.getElementById(key);
  const saved = localStorage.getItem("krflow." + key);
  selectValue(el, saved !== null ? saved : String(DEFAULTS[key]));
  el.addEventListener("change", () => {
    localStorage.setItem("krflow." + key, el.value);
    load();
  });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function query() {
  const p = new URLSearchParams();
  for (const key of ["investor", "side", "metric", "top"]) {
    p.set(key, document.getElementById(key).value);
  }
  return p.toString();
}

async function load() {
  let data;
  try {
    const res = await fetch("/api/snapshot?" + query(), { cache: "no-store" });
    data = await res.json();
  } catch (e) {
    document.getElementById("error").textContent = "서버 연결 실패: " + e;
    return;
  }

  document.getElementById("error").textContent = data.error || "";
  if (!data.ok) {
    document.getElementById("rows").innerHTML =
      '<tr><td colspan="8" style="text-align:center;padding:24px">' + esc(data.error || "데이터 없음") + "</td></tr>";
    return;
  }

  document.getElementById("title").textContent = data.title;
  document.getElementById("note").textContent = data.note || "";
  document.getElementById("asof").textContent = "갱신 " + data.asOf + " KST";
  document.getElementById("phase").textContent = data.phase + (data.delayed ? " · 지연" : " · 실시간");
  document.getElementById("source").textContent = "소스: " + data.source;

  document.getElementById("h-foreign").textContent = "외국인(" + data.unit + ")";
  document.getElementById("h-inst").textContent = "기관(" + data.unit + ")";
  document.getElementById("h-both").textContent = "합계(" + data.unit + ")";

  document.getElementById("rows").innerHTML = data.rows.map(r => `
    <tr>
      <td>${r.rank}</td>
      <td>${esc(r.name)}</td>
      <td>${esc(r.code)}</td>
      <td>${esc(r.price)}</td>
      <td class="${r.changeDir}">${esc(r.changePct)}</td>
      <td class="${r.foreignDir}">${esc(r.foreign)}</td>
      <td class="${r.instDir}">${esc(r.inst)}</td>
      <td class="${r.bothDir}">${esc(r.both)}</td>
    </tr>`).join("");

  document.getElementById("foot").innerHTML = `
    <tr>
      <td></td><td style="text-align:left">표시 종목 합계</td><td></td><td></td><td></td>
      <td>${esc(data.totals.foreign)}</td>
      <td>${esc(data.totals.inst)}</td>
      <td>${esc(data.totals.both)}</td>
    </tr>`;
}

load();
setInterval(load, REFRESH_MS);
</script>
</body>
</html>
"""
