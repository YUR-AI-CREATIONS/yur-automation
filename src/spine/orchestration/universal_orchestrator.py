"""
Universal Orchestrator — Domain-agnostic task orchestration.

Executes flows and DAGs. Integrates with flow registry and hardening.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from src.core.flow_hardening import execute_flow_hardened
from src.core.flow_interface import FlowResult, FlowSpec
from src.orchestrator.dag import DAG

from .flow_registry import UniversalFlowRegistry

logger = logging.getLogger(__name__)

__all__ = ["UniversalOrchestrator", "OrchestratorConfig"]


@dataclass
class OrchestratorConfig:
    """Orchestrator configuration."""

    tenant_id: str = "default"
    audit_fn: Optional[Callable[[str, str, dict, dict, float, bool], None]] = None
    use_hardening: bool = True


class UniversalOrchestrator:
    """
    Domain-agnostic task orchestrator.
    Invokes flows via registry with optional hardening and audit.
    """

    def __init__(
        self,
        registry: UniversalFlowRegistry,
        config: Optional[OrchestratorConfig] = None,
    ) -> None:
        self._registry = registry
        self._config = config or OrchestratorConfig()

    def invoke(
        self,
        flow_id: str,
        inp: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> FlowResult:
        """
        Invoke a flow by id. Uses hardening when enabled.
        """
        entry = self._registry.get(flow_id)
        if not entry:
            return FlowResult(
                ok=False,
                error=f"Flow not found: {flow_id}",
                flow_id=flow_id,
            )

        spec, handler = entry
        tid = tenant_id or self._config.tenant_id

        def run(payload: dict[str, Any]) -> dict[str, Any]:
            return handler.process(payload)

        if self._config.use_hardening:
            return execute_flow_hardened(
                flow_id=flow_id,
                spec=spec,
                handler_fn=run,
                inp=inp,
                tenant_id=tid,
                audit_fn=self._config.audit_fn,
            )

        # No hardening: direct invoke
        try:
            out = run(inp or {})
            return FlowResult(
                ok=True,
                out=out if isinstance(out, dict) else {"result": out},
                flow_id=flow_id,
            )
        except Exception as e:
            logger.exception("Flow %s failed: %s", flow_id, e)
            return FlowResult(ok=False, error=str(e), flow_id=flow_id)

    def run_dag(self, dag: DAG, ctx: dict[str, Any]) -> dict[str, Any]:
        """Execute a DAG with the given context."""
        return dag.run(ctx)

    def create_dag(self) -> DAG:
        """Create a new DAG for workflow composition."""
        return DAG()
