"""Command handlers.

Every handler receives the decoded :class:`~ensserver.codec.Request` and
returns a list of raw response packets.  A list is returned rather than a
single packet because the client parses *one record per packet* for its list
screens: ``Net_favorite_2RECEIVE``, ``Net_unknown_log_2RECEIVE`` and friends
each read a single entry that starts with a ``u8`` slot index, so the server
sends one packet per row.

Payload layouts below are transcribed field-for-field from the matching
``Net_*RECEIVE`` functions; ``tools/extract_protocol.py`` regenerates that
list from the APK if you want to check them.
"""

from __future__ import annotations

import time

from . import commands as C
from .codec import (
    PHONE_LEN,
    RESULT_NO_DATA,
    RESULT_OK,
    Request,
    Writer,
    encode_response,
)
from .store import Store

HANDLERS: dict[int, callable] = {}


def handler(cmd: int):
    def deco(fn):
        HANDLERS[cmd] = fn
        return fn

    return deco


class Context:
    def __init__(self, store: Store, log):
        self.store = store
        self.log = log


def ok(cmd: int, payload: bytes = b"") -> list[bytes]:
    return [encode_response(cmd, RESULT_OK, payload)]


def empty(cmd: int) -> list[bytes]:
    """Well-formed 'nothing to send'.

    ``Net_SetRECEIVE`` treats any result other than 0x0000/0x8601 as a
    failure and skips the body, which is exactly what an empty list needs.
    """
    return [encode_response(cmd, RESULT_NO_DATA)]


# ---------------------------------------------------------------------------
# session / misc
# ---------------------------------------------------------------------------


@handler(C.CMD_USER)
def h_user(ctx: Context, req: Request) -> list[bytes]:
    """0x23 - Net_userREQUEST.  Client ignores the body, only the result."""
    ctx.store.touch_player(req.phone, req.model)
    return ok(req.cmd)


@handler(C.CMD_TIME)
def h_time(ctx: Context, req: Request) -> list[bytes]:
    """0x1e - Net_timeRECEIVE reads a single s32 and stores (server - local)."""
    return ok(req.cmd, Writer().s32(int(time.time())).bytes())


@handler(C.CMD_SMS)
def h_sms(ctx: Context, req: Request) -> list[bytes]:
    """0x13 - Net_smsRECEIVE reads one u32."""
    return ok(req.cmd, Writer().u32(0).bytes())


@handler(C.CMD_CASH_IS_BUY)
@handler(C.CMD_CASH_BUY)
def h_cash(ctx: Context, req: Request) -> list[bytes]:
    """0x39 / 0x3a - the carrier billing gateway.  Always declined here."""
    return empty(req.cmd)


# ---------------------------------------------------------------------------
# 미지의 섬 (unknown island)
# ---------------------------------------------------------------------------


@handler(C.CMD_ISLAND_ENTER)
def h_island_enter(ctx: Context, req: Request) -> list[bytes]:
    """0x121 - char[21] id + u32 value.  Response carries no payload."""
    r = req.reader()
    r.skip(PHONE_LEN)
    value = r.u32() if r.remaining >= 4 else 0
    ctx.store.touch_player(req.phone, req.model)
    ctx.store.island_upsert(req.phone, v1=value)
    return ok(req.cmd)


@handler(C.CMD_ISLAND_COUNT)
def h_island_count(ctx: Context, req: Request) -> list[bytes]:
    """0x122 - char[21] id.  Net_unknown_2RECEIVE reads one u32."""
    return ok(req.cmd, Writer().u32(ctx.store.island_count(exclude=req.phone)).bytes())


@handler(C.CMD_ISLAND_TARGET)
def h_island_target(ctx: Context, req: Request) -> list[bytes]:
    """0x123 - char[21] id + u32 index + u32 kind.

    Net_unknown_3RECEIVE reads::

        char[21] target id
        s32 v1, v2, v3, v4
        char[8]  blob8
        char[10] blob10a
        char[10] blob10b
    """
    r = req.reader()
    r.skip(PHONE_LEN)
    index = r.u32() if r.remaining >= 4 else 0
    _kind = r.u32() if r.remaining >= 4 else 0

    row = ctx.store.island_at(index, exclude=req.phone)
    if row is None:
        return empty(req.cmd)
    w = Writer()
    w.text(row.phone, PHONE_LEN)
    w.s32(row.v1).s32(row.v2).s32(row.v3).s32(row.v4)
    w.buff(row.blob8[:8].ljust(8, b"\x00"))
    w.buff(row.blob10a[:10].ljust(10, b"\x00"))
    w.buff(row.blob10b[:10].ljust(10, b"\x00"))
    return ok(req.cmd, w.bytes())


