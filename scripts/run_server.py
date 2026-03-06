#!/usr/bin/env python3
"""
FranklinOps server launcher — used by packaged .exe and direct runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.franklinops.server:app",
        host="127.0.0.1",
        port=8844,
        reload=False,
    )
