#!/usr/bin/env python3
"""Talk to the private server the way the game does.

Lets you exercise the server without a phone: it builds requests with
``Net_SetPACKET1``'s exact header and prints the decoded replies.

    python3 tools/fake_client.py --host 127.0.0.1 --phone 01011112222 walkthrough
    python3 tools/fake_client.py --phone 01011112222 send 0x122
"""

from __future__ import annotations

import argparse
import socket
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from ensserver import commands as C  # noqa: E402
from ensserver.codec import (  # noqa: E402
    PHONE_LEN,
    TruncatedPacket,
    decode_response,
    encode_request,
    fixed,
)


class FakeClient:
    def __init__(self, host: str, port: int, phone: str, model: str = "Emulator"):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.phone = phone
        self.model = model
        self.buf = b""

    def send(self, cmd: int, payload: bytes = b"") -> list[tuple[int, int, bytes]]:
        self.sock.sendall(encode_request(cmd, self.phone, self.model, payload))
        out = []
        self.sock.settimeout(0.7)
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                self.buf += chunk
                while True:
                    try:
                        cmd_r, result, payload_r, used = decode_response(self.buf)
                    except TruncatedPacket:
                        break
                    self.buf = self.buf[used:]
                    out.append((cmd_r, result, payload_r))
        except socket.timeout:
            pass
        return out

    def close(self) -> None:
        self.sock.close()


def show(label: str, replies) -> None:
    if not replies:
        print(f"  {label}: (no reply)")
        return
    for cmd, result, payload in replies:
        state = "OK" if result in (0x0000, 0x8601) else f"result=0x{result:04x}"
        print(f"  {label}: {C.name(cmd)} {state} payload={payload.hex() or '-'}")


def walkthrough(cli: FakeClient) -> None:
    """The sequence a real client runs when entering 미지의 섬."""
    ident = fixed(cli.phone, PHONE_LEN)
    show("user", cli.send(C.CMD_USER))
    show("time", cli.send(C.CMD_TIME))
    show("island_update", cli.send(C.CMD_ISLAND_UPDATE, ident + b"ISLAND01" + b"A" * 10 + b"B" * 10))
    show("island_enter", cli.send(C.CMD_ISLAND_ENTER, ident + struct.pack("<I", 7)))
    show("island_count", cli.send(C.CMD_ISLAND_COUNT, ident))
    show("island_target", cli.send(C.CMD_ISLAND_TARGET, ident + struct.pack("<II", 0, 0)))
    show("log_write", cli.send(C.CMD_ISLAND_LOG_WRITE, ident + struct.pack("<I", 3)))
    show("log_list", cli.send(C.CMD_ISLAND_LOG_LIST, ident))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5018)
    ap.add_argument("--phone", default="01011112222")
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("walkthrough")
    p_send = sub.add_parser("send")
    p_send.add_argument("cmd", help="command id, e.g. 0x122")
    p_send.add_argument("payload", nargs="?", default="", help="hex payload")
    args = ap.parse_args()

    cli = FakeClient(args.host, args.port, args.phone)
    try:
        if args.action == "walkthrough":
            walkthrough(cli)
        else:
            show("reply", cli.send(int(args.cmd, 0), bytes.fromhex(args.payload)))
    finally:
        cli.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
