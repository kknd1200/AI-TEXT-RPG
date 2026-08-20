"""ENS packet codec.

Wire format reverse-engineered from ``lib/*/libjccvt.so`` in the
``com.ensony.battlemonster3`` APK (see ``docs/protocol.md``).

Request  (client -> server), built by ``Net_SetPACKET1`` at 0x34370:

    off  0  char[3]  "ENS"
    off  3  char[3]  carrier tag, "SKT" for cmd 0x13/0x39/0x3a else "KTF"
    off  6  u8       0x11
    off  7  u16      0x0087
    off  9  u16      command id
    off 11  u16      body length == 34 + len(payload)
    off 13  char[21] phone number (identity), NUL padded
    off 34  char[10] phone model, NUL padded
    off 44  char[3]  "100" (client version)
    off 47  payload

Response (server -> client), parsed by ``Net_dataRECEIVE`` at 0x33f80:

    off  0  char[3]  "ENS"
    off  3  u16      command id (echoed)
    off  5  u16      body length == 2 + len(payload)
    off  7  u16      result code (0x0000 or 0x8601 == OK, else error)
    off  9  payload

Every integer on the wire is little endian; ``EFC_fsWriteUint16`` at
0x1c9a4 stores the low byte first.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = b"ENS"

# Request header
REQ_HEADER_LEN = 47
REQ_BODY_OVERHEAD = 34  # bytes counted by the length field before the payload
REQ_PREFIX_LEN = 13  # bytes before the body the length field counts
REQ_MARKER = 0x11
REQ_TYPE = 0x0087
CLIENT_VERSION = b"100"

CARRIER_SKT = b"SKT"
CARRIER_KTF = b"KTF"
# Net_SetPACKET1 picks "SKT" for exactly these command ids.
SKT_COMMANDS = frozenset({0x13, 0x39, 0x3A})

# Response header
RES_HEADER_LEN = 9
RES_BODY_OVERHEAD = 2  # the result field is counted by the length field

# Result codes understood by Net_SetRECEIVE at 0x33588.
RESULT_OK = 0x0000
RESULT_OK_ALT = 0x8601
#: Any other value makes the client skip the payload entirely.  The server
#: uses this to answer "there is nothing to send" for list commands.
RESULT_NO_DATA = 0x0001

PHONE_LEN = 21
MODEL_LEN = 10


class TruncatedPacket(Exception):
    """Raised when a buffer does not hold a whole packet yet."""


def fixed(value, size: int) -> bytes:
    """NUL-pad/truncate ``value`` to exactly ``size`` bytes."""
    if isinstance(value, str):
        value = value.encode("cp949", "replace")
    return value[:size].ljust(size, b"\x00")


def unfixed(raw: bytes) -> str:
    """Decode a NUL-padded fixed field back to text."""
    return raw.split(b"\x00", 1)[0].decode("cp949", "replace")


class Reader:
    """Mirrors the ``EFC_fsRead*`` helpers (little endian, cursor based)."""

    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos

    def _take(self, n: int) -> bytes:
        if self.remaining < n:
            raise TruncatedPacket(f"want {n} bytes, have {self.remaining}")
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def u8(self) -> int:
        return self._take(1)[0]

    def s8(self) -> int:
        return struct.unpack("<b", self._take(1))[0]

    def u16(self) -> int:
        return struct.unpack("<H", self._take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def s32(self) -> int:
        return struct.unpack("<i", self._take(4))[0]

    def buff(self, n: int) -> bytes:
        return self._take(n)

    def text(self, n: int) -> str:
        return unfixed(self._take(n))

    def skip(self, n: int) -> None:
        self._take(n)


class Writer:
    """Mirrors the ``EFC_fsWrite*`` helpers."""

    def __init__(self):
        self.buf = bytearray()

    def u8(self, v: int) -> "Writer":
        self.buf += struct.pack("<B", v & 0xFF)
        return self

    def u16(self, v: int) -> "Writer":
        self.buf += struct.pack("<H", v & 0xFFFF)
        return self

    def u32(self, v: int) -> "Writer":
        self.buf += struct.pack("<I", v & 0xFFFFFFFF)
        return self

    def s32(self, v: int) -> "Writer":
        self.buf += struct.pack("<i", max(-2147483648, min(2147483647, int(v))))
        return self

    def buff(self, data: bytes) -> "Writer":
        self.buf += data
        return self

    def text(self, value, size: int) -> "Writer":
        self.buf += fixed(value, size)
        return self

    def bytes(self) -> bytes:
        return bytes(self.buf)


@dataclass
class Request:
    cmd: int
    phone: str
    model: str
    payload: bytes
    carrier: bytes = CARRIER_KTF
    version: bytes = CLIENT_VERSION
    raw: bytes = field(default=b"", repr=False)

    def reader(self) -> Reader:
        return Reader(self.payload)


def encode_request(
    cmd: int,
    phone: str,
    model: str = "AndroidEmulator",
    payload: bytes = b"",
    version: bytes = CLIENT_VERSION,
) -> bytes:
    """Build a request exactly the way ``Net_SetPACKET1`` does.

    Used by the test client in ``tools/fake_client.py`` and by the unit tests.
    """
    carrier = CARRIER_SKT if cmd in SKT_COMMANDS else CARRIER_KTF
    w = Writer()
    w.buff(MAGIC)
    w.buff(carrier)
    w.u8(REQ_MARKER)
    w.u16(REQ_TYPE)
    w.u16(cmd)
    w.u16(REQ_BODY_OVERHEAD + len(payload))
    w.text(phone, PHONE_LEN)
    w.text(model, MODEL_LEN)
    w.buff(fixed(version, 3))
    w.buff(payload)
    return w.bytes()


def decode_request(buf: bytes) -> tuple[Request | None, int]:
    """Pull one request out of ``buf``.

    Returns ``(request, consumed)``.  ``(None, n)`` means "no whole packet
    yet, but the first ``n`` bytes are junk and can be dropped".  The client
    itself resynchronises by scanning for ``ENS``, so the server does too.
    """
    start = buf.find(MAGIC)
    if start < 0:
        # Keep the last two bytes: they may be a split "EN" prefix.
        return None, max(0, len(buf) - (len(MAGIC) - 1))
    if len(buf) - start < REQ_HEADER_LEN:
        return None, start

    body_len = struct.unpack_from("<H", buf, start + 11)[0]
    total = REQ_PREFIX_LEN + body_len
    if total < REQ_HEADER_LEN:
        # Malformed length: skip this magic and keep looking.
        return None, start + len(MAGIC)
    if len(buf) - start < total:
        return None, start

    carrier = buf[start + 3 : start + 6]
    cmd = struct.unpack_from("<H", buf, start + 9)[0]
    phone = unfixed(buf[start + 13 : start + 34])
    model = unfixed(buf[start + 34 : start + 44])
    version = buf[start + 44 : start + 47]
    payload = bytes(buf[start + REQ_HEADER_LEN : start + total])
    req = Request(
        cmd=cmd,
        phone=phone,
        model=model,
        payload=payload,
        carrier=carrier,
        version=version,
        raw=bytes(buf[start : start + total]),
    )
    return req, start + total


def encode_response(cmd: int, result: int = RESULT_OK, payload: bytes = b"") -> bytes:
    w = Writer()
    w.buff(MAGIC)
    w.u16(cmd)
    w.u16(RES_BODY_OVERHEAD + len(payload))
    w.u16(result)
    w.buff(payload)
    return w.bytes()


def decode_response(buf: bytes) -> tuple[int, int, bytes, int]:
    """Decode one response; returns ``(cmd, result, payload, consumed)``."""
    start = buf.find(MAGIC)
    if start < 0 or len(buf) - start < RES_HEADER_LEN:
        raise TruncatedPacket("no complete response header")
    cmd = struct.unpack_from("<H", buf, start + 3)[0]
    body_len = struct.unpack_from("<H", buf, start + 5)[0]
    total = 7 + body_len
    if len(buf) - start < total:
        raise TruncatedPacket("response payload incomplete")
    result = struct.unpack_from("<H", buf, start + 7)[0]
    payload = bytes(buf[start + RES_HEADER_LEN : start + total])
    return cmd, result, payload, start + total
