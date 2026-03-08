"""
Audit Spine — Append-only audit system for the Universal Spine.

Domain-agnostic audit logging. Accepts any DB with tx() or conn.
Consolidates patterns from src/franklinops/audit.py.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

__all__ = ["AuditSpine", "AuditEvent"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditEvent:
    """Audit event payload."""

    actor: str
    action: str
    details: dict[str, Any]
    scope: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    tenant_id: str = "default"

    def to_row(self) -> tuple[str, str, str, str, Optional[str], Optional[str], Optional[str], str, str]:
        """Serialize for INSERT."""
        event_id = uuid.uuid4().hex
        ts = _utcnow_iso()
        details_json = json.dumps(self.details, ensure_ascii=False, sort_keys=True)
        return (
            event_id,
            ts,
            self.actor,
            self.action,
            self.scope,
            self.entity_type,
            self.entity_id,
            details_json,
            self.tenant_id,
        )


class AuditSpine:
    """
    Append-only audit spine. Writes to DB and optionally JSONL.
    Accepts DB with tx() context manager (e.g. OpsDB) or conn attribute.
    """

    def __init__(
        self,
        db: Any,
        jsonl_path: Optional[Path] = None,
        tenant_resolver: Optional[Callable[[], str]] = None,
    ) -> None:
        """
        Args:
            db: DB with tx() yielding conn, or conn attribute with execute/commit.
            jsonl_path: Optional append-only JSONL file path.
            tenant_resolver: Optional callable() -> str for tenant_id.
        """
        self._db = db
        self._jsonl_path = Path(jsonl_path) if jsonl_path else None
        self._tenant_resolver = tenant_resolver or (lambda: "default")
        if self._jsonl_path:
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
        """
        Append an audit event. Returns event id.
        """
        tid = tenant_id or self._tenant_resolver()
        event = AuditEvent(
            actor=actor,
            action=action,
            details=details,
            scope=scope,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tid,
        )
        event_id, ts, *rest = event.to_row()
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

        # DB insert
        if hasattr(self._db, "tx"):
            with self._db.tx() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_events (id, ts, actor, action, scope, entity_type, entity_id, details_json, tenant_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, ts, *rest),
                )
        else:
            conn = getattr(self._db, "conn", self._db)
            conn.execute(
                """
                INSERT INTO audit_events (id, ts, actor, action, scope, entity_type, entity_id, details_json, tenant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, ts, *rest),
            )
            if hasattr(conn, "commit"):
                conn.commit()

        # JSONL append
        if self._jsonl_path:
            with open(self._jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return event_id
