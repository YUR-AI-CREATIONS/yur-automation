# Franklin OS — Architecture Blueprint

**Foundational philosophy and system topology. No detail omitted.**

---

## I. Foundational Philosophy

Franklin OS is designed as a **sovereign economic intelligence runtime** rather than a traditional application.

**Typical software:**
```
input → processing → output
```

**Franklin OS:**
```
data ingestion
→ structural analysis
→ probabilistic simulation
→ policy evaluation
→ economic decision
→ real-world validation
→ learning feedback
→ improved models
```

The system is **adaptive analytical infrastructure** capable of evolving with the economic environment it observes.

### Five Guiding Principles

| Principle | Description |
|-----------|-------------|
| **Sovereign Control** | All critical data and decision logic remain locally controlled and auditable. |
| **Deterministic Governance** | No autonomous action occurs without policy validation and recorded provenance. |
| **Event-Driven Intelligence** | System components communicate through events rather than direct calls. |
| **Probabilistic Decision Framework** | Economic predictions rely on simulation and statistical modeling rather than heuristics. |
| **Reality Feedback Evolution** | Predictions are continuously validated against real outcomes to improve system accuracy. |

---

## II. System Topology

Six structural layers:

1. **User Layer**
2. **Interface Layer**
3. **Runtime Kernel**
4. **Event Fabric**
5. **Intelligence Engines**
6. **Data Fabric**

Each layer is independent yet connected through clearly defined interfaces.

---

## III. User Layer

Human interaction boundary.

**Three modes:**
- Natural language command interface
- Command-line execution interface
- Web-based operational dashboards

**Purpose:** Translate human intent into structured operational flows.

**Example intents:**
- "Analyze development potential for this parcel."
- "Estimate construction cost from these plans."
- "Identify high-growth corridors in Texas."

---

## IV. Interface Layer

Exposes system capabilities.

| Component | Role |
|-----------|------|
| **API gateway** | External access with authentication, rate limits, governance checks |
| **Web application interface** | Operational dashboards |
| **Command-line shell** | Full runtime for power users |
| **Integration endpoints** | Third-party connections |

---

## V. Runtime Kernel

Core execution environment.

**Responsibilities:**
- Flow orchestration
- Policy enforcement
- Security validation
- Resource coordination
- System lifecycle management (boot, invoke, shutdown)

**Flows:** Deterministic pipelines of analytical steps. Each flow has `flow_id`, `name`, `direction`, `scope`, `timeout_seconds`.

**Built-in flows:**
| flow_id | Name | Direction | Description |
|---------|------|-----------|-------------|
| echo | Echo | incoming | Passthrough: in → out |
| reverse | Reverse | regenerating | Reverse keys/values |
| nyse_sim | NYSE Simulation | incoming | Deterministic market sim: quote, ohlcv, optimize, predict |
| pay_app_tracker | Pay App Tracker | incoming | Track pay apps: status, amounts, lien deadlines |
| construction_dashboard | Construction Dashboard | incoming | Project summary: contract value, billed, received, outstanding |
| monte_carlo | Monte Carlo Underwriting | incoming | Probabilistic ROI: p_roi_ge_target, p_loss |
| policy_evaluate | Policy Evaluate | incoming | Policy-driven: approve/deny/escalate |
| development_pipeline | Development Pipeline | incoming | Full DAG: parcel→zoning→cost→sim→policy |

**Trace identifiers:** Every execution chain gets a `trace_id`. All actions auditable. Causality replay via `GET /api/development/trace/{trace_id}`.

**Flow hardening (every invocation):**
1. Input sanitization (strip XSS, limit depth)
2. Rate limit (per flow, per tenant; default 120/min)
3. Circuit breaker (5 failures → 60s cooldown)
4. Timeout enforcement (per-flow)
5. Retry with exponential backoff
6. Audit (every invocation logged)

---

## VI. Event Fabric

Asynchronous communication. No direct service calls.

**Event contract (every event):**
- `event_id` — unique
- `event_type` — subject
- `ts` — UTC ISO
- `trace_id` — causality chain
- `tenant_id` — multi-tenancy
- `actor` — who produced
- `payload` — data
- `evidence` — sources, hashes

