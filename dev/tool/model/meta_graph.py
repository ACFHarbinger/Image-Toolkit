"""Flagship 3D Meta-Graph Topology and Tiered Galaxy Layout (Issue #415 / D43 / D54).

Represents codebase architecture and runtime telemetry dataflows in a 3D
Tiered Galaxy topology where:
- +Y represents Frontend / UI / Host components.
- Y = 0 represents Python Core / domain logic / model orchestrators.
- -Y represents C++ native / SIMD kernels / hardware accelerators.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class MetaGraphNode:
    """A single node in the codebase/runtime meta-graph."""

    id: str
    label: str
    layer: str  # "frontend" | "core" | "native"
    kind: str = "module"  # "subsystem" | "module" | "class" | "function"
    cluster_id: str = "default"
    loc: int = 0
    complexity: float = 1.0
    latency_ms: float = 0.0
    call_count: int = 0
    error_count: int = 0
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # [x, y, z]
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaGraphNode":
        return cls(
            id=data["id"],
            label=data.get("label", data["id"]),
            layer=data.get("layer", "core"),
            kind=data.get("kind", "module"),
            cluster_id=data.get("cluster_id", "default"),
            loc=int(data.get("loc", 0)),
            complexity=float(data.get("complexity", 1.0)),
            latency_ms=float(data.get("latency_ms", 0.0)),
            call_count=int(data.get("call_count", 0)),
            error_count=int(data.get("error_count", 0)),
            position=[float(v) for v in data.get("position", [0.0, 0.0, 0.0])],
            tags=list(data.get("tags", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class MetaGraphEdge:
    """A directed dependency or runtime dataflow edge between two nodes."""

    id: str
    source_id: str
    target_id: str
    kind: str = "import"  # "import" | "call" | "dataflow" | "pipeline_stage"
    weight: float = 1.0
    volume: int = 1
    latency_ms: float = 0.0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaGraphEdge":
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            kind=data.get("kind", "import"),
            weight=float(data.get("weight", 1.0)),
            volume=int(data.get("volume", 1)),
            latency_ms=float(data.get("latency_ms", 0.0)),
            error_count=int(data.get("error_count", 0)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class MetaGraph:
    """The 3D Meta-Graph container with Tiered Galaxy layout generation."""

    nodes: Dict[str, MetaGraphNode] = field(default_factory=dict)
    edges: Dict[str, MetaGraphEdge] = field(default_factory=dict)

    def add_node(self, node: MetaGraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: MetaGraphEdge) -> None:
        self.edges[edge.id] = edge

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": {k: v.to_dict() for k, v in self.edges.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaGraph":
        graph = cls()
        for _k, v in data.get("nodes", {}).items():
            graph.add_node(MetaGraphNode.from_dict(v))
        for _k, v in data.get("edges", {}).items():
            graph.add_edge(MetaGraphEdge.from_dict(v))
        return graph

    # ------------------------------------------------------------------
    # Tiered 3D Galaxy Layout Algorithm (D54)
    # ------------------------------------------------------------------

    def compute_tiered_layout(
        self,
        layer_spacing_y: float = 35.0,
        cluster_radius: float = 25.0,
        galaxy_radius: float = 60.0,
    ) -> None:
        """Compute 3D spatial coordinates using the Tiered Galaxy layout.

        - Y-axis partition:
            - "frontend": +layer_spacing_y
            - "core": 0.0
            - "native": -layer_spacing_y
        - XZ-plane partition:
            - Clusters positioned radially around layer center.
            - Nodes positioned radially within their cluster.
        """
        layer_y_map = {
            "frontend": layer_spacing_y,
            "core": 0.0,
            "native": -layer_spacing_y,
        }

        # Group nodes by (layer, cluster_id)
        layer_clusters: Dict[str, Dict[str, List[MetaGraphNode]]] = {
            "frontend": {},
            "core": {},
            "native": {},
        }

        for node in self.nodes.values():
            layer = node.layer if node.layer in layer_clusters else "core"
            cluster = node.cluster_id or "default"
            if cluster not in layer_clusters[layer]:
                layer_clusters[layer][cluster] = []
            layer_clusters[layer][cluster].append(node)

        for layer, clusters in layer_clusters.items():
            y = layer_y_map[layer]
            cluster_keys = sorted(clusters.keys())
            num_clusters = len(cluster_keys)

            for c_idx, c_key in enumerate(cluster_keys):
                # Cluster center in XZ plane
                if num_clusters == 1:
                    c_center_x, c_center_z = 0.0, 0.0
                else:
                    angle = (2.0 * math.pi * c_idx) / num_clusters
                    c_center_x = galaxy_radius * math.cos(angle)
                    c_center_z = galaxy_radius * math.sin(angle)

                nodes_in_cluster = clusters[c_key]
                num_nodes = len(nodes_in_cluster)

                for n_idx, node in enumerate(nodes_in_cluster):
                    if num_nodes == 1:
                        nx, nz = c_center_x, c_center_z
                    else:
                        # Spiral or circular distribution inside cluster
                        node_angle = (2.0 * math.pi * n_idx) / num_nodes
                        r = cluster_radius * (0.3 + 0.7 * (n_idx / max(num_nodes - 1, 1)))
                        nx = c_center_x + r * math.cos(node_angle)
                        nz = c_center_z + r * math.sin(node_angle)

                    node.position = [round(nx, 2), round(y, 2), round(nz, 2)]

    def get_nexus_nodes(self, top_n: int = 5) -> List[MetaGraphNode]:
        """Return nodes with highest combined in-degree and out-degree connectivity."""
        degrees: Dict[str, int] = {nid: 0 for nid in self.nodes}
        for edge in self.edges.values():
            if edge.source_id in degrees:
                degrees[edge.source_id] += 1
            if edge.target_id in degrees:
                degrees[edge.target_id] += 1

        sorted_ids = sorted(degrees.keys(), key=lambda nid: degrees[nid], reverse=True)
        return [self.nodes[nid] for nid in sorted_ids[:top_n] if nid in self.nodes]
