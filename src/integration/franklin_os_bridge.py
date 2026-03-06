"""
Franklin OS Bridge — Connects Franklin OS to FranklinOps Hub.

- Status: Check path, env, health
- Data sync: Placeholder for status + data sync from Franklin OS
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional


def get_franklin_os_root() -> Path:
    """Resolve Franklin OS root from env."""
    root = os.getenv("FRANKLINOPS_FRANKLIN_OS_ROOT", "")
    if not root:
        _cursor = os.getenv("FRANKLINOPS_CURSOR_PROJECTS", str(Path.home() / ".cursor" / "projects"))
        root = f"{_cursor}\\d-Franklin-OS-local"
    return Path(root)


def franklin_os_available() -> bool:
    """Check if Franklin OS root exists and is accessible."""
    root = get_franklin_os_root()
    return root.exists() and root.is_dir()


def get_status() -> dict[str, Any]:
    """Get Franklin OS bridge status."""
    root = get_franklin_os_root()
    available = root.exists() and root.is_dir()
    return {
        "available": available,
        "root": str(root),
        "note": "Franklin OS bridge: path check only; data sync to implement" if available else "Franklin OS root not found",
    }


def sync_from_franklin_os(
    db=None,
    audit=None,
    *,
    tenant_id: str = "default",
) -> dict[str, Any]:
    """
    Placeholder for data sync from Franklin OS.
    When Franklin OS API is available, sync projects, leads, or other entities.
    """
    if not franklin_os_available():
        return {"synced": 0, "error": "Franklin OS root not found"}

    try:
        if audit:
            audit.append(
                actor="franklin_os_bridge",
                action="franklin_os_sync_attempted",
                scope="external_low",
                details={"tenant_id": tenant_id},
            )
        return {"synced": 0, "note": "Franklin OS data sync: implement when Franklin OS API is available"}
    except Exception as e:
        return {"synced": 0, "error": str(e)}
