"""Event filtering (wheel seek, keyboard seek), view resizing/fullscreen,
resolution swapping, and internal/external player-mode toggling.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QUrl, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QMessageBox, QStyle

from ....components import ClickableLabel


class _ViewControlsMixin:
    """Event filtering, view resizing/fullscreen, resolution swapping, and
    internal/external player-mode toggling."""

    def eventFilter(self, watched: QObject, event: QEvent  # noqa: C901
    ) -> bool:
        if self.lbl_current_time and watched is self.lbl_current_time and event.type() == QEvent.Type.MouseButtonPress:
                self.lbl_current_time.hide()
                self.edit_current_time.setText(self.lbl_current_time.text()) # pyrefly: ignore [missing-attribute]
                self.edit_current_time.show() # pyrefly: ignore [missing-attribute]
                self.edit_current_time.setFocus() # pyrefly: ignore [missing-attribute]
                self.edit_current_time.selectAll() # pyrefly: ignore [missing-attribute]
                return True

        if self.edit_current_time and watched is self.edit_current_time:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape: # pyrefly: ignore [missing-attribute]
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
                duration_ms = self.duration_ms or self.media_player.duration()
                if self.use_internal_player and duration_ms > 0:
                    delta = event.angleDelta().y() # pyrefly: ignore [missing-attribute]
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
                and event.button() == Qt.MouseButton.LeftButton # pyrefly: ignore [missing-attribute]
            ):
                self.toggle_playback()
                return True

            # --- Arrow Keys for Video Seeking (When video has focus) ---
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Right:# pyrefly: ignore [missing-attribute]
                    # Seek forward
                    pos = self.slider.value()
                    duration = self.duration_ms or self.media_player.duration()
                    new_pos = min(pos + self.wheel_seek_ms, duration)
                    self._seek_to(new_pos)
                    return True
                elif event.key() == Qt.Key.Key_Left:# pyrefly: ignore [missing-attribute]
                    # Seek backward
                    pos = self.slider.value()
                    new_pos = max(0, pos - self.wheel_seek_ms)
                    self._seek_to(new_pos)
                    return True
                elif event.key() == Qt.Key.Key_Escape: # pyrefly: ignore [missing-attribute]
                    if (
                        self.player_container
                        and self.player_container.isFullScreen()
                    ):
                        self.toggle_fullscreen()
                        return True

        if self.player_container and watched is self.player_container:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape and self.player_container.isFullScreen(): # pyrefly: ignore [missing-attribute]
                self.toggle_fullscreen()
                return True
            if event.type() == QEvent.Type.Resize and self.video_view.isVisible(): # pyrefly: ignore [missing-attribute]
                self.fit_video_in_view()

        return super().eventFilter(watched, event)

    def fit_video_in_view(self):
        # Don't force video_item's lazy construction (see the property
        # above) just from a resize event before any video has actually
        # been loaded -- there's nothing to fit yet, and constructing it
        # here would reintroduce the exact early-startup Qt Multimedia
        # trigger this laziness exists to avoid.
        if self._video_item is None:
            return
        rect = self.video_view.viewport().rect() # pyrefly: ignore [missing-attribute]
        self.video_item.setSize(rect.size()) # pyrefly: ignore [missing-attribute]
        self.video_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio) # pyrefly: ignore [missing-attribute]

    def toggle_fullscreen(self):
        if self.player_container.isFullScreen(): # pyrefly: ignore [missing-attribute]
            self.player_container.setWindowFlags(Qt.WindowType.Widget) # pyrefly: ignore [missing-attribute]
            self.player_container.showNormal() # pyrefly: ignore [missing-attribute]
            self.player_layout_container.addWidget(self.player_container) # pyrefly: ignore [missing-attribute, bad-argument-type]
            self.change_resolution(self.combo_resolution.currentIndex()) # pyrefly: ignore [missing-attribute]
        else:
            self.player_container.setWindowFlags(Qt.WindowType.Window) # pyrefly: ignore [missing-attribute]
            self.player_container.showFullScreen() # pyrefly: ignore [missing-attribute]
            self.video_view.setFixedSize(16777215, 16777215) # pyrefly: ignore [missing-attribute]
            self.video_view.setMinimumSize(0, 0) # pyrefly: ignore [missing-attribute]
            self.video_view.setMaximumSize(16777215, 16777215) # pyrefly: ignore [missing-attribute]
            self.player_container.setFocus() # pyrefly: ignore [missing-attribute]

    @Slot(QResizeEvent)
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self.video_view.isVisible(): # pyrefly: ignore [missing-attribute]
            self.fit_video_in_view()

    @Slot(int)
    def change_resolution(self, index: int):
        if not self.player_container.isFullScreen() and 0 <= index < len( # pyrefly: ignore [missing-attribute]
            self.available_resolutions
        ):
            w, h = self.available_resolutions[index]
            # --- NEW: Swap dimensions if vertical checkbox is checked ---
            if self.check_player_vertical.isChecked():
                w, h = h, w
            # -----------------------------------------------------------
            self.video_view.setFixedSize(w, h) # pyrefly: ignore [missing-attribute]
            self.fit_video_in_view()

    def is_path_selected(self, path: str) -> bool:
        return path in self.selected_paths

    def create_gallery_label(self, path: str, size: int) -> ClickableLabel:
        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(size, size)
        clickable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clickable_label.path = path

        clickable_label.path_clicked.connect(self.handle_thumbnail_single_click)
        clickable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)
        return clickable_label

    @Slot()
    def toggle_player_mode(self):
        self.use_internal_player = not self.use_internal_player
        self._apply_player_mode()

    def _apply_player_mode(self):
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
            self.video_view.setVisible(True) # pyrefly: ignore [missing-attribute]
            self.btn_play.setVisible(True)
            self.btn_fullscreen.setVisible(True)
            self.lbl_vol.setVisible(True)
            self.volume_slider.setVisible(True)

            self.info_label.setVisible(False)
            self.media_player.setSource(QUrl.fromLocalFile(self.video_path))
            self.media_player.setVideoOutput(self.video_item)
            self.media_player.setAudioOutput(self.audio_output)
            self.btn_play.setEnabled(True)
            self.change_resolution(self.combo_resolution.currentIndex())
        else:
            self.media_player.setSource(QUrl.fromLocalFile(self.video_path))
            self.btn_toggle_mode.setText("Switch to Internal Player")
            self.btn_toggle_mode.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            )
            self.info_label.setVisible(True)
            self.combo_resolution.setEnabled(False)
            self.video_view.setVisible(False) # pyrefly: ignore [missing-attribute]
            self.btn_play.setVisible(False)
            self.btn_fullscreen.setVisible(False)
            self.lbl_vol.setVisible(False)
            self.volume_slider.setVisible(False)
            self.media_player.setVideoOutput(None) # pyrefly: ignore [bad-argument-type]
            self.media_player.setAudioOutput(None) # pyrefly: ignore [bad-argument-type]
            self.media_player.setAudioOutput(None) # pyrefly: ignore [bad-argument-type]
            self.media_player.pause()

        # Apply current speed locally
        self.update_playback_speed(self.combo_player_speed.currentText())

    @Slot(str)
    def update_playback_speed(self, text: str):
        speed_str = text.replace("x", "")
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 1.0

        # QMediaPlayer.setPlaybackRate introduced in Qt6
        self.media_player.setPlaybackRate(speed)

    @Slot()
    def toggle_playback(self):
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
    def position_changed(self, position: int):
        self.slider.blockSignals(True)
        self.slider.setValue(position)
        self.slider.blockSignals(False)
        self.lbl_current_time.setText(self._format_time(position)) # pyrefly: ignore [missing-attribute]

    @Slot(int)
    def duration_changed(self, duration: int):
        self.duration_ms = duration
        self.slider.setRange(0, duration)
        self.lbl_total_time.setText(self._format_time(duration))

    @Slot(int)
    def set_position(self, position: int):
        self._seek_to(position)

    @Slot(QMediaPlayer.Error, str)
    def handle_player_error(self, error: QMediaPlayer.Error, error_string: str):
        if self.use_internal_player:
            self.btn_play.setEnabled(False)
            QMessageBox.critical(
                self, "Video Error", f"Media Player Error: {error_string}"
            )


__all__ = ["_ViewControlsMixin"]
