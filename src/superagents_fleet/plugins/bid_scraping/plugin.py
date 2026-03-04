"""Bid Scraping Agent — API + DB. Connects to SAM.gov and other bid portals."""
from __future__ import annotations
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter
from src.superagents_fleet.plugin.interface import AgentPlugin, PluginConfig
from src.superagents_fleet.integrations.bid_portals import SamGovAdapter


class Plugin(AgentPlugin):
    def get_private_fields(self) -> list[str]:
        return ["bidder_contact", "internal_notes", "pricing_confidential"]

    def get_router(self) -> APIRouter:
        router = APIRouter(prefix=f"/agents/{self.agent_id}", tags=[self.agent_id])

        @router.get("/health")
        def health() -> dict:
            return {"agent": self.agent_id, "status": "ok", "db": str(self.db_path)}

        @router.get("/bids")
        def list_bids(limit: int = 50) -> list[dict]:
            with sqlite3.connect(str(self.db_path)) as c:
                c.row_factory = sqlite3.Row
                return [dict(r) for r in c.execute(
                    "SELECT bid_id, event_type, amount_cents, awarded, created_at FROM bids ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()]

        @router.get("/historical_pricing")
        def historical() -> list:
            return self._get_historical()

        @router.get("/stats")
        def stats() -> dict:
            with sqlite3.connect(str(self.db_path)) as c:
                total = c.execute("SELECT COUNT(*) FROM bids").fetchone()[0]
                awarded = c.execute("SELECT COUNT(*) FROM bids WHERE awarded=1").fetchone()[0]
                return {"total_bids": total, "awarded": awarded, "scope": "local_only"}

        @router.post("/scrape_sam_gov")
        async def scrape_sam_gov(naics: str = "", state: str = "", limit: int = 50) -> dict:
            adapter = SamGovAdapter()
            opps = adapter.search(naics=naics or None, state=state or None, limit=limit)
            for o in opps:
                await self.execute_task({
                    "task_id": f"scrape_{o.bid_id}",
                    "type": "log_bid_event",
                    "bid_id": o.bid_id,
                    "event_type": "scraped",
                    "portal": "sam_gov",
                })
            return {"scraped": len(opps), "opportunities": [{"bid_id": o.bid_id, "title": o.title[:80], "posted_date": o.posted_date} for o in opps[:20]]}

        return router

    def get_schema_sql(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS bids (id TEXT PRIMARY KEY, portal TEXT, bid_id TEXT, event_type TEXT,
            amount_cents INTEGER, awarded INTEGER, created_at TEXT);
        CREATE INDEX IF NOT EXISTS idx_bids_bid_id ON bids(bid_id);
        CREATE TABLE IF NOT EXISTS learning_events (id TEXT PRIMARY KEY, bid_id TEXT, outcome TEXT, created_at TEXT);
        """

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        t = task.get("type", "generic")
        if t == "log_bid_event":
            self._log_bid(task)
            return {"status": "logged", "bid_id": task.get("bid_id")}
        if t == "scrape_portals":
            return {"portals_scraped": task.get("portals", []), "new_bids_found": 0}
        return {"acknowledged": True}
    
    def _log_bid(self, task: dict) -> None:
        try:
            with sqlite3.connect(str(self.db_path)) as c:
                c.execute(
                    """INSERT INTO bids (id, portal, bid_id, event_type, amount_cents, awarded, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        uuid.uuid4().hex,
                        task.get("portal", "unknown"),
                        task.get("bid_id", ""),
                        task.get("event_type", "logged"),
                        task.get("amount_cents"),
                        1 if task.get("awarded") else 0,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"bid_scraping _log_bid failed: {e}")
    
    def _get_historical(self) -> list:
        with sqlite3.connect(str(self.db_path)) as c:
            c.row_factory = sqlite3.Row
            return [dict(r) for r in c.execute("SELECT bid_id, event_type, amount_cents, awarded, created_at FROM bids LIMIT 100").fetchall()]
