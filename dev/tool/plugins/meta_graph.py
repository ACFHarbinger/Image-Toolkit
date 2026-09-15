"""Track B Phase 1 Meta-Graph Plugin: codebase topology, cartography, and trace overlays (#393)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..research.cartography import compute_semantic_cartography
from ..research.meta_graph import (
    apply_execution_trace_overlay,
    build_codebase_topology,
)

MANIFEST = PluginManifest(
    name="meta_graph",
    version="0.1.0",
    description="Interactive Meta-Graph: codebase topology, semantic cartography, and execution trace overlay (Track B Phase 1).",
    surfaces=(
        Surface("cli", "Topological metrics, blast-radius queries, and cartography reports"),
        Surface("web", "3D GPU force-directed galaxy, semantic zoom, and topographic map"),
        Surface("mcp", "Codebase topology queries, blast radius, and nexus module detection"),
    ),
    channels=(
        Channel("codebase_topology", "Static AST and dependency graph topology", retention="forever"),
        Channel("cartography", "LSI / MDS semantic landscape coordinates", retention="forever"),
        Channel("trace_overlay", "Dynamic execution trace mapping", retention="30d"),
    ),
    entry_point="tool.plugins.meta_graph:plugin",
)


class MetaGraphPlugin:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        root = Path(getattr(store, "repo_root", getattr(store, "root", Path.cwd())))
        artifacts: List[Artifact] = []

        # 1. Codebase topology artifact
        graph = build_codebase_topology(root, max_files=100)
        nexus = graph.get_nexus_nodes(top_n=5)
        artifacts.append(Artifact(
            kind="topology",
            name="meta_graph:codebase_topology",
            path=root,
            meta={
                "research": True,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "nexus_node_ids": [n.id for n in nexus],
            },
        ))

        # 2. Software cartography artifact
        cart = compute_semantic_cartography(graph)
        artifacts.append(Artifact(
            kind="cartography",
            name="meta_graph:cartography",
            path=root,
            meta={
                "research": True,
                "landmarks_count": len(cart.get("landmarks", [])),
                "total_nodes": cart.get("total_nodes", 0),
            },
        ))

        # 3. Dynamic execution trace overlays from session logs
        for session_path in store.sessions():
            try:
                events = []
                for line in session_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
                if events:
                    overlay = apply_execution_trace_overlay(graph, events)
                    artifacts.append(Artifact(
                        kind="trace",
                        name=f"meta_graph:trace:{session_path.name}",
                        path=session_path,
                        meta={"research": True, **overlay},
                    ))
            except Exception:
                continue

        return artifacts


plugin = MetaGraphPlugin()


def main(argv=None) -> int:
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())
