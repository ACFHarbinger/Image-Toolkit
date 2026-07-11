import contextlib
import os

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ....classes import AbstractClassTwoGalleries
from ....components import ClickableLabel, MarqueeScrollArea
from ....helpers import SamplerWorker
from ....styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from ....utils.sort_utils import natural_sort_key
from ....windows import ImagePreviewWindow


class SamplerSubTab(AbstractClassTwoGalleries):
    """Upsample / downsample images, GIFs, and videos."""

    def __init__(self):
        super().__init__()
        self.worker = None

        main_layout = QVBoxLayout(self)

        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- Input Group ---
        input_group = QGroupBox("Input")
        input_form = QFormLayout(input_group)

        input_row = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Directory or single file to resample…")
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_input)
        apply_shadow_effect(
            btn_browse, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        input_row.addWidget(self.input_path)
        input_row.addWidget(btn_browse)
        input_form.addRow("Input path:", input_row)
        content_layout.addWidget(input_group)

        # --- Sampling Settings Group ---
        settings_group = QGroupBox("Sampling Settings")
        settings_form = QFormLayout(settings_group)

        # Scale mode radio buttons
        mode_row = QHBoxLayout()
        self._scale_mode_group = QButtonGroup(self)
        self._radio_factor = QRadioButton("Scale factor")
        self._radio_dims = QRadioButton("Target dimensions")
        self._radio_factor.setChecked(True)
        self._scale_mode_group.addButton(self._radio_factor, 0)
        self._scale_mode_group.addButton(self._radio_dims, 1)
        self._radio_factor.toggled.connect(self._on_scale_mode_changed)
        mode_row.addWidget(self._radio_factor)
        mode_row.addWidget(self._radio_dims)
        mode_row.addStretch()
        settings_form.addRow("Scale mode:", mode_row)

        # Factor controls
        self._factor_widget = QWidget()
        factor_row = QHBoxLayout(self._factor_widget)
        factor_row.setContentsMargins(0, 0, 0, 0)
        self.scale_factor_spin = QDoubleSpinBox()
        self.scale_factor_spin.setRange(0.05, 16.0)
        self.scale_factor_spin.setSingleStep(0.25)
        self.scale_factor_spin.setValue(2.0)
        self.scale_factor_spin.setDecimals(2)
        self.scale_factor_spin.setSuffix("×")
        factor_row.addWidget(self.scale_factor_spin)
        for quick in ("0.25×", "0.5×", "2×", "4×"):
            val = float(quick.rstrip("×"))
            btn = QPushButton(quick)
            btn.setFixedWidth(48)
            btn.clicked.connect(lambda _, v=val: self.scale_factor_spin.setValue(v))
            factor_row.addWidget(btn)
        factor_row.addStretch()

        # Dimension controls
        self._dims_widget = QWidget()
        dims_row = QHBoxLayout(self._dims_widget)
        dims_row.setContentsMargins(0, 0, 0, 0)
        self.dim_w_spin = QSpinBox()
        self.dim_w_spin.setRange(1, 32000)
        self.dim_w_spin.setValue(1920)
        self.dim_w_spin.setSuffix(" px")
        self.dim_h_spin = QSpinBox()
        self.dim_h_spin.setRange(1, 32000)
        self.dim_h_spin.setValue(1080)
        self.dim_h_spin.setSuffix(" px")
        self.preserve_ar_cb = QCheckBox("Preserve aspect ratio")
        self.preserve_ar_cb.setChecked(True)
        dims_row.addWidget(QLabel("W:"))
        dims_row.addWidget(self.dim_w_spin)
        dims_row.addWidget(QLabel("H:"))
        dims_row.addWidget(self.dim_h_spin)
        dims_row.addWidget(self.preserve_ar_cb)
        dims_row.addStretch()
        self._dims_widget.setVisible(False)

        scale_container = QWidget()
        scale_vbox = QVBoxLayout(scale_container)
        scale_vbox.setContentsMargins(0, 0, 0, 0)
        scale_vbox.addWidget(self._factor_widget)
        scale_vbox.addWidget(self._dims_widget)
        settings_form.addRow("Scale:", scale_container)

        # Algorithm
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(
            ["Lanczos", "Bicubic", "Bilinear", "Nearest Neighbor"]
        )
        self.algorithm_combo.setToolTip(
            "Lanczos: highest quality, slower\n"
            "Bicubic: good quality, moderate speed\n"
            "Bilinear: fast, acceptable quality\n"
            "Nearest Neighbor: pixel-perfect, aliased"
        )
        settings_form.addRow("Algorithm:", self.algorithm_combo)

        # Checkboxes
        _cb_style = (
            "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; "
            "border-radius: 3px; background-color: #333; }"
            "QCheckBox::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; }"
        )
        self.multicore_cb = QCheckBox("Multi-core processing (faster for batches)")
        self.multicore_cb.setChecked(True)
        self.multicore_cb.setStyleSheet(_cb_style)
        settings_form.addRow(self.multicore_cb)

        self.delete_cb = QCheckBox("Delete originals after resampling")
        self.delete_cb.setChecked(False)
        self.delete_cb.setStyleSheet(_cb_style)
        settings_form.addRow(self.delete_cb)

        content_layout.addWidget(settings_group)

        # --- Output Settings Group (optional) ---
        out_group = QGroupBox("Output Settings")
        out_form = QFormLayout(out_group)

        # Output format
        self.out_format_combo = QComboBox()
        self.out_format_combo.addItem("Keep original format")
        self.out_format_combo.addItems(["--- Images ---"])
        self.out_format_combo.addItems(list(SUPPORTED_IMG_FORMATS))
        self.out_format_combo.addItems(["--- Videos ---"])
        self.out_format_combo.addItems([f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS])
        out_form.addRow("Output format:", self.out_format_combo)

        out_dir_row = QHBoxLayout()
        self.out_dir_edit = QLineEdit()
        self.out_dir_edit.setPlaceholderText("Leave blank to save alongside originals")
        btn_out_browse = QPushButton("Browse…")
        btn_out_browse.clicked.connect(self._browse_output)
        apply_shadow_effect(
            btn_out_browse, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        out_dir_row.addWidget(self.out_dir_edit)
        out_dir_row.addWidget(btn_out_browse)
        out_form.addRow("Output directory:", out_dir_row)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText(
            "e.g. 'upscaled_'  (leave blank to auto-suffix)"
        )
        out_form.addRow("Filename prefix:", self.prefix_edit)

        content_layout.addWidget(out_group)

        # --- Progress bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #36393f; color: white; border: 1px solid #4f545c; "
            "border-radius: 4px; padding: 2px; }"
            "QProgressBar::chunk { background-color: #5865f2; border-radius: 4px; }"
        )
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        content_layout.addWidget(self.progress_bar)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        # --- Found gallery ---
        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(500)
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.gallery_widget)
        self.found_gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.found_gallery_scroll.setWidget(self.gallery_widget)
        self.found_gallery_scroll.selection_changed.connect(
            self.handle_marquee_selection
        )

        content_layout.addWidget(self.found_search_input)
        content_layout.addWidget(self.found_gallery_scroll, 1)

        if hasattr(self, "found_pagination_widget"):
            content_layout.addWidget(
                self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        # --- Selected gallery ---
        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(300)
        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_gallery_layout = QGridLayout(self.selected_widget)
        self.selected_gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.selected_gallery_scroll.setWidget(self.selected_widget)
        content_layout.addWidget(self.selected_gallery_scroll, 1)

        if hasattr(self, "selected_pagination_widget"):
            content_layout.addWidget(
                self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        content_layout.addStretch(1)

        # --- Buttons ---
        btn_container = QWidget()
        btn_row = QHBoxLayout(btn_container)
        btn_row.setContentsMargins(0, 0, 0, 0)

        self.btn_all = QPushButton("Resample All in Directory")
        self.btn_all.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(
            self.btn_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_all.clicked.connect(lambda: self._start_worker(use_selection=False))

        self.btn_selected = QPushButton("Resample Selected (0)")
        self.btn_selected.setStyleSheet(SHARED_BUTTON_STYLE)
        self.btn_selected.setEnabled(False)
        apply_shadow_effect(
            self.btn_selected, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_selected.clicked.connect(
            lambda: self._start_worker(use_selection=True)
        )

        btn_row.addWidget(self.btn_all)
        btn_row.addWidget(self.btn_selected)
        content_layout.addWidget(btn_container)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #666; font-style: italic; padding: 8px;"
        )
        content_layout.addWidget(self.status_label)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)

        self.clear_galleries()

    # --- Scale mode toggle ---

    @Slot(bool)
    def _on_scale_mode_changed(self, factor_selected: bool):
        self._factor_widget.setVisible(factor_selected)
        self._dims_widget.setVisible(not factor_selected)

    # --- Browsing ---

    @Slot()
    def _browse_input(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select input directory",
            self.last_browsed_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.input_path.setText(path)
            self.last_browsed_dir = path
            self._scan_and_load()

    @Slot()
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            "",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self.out_dir_edit.setText(path)

    # --- File scanning ---

    def _collect_paths(self) -> list:
        p = self.input_path.text().strip()
        if not p:
            return []
        if os.path.isfile(p):
            return [p]
        if not os.path.isdir(p):
            return []

        vid_exts = {f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS}
        img_exts = {f.lower() for f in SUPPORTED_IMG_FORMATS} | {"gif"}
        all_exts = vid_exts | img_exts

        paths = []
        from gui.src.windows.settings.app_settings import AppSettings
        if AppSettings.recursive_scan():
            for root, _, files in os.walk(p):
                for f in files:
                    if os.path.splitext(f)[1].lstrip(".").lower() in all_exts:
                        paths.append(os.path.join(root, f))
        else:
            with os.scandir(p) as it:
                for entry in it:
                    if entry.is_file() and os.path.splitext(entry.name)[1].lstrip(".").lower() in all_exts:
                        paths.append(entry.path)
        return paths

    def _scan_and_load(self):
        paths = self._collect_paths()
        if not paths:
            QMessageBox.information(self, "No Files", "No supported files found.")
            self.clear_galleries()
            return
        self.start_loading_thumbnails(sorted(paths, key=natural_sort_key))

    # --- Gallery abstract implementations (mirrors FormatSubTab) ---

    def create_card_widget(self, path: str, pixmap, is_selected: bool) -> QWidget:
        thumb_size = self.thumbnail_size
        card = ClickableLabel(path)
        card.setFixedSize(thumb_size + 10, thumb_size + 10)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)
        if pixmap and not pixmap.isNull():
            img_label.setPixmap(
                pixmap.scaled(
                    thumb_size,
                    thumb_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            img_label.setText("Loading…")
            img_label.setStyleSheet("color: #999; border: 1px dashed #666;")

        card_layout.addWidget(img_label)

        # Initialize the label's internal references
        card.set_image_label(img_label)
        card.style_callback = self._update_card_style

        # Trigger the style
        card.set_selected_style(is_selected)

        card.path_double_clicked.connect(self._preview_image)
        card.path_right_clicked.connect(self._context_menu)
        return card

    def update_card_pixmap(self, widget: QWidget, pixmap):
        if not isinstance(widget, ClickableLabel):
            return
        img_label = widget.findChild(QLabel)
        if not img_label:
            return
        if pixmap and not pixmap.isNull():
            if isinstance(pixmap, QImage):
                pixmap = QPixmap.fromImage(pixmap)
            img_label.setPixmap(
                pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            img_label.setText("")
        else:
            img_label.clear()
            img_label.setText("Loading…")
        self._update_card_style(img_label, widget.path in self.selected_files)

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet(
                "border: 3px solid #5865f2; background-color: #36393f;"
            )
        elif img_label.pixmap() and not img_label.pixmap().isNull():
            img_label.setStyleSheet(
                "border: 1px solid #4f545c; background-color: #36393f;"
            )
        else:
            img_label.setStyleSheet("border: 1px dashed #666; color: #999;")

    def on_selection_changed(self):
        n = len(self.selected_files)
        self.btn_selected.setText(f"Resample Selected ({n})")
        self.btn_selected.setEnabled(n > 0)

    # --- Interaction ---

    @Slot(str)
    def _preview_image(self, path: str):
        if not os.path.exists(path):
            return
        all_paths = (
            sorted(self.found_files, key=natural_sort_key)
            if self.found_files
            else [path]
        )
        try:
            idx = all_paths.index(path)
        except ValueError:
            idx = 0
        preview = ImagePreviewWindow(
            image_path=path,
            db_tab_ref=None,
            parent=self,
            all_paths=all_paths,
            start_index=idx,
        )
        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        preview.show()
        self.open_preview_windows.append(preview)

    @Slot(QPoint, str)
    def _context_menu(self, pos: QPoint, path: str):
        menu = QMenu(self)
        view = QAction("View Full Size Preview", self)
        view.triggered.connect(lambda: self._preview_image(path))
        menu.addAction(view)
        menu.addSeparator()
        is_sel = path in self.selected_files
        tog = QAction("Deselect" if is_sel else "Select for resampling", self)
        tog.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(tog)
        menu.exec(pos)

    # --- Worker ---

    def _collect_config(self, use_selection: bool) -> dict:
        files = list(self.selected_files) if use_selection else self._collect_paths()
        scale_mode = "factor" if self._radio_factor.isChecked() else "dimensions"
        algo_map = {
            "Lanczos": "lanczos",
            "Bicubic": "bicubic",
            "Bilinear": "bilinear",
            "Nearest Neighbor": "nearest",
        }
        fmt_text = self.out_format_combo.currentText()
        out_fmt = (
            None
            if fmt_text.startswith("Keep") or "---" in fmt_text
            else fmt_text.lower()
        )
        return {
            "files_to_process": files,
            "scale_mode": scale_mode,
            "scale_factor": self.scale_factor_spin.value(),
            "target_width": self.dim_w_spin.value()
            if scale_mode == "dimensions"
            else None,
            "target_height": self.dim_h_spin.value()
            if scale_mode == "dimensions"
            else None,
            "preserve_aspect_ratio": self.preserve_ar_cb.isChecked(),
            "algorithm": algo_map.get(self.algorithm_combo.currentText(), "lanczos"),
            "output_format": out_fmt,
            "output_path": self.out_dir_edit.text().strip() or None,
            "output_filename_prefix": self.prefix_edit.text().strip(),
            "delete_original": self.delete_cb.isChecked(),
            "use_multicore": self.multicore_cb.isChecked(),
        }

    @Slot(bool)
    def _start_worker(self, use_selection: bool):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
            self._on_done(0, "**Resampling cancelled**")
            return

        config = self._collect_config(use_selection)
        if not config["files_to_process"]:
            QMessageBox.warning(self, "No Files", "No files to resample.")
            return

        self.worker = SamplerWorker(config)
        self.worker.finished.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress_update.connect(self._on_progress)

        self.btn_all.setEnabled(False)
        self.btn_selected.setEnabled(False)
        cancel_btn = self.btn_selected if use_selection else self.btn_all
        cancel_btn.setEnabled(True)
        cancel_btn.setText("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { background-color: #cc3333; color: white; font-weight: bold; }"
        )

        n = len(config["files_to_process"])
        self.status_label.setText(f"Resampling {n} file(s)…") # pyrefly: ignore [missing-attribute]
        self.progress_bar.show()
        self.worker.start()

    @Slot(int)
    def _on_progress(self, pct: int):
        self.progress_bar.setValue(pct)
        self.status_label.setText(f"Resampling… {pct}% complete") # pyrefly: ignore [missing-attribute]

    @Slot(int, str)
    def _on_done(self, count: int, msg: str):
        self.btn_all.setEnabled(True)
        self.btn_all.setText("Resample All in Directory")
        self.btn_all.setStyleSheet(SHARED_BUTTON_STYLE)
        self.on_selection_changed()
        self.btn_selected.setStyleSheet(SHARED_BUTTON_STYLE)
        self.progress_bar.hide()
        self.progress_bar.setValue(0)
        self.status_label.setText(msg) # pyrefly: ignore [missing-attribute]
        self.worker = None
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Complete", msg)

    @Slot(str)
    def _on_error(self, msg: str):
        self._on_done(0, msg)
        QMessageBox.critical(self, "Error", msg)

    def cancel_loading(self):
        super().cancel_loading()
        if self.worker:
            with contextlib.suppress(Exception):
                self.worker.cancel()

    def get_default_config(self) -> dict:
        """Return the default tab configuration dict."""
        return {
            "input_path": "",
            "scale_mode": "factor",
            "scale_factor": 2.0,
            "target_width": 1920,
            "target_height": 1080,
            "preserve_aspect_ratio": True,
            "algorithm": "Lanczos",
            "output_format": "Keep original format",
            "output_path": "",
            "output_filename_prefix": "",
            "delete_original": False,
            "use_multicore": True,
        }

    def set_config(self, config: dict) -> None:
        """Populate input fields from a saved configuration dict."""
        try:
            # 1. Paths
            input_path = config.get("input_path", "")
            self.input_path.setText(input_path)

            output_path = config.get("output_path", "")
            self.out_dir_edit.setText(output_path)

            prefix = config.get("output_filename_prefix", config.get("prefix", ""))
            self.prefix_edit.setText(prefix)

            # 2. Scale mode and values
            scale_mode = config.get("scale_mode", "factor")
            if scale_mode == "factor":
                self._radio_factor.setChecked(True)
            else:
                self._radio_dims.setChecked(True)
            self._on_scale_mode_changed(scale_mode == "factor")

            self.scale_factor_spin.setValue(config.get("scale_factor", 2.0))
            self.dim_w_spin.setValue(config.get("target_width", 1920))
            self.dim_h_spin.setValue(config.get("target_height", 1080))
            self.preserve_ar_cb.setChecked(config.get("preserve_aspect_ratio", True))

            # 3. Algorithm
            algo = config.get("algorithm", "Lanczos")
            algo_map_rev = {
                "lanczos": "Lanczos",
                "bicubic": "Bicubic",
                "bilinear": "Bilinear",
                "nearest": "Nearest Neighbor",
            }
            mapped_algo = algo_map_rev.get(algo.lower(), algo)
            idx = self.algorithm_combo.findText(mapped_algo)
            if idx != -1:
                self.algorithm_combo.setCurrentIndex(idx)

            # 4. Output format
            out_fmt = config.get("output_format", "Keep original format")
            if not out_fmt:
                out_fmt = "Keep original format"
            idx_fmt = self.out_format_combo.findText(out_fmt, Qt.MatchFlag.MatchExactly)
            if idx_fmt == -1 and out_fmt != "Keep original format":
                idx_fmt = self.out_format_combo.findText(out_fmt.upper(), Qt.MatchFlag.MatchExactly)
            if idx_fmt != -1:
                self.out_format_combo.setCurrentIndex(idx_fmt)

            # 5. Checkboxes
            self.delete_cb.setChecked(config.get("delete_original", False))
            self.multicore_cb.setChecked(config.get("use_multicore", True))

            # 6. Restore selected files
            self._restore_selected_files(config)

            # 7. Scan/load data if valid directory
            if os.path.isdir(input_path):
                self._scan_and_load()

            print("SamplerSubTab configuration loaded.")
        except Exception as e:
            print(f"Error applying SamplerSubTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        self.cancel_loading()
        super().closeEvent(event)
