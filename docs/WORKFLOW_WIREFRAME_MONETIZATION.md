# FranklinOps — Expanded Workflow Wireframe, Monetization Path & Sales Agent Playbook

**Mermaid-style diagrams + monetizable path + how to conduct agents to sell it.**

---

## 1. Full System Workflow (Mermaid)

```mermaid
flowchart TB
    subgraph USER["👤 USER LAYER"]
        CMD[Franklin Command Line / Natural Language]
        UI[Web UI: /ui, /ui/development, /ui/construction, /ui/land_dev]
    end

    subgraph ORCH["ORCHESTRATION LAYER"]
        HUB[FranklinOps Hub]
        FLOWS[Flow Registry: echo, nyse_sim, pay_app_tracker, monte_carlo, development_pipeline]
    end

    subgraph KERNEL["RUNTIME KERNEL"]
        BOOT[Boot / Shutdown]
        INVOKE[Invoke = Syscall]
        HARDEN[Flow Hardening: sanitize, rate limit, circuit breaker, retry]
    end

    subgraph BUS["EVENT BUS (In-Memory)"]
        PUB[publish]
        SUB[subscribe]
        TRACE[trace_id causality]
    end

    subgraph DAG["DAG PIPELINE"]
        ZONING[zoning_assess]
        COST[cost_estimate]
        SIM[roi_simulate]
        POLICY[policy_evaluate]
        RANK[opportunity_rank]
    end

    subgraph POLICY_ENG["POLICY ENGINE"]
        APPROVE[approve]
        DENY[deny]
        ESCALATE[escalate]
    end

    subgraph DATA["DATA FABRIC"]
        RAW[raw/]
        CLEAN[clean/]
        FEAT[features/]
        RUNS[runs/]
    end

    subgraph AUDIT["AUDIT & PROVENANCE"]
        LOG[audit.jsonl]
        GOV[governance hash]
    end

    subgraph VERTICALS["VERTICALS"]
        CONSTR[FranklinOps for Construction]
        LAND[Land Development Intelligence]
        SALES[Sales / Leads]
        FIN[Finance / AP-AR]
    end

    CMD --> HUB
    UI --> HUB
    HUB --> FLOWS
    FLOWS --> INVOKE
    INVOKE --> HARDEN
    HARDEN --> DAG
    DAG --> ZONING --> COST --> SIM --> POLICY --> RANK
    POLICY --> POLICY_ENG
    DAG --> BUS
    BUS --> TRACE
    HUB --> DATA
    HUB --> AUDIT
    FLOWS --> VERTICALS
```

---

## 2. Development Pipeline Flow (Land Deal)

```mermaid
flowchart LR
    subgraph INPUT["INPUT"]
        P[Parcel / Project Spec]
    end

    subgraph PIPELINE["PIPELINE (DAG)"]
        A[zoning_assess]
        B[cost_estimate]
        C[roi_simulate]
        D[policy_evaluate]
        E[opportunity_rank]
    end

    subgraph OUTPUT["OUTPUT"]
        O[Ranked Opportunity + trace_id]
    end

    P --> A --> B --> C --> D --> E --> O
```

---

## 3. The Circle (Incoming → Outgoing → Collection → Regenerating)

```mermaid
flowchart LR
    IN[📥 INCOMING<br/>Docs, leads, invoices]
    OUT[📤 OUTGOING<br/>Emails, reports, approvals]
    COLL[📦 COLLECTION<br/>Index, audit, store]
    REGEN[🔄 REGENERATING<br/>Metrics, backlog]

    IN --> OUT --> COLL --> REGEN --> IN
```

---

## 4. Monetizable Path

```mermaid
flowchart TB
    subgraph PRODUCT["PRODUCT LAYERS"]
        CORE[FranklinOps Core: OS for Business]
        CONSTR_V[FranklinOps for Construction]
        LAND_V[Development Intelligence]
        API[API / Flows / Integrations]
    end

    subgraph REVENUE["💰 REVENUE STREAMS"]
        S1[1. SaaS Subscription<br/>Per-seat / per-tenant]
        S2[2. Vertical Licenses<br/>Construction / Land Dev]
        S3[3. API Usage / Credits<br/>Pipeline runs, Monte Carlo]
        S4[4. Professional Services<br/>Deployment, custom flows]
        S5[5. Data / Intelligence<br/>Ranked opportunities, reports]
    end

    subgraph BUYERS["TARGET BUYERS"]
        B1[GCs / Developers]
        B2[Land Developers]
        B3[Construction Finance]
        B4[Real Estate Funds]
    end

    CORE --> S1
    CONSTR_V --> S2
    LAND_V --> S2
    API --> S3
    CORE --> S4
    LAND_V --> S5

    S1 --> B1
    S2 --> B1
    S2 --> B2
    S2 --> B3
    S5 --> B2
    S5 --> B4
```

### Monetization Summary

