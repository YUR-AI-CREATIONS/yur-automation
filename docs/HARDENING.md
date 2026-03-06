# FranklinOps / Trinity — Hardening Strategy

**Security and resilience hardening for enterprise dominance.**

## Flow Hardening

Every flow invocation passes through:

| Layer | Purpose |
|-------|---------|
| **Input sanitization** | Strip XSS, injection, dangerous patterns |
| **Payload size** | Max 1MB default (configurable) |
| **Rate limit** | Per flow, per tenant (120/min default) |
| **Circuit breaker** | Fail fast after 5 failures; 60s recovery |
| **Retry** | Exponential backoff (2 retries max) |
| **Timeout** | Max 60s per flow |
| **Audit** | Every invocation logged |

## Document Ingestion

- **Excluded patterns**: `login.txt`, `password.txt`, `credentials`, `.env`, `.env.local`
- **Allowed extensions**: pdf, eml, csv, txt, docx, xlsx
- **No credential files** ingested; use env vars / keyring

## Governance

- **5 scopes**: internal → restricted
- **Evidence gates**: blake_birthmark, intent verification, PQC signature
- **Escalation**: high_error_rate, repeated_failures, cost_overrun

## PQC (Post-Quantum)

- Dilithium3 signatures
- Kyber768 key encapsulation
- Fallback to HMAC when liboqs not installed
