"""
Air-Gap Policy — centralized control of outbound network access.

Enforces:
- Default-deny internet egress
- Allowlist for localhost, optionally LAN
- Policy-gated external endpoints (e.g., Procore, Trinity)
- Explicit audit trail of network attempts

Usage:
    policy = AirGapPolicy(mode="airgap_strict")  # Deny all outbound
    if policy.allow_http("https://api.procore.com"):
        response = requests.get(...)  # Safe to call
    else:
        raise ForbiddenError("Outbound to procore.com not allowed in airgap mode")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class AirGapMode(str, Enum):
    """Air-gap operation modes."""
    AIRGAP_STRICT = "airgap_strict"  # No internet outbound; localhost only
    AIRGAP_LAN = "airgap_lan"        # LAN allowed; internet blocked
    CONTROLLED = "controlled"        # Explicit allowlist per endpoint
    OPEN = "open"                    # No restrictions (default for development)


@dataclass
class AllowedEndpoint:
    """Allowed outbound endpoint for 'controlled' mode."""
    host: str
    reason: str  # e.g., "procore_integration", "trinity_sync"
    ports: Optional[list[int]] = None  # None = all ports


class AirGapPolicy:
    """Central network access policy enforcement."""
    
    def __init__(
        self,
        mode: AirGapMode | str = AirGapMode.OPEN,
        allowed_endpoints: Optional[list[AllowedEndpoint]] = None,
        audit_fn: Optional[Any] = None,
    ):
        """
        Initialize air-gap policy.
        
        Args:
            mode: Operation mode (airgap_strict, airgap_lan, controlled, open)
            allowed_endpoints: List of allowed endpoints for 'controlled' mode
            audit_fn: Optional audit callback: audit_fn(action, host, allowed, reason)
        """
        self.mode = AirGapMode(mode) if isinstance(mode, str) else mode
        self.allowed_endpoints = allowed_endpoints or []
        self.audit_fn = audit_fn
        self._endpoint_map = {ep.host: ep for ep in self.allowed_endpoints}
    
    def allow_http(self, url: str, reason: str = "unspecified") -> bool:
        """
        Check if outbound HTTP to a URL is allowed under current policy.
        
        Args:
            url: Full URL (e.g., "https://api.procore.com/projects")
            reason: Reason for the request (for audit trail)
        
        Returns:
            True if allowed; False otherwise
        """
        parsed = urlparse(url)
        host = parsed.hostname or "unknown"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        # Evaluate policy
        allowed = self._is_allowed(host, port)
        
        # Audit
        if self.audit_fn:
            self.audit_fn(
                action="http_request",
                host=host,
                url=url,
                port=port,
                allowed=allowed,
                reason=reason,
                policy_mode=self.mode.value,
            )
        
        # Log
        level = logging.DEBUG if allowed else logging.WARNING
        logger.log(
            level,
            f"[AirGap] {self.mode.value}: HTTP {host}:{port} = {allowed} ({reason})",
        )
        
        return allowed
    
    def _is_allowed(self, host: str, port: int) -> bool:
        """Internal check based on current mode and host."""
        if self.mode == AirGapMode.OPEN:
            return True
        
        if host in ("localhost", "127.0.0.1", "::1", "[::1]"):
            return True  # Always allow localhost
        
        if self.mode == AirGapMode.AIRGAP_STRICT:
            return False  # Only localhost allowed
        
        if self.mode == AirGapMode.AIRGAP_LAN:
            return self._is_lan_address(host)
        
        if self.mode == AirGapMode.CONTROLLED:
            ep = self._endpoint_map.get(host)
            if ep and (ep.ports is None or port in ep.ports):
                return True
            return False
        
        return False
    
    def _is_lan_address(self, host: str) -> bool:
        """Check if host is on private network (RFC 1918)."""
        try:
            import ipaddress
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback
        except ValueError:
            # Not an IP; check DNS
            # For now, assume any non-IP in AIRGAP_LAN is blocked
            # (could add internal DNS list later)
            return False
    
    def register_endpoint(self, host: str, reason: str, ports: Optional[list[int]] = None) -> None:
        """Register a new allowed endpoint for 'controlled' mode."""
        ep = AllowedEndpoint(host=host, reason=reason, ports=ports)
        self.allowed_endpoints.append(ep)
        self._endpoint_map[host] = ep
        logger.info(f"[AirGap] Registered endpoint: {host} ({reason})")
    
    def get_status(self) -> dict[str, Any]:
        """Get policy status for debugging."""
        return {
            "mode": self.mode.value,
            "localhost_allowed": True,
            "lan_allowed": self.mode in (AirGapMode.AIRGAP_LAN, AirGapMode.CONTROLLED, AirGapMode.OPEN),
            "internet_allowed": self.mode == AirGapMode.OPEN,
            "allowed_endpoints": [
                {"host": ep.host, "reason": ep.reason, "ports": ep.ports}
                for ep in self.allowed_endpoints
            ],
        }


# Global singleton for app-wide use
_policy: Optional[AirGapPolicy] = None


def get_policy() -> AirGapPolicy:
    """Get the global air-gap policy instance."""
    global _policy
    if _policy is None:
        import os
        mode_str = os.getenv("FRANKLINOPS_AIRGAP_MODE", "open").strip().lower()
        try:
            mode = AirGapMode(mode_str)
        except ValueError:
            mode = AirGapMode.OPEN
        _policy = AirGapPolicy(mode=mode)
    return _policy


def set_policy(policy: AirGapPolicy) -> None:
    """Set the global air-gap policy (for testing or reconfiguration)."""
    global _policy
    _policy = policy
