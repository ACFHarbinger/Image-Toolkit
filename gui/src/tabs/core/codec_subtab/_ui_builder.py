"""Widget construction for ``CodecSubTab`` (``_build_ui``).

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

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
from ._constants import (
    AUDIO_CODEC_OPTIONS,
    COMMON_SOURCE_AUDIO_CODECS,
    COMMON_SOURCE_VIDEO_CODECS,
    SPEED_OPTIONS,
    VIDEO_CODEC_OPTIONS,
)


class _UIBuilderMixin:
    """Builds every widget/layout that makes up the CodecSubTab UI."""

    def _build_ui(self) -> None:
        # --- UI Setup ---
        main_layout = QVBoxLayout(self)

        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setStyleSheet("QScrollArea { border: none; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # --- 1. Convert Targets Group ---
        target_group = QGroupBox("Convert Targets")
        target_layout = QFormLayout(target_group)
        v_input_group = QVBoxLayout()

        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText(
            "Path to directory containing videos for re-encoding..."
        )
        input_layout.addWidget(self.input_path)

        btn_browse_scan = QPushButton("Browse...")
        btn_browse_scan.clicked.connect(self.browse_directory_and_scan)
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        input_layout.addWidget(btn_browse_scan)

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

        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(list(VIDEO_CODEC_OPTIONS.keys()))
        settings_layout.addRow("Target Video Codec:", self.video_codec_combo)

        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(list(AUDIO_CODEC_OPTIONS.keys()))
        settings_layout.addRow("Target Audio Codec:", self.audio_codec_combo)

        quality_layout = QHBoxLayout()
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 63)
        self.crf_spin.setValue(28)
        self.crf_spin.setToolTip(
            "Quality factor for the target video codec. Lower = higher quality "
            "and larger file size. Automatically clamped to each codec's valid range."
        )
        quality_layout.addWidget(QLabel("Quality (CRF):"))
        quality_layout.addWidget(self.crf_spin)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(list(SPEED_OPTIONS.keys()))
        self.speed_combo.setCurrentText("Balanced")
        self.speed_combo.setToolTip(
            "Encoding speed vs. compression efficiency trade-off."
        )
        quality_layout.addWidget(QLabel("Speed:"))
        quality_layout.addWidget(self.speed_combo)
        quality_layout.addStretch()

        settings_layout.addRow(quality_layout)

        # Output path and filename prefix
        output_settings_container = QVBoxLayout()

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

        h_output_name = QHBoxLayout()
        self.output_filename_prefix = QLineEdit()
        self.output_filename_prefix.setPlaceholderText(
            "e.g. 'av1_' (Files will be named av1_1.mp4, av1_2.mp4...)"
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

        # Filter by source video codec
        self.video_codec_buttons: dict = {}
        video_filter_layout = QVBoxLayout()
        video_filter_btn_layout = QHBoxLayout()
        for codec in COMMON_SOURCE_VIDEO_CODECS:
            self._add_codec_filter_button(
                codec, video_filter_btn_layout, self.video_codec_buttons,
                self.selected_video_codecs,
            )
        video_filter_layout.addLayout(video_filter_btn_layout)
        video_filter_container = QWidget()
        video_filter_container.setLayout(video_filter_layout)
        self.video_filter_field = OptionalField(
            "Filter by source video codec", video_filter_container, start_open=False
        )
        settings_layout.addRow(self.video_filter_field)

        # Filter by source audio codec
        self.audio_codec_buttons: dict = {}
        audio_filter_layout = QVBoxLayout()
        audio_filter_btn_layout = QHBoxLayout()
        for codec in COMMON_SOURCE_AUDIO_CODECS:
            self._add_codec_filter_button(
                codec, audio_filter_btn_layout, self.audio_codec_buttons,
                self.selected_audio_codecs,
            )
        audio_filter_layout.addLayout(audio_filter_btn_layout)
        audio_filter_container = QWidget()
        audio_filter_container.setLayout(audio_filter_layout)
        self.audio_filter_field = OptionalField(
            "Filter by source audio codec", audio_filter_container, start_open=False
        )
        settings_layout.addRow(self.audio_filter_field)

        self.multicore_checkbox = QCheckBox(
            "Multi-core Processing (Faster for Batches)"
        )
        self.multicore_checkbox.setToolTip(
            "Process multiple files in parallel across multiple CPU cores."
        )
        self.multicore_checkbox.setStyleSheet(
            """
            QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; border-radius: 3px;  }
            QCheckBox::indicator:checked {  border: 1px solid #4CAF50; image: url(./src/gui/assets/check.png); }
        """
        )
        self.multicore_checkbox.setChecked(True)
        settings_layout.addRow(self.multicore_checkbox)

        self.delete_checkbox = QCheckBox("Delete original files after conversion")
        self.delete_checkbox.setStyleSheet(self.multicore_checkbox.styleSheet())
        self.delete_checkbox.setChecked(False)
        settings_layout.addRow(self.delete_checkbox)

        content_layout.addWidget(settings_group)

        # --- 3. Galleries ---

        self.convert_progress_bar = QProgressBar()
        self.convert_progress_bar.setTextVisible(True)
        self.convert_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.convert_progress_bar.setStyleSheet(
            "QProgressBar {  color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 2px; }"
            "QProgressBar::chunk {  border-radius: 4px; }"
        )
        self.convert_progress_bar.setMinimum(0)
        self.convert_progress_bar.setMaximum(100)
        self.convert_progress_bar.setValue(0)
        self.convert_progress_bar.hide()
        content_layout.addWidget(self.convert_progress_bar)

        # Reused for both the directory scan and the codec-probing pass.
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(True)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

        self.found_gallery_scroll = MarqueeScrollArea()
        self.found_gallery_scroll.setWidgetResizable(True)
        self.found_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c;  border-radius: 8px; }"
        )
        self.found_gallery_scroll.setMinimumHeight(600)

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

        self.selected_gallery_scroll = MarqueeScrollArea()
        self.selected_gallery_scroll.setWidgetResizable(True)
        self.selected_gallery_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c;  border-radius: 8px; }"
        )
        self.selected_gallery_scroll.setMinimumHeight(400)

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

        self.clear_galleries()


__all__ = ["_UIBuilderMixin"]
