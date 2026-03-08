"""
Universal Settings — Env-first configuration for any domain.

Extends domain-specific profiles with environment overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(float(raw.strip()))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except Exception:
        return default


@dataclass
class UniversalSettings:
    """
    Universal settings: domain-aware, env-first, YAML-mergeable.

    - SPINE_DOMAIN env var selects profile (construction, healthcare, finance, generic)
    - Falls back to FRANKLINOPS_* env vars for backward compatibility
    - Domain profiles override defaults; env overrides everything
    """

    # Domain and identity
    domain: str
    spine_id: str

    # Data directories (domain-specific paths)
    data_dir: Path
    db_path: Path
    audit_jsonl_path: Path

    # LLM configuration
    ollama_first: bool
    ollama_api_url: str
    ollama_model: str
    openai_api_key: str
    openai_model: str
    openai_temperature: float
    embeddings_model: str

    # Governance and risk
    default_authority_level: str
    default_governance_scope: str
    risk_max_approval_amount: float
    rate_limit_per_hour: int
    max_cost_per_mission: float

    # UI and UX
    enable_proactive_assistance: bool
    enable_onboarding_wizard: bool
    user_experience_level: str

    # Server
    server_host: str
    server_port: int

    # Security
    rbac_enabled: bool
    api_keys: list[str]

    # Air-gap mode (security feature)
    air_gap_mode: bool

    def __init__(
        self,
        domain: Optional[str] = None,
        profile_overrides: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize from domain profile + env overrides."""
        # Determine domain from env or arg
        self.domain = domain or os.getenv("SPINE_DOMAIN", "generic").lower()
        self.spine_id = os.getenv("SPINE_ID", f"spine-{self.domain}")

        # Load domain profile (phase 2, for now use defaults)
        from .domain_loader import DomainLoader
        loader = DomainLoader()
        profile = loader.load(self.domain)

        # Merge: profile defaults < overrides < env
        cfg = {**profile, **(profile_overrides or {})}

        # Data directories (domain-specific or env override)
        self.data_dir = Path(
            os.getenv(
                "SPINE_DATA_DIR",
                cfg.get("data_dir", f"data/{self.domain}"),
            )
        )
        self.db_path = Path(
            os.getenv(
                "SPINE_DB_PATH",
                cfg.get("db_path", f"{self.data_dir}/spine.db"),
            )
        )
        self.audit_jsonl_path = Path(
            os.getenv(
                "SPINE_AUDIT_JSONL_PATH",
                cfg.get("audit_jsonl_path", f"{self.data_dir}/audit.jsonl"),
            )
        )

        # LLM configuration
        self.openai_api_key = os.getenv(
            "OPENAI_API_KEY", cfg.get("openai_api_key", "")
        )
        self.openai_model = os.getenv(
            "SPINE_OPENAI_MODEL",
            cfg.get("openai_model", "gpt-4"),
        )
        self.openai_temperature = _env_float(
            "SPINE_OPENAI_TEMPERATURE",
            cfg.get("openai_temperature", 0.3),
        )

        self.ollama_api_url = os.getenv(
            "SPINE_OLLAMA_API_URL",
            cfg.get("ollama_api_url", "http://localhost:11434/api/generate"),
        )
        self.ollama_model = os.getenv(
            "SPINE_OLLAMA_MODEL", cfg.get("ollama_model", "llama3")
        )

        # Ollama first: true if env says so, or if no OpenAI key
        _ollama_first = os.getenv("SPINE_OLLAMA_FIRST", "").lower()
        if _ollama_first in ("true", "1", "yes"):
            self.ollama_first = True
        elif _ollama_first in ("false", "0", "no"):
            self.ollama_first = False
        else:
            self.ollama_first = cfg.get(
                "ollama_first",
                not bool((self.openai_api_key or "").strip()),
            )

        self.embeddings_model = os.getenv(
            "SPINE_EMBEDDINGS_MODEL",
            cfg.get("embeddings_model", "all-MiniLM-L6-v2"),
        )

        # Governance and risk
        self.default_authority_level = os.getenv(
            "SPINE_DEFAULT_AUTHORITY_LEVEL",
            cfg.get("default_authority_level", "SEMI_AUTO"),
        )
        self.default_governance_scope = os.getenv(
            "SPINE_DEFAULT_GOVERNANCE_SCOPE",
            cfg.get("default_governance_scope", "internal"),
        )
        self.risk_max_approval_amount = _env_float(
            "SPINE_RISK_MAX_APPROVAL_AMOUNT",
            cfg.get("risk_max_approval_amount", 5000.0),
        )
        self.rate_limit_per_hour = _env_int(
            "SPINE_RATE_LIMIT_PER_HOUR",
            cfg.get("rate_limit_per_hour", 200),
        )
        self.max_cost_per_mission = _env_float(
            "SPINE_MAX_COST_PER_MISSION",
            cfg.get("max_cost_per_mission", 1000.0),
        )

        # UI and UX
        _proactive = os.getenv("SPINE_ENABLE_PROACTIVE_ASSISTANCE", "").lower()
        if _proactive in ("true", "1", "yes"):
            self.enable_proactive_assistance = True
        elif _proactive in ("false", "0", "no"):
            self.enable_proactive_assistance = False
        else:
            self.enable_proactive_assistance = cfg.get(
                "enable_proactive_assistance", True
            )

        _wizard = os.getenv("SPINE_ENABLE_ONBOARDING_WIZARD", "").lower()
        if _wizard in ("true", "1", "yes"):
            self.enable_onboarding_wizard = True
        elif _wizard in ("false", "0", "no"):
            self.enable_onboarding_wizard = False
        else:
            self.enable_onboarding_wizard = cfg.get("enable_onboarding_wizard", True)

        self.user_experience_level = os.getenv(
            "SPINE_USER_EXPERIENCE_LEVEL",
            cfg.get("user_experience_level", "beginner"),
        )

        # Server
        self.server_host = os.getenv(
            "SPINE_SERVER_HOST", cfg.get("server_host", "127.0.0.1")
        )
        self.server_port = _env_int(
            "SPINE_SERVER_PORT", cfg.get("server_port", 8844)
        )

        # Security
        _rbac = os.getenv("SPINE_RBAC_ENABLED", "").lower()
        if _rbac in ("true", "1", "yes"):
            self.rbac_enabled = True
        elif _rbac in ("false", "0", "no"):
            self.rbac_enabled = False
        else:
            self.rbac_enabled = cfg.get("rbac_enabled", False)

        _keys = os.getenv("SPINE_API_KEYS", "").strip()
        if _keys:
            self.api_keys = [k.strip() for k in _keys.split(",") if k.strip()]
        else:
            self.api_keys = cfg.get("api_keys", [])

        # Air-gap mode
        _air_gap = os.getenv("SPINE_AIR_GAP_MODE", "").lower()
        if _air_gap in ("true", "1", "yes"):
            self.air_gap_mode = True
        elif _air_gap in ("false", "0", "no"):
            self.air_gap_mode = False
        else:
            self.air_gap_mode = cfg.get("air_gap_mode", False)

    def validate_startup(self) -> list[str]:
        """Validate critical settings; return list of warnings."""
        errs: list[str] = []
        if not self.db_path.parent.exists():
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errs.append(f"Failed to create db_path parent: {e}")
        return errs

    def to_dict(self) -> dict[str, Any]:
        """Export settings as dict (for logging, debug)."""
        return {
            "domain": self.domain,
            "spine_id": self.spine_id,
            "data_dir": str(self.data_dir),
            "db_path": str(self.db_path),
            "audit_jsonl_path": str(self.audit_jsonl_path),
            "ollama_first": self.ollama_first,
            "ollama_model": self.ollama_model,
            "openai_model": self.openai_model,
            "embeddings_model": self.embeddings_model,
            "default_authority_level": self.default_authority_level,
            "default_governance_scope": self.default_governance_scope,
            "risk_max_approval_amount": self.risk_max_approval_amount,
            "rate_limit_per_hour": self.rate_limit_per_hour,
            "max_cost_per_mission": self.max_cost_per_mission,
            "enable_proactive_assistance": self.enable_proactive_assistance,
            "enable_onboarding_wizard": self.enable_onboarding_wizard,
            "user_experience_level": self.user_experience_level,
            "server_host": self.server_host,
            "server_port": self.server_port,
            "rbac_enabled": self.rbac_enabled,
            "air_gap_mode": self.air_gap_mode,
        }
