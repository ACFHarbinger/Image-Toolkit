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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ....components import SectionedFormBuilder, VirtualDualGallery
from ....styles import apply_shadow_effect
from ....theming.theme_api import color, qss
from ._tab_bound import TabBoundController


class SamplerUIBuilder(TabBoundController):
    """Builds the input/settings/output groups, progress bars, and galleries (§5 R2.f, #567)."""

    def build_ui(self) -> None:
        main_layout = QVBoxLayout(self.tab)
        builder = SectionedFormBuilder(self.tab, scrollable=True)

        self._build_input_section(builder)
        self._build_settings_section(builder)
        self._build_output_section(builder)
        self._build_gallery_section(builder)
        self._build_actions_section(builder)

        builder.build(main_layout)
        self.clear_galleries()

    def _build_input_section(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Input")

        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Directory or single file to resample…")
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_input)
        apply_shadow_effect(btn_browse, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)

        sec.add_path_picker(
            self.input_path,
            btn_browse,
            label="Input path:",
        )

    def _build_settings_section(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Sampling Settings")

        # Scale mode radio buttons
        mode_row = QHBoxLayout()
        self._scale_mode_group = QButtonGroup(self.tab)
        self._radio_factor = QRadioButton("Scale factor")
        self._radio_dims = QRadioButton("Target dimensions")
        self._radio_factor.setChecked(True)
        self._scale_mode_group.addButton(self._radio_factor, 0)
        self._scale_mode_group.addButton(self._radio_dims, 1)
        self._radio_factor.toggled.connect(self._on_scale_mode_changed)
        mode_row.addWidget(self._radio_factor)
        mode_row.addWidget(self._radio_dims)
        mode_row.addStretch()
        sec.add_row("Scale mode:", mode_row)

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
        sec.add_row("Scale:", scale_container)

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["Lanczos", "Bicubic", "Bilinear", "Nearest Neighbor"])
        self.algorithm_combo.setToolTip(
            "Lanczos: highest quality, slower\n"
            "Bicubic: good quality, moderate speed\n"
            "Bilinear: fast, acceptable quality\n"
            "Nearest Neighbor: pixel-perfect, aliased"
        )
        sec.add_row("Algorithm:", self.algorithm_combo)

        self.multicore_cb = QCheckBox("Multi-core processing (faster for batches)")
        self.multicore_cb.setChecked(True)
        self.multicore_cb.setStyleSheet(qss("convert_checkbox"))
        sec.add_row(self.multicore_cb)

        self.delete_cb = QCheckBox("Delete originals after resampling")
        self.delete_cb.setChecked(False)
        self.delete_cb.setStyleSheet(qss("convert_checkbox"))
        sec.add_row(self.delete_cb)

    def _build_output_section(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Output Settings")

        self.out_format_combo = QComboBox()
        self.out_format_combo.addItem("Keep original format")
        self.out_format_combo.addItems(["--- Images ---"])
        self.out_format_combo.addItems(list(SUPPORTED_IMG_FORMATS))
        self.out_format_combo.addItems(["--- Videos ---"])
        self.out_format_combo.addItems([f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS])
        sec.add_row("Output format:", self.out_format_combo)

        out_dir_row = QHBoxLayout()
        self.out_dir_edit = QLineEdit()
        self.out_dir_edit.setPlaceholderText("Leave blank to save alongside originals")
        btn_out_browse = QPushButton("Browse…")
        btn_out_browse.clicked.connect(self._browse_output)
        apply_shadow_effect(btn_out_browse, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
        out_dir_row.addWidget(self.out_dir_edit)
        out_dir_row.addWidget(btn_out_browse)
        sec.add_row("Output directory:", out_dir_row)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("e.g. 'upscaled_'  (leave blank to auto-suffix)")
        sec.add_row("Filename prefix:", self.prefix_edit)

    def _build_gallery_section(self, builder: SectionedFormBuilder) -> None:
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setStyleSheet(qss("convert_progress_bar"))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        builder.add_widget(self.progress_bar)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        builder.add_widget(self.scan_progress_bar)

        # Found + Selected galleries (virtual-scroll, GUI/UX §2.1 Option A).
        # Replaces the two MarqueeScrollArea + QGridLayout grids; pagination is
        # dropped and selection lives in the dual gallery's selection models.
        self.dual = VirtualDualGallery(self.tab)
        self.dual.found_right_clicked.connect(self.show_image_context_menu)
        self.dual.found_activated.connect(self.handle_full_image_preview)
        self.dual.selected_right_clicked.connect(self.show_image_context_menu)
        self.dual.selected_activated.connect(self.handle_full_image_preview)
        self.dual.selection_changed.connect(self._sync_selection_from_dual)
        builder.add_widget(self.dual)
        builder.add_stretch(1)

    def _build_actions_section(self, builder: SectionedFormBuilder) -> None:
        btn_container = QWidget()
        btn_row = QHBoxLayout(btn_container)
        btn_row.setContentsMargins(0, 0, 0, 0)

        self.btn_all = QPushButton("Resample All in Directory")
        self.btn_all.setStyleSheet(qss("shared_button"))
        apply_shadow_effect(self.btn_all, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
        self.btn_all.clicked.connect(lambda: self._start_worker(use_selection=False))

        self.btn_selected = QPushButton("Resample Selected (0)")
        self.btn_selected.setStyleSheet(qss("shared_button"))
        self.btn_selected.setEnabled(False)
        apply_shadow_effect(self.btn_selected, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
        self.btn_selected.clicked.connect(lambda: self._start_worker(use_selection=True))

        btn_row.addWidget(self.btn_all)
        btn_row.addWidget(self.btn_selected)
        builder.add_widget(btn_container)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(qss("status_label_padded"))
        builder.add_widget(self.status_label)

    _build_ui = build_ui


__all__ = ["SamplerUIBuilder"]
