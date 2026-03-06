# Franklin OS — Complete System Index & Forensic Architecture

**Every component. Granular detail. Failure propagation. Identification. Remediation. Data lifecycle.**

---

## 1. Index Structure

Each component is documented with:

| Field | Meaning |
|-------|---------|
| **Purpose** | What it does |
| **Status** | Implemented / Stub / Future |
| **Supporting cast** | Direct dependencies |
| **Upstream** | What feeds it |
| **Downstream** | What consumes it |
| **If upstream fails** | Impact |
| **If downstream fails** | Impact |
| **Sustain** | Retry, circuit breaker, fallback |
| **Fault level** | Critical / High / Medium / Low |
| **Fault type** | Temporary (recoverable) / Permanent (requires intervention) |
| **Identify** | How the system detects this component failed |
| **Repair** | Guardrails to fix |
| **Auto-evolve** | Can system recover without human knowing? |
| **Forensic data** | trace_id, audit, logs |
| **Data lifecycle** | Where data enters, flows, exits |

---

## 2. Critical Path Components

### 2.1 Runtime Kernel (`src/core/kernel.py`)

| Field | Value |
|-------|-------|
| **Purpose** | Boot, invoke, shutdown. Flow orchestration. DB, audit, governance. |
| **Status** | Implemented |
| **Supporting cast** | flow_interface, flow_hardening, opsdb, audit, governance_provenance |
| **Upstream** | settings, migrations |
| **Downstream** | All flows, server |
| **If upstream fails** | Boot fails; no DB/audit |
| **If downstream fails** | FlowResult.ok=False; error propagated |
| **Sustain** | Flow hardening (retry, circuit breaker, timeout) |
| **Fault level** | Critical |
| **Fault type** | Temporary (boot retry); Permanent if DB corrupt |
| **Identify** | Boot exception; invoke returns FlowResult.ok=False; audit hub_startup |
| **Repair** | Migrations; flow hardening retry; circuit breaker recovery |
| **Auto-evolve** | Partial — flow failures return structured error; kernel does not auto-restart |
| **Forensic data** | governance_hash, audit hub_startup/hub_shutdown, flow_id in FlowResult |
| **Data lifecycle** | Boot → invoke(flow_id, inp) → FlowResult(out/error) |

---

### 2.2 Flow Hardening (`src/core/flow_hardening.py`)

| Field | Value |
|-------|-------|
| **Purpose** | Sanitize, rate limit, circuit breaker, retry, timeout, audit every invocation |
| **Status** | Implemented |
| **Supporting cast** | flow_interface, ThreadPoolExecutor |
| **Upstream** | Kernel invoke |
| **Downstream** | Handler |
| **If upstream fails** | Invalid inp → sanitize strips; size exceeded → FlowResult error |
| **If downstream fails** | Handler exception → FlowResult.ok=False; audit_fn(ok=False); circuit_breaker.record_failure |
| **Sustain** | retry_with_backoff; CircuitBreaker 5 failures → 60s cooldown; RateLimiter 120/min |
| **Fault level** | Critical |
| **Fault type** | Temporary — circuit breaker recovers; rate limit resets |
| **Identify** | FlowResult.error; audit_fn receives ok=False, error dict; logger.exception |
| **Repair** | Retry; circuit breaker opens → blocks further calls until recovery_seconds |
| **Auto-evolve** | Yes — circuit breaker auto-recovers; retry auto-attempts; caller gets FlowResult, not exception |
| **Forensic data** | audit_fn(flow_id, tenant_id, inp, out/error, duration_ms, ok); flow_id in FlowResult |
| **Data lifecycle** | inp → sanitize → validate → execute → out/error → audit |

---

### 2.3 Event Bus (`src/bus/in_memory_bus.py`)

