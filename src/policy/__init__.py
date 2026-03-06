"""
Policy Engine — policy-driven, not agent-driven.

Agents do work. Policies decide. approve / deny / escalate.
"""

from .engine import PolicyEngine

__all__ = ["PolicyEngine"]
