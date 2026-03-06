"""
Ollama status and white-glove setup support.

Checks if Ollama is running, which models are available, and provides
guidance for 100% white-glove onboarding.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests

_LOG = logging.getLogger("ollama_status")

OLLAMA_BASE = os.getenv("FRANKLINOPS_OLLAMA_API_URL", "http://localhost:11434/api/generate")
# Derive base URL (strip /api/generate)
_OLLAMA_HOST = OLLAMA_BASE.rsplit("/api/", 1)[0] if "/api/" in OLLAMA_BASE else "http://localhost:11434"
OLLAMA_TAGS_URL = f"{_OLLAMA_HOST}/api/tags"
OLLAMA_MODEL = os.getenv("FRANKLINOPS_OLLAMA_MODEL", "llama3")


def check_ollama_status() -> dict[str, Any]:
    """
    Check Ollama availability and model status.
    Returns status dict for concierge/API.
    """
    result: dict[str, Any] = {
        "status": "unknown",
        "reachable": False,
        "models": [],
        "preferred_model": OLLAMA_MODEL,
        "model_available": False,
        "message": "",
        "setup_steps": [],
    }

    try:
        resp = requests.get(OLLAMA_TAGS_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
        result["models"] = models
        result["reachable"] = True

        if OLLAMA_MODEL in models or any(m.startswith(OLLAMA_MODEL) for m in models):
            result["status"] = "ok"
            result["model_available"] = True
            result["message"] = f"{OLLAMA_MODEL} ready"
        elif models:
            result["status"] = "warning"
            result["message"] = f"Ollama running, but {OLLAMA_MODEL} not pulled. Available: {', '.join(models[:3])}"
            result["setup_steps"] = [f"Run: ollama pull {OLLAMA_MODEL}"]
        else:
            result["status"] = "warning"
            result["message"] = "Ollama running, no models. Run: ollama pull llama3"
            result["setup_steps"] = ["ollama pull llama3"]

    except requests.exceptions.ConnectionError:
        result["status"] = "not_configured"
        result["message"] = "Ollama not running. Install from ollama.com, then run 'ollama serve'"
        result["setup_steps"] = [
            "1. Install from ollama.com (or: winget install Ollama.Ollama)",
            f"2. Run: ollama pull {OLLAMA_MODEL}",
        ]
    except requests.exceptions.Timeout:
        result["status"] = "warning"
        result["message"] = "Ollama slow to respond (model may be loading)"
    except Exception as e:
        _LOG.debug("ollama check: %s", e)
        result["status"] = "error"
        result["message"] = str(e)[:200]

    return result
