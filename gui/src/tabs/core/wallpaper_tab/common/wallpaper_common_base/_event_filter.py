"""Wheel/drag autoscroll event filtering for ``WallpaperCommonBase``.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QWidget

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _EventFilterMixin:
    """Drag-near-edge autoscroll and Left-drag wheel scrolling of the gallery."""

    def _handle_autoscroll(self: "WallpaperCommonBaseHostProtocol", global_pos: QPoint):
        if not cast(QWidget, self).isVisible():
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

    def _uninstall_stale_app_filter(self: "WallpaperCommonBaseHostProtocol") -> None:
        """Remove this object from the application-wide event filter list.

        ``_ui_builder`` installs the SystemDisplaySubTab as an *application*
        event filter but nothing ever removed it. Once the widget is torn
        down, every event in the whole app kept routing through this now-dead
        C++ wrapper, raising ``RuntimeError`` on each one and leaving the app
        unclickable (event loop still spinning, so not "frozen"). This makes
        the filter self-evicting on the first sign of trouble.
        """
        app = QApplication.instance()
        if app is not None:
            with contextlib.suppress(Exception):
                app.removeEventFilter(cast(QObject, self))

    def eventFilter(self: "WallpaperCommonBaseHostProtocol", watched: QObject, event: QEvent):
        if self._filtering_event:
            return False

        self._filtering_event = True
        try:
            widget = cast(QWidget, self)
            if not widget.isVisible():
                return False

            et = event.type()
            if et == QEvent.Type.Wheel:
                if QApplication.mouseButtons() & Qt.MouseButton.LeftButton:
                    global_pos = QCursor.pos()
                    if widget.rect().contains(widget.mapFromGlobal(global_pos)):
                        scroll_area = getattr(self, "main_scroll_area", None)
                        if scroll_area is not None:
                            vbar = scroll_area.verticalScrollBar()
                            if vbar and vbar.isVisible():
                                delta = event.angleDelta().y()  # type: ignore[attr-defined]
                                vbar.setValue(vbar.value() - delta)
                                return True
            elif et in (QEvent.Type.DragMove, QEvent.Type.DragEnter):
                self._handle_autoscroll(QCursor.pos())
            return super().eventFilter(watched, event)  # type: ignore[misc,safe-super]
        except RuntimeError:
            # ``self`` (or a child) is a deleted C++ object -- a stale
            # app-wide filter left behind by a torn-down subtab. Evict it so
            # events stop dead-ending here and the app becomes clickable
            # again.
            self._uninstall_stale_app_filter()
            return False
        except Exception:
            return False
        finally:
            self._filtering_event = False


__all__ = ["_EventFilterMixin"]
