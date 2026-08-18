"""``MonitorDisplaySubTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import QTimer
from screeninfo import Monitor

from ..common.wallpaper_common_base import WallpaperCommonBase
from ..graph.data_schema import GraphData
from ._end_behavior import _EndBehaviorMixin
from ._graph_ops import _GraphOpsMixin
from ._lifecycle import _LifecycleMixin
from ._monitor_management import _MonitorManagementMixin
from ._preview import _PreviewMixin
from ._props_behavior import _PropsBehaviorMixin
from ._sequence_export import _SequenceExportMixin
from ._serialization import _SerializationMixin
from ._slideshow_daemon import _SlideshowDaemonMixin
from ._slideshow_inapp import _SlideshowInAppMixin
from ._slideshow_status import _SlideshowStatusMixin
from ._ui_graph_canvas import _UIGraphCanvasMixin
from ._ui_props_end import _UIPropsEndMixin


class MonitorDisplaySubTab(
    # Mixins MUST precede WallpaperCommonBase in MRO order: several mixin
    # methods (closeEvent, populate_monitor_layout, on_queue_reordered,
    # handle_item_swap_request, _on_monitor_selected,
    # handle_thumbnail_double_click, show_image_context_menu) override
    # same-named methods WallpaperCommonBase (or its own AbstractClassSingle
    # Gallery/QWidget ancestors) already define. Python's C3 linearization
    # otherwise resolves those methods against WallpaperCommonBase's entire
    # ancestor chain -- inserted as one contiguous MRO block -- before ever
    # reaching mixins listed after it, silently shadowing the overrides with
    # no error (see gui/src/tabs/core/merge_tab/manager.py for the bug this
    # was first caught as).
    _UIGraphCanvasMixin,
    _UIPropsEndMixin,
    _MonitorManagementMixin,
    _GraphOpsMixin,
    _PropsBehaviorMixin,
    _EndBehaviorMixin,
    _SequenceExportMixin,
    _SlideshowInAppMixin,
    _SlideshowDaemonMixin,
    _SlideshowStatusMixin,
    _PreviewMixin,
    _SerializationMixin,
    _LifecycleMixin,
    WallpaperCommonBase,
):
    """
    Graph-based wallpaper sequencer per monitor.

    Each monitor gets its own directed graph where:
    - Nodes are wallpaper files (image/video/GIF) with a display duration.
    - Directed edges define the playback sequence (ordered by edge ID).
    - Self-edges allow repeating the same wallpaper.
    - End behavior defines what happens after the last edge is traversed.
    """

    def __init__(self, parent=None):
        WallpaperCommonBase.__init__(self)
        if parent:
            self.setParent(parent)
        self._monitors: List[Monitor] = []
        self._graphs: Dict[str, GraphData] = {}   # monitor_id -> GraphData
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

        self._build_ui()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_queue_status_label)
        self._status_timer.start(1000)
        QTimer.singleShot(500, self._check_daemon_status_on_startup)


__all__ = ["MonitorDisplaySubTab"]
