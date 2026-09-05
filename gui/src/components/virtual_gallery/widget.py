"""Tab-facing composite for the virtualized gallery — GUI/UX §2.1 Option A.

Owns a :class:`VirtualGalleryModel` + :class:`VirtualGalleryView` and exposes
the small API a gallery tab needs (``set_paths``, ``set_thumbnail_size``,
``selected_files``, ``cancel_loading``, …) plus the interaction signals the
QLabel galleries provided via ``ClickableLabel``/``MarqueeScrollArea``. This
is the drop-in surface the §2.1 adoption path builds on — the QLabel-grid
gallery base classes stay untouched until a tab is migrated to this widget.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .virtual_gallery_model import VirtualGalleryModel
from .virtual_gallery_view import VirtualGalleryView


class VirtualGallery(QWidget):
    """Composed virtual-scrolling gallery: model + view behind a gallery API."""

    path_clicked = Signal(str)
    path_activated = Signal(str)
    path_right_clicked = Signal(QPoint, str)
    ctrl_wheel = Signal(int)
    selection_changed = Signal()

    def __init__(
        self,
        parent=None,
        shared_cache=None,
        worker_factory=None,
        max_concurrent_loads: int = 2,
    ):
        super().__init__(parent)
        self.model = VirtualGalleryModel(
            self,
            shared_cache=shared_cache,
            worker_factory=worker_factory,
            max_concurrent_loads=max_concurrent_loads,
        )
        self.view = VirtualGalleryView(self)
        self.view.setModel(self.model)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.view)

        self.view.path_clicked.connect(self.path_clicked)
        self.view.path_activated.connect(self.path_activated)
        self.view.path_right_clicked.connect(self.path_right_clicked)
        self.view.ctrl_wheel.connect(self.ctrl_wheel)
        self.view.selectionModel().selectionChanged.connect(
            lambda *_: self.selection_changed.emit()
        )

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Gallery API (mirrors the pieces tabs use from the QLabel galleries)
    # ------------------------------------------------------------------

    def set_paths(self, paths) -> None:
        """Replace the item list and reset the scroll position."""
        self.model.set_paths(paths)
        self.view.scrollToTop()
        # Report the initial visible range so _fill_all can reorder for
        # visible-first dispatch (issue #522).  fill() must come after
        # set_visible_range so the queue is ordered correctly.
        self.view.reset_prefetch()
        self.view._prefetch_visible()
        self.model.fill()

    def clear(self) -> None:
        self.model.set_paths([])

    def count(self) -> int:
        return self.model.rowCount()

    @property
    def thumbnail_size(self) -> int:
        return self.model.thumbnail_size

    def set_thumbnail_size(self, size: int) -> None:
        self.view.set_thumbnail_size(size)

    def selected_files(self) -> list[str]:
        return self.view.selected_paths()

    def select_all(self) -> None:
        self.view.select_all()

    def clear_selection(self) -> None:
        self.view.clear_selection()

    def jump_to_path(self, path: str) -> bool:
        return self.view.jump_to_path(path)

    def cancel_loading(self) -> None:
        self.model.cancel_loading()

    def clear_cache(self) -> None:
        self.model.clear_cache()

    def cached_image(self, path: str):
        """Return the model's cached QImage for *path* (None if not loaded)."""
        return self.model.cached_image(path)

    # --- State marks (selected / preview-open) ---------------------------

    def set_in_db(self, paths) -> None:
        """Mark the full set of paths with the green in-db/queued border."""
        self.model.set_in_db(paths)

    def mark_in_db(self, path: str, in_db: bool) -> None:
        self.model.mark_in_db(path, in_db)

    def is_in_db(self, path: str) -> bool:
        return self.model.is_in_db(path)

    def set_selected(self, paths) -> None:
        """Mark the full set of selected paths (indigo border)."""
        self.model.set_selected(paths)

    def mark_selected(self, path: str, selected: bool) -> None:
        self.model.mark_selected(path, selected)

    def set_preview(self, paths) -> None:
        """Mark the full set of preview-open paths (amber border)."""
        self.model.set_preview(paths)

    def mark_preview(self, path: str, preview: bool) -> None:
        self.model.mark_preview(path, preview)

    def is_preview(self, path: str) -> bool:
        return self.model.is_preview(path)

    def compare_selected(self, parent=None):
        """Open an ImageCompareWindow for the currently selected files (§2.27)."""
        selected = self.selected_files()
        if len(selected) < 2:
            return None
        from ...windows.image_compare_window import ImageCompareWindow
        win = ImageCompareWindow(image_paths=selected, parent=parent or self)
        win.show()
        return win


__all__ = ["VirtualGallery"]
