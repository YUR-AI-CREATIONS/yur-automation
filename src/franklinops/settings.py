from __future__ import annotations

import os
from pathlib import Path

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


class FranklinOpsSettings:
    """
    Lightweight settings loader (env-first).

    This intentionally avoids `pydantic-settings` so FranklinOpsHub can run in
    environments where only the core dependencies are installed.
    """

    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("FRANKLINOPS_DATA_DIR", "data/franklinops"))
        self.db_path = Path(os.getenv("FRANKLINOPS_DB_PATH", "data/franklinops/ops.db"))
        self.audit_jsonl_path = Path(os.getenv("FRANKLINOPS_AUDIT_JSONL_PATH", "data/franklinops/audit.jsonl"))

        self.onedrive_projects_root = os.getenv("FRANKLINOPS_ONEDRIVE_PROJECTS_ROOT", "")
        self.onedrive_bidding_root = os.getenv("FRANKLINOPS_ONEDRIVE_BIDDING_ROOT", "")
        self.onedrive_attachments_root = os.getenv("FRANKLINOPS_ONEDRIVE_ATTACHMENTS_ROOT", "")

        # Risk thresholds: escalate to human when exceeded
        self.risk_max_approval_amount = _env_float("FRANKLINOPS_RISK_MAX_APPROVAL_AMOUNT", 5000.0)

        self.default_authority_level = os.getenv("FRANKLINOPS_DEFAULT_AUTHORITY_LEVEL", "SEMI_AUTO")
        self.default_governance_scope = os.getenv("FRANKLINOPS_DEFAULT_GOVERNANCE_SCOPE", "internal")
        self.rate_limit_per_hour = _env_int("FRANKLINOPS_RATE_LIMIT_PER_HOUR", 200)
        self.max_cost_per_mission = _env_float("FRANKLINOPS_MAX_COST_PER_MISSION", 1000.0)

        # AI Configuration (OpenAI preferred, Ollama fallback)
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("FRANKLINOPS_OPENAI_MODEL", "gpt-4")
        self.openai_temperature = _env_float("FRANKLINOPS_OPENAI_TEMPERATURE", 0.3)
        
        # Legacy Ollama support (fallback if OpenAI not available)
        self.ollama_api_url = os.getenv("FRANKLINOPS_OLLAMA_API_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.getenv("FRANKLINOPS_OLLAMA_MODEL", "llama3")

        self.embeddings_model = os.getenv("FRANKLINOPS_EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")

        # Customer Service & UX Settings
        self.enable_proactive_assistance = os.getenv("FRANKLINOPS_ENABLE_PROACTIVE_ASSISTANCE", "true").lower() == "true"
        self.enable_onboarding_wizard = os.getenv("FRANKLINOPS_ENABLE_ONBOARDING_WIZARD", "true").lower() == "true"
        self.user_experience_level = os.getenv("FRANKLINOPS_USER_EXPERIENCE_LEVEL", "beginner")  # beginner, intermediate, advanced

        self.server_host = os.getenv("FRANKLINOPS_SERVER_HOST", "127.0.0.1")
        self.server_port = _env_int("FRANKLINOPS_SERVER_PORT", 8844)

