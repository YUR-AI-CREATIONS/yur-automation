"""
Universal Flow Interface — Any system with IN and OUT can instantly plug in.

The Main OS: Incoming → Outgoing → Collection → Regenerating → Incoming.
Every flow has: inputs (in) → processing → outputs (out).

Plug in via:
- Python handler (sync/async callable)
- HTTP webhook (POST in → response out)
- Passthrough (echo in → out)

Flow protocol:
  flow_id: str (a-z, 0-9, _, -)
  in_schema: dict (JSON Schema) or None (accept any)
  out_schema: dict (JSON Schema) or None (return any)
  handler: callable(in: dict) -> dict
"""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Flow ID: alphanumeric, underscore, hyphen only (safe for URLs, env)
FLOW_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")

# Valid governance scopes for flows
VALID_SCOPES = frozenset({"internal", "external_low", "external_medium", "external_high", "restricted"})


class FlowDirection(str, Enum):
    """Where the flow sits in the circle."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    COLLECTION = "collection"
    REGENERATING = "regenerating"


@dataclass
class FlowSpec:
    """Specification for a pluggable flow."""

    flow_id: str
    name: str
    direction: FlowDirection = FlowDirection.INCOMING
    in_schema: Optional[dict[str, Any]] = None
    out_schema: Optional[dict[str, Any]] = None
    description: str = ""
    scope: str = "internal"
    timeout_seconds: float = 60.0
    max_payload_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if not FLOW_ID_PATTERN.match(self.flow_id):
            raise ValueError(
                f"Invalid flow_id: {self.flow_id!r} (must match {FLOW_ID_PATTERN.pattern})"
            )
        if self.scope not in VALID_SCOPES:
            raise ValueError(f"Invalid scope: {self.scope!r} (must be one of {sorted(VALID_SCOPES)})")
        if self.timeout_seconds <= 0 or self.timeout_seconds > 3600:
            raise ValueError("timeout_seconds must be in (0, 3600]")
        if self.max_payload_bytes <= 0 or self.max_payload_bytes > 50_000_000:
            raise ValueError("max_payload_bytes must be in (0, 50MB]")


@dataclass
class FlowResult:
    """Result of flow execution."""

    ok: bool
    out: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    flow_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response."""
        d: dict[str, Any] = {
            "ok": self.ok,
            "flow_id": self.flow_id,
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.ok and self.out is not None:
            d["out"] = self.out
        if not self.ok and self.error:
            d["error"] = self.error
        return d


class FlowHandler(ABC):
    """Handler for a flow. Implement process()."""

    @abstractmethod
    def process(self, inp: dict[str, Any]) -> dict[str, Any]:
        """Process input, return output. Must return dict (never None)."""
        pass

    async def process_async(self, inp: dict[str, Any]) -> dict[str, Any]:
        """Async variant. Default: run process() in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process, inp)


def flow_handler(fn: Callable[[dict[str, Any]], Any]) -> FlowHandler:
    """Wrap a callable as FlowHandler. Ensures return is dict."""

    class Wrapper(FlowHandler):
        def process(self, inp: dict[str, Any]) -> dict[str, Any]:
            result = fn(inp)
            if result is None:
                return {}
            if not isinstance(result, dict):
                return {"result": result}
            return result

    return Wrapper()


class FlowRegistry:
    """
    Registry of pluggable flows. Thread-safe, instant plug.
    """

    def __init__(self) -> None:
        self._flows: dict[str, tuple[FlowSpec, FlowHandler]] = {}
        self._lock = RLock()

    def plug(
        self,
        spec: FlowSpec,
        handler: FlowHandler | Callable[[dict[str, Any]], Any],
    ) -> None:
        """Instant plug: register a flow with spec and handler."""
        if not FLOW_ID_PATTERN.match(spec.flow_id):
            raise ValueError(f"Invalid flow_id: {spec.flow_id!r}")
        h = handler if isinstance(handler, FlowHandler) else flow_handler(handler)
        with self._lock:
            self._flows[spec.flow_id] = (spec, h)
        logger.info("Flow plugged: %s (%s)", spec.flow_id, spec.name)

    def unplug(self, flow_id: str) -> bool:
        """Remove a flow. Returns True if removed."""
        with self._lock:
            if flow_id in self._flows:
                del self._flows[flow_id]
                logger.info("Flow unplugged: %s", flow_id)
                return True
        return False

    def get(self, flow_id: str) -> Optional[tuple[FlowSpec, FlowHandler]]:
        """Get flow spec and handler."""
        with self._lock:
            return self._flows.get(flow_id)

    def list_flows(self) -> list[dict[str, Any]]:
        """List all registered flows."""
        with self._lock:
            return [
                {
                    "flow_id": spec.flow_id,
                    "name": spec.name,
                    "direction": spec.direction.value,
                    "scope": spec.scope,
                    "description": (spec.description[:80] + "...") if len(spec.description or "") > 80 else (spec.description or ""),
                    "timeout_seconds": spec.timeout_seconds,
                }
                for spec, _ in self._flows.values()
            ]

    def has(self, flow_id: str) -> bool:
        """Check if flow is registered."""
        with self._lock:
            return flow_id in self._flows

    def count(self) -> int:
        """Number of registered flows."""
        with self._lock:
            return len(self._flows)


__all__ = [
    "FLOW_ID_PATTERN",
    "FlowDirection",
    "FlowSpec",
    "FlowResult",
    "FlowHandler",
    "FlowRegistry",
    "flow_handler",
]
