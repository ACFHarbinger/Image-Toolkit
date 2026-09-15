"""Resource, latency, and causal profiling research prototype (Track B Phase 5, #397).

Pure-Python analyses over *recorded* Track A artifacts — flame trees
(:class:`FlameGraph <tool.model.flame_graph.FlameGraph>`) and memory
timeseries. Nothing here samples a live process:

- :func:`simulate_virtual_speedup`: the coz question ("what if frame F
  were s% faster?") answered analytically. Real coz measures the curve
  by delaying peer threads; here the Amdahl bound is derived from the
  target's share of the recorded tree, which is the curve the
  measurement converges to under stable load. Frames whose speedup
  cannot move total time (off-critical-path) correctly predict ~zero.
- :func:`detect_leak_suspects`: sustained monotonic arena growth with no
  matching release — the streaming-merger / SAM-2 masking leak pattern
  §5.3 names — flagged from ``MemoryArena`` samples.
- :func:`summarize_arenas`: per-arena peak/growth/over-capacity rollup
  for the memory views.

No third-party dependencies (no coz binary, no py-spy, no torch).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..model.flame_graph import FlameGraph, FlameNode
from ..model.resource_profile import (
    CausalImpactCurve,
    MemoryArena,
    VirtualSpeedupPoint,
    flame_self_share,
)


def _find_nodes(root: FlameNode, name: str) -> List[FlameNode]:
    """All flame-tree nodes with a given frame name (recursion, inlining)."""
    found = [root] if root.name == name else []
    for child in root.children:
        found.extend(_find_nodes(child, name))
    return found


def simulate_virtual_speedup(
    flame: FlameGraph,
    target: str,
    speedups: Sequence[float] = (0.1, 0.2, 0.5, 1.0, 2.0),
) -> CausalImpactCurve:
    """Build a causal-impact curve for speeding up ``target``.

    The target's share is its inclusive time (self + descendants):
    every node with the frame's name contributes its subtree value, so
    recursive frames are not under-counted. The curve points are the
    analytic Amdahl gains — an upper bound a real virtual-speedup run
    would measure, valid when the profiled load is representative.
    Unknown targets yield a zero-share curve (correctly: no leverage).
    """
    total = flame.total_time_ms
    share = sum(flame_self_share(n, total) for n in _find_nodes(flame.root, target))
    curve = CausalImpactCurve(target=target, target_share=share, baseline_total_ms=total)
    for s in speedups:
        curve.points.append(VirtualSpeedupPoint(speedup=s, predicted_gain=curve.predicted_gain(s)))
    return curve


def rank_targets(flame: FlameGraph, top_n: int = 5) -> List[Dict[str, Any]]:
    """Rank frames by predicted gain at a 2x virtual speedup.

    Answers "what actually matters for throughput" (§5 goal) in one
    table: frames are ordered by causal leverage, not raw hotness — a
    hot-but-parallel frame ranks below a cooler serial bottleneck.
    (Serial vs parallel split is approximated by call-count-weighted
    self time; the recorded tree carries no schedule, documented here
    rather than invented.)
    """
    total = flame.total_time_ms
    by_name: Dict[str, float] = {}

    def _walk(node: FlameNode, is_root: bool = False) -> None:
        # The root frame is the whole profiled program, not an
        # optimization target (speeding up "everything" is vacuous).
        if not is_root:
            by_name[node.name] = by_name.get(node.name, 0.0) + node.value
        for child in node.children:
            _walk(child)

    _walk(flame.root, is_root=True)
    ranked = []
    for name, value in by_name.items():
        share = value / total if total > 0 else 0.0
        curve = CausalImpactCurve(target=name, target_share=share, baseline_total_ms=total)
        ranked.append(
            {
                "target": name,
                "share": share,
                "gain_at_2x": curve.predicted_gain(1.0),
            }
        )
    ranked.sort(key=lambda r: r["gain_at_2x"], reverse=True)
    return ranked[: max(top_n, 0)]


def detect_leak_suspects(
    arena: MemoryArena,
    min_growth_bytes: int = 10 * 1024 * 1024,
    min_run: int = 5,
) -> List[Dict[str, Any]]:
    """Flag sustained monotonic growth runs with no release.

    A leak suspect is a maximal run of ``min_run`` or more consecutive
    samples where allocated bytes never decrease and net growth exceeds
    ``min_growth_bytes``. Sawtooth allocators (alloc/release cycles)
    correctly produce no finding; a slow monotonic climb — the
    streaming-merger leak shape — is reported once, with its full window.
    """
    suspects: List[Dict[str, Any]] = []
    samples = arena.samples
    if len(samples) < min_run:
        return suspects

    def _flush(run_start: int, end: int) -> None:  # end exclusive
        length = end - run_start
        if length < min_run:
            return
        growth = samples[end - 1].allocated_bytes - samples[run_start].allocated_bytes
        if growth >= min_growth_bytes:
            suspects.append(
                {
                    "arena": arena.name,
                    "kind": arena.kind,
                    "from_t_ms": samples[run_start].t_ms,
                    "to_t_ms": samples[end - 1].t_ms,
                    "growth_bytes": growth,
                    "samples": length,
                }
            )

    run_start = 0
    for i in range(1, len(samples)):
        if samples[i].allocated_bytes < samples[i - 1].allocated_bytes:
            _flush(run_start, i)
            run_start = i
    _flush(run_start, len(samples))
    return suspects


def summarize_arenas(arenas: Sequence[MemoryArena]) -> List[Dict[str, Any]]:
    """Per-arena rollup for the memory views: peak, growth, capacity."""
    rows = []
    for arena in arenas:
        rows.append(
            {
                "name": arena.name,
                "kind": arena.kind,
                "peak_mb": round(arena.peak_bytes / (1024 * 1024), 2),
                "growth_mb": round(arena.growth_bytes() / (1024 * 1024), 2),
                "over_capacity": arena.over_capacity(),
                "leak_suspects": len(detect_leak_suspects(arena)),
            }
        )
    rows.sort(key=lambda r: r["peak_mb"], reverse=True)
    return rows


__all__ = [
    "detect_leak_suspects",
    "rank_targets",
    "simulate_virtual_speedup",
    "summarize_arenas",
]
