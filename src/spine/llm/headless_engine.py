"""
Headless Engine — Domain-agnostic LLM orchestrator.

Abstracts Ollama/OpenAI. Prefers local (Ollama) when ollama_first.
Extracted from ollama_status, ops_chat, superagents_fleet/integrations/llm.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = ["HeadlessEngine", "LLMConfig", "LLMStatus"]


@dataclass
class LLMConfig:
    """LLM configuration."""

    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.3
    ollama_api_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "llama3"
    ollama_first: bool = False

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Load from environment."""
        ollama_first = os.getenv("FRANKLINOPS_OLLAMA_FIRST", "false").lower() in ("true", "1", "yes")
        return cls(
            openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip(),
            openai_model=os.getenv("FRANKLINOPS_OPENAI_MODEL", "gpt-4"),
            openai_temperature=float(os.getenv("FRANKLINOPS_OPENAI_TEMPERATURE", "0.3")),
            ollama_api_url=(os.getenv("FRANKLINOPS_OLLAMA_API_URL") or "http://localhost:11434/api/generate").strip(),
            ollama_model=os.getenv("FRANKLINOPS_OLLAMA_MODEL", "llama3"),
            ollama_first=ollama_first,
        )


@dataclass
class LLMStatus:
    """LLM availability status."""

    status: str  # ok, warning, not_configured, error
    reachable: bool
    models: list[str]
    preferred_model: str
    model_available: bool
    message: str
    setup_steps: list[str] = field(default_factory=list)


def _call_ollama(
    api_url: str,
    model: str,
    prompt: str,
    temperature: float = 0.2,
) -> tuple[Optional[str], str]:
    """Call Ollama generate API."""
    try:
        import requests
        base = api_url.rsplit("/api/", 1)[0] if "/api/" in api_url else api_url.replace("/api/generate", "")
        url = f"{base}/api/generate" if "/api/generate" not in api_url else api_url
        resp = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_ctx": 4096},
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("response") or "").strip(), ""
    except Exception as e:
        return None, str(e)


def _call_openai(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
) -> tuple[Optional[str], str]:
    """Call OpenAI chat completions."""
    try:
        import requests
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 2000,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("choices"):
            return data["choices"][0]["message"]["content"].strip(), ""
        return None, "No response content"
    except Exception as e:
        return None, str(e)


def _check_ollama_status(api_url: str, model: str) -> LLMStatus:
    """Check Ollama availability."""
    result = LLMStatus(
        status="unknown",
        reachable=False,
        models=[],
        preferred_model=model,
        model_available=False,
        message="",
        setup_steps=[],
    )
    try:
        import requests
        base = api_url.rsplit("/api/", 1)[0] if "/api/" in api_url else api_url.replace("/api/generate", "")
        tags_url = f"{base}/api/tags"
        resp = requests.get(tags_url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
        result.models = models
        result.reachable = True

        if model in models or any(m.startswith(model) for m in models):
            result.status = "ok"
            result.model_available = True
            result.message = f"{model} ready"
        elif models:
            result.status = "warning"
            result.message = f"Ollama running, but {model} not pulled. Available: {', '.join(models[:3])}"
            result.setup_steps = [f"Run: ollama pull {model}"]
        else:
            result.status = "warning"
            result.message = f"Ollama running, no models. Run: ollama pull {model}"
            result.setup_steps = [f"ollama pull {model}"]
    except Exception as e:
        err_str = str(e)
        if "Connection" in err_str or "refused" in err_str.lower():
            result.status = "not_configured"
            result.message = "Ollama not running. Install from ollama.com, then run 'ollama serve'"
            result.setup_steps = [
                "1. Install from ollama.com (or: winget install Ollama.Ollama)",
                f"2. Run: ollama pull {model}",
            ]
        else:
            result.status = "error"
            result.message = err_str[:200]
    return result


class HeadlessEngine:
    """
    Headless LLM orchestrator. Domain-agnostic.
    Prefers local Ollama when ollama_first for air-gap/sovereign mode.
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self._config = config or LLMConfig.from_env()

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        ollama_first: Optional[bool] = None,
    ) -> tuple[Optional[str], str]:
        """
        Generate completion. Returns (content, error).
        Prefers Ollama when ollama_first.
        """
        use_ollama_first = ollama_first if ollama_first is not None else self._config.ollama_first
        temp = temperature if temperature is not None else self._config.openai_temperature
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if use_ollama_first and self._config.ollama_api_url:
            content, err = _call_ollama(
                self._config.ollama_api_url,
                self._config.ollama_model,
                full_prompt,
                temp,
            )
            if content:
                return content, ""
            logger.warning("Ollama failed: %s", err)

        if self._config.openai_api_key:
            content, err = _call_openai(
                self._config.openai_api_key,
                self._config.openai_model,
                messages,
                temp,
            )
            if content:
                return content, ""
            logger.warning("OpenAI failed: %s", err)

        if self._config.ollama_api_url and not use_ollama_first:
            content, err = _call_ollama(
                self._config.ollama_api_url,
                self._config.ollama_model,
                full_prompt,
                temp,
            )
            if content:
                return content, ""

        return None, "No LLM available (configure OPENAI_API_KEY or Ollama)"

    def status(self) -> LLMStatus:
        """Check local LLM (Ollama) status."""
        return _check_ollama_status(
            self._config.ollama_api_url,
            self._config.ollama_model,
        )
