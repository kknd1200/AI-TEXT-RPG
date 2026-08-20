#!/usr/bin/env python3
"""Recover the wire layout of every command straight from the binary.

For each ``Net_*REQUEST`` / ``Net_*RECEIVE`` function this walks the Thumb
code, tracks constants held in registers, and prints the sequence of
``EFC_fsRead*`` / ``EFC_fsWrite*`` calls -- which *is* the payload layout --
plus the command id handed to ``Net_SetPACKET1`` / ``Net_SetPACKET2``.

    python3 tools/extract_protocol.py libjccvt.so
    python3 tools/extract_protocol.py libjccvt.so --filter unknown

The output is what ``docs/protocol.md`` and ``server/ensserver/handlers.py``
were written from; re-run it after any change to check them.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from elfutil import Elf, load  # noqa: E402

try:
    from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
except ImportError:  # pragma: no cover
    print("this tool needs capstone:  pip install capstone", file=sys.stderr)
    raise SystemExit(2)

IO_PREFIXES = ("EFC_fsRead", "EFC_fsWrite", "EFC_fsSKIP")


def trace(elf: Elf, name: str) -> list[str]:
    """Return the ordered field list for one function."""
    sym = elf.func(name)
    body = elf.read(sym.addr, sym.size)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    regs: dict[str, int] = {}
    fields: list[str] = []

    for insn in md.disasm(body, sym.addr):
        op = insn.op_str
        if insn.mnemonic.startswith("ldr") and "[pc" in op:
            dst = re.match(r"(\w+),", op)
            imm = re.search(r"#(-?0x[0-9a-f]+|-?\d+)", op.split("[pc")[1])
            if dst and imm:
                lit = ((insn.address + 4) & ~3) + int(imm.group(1), 0)
                try:
                    regs[dst.group(1)] = elf.word(lit)
                except ValueError:
                    regs.pop(dst.group(1), None)
        elif insn.mnemonic == "movs" and ", #" in op:
            dst, val = op.split(", #")
            regs[dst] = int(val, 0)
        elif insn.mnemonic in ("mov", "adds") and op.count(",") == 1:
            dst, src = (p.strip() for p in op.split(","))
            if src in regs:
                regs[dst] = regs[src]
            else:
                regs.pop(dst, None)
        elif insn.mnemonic == "adds" and op.count(",") == 2:
            dst, a, b = (p.strip() for p in op.split(","))
            if b.startswith("#") and a in regs:
                regs[dst] = regs[a] + int(b[1:], 0)
            else:
                regs.pop(dst, None)
        elif insn.mnemonic == "lsls" and op.count(",") == 2:
            dst, a, b = (p.strip() for p in op.split(","))
            if b.startswith("#") and a in regs:
                regs[dst] = regs[a] << int(b[1:], 0)
            else:
                regs.pop(dst, None)
        elif insn.mnemonic == "bl":
            try:
                target = int(op.strip("#"), 0) & ~1
            except ValueError:
                continue
            callee = elf.name_by_addr.get(target, "")
            if callee.startswith(IO_PREFIXES):
                short = callee.replace("EFC_fs", "")
                if "Buff" in callee:
                    short += f"({regs.get('r2', '?')})"
                elif "SKIP" in callee:
                    short += f"({regs.get('r1', '?')})"
                fields.append(short)
            elif callee in ("Net_SetPACKET1", "Net_SetPACKET2"):
                cmd = regs.get("r0")
                fields.append(f"[SEND cmd={cmd:#x}]" if cmd is not None else "[SEND cmd=?]")
            elif callee == "MC_knlSprintk":
                fields.append("sprintf")
    return fields


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lib", type=Path)
    ap.add_argument("--filter", default="", help="only symbols containing this text")
    args = ap.parse_args()

    elf = load(str(args.lib))
    names = sorted(
        n for n in elf.func_by_name if n.startswith("Net_") and args.filter in n
    )
    for name in names:
        fields = trace(elf, name)
        if fields:
            print(f"{name:<28} {' '.join(fields)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
