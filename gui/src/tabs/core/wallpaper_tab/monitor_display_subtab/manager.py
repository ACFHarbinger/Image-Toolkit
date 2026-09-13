"""``MonitorDisplaySubTab`` -- composed TabBoundControllers + WallpaperCommonBase."""

from __future__ import annotations

import os
import shutil
from typing import Dict, List, Optional

from PySide6.QtCore import QTimer, Slot
from screeninfo import Monitor

from ..common.wallpaper_common_base import WallpaperCommonBase
from ..graph.data_schema import GraphData
from ._end_behavior import MonitorDisplayEndBehaviorController
from ._graph_ops import MonitorDisplayGraphOpsController
from ._lifecycle import MonitorDisplayLifecycleController
from ._monitor_management import MonitorDisplayMonitorManagementController
from ._preview import MonitorDisplayPreviewController
from ._props_behavior import MonitorDisplayPropsBehaviorController
from ._sequence_export import MonitorDisplaySequenceExportController
from ._serialization import MonitorDisplaySerializationController
from ._slideshow_daemon import MonitorDisplaySlideshowDaemonController
from ._slideshow_inapp import MonitorDisplaySlideshowInAppController
from ._slideshow_status import MonitorDisplaySlideshowStatusController
from ._ui_graph_canvas import MonitorDisplayUIGraphCanvas
from ._ui_props_end import MonitorDisplayUIPropsEnd


def _delegate(attr: str, name: str):
    def _fn(self, *args, **kwargs):
        return getattr(getattr(self, attr), name)(*args, **kwargs)

    _fn.__name__ = name
    _fn.__qualname__ = f"MonitorDisplaySubTab.{name}"
    return _fn


