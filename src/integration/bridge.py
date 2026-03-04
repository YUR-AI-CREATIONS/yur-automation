"""
Integration Bridge — Connects GROKSTMATE to FranklinOps Hub.

Provides unified access to:
- GROKSTMATE CostEstimator, ProjectManager, TaskAgent, BotDeploymentManager
- FranklinOps OpsDB, AuditLogger, ApprovalService
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from grokstmate import CostEstimator, ProjectManager
    from grokstmate.agents.task_agent import TaskAgent
    from grokstmate.bot_deployment.bot_manager import BotDeploymentManager, BotType

    GROKSTMATE_AVAILABLE = True
except ImportError:
    GROKSTMATE_AVAILABLE = False
    CostEstimator = None
    ProjectManager = None
    TaskAgent = None
    BotDeploymentManager = None
    BotType = None


class IntegrationBridge:
    """
    Bridge between GROKSTMATE autonomous agents and FranklinOps business automation.
    """

    def __init__(
        self,
        db=None,
        audit=None,
        approvals=None,
    ):
        self._db = db
        self._audit = audit
        self._approvals = approvals
        self._estimator: Optional[Any] = None
        self._bot_manager: Optional[Any] = None

    @property
    def available(self) -> bool:
        return GROKSTMATE_AVAILABLE

    def get_cost_estimator(self, region: str = "US", currency: str = "USD") -> Any:
        """Get GROKSTMATE CostEstimator instance."""
        if not GROKSTMATE_AVAILABLE:
            raise RuntimeError("GROKSTMATE not installed. Run: pip install -e GROKSTMATE")
        return CostEstimator(region=region, currency=currency)

    def get_project_manager(self, project_id: str, project_name: str) -> Any:
        """Get GROKSTMATE ProjectManager instance."""
        if not GROKSTMATE_AVAILABLE:
            raise RuntimeError("GROKSTMATE not installed. Run: pip install -e GROKSTMATE")
        return ProjectManager(project_id, project_name)

    def create_task_agent(
        self,
        agent_id: str,
        name: str,
        domain: str = "construction",
        capabilities: Optional[list[str]] = None,
        autonomy_level: str = "fully-autonomous",
    ) -> Any:
        """Create GROKSTMATE TaskAgent."""
        if not GROKSTMATE_AVAILABLE:
            raise RuntimeError("GROKSTMATE not installed. Run: pip install -e GROKSTMATE")
        caps = capabilities or ["estimation", "project_management", "autonomous_decision"]
        return TaskAgent(
            agent_id=agent_id,
            name=name,
            domain=domain,
            capabilities=caps,
            autonomy_level=autonomy_level,
        )

    def get_bot_manager(self) -> Any:
        """Get GROKSTMATE BotDeploymentManager (singleton)."""
        if not GROKSTMATE_AVAILABLE:
            raise RuntimeError("GROKSTMATE not installed. Run: pip install -e GROKSTMATE")
        if self._bot_manager is None:
            self._bot_manager = BotDeploymentManager()
        return self._bot_manager

    def estimate_project(self, project_spec: dict[str, Any]) -> dict[str, Any]:
        """Run cost estimation via GROKSTMATE."""
        estimator = self.get_cost_estimator()
        return estimator.estimate_project(project_spec)

    def create_project_plan(
        self,
        project_id: str,
        project_name: str,
        project_spec: dict[str, Any],
    ) -> dict[str, Any]:
        """Create project plan via GROKSTMATE."""
        pm = self.get_project_manager(project_id, project_name)
        return pm.create_project_plan(project_spec)
