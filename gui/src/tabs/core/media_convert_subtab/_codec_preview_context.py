"""External-player preview and the per-card context menu.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from ....services import PreviewContext, get_preview_service


class _PreviewContextMixin:
    """Opens the video in an external player and builds the context menu."""

    @Slot(str)
    def handle_full_image_preview(self, video_path: str):
        get_preview_service().open_preview(PreviewContext(path=video_path, parent=self))

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        view_action = QAction("Open in External Player", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Deselect video from conversion"
            if is_selected
            else "Select video to convert"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)

        menu.exec(global_pos)


__all__ = ["_PreviewContextMixin"]
