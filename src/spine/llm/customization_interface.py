"""
Customization Interface — LLM-driven domain customization.

Enables LLM-powered business domain setup and workflow generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from .headless_engine import HeadlessEngine

logger = logging.getLogger(__name__)

__all__ = ["CustomizationInterface", "CustomizationRequest"]


@dataclass
class CustomizationRequest:
    """Request for LLM-driven customization."""

    domain: str
    intent: str
    context: dict[str, Any]
    constraints: Optional[list[str]] = None


class CustomizationInterface:
    """
    LLM-driven customization. Generates configs, workflows, schemas from natural language.
    """

    def __init__(self, engine: Optional[HeadlessEngine] = None) -> None:
        self._engine = engine or HeadlessEngine()

    def customize(self, request: CustomizationRequest) -> tuple[Optional[dict[str, Any]], str]:
        """
        Use LLM to generate customization output.
        Returns (result_dict, error).
        """
        system = self._build_system_prompt(request)
        user = self._build_user_prompt(request)
        content, err = self._engine.complete(prompt=user, system=system)
        if err:
            return None, err
        if not content:
            return None, "No LLM response"

        # Parse JSON from response (best-effort)
        try:
            import json
            # Try to extract JSON block if wrapped in markdown
            text = content.strip()
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end] if end > 0 else text[start:]
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end] if end > 0 else text[start:]
            return json.loads(text), ""
        except Exception as e:
            return {"raw_response": content, "parse_error": str(e)}, ""

    def _build_system_prompt(self, req: CustomizationRequest) -> str:
        return f"""You are a domain configuration assistant for the Universal Spine.
Domain: {req.domain}
Your task: help users configure business workflows and data models from natural language.
Output valid JSON only. No markdown unless the user asks for it.
Constraints: {req.constraints or []}"""

    def _build_user_prompt(self, req: CustomizationRequest) -> str:
        ctx = "\n".join(f"- {k}: {v}" for k, v in req.context.items())
        return f"Intent: {req.intent}\n\nContext:\n{ctx}\n\nProvide a JSON configuration."
