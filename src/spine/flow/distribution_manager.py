"""
Distribution Manager — Multi-destination routing for the Universal Spine.

Routes outputs to multiple ports based on config.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.spine.orchestration.port_manager import PortManager, PortType

logger = logging.getLogger(__name__)

__all__ = ["DistributionManager", "DistributionConfig"]


@dataclass
class DistributionConfig:
    """Distribution routing configuration."""

    default_ports: list[PortType] = field(default_factory=lambda: [PortType.DATA])
    port_ids: Optional[list[str]] = None
    fan_out: bool = True  # Send to all matching ports
    metadata: dict[str, Any] = field(default_factory=dict)


class DistributionManager:
    """
    Multi-destination distribution manager.
    Routes payloads through PortManager to configured ports.
    """

    def __init__(
        self,
        port_manager: PortManager,
        config: Optional[DistributionConfig] = None,
    ) -> None:
        self._port_manager = port_manager
        self._config = config or DistributionConfig()

    def distribute(
        self,
        payload: dict[str, Any],
        port_types: Optional[list[PortType]] = None,
        port_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Distribute payload to ports.
        Returns {port_id: result} for each destination.
        """
        types = port_types or self._config.default_ports
        ids = port_ids or self._config.port_ids
        return self._port_manager.route(payload, port_types=types, port_ids=ids)

    def add_route(
        self,
        port_id: str,
        port_type: PortType,
        handler: Callable[[dict[str, Any]], Any],
        priority: int = 0,
    ) -> None:
        """Register a distribution route."""
        self._port_manager.register(port_id, port_type, handler, priority=priority)