**Core event types:**
| Event | Emitted by |
|-------|------------|
| `parcel.discovered` | land_agent |
| `zoning.assessed` | zoning_agent |
| `cost.estimated` | cost_engine |
| `roi.simulated` | simulation_engine |
| `opportunity.ranked` | ranker |
| `corridor.signal_detected` | geo-economic (future) |
| `metro.migration_shift` | geo-economic (future) |
| `permit.acceleration` | geo-economic (future) |

**Blueprint events (to wire):**
- `plan_uploaded`
- `estimate_complete`
- `simulation_complete`
- `policy_decision`

**Properties:** Horizontal scalability, fault isolation, workflow replay, system observability.

**Implementation:** `src/bus/in_memory_bus.py` — `get_bus()`, `publish()`, `subscribe()`. Optional: NATS (`nats_client.py`).

---

## VII. Flow Execution Graph

All analytical workflows = **directed acyclic graphs (DAGs)**.

**Node** = processing stage. **Edge** = execution dependency.

**Land deal DAG (implemented):**
```
parcel.discovered (emit)
    → zoning_assess
    → infrastructure_proximity
    → market_demand
    → cost_estimate
    → roi_simulate
    → policy_evaluate
    → opportunity_rank (emit opportunity.ranked)
```

**Blueprint expansion (future):**
```
parcel.discovered
   ├─> zoning.assess
   ├─> utilities.assess
   └─> comps.pull
         ↓
      cost.estimate
         ↓
     roi.simulate
         ↓
  opportunity.rank
```

**Code:** `src/orchestrator/dag.py` — DAG, add_node, add_edge, topological_sort, run.  
**Pipeline:** `src/pipeline/land_deal.py` — build_land_deal_dag, run_land_deal_pipeline.

---

## VIII. Intelligence Engines

| Engine | Role | Implementation |
|--------|------|----------------|
| **Construction Intelligence** | Plans/specs → estimates. Quantities, costs, scope risks. | GROKSTMATE, `construction_flows.py`, `bidzone_bridge.py` |
| **Land Intelligence** | Parcels → viability. Zoning, infrastructure, land value, demographics. | `land_deal.py` (zoning_assess, cost_estimate) |
| **Geo-Economic Intelligence** | Regional indicators: migration, housing demand, infrastructure, employment. | Future — emits corridor.signal_detected |
| **Simulation Engine** | Monte Carlo: cost inflation, rates, absorption, demand. | `monte_carlo.py` — simulate_roi |
| **Policy Engine** | Permissibility: min return, max capital, risk thresholds. | `policy/engine.py`, `deal_policy.yaml` |
| **Opportunity Ranking** | Aggregates outputs, assigns scores. | `land_deal.py` — opportunity_rank |

---

## IX. Data Fabric

Structured domains:

| Domain | Path | Contents |
|--------|------|----------|
| **Raw** | `data/fabric/raw/` | Unprocessed: permits, census, parcel records |
| **Normalized** | `data/fabric/clean/` | Standardized for analysis |
| **Feature** | `data/fabric/features/` | Engineered variables for models |
| **Simulation** | `data/fabric/runs/` | Monte Carlo outputs, trace_id |
| **Evidence** | `data/fabric/evidence/` | PDFs, hashes |
| **Audit** | `audit_events` table, `audit.jsonl` | All actions, decisions, policy validations |

**Stub:** `src/data_fabric/` — ingest_raw, normalize_to_clean, build_features (to be wired).

---

## X. Geo-Economic Intelligence Engine

Identifies regions with strong future development potential.

**Signals:**
- Population migration
- Housing permit growth
- Infrastructure investment
- Employment expansion
- Land price trends

**Output:** Development probability score per region. Highest = growth corridors. Parcel-level analysis follows.

**Events:** `corridor.signal_detected`, `metro.migration_shift`, `permit.acceleration`

**Status:** Future. Sits upstream on event bus.

---

## XI. Simulation Engine

Economic decisions are uncertain.

**Key variables (Monte Carlo):**
- `interest_rate_mu`, `interest_rate_sigma`
- `inflation_mu`, `inflation_sigma`
- `absorption_mu`, `absorption_sigma`
- `base_profit`, `capital_deployed`, `target_roi`

**Output:**
- `roi_mean`, `roi_std`
- `roi_p10`, `roi_p50`, `roi_p90`
- `p_roi_ge_target` — probability ROI ≥ target
- `p_loss` — probability of loss
- `n_runs`, `target_roi`

**Code:** `src/simulation/monte_carlo.py` — simulate_roi(n=10000, ...)

