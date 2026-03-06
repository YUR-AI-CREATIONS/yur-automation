# FranklinOps — Full System State (Local)

**Generated:** 2026-03-05  
**Purpose:** Single reference for where everything lives and what's implemented.

---

## Local Storage (Everything Saved Locally)

| What | Location | Format |
|------|----------|--------|
| **Database** | `data/franklinops/ops.db` | SQLite |
| **Audit log** | `data/franklinops/audit.jsonl` | JSONL (append-only) |
| **Data fabric** | `data/fabric/` (raw, clean, features, runs, evidence) | Directories |
| **Governance policies** | `governance-policies.json` | JSON |
| **Deal policy** | `policies/deal_policy.yaml` | YAML |
| **Verification report** | `scripts/verification_report.txt` | Text |

No cloud or external DB required. All state is local.

---

## Key Files & Paths

| Purpose | Path |
|---------|------|
| Server entry | `src/franklinops/server.py` |
| Runtime kernel | `src/core/kernel.py` |
| Event bus | `src/bus/` |
| DAG pipeline | `src/pipeline/land_deal.py` |
| Policy engine | `src/policy/engine.py` |
| Auth / RBAC | `src/core/auth.py` |
| Middleware | `src/franklinops/middleware.py` |
| Settings | `src/franklinops/settings.py` |
| Data fabric | `src/data_fabric/` (ingest, normalize, features) |
| Geo-economic engine | `src/geo_economic/` (corridor scanner) |
| Reality feedback | `src/reality_feedback/` |
| BID-ZONE bridge | `src/integration/bidzone_bridge.py` |
| Docker | `Dockerfile.franklinops`, `docker-compose.franklinops.yml` |

---

## Environment Variables (Optional)

| Var | Purpose | Default |
|-----|---------|---------|
| `FRANKLINOPS_DB_PATH` | SQLite path | `data/franklinops/ops.db` |
| `FRANKLINOPS_AUDIT_JSONL_PATH` | Audit log path | `data/franklinops/audit.jsonl` |
| `FRANKLINOPS_SERVER_PORT` | HTTP port | 8844 |
| `FRANKLINOPS_RBAC_ENABLED` | Enforce role checks | `false` |
| `FRANKLINOPS_API_KEYS` | Comma-separated API keys | (none) |
| `FRANKLINOPS_ENV` | `production` disables bypass | (none) |
| `BID_ZONE_API_URL` | Native BID-ZONE API | (none) |
| `BID_ZONE_API_KEY` | BID-ZONE API key | (none) |

---

## Implemented Fixes (Audit Gaps Closed)

- RBAC enforcement when `FRANKLINOPS_RBAC_ENABLED=true`
- API key validation via `FRANKLINOPS_API_KEYS`
- Dead `create_app` removed
- `GET /ui/land_dev` — JCK Land Dev view
- Bypass flags ignored in production
- Data fabric stub (`ingest_raw`, `normalize_to_clean`, `build_features`)
- BID-ZONE native stub (`bidzone_native_estimate`)
- Unit tests: `tests/test_kernel.py`, `tests/test_auth.py`
- Startup validation, event registry, docs updated

---

## Run Locally

```bash
uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844
```

**Verify:** `python scripts/verify_integration.py` (23 tests)  
**Unit tests:** `python -m pytest tests/test_kernel.py tests/test_auth.py` (8 tests)

---

## UI Routes

- http://127.0.0.1:8844/ui — Hub home
- http://127.0.0.1:8844/ui/development — Pipeline
- http://127.0.0.1:8844/ui/land_dev — JCK Land Dev
- http://127.0.0.1:8844/ui/construction — FranklinOps for Construction
