"""
NATS Event Bus — publish/subscribe. Optional: requires nats-py.

Agents never call each other. They publish events.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

NATS_AVAILABLE = False
try:
    import nats
    NATS_AVAILABLE = True
except ImportError:
    pass


def _nats_url() -> str:
    import os
    return os.getenv("NATS_URL", "nats://127.0.0.1:4222").strip()


class NatsBus:
    """NATS client for event bus. Use when nats-py is installed."""

    def __init__(self, url: str | None = None):
        self.url = url or _nats_url()
        self._nc: Any = None

    async def connect(self) -> None:
        if not NATS_AVAILABLE:
            raise RuntimeError("nats-py not installed. pip install nats-py")
        self._nc = await nats.connect(servers=[self.url])
        logger.info("NATS connected: %s", self.url)

    async def publish(self, subject: str, event: dict[str, Any]) -> None:
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")
        data = json.dumps(event, default=str).encode()
        await self._nc.publish(subject, data)
        logger.debug("Published %s", subject)

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        if not self._nc:
            raise RuntimeError("Not connected. Call connect() first.")

        async def _cb(msg: Any) -> None:
            try:
                data = json.loads(msg.data.decode())
                await handler(msg.subject, data)
            except Exception as e:
                logger.exception("Handler error for %s: %s", subject, e)

        await self._nc.subscribe(subject, cb=_cb)
        logger.info("Subscribed to %s", subject)

    async def close(self) -> None:
        if self._nc:
            await self._nc.close()
            self._nc = None
