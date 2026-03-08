# Forensic System Report: Universal Orchestration OS Analysis

**Date**: 2026-03-08  
**Scope**: FranklinOps/Trinity codebase analysis for universalization  
**Status**: Complete inventory of current architecture, gaps, and refactor requirements

---

## Executive Summary

The codebase has a **strong universal OS foundation** with kernel, event bus, and multi-layer plugin systems already in place. However, **company/industry-specific assumptions are tightly woven into core modules**, limiting reusability for other verticals. This report identifies:

1. **What works universally** (and should stay in core)
2. **What is vertically-specific** (should move to spokes)
3. **Where outbound network assumptions leak in** (needs air-gap policy)
4. **Where governance enforcement is weak** (needs hardening)

---

## Part 1: Universal Control-Plane Surfaces (Core OS)

### 1.1 Runtime Kernel (`src/core/kernel.py`)

**Status**: ✅ **Universal and well-designed**

- **What it does**: Boot, DB/migrations, audit, governance hash, flow registry, hardening (rate limit, circuit breaker).
- **Core syscall**: `kernel.invoke(flow_id, inp, tenant_id)` → dispatches through hardening → audits result.
- **Tenant-aware**: Yes — tenant context is threaded through invocations.
- **Assessment**: No changes needed for universalization.

### 1.2 Flow Interface & Registry (`src/core/flow_interface.py`)

**Status**: ✅ **Universal**

- **What it does**: `FlowSpec` (flow_id, name, direction, scope, timeout) + `FlowRegistry` (thread-safe plug/unplug).
- **Scopes**: internal, external_low, external_medium, external_high, restricted.
- **Tenant-aware**: Via `kernel.invoke()`.
- **Assessment**: Completely generic. Perfect for spokes to plug in domain-specific flows.

**Example flows already plugged in**:
- `echo`, `reverse`, `nyse_sim`, `pay_app_tracker`, `construction_dashboard`, `monte_carlo`, `policy_evaluate`, `development_pipeline`, `corridor_scan` — all currently construction-focused, but pattern is sound.

### 1.3 Flow Hardening (`src/core/flow_hardening.py`)

**Status**: ✅ **Universal**

- **What it does**: Input sanitization, payload size validation, rate limiting (per tenant+flow), circuit breaker, retry with backoff, timeout, audit every invocation.
- **Tenant-aware**: Yes — rate limit key is `{tenant_id}:{flow_id}`.
- **Assessment**: No changes needed. Works for any flow.

### 1.4 Event Bus (`src/bus/`)

**Status**: ✅ **Universal substrate**

- **InMemoryBus** (`src/bus/in_memory_bus.py`):
  - Publish/subscribe with replay buffer (last 10K events).
  - `trace_id` linking for causality.
  - Handlers can be sync or async.
  - Assessment: ✅ Works for any tenant/domain.

- **NatsBus** (optional, `src/bus/nats_client.py`):
  - NATS client for distributed event pub/sub.
  - Assessment: ✅ Optional, no barriers to universalization.

- **Event Contract** (`src/bus/event_contract.py`):
  - Standard `Event` dataclass: `event_id`, `event_type`, `ts`, `trace_id`, `tenant_id`, `actor`, `payload`, `evidence`.
  - Core event types defined: `parcel.discovered`, `zoning.assessed`, `cost.estimated`, `roi.simulated`, `opportunity.ranked`, etc.
  - Assessment: ⚠️ **Event types are geo/land-dev focused**. Need spoke-specific event types registrable at runtime.

### 1.5 Fleet Plugin System (`src/superagents_fleet/`)

**Status**: ✅ **Universal plugin loader**

- **PluginRegistry** (`src/superagents_fleet/plugin/registry.py`):
  - Loads built-in plugins from `BUILTIN_PLUGINS` map.
  - Supports external plugins from `FRANKLINOPS_FLEET_PLUGINS_DIR`.
  - Path validation prevents traversal attacks.
  - Assessment: ✅ Completely generic; no verticality hardcoded.

