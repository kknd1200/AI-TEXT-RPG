#!/usr/bin/env python3
"""List the functions still named inside libjccvt.so.

    python3 tools/dump_symbols.py libjccvt.so            # everything
    python3 tools/dump_symbols.py libjccvt.so Net_ Online_Unknown
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from elfutil import load  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lib", type=Path)
    ap.add_argument("prefix", nargs="*", help="only symbols containing one of these")
    ap.add_argument("--objects", action="store_true", help="show data symbols too")
    args = ap.parse_args()

    elf = load(str(args.lib))
    for sym in sorted(elf.symbols, key=lambda s: s.addr):
        if not sym.value or sym.name.startswith("$"):
            continue
        if not sym.is_func and not (args.objects and sym.type == 1):
            continue
        if args.prefix and not any(p in sym.name for p in args.prefix):
            continue
        kind = "FUNC" if sym.is_func else "OBJ "
        print(f"{sym.addr:08x} {sym.size:6d} {kind} {sym.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
