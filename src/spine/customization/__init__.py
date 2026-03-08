"""
Spine Customization Framework — LLM-driven domain and workflow generation.

Extends customization_interface with orchestration, workflow generation, and schema adaptation.
"""

from __future__ import annotations

from .domain_configurator import DomainConfigurator
from .workflow_generator import WorkflowGenerator
from .schema_adapter import SchemaAdapter

__all__ = ["DomainConfigurator", "WorkflowGenerator", "SchemaAdapter"]
