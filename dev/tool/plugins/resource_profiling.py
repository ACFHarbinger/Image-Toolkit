"""Track B Phase 5 Resource Profiling plugin: causal impact curves and memory arenas (#397).

Host attachment: shares Track A's flame + memory views — this plugin
charts analyses *derived from* recorded flame trees and arena samples,
it does not sample live processes. Channels carry the derived artifacts
(causal curves, arena rollups, leak-suspect lists), never raw profiler
captures.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..model.resource_profile import MemoryArena
from ..research.resource_profiling import (
    detect_leak_suspects,
    rank_targets,
    simulate_virtual_speedup,
    summarize_arenas,
)

MANIFEST = PluginManifest(
    name="resource_profiling",
    version="0.1.0",
    description="Resource, latency, and causal profiling: virtual-speedup curves from recorded flame trees, Little's-law latency, VRAM/RAM arena analysis (Track B Phase 5).",
    surfaces=(
        Surface("cli", "Rank causal targets, curve a frame, summarize arenas"),
        Surface("web", "Causal-impact chart, arena memory view, leak-suspect list"),
        Surface("mcp", "Causal-leverage queries, arena summaries"),
    ),
    channels=(
        Channel("causal_profile", "Virtual-speedup curves derived from flame trees", retention="30d"),
        Channel("memory_arenas", "VRAM/RAM arena samples and leak-suspect lists", retention="30d"),
    ),
    entry_point="tool.plugins.resource_profiling:plugin",
)


class ResourceProfiling:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        return []

    def profile_flame(self, flame_dict: Dict[str, Any], top_n: int = 5) -> Dict[str, Any]:
        """Rank causal targets for a recorded flame tree (dict form)."""
        from ..model.flame_graph import FlameGraph

        flame = FlameGraph.from_dict(flame_dict)
        return {
            "total_ms": flame.total_time_ms,
            "targets": rank_targets(flame, top_n=top_n),
        }

    def curve_for(
        self, flame_dict: Dict[str, Any], target: str
    ) -> Dict[str, Any]:
        """Virtual-speedup curve for one frame (dict in, dict out)."""
        from ..model.flame_graph import FlameGraph

        flame = FlameGraph.from_dict(flame_dict)
        return simulate_virtual_speedup(flame, target).to_dict()

    def check_arenas(self, arena_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Arena rollup + leak suspects for recorded arena samples."""
        arenas = [MemoryArena.from_dict(d) for d in arena_dicts]
        suspects = [s for a in arenas for s in detect_leak_suspects(a)]
        return {"arenas": summarize_arenas(arenas), "leak_suspects": suspects}


plugin = ResourceProfiling()


def main(argv=None) -> int:
    """D52 command-plugin entry: python -m tool.plugins.<name> --stdio."""
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())
