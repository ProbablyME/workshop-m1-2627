"""Diffusion temps réel vers le dashboard (WebSocket)."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.add(ws)
        log.info("WS client connecté (%d actifs)", len(self.active))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.active.discard(ws)
        log.info("WS client déconnecté (%d actifs)", len(self.active))

    async def broadcast(self, kind: str, data: dict[str, Any]) -> None:
        envelope = {"kind": kind, "ts": datetime.now(timezone.utc).isoformat(), "data": data}
        dead: list[WebSocket] = []
        for ws in list(self.active):
            try:
                await ws.send_json(envelope)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self.active)


manager = ConnectionManager()