| Field | Value |
|-------|-------|
| **Purpose** | Publish/subscribe. Replay buffer. trace_id causality. |
| **Status** | Implemented |
| **Supporting cast** | event_contract |
| **Upstream** | Pipeline, geo_economic, integration |
| **Downstream** | Subscribers (handlers) |
| **If upstream fails** | Malformed event → handler may fail |
| **If downstream fails** | Handler exception → logger.exception; other handlers still run |
| **Sustain** | Replay buffer capped at 10_000; async handlers via create_task |
| **Fault level** | Critical |
| **Fault type** | Temporary — process restart loses in-memory events |
| **Identify** | Handler errors logged; no central failure signal |
| **Repair** | None — handlers must be resilient |
| **Auto-evolve** | Partial — one handler failure does not block others |
| **Forensic data** | _events list; trace_id, event_id, event_type, ts in every event; get_events_by_trace |
| **Data lifecycle** | publish(subject, event) → append → notify handlers |

---

### 2.4 DAG Pipeline (`src/pipeline/land_deal.py`)

| Field | Value |
|-------|-------|
| **Purpose** | parcel → zoning → infra → market → cost → sim → policy → rank |
| **Status** | Implemented |
| **Supporting cast** | bus, orchestrator.dag, simulation.monte_carlo, policy.engine |
| **Upstream** | parcel dict |
| **Downstream** | development_pipeline flow, API |
| **If upstream fails** | Invalid parcel → _safe_float defaults; missing keys → defaults |
| **If downstream fails** | Exception propagates to flow → FlowResult.ok=False |
| **Sustain** | None — DAG runs synchronously; one node fail = whole pipeline fail |
| **Fault level** | Critical |
| **Fault type** | Temporary — retry at flow level |
| **Identify** | Exception in node → propagates; no per-node audit |
| **Repair** | Flow hardening retry; caller can re-invoke |
| **Auto-evolve** | No — pipeline fails atomically |
| **Forensic data** | trace_id; events (parcel.discovered, zoning.assessed, cost.estimated, roi.simulated, opportunity.ranked) |
| **Data lifecycle** | parcel → ctx → each node → ctx updated → opportunity |

---

### 2.5 OpsDB (`src/franklinops/opsdb.py`)

| Field | Value |
|-------|-------|
| **Purpose** | SQLite persistence: audit, approvals, tasks, artifacts, invoices, sales |
| **Status** | Implemented |
| **Supporting cast** | sqlite3, migrations |
| **Upstream** | File system (db path) |
| **Downstream** | audit, approvals, doc_ingestion, sales, finance |
| **If upstream fails** | Path invalid → connection fails |
| **If downstream fails** | All DB-backed features fail |
| **Sustain** | WAL mode; migrations idempotent |
| **Fault level** | Critical |
| **Fault type** | Permanent if disk full or DB corrupt |
| **Identify** | Connection error; write error; migrations fail |
| **Repair** | Migrations; backup/restore |
| **Auto-evolve** | No — DB failure is fatal to process |
| **Forensic data** | All tables; audit_events; retention_days |
| **Data lifecycle** | Conn → tx → INSERT/UPDATE/SELECT → commit |

---

### 2.6 Audit (`src/franklinops/audit.py`)

| Field | Value |
|-------|-------|
| **Purpose** | Append-only audit: SQLite + JSONL. Tenant-scoped. |
| **Status** | Implemented |
| **Supporting cast** | opsdb |
| **Upstream** | opsdb |
| **Downstream** | All components that append |
| **If upstream fails** | DB down → append raises |
| **If downstream fails** | Audit gaps if append not called |
| **Sustain** | None |
| **Fault level** | Critical |
| **Fault type** | Permanent — audit loss is irreversible |
| **Identify** | Append exception |
| **Repair** | None — append-only, no repair |
| **Auto-evolve** | No |
| **Forensic data** | id, ts, actor, action, scope, entity_type, entity_id, details, tenant_id |
| **Data lifecycle** | append() → INSERT + JSONL append |

---

### 2.7 Autonomy Gate (`src/core/autonomy_gate.py`)

