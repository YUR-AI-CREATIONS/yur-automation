"""
Universal UI — Base UI component registry and route management.

Domain-agnostic components that can be customized per domain.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["UIComponent", "UIRoute", "UniversalUI"]


@dataclass
class UIComponent:
    """Base UI component definition."""

    component_id: str
    component_type: str
    label: str
    description: str = ""
    icon: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UIRoute:
    """API route definition for UI."""

    path: str
    method: str
    handler: Optional[Callable[..., Any]] = None
    description: str = ""
    tags: list[str] = field(default_factory=list)
    requires_auth: bool = True
    requires_rbac: bool = False


class UniversalUI:
    """
    Domain-agnostic UI registry.

    Manages components, routes, and navigation driven by domain profiles.
    """

    def __init__(self, domain: str = "generic") -> None:
        self.domain = domain
        self.components: dict[str, UIComponent] = {}
        self.routes: dict[str, UIRoute] = {}
        self.navigation: list[dict[str, Any]] = []

    def register_component(self, component: UIComponent) -> None:
        """Register a UI component."""
        self.components[component.component_id] = component
        logger.debug(f"Registered component: {component.component_id}")

    def register_route(self, route: UIRoute) -> None:
        """Register an API route."""
        route_key = f"{route.method} {route.path}"
        self.routes[route_key] = route
        logger.debug(f"Registered route: {route_key}")

    def get_component(self, component_id: str) -> Optional[UIComponent]:
        """Retrieve a component by ID."""
        return self.components.get(component_id)

    def list_components(self, component_type: Optional[str] = None) -> list[UIComponent]:
        """List components, optionally filtered by type."""
        components = self.components.values()
        if component_type:
            components = [c for c in components if c.component_type == component_type]
        return list(components)

    def list_routes(self, tags: Optional[list[str]] = None) -> list[UIRoute]:
        """List routes, optionally filtered by tags."""
        routes = self.routes.values()
        if tags:
            routes = [r for r in routes if any(t in r.tags for t in tags)]
        return list(routes)

    def set_navigation(self, nav: list[dict[str, Any]]) -> None:
        """Set navigation structure (menu, breadcrumbs, etc.)."""
        self.navigation = nav
        logger.debug(f"Updated navigation for domain '{self.domain}'")

    def get_navigation(self) -> list[dict[str, Any]]:
        """Retrieve navigation structure."""
        return self.navigation

    def export_routes_for_fastapi(self) -> dict[str, dict[str, Any]]:
        """
        Export routes as FastAPI-compatible definitions.
        Returns dict for integration with FastAPI app.
        """
        routes_by_path: dict[str, dict[str, Any]] = {}
        for route in self.routes.values():
            if route.path not in routes_by_path:
                routes_by_path[route.path] = {}
            routes_by_path[route.path][route.method] = {
                "handler": route.handler,
                "description": route.description,
                "tags": route.tags,
                "requires_auth": route.requires_auth,
                "requires_rbac": route.requires_rbac,
            }
        return routes_by_path

    def to_dict(self) -> dict[str, Any]:
        """Export UI config as dict."""
        return {
            "domain": self.domain,
            "components": {
                cid: {
                    "type": c.component_type,
                    "label": c.label,
                    "description": c.description,
                    "icon": c.icon,
                }
                for cid, c in self.components.items()
            },
            "routes": {
                rk: {
                    "path": r.path,
                    "method": r.method,
                    "description": r.description,
                    "tags": r.tags,
                }
                for rk, r in self.routes.items()
            },
            "navigation": self.navigation,
        }
