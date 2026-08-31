"""Virtualized gallery view — GUI/UX §2.1 Option A.

A ``QListView`` in ``IconMode`` backed by :class:`VirtualGalleryModel`.
Qt's model/view machinery performs viewport culling automatically — only the
cells that intersect the visible viewport are painted and only those cells'
``data()`` is requested — so the widget/paint cost is constant regardless of
row count. This is the property the QLabel-grid galleries can't get without a
page cap.

The view adds the behaviours the QLabel galleries' ``ClickableLabel`` and
``MarqueeScrollArea`` provided, re-expressed over the selection model:

* ``path_clicked`` / ``path_activated`` / ``path_right_clicked`` signals
  (mirroring ``ClickableLabel``'s path signals, including the global-position
  right-click payload used by the context menus).
* ``ctrl_wheel`` on Ctrl+scroll for §2.2B thumbnail zoom, matching
  ``MarqueeScrollArea``.
* Scroll-prefetch: on scrollbar movement the view tells the model to start
  loading thumbnails for the visible rows plus a buffer, so scrolling ahead
  finds cached images instead of blank cells.
* ``QItemSelectionModel``-backed selection (§2.4) with ``selected_paths()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import (
    QItemSelection,
    QMimeData,
    QModelIndex,
    QPoint,
    QSize,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDrag, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QListView

from .delegate import VirtualGalleryDelegate

if TYPE_CHECKING:
    from .virtual_gallery_model import VirtualGalleryModel


class VirtualGalleryView(QListView):
    """Icon-mode list view with prefetch-on-scroll and gallery-style signals."""

    path_clicked = Signal(str)
    path_activated = Signal(str)
    path_right_clicked = Signal(QPoint, str)
    ctrl_wheel = Signal(int)

    def __init__(self, parent=None, prefetch_buffer: int = 40):
        super().__init__(parent)
        self._prefetch_buffer = prefetch_buffer
        self._last_prefetched_range: tuple[int, int] = (-1, -1)

        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setFlow(QListView.Flow.TopToBottom)
        self.setWrapping(True)
        self.setSpacing(6)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionRectVisible(True)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(VirtualGalleryDelegate(self))

        self.customContextMenuRequested.connect(self._on_context_menu)
        self.doubleClicked.connect(self._on_double_clicked)
        self.pressed.connect(self._on_pressed)
        self.verticalScrollBar().valueChanged.connect(self._on_scrolled)

        self._gallery_model: Optional["VirtualGalleryModel"] = None

    # ------------------------------------------------------------------
    # Model wiring
    # ------------------------------------------------------------------

    def setModel(self, model):
        super().setModel(model)
        from .virtual_gallery_model import VirtualGalleryModel

        self._gallery_model = model if isinstance(model, VirtualGalleryModel) else None
        if self._gallery_model is not None:
            self._apply_grid_size()

    def set_thumbnail_size(self, size: int) -> None:
        if self._gallery_model is not None:
            self._gallery_model.set_thumbnail_size(size)
            self._apply_grid_size()

    def thumbnail_size(self) -> int:
        if self._gallery_model is not None:
            return self._gallery_model.thumbnail_size
        return 180

    def _apply_grid_size(self) -> None:
        if self._gallery_model is None:
            return
        size = self._gallery_model.thumbnail_size
        # Room around the icon for spacing plus a filename line (§2.14A).
        self.setIconSize(QSize(size, size))
        self.setGridSize(QSize(size + 16, size + 16 + 14))

    # ------------------------------------------------------------------
    # Selection helpers (§2.4)
    # ------------------------------------------------------------------

    def selected_paths(self) -> list[str]:
        """Paths of the currently selected rows, in row order."""
        if self._gallery_model is None:
            return []
        sm = self.selectionModel()
        if sm is None:
            return []
        seen: set[int] = set()
        out: list[str] = []
        for index in sm.selectedIndexes():
            row = index.row()
            if row in seen:
                continue
            seen.add(row)
            path = self._gallery_model.path_at(row)
            if path is not None:
                out.append(path)
        return out

    def select_all(self) -> None:
        sm = self.selectionModel()
        if sm is not None and self._gallery_model is not None:
            n = self._gallery_model.rowCount()
            if n == 0:
                return
            selection = QItemSelection(
                self._gallery_model.index(0, 0),
                self._gallery_model.index(n - 1, 0),
            )
            sm.select(
                selection, sm.SelectionFlag.ClearAndSelect | sm.SelectionFlag.Rows
            )

    def clear_selection(self) -> None:
        sm = self.selectionModel()
        if sm is not None:
            sm.clearSelection()

    def jump_to_path(self, path: str) -> bool:
        """Scroll to the row for *path* (returns False if unknown)."""
        if self._gallery_model is None:
            return False
        row = self._gallery_model.row_for_path(path)
        if row < 0:
            return False
        self.scrollTo(self._gallery_model.index(row, 0), QListView.ScrollHint.PositionAtCenter)
        return True

    def reset_prefetch(self) -> None:
        """Clear the prefetch dedup state so the next scroll event re-prefetches."""
        self._last_prefetched_range = (-1, -1)

    # ------------------------------------------------------------------
    # Scroll prefetch
    # ------------------------------------------------------------------

    def _on_scrolled(self, *_args) -> None:
        self._prefetch_visible()

    def _prefetch_visible(self) -> None:
        if self._gallery_model is None:
            return
        lo, hi = self._visible_row_range(self._prefetch_buffer)
        if lo < 0 or hi < 0:
            return
        if (lo, hi) == self._last_prefetched_range:
            return
        self._last_prefetched_range = (lo, hi)
        for row in range(lo, hi + 1):
            path = self._gallery_model.path_at(row)
            if path is not None:
                self._gallery_model.prefetch(path)

    def _visible_row_range(self, buffer: int) -> tuple[int, int]:
        """Estimate the min/max visible row from viewport corner samples.

        Sampling several x/y points (not just the corners) is deliberate:
        with wrapping IconMode the bottom-right of the viewport can land on a
        different column than the last visible row, so corner-only sampling
        can under-report the visible tail.
        """
        if self._gallery_model is None or self._gallery_model.rowCount() == 0:
            return (-1, -1)
        vp = self.viewport()
        rect = vp.rect()
        if rect.isEmpty():
            return (-1, -1)
        xs = [1, rect.center().x(), rect.right() - 1]
        ys = [1, rect.center().y(), rect.bottom() - 1]
        rows: list[int] = []
        for x in xs:
            for y in ys:
                index = self.indexAt(QPoint(x, y))
                if index.isValid():
                    rows.append(index.row())
        if not rows:
            return (-1, -1)
        lo = max(0, min(rows) - buffer)
        hi = min(self._gallery_model.rowCount() - 1, max(rows) + buffer)
        return lo, hi

    # ------------------------------------------------------------------
    # Signal forwarding (ClickableLabel parity)
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos: QPoint) -> None:
        if self._gallery_model is None:
            return
        index = self.indexAt(pos)
        if index.isValid():
            path = self._gallery_model.path_at(index.row())
            if path is not None:
                self.path_right_clicked.emit(self.viewport().mapToGlobal(pos), path)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if self._gallery_model is not None and index.isValid():
            path = self._gallery_model.path_at(index.row())
            if path is not None:
                self.path_activated.emit(path)

    def _on_pressed(self, index: QModelIndex) -> None:
        if self._gallery_model is not None and index.isValid():
            path = self._gallery_model.path_at(index.row())
            if path is not None:
                self.path_clicked.emit(path)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ctrl_wheel.emit(event.angleDelta().y())
            event.accept()
        else:
            super().wheelEvent(event)

    # ------------------------------------------------------------------
    # Drag-to-drop (opt-in) — press an item, drag past a threshold to start
    # a native ``QDrag`` carrying the selected file URLs. Used by the
    # wallpaper tabs to drop a thumbnail onto a monitor or the graph view,
    # both of which already accept ``text/uri-list`` drops. Disabled for
    # every other tab.
    #
    # This deliberately uses ``QDrag`` rather than ``grabMouse()`` + a
    # floating preview window: on Wayland ``QWidget.grabMouse()`` is a no-op
    # for non-popup widgets ("This plugin supports grabbing the mouse only
    # for popup windows"), which left the drag half-started and every
    # subsequent click in the app routed to a widget that never got its
    # release — the app went unclickable (but not frozen). The compositor
    # owns the DnD grab for ``QDrag``, so it works on both X11 and Wayland.
    # ------------------------------------------------------------------

    _CUSTOM_DRAG_THRESHOLD = 8

    def set_custom_drag_enabled(self, enabled: bool, drop_handler=None) -> None:
        """Enable/disable drag-to-drop. ``drop_handler`` is accepted for
        backward compatibility but no longer used — the drop targets resolve
        the drop natively via their own ``dropEvent``."""
        self._custom_drag_enabled = bool(enabled)
        self._custom_drop_handler = drop_handler
        self._drag_source_path: Optional[str] = None
        self._drag_press_pos: Optional[QPoint] = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if (
            getattr(self, "_custom_drag_enabled", False)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            index = self.indexAt(event.position().toPoint())
            if index.isValid() and self._gallery_model is not None:
                self._drag_source_path = self._gallery_model.path_at(index.row())
                self._drag_press_pos = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        enabled = getattr(self, "_custom_drag_enabled", False)
        if enabled and self._drag_source_path and self._drag_press_pos is not None:
            moved = event.position().toPoint() - self._drag_press_pos
            if (
                event.buttons() & Qt.MouseButton.LeftButton
                and abs(moved.x()) + abs(moved.y()) > self._CUSTOM_DRAG_THRESHOLD
            ):
                self._start_custom_drag()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # A click on empty viewport space should clear the current selection
        # unless the user is extending it (marquee / modifier-held) — the
        # QLabel galleries treat blank-area clicks as "deselect everything".
        if (
            self._gallery_model is not None
            and not self.indexAt(event.position().toPoint()).isValid()
            and not (event.modifiers()
                     & (Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.ShiftModifier))
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.clear_selection()
        super().mouseReleaseEvent(event)

    def _start_custom_drag(self) -> None:
        source = self._drag_source_path
        selected = self.selected_paths()
        paths = [p for p in (selected if source in selected else [source]) if p]
        pm = self._drag_preview_pixmap(source)
        # Consume the press state up front: QDrag.exec() runs its own nested
        # event loop, so these must not linger to re-trigger on the way out.
        self._drag_source_path = None
        self._drag_press_pos = None
        if not paths:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        drag.setMimeData(mime)
        if not pm.isNull():
            pm = pm.scaled(
                120,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            drag.setPixmap(pm)
            drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        # Qt releases the source widget's left-button state while a native
        # drag is active. Tell Wallpaper's application event filter that a
        # drag is nevertheless in progress so its scroll area can still
        # consume wheel events while the pointer is over a monitor target.
        application = QApplication.instance()
        previous_drag_scroll = (
            application.property("image_toolkit_drag_scroll_active")
            if application is not None
            else None
        )
        if application is not None:
            application.setProperty("image_toolkit_drag_scroll_active", True)
        try:
            drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
        finally:
            if application is not None:
                application.setProperty(
                    "image_toolkit_drag_scroll_active", previous_drag_scroll
                )
        # QDrag.exec() runs a nested loop and swallows the mouse-release the
        # QListView was waiting on, so the view is left mid-press — the next
        # move would paint a rubber-band marquee. Mirror QAbstractItemView::
        # startDrag() and clear the interaction state.
        self.setState(QAbstractItemView.State.NoState)

    def _drag_preview_pixmap(self, path: Optional[str]) -> QPixmap:
        """Thumbnail pixmap for the dragged item, or a null pixmap."""
        model = self._gallery_model
        if model is not None and path is not None:
            cached = model.cached_image(path)
            if cached is not None and not cached.isNull():
                return QPixmap.fromImage(cached)
        return QPixmap()


__all__ = ["VirtualGalleryView"]