| Field | Value |
|-------|-------|
| **Purpose** | Governance: authority, scope, evidence, rate limit, cost. Blocks or allows. |
| **Status** | Implemented |
| **Supporting cast** | hmac, hashlib |
| **Upstream** | evidence (blake_birthmark, intent, timestamp, signature) |
| **Downstream** | approvals |
| **If upstream fails** | Evidence missing/invalid → can_execute returns False |
| **If downstream fails** | ApprovalService blocks auto-execute |
| **Sustain** | override_policy; ALLOW_UNVERIFIED_MISSIONS (dev only, disabled in prod) |
| **Fault level** | Critical |
| **Fault type** | Temporary — evidence can be recreated |
| **Identify** | can_execute returns (False, reason); execution_history |
| **Repair** | Valid evidence; override_policy |
| **Auto-evolve** | No — human or policy change required |
| **Forensic data** | execution_history; get_autonomy_report |
| **Data lifecycle** | mission + evidence → can_execute → delegate |

---

## 3. Identification Mechanisms (How We Detect Failure)

| Mechanism | Where | What it identifies |
|-----------|-------|---------------------|
| **FlowResult.ok** | flow_hardening, kernel | Flow failed; error string |
| **audit_fn(ok=False)** | flow_hardening | Every failed invocation logged |
| **Circuit breaker is_open** | flow_hardening | Repeated failures → block |
| **logger.exception** | flow_hardening, bus handlers | Exception with stack trace |
| **Audit append** | audit.py | All actions (success + failure when caller logs) |
| **trace_id** | bus, pipeline | Causality chain for replay |
| **Ouroboros health check** | ouroboros_spine | Subsystem health (Trinity; not wired to FranklinOps) |
| **Governance hash** | governance_provenance | Policy drift |

**Gap:** No centralized "remedy report" that aggregates failures and suggests remediation. No auto-evolve that hides failure from operators until report.

---

## 4. Repair Mechanisms

| Mechanism | Where | Repairs |
|-----------|-------|---------|
| **retry_with_backoff** | flow_hardening | Transient handler failures |
| **Circuit breaker recovery** | flow_hardening | After 60s, allows retry |
| **Rate limit reset** | flow_hardening | Per-minute window |
| **Sanitize input** | flow_hardening | XSS, injection |
| **Migrations** | migrations.py | Schema drift |
| **override_policy** | autonomy_gate | Policy change |
| **Ouroboros RETRY→RESTART→ROLLBACK→SPAWN** | ouroboros_spine | Subsystem failure (Trinity) |

---

## 5. Fault Propagation Matrix

| If this fails | Downstream impact | Upstream impact |
|---------------|-------------------|-----------------|
| **Kernel** | All flows fail | Boot fails |
| **Flow hardening** | Handlers not protected | N/A |
| **Event bus** | No events; no causality replay | Publishers get no ack |
| **DAG** | Pipeline returns error | Parcel invalid → defaults |
| **OpsDB** | Audit, approvals, all persistence fail | N/A |
| **Audit** | No audit trail | DB down |
| **Policy engine** | Wrong approve/deny | YAML missing → approve |
| **Monte Carlo** | No sim; pipeline partial | numpy missing → error dict |
| **Geo-economic** | No corridor events | Regions invalid → defaults |
| **Data fabric** | No ingestion | Path missing → ok=False |
| **Reality feedback** | No error metrics | prediction_id missing → ok=False |

---

## 6. Data Lifecycle (End-to-End)

```
User request
  → Middleware (tenant, role)
  → Route handler
  → Kernel.invoke(flow_id, inp)
  → Flow hardening (sanitize, rate limit, circuit breaker)
  → Handler (e.g. development_pipeline)
  → Pipeline: parcel → ctx
  → DAG nodes: zoning, infra, market, cost, sim, policy, rank
  → Each node: bus.publish(event)
  → Event bus: append to _events; notify subscribers
  → Audit: append (when audit_fn called)
  → OpsDB: INSERT audit_events
  → Response: trace_id, opportunity
```

