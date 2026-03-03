from __future__ import annotations

import csv
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..audit import AuditLogger
from ..opsdb import OpsDB


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
    raw = raw.replace("$", "").replace(",", "")
    try:
        return int(round(float(raw) * 100))
    except Exception:
        return None


def export_invoices_csv(
    db: OpsDB,
    *,
    out_path: Path,
    kind: Optional[str] = None,
    status: Optional[str] = None,
) -> dict[str, Any]:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    params: list[Any] = []
    sql = """
    SELECT id, kind, vendor_id, customer_id, project_id, invoice_number, invoice_date, due_date,
           amount_cents, currency, status, source_artifact_id, created_at, updated_at
    FROM invoices
    WHERE 1=1
    """
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY updated_at DESC"

    rows = db.conn.execute(sql, params).fetchall()
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "id",
                "kind",
                "vendor_id",
                "customer_id",
                "project_id",
                "invoice_number",
                "invoice_date",
                "due_date",
                "amount_cents",
                "currency",
                "status",
                "source_artifact_id",
                "created_at",
                "updated_at",
            ]
        )
        for r in rows:
            w.writerow([r[c] for c in r.keys()])

    return {"rows": int(len(rows)), "path": str(out_path)}


def export_cashflow_lines_csv(db: OpsDB, *, out_path: Path, start_week: Optional[str] = None) -> dict[str, Any]:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    params: list[Any] = []
    sql = """
    SELECT id, project_id, week_start, category, amount_cents, direction, source, source_ref, created_at
    FROM cashflow_lines
    WHERE 1=1
    """
    if start_week:
        sql += " AND week_start >= ?"
        params.append(start_week)
    sql += " ORDER BY week_start ASC"

    rows = db.conn.execute(sql, params).fetchall()
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "project_id", "week_start", "category", "amount_cents", "direction", "source", "source_ref", "created_at"])
        for r in rows:
            w.writerow([r[c] for c in r.keys()])

    return {"rows": int(len(rows)), "path": str(out_path)}