@handler(C.CMD_ISLAND_UPDATE)
def h_island_update(ctx: Context, req: Request) -> list[bytes]:
    """0x124 - char[21] id + char[8] + char[10] + char[10].  This is the
    packet that publishes *my* island so other players can find it."""
    r = req.reader()
    r.skip(PHONE_LEN)
    blob8 = r.buff(8) if r.remaining >= 8 else b"\x00" * 8
    blob10a = r.buff(10) if r.remaining >= 10 else b"\x00" * 10
    blob10b = r.buff(10) if r.remaining >= 10 else b"\x00" * 10
    ctx.store.touch_player(req.phone, req.model)
    ctx.store.island_upsert(
        req.phone, blob8=blob8, blob10a=blob10a, blob10b=blob10b
    )
    return ok(req.cmd)


@handler(C.CMD_ISLAND_BOX)
def h_island_box(ctx: Context, req: Request) -> list[bytes]:
    """0x125 - char[21] id + char[8].  Sent from Field_Box_mRun."""
    r = req.reader()
    r.skip(PHONE_LEN)
    blob8 = r.buff(8) if r.remaining >= 8 else b"\x00" * 8
    ctx.store.island_upsert(req.phone, blob8=blob8)
    return ok(req.cmd)


@handler(C.CMD_ISLAND_LOG_WRITE)
def h_island_log_write(ctx: Context, req: Request) -> list[bytes]:
    """0x126 - char[21] owner + u32 value: 'I visited this island'."""
    r = req.reader()
    owner = r.text(PHONE_LEN)
    value = r.u32() if r.remaining >= 4 else 0
    ctx.store.island_log_add(owner or req.phone, req.phone, v1=value)
    return ok(req.cmd)


@handler(C.CMD_ISLAND_LOG_LIST)
def h_island_log_list(ctx: Context, req: Request) -> list[bytes]:
    """0x127 - char[21] id.

    Net_unknown_log_2RECEIVE reads one record::

        u8 slot index
        char[21] visitor id
        s32 v1, v2, v3, v4
    """
    r = req.reader()
    owner = r.text(PHONE_LEN) or req.phone
    rows = ctx.store.island_log_list(owner)
    if not rows:
        return empty(req.cmd)
    out = []
    for idx, row in enumerate(rows):
        w = Writer()
        w.u8(idx)
        w.text(row["visitor"], PHONE_LEN)
        w.s32(row["v1"]).s32(row["v2"]).s32(row["v3"]).s32(row["v4"])
        out.append(encode_response(req.cmd, RESULT_OK, w.bytes()))
    return out


# ---------------------------------------------------------------------------
# 즐겨찾기 / 친구 (favourites & friends)
# ---------------------------------------------------------------------------


def _relation_add(ctx: Context, req: Request, kind: str) -> list[bytes]:
    """Net_favorite_1RECEIVE / Net_friend_1RECEIVE read a single s32."""
    target = req.reader().text(PHONE_LEN)
    if not target:
        return empty(req.cmd)
    ctx.store.relation_add(req.phone, target, kind)
    count = len(ctx.store.relation_list(req.phone, kind, limit=1000))
    return ok(req.cmd, Writer().s32(count).bytes())


def _relation_del(ctx: Context, req: Request, kind: str) -> list[bytes]:
    target = req.reader().text(PHONE_LEN)
    ctx.store.relation_del(req.phone, target, kind)
    return ok(req.cmd)


@handler(C.CMD_FAVORITE_ADD)
def h_favorite_add(ctx, req):
    return _relation_add(ctx, req, "favorite")


@handler(C.CMD_FAVORITE_DEL)
def h_favorite_del(ctx, req):
    return _relation_del(ctx, req, "favorite")


