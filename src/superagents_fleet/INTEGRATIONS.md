# Fleet Integrations

## Data Sources

### Bid Portals — SAM.gov
- **Adapter**: `SamGovAdapter`
- **Env**: `SAM_GOV_API_KEY` (free from SAM.gov account)
- **API**: https://api.sam.gov/opportunities/v2/search
- **Usage**: `POST /api/fleet/agents/bid_scraping/scrape_sam_gov?naics=&state=&limit=50`

### Procore Invoices
- **Bridge**: `ProcoreInvoiceBridge`
- **Flow**: Artifact (CSV) → FranklinOps import → OpsDB invoices
- **Usage**: `POST /api/fleet/integrations/procore/import` with `{"artifact_id": "..."}`
- **Requires**: Procore OAuth connected, CSV export uploaded as artifact

### OneDrive / Document Ingestion
- **Bridge**: `OneDriveDocBridge`
- **Flow**: Uses `hub_config` roots (ONEDRIVE_*, PC_*) → `ingest_roots`
- **Usage**: `POST /api/fleet/integrations/onedrive/ingest`
- **Requires**: `FRANKLINOPS_ONEDRIVE_*` or `FRANKLINOPS_PC_*` paths in .env

## LLM (OpenAI / Ollama)

- **Service**: `LLMService` — OpenAI primary, Ollama fallback
- **Env**: `OPENAI_API_KEY`, `FRANKLINOPS_OPENAI_MODEL`, `FRANKLINOPS_OLLAMA_*`

### Where LLM is used
- **Land Feasibility**: `_run_feasibility_study`, `_run_best_use_analysis` — adds `llm_analysis`, `llm_recommendation`
- **Bookkeeper**: `GET /warm_outreach_draft` — warm AR/AP copy
- **Project Manager**: `subcontractor_score` task — adds `llm_risk_analysis`
