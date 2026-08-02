"""``MergeTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Optional

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

    # ─── Selection (overrides base to sync canvas) ──────────────────────────────

    @Slot(str)
    def toggle_selection(self, path: str):
        """Toggle gallery selection. In canvas mode, syncs the canvas too;
        in every other mode, the canvas is left untouched (it's not visible)
        and only resynced lazily on the next switch into canvas mode."""
        is_canvas = self.direction.currentText() == "canvas"
        if path in self.selected_files:
            self.selected_files.remove(path)
            if is_canvas:
                self.canvas_widget.remove_item(path)
            is_selected = False
        else:
            self.selected_files.append(path)
            if is_canvas:
                self.canvas_widget.add_image(path, self._thumbnail_for(path))
            is_selected = True

        if not is_canvas:
            self._refresh_queue_gallery()

        widget = self.path_to_card_widget.get(path)
        if widget:
            self.update_card_style(widget, is_selected)

        self.on_selection_changed()

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


__all__ = ["MergeTab"]
