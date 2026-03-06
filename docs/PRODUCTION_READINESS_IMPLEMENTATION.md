# Franklin OS Production Readiness — Implementation Summary

**Goal:** Zero gaps. Every inch built to excellence. Only external APIs and subscriptions left for you to gather.

---

## 1. API Validation (Pydantic Schemas)

All previously unvalidated endpoints now use strict Pydantic models:

| Endpoint | Schema |
|----------|--------|
| `POST /api/data-fabric/ingest` | `DataFabricIngestIn` |
| `POST /api/data-fabric/normalize` | `DataFabricNormalizeIn` |
| `POST /api/data-fabric/features` | `DataFabricFeaturesIn` |
| `POST /api/geo-economic/corridors` | `GeoEconomicCorridorsIn` |
| `POST /api/reality-feedback/prediction` | `RealityFeedbackPredictionIn` |
| `POST /api/reality-feedback/outcome` | `RealityFeedbackOutcomeIn` |
| `POST /api/development/pipeline` | `DevelopmentPipelineIn` |
| `POST /api/project_controls/logs` | `ProjectControlLogCreateIn` |
| `PUT /api/project_controls/logs/{id}` | `ProjectControlLogUpdateIn` |
| `POST /api/grokstmate/estimate` | `ProjectSpecIn` |
| `POST /api/grokstmate/project` | `GrokstmateCreateProjectIn` |
| `POST /api/bidzone/estimate` | `ProjectSpecIn` |

**File:** `src/franklinops/schemas.py`

---

## 2. Error Handling — No Silent Swallowing

| Location | Before | After |
|----------|--------|-------|
| `server.py` dotenv | `except Exception: pass` | Log warning on failure |
| `server.py` corridor_scan ImportError | `pass` | Log info |
| `server.py` shutdown | `pass` | Log warning |
| `server.py` project_control entry_data parse | `pass` | Log debug, set `{}` |
| `kernel.py` shutdown audit | `pass` | Log debug |
| `kernel.py` record_failure | `pass` | Log debug |
| `data_fabric/ingest.py` normalize | `except: continue` | Log warning, return `errors` in response |
| `data_fabric/ingest.py` build_features | `except: continue` | Log warning, return `errors` in response |
| `policy/engine.py` YAML load | `except: policy={}` | Log warning |
| `finance_spokes.py` _parse_date | `except: pass` | Narrow to `ValueError, TypeError` |
| `doc_ingestion.py` xlsx close | `pass` | Log debug |

---

## 3. Pipeline — Data Fabric Integration

**Before:** `infrastructure_proximity` and `market_demand` were hardcoded stubs.

**After:**
- Load features from `data/fabric/features/{dataset}/` when available
- `infrastructure` dataset: `utilities_available`, `road_access`, `transit_miles`, `water_sewer`, `score`
- `market_demand` dataset: `absorption_months`, `demand_index`, `price_sensitivity`
- Fallback to sensible defaults when Data Fabric not populated
- Cost factors moved to env: `FRANKLINOPS_LAND_COST_PER_ACRE`, `FRANKLINOPS_BUILD_COST_PER_SF`, `FRANKLINOPS_COVERAGE_RATIO`

---

## 4. BID-ZONE Bridge — Real HTTP When Configured

**Before:** Always returned `stub: True` even when `BID_ZONE_API_URL` was set.

**After:**
- When `BID_ZONE_API_URL` and `BID_ZONE_API_KEY` are set, performs real HTTP POST
- Endpoint: `BID_ZONE_ESTIMATE_ENDPOINT` or `{BID_ZONE_API_URL}/estimate`
- Returns `stub: False` with `total_estimate` and `details` on success
- Returns structured error on failure

---

## 5. BID-ZONE Sync — Full Lead Capture

**Before:** Returned `synced: 0` with note "add doc ingestion".

**After:**
- Runs `ingest_roots` on BID-ZONE root
- When `sales_spokes` is passed (server does this), runs `scan_inbound_itbs(source="bid_zone")`
- Creates/updates `sales_leads` and `opportunities` from ITB/RFP artifacts

---

## 6. Config — Env Vars for Hardcoded Values

| Env Var | Default | Purpose |
|---------|---------|---------|
| `FRANKLINOPS_LAND_COST_PER_ACRE` | 50000 | Pipeline cost model |
| `FRANKLINOPS_BUILD_COST_PER_SF` | 80 | Pipeline cost model |
| `FRANKLINOPS_COVERAGE_RATIO` | 0.3 | Pipeline coverage |
| `FRANKLINOPS_OLLAMA_API_URL` | localhost:11434 | Cognitive query LLM |
| `FRANKLINOPS_OLLAMA_MODEL` | llama3 | Cognitive query model |
| `NATS_URL` | nats://127.0.0.1:4222 | NATS bus |
| `TRINITY_API_BASE_URL` | yur-ai-api.onrender.com | Trinity leads API |
| `BID_ZONE_ESTIMATE_ENDPOINT` | `{BID_ZONE_API_URL}/estimate` | BID-ZONE estimate URL |
| `FRANKLINOPS_AR_REMINDER_PLACEHOLDER_EMAIL` | (empty) | Skip AR reminder when no email; if set, use as fallback |

---

## 7. AR Reminder — No Placeholder Email

**Before:** Used `customer@invoice.placeholder` when customer email missing.

**After:** Skips reminder with `status: skipped`, `reason: no_customer_email` when no email. Optional `FRANKLINOPS_AR_REMINDER_PLACEHOLDER_EMAIL` for fallback.

---

## What You Still Need (APIs & Subscriptions)

These remain for you to procure and configure:

| Integration | Env Vars | Notes |
|-------------|----------|-------|
| **BID-ZONE native** | `BID_ZONE_API_URL`, `BID_ZONE_API_KEY` | When set, real HTTP calls |
| **Trinity leads** | `TRINITY_API_KEY` | Pull leads into sales_leads |
| **OpenAI** | `OPENAI_API_KEY` | Ops chat, embeddings |
| **Procore** | Procore OAuth | Construction data |
| **QuickBooks** | QB OAuth | Accounting |
| **SAM.gov** | `SAM_GOV_API_KEY` | Bid portal search |
| **OneDrive** | `FRANKLINOPS_ONEDRIVE_*` roots | Document roots |
| **Census / permits / parcel** | Data files | Ingest via Data Fabric API |

---

## Verification

```bash
python -c "
from src.franklinops.schemas import DataFabricIngestIn, DevelopmentPipelineIn
from src.pipeline.land_deal import run_land_deal_pipeline
r = run_land_deal_pipeline({'parcel_id':'p1','acres':10})
assert r.get('ok') and r.get('opportunity')
print('OK')
"
```
