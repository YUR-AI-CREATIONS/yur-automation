# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability:

1. **Do not** open a public GitHub issue.
2. Email security concerns to the maintainers (see repository contacts).
3. Include: description, steps to reproduce, impact assessment.
4. We aim to respond within 72 hours and provide a fix timeline.

## Security Practices

- **Secrets**: Never commit credentials. Use env vars, keyring, or secret managers. See [SECURITY_SECRETS_POLICY.md](SECURITY_SECRETS_POLICY.md).
- **Penetration testing**: Annual pentest recommended for enterprise deployments.
- **Vulnerability disclosure**: We track CVEs and apply patches promptly.
- **Post-quantum crypto**: Trinity uses Dilithium3 + Kyber768 for mission signatures.

## Compliance

- SOC2, PCI-DSS, GDPR: governance policies support evidence collection.
- HIPAA: Enable `hipaa_enabled` per tenant; BAA required for PHI.
- Audit trail: Append-only, configurable retention (365 days default, 7 years for financial).
