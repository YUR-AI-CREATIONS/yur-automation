"""
Prompt Registry — Domain-specific prompt templates for the Universal Spine.

Stores and resolves prompts by domain and template id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["PromptRegistry", "PromptTemplate"]


@dataclass
class PromptTemplate:
    """Prompt template with optional variables."""

    template_id: str
    domain: str
    system_prompt: str
    user_template: str
    description: str = ""
    variables: list[str] = field(default_factory=list)


class PromptRegistry:
    """
    Registry of domain-specific prompt templates.
    """

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}  # key: domain:template_id

    def register(
        self,
        template_id: str,
        domain: str,
        system_prompt: str,
        user_template: str,
        description: str = "",
        variables: Optional[list[str]] = None,
    ) -> None:
        """Register a prompt template."""
        key = f"{domain}:{template_id}"
        self._templates[key] = PromptTemplate(
            template_id=template_id,
            domain=domain,
            system_prompt=system_prompt,
            user_template=user_template,
            description=description,
            variables=variables or [],
        )
        logger.debug("Prompt registered: %s", key)

    def get(self, domain: str, template_id: str) -> Optional[PromptTemplate]:
        """Get template by domain and id."""
        return self._templates.get(f"{domain}:{template_id}")

    def resolve(
        self,
        domain: str,
        template_id: str,
        **variables: Any,
    ) -> Optional[tuple[str, str]]:
        """
        Resolve template with variables. Returns (system_prompt, user_prompt).
        """
        t = self.get(domain, template_id)
        if not t:
            return None
        system = t.system_prompt
        user = t.user_template
        for k, v in variables.items():
            placeholder = "{" + k + "}"
            val = str(v)
            system = system.replace(placeholder, val)
            user = user.replace(placeholder, val)
        return system, user

    def list_templates(self, domain: Optional[str] = None) -> list[dict[str, Any]]:
        """List templates, optionally filtered by domain."""
        items = []
        for key, t in self._templates.items():
            if domain and t.domain != domain:
                continue
            items.append({
                "template_id": t.template_id,
                "domain": t.domain,
                "description": t.description,
                "variables": t.variables,
            })
        return items
