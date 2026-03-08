"""
Continuous Processor — Continuous task processing for the Universal Spine.

Processes tasks from queue in a loop. Domain-agnostic.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["ContinuousProcessor", "ProcessorConfig"]


@dataclass
class ProcessorConfig:
    """Continuous processor configuration."""

    poll_interval_sec: float = 1.0
    max_iterations: int = 0  # 0 = infinite
    stop_on_empty: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ContinuousProcessor:
    """
    Continuous task processor.
    Polls source, processes, routes to destinations.
    """

    def __init__(
        self,
        source_fn: Callable[[], Optional[dict[str, Any]]],
        process_fn: Callable[[dict[str, Any]], dict[str, Any]],
        config: Optional[ProcessorConfig] = None,
    ) -> None:
        self._source_fn = source_fn
        self._process_fn = process_fn
        self._config = config or ProcessorConfig()
        self._running = False
        self._processed_count = 0

    def run_once(self) -> Optional[dict[str, Any]]:
        """Process one item from source. Returns result or None."""
        task = self._source_fn()
        if task is None:
            return None
        try:
            out = self._process_fn(task)
            self._processed_count += 1
            return out
        except Exception as e:
            logger.warning("ContinuousProcessor failed: %s", e)
            return {"error": str(e)}

    def run(self) -> dict[str, Any]:
        """
        Run continuous processing loop.
        Returns summary when stopped.
        """
        self._running = True
        iteration = 0
        try:
            while self._running:
                result = self.run_once()
                if result is None and self._config.stop_on_empty:
                    break
                iteration += 1
                if self._config.max_iterations and iteration >= self._config.max_iterations:
                    break
                if result is None:
                    time.sleep(self._config.poll_interval_sec)
        finally:
            self._running = False
        return {
            "processed": self._processed_count,
            "iterations": iteration,
            "stopped": not self._running,
        }

    def stop(self) -> None:
        """Signal processor to stop."""
        self._running = False
