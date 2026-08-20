"""Minimal ELF32 reader for libjccvt.so (ARM, little endian).

The shipped library still carries a full ``.symtab``, which is why the
protocol could be recovered at all -- every game function keeps its original
name (``Net_unknown_3REQUEST``, ``EFC_netSET``, ...).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class Section:
    name: str
    type: int
    addr: int
    off: int
    size: int
    link: int


@dataclass
class Symbol:
    name: str
    value: int
    size: int
    type: int

    @property
    def addr(self) -> int:
        """Thumb symbols carry the low bit set; strip it."""
        return self.value & ~1

    @property
    def is_func(self) -> bool:
        return self.type == 2


class Elf:
    def __init__(self, data: bytes):
        if data[:4] != b"\x7fELF":
            raise ValueError("not an ELF file")
        self.data = data
        shoff, = struct.unpack_from("<I", data, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x2E)
        raw = []
        for i in range(shnum):
            o = shoff + i * shentsize
            name, typ, _flags, addr, off, size, link = struct.unpack_from("<7I", data, o)
            raw.append((name, typ, addr, off, size, link))
        stroff = raw[shstrndx][3]
        self.sections = [
            Section(self._cstr(stroff + n), t, a, o, s, l) for n, t, a, o, s, l in raw
        ]
        self.by_name = {s.name: s for s in self.sections}
        self.symbols = self._read_symbols()
        self.func_by_name = {s.name: s for s in self.symbols if s.is_func and s.value}
        self.name_by_addr: dict[int, str] = {}
        for s in self.symbols:
            if s.value and not s.name.startswith("$"):
                self.name_by_addr.setdefault(s.addr, s.name)

    def _cstr(self, off: int) -> str:
        end = self.data.index(b"\0", off)
        return self.data[off:end].decode("utf-8", "replace")

    def _read_symbols(self) -> list[Symbol]:
        sym = self.by_name.get(".symtab")
        if sym is None:
            return []
        strtab = self.sections[sym.link]
        out = []
        for o in range(sym.off, sym.off + sym.size, 16):
            n, val, size, info, _other, _shndx = struct.unpack_from("<IIIBBH", self.data, o)
            out.append(Symbol(self._cstr(strtab.off + n), val, size, info & 0xF))
        return out

    # -- address helpers --------------------------------------------------
    def vaddr_to_off(self, vaddr: int) -> int | None:
        for s in self.sections:
            if s.type != 8 and s.addr and s.addr <= vaddr < s.addr + s.size:
                return s.off + vaddr - s.addr
        return None

    def read(self, vaddr: int, n: int) -> bytes:
        off = self.vaddr_to_off(vaddr)
        if off is None:
            raise ValueError("address 0x%x not mapped" % vaddr)
        return self.data[off : off + n]

    def word(self, vaddr: int) -> int:
        return struct.unpack("<I", self.read(vaddr, 4))[0]

    @property
    def got(self) -> int:
        """Base the PIC code adds to its GOT-relative literals."""
        return self.by_name[".got"].addr

    def func(self, name: str) -> Symbol:
        return self.func_by_name[name]

    def func_bytes(self, name: str) -> tuple[int, bytes]:
        s = self.func(name)
        return s.addr, self.read(s.addr, s.size)


def load(path: str) -> Elf:
    with open(path, "rb") as fh:
        return Elf(fh.read())
