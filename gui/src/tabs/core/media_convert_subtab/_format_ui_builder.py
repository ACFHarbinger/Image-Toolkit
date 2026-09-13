"""Widget construction for ``FormatSubTab`` (``_build_ui``).

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import Optional, Set

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ....components import OptionalField, SectionedFormBuilder, VirtualDualGallery
from ....styles import apply_shadow_effect
from ....theming.theme_api import color, qss


class FormatUIBuilder:
    """Builds every widget/layout that makes up the FormatSubTab UI (§5 R2.f, #567)."""

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        builder = SectionedFormBuilder(self, scrollable=True)

        self._build_targets_section(builder)
        self._build_settings_section(builder)
        self._build_aspect_ratio_section(builder)
        self._build_progress_and_gallery(builder)
        self._build_actions_and_status(builder)

        builder.build(main_layout)
        self.clear_galleries()
        self.on_output_format_changed(self.output_format_combo.currentText())

    def _build_targets_section(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Convert Targets")

        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Path to directory containing images for conversion...")

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory_and_scan)

        self._btn_recent_dirs = QToolButton()
        self._btn_recent_dirs.setText("▼")
        self._btn_recent_dirs.setToolTip("Recent directories")
        self._btn_recent_dirs.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_recent_dirs.setFixedWidth(24)
        self._recent_dirs_menu = QMenu(self._btn_recent_dirs)
        self._btn_recent_dirs.setMenu(self._recent_dirs_menu)
        self._btn_recent_dirs.clicked.connect(self._show_recent_dirs_menu)

        sec.add_path_picker(
            self.input_path,
            btn_browse_scan,
            label="Input path:",
            recent_btn=self._btn_recent_dirs,
        )

    def _build_settings_section(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Convert Settings")

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["--- Images ---"])
        formatted_formats = [f for f in SUPPORTED_IMG_FORMATS]
        self.output_format_combo.addItems(formatted_formats)

        self.output_format_combo.addItems(["--- Videos ---"])
        video_formats = [f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS]
        self.output_format_combo.addItems(video_formats)

        self.output_format_combo.setCurrentText("png")
        self.output_format_combo.currentTextChanged.connect(self.on_output_format_changed)
        sec.add_row("Output format:", self.output_format_combo)

        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["Auto (Recommended)", "FFmpeg", "MoviePy"])
        self.engine_combo.setToolTip("Select the engine used for video conversion.")
        self.engine_label = QLabel("Video Engine:")
        sec.add_row(self.engine_label, self.engine_combo)

        # Output path and Filename Prefix
        output_settings_container = QVBoxLayout()
        h_output_dir = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Leave blank to save in the input directory")
        btn_output = QPushButton("Browse...")
        btn_output.clicked.connect(self.browse_output)
        apply_shadow_effect(btn_output, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
        h_output_dir.addWidget(self.output_path)
        h_output_dir.addWidget(btn_output)
        output_settings_container.addLayout(h_output_dir)

        h_output_name = QHBoxLayout()
        self.output_filename_prefix = QLineEdit()
        self.output_filename_prefix.setPlaceholderText(
            "e.g. 'processed_' (Files will be named processed_1.png, processed_2.png...)"
        )
        h_output_name.addWidget(QLabel("Filename Prefix:"))
        h_output_name.addWidget(self.output_filename_prefix)
        output_settings_container.addLayout(h_output_name)

        output_path_container = QWidget()
        output_path_container.setLayout(output_settings_container)
        self.output_field = OptionalField("Output Directory and Filename", output_path_container, start_open=False)
        sec.add_row(self.output_field)

        # Input formats
        self.selected_formats: Optional[Set[str]] = None
        if self.dropdown:
            self.selected_formats = set()
            formats_layout = QVBoxLayout()
            btn_layout = QHBoxLayout()
            self.format_buttons = {}
            for fmt in SUPPORTED_IMG_FORMATS:
                self._add_format_button(fmt, btn_layout)
            formats_layout.addLayout(btn_layout)
            self.formats_layout_ref = formats_layout
            self.format_btn_layout = btn_layout

            all_btn_layout = QHBoxLayout()
            self.btn_add_all = QPushButton("Add All")
            self.btn_add_all.setStyleSheet(qss("btn_success_solid"))
            apply_shadow_effect(self.btn_add_all, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
            self.btn_add_all.clicked.connect(self.add_all_formats)
            self.btn_remove_all = QPushButton("Remove All")
            self.btn_remove_all.setStyleSheet(qss("btn_danger_solid"))
            apply_shadow_effect(
                self.btn_remove_all,
                color_hex=color("window_bg"),
                radius=8,
                x_offset=0,
                y_offset=3,
            )
            self.btn_remove_all.clicked.connect(self.remove_all_formats)
            all_btn_layout.addWidget(self.btn_add_all)
            all_btn_layout.addWidget(self.btn_remove_all)
            formats_layout.addLayout(all_btn_layout)

            formats_container = QWidget()
            formats_container.setLayout(formats_layout)
            self.formats_field = OptionalField("Input formats to filter", formats_container, start_open=False)
            sec.add_row(self.formats_field)
        else:
            self.input_formats = QLineEdit()
            self.input_formats.setPlaceholderText("e.g. .jpg .png .gif")
            sec.add_row("Input formats (optional):", self.input_formats)

        self.multicore_checkbox = QCheckBox("Multi-core Processing (Faster for Batches)")
        self.multicore_checkbox.setToolTip("Process multiple files in parallel across multiple CPU cores.")
        self.multicore_checkbox.setStyleSheet(qss("convert_checkbox"))
        self.multicore_checkbox.setChecked(True)
        sec.add_row(self.multicore_checkbox)

        self.delete_checkbox = QCheckBox("Delete original files after conversion")
        self.delete_checkbox.setStyleSheet(qss("convert_checkbox"))
        self.delete_checkbox.setChecked(False)
        sec.add_row(self.delete_checkbox)

    def _build_aspect_ratio_section(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Aspect Ratio")

        self.enable_ar_checkbox = QCheckBox("Change Aspect Ratio")
        self.enable_ar_checkbox.setToolTip("Enable to resize, crop, or pad images to a specific aspect ratio.")
        self.enable_ar_checkbox.toggled.connect(self.toggle_ar_controls)
        sec.add_row(self.enable_ar_checkbox)

        ar_controls_layout = QHBoxLayout()

        self.ar_mode_combo = QComboBox()
        self.ar_mode_combo.addItems(["Crop", "Pad", "Stretch"])
        self.ar_mode_combo.setToolTip(
            "Crop: Cuts the image to fit.\nPad: Adds background bars (Letterbox).\nStretch: Distorts image to fit."
        )
        ar_controls_layout.addWidget(QLabel("Mode:"))
        ar_controls_layout.addWidget(self.ar_mode_combo)

        self.ar_combo = QComboBox()
        self.ar_combo.addItems(["16:9", "4:3", "1:1", "9:16", "3:2", "Custom"])
        self.ar_combo.currentTextChanged.connect(self.on_ar_combo_change)
        ar_controls_layout.addWidget(QLabel("Ratio:"))
        ar_controls_layout.addWidget(self.ar_combo)

        self.ar_w = QSpinBox()
        self.ar_w.setRange(1, 99999)
        self.ar_w.setValue(16)
        self.ar_h = QSpinBox()
        self.ar_h.setRange(1, 99999)
        self.ar_h.setValue(9)

        self.ar_custom_container = QWidget()
        custom_layout = QHBoxLayout(self.ar_custom_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("W:"))
        custom_layout.addWidget(self.ar_w)
        custom_layout.addWidget(QLabel("H:"))
        custom_layout.addWidget(self.ar_h)

        ar_controls_layout.addWidget(self.ar_custom_container)
        ar_controls_layout.addStretch()

        self.ar_controls_widget = QWidget()
        self.ar_controls_widget.setLayout(ar_controls_layout)
        self.ar_controls_widget.setEnabled(False)
        self.ar_custom_container.setVisible(False)

        sec.add_row(self.ar_controls_widget)

    def _build_progress_and_gallery(self, builder: SectionedFormBuilder) -> None:
        self.convert_progress_bar = QProgressBar()
        self.convert_progress_bar.setTextVisible(True)
        self.convert_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.convert_progress_bar.setStyleSheet(qss("convert_progress_bar"))
        self.convert_progress_bar.setMinimum(0)
        self.convert_progress_bar.setMaximum(100)
        self.convert_progress_bar.setValue(0)
        self.convert_progress_bar.hide()
        builder.add_widget(self.convert_progress_bar)

        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        builder.add_widget(self.scan_progress_bar)

        self.dual = VirtualDualGallery(self)
        self.dual.found_right_clicked.connect(self.show_image_context_menu)
        self.dual.found_activated.connect(self.handle_full_image_preview)
        self.dual.selected_right_clicked.connect(self.show_image_context_menu)
        self.dual.selected_activated.connect(self.handle_full_image_preview)
        self.dual.selection_changed.connect(self._sync_selection_from_dual)
        builder.add_widget(self.dual)
        builder.add_stretch(1)

    def _build_actions_and_status(self, builder: SectionedFormBuilder) -> None:
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_convert_all = QPushButton("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(qss("shared_button"))
        apply_shadow_effect(self.btn_convert_all, color_hex=color("window_bg"), radius=8, x_offset=0, y_offset=3)
        self.btn_convert_all.clicked.connect(lambda: self.start_conversion_worker(use_selection=False))
        button_layout.addWidget(self.btn_convert_all)

        self.btn_convert_contents = QPushButton("Convert Selected Files (0)")
        self.btn_convert_contents.setStyleSheet(qss("shared_button"))
        apply_shadow_effect(
            self.btn_convert_contents,
            color_hex=color("window_bg"),
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_convert_contents.clicked.connect(lambda: self.start_conversion_worker(use_selection=True))
        button_layout.addWidget(self.btn_convert_contents)

        builder.add_widget(button_container)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(qss("status_label_padded"))
        builder.add_widget(self.status_label)


__all__ = ["FormatUIBuilder"]
