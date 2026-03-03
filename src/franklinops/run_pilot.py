"""
FranklinOps pilot runner: run all spokes in one pass.

Use for cron/scheduled runs:
  python -m src.franklinops.run_pilot

Or call POST /api/pilot/run from the API.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.franklinops.settings import FranklinOpsSettings
from src.franklinops.opsdb import OpsDB
from src.franklinops.audit import AuditLogger
from src.franklinops.approvals import ApprovalService, build_default_gate
from src.franklinops.autonomy import AutonomySettingsStore
from src.franklinops.doc_ingestion import ingest_roots
from src.franklinops.sales_spokes import SalesSpokes
from src.franklinops.finance_spokes import FinanceSpokes
from src.franklinops.integrations.trinity_sync import sync_trinity_leads


def run_pilot() -> dict:
    """Run ingest, sales inbound, pipeline, Trinity sync, finance AP, AR, forecast."""
    settings = FranklinOpsSettings()
    db = OpsDB(settings.db_path)
    audit = AuditLogger(db, settings.audit_jsonl_path)
    autonomy = AutonomySettingsStore(db, default_mode="shadow", default_scope=settings.default_governance_scope)
    gate = build_default_gate(
        authority_level=settings.default_authority_level,
        default_scope=settings.default_governance_scope,
        rate_limit_per_hour=settings.rate_limit_per_hour,
        max_cost_per_mission=settings.max_cost_per_mission,
    )
    approvals = ApprovalService(db, autonomy, gate)
    sales = SalesSpokes(db, audit, approvals)
    finance = FinanceSpokes(db, audit, approvals)

    results: dict = {}

    # Ingest
    roots = {
        "onedrive_projects": settings.onedrive_projects_root,
        "onedrive_bidding": settings.onedrive_bidding_root,
        "onedrive_attachments": settings.onedrive_attachments_root,
    }
    roots = {k: v for k, v in roots.items() if v}
    if roots:
        r = ingest_roots(db, audit, roots=roots)
        results["ingest"] = r.get("counts", {})
    else:
        results["ingest"] = {"skipped": "no roots configured"}

    # Sales inbound scan (folder-first for bidding root)
    r = sales.scan_bidding_folders(source="onedrive_bidding", limit_artifacts=5000)
    results["sales_bidding_folders"] = r.get("counts", {})
    # Optional keyword scan (can still catch true "ITB" emails)
    r = sales.scan_inbound_itbs(source="onedrive_bidding", limit=250)
    results["sales_inbound_itb_keywords"] = r.get("counts", {})

    # Sales pipeline refresh
    r = sales.refresh_pipeline_queue(horizon_days=21)
    results["sales_pipeline"] = r

    # Trinity sync (no-op if TRINITY_API_KEY not set)
    r = sync_trinity_leads(db, audit, limit=200)
    results["trinity_sync"] = r

    # Finance AP intake
    r = finance.scan_ap_intake(source="onedrive_attachments", limit=250)
    results["finance_ap"] = r

    # Finance AR reminders
    r = finance.run_ar_reminders(max_records=100, days_overdue=1)
    results["finance_ar"] = r

    # Finance cashflow import + forecast (creates alert tasks)
    results["finance_cashflow_import_latest"] = finance.import_latest_cashflow_waterfall(source="onedrive_projects")
    r = finance.forecast_cashflow(weeks=12, create_alert_tasks=True)
    results["finance_forecast"] = {"weeks": len(r.get("weeks", []))}

    audit.append(actor="system", action="pilot_run_complete", scope="internal", details=results)
    db.close()
    return results


if __name__ == "__main__":
    r = run_pilot()
    print("Pilot run complete:", r)
