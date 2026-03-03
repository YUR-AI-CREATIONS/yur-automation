from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .opsdb import OpsDB


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Handle trailing Z
        iso = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def approvals_stats(db: OpsDB, *, days: int = 7) -> dict[str, Any]:
    since = (utcnow() - timedelta(days=int(days))).isoformat()
    rows = db.conn.execute(
        """
        SELECT workflow, status, COUNT(1) AS n
        FROM approvals
        WHERE requested_at >= ?
        GROUP BY workflow, status
        """,
        (since,),
    ).fetchall()

    by_workflow: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    for r in rows:
        wf = r["workflow"]
        st = r["status"]
        n = int(r["n"] or 0)
        by_workflow.setdefault(wf, {})
        by_workflow[wf][st] = n
        totals[st] = totals.get(st, 0) + n

    pending = int(db.conn.execute("SELECT COUNT(1) AS n FROM approvals WHERE status = 'pending'").fetchone()["n"])
    return {"since": since, "totals": totals, "pending_now": pending, "by_workflow": by_workflow}


def time_saved_estimate_minutes(*, approvals_auto_approved: int, drafts_created: int = 0) -> int:
    # Conservative defaults; adjust as you calibrate with real observed time.
    # - auto-approval typically saves the "find + open + decide" loop
    # - draft creation saves an initial drafting pass
    return int(round(approvals_auto_approved * 2.0 + drafts_created * 1.0))


def tire_recommendations(db: OpsDB, *, days: int = 30, limit: int = 10) -> dict[str, Any]:
    """
    Prioritize automation based on where humans are spending time approving.
    """
    since = (utcnow() - timedelta(days=int(days))).isoformat()
    rows = db.conn.execute(
        """
        SELECT workflow, status, COUNT(1) AS n
        FROM approvals
        WHERE requested_at >= ?
        GROUP BY workflow, status
        """,
        (since,),
    ).fetchall()

    stats: dict[str, dict[str, int]] = {}
    for r in rows:
        wf = r["workflow"]
        st = r["status"]
        stats.setdefault(wf, {})
        stats[wf][st] = int(r["n"] or 0)

    scored: list[dict[str, Any]] = []
    for wf, st in stats.items():
        manual = st.get("pending", 0) + st.get("approved", 0) + st.get("denied", 0)
        auto = st.get("auto_approved", 0)
        score = manual * 2.0 - auto * 0.5
        scored.append({"workflow": wf, "manual": manual, "auto_approved": auto, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"since": since, "recommendations": scored[: int(limit)]}


def audit_action_counts(db: OpsDB, *, days: int = 7) -> dict[str, Any]:
    since = (utcnow() - timedelta(days=int(days))).isoformat()
    rows = db.conn.execute(
        """
        SELECT action, COUNT(1) AS n
        FROM audit_events
        WHERE ts >= ?
        GROUP BY action
        ORDER BY n DESC
        """,
        (since,),
    ).fetchall()
    return {"since": since, "actions": [{"action": r["action"], "count": int(r["n"] or 0)} for r in rows]}


def drafts_created_count(db: OpsDB, *, days: int = 7) -> int:
    """
    Count drafts created (sales outbound + finance AR reminders) from the audit log.
    """
    since = (utcnow() - timedelta(days=int(days))).isoformat()
    row = db.conn.execute(
        """
        SELECT COUNT(1) AS n
        FROM audit_events
        WHERE ts >= ?
          AND action IN ('sales_outbound_draft_created', 'ar_reminder_drafted')
        """,
        (since,),
    ).fetchone()
    return int(row["n"] or 0) if row else 0


def tasks_stats(db: OpsDB, *, days: int = 7, kind_limit: int = 25) -> dict[str, Any]:
    """
    Lightweight task KPIs for rollout monitoring.
    """
    since = (utcnow() - timedelta(days=int(days))).isoformat()
    open_now = int(
        db.conn.execute("SELECT COUNT(1) AS n FROM tasks WHERE status IN ('open','in_progress')").fetchone()["n"]
    )
    done_recent = int(
        db.conn.execute(
            "SELECT COUNT(1) AS n FROM tasks WHERE status = 'done' AND updated_at >= ?",
            (since,),
        ).fetchone()["n"]
    )
    by_kind_open_rows = db.conn.execute(
        """
        SELECT kind, COUNT(1) AS n
        FROM tasks
        WHERE status IN ('open','in_progress')
        GROUP BY kind
        ORDER BY n DESC
        LIMIT ?
        """,
        (int(kind_limit),),
    ).fetchall()
    by_kind_open = [{"kind": r["kind"], "open_count": int(r["n"] or 0)} for r in by_kind_open_rows]
    return {"since": since, "open_now": open_now, "done_recent": done_recent, "by_kind_open": by_kind_open}


def outbound_stats(db: OpsDB, *, days: int = 7) -> dict[str, Any]:
    """
    Outbound message KPIs across workflows (sales + finance).
    """
    since = (utcnow() - timedelta(days=int(days))).isoformat()
    by_workflow_status_rows = db.conn.execute(
        """
        SELECT workflow, status, COUNT(1) AS n
        FROM outbound_messages
        WHERE created_at >= ?
        GROUP BY workflow, status
        """,
        (since,),
    ).fetchall()
    by_workflow: dict[str, dict[str, int]] = {}
    for r in by_workflow_status_rows:
        wf = r["workflow"]
        st = r["status"]
        by_workflow.setdefault(wf, {})
        by_workflow[wf][st] = int(r["n"] or 0)

    sent_recent = int(
        db.conn.execute(
            "SELECT COUNT(1) AS n FROM outbound_messages WHERE status = 'sent' AND sent_at IS NOT NULL AND sent_at >= ?",
            (since,),
        ).fetchone()["n"]
    )
    pending_now = int(
        db.conn.execute(
            "SELECT COUNT(1) AS n FROM outbound_messages WHERE sent_at IS NULL AND status IN ('pending_approval','approved')",
        ).fetchone()["n"]
    )
    return {"since": since, "sent_recent": sent_recent, "pending_now": pending_now, "by_workflow": by_workflow}


def pilot_runs_count(db: OpsDB, *, days: int = 30) -> int:
    since = (utcnow() - timedelta(days=int(days))).isoformat()
    row = db.conn.execute(
        "SELECT COUNT(1) AS n FROM audit_events WHERE ts >= ? AND action = 'pilot_run_complete'",
        (since,),
    ).fetchone()
    return int(row["n"] or 0) if row else 0

