"""Active-video tabs bar management and per-video config persistence.

Split from ``_video_session_history`` (§5.17 Option B, #629) — pure code
motion, no logic change. Composed into
:class:`ExtractorVideoSessionHistoryController` together with
:mod:`_extraction_history`; cross-module calls resolve via ``self`` on
the leaf class at runtime.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtCore import QUrl, Slot
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox

from ....components import ClickableLabel
from ._player_lifecycle import PlayerLifecycleState
from ._tab_bound import TabBoundController

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class ExtractorVideoSessionConfigController(TabBoundController):
    """Active-video-tabs bar and per-video config persistence."""

    video_path: Optional[str]

    def _save_current_video_config(self: "VideoExtractorSubTabHostProtocol"):
        if not self.video_path:
            return

        config = {
            "start_time_ms": getattr(self, "start_time_ms", 0),
            "end_time_ms": getattr(self, "end_time_ms", 0),
            "cut_start_ms": getattr(self, "cut_start_ms", 0),
            "cut_end_ms": getattr(self, "cut_end_ms", 0),
            "cuts_ms": copy.deepcopy(getattr(self, "cuts_ms", [])),
            "tags_ms": copy.deepcopy(getattr(self, "tags_ms", [])),
            "check_mute_audio": self.check_mute_audio.isChecked(),
            "spin_gif_fps": self.spin_gif_fps.value(),
            "combo_extract_size": self.combo_extract_size.currentText(),
            "check_extract_vertical": self.check_extract_vertical.isChecked(),
            "spin_interval": self.spin_interval.value(),
            "check_smart_extract": self.check_smart_extract.isChecked(),
            "combo_smart_method": self.combo_smart_method.currentText(),
            "media_position": self._media_player.position() if self._media_player is not None else 0,
        }
        self.active_videos_config[self.video_path] = config

    def _load_video_config(self: "VideoExtractorSubTabHostProtocol", path: str):
        config = self.active_videos_config.get(path, {})
        if not config:
            self.clear_cuts()
            self.clear_tags()
            self.start_time_ms = 0
            self.end_time_ms = 0
            self.cut_start_ms = 0
            self.cut_end_ms = 0
            self.btn_set_start.setText("Set Start [00:00]")
            self.btn_set_end.setText("Set End [00:00]")
            self.btn_set_cut_start.setText("Set Cut Start [00:00]")
            self.btn_set_cut_end.setText("Set Cut End [00:00]")
            return

        self.start_time_ms = config.get("start_time_ms", 0)
        self.end_time_ms = config.get("end_time_ms", 0)
        self.cut_start_ms = config.get("cut_start_ms", 0)
        self.cut_end_ms = config.get("cut_end_ms", 0)

        self.btn_set_start.setText(
            f"Start [{self._format_time(self.start_time_ms)}]"
            if self.start_time_ms
            else "Set Start [00:00]"
        )
        self.btn_set_end.setText(
            f"End [{self._format_time(self.end_time_ms)}]"
            if self.end_time_ms
            else "Set End [00:00]"
        )
        self.btn_set_cut_start.setText(
            f"Cut Start [{self._format_time(self.cut_start_ms)}]"
            if self.cut_start_ms
            else "Set Cut Start [00:00]"
        )
        self.btn_set_cut_end.setText(
            f"Cut End [{self._format_time(self.cut_end_ms)}]"
            if self.cut_end_ms
            else "Set Cut End [00:00]"
        )

        self.cuts_ms = config.get("cuts_ms", [])
        self._update_cuts_label()

        self.tags_ms = config.get("tags_ms", [])
        self._update_tags_ui()

        self.check_mute_audio.setChecked(config.get("check_mute_audio", False))
        self.spin_gif_fps.setValue(config.get("spin_gif_fps", 24))
        extract_size = config.get("combo_extract_size")
        if extract_size:
            self.combo_extract_size.setCurrentText(extract_size)
        self.check_extract_vertical.setChecked(
            config.get("check_extract_vertical", False)
        )
        self.spin_interval.setValue(config.get("spin_interval", 1))
        self.check_smart_extract.setChecked(config.get("check_smart_extract", False))
        smart_method = config.get("combo_smart_method")
        if smart_method:
            self.combo_smart_method.setCurrentText(smart_method)

        pos = config.get("media_position", 0)
        if pos > 0:
            # Restore the position UI WITHOUT constructing the player. The
            # player may legitimately not exist yet (session-recovery
            # deferred load, issue #81) -- constructing QMediaPlayer here
            # during the startup burst reliably aborts the process. The
            # position is applied when the player is first constructed (see
            # the media_player property).
            self._pending_media_position = pos
            self.slider.setValue(pos)
            cast(QLabel, self.lbl_current_time).setText(self._format_time(pos))
            if self._media_player is not None:
                self._media_player.setPosition(pos) # pyrefly: ignore [missing-attribute]

    @Slot(int)
    def _on_active_video_tab_changed(self: "VideoExtractorSubTabHostProtocol", index: int):
        if self._is_switching_tabs or index < 0:
            return

        path = self.active_videos_tabbar.tabData(index)
        if path and path != self.video_path:
            # A session-recovery restore may still have a deferred (UI-only)
            # media load pending while the startup burst races Qt Multimedia
            # construction (issue #81). Keep such tab changes deferred too;
            # the first player interaction (play button) completes the load.
            if getattr(self, "_media_load_pending", False):
                self.load_media(path, defer_player=True)
            else:
                self.load_media(path)

    @Slot(int)
    def _on_active_video_tab_closed(self: "VideoExtractorSubTabHostProtocol", index: int):
        path = self.active_videos_tabbar.tabData(index)

        # Don't allow closing the last tab
        if self.active_videos_tabbar.count() <= 1:
            QMessageBox.information(
                self.tab, "Cannot Close", "Cannot close the last active video."
            )
            return

        self.active_videos_tabbar.removeTab(index)
        if path in self.active_videos_config:
            del self.active_videos_config[path]

        # If we closed the currently active video, it will automatically switch tab and load the new one via currentChanged signal
        if path == self.video_path:
            new_idx = self.active_videos_tabbar.currentIndex()
            new_path = self.active_videos_tabbar.tabData(new_idx)
            if new_path:
                self.load_media(new_path)
        else:
            # We closed an inactive tab, just update its style in the source list
            if path in self.source_path_to_widget:
                widget = self.source_path_to_widget[path]
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(path, label, False)

    @Slot(str)
    def load_media(self: "VideoExtractorSubTabHostProtocol", file_path: str, force: bool = False, defer_player: bool = False):  # noqa: C901
        old_path = self.video_path

        if (
            old_path == file_path
            and not force
            and not defer_player
            and not getattr(self, "_media_load_pending", False)
        ):
            return

        if old_path:
            self._save_current_video_config()

        if old_path and old_path != file_path:
            self._stop_storyboard()

        self.video_path = file_path

        ext = Path(file_path).suffix.lower()
        if ext == ".gif":
            self.video_container_widget.setVisible(False)
            self.extract_group.setVisible(False)
            # No internal player exists for a GIF selection either way.
            self._set_player_lifecycle_state(PlayerLifecycleState.NOT_LOADED, video_path=file_path)
            if defer_player:
                # Session-recovery restore: set up all UI state but do NOT
                # touch the Qt Multimedia player (issue #81 crash family).
                self._media_load_pending = False
                return
            self.media_player.stop()
            self.media_player.setSource(QUrl())
            # Update style
            for path in [old_path, file_path]:
                if path and path in self.source_path_to_widget:
                    widget = self.source_path_to_widget[path]
                    label = widget.findChild(ClickableLabel)
                    if label:
                        self._update_source_label_style(path, label, path == file_path)
            return

        # Check if tab exists
        tab_idx = -1
        for i in range(self.active_videos_tabbar.count()):
            if self.active_videos_tabbar.tabData(i) == file_path:
                tab_idx = i
                break

        self._is_switching_tabs = True
        if tab_idx == -1:
            # Add new tab
            name = Path(file_path).name
            idx = self.active_videos_tabbar.addTab(name)
            self.active_videos_tabbar.setTabData(idx, file_path)
            self.active_videos_tabbar.setCurrentIndex(idx)
        else:
            self.active_videos_tabbar.setCurrentIndex(tab_idx)
        self._is_switching_tabs = False

        self._load_video_config(file_path)

        # Update styles only for the affected widgets (old and new selection)
        for path in [old_path, file_path]:
            if path and path in self.source_path_to_widget:
                widget = self.source_path_to_widget[path]
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(path, label, path == file_path)

        self.video_container_widget.setVisible(True)
        self.extract_group.setVisible(True)

        self.btn_snapshot.setEnabled(
            bool(getattr(self, "start_time_ms", 0))
        )
        if not getattr(self, "start_time_ms", 0):
            self.btn_snapshot.setText("📸 Snapshot (Set Start First)")
        else:
            self.btn_snapshot.setText("📸 Snapshot Frame")

        self.btn_set_start.setEnabled(True)
        self.btn_set_end.setEnabled(True)
        self.btn_set_cut_start.setEnabled(True)
        self.btn_set_cut_end.setEnabled(True)
        self.btn_add_tag.setEnabled(True)

        if defer_player:
            # Session-recovery restore: leave the Qt Multimedia player
            # unconstructed and the storyboard unspawned until the user's
            # first interaction (tab click / play / thumbnail click) completes
            # the load via a normal load_media() call. Constructing the
            # player / forking ffmpeg during the startup burst -- with the
            # JVM loaded -- reliably aborts the process (issue #81).
            self._media_load_pending = True
            self._set_player_lifecycle_state(PlayerLifecycleState.RESTORED, video_path=file_path)
            return

        self._media_load_pending = False
        self._apply_player_mode()
        self._start_storyboard()
        self._set_player_lifecycle_state(PlayerLifecycleState.PLAYER_READY, video_path=file_path)

    @Slot()
    def browse_extraction_directory(self: "VideoExtractorSubTabHostProtocol"):
        d = QFileDialog.getExistingDirectory(
            self.tab, "Select Extraction Directory", self.last_browsed_extraction_dir
        )
        if d:
            new_path = Path(d)
            new_path.mkdir(parents=True, exist_ok=True)
            self.extraction_dir = new_path
            self.last_browsed_extraction_dir = str(new_path)
            self._save_last_extraction_dir(str(new_path))
            self.line_edit_extract_dir.setText(str(self.extraction_dir))
            self._clear_output_gallery()
            self._refresh_extracted_stems_cache()
            self._load_extraction_history()
            self._load_existing_output_images()
            self._refresh_source_extracted_indicators()


__all__ = ["ExtractorVideoSessionConfigController"]
