"""
Procore Invoice Bridge — Connects fleet bookkeeper to FranklinOps Procore.

Uses existing FranklinOps Procore OAuth + import_procore_invoices_export_csv.
Flow: artifact (CSV) → FranklinOps import → OpsDB invoices → bookkeeper route.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProcoreInvoiceBridge:
    """
    Bridge between fleet bookkeeper and FranklinOps Procore.

    - Import: triggers FranklinOps import_procore_invoices_export_csv
    - Sync: reads OpsDB invoices and routes to bookkeeper plugin
    """

    def __init__(self, db=None, finance=None):
        self._db = db
        self._finance = finance

    def import_from_artifact(self, artifact_id: str, limit: int = 5000) -> dict[str, Any]:
        """Import Procore CSV from artifact. Requires FranklinOps finance_spokes."""
        if not self._finance:
            return {"error": "Finance spokes not available", "inserted": 0, "updated": 0}
        try:
            return self._finance.import_procore_export_csv_from_artifact(artifact_id=artifact_id)
        except Exception as e:
            logger.exception(f"Procore import failed: {e}")
            return {"error": str(e), "inserted": 0, "updated": 0}

    def list_invoices_for_bookkeeper(self, kind: str = "AP", limit: int = 100) -> list[dict[str, Any]]:
        """List invoices from OpsDB for bookkeeper routing."""
        if not self._db:
            return []
        try:
            rows = self._db.conn.execute(
                "SELECT id, kind, invoice_number, amount_cents, status, vendor_id, project_id FROM invoices WHERE kind = ? ORDER BY created_at DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.exception(f"List invoices failed: {e}")
            return []
