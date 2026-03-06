"""
Onboard Concierge — walk you through, set it up, monitor, alert, prompt for approvals.

Omnipresent guide: navigate to any feature, walk-through setup, monitor every component,
alert on issues, prompt for user approvals, keep you up to date on every moving piece.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .audit import AuditLogger
from .opsdb import OpsDB

_LOG = logging.getLogger("concierge")


@dataclass
class FeatureTarget:
    """A navigable feature with URL and walkthrough."""
    id: str
    name: str
    url: str
    description: str
    walkthrough_steps: list[dict[str, Any]] = field(default_factory=list)
    setup_action: Optional[str] = None  # API to call for setup


# Registry of all navigable features
FEATURE_REGISTRY: list[FeatureTarget] = [
    FeatureTarget("boot", "Boot / Status", "/ui/boot", "System status and health"),
    FeatureTarget("enhanced", "Main Dashboard", "/ui/enhanced", "Today queue, approvals, tasks"),
    FeatureTarget("construction", "Construction", "/ui/construction", "Pay apps, lien deadlines, project dashboard",
        walkthrough_steps=[
            {"step": 1, "title": "Connect project folders", "action": "configure_folders", "hint": "Settings → roots"},
            {"step": 2, "title": "Run ingest", "action": "run_ingest", "hint": "Click Run ingest"},
            {"step": 3, "title": "View pay app tracker", "action": "view_pay_app", "hint": "Construction tab"},
        ]),
    FeatureTarget("development", "Development Pipeline", "/ui/development", "Land deal pipeline, Monte Carlo, policy",
        walkthrough_steps=[
            {"step": 1, "title": "Enter parcel (acres, region)", "action": "enter_parcel", "hint": "Use form or API"},
            {"step": 2, "title": "Run pipeline", "action": "run_pipeline", "hint": "Click Run Pipeline"},
            {"step": 3, "title": "View trace and opportunity", "action": "view_trace", "hint": "trace_id link"},
        ],
        setup_action="POST /api/development/pipeline"),
    FeatureTarget("land_dev", "Land Development", "/ui/land_dev", "Land dev intelligence"),
    FeatureTarget("finance", "Finance", "/ui/enhanced", "AP/AR, invoices, cash flow", setup_action="POST /api/finance/ap_intake/run"),
    FeatureTarget("sales", "Sales / Leads", "/ui/enhanced", "Leads, opportunities, outbound"),
    FeatureTarget("approvals", "Approvals", "/ui/enhanced", "Pending approvals"),
    FeatureTarget("ingest", "Document Ingest", "/ui/enhanced", "Run ingest, rebuild index"),
    FeatureTarget("economic_fabric", "Economic Fabric", "/api/economic-fabric/index/default", "Economic index, connectors"),
    FeatureTarget("corridors", "Corridor Scanner", "/ui/development", "Geo-economic corridors"),
    FeatureTarget("ops_chat", "Ask Me Anything", "/ui/enhanced", "Chat with ops assistant"),
    FeatureTarget("ollama", "Ollama (Local AI)", "/ui/enhanced", "Local LLM for sovereign AI — Ops Chat, fleet agents",
        walkthrough_steps=[
            {"step": 1, "title": "Install Ollama", "action": "install_ollama", "hint": "winget install Ollama.Ollama or ollama.com"},
            {"step": 2, "title": "Start Ollama", "action": "start_ollama", "hint": "ollama serve (or runs as service)"},
            {"step": 3, "title": "Pull model", "action": "pull_model", "hint": "ollama pull llama3"},
            {"step": 4, "title": "Verify", "action": "verify", "hint": "Concierge → Components → Ollama should show ok"},
        ],
        setup_action="GET /api/ollama/status"),
]


@dataclass
class ComponentStatus:
    """Status of a component in the stack."""
    id: str
    name: str
    status: str  # ok | warning | error | not_configured
    message: str
    action_url: Optional[str] = None
    last_checked: Optional[str] = None


@dataclass
class ApprovalPrompt:
    """Prompt for user approval."""
    id: str
    workflow: str
    title: str
    summary: str
    action_url: str
    created_at: str


class ConciergeService:
    """
    Onboard Concierge: walk through, set up, monitor, alert, prompt.
    """

    def __init__(self, db: OpsDB, audit: AuditLogger):
        self.db = db
        self.audit = audit
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self.db.conn.execute("""
            CREATE TABLE IF NOT EXISTS concierge_state (
                user_id TEXT PRIMARY KEY DEFAULT 'default',
                current_page TEXT DEFAULT '',
                active_walkthrough TEXT DEFAULT '',
                walkthrough_step INT DEFAULT 0,
                dismissed_prompts TEXT DEFAULT '[]',
                preferences TEXT DEFAULT '{}',
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.db.conn.commit()

    def get_state(self, user_id: str = "default") -> dict[str, Any]:
        row = self.db.conn.execute(
            "SELECT current_page, active_walkthrough, walkthrough_step, dismissed_prompts, preferences, last_seen_at FROM concierge_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            self.db.conn.execute(
                "INSERT INTO concierge_state (user_id) VALUES (?)",
                (user_id,),
            )
            self.db.conn.commit()
            return self.get_state(user_id)
        return {
            "current_page": row[0] or "",
            "active_walkthrough": row[1] or "",
            "walkthrough_step": row[2] or 0,
            "dismissed_prompts": json.loads(row[3] or "[]"),
            "preferences": json.loads(row[4] or "{}"),
            "last_seen_at": row[5],
        }

    def update_state(self, user_id: str = "default", **updates: Any) -> dict[str, Any]:
        state = self.get_state(user_id)
        allowed = {"current_page", "active_walkthrough", "walkthrough_step", "dismissed_prompts", "preferences"}
        for k, v in updates.items():
            if k in allowed:
                state[k] = v
        if "last_seen_at" not in updates:
            state["last_seen_at"] = datetime.now(timezone.utc).isoformat()
        self.db.conn.execute(
            """
            UPDATE concierge_state SET
                current_page = ?, active_walkthrough = ?, walkthrough_step = ?,
                dismissed_prompts = ?, preferences = ?, last_seen_at = ?
            WHERE user_id = ?
            """,
            (
                state.get("current_page", ""),
                state.get("active_walkthrough", ""),
                state.get("walkthrough_step", 0),
                json.dumps(state.get("dismissed_prompts", [])),
                json.dumps(state.get("preferences", {})),
                state.get("last_seen_at", datetime.now(timezone.utc).isoformat()),
                user_id,
            ),
        )
        self.db.conn.commit()
        return self.get_state(user_id)

    def list_features(self) -> list[dict[str, Any]]:
        """All navigable features."""
        return [
            {
                "id": f.id,
                "name": f.name,
                "url": f.url,
                "description": f.description,
                "has_walkthrough": len(f.walkthrough_steps) > 0,
                "setup_action": f.setup_action,
            }
            for f in FEATURE_REGISTRY
        ]

    def navigate_to(self, feature_id: str) -> Optional[dict[str, Any]]:
        """Get navigation target for feature."""
        for f in FEATURE_REGISTRY:
            if f.id == feature_id:
                return {
                    "id": f.id,
                    "name": f.name,
                    "url": f.url,
                    "description": f.description,
                    "walkthrough_available": len(f.walkthrough_steps) > 0,
                }
        return None

    def get_walkthrough(self, feature_id: str) -> Optional[dict[str, Any]]:
        """Get walkthrough steps for feature."""
        for f in FEATURE_REGISTRY:
            if f.id == feature_id:
                return {
                    "feature_id": f.id,
                    "feature_name": f.name,
                    "steps": f.walkthrough_steps,
                    "total_steps": len(f.walkthrough_steps),
                }
        return None

    def get_component_status(self, db: OpsDB) -> list[dict[str, Any]]:
        """Status of every moving piece in the stack."""
        components: list[ComponentStatus] = []
        now = datetime.now(timezone.utc).isoformat()

        # DB
        try:
            db.conn.execute("SELECT 1").fetchone()
            components.append(ComponentStatus("db", "Database", "ok", "Connected", None, now))
        except Exception as e:
            components.append(ComponentStatus("db", "Database", "error", str(e), None, now))

        # Roots configured
        try:
            from .hub_config import get_roots_from_env
            roots = get_roots_from_env()
            roots = {k: v for k, v in roots.items() if v}
            if roots:
                components.append(ComponentStatus("roots", "Folder roots", "ok", f"{len(roots)} configured", "/ui/enhanced", now))
            else:
                components.append(ComponentStatus("roots", "Folder roots", "not_configured", "No roots set", "/ui/enhanced", now))
        except Exception as e:
            components.append(ComponentStatus("roots", "Folder roots", "warning", str(e), None, now))

        # Artifacts
        try:
            row = db.conn.execute("SELECT COUNT(*) FROM artifacts WHERE status = 'ingested'").fetchone()
            count = row[0] if row else 0
            if count > 0:
                components.append(ComponentStatus("artifacts", "Documents", "ok", f"{count} ingested", "/ui/enhanced", now))
            else:
                components.append(ComponentStatus("artifacts", "Documents", "warning", "Run ingest", "/ui/enhanced", now))
        except Exception:
            components.append(ComponentStatus("artifacts", "Documents", "error", "Table missing", None, now))

        # Pending approvals (use app.state.approvals when available)
        try:
            approvals_svc = getattr(self, "_approvals", None)
            if approvals_svc:
                count = len(approvals_svc.list(status="pending", limit=500))
                if count > 0:
                    components.append(ComponentStatus("approvals", "Pending approvals", "warning", f"{count} awaiting", "/ui/enhanced", now))
                else:
                    components.append(ComponentStatus("approvals", "Approvals", "ok", "None pending", "/ui/enhanced", now))
            else:
                components.append(ComponentStatus("approvals", "Approvals", "ok", "Service available", "/ui/enhanced", now))
        except Exception as e:
            components.append(ComponentStatus("approvals", "Approvals", "warning", str(e), None, now))

        # Economic Fabric connectors
        import os
        census = "set" if os.getenv("CENSUS_API_KEY") else "not set"
        components.append(ComponentStatus("economic_census", "Census API", "ok" if census == "set" else "not_configured", census, None, now))

        # Ollama (local LLM) — 100% white-glove AI
        try:
            from .ollama_status import check_ollama_status
            ollama = check_ollama_status()
            msg = ollama.get("message", "")
            action = "/ui/enhanced" if ollama.get("status") != "ok" else None
            comp = ComponentStatus("ollama", "Ollama (AI)", ollama.get("status", "unknown"), msg, action, now)
            components.append(comp)
        except Exception as e:
            components.append(ComponentStatus("ollama", "Ollama (AI)", "error", str(e)[:100], None, now))

        return [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "message": c.message,
                "action_url": c.action_url,
            }
            for c in components
        ]

    def get_approval_prompts(self, db: OpsDB, user_id: str = "default", limit: int = 10, approvals_svc: Any = None) -> list[dict[str, Any]]:
        """Prompts needing user approval. Pass approvals_svc from app.state.approvals."""
        state = self.get_state(user_id)
        dismissed = set(state.get("dismissed_prompts", []))
        prompts = []
        svc = approvals_svc or getattr(self, "_approvals", None)
        if not svc:
            return prompts
        try:
            for a in svc.list(status="pending", limit=limit):
                aid = a.id
                if aid in dismissed:
                    continue
                intent = (a.payload.get("intent") or a.workflow or "action")[:200]
                prompts.append({
                    "id": aid,
                    "workflow": a.workflow,
                    "title": f"Approval needed: {a.workflow}",
                    "summary": intent,
                    "action_url": "/ui/enhanced",
                })
        except Exception as e:
            _LOG.debug("approval prompts: %s", e)
        return prompts

    def dismiss_prompt(self, user_id: str, prompt_id: str) -> dict[str, Any]:
        state = self.get_state(user_id)
        dismissed = list(state.get("dismissed_prompts", []))
        if prompt_id not in dismissed:
            dismissed.append(prompt_id)
        return self.update_state(user_id=user_id, dismissed_prompts=dismissed)

    def get_dashboard(self, db: OpsDB, user_id: str = "default", current_path: Optional[str] = None) -> dict[str, Any]:
        """Full concierge dashboard: features, status, approvals, next step. If current_path matches a feature, include walkthrough."""
        state = self.get_state(user_id)
        components = self.get_component_status(db)
        approval_prompts = self.get_approval_prompts(db, user_id)
        features = self.list_features()

        # Walkthrough for current page
        walkthrough = None
        if current_path:
            path = current_path.split("?")[0].rstrip("/") or "/"
            for f in FEATURE_REGISTRY:
                furl = f.url.rstrip("/") or "/"
                if path == furl or path.endswith("/" + furl.lstrip("/")):
                    if f.walkthrough_steps:
                        step = state.get("walkthrough_step", 0)
                        walkthrough = {
                            "feature_id": f.id,
                            "feature_name": f.name,
                            "steps": f.walkthrough_steps,
                            "current_step": min(step, len(f.walkthrough_steps) - 1) if f.walkthrough_steps else 0,
                            "total_steps": len(f.walkthrough_steps),
                        }
                    break

        # Next step suggestion
        next_step = None
        if approval_prompts:
            next_step = {"type": "approval", "title": "Review pending approvals", "url": "/ui/enhanced", "count": len(approval_prompts)}
        elif walkthrough:
            s = walkthrough["steps"][walkthrough["current_step"]]
            next_step = {"type": "walkthrough", "title": f"Step {walkthrough['current_step']+1}: {s.get('title','')}", "url": path or current_path, "hint": s.get("hint", "")}
        else:
            for c in components:
                if c["status"] == "warning" and "ingest" in c.get("message", "").lower():
                    next_step = {"type": "setup", "title": "Run document ingest", "url": "/ui/enhanced"}
                    break
                if c["status"] == "not_configured" and "roots" in c.get("id", ""):
                    next_step = {"type": "setup", "title": "Configure folder roots", "url": "/ui/enhanced"}
                    break
                if c["status"] in ("not_configured", "warning") and c.get("id") == "ollama":
                    next_step = {"type": "setup", "title": "Enable AI (2 steps)", "url": "/ui/enhanced", "hint": "ollama.com → ollama pull llama3. No API key."}
                    break

        # Ollama setup steps for white-glove when not configured
        ollama_setup_steps: list[str] = []
        for c in components:
            if c.get("id") == "ollama" and c.get("status") != "ok":
                try:
                    from .ollama_status import check_ollama_status
                    ollama = check_ollama_status()
                    ollama_setup_steps = ollama.get("setup_steps", [])
                except Exception:
                    pass
                break

        return {
            "state": state,
            "features": features,
            "components": components,
            "approval_prompts": approval_prompts,
            "next_step": next_step,
            "walkthrough": walkthrough,
            "ollama_setup_steps": ollama_setup_steps,
            "message": "I'm here to walk you through, set it up, and keep you updated. What would you like to do?",
        }
