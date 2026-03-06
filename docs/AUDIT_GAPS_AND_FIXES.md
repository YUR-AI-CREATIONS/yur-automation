# FranklinOps System Audit — Gaps & Recommended Fixes

**Audit Date:** 2026-03-05  
**Scope:** Highest-level system audit  
**Verification:** 23/23 tests pass (scripts/verify_integration.py)

---

## Executive Summary

FranklinOps has a solid core: kernel, flows, hardening, audit, and development pipeline are implemented and aligned with the architecture. The main gaps are **security (RBAC not enforced)**, **documentation drift**, **dead/unused code**, and **incomplete integrations**.

---

## 1. Architecture Status

| Layer | Status | Location |
|-------|--------|----------|
| **Event Bus** | Partial — In-memory works; NATS optional, not wired | `src/bus/` |
| **Graph Engine (DAG)** | Done | `src/orchestrator/dag.py`, `src/pipeline/land_deal.py` |
| **Simulation** | Done | `src/simulation/monte_carlo.py` |
| **Policy Engine** | Done | `src/policy/engine.py`, `policies/deal_policy.yaml` |
| **Data Fabric** | Stub — Directory layout only | `data/fabric/` |
| **FranklinOps Integration** | Done | `src/franklinops/server.py`, `src/integration/` |

---

## 2. Gaps by Severity

### CRITICAL

| # | Gap | Description | Recommended Fix | Location |
|---|-----|-------------|----------------|----------|
| 1 | **RBAC not enforced** | All API routes are unprotected. `TenantContextMiddleware` sets user context but never checks `FRANKLINOPS_RBAC_ENABLED` or role against route requirements. | Add middleware or dependency that checks `FRANKLINOPS_RBAC_ENABLED` and `_path_prefix_match`; return 403 when role insufficient. | `src/franklinops/middleware.py`, `src/core/auth.py` |
| 2 | **Auth trust model** | `X-Role` header is user-controlled; no JWT/OIDC/API-key validation before trusting role. | Add JWT/OIDC validation or API key validation before trusting `X-Role`. | `src/core/auth.py`, `resolve_user_from_request` |
| 3 | **Duplicate `create_app`** | Two `def create_app()` in server.py (lines 174 and 879). Second overwrites first; first is dead code (~400 lines). | Remove minimal `create_app` (lines 174–577) or expose via separate entry point (e.g. `--minimal` flag). | `src/franklinops/server.py` |

### HIGH

| # | Gap | Description | Recommended Fix | Location |
|---|-----|-------------|----------------|----------|
| 4 | **PQC vs HMAC mismatch** | Docs claim PQC when liboqs present; AutonomyGate uses HMAC-SHA256 only. | Use `quantum_royalty` in AutonomyGate when liboqs available, or update docs to state HMAC fallback. | `src/core/autonomy_gate.py` `_verify_evidence` |
| 5 | **Data fabric empty** | Only directory structure (raw/, clean/, features/, runs/, evidence/); no ingestion or wiring. | Implement ingestion into raw/clean/features, or document as future work in `data/fabric/README.md`. | `data/fabric/` |
| 6 | **BID-ZONE native API** | No real BID-ZONE integration; bridge delegates to GROKSTMATE when available. | Implement native BID-ZONE API or document as out-of-scope. | `src/integration/bidzone_bridge.py` |
| 7 | **`/ui/land_dev` missing** | WIREFRAME marks GAP; JCK Land Dev view referenced in hub_config but no route. | Add `GET /ui/land_dev` for JCK Land Dev view. | `src/franklinops/server.py` |
| 8 | **Evidence bypass flags** | `ALLOW_UNVERIFIED_MISSIONS`, `SKIP_PQC_VERIFICATION` weaken security. | Remove or restrict to non-production; fail closed in prod. | `src/core/autonomy_gate.py` |

### MEDIUM

| # | Gap | Description | Recommended Fix | Location |
|---|-----|-------------|----------------|----------|
| 9 | **PROOF_OF_EXCELLENCE outdated** | May claim "14 tests"; actual count is 23. | Update to "23 tests" and sync with verify_integration.py. | `docs/PROOF_OF_EXCELLENCE.md` |
| 10 | **DEPLOYMENT_CHECKLIST mismatch** | Targets Trinity; references endpoints FranklinOps does not expose (e.g. `/pqc/*`, Trinity health). | Add FranklinOps-specific checklist or split docs. | `DEPLOYMENT_CHECKLIST.md` |
| 11 | **NATS not wired** | `nats_client.py` exists but unused; `nats-py` not in requirements. | Wire NATS as optional bus backend when configured, or remove. | `src/bus/nats_client.py` |
| 12 | **Event type registry** | Docs mention "5 core event types"; no explicit registry in bus. | Add registry in `src/bus/` or document current behavior. | `src/bus/` |
| 13 | **No unit tests** | Only `verify_integration.py`; no pytest unit tests. | Add pytest unit tests for kernel, flows, auth, policy. | `tests/` |
| 14 | **Env validation** | No startup check for required env vars (e.g. DB path). | Validate critical env at boot; fail fast with clear message. | `src/franklinops/settings.py` |

