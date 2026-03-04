"""
Superagents Fleet — Autonomous agent fleet for construction & land development.

Runs a construction company and development company digitally with specialized agents:
- Land & Feasibility, Bid Scraping, Financial Analyst, Bookkeeper, File Keeper
- Social Media & Marketing, Internal Audit, Branding Integrity, Insurance & Bonding
- Heavy Equipment Maintenance, Logistics & Fleet, Market Study
- Civil Engineer & Land Planning, Master Feasibility Guru
- 10-Year Plan & Roadmap Agent
"""

from .registry import AGENT_REGISTRY, get_agent_spec, list_agent_ids
from .hub import FleetHub

__all__ = [
    "AGENT_REGISTRY",
    "get_agent_spec",
    "list_agent_ids",
    "FleetHub",
]
