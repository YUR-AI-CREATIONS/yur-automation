# FranklinOps — Troubleshooting

**Having trouble with the bootstrap or first run?** Here are the most common issues and how to fix them.

---

## Before You Run

### "Another installer is running" / Winget stuck

**Symptom:** Bootstrap hangs or says "Waiting for another installation to complete."

**Fix:**
1. Close any other installers (Windows Update, app store, other software installs).
2. Wait 2–3 minutes.
3. Run `scripts\bootstrap.bat` again.

---

### Port 8844 already in use

**Symptom:** "Address already in use" or "port 8844 is in use."

**Fix:** The bootstrap normally stops the old FranklinOps process. If it doesn’t:
1. Open PowerShell or Command Prompt.
2. Run: `netstat -ano | findstr :8844`
3. Note the PID (last number).
4. Run: `taskkill /PID <number> /F` (replace `<number>` with the PID).
5. Run `scripts\bootstrap.bat` again.

---

### Python not found after install

**Symptom:** "python is not recognized" even after winget installs it.

**Fix:**
1. Close the bootstrap window.
2. Open a **new** Command Prompt or PowerShell (PATH is refreshed).
3. Run `scripts\bootstrap.bat` again.

Or install manually: [python.org/downloads](https://www.python.org/downloads/) — check **"Add Python to PATH"**.

---

### Ollama not found / llama3 not ready

**Symptom:** AI features don’t work; "Ollama not available" or "llama3 not found."

**Fix:**
1. Install Ollama manually: [ollama.ai](https://ollama.ai)
2. Open a new terminal and run: `ollama pull llama3`
3. Wait for the download (~4GB). Then run `scripts\bootstrap.bat` again.

---

### Pip install fails

**Symptom:** Errors during `pip install -r requirements-minimal.txt`.

**Fix:**
1. Ensure Python 3.11+ is installed: `python --version`
2. Upgrade pip: `python -m pip install --upgrade pip`
3. Run manually: `pip install -r requirements-minimal.txt`
4. If it still fails, try: `pip install -r requirements-minimal.txt --no-cache-dir`

---

### Browser doesn’t open

**Symptom:** Bootstrap says "Browser opens in 5s" but nothing happens.

**Fix:** Open manually: [http://127.0.0.1:8844/ui/boot](http://127.0.0.1:8844/ui/boot)

---

### Antivirus or firewall blocking

**Symptom:** Ollama or FranklinOps won’t start; connection refused.

**Fix:** Add exceptions for:
- `ollama.exe` (Ollama)
- `python.exe` (FranklinOps)
- Port 8844 (local only)

---

## Manual Start (if bootstrap keeps failing)

1. **Install Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/)
2. **Install dependencies** — `pip install -r requirements-minimal.txt`
3. **Run** — `python -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844`
4. **Open** — [http://127.0.0.1:8844/ui/boot](http://127.0.0.1:8844/ui/boot)

---

## Still stuck?

- **README_FOR_DUMMIES.md** — Plain-English overview
- **README.md** — Full documentation
- **docs/INDEX.md** — All docs
