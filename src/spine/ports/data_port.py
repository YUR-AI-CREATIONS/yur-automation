"""
Data Port — Data ingestion and export for the Universal Spine.

Handles inbound data ingestion and outbound export. Domain-agnostic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["DataPort", "DataPortConfig"]


@dataclass
class DataPortConfig:
    """Data port configuration."""

    port_id: str
    direction: str = "bidirectional"  # ingest, export, bidirectional
    schema_id: Optional[str] = None
    max_payload_bytes: int = 1_000_000
    metadata: dict[str, Any] = field(default_factory=dict)


class DataPort:
    """
    Data ingestion and export port.
    Routes data to/from external systems.
    """

    def __init__(
        self,
        port_id: str,
        ingest_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
        export_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
        config: Optional[DataPortConfig] = None,
    ) -> None:
        self._port_id = port_id
        self._ingest_fn = ingest_fn
        self._export_fn = export_fn
        self._config = config or DataPortConfig(port_id=port_id)

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ingest data. Returns normalized payload for spine processing."""
        if not self._ingest_fn:
            return {"port_id": self._port_id, "payload": payload, "ingested": True}
        return self._ingest_fn(payload)

    def export(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Export data to external destination."""
        if not self._export_fn:
            return {"port_id": self._port_id, "exported": False, "error": "No export handler"}
        return self._export_fn(payload)

    def handle(self, payload: dict[str, Any], direction: str = "ingest") -> dict[str, Any]:
        """Route by direction."""
        if direction == "export":
            return self.export(payload)
        return self.ingest(payload)
