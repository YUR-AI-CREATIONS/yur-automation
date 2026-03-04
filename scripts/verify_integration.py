#!/usr/bin/env python3
"""
FranklinOps + GROKSTMATE Integration Verification

Runs live simulations and tests to prove the integration works.
Output: scripts/verification_report.txt
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPORT_LINES: list[str] = []


def log(msg: str) -> None:
    print(msg)
    REPORT_LINES.append(msg)


def section(title: str) -> None:
    log("")
    log("=" * 70)
    log(title)
    log("=" * 70)


def result(name: str, ok: bool, detail: str = "") -> None:
    status = "✓ PASS" if ok else "✗ FAIL"
    log(f"  {status}  {name}")
    if detail:
        log(f"         {detail}")


def run_grokstmate_standalone() -> dict:
    """Test GROKSTMATE components directly (no FranklinOps)."""
    section("1. GROKSTMATE Standalone Tests")
    out: dict = {"cost_estimate": None, "project_plan": None, "errors": []}

    try:
        from grokstmate import CostEstimator, ProjectManager

        # Cost estimate
        estimator = CostEstimator(region="US", currency="USD")
        spec = {"name": "Verification Test", "type": "residential", "size": 2500, "complexity": "moderate"}
        est = estimator.estimate_project(spec)
        out["cost_estimate"] = est
        total = est.get("total_estimate", 0)
        result("CostEstimator", total > 0, f"total_estimate=${total:,.2f}")
    except Exception as e:
        out["errors"].append(f"CostEstimator: {e}")
        result("CostEstimator", False, str(e))

    try:
        pm = ProjectManager("verify_proj_001", "Verification Project")
        plan = pm.create_project_plan({"type": "residential", "size": 2500, "complexity": "moderate"})
        out["project_plan"] = plan
        tasks = plan.get("tasks", [])
        result("ProjectManager", len(tasks) > 0, f"{len(tasks)} tasks created")
    except Exception as e:
        out["errors"].append(f"ProjectManager: {e}")
        result("ProjectManager", False, str(e))

    return out


def run_integration_bridge() -> dict:
    """Test Integration Bridge (GROKSTMATE → FranklinOps)."""
    section("2. Integration Bridge Tests")

    out: dict = {"available": False, "estimate": None, "plan": None, "errors": []}

    try:
        from src.integration.bridge import IntegrationBridge, GROKSTMATE_AVAILABLE

        result("Bridge import", GROKSTMATE_AVAILABLE, "GROKSTMATE_AVAILABLE" if GROKSTMATE_AVAILABLE else "Not installed")
        out["available"] = GROKSTMATE_AVAILABLE

        if not GROKSTMATE_AVAILABLE:
            return out

        bridge = IntegrationBridge()
        spec = {"name": "Bridge Test", "type": "commercial", "size": 5000, "complexity": "moderate"}
        est = bridge.estimate_project(spec)
        out["estimate"] = est
        total = est.get("total_estimate", 0)
        result("Bridge.estimate_project", total > 0, f"total_estimate=${total:,.2f}")

        plan = bridge.create_project_plan("bridge_proj_001", "Bridge Project", {"type": "residential", "size": 2000})
        out["plan"] = plan
        tasks = plan.get("tasks", [])
        result("Bridge.create_project_plan", len(tasks) > 0, f"{len(tasks)} tasks")
    except Exception as e:
        out["errors"].append(str(e))
        result("Integration Bridge", False, str(e))

    return out


def run_governance_adapter() -> dict:
    """Test Governance Adapter (audit logging)."""
    section("3. Governance Adapter Tests (with Audit)")

    out: dict = {"estimate_logged": False, "audit_count": 0, "errors": []}

    try:
        from src.franklinops.settings import FranklinOpsSettings
        from src.franklinops.opsdb import OpsDB
        from src.franklinops.audit import AuditLogger
        from src.integration.bridge import IntegrationBridge, GROKSTMATE_AVAILABLE
        from src.integration.governance_adapter import GovernanceAdapter

        if not GROKSTMATE_AVAILABLE:
            result("Governance Adapter", False, "GROKSTMATE not installed")
            return out

        settings = FranklinOpsSettings()
        db = OpsDB(settings.db_path)
        audit = AuditLogger(db, settings.audit_jsonl_path)

        bridge = IntegrationBridge(db=db, audit=audit, approvals=None)
        adapter = GovernanceAdapter(bridge, audit=audit, approvals=None)

        # Before: count audit events
        before = db.conn.execute("SELECT COUNT(*) AS n FROM audit_events").fetchone()[0]

        # Run estimate (should log to audit)
        spec = {"name": "Governance Test", "type": "residential", "size": 3000, "complexity": "moderate"}
        adapter.estimate_project(spec, actor="verify_script")

        # After: count audit events
        after = db.conn.execute("SELECT COUNT(*) AS n FROM audit_events").fetchone()[0]
        out["audit_count"] = after - before
        out["estimate_logged"] = out["audit_count"] >= 1
        result("Governance Adapter (audit)", out["audit_count"] >= 1, f"+{out['audit_count']} audit events")

        db.close()
    except Exception as e:
        out["errors"].append(str(e))
        result("Governance Adapter", False, str(e))

    return out


def run_pilot_simulation() -> dict:
    """Run full FranklinOps pilot (includes GROKSTMATE phase)."""
    section("4. FranklinOps Pilot Simulation")

    out: dict = {"results": None, "grokstmate": None, "error": None}

    try:
        from src.franklinops.run_pilot import run_pilot

        r = run_pilot()
        out["results"] = r
        out["grokstmate"] = r.get("grokstmate")
        grok = out["grokstmate"] or {}

        if grok.get("available"):
            est = grok.get("grokstmate_estimate") or {}
            total = est.get("total_estimate", 0)
            result("Pilot run", True, "completed")
            result("GROKSTMATE phase", True, f"estimate=${total:,.2f}" if total else "estimate ran")
        else:
            result("Pilot run", True, "completed")
            result("GROKSTMATE phase", False, grok.get("skipped", grok.get("error", "unknown")))
    except Exception as e:
        out["error"] = str(e)
        result("Pilot run", False, str(e))

    return out


def run_grokstmate_async_tests() -> str:
    """Run GROKSTMATE integration tests (async)."""
    section("5. GROKSTMATE Async Tests (pytest-style)")

    try:
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(ROOT / "GROKSTMATE" / "tests" / "test_integration.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        out = proc.stdout + proc.stderr
        ok = proc.returncode == 0
        result("GROKSTMATE test_integration.py", ok, f"exit={proc.returncode}")
        if out:
            for line in out.strip().split("\n")[-8:]:
                log(f"    {line}")
        return out
    except Exception as e:
        result("GROKSTMATE test_integration.py", False, str(e))
        return ""


def main() -> int:
    section("FranklinOps + GROKSTMATE Integration Verification")
    log(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    log(f"Project root: {ROOT}")

    g1 = run_grokstmate_standalone()
    g2 = run_integration_bridge()
    g3 = run_governance_adapter()
    g4 = run_pilot_simulation()
    run_grokstmate_async_tests()

    section("Summary")
    passed = sum(1 for _ in REPORT_LINES if "✓ PASS" in _)
    failed = sum(1 for _ in REPORT_LINES if "✗ FAIL" in _)
    log(f"  Passed: {passed}")
    log(f"  Failed: {failed}")

    report_path = ROOT / "scripts" / "verification_report.txt"
    report_path.write_text("\n".join(REPORT_LINES), encoding="utf-8")
    log("")
    log(f"Report saved: {report_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())