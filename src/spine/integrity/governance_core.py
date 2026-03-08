"""
Governance Core — Immutable governance engine for the Universal Spine.

Loads governance policies, validates scope, and provides policy lookup.
Extracted from src/core/governance_provenance.py and governance-policies.json.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

__all__ = ["GovernanceCore", "GovernanceScope", "compute_governance_hash"]


@dataclass
class GovernanceScope:
    """Governance scope definition from policies."""

    name: str
    description: str
    auto_execute: bool
    requires_evidence: bool
    requires_human_approval: bool
    max_concurrent: int
    max_retries: int
    timeout_seconds: int
    cost_limit_usd: float
    rate_limit_per_hour: int
    allowed_actions: list[str]
    approval_timeout_hours: Optional[int] = None
    requires_mfa: bool = False
    requires_security_review: bool = False
    requires_audit_trail: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GovernanceScope:
        """Build scope from governance-policies.json structure."""
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            auto_execute=d.get("auto_execute", False),
            requires_evidence=d.get("requires_evidence", True),
            requires_human_approval=d.get("requires_human_approval", True),
            max_concurrent=int(d.get("max_concurrent", 1)),
            max_retries=int(d.get("max_retries", 0)),
            timeout_seconds=int(d.get("timeout_seconds", 60)),
            cost_limit_usd=float(d.get("cost_limit_usd", 0)),
            rate_limit_per_hour=int(d.get("rate_limit_per_hour", 10)),
            allowed_actions=list(d.get("allowed_actions", [])),
            approval_timeout_hours=d.get("approval_timeout_hours"),
            requires_mfa=d.get("requires_mfa", False),
            requires_security_review=d.get("requires_security_review", False),
            requires_audit_trail=d.get("requires_audit_trail", False),
        )


def compute_governance_hash(policies_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Load governance policies and return version + SHA-256 hash.
    Returns empty dict if file not found.
    """
    path = policies_path or _find_governance_path()
    if not path:
        return {
            "version": None,
            "hash": None,
            "path": None,
            "error": "governance-policies.json not found",
        }

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        version = data.get("version", "unknown")
        canonical = json.dumps(data, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return {"version": version, "hash": h, "path": str(path), "error": None}
    except Exception as e:
        return {"version": None, "hash": None, "path": str(path), "error": str(e)}


def _find_governance_path() -> Optional[Path]:
    """Locate governance-policies.json (project root)."""
    candidates = [
        Path(__file__).resolve().parents[3] / "governance-policies.json",
        Path.cwd() / "governance-policies.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


class GovernanceCore:
    """
    Immutable governance engine. Loads policies once, provides scope lookup.
    """

    def __init__(self, policies_path: Optional[Path] = None) -> None:
        self._path = policies_path or _find_governance_path()
        self._data: dict[str, Any] = {}
        self._scopes: dict[str, GovernanceScope] = {}
        self._flow_config: dict[str, Any] = {}
        self._evidence_requirements: dict[str, Any] = {}
        if self._path:
            self._load()

    def _load(self) -> None:
        """Load and parse governance policies."""
        if not self._path or not self._path.exists():
            return
        raw = self._path.read_text(encoding="utf-8")
        self._data = json.loads(raw)
        scopes = self._data.get("governance_scopes", {})
        self._scopes = {
            k: GovernanceScope.from_dict(v) for k, v in scopes.items()
        }
        self._flow_config = self._data.get("flow_config", {})
        self._evidence_requirements = self._data.get("evidence_requirements", {})

    def get_scope(self, scope_id: str) -> Optional[GovernanceScope]:
        """Get governance scope by id (e.g. internal, external_low)."""
        return self._scopes.get(scope_id)

    def get_flow_config(self) -> dict[str, Any]:
        """Flow hardening config from governance (sanitize, rate limit, etc.)."""
        return dict(self._flow_config)

    def get_evidence_requirements(self) -> dict[str, Any]:
        """Evidence requirements (blake_birthmark, intent_verification, etc.)."""
        return dict(self._evidence_requirements)

    def is_action_allowed(self, scope_id: str, action: str) -> bool:
        """Check if action is allowed in the given scope."""
        scope = self.get_scope(scope_id)
        if not scope:
            return False
        return action in scope.allowed_actions

    def hash_info(self) -> dict[str, Any]:
        """Governance hash for audit and verification."""
        return compute_governance_hash(self._path)
