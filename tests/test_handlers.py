import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

import logging

import pytest

from ensserver import commands as C
from ensserver.codec import PHONE_LEN, RESULT_OK, decode_response, fixed
from ensserver.handlers import Context, dispatch
from ensserver.codec import Request
from ensserver.store import Store

A = "01011112222"
B = "01033334444"


@pytest.fixture()
def ctx():
    return Context(Store(":memory:"), logging.getLogger("test"))


def call(ctx, cmd, phone, payload=b""):
    req = Request(cmd=cmd, phone=phone, model="Emulator", payload=payload)
    return [decode_response(p)[:3] for p in dispatch(ctx, req)]


def ident(phone):
    return fixed(phone, PHONE_LEN)


def test_time_returns_a_plausible_clock(ctx):
    (cmd, result, payload), = call(ctx, C.CMD_TIME, A)
    assert (cmd, result) == (C.CMD_TIME, RESULT_OK)
    assert struct.unpack("<i", payload)[0] > 1_600_000_000


def test_island_count_only_sees_other_players(ctx):
    call(ctx, C.CMD_ISLAND_ENTER, A, ident(A) + struct.pack("<I", 1))
    (_, _, payload), = call(ctx, C.CMD_ISLAND_COUNT, A, ident(A))
    assert struct.unpack("<I", payload)[0] == 0

    call(ctx, C.CMD_ISLAND_ENTER, B, ident(B) + struct.pack("<I", 2))
    (_, _, payload), = call(ctx, C.CMD_ISLAND_COUNT, A, ident(A))
    assert struct.unpack("<I", payload)[0] == 1


def test_island_target_returns_the_other_players_island(ctx):
    """This is the packet that makes another player visible in 미지의 섬."""
    call(ctx, C.CMD_ISLAND_UPDATE, B, ident(B) + b"BOX12345" + b"a" * 10 + b"b" * 10)
    call(ctx, C.CMD_ISLAND_ENTER, B, ident(B) + struct.pack("<I", 9))

    (cmd, result, payload), = call(
        ctx, C.CMD_ISLAND_TARGET, A, ident(A) + struct.pack("<II", 0, 0)
    )
    assert (cmd, result) == (C.CMD_ISLAND_TARGET, RESULT_OK)
    # char[21] id + s32 x4 + char[8] + char[10] + char[10] == 63 bytes
    assert len(payload) == 21 + 16 + 8 + 10 + 10
    assert payload[:21] == ident(B)
    assert struct.unpack_from("<i", payload, 21)[0] == 9
    assert payload[37:45] == b"BOX12345"
    assert payload[45:55] == b"a" * 10
    assert payload[55:65] == b"b" * 10


def test_island_target_out_of_range_is_a_clean_miss(ctx):
    (cmd, result, payload), = call(
        ctx, C.CMD_ISLAND_TARGET, A, ident(A) + struct.pack("<II", 99, 0)
    )
    assert cmd == C.CMD_ISLAND_TARGET
    assert result != RESULT_OK  # client skips the body instead of reading garbage
    assert payload == b""


def test_island_visit_log_is_one_packet_per_row(ctx):
    call(ctx, C.CMD_ISLAND_LOG_WRITE, B, ident(A) + struct.pack("<I", 5))
    call(ctx, C.CMD_ISLAND_LOG_WRITE, A, ident(A) + struct.pack("<I", 6))

    replies = call(ctx, C.CMD_ISLAND_LOG_LIST, A, ident(A))
    assert len(replies) == 2
    for slot, (cmd, result, payload) in enumerate(replies):
        assert (cmd, result) == (C.CMD_ISLAND_LOG_LIST, RESULT_OK)
        assert payload[0] == slot
        assert len(payload) == 1 + 21 + 16
    # newest first: A's own visit, then B's
    assert replies[0][2][1:22] == ident(A)
    assert replies[1][2][1:22] == ident(B)


def test_empty_list_reports_no_data(ctx):
    (cmd, result, payload), = call(ctx, C.CMD_ISLAND_LOG_LIST, A, ident(A))
    assert result != RESULT_OK and payload == b""


def test_favourites_round_trip(ctx):
    (_, result, payload), = call(ctx, C.CMD_FAVORITE_ADD, A, ident(B))
    assert result == RESULT_OK and struct.unpack("<i", payload)[0] == 1

    replies = call(ctx, C.CMD_FAVORITE_LIST, A, ident(A))
    assert len(replies) == 1
    payload = replies[0][2]
    assert payload[0] == 0 and payload[4:25] == ident(B)

    call(ctx, C.CMD_FAVORITE_DEL, A, ident(B))
    (_, result, _), = call(ctx, C.CMD_FAVORITE_LIST, A, ident(A))
    assert result != RESULT_OK


def test_mail_delivers_between_players(ctx):
    call(ctx, C.CMD_GIFT_SEND, A, b"\x01" + ident(B) + b"gift" .ljust(40, b"\x00") + struct.pack("<I", 500))
    replies = call(ctx, C.CMD_GIFT_INBOX, B)
    assert len(replies) == 1
    payload = replies[0][2]
    assert payload[0] == 0
    assert payload[6:27] == ident(A)
    assert struct.unpack_from("<i", payload, 67)[0] == 500

    mail_id = struct.unpack_from("<i", payload, 1)[0]
    (_, result, _), = call(ctx, C.CMD_GIFT_TAKE, B, struct.pack("<I", mail_id))
    assert result == RESULT_OK
    (_, result, _), = call(ctx, C.CMD_GIFT_INBOX, B)
    assert result != RESULT_OK  # inbox is empty again


def test_ranking_reports_and_lists(ctx):
    payload = ident(A) + struct.pack("<7i", 120, 3, 1, 0, 0, 0, 0) + b"\x00" * 120
    call(ctx, C.CMD_RANK_REPORT, A, payload)
    (_, result, body), = call(ctx, C.CMD_RANK_MINE, A, ident(A))
    assert result == RESULT_OK
    assert body[:21] == ident(A)
    assert struct.unpack_from("<i", body, 21)[0] == 120
    assert struct.unpack_from("<i", body, len(body) - 4)[0] == 1  # rank position

    replies = call(ctx, C.CMD_RANK_LIST, A, struct.pack("<II", 0, 0))
    assert len(replies) == 1 and replies[0][2][4:25] == ident(A)


def test_unknown_command_does_not_crash(ctx):
    (cmd, result, payload), = call(ctx, 0x9999, A, b"\x01\x02")
    assert cmd == 0x9999 and result != RESULT_OK and payload == b""


def test_truncated_payload_does_not_crash(ctx):
    replies = call(ctx, C.CMD_ISLAND_TARGET, A, b"\x01\x02")
    assert replies and replies[0][1] != RESULT_OK
