"""Sequence summary, export-to-queue, and per-entry queue durations.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, cast

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox, QWidget

from ._traversal import _build_traversal, _get_video_duration

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _SequenceExportMixin:
    """Traversal summary label, Export-to-Queue, and queue-duration bookkeeping."""

    # ---- Sequence summary -------------------------------------------------

    def _update_seq_label(self: "MonitorDisplaySubTabHostProtocol"):
        graph = self._current_graph()
        if graph is None or (not graph.nodes and not graph.edges):
            self._seq_label.setText("Graph is empty. Add nodes and edges to build the sequence.")
            return
        seq = _build_traversal(graph)
        if not seq:
            self._seq_label.setText("No traversal possible. Add edges connecting the nodes.")
            return
        parts = []
        for i, (fp, dur) in enumerate(seq, 1):
            fname = os.path.basename(fp)
            if len(fname) > 20:
                fname = fname[:17] + "..."
            parts.append(f"[{i}] {fname} ({dur:.0f}s)")
        total = sum(d for _, d in seq)
        self._seq_label.setText(
            f"Sequence ({len(seq)} step{'s' if len(seq) != 1 else ''},"
            f" ~{total:.0f}s total):  "
            + "  →  ".join(parts)
        )

    # ---- Export to Queue ---------------------------------------------------

    @Slot()
    def _export_graph_to_queue(self: "MonitorDisplaySubTabHostProtocol"):
        if self._current_monitor_id is None:
            return
        graph = self._current_graph()
        if graph is None:
            return
        seq = _build_traversal(graph)
        if not seq:
            QMessageBox.information(
                cast(QWidget, self), "Empty Sequence",
                "Add nodes and edges to build a sequence before exporting to the queue.",
            )
            return

        monitor_id = self._current_monitor_id
        queue = self.monitor_slideshow_queues.setdefault(monitor_id, [])
        # Ensure any pre-existing entries have durations before we append,
        # so the parallel durations list stays index-aligned with the queue.
        durations = self._reconcile_queue_durations(monitor_id)
        was_empty = not queue
        for fp, dur in seq:
            queue.append(fp)
            durations.append(dur)

        if was_empty or not self.monitor_image_paths.get(monitor_id):
            self.monitor_image_paths[monitor_id] = queue[0]
            self.monitor_current_index[monitor_id] = 0

        self.update_monitor_widget_ui(monitor_id)
        self._refresh_open_queue_window(monitor_id)
        self.check_all_monitors_set()
        self._update_queue_status_label()

        QMessageBox.information(
                cast(QWidget, self), "Exported to Queue",
            f"Appended {len(seq)} item{'s' if len(seq) != 1 else ''} from the graph "
            f"to the Wallpaper Queue, each with its own duration from the graph.",
        )

    # ---- Per-entry queue durations -----------------------------------------

    def _default_entry_duration(self: "MonitorDisplaySubTabHostProtocol", path: str) -> float:
        """Full runtime for a video, else the default fixed duration -- the
        same fallback semantics used for graph nodes without an explicit
        duration (see _node_duration)."""
        if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            dur = _get_video_duration(path)
            if dur:
                return dur
        return 30.0

    def _reconcile_queue_durations(self: "MonitorDisplaySubTabHostProtocol", monitor_id: str) -> List[float]:
        """Keep self._queue_durations[monitor_id] index-aligned with
        monitor_slideshow_queues[monitor_id], padding new entries (added by
        drag/drop, the context menu, etc.) with a sensible default and
        truncating stale ones. Returns the (mutable) durations list."""
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        durations = self._queue_durations.setdefault(monitor_id, [])
        if len(durations) < len(queue):
            durations.extend(
                self._default_entry_duration(p) for p in queue[len(durations):]
            )
        elif len(durations) > len(queue):
            del durations[len(queue):]
        return durations

    @Slot(str, list)
    def on_queue_reordered(self: "MonitorDisplaySubTabHostProtocol", monitor_id: str, new_queue: List[str]):
        super().on_queue_reordered(monitor_id, new_queue)  # type: ignore[safe-super]
        # A manual drag-reorder in the Wallpaper Queue window carries no
        # duration metadata, so the old index-aligned durations no longer
        # correspond to the right entries. Reset rather than risk silently
        # misapplying a stale duration to the wrong item; the next
        # reconcile recomputes sane per-item defaults.
        self._queue_durations[monitor_id] = []

    def handle_item_swap_request(self: "MonitorDisplaySubTabHostProtocol", s_mid: str, s_idx: int, t_mid: str, t_idx: int):
        s_durs = self._reconcile_queue_durations(s_mid)
        t_durs = self._reconcile_queue_durations(t_mid)
        super().handle_item_swap_request(s_mid, s_idx, t_mid, t_idx)  # type: ignore[safe-super]
        if s_idx < len(s_durs) and t_idx < len(t_durs):
            s_durs[s_idx], t_durs[t_idx] = t_durs[t_idx], s_durs[s_idx]


__all__ = ["_SequenceExportMixin"]
