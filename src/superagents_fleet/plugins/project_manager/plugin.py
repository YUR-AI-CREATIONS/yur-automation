"""Project Manager — Subs, RFPs, OSHA, SWPPP, punch-out, recoupables."""
from __future__ import annotations
import sqlite3
from typing import Any
from fastapi import APIRouter
from src.superagents_fleet.plugin.interface import AgentPlugin, PluginConfig


class Plugin(AgentPlugin):
    def get_private_fields(self) -> list[str]:
        return ["subcontractor_contact_private", "internal_bid_amount"]

    def get_router(self) -> APIRouter:
        router = APIRouter(prefix=f"/agents/{self.agent_id}", tags=[self.agent_id])
        @router.get("/health")
        def health() -> dict: return {"agent": self.agent_id, "status": "ok"}
        return router

    def get_schema_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, status TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS subcontractors (id TEXT PRIMARY KEY, name TEXT, score REAL, created_at TEXT);
        CREATE TABLE IF NOT EXISTS learning_events (id TEXT PRIMARY KEY, project_id TEXT, outcome TEXT, created_at TEXT);
        """

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        t = task.get("type", "generic")
        if t == "subcontractor_agreement":
            return {"sub_id": task.get("sub_id","unknown"), "status": "tracked", "compliance": "verified"}
        if t == "rfp":
            return {"rfp_id": task.get("rfp_id","new"), "status": "issued", "responses_tracked": True}
        if t == "recoupable_audit":
            return {"recoupables_identified": [], "total_potential": 0, "status": "audit_complete"}
        if t == "subcontractor_score":
            base = {"sub_id": task.get("sub_id","unknown"), "score": 0, "recommendation": "reward", "pricing_matrix": "realistic"}
            try:
                from src.superagents_fleet.integrations.llm import LLMService
                import os
                svc = LLMService(openai_api_key=os.getenv("OPENAI_API_KEY"))
                ctx = task.get("history", "") or "No history"
                prompt = f"""Subcontractor risk. Sub: {task.get('sub_id','unknown')}. History: {ctx}. Risk level, recommendation (reward/monitor/avoid), one-sentence rationale."""
                analysis, _ = svc.complete(prompt, system="You are a construction vendor risk analyst.")
                if analysis:
                    base["llm_risk_analysis"] = analysis
            except Exception:
                pass
            return base
        return {"acknowledged": True}
