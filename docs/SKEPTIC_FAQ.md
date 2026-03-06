# Skeptic FAQ — Answers to Doubt

**Preemptive responses to common objections.**

---

## "Governance is just config—who enforces it?"

**Answer:** The Autonomy Gate enforces it. Every approval request passes through `AutonomyGate.evaluate()`. If scope is `external_medium` or higher, `auto_execute` is false and human approval is required. The gate is in the execution path—not advisory.

**Verify:** `src/core/autonomy_gate.py` — `evaluate()` is called before any auto-execution. `approvals.py` uses it.

---

## "Audit can be tampered with."

**Answer:** Append-only design. No UPDATE or DELETE on `audit_events` in the codebase. SQLite WAL mode. JSONL is append-only. For stronger guarantees: add Merkle tree or PQC signature per event (roadmap).

**Verify:** `rg "UPDATE audit_events|DELETE FROM audit" src/` — no matches.

---

## "Post-quantum is marketing—you use HMAC fallback."

**Answer:** When liboqs is installed, Dilithium3 is used. HMAC fallback is for environments where PQC libs aren't available; it's logged. The design is PQC-first; fallback is compatibility, not replacement.

**Verify:** `src/core/quantum_royalty.py` — `use_pqc and PQC_AVAILABLE` controls algorithm choice.

---

## "Self-healing—how do I know it works?"

**Answer:** Ouroboros runs health checks every 5 minutes. On failure: retry → restart → rollback → spawn → escalate. Each step is logged. You can run Ouroboros in a test env and kill a pod—it will attempt recovery.

**Verify:** `src/core/ouroboros_spine.py` — healing strategies are implemented. `governance-policies.json` auto_healing.

---

## "50 years is absurd. Systems don't last that long."

**Answer:** The *principles* last 50 years. The implementation will evolve. The Governance Manifest defines principles that do not depend on today's tech. Additive migrations, versioned API, upgrade protocol—the architecture is built for evolution without breaking the chain of trust.

**Verify:** `docs/GOVERNANCE_MANIFEST.md` — Articles I–VIII are technology-agnostic.

---

## "You're not SOC2 certified."

**Answer:** Correct. We are *SOC2-ready*: audit logging, access control, encryption, incident response, change management. Certification requires an audit firm. The system provides the evidence; the audit provides the stamp.

**Verify:** `governance-policies.json` compliance section. `docs/PROOF_OF_EXCELLENCE.md` audit readiness.

---

## "Zero-error is impossible."

**Answer:** Zero *unhandled* errors. Every flow invocation returns a `FlowResult` or a structured dict. Exceptions are caught, logged, and converted to predictable error responses. The caller never sees a raw traceback.

**Verify:** `flow_hardening.py` — `execute_flow_hardened` catches all exceptions, returns `FlowResult`. `nyse_simulation.py` — `process()` has top-level try/except.

---

## "Universal plug-in—any system? Really?"

**Answer:** Any system with a function: input → output. You provide a handler (Python callable or webhook URL). The flow registry invokes it. Rate limit, circuit breaker, sanitization, audit—all applied. The *interface* is universal; the *handler* is whatever you plug in.

**Verify:** `POST /api/flows/plug` with `handler_type: webhook` and a URL. Then `POST /api/flows/{id}/invoke`.

---

## "Why should I believe you?"

**Answer:** Don't believe—verify. The code is in the repo. The verification script runs 14 tests. The Governance Manifest is a document you can hold us to. The Proof of Excellence matrix maps claims to evidence. Run it. Inspect it. The burden of proof is on the system; the evidence is in the repository.
