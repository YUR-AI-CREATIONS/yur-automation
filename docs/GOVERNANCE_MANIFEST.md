# Governance Manifest — 50 Years of Operating Systems

**Version 1.0 · FranklinOps / Trinity Spine · 2026**

This document defines the immutable principles that govern this system for the next 50 years. Principles may be extended; they shall not be contradicted.

---

## Article I: Human Sovereignty

**Principle:** Humans retain final authority. No autonomous system may override human decision.

**Evidence:**
- `restricted` scope: manual-only, MFA, security review
- `external_high`: 24h approval, MFA required
- Autonomy modes: shadow → assist → autopilot (human controls escalation)

**Verification:** `GET /api/autonomy` — all workflows show mode; restricted always requires human.

---

## Article II: Evidence Before Execution

**Principle:** Every governed action requires evidence (birthmark, intent, signature) before execution.

**Evidence:**
- `governance-policies.json` → `evidence_requirements.blake_birthmark`, `intent_verification`, `pqc_signature`
- Autonomy Gate checks evidence before auto-execute
- Approvals store `evidence_json`

**Verification:** Approval records include evidence; gate rejects without it.

---

## Article III: Append-Only Audit

**Principle:** Audit trail is append-only. No deletion. Retention configurable by jurisdiction.

**Evidence:**
- `audit_events` table: INSERT only (no UPDATE/DELETE in code)
- JSONL append-only log
- `retention_days` per tenant (365 default, 7 years for financial)

**Verification:** No audit delete/update code paths. Schema enforces.

---

## Article IV: Post-Quantum by Default

**Principle:** Cryptographic signatures resist quantum attack. Dilithium3 + Kyber768.

**Evidence:**
- `governance-policies.json` → `pqc_config.algorithm: dilithium3`
- Quantum Royalty module signs missions
- Fallback to HMAC only when PQC unavailable (logged)

**Verification:** `src/core/quantum_royalty.py` — PQC used when liboqs present.

---

## Article V: Self-Healing Without Silent Failure

**Principle:** Systems heal themselves. Failures escalate; nothing fails silently.

**Evidence:**
- Ouroboros: retry → restart → rollback → spawn → escalate
- Circuit breaker in flows: 5 failures → 60s cooldown → escalate
- Escalation rules: high_error_rate, repeated_failures, cost_overrun

**Verification:** `governance-policies.json` → `auto_healing`, `escalation_rules`.

---

## Article VI: Zero-Error Handling

**Principle:** Every code path returns a predictable structure. No unhandled exceptions to caller.

**Evidence:**
- Flow hardening: sanitize, validate, catch, return FlowResult
- NYSE simulation: `process()` never raises; always returns dict
- Audit append: try/except with fallback

**Verification:** Flow handlers return dict; no bare `raise` to API boundary.

---

## Article VII: Upgrade Without Breaking

**Principle:** Schema and API evolve via additive migrations. Backward compatibility preserved.

**Evidence:**
- Migrations: ALTER ADD COLUMN (never DROP without deprecation)
- API versioning: /api/v1/* coexists with /api/*
- Flow registry: plug/unplug without restart

**Verification:** `migrations.py` — no destructive migrations. Deprecation headers.

---

## Article VIII: Open Provenance

**Principle:** Governance policies are versioned and hashable. Anyone can verify what governed a decision.

**Evidence:**
- `governance-policies.json` version field
- Audit events reference scope, entity, details
- `GET /api/config` exposes governance scope

**Verification:** `GET /api/governance/hash` returns version + SHA-256. Startup audit includes `governance_hash`.

---

## Amendment Protocol

To amend this manifest:
1. Propose change with rationale
2. Human approval (restricted scope)
3. Version increment
4. Audit log: `governance_manifest_amended`
5. No amendment may contradict Articles I–VIII

---

**Signed:** FranklinOps / Trinity Spine  
**Effective:** 2026  
**Horizon:** 2076
