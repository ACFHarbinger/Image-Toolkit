"""Dual-panel virtual-scrolling gallery composite — GUI/UX §2.1 & §2.4 (Found + Selected).

Provides a unified model/view composite replacing the two-gallery QLabel-grid
architecture (``AbstractClassTwoGalleries``) with two linked virtualized
galleries (Found + Selected) sharing a single ``LRUImageCache`` and coordinated
selection/filtering state without page caps or sequential layout rebuilds.
"""

from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import QPoint, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.tag_chip_widget import FlowLayout
from gui.src.components.widgets.thumbnail_zoom_control import ThumbnailZoomControl
from gui.src.utils.cache.lru_image_cache import LRUImageCache

from .widget import VirtualGallery


class VirtualDualGallery(QWidget):
    """Composed dual-gallery widget: Found (top/left) + Selected (bottom/right)."""

    found_clicked = Signal(str)
    found_activated = Signal(str)
    found_right_clicked = Signal(QPoint, str)
    selected_clicked = Signal(str)
    selected_activated = Signal(str)
    selected_right_clicked = Signal(QPoint, str)
    selection_changed = Signal()
    compare_requested = Signal(list)

    def __init__(
        self,
        parent=None,
        cache_maxsize: int = 500,
        worker_factory: Optional[Callable[[], QThread]] = None,
        persistence_key: Optional[str] = "VirtualDualGallery/main_splitter",
        orientation: Qt.Orientation = Qt.Orientation.Vertical,
    ):
        super().__init__(parent)
        self._persistence_key = persistence_key
        self._shared_cache = LRUImageCache(maxsize=cache_maxsize)
        self._worker_factory = worker_factory

        self._master_found_paths: List[str] = []
        self._filtered_found_paths: List[str] = []
        self._selected_paths: List[str] = []

        self._build_ui(orientation)
        if self._persistence_key:
            try:
                from gui.src.windows.settings.splitter_persistence import persist_splitter
                persist_splitter(self.splitter, self._persistence_key)
            except Exception:
                pass
        if hasattr(self, "zoom_control"):
            self.set_thumbnail_size(self.zoom_control.current_size)

    def _build_ui(self, orientation: Qt.Orientation):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.splitter = QSplitter(orientation, self)

        # --- 1. Found Panel (Master / Scan Results) ---
        self.found_panel = QWidget(self)
        found_layout = QVBoxLayout(self.found_panel)
        found_layout.setContentsMargins(4, 4, 4, 4)
        found_layout.setSpacing(4)

        # Found Header & Controls
        # FlowLayout: label + search box + button still clip at this pane's
        # width at the app's 800px minimum (the search box's minimum size
        # floor is wider than the leftover space once the button is
        # accounted for) -- wrap instead of hard-clipping. Built with an
        # explicit parent container (addWidget, not addLayout) -- a bare
        # FlowLayout() added later via addLayout() can intermittently never
        # settle to its real geometry, leaving widgets at Qt's raw
        # top-level default size (640x480) instead of their laid-out size.
        found_header_container = QWidget()
        found_header = FlowLayout(found_header_container)
        found_header.setSpacing(6)
        self.lbl_found_title = QLabel("Found (0)")
        self.lbl_found_title.setStyleSheet("font-weight: bold; color: #dcddde;")

        self.txt_found_search = QLineEdit()
        self.txt_found_search.setPlaceholderText("Filter found images…")
        self.txt_found_search.setClearButtonEnabled(True)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self.txt_found_search.textChanged.connect(self._search_timer.start)

        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all)

        found_header.addWidget(self.lbl_found_title)
        found_header.addWidget(self.txt_found_search)
        found_header.addWidget(self.btn_select_all)

        # Zoom Control (§2.2 Options A, C, D)
        parent_class = self.parent().__class__.__name__ if self.parent() else None
        self.zoom_control = ThumbnailZoomControl(class_name=parent_class, parent=self.found_panel)
        self.zoom_control.size_changed.connect(self.set_thumbnail_size)
        found_header.addWidget(self.zoom_control)

        found_layout.addWidget(found_header_container)

        # Found Virtual Gallery
        self.found_gallery = VirtualGallery(
            parent=self.found_panel,
            shared_cache=self._shared_cache,
            worker_factory=self._worker_factory,
        )
        self.found_gallery.path_clicked.connect(self._on_found_card_clicked)
        self.found_gallery.path_activated.connect(self.found_activated)
        self.found_gallery.path_right_clicked.connect(self.found_right_clicked)
        self.found_gallery.ctrl_wheel.connect(self._on_ctrl_wheel)
        found_layout.addWidget(self.found_gallery, 1)

        # --- 2. Selected Panel (User Staged / Reordered Subset) ---
        self.selected_panel = QWidget(self)
        selected_layout = QVBoxLayout(self.selected_panel)
        selected_layout.setContentsMargins(4, 4, 4, 4)
        selected_layout.setSpacing(4)

        # Selected Header & Controls
        # FlowLayout, not QHBoxLayout: this pane is one half of a splitter,
        # narrower than the full window -- the title + 2 buttons with no
        # shrinkable widget between them clip at the app's 800px minimum
        # width (splitter pane narrower still). FlowLayout wraps instead.
        # Parented container, see found_header's comment above for why.
        selected_header_container = QWidget()
        selected_header = FlowLayout(selected_header_container)
        selected_header.setSpacing(6)
        self.lbl_selected_title = QLabel("Selected (0)")
        self.lbl_selected_title.setStyleSheet("font-weight: bold; color: #dcddde;")

        self.btn_compare = QPushButton("Compare (0)")
        self.btn_compare.setEnabled(False)
        self.btn_compare.clicked.connect(self.compare_selected)

        self.btn_clear_selection = QPushButton("Clear Selection")
        self.btn_clear_selection.clicked.connect(self.deselect_all)

        selected_header.addWidget(self.lbl_selected_title)
        selected_header.addWidget(self.btn_compare)
        selected_header.addWidget(self.btn_clear_selection)
        selected_layout.addWidget(selected_header_container)

        # Selected Virtual Gallery
        self.selected_gallery = VirtualGallery(
            parent=self.selected_panel,
            shared_cache=self._shared_cache,
            worker_factory=self._worker_factory,
        )
        self.selected_gallery.path_clicked.connect(self.selected_clicked)
        self.selected_gallery.path_activated.connect(self.selected_activated)
        self.selected_gallery.path_right_clicked.connect(self.selected_right_clicked)
        self.selected_gallery.ctrl_wheel.connect(self._on_ctrl_wheel)
        selected_layout.addWidget(self.selected_gallery, 1)

        self.splitter.addWidget(self.found_panel)
        self.splitter.addWidget(self.selected_panel)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

        root_layout.addWidget(self.splitter)

    # ------------------------------------------------------------------
    # Data & Selection API
    # ------------------------------------------------------------------

    def set_found_paths(self, paths: List[str]) -> None:
        """Set the master found files and update the found gallery view."""
        self._master_found_paths = list(paths)
        self._apply_search_filter()

    def set_selected_paths(self, paths: List[str]) -> None:
        """Set the selected files subset and update the selected gallery view."""
        self._selected_paths = list(paths)
        self._refresh_selected_view()
        self._sync_selected_marks()
        self.selection_changed.emit()

    def found_paths(self) -> List[str]:
        return list(self._filtered_found_paths)

    def master_found_paths(self) -> List[str]:
        return list(self._master_found_paths)

    def selected_paths(self) -> List[str]:
        return list(self._selected_paths)

    def selected_files(self) -> List[str]:
        """Alias matching AbstractClassTwoGalleries.selected_files."""
        return self.selected_paths()

    def count_found(self) -> int:
        return len(self._filtered_found_paths)

    def count_selected(self) -> int:
        return len(self._selected_paths)

    @Slot(str)
    def _on_found_card_clicked(self, path: str):
        self.found_clicked.emit(path)
        self.toggle_selection(path)

    def toggle_selection(self, path: str) -> bool:
        """Toggle selection of a path: returns True if now selected, False if deselected."""
        if path in self._selected_paths:
            self._selected_paths.remove(path)
            selected = False
        else:
            self._selected_paths.append(path)
            selected = True

        self._refresh_selected_view()
        self._sync_selected_marks()
        self.selection_changed.emit()
        return selected

    def select_all(self) -> None:
        """Select all paths currently visible in the filtered found gallery."""
        changed = False
        for p in self._filtered_found_paths:
            if p not in self._selected_paths:
                self._selected_paths.append(p)
                changed = True
        if changed:
            self._refresh_selected_view()
            self._sync_selected_marks()
            self.selection_changed.emit()

    def deselect_all(self) -> None:
        """Clear all selected files."""
        if self._selected_paths:
            self._selected_paths.clear()
            self._refresh_selected_view()
            self._sync_selected_marks()
            self.selection_changed.emit()

    def remove_selected(self, path: str) -> None:
        if path in self._selected_paths:
            self._selected_paths.remove(path)
            self._refresh_selected_view()
            self._sync_selected_marks()
            self.selection_changed.emit()

    # ------------------------------------------------------------------
    # Filtering & UI Refresh
    # ------------------------------------------------------------------

    def _apply_search_filter(self):
        query = self.txt_found_search.text().strip().lower()
        if not query:
            self._filtered_found_paths = list(self._master_found_paths)
        else:
            self._filtered_found_paths = [
                p for p in self._master_found_paths
                if query in os.path.basename(p).lower()
            ]

        self.found_gallery.set_paths(self._filtered_found_paths)
        self.lbl_found_title.setText(f"Found ({len(self._filtered_found_paths):,})")
        self._sync_selected_marks()

    def _refresh_selected_view(self):
        self.selected_gallery.set_paths(self._selected_paths)
        count = len(self._selected_paths)
        self.lbl_selected_title.setText(f"Selected ({count:,})")
        self.btn_compare.setEnabled(count >= 2)
        self.btn_compare.setText(f"Compare ({count}) (C)" if count >= 2 else "Compare (C)")

    def _sync_selected_marks(self):
        """Apply the current selection (indigo border) to the found rows and to
        every row in the Selected panel, matching the classic QLabel-grid styling."""
        self.found_gallery.set_selected(self._selected_paths)
        self.selected_gallery.set_selected(self._selected_paths)

    def set_preview(self, paths: List[str]) -> None:
        """Mark the full set of preview-open paths (amber border) on both panels."""
        self.found_gallery.set_preview(paths)
        self.selected_gallery.set_preview(paths)

    def _on_ctrl_wheel(self, delta: int) -> None:
        """Step thumbnail zoom on Ctrl+wheel (§2.2 Option B)."""
        steps = 1 if delta > 0 else -1
        if hasattr(self, "zoom_control") and self.zoom_control is not None:
            self.zoom_control.step_zoom(steps)
        else:
            cur = self.found_gallery.thumbnail_size
            self.set_thumbnail_size(max(48, min(512, cur + (steps * 16))))

    # ------------------------------------------------------------------
    # Gallery Management & Actions
    # ------------------------------------------------------------------

    def set_thumbnail_size(self, size: int) -> None:
        self.found_gallery.set_thumbnail_size(size)
        self.selected_gallery.set_thumbnail_size(size)
        if (
            hasattr(self, "zoom_control")
            and self.zoom_control is not None
            and self.zoom_control.current_size != size
        ):
            self.zoom_control.set_size(size, save=False)

    def cancel_loading(self) -> None:
        self.found_gallery.cancel_loading()
        self.selected_gallery.cancel_loading()

    def clear_cache(self) -> None:
        self._shared_cache.clear()
        self.found_gallery.clear_cache()
        self.selected_gallery.clear_cache()

    def clear(self) -> None:
        self._master_found_paths.clear()
        self._filtered_found_paths.clear()
        self._selected_paths.clear()
        self.found_gallery.clear()
        self.selected_gallery.clear()
        self.lbl_found_title.setText("Found (0)")
        self.lbl_selected_title.setText("Selected (0)")
        self.btn_compare.setEnabled(False)

    def compare_selected(self, parent=None):
        """Open an ImageCompareWindow for the currently selected files (§2.27)."""
        if len(self._selected_paths) < 2:
            return None
        from gui.src.windows.image_compare_window import ImageCompareWindow
        win = ImageCompareWindow(image_paths=self._selected_paths, parent=parent or self)
        win.show()
        self.compare_requested.emit(self._selected_paths)
        return win


__all__ = ["VirtualDualGallery"]
