from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  scope TEXT,
  entity_type TEXT,
  entity_id TEXT,
  details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_events_ts ON audit_events(ts);

CREATE TABLE IF NOT EXISTS autonomy_settings (
  workflow TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  scope TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  workflow TEXT NOT NULL,
  scope TEXT NOT NULL,
  mode_at_request TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_at TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  evidence_json TEXT,
  decision_by TEXT,
  decision_at TEXT,
  decision_notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_approvals_requested_at ON approvals(requested_at);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  related_entity_type TEXT,
  related_entity_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  due_at TEXT,
  evidence_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  path TEXT NOT NULL,
  content_type TEXT,
  birthmark TEXT,
  size_bytes INTEGER,
  modified_at TEXT,
  ingested_at TEXT NOT NULL,
  status TEXT NOT NULL,
  extracted_text TEXT,
  metadata_json TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_source_path ON artifacts(source, path);
CREATE INDEX IF NOT EXISTS idx_artifacts_ingested_at ON artifacts(ingested_at);

CREATE TABLE IF NOT EXISTS doc_chunks (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  birthmark TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_artifact_id ON doc_chunks(artifact_id);

CREATE TABLE IF NOT EXISTS doc_index_runs (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  embeddings_backend TEXT NOT NULL,
  index_backend TEXT NOT NULL,
  artifacts_indexed INTEGER NOT NULL,
  chunks_indexed INTEGER NOT NULL,
  index_path TEXT NOT NULL,
  meta_path TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doc_index_runs_created_at ON doc_index_runs(created_at);

CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendors (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  customer_id TEXT,
  external_ref TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS invoices (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  vendor_id TEXT,
  customer_id TEXT,
  project_id TEXT,
  invoice_number TEXT,
  invoice_date TEXT,
  due_date TEXT,
  amount_cents INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USD',
  status TEXT NOT NULL,
  source_artifact_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(vendor_id) REFERENCES vendors(id),
  FOREIGN KEY(customer_id) REFERENCES customers(id),
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(source_artifact_id) REFERENCES artifacts(id)
);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_kind ON invoices(kind);

CREATE TABLE IF NOT EXISTS payments (
  id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL,
  paid_date TEXT,
  amount_cents INTEGER NOT NULL,
  source TEXT NOT NULL,
  source_ref TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(invoice_id) REFERENCES invoices(id)
);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_paid_date ON payments(paid_date);

CREATE TABLE IF NOT EXISTS cashflow_lines (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  week_start TEXT NOT NULL,
  category TEXT,
  amount_cents INTEGER NOT NULL,
  direction TEXT NOT NULL,
  source TEXT NOT NULL,
  source_ref TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_cashflow_lines_week_start ON cashflow_lines(week_start);

CREATE TABLE IF NOT EXISTS sales_leads (
  id TEXT PRIMARY KEY,
  name TEXT,
  company TEXT,
  email TEXT,
  phone TEXT,
  status TEXT NOT NULL,
  suppressed INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  source_artifact_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_contacted_at TEXT,
  notes TEXT,
  metadata_json TEXT,
  FOREIGN KEY(source_artifact_id) REFERENCES artifacts(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_leads_email ON sales_leads(email);
CREATE INDEX IF NOT EXISTS idx_sales_leads_status ON sales_leads(status);

CREATE TABLE IF NOT EXISTS sales_opportunities (
  id TEXT PRIMARY KEY,
  lead_id TEXT NOT NULL,
  project_name TEXT NOT NULL,
  stage TEXT NOT NULL,
  bid_due_date TEXT,
  estimated_value_cents INTEGER,
  source_artifact_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(lead_id) REFERENCES sales_leads(id),
  FOREIGN KEY(source_artifact_id) REFERENCES artifacts(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_opps_source_artifact_id ON sales_opportunities(source_artifact_id);
CREATE INDEX IF NOT EXISTS idx_sales_opps_stage ON sales_opportunities(stage);

CREATE TABLE IF NOT EXISTS outbound_messages (
  id TEXT PRIMARY KEY,
  workflow TEXT NOT NULL,
  lead_id TEXT,
  opportunity_id TEXT,
  invoice_id TEXT,
  channel TEXT NOT NULL,
  to_email TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL,
  approval_id TEXT,
  provider TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  sent_at TEXT,
  error TEXT,
  metadata_json TEXT,
  FOREIGN KEY(lead_id) REFERENCES sales_leads(id),
  FOREIGN KEY(opportunity_id) REFERENCES sales_opportunities(id),
  FOREIGN KEY(invoice_id) REFERENCES invoices(id)
);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_status ON outbound_messages(status);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_workflow ON outbound_messages(workflow);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_lead_id ON outbound_messages(lead_id);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_invoice_id ON outbound_messages(invoice_id);
"""


class OpsDB:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        # Run migrations (multi-tenancy, etc.)
        from .migrations import run_migrations
        run_migrations(self)

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()

