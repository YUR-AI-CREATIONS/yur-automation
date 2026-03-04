"""
LLM Service — Shared OpenAI/Ollama caller for fleet agents.

Used for: feasibility studies, market analysis, warm outreach copy, subcontractor scoring.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _call_openai(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> tuple[Optional[str], str]:
    try:
        import requests
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
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


def _call_ollama(
    *,
    api_url: str,
    model: str,
    prompt: str,
    temperature: float = 0.2,
) -> tuple[Optional[str], str]:
    try:
        import requests
        resp = requests.post(
            api_url,
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


class LLMService:
    """LLM caller with OpenAI primary, Ollama fallback."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4",
        openai_temperature: float = 0.3,
        ollama_api_url: Optional[str] = None,
        ollama_model: str = "llama3",
    ):
        self.openai_api_key = (openai_api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.openai_model = openai_model
        self.openai_temperature = openai_temperature
        self.ollama_api_url = (ollama_api_url or os.getenv("FRANKLINOPS_OLLAMA_API_URL", "http://localhost:11434/api/generate")).strip()
        self.ollama_model = ollama_model

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> tuple[Optional[str], str]:
        """Return (content, error). Prefer OpenAI; fallback to Ollama."""
        temp = temperature if temperature is not None else self.openai_temperature
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if self.openai_api_key:
            content, err = _call_openai(
                api_key=self.openai_api_key,
                model=self.openai_model,
                messages=messages,
                temperature=temp,
            )
            if content:
                return content, ""
            logger.warning(f"OpenAI failed: {err}")

        if self.ollama_api_url:
            full_prompt = (f"{system}\n\n{prompt}" if system else prompt)
            content, err = _call_ollama(
                api_url=self.ollama_api_url,
                model=self.ollama_model,
                prompt=full_prompt,
                temperature=temp,
            )
            if content:
                return content, ""

        return None, "No LLM available (configure OPENAI_API_KEY or Ollama)"


def llm_completion(
    prompt: str,
    system: Optional[str] = None,
    **kwargs: Any,
) -> tuple[Optional[str], str]:
    """Convenience: create LLMService from env and complete."""
    svc = LLMService(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("FRANKLINOPS_OPENAI_MODEL", "gpt-4"),
        ollama_api_url=os.getenv("FRANKLINOPS_OLLAMA_API_URL"),
        ollama_model=os.getenv("FRANKLINOPS_OLLAMA_MODEL", "llama3"),
    )
    return svc.complete(prompt, system=system, **kwargs)
