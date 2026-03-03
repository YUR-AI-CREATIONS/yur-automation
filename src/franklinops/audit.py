from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .opsdb import OpsDB


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLogger:
    """Append-only audit logger (SQLite + JSONL)."""

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
    ) -> str:
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
        }

        details_json = json.dumps(details, ensure_ascii=False, sort_keys=True)
        with self._db.tx() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (id, ts, actor, action, scope, entity_type, entity_id, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, ts, actor, action, scope, entity_type, entity_id, details_json),
            )

        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return event_id

