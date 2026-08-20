"""SQLite persistence for the private server.

The schema mirrors the fields the client actually reads back, so every
column maps onto something in ``docs/protocol.md``.  Anything the client
sends but whose meaning is not pinned down yet is kept as an opaque blob
(``blob8`` / ``blob10a`` / ``blob10b``) and echoed back verbatim -- that is
enough for players to see each other's islands even before every field is
named.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS player (
    phone      TEXT PRIMARY KEY,
    model      TEXT NOT NULL DEFAULT '',
    nick       TEXT NOT NULL DEFAULT '',
    first_seen INTEGER NOT NULL,
    last_seen  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS island (
    phone      TEXT PRIMARY KEY,
    v1         INTEGER NOT NULL DEFAULT 0,
    v2         INTEGER NOT NULL DEFAULT 0,
    v3         INTEGER NOT NULL DEFAULT 0,
    v4         INTEGER NOT NULL DEFAULT 0,
    blob8      BLOB    NOT NULL DEFAULT x'0000000000000000',
    blob10a    BLOB    NOT NULL DEFAULT x'00000000000000000000',
    blob10b    BLOB    NOT NULL DEFAULT x'00000000000000000000',
    updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS island_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    owner    TEXT NOT NULL,
    visitor  TEXT NOT NULL,
    v1       INTEGER NOT NULL DEFAULT 0,
    v2       INTEGER NOT NULL DEFAULT 0,
    v3       INTEGER NOT NULL DEFAULT 0,
    v4       INTEGER NOT NULL DEFAULT 0,
    ts       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS island_log_owner ON island_log(owner, id DESC);

CREATE TABLE IF NOT EXISTS relation (
    owner  TEXT NOT NULL,
    target TEXT NOT NULL,
    kind   TEXT NOT NULL,          -- 'favorite' | 'friend'
    ts     INTEGER NOT NULL,
    PRIMARY KEY (owner, target, kind)
);

CREATE TABLE IF NOT EXISTS rank (
    phone   TEXT PRIMARY KEY,
    score   INTEGER NOT NULL DEFAULT 0,
    win     INTEGER NOT NULL DEFAULT 0,
    lose    INTEGER NOT NULL DEFAULT 0,
    v4      INTEGER NOT NULL DEFAULT 0,
    v5      INTEGER NOT NULL DEFAULT 0,
    v6      INTEGER NOT NULL DEFAULT 0,
    v7      INTEGER NOT NULL DEFAULT 0,
    v8      INTEGER NOT NULL DEFAULT 0,
    v9      INTEGER NOT NULL DEFAULT 0,
    party   BLOB NOT NULL DEFAULT x'',
    updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS battle_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    owner   TEXT NOT NULL,
    kind    INTEGER NOT NULL DEFAULT 0,
    opponent TEXT NOT NULL DEFAULT '',
    value   INTEGER NOT NULL DEFAULT 0,
    ts      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS battle_log_owner ON battle_log(owner, id DESC);

CREATE TABLE IF NOT EXISTS mail (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sender   TEXT NOT NULL,
    receiver TEXT NOT NULL,
    kind     INTEGER NOT NULL DEFAULT 0,
    body     BLOB NOT NULL DEFAULT x'',
    amount   INTEGER NOT NULL DEFAULT 0,
    taken    INTEGER NOT NULL DEFAULT 0,
    ts       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS mail_receiver ON mail(receiver, id DESC);

CREATE TABLE IF NOT EXISTS auction (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    seller   TEXT NOT NULL,
    kind     INTEGER NOT NULL DEFAULT 0,
    attr     INTEGER NOT NULL DEFAULT 0,
    grade    INTEGER NOT NULL DEFAULT 0,
    body     BLOB NOT NULL DEFAULT x'',
    price    INTEGER NOT NULL DEFAULT 0,
    sold_to  TEXT NOT NULL DEFAULT '',
    ts       INTEGER NOT NULL
);
"""


