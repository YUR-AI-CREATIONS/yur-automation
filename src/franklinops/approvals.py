from __future__ import annotations

import hmac
import json
import os
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .autonomy import AutonomySettingsStore
from .opsdb import OpsDB

from ..core.autonomy_gate import AutonomyGate, AuthorityLevel, GovernanceScope


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_signature_hex(*, secret: str, blake_birthmark: str, intent: str, timestamp: str) -> str:
    canonical_payload = json.dumps(
        {"blake_birthmark": blake_birthmark, "intent": intent, "timestamp": timestamp},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), canonical_payload, digestmod="sha256").digest().hex()


def create_evidence(*, blake_birthmark: str, intent: str) -> dict[str, Any]:
    ts = utcnow_iso()
    secret = (os.getenv("TRINITY_SIGNING_SECRET") or "").strip()
    evidence: dict[str, Any] = {"blake_birthmark": blake_birthmark, "intent": intent, "timestamp": ts}
    if secret:
        evidence["signature"] = _evidence_signature_hex(
            secret=secret,
            blake_birthmark=blake_birthmark,
            intent=intent,
            timestamp=ts,
        )
    else:
        evidence["signature"] = ""
    return evidence


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except Exception:
        return default


def _extract_amount_cents(payload: dict[str, Any]) -> Optional[int]:
    """
    Best-effort extraction of a money amount from a payload.

    This is used to enforce risk thresholds (e.g., large AP invoices should
    never auto-execute even in assist/autopilot modes).
    """
    for k in ("amount_cents", "amountCents", "total_cents", "totalCents"):
        v = payload.get(k)
        if v is None:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            return int(v)
        if isinstance(v, float):
            return int(round(float(v)))
        if isinstance(v, str):
            s = v.strip()
            if not s:
                continue
            if s.isdigit():
                try:
                    return int(s)
                except Exception:
                    continue
            s2 = s.replace("$", "").replace(",", "")
            try:
                return int(round(float(s2) * 100))
            except Exception:
                continue

    # Common alternate key: "amount" in dollars
    v2 = payload.get("amount")
    if isinstance(v2, (int, float)) and not isinstance(v2, bool):
        return int(round(float(v2) * 100))
    if isinstance(v2, str):
        s = v2.strip()
        if s:
            s2 = s.replace("$", "").replace(",", "")
            try:
                return int(round(float(s2) * 100))
            except Exception:
                return None
    return None


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    workflow: str
    scope: str
    mode_at_request: str
    requested_by: str
    requested_at: str
    status: str
    payload: dict[str, Any]
    evidence: Optional[dict[str, Any]]
    decision_by: Optional[str]
    decision_at: Optional[str]
    decision_notes: Optional[str]


