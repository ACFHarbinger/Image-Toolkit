"""Monitor list update/selection for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import QTimer, Slot
from screeninfo import Monitor

from ..graph.data_schema import GraphData
from ._tab_bound import TabBoundController

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class MonitorDisplayMonitorManagementController(TabBoundController):
    """Update the monitor list and react to monitor selection changes."""

    _current_monitor_id: Optional[str]

    def update_monitors(self: "MonitorDisplaySubTabHostProtocol", monitors: List[Monitor]):
        self._monitors = monitors
        self.monitors = monitors
        self.populate_monitor_layout()
        if monitors:
            self._stack.setCurrentIndex(1)
            # Auto-select the first monitor on update if nothing is selected or current is invalid
            if (
                not self._current_monitor_id
                or self._current_monitor_id not in self.monitor_widgets
                and self.monitor_widgets
            ):
                first_id = next(iter(self.monitor_widgets.keys()))
                self._select_monitor(first_id)
        else:
            self._stack.setCurrentIndex(0)

    @Slot(str)
    def _on_monitor_selected(self: "MonitorDisplaySubTabHostProtocol", monitor_id: str):
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


__all__ = ["MonitorDisplayMonitorManagementController"]

_MonitorManagementMixin = (
    MonitorDisplayMonitorManagementController  # COMPAT(ui-arch-23): remove after callers drop the mixin name
)