---

## XII. Reality Feedback Engine

Evaluates prediction accuracy.

**Per forecast:**
- Record predicted outcomes
- Record actual real-world outcomes
- Calculate prediction error metrics
- Adjust model parameters

**Status:** Future. Learning feedback loop.

---

## XIII. Governance and Audit Framework

Every automated decision must be auditable.

**Recorded:**
- Input data
- Analytical steps
- Simulation results
- Policy evaluations
- Final decisions

**Trace identifiers:** Full causal chain reconstruction.

**Evidence requirements (Autonomy Gate):**
- `blake_birthmark` — content fingerprint
- `intent` — human-readable intent
- `timestamp` — ISO, within replay window (default 300s)
- `signature` — HMAC-SHA256 over canonical payload (or PQC when liboqs present)

**Governance scopes:**
| Scope | Auto-execute | Human approval | MFA |
|-------|--------------|----------------|-----|
| internal | Yes | No | No |
| external_low | Yes | No | No |
| external_medium | No | Yes (1h) | No |
| external_high | No | Yes (24h) | Yes |
| restricted | No | Yes (2h) | Yes |

**Autonomy modes:** shadow → assist → autopilot (human controls escalation).

**Governance Manifest:** Articles I–VIII. See `docs/GOVERNANCE_MANIFEST.md`.

---

## XIV. Policy Engine

**Rule:** Agents do work. Policies decide.

**Deal policy (`policies/deal_policy.yaml`):**
```yaml
constraints:
  min_roi: 0.18
  max_probability_of_loss: 0.12
  max_capital: 20000000
  max_duration_months: 36

escalation:
  if_roi_between: [0.16, 0.18]
  send_to: franklin_review

deny:
  if_probability_of_loss_gt: 0.20
```

**Actions:** approve | deny | escalate

**Code:** `src/policy/engine.py` — PolicyEngine.evaluate_deal(metrics)

---

## XV. Deployment Model

**Target:** Distributed containerized services.

| Service Type | Role |
|--------------|------|
| **Core runtime** | Orchestration, governance |
| **Analytical** | Domain-specific computations |
| **Infrastructure** | Messaging, storage, indexing |

**Current:** Single-process Python. SQLite. In-memory event bus. Horizontal scaling via event fabric when NATS/Kafka wired.

---

## XVI. Economic Intelligence Loop

```
Data ingestion
→ economic signal analysis
→ corridor detection
→ parcel evaluation
→ construction estimation
→ financial simulation
→ policy validation
→ opportunity ranking
→ real-world project outcomes
→ model improvement
```

---

## XVII. The Circle (Operational Loop)

| Phase | Meaning |
|-------|---------|
| **Incoming** | Docs, leads, invoices arrive |
| **Outgoing** | Emails, reports, approvals leave |
| **Collection** | Index, audit, store — nothing lost |
| **Regenerating** | Metrics, backlog — system improves |

*Incoming → Outgoing → Collection → Regenerating → Incoming*

---

## XVIII. Strategic Outcome

Franklin OS = **economic intelligence infrastructure**.

- Actively discovers opportunities
- Analyzes geographic and economic signals
- Models financial outcomes
- Ranks by statistical probability

Platform for informed economic decision-making across construction, development, and infrastructure investment.

---

## XIX. BID-ZONE Analysis Engine

**Components:**
- CSI Division Estimating
- Cost Database
- Vendor Pricing
- Pay Application Analysis
- Contract Interpretation
- Delay Detection
- Financial Performance Models

**Bridge:** `src/integration/bidzone_bridge.py` — run_estimate (delegates to GROKSTMATE), bidzone_native_estimate (stub for BID_ZONE_API_URL).

---

## XX. Forensic Memory

**Concept:** Immutable execution ledger.

- Merkle event chain
- State snapshots
- Decision replay
- Audit trail

**Current:** Append-only audit_events, audit.jsonl, governance hash. trace_id links causality. `GET /api/development/trace/{trace_id}` for replay.

---

## XXI. Approval Workflow

**Flow:** Request → Gate check → Approval record → Human decide → Execute (if approved).

**Evidence:** create_evidence(blake_birthmark, intent) → HMAC signature when TRINITY_SIGNING_SECRET set.

**Code:** `src/franklinops/approvals.py` — ApprovalService, build_default_gate.

---

## XXII. UI Routes

