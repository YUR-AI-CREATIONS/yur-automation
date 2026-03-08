"""
Continuous Loop Runner — orchestrates the compile→compose→recompile→confirm→distribute flow.

The loop:
1. **Compile**: Listen for incoming data (events, documents, API calls)
2. **Compose**: Route to ports (flows, plugins, services) for processing
3. **Recompile**: Collect results, merge outputs, apply transformations
4. **Confirm**: Run governance gates, check policies, require approvals if needed
5. **Distribute**: Export to final destinations (files, email, accounting, etc.)

Status is exposed via `/ui/loop` showing:
- Current traces and status
- Pending approvals
- Exports completed
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class LoopPhase(str, Enum):
    """Continuous loop phases."""
    COMPILE = "compile"
    COMPOSE = "compose"
    RECOMPILE = "recompile"
    CONFIRM = "confirm"
    DISTRIBUTE = "distribute"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class LoopTrace:
    """Trace of a single loop execution."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    phase: LoopPhase = LoopPhase.COMPILE
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_ms: int = 0
    error: Optional[str] = None
    governance_approved: bool = False
    export_destinations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["phase"] = self.phase.value
        return d


class ContinuousLoopRunner:
    """
    Orchestrates the compile→compose→recompile→confirm→distribute loop.
    """
    
    def __init__(self, kernel: Any, port_registry: Any, policy_engine: Any):
        """
        Initialize loop runner.
        
        Args:
            kernel: RuntimeKernel instance
            port_registry: PortRegistry instance
            policy_engine: Governance policy engine
        """
        self.kernel = kernel
        self.port_registry = port_registry
        self.policy_engine = policy_engine
        
        self.traces: dict[str, LoopTrace] = {}  # Trace ID → trace
        self.pending_approvals: dict[str, LoopTrace] = {}  # Traces awaiting approval
        self.is_running = False
    
    async def run_loop(
        self,
        compile_source: Callable[..., Awaitable[dict[str, Any]]],
        compose_ports: list[str],
        recompile_transformer: Optional[Callable[..., Awaitable[dict[str, Any]]]] = None,
        confirm_gates: Optional[list[str]] = None,
        distribute_destinations: Optional[list[str]] = None,
        tenant_id: str = "default",
    ) -> LoopTrace:
        """
        Execute one complete loop cycle.
        
        Args:
            compile_source: Async func returning input data dict
            compose_ports: List of port IDs to dispatch to (["flow-port", "fleet-port"])
            recompile_transformer: Optional async func to merge/transform results
            confirm_gates: Optional list of governance gate IDs to check
            distribute_destinations: Optional list of export destination IDs
            tenant_id: Tenant scope
        
        Returns:
            LoopTrace with full execution record
        """
        import time
        start_time = time.time()
        
        trace = LoopTrace(tenant_id=tenant_id)
        self.traces[trace.trace_id] = trace
        
        try:
            # Phase 1: Compile
            logger.info(f"[Loop {trace.trace_id}] COMPILE: fetching data")
            trace.phase = LoopPhase.COMPILE
            compiled_data = await compile_source()
            trace.inputs = compiled_data
            
            # Phase 2: Compose
            logger.info(f"[Loop {trace.trace_id}] COMPOSE: dispatching to {len(compose_ports)} ports")
            trace.phase = LoopPhase.COMPOSE
            compose_results = await self._compose(compose_ports, compiled_data, trace.trace_id)
            
            # Phase 3: Recompile
            logger.info(f"[Loop {trace.trace_id}] RECOMPILE: merging results")
            trace.phase = LoopPhase.RECOMPILE
            if recompile_transformer:
                recompiled = await recompile_transformer(compose_results)
            else:
                recompiled = self._default_merge(compose_results)
            trace.outputs = recompiled
            
            # Phase 4: Confirm
            logger.info(f"[Loop {trace.trace_id}] CONFIRM: checking governance gates")
            trace.phase = LoopPhase.CONFIRM
            
            if confirm_gates:
                approval_needed = await self._check_gates(confirm_gates, recompiled)
                if approval_needed:
                    self.pending_approvals[trace.trace_id] = trace
                    logger.info(f"[Loop {trace.trace_id}] Governance approval required")
                    return trace
            
            trace.governance_approved = True
            
            # Phase 5: Distribute
            logger.info(f"[Loop {trace.trace_id}] DISTRIBUTE: exporting results")
            trace.phase = LoopPhase.DISTRIBUTE
            
            if distribute_destinations:
                exports = await self._distribute(distribute_destinations, recompiled)
                trace.export_destinations = exports
            
            trace.phase = LoopPhase.COMPLETE
            logger.info(f"[Loop {trace.trace_id}] Complete")
        
        except Exception as e:
            logger.error(f"[Loop {trace.trace_id}] Failed: {e}")
            trace.phase = LoopPhase.FAILED
            trace.error = str(e)
        
        finally:
            trace.duration_ms = int((time.time() - start_time) * 1000)
        
        return trace
    
    async def _compose(
        self,
        port_ids: list[str],
        data: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        """Dispatch data to all ports concurrently."""
        from src.bus.port import TaskEnvelope
        
        tasks = []
        for port_id in port_ids:
            # Create task for each port
            task = TaskEnvelope(
                trace_id=trace_id,
                port_type=port_id.split("-")[0],
                flow_id=port_id,
                inputs=data,
            )
            tasks.append(self.port_registry.dispatch(task))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        compose_results = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                compose_results[f"port_{i}"] = {"error": str(result)}
            else:
                compose_results[f"port_{i}"] = result.to_dict() if hasattr(result, "to_dict") else result
        
        return compose_results
    
    def _default_merge(self, compose_results: dict[str, Any]) -> dict[str, Any]:
        """Default merge: combine all port outputs."""
        merged = {}
        for port_id, result in compose_results.items():
            if isinstance(result, dict) and "outputs" in result:
                merged[port_id] = result["outputs"]
            else:
                merged[port_id] = result
        return merged
    
    async def _check_gates(
        self,
        gate_ids: list[str],
        data: dict[str, Any],
    ) -> bool:
        """Check governance gates. Returns True if approval needed."""
        # For now, stub implementation
        # In reality, would call policy engine with gates and data
        for gate_id in gate_ids:
            if "approval_required" in gate_id:
                return True
        return False
    
    async def _distribute(
        self,
        destinations: list[str],
        data: dict[str, Any],
    ) -> list[str]:
        """Export data to destinations. Returns list of export paths."""
        # Stub: would implement file export, email drafts, accounting exports, etc.
        exported = []
        for dest in destinations:
            # Simulate export
            exported.append(f"/exports/{dest}/{uuid.uuid4()}.json")
        return exported
    
    def get_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent loop traces for UI display."""
        sorted_traces = sorted(
            self.traces.values(),
            key=lambda t: t.timestamp,
            reverse=True,
        )[:limit]
        return [t.to_dict() for t in sorted_traces]
    
    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get traces pending governance approval."""
        return [t.to_dict() for t in self.pending_approvals.values()]
    
    def approve_trace(self, trace_id: str) -> bool:
        """Approve a trace for distribution."""
        if trace_id not in self.pending_approvals:
            return False
        
        trace = self.pending_approvals.pop(trace_id)
        trace.governance_approved = True
        logger.info(f"[Loop {trace_id}] Approved")
        return True


# Loop metrics/status endpoint
@dataclass
class LoopStatus:
    """Current loop status for UI."""
    is_running: bool
    recent_traces: list[dict[str, Any]]
    pending_approvals: list[dict[str, Any]]
    total_traces: int
    total_succeeded: int
    total_failed: int
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
