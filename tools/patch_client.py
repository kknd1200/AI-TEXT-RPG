#!/usr/bin/env python3
"""Point the game client at your own server.

``EFC_netSET`` (0x1de80 in the shipped ``libjccvt.so``) hardcodes the
original server::

    r0 = &"218.50.3.88"
    r0 = MC_utilInetAddrInt(r0)     ; string -> u32
    NetData->addr = r0
    NetData->port = MC_utilHtons(0x139a)    ; 5018

Overwriting the string in place would only work for addresses of 11
characters or fewer -- the constant sits between two other strings, so there
is no room to grow.  Instead this script removes the string lookup
altogether:

    * ``adds r0, r4, r0`` (turn the GOT-relative literal into a pointer)
      becomes a NOP,
    * the ``bl MC_utilInetAddrInt`` becomes two NOPs,
    * the literal that used to hold the GOT offset now holds the address
      itself, in the exact byte order ``inet_addr`` would have returned.

``r0`` therefore flows straight into ``NetData->addr`` and any IPv4 address
works.  The port is a plain literal in the same pool, so it is just
rewritten.

Usage::

    python3 tools/patch_client.py game.apk 192.168.0.42 -o game-private.apk
    python3 tools/patch_client.py game.apk 10.0.0.5 --port 5018

The output APK is unsigned; sign it with ``apksigner`` (see docs/setup.md).
"""

from __future__ import annotations

import argparse
import ipaddress
import shutil
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from elfutil import Elf  # noqa: E402

ORIGINAL_HOST = b"218.50.3.88"
ORIGINAL_PORT = 0x139A
THUMB_NOP = 0x46C0  # mov r8, r8 -- safe on ARMv5 as well as ARMv7
ADDS_R0_R4_R0 = 0x1820  # adds r0, r4, r0

LIB_PATHS = ("lib/armeabi-v7a/libjccvt.so", "lib/armeabi/libjccvt.so")


class PatchError(Exception):
    pass


def _thumb_ldr_pc_target(addr: int, half: int) -> int | None:
    """Decode ``LDR Rt, [pc, #imm8*4]`` -> address of the literal."""
    if (half & 0xF800) != 0x4800:
        return None
    imm8 = half & 0xFF
    return ((addr + 4) & ~3) + imm8 * 4


def _thumb_bl_target(addr: int, hi: int, lo: int) -> int | None:
    if (hi & 0xF800) != 0xF000 or (lo & 0xF800) != 0xF800:
        return None
    imm = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
    if imm & 0x400000:
        imm -= 0x800000
    return addr + 4 + imm


def patch_library(data: bytes, ip: str, port: int) -> bytes:
    elf = Elf(data)
    try:
        fn = elf.func("EFC_netSET")
        inet = elf.func("MC_utilInetAddrInt")
    except KeyError as exc:  # pragma: no cover - depends on the input file
        raise PatchError(f"symbol not found: {exc}") from exc

    base = fn.addr
    body = elf.read(base, fn.size)
    off = elf.vaddr_to_off(base)
    if off is None:
        raise PatchError("EFC_netSET is not mapped")

    host_off = data.find(ORIGINAL_HOST + b"\x00")
    if host_off < 0:
        raise PatchError("original server string not found")
    want_gotoff = (host_off - elf.got) & 0xFFFFFFFF

    ip_literal = port_literal = None
    adds_at = bl_at = None

    for i in range(0, fn.size - 1, 2):
        half = struct.unpack_from("<H", body, i)[0]
        addr = base + i

        lit = _thumb_ldr_pc_target(addr, half)
        if lit is not None:
            try:
                value = elf.word(lit)
            except ValueError:
                continue
            if value == want_gotoff and ip_literal is None:
                ip_literal = lit
            elif value == ORIGINAL_PORT and port_literal is None:
                port_literal = lit
            continue

        if half == ADDS_R0_R4_R0 and adds_at is None:
            adds_at = addr
            continue

        if i + 3 < fn.size:
            lo = struct.unpack_from("<H", body, i + 2)[0]
            target = _thumb_bl_target(addr, half, lo)
            if target is not None and (target & ~1) == inet.addr and bl_at is None:
                bl_at = addr

    missing = [
        n
        for n, v in (
            ("address literal", ip_literal),
            ("port literal", port_literal),
            ("adds r0, r4, r0", adds_at),
            ("bl MC_utilInetAddrInt", bl_at),
        )
        if v is None
    ]
    if missing:
        raise PatchError("could not locate: " + ", ".join(missing))

    packed = ipaddress.IPv4Address(ip).packed  # network order, as inet_addr returns
    out = bytearray(data)
    struct.pack_into("<I", out, elf.vaddr_to_off(ip_literal), struct.unpack("<I", packed)[0])
    struct.pack_into("<I", out, elf.vaddr_to_off(port_literal), port)
    struct.pack_into("<H", out, elf.vaddr_to_off(adds_at), THUMB_NOP)
    struct.pack_into("<H", out, elf.vaddr_to_off(bl_at), THUMB_NOP)
    struct.pack_into("<H", out, elf.vaddr_to_off(bl_at) + 2, THUMB_NOP)
    return bytes(out)


def patch_apk(src: Path, dst: Path, ip: str, port: int, keep_signature: bool = False) -> None:
    patched_any = False
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(
        dst, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for info in zin.infolist():
            name = info.filename
            data = zin.read(name)
            if not keep_signature and name.startswith("META-INF/") and name.upper().endswith(
                (".RSA", ".DSA", ".EC", ".SF", "MANIFEST.MF")
            ):
                continue  # the old signature cannot survive the edit anyway
            if name in LIB_PATHS:
                data = patch_library(data, ip, port)
                patched_any = True
                print(f"  patched {name}")
            zout.writestr(info, data)
    if not patched_any:
        raise PatchError("no libjccvt.so found inside the APK")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("apk", type=Path, help="original APK (or a raw libjccvt.so)")
    ap.add_argument("ip", help="IPv4 address of your server")
    ap.add_argument("--port", type=int, default=ORIGINAL_PORT, help="default 5018")
    ap.add_argument("-o", "--output", type=Path, help="default: <input>-private.apk")
    args = ap.parse_args()

    ipaddress.IPv4Address(args.ip)  # fail early on hostnames: the client calls inet_addr

    out = args.output or args.apk.with_name(args.apk.stem + "-private" + args.apk.suffix)
    try:
        if args.apk.suffix == ".so":
            out.write_bytes(patch_library(args.apk.read_bytes(), args.ip, args.port))
        else:
            patch_apk(args.apk, out, args.ip, args.port)
    except PatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {out}  ->  {args.ip}:{args.port}")
    if out.suffix == ".apk":
        if shutil.which("apksigner"):
            print("sign it with:  apksigner sign --ks <keystore.jks> " + str(out))
        else:
            print("the APK is unsigned; see docs/setup.md for the signing step")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
