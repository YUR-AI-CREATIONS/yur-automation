"""
Development Intelligence flows — Monte Carlo + Policy + Full Pipeline.

Plug into FranklinOps flow interface. Used by DAG and policy-driven runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..simulation.monte_carlo import simulate_roi
from ..policy.engine import PolicyEngine
from ..pipeline.land_deal import run_land_deal_pipeline


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def monte_carlo_flow(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Monte Carlo underwriting flow. Returns roi_mean, p_roi_ge_target, p_loss, etc.
    """
    try:
        n = int(inp.get("n_runs", 10000))
        capital = _safe_float(inp.get("capital_deployed"), 80_000_000)
        base_profit = _safe_float(inp.get("base_profit"), 12_000_000)
        target_roi = _safe_float(inp.get("target_roi"), 0.18)
        out = simulate_roi(
            n=n,
            base_profit=base_profit,
            capital_deployed=capital,
            target_roi=target_roi,
        )
        out["flow_id"] = "monte_carlo"
        return out
    except Exception as e:
        return {"ok": False, "flow_id": "monte_carlo", "error": str(e)}


def policy_evaluate_flow(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Policy engine evaluate deal. Returns action (approve/deny/escalate), reason, next.
    """
    try:
        policy_path = inp.get("policy_path") or "policies/deal_policy.yaml"
        path = Path(policy_path)
        if not path.exists():
            path = Path(__file__).resolve().parents[2] / "policies" / "deal_policy.yaml"
        engine = PolicyEngine(path)
        metrics = inp.get("metrics", inp)
        decision = engine.evaluate_deal(metrics)
        return {
            "ok": True,
            "flow_id": "policy_evaluate",
            "decision": decision,
            "action": decision["action"],
            "reason": decision["reason"],
            "next": decision["next"],
        }
    except Exception as e:
        return {"ok": False, "flow_id": "policy_evaluate", "error": str(e)}


def development_pipeline_flow(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Full land deal pipeline: parcel → zoning → cost → simulation → policy → opportunity.

    Input: parcel_id, lat, lon, acres, (optional) trace_id, tenant_id
    Output: trace_id, zoning, cost, simulation, policy_decision, opportunity
    """
    try:
        parcel = {
            "parcel_id": inp.get("parcel_id", "unknown"),
            "lat": inp.get("lat"),
            "lon": inp.get("lon"),
            "acres": inp.get("acres", 10.0),
            "base_profit": inp.get("base_profit", 12_000_000),
        }
        trace_id = inp.get("trace_id")
        tenant_id = inp.get("tenant_id", "default")
        out = run_land_deal_pipeline(parcel, trace_id=trace_id, tenant_id=tenant_id)
        out["flow_id"] = "development_pipeline"
        return out
    except Exception as e:
        return {"ok": False, "flow_id": "development_pipeline", "error": str(e)}
