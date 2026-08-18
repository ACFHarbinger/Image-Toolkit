"""Hierarchical Flame Graph and Call-Tree aggregation model (Issue #416 / D43 / D45).

Constructs hierarchical flame trees from spans and execution telemetry,
linking individual call frames to 3D MetaGraph nodes and supporting differential
(A/B) flame comparisons.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FlameNode:
    """A single frame/span in the hierarchical flame graph."""

    name: str
    value: float  # Cumulative duration in milliseconds
    self_time_ms: float = 0.0
    category: str = "general"
    meta_node_id: Optional[str] = None  # Link to 3D MetaGraphNode
    start_ms: float = 0.0
    end_ms: float = 0.0
    children: List[FlameNode] = field(default_factory=list)
    call_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_child(self, child: FlameNode) -> None:
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": round(self.value, 3),
            "self_time_ms": round(self.self_time_ms, 3),
            "category": self.category,
            "meta_node_id": self.meta_node_id,
            "start_ms": round(self.start_ms, 3),
            "end_ms": round(self.end_ms, 3),
            "call_count": self.call_count,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FlameNode:
        children = [cls.from_dict(c) for c in data.get("children", [])]
        return cls(
            name=data["name"],
            value=float(data.get("value", 0.0)),
            self_time_ms=float(data.get("self_time_ms", 0.0)),
            category=data.get("category", "general"),
            meta_node_id=data.get("meta_node_id"),
            start_ms=float(data.get("start_ms", 0.0)),
            end_ms=float(data.get("end_ms", 0.0)),
            children=children,
            call_count=int(data.get("call_count", 1)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class FlameGraph:
    """Flame graph tree with search, aggregation, and differential comparison."""

    root: FlameNode
    total_time_ms: float

    @classmethod
    def from_spans(cls, spans: List[Any], root_name: str = "root") -> FlameGraph:
        """Construct a flame tree from a list of telemetry spans."""
        normalized: List[Dict[str, Any]] = []
        for s in spans:
            s_start = getattr(s, "start_ms", None)
            if s_start is None and hasattr(s, "start"):
                s_start = s.start * 1000.0 if s.start is not None else None
            if s_start is None:
                continue

            s_dur = getattr(s, "duration_ms", None)
            if s_dur is None and hasattr(s, "duration"):
                s_dur = s.duration * 1000.0 if s.duration is not None else None
            if s_dur is None or s_dur <= 0:
                s_dur = 1.0

            s_end = getattr(s, "end_ms", None)
            if s_end is None:
                s_end = s_start + s_dur

            normalized.append({
                "name": getattr(s, "name", "span"),
                "category": getattr(s, "category", "general"),
                "module": getattr(s, "module", None) or getattr(s, "name", "span"),
                "start_ms": float(s_start),
                "end_ms": float(s_end),
                "duration_ms": float(s_dur),
                "id": getattr(s, "id", None),
            })

        root = FlameNode(name=root_name, value=0.0, category="root")
        if not normalized:
            return cls(root=root, total_time_ms=0.0)

        sorted_spans = sorted(normalized, key=lambda s: s["start_ms"])
        min_start = min(s["start_ms"] for s in sorted_spans)
        max_end = max(s["end_ms"] for s in sorted_spans)
        total_time = max(max_end - min_start, 1.0)

        root.start_ms = min_start
        root.end_ms = max_end
        root.value = total_time

        # Hierarchical stack builder based on time containment
        stack: List[FlameNode] = [root]

        for s in sorted_spans:
            s_start = s["start_ms"]
            s_end = s["end_ms"]
            s_dur = s["duration_ms"]

            node = FlameNode(
                name=s["name"],
                value=s_dur,
                self_time_ms=s_dur,
                category=s["category"],
                meta_node_id=s["module"],
                start_ms=s_start,
                end_ms=s_end,
                metadata={"span_id": s["id"]},
            )

            while len(stack) > 1 and stack[-1].end_ms <= s_start:
                stack.pop()

            parent = stack[-1]
            parent.add_child(node)
            parent.self_time_ms = max(0.0, parent.self_time_ms - node.value)
            stack.append(node)

        return cls(root=root, total_time_ms=root.value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_time_ms": round(self.total_time_ms, 3),
            "tree": self.root.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FlameGraph:
        root = FlameNode.from_dict(data["tree"])
        return cls(root=root, total_time_ms=float(data.get("total_time_ms", root.value)))

    def find_nodes_by_category(self, category: str) -> List[FlameNode]:
        """Find all nodes belonging to a specific category."""
        results: List[FlameNode] = []

        def _traverse(node: FlameNode):
            if node.category == category:
                results.append(node)
            for child in node.children:
                _traverse(child)

        _traverse(self.root)
        return results
