"""헬스체크용 최소 HTTP 서버.

무료 PaaS(Koyeb·Render·Railway 등) 는 대부분 '포트를 열고 있는 웹 서비스' 만
받아준다. 텔레그램 봇은 롱폴링이라 포트를 열 이유가 없으므로, 배포 환경이
요구할 때만 200 을 돌려주는 서버를 곁들여 띄운다.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _Handler(BaseHTTPRequestHandler):
    server_version = "krflow-health"

    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 규약
        body = b"krflow bot ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def resolve_port(explicit: int | None = None) -> int | None:
    """명시 포트가 없으면 PaaS 가 주입하는 $PORT 를 쓴다."""
    if explicit:
        return explicit
    raw = os.environ.get("PORT", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def start_health_server(port: int, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