**Forensic chain:** trace_id links parcel.discovered → zoning.assessed → cost.estimated → roi.simulated → opportunity.ranked. GET /api/development/trace/{trace_id} replays full chain.

---

## 7. Gaps for Auto-Evolve & Remedy Report

To achieve "system wouldn't know module failed until remedy report":

| Gap | Current | Needed |
|-----|---------|--------|
| **Central failure aggregator** | None | Component that collects FlowResult.ok=False, audit failures, exceptions |
| **Remedy report** | None | Periodic report: failures by component, suggested actions |
| **Silent degradation** | Flow fails → caller gets error | Fallback path; degraded mode; continue with defaults |
| **Health heartbeat** | Ouroboros (Trinity) | FranklinOps health check loop for kernel, DB, bus |
| **Model remedy** | None | ML or rules to suggest "restart X", "check Y" |

---

## 8. Full Component List (Abbreviated)

| Component | Path | Status | Fault | Identify | Repair |
|-----------|------|--------|-------|----------|--------|
| kernel | src/core/kernel.py | Done | Critical | FlowResult, boot | Retry, migrations |
| flow_hardening | src/core/flow_hardening.py | Done | Critical | FlowResult, audit_fn | Retry, CB, rate limit |
| flow_interface | src/core/flow_interface.py | Done | Critical | Validation | FLOW_ID_PATTERN |
| auth | src/core/auth.py | Done | High | 401/403 | API key, role |
| tenant | src/core/tenant.py | Done | High | Wrong tenant | Header |
| autonomy_gate | src/core/autonomy_gate.py | Done | Critical | can_execute | Evidence, override |
| governance_provenance | src/core/governance_provenance.py | Done | Low | Hash mismatch | Policy file |
| in_memory_bus | src/bus/in_memory_bus.py | Done | Critical | Handler log | None |
| event_contract | src/bus/event_contract.py | Done | Critical | Malformed event | create_event |
| dag | src/orchestrator/dag.py | Done | Critical | Exception | Topological check |
| land_deal | src/pipeline/land_deal.py | Done | Critical | Exception | Flow retry |
| policy/engine | src/policy/engine.py | Done | Critical | Wrong decision | YAML fix |
| monte_carlo | src/simulation/monte_carlo.py | Done | High | ok=False | numpy |
| geo_economic | src/geo_economic/ | Done | Medium | Defaults | None |
| reality_feedback | src/reality_feedback/ | Done | Medium | ok=False | None |
| data_fabric | src/data_fabric/ | Done | Medium | ok=False | Path |
| opsdb | src/franklinops/opsdb.py | Done | Critical | Conn error | Migrations |
| audit | src/franklinops/audit.py | Done | Critical | Append error | None |
| approvals | src/franklinops/approvals.py | Done | Critical | Gate block | decide() |
| server | src/franklinops/server.py | Done | Critical | 4xx/5xx | Route handler |
| ouroboros_spine | src/core/ouroboros_spine.py | Done | High | Health report | RETRY→SPAWN |

---

## 9. Implemented: Failure Collector & Remedy Report

| Component | Path | Purpose |
|-----------|------|---------|
| **Failure collector** | `src/forensic/failure_collector.py` | record_failure() — called when flow audit_cb receives ok=False. Stores flow_id, error, trace_id, tenant_id in `data/fabric/runs/failures/{date}/`. |
| **Remedy report** | `src/forensic/remedy_report.py` | generate_remedy_report() — aggregates failures by component, flow, error pattern; suggests actions (check_logs, increase_timeout, circuit_breaker_open). |
| **API** | GET /api/forensic/remedy-report?since_hours=24 | Returns remedy report. |

**Wiring:** Kernel audit_cb calls record_failure when ok=False. No user-facing error until remedy report is fetched.

**Remaining for full auto-evolve:**
- Health loop (kernel, DB, bus heartbeat)
- Degraded mode (partial pipeline output on node fail)
