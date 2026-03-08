"""
Flow Port — Custom workflow execution for the Universal Spine.

Executes flows by id via registry. Bridges spine orchestration to port interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.spine.orchestration.flow_registry import UniversalFlowRegistry
    from src.spine.orchestration.universal_orchestrator import UniversalOrchestrator

logger = logging.getLogger(__name__)

__all__ = ["FlowPort", "FlowPortConfig"]


@dataclass
class FlowPortConfig:
    """Flow port configuration."""

    port_id: str
    default_flow_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FlowPort:
    """
    Custom workflow execution port.
    Invokes flows via orchestrator.
    """

    def __init__(
        self,
        port_id: str,
        orchestrator: "UniversalOrchestrator",
        registry: Optional["UniversalFlowRegistry"] = None,
        config: Optional[FlowPortConfig] = None,
    ) -> None:
        self._port_id = port_id
        self._orchestrator = orchestrator
        self._registry = registry
        self._config = config or FlowPortConfig(port_id=port_id)

    def execute(
        self,
        payload: dict[str, Any],
        flow_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute flow. Uses payload.flow_id or default_flow_id if not specified."""
        fid = flow_id or payload.get("flow_id") or self._config.default_flow_id
        if not fid:
            return {"port_id": self._port_id, "ok": False, "error": "No flow_id specified"}
        inp = {k: v for k, v in payload.items() if k != "flow_id"}
        result = self._orchestrator.invoke(fid, inp)
        return {
            "port_id": self._port_id,
            "flow_id": fid,
            "ok": result.ok,
            "out": result.out,
            "error": result.error,
        }
