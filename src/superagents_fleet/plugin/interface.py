"""
Agent Plugin Interface — Contract for pluggable agents with API + database.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)


@dataclass
class PluginConfig:
    """Configuration for an agent plugin."""

    agent_id: str
    name: str
    domain: str
    phase: str
    data_dir: Path
    capabilities: tuple[str, ...] = ()
    description: str = ""


class AgentPlugin(ABC):
    """
    Base interface for agent plugins.

    Each plugin has:
    - Own API (FastAPI router)
    - Own database (SQLite at data_dir / {agent_id}.db)
    - Local-only learning
    - Privacy enforcement
    """

    def __init__(self, config: PluginConfig):
        self.config = config
        self._db_path = config.data_dir / f"{config.agent_id}.db"

    @property
    def agent_id(self) -> str:
        return self.config.agent_id

    @property
    def db_path(self) -> Path:
        return self._db_path

    # --- Required ---

    @abstractmethod
    def get_router(self) -> APIRouter:
        """Return FastAPI router for this agent's API."""
        pass

    @abstractmethod
    def get_schema_sql(self) -> str:
        """Return SQL for agent's database schema (CREATE TABLE IF NOT EXISTS ...)."""
        pass

    @abstractmethod
    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute a task. All data stays local unless explicitly sanitized."""
        pass

    # --- Optional (override for learning) ---

    async def learn(self, task: dict[str, Any], result: dict[str, Any], feedback: Optional[dict[str, Any]] = None) -> None:
        """
        Learn from task execution. Called after execute_task.

        STAYS LOCAL: This runs only on local DB. No external calls.
        """
        pass

    def get_private_fields(self) -> list[str]:
        """Agent-specific private field names to never send externally."""
        return []

    def get_info(self) -> dict[str, Any]:
        """Return agent info for listing (FleetHub compatibility)."""
        return {
            "agent_id": self.config.agent_id,
            "name": self.config.name,
            "domain": self.config.domain,
            "phase": self.config.phase,
            "capabilities": list(self.config.capabilities),
            "status": "idle",
            "tasks_completed": 0,
            "has_api": True,
            "has_db": True,
        }

    # --- Lifecycle ---

    def init_db(self) -> None:
        """Initialize agent database. Called on plugin load."""
        try:
            self.config.data_dir.mkdir(parents=True, exist_ok=True)
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.executescript(self.get_schema_sql())
                conn.execute("PRAGMA journal_mode=WAL")
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.exception(f"Plugin {self.config.agent_id} init_db failed: {e}")
            raise
