from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Optional

from .approvals import ApprovalService
from .audit import AuditLogger
from .outbound_email import OutboundEmailSender
from .opsdb import OpsDB


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?x)(?:\+?1\s*)?(?:\(\s*\d{3}\s*\)|\d{3})[\s.-]*\d{3}[\s.-]*\d{4}")


ITB_KEYWORDS = {
    "invitation to bid",
    "invite to bid",
    "itb",
    "bid due",
    "bids due",
    "request for proposal",
    "rfp",
    "bid package",
    "plans and specs",
    "addendum",
}

# Folder naming patterns often include a due date, e.g. "PROJECT - DUE 2.1.26"
_RE_FOLDER_DUE = re.compile(r"(?i)\b(?:bid\s*due|due)\s*[:\-]?\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})\b")


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(float(raw.strip()))
    except Exception:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def _safe_json_loads(raw: object) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def parse_eml_headers(extracted_text: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in (extracted_text or "").splitlines():
        if not line.strip():
            break
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().lower()
        v = v.strip()
        if k and v and k not in headers:
            headers[k] = v
    return headers


def extract_emails(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in EMAIL_RE.finditer(text or ""):
        e = _norm_email(m.group(0))
        if not e or e in seen:
            continue
        seen.add(e)
        out.append(e)
    return out


def extract_phone(text: str) -> str:
    m = PHONE_RE.search(text or "")
    return (m.group(0).strip() if m else "")


def looks_like_itb(text: str, path: str) -> bool:
    blob = f"{path}\\n{text}".lower()
    return any(k in blob for k in ITB_KEYWORDS)


def _first_match_group(text: str, pattern: str) -> str:
    m = re.search(pattern, text or "", flags=re.IGNORECASE | re.MULTILINE)
    if not m:
        return ""
    for i in range(1, m.lastindex + 1 if m.lastindex else 2):
        g = (m.group(i) or "").strip()
        if g:
            return g
    return ""


def extract_project_name(text: str, *, fallback: str) -> str:
    # Common ITB patterns
    v = _first_match_group(text, r"^(?:project|job(?:\\s*name)?|project\\s*name)\\s*[:\\-]\\s*(.+)$")
    if v:
        return v[:200]
    v = _first_match_group(text, r"^(?:subject)\\s*[:\\-]\\s*(.+)$")
    if v:
        return v[:200]
    return (fallback or "Unknown Project")[:200]


def _parse_date_iso(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    try:
        from dateutil import parser as date_parser  # type: ignore

        dt = date_parser.parse(s, fuzzy=True)
        return dt.date().isoformat()
    except Exception:
        # Try ISO-ish fallback
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            return ""


def extract_bid_due_date(text: str) -> str:
    raw = _first_match_group(
        text,
        r"^(?:bid\\s*due|bids\\s*due|due\\s*date|proposal\\s*due|bid\\s*date)\\s*[:\\-]\\s*(.+)$",
    )
    if raw:
        return _parse_date_iso(raw)
    # Slightly fuzzier: "Bid Due 3/15/26"
    raw = _first_match_group(text, r"\\bbid\\s*due\\b\\s*[:\\-]?\\s*(.+)$")
    if raw:
        return _parse_date_iso(raw)
    return ""


@dataclass(frozen=True)
class InboundScanCounts:
    scanned: int
    created_leads: int
    created_opportunities: int
    created_tasks: int
    skipped_existing: int
    skipped_not_match: int
    errors: int


class SalesSpokes:
    """
    SalesSpokes (JCK) — inbound lead capture + governed outbound + pipeline hygiene.

    Design goals:
    - Local-first: persists to OpsDB, uses AuditLogger + ApprovalService for governance.
    - Idempotent: safe to re-run scans without duplicating entities.
    - Dependency-light: regex + heuristics for MVP extraction.
    """

    WORKFLOW_OUTBOUND_EMAIL = "sales_outbound_email"

    def __init__(self, db: OpsDB, audit: AuditLogger, approvals: ApprovalService, emailer: Optional[OutboundEmailSender] = None):
        self._db = db
        self._audit = audit
        self._approvals = approvals
        self._emailer = emailer or OutboundEmailSender()

    def scan_inbound_itbs(self, *, source: str = "onedrive_bidding", limit: int = 250) -> dict[str, Any]:
        rows = self._db.conn.execute(
            """
            SELECT id, path, extracted_text, metadata_json, ingested_at, status
            FROM artifacts
            WHERE source = ? AND status = 'ingested'
            ORDER BY ingested_at DESC
            LIMIT ?
            """,
            (source, int(limit)),
        ).fetchall()

        created_leads = 0
        created_opps = 0
        created_tasks = 0
        skipped_existing = 0
        skipped_not_match = 0
        errors = 0

        for r in rows:
            artifact_id = r["id"]
            rel_path = r["path"] or ""
            text = r["extracted_text"] or ""
            meta = _safe_json_loads(r["metadata_json"])

            if not looks_like_itb(text, rel_path):
                skipped_not_match += 1
                continue

            # Idempotency: if an opportunity already references this artifact, skip.
            existing = self._db.conn.execute(
                "SELECT id FROM sales_opportunities WHERE source_artifact_id = ? LIMIT 1",
                (artifact_id,),
            ).fetchone()
            if existing:
                skipped_existing += 1
                continue

            try:
                headers = parse_eml_headers(text)
                from_name, from_email = parseaddr(headers.get("from", ""))
                emails = extract_emails(text)
                primary_email = _norm_email(from_email) or (emails[0] if emails else "")
                phone = extract_phone(text)

                company = ""
                if from_name and from_name.strip() and from_name.strip().lower() != primary_email:
                    company = from_name.strip()
                elif primary_email and "@" in primary_email:
                    company = primary_email.split("@", 1)[1]
                company = (company or "Unknown").strip()[:200]

                contact_name = (from_name or "").strip()
                if not contact_name and primary_email:
                    contact_name = primary_email.split("@", 1)[0].replace(".", " ").title()
                contact_name = contact_name[:200] if contact_name else None

                fallback_project = Path(rel_path).stem if rel_path else "Unknown Project"
                project_name = extract_project_name(text, fallback=fallback_project)
                bid_due = extract_bid_due_date(text)

                with self._db.tx() as conn:
                    lead_id, lead_created = self._get_or_create_lead(
                        conn,
                        name=contact_name,
                        company=company,
                        email=primary_email,
                        phone=phone,
                        source="bidding_ingest",
                        source_artifact_id=artifact_id,
                        metadata={"artifact_path": rel_path, "source": source},
                    )
                    created_leads += 1 if lead_created else 0

                    opp_id = uuid.uuid4().hex
                    now = utcnow_iso()
                    conn.execute(
                        """
                        INSERT INTO sales_opportunities (
                          id, lead_id, project_name, stage, bid_due_date, estimated_value_cents,
                          source_artifact_id, created_at, updated_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            opp_id,
                            lead_id,
                            project_name,
                            "new",
                            bid_due or None,
                            None,
                            artifact_id,
                            now,
                            now,
                            json.dumps({"artifact_path": rel_path, "source": source}, ensure_ascii=False),
                        ),
                    )
                    created_opps += 1

                self._audit.append(
                    actor="system",
                    action="sales_inbound_opportunity_created",
                    scope="internal",
                    entity_type="sales_opportunity",
                    entity_id=opp_id,
                    details={"project_name": project_name, "lead_company": company, "email": primary_email, "artifact_id": artifact_id},
                )

                # Pipeline queue task
                t1 = self._ensure_task(
                    kind="sales",
                    title=f"Review new bid opportunity: {project_name}",
                    description=self._format_itb_task_description(project_name, bid_due, primary_email, phone, rel_path),
                    priority=10,
                    related_entity_type="sales_opportunity",
                    related_entity_id=opp_id,
                    evidence={"artifact_id": artifact_id, "source": source, "bid_due_date": bid_due},
                )
                created_tasks += 1 if t1 else 0

                # Follow-up task (if we have email)
                if primary_email:
                    t2 = self._ensure_task(
                        kind="sales",
                        title=f"Draft outreach email: {company} — {project_name}",
                        description="Create a short, professional intro and confirm bid due date / any missing bid package items.",
                        priority=7,
                        related_entity_type="sales_opportunity",
                        related_entity_id=opp_id,
                        evidence={"lead_email": primary_email, "lead_company": company},
                    )
                    created_tasks += 1 if t2 else 0

            except Exception as e:
                errors += 1
                self._audit.append(
                    actor="system",
                    action="sales_inbound_scan_error",
                    scope="internal",
                    entity_type="artifact",
                    entity_id=artifact_id,
                    details={"path": rel_path, "error": str(e)},
                )

        counts = InboundScanCounts(
            scanned=len(rows),
            created_leads=created_leads,
            created_opportunities=created_opps,
            created_tasks=created_tasks,
            skipped_existing=skipped_existing,
            skipped_not_match=skipped_not_match,
            errors=errors,
        )
        return {"counts": counts.__dict__}

    def scan_bidding_folders(self, *, source: str = "onedrive_bidding", limit_artifacts: int = 5000) -> dict[str, Any]:
        """
        Treat each top-level folder in the bidding root as a bid opportunity.

        This is intentionally more reliable than keyword-matching individual artifacts,
        since real bid packages often arrive as plan sets (PDF) + estimate sheets (XLSX/DOCX)
        without explicit "ITB" text.
        """
        rows = self._db.conn.execute(
            """
            SELECT id, path, ingested_at, extracted_text, metadata_json
            FROM artifacts
            WHERE source = ? AND status = 'ingested'
            ORDER BY ingested_at DESC
            LIMIT ?
            """,
            (source, int(limit_artifacts)),
        ).fetchall()

        # Group by top-level folder (first path segment).
        folders: dict[str, dict[str, Any]] = {}
        for r in rows:
            rel_path = (r["path"] or "").strip()
            if not rel_path:
                continue
            top = rel_path.split("/", 1)[0].strip()
            if not top:
                continue
            if top not in folders:
                folders[top] = {
                    "folder": top,
                    "rep_artifact_id": r["id"],
                    "rep_path": rel_path,
                    "rep_text": r["extracted_text"] or "",
                    "rep_meta": _safe_json_loads(r["metadata_json"]),
                }

        created_leads = 0
        created_opps = 0
        created_tasks = 0
        skipped_existing = 0
        errors = 0

        for folder, rep in folders.items():
            try:
                opp_id = hashlib.sha256(f"{source}:bidding_folder_opp:{folder}".encode("utf-8")).hexdigest()[:32]
                now = utcnow_iso()

                # Parse due date from folder name first, then fall back to representative text.
                bid_due = ""
                m = _RE_FOLDER_DUE.search(folder)
                if m:
                    bid_due = _parse_date_iso(m.group(1) or "")
                if not bid_due:
                    bid_due = extract_bid_due_date(rep.get("rep_text", ""))

                project_name = folder
                project_name = re.sub(
                    r"(?i)\s*[-–—]?\\s*(bid\\s*due|due)\\s*[:\\-]?\\s*[0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4}.*$",
                    "",
                    project_name,
                ).strip()
                project_name = (project_name or folder).strip()[:200]

                rep_text = rep.get("rep_text", "") or ""
                emails = extract_emails(rep_text)
                phone = extract_phone(rep_text)
                contact_email = emails[0] if emails else ""

                # Prefer a real lead when an email is present; otherwise create a deterministic placeholder.
                lead_id = ""
                lead_created = False
                with self._db.tx() as conn:
                    if contact_email:
                        lead_id, lead_created = self._get_or_create_lead(
                            conn,
                            name=None,
                            company=project_name,
                            email=contact_email,
                            phone=phone,
                            source="bidding_folder",
                            source_artifact_id=rep.get("rep_artifact_id"),
                            metadata={"bidding_folder": folder, "source": source, "rep_path": rep.get("rep_path", "")},
                        )
                    else:
                        lead_id = hashlib.sha256(f"{source}:bidding_folder_lead:{folder}".encode("utf-8")).hexdigest()[:32]
                        lead_row = conn.execute("SELECT id FROM sales_leads WHERE id = ? LIMIT 1", (lead_id,)).fetchone()
                        if not lead_row:
                            conn.execute(
                                """
                                INSERT INTO sales_leads (
                                  id, name, company, email, phone,
                                  status, suppressed, source, source_artifact_id,
                                  created_at, updated_at, last_contacted_at, notes, metadata_json
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    lead_id,
                                    None,
                                    project_name,
                                    None,
                                    None,
                                    "new",
                                    0,
                                    "bidding_folder",
                                    rep.get("rep_artifact_id"),
                                    now,
                                    now,
                                    None,
                                    None,
                                    json.dumps({"bidding_folder": folder, "source": source}, ensure_ascii=False),
                                ),
                            )
                            lead_created = True

                    created_leads += 1 if lead_created else 0

                    existing = conn.execute(
                        "SELECT id, lead_id FROM sales_opportunities WHERE id = ? LIMIT 1",
                        (opp_id,),
                    ).fetchone()
                    if existing:
                        skipped_existing += 1
                        # Opportunistic: if we discovered a better lead (with email), relink.
                        if contact_email and existing["lead_id"] != lead_id:
                            conn.execute(
                                "UPDATE sales_opportunities SET lead_id = ?, updated_at = ? WHERE id = ?",
                                (lead_id, now, opp_id),
                            )
                        continue

                    conn.execute(
                        """
                        INSERT INTO sales_opportunities (
                          id, lead_id, project_name, stage, bid_due_date, estimated_value_cents,
                          source_artifact_id, created_at, updated_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            opp_id,
                            lead_id,
                            project_name,
                            "new",
                            bid_due or None,
                            None,
                            rep.get("rep_artifact_id"),
                            now,
                            now,
                            json.dumps(
                                {
                                    "bidding_folder": folder,
                                    "source": source,
                                    "rep_path": rep.get("rep_path"),
                                    "rep_artifact_id": rep.get("rep_artifact_id"),
                                },
                                ensure_ascii=False,
                            ),
                        ),
                    )
                    created_opps += 1

                self._audit.append(
                    actor="system",
                    action="sales_bidding_folder_opportunity_created",
                    scope="internal",
                    entity_type="sales_opportunity",
                    entity_id=opp_id,
                    details={"project_name": project_name, "bid_due_date": bid_due, "folder": folder},
                )

                # Pipeline queue tasks
                t1 = self._ensure_task(
                    kind="sales",
                    title=f"Review bid folder: {project_name}",
                    description=f"Folder: {folder}\nRepresentative file: {rep.get('rep_path','')}\nBid due: {bid_due or 'unknown'}",
                    priority=12,
                    related_entity_type="sales_opportunity",
                    related_entity_id=opp_id,
                    evidence={"bidding_folder": folder, "rep_artifact_id": rep.get("rep_artifact_id")},
                )
                created_tasks += 1 if t1 else 0

                t2 = self._ensure_task(
                    kind="sales",
                    title=f"Find contact for bid: {project_name}",
                    description="Identify GC/owner estimator contact + email/phone. Add to lead record, then draft outreach.",
                    priority=9,
                    related_entity_type="sales_opportunity",
                    related_entity_id=opp_id,
                    evidence={"bidding_folder": folder},
                )
                created_tasks += 1 if t2 else 0

                if contact_email:
                    t3 = self._ensure_task(
                        kind="sales",
                        title=f"Draft outreach email: {project_name}",
                        description="Draft a short, professional intro and confirm bid due date / any missing bid package items.",
                        priority=8,
                        related_entity_type="sales_opportunity",
                        related_entity_id=opp_id,
                        evidence={"lead_email": contact_email},
                    )
                    created_tasks += 1 if t3 else 0

            except Exception as e:
                errors += 1
                self._audit.append(
                    actor="system",
                    action="sales_bidding_folder_scan_error",
                    scope="internal",
                    entity_type="artifact",
                    entity_id=str(rep.get("rep_artifact_id") or ""),
                    details={"folder": folder, "error": str(e)},
                )

        return {
            "counts": {
                "folders_seen": int(len(folders)),
                "created_leads": int(created_leads),
                "created_opportunities": int(created_opps),
                "created_tasks": int(created_tasks),
                "skipped_existing": int(skipped_existing),
                "errors": int(errors),
            }
        }

    def refresh_pipeline_queue(self, *, horizon_days: int = 21) -> dict[str, Any]:
        """
        Create/refresh "next best action" tasks for opportunities.
        MVP rules:
        - If bid_due_date is within horizon and no "bid due" task exists, create one.
        """
        now = datetime.now(timezone.utc).date()
        horizon = now + timedelta(days=int(horizon_days))

        rows = self._db.conn.execute(
            """
            SELECT id, project_name, stage, bid_due_date, lead_id
            FROM sales_opportunities
            WHERE stage NOT IN ('won', 'lost')
            ORDER BY updated_at DESC
            """,
        ).fetchall()

        created = 0
        for r in rows:
            opp_id = r["id"]
            project_name = r["project_name"] or "Unknown Project"
            bid_due = (r["bid_due_date"] or "").strip()
            if not bid_due:
                continue

            try:
                due_date = datetime.fromisoformat(bid_due).date()
            except Exception:
                continue

            if not (now <= due_date <= horizon):
                continue

            title = f"Bid due soon: {project_name} (due {due_date.isoformat()})"
            task_id = self._ensure_task(
                kind="sales",
                title=title,
                description="Confirm final scope + compile bid docs. If needed, request clarifications from GC/owner.",
                priority=20 if (due_date - now).days <= 3 else 12,
                related_entity_type="sales_opportunity",
                related_entity_id=opp_id,
                evidence={"bid_due_date": due_date.isoformat()},
            )
            created += 1 if task_id else 0

        if created:
            self._audit.append(
                actor="system",
                action="sales_pipeline_queue_refreshed",
                scope="internal",
                details={"tasks_created": created, "horizon_days": int(horizon_days)},
            )
        return {"tasks_created": created, "horizon_days": int(horizon_days)}

    def draft_outbound_email(
        self,
        *,
        lead_id: str,
        opportunity_id: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        scope: Optional[str] = "external_low",
        requested_by: str = "sales_spokes",
    ) -> dict[str, Any]:
        lead = self._db.conn.execute(
            "SELECT id, name, company, email, phone, status, suppressed FROM sales_leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        if not lead:
            raise KeyError(f"lead not found: {lead_id}")
        if int(lead["suppressed"] or 0) == 1:
            raise ValueError("lead is suppressed (opt-out); outbound blocked")

        to_email = _norm_email(lead["email"] or "")
        if not to_email:
            raise ValueError("lead has no email; cannot draft outbound email")

        opp = None
        if opportunity_id:
            opp = self._db.conn.execute(
                "SELECT id, project_name, bid_due_date, stage FROM sales_opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()

        subj, msg = self._default_outbound_template(
            lead_name=(lead["name"] or "").strip(),
            lead_company=(lead["company"] or "").strip(),
            lead_phone=(lead["phone"] or "").strip(),
            opportunity_project=(opp["project_name"] if opp else "") if opp else "",
            bid_due_date=(opp["bid_due_date"] if opp else "") if opp else "",
        )
        use_subject = (subject or subj).strip()
        use_body = (body or msg).strip()

        message_id = uuid.uuid4().hex
        now = utcnow_iso()

        intent = f"Send outbound email to {to_email}: {use_subject}"
        approval, gate_reason = self._approvals.request(
            workflow=self.WORKFLOW_OUTBOUND_EMAIL,
            requested_by=requested_by,
            payload={
                "message_id": message_id,
                "lead_id": lead_id,
                "opportunity_id": opportunity_id,
                "to_email": to_email,
                "subject": use_subject,
                "body": use_body,
            },
            intent=intent,
            scope=scope,
            blake_birthmark="N/A",
            cost_estimate=0.0,
        )

        status = "approved" if approval.status == "auto_approved" else "pending_approval"
        provider = (self._emailer.provider or "manual").strip().lower()
        with self._db.tx() as conn:
            conn.execute(
                """
                INSERT INTO outbound_messages (
                  id, workflow, lead_id, opportunity_id, invoice_id,
                  channel, to_email, subject, body,
                  status, approval_id, provider,
                  created_at, updated_at, sent_at, error, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    self.WORKFLOW_OUTBOUND_EMAIL,
                    lead_id,
                    opportunity_id,
                    None,
                    "email",
                    to_email,
                    use_subject,
                    use_body,
                    status,
                    approval.id,
                    provider,
                    now,
                    now,
                    None,
                    None,
                    json.dumps({"gate_reason": gate_reason}, ensure_ascii=False),
                ),
            )

        self._audit.append(
            actor=requested_by,
            action="sales_outbound_draft_created",
            scope=scope,
            entity_type="outbound_message",
            entity_id=message_id,
            details={"to_email": to_email, "subject": use_subject, "approval_status": approval.status, "gate_reason": gate_reason},
        )

        # Human queue task
        task_title = f"Approve outbound email to {to_email}"
        if status == "approved":
            task_title = f"Send approved outbound email to {to_email}"

        self._ensure_task(
            kind="sales",
            title=task_title,
            description=use_subject,
            priority=15,
            related_entity_type="outbound_message",
            related_entity_id=message_id,
            evidence={"approval_id": approval.id, "workflow": self.WORKFLOW_OUTBOUND_EMAIL, "to_email": to_email},
        )

        result: dict[str, Any] = {
            "message_id": message_id,
            "status": status,
            "approval": approval.__dict__,
            "gate_reason": gate_reason,
        }

        auto_send = _env_bool("FRANKLINOPS_SALES_OUTBOUND_AUTO_SEND", default=True)
        if auto_send and status == "approved":
            try:
                send = self.send_outbound_email(message_id=message_id, actor=requested_by)
                result["send"] = send
                # Reflect final status after attempted send.
                row2 = self._db.conn.execute("SELECT status, sent_at, error FROM outbound_messages WHERE id = ?", (message_id,)).fetchone()
                if row2:
                    result["status"] = row2["status"]
                    result["sent_at"] = row2["sent_at"]
                    result["error"] = row2["error"]
            except Exception as e:
                result["send_error"] = str(e)

        return result

    def send_outbound_email(self, *, message_id: str, actor: str = "human") -> dict[str, Any]:
        """
        Execute a previously drafted outbound email if its approval is approved/auto_approved.

        This is the governed "execution" step for `sales_outbound_email`.
        """
        row = self._db.conn.execute(
            """
            SELECT id, workflow, lead_id, opportunity_id, channel, to_email, subject, body,
                   status, approval_id, provider, sent_at, error, metadata_json
            FROM outbound_messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        if not row:
            raise KeyError(f"outbound_message not found: {message_id}")
        if (row["workflow"] or "") != self.WORKFLOW_OUTBOUND_EMAIL:
            raise ValueError("unsupported workflow for this sender")
        if (row["channel"] or "") != "email":
            raise ValueError("unsupported channel (expected email)")

        if row["sent_at"]:
            return {"ok": True, "message_id": message_id, "status": row["status"], "already_sent": True, "sent_at": row["sent_at"]}

        approval_id = (row["approval_id"] or "").strip()
        if not approval_id:
            raise ValueError("outbound_message missing approval_id")

        approval = self._db.conn.execute("SELECT id, status FROM approvals WHERE id = ? LIMIT 1", (approval_id,)).fetchone()
        if not approval:
            raise KeyError(f"approval not found: {approval_id}")

        approval_status = (approval["status"] or "").strip().lower()
        if approval_status in {"denied"}:
            now = utcnow_iso()
            with self._db.tx() as conn:
                conn.execute(
                    "UPDATE outbound_messages SET status = ?, updated_at = ?, error = ? WHERE id = ? AND sent_at IS NULL",
                    ("denied", now, "approval denied", message_id),
                )
            raise ValueError("approval denied; outbound blocked")
        if approval_status not in {"approved", "auto_approved"}:
            raise ValueError(f"approval not approved (status={approval_status})")

        lead = None
        lead_id = (row["lead_id"] or "").strip()
        if lead_id:
            lead = self._db.conn.execute(
                "SELECT id, name, company, email, suppressed, status FROM sales_leads WHERE id = ?",
                (lead_id,),
            ).fetchone()
            if lead and int(lead["suppressed"] or 0) == 1:
                raise ValueError("lead is suppressed (opt-out); outbound blocked")

        # Local rate limiting (separate from the in-memory AutonomyGate counters).
        max_per_hour = max(1, _env_int("FRANKLINOPS_SALES_OUTBOUND_MAX_PER_HOUR", 20))
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        sent_count = self._db.conn.execute(
            """
            SELECT COUNT(1) AS n
            FROM outbound_messages
            WHERE workflow = ? AND status = 'sent' AND sent_at IS NOT NULL AND sent_at >= ?
            """,
            (self.WORKFLOW_OUTBOUND_EMAIL, since),
        ).fetchone()["n"]
        if int(sent_count or 0) >= int(max_per_hour):
            raise ValueError(f"rate limit exceeded: {sent_count}/{max_per_hour} outbound emails in the last hour")

        to_email = _norm_email(row["to_email"] or "")
        if not to_email:
            raise ValueError("outbound_message has empty to_email")

        to_name = ((lead["name"] or "").strip() if lead else "") if lead else ""
        send_res = self._emailer.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=(row["subject"] or "").strip(),
            body=(row["body"] or "").strip(),
        )

        now = utcnow_iso()
        old_meta = _safe_json_loads(row["metadata_json"])
        meta_updates: dict[str, Any] = {
            "approval_status_at_send": approval_status,
            "provider_message_id": send_res.provider_message_id,
        }
        if send_res.meta:
            meta_updates.update(send_res.meta)
        merged_meta = {**old_meta, **meta_updates}

        if send_res.ok:
            with self._db.tx() as conn:
                conn.execute(
                    """
                    UPDATE outbound_messages
                    SET status = ?, provider = ?, sent_at = ?, updated_at = ?, error = NULL, metadata_json = ?
                    WHERE id = ? AND sent_at IS NULL
                    """,
                    ("sent", send_res.provider, now, now, json.dumps(merged_meta, ensure_ascii=False), message_id),
                )

                if lead_id:
                    conn.execute(
                        """
                        UPDATE sales_leads
                        SET last_contacted_at = ?, updated_at = ?,
                            status = CASE WHEN status = 'new' THEN 'contacted' ELSE status END
                        WHERE id = ?
                        """,
                        (now, now, lead_id),
                    )

                opp_id = (row["opportunity_id"] or "").strip()
                if opp_id:
                    conn.execute(
                        """
                        UPDATE sales_opportunities
                        SET updated_at = ?,
                            stage = CASE WHEN stage = 'new' THEN 'contacted' ELSE stage END
                        WHERE id = ?
                        """,
                        (now, opp_id),
                    )

                # Close any open tasks for this outbound message (approve/send).
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'done', updated_at = ?
                    WHERE related_entity_type = 'outbound_message'
                      AND related_entity_id = ?
                      AND status IN ('open', 'in_progress')
                    """,
                    (now, message_id),
                )

            self._audit.append(
                actor=actor,
                action="sales_outbound_email_sent",
                scope="external_low",
                entity_type="outbound_message",
                entity_id=message_id,
                details={"to_email": to_email, "subject": (row["subject"] or ""), "provider": send_res.provider, "provider_message_id": send_res.provider_message_id},
            )

            # Optional follow-up reminder task.
            if _env_bool("FRANKLINOPS_SALES_OUTBOUND_CREATE_FOLLOWUP_TASK", default=True) and lead_id:
                due_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
                company = (lead["company"] if lead else "") if lead else ""
                title = f"Follow up: {company or to_email}"
                self._ensure_task(
                    kind="sales",
                    title=title,
                    description="If no reply, follow up or confirm bid due date / addenda.",
                    priority=8,
                    related_entity_type="sales_lead",
                    related_entity_id=lead_id,
                    due_at=due_at,
                    evidence={"outbound_message_id": message_id, "to_email": to_email},
                )

            return {"ok": True, "message_id": message_id, "status": "sent", "sent_at": now, "provider": send_res.provider, "provider_message_id": send_res.provider_message_id}

        # Failure / non-delivery path
        prov = (send_res.provider or "").strip().lower()
        if prov in {"manual", "disabled"}:
            with self._db.tx() as conn:
                conn.execute(
                    """
                    UPDATE outbound_messages
                    SET status = ?, provider = ?, updated_at = ?, error = ?, metadata_json = ?
                    WHERE id = ? AND sent_at IS NULL
                    """,
                    ("approved", send_res.provider, now, send_res.error, json.dumps(merged_meta, ensure_ascii=False), message_id),
                )
            self._audit.append(
                actor=actor,
                action="sales_outbound_email_not_delivered",
                scope="external_low",
                entity_type="outbound_message",
                entity_id=message_id,
                details={"to_email": to_email, "subject": (row["subject"] or ""), "provider": send_res.provider, "note": send_res.error},
            )
            return {"ok": False, "message_id": message_id, "status": "approved", "not_sent": True, "error": send_res.error, "provider": send_res.provider}

        with self._db.tx() as conn:
            conn.execute(
                """
                UPDATE outbound_messages
                SET status = ?, provider = ?, updated_at = ?, error = ?, metadata_json = ?
                WHERE id = ? AND sent_at IS NULL
                """,
                ("failed", send_res.provider, now, send_res.error, json.dumps(merged_meta, ensure_ascii=False), message_id),
            )

        self._audit.append(
            actor=actor,
            action="sales_outbound_email_send_failed",
            scope="external_low",
            entity_type="outbound_message",
            entity_id=message_id,
            details={"to_email": to_email, "subject": (row["subject"] or ""), "provider": send_res.provider, "error": send_res.error},
        )
        return {"ok": False, "message_id": message_id, "status": "failed", "error": send_res.error, "provider": send_res.provider}

    def send_outbound_for_approval(self, *, approval_id: str, actor: str = "system") -> dict[str, Any]:
        rows = self._db.conn.execute(
            "SELECT id FROM outbound_messages WHERE approval_id = ? AND sent_at IS NULL",
            (approval_id,),
        ).fetchall()
        if not rows:
            return {"ok": False, "approval_id": approval_id, "sent": [], "errors": ["no outbound_messages found for approval_id"]}

        sent: list[dict[str, Any]] = []
        errors: list[str] = []
        for r in rows:
            mid = r["id"]
            try:
                sent.append(self.send_outbound_email(message_id=mid, actor=actor))
            except Exception as e:
                errors.append(f"{mid}: {e}")
        return {"ok": len(errors) == 0, "approval_id": approval_id, "sent": sent, "errors": errors}

    def send_ready_outbound(self, *, limit: int = 50, actor: str = "system") -> dict[str, Any]:
        """
        Send any outbound messages whose approvals are approved/auto_approved.
        """
        rows = self._db.conn.execute(
            """
            SELECT id
            FROM outbound_messages
            WHERE workflow = ?
              AND channel = 'email'
              AND sent_at IS NULL
              AND status IN ('approved', 'pending_approval')
            ORDER BY updated_at ASC
            LIMIT ?
            """,
            (self.WORKFLOW_OUTBOUND_EMAIL, int(limit)),
        ).fetchall()

        sent: list[dict[str, Any]] = []
        skipped = 0
        errors: list[str] = []

        for r in rows:
            mid = r["id"]
            try:
                sent.append(self.send_outbound_email(message_id=mid, actor=actor))
            except ValueError as e:
                # Common skip: not approved yet.
                skipped += 1
                errors.append(f"{mid}: {e}")
            except Exception as e:
                errors.append(f"{mid}: {e}")

        return {"attempted": int(len(rows)), "sent": sent, "skipped": int(skipped), "errors": errors}

    def list_leads(self, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._db.conn.execute(
            """
            SELECT id, name, company, email, phone, status, suppressed, source, created_at, updated_at, last_contacted_at, notes, metadata_json
            FROM sales_leads
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "company": r["company"],
                    "email": r["email"],
                    "phone": r["phone"],
                    "status": r["status"],
                    "suppressed": bool(int(r["suppressed"] or 0)),
                    "source": r["source"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "last_contacted_at": r["last_contacted_at"],
                    "notes": r["notes"],
                    "metadata": _safe_json_loads(r["metadata_json"]),
                }
            )
        return out

    def list_opportunities(self, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = self._db.conn.execute(
            """
            SELECT id, lead_id, project_name, stage, bid_due_date, estimated_value_cents, source_artifact_id, created_at, updated_at, metadata_json
            FROM sales_opportunities
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "lead_id": r["lead_id"],
                    "project_name": r["project_name"],
                    "stage": r["stage"],
                    "bid_due_date": r["bid_due_date"],
                    "estimated_value_cents": r["estimated_value_cents"],
                    "source_artifact_id": r["source_artifact_id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "metadata": _safe_json_loads(r["metadata_json"]),
                }
            )
        return out

    def list_outbound_messages(self, *, status: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
        params: list[Any] = [self.WORKFLOW_OUTBOUND_EMAIL]
        sql = """
        SELECT id, workflow, lead_id, opportunity_id, invoice_id, channel, to_email, subject, body, status,
               approval_id, provider, created_at, updated_at, sent_at, error, metadata_json
        FROM outbound_messages
        WHERE workflow = ?
        """
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(int(limit))

        rows = self._db.conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r["id"],
                    "workflow": r["workflow"],
                    "lead_id": r["lead_id"],
                    "opportunity_id": r["opportunity_id"],
                    "channel": r["channel"],
                    "to_email": r["to_email"],
                    "subject": r["subject"],
                    "body": r["body"],
                    "status": r["status"],
                    "approval_id": r["approval_id"],
                    "provider": r["provider"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "sent_at": r["sent_at"],
                    "error": r["error"],
                    "metadata": _safe_json_loads(r["metadata_json"]),
                }
            )
        return out

    def set_lead_suppressed(self, *, lead_id: str, suppressed: bool, actor: str = "human") -> dict[str, Any]:
        now = utcnow_iso()
        with self._db.tx() as conn:
            cur = conn.execute(
                "UPDATE sales_leads SET suppressed = ?, updated_at = ? WHERE id = ?",
                (1 if suppressed else 0, now, lead_id),
            )
        if cur.rowcount == 0:
            raise KeyError(f"lead not found: {lead_id}")
        self._audit.append(
            actor=actor,
            action="sales_lead_suppression_updated",
            scope="internal",
            entity_type="sales_lead",
            entity_id=lead_id,
            details={"suppressed": bool(suppressed)},
        )
        return {"ok": True}

    def _get_or_create_lead(
        self,
        conn,
        *,
        name: Optional[str],
        company: str,
        email: str,
        phone: str,
        source: str,
        source_artifact_id: Optional[str],
        metadata: dict[str, Any],
    ) -> tuple[str, bool]:
        email_norm = _norm_email(email)
        if email_norm:
            row = conn.execute(
                "SELECT id FROM sales_leads WHERE email = ? LIMIT 1",
                (email_norm,),
            ).fetchone()
            if row:
                lead_id = row["id"]
                # Opportunistic update
                conn.execute(
                    """
                    UPDATE sales_leads
                    SET updated_at = ?, company = COALESCE(NULLIF(company, ''), company),
                        phone = COALESCE(NULLIF(phone, ''), phone),
                        source_artifact_id = COALESCE(source_artifact_id, ?),
                        metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        utcnow_iso(),
                        source_artifact_id,
                        json.dumps(metadata, ensure_ascii=False),
                        lead_id,
                    ),
                )
                return lead_id, False

        lead_id = uuid.uuid4().hex
        now = utcnow_iso()
        conn.execute(
            """
            INSERT INTO sales_leads (
              id, name, company, email, phone,
              status, suppressed, source, source_artifact_id,
              created_at, updated_at, last_contacted_at, notes, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                (name or "").strip() or None,
                (company or "").strip() or "Unknown",
                email_norm or None,
                (phone or "").strip() or None,
                "new",
                0,
                source,
                source_artifact_id,
                now,
                now,
                None,
                None,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        self._audit.append(
            actor="system",
            action="sales_lead_created",
            scope="internal",
            entity_type="sales_lead",
            entity_id=lead_id,
            details={"company": company, "email": email_norm, "source": source},
        )
        return lead_id, True

    def _ensure_task(
        self,
        *,
        kind: str,
        title: str,
        description: str,
        priority: int,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        due_at: Optional[str] = None,
        evidence: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        existing = self._db.conn.execute(
            """
            SELECT id FROM tasks
            WHERE status = 'open'
              AND kind = ?
              AND title = ?
              AND COALESCE(related_entity_type, '') = COALESCE(?, '')
              AND COALESCE(related_entity_id, '') = COALESCE(?, '')
            LIMIT 1
            """,
            (kind, title, related_entity_type, related_entity_id),
        ).fetchone()
        if existing:
            return None

        task_id = uuid.uuid4().hex
        now = utcnow_iso()
        with self._db.tx() as conn:
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
                    kind,
                    title,
                    description,
                    "open",
                    int(priority),
                    related_entity_type,
                    related_entity_id,
                    now,
                    now,
                    due_at,
                    json.dumps(evidence or {}, ensure_ascii=False),
                ),
            )
        return task_id

    @staticmethod
    def _format_itb_task_description(project_name: str, bid_due: str, email: str, phone: str, rel_path: str) -> str:
        bits: list[str] = []
        bits.append(f"Project: {project_name}")
        if bid_due:
            bits.append(f"Bid due: {bid_due}")
        if email:
            bits.append(f"Contact email: {email}")
        if phone:
            bits.append(f"Contact phone: {phone}")
        if rel_path:
            bits.append(f"Source: {rel_path}")
        return "\n".join(bits)

    @staticmethod
    def _default_outbound_template(
        *,
        lead_name: str,
        lead_company: str,
        lead_phone: str,
        opportunity_project: str,
        bid_due_date: str,
    ) -> tuple[str, str]:
        greeting = f"Hi {lead_name}," if lead_name else "Hi there,"
        project_line = f"Project: {opportunity_project}\n" if opportunity_project else ""
        due_line = f"Bid due: {bid_due_date}\n" if bid_due_date else ""

        subject = "Quick question re: bid invite"
        if opportunity_project:
            subject = f"Re: {opportunity_project} — bid invite"

        body = (
            f"{greeting}\n\n"
            f"Thanks for including JCK Concrete on the invite.\n\n"
            f"{project_line}{due_line}"
            "Can you confirm the bid due date/time and whether there are any addenda we should be aware of?\n"
            "If there’s a link to the full bid package (plans/specs), please share it.\n\n"
            "Best,\n"
            "JCK Concrete\n"
        )
        if lead_phone:
            body += f"\nP.S. If it’s easier, you can call/text me at {lead_phone}."
        return subject, body

