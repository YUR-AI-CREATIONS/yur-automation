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


# Canonical folder mapping per FranklinOps plan:
# 02BIDDING → new opportunities (ITBs, contacts, RFQs)
# 01PROJECTS → active work (project docs, submittals)
# Attachments → invoices, submittals, misc paperwork
CANONICAL_FOLDER_MAPPING: tuple[FolderMapping, ...] = (
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
)


def get_roots_from_env() -> dict[str, str]:
    """Build roots dict from env vars (used by ingestion, pilot, runners)."""
    roots: dict[str, str] = {}
    for m in CANONICAL_FOLDER_MAPPING:
        val = (os.getenv(m.env_var) or "").strip()
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
