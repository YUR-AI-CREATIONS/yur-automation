"""
FranklinOps for Construction — Real-world flows.

Pay application tracking, lien rights, document evidence.
Built for how American construction actually runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    return str(v).strip() or default


def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def pay_app_tracker(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Pay application tracker — status, amounts, deadlines.
    Zero-error: always returns a dict.
    """
    try:
        action = _safe_str(inp.get("action"), "status")
        project = _safe_str(inp.get("project"), "default")
        pay_apps = inp.get("pay_apps") or []
        if isinstance(pay_apps, dict):
            pay_apps = [pay_apps]

        if action == "status":
            # Summarize pay app status
            submitted = sum(1 for p in pay_apps if _safe_str(p.get("status")) in ("submitted", "pending"))
            approved = sum(1 for p in pay_apps if _safe_str(p.get("status")) == "approved")
            paid = sum(1 for p in pay_apps if _safe_str(p.get("status")) == "paid")
            overdue = sum(1 for p in pay_apps if p.get("overdue") is True)
            total_amount = sum(_safe_float(p.get("amount")) for p in pay_apps)
            unpaid_amount = sum(_safe_float(p.get("amount")) for p in pay_apps if _safe_str(p.get("status")) != "paid")

            return {
                "ok": True,
                "flow_id": "pay_app_tracker",
                "project": project,
                "summary": {
                    "total_apps": len(pay_apps),
                    "submitted": submitted,
                    "approved": approved,
                    "paid": paid,
                    "overdue": overdue,
                    "total_amount": round(total_amount, 2),
                    "unpaid_amount": round(unpaid_amount, 2),
                },
                "timestamp": _utcnow(),
            }

        if action == "add":
            # Add a pay app (demo — in real use would persist)
            app = inp.get("pay_app") or {}
            num = _safe_str(app.get("number"), "1")
            amount = _safe_float(app.get("amount"), 0)
            status = _safe_str(app.get("status"), "submitted")
            due_date = _safe_str(app.get("due_date"), "")
            return {
                "ok": True,
                "flow_id": "pay_app_tracker",
                "action": "add",
                "pay_app": {
                    "number": num,
                    "amount": amount,
                    "status": status,
                    "due_date": due_date,
                    "added_at": _utcnow(),
                },
                "message": f"Pay app {num} recorded (${amount:,.2f}, {status})",
                "timestamp": _utcnow(),
            }

        if action == "lien_deadline":
            # Lien deadline calculator (days from last furnishing)
            last_furnish = _safe_str(inp.get("last_furnish_date"), "")
            state = _safe_str(inp.get("state"), "TX")
            # Simplified: 90 days typical for mechanics lien
            days = 90
            return {
                "ok": True,
                "flow_id": "pay_app_tracker",
                "action": "lien_deadline",
                "last_furnish_date": last_furnish,
                "state": state,
                "lien_deadline_days": days,
                "message": f"Consult state law for {state}. Typical lien deadline: {days} days from last furnishing.",
                "timestamp": _utcnow(),
            }

        return {
            "ok": True,
            "flow_id": "pay_app_tracker",
            "action": action,
            "message": f"Unknown action: {action}. Use status, add, or lien_deadline.",
            "timestamp": _utcnow(),
        }

    except Exception as e:
        return {
            "ok": False,
            "flow_id": "pay_app_tracker",
            "error": str(e),
            "timestamp": _utcnow(),
        }


def construction_dashboard(inp: dict[str, Any]) -> dict[str, Any]:
    """
    Construction dashboard — one view of projects, pay apps, documents.
    Zero-error: always returns a dict.
    """
    try:
        projects = inp.get("projects") or []
        if isinstance(projects, dict):
            projects = [projects]

        total_value = sum(_safe_float(p.get("contract_value")) for p in projects)
        total_billed = sum(_safe_float(p.get("billed_to_date")) for p in projects)
        total_received = sum(_safe_float(p.get("received_to_date")) for p in projects)
        outstanding = total_billed - total_received

        return {
            "ok": True,
            "flow_id": "construction_dashboard",
            "summary": {
                "project_count": len(projects),
                "total_contract_value": round(total_value, 2),
                "total_billed": round(total_billed, 2),
                "total_received": round(total_received, 2),
                "outstanding_receivables": round(outstanding, 2),
            },
            "projects": [
                {
                    "name": _safe_str(p.get("name"), "Unnamed"),
                    "contract_value": _safe_float(p.get("contract_value")),
                    "billed": _safe_float(p.get("billed_to_date")),
                    "received": _safe_float(p.get("received_to_date")),
                }
                for p in projects[:20]
            ],
            "timestamp": _utcnow(),
        }

    except Exception as e:
        return {
            "ok": False,
            "flow_id": "construction_dashboard",
            "error": str(e),
            "timestamp": _utcnow(),
        }