@handler(C.CMD_FAVORITE_LIST)
def h_favorite_list(ctx: Context, req: Request) -> list[bytes]:
    """0x132 - Net_favorite_2RECEIVE: u8 idx + char[3] + char[21] + s32 x3."""
    rows = ctx.store.relation_list(req.phone, "favorite")
    if not rows:
        return empty(req.cmd)
    out = []
    for idx, row in enumerate(rows):
        island = ctx.store.island_get(row["target"])
        w = Writer()
        w.u8(idx)
        w.text("", 3)
        w.text(row["target"], PHONE_LEN)
        w.s32(island.v1 if island else 0)
        w.s32(island.v2 if island else 0)
        w.s32(island.v3 if island else 0)
        out.append(encode_response(req.cmd, RESULT_OK, w.bytes()))
    return out


@handler(C.CMD_FRIEND_ADD)
def h_friend_add(ctx, req):
    return _relation_add(ctx, req, "friend")


@handler(C.CMD_FRIEND_DEL)
def h_friend_del(ctx, req):
    return _relation_del(ctx, req, "friend")


@handler(C.CMD_FRIEND_LIST)
def h_friend_list(ctx: Context, req: Request) -> list[bytes]:
    """0x142 - Net_friend_2RECEIVE: u8 idx + char[3] + char[21] + s32 x2."""
    rows = ctx.store.relation_list(req.phone, "friend")
    if not rows:
        return empty(req.cmd)
    out = []
    for idx, row in enumerate(rows):
        rank = ctx.store.rank_get(row["target"])
        w = Writer()
        w.u8(idx)
        w.text("", 3)
        w.text(row["target"], PHONE_LEN)
        w.s32(rank["score"] if rank else 0)
        w.s32(rank["win"] if rank else 0)
        out.append(encode_response(req.cmd, RESULT_OK, w.bytes()))
    return out


# ---------------------------------------------------------------------------
# 랭킹 / 대전 (ranking & battle)
# ---------------------------------------------------------------------------


@handler(C.CMD_RANK_REPORT)
def h_rank_report(ctx: Context, req: Request) -> list[bytes]:
    """0x111 - char[21] id + s32 x7 + char[40] x3 (my party snapshot)."""
    r = req.reader()
    r.skip(PHONE_LEN)
    values = [r.s32() for _ in range(7) if r.remaining >= 4]
    party = r.buff(min(120, r.remaining))
    ctx.store.touch_player(req.phone, req.model)
    ctx.store.rank_upsert(req.phone, values, party)
    return ok(req.cmd)


@handler(C.CMD_RANK_MINE)
def h_rank_mine(ctx: Context, req: Request) -> list[bytes]:
    """0x112 - Net_battle_rank_2RECEIVE:
    char[21] id + s32 x9 + char[40] + s32 (rank position)."""
    target = req.reader().text(PHONE_LEN) or req.phone
    row = ctx.store.rank_get(target)
    if row is None:
        return empty(req.cmd)
    w = Writer()
    w.text(target, PHONE_LEN)
    for col in ("score", "win", "lose", "v4", "v5", "v6", "v7", "v8", "v9"):
        w.s32(row[col])
    w.buff(bytes(row["party"])[:40].ljust(40, b"\x00"))
    w.s32(ctx.store.rank_position(target))
    return ok(req.cmd, w.bytes())


@handler(C.CMD_RANK_LIST)
def h_rank_list(ctx: Context, req: Request) -> list[bytes]:
    """0x113 - u32 offset + u32 kind.
    Net_battle_rank_3RECEIVE: u8 idx + char[3] + char[21] + s32 x2."""
    r = req.reader()
    offset = r.u32() if r.remaining >= 4 else 0
    rows = ctx.store.rank_list(offset)
    if not rows:
        return empty(req.cmd)
    out = []
    for idx, row in enumerate(rows):
        w = Writer()
        w.u8(idx)
        w.text("", 3)
        w.text(row["phone"], PHONE_LEN)
        w.s32(row["score"])
        w.s32(row["win"])
        out.append(encode_response(req.cmd, RESULT_OK, w.bytes()))
    return out


