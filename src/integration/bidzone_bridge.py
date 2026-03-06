"""
BID-ZONE Bridge — Connects BID-ZONE sales portal to FranklinOps Hub.

- Lead flow: Scan BID_ZONE root, ingest documents, create/update sales leads
- Estimate: Delegate to GROKSTMATE when available
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from .bridge import IntegrationBridge, GROKSTMATE_AVAILABLE


def get_bidzone_root() -> Path:
    """Resolve BID-ZONE root from env."""
    root = os.getenv("FRANKLINOPS_BID_ZONE_ROOT", "")
    if not root:
        _cursor = os.getenv("FRANKLINOPS_CURSOR_PROJECTS", str(Path.home() / ".cursor" / "projects"))
        root = f"{_cursor}\\d-XAI-BID-ZONE"
    return Path(root)


def bidzone_available() -> bool:
    """Check if BID-ZONE root exists and is accessible."""
    root = get_bidzone_root()
    return root.exists() and root.is_dir()


def bidzone_native_estimate(project_spec: dict[str, Any]) -> dict[str, Any]:
    """
    BID-ZONE native API. When BID_ZONE_API_URL is set, calls external API.
    Otherwise returns structured unavailable response.
    """
    api_url = os.getenv("BID_ZONE_API_URL", "").strip()
    api_key = os.getenv("BID_ZONE_API_KEY", "").strip()
    if not api_url:
        return {
            "available": False,
            "source": "bidzone_native",
            "stub": True,
            "note": "Set BID_ZONE_API_URL and BID_ZONE_API_KEY for native integration",
            "project_spec_keys": list(project_spec.keys()) if project_spec else [],
        }
    try:
        import urllib.request
        import json as _json
        endpoint = os.getenv("BID_ZONE_ESTIMATE_ENDPOINT", "").strip() or (api_url.rstrip("/") + "/estimate")
        req = urllib.request.Request(
            endpoint,
            data=_json.dumps(project_spec).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"} if api_key else {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = _json.loads(r.read().decode())
        return {
            "available": True,
            "source": "bidzone_native",
            "stub": False,
            "total_estimate": resp.get("total_estimate") or resp.get("total"),
            "details": resp,
        }
    except Exception as e:
        return {
            "available": False,
            "source": "bidzone_native",
            "stub": False,
            "error": str(e),
            "note": "BID-ZONE API call failed; check BID_ZONE_API_URL and network",
        }


def run_estimate(
    project_spec: dict[str, Any],
    bridge: Optional[IntegrationBridge] = None,
) -> dict[str, Any]:
    """
    Run cost estimate. Tries BID-ZONE native first, then GROKSTMATE when available.
    """
    native = bidzone_native_estimate(project_spec)
    if native.get("available") and not native.get("stub"):
        return native
    if GROKSTMATE_AVAILABLE and bridge:
        try:
            result = bridge.estimate_project(project_spec)
            total = result.get("total_estimate") or result.get("total") or 0
            return {
                "available": True,
                "source": "grokstmate",
                "total_estimate": total,
                "details": result,
            }
        except Exception as e:
            return {
                "available": True,
                "source": "grokstmate",
                "error": str(e),
                "fallback": "BID-ZONE native estimate not wired",
            }
    return {
        "available": False,
        "error": "GROKSTMATE not installed; BID-ZONE native API not wired",
        "action": "pip install -e GROKSTMATE for estimate via bridge",
    }


def sync_leads_from_bidzone(
    db,
    audit,
    *,
    sales_spokes: Optional[Any] = None,
    bidzone_root: Optional[Path] = None,
    tenant_id: str = "default",
) -> dict[str, Any]:
    """
    Ingest BID-ZONE root, then scan for ITB/RFP leads and upsert into sales_leads.
    When sales_spokes is provided, runs full lead capture. Otherwise ingest only.
    """
    root = bidzone_root or get_bidzone_root()
    if not root.exists():
        return {"synced": 0, "error": "BID-ZONE root not found", "root": str(root)}

    try:
        audit.append(
            actor="bidzone_bridge",
            action="bidzone_sync_attempted",
            scope="external_low",
            details={"root": str(root), "tenant_id": tenant_id},
        )
        from src.franklinops.doc_ingestion import ingest_roots
        ingest_result = ingest_roots(db, audit, roots={"bid_zone": str(root)})
        counts = ingest_result.get("counts", {})

        if sales_spokes:
            scan_result = sales_spokes.scan_inbound_itbs(source="bid_zone", limit=500)
            created_leads = scan_result.get("created_leads", 0)
            created_opps = scan_result.get("created_opportunities", 0)
            synced = created_leads + created_opps
            return {
                "synced": synced,
                "root": str(root),
                "ingest": counts,
                "scan": scan_result,
            }
        return {
            "synced": 0,
            "root": str(root),
            "ingest": counts,
            "note": "Pass sales_spokes for lead creation from scan",
        }
    except Exception as e:
        return {"synced": 0, "error": str(e), "root": str(root)}
