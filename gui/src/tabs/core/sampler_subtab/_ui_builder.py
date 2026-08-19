"""Widget construction for ``SamplerSubTab`` (``_build_ui``).

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ....components import MarqueeScrollArea
from ....styles import SHARED_BUTTON_STYLE, apply_shadow_effect


class _UIBuilderMixin:
    """Builds the input/settings/output groups, progress bars, and galleries."""

    def _build_ui(self) -> None:
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
            "border-radius: 3px;  }"
            "QCheckBox::indicator:checked {  border: 1px solid #4CAF50; }"
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
            "QProgressBar {  color: white; border: 1px solid #4f545c; "
            "border-radius: 4px; padding: 2px; }"
            "QProgressBar::chunk {  border-radius: 4px; }"
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
            "QScrollArea { border: 1px solid #4f545c;  border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(500)
        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("")
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
            "QScrollArea { border: 1px solid #4f545c;  border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(300)
        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("")
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


__all__ = ["_UIBuilderMixin"]
