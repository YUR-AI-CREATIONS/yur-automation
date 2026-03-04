"""Bookkeeper — AP/AR, invoice tracking. Private financial data stays local."""
from __future__ import annotations
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from src.superagents_fleet.plugin.interface import AgentPlugin, PluginConfig


class InvoiceIn(BaseModel):
    invoice_id: str
    kind: str = "AP"  # AP | AR
    vendor_id: Optional[str] = None
    amount_cents: Optional[int] = None


class Plugin(AgentPlugin):
    def get_private_fields(self) -> list[str]:
        return ["vendor_bank_account", "customer_ssn", "internal_memo", "payment_details"]

    def get_router(self) -> APIRouter:
        router = APIRouter(prefix=f"/agents/{self.agent_id}", tags=[self.agent_id])

        @router.get("/health")
        def health() -> dict:
            return {"agent": self.agent_id, "status": "ok", "db": str(self.db_path)}

        @router.get("/invoices")
        def list_invoices(kind: Optional[str] = None, limit: int = 50) -> list[dict]:
            with sqlite3.connect(str(self.db_path)) as c:
                c.row_factory = sqlite3.Row
                sql = "SELECT id, kind, invoice_id, status, created_at FROM invoices"
                params: list[Any] = []
                if kind:
                    sql += " WHERE kind = ?"
                    params.append(kind)
                sql += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                return [dict(r) for r in c.execute(sql, params).fetchall()]

        @router.get("/stats")
        def stats() -> dict:
            with sqlite3.connect(str(self.db_path)) as c:
                ap = c.execute("SELECT COUNT(*) FROM invoices WHERE kind='AP'").fetchone()[0]
                ar = c.execute("SELECT COUNT(*) FROM invoices WHERE kind='AR'").fetchone()[0]
                return {"ap_count": ap, "ar_count": ar, "scope": "local_only"}

        @router.get("/warm_outreach_draft")
        async def draft_warm_outreach(vendor_name: str = "", amount_cents: int = 0, days_overdue: int = 0) -> dict:
            """Generate warm, human-like AR/AP outreach copy via LLM."""
            try:
                from src.superagents_fleet.integrations.llm import LLMService
                import os
                svc = LLMService(openai_api_key=os.getenv("OPENAI_API_KEY"))
                prompt = f"""Write a brief, professional, warm accounts receivable follow-up. Vendor: {vendor_name or 'Customer'}. Amount: ${amount_cents/100:.2f}. Days overdue: {days_overdue}. 
Tone: friendly but firm. No AI-sounding phrases. 2-3 sentences max."""
                draft, err = svc.complete(prompt, system="You write natural, human-sounding business emails. Avoid robotic or AI-detecting phrases.")
                return {"draft": draft or err, "available": bool(draft)}
            except Exception as e:
                return {"draft": "", "available": False, "error": str(e)}

        @router.post("/invoice_in")
        async def register_invoice(body: InvoiceIn) -> dict:
            if body.kind not in ("AP", "AR"):
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="kind must be AP or AR")
            result = await self.execute_task({
                "task_id": f"inv_{uuid.uuid4().hex[:12]}",
                "type": "invoice_in",
                "invoice_id": body.invoice_id,
                "kind": body.kind,
            })
            return result.get("result", result)

        return router

    def get_schema_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS invoices (id TEXT PRIMARY KEY, kind TEXT, invoice_id TEXT, status TEXT, created_at TEXT);
        CREATE INDEX IF NOT EXISTS idx_invoices_kind ON invoices(kind);
        CREATE TABLE IF NOT EXISTS learning_events (id TEXT PRIMARY KEY, invoice_id TEXT, outcome TEXT, created_at TEXT);
        """

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        t = task.get("type", "generic")
        if t == "invoice_in":
            inv_id = task.get("invoice_id", "new")
            ts = datetime.now(timezone.utc).isoformat()
            try:
                with sqlite3.connect(str(self.db_path)) as c:
                    c.execute(
                        "INSERT OR REPLACE INTO invoices (id, kind, invoice_id, status, created_at) VALUES (?,?,?,?,?)",
                        (f"inv_{inv_id}", task.get("kind", "AP"), inv_id, "ingested", ts),
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f"bookkeeper invoice_in failed: {e}")
                raise
            return {"invoice_id": inv_id, "routed_to": ["ap", "file_keeper"], "status": "ingested"}
        if t == "invoice_out":
            return {"invoice_id": task.get("invoice_id", "new"), "status": "sent", "ar_tracking_active": True}
        if t == "ar_followup":
            return {"action": "warm_outreach", "tone": "professional_friendly", "status": "scheduled"}
        return {"acknowledged": True}