- **FleetHub** (`src/superagents_fleet/hub.py`):
  - Central task dispatcher: routes (agent_id, task) pairs to loaded plugins.
  - Supports parallel dispatch (`dispatch_multi()`).
  - Document routing rules currently hardcoded (e.g., "if invoice → bookkeeper"). 
  - Assessment: ⚠️ **Document routing rules are construction-domain specific** (see `route_document()` method).

- **Built-in Plugins**:
  - `land_feasibility`, `civil_land_planning`, `bid_scraping`, `financial_analyst`, `bookkeeper`, `file_keeper`, `project_manager`, `logistics_fleet`, `social_marketing`, `internal_audit`.
  - Assessment: 🚩 **All are construction/dev-focused**. New verticals would need their own plugin set.

### 1.6 Governance & Audit (`src/core/governance_provenance.py`, `src/franklinops/audit.py`)

**Status**: ✅ **Universal framework**

- **Governance Provenance**:
  - Computes SHA-256 hash of `governance-policies.json` at boot.
  - Allows verification that decisions matched the policy in effect at that time.
  - Assessment: ✅ Works for any policy; no verticality.

- **Audit Logger** (`src/franklinops/audit.py`):
  - Append-only JSONL log.
  - Records: actor, action, scope, entity_type, entity_id, details.
  - Tenant-aware via context.
  - Assessment: ✅ Generic and reusable.

- **Failure Collector** (`src/forensic/failure_collector.py`):
  - Records flow failures with trace_id, flow_id, error, component.
  - Stored per-date in `data/fabric/runs/failures/`.
  - Assessment: ✅ Generic.

---

## Part 2: Where Company/Industry Specificity Leaks In (Move to Spokes)

### 2.1 Server & UI (`src/franklinops/server.py`)

**Status**: 🚩 **Tightly coupled to construction demo**

**Construction-specific endpoints/features**:
- `/ui/construction` — entire page dedicated to pay apps, lien deadlines (JCK-focused).
- `/ui/bidzone` — references d-XAI-BID-ZONE (external construction portal).
- `/api/bidzone/*`, `/api/fleet/integrations/onedrive/ingest`, `/api/fleet/integrations/procore/import` — construction workflows.
- Default flows plugged at startup: `pay_app_tracker`, `construction_dashboard` — hard-coded.

**Sales/Finance spokes hardcoded**:
- SalesSpokes (JCK branding, OneDrive bidding, ITB scanning).
- FinanceSpokes (AP/AR, Procore invoices).
- Both assume specific document sources (OneDrive, Procore).

**Assessment**: ⚠️ These should be in **spoke modules** (`src/spokes/construction/`, `src/spokes/sales/`, etc.), loaded conditionally per tenant.

### 2.2 Settings & Configuration (`src/franklinops/settings.py`, `src/franklinops/hub_config.py`)

**Status**: 🚩 **Hardcoded construction roots**

**Construction-specific defaults**:
```python
self.onedrive_projects_root = os.getenv("FRANKLINOPS_ONEDRIVE_PROJECTS_ROOT", "")
self.onedrive_bidding_root = os.getenv("FRANKLINOPS_ONEDRIVE_BIDDING_ROOT", "")
self.bid_zone_root = os.getenv("FRANKLINOPS_BID_ZONE_ROOT", f"{_cursor}\\d-XAI-BID-ZONE")
```

**Hub config**:
- `HubRoot` enum lists: ONEDRIVE_BIDDING, ONEDRIVE_PROJECTS, ONEDRIVE_ATTACHMENTS, PROJECT_CONTROLS, SUPERAGENTS, BID_ZONE, FRANKLIN_OS, JCK_LAND_DEV.
- All are construction/land-dev specific.

**Assessment**: 🚩 **These should be generic `TenantConfig` objects loaded from a registry**, not hard-coded.

### 2.3 Onboarding (`src/franklinops/onboarding.py`)

**Status**: 🚩 **Hardcoded construction/concrete business**

**Construction-specific personas**:
```python
self.user_experience_level = os.getenv("FRANKLINOPS_USER_EXPERIENCE_LEVEL", "beginner")  # beginner, intermediate, advanced
```

**Industry detection**:
- Defaults to "construction" persona with hard-coded prompts.
- Detects keywords: "construction", "contractor", "builder", "concrete", "electrical", etc.

