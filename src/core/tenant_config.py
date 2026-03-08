"""
TenantConfig — generic, industry-agnostic tenant configuration.

Replaces hardcoded construction/land-dev assumptions in settings.py.
Spokes can provide spoke-specific configs that inherit from TenantConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import json


@dataclass
class TenantConfig:
    """
    Base tenant configuration (core OS).
    
    Spokes extend this with industry-specific settings.
    """
    tenant_id: str
    tenant_name: str
    tenant_type: str = "generic"  # construction, sales, finance, land_dev, etc.
    
    # Generic data sources (plug-in friendly)
    data_sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Example: {"onedrive": {"root": "/path", "type": "cloud_storage"}, ...}
    
    # Generic export destinations
    export_destinations: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Example: {"filesystem": {"root": "/exports"}, "email": {...}, ...}
    
    # LLM settings (moved to core)
    ollama_enabled: bool = True
    ollama_api_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "llama3"
    
    # Air-gap settings (moved to core)
    airgap_mode: str = "open"  # airgap_strict, airgap_lan, controlled, open
    airgap_allowed_endpoints: list[dict[str, Any]] = field(default_factory=list)
    
    # Governance
    governance_policy_file: str = "governance-policies.json"
    approval_required_scopes: list[str] = field(default_factory=lambda: ["external_medium", "external_high", "restricted"])
    
    # UI/UX
    ui_brand_name: str = "FranklinOps"
    ui_brand_accent_color: str = "#e8c547"
    ui_spokes_enabled: list[str] = field(default_factory=list)  # Which spokes to show in UI
    
    # Database
    opsdb_path: str = "data/opsdb"
    
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @staticmethod
    def from_dict(d: dict[str, Any]) -> TenantConfig:
        return TenantConfig(**{k: v for k, v in d.items() if k in TenantConfig.__dataclass_fields__})
    
    @staticmethod
    def from_json(json_str: str) -> TenantConfig:
        return TenantConfig.from_dict(json.loads(json_str))


@dataclass
class ConstructionTenantConfig(TenantConfig):
    """Construction spoke tenant config."""
    
    def __post_init__(self):
        self.tenant_type = "construction"
        # Add construction-specific defaults
        if not self.ui_spokes_enabled:
            self.ui_spokes_enabled = ["construction", "finance"]


@dataclass
class SalesTenantConfig(TenantConfig):
    """Sales spoke tenant config."""
    
    def __post_init__(self):
        self.tenant_type = "sales"
        if not self.ui_spokes_enabled:
            self.ui_spokes_enabled = ["sales"]


class TenantConfigRegistry:
    """Global registry of tenant configs."""
    
    def __init__(self):
        self.configs: dict[str, TenantConfig] = {}
    
    def register(self, config: TenantConfig) -> None:
        """Register a tenant config."""
        self.configs[config.tenant_id] = config
    
    def get(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get a tenant config by ID."""
        return self.configs.get(tenant_id)
    
    def get_or_default(self, tenant_id: str) -> TenantConfig:
        """Get tenant config or create a default one."""
        return self.configs.get(tenant_id) or TenantConfig(
            tenant_id=tenant_id,
            tenant_name=tenant_id,
        )
    
    def list_all(self) -> dict[str, TenantConfig]:
        """List all registered tenant configs."""
        return dict(self.configs)


# Global singleton
_registry: Optional[TenantConfigRegistry] = None


def get_registry() -> TenantConfigRegistry:
    """Get the global tenant config registry."""
    global _registry
    if _registry is None:
        _registry = TenantConfigRegistry()
    return _registry


def set_registry(registry: TenantConfigRegistry) -> None:
    """Set the global tenant config registry (for testing)."""
    global _registry
    _registry = registry
