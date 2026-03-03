from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .opsdb import OpsDB


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkflowAutonomy:
    workflow: str
    mode: str  # shadow | assist | autopilot
    scope: str  # internal | external_low | external_medium | external_high | restricted
    updated_at: str


class AutonomySettingsStore:
    def __init__(self, db: OpsDB, *, default_mode: str = "shadow", default_scope: str = "internal"):
        self._db = db
        self._default_mode = default_mode
        self._default_scope = default_scope

    def get_or_create(self, workflow: str) -> WorkflowAutonomy:
        row = self._db.conn.execute(
            "SELECT workflow, mode, scope, updated_at FROM autonomy_settings WHERE workflow = ?",
            (workflow,),
        ).fetchone()
        if row:
            return WorkflowAutonomy(
                workflow=row["workflow"],
                mode=row["mode"],
                scope=row["scope"],
                updated_at=row["updated_at"],
            )

        now = utcnow_iso()
        with self._db.tx() as conn:
            conn.execute(
                """
                INSERT INTO autonomy_settings (workflow, mode, scope, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (workflow, self._default_mode, self._default_scope, now),
            )
        return WorkflowAutonomy(workflow=workflow, mode=self._default_mode, scope=self._default_scope, updated_at=now)

    def set(self, workflow: str, *, mode: str, scope: Optional[str] = None) -> WorkflowAutonomy:
        current = self.get_or_create(workflow)
        new_scope = scope or current.scope
        now = utcnow_iso()
        with self._db.tx() as conn:
            conn.execute(
                """
                INSERT INTO autonomy_settings (workflow, mode, scope, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workflow) DO UPDATE SET
                  mode=excluded.mode,
                  scope=excluded.scope,
                  updated_at=excluded.updated_at
                """,
                (workflow, mode, new_scope, now),
            )
        return WorkflowAutonomy(workflow=workflow, mode=mode, scope=new_scope, updated_at=now)

    def list_all(self) -> list[WorkflowAutonomy]:
        rows = self._db.conn.execute(
            "SELECT workflow, mode, scope, updated_at FROM autonomy_settings ORDER BY workflow ASC"
        ).fetchall()
        return [
            WorkflowAutonomy(
                workflow=r["workflow"],
                mode=r["mode"],
                scope=r["scope"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

