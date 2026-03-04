"""
OneDrive / Sharepoint Document Bridge — Connects file_keeper to FranklinOps ingest.

Uses hub_config roots (ONEDRIVE_PROJECTS, BIDDING, ATTACHMENTS) and ingest_roots.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OneDriveDocBridge:
    """
    Bridge between fleet file_keeper and FranklinOps document ingestion.

    - Runs ingest_roots with configured OneDrive paths
    - Returns ingested artifacts for file_keeper routing
    """

    def __init__(self, db=None, audit=None):
        self._db = db
        self._audit = audit

    def ingest_from_roots(self, roots: dict[str, str]) -> dict[str, Any]:
        """Run FranklinOps ingest_roots. Returns counts and results."""
        if not self._db or not self._audit:
            return {"error": "DB or audit not available", "counts": {}}
        try:
            from src.franklinops.doc_ingestion import ingest_roots
            return ingest_roots(self._db, self._audit, roots=roots)
        except Exception as e:
            logger.exception(f"OneDrive ingest failed: {e}")
            return {"error": str(e), "counts": {}}

    def get_roots_from_env(self) -> dict[str, str]:
        """Get OneDrive roots from hub_config."""
        try:
            from src.franklinops.hub_config import get_roots_from_env
            roots = get_roots_from_env()
            return {k: v for k, v in roots.items() if v and ("onedrive" in k or "pc_" in k)}
        except Exception:
            return {}