| Path | What | Who Pays | Price Signal |
|------|------|----------|--------------|
| **SaaS** | Hub + flows + audit | GCs, developers | $X/seat/month |
| **Construction** | Pay app tracker, dashboard, lien deadlines | Construction PMs, finance | $Y/project or $Z/tenant |
| **Land Dev** | Pipeline, Monte Carlo, policy, ranked opportunities | Land developers, funds | $A/run or $B/month |
| **API** | Invoke flows, pipeline, trace replay | Integrators, partners | $C/credit |

---

## 5. Sales Agent Playbook — How to Conduct Agents to Sell It

```mermaid
flowchart TB
    subgraph AGENT["SALES AGENT CONDUCT"]
        K1[Know the value prop]
        K2[Know the vertical]
        K3[Know the objection]
    end

    subgraph SCRIPT["SCRIPT / ELEVATOR"]
        E1["Documents in. Decisions out. Humans in control."]
        E2["Bloomberg Terminal for real estate development."]
        E3["Operating system for business — not another app."]
    end

    subgraph DEMO["DEMO FLOW"]
        D1[Show /ui/boot]
        D2[Show /ui/construction or /ui/development]
        D3[Run pipeline, show trace_id]
        D4[Show audit trail]
    end

    subgraph CLOSE["CLOSE"]
        C1[Free trial / pilot]
        C2[Per-seat or per-project]
        C3[API / integration]
    end

    AGENT --> SCRIPT
    SCRIPT --> DEMO
    DEMO --> CLOSE
```

### Agent Conduct Rules

| Rule | Instruction |
|------|-------------|
| **1. Lead with value** | "Saves 10+ hours/week on pay apps and lien tracking" (Construction) or "Ranks the top 1% of deals with probability, not gut guess" (Land Dev) |
| **2. Use the tagline** | "Documents in. Decisions out. Humans in control." |
| **3. Differentiate** | "Not an app — an operating system. Everything plugs in. Everything is audited." |
| **4. Demo first** | Show `/ui/construction` or `/ui/development` before slides. |
| **5. Prove traceability** | "Every decision has a trace_id. You can replay causality." |
| **6. Offer pilot** | "Run it on one project. We'll prove ROI before you commit." |

### Vertical-Specific Scripts

**Construction (GCs, PMs):**
- "FranklinOps for Construction tracks pay apps, lien deadlines, and contract value. One dashboard. No spreadsheets."

**Land Development (Developers, Funds):**
- "Development Intelligence runs the full pipeline: parcel → zoning → cost → Monte Carlo → policy. You get ranked opportunities with probabilities, not guesses."

**Finance (AP/AR, Controllers):**
- "Invoice intake, cash flow forecasting, AR reminders. All integrated. All audited."

---

## 6. End-to-End Flow (User → Money)

```mermaid
flowchart LR
    U[User signs up]
    CONFIG[Configure roots / folders]
    INGEST[Ingest documents]
    USE[Use: flows, approvals, chat]
    VALUE[Value: time saved, better decisions]
    PAY[Pay: subscription / license]

    U --> CONFIG --> INGEST --> USE --> VALUE --> PAY
```

---

## 7. Agent Decision Tree (When to Pitch What)

```mermaid
flowchart TB
    Q{What does prospect do?}
    Q -->|Construction| CONSTR[Pitch FranklinOps for Construction]
    Q -->|Land development| LAND[Pitch Development Intelligence]
    Q -->|General ops| CORE[Pitch Core Hub]
    Q -->|Integrator / API| API[Pitch API / Flows]

    CONSTR -->|Pain: pay apps, liens| DEMO[Demo /ui/construction]
    LAND -->|Pain: deal selection| DEMO2[Demo /ui/development + pipeline]
    CORE -->|Pain: docs, approvals| DEMO3[Demo /ui/enhanced]
    API -->|Pain: automation| DEMO4[Demo POST /api/flows/*/invoke]
```

---

## 8. Quick Reference

| Item | URL / Command |
|------|---------------|
| **Download (Red Carpet)** | http://127.0.0.1:8844/ui/download — one-click zip, launcher scripts |
| Boot screen | http://127.0.0.1:8844/ui/boot |
| Main UI | http://127.0.0.1:8844/ui/enhanced |
| **Onboard Concierge** | 🛎️ button on home, construction, development, land_dev, enhanced — walk-through, navigate, approvals, component status |
| Construction | http://127.0.0.1:8844/ui/construction |
| Development | http://127.0.0.1:8844/ui/development |
| Land Dev | http://127.0.0.1:8844/ui/land_dev |
| **Ollama (Local AI)** | Auto-used when no OpenAI key. 2 steps: ollama.com → ollama pull llama3 |
| API docs | http://127.0.0.1:8844/docs |
| Verify | `python scripts/verify_integration.py` |

---

**To view Mermaid diagrams:** Paste into [Mermaid Live Editor](https://mermaid.live) or use VS Code with Mermaid extension.
