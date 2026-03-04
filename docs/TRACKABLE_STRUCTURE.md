# Trackable File Structure and Agent Mapping

Canonical mapping of Cursor project paths to FranklinOps agents and workflows.

## Cursor Projects Root

```
C:\Users\jerem\.cursor\projects\
```

---

## Trackable Roots

### Main Systems

| Project | Env Var | Role |
|---------|---------|------|
| **d-Superagents** | `FRANKLINOPS_SUPERAGENTS_ROOT` | FranklinOps hub, GROKSTMATE, orchestration |
| **d-XAI-BID-ZONE** | `FRANKLINOPS_BID_ZONE_ROOT` | Sales portal (estimating, land procurement) |
| **d-Franklin-OS-local** | `FRANKLINOPS_FRANKLIN_OS_ROOT` | Franklin OS |
| **d-JCK-Land-Development** | `FRANKLINOPS_JCK_LAND_DEV_ROOT` | Land development |

### Project Controls (c-00-Project-Controls-*)

Each log type is a separate Cursor workspace:

| Project | Env Var | Role |
|---------|---------|------|
| c-00-Project-Controls-Change-Order-Log | `FRANKLINOPS_PC_CHANGE_ORDER` | Change orders |
| c-00-Project-Controls-Document-Log | `FRANKLINOPS_PC_DOCUMENT` | Document tracking |
| c-00-Project-Controls-Long-Lead-Material-Log | `FRANKLINOPS_PC_LONG_LEAD_MATERIAL` | Long-lead materials |
| c-00-Project-Controls-Material-Delivery-Log | `FRANKLINOPS_PC_MATERIAL_DELIVERY` | Material deliveries |
| c-00-Project-Controls-Material-Return-Log | `FRANKLINOPS_PC_MATERIAL_RETURN` | Material returns |
| c-00-Project-Controls-Material-Shortage-Log | `FRANKLINOPS_PC_MATERIAL_SHORTAGE` | Material shortages |
| c-00-Project-Controls-Project-Roster | `FRANKLINOPS_PC_PROJECT_ROSTER` | Project roster/contacts |
| c-00-Project-Controls-Rain-Delay-Log | `FRANKLINOPS_PC_RAIN_DELAY` | Rain delay tracking |
| c-00-Project-Controls-RFI-Log | `FRANKLINOPS_PC_RFI` | RFIs |
| c-00-Project-Controls-Submittal-Log | `FRANKLINOPS_PC_SUBMITTAL` | Submittals |
| c-00-Project-Controls-Substitution-Log | `FRANKLINOPS_PC_SUBSTITUTION` | Substitutions |
| c-00-Project-Controls-Value-Engineering-Log | `FRANKLINOPS_PC_VALUE_ENGINEERING` | Value engineering |

### OneDrive Roots (when configured)

| Root | Env Var | Role |
|------|---------|------|
| 02BIDDING | `FRANKLINOPS_ONEDRIVE_BIDDING_ROOT` | New opportunities (ITBs, RFQs, contacts) |
| 01PROJECTS | `FRANKLINOPS_ONEDRIVE_PROJECTS_ROOT` | Active work (project docs, submittals) |
| Attachments | `FRANKLINOPS_ONEDRIVE_ATTACHMENTS_ROOT` | Invoices, submittals, misc paperwork |

---

## Ecosystem Overview

```
C:\Users\jerem\.cursor\projects\
├── d-Superagents/           # FranklinOps hub, GROKSTMATE
├── d-XAI-BID-ZONE/         # Sales portal (BID-ZONE)
├── d-Franklin-OS-local/     # Franklin OS
├── d-JCK-Land-Development/  # Land development
├── c-00-Project-Controls-Change-Order-Log/
├── c-00-Project-Controls-Document-Log/
├── c-00-Project-Controls-Long-Lead-Material-Log/
├── c-00-Project-Controls-Material-Delivery-Log/
├── c-00-Project-Controls-Material-Return-Log/
├── c-00-Project-Controls-Material-Shortage-Log/
├── c-00-Project-Controls-Project-Roster/
├── c-00-Project-Controls-Rain-Delay-Log/
├── c-00-Project-Controls-RFI-Log/
├── c-00-Project-Controls-Submittal-Log/
├── c-00-Project-Controls-Substitution-Log/
└── c-00-Project-Controls-Value-Engineering-Log/
```

---

## Agent → Folder Mapping

| Agent / Spoke | Primary Sources | Purpose |
|---------------|-----------------|---------|
| **SalesSpokes** | onedrive_bidding, pc_project_roster | Lead capture, ITB detection, pipeline |
| **FinanceSpokes** | onedrive_attachments, pc_change_order, pc_rfi, pc_submittal | AP intake, AR follow-up, cashflow |
| **DocIngestion** | All roots | Birthmark, delta scan, vector index |
| **GROKSTMATE CostEstimator** | pc_value_engineering, bid_zone | Cost estimation |
| **GROKSTMATE ProjectManager** | pc_* (all project controls) | Scheduling, resource allocation |
| **BID-ZONE** | bid_zone | Sales portal — estimating, land procurement |
| **Ops Chat** | All ingested (via DocIndex) | RAG, grounded Q&A |

---

## Configuration

Paths default to Cursor project locations. Override in `.env` only if your paths differ:

```bash
# Main systems (defaults used when empty)
FRANKLINOPS_SUPERAGENTS_ROOT=
FRANKLINOPS_BID_ZONE_ROOT=
FRANKLINOPS_FRANKLIN_OS_ROOT=
FRANKLINOPS_JCK_LAND_DEV_ROOT=

# Project Controls (defaults used when empty)
FRANKLINOPS_PC_CHANGE_ORDER=
FRANKLINOPS_PC_DOCUMENT=
# ... etc
```

All configured roots are ingested when running:

- `python -m src.franklinops.run_pilot`
- `python -m src.franklinops.sales_runner --once`
- `POST /api/ingest/run`