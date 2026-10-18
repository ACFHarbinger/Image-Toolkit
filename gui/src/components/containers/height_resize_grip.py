"""Drag-to-resize top and bottom borders for gallery widgets.

``enable_height_resize(widget)`` overlays a thin grip along the widget's top
and bottom edges. Dragging the bottom edge down (or the top edge up) makes
the widget taller; the opposite drag makes it shorter. The new height is
pinned with ``setFixedHeight`` so the surrounding layout absorbs the
difference, and a double-click on either grip restores the widget's
original size constraints. With a ``settings_scope`` the chosen height is
remembered across sessions.

``watch_gallery_host(host)`` does this automatically for every gallery
inside a gallery tab: on each show it finds the ``VirtualDualGallery``,
``VirtualGallery`` and ``MarqueeScrollArea`` widgets under *host* and
attaches grips to any that do not have them yet. A ``VirtualGallery`` inside
a ``VirtualDualGallery`` is left alone, because the dual gallery's own
splitter already divides the space between its two panels.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ...theming.theme_api import color

GRIP_THICKNESS = 6
MIN_GALLERY_HEIGHT = 120
MAX_GALLERY_HEIGHT = 10000
# Qt's QWIDGETSIZE_MAX: the "no maximum" value of maximumHeight().
_QWIDGETSIZE_MAX = (1 << 24) - 1


class _EdgeGrip(QWidget):
    """Transparent strip along one edge; highlights on hover, drags on press."""

    def __init__(self, resizer: "GalleryHeightResizer", edge: str):
        super().__init__(resizer.target)
        self._resizer = resizer
        self.edge = edge
        self._hovered = False
        self.setObjectName(f"gallery_height_grip_{edge}")
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag to resize the gallery · double-click to reset")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, event):
        if not (self._hovered or self._resizer.dragging):
            return
        painter = QPainter(self)
        line = QColor(color("accent"))
        y = 0 if self.edge == "top" else self.height() - 2
        painter.fillRect(0, y, self.width(), 2, line)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resizer.begin_drag(event.globalPosition().y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizer.dragging:
            self._resizer.drag_to(self.edge, event.globalPosition().y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._resizer.dragging:
            self._resizer.end_drag()
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resizer.reset()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class GalleryHeightResizer(QObject):
    """Owns the two edge grips of one widget and applies the dragged height."""

    def __init__(
        self,
        target: QWidget,
        *,
        settings_scope: Optional[str] = None,
        settings_key: Optional[str] = None,
        min_height: int = MIN_GALLERY_HEIGHT,
    ):
        super().__init__(target)
        self.target = target
        self.min_height = min_height
        self._settings_scope = settings_scope
        self._settings_key = settings_key
        self._original_min = target.minimumHeight()
        self._original_max = target.maximumHeight()
        self.custom_height: Optional[int] = None
        self.dragging = False
        self._start_y = 0.0
        self._start_height = 0

        self.top_grip = _EdgeGrip(self, "top")
        self.bottom_grip = _EdgeGrip(self, "bottom")
        target.installEventFilter(self)
        self._restore_saved_height()
        self._place_grips()

    # --- Geometry -------------------------------------------------------

    def eventFilter(self, watched, event):
        if watched is self.target and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.ChildAdded,
        ):
            self._place_grips()
        return False

    def _place_grips(self) -> None:
        width = self.target.width()
        height = self.target.height()
        self.top_grip.setGeometry(0, 0, width, GRIP_THICKNESS)
        self.bottom_grip.setGeometry(0, max(0, height - GRIP_THICKNESS), width, GRIP_THICKNESS)
        self.top_grip.raise_()
        self.bottom_grip.raise_()

    def set_height(self, height: int) -> int:
        height = max(self.min_height, min(int(height), MAX_GALLERY_HEIGHT))
        self.target.setFixedHeight(height)
        self.custom_height = height
        self._place_grips()
        return height

    # --- Dragging -------------------------------------------------------

    def begin_drag(self, global_y: float) -> None:
        self.dragging = True
        self._start_y = global_y
        self._start_height = self.target.height()

    def drag_to(self, edge: str, global_y: float) -> None:
        delta = round(global_y - self._start_y)
        # The bottom edge grows the widget when dragged down; the top edge
        # grows it when dragged up.
        self.set_height(self._start_height + delta if edge == "bottom" else self._start_height - delta)

    def end_drag(self) -> None:
        self.dragging = False
        self._save_height()

    def reset(self) -> None:
        """Restore the widget's original size constraints."""
        self.dragging = False
        self.custom_height = None
        self.target.setMinimumHeight(self._original_min)
        self.target.setMaximumHeight(self._original_max)
        self._place_grips()
        self._save_height()

    # --- Persistence ----------------------------------------------------

    def _restore_saved_height(self) -> None:
        if not (self._settings_scope and self._settings_key):
            return
        from gui.src.windows.settings.app_settings import AppSettings

        try:
            saved = int(AppSettings.session(self._settings_scope, self._settings_key, 0) or 0)
        except (TypeError, ValueError):
            saved = 0
        if saved > 0:
            self.set_height(saved)

    def _save_height(self) -> None:
        if not (self._settings_scope and self._settings_key):
            return
        from gui.src.windows.settings.app_settings import AppSettings

        AppSettings.set_session(self._settings_scope, self._settings_key, self.custom_height or 0)


def enable_height_resize(
    target: QWidget,
    *,
    settings_scope: Optional[str] = None,
    settings_key: Optional[str] = None,
    min_height: int = MIN_GALLERY_HEIGHT,
) -> GalleryHeightResizer:
    """Give *target* draggable top/bottom borders (idempotent)."""
    existing = getattr(target, "_height_resizer", None)
    if isinstance(existing, GalleryHeightResizer):
        return existing
    resizer = GalleryHeightResizer(
        target, settings_scope=settings_scope, settings_key=settings_key, min_height=min_height
    )
    target._height_resizer = resizer  # type: ignore[attr-defined]
    return resizer


def install_gallery_height_grips(host: QWidget) -> list[GalleryHeightResizer]:
    """Attach grips to every gallery widget under *host* that lacks them."""
    from ..virtual_gallery import VirtualDualGallery, VirtualGallery
    from .marquee_scroll_area import MarqueeScrollArea

    duals = host.findChildren(VirtualDualGallery)
    targets: list[QWidget] = list(duals)
    targets += [g for g in host.findChildren(VirtualGallery) if not any(d.isAncestorOf(g) for d in duals)]
    targets += host.findChildren(MarqueeScrollArea)

    scope = type(host).__name__
    counts: dict[str, int] = {}
    resizers = []
    for widget in targets:
        kind = type(widget).__name__
        index = counts.get(kind, 0)
        counts[kind] = index + 1
        name = widget.objectName() or f"{kind}_{index}"
        resizers.append(enable_height_resize(widget, settings_scope=scope, settings_key=f"gallery_height/{name}"))
    return resizers


class _GalleryHostWatcher(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget):
            install_gallery_height_grips(watched)
        return False


def watch_gallery_host(host: QWidget) -> None:
    """Install gallery grips under *host* every time it is shown."""
    watcher = _GalleryHostWatcher(host)
    host.installEventFilter(watcher)
    host._gallery_host_watcher = watcher  # type: ignore[attr-defined]


__all__ = [
    "GalleryHeightResizer",
    "enable_height_resize",
    "install_gallery_height_grips",
    "watch_gallery_host",
]
