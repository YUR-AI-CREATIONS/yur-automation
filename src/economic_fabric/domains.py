"""
Economic Fabric — domain schemas.

Structured economic data: Census, permits, migration, employment, GDP, interest rates.
Plus nitty-gritty infrastructure: traffic, healthcare, postal, water, sewer, bridges,
treatment plants, forestry, permit denials, compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# --- Core economic ---
@dataclass
class CensusRecord:
    """Census / demographic record per region."""
    region_id: str
    year: int
    population: Optional[int] = None
    households: Optional[int] = None
    median_income: Optional[float] = None
    median_age: Optional[float] = None
    housing_units: Optional[int] = None
    vacancy_rate: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermitRecord:
    """Building permit record per region."""
    region_id: str
    year: int
    month: Optional[int] = None
    single_family: Optional[int] = None
    multi_family: Optional[int] = None
    total_units: Optional[int] = None
    total_value: Optional[float] = None
    yoy_growth_pct: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationRecord:
    """Net migration / population flow per region."""
    region_id: str
    year: int
    net_migration: Optional[int] = None
    domestic_inflow: Optional[int] = None
    domestic_outflow: Optional[int] = None
    international_inflow: Optional[int] = None
    migration_score: Optional[float] = None  # 0–1 normalized
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmploymentRecord:
    """Employment / labor market record per region."""
    region_id: str
    year: int
    month: Optional[int] = None
    employed: Optional[int] = None
    unemployed: Optional[int] = None
    labor_force: Optional[int] = None
    unemployment_rate: Optional[float] = None
    job_growth_yoy_pct: Optional[float] = None
    wage_growth_yoy_pct: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class GDPRecord:
    """Regional GDP / output record."""
    region_id: str
    year: int
    quarter: Optional[int] = None
    gdp_millions: Optional[float] = None
    gdp_growth_yoy_pct: Optional[float] = None
    real_gdp_growth_pct: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class InterestRateRecord:
    """Interest rate / macro record (national or regional)."""
    region_id: str  # "US" for national
    year: int
    month: Optional[int] = None
    fed_funds: Optional[float] = None
    mortgage_30y: Optional[float] = None
    mortgage_15y: Optional[float] = None
    treasury_10y: Optional[float] = None
    inflation_cpi_yoy: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


# --- Infrastructure (nitty-gritty) ---
@dataclass
class TrafficRecord:
    """Traffic / transportation record. Leading indicator for growth."""
    region_id: str
    year: int
    month: Optional[int] = None
    corridor_id: Optional[str] = None
    adt: Optional[int] = None  # average daily traffic
    congestion_index: Optional[float] = None  # 0–1
    capacity_pct: Optional[float] = None  # utilization
    yoy_growth_pct: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthcareRecord:
    """Hospital / healthcare capacity. Patient volume = migration proxy."""
    region_id: str
    year: int
    month: Optional[int] = None
    beds: Optional[int] = None
    patient_days: Optional[int] = None
    admissions: Optional[int] = None
    capacity_utilization_pct: Optional[float] = None
    yoy_patient_growth_pct: Optional[float] = None
    new_facilities_planned: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PostalRecord:
    """USPS / postal relocation and volume. Strong migration leading indicator."""
    region_id: str
    year: int
    month: Optional[int] = None
    facility_relocations: Optional[int] = None
    address_changes: Optional[int] = None
    mail_volume_yoy_pct: Optional[float] = None
    delivery_points_added: Optional[int] = None
    migration_proxy_score: Optional[float] = None  # 0–1
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class WaterInfrastructureRecord:
    """Water mains, design capacity, projects. Front-end development signal."""
    region_id: str
    year: int
    main_line_miles: Optional[float] = None
    design_capacity_mgd: Optional[float] = None  # million gallons/day
    projects_planned: Optional[int] = None
    projects_under_construction: Optional[int] = None
    capital_investment_millions: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SewerInfrastructureRecord:
    """Sewer lines, treatment capacity. Sanitary plant signal."""
    region_id: str
    year: int
    sewer_line_miles: Optional[float] = None
    treatment_capacity_mgd: Optional[float] = None
    plants_planned: Optional[int] = None
    plants_under_construction: Optional[int] = None
    capital_investment_millions: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeRecord:
    """Bridge construction, replacement, inspection. Infrastructure investment."""
    region_id: str
    year: int
    bridges_total: Optional[int] = None
    structurally_deficient: Optional[int] = None
    replacement_projects: Optional[int] = None
    new_construction: Optional[int] = None
    capital_planned_millions: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TreatmentPlantRecord:
    """Water treatment + wastewater/sanitary plants."""
    region_id: str
    year: int
    plant_type: str  # "water" | "wastewater" | "sanitary"
    capacity_mgd: Optional[float] = None
    plants_operational: Optional[int] = None
    plants_planned: Optional[int] = None
    upgrades_planned: Optional[int] = None
    capital_millions: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForestryRecord:
    """Forestry operations, timber permits, land use."""
    region_id: str
    year: int
    timber_harvest_acres: Optional[float] = None
    permits_issued: Optional[int] = None
    permits_denied: Optional[int] = None
    compliance_violations: Optional[int] = None
    stricter_policy_adopted: Optional[bool] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermitDenialRecord:
    """Hazardous/industrial permit denials. Concrete, paper mills, etc."""
    region_id: str
    year: int
    denial_type: str  # "concrete_plant" | "paper_mill" | "chemical" | "hazardous" | "other"
    facility_type: Optional[str] = None
    denial_reason: Optional[str] = None
    total_denials: Optional[int] = None
    regulatory_shift_score: Optional[float] = None  # 0–1, stricter = higher
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceRecord:
    """Regulatory compliance trends. Stricter enforcement signal."""
    region_id: str
    year: int
    inspections: Optional[int] = None
    violations_cited: Optional[int] = None
    enforcement_actions: Optional[int] = None
    new_regulations_adopted: Optional[int] = None
    compliance_strictness_score: Optional[float] = None  # 0–1
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EconomicDevelopmentRecord:
    """Front-end economic development: incentives, rezoning, EDD projects."""
    region_id: str
    year: int
    incentives_approved: Optional[int] = None
    rezoning_approvals: Optional[int] = None
    edd_projects_planned: Optional[int] = None
    capital_committed_millions: Optional[float] = None
    jobs_committed: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EconomicRegion:
    """Unified economic view for a region. Aggregates all domains."""
    region_id: str
    migration_score: float = 0.0
    permit_growth: float = 0.0
    infrastructure_investment: float = 0.0
    employment_expansion: float = 0.0
    land_price_trend: float = 0.0
    growth_index: float = 0.0
    demand_index: float = 0.0
    absorption_months: float = 14.0
    migration_prediction_score: float = 0.0  # 0–1 from leading signals (postal, healthcare, traffic)
    infrastructure_readiness: float = 0.0  # 0–1 water, sewer, treatment plants
    regulatory_risk_score: float = 0.0  # 0–1 higher = more denials, stricter compliance
    census: Optional[CensusRecord] = None
    permits: list[PermitRecord] = field(default_factory=list)
    migration: Optional[MigrationRecord] = None
    employment: Optional[EmploymentRecord] = None
    gdp: Optional[GDPRecord] = None
    interest_rates: Optional[InterestRateRecord] = None
    traffic: list[TrafficRecord] = field(default_factory=list)
    healthcare: Optional[HealthcareRecord] = None
    postal: Optional[PostalRecord] = None
    water_infrastructure: list[WaterInfrastructureRecord] = field(default_factory=list)
    sewer_infrastructure: list[SewerInfrastructureRecord] = field(default_factory=list)
    bridges: list[BridgeRecord] = field(default_factory=list)
    treatment_plants: list[TreatmentPlantRecord] = field(default_factory=list)
    forestry: Optional[ForestryRecord] = None
    permit_denials: list[PermitDenialRecord] = field(default_factory=list)
    compliance: Optional[ComplianceRecord] = None
    economic_development: list[EconomicDevelopmentRecord] = field(default_factory=list)
    source: str = "default"  # "economic_fabric" | "default" | "connector"
    updated_at: Optional[str] = None