class MonitorDisplaySubTab(WallpaperCommonBase):
    """
    Graph-based wallpaper sequencer per monitor.

    Each monitor gets its own directed graph where:
    - Nodes are wallpaper files (image/video/GIF) with a display duration.
    - Directed edges define the playback sequence (ordered by edge ID).
    - Self-edges allow repeating the same wallpaper.
    - End behavior defines what happens after the last edge is traversed.
    """

    def __init__(self, parent=None):
        super().__init__()
        if parent:
            self.setParent(parent)
        self._monitors: List[Monitor] = []
        self._graphs: Dict[str, GraphData] = {}  # monitor_id -> GraphData
        self._current_monitor_id: Optional[str] = None
        self._preview_tmp_dir: Optional[str] = None

        # Per-entry queue durations: monitor_id -> [seconds, ...] parallel to
        # monitor_slideshow_queues[monitor_id]. Local to this subtab (not
        # shared with System Display) since it models the graph-driven,
        # per-item duration semantics unique to this queue export/slideshow.
        self._queue_durations: Dict[str, List[float]] = {}

        # In-app slideshow: delegated to the native scheduler
        # (base.run_monitor_slideshow, via monitor_slideshow_daemon.py) which
        # runs its own std::thread inside this GUI process. It's a
        # process-wide singleton, so only one display's in-app slideshow can
        # be active at a time -- same constraint as the background daemon.
        self._inapp_active_monitor_id: Optional[str] = None

        # Background daemon: only one display can run it at a time (single
        # shared config file / detached process)
        self._daemon_active_monitor_id: Optional[str] = None

        self.ui_graph_canvas = MonitorDisplayUIGraphCanvas(self)
        self.ui_props_end = MonitorDisplayUIPropsEnd(self)
        self.monitor_management_controller = MonitorDisplayMonitorManagementController(self)
        self.graph_ops_controller = MonitorDisplayGraphOpsController(self)
        self.props_behavior_controller = MonitorDisplayPropsBehaviorController(self)
        self.end_behavior_controller = MonitorDisplayEndBehaviorController(self)
        self.sequence_export_controller = MonitorDisplaySequenceExportController(self)
        self.slideshow_inapp_controller = MonitorDisplaySlideshowInAppController(self)
        self.slideshow_daemon_controller = MonitorDisplaySlideshowDaemonController(self)
        self.slideshow_status_controller = MonitorDisplaySlideshowStatusController(self)
        self.preview_controller = MonitorDisplayPreviewController(self)
        self.serialization_controller = MonitorDisplaySerializationController(self)
        self.lifecycle_controller = MonitorDisplayLifecycleController(self)

        self._build_ui()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_queue_status_label)
        self._status_timer.start(1000)
        QTimer.singleShot(500, self._check_daemon_status_on_startup)

    def closeEvent(self, event):
        # In-app slideshows only make sense "while the user remains in-app",
        # so stop the native scheduler here. The background daemon is
        # intentionally left running -- that is its whole point.
        if self._inapp_active_monitor_id is not None:
            self._stop_inapp_slideshow()

        if hasattr(self, "_status_timer") and self._status_timer.isActive():
            self._status_timer.stop()

        if self._preview_tmp_dir and os.path.isdir(self._preview_tmp_dir):
            shutil.rmtree(self._preview_tmp_dir, ignore_errors=True)
        super().closeEvent(event)

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

    @Slot(str, list)
    def on_queue_reordered(self, monitor_id: str, new_queue: List[str]):
        super().on_queue_reordered(monitor_id, new_queue)
        # A manual drag-reorder in the Wallpaper Queue window carries no
        # duration metadata, so the old index-aligned durations no longer
        # correspond to the right entries. Reset rather than risk silently
        # misapplying a stale duration to the wrong item; the next
        # reconcile recomputes sane per-item defaults.
        self._queue_durations[monitor_id] = []

    def handle_item_swap_request(self, s_mid: str, s_idx: int, t_mid: str, t_idx: int):
        s_durs = self._reconcile_queue_durations(s_mid)
        t_durs = self._reconcile_queue_durations(t_mid)
        super().handle_item_swap_request(s_mid, s_idx, t_mid, t_idx)
        if s_idx < len(s_durs) and t_idx < len(t_durs):
            s_durs[s_idx], t_durs[t_idx] = t_durs[t_idx], s_durs[s_idx]

    _sync_end_behavior_ui = _delegate("end_behavior_controller", "_sync_end_behavior_ui")
    _on_end_behavior_changed = _delegate("end_behavior_controller", "_on_end_behavior_changed")
    _read_end_behavior_to_graph = _delegate("end_behavior_controller", "_read_end_behavior_to_graph")
    _pick_end_color = _delegate("end_behavior_controller", "_pick_end_color")
    _refresh_end_color_preview = _delegate("end_behavior_controller", "_refresh_end_color_preview")
    _update_end_jump_combo = _delegate("end_behavior_controller", "_update_end_jump_combo")

    _current_graph = _delegate("graph_ops_controller", "_current_graph")
    _add_node = _delegate("graph_ops_controller", "_add_node")
    _selected_node_id = _delegate("graph_ops_controller", "_selected_node_id")
    _add_self_edge = _delegate("graph_ops_controller", "_add_self_edge")
    _add_edge = _delegate("graph_ops_controller", "_add_edge")
    _delete_selected = _delegate("graph_ops_controller", "_delete_selected")
    _set_start_node = _delegate("graph_ops_controller", "_set_start_node")
    _clear_canvas = _delegate("graph_ops_controller", "_clear_canvas")
    _fit_view = _delegate("graph_ops_controller", "_fit_view")
    _edit_node = _delegate("graph_ops_controller", "_edit_node")
    _on_graph_changed = _delegate("graph_ops_controller", "_on_graph_changed")
    handle_thumbnail_double_click = _delegate("graph_ops_controller", "handle_thumbnail_double_click")
    show_image_context_menu = _delegate("graph_ops_controller", "show_image_context_menu")

    update_monitors = _delegate("monitor_management_controller", "update_monitors")
    _on_monitor_selected = _delegate("monitor_management_controller", "_on_monitor_selected")

    _preview_timelapse = _delegate("preview_controller", "_preview_timelapse")
    _generate_preview = _delegate("preview_controller", "_generate_preview")
    _open_file = _delegate("preview_controller", "_open_file")

    _on_selection_changed = _delegate("props_behavior_controller", "_on_selection_changed")
    _show_node_in_props = _delegate("props_behavior_controller", "_show_node_in_props")
    _apply_props = _delegate("props_behavior_controller", "_apply_props")
    _populate_props_edges_list = _delegate("props_behavior_controller", "_populate_props_edges_list")
    _add_props_edge = _delegate("props_behavior_controller", "_add_props_edge")
    _props_edges_context_menu = _delegate("props_behavior_controller", "_props_edges_context_menu")
    _on_props_edges_reordered = _delegate("props_behavior_controller", "_on_props_edges_reordered")

    _update_seq_label = _delegate("sequence_export_controller", "_update_seq_label")
    _export_graph_to_queue = _delegate("sequence_export_controller", "_export_graph_to_queue")
    _default_entry_duration = _delegate("sequence_export_controller", "_default_entry_duration")
    _reconcile_queue_durations = _delegate("sequence_export_controller", "_reconcile_queue_durations")

    collect_graphs = _delegate("serialization_controller", "collect_graphs")
    restore_graphs = _delegate("serialization_controller", "restore_graphs")
    get_default_config = _delegate("serialization_controller", "get_default_config")
    set_config = _delegate("serialization_controller", "set_config")
    _persist_current = _delegate("serialization_controller", "_persist_current")

    _read_daemon_status = _delegate("slideshow_daemon_controller", "_read_daemon_status")
    _check_daemon_status_on_startup = _delegate("slideshow_daemon_controller", "_check_daemon_status_on_startup")
    _toggle_daemon_slideshow = _delegate("slideshow_daemon_controller", "_toggle_daemon_slideshow")
    _start_daemon_slideshow = _delegate("slideshow_daemon_controller", "_start_daemon_slideshow")
    _stop_daemon_slideshow = _delegate("slideshow_daemon_controller", "_stop_daemon_slideshow")

    _toggle_inapp_slideshow = _delegate("slideshow_inapp_controller", "_toggle_inapp_slideshow")
    _start_inapp_slideshow = _delegate("slideshow_inapp_controller", "_start_inapp_slideshow")
    _stop_inapp_slideshow = _delegate("slideshow_inapp_controller", "_stop_inapp_slideshow")
    _sync_inapp_state_from_native = _delegate("slideshow_inapp_controller", "_sync_inapp_state_from_native")

    _update_slideshow_buttons = _delegate("slideshow_status_controller", "_update_slideshow_buttons")
    _update_queue_status_label = _delegate("slideshow_status_controller", "_update_queue_status_label")

    _build_ui = _delegate("ui_graph_canvas", "_build_ui")
    _build_graph_toolbar = _delegate("ui_graph_canvas", "_build_graph_toolbar")
    _build_bottom_toolbar = _delegate("ui_graph_canvas", "_build_bottom_toolbar")
    _build_gallery_panel = _delegate("ui_graph_canvas", "_build_gallery_panel")

    _build_props_panel = _delegate("ui_props_end", "_build_props_panel")
    _build_end_behavior_bar = _delegate("ui_props_end", "_build_end_behavior_bar")


__all__ = ["MonitorDisplaySubTab"]