def import_payments_csv_from_artifact(db: OpsDB, audit: AuditLogger, *, artifact_id: str, source: str = "accounting_import") -> dict[str, Any]:
    art = db.conn.execute("SELECT id, extracted_text, metadata_json FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not art:
        raise KeyError(f"artifact not found: {artifact_id}")

    meta = json.loads(art["metadata_json"]) if art["metadata_json"] else {}
    abs_path = meta.get("abs_path")
    csv_path = Path(abs_path) if abs_path else None
    if not (csv_path and csv_path.exists()):
        raise FileNotFoundError("payments import requires a local CSV file path (artifact metadata 'abs_path').")

    inserted = 0
    skipped = 0
    now = utcnow_iso()

    with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_lc = {((k or "").strip().lower()): (v or "").strip() for k, v in row.items() if k}
            invoice_id = row_lc.get("invoice_id") or row_lc.get("id") or ""
            invoice_number = row_lc.get("invoice_number") or row_lc.get("invoice") or ""
            amount_raw = row_lc.get("amount_cents") or row_lc.get("amount_paid") or row_lc.get("amount") or ""
            paid_date = _parse_date(row_lc.get("paid_date") or row_lc.get("date") or "")

            amount_cents = int(amount_raw) if amount_raw.isdigit() else (_parse_money_to_cents(amount_raw) or 0)
            if amount_cents <= 0:
                skipped += 1
                continue

            inv = None
            if invoice_id:
                inv = db.conn.execute("SELECT id, amount_cents FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if not inv and invoice_number:
                inv = db.conn.execute(
                    "SELECT id, amount_cents FROM invoices WHERE invoice_number = ? ORDER BY updated_at DESC LIMIT 1",
                    (invoice_number,),
                ).fetchone()

            if not inv:
                skipped += 1
                continue

            pay_id = uuid.uuid4().hex
            with db.tx() as conn:
                conn.execute(
                    """
                    INSERT INTO payments (id, invoice_id, paid_date, amount_cents, source, source_ref, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (pay_id, inv["id"], paid_date, amount_cents, source, artifact_id, now),
                )

                total_paid = conn.execute(
                    "SELECT COALESCE(SUM(amount_cents),0) AS paid FROM payments WHERE invoice_id = ?",
                    (inv["id"],),
                ).fetchone()["paid"]
                inv_total = int(inv["amount_cents"] or 0)
                new_status = "paid" if total_paid >= inv_total and inv_total > 0 else "partial"
                conn.execute("UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, inv["id"]))

            inserted += 1

    audit.append(
        actor="system",
        action="accounting_payments_imported",
        scope="external_low",
        entity_type="artifact",
        entity_id=artifact_id,
        details={"inserted": inserted, "skipped": skipped},
    )
    return {"inserted": inserted, "skipped": skipped}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _get_or_create_vendor(conn, *, name: str) -> str:
    nm = (name or "").strip() or "Unknown Vendor"
    row = conn.execute("SELECT id FROM vendors WHERE lower(name) = lower(?) LIMIT 1", (nm,)).fetchone()
    if row:
        return row["id"]
    vendor_id = uuid.uuid4().hex
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO vendors (id, name, email, phone, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (vendor_id, nm, None, None, now, now),
    )
    return vendor_id


def _get_or_create_customer(conn, *, name: str, email: str = "") -> str:
    nm = (name or "").strip() or "Unknown Customer"
    row = conn.execute("SELECT id FROM customers WHERE lower(name) = lower(?) LIMIT 1", (nm,)).fetchone()
    if row:
        # Opportunistic: fill missing email
        if email:
            conn.execute(
                "UPDATE customers SET email = COALESCE(NULLIF(email,''), ?), updated_at = ? WHERE id = ?",
                (email.strip().lower(), utcnow_iso(), row["id"]),
            )
        return row["id"]
    cust_id = uuid.uuid4().hex
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO customers (id, name, email, phone, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (cust_id, nm, (email.strip().lower() if email else None), None, now, now),
    )
    return cust_id


def _get_or_create_project(conn, *, name: str) -> Optional[str]:
    nm = (name or "").strip()
    if not nm:
        return None
    row = conn.execute("SELECT id FROM projects WHERE lower(name) = lower(?) LIMIT 1", (nm,)).fetchone()
    if row:
        return row["id"]
    proj_id = uuid.uuid4().hex
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO projects (id, name, status, customer_id, external_ref, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (proj_id, nm, "unknown", None, None, now, now),
    )
    return proj_id


def import_invoices_csv_from_artifact(
    db: OpsDB,
    audit: AuditLogger,
    *,
    artifact_id: str,
    source: str = "accounting_import",
    default_kind: Optional[str] = None,  # AP | AR (optional)
    limit: int = 5000,
) -> dict[str, Any]:
    """
    Import invoices from a local CSV file referenced by an ingested artifact.

    Supported inputs:
    - FranklinOps exports (columns: id, kind, vendor_id, customer_id, project_id, ...)
    - External exports with name-based columns (vendor_name/customer_name/project_name, amount/total, etc.)

    Notes:
    - This is read-only integration from the accounting system's perspective (CSV import).
    - Creates/updates invoices and (optionally) corresponding cashflow_lines anchored at due_date.
    """
    art = db.conn.execute("SELECT id, metadata_json FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not art:
        raise KeyError(f"artifact not found: {artifact_id}")

    meta = json.loads(art["metadata_json"]) if art["metadata_json"] else {}
    abs_path = meta.get("abs_path")
    csv_path = Path(abs_path) if abs_path else None
    if not (csv_path and csv_path.exists()):
        raise FileNotFoundError("invoices import requires a local CSV file path (artifact metadata 'abs_path').")

    inserted = 0
    updated = 0
    skipped = 0
    cashflow_lines = 0
    now = utcnow_iso()

    def as_kind(raw: str) -> str:
        k = (raw or "").strip().upper()
        return k if k in {"AP", "AR"} else ""

    with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= int(limit):
                break

            try:
                cols = {_norm(k): (v or "").strip() for k, v in row.items() if k}

                invoice_id = cols.get("id") or cols.get("invoiceid") or ""
                kind = as_kind(cols.get("kind") or "") or as_kind(default_kind or "")

                invoice_number = cols.get("invoicenumber") or cols.get("invoice") or cols.get("invnumber") or cols.get("number") or ""
                invoice_date = _parse_date(cols.get("invoicedate") or cols.get("date") or "") or None
                due_date = _parse_date(cols.get("duedate") or cols.get("due") or "") or None

                amount_raw = cols.get("amountcents") or cols.get("amount") or cols.get("total") or cols.get("invoiceamount") or ""
                if (amount_raw or "").strip().isdigit():
                    amount_cents = int(amount_raw)
                else:
                    amount_cents = _parse_money_to_cents(amount_raw) or 0

                currency = (cols.get("currency") or "USD").strip().upper() or "USD"
                status = (cols.get("status") or "imported").strip().lower() or "imported"

                vendor_id = cols.get("vendorid") or ""
                vendor_name = cols.get("vendorname") or cols.get("vendor") or cols.get("company") or ""

                customer_id = cols.get("customerid") or ""
                customer_name = cols.get("customername") or cols.get("customer") or cols.get("client") or ""
                customer_email = cols.get("customeremail") or cols.get("email") or ""

                project_id = cols.get("projectid") or ""
                project_name = cols.get("projectname") or cols.get("project") or cols.get("job") or cols.get("jobname") or ""

                # Infer kind if missing
                if not kind:
                    if customer_id or customer_name:
                        kind = "AR"
                    elif vendor_id or vendor_name:
                        kind = "AP"

                if not kind or amount_cents <= 0:
                    skipped += 1
                    continue

                direction = "inflow" if kind == "AR" else "outflow"

                with db.tx() as conn:
                    # Resolve vendor/customer/project identifiers
                    if kind == "AP":
                        if not vendor_id and vendor_name:
                            vendor_id = _get_or_create_vendor(conn, name=vendor_name)
                        if not vendor_id:
                            # AP invoice without a vendor is not actionable.
                            raise ValueError("missing vendor for AP invoice")
                    else:
                        if not customer_id and (customer_name or customer_email):
                            customer_id = _get_or_create_customer(conn, name=(customer_name or customer_email or "Customer"), email=customer_email)
                        if not customer_id:
                            raise ValueError("missing customer for AR invoice")

                    if not project_id and project_name:
                        project_id = _get_or_create_project(conn, name=project_name) or ""

                    existing = None
                    if invoice_id:
                        existing = conn.execute("SELECT id FROM invoices WHERE id = ? LIMIT 1", (invoice_id,)).fetchone()

                    if not existing and invoice_number:
                        existing = conn.execute(
                            """
                            SELECT id
                            FROM invoices
                            WHERE kind = ?
                              AND invoice_number = ?
                              AND COALESCE(vendor_id,'') = COALESCE(?, '')
                              AND COALESCE(customer_id,'') = COALESCE(?, '')
                              AND (invoice_date = ? OR invoice_date IS NULL OR ? IS NULL)
                            ORDER BY updated_at DESC
                            LIMIT 1
                            """,
                            (kind, invoice_number, (vendor_id or ""), (customer_id or ""), invoice_date, invoice_date),
                        ).fetchone()

                    if existing:
                        use_id = existing["id"]
                        conn.execute(
                            """
                            UPDATE invoices
                            SET vendor_id = ?,
                                customer_id = ?,
                                project_id = COALESCE(NULLIF(?, ''), project_id),
                                invoice_date = COALESCE(?, invoice_date),
                                due_date = COALESCE(?, due_date),
                                amount_cents = ?,
                                currency = ?,
                                status = ?,
                                source_artifact_id = ?,
                                updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                (vendor_id or None),
                                (customer_id or None),
                                (project_id or None),
                                invoice_date,
                                due_date,
                                int(amount_cents),
                                currency,
                                status,
                                artifact_id,
                                now,
                                use_id,
                            ),
                        )
                        updated += 1
                    else:
                        use_id = invoice_id or uuid.uuid4().hex
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
                                use_id,
                                kind,
                                (vendor_id or None),
                                (customer_id or None),
                                (project_id or None),
                                invoice_number,
                                invoice_date,
                                due_date,
                                int(amount_cents),
                                currency,
                                status,
                                artifact_id,
                                now,
                                now,
                            ),
                        )
                        inserted += 1

                    # Cashflow projection line (idempotent)
                    conn.execute("DELETE FROM cashflow_lines WHERE source = ? AND source_ref = ?", (source, use_id))
                    if due_date:
                        conn.execute(
                            """
                            INSERT INTO cashflow_lines (
                              id, project_id, week_start, category, amount_cents, direction,
                              source, source_ref, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                uuid.uuid4().hex,
                                (project_id or None),
                                due_date,
                                f"{kind} invoice {invoice_number or use_id}".strip()[:240],
                                int(amount_cents),
                                direction,
                                source,
                                use_id,
                                now,
                            ),
                        )
                        cashflow_lines += 1

            except Exception:
                skipped += 1
                continue

    audit.append(
        actor="system",
        action="accounting_invoices_imported",
        scope="external_low",
        entity_type="artifact",
        entity_id=artifact_id,
        details={"inserted": inserted, "updated": updated, "skipped": skipped, "cashflow_lines": cashflow_lines, "source": source},
    )
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "cashflow_lines": cashflow_lines}

