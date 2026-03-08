"""
API Port — External system integration for the Universal Spine.

Bridges external APIs and webhooks to spine flows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["APIPort", "APIPortConfig"]


@dataclass
class APIPortConfig:
    """API port configuration."""

    port_id: str
    base_url: Optional[str] = None
    auth_type: str = "none"  # none, bearer, api_key
    metadata: dict[str, Any] = field(default_factory=dict)


class APIPort:
    """
    External API integration port.
    Forwards requests to external systems and normalizes responses.
    """

    def __init__(
        self,
        port_id: str,
        request_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
        config: Optional[APIPortConfig] = None,
    ) -> None:
        self._port_id = port_id
        self._request_fn = request_fn
        self._config = config or APIPortConfig(port_id=port_id)

    def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call external API. Returns normalized response."""
        if not self._request_fn:
            return {
                "port_id": self._port_id,
                "ok": False,
                "error": "No request handler configured",
            }
        try:
            out = self._request_fn(payload)
            return {"port_id": self._port_id, "ok": True, "response": out}
        except Exception as e:
            logger.warning("APIPort %s call failed: %s", self._port_id, e)
            return {"port_id": self._port_id, "ok": False, "error": str(e)}
