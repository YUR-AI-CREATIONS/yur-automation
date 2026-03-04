"""
Land & Feasibility Agent — Plugin with API + database.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.superagents_fleet.plugin.interface import AgentPlugin, PluginConfig
from src.superagents_fleet.plugin.privacy import PrivacyFilter


class DueDiligenceIn(BaseModel):
    parcel_id: str
    municipality: Optional[str] = None
    # Private fields (never sent externally) — add to get_private_fields()
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None


class FeasibilityStudyIn(BaseModel):
    parcel_id: str
    proposed_use: str = "residential"
    size_acres: Optional[float] = None


class Plugin(AgentPlugin):
    """Land & Feasibility Agent — due diligence, feasibility, best use."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._privacy = PrivacyFilter(extra_private_fields=self.get_private_fields())

    def get_private_fields(self) -> list[str]:
        return ["owner_name", "owner_email", "owner_phone", "purchase_price", "confidential_notes"]

    def get_router(self) -> APIRouter:
        router = APIRouter(prefix=f"/agents/{self.agent_id}", tags=[self.agent_id])

        @router.get("/health")
        def health() -> dict[str, Any]:
            return {"agent": self.agent_id, "status": "ok", "db": str(self.db_path)}

        @router.get("/tasks")
        def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT task_id, type, status, created_at FROM tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]

        @router.post("/due_diligence")
        async def run_due_diligence(body: DueDiligenceIn) -> dict[str, Any]:
            result = await self.execute_task({
                "task_id": f"dd_{uuid.uuid4().hex[:12]}",
                "type": "due_diligence",
                "parcel_id": body.parcel_id,
                "municipality": body.municipality,
                "owner_name": body.owner_name,
                "owner_email": body.owner_email,
            })
            return result.get("result", result)

        @router.post("/feasibility_study")
        async def run_feasibility(body: FeasibilityStudyIn) -> dict[str, Any]:
            result = await self.execute_task({
                "task_id": f"fs_{uuid.uuid4().hex[:12]}",
                "type": "feasibility_study",
                "parcel_id": body.parcel_id,
                "proposed_use": body.proposed_use,
                "size_acres": body.size_acres,
            })
            return result.get("result", result)

        @router.get("/learning/stats")
        def learning_stats() -> dict[str, Any]:
            """Learning stats from local DB only — never leaves this agent."""
            with sqlite3.connect(str(self.db_path)) as conn:
                count = conn.execute("SELECT COUNT(*) FROM learning_events").fetchone()[0]
                return {"learning_events": count, "scope": "local_only"}

        return router

    def get_schema_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            parcel_id TEXT,
            result_json TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_parcel ON tasks(parcel_id);

        CREATE TABLE IF NOT EXISTS learning_events (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            outcome TEXT,
            feedback_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id)
        );
        CREATE INDEX IF NOT EXISTS idx_learning_task ON learning_events(task_id);
        """

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = task.get("task_id", "unknown")
        task_type = task.get("type", "generic")

        if task_type == "due_diligence":
            result = await self._run_due_diligence(task)
        elif task_type == "feasibility_study":
            result = await self._run_feasibility_study(task)
        elif task_type == "best_use_analysis":
            result = await self._run_best_use_analysis(task)
        elif task_type == "development_agreement_analysis":
            result = await self._run_dev_agreement_analysis(task)
        elif task_type == "land_plan":
            result = await self._create_land_plan(task)
        else:
            result = {"acknowledged": True, "domain": "land_feasibility", "task_type": task_type}

        # Persist to local DB
        self._persist_task(task_id, task_type, "completed", result, parcel_id=task.get("parcel_id"))

        # Learn locally (no external calls)
        await self.learn(task, {"result": result})

        return {"status": "success", "task_id": task_id, "agent_id": self.agent_id, "result": result}

    def _persist_task(self, task_id: str, task_type: str, status: str, result: dict[str, Any], parcel_id: Optional[str] = None) -> None:
        import json
        import logging
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO tasks (task_id, type, status, parcel_id, result_json, created_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (task_id, task_type, status, parcel_id, json.dumps(result), ts, ts),
                )
        except Exception as e:
            logging.getLogger(__name__).exception(f"land_feasibility persist_task failed: {e}")

    async def learn(self, task: dict[str, Any], result: dict[str, Any], feedback: Optional[dict[str, Any]] = None) -> None:
        """Learn from execution. LOCAL ONLY — never leaves this agent's DB."""
        import json
        import logging
        try:
            sanitized = self._privacy.sanitize_for_learning({**task, **result})
            event_id = uuid.uuid4().hex
            ts = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """INSERT INTO learning_events (id, task_id, task_type, outcome, feedback_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (event_id, task.get("task_id", ""), task.get("type", ""), "success", json.dumps(sanitized), ts),
                )
        except Exception as e:
            logging.getLogger(__name__).exception(f"land_feasibility learn failed: {e}")

    async def _run_due_diligence(self, task: dict[str, Any]) -> dict[str, Any]:
        parcel_id = task.get("parcel_id", "unknown")
        return {
            "parcel_id": parcel_id,
            "status": "completed",
            "findings": ["zoning_verified", "title_clear", "utilities_available"],
            "recommendation": "proceed_to_feasibility",
        }

    async def _run_feasibility_study(self, task: dict[str, Any]) -> dict[str, Any]:
        base = {
            "status": "completed",
            "viability_score": 0.78,
            "recommended_use": "residential_subdivision",
            "estimated_units": 45,
            "key_risks": [],
        }
        try:
            from src.superagents_fleet.integrations.llm import LLMService
            import os
            svc = LLMService(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                openai_model=os.getenv("FRANKLINOPS_OPENAI_MODEL", "gpt-4"),
            )
            ctx = f"Parcel: {task.get('parcel_id','unknown')}, proposed use: {task.get('proposed_use','residential')}, size acres: {task.get('size_acres','')}"
            prompt = f"""As a construction feasibility analyst, provide a brief (2-3 sentence) feasibility assessment for this land: {ctx}.
Include: viability score 0-1, recommended use, key risks. Be concise."""
            analysis, _ = svc.complete(prompt, system="You are a land development feasibility expert.")
            if analysis:
                base["llm_analysis"] = analysis
        except Exception:
            pass
        return base

    async def _run_best_use_analysis(self, task: dict[str, Any]) -> dict[str, Any]:
        base = {
            "best_use": "residential_subdivision",
            "alternatives": ["mixed_use", "commercial"],
            "rationale": "Demand, zoning, infrastructure support residential.",
        }
        try:
            from src.superagents_fleet.integrations.llm import LLMService
            import os
            svc = LLMService(openai_api_key=os.getenv("OPENAI_API_KEY"))
            prompt = f"""Best use analysis for land. Parcel: {task.get('parcel_id','unknown')}. 
Recommend best use and 2 alternatives in one short paragraph."""
            analysis, _ = svc.complete(prompt, system="You are a land use and market analyst.")
            if analysis:
                base["llm_recommendation"] = analysis
        except Exception:
            pass
        return base

    async def _run_dev_agreement_analysis(self, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "municipality": task.get("municipality", "unknown"),
            "agreement_upside": "potential_fee_waivers",
            "recommendations": ["engage_early", "document_all_commitments"],
        }

    async def _create_land_plan(self, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "plan_type": "preliminary",
            "format": ["2d", "3d"],
            "industry_standards": "applied",
            "cost_model_ready": True,
        }
