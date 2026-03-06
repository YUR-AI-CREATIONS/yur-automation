#!/usr/bin/env python3
"""
Create FranklinOps-Portable.zip — everything needed to run on another computer.

Usage: python scripts/create_portable_zip.py

Output: FranklinOps-Portable.zip (in project root)
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "FranklinOps-Portable.zip"

# Include these paths (relative to ROOT)
INCLUDE = [
    "src",
    "docs",
    "scripts",  # bootstrap.bat, bootstrap.ps1, Run-FranklinOps.bat
    "tests",
    "policies",
    "governance-policies.json",
    "Dockerfile.franklinops",
    "docker-compose.franklinops.yml",
    "README.md",
    "README_FOR_DUMMIES.md",
    "TROUBLESHOOTING.md",
    "SYSTEM_STATE_LOCAL.md",
    "requirements.txt",
    "requirements-minimal.txt",
    "SECURITY.md",
    "CONTRIBUTING.md",
]
# Add .env.example if present (user copies to .env)
if (ROOT / ".env.example").exists():
    INCLUDE.append(".env.example")

# Data fabric structure (empty dirs need .gitkeep or a file)
if (ROOT / "data").exists():
    INCLUDE.append("data")

# Include GROKSTMATE if it exists (optional add-on)
if (ROOT / "GROKSTMATE").exists():
    INCLUDE.append("GROKSTMATE")

# Exclude patterns (any path segment matching)
EXCLUDE_PATTERNS = {
    "__pycache__",
    ".git",
    ".gitignore",
    ".env",  # Never bundle secrets
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
    "ops.db",
    "ops.db-wal",
    "ops.db-shm",
    "audit.jsonl",
    "*.log",
    "egg-info",  # Build artifacts
    "verification_report.txt",  # Runtime output
}

# File extensions to exclude
EXCLUDE_EXT = {".pyc", ".pyo", ".log", ".db", ".db-wal", ".db-shm"}


def should_exclude(path: Path, base: Path) -> bool:
    rel = path.relative_to(base)
    parts = rel.parts
    for part in parts:
        if part in EXCLUDE_PATTERNS:
            return True
        if "egg-info" in part:
            return True
        if part.startswith(".") and part != ".env.example":
            return True
    if path.suffix in EXCLUDE_EXT:
        return True
    if path.name == ".env":
        return True
    return False


def collect_files() -> list[Path]:
    files: list[Path] = []
    for item in INCLUDE:
        p = ROOT / item
        if not p.exists():
            continue
        if p.is_file():
            if not should_exclude(p, ROOT):
                files.append(p)
        else:
            for fp in p.rglob("*"):
                if fp.is_file() and not should_exclude(fp, ROOT):
                    files.append(fp)
    return files


def write_start_here(zf: zipfile.ZipFile) -> None:
    content = """================================================================================
FRANKLINOPS — RED CARPET EXPERIENCE
================================================================================

Documents in. Decisions out. Humans in control.

ALL-IN-ONE BOOTSTRAP
--------------------

  WINDOWS:  Double-click  scripts\\bootstrap.bat
  MAC/LINUX:  ./scripts/bootstrap.sh

  Installs Python + Ollama + deps if needed. Runs. Opens browser.
  One click. No config. No API key.
  Concierge (🛎️) will guide you through setup.


MANUAL START (3 steps)
----------------------

1. INSTALL PYTHON 3.11+
   https://www.python.org/downloads/
   (Check "Add Python to PATH" on Windows)

2. INSTALL DEPENDENCIES
   pip install -r requirements-minimal.txt

3. RUN
   python -m uvicorn src.franklinops.server:app --host 127.0.0.1 --port 8844

   Open: http://127.0.0.1:8844/ui/boot  or  /ui/enhanced  or  /ui/construction


OPTIONAL: CONFIGURE
-------------------
- Copy .env.example to .env (if it exists)
- Edit .env with folder paths and API keys
- See README_FOR_DUMMIES.md for plain-English guide


VERIFY
------
python scripts/verify_integration.py


NEED HELP?
----------
- TROUBLESHOOTING.md — bootstrap / first-run issues (port 8844, winget, etc.)
- README_FOR_DUMMIES.md — simple overview
- README.md — full documentation
- docs/INDEX.md — all documentation

Built with Cursor — best end-to-end AI pair programmer.

================================================================================
"""
    zf.writestr("START_HERE.txt", content)


def main() -> int:
    files = collect_files()
    print(f"Adding {len(files)} files to {OUTPUT.name}...")

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        write_start_here(zf)
        for fp in sorted(files):
            arcname = fp.relative_to(ROOT)
            zf.write(fp, arcname)
            print(f"  + {arcname}")

    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"\nDone. {OUTPUT} ({size_mb:.1f} MB)")
    print(f"Unzip on another computer and follow START_HERE.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
