# FranklinOps for Construction

**The operating system for how American construction runs.**

---

## One Sentence

*Your business runs on documents and decisions. FranklinOps runs underneath — so you can see everything, control everything, and prove everything.*

---

## What It Does

| Flow | Purpose |
|------|---------|
| **Pay App Tracker** | Status (submitted/approved/paid), amounts, overdue, lien deadlines |
| **Construction Dashboard** | Project summary: contract value, billed, received, outstanding receivables |
| **Document Ingestion** | Ingest pay apps, change orders, submittals from your folders |
| **Finance** | AP intake, AR reminders, cash flow, Procore sync |
| **Project Controls** | 12 roots: change orders, RFIs, submittals, material delivery, etc. |

---

## The Circle in Construction

| Phase | Construction Example |
|-------|----------------------|
| **Incoming** | Pay apps, change orders, RFIs, submittals, invoices |
| **Outgoing** | Lien waivers, payment requests, approvals, reports |
| **Collection** | Store, index, audit — nothing is lost |
| **Regenerating** | Metrics, backlog, what to chase next |

---

## Works with FranklinOps

- **Procore** — OAuth, projects, sync
- **QuickBooks / Accounting** — Export invoices, import payments
- **OneDrive / Folders** — Document ingestion
- **BID-ZONE** — Bidding portal (ingestion)

---

## Human in the Loop

- **Shadow** — FranklinOps drafts, you approve
- **Assist** — Routine tasks automated, important decisions escalated
- **Autopilot** — Trusted workflows run, sampled for audit

*The only OS that lets you dial autonomy up or down.*

---

## Audit as a Product

Every action is logged. Every decision is traceable. Governance hash proves what governed each decision. Built for compliance from day one.

---

## Quick Start

1. Start FranklinOps: `python -m uvicorn src.franklinops.server:app --port 8844`
2. Open: http://127.0.0.1:8844/ui/boot (OS boot experience)
3. Go to: http://127.0.0.1:8844/ui/construction (Pay apps, dashboard)
4. Configure: Point `FRANKLINOPS_ONEDRIVE_*` at your project folders
