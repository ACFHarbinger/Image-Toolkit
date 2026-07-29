"""``MonitorDropView`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QMenu
from screeninfo import Monitor

from ._context_menu import _ContextMenuMixin
from ._drag_drop import _DragDropMixin
from ._image_display import _ImageDisplayMixin
from ._monitor_info import _MonitorInfoMixin
from ._mouse_events import _MouseEventsMixin
from ._ui_builder import _UIBuilderMixin


class MonitorDropView(
    # Mixins MUST precede QLabel in MRO order (see gui/src/tabs/core/
    # merge_tab/manager.py for the bug this pattern fixes): several mixin
    # methods here (text, resizeEvent, mouseDoubleClickEvent, mousePressEvent,
    # mouseMoveEvent, dragEnterEvent, dragMoveEvent, dragLeaveEvent, dropEvent,
    # contextMenuEvent) override same-named methods QLabel itself defines.
    _UIBuilderMixin,
    _MonitorInfoMixin,
    _ContextMenuMixin,
    _MouseEventsMixin,
    _DragDropMixin,
    _ImageDisplayMixin,
    QLabel,
):
    """
    A custom QLabel that acts as a drop target for images,
    displays monitor info, and shows a preview of the dropped image.
    """

    # Emits (monitor_id, [image_paths]) when images are successfully dropped
    images_dropped = Signal(str, list)

    # Emits monitor_id when the widget is double-clicked
    double_clicked = Signal(str)

    # Emits monitor_id when the 'Clear Monitor' right-click action is selected
    clear_requested_id = Signal(str)

    # Emits (source_id, target_id) when a 'Swap Wallpapers' target is selected
    swap_requested_id = Signal(str, str)

    # Emits (source_id, target_id) when a 'Swap Wallpaper Graph' target is selected
    swap_graph_requested_id = Signal(str, str)

    # Emits (monitor_id, menu) to allow parent to add dynamic items
    context_menu_requested = Signal(str, QMenu)

    # Emits monitor_id when the widget is clicked
    clicked = Signal(str)

    def __init__(self, monitor: Monitor, monitor_id: str, hardware_name: Optional[str] = None):
        super().__init__()
        self.monitor = monitor
        self.monitor_id = monitor_id
        self.hardware_name = hardware_name
        self.image_path: Optional[str] = None

        self._build_ui()


__all__ = ["MonitorDropView"]
