"""
Agent Factory — Creates FleetAgent instances from registry specs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..registry import AGENT_REGISTRY, get_agent_spec
from .base import FleetAgent
from .land_feasibility import LandFeasibilityAgent
from .bid_scraping import BidScrapingAgent
from .financial import FinancialAnalystAgent
from .bookkeeper import BookkeeperAgent
from .file_keeper import FileKeeperAgent
from .project_manager import ProjectManagerAgent
from .logistics_fleet import LogisticsFleetAgent
from .social_marketing import SocialMarketingAgent
from .internal_audit import InternalAuditAgent

if TYPE_CHECKING:
    pass

# Map agent_id -> specialized class (or base FleetAgent for generic)
_AGENT_CLASSES: dict[str, type[FleetAgent]] = {
    "land_feasibility": LandFeasibilityAgent,
    "civil_land_planning": LandFeasibilityAgent,  # shares logic for now
    "market_study": LandFeasibilityAgent,
    "master_feasibility": LandFeasibilityAgent,
    "roadmap_10yr": LandFeasibilityAgent,
    "bid_scraping": BidScrapingAgent,
    "financial_analyst": FinancialAnalystAgent,
    "bookkeeper": BookkeeperAgent,
    "file_keeper": FileKeeperAgent,
    "ar_ap_outreach": BookkeeperAgent,
    "logistics_fleet": LogisticsFleetAgent,
    "heavy_equipment": LogisticsFleetAgent,
    "concrete_dispatch": LogisticsFleetAgent,
    "social_marketing": SocialMarketingAgent,
    "branding_integrity": SocialMarketingAgent,
    "internal_audit": InternalAuditAgent,
    "insurance_bonding": InternalAuditAgent,
    "project_manager": ProjectManagerAgent,
    "subcontractor_scoring": ProjectManagerAgent,
    "warm_outreach": SocialMarketingAgent,
}


def create_fleet_agent(agent_id: str, autonomy_level: str = "semi-autonomous") -> FleetAgent | None:
    """Create a FleetAgent instance by ID."""
    spec = get_agent_spec(agent_id)
    if not spec:
        return None
    cls = _AGENT_CLASSES.get(agent_id, FleetAgent)
    return cls(spec=spec, autonomy_level=autonomy_level)
