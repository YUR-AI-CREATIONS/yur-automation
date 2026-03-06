"""
Event Bus — Agents publish events. No direct calls.

Producer → Bus → Subscribers. Reactive, parallel, replayable, observable.
"""

from .event_contract import Event, create_event, EVENT_TYPES
from .in_memory_bus import InMemoryBus, get_bus

__all__ = ["Event", "create_event", "EVENT_TYPES", "InMemoryBus", "get_bus"]
