# Secrets & Credential Policy (FranklinOps / Superagents)

This repo must never contain real credentials (API keys, OAuth client secrets, refresh tokens, passwords, signing keys, private keys, or access tokens).

## Storage rules

- **Preferred**: environment variables set at the OS / container / CI level.
- **Allowed for local development only**: a local `.env` file created from `.env.example` (never committed).
- **Recommended “secret store”**: OS keychain/credential manager (Windows Credential Manager / macOS Keychain / Linux Secret Service). For Python, use `keyring` so tokens (e.g., OAuth refresh tokens) never live in plaintext on disk.

## Access policy

- **Least privilege**: use provider-scoped keys (read-only where possible; separate prod vs dev keys).
- **Separation of duties**: only designated operators can create/rotate production credentials.
- **No sharing**: never paste secrets into chat, tickets, email, docs, or commit history.
- **MFA required** on all third‑party dashboards that issue keys (OpenAI, SendGrid, HubSpot, Procore, accounting, etc.).

## Rotation policy

Rotate secrets:

- **Immediately** if exposure is suspected (accidental commit, screen-share, leaked log).
- **On personnel change** (offboarding, role change).
- **On schedule**: at least every **90 days** for high-impact credentials (email, payments, accounting, OAuth refresh tokens), and **180 days** for lower-impact keys.

Rotation steps (generic):

1. **Issue new credential** in the provider dashboard (or create a new OAuth app secret).
2. **Deploy new credential** to env/secret store (do not put in files).
3. **Validate** in a controlled environment (smoke test the affected workflow).
4. **Revoke old credential** after validation.
5. **Record** the rotation in the audit log/runbook (who/when/what scope changed).

## Incident response (credential leak)

1. **Revoke/rotate immediately** at the provider.
2. **Search for secondary leakage** (logs, email drafts, exports, backups).
3. **Invalidate sessions/tokens** where supported (OAuth refresh tokens, service keys).
4. **Review audit trail** for abnormal activity during the exposure window.

## FranklinOps document ingestion

- **Never ingest credential files**: The doc ingestor excludes files matching `login.txt`, `password.txt`, `credentials.txt`, `PROCORE LOGIN`, `.env`, etc. See `doc_ingestion.EXCLUDED_FILE_PATTERNS`.
- **If you have plaintext credentials in OneDrive** (e.g. `PROCORE LOGIN.txt`): move them to env vars or keyring, then delete the file. Rotate the credential if it may have been ingested before exclusion was added.

## Provider notes (high level)

- **OpenAI**: rotate API key; restrict by project/org; keep separate dev/prod keys.
- **SendGrid**: create scoped API keys (mail send only); rotate and revoke old.
- **HubSpot**: prefer private app tokens with minimal scopes; rotate on leak.
- **OAuth (e.g., Procore)**: treat **client secrets** and **refresh tokens** as high-impact; store refresh tokens in OS secret store (`keyring`) and rotate/re-consent on leak.
- **Databases**: rotate DB user password; prefer separate users per service; enforce TLS where possible.

