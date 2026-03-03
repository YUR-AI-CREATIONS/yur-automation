from __future__ import annotations

import csv
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .approvals import ApprovalService
from .audit import AuditLogger
from .opsdb import OpsDB


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_date(s: str) -> Optional[str]:
    raw = (s or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except Exception:
            pass
    return None


def _parse_money_to_cents(s: str) -> Optional[int]:
    raw = (s or "").strip()
    if not raw:
        return None
    neg = False
    # Common accounting format: (1,234.56) for negative amounts
    if raw.startswith("(") and raw.endswith(")"):
        neg = True
        raw = raw[1:-1].strip()
    raw = raw.replace("$", "").replace(",", "")
    try:
        val = float(raw)
        if neg:
            val = -val
        return int(round(val * 100))
    except Exception:
        return None


@dataclass(frozen=True)
class ParsedInvoice:
    vendor_name: str
    invoice_number: str
    invoice_date: Optional[str]
    due_date: Optional[str]
    amount_cents: int
    currency: str = "USD"
    project_name: str = ""
    confidence: float = 0.5


_RE_INV_NUM = re.compile(r"(?i)\b(invoice\s*(#|no\.?|number)|inv\s*#)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-_\/]*)")
_RE_INV_DATE = re.compile(r"(?i)\binvoice\s*date\s*[:#]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})")
_RE_DUE_DATE = re.compile(r"(?i)\b(due\s*date|due)\s*[:#]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})")
_RE_TOTAL_DUE = re.compile(r"(?i)\btotal\s*(due)?\s*[:#]?\s*\$?\s*([0-9][0-9,]*\.[0-9]{2})")
_RE_PROJECT = re.compile(r"(?i)\bproject\s*[:#]?\s*(.+)")


def parse_invoice_text(text: str) -> Optional[ParsedInvoice]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return None

    vendor = lines[0][:120]
    for ln in lines[:10]:
        if ln.lower().startswith("from:"):
            vendor = ln.split(":", 1)[1].strip()[:120] or vendor
            break

    inv_num = ""
    inv_date = None
    due_date = None
    project = ""
    amount_cents: Optional[int] = None
    confidence = 0.4

    for ln in lines[:120]:
        m = _RE_INV_NUM.search(ln)
        if m and not inv_num:
            inv_num = (m.group(3) or "").strip()
            confidence += 0.15

        m = _RE_INV_DATE.search(ln)
        if m and not inv_date:
            inv_date = _parse_date(m.group(1) or "")
            if inv_date:
                confidence += 0.1

        m = _RE_DUE_DATE.search(ln)
        if m and not due_date:
            due_date = _parse_date(m.group(2) or "")
            if due_date:
                confidence += 0.1

        m = _RE_PROJECT.search(ln)
        if m and not project:
            project = (m.group(1) or "").strip()[:200]
            confidence += 0.05

        m = _RE_TOTAL_DUE.search(ln)
        if m and amount_cents is None:
            amount_cents = _parse_money_to_cents(m.group(2) or "")
            if amount_cents is not None:
                confidence += 0.15

    if amount_cents is None:
        moneys = re.findall(r"\$\s*([0-9][0-9,]*\.[0-9]{2})", text or "")
        cents = [_parse_money_to_cents(x) for x in moneys]
        cents = [c for c in cents if c is not None]
        if cents:
            amount_cents = max(cents)
            confidence += 0.05

    if amount_cents is None or amount_cents <= 0:
        return None

    confidence = min(max(confidence, 0.0), 0.99)
    return ParsedInvoice(
        vendor_name=vendor,
        invoice_number=inv_num or "",
        invoice_date=inv_date,
        due_date=due_date,
        amount_cents=int(amount_cents),
        project_name=project,
        confidence=confidence,
    )


def _get_or_create_vendor(db: OpsDB, *, name: str) -> str:
    nm = (name or "").strip() or "Unknown Vendor"
    row = db.conn.execute("SELECT id FROM vendors WHERE lower(name) = lower(?)", (nm,)).fetchone()
    if row:
        return row["id"]
    vendor_id = uuid.uuid4().hex
    now = utcnow_iso()
    with db.tx() as conn:
        conn.execute("INSERT INTO vendors (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)", (vendor_id, nm, now, now))
    return vendor_id


def _get_or_create_project(db: OpsDB, *, name: str) -> Optional[str]:
    nm = (name or "").strip()
    if not nm:
        return None
    row = db.conn.execute("SELECT id FROM projects WHERE lower(name) = lower(?)", (nm,)).fetchone()
    if row:
        return row["id"]
    project_id = uuid.uuid4().hex
    now = utcnow_iso()
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, nm, "unknown", now, now),
        )
    return project_id


