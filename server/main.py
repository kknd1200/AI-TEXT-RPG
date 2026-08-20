#!/usr/bin/env python3
"""Entry point: python3 server/main.py [--port 5018] [--db ens.db]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ensserver.server import DEFAULT_PORT, EnsServer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="배틀몬스터3 / 미지의 섬 private server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help="default 5018, the port compiled into the client")
    ap.add_argument("--db", default="ens.db")
    ap.add_argument("--record", metavar="FILE",
                    help="append every packet to FILE as JSONL for analysis")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    srv = EnsServer(args.db, args.record)
    try:
        asyncio.run(srv.serve(args.host, args.port))
    except KeyboardInterrupt:
        print()
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
