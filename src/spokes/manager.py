"""
Spoke Manager — coordinate spoke loading, flow registration, and UI injection.

Spokes register:
- Flows (via FlowSpec)
- Fleet plugins
- UI pages
- Personas (for onboarding/conversational UI)
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class Spoke:
    """A registered spoke with flows, plugins, and UI pages."""
    
    def __init__(
        self,
        spoke_id: str,
        name: str,
        description: str,
        flows: Optional[list[dict[str, Any]]] = None,
        ui_pages: Optional[list[dict[str, Any]]] = None,
        fleet_plugins: Optional[list[dict[str, Any]]] = None,
        personas: Optional[dict[str, str]] = None,
    ):
        self.spoke_id = spoke_id
        self.name = name
        self.description = description
        self.flows = flows or []
        self.ui_pages = ui_pages or []
        self.fleet_plugins = fleet_plugins or []
        self.personas = personas or {}
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "spoke_id": self.spoke_id,
            "name": self.name,
            "description": self.description,
            "flows": len(self.flows),
            "ui_pages": len(self.ui_pages),
            "fleet_plugins": len(self.fleet_plugins),
        }


class SpokeManager:
    """Manages spoke lifecycle and coordination."""
    
    def __init__(self, kernel: Any):
        self.kernel = kernel
        self.spokes: dict[str, Spoke] = {}
        self.flow_registry = kernel.flow_registry if hasattr(kernel, "flow_registry") else None
    
    def load_spoke_module(self, spoke_name: str) -> Optional[Spoke]:
        """
        Load a spoke from src.spokes.{spoke_name}.
        
        Args:
            spoke_name: Spoke module name (e.g., "construction")
        
        Returns:
            Spoke instance or None if load fails
        """
        try:
            module = importlib.import_module(f"src.spokes.{spoke_name}")
            
            spoke = Spoke(
                spoke_id=spoke_name,
                name=module.SPOKE_NAME if hasattr(module, "SPOKE_NAME") else spoke_name,
                description=module.SPOKE_DESCRIPTION if hasattr(module, "SPOKE_DESCRIPTION") else "",
                flows=module.FLOWS_TO_REGISTER if hasattr(module, "FLOWS_TO_REGISTER") else [],
                ui_pages=module.UI_PAGES if hasattr(module, "UI_PAGES") else [],
                fleet_plugins=module.FLEET_PLUGINS if hasattr(module, "FLEET_PLUGINS") else [],
                personas=module.PERSONAS if hasattr(module, "PERSONAS") else {},
            )
            
            self.spokes[spoke_name] = spoke
            logger.info(f"[SpokeManager] Loaded spoke: {spoke_name}")
            return spoke
        
        except ImportError as e:
            logger.warning(f"[SpokeManager] Failed to load spoke {spoke_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"[SpokeManager] Error loading spoke {spoke_name}: {e}")
            return None
    
    def register_spoke_flows(self, spoke: Spoke) -> None:
        """Register all flows from a spoke into the kernel flow registry."""
        if not self.flow_registry:
            logger.warning("[SpokeManager] Flow registry not available; cannot register flows")
            return
        
        for flow_spec_dict in spoke.flows:
            try:
                # Extract handler from dict (it's already a callable)
                handler = flow_spec_dict.pop("handler", None)
                
                # Import and create FlowSpec
                from src.core.flow_interface import FlowSpec
                
                flow_spec = FlowSpec(
                    flow_id=flow_spec_dict.get("flow_id"),
                    name=flow_spec_dict.get("name"),
                    direction=flow_spec_dict.get("direction", "incoming"),
                    description=flow_spec_dict.get("description", ""),
                    scope=flow_spec_dict.get("scope", "internal"),
                    timeout_seconds=flow_spec_dict.get("timeout_seconds", 30),
                )
                
                # Register with handler
                self.flow_registry.plug(flow_spec, handler)
                logger.info(f"[SpokeManager] Registered flow: {flow_spec.flow_id}")
            
            except Exception as e:
                logger.error(f"[SpokeManager] Error registering flow: {e}")
    
    def get_ui_pages_for_tenant(self, tenant_spokes: list[str]) -> list[dict[str, Any]]:
        """Get UI pages for a tenant's enabled spokes."""
        pages = []
        for spoke_id in tenant_spokes:
            if spoke_id in self.spokes:
                spoke = self.spokes[spoke_id]
                pages.extend(spoke.ui_pages)
        return pages
    
    def get_persona_for_spoke(self, spoke_id: str, persona_type: str = "default") -> Optional[str]:
        """Get a persona string for onboarding/conversational UI."""
        if spoke_id in self.spokes:
            return self.spokes[spoke_id].personas.get(persona_type)
        return None
    
    def list_spokes(self) -> dict[str, dict[str, Any]]:
        """List all loaded spokes."""
        return {sid: spoke.to_dict() for sid, spoke in self.spokes.items()}
