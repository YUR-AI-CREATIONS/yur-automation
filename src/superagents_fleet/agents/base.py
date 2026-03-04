"""
Fleet Agent Base — Extends BaseAgent for construction/development domain.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from ..registry import AgentSpec

logger = logging.getLogger(__name__)


class FleetAgent:
    """
    Fleet agent for construction & development operations.

    Each agent has a spec (id, name, domain, capabilities) and implements
    execute_task and make_decision for its domain.
    """

    def __init__(self, spec: AgentSpec, autonomy_level: str = "semi-autonomous"):
        self.spec = spec
        self.autonomy_level = autonomy_level
        self.status = "idle"
        self.tasks_completed = 0
        self.context: dict[str, Any] = {}
        self._created_at = datetime.now(timezone.utc)

    @property
    def agent_id(self) -> str:
        return self.spec.id

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def domain(self) -> str:
        return self.spec.domain

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self.spec.capabilities

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a task in this agent's domain.

        Override in subclasses for domain-specific logic.
        """
        task_id = task.get("task_id", "unknown")
        task_type = task.get("type", "generic")

        logger.info(f"FleetAgent {self.agent_id} executing {task_id} ({task_type})")
        self.status = "executing"

        try:
            result = await self._handle_task(task)
            self.tasks_completed += 1
            self.status = "idle"
            return {
                "status": "success",
                "task_id": task_id,
                "agent_id": self.agent_id,
                "result": result,
            }
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self.status = "error"
            return {
                "status": "failed",
                "task_id": task_id,
                "agent_id": self.agent_id,
                "error": str(e),
            }

    async def _handle_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Override in subclasses. Default: acknowledge."""
        await asyncio.sleep(0.05)
        return {"acknowledged": True, "domain": self.domain}

    async def make_decision(self, context: dict[str, Any]) -> dict[str, Any]:
        """Make a decision in this agent's domain."""
        options = context.get("options", [])
        return {
            "decision": options[0] if options else None,
            "reasoning": f"Based on {self.domain} domain expertise",
            "confidence": "medium" if self.autonomy_level == "semi-autonomous" else "high",
            "agent_id": self.agent_id,
        }

    def get_info(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "domain": self.domain,
            "capabilities": list(self.capabilities),
            "phase": self.spec.phase,
            "status": self.status,
            "tasks_completed": self.tasks_completed,
            "autonomy_level": self.autonomy_level,
        }
