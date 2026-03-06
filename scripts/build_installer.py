#!/usr/bin/env python3
"""
Build FranklinOps installer — PyInstaller .exe or run create_portable_zip.

Usage:
  python scripts/build_installer.py          # Creates FranklinOps-Portable.zip
  python scripts/build_installer.py --exe    # Builds .exe with PyInstaller (requires: pip install pyinstaller)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_portable() -> int:
    """Create FranklinOps-Portable.zip."""
    script = ROOT / "scripts" / "create_portable_zip.py"
    r = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
    return r.returncode


def build_exe() -> int:
    """Build standalone .exe with PyInstaller."""
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Install with: pip install pyinstaller")
        return 1
    spec = ROOT / "FranklinOps.spec"
    if not spec.exists():
        print(f"Spec file not found: {spec}")
        return 1
    r = subprocess.run([sys.executable, "-m", "PyInstaller", str(spec), "--clean"], cwd=str(ROOT))
    if r.returncode == 0:
        out = ROOT / "dist" / "FranklinOps"
        print(f"\nDone. Executable: {out}")
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Build FranklinOps installer")
    ap.add_argument("--exe", action="store_true", help="Build .exe with PyInstaller")
    args = ap.parse_args()
    if args.exe:
        return build_exe()
    return build_portable()


if __name__ == "__main__":
    raise SystemExit(main())
