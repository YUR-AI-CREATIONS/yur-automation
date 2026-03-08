"""
Selective Sync — Controlled external connections.

Manages whitelist/blacklist for external API endpoints and data sources.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["SyncRule", "SelectiveSync"]


@dataclass
class SyncRule:
    """Rule for selective data synchronization."""

    name: str
    source_url: str
    direction: str
    enabled: bool = True
    frequency_minutes: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)


class SelectiveSync:
    """
    Manages controlled external connections.

    Maintains whitelist of allowed external endpoints and controls
    when/how data synchronization happens.
    """

    def __init__(self) -> None:
        self.sync_rules: dict[str, SyncRule] = {}
        self.whitelisted_domains: set[str] = set()
        self.blacklisted_domains: set[str] = set()
        self.default_policy = "DENY"  # DENY or ALLOW

    def register_sync_rule(self, rule: SyncRule) -> None:
        """Register a synchronization rule."""
        self.sync_rules[rule.name] = rule
        logger.info(f"Registered sync rule: {rule.name}")

    def enable_sync_rule(self, rule_name: str) -> bool:
        """Enable a sync rule."""
        if rule_name in self.sync_rules:
            self.sync_rules[rule_name].enabled = True
            logger.info(f"Enabled sync rule: {rule_name}")
            return True
        return False

    def disable_sync_rule(self, rule_name: str) -> bool:
        """Disable a sync rule."""
        if rule_name in self.sync_rules:
            self.sync_rules[rule_name].enabled = False
            logger.info(f"Disabled sync rule: {rule_name}")
            return True
        return False

    def whitelist_domain(self, domain: str) -> None:
        """Add domain to whitelist."""
        self.whitelisted_domains.add(domain)
        self.blacklisted_domains.discard(domain)
        logger.debug(f"Whitelisted domain: {domain}")

    def blacklist_domain(self, domain: str) -> None:
        """Add domain to blacklist."""
        self.blacklisted_domains.add(domain)
        self.whitelisted_domains.discard(domain)
        logger.debug(f"Blacklisted domain: {domain}")

    def is_connection_allowed(self, url: str) -> bool:
        """Check if connection to URL is allowed."""
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check blacklist first
            if domain in self.blacklisted_domains:
                logger.warning(f"Connection blocked by blacklist: {domain}")
                return False

            # Check whitelist if policy is DENY
            if self.default_policy == "DENY":
                if domain not in self.whitelisted_domains:
                    logger.warning(f"Connection denied by policy: {domain}")
                    return False

            return True
        except Exception as e:
            logger.error(f"Failed to parse URL: {e}")
            return False

    def get_enabled_sync_rules(self) -> list[SyncRule]:
        """Get list of enabled sync rules."""
        return [r for r in self.sync_rules.values() if r.enabled]

    def get_status(self) -> dict[str, Any]:
        """Get selective sync status."""
        return {
            "default_policy": self.default_policy,
            "whitelisted_domains": list(self.whitelisted_domains),
            "blacklisted_domains": list(self.blacklisted_domains),
            "sync_rules": {
                name: {
                    "enabled": rule.enabled,
                    "source_url": rule.source_url,
                    "frequency_minutes": rule.frequency_minutes,
                }
                for name, rule in self.sync_rules.items()
            },
        }
