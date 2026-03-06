"""
Corridor Scanner — identifies regions with strong development potential.

Analyzes: population migration, housing permits, infrastructure, employment, land prices.
Uses Economic Fabric when available for real data. Falls back to input scores.
Output: development probability score per region. Highest = growth corridors.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ..bus import create_event, get_bus

_LOG = logging.getLogger("geo_economic")


def _enrich_from_economic_fabric(region: dict[str, Any]) -> dict[str, Any]:
    """Enrich region with Economic Fabric data when region_id present."""
    rid = region.get("region_id") or region.get("id")
    if not rid or rid == "unknown":
        return region
    try:
        from ..economic_fabric import get_economic_index
        econ = get_economic_index(str(rid), use_connectors=True, use_fabric=True)
        if econ.source == "economic_fabric":
            return {
                **region,
                "migration_score": econ.migration_score,
                "permit_growth": econ.permit_growth,
                "infrastructure_investment": econ.infrastructure_investment,
                "employment_expansion": econ.employment_expansion,
                "land_price_trend": econ.land_price_trend,
                "growth_index": econ.growth_index,
                "demand_index": econ.demand_index,
            }
    except Exception as e:
        _LOG.debug("economic fabric enrich %s: %s", rid, e)
    return region


def score_region(
    region_id: str,
    *,
    migration_score: float = 0.0,
    permit_growth: float = 0.0,
    infrastructure_investment: float = 0.0,
    employment_expansion: float = 0.0,
    land_price_trend: float = 0.0,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Compute development probability score for a region.
    Weights default: migration 0.25, permits 0.25, infra 0.2, employment 0.2, land 0.1.
    """
    w = weights or {
        "migration": 0.25,
        "permits": 0.25,
        "infrastructure": 0.2,
        "employment": 0.2,
        "land": 0.1,
    }
    score = (
        migration_score * w.get("migration", 0.25)
        + permit_growth * w.get("permits", 0.25)
        + infrastructure_investment * w.get("infrastructure", 0.2)
        + employment_expansion * w.get("employment", 0.2)
        + land_price_trend * w.get("land", 0.1)
    )
    return {
        "region_id": region_id,
        "development_score": min(1.0, max(0.0, score)),
        "signals": {
            "migration": migration_score,
            "permits": permit_growth,
            "infrastructure": infrastructure_investment,
            "employment": employment_expansion,
            "land_price": land_price_trend,
        },
    }


def scan_corridors(
    regions: list[dict[str, Any]],
    *,
    trace_id: str | None = None,
    tenant_id: str = "default",
    threshold: float = 0.6,
) -> dict[str, Any]:
    """
    Scan regions, score each, emit corridor.signal_detected for high-scoring.
    Returns ranked list of growth corridors.
    """
    tid = trace_id or str(uuid.uuid4())
    bus = get_bus()

    scored = []
    for r in regions:
        r = _enrich_from_economic_fabric(dict(r))
        region_id = r.get("region_id", r.get("id", "unknown"))
        s = score_region(
            region_id,
            migration_score=r.get("migration_score", 0.5),
            permit_growth=r.get("permit_growth", 0.5),
            infrastructure_investment=r.get("infrastructure_investment", 0.5),
            employment_expansion=r.get("employment_expansion", 0.5),
            land_price_trend=r.get("land_price_trend", 0.5),
        )
        scored.append(s)

        if s["development_score"] >= threshold:
            ev = create_event(
                "corridor.signal_detected",
                "geo_economic_engine",
                s,
                trace_id=tid,
                tenant_id=tenant_id,
            )
            bus.publish("corridor.signal_detected", ev)

    scored.sort(key=lambda x: x["development_score"], reverse=True)
    corridors = [s for s in scored if s["development_score"] >= threshold]

    return {
        "ok": True,
        "trace_id": tid,
        "regions_scored": len(scored),
        "corridors_found": len(corridors),
        "corridors": corridors,
        "all_scores": scored,
    }
