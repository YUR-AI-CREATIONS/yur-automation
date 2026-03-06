# Franklin Upgrade Roadmap

**The layers that transform Franklin from agent-driven to policy-driven, reactive, and probabilistic.**

---

## The Problem Today

- **Agents talk directly** — does not scale
- **Sequential execution** — not reactive
- **No probabilistic modeling** — gut instinct, not Monte Carlo
- **Agent-driven decisions** — not auditable, not policy-modifiable

---

## Missing Layer 1: Event Bus

**Right now:** Agents call each other directly.

**Need:** Agent → Event Bus → Agent

| Option | Use Case |
|--------|----------|
| **NATS** | Lightweight, fast, simple |
| **Kafka** | High throughput, replay, persistence |
| **Redis Streams** | Already in stack, good for moderate scale |

### Example Flow

```
land_agent publishes parcel_discovered
    │
    ├─→ finance_agent subscribes
    ├─→ simulation_agent subscribes
    └─→ bid_engine subscribes
```

**Result:** System becomes **reactive** instead of sequential. One event fans out to many consumers. Scale by adding subscribers.

---

## Missing Layer 2: Graph Execution Engine

**Right now:** Manual code, linear flows.

**Need:** Define workflows as **directed acyclic graphs (DAGs)**. Runtime executes the graph.

### Example DAG

```
land_discovered
    ↓
zoning_analysis
    ↓
cost_model
    ↓
simulation
    ↓
ranking
```

**Rust libraries:** `petgraph`, `daggy`

**Benefit:** Dynamically construct workflows. No manual orchestration code. Add nodes, connect edges, runtime executes.

---

## Missing Layer 3: Simulation Engine

**Right now:** NYSE sim is deterministic (seed-based). Not probabilistic.

**Need:** Real probabilistic engine for institutional underwriting.

| Tool | Purpose |
|------|---------|
| **PyMC** | Probabilistic programming |
| **NumPy** | Numerical ops |
| **ArviZ** | Visualization, diagnostics |

### Simulation Example

- Interest rate volatility
- Construction inflation
- Absorption curves

**Monte Carlo:** 10,000 runs → **probability of ROI success**

That's how institutional investors underwrite projects.

---

## The Biggest Upgrade: Policy-Driven Runtime

**Right now:** Agent-driven. Agents decide.

```python
if roi > 0.15:
    buy_land()
```

**Target:** Policy-driven. **Agents never decide. Policies decide.**

```yaml
policy:
  min_roi: 0.18
  max_risk: 0.35
  max_capital: 20M
```

Runtime evaluates:

```python
policy_engine.evaluate(project)
```

### Benefits

| Benefit | Why |
|---------|-----|
| **Auditable** | Every decision traces to a policy |
| **Modifiable without code** | Change policy, not agents |
| **Governance friendly** | Policies are the governance layer |

**This is how high-assurance systems operate.**

---

## Target Architecture

```
               FranklinOps
                   │
                   │
           Sovereign Runtime
                   │
        ┌──────────┴──────────┐
        │                     │
     Event Bus           Policy Engine
        │                     │
        │                     │
 ┌──────┴──────────────┐     │
 │                     │     │
Land Discovery      Finance Engine
 │                     │
 │                     │
Migration Engine    Cost Engine
 │                     │
 │                     │
 Simulation Engine    CSI Estimator
 │
 │
Opportunity Ranker
 │
 │
Decision Engine  ←── policy_engine.evaluate()
```

---

## What Makes This Special

| Typical AI | Franklin |
|------------|----------|
| prompt → answer | **data → simulation → probabilistic decision** |

Closer to:

- **Bloomberg Terminal** — data, analytics, decision support
- **Palantir Foundry** — data fusion, pipelines, models
- **Renaissance Technologies** — probabilistic, quantitative

Than a typical AI product.

---

## Honest Observation

**Strong:** Philosophy, governance, audit, policy thinking.

**Weak:** Data pipeline layer is not built yet.

Without:

- Data ingestion
- Data normalization
- Data streaming

the intelligence layer will starve.

**Priority:** Build the data pipeline before scaling agents.

---

## Next Upgrade: Geo-Economic Intelligence Engine

Detect **where growth corridors will emerge** by analyzing:

- Migration patterns
- Housing permits
- Infrastructure spending
- Traffic expansion
- Employment clusters

**That's how hedge funds identify growth before developers.**

---

## The Ultimate Target

*Architecture that would let FranklinOps automatically discover the best land investments in the entire United States before anyone else does.*

---

## Related

- [FRANKLIN_DEVELOPMENT_INTELLIGENCE.md](FRANKLIN_DEVELOPMENT_INTELLIGENCE.md) — Full vision, full architecture
- [GOVERNANCE_MANIFEST.md](GOVERNANCE_MANIFEST.md) — Policy-driven aligns with governance
- [50_YEAR_ARCHITECTURE.md](50_YEAR_ARCHITECTURE.md) — Design principles for longevity
