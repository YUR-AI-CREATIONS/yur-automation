"""
Headless LLM Layer — Domain-agnostic local LLM processing.

Orchestrates Ollama/OpenAI, prompt templates, and customization.
"""

from .headless_engine import HeadlessEngine
from .customization_interface import CustomizationInterface
from .prompt_registry import PromptRegistry

__all__ = [
    "HeadlessEngine",
    "CustomizationInterface",
    "PromptRegistry",
]
