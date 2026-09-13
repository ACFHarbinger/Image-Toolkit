"""Widget construction for ``CodecSubTab`` (``_build_ui``).

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from ._codec_constants import (
    AUDIO_CODEC_OPTIONS,
    COMMON_SOURCE_AUDIO_CODECS,
    COMMON_SOURCE_VIDEO_CODECS,
    SPEED_OPTIONS,
    VIDEO_CODEC_OPTIONS,
)

if TYPE_CHECKING:
    pass


class CodecUIBuilder:
    """Builds every widget/layout that makes up the CodecSubTab UI (§5 R2.f, #567)."""

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        builder = SectionedFormBuilder(self, scrollable=True)

        self._build_targets_section(builder)
        self._build_settings_section(builder)
        self._build_progress_and_gallery(builder)
        self._build_actions_and_status(builder)

        builder.build(main_layout)
        self.clear_galleries()

    def _build_targets_section(self, builder: SectionedFormBuilder) -> None:
        sec = builder.add_section("Convert Targets")

        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Path to directory containing videos for re-encoding...")

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

        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(list(VIDEO_CODEC_OPTIONS.keys()))
        sec.add_row("Target Video Codec:", self.video_codec_combo)

        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(list(AUDIO_CODEC_OPTIONS.keys()))
        sec.add_row("Target Audio Codec:", self.audio_codec_combo)

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
        self.speed_combo.setToolTip("Encoding speed vs. compression efficiency trade-off.")
        quality_layout.addWidget(QLabel("Speed:"))
        quality_layout.addWidget(self.speed_combo)
        quality_layout.addStretch()
        sec.add_row(None, quality_layout)

        # Output path and filename prefix
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
        self.output_filename_prefix.setPlaceholderText("e.g. 'av1_' (Files will be named av1_1.mp4, av1_2.mp4...)")
        h_output_name.addWidget(QLabel("Filename Prefix:"))
        h_output_name.addWidget(self.output_filename_prefix)
        output_settings_container.addLayout(h_output_name)

        output_path_container = QWidget()
        output_path_container.setLayout(output_settings_container)
        self.output_field = OptionalField("Output Directory and Filename", output_path_container, start_open=False)
        sec.add_row(self.output_field)

        # Filters
        self.video_codec_buttons: dict = {}
        video_filter_layout = QVBoxLayout()
        video_filter_btn_layout = QHBoxLayout()
        for codec in COMMON_SOURCE_VIDEO_CODECS:
            self._add_codec_filter_button(
                codec,
                video_filter_btn_layout,
                self.video_codec_buttons,
                self.selected_video_codecs,
            )
        video_filter_layout.addLayout(video_filter_btn_layout)
        video_filter_container = QWidget()
        video_filter_container.setLayout(video_filter_layout)
        self.video_filter_field = OptionalField(
            "Filter by source video codec", video_filter_container, start_open=False
        )
        sec.add_row(self.video_filter_field)

        self.audio_codec_buttons: dict = {}
        audio_filter_layout = QVBoxLayout()
        audio_filter_btn_layout = QHBoxLayout()
        for codec in COMMON_SOURCE_AUDIO_CODECS:
            self._add_codec_filter_button(
                codec,
                audio_filter_btn_layout,
                self.audio_codec_buttons,
                self.selected_audio_codecs,
            )
        audio_filter_layout.addLayout(audio_filter_btn_layout)
        audio_filter_container = QWidget()
        audio_filter_container.setLayout(audio_filter_layout)
        self.audio_filter_field = OptionalField(
            "Filter by source audio codec", audio_filter_container, start_open=False
        )
        sec.add_row(self.audio_filter_field)

        self.multicore_checkbox = QCheckBox("Multi-core Processing (Faster for Batches)")
        self.multicore_checkbox.setToolTip("Process multiple files in parallel across multiple CPU cores.")
        self.multicore_checkbox.setStyleSheet(qss("convert_checkbox"))
        self.multicore_checkbox.setChecked(True)
        sec.add_row(self.multicore_checkbox)

        self.delete_checkbox = QCheckBox("Delete original files after conversion")
        self.delete_checkbox.setStyleSheet(qss("convert_checkbox"))
        self.delete_checkbox.setChecked(False)
        sec.add_row(self.delete_checkbox)

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
        self.scan_progress_bar.setTextVisible(True)
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


__all__ = ["CodecUIBuilder"]
