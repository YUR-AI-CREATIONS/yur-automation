"""
Land Deal Pipeline — concrete DAG execution.

parcel_input → zoning → infrastructure → market_demand → cost → simulation → policy → opportunity_ranked

Every step: emit event to bus, pass ctx to next. trace_id links causality.
Infrastructure and market_demand use Data Fabric features when available.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from ..bus import create_event, get_bus
from ..orchestrator.dag import DAG
from ..simulation.monte_carlo import simulate_roi
from ..policy.engine import PolicyEngine

_LOG = logging.getLogger("pipeline.land_deal")

FABRIC_FEATURES = Path(__file__).resolve().parents[2] / "data" / "fabric" / "features"
LAND_COST_PER_ACRE = float(os.getenv("FRANKLINOPS_LAND_COST_PER_ACRE", "50000"))
BUILD_COST_PER_SF = float(os.getenv("FRANKLINOPS_BUILD_COST_PER_SF", "80"))
COVERAGE_RATIO = float(os.getenv("FRANKLINOPS_COVERAGE_RATIO", "0.3"))


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_land_deal_dag(
    trace_id: str | None = None,
    tenant_id: str = "default",
    policy_path: str | Path | None = None,
) -> DAG:
    """Build the land deal DAG. Each node emits event + updates ctx."""

    tid = trace_id or str(uuid.uuid4())
    bus = get_bus()
    policy_path = policy_path or Path(__file__).resolve().parents[2] / "policies" / "deal_policy.yaml"

    dag = DAG()

    def zoning_assess(ctx: dict[str, Any]) -> dict[str, Any]:
        parcel_id = ctx.get("parcel_id", "unknown")
        acres = _safe_float(ctx.get("acres"), 10.0)
        zoning = {"compatible": True, "use": "residential", "density": "4 du/acre"}
        ctx["zoning"] = zoning
        ev = create_event("zoning.assessed", "zoning_agent", {"parcel_id": parcel_id, "zoning": zoning}, trace_id=tid, tenant_id=tenant_id)
        bus.publish("zoning.assessed", ev)
        return ctx

    def _load_economic_fabric(region_id: str) -> dict[str, Any] | None:
        """Load from Economic Fabric when available."""
        try:
            from ..economic_fabric import get_economic_index
            econ = get_economic_index(region_id, use_connectors=False, use_fabric=True)
            if econ.source == "economic_fabric" or econ.growth_index > 0:
                return {
                    "absorption_months": econ.absorption_months,
                    "demand_index": econ.demand_index,
                    "price_sensitivity": 0.3,
                    "source": "economic_fabric",
                    "utilities_available": True,
                    "road_access": "primary",
                    "transit_miles": 2.5,
                    "water_sewer": True,
                    "score": 0.85 + econ.growth_index * 0.15,
                }
        except Exception as e:
            _LOG.debug("economic fabric load %s: %s", region_id, e)
        return None

    def _load_fabric_features(dataset: str, region_id: str | None = None) -> list[dict[str, Any]]:
        """Load features from Data Fabric when available. Returns [] if not found."""
        try:
            ds_dir = FABRIC_FEATURES / dataset
            if not ds_dir.exists():
                return []
            files = sorted(ds_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for fp in files[:3]:
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    rows = data if isinstance(data, list) else [data]
                    if region_id and isinstance(rows, list):
                        for r in rows:
                            if isinstance(r, dict) and r.get("region_id") == region_id:
                                return [r]
                    return rows if isinstance(rows, list) else [rows]
                except (json.JSONDecodeError, OSError) as e:
                    _LOG.debug("fabric feature load %s: %s", fp.name, e)
            return []
        except Exception as e:
            _LOG.debug("fabric load %s: %s", dataset, e)
            return []

    def infrastructure_proximity(ctx: dict[str, Any]) -> dict[str, Any]:
        """Assess utilities, roads, transit. Uses Economic Fabric + Data Fabric when available."""
        parcel_id = ctx.get("parcel_id", "unknown")
        region_id = ctx.get("region_id")
        econ = _load_economic_fabric(region_id or parcel_id) if (region_id or parcel_id) else None
        if econ:
            ctx["infrastructure"] = {
                "utilities_available": econ.get("utilities_available", True),
                "road_access": econ.get("road_access", "primary"),
                "transit_miles": _safe_float(econ.get("transit_miles"), 2.5),
                "water_sewer": econ.get("water_sewer", True),
                "score": _safe_float(econ.get("score"), 0.85),
                "source": "economic_fabric",
            }
            return ctx
        features = _load_fabric_features("infrastructure", region_id)
        if features and isinstance(features[0], dict):
            f = features[0]
            infra = {
                "utilities_available": f.get("utilities_available", True),
                "road_access": f.get("road_access", "primary"),
                "transit_miles": _safe_float(f.get("transit_miles"), 2.5),
                "water_sewer": f.get("water_sewer", True),
                "score": _safe_float(f.get("score"), 0.85),
                "source": "data_fabric",
            }
        else:
            infra = {
                "utilities_available": True,
                "road_access": "primary",
                "transit_miles": 2.5,
                "water_sewer": True,
                "score": 0.85,
                "source": "default",
            }
        ctx["infrastructure"] = infra
        return ctx

    def market_demand(ctx: dict[str, Any]) -> dict[str, Any]:
        """Model absorption, demand. Uses Economic Fabric + Data Fabric when available."""
        region_id = ctx.get("region_id")
        parcel_id = ctx.get("parcel_id", "unknown")
        econ = _load_economic_fabric(region_id or parcel_id) if (region_id or parcel_id) else None
        if econ:
            ctx["market_demand"] = {
                "absorption_months": _safe_float(econ.get("absorption_months"), 14.0),
                "demand_index": _safe_float(econ.get("demand_index"), 0.78),
                "price_sensitivity": 0.3,
                "source": "economic_fabric",
            }
            return ctx
        features = _load_fabric_features("market_demand", region_id)
        if features and isinstance(features[0], dict):
            f = features[0]
            demand = {
                "absorption_months": _safe_float(f.get("absorption_months"), 14.0),
                "demand_index": _safe_float(f.get("demand_index"), 0.78),
                "price_sensitivity": _safe_float(f.get("price_sensitivity"), 0.3),
                "source": "data_fabric",
            }
        else:
            demand = {
                "absorption_months": 14.0,
                "demand_index": 0.78,
                "price_sensitivity": 0.3,
                "source": "default",
            }
        ctx["market_demand"] = demand
        return ctx

    def cost_estimate(ctx: dict[str, Any]) -> dict[str, Any]:
        acres = _safe_float(ctx.get("acres"), 10.0)
        infra = ctx.get("infrastructure", {})
        infra_score = _safe_float(infra.get("score"), 0.85)
        land_cost = acres * LAND_COST_PER_ACRE * (1.1 - infra_score * 0.2)
        build_sf = acres * 43_560 * COVERAGE_RATIO
        build_cost = build_sf * BUILD_COST_PER_SF
        total_cost = land_cost + build_cost
        ctx["cost"] = {"land_cost": land_cost, "build_cost": build_cost, "total_cost": total_cost, "capital_required": total_cost}
        ev = create_event("cost.estimated", "cost_engine", ctx["cost"], trace_id=tid, tenant_id=tenant_id)
        bus.publish("cost.estimated", ev)
        return ctx

    def roi_simulate(ctx: dict[str, Any]) -> dict[str, Any]:
        capital = ctx.get("cost", {}).get("capital_required", 80_000_000)
        base_profit = _safe_float(ctx.get("base_profit"), 12_000_000)
        demand = ctx.get("market_demand", {})
        absorption = _safe_float(demand.get("absorption_months"), 14.0)
        sim = simulate_roi(n=5000, capital_deployed=capital, base_profit=base_profit, absorption_mu=absorption)
        ctx["simulation"] = sim
        ev = create_event("roi.simulated", "simulation_engine", sim, trace_id=tid, tenant_id=tenant_id)
        bus.publish("roi.simulated", ev)
        return ctx

    def policy_evaluate(ctx: dict[str, Any]) -> dict[str, Any]:
        sim = ctx.get("simulation", {})
        cost = ctx.get("cost", {})
        metrics = {
            "roi_mean": sim.get("roi_mean", 0),
            "p_loss": sim.get("p_loss", 0),
            "p_roi_ge_target": sim.get("p_roi_ge_target", 0),
            "capital_required": cost.get("capital_required", 0),
        }
        engine = PolicyEngine(policy_path)
        decision = engine.evaluate_deal(metrics)
        ctx["policy_decision"] = decision
        return ctx

    def opportunity_rank(ctx: dict[str, Any]) -> dict[str, Any]:
        sim = ctx.get("simulation", {})
        cost = ctx.get("cost", {})
        decision = ctx.get("policy_decision", {})
        rank = {
            "roi_mean": sim.get("roi_mean"),
            "p_roi_ge_target": sim.get("p_roi_ge_target"),
            "p_loss": sim.get("p_loss"),
            "capital_required": cost.get("capital_required"),
            "action": decision.get("action"),
            "reason": decision.get("reason"),
            "next": decision.get("next"),
        }
        ctx["opportunity"] = rank
        ev = create_event("opportunity.ranked", "ranker", rank, trace_id=tid, tenant_id=tenant_id)
        bus.publish("opportunity.ranked", ev)
        return ctx

    dag.add_node("zoning_assess", zoning_assess)
    dag.add_node("infrastructure_proximity", infrastructure_proximity)
    dag.add_node("market_demand", market_demand)
    dag.add_node("cost_estimate", cost_estimate)
    dag.add_node("roi_simulate", roi_simulate)
    dag.add_node("policy_evaluate", policy_evaluate)
    dag.add_node("opportunity_rank", opportunity_rank)
    dag.add_edge("zoning_assess", "infrastructure_proximity")
    dag.add_edge("infrastructure_proximity", "market_demand")
    dag.add_edge("market_demand", "cost_estimate")
    dag.add_edge("cost_estimate", "roi_simulate")
    dag.add_edge("roi_simulate", "policy_evaluate")
    dag.add_edge("policy_evaluate", "opportunity_rank")

    return dag


def run_land_deal_pipeline(
    parcel: dict[str, Any],
    *,
    trace_id: str | None = None,
    tenant_id: str = "default",
) -> dict[str, Any]:
    """
    Run full land deal pipeline. Returns opportunity + policy decision + trace_id.
    """
    tid = trace_id or str(uuid.uuid4())
    bus = get_bus()

    # Emit parcel.discovered
    ev = create_event("parcel.discovered", "land_agent", parcel, trace_id=tid, tenant_id=tenant_id)
    bus.publish("parcel.discovered", ev)

    ctx = dict(parcel)
    dag = build_land_deal_dag(trace_id=tid, tenant_id=tenant_id)
    ctx = dag.run(ctx)

    return {
        "ok": True,
        "trace_id": tid,
        "tenant_id": tenant_id,
        "parcel": parcel,
        "zoning": ctx.get("zoning"),
        "infrastructure": ctx.get("infrastructure"),
        "market_demand": ctx.get("market_demand"),
        "cost": ctx.get("cost"),
        "simulation": ctx.get("simulation"),
        "policy_decision": ctx.get("policy_decision"),
        "opportunity": ctx.get("opportunity"),
    }
