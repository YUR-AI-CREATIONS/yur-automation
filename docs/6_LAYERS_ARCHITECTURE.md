# 6 Layers — How It All Plugs In

**Event Bus → Graph Engine → Simulation → Policy → Data Fabric → FranklinOpsHub + Bid-Zone**

---

## Layer 1: Event Bus (NATS / Redis Streams / Kafka)

**Why:** Agents stop calling each other directly. Reactive, parallel, replayable, observable.

**Pattern:** Producer → Bus → Subscribers

**Core event types:**
- `parcel.discovered`
- `zoning.assessed`
- `cost.estimated`
- `roi.simulated`
- `opportunity.ranked`

**Message contract:** `event_id`, `event_type`, `ts`, `trace_id`, `tenant_id`, `actor`, `payload`, `evidence`

**Code:** `src/bus/` — Event, create_event, NatsBus (optional: `pip install nats-py`)

---

## Layer 2: Graph Execution Engine (DAG)

**Why:** Workflows are branching, parallel, conditional. State machine isn't enough.

**Pattern:** Define graph, runtime executes topologically.

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

**Code:** `src/orchestrator/dag.py` — DAG, add_node, add_edge, run

---

## Layer 3: Simulation Engine (PyMC + Monte Carlo)

**Why:** Not "ROI = 22%". Probability ROI ≥ target, probability of loss, VaR.

**Output:** roi_mean, roi_p10/p50/p90, p_roi_ge_target, p_loss

**Code:** `src/simulation/monte_carlo.py` — simulate_roi

---

## Layer 4: Policy Engine

**Rule:** Agents do work. Policies decide.

**Agents:** extract, compute, propose  
**Policies:** approve, route, gate, escalate

**Code:** `src/policy/engine.py` — PolicyEngine.evaluate_deal  
**Config:** `policies/deal_policy.yaml`

---

## Layer 5: Data Fabric

**Structure:**
- raw/ — original source, immutable
- clean/ — normalized tables
- features/ — model-ready
- runs/ — simulation runs with trace_id
- evidence/ — PDFs, hashes

**Code:** `data/fabric/` — directory structure

---

## Layer 6: Integration — FranklinOpsHub + Bid-Zone

**Operating loop:**

1. **Ingest** — emails, bid sites, parcels, docs
2. **Publish events** to the bus
3. **DAG orchestrator** composes workflows by intent (land / bid / finance / ops)
4. **Bid-Zone** runs CSI estimate + risk extraction
5. **Simulation engine** returns probabilities
6. **Policy engine** decides approve/deny/escalate
7. **FranklinOps UI** shows package + requires approval when escalated
8. **Audit log** records every step (trace_id links it all)

---

## Geo-Economic Intelligence Engine

Sits upstream. Emits: `corridor.signal_detected`, `metro.migration_shift`, `permit.acceleration`

Just another producer on the bus + workflow in the DAG.

When it flags a corridor → orchestrator kicks off: land discovery → comps → zoning → feasibility → bid-zone cost → simulation + ranking → ranked list with probabilities.

---

## Implemented (Highest Granularity)

| Component | Status | Location |
|-----------|--------|----------|
| **In-memory Event Bus** | Done | `src/bus/in_memory_bus.py` — get_bus(), publish(), subscribe() |
| **Event contract** | Done | trace_id, event_id, event_type, payload, evidence |
| **DAG pipeline** | Done | `src/pipeline/land_deal.py` — full parcel→zoning→cost→sim→policy |
| **development_pipeline flow** | Done | Plugged. POST /api/flows/development_pipeline/invoke |
| **POST /api/development/pipeline** | Done | Run full pipeline, audit with trace_id |
| **GET /api/development/trace/{trace_id}** | Done | Causality replay |

**UI:** http://127.0.0.1:8844/ui/development

---

## Next Actions (In Order)

1. Pick bus (NATS or Redis Streams), wire trace_id everywhere
2. Implement 5 core event types
3. Add DAG workflow registry (workflows/land_deal.yaml, workflows/bid_job.yaml)
4. Wrap Bid-Zone estimate into standard metrics payload
5. Put PolicyEngine in front of every action
6. Log everything into AuditLog keyed by trace_id
