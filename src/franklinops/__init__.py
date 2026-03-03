"""FranklinOps Hub + Spokes (local-first operations system)."""

from .hub_config import CANONICAL_FOLDER_MAPPING, get_risk_thresholds, get_roots_from_env

__all__ = [
    "__version__",
    "CANONICAL_FOLDER_MAPPING",
    "get_roots_from_env",
    "get_risk_thresholds",
]

__version__ = "0.1.0"

