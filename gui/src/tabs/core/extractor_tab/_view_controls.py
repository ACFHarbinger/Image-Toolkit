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

from PySide6.QtCore import QEvent, QObject, Qt, QUrl, Slot
from PySide6.QtGui import QKeyEvent, QMouseEvent, QResizeEvent, QWheelEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QGraphicsView, QLabel, QLineEdit, QMessageBox, QStyle, QWidget

from ....components import ClickableLabel

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _ViewControlsMixin:
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

    def eventFilter(self: "VideoExtractorSubTabHostProtocol", watched: QObject, event: QEvent  # noqa: C901
    ) -> bool:
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
                # Only cancel if it's not a return press (which also triggers focus out in some cases)
                self._cancel_time_edit()
                return True

        # MANDATORY: Intercept mouse wheel events over any player-related object
        # This performs seeking AND locks the page position by consuming the event.
        if event.type() == QEvent.Type.Wheel:
            is_view = self.video_view and watched is self.video_view
            is_viewport = (
                self.video_view
                and hasattr(self.video_view, "viewport")
                and watched is self.video_view.viewport()
            )
            is_container = self.player_container and watched is self.player_container

            if is_view or is_viewport or is_container:
                # Only perform seek logic if the video is loaded and we are in internal player mode
                duration_ms = self._current_duration_ms()
                if self.use_internal_player and duration_ms > 0:
                    delta = cast(QWheelEvent, event).angleDelta().y()
                    # Jump by configured ms per scroll tick
                    step = self.wheel_seek_ms if delta > 0 else -self.wheel_seek_ms
                    current_pos = self.slider.value()
                    new_pos = max(0, min(current_pos + step, duration_ms))
                    self._seek_to(new_pos)

                # ALWAYS accept the event and return True.
                # This explicitly blocks the parent QScrollArea from shifting the player's alignment.
                event.accept()
                return True

        if self.video_view and watched is self.video_view and self.use_internal_player:
            # toggle play on click
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and cast(QMouseEvent, event).button() == Qt.MouseButton.LeftButton
            ):
                self.toggle_playback()
                return True

            # --- Arrow Keys for Video Seeking (When video has focus) ---
            if event.type() == QEvent.Type.KeyPress:
                key_event = cast(QKeyEvent, event)
                if key_event.key() == Qt.Key.Key_Right:
                    # Seek forward
                    pos = self.slider.value()
                    duration = self._current_duration_ms()
                    new_pos = min(pos + self.wheel_seek_ms, duration)
                    self._seek_to(new_pos)
                    return True
                elif key_event.key() == Qt.Key.Key_Left:
                    # Seek backward
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

        return super().eventFilter(watched, event)  # type: ignore[misc]

    def fit_video_in_view(self: "VideoExtractorSubTabHostProtocol"):
        # Don't force video_item's lazy construction (see the property
        # above) just from a resize event before any video has actually
        # been loaded -- there's nothing to fit yet, and constructing it
        # here would reintroduce the exact early-startup Qt Multimedia
        # trigger this laziness exists to avoid.
        if self._video_item is None:
            return
        video_view = cast(QGraphicsView, self.video_view)
        rect = video_view.viewport().rect()
        self.video_item.setSize(rect.size())
        video_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)

    def toggle_fullscreen(self: "VideoExtractorSubTabHostProtocol"):
        player_container = cast(QWidget, self.player_container)
        video_view = cast(QWidget, self.video_view)
        if player_container.isFullScreen():
            player_container.setWindowFlags(Qt.WindowType.Widget)
            player_container.showNormal()
            self.player_layout_container.addWidget(player_container)
            self.change_resolution(self.combo_resolution.currentIndex())
        else:
            player_container.setWindowFlags(Qt.WindowType.Window)
            player_container.showFullScreen()
            video_view.setFixedSize(16777215, 16777215)  # pyrefly: ignore [missing-attribute]
            video_view.setMinimumSize(0, 0)  # pyrefly: ignore [missing-attribute]
            video_view.setMaximumSize(16777215, 16777215)  # pyrefly: ignore [missing-attribute]
            player_container.setFocus()

    @Slot(QResizeEvent)
    def resizeEvent(self: "VideoExtractorSubTabHostProtocol", event: QResizeEvent):
        super().resizeEvent(event)  # type: ignore[safe-super]
        if self.video_view and self.video_view.isVisible():
            self.fit_video_in_view()

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
            video_view = cast(QWidget, self.video_view)
            # Keep the user's chosen player resolution as an upper bound.
            # A fixed canvas forces the tab scroll area's content width to
            # 1280--3840px and makes unrelated controls overflow in a normal
            # 800px window.
            video_view.setMaximumSize(w, h)
            video_view.updateGeometry()
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
            self.media_player.setSource(QUrl.fromLocalFile(self.video_path))
            self.media_player.setVideoOutput(self.video_item)
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
                cast(QWidget, self),
                "External Player",
                "No external video player found. Install a player (e.g. "
                "Haruna, mpv, VLC) or set one as the system default.",
            )
        except Exception as e:
            QMessageBox.warning(
                cast(QWidget, self),
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
        else:
            self.media_player.play()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
            )

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
                cast(QWidget, self), "Video Error", f"Media Player Error: {error_string}"
            )


__all__ = ["_ViewControlsMixin"]
