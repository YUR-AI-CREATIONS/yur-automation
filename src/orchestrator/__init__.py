"""
Orchestrator — DAG workflows instead of if-spaghetti.

Define workflows as graphs. Runtime executes topologically.
"""

from .dag import DAG, Node

__all__ = ["DAG", "Node"]
