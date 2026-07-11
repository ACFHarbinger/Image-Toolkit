import contextlib
import os
import platform
import subprocess
from typing import Optional, Set

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction, QImage, QPixmap
from PySide6.QtWidgets import (
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
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ....classes import AbstractClassTwoGalleries
from ....components import ClickableLabel, MarqueeScrollArea, OptionalField
from ....helpers import CodecConversionWorker, CodecScanWorker
from ....styles import SHARED_BUTTON_STYLE, apply_shadow_effect
from ....utils.sort_utils import natural_sort_key

# Target codec label -> internal key. "copy" means "leave this stream alone".
VIDEO_CODEC_OPTIONS = {
    "Keep Original (No Re-encode)": "copy",
    "H.264": "h264",
    "H.265 / HEVC": "hevc",
    "AV1": "av1",
    "VP9": "vp9",
}
AUDIO_CODEC_OPTIONS = {
    "Keep Original (No Re-encode)": "copy",
    "AAC": "aac",
    "Opus": "opus",
    "MP3": "mp3",
    "FLAC": "flac",
}
SPEED_OPTIONS = {
    "Fastest": 0,
    "Fast": 1,
    "Balanced": 2,
    "Slow": 3,
    "Best Quality": 4,
}

# Common codecs offered as source-filter toggle buttons. Not exhaustive --
# any file whose probed codec isn't in the active filter set is simply
# excluded, so obscure codecs are still handled correctly, just without a
# dedicated button.
COMMON_SOURCE_VIDEO_CODECS = [
    "h264",
    "hevc",
    "vp9",
    "av1",
    "mpeg4",
    "mpeg2video",
    "vc1",
    "prores",
]
COMMON_SOURCE_AUDIO_CODECS = [
    "aac",
    "mp3",
    "ac3",
    "dts",
    "opus",
    "flac",
    "vorbis",
    "pcm_s16le",
]


class CodecSubTab(AbstractClassTwoGalleries):
    """Convert tab subtab for re-encoding a video's video and/or audio stream
    to a different codec (e.g. HEVC -> AV1) while keeping the container.
    """

    def __init__(self):
        super().__init__()
        self.worker: Optional[CodecConversionWorker] = None
        self._codec_scan_worker: Optional[CodecScanWorker] = None
        self._codec_probe_results: dict = {}
        self.selected_video_codecs: Set[str] = set()
        self.selected_audio_codecs: Set[str] = set()

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

        # --- 3. Galleries ---

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

        # Reused for both the directory scan and the codec-probing pass.
        self.scan_progress_bar = QProgressBar()
        self.scan_progress_bar.setTextVisible(True)
        self.scan_progress_bar.hide()
        content_layout.addWidget(self.scan_progress_bar)

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

    def _add_codec_filter_button(self, codec: str, layout, button_map: dict, selection_set: Set[str]):
        btn = QPushButton(codec)
        btn.setCheckable(True)
        btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
        apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)
        btn.clicked.connect(
            lambda checked, c=codec, m=button_map, s=selection_set: self._toggle_codec_filter(
                c, checked, m, s
            )
        )
        layout.addWidget(btn)
        button_map[codec] = btn

    def _toggle_codec_filter(self, codec: str, checked: bool, button_map: dict, selection_set: Set[str]):
        btn = button_map[codec]
        if checked:
            selection_set.add(codec)
            btn.setStyleSheet(
                """
                QPushButton:checked { background-color: #3320b5; color: white; }
                QPushButton:hover { background-color: #00838a; }
            """
            )
        else:
            selection_set.discard(codec)
            btn.setStyleSheet("QPushButton:hover { background-color: #3498db; }")
        apply_shadow_effect(btn, color_hex="#000000", radius=8, x_offset=0, y_offset=3)

    # --- IMPLEMENTING ABSTRACT METHODS ---

    def create_card_widget(
        self, path: str, pixmap: Optional[QPixmap], is_selected: bool
    ) -> QWidget:
        thumb_size = self.thumbnail_size
        card_wrapper = ClickableLabel(path)
        card_wrapper.setFixedSize(thumb_size + 10, thumb_size + 10)
        card_wrapper.get_pixmap = lambda: img_label.pixmap()

        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)

        card_wrapper.set_image_label(img_label)
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                thumb_size,
                thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(scaled)
        else:
            img_label.setText("Loading...")
            img_label.setStyleSheet("color: #3498db; border: 2px dashed #3498db;")

        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)

        self._update_card_style(img_label, is_selected)

        card_wrapper.path_double_clicked.connect(self.handle_full_image_preview)
        card_wrapper.path_right_clicked.connect(self.show_image_context_menu)

        return card_wrapper

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        if not isinstance(widget, ClickableLabel):
            return

        img_label = widget.findChild(QLabel)
        if not img_label:
            return

        if pixmap and not pixmap.isNull():
            if isinstance(pixmap, QImage):
                pixmap = QPixmap.fromImage(pixmap)

            thumb_size = self.thumbnail_size
            scaled = pixmap.scaled(
                thumb_size,
                thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            img_label.setPixmap(scaled)
            img_label.setText("")
        else:
            img_label.clear()
            img_label.setText("Loading...")

        is_selected = widget.path in self.selected_files
        self._update_card_style(img_label, is_selected)

    def _update_card_style(self, img_label: QLabel, is_selected: bool):
        if is_selected:
            img_label.setStyleSheet(
                "border: 3px solid #5865f2; background-color: #36393f;"
            )
        else:
            if img_label.pixmap() and not img_label.pixmap().isNull():
                img_label.setStyleSheet(
                    "border: 1px solid #4f545c; background-color: #36393f;"
                )
            else:
                img_label.setStyleSheet("border: 1px dashed #666; color: #999;")

    def on_selection_changed(self):
        count = len(self.selected_files)
        self.btn_convert_contents.setText(f"Convert Selected Files ({count})")
        self.btn_convert_contents.setEnabled(count > 0)

    # --- INTERACTION HANDLERS ---

    @Slot(str)
    def handle_full_image_preview(self, video_path: str):
        if not os.path.exists(video_path):
            return
        try:
            if platform.system() == "Windows":
                os.startfile(video_path)  # pyrefly: ignore [missing-attribute]
            elif platform.system() == "Linux":
                subprocess.Popen(
                    ["xdg-open", video_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["open", video_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            QMessageBox.warning(
                self, "Video Error", f"Could not launch video player: {e}"
            )

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        view_action = QAction("Open in External Player", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Deselect video from conversion"
            if is_selected
            else "Select video to convert"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)

        menu.exec(global_pos)

    # --- INPUT LOGIC ---

    @Slot()
    def browse_directory_and_scan(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select input directory",
            self.last_browsed_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self._push_dir_history(self.last_browsed_dir)
            self.input_path.setText(directory)
            self.last_browsed_dir = directory
            self._add_recent_dir(directory)
            self.scan_directory_visual()

    def _navigate_to_dir(self, path: str) -> None:
        if not os.path.isdir(path):
            return
        self.input_path.setText(path)
        self.last_browsed_dir = path
        self._add_recent_dir(path)
        self.scan_directory_visual()

    def _show_recent_dirs_menu(self) -> None:
        self._recent_dirs_menu.clear()
        dirs = self._get_recent_dirs()
        if not dirs:
            act = self._recent_dirs_menu.addAction("(no recent directories)")
            act.setEnabled(False)
        else:
            for d in dirs:
                act = self._recent_dirs_menu.addAction(d)
                act.triggered.connect(
                    lambda checked=False, p=d: self._navigate_to_dir(p)
                )
        self._recent_dirs_menu.exec(
            self._btn_recent_dirs.mapToGlobal(self._btn_recent_dirs.rect().bottomLeft())
        )

    @Slot()
    def browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            "",
        )
        if directory:
            self.output_path.setText(directory)

    def collect_paths(self) -> list[str]:
        """Lists candidate video files by extension only. Codec filtering (if
        any source-codec filters are active) happens after this, once each
        file's codec has been probed -- see scan_directory_visual()."""
        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            return []

        vid_formats = [f.lstrip(".").lower() for f in SUPPORTED_VIDEO_FORMATS]
        paths = []
        from gui.src.windows.settings.app_settings import AppSettings
        if AppSettings.recursive_scan():
            for root, _, files in os.walk(p):
                for file in files:
                    file_ext = os.path.splitext(file)[1].lstrip(".").lower()
                    if file_ext in vid_formats:
                        paths.append(os.path.join(root, file))
        else:
            with os.scandir(p) as it:
                for entry in it:
                    if entry.is_file():
                        file_ext = os.path.splitext(entry.name)[1].lstrip(".").lower()
                        if file_ext in vid_formats:
                            paths.append(entry.path)
        return paths

    @Slot()
    def scan_directory_visual(self):
        paths = self.collect_paths()
        if not paths:
            QMessageBox.information(self, "No Files", "No matching video files found.")
            self.clear_galleries()
            return

        if not self.selected_video_codecs and not self.selected_audio_codecs:
            self.start_loading_thumbnails(sorted(paths, key=natural_sort_key))
            return

        self._start_codec_probe_scan(paths)

    def _start_codec_probe_scan(self, paths: list[str]):
        if self._codec_scan_worker is not None:
            self._codec_scan_worker.stop()
            self._codec_scan_worker = None

        self._codec_probe_results = {}
        self.scan_progress_bar.setMinimum(0)
        self.scan_progress_bar.setMaximum(len(paths))
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.setFormat("Probing codecs... %v/%m")
        self.scan_progress_bar.show()
        self.status_label.setText(f"Probing codecs for {len(paths)} file(s)...") # pyrefly: ignore [missing-attribute]

        worker = CodecScanWorker(paths)
        worker.signals.codec_ready.connect(self._on_codec_probe_result)
        worker.signals.finished.connect(self._on_codec_probe_finished)
        self._codec_scan_worker = worker
        self.thread_pool.start(worker)

    @Slot(str, object, object)
    def _on_codec_probe_result(self, path: str, video_codec, audio_codec):
        self._codec_probe_results[path] = (video_codec, audio_codec)
        self.scan_progress_bar.setValue(len(self._codec_probe_results))

    @Slot()
    def _on_codec_probe_finished(self):
        self.scan_progress_bar.hide()
        self._codec_scan_worker = None

        matched = []
        for path, (video_codec, audio_codec) in self._codec_probe_results.items():
            if self.selected_video_codecs and (
                not video_codec or video_codec not in self.selected_video_codecs
            ):
                continue
            if self.selected_audio_codecs and (
                not audio_codec or audio_codec not in self.selected_audio_codecs
            ):
                continue
            matched.append(path)

        if not matched:
            QMessageBox.information(
                self, "No Files", "No files matched the selected codec filters."
            )
            self.clear_galleries()
            return

        self.start_loading_thumbnails(sorted(matched, key=natural_sort_key))

    # --- CONVERSION WORKER ---

    @Slot(bool)
    def start_conversion_worker(self, use_selection: bool = False):
        if self.worker and self.worker.isRunning():
            self.cancel_conversion()
            return

        p = self.input_path.text().strip()
        if not p or not os.path.isdir(p):
            QMessageBox.warning(self, "Invalid", "Please select a valid directory.")
            return

        files_for_conversion = (
            self.selected_files if use_selection else self.found_files
        )

        if not files_for_conversion:
            QMessageBox.warning(self, "No Files", "No files to convert.")
            return

        config = self.collect()
        config["files_to_convert"] = list(files_for_conversion)

        if config["video_codec"] == "copy" and config["audio_codec"] == "copy":
            QMessageBox.warning(
                self,
                "Nothing to Do",
                "Select a target video codec and/or a target audio codec "
                "different from \"Keep Original\".",
            )
            return

        self.btn_convert_all.setEnabled(False)
        self.btn_convert_contents.setEnabled(False)

        button_to_cancel = (
            self.btn_convert_contents if use_selection else self.btn_convert_all
        )
        button_to_cancel.setEnabled(True)
        button_to_cancel.setText("Cancel Conversion")
        button_to_cancel.setStyleSheet(
            """
            QPushButton { background-color: #cc3333; color: white; font-weight: bold; }
        """
        )

        self.status_label.setText( # pyrefly: ignore [missing-attribute]
            f"Re-encoding {len(files_for_conversion)} file(s)..."
        )
        self.convert_progress_bar.setValue(0)
        self.convert_progress_bar.show()

        self.worker = CodecConversionWorker(config)
        self.worker.finished_signal.connect(self.on_conversion_done)
        self.worker.error_signal.connect(self.on_conversion_error)
        self.worker.progress_signal.connect(self.update_progress_bar)
        self.worker.start()

    def cancel_conversion(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
            self.on_conversion_done(0, "**Conversion cancelled**")
            self.worker = None

    @Slot(int)
    def update_progress_bar(self, percentage: int):
        self.convert_progress_bar.setValue(percentage)
        self.status_label.setText(f"Re-encoding... {percentage}% complete") # pyrefly: ignore [missing-attribute]

    @Slot(int, str)
    def on_conversion_done(self, count, msg):
        self.btn_convert_all.setEnabled(True)
        self.btn_convert_all.setText("Convert All in Directory")
        self.btn_convert_all.setStyleSheet(SHARED_BUTTON_STYLE)

        self.on_selection_changed()
        self.btn_convert_contents.setStyleSheet(SHARED_BUTTON_STYLE)

        self.convert_progress_bar.hide()
        self.convert_progress_bar.setValue(0)
        self.status_label.setText(f"{msg}") # pyrefly: ignore [missing-attribute]
        self.worker = None
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Complete", msg)

    @Slot(str)
    def on_conversion_error(self, msg):
        self.on_conversion_done(0, msg)
        QMessageBox.critical(self, "Error", msg)

    def collect(self) -> dict:
        return {
            "input_path": self.input_path.text().strip(),
            "output_path": self.output_path.text().strip() or None,
            "output_filename_prefix": self.output_filename_prefix.text().strip(),
            "video_codec": VIDEO_CODEC_OPTIONS[self.video_codec_combo.currentText()],
            "audio_codec": AUDIO_CODEC_OPTIONS[self.audio_codec_combo.currentText()],
            "crf": self.crf_spin.value(),
            "speed": SPEED_OPTIONS[self.speed_combo.currentText()],
            "source_video_codecs": list(self.selected_video_codecs),
            "source_audio_codecs": list(self.selected_audio_codecs),
            "delete_original": self.delete_checkbox.isChecked(),
            "use_multicore": self.multicore_checkbox.isChecked(),
            "selected_files": list(self.selected_files),
        }

    def get_default_config(self) -> dict:
        return {
            "input_path": "",
            "output_path": "",
            "output_filename_prefix": "",
            "video_codec": "copy",
            "audio_codec": "copy",
            "crf": 28,
            "speed": 2,
            "source_video_codecs": [],
            "source_audio_codecs": [],
            "delete_original": False,
            "use_multicore": True,
        }

    def set_config(self, config: dict):
        try:
            input_path = config.get("input_path", "")
            self.input_path.setText(input_path)
            output_path = config.get("output_path", "") or ""
            self.output_path.setText(output_path)
            self.output_filename_prefix.setText(
                config.get("output_filename_prefix", "")
            )
            if output_path or config.get("output_filename_prefix"):
                self.output_field.set_open(True)

            video_codec_key = config.get("video_codec", "copy")
            for label, key in VIDEO_CODEC_OPTIONS.items():
                if key == video_codec_key:
                    self.video_codec_combo.setCurrentText(label)
                    break

            audio_codec_key = config.get("audio_codec", "copy")
            for label, key in AUDIO_CODEC_OPTIONS.items():
                if key == audio_codec_key:
                    self.audio_codec_combo.setCurrentText(label)
                    break

            self.crf_spin.setValue(config.get("crf", 28))

            speed_val = config.get("speed", 2)
            for label, val in SPEED_OPTIONS.items():
                if val == speed_val:
                    self.speed_combo.setCurrentText(label)
                    break

            for codec in config.get("source_video_codecs", []):
                if codec in self.video_codec_buttons:
                    self.video_codec_buttons[codec].setChecked(True)
                    self._toggle_codec_filter(
                        codec, True, self.video_codec_buttons, self.selected_video_codecs
                    )
            for codec in config.get("source_audio_codecs", []):
                if codec in self.audio_codec_buttons:
                    self.audio_codec_buttons[codec].setChecked(True)
                    self._toggle_codec_filter(
                        codec, True, self.audio_codec_buttons, self.selected_audio_codecs
                    )
            if self.selected_video_codecs:
                self.video_filter_field.set_open(True)
            if self.selected_audio_codecs:
                self.audio_filter_field.set_open(True)

            self.delete_checkbox.setChecked(config.get("delete_original", False))
            self.multicore_checkbox.setChecked(config.get("use_multicore", True))

            self._restore_selected_files(config)

            if os.path.isdir(input_path):
                self.scan_directory_visual()

            print("CodecSubTab configuration loaded.")
        except Exception as e:
            print(f"Error applying CodecSubTab config: {e}")
            QMessageBox.warning(
                self, "Config Error", f"Failed to apply some settings: {e}"
            )

    def cancel_loading(self):
        super().cancel_loading()

        if self._codec_scan_worker:
            with contextlib.suppress(Exception):
                self._codec_scan_worker.stop()
            self._codec_scan_worker = None

        if self.worker:
            try:
                if hasattr(self.worker, "stop"):
                    self.worker.stop()
                elif hasattr(self.worker, "cancel"):
                    self.worker.cancel()
            except Exception:
                pass

        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_conversion()
        self.cancel_loading()
        super().closeEvent(event)
