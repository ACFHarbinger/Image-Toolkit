"""Per-monitor graph serialization + tab-config persistence.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

from ..graph.data_schema import GraphData


class _SerializationMixin:
    """Serialize/restore per-monitor graphs and the tab's saved config."""

    def collect_graphs(self) -> dict:
        self._persist_current()
        return {
            mid: g.to_dict()
            for mid, g in self._graphs.items()
        }

    def restore_graphs(self, data: dict):
        self._graphs = {
            mid: GraphData.from_dict(gd)
            for mid, gd in data.items()
        }
        # Reload current monitor's graph if applicable
        if self._current_monitor_id and self._current_monitor_id in self._graphs:
            graph = self._graphs[self._current_monitor_id]
            self._scene.load_graph(graph)
            self._sync_end_behavior_ui(graph)
            self._update_end_jump_combo()
            self._update_seq_label()

    def get_default_config(self) -> dict:
        """Return the default tab configuration dict."""
        return {
            "monitor_display_graphs": {},
        }

    def set_config(self, config: dict) -> None:
        """Populate input fields from a saved configuration dict."""
        if "monitor_display_graphs" in config:
            self.restore_graphs(config["monitor_display_graphs"])

    def _persist_current(self):
        """Flush UI end-behavior state back into the current graph."""
        graph = self._current_graph()
        if graph:
            self._read_end_behavior_to_graph(graph)


__all__ = ["_SerializationMixin"]
