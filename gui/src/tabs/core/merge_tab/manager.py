"""``MergeTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ....classes import AbstractClassSingleGallery
from ....components import ClickableLabel
from ....helpers import ImageScannerWorker, MergeWorker
from ._canvas_controls import _CanvasControlsMixin
from ._config_persistence import _ConfigPersistenceMixin
from ._lifecycle_qml import _LifecycleQmlMixin
from ._merge_execution import _MergeExecutionMixin
from ._preview_context import _PreviewContextMixin
from ._scan_input import _ScanInputMixin
from ._ui_config import _UIConfigMixin
from ._ui_gallery_canvas import _UIGalleryCanvasMixin


class MergeTab(
    # Mixins MUST precede AbstractClassSingleGallery in MRO order: several
    # mixin methods (_LifecycleQmlMixin.closeEvent/cancel_loading) override
    # same-named methods AbstractClassSingleGallery itself defines, and
    # Python's C3 linearization otherwise resolves those methods against the
    # entire AbstractClassSingleGallery ancestor chain (which is inserted as
    # one contiguous block) before ever reaching the mixins listed after it,
    # silently shadowing the overrides with no error.
    _UIConfigMixin,
    _UIGalleryCanvasMixin,
    _CanvasControlsMixin,
    _ScanInputMixin,
    _PreviewContextMixin,
    _MergeExecutionMixin,
    _ConfigPersistenceMixin,
    _LifecycleQmlMixin,
    AbstractClassSingleGallery,
):
    preview_ready = Signal(str)
    qml_input_path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.thumbnail_size = 150

        # --- State ---
        self.scanned_dir: str | None = None
        self.output_dir: str | None = None
        self.last_output_dir: str | None = None
        self.current_scan_thread: Optional[QThread] = None
        self.current_scan_worker: Optional[ImageScannerWorker] = None
        self.current_merge_thread: Optional[QThread] = None
        self.current_merge_worker: Optional[MergeWorker] = None
        self.temp_file_path: Optional[str] = None
        self._zombie_threads: list[QThread] = []
        self._threads_to_cleanup: set[QThread] = set()
        self.pending_save_path: Optional[str] = None
        self._last_merged_pixmap: Optional[QPixmap] = None
        self._syncing_spinboxes = False
        # Tracks the Mode combo's previous value so handle_direction_change
        # can detect canvas<->non-canvas transitions (queue/canvas resync).
        self._prev_direction = "canvas"

        # --- Queue gallery pagination (new for #448) ---
        self._queue_page_size = 100
        self._queue_current_page = 0
        self._queue_pagination_widget: Optional[QWidget] = None
        self._queue_page_combo: Optional[Any] = None
        self._queue_prev_btn: Optional[Any] = None
        self._queue_next_btn: Optional[Any] = None
        self._queue_page_btn: Optional[Any] = None
        self._queue_item_range_lbl: Optional[Any] = None

        # --- Main Layout: single outer QScrollArea (mirrors convert_tab / wallpaper_tab) ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setStyleSheet("QScrollArea { border: none; }")
        self.page_scroll.installEventFilter(self)
        self.page_scroll.viewport().installEventFilter(self)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(4, 4, 4, 4)

        self._build_input_output_sections(content_layout)
        self._build_merge_settings_section(content_layout)
        self._build_gallery_section(content_layout)
        self._build_canvas_section(content_layout)
        self._build_action_buttons_section(content_layout)

        self.page_scroll.setWidget(content_widget)
        main_layout.addWidget(self.page_scroll)

        # --- Wire up canvas-size spinboxes ---
        self.canvas_w_spin.valueChanged.connect(self._on_canvas_size_changed)
        self.canvas_h_spin.valueChanged.connect(self._on_canvas_size_changed)

        # --- Wire up item-geometry spinboxes ---
        for spin in self.spin_list:
            spin.valueChanged.connect(self._on_item_spinbox_changed)

        # --- Initialize ---
        self.on_selection_changed()
        self.handle_direction_change(self.direction.currentText())
        self.clear_gallery_widgets()

    # ─── AbstractClassSingleGallery abstract method ─────────────────────────────

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        label = ClickableLabel(path)
        label.setFixedSize(size, size)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.path_clicked.connect(self.toggle_selection)
        label.path_double_clicked.connect(self.handle_full_image_preview)
        label.path_right_clicked.connect(self.show_image_context_menu)
        return label

    # ─── Selection (drives canvas/queue via the gallery's selection model) ─────

    @Slot(str)
    def toggle_selection(self, path: str):
        """Toggle gallery selection via the view's selection model.

        ``MultiSelection`` gives native toggle-on-click + highlight; the
        resulting ``selection_changed`` fires ``_sync_selection_from_gallery``
        which applies the canvas/queue side effects that the old QLabel-grid
        toggle_selection did inline."""
        sm = self.gallery.view.selectionModel()
        row = self.gallery.model.row_for_path(path)
        if row < 0:
            return
        sm.select(self.gallery.model.index(row, 0), sm.SelectionFlag.Toggle)

    def _sync_selection_from_gallery(self):
        """Mirror the gallery selection into ``selected_files`` and apply the
        canvas/queue side effects (delta-driven, so canvas removal of an
        already-removed item is a no-op)."""
        new_sel = list(self.gallery.selected_files())
        old_set = set(self.selected_files)
        new_set = set(new_sel)
        added = new_set - old_set
        removed = old_set - new_set
        self.selected_files = new_sel

        is_canvas = self.direction.currentText() == "canvas"
        if is_canvas:
            for p in removed:
                self.canvas_widget.remove_item(p)
            for p in added:
                self.canvas_widget.add_image(p, self._thumbnail_for(p))
        else:
            self._refresh_queue_gallery()
        self.on_selection_changed()

    def _push_selection_to_gallery(self):
        """Apply ``selected_files`` to the gallery's selection model (signals
        blocked so the clear+select can't reentrantly wipe ``selected_files``)."""
        sm = self.gallery.view.selectionModel()
        sm.blockSignals(True)
        try:
            self.gallery.clear_selection()
            for path in self.selected_files:
                row = self.gallery.model.row_for_path(path)
                if row >= 0:
                    sm.select(self.gallery.model.index(row, 0), sm.SelectionFlag.Select)
        finally:
            sm.blockSignals(False)

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.selection_label.setText(f"{count} images selected.")
        if count < 2:
            self.run_button.setEnabled(False)
            self.run_button.setText("Run Merge (Select 2+ images)")
        else:
            self.run_button.setEnabled(True)
            self.run_button.setText(f"Run Merge ({count} images)")
        self.status_label.setText(
            "" if count < 2 else f"Ready to merge {count} images."
        )

    def refresh_gallery_view(self):
        """Feed the filtered path list to the virtual gallery (no page slice /
        per-card populate). Overrides the base grid refresh."""
        self.cancel_loading()
        self.clear_gallery_widgets()
        paths = self.gallery_image_paths
        if not paths:
            return
        self.gallery.set_paths(paths)

    def clear_gallery_widgets(self):
        """Clear the virtual gallery and cancel its in-flight loads."""
        self.gallery.clear()
        self.cancel_loading()


__all__ = ["MergeTab"]