@handler(C.CMD_RANK_RESULT)
def h_rank_result(ctx: Context, req: Request) -> list[bytes]:
    """0x116 - battle result upload.
    Net_battle_rank_4RECEIVE: s32 x9 + char[40]."""
    r = req.reader()
    values = [r.s32() for _ in range(7) if r.remaining >= 4]
    party = r.buff(120) if r.remaining >= 120 else r.buff(r.remaining)
    ctx.store.rank_upsert(req.phone, values, party[:40])
    row = ctx.store.rank_get(req.phone)
    w = Writer()
    for col in ("score", "win", "lose", "v4", "v5", "v6", "v7", "v8", "v9"):
        w.s32(row[col] if row else 0)
    w.buff(bytes(row["party"])[:40].ljust(40, b"\x00") if row else b"\x00" * 40)
    return ok(req.cmd, w.bytes())


@handler(C.CMD_BATTLE_LOG_WRITE)
def h_battle_log_write(ctx: Context, req: Request) -> list[bytes]:
    """0x114 - u8 kind + char[21] opponent."""
    r = req.reader()
    kind = r.u8() if r.remaining else 0
    opponent = r.text(PHONE_LEN) if r.remaining >= PHONE_LEN else ""
    ctx.store.battle_log_add(req.phone, kind, opponent, 0)
    return ok(req.cmd)


@handler(C.CMD_BATTLE_LOG_LIST)
def h_battle_log_list(ctx: Context, req: Request) -> list[bytes]:
    """0x115 - Net_battle_log_2RECEIVE: u8 idx + u32 id + u8 kind
    + char[21] opponent + s32 value."""
    rows = ctx.store.battle_log_list(req.phone)
    if not rows:
        return empty(req.cmd)
    out = []
    for idx, row in enumerate(rows):
        w = Writer()
        w.u8(idx)
        w.u32(row["id"])
        w.u8(row["kind"])
        w.text(row["opponent"], PHONE_LEN)
        w.s32(row["value"])
        out.append(encode_response(req.cmd, RESULT_OK, w.bytes()))
    return out


# ---------------------------------------------------------------------------
# 우편함 / 선물 (mail & gifts)
# ---------------------------------------------------------------------------


@handler(C.CMD_GIFT_SEND)
def h_gift_send(ctx: Context, req: Request) -> list[bytes]:
    """0x45 - u8 kind + char[21] receiver + char[40] body + u32 amount."""
    r = req.reader()
    kind = r.u8() if r.remaining else 0
    receiver = r.text(PHONE_LEN) if r.remaining >= PHONE_LEN else ""
    body = r.buff(40) if r.remaining >= 40 else r.buff(r.remaining)
    amount = r.u32() if r.remaining >= 4 else 0
    if not receiver:
        return empty(req.cmd)
    ctx.store.mail_add(req.phone, receiver, kind, body, amount)
    return ok(req.cmd)


def _mail_record(row, idx: int) -> bytes:
    """Shared by Net_gift_2RECEIVE and Net_gift_4RECEIVE:
    u8 idx + s32 id + u8 kind + char[21] sender + char[40] body + s32 x3."""
    w = Writer()
    w.u8(idx)
    w.s32(row["id"])
    w.u8(row["kind"])
    w.text(row["sender"], PHONE_LEN)
    w.buff(bytes(row["body"])[:40].ljust(40, b"\x00"))
    w.s32(row["amount"])
    w.s32(row["ts"])
    w.s32(0)
    return w.bytes()


@handler(C.CMD_GIFT_INBOX)
def h_gift_inbox(ctx: Context, req: Request) -> list[bytes]:
    rows = ctx.store.mail_list(req.phone)
    if not rows:
        return empty(req.cmd)
    return [
        encode_response(req.cmd, RESULT_OK, _mail_record(row, idx))
        for idx, row in enumerate(rows)
    ]


@handler(C.CMD_GIFT_TAKE)
def h_gift_take(ctx: Context, req: Request) -> list[bytes]:
    """0x47 - u32 mail id.  No payload in the reply."""
    r = req.reader()
    mail_id = r.u32() if r.remaining >= 4 else 0
    row = ctx.store.mail_get(mail_id)
    if row is None or row["receiver"] != req.phone:
        return empty(req.cmd)
    ctx.store.mail_take(mail_id)
    return ok(req.cmd)


