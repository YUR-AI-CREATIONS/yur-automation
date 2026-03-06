"""
DAG Execution Engine — workflows as directed acyclic graphs.

Instead of hard-coding sequences, define a graph. Runtime executes topologically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Set


@dataclass(frozen=True)
class Node:
    """A node in the DAG. name + callable."""

    name: str
    fn: Callable[[dict[str, Any]], dict[str, Any]]


class DAG:
    """
    Directed acyclic graph. Add nodes, add edges, run topologically.

    Example:
        dag = DAG()
        dag.add_node("zoning", lambda ctx: {...})
        dag.add_node("cost", lambda ctx: {...})
        dag.add_edge("zoning", "cost")
        result = dag.run({"parcel_id": "..."})
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, name: str, fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self.nodes[name] = Node(name, fn)
        self.edges.setdefault(name, [])

    def add_edge(self, src: str, dst: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            raise ValueError(f"Unknown node: {src} or {dst}")
        self.edges.setdefault(src, []).append(dst)

    def topological_sort(self) -> List[str]:
        """Return execution order. Raises if cycle detected."""
        visited: Set[str] = set()
        temp: Set[str] = set()
        order: List[str] = []

        def visit(n: str) -> None:
            if n in temp:
                raise ValueError("Cycle detected in DAG")
            if n not in visited:
                temp.add(n)
                for m in self.edges.get(n, []):
                    visit(m)
                temp.remove(n)
                visited.add(n)
                order.append(n)

        for n in self.nodes:
            visit(n)
        return order[::-1]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Execute DAG in topological order. Each node receives ctx, returns updated ctx."""
        for name in self.topological_sort():
            ctx = self.nodes[name].fn(ctx)
        return ctx
