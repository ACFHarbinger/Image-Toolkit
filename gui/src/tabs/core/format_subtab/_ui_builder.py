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
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ....components import MarqueeScrollArea, OptionalField
from ....styles import SHARED_BUTTON_STYLE, apply_shadow_effect


class _UIBuilderMixin:
    """Builds every widget/layout that makes up the FormatSubTab UI."""

    def _build_ui(self) -> None:
        # --- UI Setup ---
        main_layout = QVBoxLayout(self)

        # Page Scroll Area
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- 1. Convert Targets Group ---
        target_group = QGroupBox("Convert Targets")
        target_layout = QFormLayout(target_group)
        v_input_group = QVBoxLayout()

        # Input path
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText(
            "Path to directory containing images for conversion..."
        )
        input_layout.addWidget(self.input_path)

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory_and_scan)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        input_layout.addWidget(btn_browse_scan)

        # §2.21D — MRU recent-dirs dropdown button
        self._btn_recent_dirs = QToolButton()
        self._btn_recent_dirs.setText("▼")
        self._btn_recent_dirs.setToolTip("Recent directories")
        self._btn_recent_dirs.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._btn_recent_dirs.setFixedWidth(24)
        self._recent_dirs_menu = QMenu(self._btn_recent_dirs)
        self._btn_recent_dirs.setMenu(self._recent_dirs_menu)
        self._btn_recent_dirs.clicked.connect(self._show_recent_dirs_menu)
        input_layout.addWidget(self._btn_recent_dirs)

        v_input_group.addLayout(input_layout)
        target_layout.addRow("Input path:", v_input_group)
        content_layout.addWidget(target_group)

        # --- 2. Convert Settings Group ---
        settings_group = QGroupBox("Convert Settings")
        settings_layout = QFormLayout(settings_group)

        # Output format
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(["--- Images ---"])
        formatted_formats = [f for f in SUPPORTED_IMG_FORMATS]
        self.output_format_combo.addItems(formatted_formats)

        self.output_format_combo.addItems(["--- Videos ---"])
        video_formats = [f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS]
        self.output_format_combo.addItems(video_formats)

        self.output_format_combo.setCurrentText("png")
        self.output_format_combo.currentTextChanged.connect(
            self.on_output_format_changed
        )
        settings_layout.addRow("Output format:", self.output_format_combo)

        # New Video Engine Selection
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["Auto (Recommended)", "FFmpeg", "MoviePy"])
        self.engine_combo.setToolTip("Select the engine used for video conversion.")
        self.engine_label = QLabel("Video Engine:")  # Keep ref to hide/show
        settings_layout.addRow(self.engine_label, self.engine_combo)

        # Output path and Filename Prefix (UPDATED LAYOUT)
        output_settings_container = QVBoxLayout()

        # Output Directory Path
        h_output_dir = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText(
            "Leave blank to save in the input directory"
        )
        btn_output = QPushButton("Browse...")
        btn_output.clicked.connect(self.browse_output)
        apply_shadow_effect(
            btn_output, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        h_output_dir.addWidget(self.output_path)
        h_output_dir.addWidget(btn_output)
        output_settings_container.addLayout(h_output_dir)

        # Output Filename Prefix (NEW)
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
        self.output_field = OptionalField(
            "Output Directory and Filename", output_path_container, start_open=False
        )
        settings_layout.addRow(self.output_field)

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
            self.formats_layout_ref = (
                formats_layout  # Store ref to clear later if needed
            )
            self.format_btn_layout = btn_layout

            all_btn_layout = QHBoxLayout()
            self.btn_add_all = QPushButton("Add All")
            self.btn_add_all.setStyleSheet("background-color: green; color: white;")
            apply_shadow_effect(
                self.btn_add_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3
            )
            self.btn_add_all.clicked.connect(self.add_all_formats)
            self.btn_remove_all = QPushButton("Remove All")
            self.btn_remove_all.setStyleSheet("background-color: red; color: white;")
            apply_shadow_effect(
                self.btn_remove_all,
                color_hex="#000000",
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
            self.formats_field = OptionalField(
                "Input formats to filter", formats_container, start_open=False
            )
            settings_layout.addRow(self.formats_field)
        else:
            self.input_formats = QLineEdit()
            self.input_formats.setPlaceholderText("e.g. .jpg .png .gif")
            settings_layout.addRow("Input formats (optional):", self.input_formats)

        self.multicore_checkbox = QCheckBox(
            "Multi-core Processing (Faster for Batches)"
        )
        self.multicore_checkbox.setToolTip(
            "Process multiple files in parallel across multiple CPU cores."
        )
        self.multicore_checkbox.setStyleSheet(
            """
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; border-radius: 3px; background-color: #333; }
            QCheckBox::indicator:checked { background-color: #4CAF50; border: 1px solid #4CAF50; image: url(./src/gui/assets/check.png); }
        """
        )
        self.multicore_checkbox.setChecked(True)
        settings_layout.addRow(self.multicore_checkbox)

        self.delete_checkbox = QCheckBox("Delete original files after conversion")
        self.delete_checkbox.setStyleSheet(self.multicore_checkbox.styleSheet())
        self.delete_checkbox.setChecked(False)
        settings_layout.addRow(self.delete_checkbox)

        content_layout.addWidget(settings_group)

        # --- 3. Aspect Ratio Group ---
        ar_group = QGroupBox("Aspect Ratio")
        ar_layout = QFormLayout(ar_group)

        self.enable_ar_checkbox = QCheckBox("Change Aspect Ratio")
        self.enable_ar_checkbox.setToolTip(
            "Enable to resize, crop, or pad images to a specific aspect ratio."
        )
        self.enable_ar_checkbox.toggled.connect(self.toggle_ar_controls)
        ar_layout.addRow(self.enable_ar_checkbox)

        # AR Controls
        ar_controls_layout = QHBoxLayout()

        # Mode Selection
        self.ar_mode_combo = QComboBox()
        self.ar_mode_combo.addItems(["Crop", "Pad", "Stretch"])
        self.ar_mode_combo.setToolTip(
            "Crop: Cuts the image to fit.\n"
            "Pad: Adds background bars (Letterbox).\n"
            "Stretch: Distorts image to fit."
        )
        ar_controls_layout.addWidget(QLabel("Mode:"))
        ar_controls_layout.addWidget(self.ar_mode_combo)

        # Preset Selection
        self.ar_combo = QComboBox()
        self.ar_combo.addItems(["16:9", "4:3", "1:1", "9:16", "3:2", "Custom"])
        self.ar_combo.currentTextChanged.connect(self.on_ar_combo_change)
        ar_controls_layout.addWidget(QLabel("Ratio:"))
        ar_controls_layout.addWidget(self.ar_combo)

        # Custom W/H
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
        self.ar_controls_widget.setEnabled(False)  # Start disabled
        self.ar_custom_container.setVisible(
            False
        )  # Start hidden (preset 16:9 selected)

        ar_layout.addRow(self.ar_controls_widget)
        content_layout.addWidget(ar_group)

        # --- 4. Galleries ---

        # Conversion Progress Bar
        self.convert_progress_bar = QProgressBar()
        self.convert_progress_bar.setTextVisible(True)
        self.convert_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.convert_progress_bar.setStyleSheet(
            "QProgressBar { background-color: #36393f; color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 2px; }"
            "QProgressBar::chunk { background-color: #5865f2; border-radius: 4px; }"
        )
        self.convert_progress_bar.setMinimum(0)
        self.convert_progress_bar.setMaximum(100)
        self.convert_progress_bar.setValue(0)
        self.convert_progress_bar.hide()
        content_layout.addWidget(self.convert_progress_bar)

        # Scan Progress Bar (Existing)
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(False)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        # Found Files (Top)
        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(600)

        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet("background-color: #2c2f33;")
        self.found_gallery_layout = QGridLayout(self.gallery_widget)
        self.found_gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.found_gallery_scroll.setWidget(self.gallery_widget)

        # Connect Base logic
        self.found_gallery_scroll.selection_changed.connect(
            self.handle_marquee_selection
        )

        # Add shared search input (Lazy Search) for Found Gallery
        content_layout.addWidget(self.found_search_input)

        content_layout.addWidget(self.found_gallery_scroll, 1)

        # Add Pagination Widget (Found)
        if hasattr(self, "found_pagination_widget"):
            content_layout.addWidget(
                self.found_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        # Selected Files (Bottom)
        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(400)

        self.selected_widget = QWidget()
        self.selected_widget.setStyleSheet("background-color: #2c2f33;")
        self.selected_gallery_layout = QGridLayout(self.selected_widget)
        self.selected_gallery_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.selected_gallery_scroll.setWidget(self.selected_widget)
        content_layout.addWidget(self.selected_gallery_scroll, 1)

        # Add Pagination Widget (Selected)
        if hasattr(self, "selected_pagination_widget"):
            content_layout.addWidget(
                self.selected_pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
            )

        content_layout.addStretch(1)

        # --- Buttons ---
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_convert_all = QPushButton("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(
            self.btn_convert_all, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.btn_convert_all.clicked.connect(
            lambda: self.start_conversion_worker(use_selection=False)
        )
        button_layout.addWidget(self.btn_convert_all)

        self.btn_convert_contents = QPushButton("Convert Selected Files (0)")
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)
        apply_shadow_effect(
            self.btn_convert_contents,
            color_hex="#000000",
            radius=8,
            x_offset=0,
            y_offset=3,
        )
        self.btn_convert_contents.clicked.connect(
            lambda: self.start_conversion_worker(use_selection=True)
        )
        button_layout.addWidget(self.btn_convert_contents)

        content_layout.addWidget(button_container)

        self.status_label = QLabel("Ready.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: #666; font-style: italic; padding: 8px;"
        )
        content_layout.addWidget(self.status_label)

        page_scroll.setWidget(content_widget)
        main_layout.addWidget(page_scroll)

        # Initial Clear
        self.clear_galleries()

        # Trigger initial state
        self.on_output_format_changed(self.output_format_combo.currentText())


__all__ = ["_UIBuilderMixin"]