@dataclass
class IslandRow:
    phone: str
    v1: int
    v2: int
    v3: int
    v4: int
    blob8: bytes
    blob10a: bytes
    blob10b: bytes
    updated_at: int


class Store:
    def __init__(self, path: str = "ens.db"):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # -- players ----------------------------------------------------------
    def touch_player(self, phone: str, model: str = "") -> None:
        now = int(time.time())
        self.db.execute(
            "INSERT INTO player(phone, model, first_seen, last_seen) VALUES(?,?,?,?) "
            "ON CONFLICT(phone) DO UPDATE SET last_seen=excluded.last_seen, "
            "model=CASE WHEN excluded.model<>'' THEN excluded.model ELSE player.model END",
            (phone, model, now, now),
        )

    def player_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM player").fetchone()[0]

    # -- island -----------------------------------------------------------
    def island_upsert(
        self,
        phone: str,
        *,
        v1: int | None = None,
        v2: int | None = None,
        v3: int | None = None,
        v4: int | None = None,
        blob8: bytes | None = None,
        blob10a: bytes | None = None,
        blob10b: bytes | None = None,
    ) -> None:
        now = int(time.time())
        self.db.execute(
            "INSERT OR IGNORE INTO island(phone, updated_at) VALUES(?,?)", (phone, now)
        )
        sets, args = ["updated_at=?"], [now]
        for col, val in (
            ("v1", v1),
            ("v2", v2),
            ("v3", v3),
            ("v4", v4),
            ("blob8", blob8),
            ("blob10a", blob10a),
            ("blob10b", blob10b),
        ):
            if val is not None:
                sets.append(f"{col}=?")
                args.append(val)
        args.append(phone)
        self.db.execute(f"UPDATE island SET {','.join(sets)} WHERE phone=?", args)

    def island_get(self, phone: str) -> IslandRow | None:
        row = self.db.execute("SELECT * FROM island WHERE phone=?", (phone,)).fetchone()
        return IslandRow(**dict(row)) if row else None

    def island_count(self, exclude: str = "") -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM island WHERE phone<>?", (exclude,)
        ).fetchone()[0]

    def island_at(self, index: int, exclude: str = "") -> IslandRow | None:
        """Fetch the ``index``-th island, newest first, skipping ``exclude``."""
        row = self.db.execute(
            "SELECT * FROM island WHERE phone<>? ORDER BY updated_at DESC, phone "
            "LIMIT 1 OFFSET ?",
            (exclude, max(0, index)),
        ).fetchone()
        return IslandRow(**dict(row)) if row else None

    def island_log_add(self, owner: str, visitor: str, v1=0, v2=0, v3=0, v4=0) -> None:
        self.db.execute(
            "INSERT INTO island_log(owner, visitor, v1, v2, v3, v4, ts) VALUES(?,?,?,?,?,?,?)",
            (owner, visitor, v1, v2, v3, v4, int(time.time())),
        )

    def island_log_list(self, owner: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM island_log WHERE owner=? ORDER BY id DESC LIMIT ?",
            (owner, limit),
        ).fetchall()

    # -- relations --------------------------------------------------------
    def relation_add(self, owner: str, target: str, kind: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO relation(owner, target, kind, ts) VALUES(?,?,?,?)",
            (owner, target, kind, int(time.time())),
        )

    def relation_del(self, owner: str, target: str, kind: str) -> None:
        self.db.execute(
            "DELETE FROM relation WHERE owner=? AND target=? AND kind=?",
            (owner, target, kind),
        )

    def relation_list(self, owner: str, kind: str, limit: int = 50) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM relation WHERE owner=? AND kind=? ORDER BY ts DESC LIMIT ?",
            (owner, kind, limit),
        ).fetchall()

    # -- ranking ----------------------------------------------------------
    def rank_upsert(self, phone: str, values: list[int], party: bytes) -> None:
        cols = ["score", "win", "lose", "v4", "v5", "v6", "v7", "v8", "v9"]
        values = (values + [0] * len(cols))[: len(cols)]
        self.db.execute("INSERT OR IGNORE INTO rank(phone) VALUES(?)", (phone,))
        self.db.execute(
            f"UPDATE rank SET {','.join(c + '=?' for c in cols)}, party=?, updated_at=? "
            "WHERE phone=?",
            (*values, party, int(time.time()), phone),
        )

    def rank_get(self, phone: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM rank WHERE phone=?", (phone,)).fetchone()

    def rank_list(self, offset: int = 0, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM rank ORDER BY score DESC, win DESC LIMIT ? OFFSET ?",
            (limit, max(0, offset)),
        ).fetchall()

    def rank_position(self, phone: str) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) FROM rank WHERE score > (SELECT score FROM rank WHERE phone=?)",
            (phone,),
        ).fetchone()
        return (row[0] + 1) if row else 0

    # -- battle log -------------------------------------------------------
    def battle_log_add(self, owner: str, kind: int, opponent: str, value: int) -> None:
        self.db.execute(
            "INSERT INTO battle_log(owner, kind, opponent, value, ts) VALUES(?,?,?,?,?)",
            (owner, kind, opponent, value, int(time.time())),
        )

    def battle_log_list(self, owner: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM battle_log WHERE owner=? ORDER BY id DESC LIMIT ?",
            (owner, limit),
        ).fetchall()

    # -- mail -------------------------------------------------------------
    def mail_add(self, sender: str, receiver: str, kind: int, body: bytes, amount: int) -> int:
        cur = self.db.execute(
            "INSERT INTO mail(sender, receiver, kind, body, amount, ts) VALUES(?,?,?,?,?,?)",
            (sender, receiver, kind, body, amount, int(time.time())),
        )
        return cur.lastrowid

    def mail_list(self, receiver: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM mail WHERE receiver=? AND taken=0 ORDER BY id DESC LIMIT ?",
            (receiver, limit),
        ).fetchall()

    def mail_get(self, mail_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM mail WHERE id=?", (mail_id,)).fetchone()

    def mail_take(self, mail_id: int) -> None:
        self.db.execute("UPDATE mail SET taken=1 WHERE id=?", (mail_id,))

    # -- auction ----------------------------------------------------------
    def auction_add(self, seller: str, kind: int, attr: int, grade: int, body: bytes, price: int) -> int:
        cur = self.db.execute(
            "INSERT INTO auction(seller, kind, attr, grade, body, price, ts) VALUES(?,?,?,?,?,?,?)",
            (seller, kind, attr, grade, body, price, int(time.time())),
        )
        return cur.lastrowid

    def auction_list(self, kind: int, attr: int, offset: int = 0, limit: int = 20) -> list[sqlite3.Row]:
        sql = "SELECT * FROM auction WHERE sold_to='' "
        args: list = []
        if kind:
            sql += "AND kind=? "
            args.append(kind)
        if attr:
            sql += "AND attr=? "
            args.append(attr)
        sql += "ORDER BY id DESC LIMIT ? OFFSET ?"
        args += [limit, max(0, offset)]
        return self.db.execute(sql, args).fetchall()

    def auction_count(self, kind: int, attr: int) -> int:
        sql = "SELECT COUNT(*) FROM auction WHERE sold_to='' "
        args: list = []
        if kind:
            sql += "AND kind=? "
            args.append(kind)
        if attr:
            sql += "AND attr=? "
            args.append(attr)
        return self.db.execute(sql, args).fetchone()[0]

    def auction_get(self, auction_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM auction WHERE id=?", (auction_id,)).fetchone()

    def auction_sell_to(self, auction_id: int, buyer: str) -> None:
        self.db.execute("UPDATE auction SET sold_to=? WHERE id=?", (buyer, auction_id))

    def auction_remove(self, auction_id: int) -> None:
        self.db.execute("DELETE FROM auction WHERE id=?", (auction_id,))
