"""
Trinity Superagents sync: pull leads from Trinity API into FranklinOps OpsDB.

When TRINITY_API_KEY is set, this syncs leads from the Trinity backend
into sales_leads so SalesSpokes can use them for governed outbound.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..audit import AuditLogger
from ..opsdb import OpsDB


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def sync_trinity_leads(
    db: OpsDB,
    audit: AuditLogger,
    *,
    base_url: str | None = None,
    api_key: Optional[str] = None,
    limit: int = 200,
) -> dict[str, Any]:
    """
    Pull leads from Trinity API and upsert into sales_leads.
    Returns counts: fetched, created, updated, skipped.
    """
    api_key = (api_key or os.getenv("TRINITY_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "error": "TRINITY_API_KEY not set", "fetched": 0, "created": 0, "updated": 0, "skipped": 0}

    url = (base_url or os.getenv("TRINITY_API_BASE_URL", "https://yur-ai-api.onrender.com")).strip()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{url.rstrip('/')}/api/leads",
                headers=headers,
                params={"limit": limit} if limit else {},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        audit.append(
            actor="system",
            action="trinity_sync_error",
            scope="internal",
            details={"error": str(e)},
        )
        return {"ok": False, "error": str(e), "fetched": 0, "created": 0, "updated": 0, "skipped": 0}

    # Handle various response shapes: list, or {data: [...]}, or single lead
    leads_raw: list[dict[str, Any]] = []
    if isinstance(data, list):
        leads_raw = data
    elif isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            leads_raw = data["data"]
        elif "id" in data and data.get("email"):
            leads_raw = [data]
        elif "leads" in data and isinstance(data["leads"], list):
            leads_raw = data["leads"]

    created = 0
    updated = 0
    skipped = 0

    for raw in leads_raw[: int(limit)]:
        email = _norm_email(raw.get("email") or "")
        if not email:
            skipped += 1
            continue

        name = (raw.get("name") or "").strip() or None
        company = (raw.get("company") or "").strip() or "Unknown"
        if email and "@" in email and not company:
            company = email.split("@", 1)[1]
        company = (company or "Unknown").strip()[:200]
        phone = (raw.get("phone") or raw.get("metadata", {}).get("phone") or "").strip() or None
        trinity_id = str(raw.get("id") or "").strip()

        existing = db.conn.execute(
            "SELECT id, company, phone, metadata_json FROM sales_leads WHERE email = ? LIMIT 1",
            (email,),
        ).fetchone()

        now = utcnow_iso()
        meta = {"trinity_id": trinity_id, "trinity_synced_at": now, "source": "trinity_sync"}

        if existing:
            # Opportunistic update
            old_meta = json.loads(existing["metadata_json"]) if existing["metadata_json"] else {}
            old_meta.update(meta)
            with db.tx() as conn:
                conn.execute(
                    """
                    UPDATE sales_leads
                    SET company = COALESCE(NULLIF(?, ''), company),
                        phone = COALESCE(NULLIF(?, ''), phone),
                        name = COALESCE(NULLIF(?, ''), name),
                        updated_at = ?,
                        metadata_json = ?
                    WHERE id = ?
                    """,
                    (company, phone, name, now, json.dumps(old_meta, ensure_ascii=False), existing["id"]),
                )
            updated += 1
        else:
            lead_id = uuid.uuid4().hex
            with db.tx() as conn:
                conn.execute(
                    """
                    INSERT INTO sales_leads (
                      id, name, company, email, phone,
                      status, suppressed, source,
                      created_at, updated_at, last_contacted_at, notes, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lead_id,
                        name,
                        company,
                        email,
                        phone,
                        "new",
                        0,
                        "trinity_sync",
                        now,
                        now,
                        None,
                        None,
                        json.dumps(meta, ensure_ascii=False),
                    ),
                )
            created += 1
            audit.append(
                actor="system",
                action="trinity_lead_synced",
                scope="internal",
                entity_type="sales_lead",
                entity_id=lead_id,
                details={"email": email, "company": company, "trinity_id": trinity_id},
            )

    audit.append(
        actor="system",
        action="trinity_sync_complete",
        scope="internal",
        details={"fetched": len(leads_raw), "created": created, "updated": updated, "skipped": skipped},
    )
    return {
        "ok": True,
        "fetched": len(leads_raw),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }
