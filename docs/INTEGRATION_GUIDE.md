# Integration Guide: Universal Orchestration OS Implementation

**Status**: Implementation guide for existing FranklinOps codebase  
**Date**: 2026-03-08

This guide documents how to integrate the new universal OS components into the existing `src/franklinops` server, settings, and UI.

---

## Overview of New Components

### New Modules Created

1. **`src/core/airgap_policy.py`** — Air-gap enforcement
2. **`src/core/tenant_config.py`** — Generic tenant configuration (replaces construction-specific settings)
3. **`src/bus/port.py`** — Port abstraction (flows, plugins, HTTP, events)
4. **`src/builder/deterministic_builder.py`** — Deterministic, reproducible builds
5. **`src/orchestrator/continuous_loop.py`** — Continuous compile→compose→recompile→confirm→distribute loop
6. **`src/spokes/manager.py`** — Spoke lifecycle coordination
7. **`src/spokes/construction.py`** — Construction spoke (extracted from core)
8. **`src/spokes/sales.py`** — Sales spoke (extracted from core)
9. **`src/spokes/finance.py`** — Finance spoke (extracted from core)
10. **`src/spokes/core_ui.py`** — Neutral UI pages (spoke-agnostic)

---

## Integration Steps (for existing FranklinOps server.py)

### Step 1: Update `settings.py`

**Current state**: Hardcoded construction-specific roots (OneDrive, BID-ZONE, etc.)

**Action**: Replace with generic TenantConfig

```python
from src.core.tenant_config import TenantConfig, TenantConfigRegistry, get_registry

class FranklinOpsSettings:
    def __init__(self):
        # Instead of hardcoding construction roots, load from registry
        self.tenant_registry = get_registry()
        self.tenant_config = self.tenant_registry.get_or_default("default")
        
        # Ollama settings (now in core TenantConfig)
        self.ollama_api_url = self.tenant_config.ollama_api_url
        self.ollama_model = self.tenant_config.ollama_model
```

### Step 2: Initialize Air-Gap Policy at Startup

**Location**: `server.py` startup

```python
from src.core.airgap_policy import AirGapPolicy, AirGapMode, get_policy

def create_app():
    app = FastAPI()
    
    # Initialize air-gap policy
    import os
    airgap_mode = os.getenv("FRANKLINOPS_AIRGAP_MODE", "open")
    airgap_policy = AirGapPolicy(mode=airgap_mode)
    app.state.airgap_policy = airgap_policy
    
    # Register endpoints that need network access
    if airgap_mode != "airgap_strict":
        airgap_policy.register_endpoint(
            host="api.procore.com",
            reason="procore_integration",
            ports=[443],
        )
```

### Step 3: Integrate Port Abstraction

**Location**: Anywhere task dispatch happens (currently: kernel flows, fleet plugins)

```python
from src.bus.port import PortRegistry, FlowPort, FleetPort, TaskEnvelope, ResultEnvelope

def create_app():
    # Initialize port registry
    port_registry = PortRegistry()
    port_registry.register(FlowPort(kernel))
    port_registry.register(FleetPort(fleet_hub))
    app.state.port_registry = port_registry

# Use in endpoints
@app.post("/api/task/dispatch")
async def dispatch_task(task_envelope: dict):
    task = TaskEnvelope.from_dict(task_envelope)
    result = await app.state.port_registry.dispatch(task)
    return result.to_dict()
```

### Step 4: Initialize Spoke Manager

**Location**: `server.py` startup

```python
from src.spokes.manager import SpokeManager

def create_app():
    # Initialize spoke manager
    spoke_manager = SpokeManager(kernel)
    
    # Load enabled spokes
    for spoke_name in ["construction", "sales", "finance"]:
        spoke = spoke_manager.load_spoke_module(spoke_name)
        if spoke:
            spoke_manager.register_spoke_flows(spoke)
    
    app.state.spoke_manager = spoke_manager
```

### Step 5: Initialize Continuous Loop Runner

**Location**: `server.py` startup

```python
from src.orchestrator.continuous_loop import ContinuousLoopRunner

def create_app():
    loop_runner = ContinuousLoopRunner(
        kernel=kernel,
        port_registry=port_registry,
        policy_engine=policy_engine,
    )
    app.state.loop_runner = loop_runner
```

### Step 6: Refactor `/ui` Routes

**Current state**: `/ui` hardcoded to construction dashboard

**Action**: Make core `/ui` neutral and spoke-aware

```python
from src.spokes.core_ui import generate_core_home_page

@app.get("/ui", response_class=HTMLResponse)
async def ui_home(request: Request):
    # Return neutral home page
    return generate_core_home_page()

@app.get("/ui/construction", response_class=HTMLResponse)
async def ui_construction():
    # Construction spoke page
    spoke = app.state.spoke_manager.spokes.get("construction")
    if spoke:
        return generate_construction_dashboard()
    raise HTTPException(status_code=404)

# Similarly for /ui/sales, /ui/finance
```

### Step 7: Guard Outbound HTTP Calls

**Anywhere HTTP requests are made**:

```python
import requests
from src.core.airgap_policy import get_policy

def call_procore_api():
    url = "https://api.procore.com/v2.0/projects"
    
    # Check air-gap policy before calling
    policy = get_policy()
    if not policy.allow_http(url, reason="procore_fetch_projects"):
        raise PermissionError("Outbound to Procore blocked by air-gap policy")
    
    # Safe to make request
    response = requests.get(url, headers=auth_headers)
    return response.json()
```

### Step 8: Add Loop Runner Endpoints

**Location**: `server.py` new routes

