"""
Port Abstraction & Task Lifecycle — unified task dispatch across flows, plugins, and HTTP services.

A "Port" is an entry point where the hub sends work and receives results:
- Flow Port: kernel.invoke() flows
- Fleet Port: FleetHub plugin dispatch
- HTTP Port: external microservices (gated by AirGapPolicy)
- Event Port: event subscribers (NATS/in-memory)

TaskEnvelope and ResultEnvelope provide a standard shape for all ports to use.
"""

from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    """Task lifecycle status."""
    CREATED = "created"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPORTED = "exported"


class ResultStatus(str, Enum):
    """Result status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TaskEnvelope:
    """
    Standard task container sent from hub to a port.
    
    Attributes:
        task_id: Unique task identifier (UUID)
        trace_id: Causality trace for distributed tracing
        tenant_id: Tenant scope
        port_type: Type of port (flow, fleet, http, event)
        flow_id or agent_id: Target flow or agent
        inputs: Task input payload
        required_evidence: Optional list of evidence/audit requirements
        timeout_seconds: Max execution time
        created_at: Timestamp
        attempts: Number of retry attempts (default 0)
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    port_type: str = "flow"  # flow, fleet, http, event
    flow_id: Optional[str] = None
    agent_id: Optional[str] = None
    inputs: dict[str, Any] = field(default_factory=dict)
    required_evidence: Optional[list[str]] = None
    timeout_seconds: int = 30
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    attempts: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)
    
    @staticmethod
    def from_dict(d: dict[str, Any]) -> TaskEnvelope:
        return TaskEnvelope(**{k: v for k, v in d.items() if k in TaskEnvelope.__dataclass_fields__})


@dataclass
class ResultEnvelope:
    """
    Standard result container returned from port to hub.
    
    Attributes:
        result_id: Unique result identifier
        task_id: Reference to originating task
        trace_id: Causality trace (same as task)
        tenant_id: Tenant scope
        status: success, partial, failed, timeout
        outputs: Result payload
        error: Error message if failed
        evidence: Audit evidence (hashes, signatures, etc.)
        completed_at: Timestamp
        duration_ms: Execution time in milliseconds
    """
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    trace_id: str = ""
    tenant_id: str = "default"
    status: ResultStatus | str = ResultStatus.SUCCESS
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    evidence: dict[str, Any] = field(default_factory=dict)
    completed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    duration_ms: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)
    
    @staticmethod
    def from_dict(d: dict[str, Any]) -> ResultEnvelope:
        return ResultEnvelope(**{k: v for k, v in d.items() if k in ResultEnvelope.__dataclass_fields__})


class Port(ABC):
    """Abstract base class for all port types."""
    
    def __init__(self, port_id: str, port_type: str):
        self.port_id = port_id
        self.port_type = port_type
    
    @abstractmethod
    async def dispatch(self, task: TaskEnvelope) -> ResultEnvelope:
        """
        Dispatch a task and return a result.
        
        Args:
            task: TaskEnvelope to execute
        
        Returns:
            ResultEnvelope with status and outputs
        """
        pass
    
    async def dispatch_sync(self, task: TaskEnvelope) -> ResultEnvelope:
        """Synchronous wrapper (for backwards compat with blocking code)."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.create_task(self.dispatch(task))


class FlowPort(Port):
    """Port adapter for kernel flows."""
    
    def __init__(self, kernel: Any):
        super().__init__("flow-port", "flow")
        self.kernel = kernel
    
    async def dispatch(self, task: TaskEnvelope) -> ResultEnvelope:
        """Dispatch task to kernel flow."""
        start_time = time.time()
        try:
            # Invoke flow through kernel
            result = await self.kernel.invoke(
                task.flow_id,
                task.inputs,
                tenant_id=task.tenant_id,
                trace_id=task.trace_id,
            )
            
            return ResultEnvelope(
                result_id=str(uuid.uuid4()),
                task_id=task.task_id,
                trace_id=task.trace_id,
                tenant_id=task.tenant_id,
                status=ResultStatus.SUCCESS,
                outputs=result,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return ResultEnvelope(
                result_id=str(uuid.uuid4()),
                task_id=task.task_id,
                trace_id=task.trace_id,
                tenant_id=task.tenant_id,
                status=ResultStatus.FAILED,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )


class FleetPort(Port):
    """Port adapter for fleet plugin dispatch."""
    
    def __init__(self, fleet_hub: Any):
        super().__init__("fleet-port", "fleet")
        self.fleet_hub = fleet_hub
    
    async def dispatch(self, task: TaskEnvelope) -> ResultEnvelope:
        """Dispatch task to fleet plugin."""
        start_time = time.time()
        try:
            # Dispatch to fleet
            result = await self.fleet_hub.dispatch(
                task.agent_id,
                task.inputs,
                trace_id=task.trace_id,
            )
            
            return ResultEnvelope(
                result_id=str(uuid.uuid4()),
                task_id=task.task_id,
                trace_id=task.trace_id,
                tenant_id=task.tenant_id,
                status=ResultStatus.SUCCESS,
                outputs=result,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return ResultEnvelope(
                result_id=str(uuid.uuid4()),
                task_id=task.task_id,
                trace_id=task.trace_id,
                tenant_id=task.tenant_id,
                status=ResultStatus.FAILED,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )


class EventPort(Port):
    """Port adapter for event subscribers (NATS/in-memory bus)."""
    
    def __init__(self, event_bus: Any):
        super().__init__("event-port", "event")
        self.event_bus = event_bus
    
    async def dispatch(self, task: TaskEnvelope) -> ResultEnvelope:
        """Publish task as event; collect result from subscriber."""
        start_time = time.time()
        try:
            # Publish event to bus
            await self.event_bus.publish(
                event_type=f"task.{task.flow_id}",
                payload=task.to_dict(),
                trace_id=task.trace_id,
            )
            
            return ResultEnvelope(
                result_id=str(uuid.uuid4()),
                task_id=task.task_id,
                trace_id=task.trace_id,
                tenant_id=task.tenant_id,
                status=ResultStatus.SUCCESS,
                outputs={"published": True},
                duration_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return ResultEnvelope(
                result_id=str(uuid.uuid4()),
                task_id=task.task_id,
                trace_id=task.trace_id,
                tenant_id=task.tenant_id,
                status=ResultStatus.FAILED,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )


class PortRegistry:
    """Registry and dispatcher for ports."""
    
    def __init__(self):
        self.ports: dict[str, Port] = {}
    
    def register(self, port: Port) -> None:
        """Register a port."""
        self.ports[port.port_id] = port
    
    def get(self, port_id: str) -> Optional[Port]:
        """Get a port by ID."""
        return self.ports.get(port_id)
    
    async def dispatch(self, task: TaskEnvelope) -> ResultEnvelope:
        """Dispatch task to appropriate port."""
        port_id = f"{task.port_type}-port"
        port = self.get(port_id)
        if not port:
            return ResultEnvelope(
                task_id=task.task_id,
                trace_id=task.trace_id,
                tenant_id=task.tenant_id,
                status=ResultStatus.FAILED,
                error=f"Port {port_id} not found",
            )
        return await port.dispatch(task)
