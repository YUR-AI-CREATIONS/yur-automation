"""
Plugin Registry — Discovers and loads agent plugins.

Supports:
- Built-in plugins (BUILTIN_PLUGINS)
- External plugins from FRANKLINOPS_FLEET_PLUGINS_DIR
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import re
import sys
from pathlib import Path
from threading import RLock
from typing import Any, Optional

from .interface import AgentPlugin, PluginConfig
from ..registry import AGENT_REGISTRY, get_agent_spec

logger = logging.getLogger(__name__)

# agent_id must be alphanumeric + underscore only
AGENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _env_plugins_dir() -> Optional[Path]:
    """Get external plugins directory from env. Validates path is safe."""
    raw = os.environ.get("FRANKLINOPS_FLEET_PLUGINS_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw).resolve()
    if not p.exists() or not p.is_dir():
        return None
    # Reject paths that could be sensitive (e.g. /etc, home dirs with secrets)
    try:
        p = p.resolve()
    except OSError:
        return None
    return p


def _validate_agent_id(agent_id: str) -> bool:
    """Validate agent_id format for safe use in module names and paths."""
    return bool(agent_id and AGENT_ID_PATTERN.match(agent_id))


def _validate_plugin_path(plugin_path: Path, allowed_base: Optional[Path] = None) -> bool:
    """Ensure plugin_path is within allowed base (no path traversal)."""
    try:
        resolved = plugin_path.resolve()
        if allowed_base:
            base = allowed_base.resolve()
            return str(resolved).startswith(str(base))
        return True
    except OSError:
        return False


# Built-in plugin modules (agent_id -> module path)
BUILTIN_PLUGINS: dict[str, str] = {
    "land_feasibility": "src.superagents_fleet.plugins.land_feasibility",
    "civil_land_planning": "src.superagents_fleet.plugins.land_feasibility",
    "market_study": "src.superagents_fleet.plugins.land_feasibility",
    "master_feasibility": "src.superagents_fleet.plugins.land_feasibility",
    "roadmap_10yr": "src.superagents_fleet.plugins.land_feasibility",
    "bid_scraping": "src.superagents_fleet.plugins.bid_scraping",
    "financial_analyst": "src.superagents_fleet.plugins.financial_analyst",
    "bookkeeper": "src.superagents_fleet.plugins.bookkeeper",
    "ar_ap_outreach": "src.superagents_fleet.plugins.bookkeeper",
    "file_keeper": "src.superagents_fleet.plugins.file_keeper",
    "project_manager": "src.superagents_fleet.plugins.project_manager",
    "subcontractor_scoring": "src.superagents_fleet.plugins.project_manager",
    "logistics_fleet": "src.superagents_fleet.plugins.logistics_fleet",
    "heavy_equipment": "src.superagents_fleet.plugins.logistics_fleet",
    "concrete_dispatch": "src.superagents_fleet.plugins.logistics_fleet",
    "social_marketing": "src.superagents_fleet.plugins.social_marketing",
    "branding_integrity": "src.superagents_fleet.plugins.social_marketing",
    "warm_outreach": "src.superagents_fleet.plugins.social_marketing",
    "internal_audit": "src.superagents_fleet.plugins.internal_audit",
    "insurance_bonding": "src.superagents_fleet.plugins.internal_audit",
}


class PluginRegistry:
    """
    Registry of loaded agent plugins. Thread-safe.
    """

    def __init__(self, data_dir: Path):
        self._data_dir = Path(data_dir)
        self._plugins: dict[str, AgentPlugin] = {}
        self._loaded: set[str] = set()
        self._lock = RLock()

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def load(self, agent_id: str, module_path: Optional[str] = None) -> Optional[AgentPlugin]:
        """Load a plugin by agent_id. Uses BUILTIN_PLUGINS if module_path not given."""
        if not _validate_agent_id(agent_id):
            logger.warning(f"Invalid agent_id format: {agent_id}")
            return None

        with self._lock:
            if agent_id in self._plugins:
                return self._plugins[agent_id]

            path = module_path or BUILTIN_PLUGINS.get(agent_id)
            if not path:
                logger.warning(f"No plugin path for agent {agent_id}")
                return None

            spec = get_agent_spec(agent_id)
            if not spec:
                logger.warning(f"No spec for agent {agent_id}")
                return None

            try:
                mod = importlib.import_module(path)
                plugin_class = getattr(mod, "Plugin", None)
                if not plugin_class or not issubclass(plugin_class, AgentPlugin):
                    logger.warning(f"Module {path} has no AgentPlugin subclass 'Plugin'")
                    return None

                config = PluginConfig(
                    agent_id=spec.id,
                    name=spec.name,
                    domain=spec.domain,
                    phase=spec.phase,
                    data_dir=self._data_dir / "agents",
                    capabilities=spec.capabilities,
                    description=spec.description,
                )
                plugin = plugin_class(config)
                plugin.init_db()
                self._plugins[agent_id] = plugin
                self._loaded.add(agent_id)
                logger.info(f"Loaded plugin: {agent_id}")
                return plugin
            except Exception as e:
                logger.exception(f"Failed to load plugin {agent_id}: {e}")
                return None

    def get(self, agent_id: str) -> Optional[AgentPlugin]:
        """Get loaded plugin. Loads on first access if in BUILTIN_PLUGINS."""
        if not _validate_agent_id(agent_id):
            return None
        with self._lock:
            if agent_id not in self._plugins and agent_id in BUILTIN_PLUGINS:
                self.load(agent_id)
            return self._plugins.get(agent_id)

    def list_loaded(self) -> list[str]:
        with self._lock:
            return list(self._loaded)

    def load_all_builtin(self) -> int:
        """Load all built-in plugins. Returns count loaded."""
        count = 0
        for agent_id in BUILTIN_PLUGINS:
            if self.load(agent_id):
                count += 1
        return count

    def load_external(self, plugin_path: Path, agent_id: str) -> Optional[AgentPlugin]:
        """
        Load plugin from external path. Validates path and agent_id.
        """
        if not _validate_agent_id(agent_id):
            logger.warning(f"Invalid agent_id for external plugin: {agent_id}")
            return None

        allowed_base = _env_plugins_dir()
        if allowed_base and not _validate_plugin_path(plugin_path, allowed_base):
            logger.warning(f"Plugin path outside allowed dir: {plugin_path}")
            return None

        with self._lock:
            for name in ("plugin", "__init__"):
                mod_file = plugin_path / f"{name}.py"
                if not mod_file.exists():
                    continue
                try:
                    spec = get_agent_spec(agent_id)
                    module_name = f"fleet_plugin_{agent_id}".replace("-", "_")
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                    spec_load = importlib.util.spec_from_file_location(module_name, mod_file)
                    if not spec_load or not spec_load.loader:
                        continue
                    mod = importlib.util.module_from_spec(spec_load)
                    sys.modules[module_name] = mod
                    spec_load.loader.exec_module(mod)
                    plugin_class = getattr(mod, "Plugin", None)
                    if not plugin_class or not issubclass(plugin_class, AgentPlugin):
                        continue
                    config = PluginConfig(
                        agent_id=spec.id if spec else agent_id,
                        name=spec.name if spec else agent_id.replace("_", " ").title(),
                        domain=spec.domain if spec else "custom",
                        phase=spec.phase if spec else "ops",
                        data_dir=self._data_dir / "agents",
                        capabilities=tuple(spec.capabilities) if spec else (),
                        description=spec.description if spec else "",
                    )
                    plugin = plugin_class(config)
                    plugin.init_db()
                    self._plugins[agent_id] = plugin
                    self._loaded.add(agent_id)
                    logger.info(f"Loaded external plugin: {agent_id} from {plugin_path}")
                    return plugin
                except Exception as e:
                    logger.exception(f"Failed to load external plugin {plugin_path}: {e}")
                    continue
        return None

    def discover_external_plugins(self) -> list[str]:
        """Discover agent IDs from external plugins dir."""
        plugins_dir = _env_plugins_dir()
        if not plugins_dir:
            return []
        found = []
        for sub in plugins_dir.iterdir():
            if sub.is_dir() and ((sub / "plugin.py").exists() or (sub / "__init__.py").exists()):
                if _validate_agent_id(sub.name):
                    found.append(sub.name)
        return found


def discover_plugins(plugins_dir: Path) -> list[str]:
    """Discover plugin modules in a directory."""
    found: list[str] = []
    if not plugins_dir.exists():
        return found
    for sub in plugins_dir.iterdir():
        if sub.is_dir():
            for name in ("plugin", "__init__"):
                if (sub / f"{name}.py").exists():
                    found.append(sub.name)
                    break
    return found


def load_plugin(agent_id: str, data_dir: Path, module_path: Optional[str] = None) -> Optional[AgentPlugin]:
    """Convenience: load a single plugin."""
    reg = PluginRegistry(data_dir)
    return reg.load(agent_id, module_path)
