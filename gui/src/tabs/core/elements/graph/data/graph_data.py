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
