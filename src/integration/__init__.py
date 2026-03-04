"""
Integration Bridge between GROKSTMATE and FranklinOps

This module provides the unified interface that combines:
- GROKSTMATE's autonomous agents and construction capabilities
- FranklinOps' business automation and governance
- Trackable roots: Cursor project paths (d-Superagents, c-00-Project-Controls-*, etc.)
"""

__version__ = "1.0.0"

from .bridge import IntegrationBridge, GROKSTMATE_AVAILABLE
from .governance_adapter import GovernanceAdapter
from .unified_orchestrator import run_grokstmate_phase

__all__ = [
    "__version__",
    "IntegrationBridge",
    "GovernanceAdapter",
    "run_grokstmate_phase",
    "GROKSTMATE_AVAILABLE",
]