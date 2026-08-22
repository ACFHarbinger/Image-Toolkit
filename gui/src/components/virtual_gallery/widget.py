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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = VirtualGalleryModel(self)
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
        self.view.reset_prefetch()
        self.view._prefetch_visible()

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

    def compare_selected(self, parent=None):
        """Open an ImageCompareWindow for the currently selected files (§2.27)."""
        selected = self.selected_files()
        if len(selected) < 2:
            return None
        from ...windows import ImageCompareWindow
        win = ImageCompareWindow(image_paths=selected, parent=parent or self)
        win.show()
        return win


__all__ = ["VirtualGallery"]
