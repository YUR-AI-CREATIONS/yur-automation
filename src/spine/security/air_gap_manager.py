"""
Air Gap Manager — Offline operation controller.

Enforces air-gap mode to block external connections when needed.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = ["AirGapManager"]


class AirGapManager:
    """
    Controls air-gap mode for offline operation.

    When enabled, blocks all external API calls and routes requests to
    local services only (Ollama, local DB, etc).
    """

    def __init__(self, air_gap_enabled: bool = False) -> None:
        self.air_gap_enabled = air_gap_enabled
        self.blocked_domains: set[str] = set()
        self.allowed_local_services: set[str] = {
            "localhost",
            "127.0.0.1",
            "::1",
            "ollama",
        }

    def enable_air_gap(self) -> None:
        """Enable air-gap mode."""
        self.air_gap_enabled = True
        logger.info("Air-gap mode ENABLED - external connections blocked")

    def disable_air_gap(self) -> None:
        """Disable air-gap mode."""
        self.air_gap_enabled = False
        logger.info("Air-gap mode disabled")

    def is_air_gap_enabled(self) -> bool:
        """Check if air-gap mode is active."""
        return self.air_gap_enabled

    def can_connect_to(self, host: str, port: Optional[int] = None) -> bool:
        """Check if a connection is allowed."""
        if not self.air_gap_enabled:
            return True

        # Allow local services
        for allowed in self.allowed_local_services:
            if host.lower() == allowed or host.startswith(allowed):
                return True

        # Check blocked domains
        if host in self.blocked_domains:
            return False

        logger.warning(
            f"Air-gap mode: blocking connection to {host}:{port or 'unknown'}"
        )
        return False

    def block_domain(self, domain: str) -> None:
        """Add domain to blocklist."""
        self.blocked_domains.add(domain)
        logger.debug(f"Blocked domain: {domain}")

    def allow_domain(self, domain: str) -> None:
        """Remove domain from blocklist."""
        self.blocked_domains.discard(domain)
        logger.debug(f"Allowed domain: {domain}")

    def add_local_service(self, host: str) -> None:
        """Register additional local service."""
        self.allowed_local_services.add(host)
        logger.debug(f"Registered local service: {host}")

    def get_status(self) -> dict[str, any]:
        """Get current air-gap status."""
        return {
            "air_gap_enabled": self.air_gap_enabled,
            "blocked_domains": list(self.blocked_domains),
            "allowed_local_services": list(self.allowed_local_services),
        }
