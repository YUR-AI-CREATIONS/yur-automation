"""
Economic Fabric — indicator computation.

Growth index, demand index, absorption forecast. Migration prediction from leading
signals (postal, healthcare, traffic). Infrastructure readiness. Regulatory risk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .domains import (
    CensusRecord,
    PermitRecord,
    MigrationRecord,
    EmploymentRecord,
    GDPRecord,
    InterestRateRecord,
    EconomicRegion,
    TrafficRecord,
    HealthcareRecord,
    PostalRecord,
    WaterInfrastructureRecord,
    SewerInfrastructureRecord,
    BridgeRecord,
    TreatmentPlantRecord,
    ForestryRecord,
    PermitDenialRecord,
    ComplianceRecord,
    EconomicDevelopmentRecord,
)


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def compute_migration_prediction_score(
    *,
    postal: Optional[PostalRecord] = None,
    healthcare: Optional[HealthcareRecord] = None,
    traffic: Optional[list[TrafficRecord]] = None,
) -> float:
    """
    Leading-indicator migration prediction 0–1. Postal relocation, hospital patients,
    traffic growth = people moving in before Census catches it.
    """
    scores = []
    if postal and postal.migration_proxy_score is not None:
        scores.append(postal.migration_proxy_score)
    elif postal and postal.mail_volume_yoy_pct is not None:
        scores.append(min(1.0, max(0.0, (postal.mail_volume_yoy_pct + 0.05) / 0.15)))
    elif postal and postal.address_changes and postal.address_changes > 0:
        scores.append(min(1.0, postal.address_changes / 10000))
    if healthcare and healthcare.yoy_patient_growth_pct is not None:
        scores.append(min(1.0, max(0.0, (healthcare.yoy_patient_growth_pct + 0.02) / 0.12)))
    if traffic:
        for t in traffic[-3:]:
            if t.yoy_growth_pct is not None:
                scores.append(min(1.0, max(0.0, (t.yoy_growth_pct + 0.02) / 0.10)))
    if not scores:
        return 0.5
    return min(1.0, max(0.0, sum(scores) / len(scores)))


def compute_infrastructure_readiness(
    *,
    water: Optional[list[WaterInfrastructureRecord]] = None,
    sewer: Optional[list[SewerInfrastructureRecord]] = None,
    treatment_plants: Optional[list[TreatmentPlantRecord]] = None,
    bridges: Optional[list[BridgeRecord]] = None,
    economic_dev: Optional[list[EconomicDevelopmentRecord]] = None,
) -> float:
    """
    Infrastructure readiness 0–1. Water, sewer, treatment plants, bridges, front-end EDD.
    Higher = region can absorb growth.
    """
    scores = []
    if water and water:
        w = water[-1]
        if w.projects_under_construction or w.projects_planned:
            scores.append(min(1.0, ((w.projects_under_construction or 0) * 0.6 + (w.projects_planned or 0) * 0.2) / 3))
        elif w.design_capacity_mgd and w.design_capacity_mgd > 0:
            scores.append(0.7)
    if sewer and sewer:
        s = sewer[-1]
        if s.plants_under_construction or s.plants_planned:
            scores.append(min(1.0, ((s.plants_under_construction or 0) * 0.6 + (s.plants_planned or 0) * 0.2) / 2))
    if treatment_plants and treatment_plants:
        tp = [t for t in treatment_plants if t.plants_planned or t.upgrades_planned]
        if tp:
            scores.append(min(1.0, len(tp) * 0.3))
    if bridges and bridges:
        b = bridges[-1]
        if b.replacement_projects or b.new_construction:
            scores.append(min(1.0, ((b.replacement_projects or 0) + (b.new_construction or 0)) / 5))
    if economic_dev and economic_dev:
        scores.append(min(1.0, len(economic_dev) * 0.2))
    if not scores:
        return 0.5
    return min(1.0, max(0.0, sum(scores) / max(1, len(scores))))


def compute_regulatory_risk_score(
    *,
    permit_denials: Optional[list[PermitDenialRecord]] = None,
    compliance: Optional[ComplianceRecord] = None,
    forestry: Optional[ForestryRecord] = None,
) -> float:
    """
    Regulatory risk 0–1. Higher = more denials, stricter compliance, forestry restrictions.
    Concrete plants, paper mills denied; stricter enforcement.
    """
    scores = []
    if permit_denials and permit_denials:
        denials = sum(d.total_denials or 1 for d in permit_denials)
        scores.append(min(1.0, denials / 5))
        for d in permit_denials:
            if d.regulatory_shift_score is not None:
                scores.append(d.regulatory_shift_score)
    if compliance and compliance.compliance_strictness_score is not None:
        scores.append(compliance.compliance_strictness_score)
    elif compliance and compliance.new_regulations_adopted and compliance.new_regulations_adopted > 0:
        scores.append(min(1.0, compliance.new_regulations_adopted / 3))
    if forestry and forestry.stricter_policy_adopted:
        scores.append(0.7)
    if forestry and forestry.permits_denied and (forestry.permits_denied or 0) > 0:
        scores.append(min(1.0, (forestry.permits_denied or 0) / 5))
    if not scores:
        return 0.0
    return min(1.0, max(0.0, sum(scores) / len(scores)))


def compute_growth_index(
    *,
    migration_score: float = 0.0,
    permit_growth: float = 0.0,
    employment_expansion: float = 0.0,
    gdp_growth: float = 0.0,
    infrastructure_readiness: float = 0.0,
    migration_prediction: float = 0.0,
    weights: Optional[dict[str, float]] = None,
) -> float:
    """
    Composite growth index 0–1. Higher = stronger growth corridor.
    Now includes infrastructure readiness and migration prediction (leading signals).
    """
    w = weights or {
        "migration": 0.22,
        "permits": 0.22,
        "employment": 0.18,
        "gdp": 0.10,
        "infrastructure": 0.14,
        "migration_prediction": 0.14,
    }
    mig = migration_score if migration_prediction <= 0 else (migration_score + migration_prediction) / 2
    score = (
        min(1.0, max(0.0, mig)) * w.get("migration", 0.22)
        + min(1.0, max(0.0, permit_growth)) * w.get("permits", 0.22)
        + min(1.0, max(0.0, employment_expansion)) * w.get("employment", 0.18)
        + min(1.0, max(0.0, (gdp_growth + 0.1) / 0.2)) * w.get("gdp", 0.10)
        + min(1.0, max(0.0, infrastructure_readiness)) * w.get("infrastructure", 0.14)
        + min(1.0, max(0.0, migration_prediction)) * w.get("migration_prediction", 0.14)
    )
    return min(1.0, max(0.0, score))


def compute_demand_index(
    *,
    population: Optional[int] = None,
    households: Optional[int] = None,
    vacancy_rate: Optional[float] = None,
    permit_units: Optional[int] = None,
    baseline_population: int = 100_000,
) -> float:
    """
    Housing demand index 0–1. Based on population, vacancy, permits.
    """
    pop = population or households or 0
    vac = _safe_float(vacancy_rate, 0.05)
    permits = permit_units or 0
    if pop <= 0:
        return 0.5  # neutral when no data
    pop_ratio = min(2.0, pop / baseline_population)
    demand_from_pop = min(1.0, pop_ratio * 0.5)
    demand_from_vacancy = max(0.0, 1.0 - vac * 10) if vac < 0.2 else 0.0
    demand_from_permits = min(1.0, permits / 5000) * 0.3 if permits else 0.0
    return min(1.0, max(0.0, demand_from_pop + demand_from_vacancy * 0.3 + demand_from_permits))


def compute_absorption_forecast(
    *,
    demand_index: float = 0.5,
    permit_growth: float = 0.5,
    interest_rate: Optional[float] = None,
    baseline_months: float = 14.0,
) -> float:
    """
    Forecast absorption in months. Higher demand → faster absorption (fewer months).
    Higher rates → slower absorption.
    """
    # demand 0→1: 24 months → 8 months
    months_from_demand = 24.0 - (demand_index * 16.0)
    # permit growth: more permits → slightly slower (more supply)
    months_from_permits = permit_growth * 4.0
    months = baseline_months + (months_from_demand - baseline_months) * 0.6 - months_from_permits * 0.2
    if interest_rate is not None and interest_rate > 0:
        # each 1% above 5% adds ~1 month
        months += max(0, (interest_rate - 5.0) * 1.0)
    return max(6.0, min(36.0, months))


def compute_region_scores(
    region: EconomicRegion,
    *,
    census: Optional[CensusRecord] = None,
    permits: Optional[list[PermitRecord]] = None,
    migration: Optional[MigrationRecord] = None,
    employment: Optional[EmploymentRecord] = None,
    gdp: Optional[GDPRecord] = None,
    interest_rates: Optional[InterestRateRecord] = None,
    traffic: Optional[list[TrafficRecord]] = None,
    healthcare: Optional[HealthcareRecord] = None,
    postal: Optional[PostalRecord] = None,
    water_infrastructure: Optional[list[WaterInfrastructureRecord]] = None,
    sewer_infrastructure: Optional[list[SewerInfrastructureRecord]] = None,
    bridges: Optional[list[BridgeRecord]] = None,
    treatment_plants: Optional[list[TreatmentPlantRecord]] = None,
    forestry: Optional[ForestryRecord] = None,
    permit_denials: Optional[list[PermitDenialRecord]] = None,
    compliance: Optional[ComplianceRecord] = None,
    economic_development: Optional[list[EconomicDevelopmentRecord]] = None,
) -> EconomicRegion:
    """
    Compute all indicators for a region from domain records.
    Updates region in place, returns it.
    """
    perm_list = permits or region.permits
    permit_growth = region.permit_growth
    if perm_list and len(perm_list) >= 2:
        recent = sum(p.total_units or 0 for p in perm_list[-12:])
        older = sum(p.total_units or 0 for p in perm_list[-24:-12]) or 1
        permit_growth = min(1.0, max(0.0, (recent - older) / older)) if older else 0.5

    migration_score = region.migration_score
    if migration and migration.migration_score is not None:
        migration_score = migration.migration_score
    elif migration and migration.net_migration is not None:
        migration_score = min(1.0, max(0.0, (migration.net_migration + 10000) / 20000))

    employment_expansion = region.employment_expansion
    if employment and employment.job_growth_yoy_pct is not None:
        employment_expansion = min(1.0, max(0.0, (employment.job_growth_yoy_pct + 0.05) / 0.15))

    gdp_growth = 0.0
    if gdp and gdp.gdp_growth_yoy_pct is not None:
        gdp_growth = gdp.gdp_growth_yoy_pct / 100.0

    migration_prediction = compute_migration_prediction_score(
        postal=postal or region.postal,
        healthcare=healthcare or region.healthcare,
        traffic=traffic or region.traffic,
    )
    infrastructure_readiness = compute_infrastructure_readiness(
        water=water_infrastructure or region.water_infrastructure,
        sewer=sewer_infrastructure or region.sewer_infrastructure,
        treatment_plants=treatment_plants or region.treatment_plants,
        bridges=bridges or region.bridges,
        economic_dev=economic_development or region.economic_development,
    )
    regulatory_risk = compute_regulatory_risk_score(
        permit_denials=permit_denials or region.permit_denials,
        compliance=compliance or region.compliance,
        forestry=forestry or region.forestry,
    )

    growth_index = compute_growth_index(
        migration_score=migration_score,
        permit_growth=permit_growth,
        employment_expansion=employment_expansion,
        gdp_growth=gdp_growth,
        infrastructure_readiness=infrastructure_readiness,
        migration_prediction=migration_prediction,
    )

    pop = census.population if census else None
    hh = census.households if census else None
    vac = census.vacancy_rate if census else None
    permit_units = sum(p.total_units or 0 for p in perm_list) if perm_list else None
    demand_index = compute_demand_index(
        population=pop,
        households=hh,
        vacancy_rate=vac,
        permit_units=permit_units,
    )

    mort_rate = interest_rates.mortgage_30y if interest_rates else None
    absorption_months = compute_absorption_forecast(
        demand_index=demand_index,
        permit_growth=permit_growth,
        interest_rate=mort_rate,
    )

    region.migration_score = migration_score
    region.permit_growth = permit_growth
    region.employment_expansion = employment_expansion
    region.growth_index = growth_index
    region.demand_index = demand_index
    region.absorption_months = absorption_months
    region.migration_prediction_score = migration_prediction
    region.infrastructure_readiness = infrastructure_readiness
    region.regulatory_risk_score = regulatory_risk
    region.census = census or region.census
    region.permits = perm_list or region.permits
    region.migration = migration or region.migration
    region.employment = employment or region.employment
    region.gdp = gdp or region.gdp
    region.interest_rates = interest_rates or region.interest_rates
    region.traffic = traffic or region.traffic
    region.healthcare = healthcare or region.healthcare
    region.postal = postal or region.postal
    region.water_infrastructure = water_infrastructure or region.water_infrastructure
    region.sewer_infrastructure = sewer_infrastructure or region.sewer_infrastructure
    region.bridges = bridges or region.bridges
    region.treatment_plants = treatment_plants or region.treatment_plants
    region.forestry = forestry or region.forestry
    region.permit_denials = permit_denials or region.permit_denials
    region.compliance = compliance or region.compliance
    region.economic_development = economic_development or region.economic_development
    region.source = "economic_fabric"
    region.updated_at = datetime.now(timezone.utc).isoformat()

    return region
