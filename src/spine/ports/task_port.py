"""
Task Port — Task processing queue for the Universal Spine.

Queues tasks for processing and dispatches to workers.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["TaskPort", "TaskPortConfig"]


@dataclass
class TaskPortConfig:
    """Task port configuration."""

    port_id: str
    max_queue_size: int = 10_000
    worker_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskPort:
    """
    Task processing queue port.
    Enqueues tasks and processes via worker.
    """

    def __init__(
        self,
        port_id: str,
        worker_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
        config: Optional[TaskPortConfig] = None,
    ) -> None:
        self._port_id = port_id
        self._worker_fn = worker_fn
        self._config = config or TaskPortConfig(port_id=port_id)
        self._queue: deque[dict[str, Any]] = deque(maxlen=self._config.max_queue_size)

    def enqueue(self, task: dict[str, Any]) -> dict[str, Any]:
        """Add task to queue. Returns enqueue result."""
        if len(self._queue) >= self._config.max_queue_size:
            return {"port_id": self._port_id, "enqueued": False, "error": "Queue full"}
        self._queue.append(task)
        return {"port_id": self._port_id, "enqueued": True, "queue_size": len(self._queue)}

    def process_one(self) -> Optional[dict[str, Any]]:
        """Process one task from queue. Returns result or None if empty."""
        if not self._queue:
            return None
        task = self._queue.popleft()
        fn = self._worker_fn or self._config.worker_fn
        if not fn:
            return {"port_id": self._port_id, "task": task, "processed": False, "error": "No worker"}
        try:
            out = fn(task)
            return {"port_id": self._port_id, "result": out, "processed": True}
        except Exception as e:
            logger.warning("TaskPort %s process failed: %s", self._port_id, e)
            return {"port_id": self._port_id, "error": str(e), "processed": False}

    def queue_size(self) -> int:
        """Current queue length."""
        return len(self._queue)
