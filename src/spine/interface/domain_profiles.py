"""
Domain Profiles — Maps domain to UI adaptations (nav, features, branding).

Centralizes domain-specific UI configuration and feature flags.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["DomainProfile", "DomainProfileManager"]


@dataclass
class NavItem:
    """Navigation item (menu entry)."""

    label: str
    path: str
    icon: Optional[str] = None
    children: list[NavItem] = field(default_factory=list)
    requires_feature: Optional[str] = None


@dataclass
class Branding:
    """Domain branding configuration."""

    app_title: str
    app_logo_url: Optional[str] = None
    primary_color: str = "#1f2937"
    accent_color: str = "#3b82f6"
    tagline: str = "Universal Spine Operations"


@dataclass
class DomainProfile:
    """Complete domain UI profile."""

    domain: str
    description: str
    branding: Branding
    navigation: list[NavItem] = field(default_factory=list)
    enabled_features: list[str] = field(default_factory=list)
    disabled_features: list[str] = field(default_factory=list)
    custom_routes: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class DomainProfileManager:
    """Manage domain profiles and UI adaptations."""

    def __init__(self) -> None:
        self.profiles: dict[str, DomainProfile] = {}
        self._initialize_default_profiles()

    def _initialize_default_profiles(self) -> None:
        """Initialize built-in domain profiles."""
        # Generic profile
        self.profiles["generic"] = DomainProfile(
            domain="generic",
            description="Universal default configuration",
            branding=Branding(
                app_title="Universal Spine",
                tagline="Intelligent Operations Platform",
                primary_color="#1f2937",
                accent_color="#3b82f6",
            ),
            navigation=[
                NavItem(label="Dashboard", path="/ui/dashboard", icon="dashboard"),
                NavItem(label="Tasks", path="/api/tasks", icon="tasks"),
                NavItem(label="Audit", path="/api/audit", icon="audit"),
                NavItem(label="Config", path="/ui/config", icon="settings"),
            ],
            enabled_features=["core", "tasks", "audit"],
        )

        # Construction profile
        self.profiles["construction"] = DomainProfile(
            domain="construction",
            description="Construction industry configuration",
            branding=Branding(
                app_title="FranklinOps Construction",
                tagline="Construction Project Intelligence",
                primary_color="#92400e",
                accent_color="#f59e0b",
            ),
            navigation=[
                NavItem(label="Dashboard", path="/ui/construction", icon="dashboard"),
                NavItem(
                    label="Sales",
                    path="/ui/sales",
                    icon="sales",
                    children=[
                        NavItem(label="Pipeline", path="/api/sales/opportunities"),
                        NavItem(label="Leads", path="/api/sales/leads"),
                    ],
                ),
                NavItem(
                    label="Finance",
                    path="/ui/finance",
                    icon="finance",
                    children=[
                        NavItem(label="AR", path="/api/finance/ar_reminders"),
                        NavItem(label="Invoices", path="/api/finance/invoices"),
                    ],
                ),
                NavItem(label="BidZone", path="/api/bidzone/status", icon="bidding"),
                NavItem(label="Projects", path="/api/grokstmate/status", icon="projects"),
                NavItem(
                    label="Project Controls",
                    path="/ui/project_controls",
                    icon="controls",
                ),
                NavItem(label="Audit", path="/api/audit", icon="audit"),
            ],
            enabled_features=[
                "core",
                "sales_spokes",
                "finance_spokes",
                "project_controls",
                "bidzone",
                "grokstmate",
                "fleet",
            ],
            custom_routes={
                "/ui/construction": "construction_dashboard",
                "/ui/sales": "sales_dashboard",
                "/ui/finance": "finance_dashboard",
                "/ui/project_controls": "project_controls_dashboard",
            },
        )

        # Healthcare profile
        self.profiles["healthcare"] = DomainProfile(
            domain="healthcare",
            description="Healthcare industry configuration",
            branding=Branding(
                app_title="Healthcare Operations Suite",
                tagline="Patient and Operational Excellence",
                primary_color="#065f46",
                accent_color="#10b981",
            ),
            navigation=[
                NavItem(label="Dashboard", path="/ui/healthcare", icon="dashboard"),
                NavItem(
                    label="Patients",
                    path="/ui/patients",
                    icon="patients",
                    requires_feature="patient_management",
                ),
                NavItem(
                    label="Schedule",
                    path="/ui/schedule",
                    icon="calendar",
                    requires_feature="scheduling",
                ),
                NavItem(
                    label="Compliance",
                    path="/ui/compliance",
                    icon="compliance",
                    requires_feature="compliance_audit",
                ),
                NavItem(label="Audit", path="/api/audit", icon="audit"),
            ],
            enabled_features=[
                "core",
                "patient_management",
                "scheduling",
                "compliance_audit",
                "hipaa_logging",
                "patient_data_protection",
            ],
        )

        # Finance profile
        self.profiles["finance"] = DomainProfile(
            domain="finance",
            description="Finance industry configuration",
            branding=Branding(
                app_title="Finance Operations",
                tagline="Precision Financial Control",
                primary_color="#1e3a8a",
                accent_color="#0ea5e9",
            ),
            navigation=[
                NavItem(label="Dashboard", path="/ui/finance", icon="dashboard"),
                NavItem(
                    label="Accounts",
                    path="/ui/accounts",
                    icon="accounts",
                    children=[
                        NavItem(label="Receivable", path="/api/finance/ar_reminders"),
                        NavItem(label="Payable", path="/api/finance/ap_intake"),
                    ],
                ),
                NavItem(
                    label="Reconciliation",
                    path="/ui/reconciliation",
                    icon="reconciliation",
                ),
                NavItem(
                    label="Audit Trail",
                    path="/ui/audit",
                    icon="audit",
                    requires_feature="sox_enabled",
                ),
            ],
            enabled_features=[
                "core",
                "accounts_payable",
                "accounts_receivable",
                "cashflow_forecasting",
                "invoice_management",
                "reconciliation",
                "audit_trail",
            ],
        )

    def get_profile(self, domain: str) -> Optional[DomainProfile]:
        """Retrieve a domain profile."""
        return self.profiles.get(domain)

    def register_profile(self, profile: DomainProfile) -> None:
        """Register a custom domain profile."""
        self.profiles[profile.domain] = profile
        logger.debug(f"Registered domain profile: {profile.domain}")

    def get_navigation(self, domain: str) -> list[dict[str, Any]]:
        """Get navigation structure for domain."""
        profile = self.get_profile(domain)
        if not profile:
            profile = self.get_profile("generic")

        def nav_to_dict(item: NavItem) -> dict[str, Any]:
            return {
                "label": item.label,
                "path": item.path,
                "icon": item.icon,
                "children": [nav_to_dict(c) for c in item.children],
                "requires_feature": item.requires_feature,
            }

        return [nav_to_dict(n) for n in profile.navigation]

    def get_branding(self, domain: str) -> dict[str, Any]:
        """Get branding for domain."""
        profile = self.get_profile(domain) or self.get_profile("generic")
        b = profile.branding
        return {
            "app_title": b.app_title,
            "app_logo_url": b.app_logo_url,
            "primary_color": b.primary_color,
            "accent_color": b.accent_color,
            "tagline": b.tagline,
        }

    def is_feature_enabled(self, domain: str, feature: str) -> bool:
        """Check if a feature is enabled for domain."""
        profile = self.get_profile(domain)
        if not profile:
            return False

        if feature in profile.disabled_features:
            return False
        return feature in profile.enabled_features

    def list_enabled_features(self, domain: str) -> list[str]:
        """List enabled features for domain."""
        profile = self.get_profile(domain)
        if not profile:
            return []
        return profile.enabled_features

    def to_dict(self, domain: str) -> dict[str, Any]:
        """Export profile as dict."""
        profile = self.get_profile(domain)
        if not profile:
            profile = self.get_profile("generic")

        return {
            "domain": profile.domain,
            "description": profile.description,
            "branding": {
                "app_title": profile.branding.app_title,
                "app_logo_url": profile.branding.app_logo_url,
                "primary_color": profile.branding.primary_color,
                "accent_color": profile.branding.accent_color,
                "tagline": profile.branding.tagline,
            },
            "navigation": self.get_navigation(domain),
            "enabled_features": profile.enabled_features,
            "disabled_features": profile.disabled_features,
        }
