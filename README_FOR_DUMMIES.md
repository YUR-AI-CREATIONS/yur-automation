# FranklinOps — README for Dummies

**In plain English: what this is, and what it can do right now.**

---

## What Is This?

FranklinOps is the **first operating system for business operations**. It's the layer between your people and your work — like Windows runs under your apps.

- Watches your folders for new stuff
- Helps you track leads, invoices, pay applications, and cash flow
- Lets you ask questions about your business in plain English
- Keeps a record of everything it does (audit trail)

**One sentence:** *Documents in. Decisions out. Humans in control.*

**For users:** *Your business runs on documents and decisions. FranklinOps runs underneath — so you can see everything, control everything, and prove everything.*

---

## What Can It Do Today?

Here’s what works **right now** (as of today):

### 1. **Ask Questions About Your Business**
- "Which vendors haven't been paid?"
- "What changed in my documents since last week?"
- "Summarize my project status"

You type a question, it searches your documents and answers.

### 2. **Sales Stuff**
- See leads and opportunities
- Draft outbound emails (you approve before sending)
- Scan folders for new bids/opportunities
- Sync with Trinity (if configured)

### 3. **Finance Stuff**
- Import invoices and track AP (accounts payable)
- Cash flow forecasting from spreadsheets
- AR reminders (who owes you money)
- Import from Procore (construction software)
- Connect to accounting (export/import invoices, payments)

### 4. **Documents**
- Ingest documents from folders you specify
- Search across all your files (vector search)
- Rebuild the index when you add new docs

### 5. **Approvals & Governance**
- Request approval for actions (e.g. send email)
- Approve or deny with one click
- Shadow / Assist / Autopilot modes (you control how much it does automatically)
- Everything is logged (audit trail)

### 6. **FranklinOps for Construction**
- **Pay app tracker** — Status (submitted/approved/paid), amounts, lien deadlines
- **Construction dashboard** — Contract value, billed, received, outstanding
- Procore integration, BID-ZONE, project controls (12 document roots)

### 7. **Plug-In Your Own Stuff (Flows)**
- Echo flow — send data in, get it back (test)
- Reverse flow — flip keys and values (demo)
- NYSE simulation — deterministic market sim (quote, OHLCV, optimize, predict)
- **Or plug any system** that takes input and returns output (webhook or Python)

### 8. **Other**
- Tasks (create, list, update status)
- Onboarding (detect business type, auto-detect folders)
- Proactive support (scan for issues, suggestions)
- Metrics summary
- Multi-tenant (different customers/orgs)
- Fleet agents (dispatch work, route documents)

---

## How Do I Run It?

### Quick Start (3 steps)

1. **Install**
   ```powershell
   pip install -r requirements-minimal.txt
   ```

2. **Start the server**
   ```powershell
   python -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844
   ```

3. **Open in browser**
   - **Boot screen (OS experience):** http://127.0.0.1:8844/ui/boot
   - Main UI: http://127.0.0.1:8844/ui/enhanced
   - **FranklinOps for Construction:** http://127.0.0.1:8844/ui/construction
   - API docs: http://127.0.0.1:8844/docs

### Run Without the Web Server (Kernel Only)

```powershell
# Interactive mode — type flow names and JSON
python scripts/run_kernel.py

# One-shot — run a flow once
python scripts/run_kernel.py echo
echo {"x": 42} | python scripts/run_kernel.py echo -
```

---

## Try These Right Now

### 1. Health Check
```powershell
curl http://127.0.0.1:8844/healthz
```
Should return `{"ok": true}`.

### 2. List Flows
```powershell
curl http://127.0.0.1:8844/api/flows
```
Shows echo, reverse, nyse_sim (and any you plugged in).

### 3. Invoke Echo
```powershell
curl -X POST http://127.0.0.1:8844/api/flows/echo/invoke -H "Content-Type: application/json" -d "{\"hello\": \"world\"}"
```
Returns your input back.

### 4. NYSE Quote
```powershell
curl -X POST http://127.0.0.1:8844/api/flows/nyse_sim/invoke -H "Content-Type: application/json" -d "{\"action\": \"quote\", \"symbols\": [\"AAPL\", \"MSFT\"]}"
```
Returns simulated stock quotes.

### 5. Ask a Question (Ops Chat)
```powershell
curl -X POST http://127.0.0.1:8844/api/ops_chat -H "Content-Type: application/json" -d "{\"question\": \"What documents do we have?\"}"
```
Searches your docs and answers (needs docs ingested first).

### 6. Run Full Pilot
```powershell
python -m src.franklinops.run_pilot
```
Runs a full demo: ingest, sales, finance, GROKSTMATE.

### 7. Verify Everything Works
```powershell
$env:PYTHONIOENCODING = "utf-8"
python scripts/verify_integration.py
```
18 tests. Should all pass.

---

## What’s the “Circle”?

The system is built around four phases that loop:

| Phase | What It Means |
|-------|----------------|
| **Incoming** | Stuff that arrives (docs, leads, invoices) |
| **Outgoing** | Stuff that leaves (emails, reports, approvals) |
| **Collection** | Store, index, audit — nothing is lost |
| **Regenerating** | Metrics, backlog — the system improves itself |

*Incoming → Outgoing → Collection → Regenerating → back to Incoming.*

---

## Do I Need to Configure Anything?

For basic use, no. It runs with defaults.

For real work, set these in `.env`:

```env
# Where your documents live
FRANKLINOPS_ONEDRIVE_PROJECTS_ROOT=C:\Users\You\OneDrive\01PROJECTS
FRANKLINOPS_ONEDRIVE_BIDDING_ROOT=C:\Users\You\OneDrive\02BIDDING

# Optional: better AI answers
OPENAI_API_KEY=sk-your-key
```

---

## Where’s the Fancy Docs?

- **Full README:** [README.md](README.md)
- **Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Flow interface:** [docs/FLOW_INTERFACE.md](docs/FLOW_INTERFACE.md)
- **Verification:** [docs/VERIFICATION.md](docs/VERIFICATION.md)
- **Index of all docs:** [docs/INDEX.md](docs/INDEX.md)

---

## Portable Zip (Run on Another Computer)

**All-in-one bootstrap:** Unzip → double-click `scripts/bootstrap.bat`. Installs Python + Ollama if needed. Runs. Opens browser. One click.

**Download zip:** http://127.0.0.1:8844/ui/download (when server running) or `python scripts/create_portable_zip.py`

---

## TL;DR

| Question | Answer |
|----------|--------|
| What is it? | Business automation hub |
| What does it do? | Documents, sales, finance, approvals, AI chat, plug-in flows |
| How do I run it? | `uvicorn src.franklinops.server:app --port 8844` |
| Where’s the UI? | http://127.0.0.1:8844/ui/enhanced |
| Does it work? | Yes — 18 tests pass |
