"""
Database migrations for FranklinOps (multi-tenancy, schema evolution).

Run on startup to ensure schema is up to date.
"""

from __future__ import annotations

from pathlib import Path

from .opsdb import OpsDB


MIGRATIONS: list[tuple[str, str]] = [
    (
        "001_tenants",
        """
        CREATE TABLE IF NOT EXISTS tenants (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          region TEXT,
          data_residency_zone TEXT,
          retention_days INTEGER NOT NULL DEFAULT 365,
          hipaa_enabled INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        INSERT OR IGNORE INTO tenants (id, name, region, data_residency_zone, retention_days, hipaa_enabled, created_at, updated_at)
        VALUES ('default', 'Default Tenant', NULL, NULL, 365, 0, datetime('now'), datetime('now'));
        """,
    ),
    (
        "002_audit_tenant",
        """
        ALTER TABLE audit_events ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_id ON audit_events(tenant_id);
        """,
    ),
    (
        "003_autonomy_tenant",
        """
        ALTER TABLE autonomy_settings ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_autonomy_settings_tenant_id ON autonomy_settings(tenant_id);
        """,
    ),
    (
        "004_approvals_tenant",
        """
        ALTER TABLE approvals ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_approvals_tenant_id ON approvals(tenant_id);
        """,
    ),
    (
        "005_tasks_tenant",
        """
        ALTER TABLE tasks ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_tasks_tenant_id ON tasks(tenant_id);
        """,
    ),
    (
        "006_artifacts_tenant",
        """
        ALTER TABLE artifacts ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_artifacts_tenant_id ON artifacts(tenant_id);
        """,
    ),
    (
        "007_doc_chunks_tenant",
        """
        ALTER TABLE doc_chunks ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_tenant_id ON doc_chunks(tenant_id);
        """,
    ),
    (
        "008_doc_index_runs_tenant",
        """
        ALTER TABLE doc_index_runs ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_doc_index_runs_tenant_id ON doc_index_runs(tenant_id);
        """,
    ),
    (
        "009_customers_tenant",
        """
        ALTER TABLE customers ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_customers_tenant_id ON customers(tenant_id);
        """,
    ),
    (
        "010_vendors_tenant",
        """
        ALTER TABLE vendors ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_vendors_tenant_id ON vendors(tenant_id);
        """,
    ),
    (
        "011_projects_tenant",
        """
        ALTER TABLE projects ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_projects_tenant_id ON projects(tenant_id);
        """,
    ),
    (
        "012_invoices_tenant",
        """
        ALTER TABLE invoices ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_invoices_tenant_id ON invoices(tenant_id);
        """,
    ),
    (
        "013_sales_leads_tenant",
        """
        ALTER TABLE sales_leads ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_sales_leads_tenant_id ON sales_leads(tenant_id);
        """,
    ),
    (
        "014_sales_opportunities_tenant",
        """
        ALTER TABLE sales_opportunities ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_sales_opportunities_tenant_id ON sales_opportunities(tenant_id);
        """,
    ),
    (
        "015_outbound_messages_tenant",
        """
        ALTER TABLE outbound_messages ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_outbound_messages_tenant_id ON outbound_messages(tenant_id);
        """,
    ),
    (
        "016_payments_tenant",
        """
        ALTER TABLE payments ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_payments_tenant_id ON payments(tenant_id);
        """,
    ),
    (
        "017_cashflow_lines_tenant",
        """
        ALTER TABLE cashflow_lines ADD COLUMN tenant_id TEXT DEFAULT 'default';
        CREATE INDEX IF NOT EXISTS idx_cashflow_lines_tenant_id ON cashflow_lines(tenant_id);
        """,
    ),
    (
        "018_tenant_data_residency",
        """
        ALTER TABLE tenants ADD COLUMN data_residency_zone TEXT;
        """,
    ),
    (
        "019_project_control_logs",
        """
        CREATE TABLE IF NOT EXISTS project_control_logs (
          id TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          log_type TEXT NOT NULL,
          entry_data TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          tenant_id TEXT DEFAULT 'default',
          created_by TEXT,
          status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE INDEX IF NOT EXISTS idx_pc_logs_source ON project_control_logs(source);
        CREATE INDEX IF NOT EXISTS idx_pc_logs_tenant ON project_control_logs(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_pc_logs_created_at ON project_control_logs(created_at);
        """,
    ),
    (
        "020_tenant_white_label",
        """
        ALTER TABLE tenants ADD COLUMN branding_name TEXT;
        ALTER TABLE tenants ADD COLUMN branding_logo_url TEXT;
        ALTER TABLE tenants ADD COLUMN support_email TEXT;
        ALTER TABLE tenants ADD COLUMN custom_domain TEXT;
        """,
    ),
    (
        "021_flows_registry",
        """
        CREATE TABLE IF NOT EXISTS flows_registry (
          flow_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          direction TEXT NOT NULL DEFAULT 'incoming',
          scope TEXT NOT NULL DEFAULT 'internal',
          handler_type TEXT NOT NULL DEFAULT 'passthrough',
          handler_config TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          tenant_id TEXT DEFAULT 'default'
        );
        CREATE INDEX IF NOT EXISTS idx_flows_tenant ON flows_registry(tenant_id);
        """,
    ),
]


def _migrations_table_exists(conn) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
    ).fetchone()
    return row is not None


def _ensure_migrations_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
          id TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL
        )
        """
    )


def _applied_migrations(conn) -> set[str]:
    if not _migrations_table_exists(conn):
        return set()
    rows = conn.execute("SELECT id FROM _migrations").fetchall()
    return {r["id"] for r in rows}


def _is_ignorable_sqlite_error(e: Exception) -> bool:
    """Return True if migration can safely ignore this error (idempotency)."""
    msg = str(e).lower()
    return (
        "duplicate column name" in msg
        or "already exists" in msg
        or "unique constraint" in msg
    )


def run_migrations(db: OpsDB) -> list[str]:
    """
    Run pending migrations. Returns list of applied migration IDs.
    Idempotent: duplicate column/index/table errors are ignored.
    """
    import logging
    logger = logging.getLogger(__name__)
    applied: list[str] = []
    conn = db.conn

    _ensure_migrations_table(conn)
    done = _applied_migrations(conn)

    for mig_id, sql in MIGRATIONS:
        if mig_id in done:
            continue
        try:
            for stmt in sql.strip().split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    conn.execute(stmt)
                except Exception as e:
                    if _is_ignorable_sqlite_error(e):
                        logger.debug("Migration %s: ignorable SQLite error: %s", mig_id, e)
                        continue
                    raise
            conn.execute(
                "INSERT OR IGNORE INTO _migrations (id, applied_at) VALUES (?, datetime('now'))",
                (mig_id,),
            )
            conn.commit()
            applied.append(mig_id)
            logger.info("Migration applied: %s", mig_id)
        except Exception:
            conn.rollback()
            raise

    return applied
