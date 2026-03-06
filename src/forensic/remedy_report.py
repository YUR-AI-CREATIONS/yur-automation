"""
Remedy Report — aggregate failures, identify problems, suggest remediation.

Purpose: Model remedy report with forensic data. System can run without surfacing every failure;
report summarizes what failed, why, and what to do.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .failure_collector import get_failures


def generate_remedy_report(
    *,
    since_hours: float = 24.0,
    include_suggestions: bool = True,
) -> dict[str, Any]:
    """
    Generate remedy report: failures by component, suggested actions, forensic summary.
    """
    failures = get_failures(since_hours=since_hours, limit=1000)

    by_component: dict[str, list[dict]] = defaultdict(list)
    by_flow: dict[str, int] = defaultdict(int)
    by_error_pattern: dict[str, int] = defaultdict(int)

    for f in failures:
        comp = f.get("component", f.get("flow_id", "unknown"))
        by_component[comp].append(f)
        by_flow[f.get("flow_id", "unknown")] += 1
        err = f.get("error", "")[:80]
        by_error_pattern[err] += 1

    suggestions = []
    if include_suggestions:
        for comp, flist in by_component.items():
            count = len(flist)
            if count >= 5:
                suggestions.append({
                    "component": comp,
                    "failure_count": count,
                    "action": "check_logs",
                    "detail": f"{comp} failed {count} times; inspect trace_ids and error patterns",
                })
            if any("timeout" in (f.get("error") or "").lower() for f in flist):
                suggestions.append({
                    "component": comp,
                    "action": "increase_timeout",
                    "detail": "Timeout errors detected; consider FlowSpec.timeout_seconds",
                })
            if any("circuit breaker" in (f.get("error") or "").lower() for f in flist):
                suggestions.append({
                    "component": comp,
                    "action": "circuit_breaker_open",
                    "detail": "Circuit breaker tripped; wait for recovery or check upstream",
                })

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "since_hours": since_hours,
        "total_failures": len(failures),
        "by_component": {k: len(v) for k, v in by_component.items()},
        "by_flow": dict(by_flow),
        "top_errors": sorted(by_error_pattern.items(), key=lambda x: -x[1])[:10],
        "suggestions": suggestions,
        "sample_trace_ids": list({f.get("trace_id") for f in failures if f.get("trace_id")})[:20],
    }
