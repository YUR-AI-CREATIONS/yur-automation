"""
Economic Fabric — unified economic index.

Aggregates: Data Fabric features + connector fetches.
Provides: get_economic_index(region_id) → EconomicRegion.
Used by: Geo-Economic Engine, Land Pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from .domains import (
    CensusRecord,
    PermitRecord,
    MigrationRecord,
    EmploymentRecord,
    GDPRecord,
    InterestRateRecord,
    EconomicRegion,
)
from .connectors import (
    fetch_census,
    fetch_permits,
    fetch_employment,
    fetch_gdp,
    fetch_interest_rates,
)
from .indicators import compute_region_scores

_LOG = logging.getLogger("economic_fabric")

FABRIC_ROOT = Path(__file__).resolve().parents[2] / "data" / "fabric"
RAW_ECONOMIC = FABRIC_ROOT / "raw" / "economic"
CLEAN_ECONOMIC = FABRIC_ROOT / "clean" / "economic"
FEATURES_ECONOMIC = FABRIC_ROOT / "features" / "economic"
INDEX_PATH = FABRIC_ROOT / "economic_index.json"


def _load_from_fabric(region_id: str) -> Optional[dict[str, Any]]:
    """Load economic features from Data Fabric when available."""
    # 1. Check region-specific dirs: features/economic/{region_id}/, clean/economic/{region_id}/
    for base in FEATURES_ECONOMIC, CLEAN_ECONOMIC:
        region_dir = base / region_id
        if region_dir.exists():
            for fp in sorted(region_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]:
                try:
                    data = json.loads(fp.read_text(encoding="utf-8"))
                    if isinstance(data, list) and data:
                        for row in data:
                            if isinstance(row, dict):
                                row = dict(row)
                                row["region_id"] = region_id
                                return row
                    if isinstance(data, dict):
                        data = dict(data)
                        data["region_id"] = region_id
                        return data
                except (json.JSONDecodeError, OSError) as e:
                    _LOG.debug("fabric load %s: %s", fp, e)
    # 2. Scan features/economic/*.json for matching region_id
    if FEATURES_ECONOMIC.exists():
        for fp in sorted(FEATURES_ECONOMIC.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                rows = data if isinstance(data, list) else [data]
                for row in rows:
                    if isinstance(row, dict) and row.get("region_id") == region_id:
                        return dict(row)
                if isinstance(data, dict) and data.get("region_id") == region_id:
                    return dict(data)
            except (json.JSONDecodeError, OSError):
                pass
    return None


def _dict_to_region(d: dict[str, Any]) -> EconomicRegion:
    """Build EconomicRegion from raw dict (Data Fabric or JSON)."""
    r = EconomicRegion(
        region_id=d.get("region_id", "unknown"),
        migration_score=float(d.get("migration_score", 0.5)),
        permit_growth=float(d.get("permit_growth", 0.5)),
        infrastructure_investment=float(d.get("infrastructure_investment", 0.5)),
        employment_expansion=float(d.get("employment_expansion", 0.5)),
        land_price_trend=float(d.get("land_price_trend", 0.5)),
        growth_index=float(d.get("growth_index", 0)),
        demand_index=float(d.get("demand_index", 0)),
        absorption_months=float(d.get("absorption_months", 14.0)),
        migration_prediction_score=float(d.get("migration_prediction_score", 0)),
        infrastructure_readiness=float(d.get("infrastructure_readiness", 0)),
        regulatory_risk_score=float(d.get("regulatory_risk_score", 0)),
        source=d.get("source", "fabric"),
    )
    if d.get("population"):
        r.census = CensusRecord(
            region_id=r.region_id,
            year=int(d.get("year", 2023)),
            population=int(d.get("population", 0)),
            households=int(d.get("households", 0)) if d.get("households") else None,
            median_income=float(d.get("median_income")) if d.get("median_income") else None,
            vacancy_rate=float(d.get("vacancy_rate")) if d.get("vacancy_rate") else None,
        )
    return r


def get_economic_index(
    region_id: str,
    *,
    use_connectors: bool = True,
    use_fabric: bool = True,
) -> EconomicRegion:
    """
    Get unified economic view for region.
    Loads from Data Fabric first, then optionally fetches from connectors.
    Returns EconomicRegion with scores and indicators.
    """
    region = EconomicRegion(region_id=region_id, source="default")

    if use_fabric:
        fabric_data = _load_from_fabric(region_id)
        if fabric_data:
            region = _dict_to_region(fabric_data)

    if use_connectors:
        census_records, _ = fetch_census(region_id)
        permit_records, _ = fetch_permits(region_id)
        employment_records, _ = fetch_employment(region_id)
        gdp_records, _ = fetch_gdp(region_id)
        rate_records, _ = fetch_interest_rates(region_id)

        census = census_records[0] if census_records else None
        permits = permit_records
        employment = employment_records[0] if employment_records else None
        gdp = gdp_records[0] if gdp_records else None
        interest_rates = rate_records[0] if rate_records else None

        migration = None
        if census and census.population:
            migration = MigrationRecord(
                region_id=region_id,
                year=census.year,
                migration_score=region.migration_score,
            )

        region = compute_region_scores(
            region,
            census=census,
            permits=permits or None,
            migration=migration,
            employment=employment,
            gdp=gdp,
            interest_rates=interest_rates,
        )

    return region


def refresh_economic_index(
    regions: list[str],
    *,
    use_connectors: bool = True,
) -> dict[str, Any]:
    """
    Refresh economic index for multiple regions. Persist to INDEX_PATH.
    Returns status and per-region counts.
    """
    index: dict[str, dict[str, Any]] = {}
    connector_status: dict[str, list[str]] = {}

    for rid in regions:
        region = get_economic_index(rid, use_connectors=use_connectors, use_fabric=True)
        index[rid] = {
            "region_id": region.region_id,
            "migration_score": region.migration_score,
            "permit_growth": region.permit_growth,
            "infrastructure_investment": region.infrastructure_investment,
            "employment_expansion": region.employment_expansion,
            "land_price_trend": region.land_price_trend,
            "growth_index": region.growth_index,
            "demand_index": region.demand_index,
            "absorption_months": region.absorption_months,
            "migration_prediction_score": region.migration_prediction_score,
            "infrastructure_readiness": region.infrastructure_readiness,
            "regulatory_risk_score": region.regulatory_risk_score,
            "source": region.source,
            "updated_at": region.updated_at,
        }

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")

    return {
        "ok": True,
        "regions": list(index.keys()),
        "path": str(INDEX_PATH),
    }