@handler(C.CMD_GIFT_DETAIL)
def h_gift_detail(ctx: Context, req: Request) -> list[bytes]:
    r = req.reader()
    mail_id = r.u32() if r.remaining >= 4 else 0
    row = ctx.store.mail_get(mail_id)
    if row is None or row["receiver"] != req.phone:
        return empty(req.cmd)
    return ok(req.cmd, _mail_record(row, 0))


# ---------------------------------------------------------------------------
# 경매장 (auction house)
# ---------------------------------------------------------------------------


@handler(C.CMD_AUCTION_SELL)
def h_auction_sell(ctx: Context, req: Request) -> list[bytes]:
    """0x101 - u8 kind + u8 attr + u8 grade + char[40] body + u32 price."""
    r = req.reader()
    kind = r.u8() if r.remaining else 0
    attr = r.u8() if r.remaining else 0
    grade = r.u8() if r.remaining else 0
    body = r.buff(40) if r.remaining >= 40 else r.buff(r.remaining)
    price = r.u32() if r.remaining >= 4 else 0
    ctx.store.auction_add(req.phone, kind, attr, grade, body, price)
    return ok(req.cmd)


@handler(C.CMD_AUCTION_COUNT)
def h_auction_count(ctx: Context, req: Request) -> list[bytes]:
    """0x102 - u8 kind + u8 attr.
    Net_auction_2RECEIVE: u8 kind + u8 attr + s32 count."""
    r = req.reader()
    kind = r.u8() if r.remaining else 0
    attr = r.u8() if r.remaining else 0
    w = Writer().u8(kind).u8(attr).s32(ctx.store.auction_count(kind, attr))
    return ok(req.cmd, w.bytes())


@handler(C.CMD_AUCTION_LIST)
def h_auction_list(ctx: Context, req: Request) -> list[bytes]:
    """0x103 - u8 x4 + u32 offset + u8 x2.

    Net_auction_3RECEIVE: u32 id + u8 idx + u32 price + u8 kind + u8 attr
    + char[40] body + char[21] seller + s32 ts + char[21] buyer.
    """
    r = req.reader()
    kind = r.u8() if r.remaining else 0
    attr = r.u8() if r.remaining else 0
    if r.remaining >= 2:
        r.skip(2)
    offset = r.u32() if r.remaining >= 4 else 0
    rows = ctx.store.auction_list(kind, attr, offset)
    if not rows:
        return empty(req.cmd)
    out = []
    for idx, row in enumerate(rows):
        w = Writer()
        w.u32(row["id"])
        w.u8(idx)
        w.u32(row["price"])
        w.u8(row["kind"])
        w.u8(row["attr"])
        w.buff(bytes(row["body"])[:40].ljust(40, b"\x00"))
        w.text(row["seller"], PHONE_LEN)
        w.s32(row["ts"])
        w.text(row["sold_to"], PHONE_LEN)
        out.append(encode_response(req.cmd, RESULT_OK, w.bytes()))
    return out


@handler(C.CMD_AUCTION_CANCEL)
def h_auction_cancel(ctx: Context, req: Request) -> list[bytes]:
    r = req.reader()
    auction_id = r.u32() if r.remaining >= 4 else 0
    row = ctx.store.auction_get(auction_id)
    if row is None or row["seller"] != req.phone:
        return empty(req.cmd)
    ctx.store.auction_remove(auction_id)
    return ok(req.cmd)


@handler(C.CMD_AUCTION_BUY)
def h_auction_buy(ctx: Context, req: Request) -> list[bytes]:
    r = req.reader()
    auction_id = r.u32() if r.remaining >= 4 else 0
    row = ctx.store.auction_get(auction_id)
    if row is None or row["sold_to"]:
        return empty(req.cmd)
    ctx.store.auction_sell_to(auction_id, req.phone)
    ctx.store.mail_add(row["seller"], row["seller"], 0, bytes(row["body"]), row["price"])
    return ok(req.cmd)


def dispatch(ctx: Context, req: Request) -> list[bytes]:
    fn = HANDLERS.get(req.cmd)
    if fn is None:
        ctx.log.warning(
            "unhandled cmd 0x%x from %s payload=%s",
            req.cmd,
            req.phone,
            req.payload.hex(),
        )
        return empty(req.cmd)
    try:
        return fn(ctx, req)
    except Exception:  # a malformed packet must not take the server down
        ctx.log.exception("handler for 0x%x failed", req.cmd)
        return empty(req.cmd)
