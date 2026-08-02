"""Wheel/drag autoscroll event filtering for ``WallpaperCommonBase``.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication


class _EventFilterMixin:
    """Drag-near-edge autoscroll and Left-drag wheel scrolling of the gallery."""

    def _handle_autoscroll(self, global_pos: QPoint):
        if not self.isVisible():
            return
        scroll_area = getattr(self, "main_scroll_area", None)
        if scroll_area is None:
            return

        vbar = scroll_area.verticalScrollBar()
        if not vbar or not vbar.isVisible():
            return

        viewport = scroll_area.viewport()
        vp_global_pos = viewport.mapToGlobal(QPoint(0, 0))
        vp_global_rect = QRect(vp_global_pos, viewport.size())

        buffer = 50
        if (global_pos.x() < vp_global_rect.left() - buffer) or (
            global_pos.x() > vp_global_rect.right() + buffer
        ):
            return

        height = vp_global_rect.height()
        threshold = 120
        scroll_step = 20
        rel_y = global_pos.y() - vp_global_rect.top()

        if rel_y < threshold:
            vbar.setValue(vbar.value() - scroll_step)
        elif rel_y > height - threshold:
            vbar.setValue(vbar.value() + scroll_step)

    def eventFilter(self, watched, event):
        if self._filtering_event:
            return False

        self._filtering_event = True
        try:
            if not self.isVisible():
                return False
        finally:
            self._filtering_event = False

        if event.type() == QEvent.Type.Wheel:
            if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
                global_pos = QCursor.pos()
                if self.rect().contains(self.mapFromGlobal(global_pos)):
                    scroll_area = getattr(self, "main_scroll_area", None)
                    if scroll_area is not None:
                        vbar = scroll_area.verticalScrollBar()
                        if vbar and vbar.isVisible():
                            delta = event.angleDelta().y()
                            vbar.setValue(vbar.value() - delta)
                            return True

        elif event.type() in (QEvent.Type.DragMove, QEvent.Type.DragEnter):
            self._handle_autoscroll(QCursor.pos())

        return super().eventFilter(watched, event)


__all__ = ["_EventFilterMixin"]
