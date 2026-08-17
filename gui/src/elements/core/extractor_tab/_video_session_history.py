"""Active-video-tabs bar management, per-video config persistence, and the
extraction-history JSON (recent extractions dropdown).

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import copy
import json
import time
from pathlib import Path
from typing import List, Optional, cast

from backend.src.constants import IMAGE_TOOLKIT_DIR
from PySide6.QtCore import QUrl, Slot
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QWidget

from ....components import ClickableLabel

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _VideoSessionHistoryMixin:
    """Active-video-tabs bar, per-video config persistence, and the
    extraction-history JSON."""

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
        if pos > 0 and self.media_player:
            self.media_player.setPosition(pos)
            self.slider.setValue(pos)
            cast(QLabel, self.lbl_current_time).setText(self._format_time(pos)) # pyrefly: ignore [missing-attribute]

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
                cast(QWidget, self), "Cannot Close", "Cannot close the last active video."
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
    def load_media(self: "VideoExtractorSubTabHostProtocol", file_path: str, force: bool = False, defer_player: bool = False):
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
            return

        self._media_load_pending = False
        self._apply_player_mode()
        self._start_storyboard()

    @Slot()
    def browse_extraction_directory(self: "VideoExtractorSubTabHostProtocol"):
        d = QFileDialog.getExistingDirectory(
            cast(QWidget, self), "Select Extraction Directory", self.last_browsed_extraction_dir
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

    def _load_extraction_history(self: "VideoExtractorSubTabHostProtocol"):
        """Loads metadata for extracted frames from a central hidden JSON file."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "recent_runs" in data:
                        self.recent_runs = data.get("recent_runs", [])
                        self.extraction_metadata = data.get("file_map", {})
                    else:
                        # Legacy format where the whole json was extraction_metadata
                        self.extraction_metadata = data
                        # Reconstruct recent_runs from unique metadata in extraction_metadata
                        unique_runs = {}
                        for meta in self.extraction_metadata.values():
                            ts = meta.get("timestamp", 0)
                            unique_runs[ts] = meta
                        self.recent_runs = sorted(
                            unique_runs.values(),
                            key=lambda x: x.get("timestamp", 0),
                            reverse=True,
                        )
            except Exception as e:
                print(f"Error loading extraction history: {e}")
                self.extraction_metadata = {}
                self.recent_runs = []
        else:
            self.extraction_metadata = {}
            self.recent_runs = []

        if (
            hasattr(self, "combo_recent_extractions")
            and self.combo_recent_extractions is not None
        ):
            self._update_recent_extractions_ui()

    def _save_extraction_history(self: "VideoExtractorSubTabHostProtocol"):
        """Saves metadata for extracted frames to a central hidden JSON file."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "recent_runs": self.recent_runs,
                "file_map": self.extraction_metadata,
            }
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving extraction history: {e}")

    def _record_extraction(self: "VideoExtractorSubTabHostProtocol", file_paths: List[str], metadata: dict):
        """Records metadata for a set of extracted files using absolute paths as keys."""
        metadata = copy.deepcopy(metadata)
        # 1. Update file_map for the new files
        for path in file_paths:
            abs_path = str(Path(path).absolute())
            self.extraction_metadata[abs_path] = metadata

        # 2. Add to recent runs (avoid duplicate additions based on timestamp)
        run_ts = metadata.get("timestamp")
        if not any(run.get("timestamp") == run_ts for run in self.recent_runs):
            self.recent_runs.append(metadata)

        # 3. Sort recent runs and limit to N
        self.recent_runs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        self.recent_runs = self.recent_runs[: self.recent_extractions_limit]

        # 4. Prune file_map to only contain files from the N most recent runs
        recent_timestamps = {
            run.get("timestamp") for run in self.recent_runs if run.get("timestamp")
        }
        keys_to_delete = [
            path
            for path, meta in self.extraction_metadata.items()
            if meta.get("timestamp") not in recent_timestamps
        ]
        for key in keys_to_delete:
            del self.extraction_metadata[key]

        self._save_extraction_history()
        self._update_recent_extractions_ui()

    def _apply_new_extractions_limit(self: "VideoExtractorSubTabHostProtocol"):
        """Called when the settings window updates recent_extractions_limit."""
        if hasattr(self, "recent_runs") and self.recent_runs:
            self.recent_runs = self.recent_runs[: self.recent_extractions_limit]

            # Prune file_map too
            recent_timestamps = {
                run.get("timestamp") for run in self.recent_runs if run.get("timestamp")
            }
            keys_to_delete = [
                path
                for path, meta in self.extraction_metadata.items()
                if meta.get("timestamp") not in recent_timestamps
            ]
            for key in keys_to_delete:
                del self.extraction_metadata[key]

            self._save_extraction_history()
            self._update_recent_extractions_ui()

    def _update_recent_extractions_ui(self: "VideoExtractorSubTabHostProtocol"):
        """Updates the dropdown of recent extractions in the Extract tab."""
        if self._recent_combo_connected:
            with contextlib.suppress(RuntimeError, TypeError):
                self.combo_recent_extractions.currentIndexChanged.disconnect(
                    self._on_recent_extraction_selected
                )
            self._recent_combo_connected = False

        self.combo_recent_extractions.clear()
        self.combo_recent_extractions.addItem("Select a previous configuration...")

        for run in self.recent_runs:
            video_path = run.get("video_path", "")
            video_name = Path(video_path).name if video_path else "Unknown Video"
            start_ms = run.get("start_ms", 0)
            end_ms = run.get("end_ms", 0)
            engine = run.get("engine", "FFmpeg")

            # Format timestamp nicely
            ts = run.get("timestamp", 0)
            ts_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "N/A"
            )

            start_str = self._format_time(start_ms)
            end_str = self._format_time(end_ms)

            label = f"[{ts_str}] {video_name} ({start_str} - {end_str}) [{engine}]"
            # Set the metadata dictionary as the item data!
            self.combo_recent_extractions.addItem(label, run)

        if hasattr(self, "btn_load_recent") and self.btn_load_recent is not None:
            self.btn_load_recent.setEnabled(
                self.combo_recent_extractions.currentIndex() > 0
            )

        self.combo_recent_extractions.currentIndexChanged.connect(
            self._on_recent_extraction_selected
        )
        self._recent_combo_connected = True

    def _on_recent_extraction_selected(self: "VideoExtractorSubTabHostProtocol", index: int):
        """Enables/disables the load button based on selection."""
        if hasattr(self, "btn_load_recent") and self.btn_load_recent is not None:
            self.btn_load_recent.setEnabled(index > 0)

    def _load_selected_recent_extraction(self: "VideoExtractorSubTabHostProtocol"):
        """Loads the selected recent extraction configuration into the UI."""
        index = self.combo_recent_extractions.currentIndex()
        if index <= 0:
            QMessageBox.warning(
                cast(QWidget, self), "Error", "Please select a valid configuration from the list."
            )
            return

        run_data = self.combo_recent_extractions.itemData(index)
        if run_data:
            self._reload_extraction(run_data)
            QMessageBox.information(
                cast(QWidget, self), "Success", "Extraction configuration loaded successfully."
            )

    def _clear_output_gallery(self: "VideoExtractorSubTabHostProtocol"):
        """Clear only the extracted-output gallery (not source media or player state)."""
        output_paths = set(self.gallery_image_paths) | set(
            self.current_extracted_paths
        )
        for path in output_paths:
            self._initial_pixmap_cache.pop(path, None)

        self.current_extracted_paths.clear()
        self.selected_paths.clear()
        self.gallery_image_paths.clear()
        self.clear_gallery_widgets()

    def _clear_gallery(self: "VideoExtractorSubTabHostProtocol"):
        self._clear_output_gallery()
        self._initial_pixmap_cache.clear()
        self.start_time_ms = 0
        self.end_time_ms = 0

        # --- MODIFIED: Reset Snapshot button ---
        self.btn_snapshot.setEnabled(False)
        self.btn_snapshot.setText("📸 Snapshot Frame")
        # ---------------------------------------

        self.btn_set_start.setText("Set Start [00:00:000]")
        self.btn_set_end.setText("Set End [00:00:000]")

        self.btn_set_cut_start.setText("Set Cut Start [00:00]")
        self.btn_set_cut_end.setText("Set Cut End [00:00]")
        self.btn_add_cut.setEnabled(False)
        self.cuts_ms.clear()
        self._update_cuts_label()

        self.btn_add_tag.setEnabled(False)
        self.tags_ms.clear()
        self._update_tags_ui()
        self.btn_extract_range.setEnabled(False)
        self.btn_extract_gif.setEnabled(False)
        self.btn_extract_gif.setEnabled(False)
        self.btn_extract_video.setEnabled(False)
        self.btn_extract_range.setText("🎞️ Extract Range")

        self.btn_jump_start.setEnabled(False)
        self.btn_jump_end.setEnabled(False)


__all__ = ["_VideoSessionHistoryMixin"]
