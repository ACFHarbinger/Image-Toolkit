"""Composed VideoExtractorSubTab: state bootstrap + section wiring.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
The bulk of the original monolithic ``__init__`` (UI section construction)
now lives in each mixin's own ``_build_*_section()`` method; this
``__init__`` keeps only state bootstrap and the call order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGraphicsView,
    QLabel,
    QLineEdit,
    QProgressDialog,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ....classes import AbstractClassSingleGallery
from ....components import ScrubPreviewPopup
from ....helpers import FrameExtractionWorker
from ....helpers.core.queue_execution_worker import QueueExecutionWorker
from ....helpers.video.storyboard import StoryboardBuilder, StoryboardMeta
from ._config_methods import _ConfigMethodsMixin
from ._cuts_logic import _CutsLogicMixin
from ._directory_scanning import _DirectoryScanningMixin
from ._extraction_execution import _ExtractionExecutionMixin
from ._extraction_panel_ui import _ExtractionPanelUIMixin
from ._extraction_workers import _ExtractionWorkersMixin
from ._gallery_selection import _GallerySelectionMixin
from ._media_player import _MediaPlayerMixin
from ._qml_handlers import _QmlHandlersMixin
from ._queue_management import _QueueManagementMixin
from ._tags_logic import _TagsLogicMixin
from ._video_session_history import _VideoSessionHistoryMixin
from ._view_controls import _ViewControlsMixin


class VideoExtractorSubTab(
    _MediaPlayerMixin,
    _DirectoryScanningMixin,
    _VideoSessionHistoryMixin,
    _ViewControlsMixin,
    _GallerySelectionMixin,
    _CutsLogicMixin,
    _TagsLogicMixin,
    _ExtractionExecutionMixin,
    _ExtractionWorkersMixin,
    _ExtractionPanelUIMixin,
    _QueueManagementMixin,
    _ConfigMethodsMixin,
    _QmlHandlersMixin,
    AbstractClassSingleGallery,
):
    # Signals for QML
    qml_source_path_changed = Signal(str)
    qml_extraction_status = Signal(str)

    def __init__(self):
        super().__init__()
        self.video_path: Optional[str] = None
        self.current_extracted_paths: List[str] = []
        self.selected_paths: Set[str] = set()
        self.duration_ms = 0
        self.extractor_worker: Optional[FrameExtractionWorker] = None
        self.open_preview_windows: List[QWidget] = []

        # Reference for the progress dialog and active workers
        self.progress_dialog: Optional[QProgressDialog] = None
        self.active_extraction_worker: Optional[Any] = None
        self._active_metadata: Optional[dict] = None
        self.wheel_seek_ms = 100
        self.extraction_queue_enabled = False
        self.extraction_queue: List[dict] = []
        self.active_queue_worker: Optional[QueueExecutionWorker] = None
        self.time_display_format = "m:s:ms"

        self.use_internal_player = True
        self._slider_scrubbing = False

        # --- Storyboard drag-scrub preview (YouTube-style) ---
        # While the playhead is being dragged, the main video surface is
        # never touched at all -- a floating popup crops a pre-generated
        # sprite sheet instead (see helpers/video/storyboard.py), which is
        # cheap enough to update on every tick regardless of drag speed or
        # the source's codec. The real player frame is only committed once
        # the drag pauses ("settles") or releases -- see _on_drag_settled().
        self._storyboard_builder: Optional[StoryboardBuilder] = None
        self._storyboard_pages: List[QPixmap] = []
        self._storyboard_meta: Optional[StoryboardMeta] = None
        self._scrub_popup: Optional[ScrubPreviewPopup] = None
        self._drag_settle_timer = QTimer(self)
        self._drag_settle_timer.setSingleShot(True)
        self._drag_settle_timer.setInterval(200)
        self._drag_settle_timer.timeout.connect(self._on_drag_settled)
        self.video_view: Optional[QGraphicsView] = None
        self.player_container: Optional[QWidget] = None
        self.lbl_current_time: Optional[QLabel] = None
        self.edit_current_time: Optional[QLineEdit] = None

        # Map to track source widgets for alphabetical updates
        self.source_path_to_widget: Dict[str, QWidget] = {}
        self.active_videos_config: Dict[str, dict] = {}
        self._is_switching_tabs = False

        # Defined resolutions corresponding to the Combo Box items
        self.available_resolutions = [
            (1280, 720),
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
        ]

        # Mapping for Extraction Resolutions
        self.extraction_res_map = {
            "Native": "native",
            "Player": None,
            "480p": (854, 480),
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "4K": (3840, 2160),
        }

        self.extraction_dir = Path(LOCAL_SOURCE_PATH) / "Frames"
        self.extraction_dir.mkdir(parents=True, exist_ok=True)
        self.last_browsed_extraction_dir = self._load_last_extraction_dir(
            str(self.extraction_dir)
        )

        # --- Extraction History ---
        self.recent_extractions_limit = 10
        self.recent_runs: List[Dict[str, Any]] = []
        self.extraction_metadata: Dict[str, Any] = {}
        self._extracted_stems_cache: Set[str] = set()
        self._recent_combo_connected = False
        self._load_extraction_history()

        # --- Initialize Pagination ---
        self.pagination_widget = self.create_pagination_controls()

        # --- UI Setup ---
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        # Main Tab Scroll Area
        self.tab_scroll_area = QScrollArea()
        self.tab_scroll_area.setWidgetResizable(True)
        self.tab_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root_layout.addWidget(self.tab_scroll_area)

        self.content_widget = QWidget()
        self.main_layout = QVBoxLayout(self.content_widget)
        self.tab_scroll_area.setWidget(self.content_widget)

        self._build_directory_section()
        self._build_player_section()
        self._build_extraction_settings_section()
        self._build_results_section()

        self._load_existing_output_images()
        self._update_recent_extractions_ui()


__all__ = ["VideoExtractorSubTab"]
