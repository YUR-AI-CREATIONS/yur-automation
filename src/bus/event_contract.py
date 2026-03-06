"""
Event contract — standard fields for every event.

trace_id is non-negotiable. That's how Franklin tracks causality end-to-end.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Event:
    """Standard event. Every event has these fields."""

    event_id: str
    event_type: str
    ts: str
    trace_id: str
    tenant_id: str
    actor: str
    payload: dict[str, Any]
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "ts": self.ts,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "actor": self.actor,
            "payload": self.payload,
            "evidence": self.evidence,
        }


def create_event(
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    *,
    trace_id: str | None = None,
    tenant_id: str = "default",
    evidence: dict[str, Any] | None = None,
) -> Event:
    """Create a standard event. trace_id links causality."""
    tid = trace_id or str(uuid.uuid4())
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        ts=_utcnow_iso(),
        trace_id=tid,
        tenant_id=tenant_id,
        actor=actor,
        payload=payload,
        evidence=evidence or {"sources": [], "hashes": []},
    )


# Core event types (standardize these)
EVENT_TYPES = frozenset({
    "parcel.discovered",
    "zoning.assessed",
    "cost.estimated",
    "roi.simulated",
    "opportunity.ranked",
    "corridor.signal_detected",
    "metro.migration_shift",
    "permit.acceleration",
})
