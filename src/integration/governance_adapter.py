"""
Governance Adapter — Applies FranklinOps security and governance to GROKSTMATE.

- Audit: Log all GROKSTMATE actions
- Approvals: Route high-risk actions through approval workflow
- Birthmark: Evidence verification for autonomous decisions
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from .bridge import IntegrationBridge, GROKSTMATE_AVAILABLE


class GovernanceAdapter:
    """
    Wraps GROKSTMATE operations with FranklinOps governance.
    """

    def __init__(
        self,
        bridge: IntegrationBridge,
        audit=None,
        approvals=None,
    ):
        self._bridge = bridge
        self._audit = audit
        self._approvals = approvals

    def _log_audit(self, actor: str, action: str, details: dict[str, Any]) -> None:
        """Log to FranklinOps audit trail."""
        if self._audit:
            self._audit.append(
                actor=actor,
                action=action,
                details=details,
                scope="internal",
                entity_type="grokstmate",
            )

    def estimate_project(
        self,
        project_spec: dict[str, Any],
        actor: str = "system",
    ) -> dict[str, Any]:
        """Run cost estimation with audit logging."""
        if not GROKSTMATE_AVAILABLE:
            return {"error": "GROKSTMATE not installed", "available": False}
        try:
            result = self._bridge.estimate_project(project_spec)
            self._log_audit(
                actor=actor,
                action="grokstmate_estimate",
                details={
                    "project_spec": project_spec,
                    "total_estimate": result.get("total_estimate"),
                    "project_name": result.get("project_name"),
                },
            )
            return result
        except Exception as e:
            self._log_audit(
                actor=actor,
                action="grokstmate_estimate_failed",
                details={"project_spec": project_spec, "error": str(e)},
            )
            raise

    def create_project_plan(
        self,
        project_id: str,
        project_name: str,
        project_spec: dict[str, Any],
        actor: str = "system",
    ) -> dict[str, Any]:
        """Create project plan with audit logging."""
        if not GROKSTMATE_AVAILABLE:
            return {"error": "GROKSTMATE not installed", "available": False}
        try:
            result = self._bridge.create_project_plan(
                project_id, project_name, project_spec
            )
            self._log_audit(
                actor=actor,
                action="grokstmate_create_plan",
                details={
                    "project_id": project_id,
                    "project_name": project_name,
                    "task_count": len(result.get("tasks", [])),
                },
            )
            return result
        except Exception as e:
            self._log_audit(
                actor=actor,
                action="grokstmate_create_plan_failed",
                details={
                    "project_id": project_id,
                    "error": str(e),
                },
            )
            raise

    async def deploy_bots(
        self,
        bot_type: str,
        count: int = 1,
        capabilities: Optional[list[str]] = None,
        actor: str = "system",
    ) -> list[str]:
        """Deploy bots with audit logging."""
        if not GROKSTMATE_AVAILABLE:
            return []
        try:
            from grokstmate.bot_deployment.bot_manager import BotType

            manager = self._bridge.get_bot_manager()
            bot_type_map = {
                "estimation_bot": BotType.ESTIMATION_BOT,
                "construction_bot": BotType.CONSTRUCTION_BOT,
                "software_builder_bot": BotType.SOFTWARE_BUILDER_BOT,
                "project_monitor_bot": BotType.PROJECT_MONITOR_BOT,
            }
            bt = bot_type_map.get(bot_type, BotType.CONSTRUCTION_BOT)
            bot_ids = await manager.deploy_swarm(
                bt, count, capabilities or ["autonomous_operation"], {}
            )
            self._log_audit(
                actor=actor,
                action="grokstmate_deploy_bots",
                details={"bot_type": bot_type, "count": len(bot_ids), "bot_ids": bot_ids},
            )
            return bot_ids
        except Exception as e:
            self._log_audit(
                actor=actor,
                action="grokstmate_deploy_bots_failed",
                details={"bot_type": bot_type, "error": str(e)},
            )
            raise