```python
from src.orchestrator.continuous_loop import ContinuousLoopRunner

@app.post("/api/loop/run")
async def run_loop(
    request: Request,
    compile_source: str = "onedrive",  # where to read data
    compose_ports: list[str] = ["flow-port", "fleet-port"],
    confirm_gates: list[str] = [],
    distribute_destinations: list[str] = [],
):
    runner = request.app.state.loop_runner
    
    async def compile_fn():
        # Read from data source
        return {"source": compile_source, "data": []}
    
    trace = await runner.run_loop(
        compile_source=compile_fn,
        compose_ports=compose_ports,
        confirm_gates=confirm_gates,
        distribute_destinations=distribute_destinations,
    )
    
    return trace.to_dict()

@app.get("/api/loop/status")
async def loop_status(request: Request):
    runner = request.app.state.loop_runner
    traces = runner.get_traces(limit=20)
    approvals = runner.get_pending_approvals()
    return {
        "recent_traces": traces,
        "pending_approvals": approvals,
        "total_traces": len(runner.traces),
    }

@app.post("/api/loop/approve")
async def approve_trace(request: Request, trace_id: str):
    runner = request.app.state.loop_runner
    success = runner.approve_trace(trace_id)
    return {"approved": success}
```

### Step 9: Add Deterministic Builder as a Flow

**Location**: `kernel.py` flow registration or `server.py` startup

```python
from src.builder.deterministic_builder import deterministic_build_flow

# Register as a flow
kernel.flow_registry.plug(
    flow_spec=FlowSpec(
        flow_id="deterministic_build",
        name="Deterministic Builder",
        direction="incoming",
        scope="internal",
        timeout_seconds=60,
    ),
    handler=deterministic_build_flow,
)
```

---

## Environment Variables

Add to `.env` or deployment config:

```bash
# Air-gap mode (airgap_strict, airgap_lan, controlled, open)
FRANKLINOPS_AIRGAP_MODE=open

# Ollama settings (now in tenant config)
FRANKLINOPS_OLLAMA_API_URL=http://localhost:11434/api/generate
FRANKLINOPS_OLLAMA_MODEL=llama3

# Tenant config (if loading from file)
FRANKLINOPS_TENANT_CONFIG_PATH=config/tenants.json
```

---

## Database/Storage Implications

### Task Lifecycle Persistence

**New tables/collections needed**:

```sql
-- Tasks table (for TaskEnvelope lifecycle)
CREATE TABLE tasks (
    task_id VARCHAR PRIMARY KEY,
    trace_id VARCHAR,
    tenant_id VARCHAR,
    port_type VARCHAR,
    flow_id VARCHAR,
    inputs JSONB,
    created_at TIMESTAMP,
    status VARCHAR,  -- created, dispatched, completed, failed
    INDEX(trace_id),
    INDEX(tenant_id)
);

-- Results table (for ResultEnvelope)
CREATE TABLE results (
    result_id VARCHAR PRIMARY KEY,
    task_id VARCHAR,
    trace_id VARCHAR,
    status VARCHAR,  -- success, partial, failed, timeout
    outputs JSONB,
    duration_ms INT,
    created_at TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

-- Loop traces table
CREATE TABLE loop_traces (
    trace_id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR,
    phase VARCHAR,  -- compile, compose, recompile, confirm, distribute, complete, failed
    inputs JSONB,
    outputs JSONB,
    duration_ms INT,
    governance_approved BOOLEAN,
    created_at TIMESTAMP,
    INDEX(tenant_id),
    INDEX(phase)
);
```

### Build Receipts

Store deterministic builder receipts in audit trail:

```sql
CREATE TABLE build_receipts (
    build_id VARCHAR PRIMARY KEY,
    spec_hash VARCHAR,  -- Frozen immutable anchor
    output_hash VARCHAR,
    output_path VARCHAR,
    status VARCHAR,
    created_at TIMESTAMP,
    INDEX(spec_hash)
);
```

---

## Testing Checklist

- [ ] Air-gap policy blocks internet egress when mode=airgap_strict
- [ ] Spoke flows register and dispatch correctly
- [ ] Core `/ui` is neutral (no construction bias)
- [ ] TaskEnvelope lifecycle persists across all port types
- [ ] Deterministic builder produces identical hashes for same spec
- [ ] Continuous loop completes all 5 phases
- [ ] Governance approval gates work
- [ ] Loop traces are queryable and show full causality

---

## Migration Path (Minimal Disruption)

1. **Week 1**: Deploy new components alongside existing code (no changes to server.py yet)
2. **Week 2**: Add air-gap policy initialization; all HTTP calls check it (but policy mode defaults to "open")
3. **Week 3**: Migrate settings to TenantConfig; keep construction as default tenant
4. **Week 4**: Refactor `/ui` to be spoke-aware; inject construction/sales/finance spokes
5. **Week 5**: Enable continuous loop runner; expose loop UI and endpoints
6. **Week 6**: Default air-gap mode to "controlled" for production; allowlist known endpoints
7. **Week 7**: Full testing and documentation

---

## Conclusion

These components provide a foundation for:
- ✅ **Universal core OS** (kernel, bus, governance, plugins)
- ✅ **Industry-agnostic defaults** (neutral UI, generic config)
- ✅ **Plug-in domains** (spokes for construction, sales, finance, etc.)
- ✅ **Air-gap enforcement** (all outbound gated by policy)
- ✅ **Distributed tracing** (trace_id across all ports)
- ✅ **Deterministic execution** (reproducible builds with frozen hashes)
- ✅ **Continuous orchestration** (compile→compose→recompile→confirm→distribute)

Next: Begin integration in Phase 1 by updating existing `settings.py` and server.py.
