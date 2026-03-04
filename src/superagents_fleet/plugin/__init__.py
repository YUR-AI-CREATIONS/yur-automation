"""
Agent Plugin System — Scalable, pluggable agents with own API + database.

Each agent plugin:
- Has its own API (FastAPI router)
- Has its own database (SQLite, isolated)
- Learns from operations (local only)
- Enforces privacy: private data never leaves local
"""

from .interface import AgentPlugin, PluginConfig
from .registry import PluginRegistry, discover_plugins, load_plugin
from .privacy import PrivacyFilter, PRIVATE_FIELD_PATTERNS

__all__ = [
    "AgentPlugin",
    "PluginConfig",
    "PluginRegistry",
    "discover_plugins",
    "load_plugin",
    "PrivacyFilter",
    "PRIVATE_FIELD_PATTERNS",
]
