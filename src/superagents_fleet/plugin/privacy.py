"""
Privacy Filter — Ensures private/sensitive data stays local.

- Fields matching patterns are never sent to external APIs
- Learning happens only on local DB
- Sanitization before any LLM or cloud call
"""

from __future__ import annotations

import re
from typing import Any

# Field names/keys that contain private data — never send externally
PRIVATE_FIELD_PATTERNS = [
    r"ssn|social_security",
    r"^(tax_id|ein|tin)$",
    r"^(password|secret|token|api_key|credential)$",
    r"^(bank_account|routing|account_number)$",
    r"^(credit_card|cvv|card_number)$",
    r"^(salary|compensation|wage)$",
    r"^(dob|date_of_birth|birth_date)$",
    r"^(driver_license|dl_number)$",
    r"^(address|street|city|zip)$",
    r"^(phone|mobile|cell)$",
    r"^(email)$",
    r"^(name|first_name|last_name)$",
    r"_private$",
    r"_pii$",
    r"_sensitive$",
]

# Keys that must be redacted even in local learning storage (highest sensitivity)
LEARNING_REDACT_PATTERNS = [
    r"password", r"secret", r"token", r"api_key", r"credential",
    r"ssn", r"social_security", r"bank_account", r"routing",
    r"credit_card", r"cvv", r"card_number",
]

_COMPILED = [re.compile(p, re.I) for p in PRIVATE_FIELD_PATTERNS]
_LEARNING_COMPILED = [re.compile(p, re.I) for p in LEARNING_REDACT_PATTERNS]


class PrivacyFilter:
    """
    Redacts private fields from payloads before external transmission.

    Use before: LLM API calls, cloud sync, analytics, any outbound.
    """

    def __init__(self, extra_private_fields: list[str] | None = None):
        self._extra = set((extra_private_fields or []))
        self._patterns = _COMPILED
        self._learning_patterns = _LEARNING_COMPILED

    def is_private_key(self, key: str) -> bool:
        """Return True if key should be treated as private."""
        if key in self._extra:
            return True
        key_lower = key.lower()
        return any(p.search(key_lower) for p in self._patterns)

    def _is_learning_redact_key(self, key: str) -> bool:
        """Return True if key must be redacted even in local learning."""
        key_lower = key.lower()
        return any(p.search(key_lower) for p in self._learning_patterns)

    def sanitize(self, data: Any, depth: int = 0) -> Any:
        """
        Recursively sanitize data, replacing private values with placeholder.

        Max depth 10 to avoid infinite recursion.
        """
        if depth > 10:
            return "[max_depth]"

        if isinstance(data, dict):
            return {
                k: "[REDACTED]" if self.is_private_key(k) else self.sanitize(v, depth + 1)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self.sanitize(item, depth + 1) for item in data]
        return data

    def sanitize_for_learning(self, data: Any, depth: int = 0) -> Any:
        """
        Sanitize for local learning storage. RECURSIVE.

        Redacts highest-sensitivity keys (passwords, SSN, bank, etc.).
        Keeps non-PII for learning. Max depth 10.
        """
        if depth > 10:
            return "[max_depth]"

        if isinstance(data, dict):
            return {
                k: "[REDACTED]" if self._is_learning_redact_key(k) else self.sanitize_for_learning(v, depth + 1)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self.sanitize_for_learning(item, depth + 1) for item in data]
        return data