class ApprovalService:
    def __init__(
        self,
        db: OpsDB,
        autonomy_store: AutonomySettingsStore,
        gate: AutonomyGate,
    ):
        self._db = db
        self._autonomy = autonomy_store
        self._gate = gate

    def request(
        self,
        *,
        workflow: str,
        requested_by: str,
        payload: dict[str, Any],
        intent: str,
        scope: Optional[str] = None,
        blake_birthmark: str = "N/A",
        cost_estimate: float = 0.0,
    ) -> tuple[ApprovalRecord, str]:
        """
        Returns: (record, gate_reason)
        - record.status is one of: pending | auto_approved
        """
        autonomy = self._autonomy.get_or_create(workflow)
        use_scope = scope or autonomy.scope

        evidence = create_evidence(blake_birthmark=blake_birthmark, intent=intent)
        mission = {
            "id": f"approval_request:{workflow}:{uuid.uuid4().hex[:12]}",
            "prompt": intent,
            "scope": use_scope,
            "provider": "franklinops",
        }

        if autonomy.mode == "shadow":
            can_execute, reason = (False, "shadow mode: drafts only")
        else:
            can_execute, reason = self._gate.can_execute(mission, evidence=evidence, cost_estimate=cost_estimate)

            # Risk gating: large-dollar actions must escalate even if the gate allows auto-execution.
            if can_execute:
                max_amount_usd = _env_float("FRANKLINOPS_RISK_MAX_APPROVAL_AMOUNT", 5000.0)
                amt_cents = _extract_amount_cents(payload)
                if amt_cents is not None and max_amount_usd > 0:
                    amt_usd = float(amt_cents) / 100.0
                    if amt_usd > max_amount_usd:
                        can_execute = False
                        reason = f"risk threshold exceeded: ${amt_usd:,.2f} > ${max_amount_usd:,.2f}"

        approval_id = uuid.uuid4().hex
        requested_at = utcnow_iso()
        status = "auto_approved" if can_execute else "pending"

        with self._db.tx() as conn:
            conn.execute(
                """
                INSERT INTO approvals (
                  id, workflow, scope, mode_at_request, requested_by, requested_at, status,
                  payload_json, evidence_json, decision_by, decision_at, decision_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval_id,
                    workflow,
                    use_scope,
                    autonomy.mode,
                    requested_by,
                    requested_at,
                    status,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(evidence, ensure_ascii=False),
                    "autonomy_gate" if status == "auto_approved" else None,
                    requested_at if status == "auto_approved" else None,
                    reason if status == "auto_approved" else None,
                ),
            )

            # Autopilot sampled audits: create occasional human review tasks even when auto-approved.
            if status == "auto_approved" and autonomy.mode == "autopilot":
                raw = (os.getenv("FRANKLINOPS_AUTOPILOT_AUDIT_SAMPLE_RATE") or "0.10").strip()
                try:
                    rate = float(raw)
                except Exception:
                    rate = 0.10
                rate = max(0.0, min(rate, 1.0))

                if rate > 0.0 and random.random() < rate:
                    task_id = uuid.uuid4().hex
                    conn.execute(
                        """
                        INSERT INTO tasks (
                          id, kind, title, description, status, priority,
                          related_entity_type, related_entity_id,
                          created_at, updated_at, due_at, evidence_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            task_id,
                            "audit.sample",
                            f"Sample audit: {workflow}",
                            "Autopilot auto-approved this action. Review evidence/payload for correctness.",
                            "open",
                            5,
                            "approval",
                            approval_id,
                            requested_at,
                            requested_at,
                            None,
                            json.dumps(
                                {
                                    "workflow": workflow,
                                    "scope": use_scope,
                                    "intent": intent,
                                    "gate_reason": reason,
                                    "payload": payload,
                                    "evidence": evidence,
                                },
                                ensure_ascii=False,
                            ),
                        ),
                    )

        record = ApprovalRecord(
            id=approval_id,
            workflow=workflow,
            scope=use_scope,
            mode_at_request=autonomy.mode,
            requested_by=requested_by,
            requested_at=requested_at,
            status=status,
            payload=payload,
            evidence=evidence,
            decision_by="autonomy_gate" if status == "auto_approved" else None,
            decision_at=requested_at if status == "auto_approved" else None,
            decision_notes=reason if status == "auto_approved" else None,
        )
        return record, reason

    def list(self, *, status: Optional[str] = None, limit: int = 200) -> list[ApprovalRecord]:
        params: list[Any] = []
        sql = """
        SELECT
          id, workflow, scope, mode_at_request, requested_by, requested_at, status,
          payload_json, evidence_json, decision_by, decision_at, decision_notes
        FROM approvals
        """
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY requested_at DESC LIMIT ?"
        params.append(limit)

        rows = self._db.conn.execute(sql, params).fetchall()
        out: list[ApprovalRecord] = []
        for r in rows:
            out.append(
                ApprovalRecord(
                    id=r["id"],
                    workflow=r["workflow"],
                    scope=r["scope"],
                    mode_at_request=r["mode_at_request"],
                    requested_by=r["requested_by"],
                    requested_at=r["requested_at"],
                    status=r["status"],
                    payload=json.loads(r["payload_json"]) if r["payload_json"] else {},
                    evidence=json.loads(r["evidence_json"]) if r["evidence_json"] else None,
                    decision_by=r["decision_by"],
                    decision_at=r["decision_at"],
                    decision_notes=r["decision_notes"],
                )
            )
        return out

    def decide(
        self,
        *,
        approval_id: str,
        decision: str,  # approved | denied
        decision_by: str,
        notes: str = "",
    ) -> ApprovalRecord:
        if decision not in {"approved", "denied"}:
            raise ValueError("decision must be 'approved' or 'denied'")

        decision_at = utcnow_iso()
        with self._db.tx() as conn:
            conn.execute(
                """
                UPDATE approvals
                SET status = ?, decision_by = ?, decision_at = ?, decision_notes = ?
                WHERE id = ? AND status = 'pending'
                """,
                (decision, decision_by, decision_at, notes, approval_id),
            )

        row = self._db.conn.execute(
            """
            SELECT
              id, workflow, scope, mode_at_request, requested_by, requested_at, status,
              payload_json, evidence_json, decision_by, decision_at, decision_notes
            FROM approvals WHERE id = ?
            """,
            (approval_id,),
        ).fetchone()
        if not row:
            raise KeyError(f"approval not found: {approval_id}")

        return ApprovalRecord(
            id=row["id"],
            workflow=row["workflow"],
            scope=row["scope"],
            mode_at_request=row["mode_at_request"],
            requested_by=row["requested_by"],
            requested_at=row["requested_at"],
            status=row["status"],
            payload=json.loads(row["payload_json"]) if row["payload_json"] else {},
            evidence=json.loads(row["evidence_json"]) if row["evidence_json"] else None,
            decision_by=row["decision_by"],
            decision_at=row["decision_at"],
            decision_notes=row["decision_notes"],
        )


def build_default_gate(*, authority_level: str, default_scope: str, rate_limit_per_hour: int, max_cost_per_mission: float) -> AutonomyGate:
    try:
        level = AuthorityLevel[authority_level]
    except KeyError:
        level = AuthorityLevel.SEMI_AUTO

    try:
        scope = GovernanceScope(default_scope)
    except Exception:
        scope = GovernanceScope.INTERNAL

    return AutonomyGate(
        authority_level=level,
        default_scope=scope,
        rate_limit_per_hour=rate_limit_per_hour,
        max_cost_per_mission=max_cost_per_mission,
    )

