"""
Agent Registry — Canonical list of all fleet agents and their specifications.

Each agent has: id, name, domain, capabilities, phase (land|bid|ops|finance|marketing|governance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentSpec:
    """Specification for a fleet agent."""

    id: str
    name: str
    domain: str
    capabilities: tuple[str, ...]
    phase: str  # land | bid | ops | finance | marketing | governance | roadmap
    description: str = ""


# Canonical registry of all fleet agents
AGENT_REGISTRY: dict[str, AgentSpec] = {
    # Phase 1: Land Acquisition & Feasibility
    "land_feasibility": AgentSpec(
        id="land_feasibility",
        name="Land & Feasibility Agent",
        domain="land_acquisition",
        capabilities=("due_diligence", "feasibility_studies", "best_use_analysis", "development_agreement_analysis"),
        phase="land",
        description="Runs due diligence, feasibility studies, determines best use, development agreement upside.",
    ),
    "civil_land_planning": AgentSpec(
        id="civil_land_planning",
        name="Civil Engineer & Land Planning Agent",
        domain="civil_engineering",
        capabilities=("2d_planning", "3d_planning", "land_mapping", "preliminary_design", "industry_standards"),
        phase="land",
        description="Creates 2D/3D land plans, maps land, preliminary design per industry standards.",
    ),
    "market_study": AgentSpec(
        id="market_study",
        name="Market Study Agent",
        domain="market_research",
        capabilities=("demand_analysis", "growth_forecasting", "financial_ecosystem", "market_trends"),
        phase="land",
        description="Understands demand, future growth, financial ecosystem around land speculation.",
    ),
    "master_feasibility": AgentSpec(
        id="master_feasibility",
        name="Master Feasibility Guru",
        domain="feasibility",
        capabilities=("full_feasibility_package", "cost_modeling", "end_user_suggestions", "go_no_go_decision"),
        phase="land",
        description="Delivers full land speculation feasibility + civil construction package for close decision.",
    ),
    "roadmap_10yr": AgentSpec(
        id="roadmap_10yr",
        name="10-Year Plan & Roadmap Agent",
        domain="strategic_planning",
        capabilities=("10yr_projection", "roadmap", "strategic_planning"),
        phase="roadmap",
        description="10-year plan projection and strategic roadmap.",
    ),
    # Phase 2: Bidding & Procurement
    "bid_scraping": AgentSpec(
        id="bid_scraping",
        name="Bid Scraping & Compiling Agent",
        domain="bidding",
        capabilities=("bid_portal_monitoring", "bid_scraping", "bid_compilation", "award_tracking", "historical_pricing"),
        phase="bid",
        description="Monitors bid portals, scrapes bids, logs time, tracks awards for historical pricing matrix.",
    ),
    # Phase 3: Finance & Operations
    "financial_analyst": AgentSpec(
        id="financial_analyst",
        name="Financial Analyst",
        domain="finance",
        capabilities=("financial_modeling", "projections", "risk_analysis", "cost_analysis"),
        phase="finance",
        description="Financial analysis, projections, risk analysis.",
    ),
    "bookkeeper": AgentSpec(
        id="bookkeeper",
        name="Bookkeeper",
        domain="accounting",
        capabilities=("ap", "ar", "reconciliation", "invoice_tracking"),
        phase="finance",
        description="AP/AR, bookkeeping, invoice tracking.",
    ),
    "file_keeper": AgentSpec(
        id="file_keeper",
        name="File Keeper",
        domain="document_management",
        capabilities=("document_ingestion", "file_routing", "central_hub", "version_control"),
        phase="ops",
        description="Central document hub — everything in, orchestrated out, tracked.",
    ),
    "ar_ap_outreach": AgentSpec(
        id="ar_ap_outreach",
        name="AR/AP Outreach Agent",
        domain="collections",
        capabilities=("warm_outreach", "invoice_tracking", "collections", "human_like_communication"),
        phase="finance",
        description="Warm outreach for AR/AP, well-spoken non-AI-detecting face of company.",
    ),
    # Phase 4: Operations
    "logistics_fleet": AgentSpec(
        id="logistics_fleet",
        name="Logistics & Fleet Agent",
        domain="fleet",
        capabilities=("fleet_dispatch", "routing", "geolocation", "timesheet_tracking"),
        phase="ops",
        description="Fleet dispatch, logistics, employee timesheets, geolocation.",
    ),
    "heavy_equipment": AgentSpec(
        id="heavy_equipment",
        name="Heavy Equipment Maintenance Agent",
        domain="equipment",
        capabilities=("maintenance_scheduling", "equipment_tracking", "preventive_maintenance"),
        phase="ops",
        description="Heavy equipment maintenance scheduling and tracking.",
    ),
    "concrete_dispatch": AgentSpec(
        id="concrete_dispatch",
        name="Concrete Dispatch Agent",
        domain="ready_mix",
        capabilities=("order_routing", "batch_house_dispatch", "ticket_logging", "customer_history"),
        phase="ops",
        description="Every concrete order through engine, dispatch to batch house, ticket logging, customer rewards.",
    ),
    # Phase 5: Marketing & Brand
    "social_marketing": AgentSpec(
        id="social_marketing",
        name="Social Media & Marketing Specialist",
        domain="marketing",
        capabilities=("daily_posting", "content_creation", "event_management", "engagement", "leadership_narrative"),
        phase="marketing",
        description="Post daily on all sites, beautiful neighborhoods, operational excellence, events.",
    ),
    "branding_integrity": AgentSpec(
        id="branding_integrity",
        name="Branding Integrity Agent",
        domain="brand",
        capabilities=("brand_consistency", "visual_standards", "messaging_standards"),
        phase="marketing",
        description="Ensures brand consistency across all touchpoints.",
    ),
    # Phase 6: Governance & Compliance
    "internal_audit": AgentSpec(
        id="internal_audit",
        name="Internal Audit Agent",
        domain="audit",
        capabilities=("compliance_check", "process_audit", "risk_identification"),
        phase="governance",
        description="Internal audit, compliance, process verification.",
    ),
    "insurance_bonding": AgentSpec(
        id="insurance_bonding",
        name="Insurance & Bonding Specialist",
        domain="insurance",
        capabilities=("insurance_tracking", "bond_compliance", "renewals"),
        phase="governance",
        description="Insurance and bonding compliance.",
    ),
    # Phase 7: Project Management & Subcontractors
    "project_manager": AgentSpec(
        id="project_manager",
        name="Project Management Agent",
        domain="construction_pm",
        capabilities=(
            "subcontractor_agreements",
            "rfp_management",
            "osha_compliance",
            "swppp",
            "grading_criteria",
            "city_standards",
            "punch_out",
            "recoupable_tracking",
        ),
        phase="ops",
        description="Full PM: subs, RFPs, OSHA, SWPPP, grading, city standards, punch-out, recoupables.",
    ),
    "subcontractor_scoring": AgentSpec(
        id="subcontractor_scoring",
        name="Subcontractor Scoring Agent",
        domain="vendor_management",
        capabilities=("scoring_matrix", "vendor_reward", "vendor_blacklist", "pricing_matrix"),
        phase="ops",
        description="Subcontractor scoring, reward good, avoid bad, realistic pricing.",
    ),
    # Phase 8: Sales & Business Development
    "warm_outreach": AgentSpec(
        id="warm_outreach",
        name="Warm Outreach Agent",
        domain="business_development",
        capabilities=(
            "targeted_emails",
            "architects",
            "engineers",
            "developers",
            "home_builders",
            "family_offices",
            "process_improvement",
        ),
        phase="marketing",
        description="Consistent warm reach to architects, engineers, developers, home builders, family offices.",
    ),
}


def get_agent_spec(agent_id: str) -> AgentSpec | None:
    """Return agent spec by ID, or None if not found."""
    return AGENT_REGISTRY.get(agent_id)


def list_agent_ids(phase: str | None = None) -> list[str]:
    """List all agent IDs, optionally filtered by phase."""
    if phase is None:
        return list(AGENT_REGISTRY.keys())
    return [aid for aid, spec in AGENT_REGISTRY.items() if spec.phase == phase]
