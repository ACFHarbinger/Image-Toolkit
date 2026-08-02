"""Lazy media-player/video-surface construction, slider seeking, and the
storyboard drag-scrub preview.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
Several blocks here guard the crash class documented in
.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md -- preserve verbatim.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QStyle,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from ....components import ScrubPreviewPopup
from ....helpers.video.storyboard import (
    StoryboardBuilder,
    StoryboardMeta,
    probe_duration_ms,
    storyboard_is_complete,
    storyboard_meta_path_for,
)
from ....utils.sort_utils import natural_sort_key


class _MediaPlayerMixin:
    """Lazy QMediaPlayer/QGraphicsVideoItem, slider seeking, and storyboard
    scrub-preview drag handling."""

    def _build_player_section(self) -> None:
        """Builds "3. Video Player Section" and adds it to self.main_layout."""
        self.video_container_widget = QWidget()
        video_container_layout = QVBoxLayout(self.video_container_widget)

        self.active_videos_tabbar = QTabBar()
        self.active_videos_tabbar.setTabsClosable(True)
        self.active_videos_tabbar.currentChanged.connect(
            self._on_active_video_tab_changed
        )
        self.active_videos_tabbar.tabCloseRequested.connect(
            self._on_active_video_tab_closed
        )
        self.active_videos_tabbar.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.active_videos_tabbar.customContextMenuRequested.connect(
            self._show_tab_context_menu
        )
        self.active_videos_tabbar.setStyleSheet(
            "QTabBar::tab { background: #2c2f33; color: #9b59b6; padding: 8px 16px; border: 1px solid #4f545c; border-top-left-radius: 4px; border-top-right-radius: 4px; }"
            "QTabBar::tab:selected { background: #23272a; color: #00bcd4; border-bottom-color: #23272a; font-weight: bold; }"
            "QTabBar::close-button { image: url(close.png); }"
        )
        video_container_layout.addWidget(self.active_videos_tabbar)

        player_group = QGroupBox("Video Player")
        self.player_layout_container = QVBoxLayout(player_group)

        self.player_container = QWidget()
        self.player_container.setStyleSheet("background-color: #2b2d31;")
        self.player_inner_layout = QVBoxLayout(self.player_container)
        self.player_inner_layout.setContentsMargins(0, 0, 0, 0)

        # QGraphicsVideoItem() is constructed lazily (see the video_item
        # property below), not here -- constructing it eagerly for every
        # tab at app startup is what actually triggers Qt Multimedia's
        # FFmpeg/PipeWire backend to load (confirmed: QAudioOutput() alone
        # does NOT print "Using Qt multimedia with FFmpeg version...";
        # constructing QGraphicsVideoItem() does), during the same fragile
        # startup window described above for QAudioOutput/audio_output.
        # See .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md
        # Addendum 14.
        self._video_item: Optional[QGraphicsVideoItem] = None
        self.graphics_scene = QGraphicsScene(self)

        self.video_view = QGraphicsView(self.graphics_scene)
        self.video_view.setFixedSize(1920, 1080)
        self.video_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_view.setVisible(True)

        # Install event filters on the view AND its viewport for robust wheel capture
        self.video_view.installEventFilter(self)
        self.video_view.viewport().installEventFilter(self)
        self.video_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_view.customContextMenuRequested.connect(self.show_video_context_menu)

        self.player_inner_layout.addWidget(
            self.video_view, 1, Qt.AlignmentFlag.AlignCenter
        )

        # QMediaPlayer/QAudioOutput are constructed lazily (see the
        # media_player/audio_output properties below) on first real use
        # rather than here. Constructing QAudioOutput eagerly for every tab
        # at app startup — before every tab is even visible, let alone used —
        # triggers the platform audio backend (PipeWire) to probe devices on
        # its own thread; that probe can race Qt's event loop startup and
        # raise "QSocketNotifier: Socket notifiers cannot be enabled or
        # disabled from another thread", cascading into heap corruption and
        # a SIGABRT. Deferring construction until a video is actually opened
        # avoids doing this during the fragile startup window.
        self._media_player: Optional[QMediaPlayer] = None
        self._audio_output: Optional[QAudioOutput] = None

        # Controls Row 1 (Top)
        controls_top_layout = QHBoxLayout()
        controls_top_layout.setContentsMargins(10, 5, 10, 0)

        self.btn_toggle_mode = QPushButton("Switch to External Player")
        self.btn_toggle_mode.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        )
        self.btn_toggle_mode.clicked.connect(self.toggle_player_mode)
        controls_top_layout.addWidget(self.btn_toggle_mode)

        controls_top_layout.addWidget(QLabel("Player Size:"))
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["720p", "1080p", "1440p", "4K"])
        self.combo_resolution.setCurrentIndex(0)
        self.combo_resolution.currentIndexChanged.connect(
            lambda: self.change_resolution(self.combo_resolution.currentIndex())
        )
        controls_top_layout.addWidget(self.combo_resolution)

        # --- NEW: Vertical Checkbox for Player ---
        self.check_player_vertical = QCheckBox("Vertical")
        self.check_player_vertical.setToolTip("Swap width/height for vertical displays")
        self.check_player_vertical.toggled.connect(
            lambda: self.change_resolution(self.combo_resolution.currentIndex())
        )
        controls_top_layout.addWidget(self.check_player_vertical)
        # ----------------------------------------

        controls_top_layout.addSpacing(20)
        controls_top_layout.addWidget(QLabel("Player Speed:"))
        self.combo_player_speed = QComboBox()
        self.combo_player_speed.addItems(["0.25x", "0.5x", "1x", "1.5x", "2x", "4x"])
        self.combo_player_speed.setCurrentText("1x")
        self.combo_player_speed.currentTextChanged.connect(self.update_playback_speed)
        controls_top_layout.addWidget(self.combo_player_speed)

        controls_top_layout.addStretch()
        self.player_inner_layout.addLayout(controls_top_layout)

        # Controls Row 2 (Bottom)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 0, 10, 10)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setVisible(True)

        self.lbl_vol = QLabel("Vol:")
        self.lbl_vol.setVisible(True)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(0)
        self.volume_slider.setFixedWidth(60)
        self.volume_slider.valueChanged.connect(
            lambda v: self.audio_output.setVolume(v / 100.0)
        )
        self.volume_slider.setVisible(True)

        self.lbl_current_time = QLabel("00:00:000")
        self.lbl_current_time.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_current_time.setToolTip("Click to jump to time")
        self.lbl_current_time.installEventFilter(self)

        self.edit_current_time = QLineEdit()
        self.edit_current_time.setFixedWidth(85)
        self.edit_current_time.setVisible(False)
        self.edit_current_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_current_time.setStyleSheet(
            "QLineEdit { background-color: #1e1f22; color: #00BCD4; border: 1px solid #4f545c; border-radius: 4px; font-family: monospace; }"
        )
        self.edit_current_time.returnPressed.connect(self._jump_to_edited_time)
        self.edit_current_time.installEventFilter(self)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        self.slider.sliderPressed.connect(self._on_slider_pressed)
        self.slider.sliderReleased.connect(self.set_position_on_release)
        self.slider.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.slider.customContextMenuRequested.connect(self.show_video_context_menu)

        self.lbl_total_time = QLabel("00:00")

        self.btn_fullscreen = QPushButton()
        self.btn_fullscreen.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton)
        )
        self.btn_fullscreen.setToolTip("Toggle Fullscreen")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self.btn_fullscreen.setFixedWidth(30)

        controls_layout.addWidget(self.lbl_vol)
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.lbl_current_time)
        controls_layout.addWidget(self.edit_current_time)
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.lbl_total_time)
        controls_layout.addWidget(self.btn_fullscreen)

        self.player_inner_layout.addLayout(controls_layout)

        self.info_label = QLabel(
            "Video is playing externally. Use slider to select timestamps."
        )
        self.info_label.setStyleSheet(
            "color: #aaa; font-style: italic; font-size: 11px;"
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setVisible(False)
        self.player_inner_layout.addWidget(self.info_label)

        self.storyboard_progress_bar = QProgressBar()
        self.storyboard_progress_bar.setTextVisible(True)
        self.storyboard_progress_bar.setFormat("Generating scrub preview... %p%")
        self.storyboard_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.storyboard_progress_bar.setFixedHeight(14)
        self.storyboard_progress_bar.setStyleSheet(
            "QProgressBar { background-color: #36393f; color: #aaa; border: 1px solid #4f545c;"
            " border-radius: 4px; font-size: 10px; }"
            "QProgressBar::chunk { background-color: #5865f2; border-radius: 4px; }"
        )
        self.storyboard_progress_bar.setMinimum(0)
        self.storyboard_progress_bar.setMaximum(100)
        self.storyboard_progress_bar.setValue(0)
        self.storyboard_progress_bar.hide()
        self.player_inner_layout.addWidget(self.storyboard_progress_bar)

        self.player_layout_container.addWidget(self.player_container)
        self.player_container.installEventFilter(self)

        video_container_layout.addWidget(player_group)
        self.main_layout.addWidget(self.video_container_widget)
        self.video_container_widget.setVisible(False)

    @property
    def video_item(self) -> QGraphicsVideoItem:
        if self._video_item is None:
            self._video_item = QGraphicsVideoItem()
            self.graphics_scene.addItem(self._video_item)
        return self._video_item

    @property
    def audio_output(self) -> QAudioOutput:
        if self._audio_output is None:
            self._audio_output = QAudioOutput()
            self._audio_output.setVolume(0.0)
        return self._audio_output

    @property
    def media_player(self) -> QMediaPlayer:
        if self._media_player is None:
            self._media_player = QMediaPlayer()
            self._media_player.setAudioOutput(self.audio_output)
            self._media_player.setVideoOutput(self.video_item)
            self._media_player.positionChanged.connect(self.position_changed)
            self._media_player.durationChanged.connect(self.duration_changed)
            self._media_player.errorOccurred.connect(self.handle_player_error)
        return self._media_player

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

        if self.active_extraction_worker:
            self.active_extraction_worker.cancel()
            self.active_extraction_worker = None

        # Close sub-windows
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()
        self._stop_storyboard()
        super().closeEvent(event)

    def _load_existing_output_images(self):
        valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".mp4"}
        found_paths = []

        if self.extraction_dir.exists():
            for entry in self.extraction_dir.iterdir():
                if entry.is_file() and entry.suffix.lower() in valid_extensions:
                    full_path = str(entry.absolute())
                    found_paths.append(full_path)

        found_paths.sort(key=natural_sort_key)

        if found_paths:
            self.current_extracted_paths = found_paths
            self.start_loading_gallery(
                self.current_extracted_paths, pixmap_cache=self._initial_pixmap_cache # pyrefly: ignore [bad-argument-type]
            )

    @Slot()
    def _on_slider_pressed(self):
        self._slider_scrubbing = True
        self.media_player.pause()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self._update_drag_preview(self.slider.value())

    @Slot(int)
    def _on_slider_value_changed(self, position: int):
        if self.slider.isSliderDown():
            self._update_drag_preview(position)

    @Slot()
    def set_position_on_release(self):
        self._slider_scrubbing = False
        self._drag_settle_timer.stop()
        self._hide_scrub_popup()
        self._seek_to(self.slider.value())

    @Slot()
    def _on_drag_settled(self):
        """Fires ~200ms after the last drag tick, while the slider is still
        held down. Commits the real player frame without waiting for the
        user to actually release -- matches how a paused pointer hovering a
        target still updates the preview, just debounced so it isn't
        re-triggered on every single pixel of motion."""
        if not self.slider.isSliderDown():
            return
        self._seek_to(self.slider.value())

    def _seek_to(self, position_ms: int):
        """Seeks the real player to position_ms immediately. Used by every
        seek trigger except an active slider drag -- a drag instead shows a
        storyboard preview via _update_drag_preview() and only ever calls
        this once the drag pauses or releases, so QMediaPlayer's inherent
        seek latency (observed ~100-300ms) stays a one-off, unremarkable
        wait instead of looking like the player is stuck."""
        self.slider.blockSignals(True)
        self.slider.setValue(position_ms)
        self.slider.blockSignals(False)
        self.lbl_current_time.setText(self._format_time(position_ms)) # pyrefly: ignore [missing-attribute]
        self.media_player.setPosition(position_ms)

    # --- Storyboard drag-scrub preview ---

    def _stop_storyboard(self):
        if self._storyboard_builder is not None:
            self._storyboard_builder.cancel()
            self._storyboard_builder.wait(1000)
            self._storyboard_builder.deleteLater()
            self._storyboard_builder = None
        self._storyboard_pages = []
        self._storyboard_meta = None
        self._hide_scrub_popup()
        self.storyboard_progress_bar.hide()

    def _start_storyboard(self):
        self._stop_storyboard()
        if not self.video_path or not self.use_internal_player:
            return

        if storyboard_is_complete(self.video_path):
            self._load_storyboard_cache()
            return

        duration_ms = self.duration_ms or probe_duration_ms(self.video_path)
        if duration_ms <= 0:
            return

        self._storyboard_builder = StoryboardBuilder(self.video_path, duration_ms, self)
        self._storyboard_builder.finished_ok.connect(self._on_storyboard_ready)
        self._storyboard_builder.failed.connect(self._on_storyboard_failed)
        self._storyboard_builder.progress_changed.connect(self._on_storyboard_progress)
        self._storyboard_builder.finished.connect(self._storyboard_builder.deleteLater)
        self.storyboard_progress_bar.setValue(0)
        self.storyboard_progress_bar.show()
        self._storyboard_builder.start()

    def _load_storyboard_cache(self):
        meta_path = storyboard_meta_path_for(self.video_path) # pyrefly: ignore [bad-argument-type]
        self._on_storyboard_ready(str(meta_path))

    @Slot(int, int)
    def _on_storyboard_progress(self, elapsed_ms: int, duration_ms: int):
        self.storyboard_progress_bar.setMaximum(max(duration_ms, 1))
        self.storyboard_progress_bar.setValue(elapsed_ms)

    @Slot(str)
    def _on_storyboard_ready(self, meta_path: str):
        self.storyboard_progress_bar.hide()
        try:
            meta = StoryboardMeta.load(Path(meta_path))
        except (OSError, ValueError, TypeError):
            return

        page_dir = Path(meta_path).parent
        pages: List[QPixmap] = []
        for page_name in meta.pages:
            pixmap = QPixmap(str(page_dir / page_name))
            if pixmap.isNull():
                # A corrupt/truncated page makes the whole set unusable for
                # correct indexing -- bail rather than show tiles from the
                # wrong page.
                return
            pages.append(pixmap)

        self._storyboard_pages = pages
        self._storyboard_meta = meta
        self._storyboard_builder = None

    @Slot(str)
    def _on_storyboard_failed(self, message: str):
        # Silent: the drag preview simply won't appear for this video, but
        # dragging still works (it just commits real frames on pause/
        # release, same as if the storyboard were never attempted).
        self.storyboard_progress_bar.hide()
        self._storyboard_builder = None

    def _ensure_scrub_popup(self) -> ScrubPreviewPopup:
        # Parented to the tab's top-level window (not `self`): Wayland
        # compositors ignore a client's attempt to freely reposition a
        # top-level window (confirmed empirically -- .move() on one is
        # silently a no-op), so this can't be a separate floating window at
        # all. It has to be a plain child widget of something already
        # correctly on-screen, positioned via local-coordinate .move() +
        # .raise_(), which Wayland always honors. It must be the *window*
        # specifically (not `self`) so it isn't clipped by the tab's own
        # QScrollArea viewport.
        top_level = self.window()
        if self._scrub_popup is None or self._scrub_popup.parentWidget() is not top_level:
            if self._scrub_popup is not None:
                self._scrub_popup.deleteLater()
            self._scrub_popup = ScrubPreviewPopup(top_level)
        return self._scrub_popup

    def _hide_scrub_popup(self):
        if self._scrub_popup is not None:
            self._scrub_popup.hide_popup()

    def _slider_handle_local_pos(self) -> QPoint:
        """The slider's current handle position, mapped into the top-level
        window's local coordinate space (see _ensure_scrub_popup for why
        this can't be a screen-global point)."""
        rng = self.slider.maximum() - self.slider.minimum()
        frac = 0.0 if rng <= 0 else (self.slider.value() - self.slider.minimum()) / rng
        local_x = int(frac * self.slider.width())
        return self.slider.mapTo(self.window(), QPoint(local_x, 0))

    def _update_drag_preview(self, position_ms: int):
        """Called on every slider tick while actively dragging. Never
        touches QMediaPlayer or the video surface -- only crops the
        pre-generated storyboard sprite sheet (cheap pixmap slicing, no
        decode) into the floating popup, so update speed is bound by
        nothing but repaint cost. The real player frame is committed
        separately once the drag pauses -- see _on_drag_settled()."""
        self.slider.blockSignals(True)
        self.slider.setValue(position_ms)
        self.slider.blockSignals(False)
        self.lbl_current_time.setText(self._format_time(position_ms)) # pyrefly: ignore [missing-attribute]

        if self._storyboard_pages and self._storyboard_meta is not None:
            page_index, x, y, w, h = self._storyboard_meta.tile_location_for(position_ms)
            if 0 <= page_index < len(self._storyboard_pages):
                self._ensure_scrub_popup().show_at(
                    pixmap=self._storyboard_pages[page_index],
                    tile_rect=(x, y, w, h),
                    time_text=self._format_time(position_ms), # pyrefly: ignore [missing-attribute]
                    anchor_local=self._slider_handle_local_pos(),
                )

        self._drag_settle_timer.start()


__all__ = ["_MediaPlayerMixin"]
