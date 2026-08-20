#!/usr/bin/env python3
"""Annotated Thumb disassembler for libjccvt.so.

Resolves the two things that make the game's PIC code unreadable otherwise:
``ldr rX, [pc, #n]`` literals, and the GOT-relative offsets those literals
hold (``literal + .got`` is usually a string or a global).

    python3 tools/disasm.py libjccvt.so EFC_netSET Net_SetPACKET1

Requires ``capstone`` (``pip install capstone``).
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


def cstring(elf: Elf, vaddr: int, limit: int = 64) -> str | None:
    off = elf.vaddr_to_off(vaddr)
    if off is None:
        return None
    end = elf.data.find(b"\0", off)
    if end < 0 or end - off > limit or end == off:
        return None
    raw = elf.data[off:end]
    if not all(32 <= c < 127 for c in raw):
        return None
    return raw.decode("ascii")


def disassemble(elf: Elf, name: str) -> None:
    sym = elf.func(name)
    body = elf.read(sym.addr, sym.size)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    print(f"=== {name} @0x{sym.addr:x} ({sym.size} bytes)")
    for insn in md.disasm(body, sym.addr):
        line = f"  {insn.address:08x}  {insn.mnemonic:<8} {insn.op_str}"
        notes = []
        if insn.mnemonic.startswith("ldr") and "[pc" in insn.op_str:
            m = re.search(r"#(-?0x[0-9a-f]+|-?\d+)", insn.op_str.split("[pc")[1])
            if m:
                lit = ((insn.address + 4) & ~3) + int(m.group(1), 0)
                try:
                    value = elf.word(lit)
                except ValueError:
                    value = None
                if value is not None:
                    signed = value - (1 << 32) if value >= 1 << 31 else value
                    notes.append(f"={value:#x} ({signed})")
                    if (value & ~1) in elf.name_by_addr:
                        notes.append(elf.name_by_addr[value & ~1])
                    target = (elf.got + value) & 0xFFFFFFFF
                    text = cstring(elf, target)
                    if text is not None:
                        notes.append(f'GOT+ -> "{text}"')
                    elif target in elf.name_by_addr:
                        notes.append(f"GOT+ -> {elf.name_by_addr[target]}")
        elif insn.mnemonic in ("bl", "blx", "b"):
            try:
                target = int(insn.op_str.strip("#"), 0) & ~1
            except ValueError:
                target = None
            if target is not None and target in elf.name_by_addr:
                notes.append(elf.name_by_addr[target])
        if notes:
            line += "   ; " + "  ".join(notes)
        print(line)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lib", type=Path)
    ap.add_argument("symbols", nargs="+")
    args = ap.parse_args()
    elf = load(str(args.lib))
    for name in args.symbols:
        if name not in elf.func_by_name:
            print(f"!! no such function: {name}", file=sys.stderr)
            continue
        disassemble(elf, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
