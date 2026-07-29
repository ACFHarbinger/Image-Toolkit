"""Monitor list update/selection for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QTimer, Slot
from screeninfo import Monitor

from ..graph.data_schema import GraphData


class _MonitorManagementMixin:
    """Update the monitor list and react to monitor selection changes."""

    def update_monitors(self, monitors: List[Monitor]):
        self._monitors = monitors
        self.monitors = monitors
        self.populate_monitor_layout()
        if monitors:
            self._stack.setCurrentIndex(1)
            # Auto-select the first monitor on update if nothing is selected or current is invalid
            if not self._current_monitor_id or self._current_monitor_id not in self.monitor_widgets and self.monitor_widgets:
                first_id = next(iter(self.monitor_widgets.keys()))
                self._select_monitor(first_id)
        else:
            self._stack.setCurrentIndex(0)

    def populate_monitor_layout(self):
        super().populate_monitor_layout()

        # If we have a system display reference, sync the images to our newly created widgets!
        if hasattr(self, "_system_display_ref") and self._system_display_ref:
            for mid, sys_widget in self._system_display_ref.monitor_widgets.items():
                widget = self.monitor_widgets.get(mid)
                if widget and sys_widget.image_path:
                    thumb = self._system_display_ref._get_or_generate_thumbnail(sys_widget.image_path)
                    widget.set_image(sys_widget.image_path, thumb)

        # Re-apply selection style to current selected monitor if it exists
        if self._current_monitor_id and self._current_monitor_id in self.monitor_widgets:
            self.monitor_widgets[self._current_monitor_id].set_selected(True)

    @Slot(str)
    def _on_monitor_selected(self, monitor_id: str):
        self._current_monitor_id = monitor_id
        if monitor_id not in self._graphs:
            self._graphs[monitor_id] = GraphData()
        graph = self._graphs[monitor_id]
        self._scene.load_graph(graph)
        self._sync_end_behavior_ui(graph)
        self._update_end_jump_combo()
        self._update_seq_label()
        self._update_slideshow_buttons()
        self._update_queue_status_label()
        QTimer.singleShot(50, self._fit_view)


__all__ = ["_MonitorManagementMixin"]
