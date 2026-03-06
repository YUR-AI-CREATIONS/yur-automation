"""
Governance provenance: hash of governance-policies.json for audit and verification.

Anyone can verify what governed a decision by checking the hash at startup.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _find_governance_path() -> Path | None:
    """Locate governance-policies.json (project root)."""
    candidates = [
        Path(__file__).resolve().parents[2] / "governance-policies.json",
        Path.cwd() / "governance-policies.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def compute_governance_hash() -> dict[str, Any]:
    """
    Load governance-policies.json and return version + SHA-256 hash.
    Returns empty dict if file not found.
    """
    path = _find_governance_path()
    if not path:
        return {"version": None, "hash": None, "path": None, "error": "governance-policies.json not found"}

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        version = data.get("version", "unknown")
        # Canonical JSON (sorted keys) for deterministic hash
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return {"version": version, "hash": h, "path": str(path), "error": None}
    except Exception as e:
        return {"version": None, "hash": None, "path": str(path), "error": str(e)}
