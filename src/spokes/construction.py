"""
Construction Spoke — pay apps, project controls, construction-specific integrations.

Registers flows and provides UI for:
- Pay app tracker (status, amounts, lien deadlines)
- Construction dashboard (contract value, billed, received, outstanding)
- Procore integration
"""

from __future__ import annotations

from typing import Any


def pay_app_tracker(inp: dict[str, Any]) -> dict[str, Any]:
    """Pay app tracker flow — stub for now. Will integrate with Procore."""
    action = inp.get("action", "status")
    
    if action == "status":
        return {
            "status": "ok",
            "total_apps": 3,
            "summary": {
                "submitted": 1,
                "approved": 1,
                "paid": 1,
                "total_amount": 187000,
            }
        }
    return {"status": "unknown_action", "action": action}


def construction_dashboard(inp: dict[str, Any]) -> dict[str, Any]:
    """Construction dashboard — project summary (contract value, billed, received, outstanding)."""
    return {
        "status": "ok",
        "summary": {
            "contract_value": 500000,
            "billed": 350000,
            "received": 300000,
            "outstanding": 50000,
        }
    }


# Spoke metadata
SPOKE_NAME = "construction"
SPOKE_DESCRIPTION = "Construction project controls, pay apps, lien tracking"

# Flows that this spoke registers
FLOWS_TO_REGISTER = [
    {
        "flow_id": "construction_pay_app_tracker",
        "name": "Pay App Tracker",
        "direction": "incoming",
        "description": "Track pay applications: status, amounts, lien deadlines",
        "scope": "internal",
        "timeout_seconds": 30,
        "handler": pay_app_tracker,
    },
    {
        "flow_id": "construction_dashboard",
        "name": "Construction Dashboard",
        "direction": "incoming",
        "description": "Project summary: contract value, billed, received, outstanding",
        "scope": "internal",
        "timeout_seconds": 30,
        "handler": construction_dashboard,
    },
]

# UI pages that this spoke provides
UI_PAGES = [
    {
        "path": "/ui/construction",
        "title": "FranklinOps for Construction",
        "description": "Pay apps, lien deadlines, project dashboard",
    }
]
