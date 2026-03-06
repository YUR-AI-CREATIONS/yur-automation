"""
Flow Hardening — Validation, rate limit, circuit breaker, retry, timeout.

Every flow invocation passes through:
  1. Input validation (schema + sanitization)
  2. Rate limit (per flow, per tenant)
  3. Circuit breaker (fail fast if flow is down)
  4. Timeout enforcement
  5. Retry with exponential backoff (configurable)
  6. Audit (every invocation logged)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .flow_interface import FlowResult, FlowSpec

logger = logging.getLogger(__name__)

# --- Input sanitization ---
DANGEROUS_PATTERNS = (
    r"(?i)<script",
    r"(?i)javascript:",
    r"(?i)on\w+\s*=",
    r"(?i)eval\s*\(",
    r"(?i)expression\s*\(",
    r"(?i)vbscript:",
    r"(?i)data:",
    r"(?i)\$\{.*\}",
    r"(?i)\{\{.*\}\}",
)

# Default executor for timeout (single thread to avoid unbounded growth)
_EXECUTOR: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="flow_")
    return _EXECUTOR


def sanitize_input(obj: Any, max_depth: int = 10) -> Any:
    """Recursively sanitize input: strip dangerous patterns, limit depth."""
    if max_depth <= 0:
        return None
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): sanitize_input(v, max_depth - 1) for k, v in list(obj.items())[:500]}
    if isinstance(obj, list):
        return [sanitize_input(x, max_depth - 1) for x in obj[:1000]]
    if isinstance(obj, str):
        s = obj[:100_000]
        for pat in DANGEROUS_PATTERNS:
            s = re.sub(pat, "[REDACTED]", s)
        return s
    if isinstance(obj, (int, float, bool)):
        return obj
    return str(obj)[:1000]


def validate_payload_size(payload: Any, max_bytes: int) -> None:
    """Raise if serialized payload exceeds max_bytes."""
    try:
        size = len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))
    except (TypeError, ValueError) as e:
        raise ValueError(f"Payload not serializable: {e}") from e
    if size > max_bytes:
        raise ValueError(f"Payload too large: {size} > {max_bytes} bytes")


# --- Rate limiter ---
@dataclass
class RateLimiter:
    """Per-flow, per-tenant rate limit."""

    max_per_minute: int = 60
    _counts: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def check(self, key: str) -> bool:
        """Return True if under limit."""
        now = time.monotonic()
        cutoff = now - 60
        self._counts[key] = [t for t in self._counts[key] if t > cutoff]
        if len(self._counts[key]) >= self.max_per_minute:
            return False
        self._counts[key].append(now)
        return True


# --- Circuit breaker ---
@dataclass
class CircuitBreaker:
    """Fail fast when flow is repeatedly failing."""

    failure_threshold: int = 5
    recovery_seconds: float = 60.0
    _failures: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _open_until: dict[str, float] = field(default_factory=dict)

    def is_open(self, flow_id: str) -> bool:
        now = time.monotonic()
        if flow_id in self._open_until and now < self._open_until[flow_id]:
            return True
        if flow_id in self._open_until:
            del self._open_until[flow_id]
            self._failures[flow_id] = []
        return False

    def record_success(self, flow_id: str) -> None:
        self._failures[flow_id] = []
        self._open_until.pop(flow_id, None)

    def record_failure(self, flow_id: str) -> None:
        now = time.monotonic()
        cutoff = now - self.recovery_seconds
        self._failures[flow_id] = [t for t in self._failures[flow_id] if t > cutoff]
        self._failures[flow_id].append(now)
        if len(self._failures[flow_id]) >= self.failure_threshold:
            self._open_until[flow_id] = now + self.recovery_seconds


# --- Retry with backoff ---
def retry_with_backoff(
    fn: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
) -> Any:
    """Execute fn with exponential backoff on exception."""
    last_err: Optional[Exception] = None
    delay = base_delay
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt == max_retries:
                raise
            logger.debug("Flow retry attempt %d/%d after %s", attempt + 1, max_retries, e)
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
    raise last_err or RuntimeError("retry exhausted")


# --- Config from env ---
def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(float(raw.strip()))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


# --- Hardened executor ---
@dataclass
class FlowHardeningConfig:
    """Config for flow hardening. Loads from env when not specified."""

    sanitize_input: bool = True
    validate_size: bool = True
    rate_limit_per_minute: int = 60
    circuit_breaker_threshold: int = 5
    circuit_breaker_recovery_sec: float = 60.0
    max_retries: int = 2
    audit_every_invocation: bool = True
    timeout_enabled: bool = True

    @classmethod
    def from_env(cls) -> FlowHardeningConfig:
        """Load config from environment."""
        return cls(
            sanitize_input=os.getenv("FRANKLINOPS_FLOW_SANITIZE", "true").lower() == "true",
            validate_size=os.getenv("FRANKLINOPS_FLOW_VALIDATE_SIZE", "true").lower() == "true",
            rate_limit_per_minute=_env_int("FRANKLINOPS_FLOW_RATE_LIMIT", 120),
            circuit_breaker_threshold=_env_int("FRANKLINOPS_FLOW_CB_THRESHOLD", 5),
            circuit_breaker_recovery_sec=_env_float("FRANKLINOPS_FLOW_CB_RECOVERY", 60.0),
            max_retries=_env_int("FRANKLINOPS_FLOW_MAX_RETRIES", 2),
            audit_every_invocation=os.getenv("FRANKLINOPS_FLOW_AUDIT", "true").lower() == "true",
            timeout_enabled=os.getenv("FRANKLINOPS_FLOW_TIMEOUT", "true").lower() == "true",
        )


def execute_flow_hardened(
    flow_id: str,
    spec: FlowSpec,
    handler_fn: Callable[[dict[str, Any]], dict[str, Any]],
    inp: Optional[dict[str, Any]],
    *,
    tenant_id: str = "default",
    config: Optional[FlowHardeningConfig] = None,
    rate_limiter: Optional[RateLimiter] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
    audit_fn: Optional[Callable[[str, str, dict, dict, float, bool], None]] = None,
) -> FlowResult:
    """
    Execute a flow with full hardening.
    Returns FlowResult with out or error.
    """
    cfg = config or FlowHardeningConfig.from_env()
    rl = rate_limiter or RateLimiter(max_per_minute=cfg.rate_limit_per_minute)
    cb = circuit_breaker or CircuitBreaker(
        failure_threshold=cfg.circuit_breaker_threshold,
        recovery_seconds=cfg.circuit_breaker_recovery_sec,
    )

    inp = inp if inp is not None else {}
    if not isinstance(inp, dict):
        inp = {"value": inp}

    start = time.monotonic()

    # 1. Circuit breaker
    if cb.is_open(flow_id):
        logger.warning("Flow %s: circuit breaker open", flow_id)
        return FlowResult(
            ok=False,
            error="Circuit breaker open",
            duration_ms=(time.monotonic() - start) * 1000,
            flow_id=flow_id,
        )

    # 2. Rate limit
    key = f"{tenant_id}:{flow_id}"
    if not rl.check(key):
        logger.warning("Flow %s: rate limit exceeded for %s", flow_id, key)
        return FlowResult(
            ok=False,
            error="Rate limit exceeded",
            duration_ms=(time.monotonic() - start) * 1000,
            flow_id=flow_id,
        )

    # 3. Sanitize input
    if cfg.sanitize_input:
        inp = sanitize_input(inp)

    # 4. Validate size
    if cfg.validate_size:
        try:
            validate_payload_size(inp, spec.max_payload_bytes)
        except ValueError as e:
            return FlowResult(ok=False, error=str(e), duration_ms=0, flow_id=flow_id)

    # 5. Execute with timeout and retry
    def run() -> dict[str, Any]:
        return handler_fn(inp)

    try:
        if cfg.timeout_enabled and spec.timeout_seconds > 0:
            executor = _get_executor()
            future = executor.submit(retry_with_backoff, run, max_retries=cfg.max_retries)
            out = future.result(timeout=spec.timeout_seconds)
        else:
            out = retry_with_backoff(run, max_retries=cfg.max_retries)

        out = out if isinstance(out, dict) else {"result": out}
        duration_ms = (time.monotonic() - start) * 1000
        cb.record_success(flow_id)

        if cfg.audit_every_invocation and audit_fn:
            audit_fn(flow_id, tenant_id, inp, out, duration_ms, True)

        logger.debug("Flow %s completed in %.2fms", flow_id, duration_ms)
        return FlowResult(ok=True, out=out, duration_ms=duration_ms, flow_id=flow_id)

    except FuturesTimeoutError:
        cb.record_failure(flow_id)
        duration_ms = (time.monotonic() - start) * 1000
        err_msg = f"Flow timed out after {spec.timeout_seconds}s"
        if cfg.audit_every_invocation and audit_fn:
            audit_fn(flow_id, tenant_id, inp, {"error": err_msg}, duration_ms, False)
        logger.warning("Flow %s: %s", flow_id, err_msg)
        return FlowResult(ok=False, error=err_msg, duration_ms=duration_ms, flow_id=flow_id)

    except Exception as e:
        cb.record_failure(flow_id)
        duration_ms = (time.monotonic() - start) * 1000
        if cfg.audit_every_invocation and audit_fn:
            audit_fn(flow_id, tenant_id, inp, {"error": str(e)}, duration_ms, False)
        logger.exception("Flow %s failed: %s", flow_id, e)
        return FlowResult(
            ok=False,
            error=str(e),
            duration_ms=duration_ms,
            flow_id=flow_id,
        )


__all__ = [
    "sanitize_input",
    "validate_payload_size",
    "RateLimiter",
    "CircuitBreaker",
    "FlowHardeningConfig",
    "retry_with_backoff",
    "execute_flow_hardened",
]
