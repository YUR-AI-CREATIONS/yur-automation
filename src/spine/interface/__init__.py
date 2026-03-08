"""
Universal Spine Interface — Domain-agnostic UI framework.

Provides base UI component registry and domain-driven route management.
"""

from __future__ import annotations

from .universal_ui import UniversalUI
from .adaptive_dashboard import AdaptiveDashboard
from .domain_profiles import DomainProfile, DomainProfileManager

__all__ = ["UniversalUI", "AdaptiveDashboard", "DomainProfile", "DomainProfileManager"]
