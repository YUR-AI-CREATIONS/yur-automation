from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .opsdb import OpsDB

try:
    from ..core.tenant import get_tenant_id
except ImportError:
    def get_tenant_id() -> str:
        return "default"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLogger:
    """Append-only audit logger (SQLite + JSONL). Tenant-scoped for enterprise multi-tenancy."""

    def __init__(self, db: OpsDB, jsonl_path: Path):
        self._db = db
        self._jsonl_path = Path(jsonl_path)
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        actor: str,
        action: str,
        details: dict[str, Any],
        scope: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> str:
        tid = tenant_id or get_tenant_id()
        event_id = uuid.uuid4().hex
        ts = utcnow_iso()
        row = {
            "id": event_id,
            "ts": ts,
            "actor": actor,
            "action": action,
            "scope": scope,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
            "tenant_id": tid,
        }

        details_json = json.dumps(details, ensure_ascii=False, sort_keys=True)
        with self._db.tx() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (id, ts, actor, action, scope, entity_type, entity_id, details_json, tenant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, ts, actor, action, scope, entity_type, entity_id, details_json, tid),
            )

        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return event_id

    def get_retention_days(self, tenant_id: Optional[str] = None) -> int:
        """Get audit retention days for tenant (from tenants table or default 365)."""
        tid = tenant_id or get_tenant_id()
        try:
            row = self._db.conn.execute(
                "SELECT retention_days FROM tenants WHERE id = ?", (tid,)
            ).fetchone()
            return int(row["retention_days"]) if row else 365
        except Exception:
            return 365

    def list(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List audit events, optionally filtered by tenant."""
        tid = tenant_id or get_tenant_id()
        rows = self._db.conn.execute(
            """
            SELECT id, ts, actor, action, scope, entity_type, entity_id, details_json, tenant_id
            FROM audit_events
            WHERE tenant_id = ? OR ? = ''
            ORDER BY ts DESC
            LIMIT ? OFFSET ?
            """,
            (tid, tid, limit, offset),
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "ts": r["ts"],
                "actor": r["actor"],
                "action": r["action"],
                "scope": r["scope"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "details": json.loads(r["details_json"] or "{}"),
                "tenant_id": r.get("tenant_id") or "default",
            })
        return out

