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
        # Detect project root from this file (works from D: or F: or any drive)
        _project_root = Path(__file__).resolve().parents[2]
        _cursor = os.getenv("FRANKLINOPS_CURSOR_PROJECTS", str(Path.home() / ".cursor" / "projects"))
        self.superagents_root = os.getenv("FRANKLINOPS_SUPERAGENTS_ROOT", str(_project_root))
        self.bid_zone_root = os.getenv("FRANKLINOPS_BID_ZONE_ROOT", f"{_cursor}\\d-XAI-BID-ZONE")
        self.franklin_os_root = os.getenv("FRANKLINOPS_FRANKLIN_OS_ROOT", f"{_cursor}\\d-Franklin-OS-local")
        self.jck_land_dev_root = os.getenv("FRANKLINOPS_JCK_LAND_DEV_ROOT", f"{_cursor}\\d-JCK-Land-Development")

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
        
        # Ollama — local LLM. Simple: no OpenAI key? Use Ollama. No config needed.
        self.ollama_api_url = os.getenv("FRANKLINOPS_OLLAMA_API_URL", "http://localhost:11434/api/generate")
        self.ollama_model = os.getenv("FRANKLINOPS_OLLAMA_MODEL", "llama3")
        _ollama_first = os.getenv("FRANKLINOPS_OLLAMA_FIRST", "").lower()
        if _ollama_first in ("true", "1", "yes"):
            self.ollama_first = True
        elif _ollama_first in ("false", "0", "no"):
            self.ollama_first = False
        else:
            # Auto: use Ollama when no OpenAI key (simple for everyone)
            self.ollama_first = not bool((self.openai_api_key or "").strip())

        self.embeddings_model = os.getenv("FRANKLINOPS_EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")

        # Customer Service & UX Settings
        self.enable_proactive_assistance = os.getenv("FRANKLINOPS_ENABLE_PROACTIVE_ASSISTANCE", "true").lower() == "true"
        self.enable_onboarding_wizard = os.getenv("FRANKLINOPS_ENABLE_ONBOARDING_WIZARD", "true").lower() == "true"
        self.user_experience_level = os.getenv("FRANKLINOPS_USER_EXPERIENCE_LEVEL", "beginner")  # beginner, intermediate, advanced

        self.server_host = os.getenv("FRANKLINOPS_SERVER_HOST", "127.0.0.1")
        self.server_port = _env_int("FRANKLINOPS_SERVER_PORT", 8844)

        # RBAC: when true, enforce role-based access on /api/* routes
        self.rbac_enabled = os.getenv("FRANKLINOPS_RBAC_ENABLED", "false").lower() == "true"
        # API keys (comma-separated); when set, Bearer token must match one
        _keys = os.getenv("FRANKLINOPS_API_KEYS", "").strip()
        self.api_keys = [k.strip() for k in _keys.split(",") if k.strip()] if _keys else []


def validate_startup(settings: FranklinOpsSettings | None = None) -> list[str]:
    """Validate critical env at boot; return list of warnings/errors."""
    s = settings or FranklinOpsSettings()
    errs: list[str] = []
    if not s.db_path.parent.exists():
        s.db_path.parent.mkdir(parents=True, exist_ok=True)
    return errs

