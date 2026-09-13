"""Event filtering (wheel seek, keyboard seek), view resizing/fullscreen,
resolution swapping, and internal/external player-mode toggling.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QLabel, QMessageBox, QStyle, QWidget

from ....components import ClickableLabel
from ._player_lifecycle import PlayerLifecycleState
from ._tab_bound import TabBoundController
from ._video_view import VideoView

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class ExtractorViewControlsController(TabBoundController):
    """Event filtering, view resizing/fullscreen, resolution swapping, and
    internal/external player-mode toggling."""

    def _current_duration_ms(self: "VideoExtractorSubTabHostProtocol") -> int:
        """Current media duration WITHOUT constructing the player.

        Passive events (wheel-seek over the player container, arrow-key
        seeking) must not build QMediaPlayer/QAudioOutput: constructing them
        lazily loads Qt Multimedia's native backend, which during the startup
        burst -- with the JVM loaded and other QThreads active -- reliably
        aborts the process (issue #81). A not-yet-built player has no
        duration (0), which is correct: there is nothing to seek before a
        video is loaded.
        """
        if self.duration_ms:
            return self.duration_ms
        if self._media_player is not None:
            return self._media_player.duration()
        return 0

    @Slot()
    def skip_video_runtime(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Skip ahead by the user-selected runtime without passing video end."""
        if not self.use_internal_player:
            return
        duration_ms = self._current_duration_ms()
        if duration_ms <= 0:
            return
        skip_ms = (
            self.skip_minutes_spinbox.value() * 60_000
            + self.skip_seconds_spinbox.value() * 1_000
            + self.skip_microseconds_spinbox.value() // 1_000
        )
        if skip_ms <= 0:
            return
        self._seek_to(min(self.slider.value() + skip_ms, duration_ms))

    @Slot()
    def fit_video_in_view(self: "VideoExtractorSubTabHostProtocol"):
        # Don't force video_item's lazy construction (see the property
        # above) just from a resize event before any video has actually
        # been loaded -- there's nothing to fit yet, and constructing it
        # here would reintroduce the exact early-startup Qt Multimedia
        # trigger this laziness exists to avoid.
        if self._video_item is None:
            return
        # Regression (root-caused to 4d33faeb, "resolve remaining Extractor
        # tab overflow at 800px minimum width"): this used to size the item
        # to the VIEWPORT's raw rect, which forces the item's own aspect
        # ratio to match whatever the surrounding layout happens to give
        # it -- QGraphicsVideoItem stretches its decoded frame to fill its
        # own size(), so any mismatch between that forced size and the
        # video's real aspect ratio crops/distorts the picture. Before
        # 4d33faeb this was mostly invisible because video_view.setFixedSize
        # kept the viewport at a fixed ~16:9-ish resolution matching most
        # test videos closely enough; once that became setMaximumSize-only,
        # the real viewport aspect started varying far more, and the
        # distortion became visible (confirmed live: a 890x480, ~1.85:1
        # video rendered as a tall, narrow, heavily cropped strip).
        #
        # Fix: size the item to the video's own native aspect ratio (once
        # known -- see video_item's nativeSizeChanged connection) and let
        # VideoView.fit_video_item scale+letterbox it within whatever
        # space its own sizing (aspect-derived fixed height, see
        # _video_view.py) actually gives it, instead of forcing the
        # item's own shape to match the viewport.
        video_view = cast(VideoView, self.video_view)
        video_item = self._video_item
        native_size = video_item.nativeSize()
        if not native_size.isEmpty():
            w, h = native_size.width(), native_size.height()
            aspect = (w / h) if h else 0
            # Some real-world files carry corrupted/unusual aspect-ratio
            # metadata (confirmed live: an h264 stream with SAR
            # 40230968:40208865 -- an oddly "computed"-looking, non-
            # standard fraction -- made Qt Multimedia's own FFmpeg backend
            # report nativeSize() as 35x480 for what ffprobe confirms is
            # actually an 890x480, ~1.85:1 frame). That isn't something
            # this codebase can correct -- Qt is relaying bad container
            # metadata, not misusing good metadata. Sanity-clamp to a
            # plausible aspect ratio range (wider than 5:1 or narrower
            # than 1:5 covers real ultra-wide/portrait content with
            # margin) and leave the item's existing size alone rather
            # than rendering a postage-stamp sliver from data we can't
            # trust.
            if 0.2 <= aspect <= 5.0:
                video_item.setSize(native_size)
        video_view.fit_video_item(video_item)

    def toggle_fullscreen(self: "VideoExtractorSubTabHostProtocol"):
        player_container = cast(QWidget, self.player_container)
        video_view = cast(VideoView, self.video_view)
        if player_container.isFullScreen():
            video_view.set_fullscreen(False)
            player_container.setWindowFlags(Qt.WindowType.Widget)
            player_container.showNormal()
            self.player_layout_container.addWidget(player_container)
            self.change_resolution(self.combo_resolution.currentIndex())
        else:
            video_view.set_fullscreen(True)
            player_container.setWindowFlags(Qt.WindowType.Window)
            player_container.showFullScreen()
            player_container.setFocus()

    @Slot(int)
    def change_resolution(self: "VideoExtractorSubTabHostProtocol", index: int):
        if not cast(QWidget, self.player_container).isFullScreen() and 0 <= index < len(
            self.available_resolutions
        ):
            w, h = self.available_resolutions[index]
            # --- NEW: Swap dimensions if vertical checkbox is checked ---
            if self.check_player_vertical.isChecked():
                w, h = h, w
            # -----------------------------------------------------------
            video_view = cast(VideoView, self.video_view)
            # Keep the user's chosen player resolution as an upper bound.
            # A fixed canvas forces the tab scroll area's content width to
            # 1280--3840px and makes unrelated controls overflow in a normal
            # 800px window.
            video_view.set_display_size(w, h)
            self.fit_video_in_view()

    def is_path_selected(self: "VideoExtractorSubTabHostProtocol", path: str) -> bool:
        return path in self.selected_paths

    def create_gallery_label(self: "VideoExtractorSubTabHostProtocol", path: str, size: int) -> ClickableLabel:
        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(size, size)
        clickable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clickable_label.path = path

        clickable_label.path_clicked.connect(self.handle_thumbnail_single_click)
        clickable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)
        return clickable_label

    @Slot()
    def toggle_player_mode(self: "VideoExtractorSubTabHostProtocol"):
        self.use_internal_player = not self.use_internal_player
        if not self.use_internal_player:
            # Explicit switch to external: always (re)launch the current
            # video, even if it was already launched once -- the user may
            # have closed the external player window since.
            self._external_player_launched_path = None
        self._apply_player_mode()

    def _apply_player_mode(self: "VideoExtractorSubTabHostProtocol"):
        if not self.video_path:
            return
        ext = Path(self.video_path).suffix.lower()
        if ext == ".gif":
            return

        if self.use_internal_player:
            self.btn_toggle_mode.setText("Switch to External Player")
            self.btn_toggle_mode.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
            )
            self.combo_resolution.setEnabled(True)
            cast(QWidget, self.video_view).setVisible(True)
            self.btn_play.setVisible(True)
            self.btn_fullscreen.setVisible(True)
            self.lbl_vol.setVisible(True)
            self.volume_slider.setVisible(True)

            self.info_label.setVisible(False)
            self.media_player.setVideoOutput(self.video_item)
            self.media_player.setSource(QUrl.fromLocalFile(self.video_path))
            # QAudioOutput is constructed on demand only (issue #81: its
            # construction aborts the process in this environment). Attach
            # it if the user already has one.
            if self._audio_output is not None:
                self.media_player.setAudioOutput(self._audio_output)
            self.btn_play.setEnabled(True)
            self.change_resolution(self.combo_resolution.currentIndex())
        else:
            # Keep the internal player's source loaded (it drives the
            # slider/timestamps -- see the info label) but detach its
            # video/audio output and pause it; the actual viewing happens
            # in an external player launched below.
            self.media_player.setSource(QUrl.fromLocalFile(self.video_path))
            self.btn_toggle_mode.setText("Switch to Internal Player")
            self.btn_toggle_mode.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            )
            self.info_label.setVisible(True)
            self.combo_resolution.setEnabled(False)
            cast(QWidget, self.video_view).setVisible(False)
            self.btn_play.setVisible(False)
            self.btn_fullscreen.setVisible(False)
            self.lbl_vol.setVisible(False)
            self.volume_slider.setVisible(False)
            self.media_player.setVideoOutput(None)  # type: ignore[arg-type] # pyrefly: ignore [bad-argument-type]
            self.media_player.setAudioOutput(None)  # type: ignore[arg-type] # pyrefly: ignore [bad-argument-type]
            self.media_player.pause()

            # Actually launch an external player for the current video
            # (previously this branch only toggled the internal player's
            # output -- the button appeared to do nothing). Avoid spawning
            # duplicate windows when re-applying the same video.
            if self.video_path != self._external_player_launched_path:
                self._external_player_launched_path = self.video_path
                self._launch_external_player()

        # Apply current speed locally
        self.update_playback_speed(self.combo_player_speed.currentText())

    def _launch_external_player(self: "VideoExtractorSubTabHostProtocol"):
        """Open the current video in an external player.

        On Linux this prefers the user's default handler (xdg-open -- the
        same thing the file manager uses, e.g. Haruna), falling back to a
        known player binary only if xdg-open is unavailable.
        """
        path = self.video_path
        if not path or not os.path.exists(path):
            return
        try:
            if platform.system() == "Windows":
                os.startfile(path)  # pyrefly: ignore [missing-attribute]
                return
            if platform.system() == "Darwin":
                subprocess.Popen(
                    ["open", path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            xdg = shutil.which("xdg-open")
            if xdg:
                subprocess.Popen(
                    [xdg, path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            for player in ("haruna", "mpv", "vlc", "celluloid"):
                exe = shutil.which(player)
                if exe:
                    subprocess.Popen(
                        [exe, path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return
            QMessageBox.warning(
                self.tab,
                "External Player",
                "No external video player found. Install a player (e.g. "
                "Haruna, mpv, VLC) or set one as the system default.",
            )
        except Exception as e:
            QMessageBox.warning(
                self.tab,
                "External Player",
                f"Could not launch external player: {e}",
            )

    @Slot(str)
    def update_playback_speed(self: "VideoExtractorSubTabHostProtocol", text: str):
        speed_str = text.replace("x", "")
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 1.0

        # Record the requested rate; apply it only if the player already
        # exists. Deliberately does NOT construct the player here: this slot
        # fires during session recovery (combo_player_speed.setCurrentIndex
        # in set_config), and constructing QMediaPlayer/QAudioOutput in the
        # startup burst -- with the JVM loaded and ffmpeg thumbnail workers
        # forking subprocesses -- reliably aborts the process (issue #81).
        # The rate is applied when the player is first constructed (see the
        # media_player property).
        self._pending_playback_rate = speed
        if self._media_player is not None:
            # QMediaPlayer.setPlaybackRate introduced in Qt6
            self._media_player.setPlaybackRate(speed)

    @Slot()
    def toggle_playback(self: "VideoExtractorSubTabHostProtocol"):
        # Complete a session-recovery deferred load on first user interaction
        # (the tab restore sets up UI state but leaves the player unbuilt).
        if getattr(self, "_media_load_pending", False) and self.video_path:
            self.load_media(self.video_path, force=True)
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
            self._set_player_lifecycle_state(PlayerLifecycleState.PLAYER_READY)
        else:
            self.media_player.play()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
            )
            self._set_player_lifecycle_state(PlayerLifecycleState.PLAYING)

    @Slot(int)
    def position_changed(self: "VideoExtractorSubTabHostProtocol", position: int):
        self.slider.blockSignals(True)
        self.slider.setValue(position)
        self.slider.blockSignals(False)
        cast(QLabel, self.lbl_current_time).setText(self._format_time(position)) # pyrefly: ignore [missing-attribute]

    @Slot(int)
    def duration_changed(self: "VideoExtractorSubTabHostProtocol", duration: int):
        self.duration_ms = duration
        self.slider.setRange(0, duration)
        self.lbl_total_time.setText(self._format_time(duration))
        enabled = duration > 0
        self.skip_minutes_spinbox.setEnabled(enabled)
        self.skip_seconds_spinbox.setEnabled(enabled)
        self.skip_microseconds_spinbox.setEnabled(enabled)
        self.btn_skip_runtime.setEnabled(enabled)

    @Slot(int)
    def set_position(self: "VideoExtractorSubTabHostProtocol", position: int):
        self._seek_to(position)

    @Slot(QMediaPlayer.Error, str)
    def handle_player_error(self: "VideoExtractorSubTabHostProtocol", error: QMediaPlayer.Error, error_string: str):
        if self.use_internal_player:
            self.btn_play.setEnabled(False)
            QMessageBox.critical(
                self.tab, "Video Error", f"Media Player Error: {error_string}"
            )


__all__ = ["ExtractorViewControlsController"]

