"""
Domain Loader — Load and merge domain-specific YAML profiles.

Reads from config/domains/{domain}.yaml; falls back to generic.yaml.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["DomainLoader"]


class DomainLoader:
    """Load domain profiles from YAML. Fallback: generic profile."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """Initialize loader with config directory."""
        if config_dir is None:
            # Default: config/domains relative to repo root
            config_dir = Path(__file__).resolve().parents[3] / "config" / "domains"
        self.config_dir = config_dir

    def load(self, domain: str) -> dict[str, Any]:
        """
        Load domain profile. Returns dict of settings.
        Falls back to generic if domain not found.
        """
        domain_file = self.config_dir / f"{domain}.yaml"

        # Try domain file first
        if domain_file.exists():
            return self._load_yaml(domain_file)

        # Fall back to generic
        if domain != "generic":
            logger.warning(
                f"Domain profile '{domain}' not found at {domain_file}, using generic"
            )
            generic_file = self.config_dir / "generic.yaml"
            if generic_file.exists():
                return self._load_yaml(generic_file)

        # Hard-coded defaults if no files
        logger.warning(
            f"No domain profile found; using built-in defaults for '{domain}'"
        )
        return self._default_profile(domain)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load YAML file and return dict."""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML not installed; using built-in defaults")
            return self._default_profile(path.stem)

        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return data or {}
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            return self._default_profile(path.stem)

    def _default_profile(self, domain: str) -> dict[str, Any]:
        """Built-in defaults for a domain."""
        defaults = {
            "generic": {
                "data_dir": "data/spine",
                "db_path": "data/spine/spine.db",
                "audit_jsonl_path": "data/spine/audit.jsonl",
                "ollama_first": True,
                "ollama_api_url": "http://localhost:11434/api/generate",
                "ollama_model": "llama3",
                "openai_api_key": "",
                "openai_model": "gpt-4",
                "openai_temperature": 0.3,
                "embeddings_model": "all-MiniLM-L6-v2",
                "default_authority_level": "SEMI_AUTO",
                "default_governance_scope": "internal",
                "risk_max_approval_amount": 5000.0,
                "rate_limit_per_hour": 200,
                "max_cost_per_mission": 1000.0,
                "enable_proactive_assistance": True,
                "enable_onboarding_wizard": True,
                "user_experience_level": "beginner",
                "server_host": "127.0.0.1",
                "server_port": 8844,
                "rbac_enabled": False,
                "api_keys": [],
                "air_gap_mode": False,
            },
            "construction": {
                "data_dir": "data/construction",
                "db_path": "data/construction/ops.db",
                "audit_jsonl_path": "data/construction/audit.jsonl",
                "ollama_first": True,
                "ollama_api_url": "http://localhost:11434/api/generate",
                "ollama_model": "llama3",
                "openai_api_key": "",
                "openai_model": "gpt-4",
                "openai_temperature": 0.3,
                "embeddings_model": "all-MiniLM-L6-v2",
                "default_authority_level": "SEMI_AUTO",
                "default_governance_scope": "internal",
                "risk_max_approval_amount": 50000.0,
                "rate_limit_per_hour": 500,
                "max_cost_per_mission": 25000.0,
                "enable_proactive_assistance": True,
                "enable_onboarding_wizard": True,
                "user_experience_level": "intermediate",
                "server_host": "0.0.0.0",
                "server_port": 8844,
                "rbac_enabled": True,
                "api_keys": [],
                "air_gap_mode": False,
            },
            "healthcare": {
                "data_dir": "data/healthcare",
                "db_path": "data/healthcare/spine.db",
                "audit_jsonl_path": "data/healthcare/audit.jsonl",
                "ollama_first": True,
                "ollama_api_url": "http://localhost:11434/api/generate",
                "ollama_model": "llama3",
                "openai_api_key": "",
                "openai_model": "gpt-4",
                "openai_temperature": 0.2,
                "embeddings_model": "all-MiniLM-L6-v2",
                "default_authority_level": "SEMI_AUTO",
                "default_governance_scope": "restricted",
                "risk_max_approval_amount": 10000.0,
                "rate_limit_per_hour": 100,
                "max_cost_per_mission": 5000.0,
                "enable_proactive_assistance": True,
                "enable_onboarding_wizard": True,
                "user_experience_level": "advanced",
                "server_host": "127.0.0.1",
                "server_port": 8844,
                "rbac_enabled": True,
                "api_keys": [],
                "air_gap_mode": True,
            },
            "finance": {
                "data_dir": "data/finance",
                "db_path": "data/finance/spine.db",
                "audit_jsonl_path": "data/finance/audit.jsonl",
                "ollama_first": False,
                "ollama_api_url": "http://localhost:11434/api/generate",
                "ollama_model": "llama3",
                "openai_api_key": "",
                "openai_model": "gpt-4",
                "openai_temperature": 0.1,
                "embeddings_model": "all-MiniLM-L6-v2",
                "default_authority_level": "MANUAL",
                "default_governance_scope": "restricted",
                "risk_max_approval_amount": 100000.0,
                "rate_limit_per_hour": 50,
                "max_cost_per_mission": 50000.0,
                "enable_proactive_assistance": False,
                "enable_onboarding_wizard": False,
                "user_experience_level": "advanced",
                "server_host": "127.0.0.1",
                "server_port": 8844,
                "rbac_enabled": True,
                "api_keys": [],
                "air_gap_mode": True,
            },
        }
        return defaults.get(domain, defaults["generic"])

    def list_available_domains(self) -> list[str]:
        """List available domain profiles."""
        if self.config_dir.exists():
            return [
                f.stem
                for f in self.config_dir.glob("*.yaml")
                if f.is_file() and f.stem != ".gitkeep"
            ]
        return ["generic"]