### LOW

| # | Gap | Description | Recommended Fix | Location |
|---|-----|-------------|----------------|----------|
| 15 | **Rust kernel claim** | FRANKLIN_DEVELOPMENT_INTELLIGENCE mentions Rust Sovereign Runtime. | Clarify as future target; current kernel is Python. | `docs/FRANKLIN_DEVELOPMENT_INTELLIGENCE.md` |
| 16 | **Unused ROUTE_ROLES** | `ROUTE_ROLES` and `_path_prefix_match` defined but never used. | Use in RBAC middleware or remove. | `src/core/auth.py` |
| 17 | **requirements.txt bloat** | Supabase, Stripe, Redis in requirements but not used by FranklinOps core. | Split into `requirements-minimal.txt` and `requirements-full.txt`. | `requirements.txt` |
| 18 | **Structured logging** | Plain `logging`; no JSON/structured logs for observability. | Add structured logging (e.g. structlog) for production. | `src/` |

---

## 3. Documentation vs Reality

| Doc | Claim | Reality |
|-----|-------|---------|
| PROOF_OF_EXCELLENCE | "14 tests" | 23 tests |
| GOVERNANCE_MANIFEST | "PQC when liboqs present" | AutonomyGate uses HMAC only |
| FRANKLIN_DEVELOPMENT_INTELLIGENCE | "Rust Sovereign Runtime" | Python kernel only |
| 6_LAYERS_ARCHITECTURE | "5 core event types" | No explicit registry |
| WIREFRAME | `GET /ui/land_dev` GAP | Still missing |
| ARCHITECTURE | "Auth / RBAC: src/core/auth.py" | RBAC defined but not enforced |
| DEPLOYMENT_CHECKLIST | Trinity endpoints | FranklinOps has no `/pqc/*` |

---

## 4. Security Summary

| Area | Status |
|------|--------|
| RBAC enforcement | Not enforced |
| Role resolution | Trust-based (X-Role header) |
| API key validation | Stub only |
| Route protection | None — all `/api/*` open |
| Audit append-only | Yes |
| Governance hash | Yes |
| Flow hardening | Yes (sanitize, rate limit, circuit breaker, retry) |

---

## 5. Recommended Fix Order

1. **Critical:** Enforce RBAC (Gap 1), fix auth trust (Gap 2), remove dead `create_app` (Gap 3)
2. **High:** Add `/ui/land_dev` (Gap 7), restrict bypass flags (Gap 8), align PQC docs (Gap 4)
3. **Medium:** Update PROOF_OF_EXCELLENCE (Gap 9), add env validation (Gap 14), add unit tests (Gap 13)
4. **Low:** Clarify Rust claim (Gap 15), split requirements (Gap 17)

---

## 7. Implemented Fixes (2026-03-05)

| Gap | Fix Applied |
|-----|-------------|
| 1 | RBAC enforced when `FRANKLINOPS_RBAC_ENABLED=true`; middleware checks `_path_prefix_match` |
| 2 | API key validation stub: `validate_api_key()`, `FRANKLINOPS_API_KEYS` env |
| 3 | Removed dead `create_app` (~400 lines); single app definition |
| 7 | Added `GET /ui/land_dev` — JCK Land Dev view |
| 8 | Bypass flags ignored when `FRANKLINOPS_ENV=production` |
| 9 | PROOF_OF_EXCELLENCE updated to 23 tests |
| 12 | `EVENT_TYPES` exported from `src/bus` |
| 13 | Unit tests: `tests/test_kernel.py`, `tests/test_auth.py` (8 tests) |
| 14 | `validate_startup()` in settings; called at hub startup |
| 15 | FRANKLIN_DEVELOPMENT_INTELLIGENCE: "Python today, Rust target (future)" |
| 5 | Data fabric stub: `src/data_fabric/` with `ingest_raw`, `normalize_to_clean`, `build_features` |
| 6 | BID-ZONE native stub: `bidzone_native_estimate()`, `BID_ZONE_API_URL` env |
| 10 | FranklinOps Quick Start section in DEPLOYMENT_CHECKLIST |

---

## 6. What Works Well

- Kernel lifecycle (boot, invoke, shutdown)
- Flow hardening (sanitize, rate limit, circuit breaker, retry)
- Audit append-only for `audit_events`
- Governance hash via `compute_governance_hash()`
- Development pipeline (parcel → zoning → cost → sim → policy → opportunity)
- trace_id end-to-end in pipeline and causality replay
- 23/23 verification tests pass
