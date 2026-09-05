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

import os
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import (
    QEvent,
    QItemSelection,
    QMimeData,
    QModelIndex,
    QPoint,
    QSize,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QCursor,
    QDrag,
    QKeyEvent,
    QMouseEvent,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QInputDialog,
    QListView,
    QMessageBox,
)

from .delegate import VirtualGalleryDelegate
from .presentation_mode import (
    GalleryOverlayConfig,
    GalleryPresentationMode,
)

if TYPE_CHECKING:
    from .virtual_gallery_model import VirtualGalleryModel


class VirtualGalleryView(QListView):
    """Icon-mode list view with prefetch-on-scroll and gallery-style signals."""

    path_clicked = Signal(str)
    path_activated = Signal(str)
    path_right_clicked = Signal(QPoint, str)
    path_renamed = Signal(str, str)
    ctrl_wheel = Signal(int)

    def __init__(self, parent=None, prefetch_buffer: int = 40):
        super().__init__(parent)
        self._prefetch_buffer = prefetch_buffer
        self._last_prefetched_range: tuple[int, int] = (-1, -1)

        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        # IconMode must fill rows before wrapping downward. TopToBottom fills
        # the viewport height first, then puts the remaining items in
        # horizontal columns outside the visible gallery.
        self.setFlow(QListView.Flow.LeftToRight)
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

    def set_presentation_mode(self, mode: GalleryPresentationMode) -> None:
        """Switch between Uniform Grid, Masonry, and Compact List view modes (§2.40)."""
        self._presentation_mode = mode
        if mode == GalleryPresentationMode.COMPACT_LIST:
            self.setViewMode(QListView.ViewMode.ListMode)
            self.setFlow(QListView.Flow.TopToBottom)
            self.setWrapping(False)
            self.setGridSize(QSize())
            self.setIconSize(QSize(48, 48))
        elif mode == GalleryPresentationMode.MASONRY:
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setFlow(QListView.Flow.LeftToRight)
            self.setWrapping(True)
            self.setUniformItemSizes(False)
            if self._gallery_model is not None:
                size = self._gallery_model.thumbnail_size
                self.setIconSize(QSize(size, size))
                self.setGridSize(QSize(size + 12, size + 40))
        else:  # UNIFORM_GRID
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setFlow(QListView.Flow.LeftToRight)
            self.setWrapping(True)
            self.setUniformItemSizes(True)
            self._apply_grid_size()
        self.viewport().update()

    def set_overlay_config(self, config: GalleryOverlayConfig) -> None:
        """Configure thumbnail overlay badges on the item delegate."""
        delegate = self.itemDelegate()
        if isinstance(delegate, VirtualGalleryDelegate):
            delegate.set_overlay_config(config)
            self.viewport().update()

    @property
    def presentation_mode(self) -> GalleryPresentationMode:
        return getattr(self, "_presentation_mode", GalleryPresentationMode.UNIFORM_GRID)

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

    def invert_selection(self) -> None:
        """Invert the selection across all gallery items (§2.4E)."""
        if self._gallery_model is None:
            return
        n = self._gallery_model.rowCount()
        if n == 0:
            return
        sm = self.selectionModel()
        if sm is not None:
            selection = QItemSelection(
                self._gallery_model.index(0, 0),
                self._gallery_model.index(n - 1, 0),
            )
            sm.select(
                selection, sm.SelectionFlag.Toggle | sm.SelectionFlag.Rows
            )


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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        from gui.src.utils.manager.shortcut_manager import get_registry
        from gui.src.utils.undo_manager import UndoManager

        reg = get_registry()
        if reg.matches(event, "gallery.rename") or event.key() == Qt.Key.Key_F2:
            self.rename_selected_file()
            event.accept()
        elif reg.matches(event, "gallery.select_all"):
            self.select_all()
            event.accept()
        elif reg.matches(event, "gallery.deselect_all"):
            self.clear_selection()
            event.accept()
        elif reg.matches(event, "gallery.invert_selection"):
            self.invert_selection()
            event.accept()
        elif reg.matches(event, "general.undo"):
            UndoManager.instance().undo()
            event.accept()
        elif reg.matches(event, "general.redo"):
            UndoManager.instance().redo()
            event.accept()
        else:
            super().keyPressEvent(event)


    def rename_selected_file(self) -> Optional[str]:
        """Trigger inline rename on the active/selected gallery item via F2 (§2.26)."""
        selected = self.selected_paths()
        target = selected[0] if selected else None
        if target is None and self._gallery_model and self._gallery_model.rowCount() > 0:
            target = self._gallery_model.path_at(0)
        if not target or not os.path.exists(target):
            return None

        old_name = os.path.basename(target)
        stem, ext = os.path.splitext(old_name)
        new_stem, ok = QInputDialog.getText(
            self, "Rename File (F2)", "New filename (without extension):", text=stem
        )
        if not ok or not new_stem.strip() or new_stem.strip() == stem:
            return None

        new_stem = new_stem.strip()
        for ch in r'\/:*?"<>|':
            new_stem = new_stem.replace(ch, "_")

        new_path = os.path.join(os.path.dirname(target), new_stem + ext)
        if os.path.exists(new_path):
            QMessageBox.warning(
                self, "Rename Conflict", f"A file named '{new_stem + ext}' already exists."
            )
            return None

        try:
            from gui.src.utils.undo_manager import UndoManager

            def _on_renamed(old_p: str, new_p: str) -> None:
                if self._gallery_model:
                    self._gallery_model.rename_path(old_p, new_p)
                self.path_renamed.emit(old_p, new_p)

            UndoManager.instance().rename_file_undoable(
                old_path=target,
                new_path=new_path,
                on_renamed=_on_renamed,
            )
            return new_path
        except Exception as exc:
            QMessageBox.critical(self, "Rename Error", str(exc))
            return None

    # ------------------------------------------------------------------
    # Drag-to-drop (opt-in). Wallpaper supplies an in-app drop resolver, so
    # its drag uses an application event filter: unlike native Wayland DnD,
    # this preserves wheel events while moving between the gallery and monitor
    # cards. Handler-less callers retain a native QDrag fallback.
    # ------------------------------------------------------------------

    _CUSTOM_DRAG_THRESHOLD = 8

    def set_custom_drag_enabled(self, enabled: bool, drop_handler=None) -> None:
        """Enable/disable drag-to-drop. ``drop_handler`` is accepted for
        the in-app Wallpaper drop target resolver."""
        if getattr(self, "_manual_drag_active", False):
            self._end_manual_drag(drop=False)
        self._custom_drag_enabled = bool(enabled)
        self._custom_drop_handler = drop_handler
        self._drag_source_path: Optional[str] = None
        self._drag_press_pos: Optional[QPoint] = None
        self._manual_drag_active = False
        self._manual_drag_source: Optional[str] = None
        self._manual_drag_paths: list[str] = []
        self._drag_preview_window = None
        self._previous_drag_scroll_property = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if (
            getattr(self, "_custom_drag_enabled", False)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            # Clear any pending-drag state left over from a prior click that
            # never crossed the threshold; only a press on an item re-arms it.
            # Otherwise a later press on blank space would inherit a stale
            # source path and be treated as a drag instead of a marquee.
            self._drag_source_path = None
            self._drag_press_pos = None
            index = self.indexAt(event.position().toPoint())
            if index.isValid() and self._gallery_model is not None:
                self._drag_source_path = self._gallery_model.path_at(index.row())
                self._drag_press_pos = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if getattr(self, "_manual_drag_active", False):
            # A manual (in-app) drag is in flight; the application event
            # filter owns the gesture. Forwarding to the base class here
            # would let QAbstractItemView enter DragSelectingState and paint
            # a rubber band under the running drag.
            return
        enabled = getattr(self, "_custom_drag_enabled", False)
        if (
            enabled
            and self._drag_source_path
            and self._drag_press_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            # Press landed on a thumbnail: this gesture is a drag-the-item,
            # never a marquee. Swallow every move (not just post-threshold
            # ones) so the base class never starts a rubber-band selection
            # on an item press. Blank-space presses leave _drag_source_path
            # unset and still fall through to the marquee below.
            moved = event.position().toPoint() - self._drag_press_pos
            if abs(moved.x()) + abs(moved.y()) > self._CUSTOM_DRAG_THRESHOLD:
                self._start_custom_drag()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        # A plain click on an item that never reached the drag threshold:
        # drop the armed drag state so it can't leak into the next gesture.
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_source_path = None
            self._drag_press_pos = None
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

        if callable(self._custom_drop_handler):
            self._begin_manual_drag(source, paths, pm)
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
        # Preserve the shared drag-active marker for handler-less callers that
        # also install an application wheel filter.
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

    def _begin_manual_drag(self, source: str, paths: list[str], pixmap: QPixmap) -> None:
        """Start an in-app drag without Qt's native DnD event loop.

        Wayland's native drag owns the pointer and consumes wheel events before
        QApplication can route them. Wallpaper drops are entirely in-app, so an
        application event filter can preserve wheel scrolling and still resolve
        the release target by global position.
        """
        if self._manual_drag_active:
            self._end_manual_drag(drop=False)
        # Clear whatever interaction state the press left behind so the base
        # class isn't mid-gesture (rubber band) once the manual drag ends.
        self.setState(QAbstractItemView.State.NoState)
        self._manual_drag_active = True
        self._manual_drag_source = source
        self._manual_drag_paths = list(paths)

        app = QApplication.instance()
        if app is not None:
            self._previous_drag_scroll_property = app.property(
                "image_toolkit_drag_scroll_active"
            )
            app.setProperty("image_toolkit_drag_scroll_active", True)
            app.installEventFilter(self)

        if not pixmap.isNull():
            from gui.src.windows.drag_preview_window import DragPreviewWindow

            preview = pixmap.scaled(
                120,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._drag_preview_window = DragPreviewWindow(preview)
            self._drag_preview_window.update_position(QCursor.pos())
            self._drag_preview_window.show()

    def eventFilter(self, watched, event):
        if not getattr(self, "_manual_drag_active", False):
            return super().eventFilter(watched, event)

        event_type = event.type()
        if event_type == QEvent.Type.Wheel:
            pixel_delta = event.pixelDelta().y()
            delta = pixel_delta or event.angleDelta().y()
            if self._scroll_active_drag(delta):
                event.accept()
                return True
        elif event_type == QEvent.Type.MouseMove:
            if not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
                self._end_manual_drag(drop=False)
                return False
            global_pos = self._event_global_pos(event)
            if self._drag_preview_window is not None:
                self._drag_preview_window.update_position(global_pos)
            owner = self._wallpaper_scroll_owner()
            if owner is not None and hasattr(owner, "_handle_autoscroll"):
                owner._handle_autoscroll(global_pos)
        elif event_type == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self._end_manual_drag(drop=True, global_pos=self._event_global_pos(event))
                event.accept()
                return True
        elif event_type == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self._end_manual_drag(drop=False)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _wallpaper_scroll_owner(self):
        current = self.parentWidget()
        while current is not None:
            if getattr(current, "main_scroll_area", None) is not None:
                return current
            current = current.parentWidget()
        return None

    def _scroll_active_drag(self, delta_y: int) -> bool:
        if not delta_y:
            return False
        owner = self._wallpaper_scroll_owner()
        scroll_area = getattr(owner, "main_scroll_area", None) if owner else None
        bar = scroll_area.verticalScrollBar() if scroll_area is not None else None
        if bar is None or bar.maximum() <= bar.minimum():
            bar = self.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            return False
        old_value = bar.value()
        bar.setValue(old_value - delta_y)
        return bar.value() != old_value

    @staticmethod
    def _event_global_pos(event) -> QPoint:
        global_position = getattr(event, "globalPosition", None)
        if callable(global_position):
            return global_position().toPoint()
        return QCursor.pos()

    def _end_manual_drag(
        self, *, drop: bool, global_pos: Optional[QPoint] = None
    ) -> None:
        if not getattr(self, "_manual_drag_active", False):
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
            app.setProperty(
                "image_toolkit_drag_scroll_active",
                self._previous_drag_scroll_property,
            )

        source = self._manual_drag_source
        paths = list(self._manual_drag_paths)
        preview = self._drag_preview_window
        self._manual_drag_active = False
        self._manual_drag_source = None
        self._manual_drag_paths.clear()
        self._drag_preview_window = None
        self._previous_drag_scroll_property = None
        if preview is not None:
            preview.close()
            preview.deleteLater()

        self.setState(QAbstractItemView.State.NoState)
        if drop and source and callable(self._custom_drop_handler):
            self._custom_drop_handler(source, paths, global_pos or QCursor.pos())

    def closeEvent(self, event) -> None:
        self._end_manual_drag(drop=False)
        super().closeEvent(event)

    def _drag_preview_pixmap(self, path: Optional[str]) -> QPixmap:
        """Thumbnail pixmap for the dragged item, or a null pixmap."""
        model = self._gallery_model
        if model is not None and path is not None:
            cached = model.cached_image(path)
            if cached is not None and not cached.isNull():
                return QPixmap.fromImage(cached)
        return QPixmap()


__all__ = ["VirtualGalleryView"]
