"""
FranklinOps Runtime Kernel — The minimal substrate everything runs on.

A true runtime kernel provides:
  - Boot / shutdown lifecycle
  - Flow dispatch (invoke flows with hardening)
  - Core services: DB, Audit, Governance provenance
  - Tenant context
  - Everything else (HTTP, spokes, domain logic) runs on top

The kernel is the OS. Flows are processes. Invoke is the syscall.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .flow_hardening import (
    CircuitBreaker,
    FlowHardeningConfig,
    RateLimiter,
    execute_flow_hardened,
)
from .flow_interface import FlowHandler, FlowRegistry, FlowResult, FlowSpec, flow_handler

logger = logging.getLogger(__name__)


@dataclass
class KernelConfig:
    """Kernel configuration. Load from env or pass explicitly."""

    db_path: Path
    audit_jsonl_path: Path
    default_tenant: str = "default"
    flow_rate_limit_per_minute: int = 120
    flow_circuit_breaker_threshold: int = 5
    flow_circuit_breaker_recovery_sec: float = 60.0


class RuntimeKernel:
    """
    FranklinOps Runtime Kernel.

    Boot → Run (invoke flows) → Shutdown.
    The kernel owns: DB, Audit, FlowRegistry, hardening.
    """

    def __init__(self, config: KernelConfig) -> None:
        self._config = config
        self._db: Any = None
        self._audit: Any = None
        self._flow_registry: Optional[FlowRegistry] = None
        self._rate_limiter: Optional[RateLimiter] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None
        self._governance: Optional[dict[str, Any]] = None
        self._booted: bool = False

    @property
    def booted(self) -> bool:
        """True if kernel has been booted."""
        return self._booted

    @property
    def db(self):
        """OpsDB instance. Available after boot."""
        if not self._booted or self._db is None:
            raise RuntimeError("Kernel not booted. Call boot() first.")
        return self._db

    @property
    def audit(self):
        """AuditLogger instance. Available after boot."""
        if not self._booted or self._audit is None:
            raise RuntimeError("Kernel not booted. Call boot() first.")
        return self._audit

    @property
    def flows(self) -> FlowRegistry:
        """Flow registry. Available after boot."""
        if not self._booted or self._flow_registry is None:
            raise RuntimeError("Kernel not booted. Call boot() first.")
        return self._flow_registry

    @property
    def governance(self) -> dict[str, Any]:
        """Governance provenance (version, hash). Available after boot."""
        if not self._booted:
            return {}
        return self._governance or {}

    def boot(self) -> None:
        """
        Boot the kernel: init DB, migrations, audit, governance, flow registry.
        Idempotent: safe to call multiple times (no-op if already booted).
        """
        if self._booted:
            logger.debug("Kernel already booted")
            return

        from ..franklinops.migrations import run_migrations
        from ..franklinops.opsdb import OpsDB
        from ..franklinops.audit import AuditLogger
        from .governance_provenance import compute_governance_hash

        # 1. DB + migrations
        self._db = OpsDB(self._config.db_path)
        run_migrations(self._db)

        # 2. Audit (AuditLogger creates parent dir in __init__)
        self._audit = AuditLogger(self._db, self._config.audit_jsonl_path)

        # 3. Governance provenance
        self._governance = compute_governance_hash()

        # 4. Flow registry + hardening
        self._flow_registry = FlowRegistry()
        self._rate_limiter = RateLimiter(max_per_minute=self._config.flow_rate_limit_per_minute)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=self._config.flow_circuit_breaker_threshold,
            recovery_seconds=self._config.flow_circuit_breaker_recovery_sec,
        )

        # 5. Startup audit
        self._audit.append(
            actor="kernel",
            action="kernel_boot",
            details={
                "db_path": str(self._config.db_path),
                "governance_hash": self._governance.get("hash"),
                "governance_version": self._governance.get("version"),
            },
        )

        self._booted = True
        logger.info("Kernel booted: governance=%s", self._governance.get("version", "?"))

    def shutdown(self) -> None:
        """Shutdown the kernel: close DB, audit final event."""
        if not self._booted:
            return

        try:
            self._audit.append(actor="kernel", action="kernel_shutdown", details={})
        except Exception as e:
            logger.debug("shutdown audit append: %s", e)

        if self._db:
            self._db.close()
            self._db = None

        self._audit = None
        self._flow_registry = None
        self._rate_limiter = None
        self._circuit_breaker = None
        self._booted = False
        logger.info("Kernel shutdown")

    def plug(
        self,
        spec: FlowSpec,
        handler: FlowHandler | Callable[[dict[str, Any]], Any],
    ) -> None:
        """Plug a flow into the kernel. Must be booted."""
        h = handler if isinstance(handler, FlowHandler) else flow_handler(handler)
        self.flows.plug(spec, h)
        self._audit.append(
            actor="kernel",
            action="flow_plugged",
            scope=spec.scope,
            entity_type="flow",
            entity_id=spec.flow_id,
            details={"name": spec.name},
        )

    def unplug(self, flow_id: str) -> bool:
        """Unplug a flow. Returns True if removed."""
        if self.flows.unplug(flow_id):
            self._audit.append(
                actor="kernel",
                action="flow_unplugged",
                scope="internal",
                entity_type="flow",
                entity_id=flow_id,
                details={},
            )
            return True
        return False

    def invoke(
        self,
        flow_id: str,
        inp: Optional[dict[str, Any]] = None,
        *,
        tenant_id: Optional[str] = None,
    ) -> FlowResult:
        """
        Invoke a flow. The core kernel syscall.

        Dispatches through: circuit breaker → rate limit → sanitize → execute → audit.
        Returns FlowResult (ok, out, error).
        """
        flow = self.flows.get(flow_id)
        if not flow:
            return FlowResult(ok=False, error=f"Flow not found: {flow_id}", flow_id=flow_id)

        spec, handler = flow
        tid = tenant_id or self._config.default_tenant

        def audit_cb(
            fid: str, t: str, i: dict, o: dict, dur: float, ok: bool
        ) -> None:
            self._audit.append(
                actor="flow",
                action="flow_invoked",
                scope=spec.scope,
                entity_type="flow",
                entity_id=fid,
                details={"tenant_id": t, "ok": ok, "duration_ms": dur},
            )
            if not ok:
                try:
                    from ..forensic.failure_collector import record_failure
                    err = o.get("error", "unknown") if isinstance(o, dict) else str(o)
                    record_failure(flow_id=fid, error=err, tenant_id=t, inp_summary={k: str(v)[:200] for k, v in (i or {}).items()}, component=fid)
                except Exception as e:
                    logger.debug("record_failure: %s", e)

        return execute_flow_hardened(
            flow_id,
            spec,
            handler.process,
            inp if isinstance(inp, dict) else {},
            tenant_id=tid,
            config=FlowHardeningConfig.from_env(),
            rate_limiter=self._rate_limiter,
            circuit_breaker=self._circuit_breaker,
            audit_fn=audit_cb,
        )


def create_kernel(config: Optional[KernelConfig] = None) -> RuntimeKernel:
    """Create kernel with config from env if not provided."""
    if config is None:
        import os
        from ..franklinops.settings import FranklinOpsSettings
        s = FranklinOpsSettings()
        config = KernelConfig(
            db_path=s.db_path,
            audit_jsonl_path=s.audit_jsonl_path,
            default_tenant=os.getenv("FRANKLINOPS_DEFAULT_TENANT", "default"),
        )
    return RuntimeKernel(config)


__all__ = ["RuntimeKernel", "KernelConfig", "create_kernel"]
