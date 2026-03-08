"""
Port Manager — Multi-port distribution system for the Universal Spine.

Routes outputs to Data, Task, Flow, and API ports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["PortManager", "PortType", "PortConfig"]


class PortType(str, Enum):
    """Standard distribution port types."""

    DATA = "data"
    TASK = "task"
    FLOW = "flow"
    API = "api"


@dataclass
class PortConfig:
    """Port configuration."""

    port_id: str
    port_type: PortType
    enabled: bool = True
    priority: int = 0  # Higher = tried first
    metadata: dict[str, Any] = field(default_factory=dict)


class PortManager:
    """
    Manages distribution ports. Routes outputs to registered handlers.
    """

    def __init__(self) -> None:
        self._ports: dict[str, tuple[PortConfig, Callable[[dict[str, Any]], Any]]] = {}

    def register(
        self,
        port_id: str,
        port_type: PortType,
        handler: Callable[[dict[str, Any]], Any],
        priority: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Register a port handler."""
        config = PortConfig(
            port_id=port_id,
            port_type=port_type,
            priority=priority,
            metadata=metadata or {},
        )
        self._ports[port_id] = (config, handler)
        logger.info("Port registered: %s (%s)", port_id, port_type.value)

    def unregister(self, port_id: str) -> bool:
        """Remove a port."""
        if port_id in self._ports:
            del self._ports[port_id]
            return True
        return False

    def route(
        self,
        payload: dict[str, Any],
        port_types: Optional[list[PortType]] = None,
        port_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Route payload to matching ports.
        Returns {port_id: result} for each port invoked.
        """
        results: dict[str, Any] = {}
        targets = self._get_targets(port_types, port_ids)

        for port_id, (config, handler) in targets:
            if not config.enabled:
                continue
            try:
                out = handler(payload)
                results[port_id] = {"ok": True, "out": out}
            except Exception as e:
                logger.warning("Port %s failed: %s", port_id, e)
                results[port_id] = {"ok": False, "error": str(e)}

        return results

    def _get_targets(
        self,
        port_types: Optional[list[PortType]] = None,
        port_ids: Optional[list[str]] = None,
    ) -> list[tuple[str, tuple[PortConfig, Callable]]]:
        """Get ports to invoke, sorted by priority."""
        if port_ids:
            items = [(pid, self._ports[pid]) for pid in port_ids if pid in self._ports]
        elif port_types:
            types_set = set(port_types)
            items = [
                (pid, (cfg, h))
                for pid, (cfg, h) in self._ports.items()
                if cfg.port_type in types_set
            ]
        else:
            items = list(self._ports.items())

        items.sort(key=lambda x: -x[1][0].priority)
        return items

    def list_ports(self) -> list[dict[str, Any]]:
        """List registered ports."""
        return [
            {
                "port_id": pid,
                "port_type": cfg.port_type.value,
                "enabled": cfg.enabled,
                "priority": cfg.priority,
            }
            for pid, (cfg, _) in sorted(self._ports.items(), key=lambda x: -x[1][0].priority)
        ]
