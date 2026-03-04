"""
Unified Orchestrator — Runs GROKSTMATE alongside FranklinOps pilot.

Extends the pilot run with optional GROKSTMATE phase:
- Cost estimation for active opportunities
- Project plan creation
- Bot deployment (shadow mode by default)
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from .bridge import IntegrationBridge, GROKSTMATE_AVAILABLE
from .governance_adapter import GovernanceAdapter


def run_grokstmate_phase(
    db=None,
    audit=None,
    approvals=None,
    *,
    estimate_opportunities: bool = True,
    deploy_bots: bool = False,
    bot_count: int = 0,
) -> dict[str, Any]:
    """
    Run GROKSTMATE phase as part of unified pilot.

    Returns dict with grokstmate_estimate, grokstmate_plans, grokstmate_bots.
    """
    results: dict[str, Any] = {
        "available": GROKSTMATE_AVAILABLE,
        "grokstmate_estimate": None,
        "grokstmate_plans": [],
        "grokstmate_bots": [],
    }
    if not GROKSTMATE_AVAILABLE:
        results["skipped"] = "GROKSTMATE not installed"
        return results

    bridge = IntegrationBridge(db=db, audit=audit, approvals=approvals)
    adapter = GovernanceAdapter(bridge, audit=audit, approvals=approvals)

    # Demo estimate (in production, would use real opportunities from OpsDB)
    if estimate_opportunities:
        try:
            est = adapter.estimate_project(
                {
                    "name": "Pilot Estimate",
                    "type": "commercial",
                    "size": 5000,
                    "complexity": "moderate",
                },
                actor="unified_orchestrator",
            )
            results["grokstmate_estimate"] = {
                "total_estimate": est.get("total_estimate"),
                "project_name": est.get("project_name"),
            }
        except Exception as e:
            results["grokstmate_estimate"] = {"error": str(e)}

    # Deploy bots only if explicitly requested (shadow/assist by default)
    if deploy_bots and bot_count > 0:
        try:
            bot_ids = asyncio.run(
                adapter.deploy_bots(
                    "construction_bot",
                    count=bot_count,
                    actor="unified_orchestrator",
                )
            )
            results["grokstmate_bots"] = bot_ids
        except Exception as e:
            results["grokstmate_bots"] = {"error": str(e)}

    return results