**Assessment**: 🚩 Should be **spoke-driven personality injection**.

### 2.4 Sales Spokes (`src/franklinops/sales_spokes.py`)

**Status**: 🚩 **100% construction/JCK-specific**

**JCK branding**:
```python
f"Thanks for including JCK Concrete on the invite.\n\n"
```

**OneDrive assumptions**:
- `scan_inbound_itbs(source="onedrive_bidding", limit=250)` — assumes bidding folder exists.
- `scan_bidding_folders(source="onedrive_bidding", limit_artifacts=5000)` — assumes bidding root.

**Assessment**: 🚩 **Entire module should be a spoke** that plugs into sales flow registry.

### 2.5 Integrations (`src/franklinops/integrations/`)

**Status**: ⚠️ **Mix of universal and specific**

**Specific integrations**:
- `src/franklinops/integrations/procore.py` — construction project management.
- `src/franklinops/integrations/construction_flows.py` — pay app tracker, construction dashboard.
- `src/franklinops/integrations/development_intelligence_flows.py` — land dev simulation.
- `src/franklinops/integrations/nyse_simulation.py` — financial sim (generic but currently land-dev use case).

**Assessment**: ⚠️ **Integrations should be spoke-owned**. Generic ones (like simulation) can stay in core.

### 2.6 OnBoarding ("Business Type Detection") (`src/franklinops/onboarding.py`)

**Status**: 🚩 **Construction-first**

- Detects OneDrive paths specific to Windows construction workflows.
- Recommends OneDrive as primary document source (Windows-centric).

**Assessment**: 🚩 **Should be abstracted to generic "data source discovery"**.

---

## Part 3: Outbound Network Calls (Air-Gap Vulnerabilities)

### 3.1 External Network Dependencies

**Trinity Sync** (`src/franklinops/integrations/trinity_sync.py`):
```python
url = (base_url or os.getenv("TRINITY_API_BASE_URL", "https://yur-ai-api.onrender.com"))
```
- **Risk**: ⚠️ Defaults to external HTTPS URL; no air-gap check.

**Procore OAuth** (`src/franklinops/integrations/procore.py`):
- Calls `https://login.procore.com` (prod) or `https://login-sandbox.procore.com` (sandbox).
- **Risk**: 🚩 No mechanism to block/allow outbound in air-gap mode.

**Ollama** (`src/franklinops/settings.py`):
```python
self.ollama_api_url = os.getenv("FRANKLINOPS_OLLAMA_API_URL", "http://localhost:11434/api/generate")
```
- **Status**: ✅ Defaults to localhost; safe for air-gap.

**Assessment**:
- ⚠️ **No centralized outbound network policy**. Each integration decides whether to call out.
- 🚩 **No enforcement**: Trinity sync and Procore can reach the internet without checks.
- ✅ Ollama already defaults to localhost.

---

## Part 4: Governance Enforcement (Where It's Weak)

### 4.1 Governance Policy Gaps

**Current enforcement** (`governance-policies.json`):
- **Scopes defined**: internal, external_low, external_medium, external_high, restricted.
- **Auto-execute rules**: internal=true, external_low=true, external_medium=false (requires approval).
- **Flow-level scope assignment**: Each flow has a scope.

**Weak enforcement**:
- ⚠️ **Flow scope enforcement** is only in `flow_hardening.py` (sanitize, rate limit, circuit break).
- ⚠️ **Approval gates** exist in `src/franklinops/approvals.py` but are not mandatory for "external_medium" flows.
- 🚩 **Outbound HTTP is NOT gated by governance scope** — no check like "can this scope reach procore.com?".
- 🚩 **No "air-gap lock"** — cannot disable internet egress via policy.

**Assessment**:
- ✅ Scopes exist; ⚠️ scope enforcement is incomplete.
- 🚩 **Missing: AirGapPolicy** that gates all outbound HTTP and can lock down network access.

---

## Part 5: Task Lifecycle & Ports (Gap)

### 5.1 Current Task Dispatch Patterns

