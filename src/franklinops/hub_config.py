"""
FranklinOpsHub — Canonical folder mapping and risk thresholds.

Phase 0: Single source of truth for OneDrive roots and their semantic meaning.
Use env vars for paths; this module defines the mapping and governance defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class FolderMapping:
    """Canonical mapping: source key → semantic role + env var."""

    source: str
    role: str
    env_var: str
    description: str


# Canonical folder mapping — Cursor project paths
# OneDrive roots (when configured): 02BIDDING, 01PROJECTS, Attachments
# Project Controls: c-00-Project-Controls-* (each log = separate Cursor workspace)
# Main systems: d-Superagents, d-XAI-BID-ZONE (sales portal), d-Franklin-OS-local, d-JCK-Land-Development
_CURSOR_PROJECTS = "C:\\Users\\jerem\\.cursor\\projects"

CANONICAL_FOLDER_MAPPING: tuple[FolderMapping, ...] = (
    # OneDrive (optional)
    FolderMapping(
        source="onedrive_bidding",
        role="new_opportunities",
        env_var="FRANKLINOPS_ONEDRIVE_BIDDING_ROOT",
        description="02BIDDING — ITBs, RFQs, new leads, contacts",
    ),
    FolderMapping(
        source="onedrive_projects",
        role="active_work",
        env_var="FRANKLINOPS_ONEDRIVE_PROJECTS_ROOT",
        description="01PROJECTS — active project docs, submittals, specs",
    ),
    FolderMapping(
        source="onedrive_attachments",
        role="invoices_submittals",
        env_var="FRANKLINOPS_ONEDRIVE_ATTACHMENTS_ROOT",
        description="Attachments — vendor invoices, submittals, misc paperwork",
    ),
    # Project Controls (Cursor workspaces)
    FolderMapping(
        source="pc_change_order",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_CHANGE_ORDER",
        description="Change Order Log",
    ),
    FolderMapping(
        source="pc_document",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_DOCUMENT",
        description="Document Log",
    ),
    FolderMapping(
        source="pc_long_lead_material",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_LONG_LEAD_MATERIAL",
        description="Long Lead Material Log",
    ),
    FolderMapping(
        source="pc_material_delivery",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_MATERIAL_DELIVERY",
        description="Material Delivery Log",
    ),
    FolderMapping(
        source="pc_material_return",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_MATERIAL_RETURN",
        description="Material Return Log",
    ),
    FolderMapping(
        source="pc_material_shortage",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_MATERIAL_SHORTAGE",
        description="Material Shortage Log",
    ),
    FolderMapping(
        source="pc_project_roster",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_PROJECT_ROSTER",
        description="Project Roster",
    ),
    FolderMapping(
        source="pc_rain_delay",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_RAIN_DELAY",
        description="Rain Delay Log",
    ),
    FolderMapping(
        source="pc_rfi",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_RFI",
        description="RFI Log",
    ),
    FolderMapping(
        source="pc_submittal",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_SUBMITTAL",
        description="Submittal Log",
    ),
    FolderMapping(
        source="pc_substitution",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_SUBSTITUTION",
        description="Substitution Log",
    ),
    FolderMapping(
        source="pc_value_engineering",
        role="construction_logs",
        env_var="FRANKLINOPS_PC_VALUE_ENGINEERING",
        description="Value Engineering Log",
    ),
    # Main systems
    FolderMapping(
        source="superagents",
        role="agent_codebase",
        env_var="FRANKLINOPS_SUPERAGENTS_ROOT",
        description="Superagents — hub, GROKSTMATE, orchestration",
    ),
    FolderMapping(
        source="bid_zone",
        role="sales_portal",
        env_var="FRANKLINOPS_BID_ZONE_ROOT",
        description="BID-ZONE — sales portal (estimating, land procurement)",
    ),
    FolderMapping(
        source="franklin_os",
        role="franklin_os",
        env_var="FRANKLINOPS_FRANKLIN_OS_ROOT",
        description="Franklin OS",
    ),
    FolderMapping(
        source="jck_land_dev",
        role="land_development",
        env_var="FRANKLINOPS_JCK_LAND_DEV_ROOT",
        description="JCK Land Development",
    ),
)


# Default Cursor project paths (used when env var not set)
_DEFAULT_PATHS: dict[str, str] = {
    "FRANKLINOPS_PC_CHANGE_ORDER": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Change-Order-Log",
    "FRANKLINOPS_PC_DOCUMENT": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Document-Log",
    "FRANKLINOPS_PC_LONG_LEAD_MATERIAL": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Long-Lead-Material-Log",
    "FRANKLINOPS_PC_MATERIAL_DELIVERY": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Material-Delivery-Log",
    "FRANKLINOPS_PC_MATERIAL_RETURN": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Material-Return-Log",
    "FRANKLINOPS_PC_MATERIAL_SHORTAGE": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Material-Shortage-Log",
    "FRANKLINOPS_PC_PROJECT_ROSTER": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Project-Roster",
    "FRANKLINOPS_PC_RAIN_DELAY": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Rain-Delay-Log",
    "FRANKLINOPS_PC_RFI": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-RFI-Log",
    "FRANKLINOPS_PC_SUBMITTAL": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Submittal-Log",
    "FRANKLINOPS_PC_SUBSTITUTION": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Substitution-Log",
    "FRANKLINOPS_PC_VALUE_ENGINEERING": f"{_CURSOR_PROJECTS}\\c-00-Project-Controls-Value-Engineering-Log",
    "FRANKLINOPS_SUPERAGENTS_ROOT": f"{_CURSOR_PROJECTS}\\d-Superagents",
    "FRANKLINOPS_BID_ZONE_ROOT": f"{_CURSOR_PROJECTS}\\d-XAI-BID-ZONE",
    "FRANKLINOPS_FRANKLIN_OS_ROOT": f"{_CURSOR_PROJECTS}\\d-Franklin-OS-local",
    "FRANKLINOPS_JCK_LAND_DEV_ROOT": f"{_CURSOR_PROJECTS}\\d-JCK-Land-Development",
}


def get_roots_from_env() -> dict[str, str]:
    """Build roots dict from env vars (used by ingestion, pilot, runners)."""
    roots: dict[str, str] = {}
    for m in CANONICAL_FOLDER_MAPPING:
        val = (os.getenv(m.env_var) or _DEFAULT_PATHS.get(m.env_var, "") or "").strip()
        if val:
            roots[m.source] = val
    return roots


def get_root_path(source: str) -> Optional[Path]:
    """Return resolved Path for a source, or None if not configured."""
    roots = get_roots_from_env()
    raw = roots.get(source)
    if not raw:
        return None
    p = Path(raw)
    return p.resolve() if p.exists() else None


# Risk thresholds for approval escalation (Phase 0)
# When an action exceeds these, escalate to human instead of auto-execute.
def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except Exception:
        return default


def get_risk_thresholds() -> dict[str, float]:
    """Risk thresholds for governance (money, commitments, etc.)."""
    return {
        "max_approval_amount": _env_float("FRANKLINOPS_RISK_MAX_APPROVAL_AMOUNT", 5000.0),
        "max_cost_per_mission": _env_float("FRANKLINOPS_MAX_COST_PER_MISSION", 1000.0),
    }
