"""
Finance Spoke — AP/AR, cash flow, accounting integrations.
"""

from __future__ import annotations

from typing import Any


def ap_intake_run(inp: dict[str, Any]) -> dict[str, Any]:
    """Intake accounts payable documents."""
    return {
        "status": "ok",
        "documents_scanned": 18,
        "invoices_extracted": 15,
        "total_amount": 45000,
    }


def ar_aging_report(inp: dict[str, Any]) -> dict[str, Any]:
    """Generate accounts receivable aging report."""
    return {
        "status": "ok",
        "aging_summary": {
            "current": 120000,
            "30_days": 45000,
            "60_days": 15000,
            "90plus_days": 8000,
        }
    }


# Spoke metadata
SPOKE_NAME = "finance"
SPOKE_DESCRIPTION = "AP/AR, cash flow, accounting integrations"

# Flows that this spoke registers
FLOWS_TO_REGISTER = [
    {
        "flow_id": "finance_ap_intake",
        "name": "AP Intake",
        "direction": "incoming",
        "description": "Intake and process accounts payable documents",
        "scope": "internal",
        "timeout_seconds": 60,
        "handler": ap_intake_run,
    },
    {
        "flow_id": "finance_ar_aging",
        "name": "AR Aging Report",
        "direction": "incoming",
        "description": "Generate accounts receivable aging report",
        "scope": "internal",
        "timeout_seconds": 30,
        "handler": ar_aging_report,
    },
]

# UI pages that this spoke provides
UI_PAGES = [
    {
        "path": "/ui/finance",
        "title": "FranklinOps for Finance",
        "description": "AP/AR, cash flow, accounting",
    }
]

# Personas
PERSONAS = {
    "default": "You are a financial operations assistant helping manage AP, AR, and cash flow.",
}