def run_ap_intake(
    db: OpsDB,
    audit: AuditLogger,
    approvals: ApprovalService,
    *,
    source: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    sql = """
    SELECT a.id, a.source, a.path, a.birthmark, a.extracted_text
    FROM artifacts a
    WHERE a.status = 'ingested'
      AND (a.path LIKE '%.pdf' OR a.path LIKE '%.eml' OR a.path LIKE '%.txt')
      AND NOT EXISTS (SELECT 1 FROM invoices i WHERE i.source_artifact_id = a.id)
    """
    params: list[Any] = []
    if source:
        sql += " AND a.source = ?"
        params.append(source)
    sql += " ORDER BY a.ingested_at DESC LIMIT ?"
    params.append(limit)

    candidates = db.conn.execute(sql, params).fetchall()

    created: list[dict[str, Any]] = []
    skipped = 0

    for art in candidates:
        parsed = parse_invoice_text(art["extracted_text"] or "")
        if not parsed:
            skipped += 1
            continue

        vendor_id = _get_or_create_vendor(db, name=parsed.vendor_name)
        project_id = _get_or_create_project(db, name=parsed.project_name)

        invoice_id = uuid.uuid4().hex
        now = utcnow_iso()
        with db.tx() as conn:
            conn.execute(
                """
                INSERT INTO invoices (
                  id, kind, vendor_id, customer_id, project_id,
                  invoice_number, invoice_date, due_date,
                  amount_cents, currency, status, source_artifact_id,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    "AP",
                    vendor_id,
                    None,
                    project_id,
                    parsed.invoice_number,
                    parsed.invoice_date,
                    parsed.due_date,
                    int(parsed.amount_cents),
                    parsed.currency,
                    "received",
                    art["id"],
                    now,
                    now,
                ),
            )

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
                    "finance.ap_review",
                    f"Review vendor invoice {parsed.invoice_number or '(no #)'} (${parsed.amount_cents/100:,.2f})",
                    f"Source: {art['source']} / {art['path']}",
                    "open",
                    10,
                    "invoice",
                    invoice_id,
                    now,
                    now,
                    parsed.due_date,
                    json.dumps(
                        {
                            "invoice_id": invoice_id,
                            "artifact_id": art["id"],
                            "vendor": parsed.vendor_name,
                            "amount_cents": parsed.amount_cents,
                            "due_date": parsed.due_date,
                            "confidence": parsed.confidence,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        intent = f"Approve AP invoice {parsed.invoice_number or '(no #)'} from {parsed.vendor_name} for ${parsed.amount_cents/100:,.2f}"
        if parsed.due_date:
            intent += f" due {parsed.due_date}"

        approval_record, gate_reason = approvals.request(
            workflow="finance.ap_intake",
            requested_by="finance_spokes",
            payload={
                "invoice_id": invoice_id,
                "artifact_id": art["id"],
                "vendor": parsed.vendor_name,
                "invoice_number": parsed.invoice_number,
                "invoice_date": parsed.invoice_date,
                "due_date": parsed.due_date,
                "amount_cents": parsed.amount_cents,
                "currency": parsed.currency,
                "confidence": parsed.confidence,
            },
            intent=intent,
            scope="external_medium",
            blake_birthmark=art["birthmark"] or "N/A",
            cost_estimate=0.0,
        )

        audit.append(
            actor="finance_spokes",
            action="ap_invoice_created",
            scope="external_medium",
            entity_type="invoice",
            entity_id=invoice_id,
            details={
                "artifact_id": art["id"],
                "vendor": parsed.vendor_name,
                "amount_cents": parsed.amount_cents,
                "approval_id": approval_record.id,
                "approval_status": approval_record.status,
                "gate_reason": gate_reason,
            },
        )

        applied: Optional[dict[str, Any]] = None
        if approval_record.status == "auto_approved":
            try:
                applied = apply_finance_ap_intake_decision(
                    db,
                    audit,
                    approval_id=approval_record.id,
                    approval_status="auto_approved",
                    actor="autonomy_gate",
                    payload=approval_record.payload,
                )
            except Exception as e:
                applied = {"ok": False, "error": str(e)}
                audit.append(
                    actor="system",
                    action="finance_ap_intake_auto_apply_failed",
                    scope="external_medium",
                    entity_type="invoice",
                    entity_id=invoice_id,
                    details={"approval_id": approval_record.id, "error": str(e)},
                )

        created.append(
            {
                "invoice_id": invoice_id,
                "artifact_id": art["id"],
                "approval_id": approval_record.id,
                "approval_status": approval_record.status,
                "applied": applied,
            }
        )

    return {"candidates": int(len(candidates)), "created": created, "skipped": int(skipped)}


def import_cashflow_waterfall_csv(db: OpsDB, audit: AuditLogger, *, artifact_id: str) -> dict[str, Any]:
    row = db.conn.execute(
        "SELECT id, source, path, extracted_text, metadata_json FROM artifacts WHERE id = ?",
        (artifact_id,),
    ).fetchone()
    if not row:
        raise KeyError(f"artifact not found: {artifact_id}")

    meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
    abs_path = meta.get("abs_path")
    csv_path = Path(abs_path) if abs_path else None
    rel_path = (row["path"] or "").strip()

    project_id: Optional[str] = None
    if rel_path:
        top = rel_path.split("/", 1)[0].strip()
        project_id = _get_or_create_project(db, name=top)

    lines: list[dict[str, str]] = []
    if csv_path and csv_path.exists():
        with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                lines.append({k: (v or "") for k, v in r.items() if k})
    else:
        text = row["extracted_text"] or ""
        parts = [p for p in (ln.strip() for ln in text.splitlines()) if p]
        if not parts:
            return {"inserted": 0}
        header = [h.strip() for h in parts[0].split(",")]
        for ln in parts[1:]:
            cells = [c.strip() for c in ln.split(",")]
            lines.append({header[i]: (cells[i] if i < len(cells) else "") for i in range(len(header))})

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

    # For monthly waterfall CSVs, anchor month 1 to a configurable start date.
    # Default: first day of current month (safe + deterministic for local runs).
    start_raw = (os.getenv("FRANKLINOPS_WATERFALL_START_DATE") or os.getenv("FRANKLINOPS_CASHFLOW_START_DATE") or "").strip()
    start_iso = _parse_date(start_raw) or date.today().replace(day=1).isoformat()
    try:
        base_month = date.fromisoformat(start_iso).replace(day=1)
    except Exception:
        base_month = date.today().replace(day=1)

    def month_start(month_num: int) -> str:
        idx = max(int(month_num) - 1, 0)
        y = base_month.year + (base_month.month - 1 + idx) // 12
        m = (base_month.month - 1 + idx) % 12 + 1
        return date(y, m, 1).isoformat()

    inserted = 0
    totals_draw_cents = 0
    totals_rev_cents = 0
    now = utcnow_iso()
    with db.tx() as conn:
        conn.execute("DELETE FROM cashflow_lines WHERE source = ? AND source_ref = ?", ("csv_waterfall", artifact_id))
        for r in lines:
            cols = {norm(k): v for k, v in r.items()}

            # 1) Monthly waterfall format (like JCK's `02_Cash_Flow_Waterfall.csv`)
            if "month" in cols and ("phase" in cols or "activity" in cols or "totaldraw" in cols or "revenuesales" in cols):
                month_raw = str(cols.get("month") or "").strip()
                try:
                    month_num = int(month_raw)
                except Exception:
                    # Allow a TOTALS row fallback when monthly rows are empty
                    if "total" in month_raw.lower():
                        draw_raw = (cols.get("totaldraw") or cols.get("drawexpense") or cols.get("draw") or "").strip()
                        rev_raw = (cols.get("revenuesales") or cols.get("revenue") or cols.get("sales") or "").strip()
                        totals_draw_cents = _parse_money_to_cents(draw_raw) or totals_draw_cents
                        totals_rev_cents = _parse_money_to_cents(rev_raw) or totals_rev_cents
                    continue

                phase = (cols.get("phase") or "").strip()
                activity = (cols.get("activity") or "").strip()
                cat = f"{phase} — {activity}".strip(" —")[:240]
                wk = month_start(month_num)

                draw_raw = (cols.get("totaldraw") or cols.get("drawexpense") or cols.get("draw") or "").strip()
                rev_raw = (cols.get("revenuesales") or cols.get("revenue") or cols.get("sales") or "").strip()

                draw_cents = _parse_money_to_cents(draw_raw) or 0
                rev_cents = _parse_money_to_cents(rev_raw) or 0

                if draw_cents == 0 and rev_cents == 0:
                    continue

                if draw_cents:
                    conn.execute(
                        """
                        INSERT INTO cashflow_lines (
                          id, project_id, week_start, category, amount_cents, direction,
                          source, source_ref, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            uuid.uuid4().hex,
                            project_id,
                            wk,
                            cat or "Expense",
                            int(abs(draw_cents)),
                            "outflow" if draw_cents >= 0 else "inflow",
                            "csv_waterfall",
                            artifact_id,
                            now,
                        ),
                    )
                    inserted += 1

                if rev_cents:
                    conn.execute(
                        """
                        INSERT INTO cashflow_lines (
                          id, project_id, week_start, category, amount_cents, direction,
                          source, source_ref, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            uuid.uuid4().hex,
                            project_id,
                            wk,
                            cat or "Revenue",
                            int(abs(rev_cents)),
                            "inflow" if rev_cents >= 0 else "outflow",
                            "csv_waterfall",
                            artifact_id,
                            now,
                        ),
                    )
                    inserted += 1

                continue

            # 2) Generic "week_start/category/direction/amount" format
            week = cols.get("weekstart") or cols.get("week") or cols.get("date") or ""
            category = cols.get("category") or cols.get("description") or cols.get("type") or ""
            direction = cols.get("direction") or cols.get("inout") or ""
            amount = cols.get("amount") or cols.get("value") or cols.get("total") or ""

            week_iso = _parse_date(week) or ""
            amount_cents = _parse_money_to_cents(amount)
            if not week_iso or amount_cents is None:
                continue

            dir_norm = norm(direction)
            if dir_norm in {"outflow", "out", "expense", "payable", "payment"}:
                direction_val = "outflow"
            elif dir_norm in {"inflow", "in", "revenue", "receivable"}:
                direction_val = "inflow"
            else:
                direction_val = "outflow" if str(amount).strip().startswith("-") else "inflow"

            conn.execute(
                """
                INSERT INTO cashflow_lines (
                  id, project_id, week_start, category, amount_cents, direction,
                  source, source_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    project_id,
                    week_iso,
                    category,
                    int(abs(amount_cents)),
                    direction_val,
                    "csv_waterfall",
                    artifact_id,
                    now,
                ),
            )
            inserted += 1

        # If the CSV is a template with only TOTALS populated, insert a single summary entry.
        if inserted == 0 and (totals_draw_cents or totals_rev_cents):
            wk = base_month.isoformat()
            if totals_draw_cents:
                conn.execute(
                    """
                    INSERT INTO cashflow_lines (
                      id, project_id, week_start, category, amount_cents, direction,
                      source, source_ref, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        project_id,
                        wk,
                        "TOTALS (waterfall)",
                        int(abs(totals_draw_cents)),
                        "outflow" if totals_draw_cents >= 0 else "inflow",
                        "csv_waterfall",
                        artifact_id,
                        now,
                    ),
                )
                inserted += 1
            if totals_rev_cents:
                conn.execute(
                    """
                    INSERT INTO cashflow_lines (
                      id, project_id, week_start, category, amount_cents, direction,
                      source, source_ref, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        project_id,
                        wk,
                        "TOTALS (waterfall)",
                        int(abs(totals_rev_cents)),
                        "inflow" if totals_rev_cents >= 0 else "outflow",
                        "csv_waterfall",
                        artifact_id,
                        now,
                    ),
                )
                inserted += 1

    audit.append(
        actor="finance_spokes",
        action="cashflow_imported",
        scope="internal",
        entity_type="artifact",
        entity_id=artifact_id,
        details={"inserted": inserted, "source": "csv_waterfall", "base_month": base_month.isoformat()},
    )
    return {"inserted": inserted}


def import_procore_invoices_export_csv(db: OpsDB, audit: AuditLogger, *, artifact_id: str, limit: int = 5000) -> dict[str, Any]:
    row = db.conn.execute("SELECT id, metadata_json FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not row:
        raise KeyError(f"artifact not found: {artifact_id}")

    meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
    abs_path = meta.get("abs_path")
    csv_path = Path(abs_path) if abs_path else None
    if not (csv_path and csv_path.exists()):
        raise ValueError("Procore export import requires a local CSV file path (artifact metadata 'abs_path').")

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

    inserted = 0
    updated = 0
    skipped = 0
    now = utcnow_iso()

    with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)[: int(limit)]

    for r in rows:
        cols = {norm(k): (v or "").strip() for k, v in r.items() if k}

        project_name = cols.get("project") or cols.get("projectname") or cols.get("job") or cols.get("jobname") or ""
        vendor_name = cols.get("vendor") or cols.get("vendorcompany") or cols.get("company") or ""
        inv_no = cols.get("invoicenumber") or cols.get("invoice") or cols.get("invnumber") or ""
        inv_date = _parse_date(cols.get("invoicedate", "") or cols.get("date", "") or "")
        due_date = _parse_date(cols.get("duedate", "") or "")
        amt_cents = _parse_money_to_cents(cols.get("amount", "") or cols.get("total", "") or cols.get("invoiceamount", "") or "")
        status_raw = cols.get("status", "")

        if not vendor_name or amt_cents is None:
            skipped += 1
            continue

        vendor_id = _get_or_create_vendor(db, name=vendor_name)
        project_id = _get_or_create_project(db, name=project_name)

        existing = None
        if inv_no:
            existing = db.conn.execute(
                "SELECT id FROM invoices WHERE kind = 'AP' AND vendor_id = ? AND invoice_number = ? AND (invoice_date = ? OR invoice_date IS NULL)",
                (vendor_id, inv_no, inv_date),
            ).fetchone()

        if existing:
            invoice_id = existing["id"]
            with db.tx() as conn:
                conn.execute(
                    """
                    UPDATE invoices
                    SET project_id = COALESCE(?, project_id),
                        due_date = COALESCE(?, due_date),
                        amount_cents = ?,
                        status = ?,
                        source_artifact_id = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (project_id, due_date, int(amt_cents), (status_raw or "imported").lower(), artifact_id, now, invoice_id),
                )
            updated += 1
        else:
            invoice_id = uuid.uuid4().hex
            with db.tx() as conn:
                conn.execute(
                    """
                    INSERT INTO invoices (
                      id, kind, vendor_id, customer_id, project_id,
                      invoice_number, invoice_date, due_date,
                      amount_cents, currency, status, source_artifact_id,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_id,
                        "AP",
                        vendor_id,
                        None,
                        project_id,
                        inv_no,
                        inv_date,
                        due_date,
                        int(amt_cents),
                        "USD",
                        (status_raw or "imported").lower(),
                        artifact_id,
                        now,
                        now,
                    ),
                )
            inserted += 1

        if due_date:
            with db.tx() as conn:
                conn.execute("DELETE FROM cashflow_lines WHERE source = ? AND source_ref = ?", ("procore_export", invoice_id))
                conn.execute(
                    """
                    INSERT INTO cashflow_lines (
                      id, project_id, week_start, category, amount_cents, direction,
                      source, source_ref, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        project_id,
                        due_date,
                        f"AP invoice {inv_no}".strip(),
                        int(amt_cents),
                        "outflow",
                        "procore_export",
                        invoice_id,
                        now,
                    ),
                )

    audit.append(actor="finance_spokes", action="procore_invoices_imported", scope="external_low", entity_type="artifact", entity_id=artifact_id, details={"inserted": inserted, "updated": updated, "skipped": skipped})
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def cashflow_forecast(db: OpsDB, *, start_week: Optional[str] = None, weeks: int = 8) -> dict[str, Any]:
    if start_week is None:
        start_week = date.today().isoformat()

    rows = db.conn.execute(
        """
        SELECT week_start, direction, SUM(amount_cents) AS amount_cents
        FROM cashflow_lines
        WHERE week_start >= ?
        GROUP BY week_start, direction
        ORDER BY week_start ASC
        """,
        (start_week,),
    ).fetchall()

    by_week: dict[str, dict[str, int]] = {}
    for r in rows:
        wk = r["week_start"]
        by_week.setdefault(wk, {"inflow": 0, "outflow": 0})
        direction = (r["direction"] or "").lower()
        amt = int(r["amount_cents"] or 0)
        if direction == "outflow":
            by_week[wk]["outflow"] += amt
        else:
            by_week[wk]["inflow"] += amt

    weeks_sorted = sorted(by_week.keys())[: int(weeks)]
    out: list[dict[str, Any]] = []
    cumulative = 0
    for wk in weeks_sorted:
        inflow = by_week[wk]["inflow"]
        outflow = by_week[wk]["outflow"]
        net = inflow - outflow
        cumulative += net
        out.append({"week_start": wk, "inflow_cents": inflow, "outflow_cents": outflow, "net_cents": net, "cumulative_cents": cumulative})

    return {"start_week": start_week, "weeks": out}


def generate_ar_reminder_draft(*, invoice_number: str, amount_cents: int, due_date: Optional[str], customer_name: str = "") -> dict[str, str]:
    subj = f"Payment reminder: invoice {invoice_number}".strip()
    due_phrase = f" (due {due_date})" if due_date else ""
    greet = f"Hi {customer_name}," if customer_name else "Hi,"
    body = (
        f"{greet}\n\n"
        f"Just a friendly reminder that invoice {invoice_number} for ${amount_cents/100:,.2f}{due_phrase} is still outstanding.\n"
        f"If you’ve already sent payment, thank you—please disregard this note.\n\n"
        f"Best,\n"
        f"Accounts Receivable"
    )
    return {"subject": subj, "body": body}


def run_ar_reminders(db: OpsDB, audit: AuditLogger, approvals: ApprovalService, *, as_of: Optional[str] = None, limit: int = 50) -> dict[str, Any]:
    if as_of is None:
        as_of = date.today().isoformat()

    rows = db.conn.execute(
        """
        SELECT i.id, i.invoice_number, i.due_date, i.amount_cents, i.currency, i.status, i.customer_id,
               c.name AS customer_name, c.email AS customer_email
        FROM invoices i
        LEFT JOIN customers c ON c.id = i.customer_id
        WHERE i.kind = 'AR'
          AND i.due_date IS NOT NULL
          AND i.due_date < ?
          AND i.status IN ('sent', 'unpaid', 'past_due')
        ORDER BY i.due_date ASC
        LIMIT ?
        """,
        (as_of, limit),
    ).fetchall()

    created: list[dict[str, Any]] = []
    for r in rows:
        customer_name = (r["customer_name"] or "").strip() if "customer_name" in r.keys() else ""
        customer_name = customer_name.strip() or ""
        to_email = (r["customer_email"] or "").strip().lower() if "customer_email" in r.keys() else ""
        if not to_email:
            to_email = "customer@invoice.placeholder"  # Human must fill in

        draft = generate_ar_reminder_draft(
            invoice_number=r["invoice_number"] or "(no #)",
            amount_cents=int(r["amount_cents"] or 0),
            due_date=r["due_date"],
            customer_name=customer_name,
        )
        intent = f"Send AR reminder for invoice {r['invoice_number'] or '(no #)'} to {to_email}"
        approval_record, gate_reason = approvals.request(
            workflow="finance.ar_reminder",
            requested_by="finance_spokes",
            payload={"invoice_id": r["id"], "draft": draft, "to_email": to_email, "customer_name": customer_name},
            intent=intent,
            scope="external_low",
            blake_birthmark="N/A",
            cost_estimate=0.0,
        )
        status = "approved" if approval_record.status == "auto_approved" else "pending_approval"
        task_title = (
            f"Send AR reminder: invoice {r['invoice_number'] or '(no #)'} to {to_email}"
            if status == "approved"
            else f"Approve AR reminder: invoice {r['invoice_number'] or '(no #)'} to {to_email}"
        )

        message_id = uuid.uuid4().hex
        now = utcnow_iso()
        with db.tx() as conn:
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
                    "finance.ar_reminder",
                    None,
                    None,
                    r["id"],
                    "email",
                    to_email,
                    draft["subject"],
                    draft["body"],
                    status,
                    approval_record.id,
                    "manual",
                    now,
                    now,
                    None,
                    None,
                    json.dumps({"gate_reason": gate_reason}, ensure_ascii=False),
                ),
            )
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
                    "finance.ar_reminder",
                    task_title,
                    draft["subject"],
                    "open",
                    12,
                    "outbound_message",
                    message_id,
                    now,
                    now,
                    r["due_date"],
                    json.dumps({"invoice_id": r["id"], "approval_id": approval_record.id}, ensure_ascii=False),
                ),
            )

        audit.append(actor="finance_spokes", action="ar_reminder_drafted", scope="external_low", entity_type="invoice", entity_id=r["id"], details={"approval_id": approval_record.id, "approval_status": approval_record.status, "gate_reason": gate_reason, "message_id": message_id})
        created.append({"invoice_id": r["id"], "message_id": message_id, "approval_id": approval_record.id, "status": approval_record.status})

    return {"eligible": int(len(rows)), "drafted": created}


def apply_finance_ap_intake_decision(
    db: OpsDB,
    audit: AuditLogger,
    *,
    approval_id: str,
    approval_status: str,
    actor: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply an approval decision to an AP invoice created by AP intake.

    This is the governed "state transition" step after a human (or autopilot)
    approves/denies the intake action.
    """
    invoice_id = (payload.get("invoice_id") or "").strip()
    if not invoice_id:
        return {"ok": False, "error": "missing invoice_id in approval payload"}

    inv = db.conn.execute(
        """
        SELECT i.id, i.kind, i.vendor_id, i.project_id, i.invoice_number, i.invoice_date, i.due_date,
               i.amount_cents, i.currency, i.status,
               v.name AS vendor_name,
               p.name AS project_name
        FROM invoices i
        LEFT JOIN vendors v ON v.id = i.vendor_id
        LEFT JOIN projects p ON p.id = i.project_id
        WHERE i.id = ?
        """,
        (invoice_id,),
    ).fetchone()
    if not inv:
        return {"ok": False, "error": f"invoice not found: {invoice_id}"}

    if (inv["kind"] or "").upper() != "AP":
        return {"ok": False, "error": f"invoice is not AP (kind={inv['kind']})"}

    if approval_status in {"approved", "auto_approved"}:
        new_invoice_status = "approved"
    elif approval_status == "denied":
        new_invoice_status = "denied"
    else:
        return {"ok": False, "error": f"unsupported approval_status: {approval_status}"}

    vendor_name = (inv["vendor_name"] or "").strip() or "Vendor"
    inv_no = (inv["invoice_number"] or "").strip() or "(no #)"
    due_date = (inv["due_date"] or "").strip() or None
    amount_cents = int(inv["amount_cents"] or 0)

    now = utcnow_iso()
    with db.tx() as conn:
        # Update invoice status
        conn.execute(
            "UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?",
            (new_invoice_status, now, invoice_id),
        )

        # Close the review task(s) for this invoice
        conn.execute(
            """
            UPDATE tasks
            SET status = 'done', updated_at = ?
            WHERE kind = 'finance.ap_review'
              AND related_entity_type = 'invoice'
              AND related_entity_id = ?
              AND status IN ('open', 'in_progress')
            """,
            (now, invoice_id),
        )

        # Keep cashflow model in sync (idempotent)
        conn.execute("DELETE FROM cashflow_lines WHERE source = ? AND source_ref = ?", ("ap_intake", invoice_id))
        if new_invoice_status == "approved" and due_date and amount_cents > 0:
            conn.execute(
                """
                INSERT INTO cashflow_lines (
                  id, project_id, week_start, category, amount_cents, direction,
                  source, source_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    inv["project_id"],
                    due_date,
                    f"AP invoice {inv_no} — {vendor_name}"[:240],
                    int(amount_cents),
                    "outflow",
                    "ap_intake",
                    invoice_id,
                    now,
                ),
            )

        # If approved, create a follow-on payment processing task
        if new_invoice_status == "approved":
            existing = conn.execute(
                """
                SELECT id FROM tasks
                WHERE kind = 'finance.ap_pay'
                  AND related_entity_type = 'invoice'
                  AND related_entity_id = ?
                  AND status IN ('open', 'in_progress')
                LIMIT 1
                """,
                (invoice_id,),
            ).fetchone()
            if not existing:
                title = f"Schedule payment: {vendor_name} — invoice {inv_no} (${amount_cents/100:,.2f})"
                desc = f"Approved AP invoice. Due: {due_date or 'unknown'}"
                conn.execute(
                    """
                    INSERT INTO tasks (
                      id, kind, title, description, status, priority,
                      related_entity_type, related_entity_id,
                      created_at, updated_at, due_at, evidence_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        "finance.ap_pay",
                        title,
                        desc,
                        "open",
                        18,
                        "invoice",
                        invoice_id,
                        now,
                        now,
                        due_date,
                        json.dumps({"approval_id": approval_id, "invoice_id": invoice_id}, ensure_ascii=False),
                    ),
                )

    audit.append(
        actor=actor,
        action="finance_ap_intake_decision_applied",
        scope="external_medium",
        entity_type="invoice",
        entity_id=invoice_id,
        details={
            "approval_id": approval_id,
            "approval_status": approval_status,
            "invoice_status": new_invoice_status,
            "vendor": vendor_name,
            "invoice_number": inv_no,
            "amount_cents": amount_cents,
            "due_date": due_date,
        },
    )

    return {"ok": True, "invoice_id": invoice_id, "invoice_status": new_invoice_status}


def apply_finance_ar_reminder_decision(
    db: OpsDB,
    audit: AuditLogger,
    *,
    approval_id: str,
    approval_status: str,
    actor: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Apply an approval decision to AR reminder drafts (outbound_messages workflow=finance.ar_reminder).

    When approved: mark draft(s) as approved and create a "send" task.
    When denied: mark draft(s) as denied and close any approval tasks.
    """
    if approval_status in {"approved", "auto_approved"}:
        new_msg_status = "approved"
    elif approval_status == "denied":
        new_msg_status = "denied"
    else:
        return {"ok": False, "error": f"unsupported approval_status: {approval_status}"}

    rows = db.conn.execute(
        """
        SELECT id, invoice_id, to_email, subject, status, sent_at
        FROM outbound_messages
        WHERE workflow = 'finance.ar_reminder' AND approval_id = ?
        """,
        (approval_id,),
    ).fetchall()
    if not rows:
        return {"ok": False, "error": f"no outbound_messages found for approval_id: {approval_id}"}

    now = utcnow_iso()
    updated = 0
    created_tasks = 0

    with db.tx() as conn:
        for r in rows:
            mid = r["id"]
            if r["sent_at"]:
                continue

            conn.execute(
                """
                UPDATE outbound_messages
                SET status = ?, updated_at = ?, error = ?
                WHERE id = ? AND sent_at IS NULL
                """,
                (new_msg_status, now, ("approval denied" if new_msg_status == "denied" else None), mid),
            )
            updated += 1

            # Close any existing approval tasks for this draft
            conn.execute(
                """
                UPDATE tasks
                SET status = 'done', updated_at = ?
                WHERE kind = 'finance.ar_reminder'
                  AND related_entity_type = 'outbound_message'
                  AND related_entity_id = ?
                  AND status IN ('open', 'in_progress')
                """,
                (now, mid),
            )

            if new_msg_status != "approved":
                continue

            # Create a follow-on "send" task (no auto-send in MVP)
            existing = conn.execute(
                """
                SELECT id FROM tasks
                WHERE kind = 'finance.ar_send'
                  AND related_entity_type = 'outbound_message'
                  AND related_entity_id = ?
                  AND status IN ('open', 'in_progress')
                LIMIT 1
                """,
                (mid,),
            ).fetchone()
            if existing:
                continue

            inv_no = ""
            inv_id = (r["invoice_id"] or "").strip()
            if inv_id:
                inv = conn.execute("SELECT invoice_number FROM invoices WHERE id = ? LIMIT 1", (inv_id,)).fetchone()
                inv_no = (inv["invoice_number"] if inv else "") or ""

            title = f"Send AR reminder: invoice {inv_no or '(no #)'} to {(r['to_email'] or '').strip()}"
            conn.execute(
                """
                INSERT INTO tasks (
                  id, kind, title, description, status, priority,
                  related_entity_type, related_entity_id,
                  created_at, updated_at, due_at, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    "finance.ar_send",
                    title,
                    (r["subject"] or "").strip(),
                    "open",
                    14,
                    "outbound_message",
                    mid,
                    now,
                    now,
                    None,
                    json.dumps({"approval_id": approval_id, "message_id": mid, "payload": payload}, ensure_ascii=False),
                ),
            )
            created_tasks += 1

    audit.append(
        actor=actor,
        action="finance_ar_reminder_decision_applied",
        scope="external_low",
        entity_type="approval",
        entity_id=approval_id,
        details={"approval_status": approval_status, "messages_updated": updated, "send_tasks_created": created_tasks},
    )

    return {"ok": True, "messages_updated": updated, "send_tasks_created": created_tasks}


def apply_finance_approval_decision(
    db: OpsDB,
    audit: AuditLogger,
    *,
    workflow: str,
    approval_id: str,
    approval_status: str,
    actor: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if workflow == "finance.ap_intake":
        return apply_finance_ap_intake_decision(
            db,
            audit,
            approval_id=approval_id,
            approval_status=approval_status,
            actor=actor,
            payload=payload,
        )
    if workflow == "finance.ar_reminder":
        return apply_finance_ar_reminder_decision(
            db,
            audit,
            approval_id=approval_id,
            approval_status=approval_status,
            actor=actor,
            payload=payload,
        )
    return {"ok": False, "error": f"unsupported finance workflow: {workflow}"}


class FinanceSpokes:
    """
    Thin orchestration wrapper used by `src.franklinops.server` (UI + API).

    Defaults to safe behavior:
    - AP intake creates invoices + review tasks + approval requests (shadow by default).
    - AR reminders produce drafts and route through approvals (no auto-send here).
    - Cashflow forecast can optionally create alert tasks.
    """

    def __init__(self, db: OpsDB, audit: AuditLogger, approvals: ApprovalService):
        self._db = db
        self._audit = audit
        self._approvals = approvals

    def scan_ap_intake(self, *, source: str = "", limit: int = 250) -> dict[str, Any]:
        return run_ap_intake(self._db, self._audit, self._approvals, source=(source or None), limit=int(limit))

    def import_cashflow_csv_from_artifact(self, *, artifact_id: str, source: str = "csv_cashflow") -> dict[str, Any]:
        src = (source or "").strip().lower()
        if src in {"csv_cashflow", "csv_waterfall", "csv"}:
            return import_cashflow_waterfall_csv(self._db, self._audit, artifact_id=artifact_id)
        raise ValueError(f"unsupported cashflow import source: {source}")

    def import_latest_cashflow_waterfall(self, *, source: Optional[str] = None) -> dict[str, Any]:
        """
        Convenience helper for operators: find the newest cashflow waterfall CSV artifact and import it.
        """
        params: list[Any] = []
        sql = """
        SELECT id, source, path
        FROM artifacts
        WHERE status = 'ingested'
          AND lower(path) LIKE '%cash%flow%waterfall%.csv'
        """
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY ingested_at DESC LIMIT 1"

        row = self._db.conn.execute(sql, params).fetchone()
        if not row:
            return {"ok": False, "error": "No cashflow waterfall CSV artifact found (ingest projects root first)."}

        artifact_id = row["id"]
        result = import_cashflow_waterfall_csv(self._db, self._audit, artifact_id=artifact_id)
        return {
            "ok": True,
            "artifact_id": artifact_id,
            "artifact_source": row["source"],
            "artifact_path": row["path"],
            **result,
        }

    def forecast_cashflow(self, *, start_week: Optional[str] = None, weeks: int = 12, create_alert_tasks: bool = True) -> dict[str, Any]:
        fc = cashflow_forecast(self._db, start_week=start_week, weeks=int(weeks))
        if not create_alert_tasks:
            return fc

        now = utcnow_iso()
        for wk in fc.get("weeks", []):
            week_start = wk.get("week_start")
            net_cents = int(wk.get("net_cents") or 0)
            if not week_start or net_cents >= 0:
                continue

            existing = self._db.conn.execute(
                """
                SELECT id FROM tasks
                WHERE kind = 'finance.cashflow_alert'
                  AND related_entity_type = 'cashflow_week'
                  AND related_entity_id = ?
                  AND status IN ('open', 'in_progress')
                """,
                (week_start,),
            ).fetchone()
            if existing:
                continue

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
                        uuid.uuid4().hex,
                        "finance.cashflow_alert",
                        f"Cashflow alert: {week_start} net ${net_cents/100:,.2f}",
                        "Net cashflow is negative for this week. Review payables/receivables timing.",
                        "open",
                        20,
                        "cashflow_week",
                        week_start,
                        now,
                        now,
                        week_start,
                        json.dumps(wk, ensure_ascii=False),
                    ),
                )

        return fc

    def run_ar_reminders(self, *, as_of: Optional[str] = None, max_records: int = 100, days_overdue: int = 1) -> dict[str, Any]:
        # Interpret days_overdue as "strictly past due by at least N days"
        if as_of is None:
            as_of_date = date.today()
        else:
            try:
                as_of_date = date.fromisoformat(as_of)
            except Exception:
                as_of_date = date.today()

        cutoff = (as_of_date.toordinal() - int(days_overdue))
        cutoff_date = date.fromordinal(cutoff) if cutoff > 0 else as_of_date
        return run_ar_reminders(
            self._db,
            self._audit,
            self._approvals,
            as_of=cutoff_date.isoformat(),
            limit=int(max_records),
        )

    def import_procore_export_csv_from_artifact(self, *, artifact_id: str) -> dict[str, Any]:
        return import_procore_invoices_export_csv(self._db, self._audit, artifact_id=artifact_id)


# End of finance_spokes.py
