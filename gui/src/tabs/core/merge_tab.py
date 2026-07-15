import contextlib
import os
import shutil
import tempfile
from typing import Any, Dict, Optional

import cv2
from backend.src.constants import SUPPORTED_IMG_FORMATS
from gui.src.components.containers.merge_canvas import MergeCanvas
from PySide6.QtCore import (
    Q_ARG,
    QEventLoop,
    QMetaObject,
    QPoint,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QImage,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ...classes import AbstractClassSingleGallery
from ...components import ClickableLabel, MarqueeScrollArea, MergeCanvasItem
from ...helpers import ImageScannerWorker, MergeWorker
from ...styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from ...windows import ImagePreviewWindow

# ─── Main Tab ───────────────────────────────────────────────────────────────────


class MergeTab(AbstractClassSingleGallery):
    preview_ready = Signal(str)
    qml_input_path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.thumbnail_size = 150

        # --- State ---
        self.scanned_dir: str | None = None
        self.output_dir: str | None = None
        self.last_output_dir: str | None = None
        self.current_scan_thread: QThread | None = None
        self.current_scan_worker: ImageScannerWorker | None = None
        self.current_merge_thread: QThread | None = None
        self.current_merge_worker: MergeWorker | None = None
        self.temp_file_path: Optional[str] = None
        self._zombie_threads: list[QThread] = []
        self.pending_save_path: Optional[str] = None
        self._last_merged_pixmap: Optional[QPixmap] = None
        self._syncing_spinboxes = False

        # --- Main Layout: single outer QScrollArea (mirrors convert_tab / wallpaper_tab) ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(4, 4, 4, 4)

        # === 1. Input Configuration ===
        target_group = QGroupBox("Input Configuration")
        target_layout = QFormLayout(target_group)

        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText(
            "Path to directory containing images for merging…"
        )
        self.scan_directory_path.returnPressed.connect(
            self.handle_scan_directory_return
        )
        btn_browse_scan = QPushButton("Browse Input…")
        btn_browse_scan.clicked.connect(self.browse_and_scan_directory)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        target_layout.addRow("Input path:", scan_dir_layout)
        content_layout.addWidget(target_group)

        # === 2. Output Configuration ===
        output_group = QGroupBox("Output Configuration")
        output_layout = QFormLayout(output_group)

        out_dir_layout = QHBoxLayout()
        self.output_directory_path = QLineEdit()
        self.output_directory_path.setPlaceholderText(
            "(Optional) Select output folder. If empty, you will be prompted to save after merge."
        )
        self.output_directory_path.textChanged.connect(self._update_output_dir_state)
        btn_browse_out = QPushButton("Browse Output…")
        btn_browse_out.clicked.connect(self.browse_output_directory)
        apply_shadow_effect(
            btn_browse_out, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        out_dir_layout.addWidget(self.output_directory_path)
        out_dir_layout.addWidget(btn_browse_out)
        output_layout.addRow("Output Folder:", out_dir_layout)

        self.output_filename_input = QLineEdit()
        self.output_filename_input.setPlaceholderText(
            "merged_image (Extension added automatically)"
        )
        output_layout.addRow("Filename:", self.output_filename_input)
        content_layout.addWidget(output_group)

        # === 3. Merge Settings ===
        config_group = QGroupBox("Merge Settings")
        config_layout = QFormLayout(config_group)

        self.direction = QComboBox()
        self.direction.addItems(
            [
                "canvas",
                "horizontal",
                "vertical",
                "grid",
                "panorama",
                "stitch",
                "sequential",
                "gif",
            ]
        )
        self.direction.currentTextChanged.connect(self.handle_direction_change)
        config_layout.addRow("Mode:", self.direction)

        self.lbl_spacing = QLabel("Spacing (px):")
        self.spacing = QSpinBox()
        self.spacing.setRange(0, 1000)
        self.spacing.setValue(10)
        config_layout.addRow(self.lbl_spacing, self.spacing)

        self.lbl_align = QLabel("Alignment/Resize:")
        self.align_mode = QComboBox()
        self.align_mode.addItems(
            [
                "Default (Top/Center)",
                "Align Top/Left",
                "Align Bottom/Right",
                "Center",
                "Scaled (Grow Smallest)",
                "Squish (Shrink Largest)",
            ]
        )
        config_layout.addRow(self.lbl_align, self.align_mode)

        self.lbl_duration = QLabel("Duration (ms/frame):")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 10000)
        self.duration_spin.setValue(500)
        self.duration_spin.setSingleStep(50)
        config_layout.addRow(self.lbl_duration, self.duration_spin)
        self.lbl_duration.hide()
        self.duration_spin.hide()

        self.grid_group = QGroupBox("Grid Size")
        grid_layout = QHBoxLayout()
        self.grid_rows = QSpinBox()
        self.grid_rows.setRange(1, 100)
        self.grid_cols = QSpinBox()
        self.grid_cols.setRange(1, 100)
        grid_layout.addWidget(QLabel("Rows:"))
        grid_layout.addWidget(self.grid_rows)
        grid_layout.addWidget(QLabel("Cols:"))
        grid_layout.addWidget(self.grid_cols)
        self.grid_group.setLayout(grid_layout)
        config_layout.addRow(self.grid_group)
        self.grid_group.hide()

        # --- Perfect Stitch (Anime Pan) Settings ---
        self.perfect_stitch_checkbox = QCheckBox("Perfect Stitch Mode (Digital Art)")
        self.perfect_stitch_checkbox.setToolTip(
            "Optimized for digital anime pan shots. Uses template matching and pyramidal blending."
        )
        config_layout.addRow(self.perfect_stitch_checkbox)

        self.lbl_edge_crop = QLabel("Edge Crop (px):")
        self.edge_crop_spinbox = QSpinBox()
        self.edge_crop_spinbox.setRange(0, 500)
        self.edge_crop_spinbox.setValue(50)
        self.edge_crop_spinbox.setToolTip(
            "Crops left/right edges to neutralize vignettes before stitching."
        )
        config_layout.addRow(self.lbl_edge_crop, self.edge_crop_spinbox)

        self.lbl_pyramid_levels = QLabel("Pyramid Levels:")
        self.pyramid_levels_spinbox = QSpinBox()
        self.pyramid_levels_spinbox.setRange(1, 12)
        self.pyramid_levels_spinbox.setValue(8)
        self.pyramid_levels_spinbox.setToolTip(
            "Width of the linear alpha blend at the overlap seams."
        )
        config_layout.addRow(self.lbl_pyramid_levels, self.pyramid_levels_spinbox)

        self.ai_options_group = QGroupBox("AI Optimization (Advanced)")
        ai_layout = QVBoxLayout()

        self.use_siamese_checkbox = QCheckBox(
            "Order-Agnostic Matching (Siamese Network)"
        )
        self.use_siamese_checkbox.setChecked(True)
        self.use_apap_checkbox = QCheckBox("Parallax Absorption (APAP Mesh Warping)")
        self.use_apap_checkbox.setChecked(True)
        self.use_lsd_checkbox = QCheckBox(
            "Structure Preservation (Line Segment Detector)"
        )
        self.use_lsd_checkbox.setChecked(True)
        self.use_gan_checkbox = QCheckBox("Neural Synthesis Refinement (AnimeGAN2)")
        self.use_gan_checkbox.setChecked(True)
        self.use_birefnet_checkbox = QCheckBox("Character-Aware Seams (BiRefNet)")
        self.use_birefnet_checkbox.setChecked(True)

        self.renderer_combo = QComboBox()
        self.renderer_combo.addItems(["blend", "median", "first"])
        self.renderer_combo.setToolTip(
            "blend: Multi-band seamless (robust)\nmedian: Temporal denoising (sharpest)\nfirst: No blending (fast)"
        )

        self.use_basic_checkbox = QCheckBox("Use BaSiC (Luma Correction)")
        self.use_basic_checkbox.setChecked(True)
        self.use_loftr_checkbox = QCheckBox("Use LoFTR (Dense Matching)")
        self.use_loftr_checkbox.setChecked(True)
        self.use_ecc_checkbox = QCheckBox("Use ECC (Sub-pixel Align)")
        self.use_ecc_checkbox.setChecked(True)
        self.composite_fg_checkbox = QCheckBox("Composite Foreground")
        self.composite_fg_checkbox.setChecked(True)

        self.motion_model_combo = QComboBox()
        self.motion_model_combo.addItem("Translation", "translation")
        self.motion_model_combo.addItem("Affine 4-DOF", "affine")

        ai_layout.addWidget(QLabel("Renderer:"))
        ai_layout.addWidget(self.renderer_combo)
        ai_layout.addWidget(QLabel("Motion model:"))
        ai_layout.addWidget(self.motion_model_combo)
        ai_layout.addWidget(self.use_basic_checkbox)
        ai_layout.addWidget(self.use_loftr_checkbox)
        ai_layout.addWidget(self.use_ecc_checkbox)
        ai_layout.addWidget(self.composite_fg_checkbox)
        ai_layout.addWidget(self.use_siamese_checkbox)
        ai_layout.addWidget(self.use_apap_checkbox)
        ai_layout.addWidget(self.use_lsd_checkbox)
        ai_layout.addWidget(self.use_gan_checkbox)
        ai_layout.addWidget(self.use_birefnet_checkbox)

        mfsr_group = QGroupBox("MFSR Super-Resolution")
        mfsr_vbox = QVBoxLayout(mfsr_group)
        self.mfsr_checkbox = QCheckBox("Enable MFSR post-processing")
        self.mfsr_checkbox.setChecked(False)
        mfsr_vbox.addWidget(self.mfsr_checkbox)
        mfsr_form = QFormLayout()
        self.mfsr_dct_iter_spin = QSpinBox()
        self.mfsr_dct_iter_spin.setRange(1, 100)
        self.mfsr_dct_iter_spin.setValue(20)
        mfsr_form.addRow("DCT iterations:", self.mfsr_dct_iter_spin)
        self.mfsr_prior_checkbox = QCheckBox("CNN prior injection")
        self.mfsr_prior_checkbox.setChecked(True)
        self.mfsr_diffusion_checkbox = QCheckBox("Diffusion inpainting")
        self.mfsr_diffusion_checkbox.setChecked(False)
        mfsr_form.addRow(self.mfsr_prior_checkbox)
        mfsr_form.addRow(self.mfsr_diffusion_checkbox)
        mfsr_vbox.addLayout(mfsr_form)
        ai_layout.addWidget(mfsr_group)

        self.ai_options_group.setLayout(ai_layout)
        config_layout.addRow(self.ai_options_group)

        self.perfect_stitch_checkbox.toggled.connect(
            self._toggle_perfect_stitch_visibility
        )
        self._toggle_perfect_stitch_visibility(False)
        content_layout.addWidget(config_group)

        # === 4. Image Library Gallery ===
        self.selection_label = QLabel("0 images selected.")
        self.selection_label.setStyleSheet("padding: 4px 0; font-weight: bold;")
        content_layout.addWidget(self.selection_label)

        gallery_header = QLabel("Image Library")
        gallery_header.setStyleSheet("font-weight: bold; padding: 4px;")
        content_layout.addWidget(gallery_header)
        content_layout.addWidget(self.search_input)

        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.gallery_scroll_area.setMinimumHeight(600)

        gallery_inner = QWidget()
        gallery_inner.setStyleSheet("background-color: #2c2f33;")
        self.gallery_layout = QGridLayout(gallery_inner)
        self.gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.gallery_scroll_area.setWidget(gallery_inner)

        content_layout.addWidget(self.gallery_scroll_area, 1)
        content_layout.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

        # === 5. Merge Canvas ===
        canvas_header_row = QHBoxLayout()
        canvas_lbl = QLabel("Merge Canvas")
        canvas_lbl.setStyleSheet("font-weight: bold; padding: 4px;")
        canvas_header_row.addWidget(canvas_lbl)
        canvas_header_row.addStretch()
        canvas_header_row.addWidget(QLabel("W:"))
        self.canvas_w_spin = QSpinBox()
        self.canvas_w_spin.setRange(100, 20000)
        self.canvas_w_spin.setValue(1920)
        self.canvas_w_spin.setSingleStep(10)
        self.canvas_w_spin.setFixedWidth(75)
        canvas_header_row.addWidget(self.canvas_w_spin)
        canvas_header_row.addWidget(QLabel("H:"))
        self.canvas_h_spin = QSpinBox()
        self.canvas_h_spin.setRange(100, 20000)
        self.canvas_h_spin.setValue(1080)
        self.canvas_h_spin.setSingleStep(10)
        self.canvas_h_spin.setFixedWidth(75)
        canvas_header_row.addWidget(self.canvas_h_spin)
        canvas_header_row.addWidget(QLabel("BG:"))
        self.canvas_bg_combo = QComboBox()
        self.canvas_bg_combo.addItems(["Transparent", "White", "Black"])
        canvas_header_row.addWidget(self.canvas_bg_combo)
        content_layout.addLayout(canvas_header_row)

        self.canvas_widget = MergeCanvas(1920, 1080)
        self.canvas_widget.setMinimumHeight(600)
        self.canvas_widget.item_selected.connect(self._on_canvas_item_selected)
        content_layout.addWidget(self.canvas_widget, 1)

        # Per-item controls (x, y, w, h + remove/clear buttons)
        item_ctrl = QWidget()
        item_ctrl_layout = QHBoxLayout(item_ctrl)
        item_ctrl_layout.setContentsMargins(0, 2, 0, 2)
        self.spin_list = []
        for attr, label_txt, lo, hi in (
            ("item_x_spin", "X:", -20000, 20000),
            ("item_y_spin", "Y:", -20000, 20000),
            ("item_w_spin", "W:", 1, 20000),
            ("item_h_spin", "H:", 1, 20000),
        ):
            item_ctrl_layout.addWidget(QLabel(label_txt))
            spin = QSpinBox()
            spin.setRange(lo, hi)
            spin.setFixedWidth(72)
            spin.setEnabled(False)
            setattr(self, attr, spin)
            item_ctrl_layout.addWidget(spin)
            self.spin_list.append(spin)

        item_ctrl_layout.addStretch()

        self.btn_remove_from_canvas = QPushButton("Remove Selected")
        self.btn_remove_from_canvas.setEnabled(False)
        self.btn_remove_from_canvas.clicked.connect(self._remove_from_canvas)
        item_ctrl_layout.addWidget(self.btn_remove_from_canvas)

        self.btn_clear_canvas = QPushButton("Clear Canvas")
        self.btn_clear_canvas.clicked.connect(self._clear_canvas)
        item_ctrl_layout.addWidget(self.btn_clear_canvas)

        content_layout.addWidget(item_ctrl)

        # === 6. Action Buttons ===
        btns_layout = QHBoxLayout()

        self.run_button = QPushButton("Run Merge")
        self.run_button.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(self.run_button, "#000000", 8, 0, 3)
        self.run_button.clicked.connect(self.start_merge)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(
            "QPushButton { background-color: #c0392b; color: white; font-weight: bold; "
            "padding: 12px; border-radius: 8px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        apply_shadow_effect(self.cancel_button, "#000000", 8, 0, 3)
        self.cancel_button.clicked.connect(self.cancel_merge)
        self.cancel_button.setVisible(False)

        btns_layout.addWidget(self.run_button)
        btns_layout.addWidget(self.cancel_button)
        content_layout.addLayout(btns_layout)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #b9bbbe; font-style: italic; padding: 10px;"
        )
        content_layout.addWidget(self.status_label)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)

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
        """Toggle gallery selection and sync the canvas accordingly."""
        if path in self.selected_files:
            self.selected_files.remove(path)
            self.canvas_widget.remove_item(path)
            is_selected = False
        else:
            self.selected_files.append(path)
            cached = self._initial_pixmap_cache.get(path)
            if cached and isinstance(cached, QImage) and not cached.isNull():
                thumb = QPixmap.fromImage(cached)
            else:
                thumb = QPixmap()
            self.canvas_widget.add_image(path, thumb)
            is_selected = True

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

    # ─── Canvas controls ────────────────────────────────────────────────────────

    @Slot(object)
    def _on_canvas_item_selected(self, item: Optional[MergeCanvasItem]):
        has_item = item is not None
        self.btn_remove_from_canvas.setEnabled(has_item)

        self._syncing_spinboxes = True
        for spin in self.spin_list:
            spin.setEnabled(has_item)

        if has_item:
            self.spin_list[0].setValue(int(item.x()))
            self.spin_list[1].setValue(int(item.y()))
            self.spin_list[2].setValue(item._w)
            self.spin_list[3].setValue(item._h)
        self._syncing_spinboxes = False

    def _on_item_spinbox_changed(self):
        if self._syncing_spinboxes:
            return
        item = self.canvas_widget.get_selected_item()
        if item is None:
            return
        self._syncing_spinboxes = True
        item.set_geometry(
            self.spin_list[0].value(),
            self.spin_list[1].value(),
            self.spin_list[2].value(),
            self.spin_list[3].value(),
        )
        self._syncing_spinboxes = False

    def _on_canvas_size_changed(self):
        w = self.canvas_w_spin.value()
        h = self.canvas_h_spin.value()
        self.canvas_widget.resize_canvas(w, h)

    def _remove_from_canvas(self):
        removed = self.canvas_widget.remove_selected()
        for path in removed:
            if path in self.selected_files:
                self.selected_files.remove(path)
            widget = self.path_to_card_widget.get(path)
            if widget:
                self.update_card_style(widget, False)
        if removed:
            self.on_selection_changed()

    def _clear_canvas(self):
        paths = self.canvas_widget.clear_canvas()
        for path in paths:
            if path in self.selected_files:
                self.selected_files.remove(path)
            widget = self.path_to_card_widget.get(path)
            if widget:
                self.update_card_style(widget, False)
        if paths:
            self.on_selection_changed()

    # ─── Helper: UI reset ───────────────────────────────────────────────────────

    def reset_ui_state(self):
        self.cancel_button.setVisible(False)
        self.run_button.setVisible(True)
        self.run_button.setEnabled(True)
        self.current_merge_worker = None
        self.current_merge_thread = None
        self.on_selection_changed()

    # ─── Cancel Merge ───────────────────────────────────────────────────────────

    @Slot()
    def cancel_merge(self):
        self.status_label.setText("Cancelling…")
        thread = self.current_merge_thread
        worker = self.current_merge_worker

        if thread:
            try:
                if worker:
                    worker.sig_finished.disconnect()
                    worker.error.disconnect()
                    worker.progress.disconnect()
                thread.finished.disconnect()
            except Exception:
                pass

            thread.requestInterruption()
            thread.quit()

            if thread.isRunning():
                self._zombie_threads.append(thread)
                thread.finished.connect(self._cleanup_zombie_thread)
            else:
                thread.deleteLater()

        self.cleanup_temp_file()
        self.status_label.setText("Merge cancelled.")
        self.reset_ui_state()

    @Slot()
    def _cleanup_zombie_thread(self):
        thread = self.sender()
        if thread:
            if thread in self._zombie_threads:
                self._zombie_threads.remove(thread) # pyrefly: ignore [bad-argument-type]
            thread.deleteLater()

    # ─── Direction / mode visibility ────────────────────────────────────────────

    def handle_direction_change(self, direction: str):
        is_canvas = direction == "canvas"
        is_grid = direction == "grid"
        is_complex = direction in ("panorama", "stitch", "sequential")
        is_gif = direction == "gif"
        is_traditional = not (is_canvas or is_complex or is_gif)

        self.grid_group.setVisible(is_grid)
        self.lbl_spacing.setVisible(is_traditional and not is_canvas)
        self.spacing.setVisible(is_traditional and not is_canvas)
        self.lbl_align.setVisible(is_traditional and not is_canvas)
        self.align_mode.setVisible(is_traditional and not is_canvas)
        self.lbl_duration.setVisible(is_gif)
        self.duration_spin.setVisible(is_gif)
        self.perfect_stitch_checkbox.setVisible(is_complex)
        self._toggle_perfect_stitch_visibility(
            self.perfect_stitch_checkbox.isChecked() and is_complex
        )

    @Slot(bool)
    def _toggle_perfect_stitch_visibility(self, checked: bool):
        visible = checked and self.perfect_stitch_checkbox.isVisible()
        self.lbl_edge_crop.setVisible(visible)
        self.edge_crop_spinbox.setVisible(visible)
        self.lbl_pyramid_levels.setVisible(visible)
        self.pyramid_levels_spinbox.setVisible(visible)
        self.ai_options_group.setVisible(visible)
        if checked and self.perfect_stitch_checkbox.isVisible():
            self.spacing.setEnabled(False)
            self.align_mode.setEnabled(False)
        else:
            self.spacing.setEnabled(True)
            self.align_mode.setEnabled(True)

    # ─── Input / Scan ───────────────────────────────────────────────────────────

    @Slot()
    def handle_scan_directory_return(self):
        d = self.scan_directory_path.text().strip()
        if d and os.path.isdir(d):
            self.populate_scan_gallery(d)
        else:
            QMessageBox.warning(
                self, "Invalid Path", "The entered path is not a valid directory."
            )

    @Slot()
    def browse_and_scan_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", self.last_browsed_scan_dir
        )
        if d:
            self.scan_directory_path.setText(d)
            self.last_browsed_scan_dir = d
            self.populate_scan_gallery(d)

    @Slot()
    def browse_output_directory(self):
        start_dir = (
            self.last_output_dir if self.last_output_dir else self.last_browsed_scan_dir
        )
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", start_dir)
        if d:
            self.output_directory_path.setText(d)
            self.output_dir = d
            self.last_output_dir = d

    @Slot(str)
    def _update_output_dir_state(self, path: str):
        self.output_dir = path.strip() if path.strip() else None

    def populate_scan_gallery(self, directory: str):
        self.scanned_dir = directory
        if self.current_scan_thread and self.current_scan_thread.isRunning():
            self.current_scan_thread.quit()
            self.current_scan_thread.wait(2000)

        self.cancel_loading()

        loop = QEventLoop()
        QTimer.singleShot(1, loop.quit)
        loop.exec()

        worker = ImageScannerWorker(directory)
        self.current_scan_worker = worker
        self.current_scan_thread = worker
        worker.scan_finished.connect(self.on_scan_finished)
        worker.finished.connect(self.cleanup_scan_thread_ref)
        worker.start()

    @Slot()
    def cleanup_scan_thread_ref(self):
        self.current_scan_thread = None
        self.current_scan_worker = None

    @Slot(list)
    def on_scan_finished(self, paths):
        if not paths:
            QMessageBox.information(
                self, "No Files", f"No supported images found in {self.scanned_dir}"
            )
            self.clear_gallery_widgets()
            return
        self.start_loading_gallery(paths)
        self.status_label.setText(f"Scan complete. Loaded {len(paths)} files.")

    # ─── Preview / context menu ─────────────────────────────────────────────────

    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        target_list = (
            list(self.gallery_image_paths) if self.gallery_image_paths else [image_path]
        )
        if image_path not in target_list:
            target_list.append(image_path)
        try:
            start_index = target_list.index(image_path)
        except ValueError:
            start_index = 0

        window = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=target_list,
            start_index=start_index,
        )
        window.path_changed.connect(self.update_preview_highlight)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.show()
        self.open_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        menu.addSeparator()

        copy_action = QAction("Copy Image to Clipboard", self)
        copy_action.triggered.connect(lambda: self._copy_image_path_to_clipboard(path))
        menu.addAction(copy_action)
        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Remove from Canvas (Deselect)" if is_selected else "Add to Canvas (Select)"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        menu.addSeparator()

        delete_action = QAction("Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _copy_image_path_to_clipboard(self, path: str):
        if os.path.exists(path):
            try:
                img = QImage(path)
                if not img.isNull():
                    QApplication.clipboard().setImage(img)
                    self.status_label.setText(
                        f"Copied image to clipboard: {os.path.basename(path)}"
                    )
                else:
                    QMessageBox.warning(
                        self, "Copy Error", "Failed to load image for copying."
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Copy failed: {e}")

    def handle_delete_image(self, path: str):
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        if (
            QMessageBox.question(
                self,
                f"Confirm {action_name}",
                f"Move {os.path.basename(path)} to {action_name}?",
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                if send_to_trash_enabled:
                    send2trash(path)
                else:
                    os.remove(path)

                for lst in (
                    self.gallery_image_paths,
                    self.master_image_paths,
                    self.selected_files,
                ):
                    with contextlib.suppress(ValueError, AttributeError):
                        lst.remove(path)

                self.canvas_widget.remove_item(path)

                widget = self.path_to_card_widget.pop(path, None)
                if widget:
                    widget.deleteLater()

                self.on_selection_changed()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # ─── Merge ──────────────────────────────────────────────────────────────────

    def start_merge(self):
        if len(self.selected_files) < 2:
            QMessageBox.warning(self, "Invalid", "Select at least 2 images.")
            return

        direction = self.direction.currentText()
        ext = ".gif" if direction == "gif" else ".png"
        temp_dir = tempfile.gettempdir()
        temp_filename = next(tempfile._get_candidate_names()) + ext # pyrefly: ignore [missing-attribute]
        target_path = os.path.join(temp_dir, temp_filename)
        self.temp_file_path = target_path

        self.pending_save_path = None
        if self.output_dir and os.path.isdir(self.output_dir):
            filename = self.output_filename_input.text().strip()
            if not filename:
                filename = next(tempfile._get_candidate_names()) # pyrefly: ignore [missing-attribute]
            if not filename.lower().endswith(ext):
                filename += ext
            self.pending_save_path = os.path.join(self.output_dir, filename)

        merge_config = self.collect(self.temp_file_path)

        self.run_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.status_label.setText("Merging…")

        if cv2.ocl.haveOpenCL():
            cv2.ocl.finish()

        worker = MergeWorker(merge_config)
        self.current_merge_worker = worker
        self.current_merge_thread = worker

        worker.progress.connect(
            lambda c, t: self.status_label.setText(f"Merging {c}/{t}")
        )

        with contextlib.suppress(Exception):
            worker.sig_finished.disconnect()

        worker.error.connect(self.on_merge_error)

        def invoke_cleanup(path):
            # pyrefly: ignore [no-matching-overload]
            QMetaObject.invokeMethod(
                self,
                "_cleanup_merge_worker_and_show_dialog",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, path),
            )

        worker.sig_finished.connect(invoke_cleanup)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @Slot(str)
    def _cleanup_merge_worker_and_show_dialog(self, result_path: str):
        self.reset_ui_state()
        self.show_preview_and_confirm(result_path)

    def on_merge_error(self, msg: str):
        self.cleanup_temp_file()
        self.on_selection_changed()
        self.reset_ui_state()
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Error", msg)

    @Slot(str)
    def show_preview_and_confirm(self, result_path: str):
        if not os.path.exists(result_path):
            self.on_merge_error(f"Failed to create merge file at: {result_path}")
            return

        self.status_label.setText("Merge complete.")
        self._last_merged_pixmap = QPixmap(result_path)

        preview_window = ImagePreviewWindow(
            image_path=result_path,
            db_tab_ref=None,
            parent=self,
            all_paths=[result_path],
            start_index=0,
        )
        preview_window.setWindowTitle("Merged Image Preview")
        preview_window.show()
        preview_window.activateWindow()

        confirm = QMessageBox(self)
        confirm.setWindowTitle("Save Merged Image?")

        if self.pending_save_path:
            confirm.setText(
                f"Merge successful. Save to configured output?\n\n{self.pending_save_path}"
            )
            save_text = "Save"
        else:
            confirm.setText("Merge successful. Choose an action:")
            save_text = "Save As…"

        copy_btn = confirm.addButton(
            "Copy to Clipboard", QMessageBox.ButtonRole.ActionRole
        )
        save_btn = confirm.addButton(save_text, QMessageBox.ButtonRole.AcceptRole)
        save_add_btn = confirm.addButton(
            "Save and Add to Canvas", QMessageBox.ButtonRole.AcceptRole
        )
        confirm.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.exec()
        clicked = confirm.clickedButton()

        saved_final_path = None

        if clicked == copy_btn:
            if self._last_merged_pixmap:
                QApplication.clipboard().setPixmap(self._last_merged_pixmap)
            self.cleanup_temp_file()

        elif clicked in (save_btn, save_add_btn):
            if self.pending_save_path:
                try:
                    if os.path.exists(self.pending_save_path):
                        overwrite = QMessageBox.question(
                            self,
                            "Overwrite?",
                            f"File already exists:\n{self.pending_save_path}\nOverwrite?",
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                        )
                        if overwrite != QMessageBox.StandardButton.Yes:
                            self.cleanup_temp_file()
                            return
                    shutil.move(result_path, self.pending_save_path)
                    saved_final_path = self.pending_save_path
                    self.temp_file_path = None
                    self.last_output_dir = os.path.dirname(saved_final_path)
                    QMessageBox.information(
                        self, "Success", f"Saved to {saved_final_path}"
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self, "Save Error", f"Failed to move file: {e}"
                    )
                    self.cleanup_temp_file()
            else:
                filter_str = (
                    "GIF (*.gif)"
                    if result_path.lower().endswith(".gif")
                    else "PNG (*.png)"
                )
                start_dir = (
                    self.last_output_dir
                    if self.last_output_dir
                    else self.last_browsed_scan_dir
                )
                out, _ = QFileDialog.getSaveFileName(
                    self, "Save Merged Image", start_dir, filter_str
                )
                if out:
                    try:
                        shutil.move(result_path, out)
                        saved_final_path = out
                        self.temp_file_path = None
                        self.last_output_dir = os.path.dirname(out)
                        QMessageBox.information(self, "Success", f"Saved to {out}")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Move failed: {e}")
                        self.cleanup_temp_file()
                else:
                    self.cleanup_temp_file()

            if saved_final_path and clicked == save_add_btn:
                self._inject_new_image(saved_final_path)
        else:
            self.cleanup_temp_file()

        self._last_merged_pixmap = None
        if self.temp_file_path is None and not os.path.exists(result_path):
            preview_window.close()

        self.status_label.setText("Ready to merge.")

    def _inject_new_image(self, path: str):
        """Add a newly-saved merged image to the gallery and canvas."""
        self.start_loading_gallery([path], append=True)
        # Immediately add to canvas selection too
        self.selected_files.append(path)
        self.canvas_widget.add_image(path, QPixmap(path))
        self.on_selection_changed()

    def cleanup_temp_file(self):
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.remove(self.temp_file_path)
            except Exception as e:
                print(f"Error cleaning up temp file: {e}")
        self.temp_file_path = None

    # ─── Collect config ─────────────────────────────────────────────────────────

    def collect(self, output_path: str = "") -> Dict[str, Any]:
        layout = self.canvas_widget.get_layout()
        direction = self.direction.currentText()
        return {
            "direction": direction,
            "scan_directory": self.scan_directory_path.text().strip(),
            "input_path": [item["path"] for item in layout],
            "canvas_layout": layout,
            "canvas_width": self.canvas_w_spin.value(),
            "canvas_height": self.canvas_h_spin.value(),
            "canvas_background": self.canvas_bg_combo.currentText().lower(),
            "output_path": output_path,
            "input_formats": [
                f.strip().lstrip(".") for f in SUPPORTED_IMG_FORMATS if f.strip()
            ],
            "spacing": self.spacing.value(),
            "align_mode": self.align_mode.currentText(),
            "grid_size": (
                (self.grid_rows.value(), self.grid_cols.value())
                if direction == "grid"
                else None
            ),
            "duration": self.duration_spin.value(),
            "perfect_stitch_mode": self.perfect_stitch_checkbox.isChecked(),
            "edge_crop_px": self.edge_crop_spinbox.value(),
            "pyramid_levels": self.pyramid_levels_spinbox.value(),
            "use_siamese": self.use_siamese_checkbox.isChecked(),
            "use_apap": self.use_apap_checkbox.isChecked(),
            "use_lsd": self.use_lsd_checkbox.isChecked(),
            "use_gan": self.use_gan_checkbox.isChecked(),
            "use_birefnet": self.use_birefnet_checkbox.isChecked(),
            "use_basic": self.use_basic_checkbox.isChecked(),
            "use_loftr": self.use_loftr_checkbox.isChecked(),
            "use_ecc": self.use_ecc_checkbox.isChecked(),
            "renderer": self.renderer_combo.currentText(),
            "composite_fg": self.composite_fg_checkbox.isChecked(),
            "motion_model": self.motion_model_combo.currentData(),
            "mfsr_mode": self.mfsr_checkbox.isChecked(),
            "mfsr_n_dct_iter": self.mfsr_dct_iter_spin.value(),
            "mfsr_use_prior": self.mfsr_prior_checkbox.isChecked(),
            "mfsr_use_diffusion": self.mfsr_diffusion_checkbox.isChecked(),
            "selected_files": list(self.selected_files),
        }

    # ─── Config save/restore ────────────────────────────────────────────────────

    def get_default_config(self) -> dict:
        return {
            "direction": "canvas",
            "spacing": 10,
            "grid_size": [2, 2],
            "scan_directory": "",
            "output_directory": "",
            "output_filename": "",
            "align_mode": "Default (Top/Center)",
            "canvas_width": 1920,
            "canvas_height": 1080,
            "canvas_background": "transparent",
        }

    def set_config(self, config: dict):
        try:
            direction = config.get("direction", "canvas")
            if self.direction.findText(direction) != -1:
                self.direction.setCurrentText(direction)

            self.spacing.setValue(config.get("spacing", 10))

            align_mode = config.get("align_mode", "Default (Top/Center)")
            if self.align_mode.findText(align_mode) != -1:
                self.align_mode.setCurrentText(align_mode)

            grid_size = config.get("grid_size", [2, 2])
            if isinstance(grid_size, list) and len(grid_size) == 2:
                self.grid_rows.setValue(grid_size[0])
                self.grid_cols.setValue(grid_size[1])

            cw = config.get("canvas_width", 1920)
            ch = config.get("canvas_height", 1080)
            self.canvas_w_spin.setValue(cw)
            self.canvas_h_spin.setValue(ch)

            bg = config.get("canvas_background", "transparent").capitalize()
            idx = self.canvas_bg_combo.findText(bg)
            if idx >= 0:
                self.canvas_bg_combo.setCurrentIndex(idx)

            self._restore_selected_files(config)

            scan_dir = config.get("scan_directory")
            if scan_dir:
                self.scan_directory_path.setText(scan_dir)
                if os.path.isdir(scan_dir):
                    self.populate_scan_gallery(scan_dir)

            out_dir = config.get("output_directory")
            if out_dir:
                self.output_directory_path.setText(out_dir)
                self.output_dir = out_dir

            out_fname = config.get("output_filename")
            if out_fname:
                self.output_filename_input.setText(out_fname)

            self.perfect_stitch_checkbox.setChecked(
                config.get("perfect_stitch_mode", False)
            )
            self.edge_crop_spinbox.setValue(config.get("edge_crop_px", 50))
            self.pyramid_levels_spinbox.setValue(config.get("pyramid_levels", 4))
            self.use_siamese_checkbox.setChecked(config.get("use_siamese", True))
            self.use_apap_checkbox.setChecked(config.get("use_apap", True))
            self.use_lsd_checkbox.setChecked(config.get("use_lsd", True))
            self.use_gan_checkbox.setChecked(config.get("use_gan", True))
            self.use_birefnet_checkbox.setChecked(config.get("use_birefnet", True))

            mm_idx = self.motion_model_combo.findData(
                config.get("motion_model", "translation")
            )
            if mm_idx >= 0:
                self.motion_model_combo.setCurrentIndex(mm_idx)
            self.mfsr_checkbox.setChecked(config.get("mfsr_mode", False))
            self.mfsr_dct_iter_spin.setValue(config.get("mfsr_n_dct_iter", 20))
            self.mfsr_prior_checkbox.setChecked(config.get("mfsr_use_prior", True))
            self.mfsr_diffusion_checkbox.setChecked(
                config.get("mfsr_use_diffusion", False)
            )

            print("MergeTab configuration loaded.")
        except Exception as e:
            print(f"Error applying MergeTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )

    def _restore_selected_files(self, config: dict):
        saved = config.get("selected_files", [])
        if not saved:
            return
        valid = [p for p in saved if os.path.isfile(p)]
        if not valid:
            return
        self.selected_files = list(valid)
        for path in valid:
            cached = self._initial_pixmap_cache.get(path)
            if cached and isinstance(cached, QImage) and not cached.isNull():
                thumb = QPixmap.fromImage(cached)
            else:
                thumb = QPixmap()
            self.canvas_widget.add_image(path, thumb)
        self.on_selection_changed()

    # ─── Lifecycle ──────────────────────────────────────────────────────────────

    def cancel_loading(self):
        super().cancel_loading()

        if self.current_scan_worker:
            with contextlib.suppress(Exception):
                self.current_scan_worker.stop()

        if self.current_merge_worker and self.current_merge_thread:
            self.current_merge_thread.requestInterruption()
            self.current_merge_thread.quit()

        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)

    # ─── QML handlers ───────────────────────────────────────────────────────────

    @Slot(str)
    def browse_input_qml(self, current_path: str = ""):
        starting_dir = (
            current_path if os.path.isdir(current_path) else self.last_browsed_scan_dir
        )
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", starting_dir
        )
        if d:
            self.scan_directory_path.setText(d)
            self.last_browsed_scan_dir = d
            self.qml_input_path_changed.emit(d)
            self.populate_scan_gallery(d)
            return d
        return ""

    @Slot(str, int, int, str)
    def start_merge_qml(
        self, direction: str, spacing: int, duration: int, align_mode: str
    ):
        self.direction.setCurrentText(direction)
        self.spacing.setValue(spacing)
        self.duration_spin.setValue(duration)
        self.align_mode.setCurrentText(align_mode)
        self.start_merge()

    @Slot(list)
    def set_selected_files_qml(self, paths):
        self.selected_files = list(paths)
        self.on_selection_changed()
