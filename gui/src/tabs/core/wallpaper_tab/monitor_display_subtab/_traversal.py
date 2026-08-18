"""Graph-traversal helpers for the monitor-display wallpaper sequencer.

Module-level functions (not methods) shared by several mixins -- extracted
verbatim from ``monitor_display_subtab.py``, pure code motion, no logic
change, to keep the file under the codebase's 500-code-line convention
(§5.17).
"""

from __future__ import annotations

import subprocess
from typing import Dict, List, Optional, Tuple

from ..graph.data_schema import GraphData, NodeData

_VIDEO_DURATION_CACHE: Dict[str, float] = {}


def _get_video_duration(path: str) -> Optional[float]:
    """Return video duration in seconds via ffprobe or cv2."""
    if path in _VIDEO_DURATION_CACHE:
        return _VIDEO_DURATION_CACHE[path]
    try:
        # Issue #81 crash family: this ffprobe fork can race the first
        # QMediaPlayer construction (sequence export runs in the GUI).
        from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard

        with media_backend_spawn_guard():
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=10,
            )
        val = result.stdout.strip()
        if val:
            dur = float(val)
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            dur = frames / fps
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    return None


def _node_duration(nd: NodeData) -> float:
    if nd.display_mode == "video_runtime":
        dur = _get_video_duration(nd.file_path)
        return dur if dur else nd.duration_sec
    return nd.duration_sec


def _build_traversal(graph: GraphData) -> List[Tuple[str, float]]:
    """
    Return [(file_path, duration_sec), ...] for the graph traversal.
    Starts from basis_node_id; at each node follows the lowest-edge_id
    outgoing edge that hasn't been used yet (so a self-edge is taken once
    to repeat the node, then the next unused edge continues the chain).
    Each edge can only be consumed once, which bounds the walk to at most
    len(graph.edges) hops and terminates any cycle.

    An edge's repeat_count (default 1) repeats its target node back-to-back
    that many times before the traversal continues from it -- equivalent to
    repeat_count separate consecutive edges into copies of the same target,
    without having to actually create them. Most useful on self-edges that
    should repeat many times in a row.
    """
    if not graph.nodes:
        return []

    start = graph.basis_node_id
    if not start or start not in graph.nodes:
        start = next(iter(graph.nodes))

    # If no edges, just show the basis node
    if not graph.edges:
        nd = graph.nodes[start]
        return [(nd.file_path, _node_duration(nd))]

    from collections import defaultdict
    adj: Dict[str, List] = defaultdict(list)
    for src in graph.nodes:
        src_edges = sorted(
            [e for e in graph.edges if e.source_id == src],
            key=lambda e: e.edge_id,
        )
        adj[src] = src_edges

    seq: List[Tuple[str, float]] = []
    used_edges: set = set()  # (source_id, edge_id) — edge_id is only unique per-source
    current = start
    while True:
        node = graph.nodes.get(current)
        if node is None:
            break
        seq.append((node.file_path, _node_duration(node)))

        next_edge = next(
            (e for e in adj.get(current, [])
             if (e.source_id, e.edge_id) not in used_edges),
            None,
        )
        if next_edge is None:
            break  # no unused outgoing edges — sink or cycle exhausted
        used_edges.add((next_edge.source_id, next_edge.edge_id))
        current = next_edge.target_id

        repeat = max(1, getattr(next_edge, "repeat_count", 1))
        if repeat > 1:
            target_nd = graph.nodes.get(current)
            if target_nd is not None:
                seq.extend([(target_nd.file_path, _node_duration(target_nd))] * (repeat - 1))

    return seq


__all__ = ["_get_video_duration", "_node_duration", "_build_traversal", "_VIDEO_DURATION_CACHE"]
