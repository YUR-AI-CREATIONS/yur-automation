# Migrate to F Drive — Done ✅

**Status:** Project copied to `F:\Superagents`. Ready to use.

---

## What Was Done

1. **Full copy** of `D:\Superagents` → `F:\Superagents` (1,489 files)
2. **Config updates** — `settings.py` and `hub_config.py` now auto-detect project root from the file location, so they work from any drive (D, F, etc.)
3. **`.env`** copied to F drive (if it existed)

---

## How to Switch to F Drive

1. **Close Cursor** (or close the current workspace)
2. **Open** `F:\Superagents` in Cursor: **File → Open Folder** → `F:\Superagents`
3. **Recreate venv** (if you use one):
   ```powershell
   cd F:\Superagents
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Run the server** from F:
   ```powershell
   cd F:\Superagents
   python -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8000
   ```

---

## Freeing Space on C/D

After confirming everything works from F:

- You can **delete** `D:\Superagents` to free space
- Or keep it as a backup until you're confident

---

## Optional: Set F as Default

To always work from F, add to your `.env` on F drive:

```
FRANKLINOPS_DATA_DIR=F:/Superagents/data/franklinops
```

(Paths work with forward slashes in env vars.)
