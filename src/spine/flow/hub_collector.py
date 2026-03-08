"""
Hub Collector — Central result collection for the Universal Spine.

Collects results from multiple sources into a central hub.
"""

from __future__ import annotations

import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["HubCollector", "CollectedResult"]


@dataclass
class CollectedResult:
    """A result collected at the hub."""

    result_id: str
    source: str
    payload: dict[str, Any]
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


class HubCollector:
    """
    Central result collector.
    Accepts results from ports and flows; provides query interface.
    """

    def __init__(self, max_results: int = 10_000) -> None:
        self._results: deque[CollectedResult] = deque(maxlen=max_results)
        self._by_source: dict[str, list[str]] = {}

    def collect(
        self,
        source: str,
        payload: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Collect a result. Returns result_id."""
        rid = uuid.uuid4().hex[:16]
        ts = datetime.now(timezone.utc).isoformat()
        result = CollectedResult(
            result_id=rid,
            source=source,
            payload=payload,
            timestamp=ts,
            metadata=metadata or {},
        )
        self._results.append(result)
        self._by_source.setdefault(source, []).append(rid)
        return rid

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get most recent results."""
        items = list(self._results)[-limit:]
        return [
            {
                "result_id": r.result_id,
                "source": r.source,
                "payload": r.payload,
                "timestamp": r.timestamp,
            }
            for r in reversed(items)
        ]

    def get_by_source(self, source: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get results by source."""
        rids = self._by_source.get(source, [])[-limit:]
        out = []
        for r in reversed(self._results):
            if r.result_id in rids:
                out.append({
                    "result_id": r.result_id,
                    "source": r.source,
                    "payload": r.payload,
                    "timestamp": r.timestamp,
                })
            if len(out) >= limit:
                break
        return out

    def count(self) -> int:
        """Total collected results."""
        return len(self._results)
