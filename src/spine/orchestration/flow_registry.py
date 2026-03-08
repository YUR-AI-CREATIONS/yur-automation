"""
Universal Flow Registry — Domain-agnostic flow plugin system.

Wraps and extends src/core/flow_interface for the spine.
"""

from __future__ import annotations

import logging
from threading import RLock
from typing import Any, Callable, Optional

from src.core.flow_interface import (
    FLOW_ID_PATTERN,
    FlowDirection,
    FlowHandler,
    FlowSpec,
    flow_handler,
)

logger = logging.getLogger(__name__)

__all__ = ["UniversalFlowRegistry"]


class UniversalFlowRegistry:
    """
    Universal flow registry. Thread-safe, domain-agnostic.
    Delegates to flow_interface patterns; adds domain tagging.
    """

    def __init__(self) -> None:
        self._flows: dict[str, tuple[FlowSpec, FlowHandler]] = {}
        self._lock = RLock()
        self._domains: dict[str, str] = {}  # flow_id -> domain tag

    def plug(
        self,
        spec: FlowSpec,
        handler: FlowHandler | Callable[[dict[str, Any]], Any],
        domain: str = "generic",
    ) -> None:
        """Register a flow. Domain tag for multi-domain deployments."""
        if not FLOW_ID_PATTERN.match(spec.flow_id):
            raise ValueError(f"Invalid flow_id: {spec.flow_id!r}")
        h = handler if isinstance(handler, FlowHandler) else flow_handler(handler)
        with self._lock:
            self._flows[spec.flow_id] = (spec, h)
            self._domains[spec.flow_id] = domain
        logger.info("Flow plugged: %s (%s) [%s]", spec.flow_id, spec.name, domain)

    def unplug(self, flow_id: str) -> bool:
        """Remove a flow. Returns True if removed."""
        with self._lock:
            if flow_id in self._flows:
                del self._flows[flow_id]
                self._domains.pop(flow_id, None)
                logger.info("Flow unplugged: %s", flow_id)
                return True
        return False

    def get(self, flow_id: str) -> Optional[tuple[FlowSpec, FlowHandler]]:
        """Get flow spec and handler."""
        with self._lock:
            return self._flows.get(flow_id)

    def get_domain(self, flow_id: str) -> str:
        """Get domain tag for flow."""
        with self._lock:
            return self._domains.get(flow_id, "generic")

    def list_flows(self, domain: Optional[str] = None) -> list[dict[str, Any]]:
        """List flows, optionally filtered by domain."""
        with self._lock:
            items = []
            for fid, (spec, _) in self._flows.items():
                if domain and self._domains.get(fid) != domain:
                    continue
                items.append({
                    "flow_id": spec.flow_id,
                    "name": spec.name,
                    "direction": spec.direction.value,
                    "scope": spec.scope,
                    "domain": self._domains.get(fid, "generic"),
                    "description": (spec.description[:80] + "...") if len(spec.description or "") > 80 else (spec.description or ""),
                    "timeout_seconds": spec.timeout_seconds,
                })
            return items

    def has(self, flow_id: str) -> bool:
        """Check if flow is registered."""
        with self._lock:
            return flow_id in self._flows

    def count(self) -> int:
        """Number of registered flows."""
        with self._lock:
            return len(self._flows)
