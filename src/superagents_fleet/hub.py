"""
FleetHub — Central orchestration for the superagents fleet.

- Routes tasks to the right agent (plugin or legacy)
- Each plugin agent has own API + database
- Learning stays local; private data never leaves
- Error handling, audit on success and failure
"""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .registry import AGENT_REGISTRY, get_agent_spec, list_agent_ids
from .agents.factory import create_fleet_agent
from .plugin.registry import PluginRegistry, BUILTIN_PLUGINS
from .plugin.privacy import PrivacyFilter

logger = logging.getLogger(__name__)

# Safe keys to pass from documents to tasks (no PII)
DOC_ROUTE_SAFE_KEYS = {"type", "id", "source", "doc_type", "invoice_id", "bid_id", "project_id"}


class FleetHub:
    """
    Central hub for the superagents fleet.

    Every task flows in → routed to agent(s) → results flow back → redistributed.
    Plugin agents have own API + DB. Private data stays local.
    """

    def __init__(
        self,
        db=None,
        audit=None,
        autonomy_level: str = "semi-autonomous",
        data_dir: Optional[Path] = None,
    ):
        self._db = db
        self._audit = audit
        self._autonomy_level = autonomy_level
        self._data_dir = Path(data_dir or "data/franklinops/fleet")
        self._plugin_registry = PluginRegistry(self._data_dir)
        self._plugins: dict[str, Any] = {}
        self._legacy_agents: dict[str, Any] = {}
        self._task_log: list[dict[str, Any]] = []
        self._privacy = PrivacyFilter()

    def get_agent(self, agent_id: str):
        """Get agent by ID. Prefer plugin; fall back to legacy."""
        if agent_id in BUILTIN_PLUGINS:
            if agent_id not in self._plugins:
                plugin = self._plugin_registry.get(agent_id)
                if plugin:
                    self._plugins[agent_id] = plugin
            if agent_id in self._plugins:
                return self._plugins[agent_id]
        if agent_id not in self._legacy_agents:
            agent = create_fleet_agent(agent_id, self._autonomy_level)
            if agent:
                self._legacy_agents[agent_id] = agent
        return self._legacy_agents.get(agent_id)

    def get_plugin(self, agent_id: str):
        """Get plugin agent only (for API mounting)."""
        return self._plugin_registry.get(agent_id)

    def list_agents(self, phase: Optional[str] = None) -> list[dict[str, Any]]:
        """List all agents, optionally by phase."""
        ids = list_agent_ids(phase)
        result = []
        for aid in ids:
            agent = self.get_agent(aid)
            if agent:
                info = agent.get_info() if hasattr(agent, "get_info") else {"agent_id": aid}
                result.append(info)
        return result

    def get_all_plugin_routers(self) -> list[tuple[str, Any]]:
        """Return (prefix, router) for mounting."""
        routers = []
        seen = set()
        for agent_id in BUILTIN_PLUGINS:
            plugin = self._plugin_registry.get(agent_id)
            if plugin and id(plugin) not in seen:
                seen.add(id(plugin))
                routers.append(("/api/fleet", plugin.get_router()))
        return routers

    def _sanitize_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize hub response before returning to API (remove PII)."""
        return self._privacy.sanitize(data)

    async def dispatch(
        self,
        agent_id: str,
        task: dict[str, Any],
        *,
        audit: bool = True,
        sanitize_response: bool = True,
    ) -> dict[str, Any]:
        """
        Dispatch task to agent. Log to audit. Catch errors, return structured result.
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return {"status": "failed", "error": f"Unknown agent: {agent_id}"}

        task_id = task.get("task_id") or f"task_{datetime.now(timezone.utc).timestamp()}"
        task_copy = copy.deepcopy(task)
        task_copy["task_id"] = task_id

        if audit and self._audit:
            self._audit.append(
                actor="fleet_hub",
                action="fleet_dispatch_start",
                details={
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "task_type": task_copy.get("type", "generic"),
                },
                entity_type="fleet_task",
                entity_id=task_id,
            )

        try:
            result = await agent.execute_task(task_copy)
            self._task_log.append({"task_id": task_id, "agent_id": agent_id, "result": result})

            if audit and self._audit:
                self._audit.append(
                    actor="fleet_hub",
                    action="fleet_dispatch_success",
                    details={"agent_id": agent_id, "task_id": task_id},
                    entity_type="fleet_task",
                    entity_id=task_id,
                )

            if sanitize_response:
                return self._sanitize_response(result)
            return result

        except Exception as e:
            logger.exception(f"Fleet dispatch failed: agent={agent_id} task_id={task_id}")

            if audit and self._audit:
                self._audit.append(
                    actor="fleet_hub",
                    action="fleet_dispatch_failed",
                    details={
                        "agent_id": agent_id,
                        "task_id": task_id,
                        "error": str(e),
                    },
                    entity_type="fleet_task",
                    entity_id=task_id,
                )

            return {"status": "failed", "task_id": task_id, "agent_id": agent_id, "error": str(e)}

    async def dispatch_multi(
        self,
        tasks: list[tuple[str, dict[str, Any]]],
        *,
        parallel: bool = True,
    ) -> list[dict[str, Any]]:
        """Dispatch multiple (agent_id, task) pairs."""
        if parallel:
            results = await asyncio.gather(
                *[self.dispatch(aid, t) for aid, t in tasks],
                return_exceptions=True,
            )
            return [
                r if isinstance(r, dict) else {"status": "failed", "error": str(r)}
                for r in results
            ]
        return [await self.dispatch(aid, t) for aid, t in tasks]

    def route_document(self, doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """
        Route a document to appropriate agents.
        Only safe keys are passed; PII is not forwarded.
        """
        doc_type = doc.get("type", "unknown")
        doc_id = doc.get("id", "unknown")

        safe = {k: v for k, v in doc.items() if k in DOC_ROUTE_SAFE_KEYS}
        safe.setdefault("type", doc_type)
        safe.setdefault("id", doc_id)

        tasks: list[tuple[str, dict[str, Any]]] = [
            ("file_keeper", {"task_id": f"ingest_{doc_id}", "type": "ingest", "doc_type": doc_type, "source": safe.get("source", "unknown")}),
        ]

        if doc_type in ("invoice", "ap", "ar"):
            tasks.append((
                "bookkeeper",
                {"task_id": f"invoice_{doc_id}", "type": "invoice_in", "invoice_id": doc_id, **safe},
            ))
        if doc_type in ("bid", "rfp"):
            tasks.append((
                "bid_scraping",
                {"task_id": f"bid_{doc_id}", "type": "log_bid_event", "bid_id": doc_id, **safe},
            ))
        if doc_type in ("project", "subcontract"):
            tasks.append((
                "project_manager",
                {"task_id": f"pm_{doc_id}", "type": "subcontractor_agreement", "doc_id": doc_id, **safe},
            ))

        return tasks

    def get_status(self) -> dict[str, Any]:
        """Get hub status."""
        return {
            "agents_loaded": len(set(self._plugins) | set(self._legacy_agents)),
            "plugins_loaded": len(set(self._plugins)),
            "agents_total": len(AGENT_REGISTRY),
            "tasks_dispatched": len(self._task_log),
            "phases": list(set(s.phase for s in AGENT_REGISTRY.values())),
            "data_dir": str(self._data_dir),
            "architecture": "plugin",
        }
