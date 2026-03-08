"""
Universal Spine Configuration — Domain-aware settings and profile loading.

Supports environment-first configuration with domain-specific YAML profiles.
"""

from __future__ import annotations

from .universal_settings import UniversalSettings
from .domain_loader import DomainLoader

__all__ = ["UniversalSettings", "DomainLoader"]
