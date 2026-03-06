"""
In-memory Event Bus — works without NATS. Reactive, parallel, observable.

Producer → Bus → Subscribers. trace_id links causality end-to-end.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from .event_contract import Event, create_event

logger = logging.getLogger(__name__)


class InMemoryBus:
    """
    In-memory publish/subscribe. No external deps.
    Subscribers receive events. Handlers can be sync or async.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._events: list[dict[str, Any]] = []  # Replay buffer (last N)
        self._max_replay = 10_000

    def publish(self, subject: str, event: dict[str, Any] | Event) -> None:
        """Publish event. All subscribers are notified."""
        d = event.to_dict() if isinstance(event, Event) else event
        d["_subject"] = subject
        self._events.append(d)
        if len(self._events) > self._max_replay:
            self._events = self._events[-self._max_replay:]
        for h in self._handlers.get(subject, []) + self._handlers.get("*", []):
            try:
                r = h(subject, d)
                if asyncio.iscoroutine(r):
                    asyncio.create_task(r)
            except Exception as e:
                logger.exception("Handler error for %s: %s", subject, e)

    def subscribe(self, subject: str, handler: Callable[[str, dict[str, Any]], Any]) -> None:
        """Subscribe to subject. Handlers receive (subject, event_dict)."""
        self._handlers[subject].append(handler)

    def get_events_by_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """Get all events for a trace_id. For causality replay."""
        return [e for e in self._events if e.get("trace_id") == trace_id]

    def get_events_by_type(self, event_type: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent events by type."""
        out = [e for e in reversed(self._events) if e.get("event_type") == event_type]
        return out[:limit]


# Singleton for app-wide use
_bus: InMemoryBus | None = None


def get_bus() -> InMemoryBus:
    global _bus
    if _bus is None:
        _bus = InMemoryBus()
    return _bus
