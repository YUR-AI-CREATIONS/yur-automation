"""
Failure Collector — central aggregation of flow failures, exceptions, audit anomalies.

Purpose: IDENTIFY the problem. Every failure is recorded with trace_id, flow_id, error, timestamp.
Feeds: remedy report, forensic analysis.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FAILURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fabric" / "runs" / "failures"
FAILURES_DIR.mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_failure(
    *,
    flow_id: str,
    error: str,
    trace_id: str | None = None,
    tenant_id: str = "default",
    inp_summary: dict[str, Any] | None = None,
    component: str | None = None,
) -> str:
    """
    Record a failure. Returns failure_id.
    Stored in data/fabric/runs/failures/{date}/{failure_id}.json
    """
    from uuid import uuid4
    fid = uuid4().hex[:12]
    ts = _utcnow_iso()
    date_dir = FAILURES_DIR / ts[:10]
    date_dir.mkdir(parents=True, exist_ok=True)

    rec = {
        "failure_id": fid,
        "flow_id": flow_id,
        "error": error,
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "component": component or flow_id,
        "inp_summary": inp_summary or {},
        "recorded_at": ts,
    }
    path = date_dir / f"{fid}.json"
    path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return fid


def get_failures(
    *,
    flow_id: str | None = None,
    component: str | None = None,
    since_hours: float = 24.0,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Get recent failures. For remedy report."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    out = []
    for date_dir in sorted(FAILURES_DIR.iterdir(), reverse=True):
        if date_dir.is_dir() and len(out) < limit:
            for fp in date_dir.glob("*.json"):
                try:
                    rec = json.loads(fp.read_text(encoding="utf-8"))
                    ts = rec.get("recorded_at", "")
                    if ts and datetime.fromisoformat(ts.replace("Z", "+00:00")) < cutoff:
                        continue
                    if flow_id and rec.get("flow_id") != flow_id:
                        continue
                    if component and rec.get("component") != component:
                        continue
                    out.append(rec)
                    if len(out) >= limit:
                        break
                except Exception:
                    continue
    return out
