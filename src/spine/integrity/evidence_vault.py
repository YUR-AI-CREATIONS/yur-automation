"""
Evidence Vault — Cryptographic evidence storage for the Universal Spine.

Stores and retrieves governance evidence (blake_birthmark, intent, signatures).
Domain-agnostic; works with any key-value or DB backend.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

__all__ = ["EvidenceVault", "Evidence", "create_evidence"]


@dataclass
class Evidence:
    """Governance evidence payload."""

    blake_birthmark: str
    intent: str
    timestamp: str
    signature: str = ""
    pqc_signature: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        d: dict[str, Any] = {
            "blake_birthmark": self.blake_birthmark,
            "intent": self.intent,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }
        if self.pqc_signature:
            d["pqc_signature"] = self.pqc_signature
        if self.extra:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Evidence:
        """Deserialize from storage."""
        return cls(
            blake_birthmark=d.get("blake_birthmark", ""),
            intent=d.get("intent", ""),
            timestamp=d.get("timestamp", ""),
            signature=d.get("signature", ""),
            pqc_signature=d.get("pqc_signature"),
            extra=d.get("extra", {}),
        )


def create_evidence(
    *,
    blake_birthmark: str,
    intent: str,
    secret: Optional[str] = None,
) -> Evidence:
    """
    Create signed evidence for governance decisions.
    Uses HMAC-SHA256 when secret is provided.
    """
    ts = datetime.now(timezone.utc).isoformat()
    sec = (secret or os.getenv("TRINITY_SIGNING_SECRET", "")).strip()
    canonical = json.dumps(
        {"blake_birthmark": blake_birthmark, "intent": intent, "timestamp": ts},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    sig = hmac.new(sec.encode("utf-8"), canonical, digestmod="sha256").hexdigest() if sec else ""
    return Evidence(
        blake_birthmark=blake_birthmark,
        intent=intent,
        timestamp=ts,
        signature=sig,
    )


def _evidence_id(evidence: Evidence) -> str:
    """Content-addressable ID for evidence."""
    canonical = json.dumps(evidence.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class EvidenceVault:
    """
    Cryptographic evidence storage. In-memory by default; pluggable persistence.
    """

    def __init__(
        self,
        store: Optional[Callable[[str, dict[str, Any]], None]] = None,
        load: Optional[Callable[[str], Optional[dict[str, Any]]]] = None,
    ) -> None:
        """
        Args:
            store: Optional (evidence_id, evidence_dict) -> None for persistence.
            load: Optional (evidence_id) -> evidence_dict for retrieval.
        """
        self._store_fn = store
        self._load_fn = load
        self._cache: dict[str, dict[str, Any]] = {}

    def put(self, evidence: Evidence) -> str:
        """Store evidence. Returns content-addressable id."""
        eid = _evidence_id(evidence)
        d = evidence.to_dict()
        self._cache[eid] = d
        if self._store_fn:
            self._store_fn(eid, d)
        return eid

    def get(self, evidence_id: str) -> Optional[Evidence]:
        """Retrieve evidence by id."""
        d = self._cache.get(evidence_id)
        if d is None and self._load_fn:
            d = self._load_fn(evidence_id)
            if d:
                self._cache[evidence_id] = d
        if d:
            return Evidence.from_dict(d)
        return None

    def verify_signature(self, evidence: Evidence, secret: Optional[str] = None) -> bool:
        """Verify HMAC signature if present."""
        if not evidence.signature:
            return True
        sec = (secret or os.getenv("TRINITY_SIGNING_SECRET", "")).strip()
        if not sec:
            return False
        canonical = json.dumps(
            {
                "blake_birthmark": evidence.blake_birthmark,
                "intent": evidence.intent,
                "timestamp": evidence.timestamp,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected = hmac.new(sec.encode("utf-8"), canonical, digestmod="sha256").hexdigest()
        return hmac.compare_digest(expected, evidence.signature)
