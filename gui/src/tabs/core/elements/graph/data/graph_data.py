from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .node_data import NodeData
from .edge_data import EdgeData

@dataclass
class GraphData:
    """Represents the entire graph structure."""
    nodes: Dict[str, NodeData] = field(default_factory=dict)
    edges: List[EdgeData] = field(default_factory=list)
    end_behavior: str = "repeat_graph"
    end_color: str = "#000000"
    end_jump_node_id: Optional[str] = None
    basis_node_id: Optional[str] = None  # starting node of the slideshow

    def alloc_edge_id(self, source_id: str) -> int:
        """Return the next per-source edge index (1-based) for *source_id*."""
        existing = [e for e in self.edges if e.source_id == source_id]
        return len(existing) + 1

    def renumber_edges(self):
        """Re-assign edge_id values so each source node's edges are numbered 1…N."""
        from collections import defaultdict
        counter: Dict[str, int] = defaultdict(int)
        for e in self.edges:
            counter[e.source_id] += 1
            e.edge_id = counter[e.source_id]

    def reorder_source_edges(self, source_id: str, ordered_edge_ids: List[int]) -> None:
        """Reorder source_id's outgoing edges to match ordered_edge_ids (a
        permutation of their current edge_id values), then renumber 1..N to
        match the new order.

        Traversal always follows the lowest-numbered outgoing edge first, so
        this is what actually changes playback order for a node with
        multiple outgoing edges. Physically reorders self.edges (not just
        the edge_id labels) at that source's existing slots, so a later
        renumber_edges() call (e.g. after an unrelated edge removal) won't
        silently revert the reorder back to insertion order.
        """
        src_edges = {e.edge_id: e for e in self.edges if e.source_id == source_id}
        ordered = [src_edges[eid] for eid in ordered_edge_ids if eid in src_edges]
        if len(ordered) != len(src_edges):
            return  # malformed/stale order; ignore rather than corrupt the graph

        for new_id, e in enumerate(ordered, start=1):
            e.edge_id = new_id

        positions = [i for i, e in enumerate(self.edges) if e.source_id == source_id]
        for pos, e in zip(positions, ordered):
            self.edges[pos] = e

    def to_dict(self) -> dict:
        return {
            "nodes": {
                nid: {
                    "node_id": nd.node_id,
                    "file_path": nd.file_path,
                    "display_mode": nd.display_mode,
                    "duration_sec": nd.duration_sec,
                    "pos_x": nd.pos_x,
                    "pos_y": nd.pos_y,
                }
                for nid, nd in self.nodes.items()
            },
            "edges": [
                {"edge_id": e.edge_id, "source_id": e.source_id, "target_id": e.target_id}
                for e in self.edges
            ],
            "end_behavior": self.end_behavior,
            "end_color": self.end_color,
            "end_jump_node_id": self.end_jump_node_id,
            "basis_node_id": self.basis_node_id,
        }

    @staticmethod
    def from_dict(d: dict) -> "GraphData":
        g = GraphData()
        g.end_behavior = d.get("end_behavior", "repeat_graph")
        g.end_color = d.get("end_color", "#000000")
        g.end_jump_node_id = d.get("end_jump_node_id")
        g.basis_node_id = d.get("basis_node_id")
        for nid, nd in d.get("nodes", {}).items():
            g.nodes[nid] = NodeData(**nd)
        for ed in d.get("edges", []):
            g.edges.append(EdgeData(**ed))
        return g
