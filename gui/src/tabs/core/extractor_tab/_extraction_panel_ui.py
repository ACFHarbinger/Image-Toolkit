"""Top-level assembly of the "4. Extraction Controls" panel: recent-config
row, output/engine config row, action buttons, progress bar/status label.
Delegates the cuts and tags rows to their own mixins.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ....components.tag_chip_widget import FlowLayout

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _ExtractionPanelUIMixin:
    """Builds the "4. Extraction Controls" groupbox and adds it to
    self.main_layout."""

    def _build_extraction_settings_section(self: "VideoExtractorSubTabHostProtocol") -> None:
        self.extract_group = QGroupBox("Extraction Settings")
        extract_main_layout = QVBoxLayout(self.extract_group)

        # -- Row 0: Recent Configurations --
        recent_layout = QHBoxLayout()
        recent_layout.addWidget(QLabel("Recent Extractions:"))
        self.combo_recent_extractions = QComboBox()
        self.combo_recent_extractions.setMinimumWidth(300)
        self.combo_recent_extractions.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        # Right-click a dropdown entry to enqueue / load / delete just that one.
        _recent_view = self.combo_recent_extractions.view()
        _recent_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _recent_view.customContextMenuRequested.connect(
            self._on_recent_extraction_context_menu
        )
        recent_layout.addWidget(self.combo_recent_extractions)

        self.btn_load_recent = QPushButton("Load Config")
        self.btn_load_recent.clicked.connect(self._load_selected_recent_extraction)
        self.btn_load_recent.setEnabled(False)
        recent_layout.addWidget(self.btn_load_recent)

        # Bulk: enqueue the N most recent extraction configs at once.
        self.spin_recent_to_queue_n = QSpinBox()
        self.spin_recent_to_queue_n.setRange(1, 1)
        self.spin_recent_to_queue_n.setToolTip(
            "How many of the most recent extractions to add to the queue"
        )
        self.spin_recent_to_queue_n.valueChanged.connect(
            lambda _v: self._refresh_recent_to_queue_controls()
        )
        recent_layout.addWidget(self.spin_recent_to_queue_n)

        self.btn_add_recent_to_queue = QPushButton("➕ Add Recent to Queue")
        self.btn_add_recent_to_queue.setToolTip(
            "Append the N most recent extraction configurations to the extraction queue"
        )
        self.btn_add_recent_to_queue.clicked.connect(self._add_recent_extractions_to_queue)
        self.btn_add_recent_to_queue.setEnabled(False)
        recent_layout.addWidget(self.btn_add_recent_to_queue)

        extract_main_layout.addLayout(recent_layout)

        # -- Row 1: Configuration --
        # FlowLayout, not QHBoxLayout: 4 label+control groups (Output Size,
        # GIF FPS, Engine, Extraction Speed) plus 2 checkboxes overflow the
        # app's 800px minimum width in a single non-wrapping row. Built with
        # an explicit parent container (addWidget, not addLayout) -- a bare
        # FlowLayout() added later via addLayout() can intermittently never
        # settle to its real geometry, leaving widgets at Qt's raw
        # top-level default size (640x480) instead of their laid-out size.
        extract_config_container = QWidget()
        extract_config_layout = FlowLayout(extract_config_container)

        extract_config_layout.addWidget(QLabel("Output Size:"))
        self.combo_extract_size = QComboBox()
        self.combo_extract_size.addItems(list(self.extraction_res_map.keys()))
        self.combo_extract_size.setCurrentText("Native")
        extract_config_layout.addWidget(self.combo_extract_size)

        # --- NEW: Vertical Checkbox for Extraction ---
        self.check_extract_vertical = QCheckBox("Vertical Output")
        self.check_extract_vertical.setToolTip(
            "Swap width/height for vertical output resolution"
        )
        extract_config_layout.addWidget(self.check_extract_vertical)
        # ---------------------------------------------

        extract_config_layout.addWidget(QLabel("GIF FPS:"))
        self.spin_gif_fps = QSpinBox()
        self.spin_gif_fps.setRange(1, 60)
        self.spin_gif_fps.setValue(24)
        extract_config_layout.addWidget(self.spin_gif_fps)

        self.check_mute_audio = QCheckBox("Mute Audio in MP4/GIF")
        self.check_mute_audio.setChecked(False)
        extract_config_layout.addWidget(self.check_mute_audio)

        extract_config_layout.addWidget(QLabel("Engine:"))
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(["FFmpeg", "MoviePy"])
        extract_config_layout.addWidget(self.combo_engine)

        extract_config_layout.addWidget(QLabel("Extraction Speed:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.25x", "0.5x", "1x", "1.5x", "2x", "4x"])
        self.combo_speed.setCurrentText("1x")
        # Decoupled from player speed
        extract_config_layout.addWidget(self.combo_speed)

        extract_main_layout.addWidget(extract_config_container)

        # -- Row 2: Actions --
        # FlowLayout: 9 buttons (Snapshot / Set Start+Go / Set End+Go /
        # Extract Range / Extract Video / Extract GIF / Run on GCD / Cancel)
        # in one row is the same overflow shape as Row 1 above. Parented
        # container, see Row 1's comment.
        extract_actions_container = QWidget()
        extract_actions_layout = FlowLayout(extract_actions_container)

        self.btn_snapshot = QPushButton("📸 Snapshot Frame")
        self.btn_snapshot.clicked.connect(self.extract_single_frame)
        self.btn_snapshot.setEnabled(False)
        extract_actions_layout.addWidget(self.btn_snapshot)
        extract_actions_layout.addWidget(QLabel("|"))

        self.start_time_ms = 0
        self.end_time_ms = 0
        self.cut_start_ms = 0
        self.cut_end_ms = 0
        self.cuts_ms: List[Tuple[int, int]] = []
        self.tags_ms: List[Tuple[int, str]] = []

        self.btn_cancel_extraction = QPushButton("🛑 Cancel Extraction")
        self.btn_cancel_extraction.setStyleSheet(
            "QPushButton {  color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px; }"
            "QPushButton:hover {  }"
            "QPushButton:disabled {  color: #888; }"
        )
        self.btn_cancel_extraction.clicked.connect(self.cancel_extraction)
        self.btn_cancel_extraction.hide()

        self.btn_set_start = QPushButton("Set Start [00:00]")
        self.btn_set_start.clicked.connect(self.set_range_start)
        self.btn_set_start.setEnabled(False)

        self.btn_jump_start = QPushButton("Go")
        self.btn_jump_start.setFixedWidth(40)
        self.btn_jump_start.clicked.connect(self.jump_to_range_start)
        self.btn_jump_start.setEnabled(False)

        self.btn_set_end = QPushButton("Set End [00:00]")
        self.btn_set_end.clicked.connect(self.set_range_end)
        self.btn_set_end.setEnabled(False)

        self.btn_jump_end = QPushButton("Go")
        self.btn_jump_end.setFixedWidth(40)
        self.btn_jump_end.clicked.connect(self.jump_to_range_end)
        self.btn_jump_end.setEnabled(False)
        self.btn_extract_range = QPushButton("🎞️ Extract Range")
        self.btn_extract_range.setStyleSheet(
            "QPushButton { background-color: #168f88; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #10736e; }"
            "QPushButton:disabled { background-color: #4b5563; color: #c4c7cc; }"
        )
        self.btn_extract_range.clicked.connect(self.extract_range)
        self.btn_extract_range.setEnabled(False)

        self.btn_extract_gif = QPushButton("GIF Extract as GIF")
        self.btn_extract_gif.setStyleSheet(
            "QPushButton { background-color: #8e44ad; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #70368a; }"
            "QPushButton:disabled { background-color: #4b5563; color: #c4c7cc; }"
        )
        self.btn_extract_gif.clicked.connect(self.extract_range_as_gif)
        self.btn_extract_gif.setEnabled(False)

        self.btn_extract_video = QPushButton("MP4 Extract as Video")
        self.btn_extract_video.setStyleSheet(
            "QPushButton { background-color: #d97706; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #b45309; }"
            "QPushButton:disabled { background-color: #4b5563; color: #c4c7cc; }"
        )
        self.btn_extract_video.clicked.connect(self.extract_range_as_video)
        self.btn_extract_video.setEnabled(False)

        # Cloud Compute Offload PoC (#487): run the current range on Google
        # Cloud Run instead of locally. Needs a Cloud Run URL in
        # Cloud Compute ▸ Settings; the handler warns before uploading.
        self.btn_run_on_gcd = QPushButton("☁ Run on GCD")
        self.btn_run_on_gcd.setToolTip(
            "Extract this range on Google Cloud Run (uploads the source video)"
        )
        self.btn_run_on_gcd.setStyleSheet(
            "QPushButton { background-color: #1f6feb; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #1a5fce; }"
            "QPushButton:disabled { background-color: #4b5563; color: #c4c7cc; }"
        )
        self.btn_run_on_gcd.clicked.connect(lambda: self.run_current_on_gcd("gif"))
        self.btn_run_on_gcd.setEnabled(False)

        extract_actions_layout.addWidget(self.btn_set_start)
        extract_actions_layout.addWidget(self.btn_jump_start)
        extract_actions_layout.addWidget(self.btn_set_end)
        extract_actions_layout.addWidget(self.btn_jump_end)
        extract_actions_layout.addWidget(self.btn_extract_range)
        extract_actions_layout.addWidget(self.btn_extract_video)
        extract_actions_layout.addWidget(self.btn_extract_gif)
        extract_actions_layout.addWidget(self.btn_run_on_gcd)
        extract_actions_layout.addWidget(self.btn_cancel_extraction)

        extract_main_layout.addWidget(extract_actions_container)

        # -- Row 3: Cuts --
        extract_main_layout.addLayout(self._build_cuts_row())

        # -- Row 4: Advanced Extraction Options --
        extract_adv_layout = QHBoxLayout()
        extract_adv_layout.addWidget(QLabel("Frame Interval:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 1000)
        self.spin_interval.setValue(1)
        self.spin_interval.setSuffix(" frames")
        extract_adv_layout.addWidget(self.spin_interval)

        extract_adv_layout.addSpacing(20)
        self.check_smart_extract = QCheckBox("Smart Extract (FFmpeg)")
        self.check_smart_extract.setToolTip(
            "Use FFmpeg filters to only extract unique frames or scene changes"
        )
        extract_adv_layout.addWidget(self.check_smart_extract)

        self.combo_smart_method = QComboBox()
        self.combo_smart_method.addItems(
            [
                "mpdecimate (De-duplicate)",
                "scene (0.1)",
                "scene (0.2)",
                "scene (0.4)",
                "scene (0.6)",
            ]
        )
        self.combo_smart_method.setCurrentText("mpdecimate (De-duplicate)")
        self.combo_smart_method.setEnabled(False)
        self.check_smart_extract.toggled.connect(self.combo_smart_method.setEnabled)
        extract_adv_layout.addWidget(self.combo_smart_method)

        extract_adv_layout.addStretch()
        extract_main_layout.addLayout(extract_adv_layout)

        # -- Row 5: Tags --
        extract_main_layout.addLayout(self._build_tags_row())

        # -- Row 6: Progress --
        self.extraction_progress_bar = QProgressBar()
        self.extraction_progress_bar.setTextVisible(True)
        self.extraction_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extraction_progress_bar.setStyleSheet(
            "QProgressBar {  color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 2px; height: 20px; }"
            "QProgressBar::chunk {  border-radius: 4px; }"
        )
        self.extraction_progress_bar.setMinimum(0)
        self.extraction_progress_bar.setMaximum(100)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.hide()
        extract_main_layout.addWidget(self.extraction_progress_bar)

        self.extraction_status_label = QLabel("Ready.")
        self.extraction_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extraction_status_label.setStyleSheet(
            "color: #00BCD4; font-style: italic; padding: 4px; font-weight: bold;"
        )
        self.extraction_status_label.hide()
        extract_main_layout.addWidget(self.extraction_status_label)

        self.main_layout.addWidget(self.extract_group)
        self.extract_group.setVisible(False)


__all__ = ["_ExtractionPanelUIMixin"]
