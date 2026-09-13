"""Composed VideoExtractorSubTab: state bootstrap + section wiring.

Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
Gallery inheritance stays -- this subtab owns one virtual gallery.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, cast

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import QEvent, QObject, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPixmap, QResizeEvent, QWheelEvent
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
from ....components import ClickableLabel, ScrubPreviewPopup
from ....helpers import FrameExtractionWorker
from ....helpers.core.queue_execution_worker import QueueExecutionWorker
from ....helpers.video.storyboard import StoryboardBuilder, StoryboardMeta
from ._cloud_dispatch import ExtractorCloudDispatchController
from ._config_methods import ExtractorConfigMethodsController
from ._cuts_logic import ExtractorCutsLogicController
from ._directory_scanning import ExtractorDirectoryScanningController
from ._extraction_execution import ExtractorExtractionExecutionController
from ._extraction_panel_ui import ExtractorExtractionPanelUIController
from ._extraction_workers import ExtractorExtractionWorkersController
from ._gallery_selection import ExtractorGallerySelectionController
from ._media_player import ExtractorMediaPlayerController
from ._player_lifecycle import ExtractorPlayerLifecycleController, PlayerLifecycleState
from ._qml_handlers import ExtractorQmlHandlersController
from ._queue_management import ExtractorQueueManagementController
from ._tags_logic import ExtractorTagsLogicController
from ._video_session_history import ExtractorVideoSessionHistoryController
from ._view_controls import ExtractorViewControlsController

_CONTROLLER_ATTRS = (
    "player_lifecycle",
    "media",
    "directory",
    "session",
    "view_controls",
    "gallery_selection",
    "cuts",
    "tags",
    "extraction",
    "workers",
    "cloud",
    "panel_ui",
    "queue",
    "config_controller",
    "qml",
)


class VideoExtractorSubTab(AbstractClassSingleGallery):
    """Video frame extractor subtab.

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    Gallery inheritance stays. Player lifecycle (#565) is a controller too.
    """

    qml_source_path_changed = Signal(str)
    qml_extraction_status = Signal(str)

    _AUTO_LOAD_OUTPUT_IMAGES_BYTE_BUDGET = 500 * 1024 * 1024  # 500MB

    def __init__(self):
        super().__init__()
        # Extraction/scanning jobs must not share the gallery loader pool.
        # Gallery refreshes synchronously drain ``thread_pool``; a queue
        # completion handler refreshing the gallery would otherwise wait on
        # the queue worker that is waiting for that handler to return.
        self.operation_thread_pool = QThreadPool()
        self.operation_thread_pool.setMaxThreadCount(
            max(2, min(8, os.cpu_count() or 4))
        )
        self.video_path: Optional[str] = None
        self._player_lifecycle_state = PlayerLifecycleState.NOT_LOADED
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
        self.parallel_extraction_processors = min(4, os.cpu_count() or 1)
        self.encoder_threads = 0
        self.gif_max_colors = 256
        self.fps_clamp = 0
        self.extraction_queue: List[dict] = []
        # Right-hand "In Process" queue: the batch handed to the worker when
        # Process Queue is clicked. Stays populated (with per-item status)
        # until the user confirms the completion dialog. Independent of
        # extraction_queue, so new items can be added to the left queue while
        # this one runs.
        self.inprocess_items: List[dict] = []
        self._inprocess_status: List[str] = []
        self._inprocess_awaiting_confirm: bool = False
        self.active_queue_worker: Optional[QueueExecutionWorker] = None
        self._close_progress_dialog: Optional[Any] = None
        self._close_when_finished: Optional[Any] = None
        self._queue_total_count = 0
        self._queue_completed_count = 0
        self._current_queue_item_title = ""
        self._cloud_worker = None
        self.time_display_format = "m:s:ms"

        self.use_internal_player = True
        self._external_player_launched_path: Optional[str] = None
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

        self.player_lifecycle = ExtractorPlayerLifecycleController(self)
        self.media = ExtractorMediaPlayerController(self)
        self.directory = ExtractorDirectoryScanningController(self)
        self.session = ExtractorVideoSessionHistoryController(self)
        self.view_controls = ExtractorViewControlsController(self)
        self.gallery_selection = ExtractorGallerySelectionController(self)
        self.cuts = ExtractorCutsLogicController(self)
        self.tags = ExtractorTagsLogicController(self)
        self.extraction = ExtractorExtractionExecutionController(self)
        self.workers = ExtractorExtractionWorkersController(self)
        self.cloud = ExtractorCloudDispatchController(self)
        self.panel_ui = ExtractorExtractionPanelUIController(self)
        self.queue = ExtractorQueueManagementController(self)
        self.config_controller = ExtractorConfigMethodsController(self)
        self.qml = ExtractorQmlHandlersController(self)

        self._drag_settle_timer.timeout.connect(self._on_drag_settled)
        # video_view/player_container/lbl_current_time/edit_current_time are
        # only assigned partway through _build_player_section() below, but
        # installEventFilter() calls made earlier in that same method can
        # trigger a reentrant eventFilter() (e.g. via a nested event loop)
        # before the later widgets exist -- eventFilter guards against that
        # with `if self.lbl_current_time and ...`, so the attribute must
        # exist (as None) from the start rather than only after assignment.
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

        self.directory._build_directory_section()
        self.media._build_player_section()
        self.panel_ui._build_extraction_settings_section()
        self.queue._build_results_section()

        self._load_existing_output_images()
        self._update_recent_extractions_ui()

    def __getattr__(self, name: str):
        for key in _CONTROLLER_ATTRS:
            ctrl = self.__dict__.get(key)
            if ctrl is None:
                continue
            impl = getattr(type(ctrl), name, None)
            if impl is None:
                continue
            if isinstance(impl, property) or callable(impl):
                return getattr(ctrl, name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def cancel_loading(self):
        """Stops all active media players, timers, and background workers.

        Deliberately does NOT stop the storyboard scrub-preview builder: the
        base class's refresh_gallery_view() (and therefore every search/sort/
        pagination change and every post-extraction gallery reload, e.g.
        extract_single_frame()'s start_loading_gallery(append=True) call)
        calls this method purely to cancel in-flight gallery thumbnail
        workers -- it has nothing to do with the video player. Stopping the
        storyboard here silently broke the drag-preview popup after every
        snapshot/extraction until the user switched videos or restarted.
        Storyboard teardown is handled explicitly by load_media() (on actual
        video switch) and closeEvent() (on tab close) instead.
        """
        super().cancel_loading()

        if hasattr(self, "gallery"):
            self.gallery.cancel_loading()

        if self.active_extraction_worker:
            self.active_extraction_worker.cancel()
            self.active_extraction_worker = None

        if self.active_queue_worker:
            self.active_queue_worker.cancel()

        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()
        self._stop_storyboard()
        self._set_player_lifecycle_state(PlayerLifecycleState.NOT_LOADED)
        self.operation_thread_pool.clear()
        self.operation_thread_pool.waitForDone(2000)
        super().closeEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self.video_view and self.video_view.isVisible():
            self.fit_video_in_view()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: C901
        if self.lbl_current_time and watched is self.lbl_current_time and event.type() == QEvent.Type.MouseButtonPress:
                edit_current_time = cast(QLineEdit, self.edit_current_time)
                self.lbl_current_time.hide()
                edit_current_time.setText(self.lbl_current_time.text())
                edit_current_time.show()
                edit_current_time.setFocus()
                edit_current_time.selectAll()
                return True

        if self.edit_current_time and watched is self.edit_current_time:
            if event.type() == QEvent.Type.KeyPress:
                if cast(QKeyEvent, event).key() == Qt.Key.Key_Escape:
                    self._cancel_time_edit()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                self._cancel_time_edit()
                return True

        if event.type() == QEvent.Type.Wheel:
            is_view = self.video_view and watched is self.video_view
            is_viewport = (
                self.video_view
                and hasattr(self.video_view, "viewport")
                and watched is self.video_view.viewport()
            )
            is_container = self.player_container and watched is self.player_container

            if is_view or is_viewport or is_container:
                duration_ms = self._current_duration_ms()
                if self.use_internal_player and duration_ms > 0:
                    delta = cast(QWheelEvent, event).angleDelta().y()
                    step = self.wheel_seek_ms if delta > 0 else -self.wheel_seek_ms
                    current_pos = self.slider.value()
                    new_pos = max(0, min(current_pos + step, duration_ms))
                    self._seek_to(new_pos)

                event.accept()
                return True

        if self.video_view and watched is self.video_view and self.use_internal_player:
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and cast(QMouseEvent, event).button() == Qt.MouseButton.LeftButton
            ):
                self.toggle_playback()
                return True

            if event.type() == QEvent.Type.KeyPress:
                key_event = cast(QKeyEvent, event)
                if key_event.key() == Qt.Key.Key_Right:
                    pos = self.slider.value()
                    duration = self._current_duration_ms()
                    new_pos = min(pos + self.wheel_seek_ms, duration)
                    self._seek_to(new_pos)
                    return True
                elif key_event.key() == Qt.Key.Key_Left:
                    pos = self.slider.value()
                    new_pos = max(0, pos - self.wheel_seek_ms)
                    self._seek_to(new_pos)
                    return True
                elif key_event.key() == Qt.Key.Key_Escape:
                    if (
                        self.player_container
                        and self.player_container.isFullScreen()
                    ):
                        self.toggle_fullscreen()
                        return True

        if self.player_container and watched is self.player_container:
            if event.type() == QEvent.Type.KeyPress and cast(QKeyEvent, event).key() == Qt.Key.Key_Escape and self.player_container.isFullScreen():
                self.toggle_fullscreen()
                return True
            if event.type() == QEvent.Type.Resize and self.video_view and self.video_view.isVisible():
                self.fit_video_in_view()

        return super().eventFilter(watched, event)

    @property
    def video_item(self):
        return self.media.video_item

    @property
    def audio_output(self):
        return self.media.audio_output

    @property
    def media_player(self):
        return self.media.media_player

    def create_gallery_label(self, path: str, size: int) -> ClickableLabel:
        return self.view_controls.create_gallery_label(path, size)

    def is_path_selected(self, path: str) -> bool:
        return self.view_controls.is_path_selected(path)

    def handle_marquee_selection(self, marquee_selection: Set[str], is_ctrl: bool):
        return self.gallery_selection.handle_marquee_selection(marquee_selection, is_ctrl)

    def refresh_gallery_view(self):
        return self.gallery_selection.refresh_gallery_view()

    def clear_gallery_widgets(self):
        return self.gallery_selection.clear_gallery_widgets()

    def _generate_video_thumbnail(self, path: str) -> Optional[QPixmap]:
        return self.workers._generate_video_thumbnail(path)

    def get_default_config(self) -> Dict[str, Any]:
        return self.config_controller.get_default_config()

    def collect(self) -> Dict[str, Any]:
        return self.config_controller.collect()

    def set_config(self, config: Dict[str, Any], quiet: bool = False):
        return self.config_controller.set_config(config, quiet=quiet)


__all__ = ["VideoExtractorSubTab"]
