"""asyncio TCP server speaking the ENS protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import time

from . import commands as C
from .codec import decode_request
from .handlers import Context, dispatch
from .store import Store

LOG = logging.getLogger("ens")

#: The port baked into ``EFC_netSET``: ``MC_utilHtons(0x139a)``.
DEFAULT_PORT = 5018


class Recorder:
    """Appends every packet to a JSONL file.

    Invaluable while filling in the fields that are still opaque: run the
    game against the server, then read back what the client actually sent.
    """

    def __init__(self, path: str | None):
        self.fh = open(path, "a", encoding="utf-8") if path else None

    def write(self, direction: str, peer: str, cmd: int, phone: str, data: bytes) -> None:
        if self.fh is None:
            return
        self.fh.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "dir": direction,
                    "peer": peer,
                    "cmd": f"0x{cmd:x}",
                    "name": C.name(cmd),
                    "phone": phone,
                    "hex": data.hex(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        self.fh.flush()

    def close(self) -> None:
        if self.fh is not None:
            self.fh.close()


class EnsServer:
    def __init__(self, db_path: str = "ens.db", record_path: str | None = None):
        self.store = Store(db_path)
        self.recorder = Recorder(record_path)
        self.ctx = Context(self.store, LOG)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = "%s:%s" % (writer.get_extra_info("peername") or ("?", "?"))[:2]
        LOG.info("connect %s", peer)
        buf = bytearray()
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buf += chunk
                while True:
                    req, consumed = decode_request(bytes(buf))
                    if req is None:
                        if consumed:
                            del buf[:consumed]
                        break
                    del buf[:consumed]
                    LOG.info(
                        "%s <- %s (0x%x) from %s, %d byte payload",
                        peer,
                        C.name(req.cmd),
                        req.cmd,
                        req.phone or "(no id)",
                        len(req.payload),
                    )
                    self.recorder.write("req", peer, req.cmd, req.phone, req.raw)
                    for packet in dispatch(self.ctx, req):
                        writer.write(packet)
                        self.recorder.write("res", peer, req.cmd, req.phone, packet)
                    await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        except Exception:
            LOG.exception("connection %s failed", peer)
        finally:
            LOG.info("disconnect %s", peer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def serve(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
        srv = await asyncio.start_server(self.handle, host, port)
        addrs = ", ".join(str(s.getsockname()) for s in srv.sockets or [])
        LOG.info("ENS server listening on %s (db: %d players)", addrs, self.store.player_count())
        async with srv:
            await srv.serve_forever()

    def close(self) -> None:
        self.recorder.close()
        self.store.close()
