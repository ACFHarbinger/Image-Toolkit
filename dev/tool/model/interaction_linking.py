"""Cross-View Interactivity & Bi-Directional Linking Engine (Issue #417 / D45 / D57).

Unifies selection, live hovering pulses, drill-downs, and Investigation
bookmarking across the 3D MetaGraph, 2D Flame Graphs, Metrics Timelines,
and Side-Drawer Inspectors.
"""

from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class SelectionTarget:
    """An active selection in any viewport (3D world, 2D chart, side drawer)."""

    entity_id: str
    entity_kind: str  # "meta_node" | "meta_edge" | "flame_span" | "timeseries_point" | "benchmark_case"
    source_surface: str  # "3d_world" | "flame_graph" | "metrics_chart" | "side_drawer" | "investigation"
    timestamp_ms: Optional[float] = None
    linked_meta_node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SelectionTarget:
        return cls(
            entity_id=data["entity_id"],
            entity_kind=data["entity_kind"],
            source_surface=data.get("source_surface", "unknown"),
            timestamp_ms=data.get("timestamp_ms"),
            linked_meta_node_id=data.get("linked_meta_node_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class HoverTarget:
    """A transient hover event for live pulse synchronization across viewports."""

    entity_id: str
    entity_kind: str
    source_surface: str
    pulse_color: str = "#22d3ee"  # Cyan pulse default
    tooltip: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HoverTarget:
        return cls(
            entity_id=data["entity_id"],
            entity_kind=data["entity_kind"],
            source_surface=data.get("source_surface", "unknown"),
            pulse_color=data.get("pulse_color", "#22d3ee"),
            tooltip=data.get("tooltip"),
            metadata=dict(data.get("metadata", {})),
        )


class CrossViewBridge:
    """Central state & event dispatcher for cross-view linking (D45)."""

    def __init__(self) -> None:
        self.active_selection: Optional[SelectionTarget] = None
        self.active_hover: Optional[HoverTarget] = None
        self._selection_listeners: List[Callable[[SelectionTarget], None]] = []
        self._hover_listeners: List[Callable[[Optional[HoverTarget]], None]] = []

    def on_selection(self, callback: Callable[[SelectionTarget], None]) -> None:
        self._selection_listeners.append(callback)

    def on_hover(self, callback: Callable[[Optional[HoverTarget]], None]) -> None:
        self._hover_listeners.append(callback)

    def set_selection(self, target: SelectionTarget) -> None:
        """Publish a new selection to all viewports."""
        self.active_selection = target
        for cb in self._selection_listeners:
            with contextlib.suppress(Exception):
                cb(target)

    def clear_selection(self) -> None:
        self.active_selection = None

    def set_hover(self, target: Optional[HoverTarget]) -> None:
        """Publish a live hover pulse to all viewports."""
        self.active_hover = target
        for cb in self._hover_listeners:
            with contextlib.suppress(Exception):
                cb(target)

    @staticmethod
    def resolve_meta_node_id(entity_id: str, kind: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Resolve a 2D span, trace, or metric ID back to its canonical 3D MetaNode ID."""
        if kind == "meta_node":
            return entity_id
        if "meta_node_id" in metadata:
            return str(metadata["meta_node_id"])
        if "module" in metadata:
            return str(metadata["module"])
        return None
