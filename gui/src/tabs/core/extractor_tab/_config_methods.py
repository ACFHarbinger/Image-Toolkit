"""Tab-config persistence hooks used by SettingsWindow / session recovery.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, cast

from PySide6.QtWidgets import QMessageBox, QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _ConfigMethodsMixin:
    """get_default_config/collect/set_config for SettingsWindow integration."""

    def get_default_config(self: "VideoExtractorSubTabHostProtocol") -> Dict[str, Any]:
        return {
            "source_directory": str(Path.home()),
            "extraction_directory": str(self.extraction_dir),
            "player_mode_internal": True,
            "player_resolution_index": 1,
            "player_speed_index": 2,  # NEW: Default to 1x (index 2)
            "player_vertical": False,  # NEW
            "extract_vertical": False,  # NEW
            "extraction_engine": "MoviePy",
        }

    def collect(self: "VideoExtractorSubTabHostProtocol") -> Dict[str, Any]:
        if self.video_path:
            self._save_current_video_config()
        return {
            "source_directory": self.line_edit_dir.text(),
            "extraction_directory": self.line_edit_extract_dir.text(),
            "player_mode_internal": self.use_internal_player,
            "player_resolution_index": self.combo_resolution.currentIndex(),
            "player_speed_index": self.combo_player_speed.currentIndex(),  # NEW
            "player_vertical": self.check_player_vertical.isChecked(),  # NEW
            "extract_vertical": self.check_extract_vertical.isChecked(),  # NEW
            "extraction_engine": self.combo_engine.currentText(),
            "active_videos_config": copy.deepcopy(self.active_videos_config),
            "video_path": self.video_path,
        }

    def set_config(self: "VideoExtractorSubTabHostProtocol", config: Dict[str, Any], quiet: bool = False):  # noqa: C901
        try:
            # 1. Restore active videos tab state FIRST so scan_directory can style them
            active_configs = config.get("active_videos_config", {})
            if active_configs:
                self.active_videos_config = copy.deepcopy(active_configs)

                # Clear tabbar and repopulate under switching guard
                self._is_switching_tabs = True
                while self.active_videos_tabbar.count() > 0:
                    self.active_videos_tabbar.removeTab(0)
                for path in self.active_videos_config.keys():
                    if os.path.exists(path):
                        name = Path(path).name
                        idx = self.active_videos_tabbar.addTab(name)
                        self.active_videos_tabbar.setTabData(idx, path)
                self._is_switching_tabs = False

            # 2. Restore extraction directory config so scan_directory can use it for correct thumbnail styling
            extract_dir_str = config.get("extraction_directory")
            if extract_dir_str and os.path.isdir(extract_dir_str):
                new_path = Path(extract_dir_str)
                self.extraction_dir = new_path
                self.last_browsed_extraction_dir = str(new_path)
                self._save_last_extraction_dir(str(new_path))
                self.line_edit_extract_dir.setText(str(new_path))
                self._refresh_extracted_stems_cache()
                self._load_existing_output_images()

            # 3. Restore source directories and scan
            source_dir = config.get("source_directory", "")
            self.line_edit_dir.setText(source_dir)
            if os.path.isdir(source_dir):
                self.scan_directory(source_dir)

            # --- Restore Checkboxes ---
            self.check_player_vertical.setChecked(config.get("player_vertical", False))
            self.check_extract_vertical.setChecked(
                config.get("extract_vertical", False)
            )

            res_index = config.get("player_resolution_index")
            if res_index is not None and 0 <= res_index < self.combo_resolution.count():
                self.combo_resolution.setCurrentIndex(res_index)
                self.change_resolution(res_index)

            speed_index = config.get("player_speed_index")
            if (
                speed_index is not None
                and 0 <= speed_index < self.combo_player_speed.count()
            ):
                self.combo_player_speed.setCurrentIndex(speed_index)

            mode = config.get("player_mode_internal")
            if mode is not None:
                if mode != self.use_internal_player:
                    self.toggle_player_mode()
                self._apply_player_mode()

            engine = config.get("extraction_engine")
            if engine in ["MoviePy", "FFmpeg"]:
                self.combo_engine.setCurrentText(engine)

            # Load the current video path
            curr_video = config.get("video_path", "")
            if (not curr_video or not os.path.exists(curr_video)) and self.active_videos_config:
                for path in self.active_videos_config.keys():
                    if os.path.exists(path):
                        curr_video = path
                        break

            if curr_video and os.path.exists(curr_video):
                # Select the matching tab in the tabbar *before* releasing the guard
                # so that load_media finds tab_idx != -1 and doesn't add a duplicate.
                self._is_switching_tabs = True
                for i in range(self.active_videos_tabbar.count()):
                    if self.active_videos_tabbar.tabData(i) == curr_video:
                        self.active_videos_tabbar.setCurrentIndex(i)
                        break
                self._is_switching_tabs = False

                # Unconditionally make the player section visible before load_media
                # so that even when scan_directory was called first (which clears
                # widgets and can leave the container hidden), the UI shows correctly.
                self.video_container_widget.setVisible(True)
                self.extract_group.setVisible(True)

                # defer_player: restore all UI state (tab selection, video
                # path, per-video config) but leave the Qt Multimedia player
                # unconstructed and the storyboard subprocess unspawned until
                # the user's first interaction. Constructing the player /
                # forking ffmpeg during the startup burst -- with the JVM
                # loaded -- reliably aborts the process (issue #81).
                self.load_media(curr_video, force=True, defer_player=True)

            if not quiet:
                QMessageBox.information(
                    cast(QWidget, self),
                    "Config Loaded",
                    "Image Extractor configuration applied successfully.",
                )

        except Exception as e:
            QMessageBox.critical(
                cast(QWidget, self),
                "Config Error",
                f"Failed to apply image extractor configuration:\n{e}",
            )


__all__ = ["_ConfigMethodsMixin"]