| Route | Purpose |
|-------|---------|
| /ui | Hub home |
| /ui/boot | OS boot sequence |
| /ui/enhanced | Main operational dashboard |
| /ui/ops | Operations |
| /ui/sales | Sales, leads, outbound |
| /ui/finance | Finance, AP/AR, cashflow |
| /ui/grokstmate | GROKSTMATE status |
| /ui/fleet | Fleet agents |
| /ui/bidzone | BID-ZONE |
| /ui/project_controls | Project controls |
| /ui/rollout | Rollout |
| /ui/flows | Flow registry, invoke, plug |
| /ui/nyse | NYSE simulation |
| /ui/construction | FranklinOps for Construction |
| /ui/development | Development pipeline, trace replay |
| /ui/land_dev | JCK Land Dev |
| /ui/admin | Enterprise admin |

---

## XXIII. Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| GET /healthz | Health check |
| GET /api/config | Configuration |
| GET /api/autonomy | Autonomy modes |
| GET/POST /api/approvals/* | Approval workflow |
| GET /api/audit | Audit log |
| POST /api/development/pipeline | Run land deal pipeline |
| GET /api/development/trace/{trace_id} | Causality replay |
| GET /api/flows | List flows |
| POST /api/flows/plug | Register flow |
| POST /api/flows/{flow_id}/invoke | Invoke flow |
| GET /api/governance/hash | Governance provenance |
| GET /api/kernel | Kernel status |

---

## XXIV. Implementation Map (Complete)

| Blueprint Component | Implementation | Location |
|---------------------|----------------|----------|
| User Layer | Web UI, CLI | `/ui/*`, `run_kernel.py` |
| Interface Layer | FastAPI, middleware | `server.py`, `middleware.py` |
| Runtime Kernel | Boot, invoke, shutdown | `src/core/kernel.py` |
| Event Fabric | In-memory bus, trace_id | `src/bus/` |
| Flow Execution Graph | DAG pipeline | `src/pipeline/land_deal.py`, `src/orchestrator/dag.py` |
| Construction Intelligence | GROKSTMATE, pay app tracker | `src/integration/construction_flows.py` |
| Land Intelligence | Zoning, cost, parcel | `src/pipeline/land_deal.py` |
| Geo-Economic Engine | Corridor scanner, score_region | `src/geo_economic/` |
| Simulation Engine | Monte Carlo | `src/simulation/monte_carlo.py` |
| Policy Engine | YAML policy | `src/policy/engine.py`, `policies/deal_policy.yaml` |
| Opportunity Ranking | DAG final node | `src/pipeline/land_deal.py` |
| Data Fabric | raw/clean/features/runs/evidence | `data/fabric/`, `src/data_fabric/` |
| Governance & Audit | Audit log, governance hash | `audit.py`, `governance_provenance.py` |
| Flow Hardening | Sanitize, rate limit, circuit breaker, retry | `src/core/flow_hardening.py` |
| Evidence Verification | blake_birthmark, intent, timestamp, signature | `src/core/autonomy_gate.py` |
| Approval Service | Request, decide, execute | `src/franklinops/approvals.py` |
| BID-ZONE | Bridge, native stub | `src/integration/bidzone_bridge.py` |

---

## XXV. Cross-References

| Document | Content |
|----------|---------|
| [GOVERNANCE_MANIFEST.md](GOVERNANCE_MANIFEST.md) | Articles I–VIII, 50-year principles |
| [6_LAYERS_ARCHITECTURE.md](6_LAYERS_ARCHITECTURE.md) | Event Bus, DAG, Simulation, Policy, Data Fabric |
| [FRANKLIN_DEVELOPMENT_INTELLIGENCE.md](FRANKLIN_DEVELOPMENT_INTELLIGENCE.md) | Full vision, agent layer, BID-ZONE |
| [RUNTIME_KERNEL.md](RUNTIME_KERNEL.md) | Kernel boot, invoke, shutdown |
| [FRANKLINOPS_FOR_CONSTRUCTION.md](FRANKLINOPS_FOR_CONSTRUCTION.md) | Construction vertical |
| [WORKFLOW_WIREFRAME_MONETIZATION.md](WORKFLOW_WIREFRAME_MONETIZATION.md) | Mermaid diagrams, monetization, sales playbook |
| [governance-policies.json](../governance-policies.json) | Scopes, evidence, PQC config |
