import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from ensserver.codec import (
    CARRIER_KTF,
    CARRIER_SKT,
    REQ_HEADER_LEN,
    Reader,
    Writer,
    decode_request,
    decode_response,
    encode_request,
    encode_response,
)


def test_request_header_matches_net_setpacket1():
    pkt = encode_request(0x121, "01012345678", "SHW-M110S", b"\x01\x02\x03\x04")
    assert pkt[0:3] == b"ENS"
    assert pkt[3:6] == CARRIER_KTF
    assert pkt[6] == 0x11
    assert struct.unpack_from("<H", pkt, 7)[0] == 0x0087
    assert struct.unpack_from("<H", pkt, 9)[0] == 0x121
    # length counts everything after the length field: 34 + payload
    assert struct.unpack_from("<H", pkt, 11)[0] == 34 + 4
    assert pkt[13:34] == b"01012345678".ljust(21, b"\x00")
    assert pkt[34:44] == b"SHW-M110S\x00"
    assert pkt[44:47] == b"100"
    assert len(pkt) == REQ_HEADER_LEN + 4


def test_sms_and_billing_use_the_skt_tag():
    for cmd in (0x13, 0x39, 0x3A):
        assert encode_request(cmd, "010")[3:6] == CARRIER_SKT
    assert encode_request(0x121, "010")[3:6] == CARRIER_KTF


def test_request_round_trip():
    pkt = encode_request(0x123, "01099998888", "Emulator", b"\xde\xad\xbe\xef")
    req, used = decode_request(pkt)
    assert used == len(pkt)
    assert (req.cmd, req.phone, req.model, req.payload) == (
        0x123,
        "01099998888",
        "Emulator",
        b"\xde\xad\xbe\xef",
    )


def test_decoder_resynchronises_on_leading_junk():
    pkt = encode_request(0x122, "010")
    req, used = decode_request(b"\x00\xff\x7f" + pkt)
    assert req is not None and req.cmd == 0x122
    assert used == 3 + len(pkt)


def test_decoder_waits_for_a_whole_packet():
    pkt = encode_request(0x122, "010", payload=b"12345678")
    req, used = decode_request(pkt[:-2])
    assert req is None and used == 0


def test_two_packets_in_one_read():
    stream = encode_request(0x122, "010") + encode_request(0x1E, "010")
    first, used = decode_request(stream)
    assert first.cmd == 0x122
    second, _ = decode_request(stream[used:])
    assert second.cmd == 0x1E


def test_response_header_matches_net_datareceive():
    res = encode_response(0x122, 0, b"\x2a\x00\x00\x00")
    assert res[0:3] == b"ENS"
    assert struct.unpack_from("<H", res, 3)[0] == 0x122
    # the length field covers the result word plus the payload
    assert struct.unpack_from("<H", res, 5)[0] == 2 + 4
    assert struct.unpack_from("<H", res, 7)[0] == 0
    cmd, result, payload, used = decode_response(res)
    assert (cmd, result, payload, used) == (0x122, 0, b"\x2a\x00\x00\x00", len(res))


def test_integers_are_little_endian():
    assert Writer().u16(0x1234).bytes() == b"\x34\x12"
    assert Writer().u32(0x11223344).bytes() == b"\x44\x33\x22\x11"
    assert Reader(b"\x34\x12").u16() == 0x1234
    assert Reader(b"\xff\xff\xff\xff").s32() == -1


def test_fixed_fields_are_nul_padded_and_truncated():
    assert Writer().text("abc", 5).bytes() == b"abc\x00\x00"
    assert Writer().text("abcdefg", 3).bytes() == b"abc"
    assert Reader(b"abc\x00\x00").text(5) == "abc"