**Pattern 1: Flows** (`kernel.invoke()`):
- Input → flow handler → output.
- Hardened (sanitized, rate-limited, circuit-breaker).
- Audited.
- **Gap**: No explicit task envelope; no result persistence; no distributed tracing across ports.

**Pattern 2: Fleet Plugins** (`FleetHub.dispatch()`):
- Task routed to plugin.
- Plugin executes, returns result.
- Audited.
- **Gap**: No task envelope; results not persisted; dispatch is synchronous (could time out).

**Assessment**: 🚩 **Missing: unified TaskEnvelope + ResultEnvelope** that spans all ports (flows, plugins, HTTP services, event subscribers).

---

## Part 6: Deterministic Builder & Headless Execution (Gap)

**Status**: ⛔ **Does not exist**

- No deterministic file generator.
- No "build receipt" with immutable hashes.
- No frozen spine integration.

**Assessment**: 🚩 **Needs implementation**.

---

## Part 7: Continuous Loop (Gap)

**Status**: ⛔ **Does not exist**

- No "compile → compose → recompile → confirm → distribute" runner.
- No UI to show traces, pending approvals, exports.

**Assessment**: 🚩 **Needs implementation**.

---

## Summary: What To Do

| Area | Status | Action |
|------|--------|--------|
| **Kernel** | ✅ Universal | Keep as-is; no changes |
| **Flows & Registry** | ✅ Universal | Keep; add spoke-specific flow registration |
| **Hardening** | ✅ Universal | Keep; enhance with AirGapPolicy |
| **Event Bus** | ✅ Universal substrate | Keep; add spoke-specific event types |
| **Fleet Plugins** | ✅ Generic loader | Keep; move construction plugins → spoke |
| **Server & UI** | 🚩 Construction-specific | Refactor: core OS `/ui` + spoke-injected `/ui/construction`, `/ui/sales`, etc. |
| **Settings** | 🚩 Construction-specific | Refactor: generic `TenantConfig` + spoke configs |
| **Onboarding** | 🚩 Construction-first | Refactor: generic data-source discovery + spoke persona injection |
| **Sales Spokes** | 🚩 JCK-specific | Move entirely to `src/spokes/sales/` |
| **Integrations** | ⚠️ Mixed | Move construction/land-dev → spokes; keep generic ones in core |
| **Procore OAuth** | 🚩 No air-gap check | Add AirGapPolicy gating |
| **Trinity Sync** | ⚠️ External default | Add AirGapPolicy; allow explicit allowlist |
| **Governance** | ⚠️ Scope exists; enforcement weak | Add `AirGapPolicy` class; gate all HTTP |
| **Task Lifecycle** | 🚩 Missing | Implement TaskEnvelope + ResultEnvelope + Port abstraction |
| **Deterministic Builder** | 🚩 Missing | Implement as flow/plugin |
| **Continuous Loop** | 🚩 Missing | Implement loop runner + UI |

---

## Refactoring Roadmap (High Level)

1. **Phase 0**: ✅ This forensic report
2. **Phase 1**: Separate core OS from construction/land-dev spokes
   - Extract construction flows → `src/spokes/construction/flows.py`
   - Extract sales flows → `src/spokes/sales/flows.py`
   - Refactor `/ui` to be spoke-aware
3. **Phase 2**: Implement `AirGapPolicy` + HTTP guard
   - New module: `src/core/airgap_policy.py`
   - All outbound HTTP routes through it
4. **Phase 3**: Implement Port + TaskEnvelope + lifecycle
   - New module: `src/bus/port.py` (abstraction)
   - New module: `src/franklinops/task_lifecycle.py` (persistence)
5. **Phase 4**: Deterministic builder
   - New module: `src/builder/deterministic_builder.py`
6. **Phase 5**: Continuous loop runner
   - New module: `src/orchestrator/continuous_loop.py`
   - UI: `/ui/loop` showing traces, pending approvals, exports

---

## Conclusion

The foundation is **excellent and universal**. The gaps are **clear and fixable**: company-specific code is localized, outbound network calls can be centrally gated, and the missing pieces (ports, builder, loop) have a clear architecture to implement.

**Effort estimate**: Medium (6–8 weeks for a team of 2–3 devs, depending on test coverage).
