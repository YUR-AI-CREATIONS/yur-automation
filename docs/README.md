# YUR Corporate Automation — Documentation

**Start here for marketing, technical, or verification.**

---

## For Marketing & Campaigns

| Document | Use |
|----------|-----|
| **[YUR_CORPORATE_AUTOMATION.md](YUR_CORPORATE_AUTOMATION.md)** | Main marketing narrative. Tagline, circle, proof, construction example. |
| **[CAMPAIGN_COPY.md](CAMPAIGN_COPY.md)** | Ready-to-use copy: taglines, LinkedIn posts, email subjects, pitch bullets. |

---

## For Technical & Architecture

| Document | Use |
|----------|-----|
| **[WIREFRAME.md](WIREFRAME.md)** | Architecture wireframe. Circle, spine mapping, component matrix, API, UI, construction lifecycle. |
| **[TRACKABLE_STRUCTURE.md](TRACKABLE_STRUCTURE.md)** | Folder roots, env vars, agent mapping. |
| **[INTEGRATION_COMPLETE.md](INTEGRATION_COMPLETE.md)** | GROKSTMATE integration. Bridge, governance, endpoints. |

---

## For Proof & Verification

| Document | Use |
|----------|-----|
| **[VERIFICATION.md](VERIFICATION.md)** | Live test results. How to run verification. 9/9 tests. |

```powershell
python scripts/verify_integration.py
```

---

## Quick Links

- **Root README:** [../README.md](../README.md)
- **Verification script:** `scripts/verify_integration.py`
- **Pilot run:** `python -m src.franklinops.run_pilot`
- **Server:** `python -m uvicorn src.franklinops.server:app --port 8844`
