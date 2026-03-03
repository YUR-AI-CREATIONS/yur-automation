from __future__ import annotations

"""
SalesSpokes runner (polling "watcher") for FranklinOpsHub.

This is a lightweight, dependency-free alternative to filesystem watchers:
- periodically runs ingestion on configured roots
- scans inbound ITBs to create leads/opportunities/tasks
- refreshes pipeline queue tasks
- optionally sends any approved outbound messages

Run:
  python -m src.franklinops.sales_runner --once
  python -m src.franklinops.sales_runner --interval-sec 300
"""

import argparse
import time
from typing import Any

from .approvals import ApprovalService, build_default_gate
from .audit import AuditLogger
from .autonomy import AutonomySettingsStore
from .doc_ingestion import ingest_roots
from .opsdb import OpsDB
from .sales_spokes import SalesSpokes
from .settings import FranklinOpsSettings


def run_sales_cycle(*, send_ready: bool = True, inbound_limit: int = 250) -> dict[str, Any]:
    settings = FranklinOpsSettings()
    db = OpsDB(settings.db_path)
    audit = AuditLogger(db, settings.audit_jsonl_path)

    autonomy = AutonomySettingsStore(
        db,
        default_mode="shadow",
        default_scope=settings.default_governance_scope,
    )
    gate = build_default_gate(
        authority_level=settings.default_authority_level,
        default_scope=settings.default_governance_scope,
        rate_limit_per_hour=settings.rate_limit_per_hour,
        max_cost_per_mission=settings.max_cost_per_mission,
    )
    approvals = ApprovalService(db, autonomy, gate)
    sales = SalesSpokes(db, audit, approvals)

    roots = {
        "onedrive_projects": settings.onedrive_projects_root,
        "onedrive_bidding": settings.onedrive_bidding_root,
        "onedrive_attachments": settings.onedrive_attachments_root,
    }

    out: dict[str, Any] = {}
    try:
        out["ingest"] = ingest_roots(db, audit, roots=roots)
        # Folder-first scan is more reliable for real bid packages (plan sets + estimate sheets).
        out["bidding_folders"] = sales.scan_bidding_folders(source="onedrive_bidding", limit_artifacts=5000)
        # Keyword scan can still catch true ITB emails.
        out["inbound_scan"] = sales.scan_inbound_itbs(source="onedrive_bidding", limit=int(inbound_limit))
        out["pipeline_refresh"] = sales.refresh_pipeline_queue(horizon_days=21)
        if send_ready:
            out["send_ready"] = sales.send_ready_outbound(limit=50, actor="sales_runner")
        audit.append(actor="system", action="sales_runner_cycle_complete", scope="internal", details={"send_ready": bool(send_ready)})
        return out
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="FranklinOps SalesSpokes polling runner")
    ap.add_argument("--once", action="store_true", help="Run one cycle then exit")
    ap.add_argument("--interval-sec", type=int, default=300, help="Poll interval seconds (default 300)")
    ap.add_argument("--no-send", action="store_true", help="Do not send approved outbound messages")
    ap.add_argument("--inbound-limit", type=int, default=250, help="Max artifacts to scan per cycle")
    args = ap.parse_args()

    send_ready = not bool(args.no_send)
    interval = max(10, int(args.interval_sec))

    while True:
        res = run_sales_cycle(send_ready=send_ready, inbound_limit=int(args.inbound_limit))
        print("[SalesRunner] cycle complete:", {k: (v.get("counts") if isinstance(v, dict) and "counts" in v else v) for k, v in res.items()})
        if args.once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()

