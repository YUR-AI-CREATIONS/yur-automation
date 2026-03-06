"""
Policy Engine — agents never decide. Policies decide.

Every decision is reproducible. Every override is logged.
Humans can change policy without code changes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("policy")


class PolicyEngine:
    """
    Evaluate deals against policy. Returns approve / deny / escalate.

    Policy file (YAML): constraints, escalation, deny rules.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.policy: dict[str, Any] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            import yaml
            with open(self.path, "r", encoding="utf-8") as f:
                self.policy = yaml.safe_load(f) or {}
        except ImportError as e:
            _LOG.warning("policy load: PyYAML not installed: %s", e)
            self.policy = {}
        except Exception as e:
            _LOG.warning("policy load failed %s: %s", self.path, e)
            self.policy = {}

    def evaluate_deal(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """
        Evaluate deal against policy. Returns action, reason, next.

        action: approve | deny | escalate
        next: execute | stop | franklin_review
        """
        p = self.policy.get("deal_policy_v1") or self.policy.get("deal_policy", {})
        c = p.get("constraints", {})
        esc = p.get("escalation", {})
        deny = p.get("deny", {})

        decision: dict[str, Any] = {
            "action": "approve",
            "reason": [],
            "next": "execute",
        }

        capital = metrics.get("capital_required", 0)
        max_cap = c.get("max_capital", 20_000_000)
        if capital > max_cap:
            decision["action"] = "deny"
            decision["reason"].append("capital_exceeds_max")
            decision["next"] = "stop"
            return decision

        p_loss = metrics.get("p_loss", 0)
        deny_threshold = deny.get("if_probability_of_loss_gt", 0.20)
        if p_loss > deny_threshold:
            decision["action"] = "deny"
            decision["reason"].append("loss_probability_too_high")
            decision["next"] = "stop"
            return decision

        roi_mean = metrics.get("roi_mean", 0)
        min_roi = c.get("min_roi", 0.18)
        roi_range = esc.get("if_roi_between", [0.16, 0.18])
        if roi_mean < min_roi and roi_mean >= roi_range[0]:
            decision["action"] = "escalate"
            decision["reason"].append("roi_borderline")
            decision["next"] = esc.get("send_to", "franklin_review")
            return decision

        if roi_mean < min_roi:
            decision["action"] = "deny"
            decision["reason"].append("roi_below_min")
            decision["next"] = "stop"
            return decision

        return decision
