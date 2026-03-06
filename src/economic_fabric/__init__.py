"""
Economic Fabric — sovereign economic intelligence layer.

Domains: Census, permits, migration, employment, GDP, interest rates.
Connectors: Census API, BLS, permit APIs (stubs when no subscription).
Indicators: growth_index, demand_index, absorption_forecast.
Feeds: Geo-Economic Engine, Land Pipeline, Simulation.
"""

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
from .indicators import (
    compute_growth_index,
    compute_demand_index,
    compute_absorption_forecast,
    compute_region_scores,
    compute_migration_prediction_score,
    compute_infrastructure_readiness,
    compute_regulatory_risk_score,
)
from .connectors import (
    fetch_census,
    fetch_permits,
    fetch_employment,
    fetch_gdp,
    fetch_interest_rates,
)
from .index import get_economic_index, refresh_economic_index

__all__ = [
    "CensusRecord",
    "PermitRecord",
    "MigrationRecord",
    "EmploymentRecord",
    "GDPRecord",
    "InterestRateRecord",
    "EconomicRegion",
    "TrafficRecord",
    "HealthcareRecord",
    "PostalRecord",
    "WaterInfrastructureRecord",
    "SewerInfrastructureRecord",
    "BridgeRecord",
    "TreatmentPlantRecord",
    "ForestryRecord",
    "PermitDenialRecord",
    "ComplianceRecord",
    "EconomicDevelopmentRecord",
    "compute_growth_index",
    "compute_demand_index",
    "compute_absorption_forecast",
    "compute_region_scores",
    "compute_migration_prediction_score",
    "compute_infrastructure_readiness",
    "compute_regulatory_risk_score",
    "fetch_census",
    "fetch_permits",
    "fetch_employment",
    "fetch_gdp",
    "fetch_interest_rates",
    "get_economic_index",
    "refresh_economic_index",
]
