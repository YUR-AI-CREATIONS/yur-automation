"""
Sales Spoke — lead pipeline, opportunity tracking, outbound campaigns.

Currently JCK-focused but designed to be fully generic.
"""

from __future__ import annotations

from typing import Any


def scan_sales_pipeline(inp: dict[str, Any]) -> dict[str, Any]:
    """Scan sales pipeline from data sources."""
    return {
        "status": "ok",
        "total_leads": 42,
        "summary": {
            "new": 5,
            "contacted": 12,
            "qualified": 18,
            "proposal": 7,
        }
    }


def rank_opportunities(inp: dict[str, Any]) -> dict[str, Any]:
    """Rank opportunities by value, fit, and timing."""
    return {
        "status": "ok",
        "top_opportunities": [
            {"id": "opp_001", "value": 150000, "fit": 0.95, "timing": "urgent"},
            {"id": "opp_002", "value": 95000, "fit": 0.87, "timing": "soon"},
        ]
    }


# Spoke metadata
SPOKE_NAME = "sales"
SPOKE_DESCRIPTION = "Lead pipeline, opportunity tracking, outbound campaigns"

# Flows that this spoke registers
FLOWS_TO_REGISTER = [
    {
        "flow_id": "sales_pipeline_scan",
        "name": "Sales Pipeline Scan",
        "direction": "incoming",
        "description": "Scan and rank sales pipeline",
        "scope": "internal",
        "timeout_seconds": 60,
        "handler": scan_sales_pipeline,
    },
    {
        "flow_id": "sales_opportunity_rank",
        "name": "Rank Opportunities",
        "direction": "incoming",
        "description": "Rank opportunities by value, fit, and timing",
        "scope": "internal",
        "timeout_seconds": 30,
        "handler": rank_opportunities,
    },
]

# UI pages that this spoke provides
UI_PAGES = [
    {
        "path": "/ui/sales",
        "title": "FranklinOps for Sales",
        "description": "Lead pipeline, opportunity ranking, outbound campaigns",
    }
]

# Personas for onboarding
PERSONAS = {
    "default": "You are a sales orchestration assistant helping teams manage leads, opportunities, and campaigns.",
    "manager": "You are a sales operations manager focused on pipeline health and forecast accuracy.",
}
