# FranklinOps + GROKSTMATE Integration — Complete

## What Was Built

### 1. Integration Bridge (`src/integration/`)

- **bridge.py** — Connects GROKSTMATE (CostEstimator, ProjectManager, TaskAgent, BotDeploymentManager) to FranklinOps
- **governance_adapter.py** — Wraps GROKSTMATE operations with audit logging and approval workflows
- **unified_orchestrator.py** — Runs GROKSTMATE phase as part of the FranklinOps pilot

### 2. Trackable Roots (Cursor Project Paths)

All roots default to `C:\Users\jerem\.cursor\projects\`:

| Source | Path |
|--------|------|
| superagents | d-Superagents |
| bid_zone | d-XAI-BID-ZONE (sales portal) |
| franklin_os | d-Franklin-OS-local |
| jck_land_dev | d-JCK-Land-Development |
| pc_change_order | c-00-Project-Controls-Change-Order-Log |
| pc_document | c-00-Project-Controls-Document-Log |
| pc_long_lead_material | c-00-Project-Controls-Long-Lead-Material-Log |
| pc_material_delivery | c-00-Project-Controls-Material-Delivery-Log |
| pc_material_return | c-00-Project-Controls-Material-Return-Log |
| pc_material_shortage | c-00-Project-Controls-Material-Shortage-Log |
| pc_project_roster | c-00-Project-Controls-Project-Roster |
| pc_rain_delay | c-00-Project-Controls-Rain-Delay-Log |
| pc_rfi | c-00-Project-Controls-RFI-Log |
| pc_submittal | c-00-Project-Controls-Submittal-Log |
| pc_substitution | c-00-Project-Controls-Substitution-Log |
| pc_value_engineering | c-00-Project-Controls-Value-Engineering-Log |

### 3. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/grokstmate/status` | GET | Check if GROKSTMATE is available |
| `/api/grokstmate/estimate` | POST | Run cost estimation (JSON body: name, type, size, complexity) |
| `/api/grokstmate/project` | POST | Create project plan (JSON body: project_id, project_name, project_spec) |

### 4. Dashboard

- **/ui/grokstmate** — GROKSTMATE dashboard with cost estimate and project plan creation
- Link added to `/ui` home

### 5. Pilot Integration

The `run_pilot()` now includes a GROKSTMATE phase:

- Runs cost estimation (demo)
- Results in `results["grokstmate"]`

### 6. Governance

- All GROKSTMATE actions logged to FranklinOps audit
- Actions: `grokstmate_estimate`, `grokstmate_create_plan`, `grokstmate_deploy_bots`

## Verification (Live Tests)

Run `python scripts/verify_integration.py` to prove the integration works. See [docs/VERIFICATION.md](VERIFICATION.md) for results.

---

## Quick Start

```bash
# Install GROKSTMATE (if not already)
pip install -e GROKSTMATE

# Run pilot (includes GROKSTMATE)
python -m src.franklinops.run_pilot

# Start server
python -m uvicorn src.franklinops.server:app --host 0.0.0.0 --port 8844

# Open dashboard
# http://localhost:8844/ui
# http://localhost:8844/ui/grokstmate
```

## Ecosystem

```text
BID-ZONE (d-XAI-BID-ZONE)     → Sales portal
FranklinOps (d-Superagents)   → Hub, SalesSpokes, FinanceSpokes, GROKSTMATE
Project Controls (c-00-*)     → 12 log workspaces
```
