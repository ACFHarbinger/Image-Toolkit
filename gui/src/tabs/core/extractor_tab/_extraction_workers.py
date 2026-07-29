"""GIF/video-clip extraction worker dispatch, export completion handling,
extraction-metadata snapshotting, and time formatting/parsing.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMessageBox

from ....components import ClickableLabel
from ....helpers import GifCreationWorker, VideoExtractionWorker
from ....helpers.video.video_scan_worker import VideoThumbnailer


class _ExtractionWorkersMixin:
    """GIF/video export worker dispatch, export completion, metadata
    snapshotting, and time formatting/parsing."""

    def _run_gif_extraction(self, start: int, end: int):
        target_size = self._get_target_size()
        fps = self.spin_gif_fps.value()

        # Speed
        speed_str = self.combo_speed.currentText().replace("x", "")
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 1.0

        if self.extraction_queue_enabled:
            config = {
                "type": "gif",
                "video_path": self.video_path,
                "start_ms": start,
                "end_ms": end,
                "output_dir": str(self.extraction_dir),
                "target_resolution": target_size,
                "cuts_ms": self.cuts_ms[:],
                "frame_interval": 1,
                "smart_extract": False,
                "smart_method": "",
                "fps": fps,
                "mute_audio": False,
                "use_ffmpeg": (self.combo_engine.currentText() == "FFmpeg"),
                "speed": speed,
            }
            self.extraction_queue.append(config)
            self._update_queue_ui()
            self.extraction_status_label.setText(
                f"Added GIF extract to queue. Queue size: {len(self.extraction_queue)}"
            )
            self.extraction_status_label.show()
            return

        self._set_extraction_buttons_enabled(False)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText(
            "Generating GIF... This may take a moment."
        )
        self.extraction_status_label.show()

        self._active_metadata = self._get_current_extraction_metadata()
        self._active_metadata["mode"] = "gif"

        assert self.video_path is not None
        output_name = f"{Path(self.video_path).stem}_{start}ms_{end}ms.gif"
        output_path = str(self.extraction_dir / output_name)
        self.active_extraction_worker = GifCreationWorker(
            video_path=self.video_path,
            start_ms=start,
            end_ms=end,
            output_path=output_path,
            target_size=target_size,
            fps=fps,
            use_ffmpeg=(self.combo_engine.currentText() == "FFmpeg"),
            speed=speed,
            cuts_ms=self.cuts_ms,
        )
        self.active_extraction_worker.signals.progress.connect(
            self.extraction_progress_bar.setValue
        )
        self.active_extraction_worker.signals.finished.connect(self._on_export_finished)
        self.active_extraction_worker.signals.error.connect(self._on_export_error)
        QThreadPool.globalInstance().start(self.active_extraction_worker)

    def _run_video_extraction(self, start: int, end: int):
        target_size = self._get_target_size()
        mute_audio = self.check_mute_audio.isChecked()

        # Speed
        speed_str = self.combo_speed.currentText().replace("x", "")
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 1.0

        if self.extraction_queue_enabled:
            config = {
                "type": "video",
                "video_path": self.video_path,
                "start_ms": start,
                "end_ms": end,
                "output_dir": str(self.extraction_dir),
                "target_resolution": target_size,
                "cuts_ms": self.cuts_ms[:],
                "frame_interval": 1,
                "smart_extract": False,
                "smart_method": "",
                "fps": 23.976,
                "mute_audio": mute_audio,
                "use_ffmpeg": (self.combo_engine.currentText() == "FFmpeg"),
                "speed": speed,
            }
            self.extraction_queue.append(config)
            self._update_queue_ui()
            self.extraction_status_label.setText(
                f"Added video extract to queue. Queue size: {len(self.extraction_queue)}"
            )
            self.extraction_status_label.show()
            return

        self._set_extraction_buttons_enabled(False)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText(
            "Extracting video clip... This may take a moment."
        )
        self.extraction_status_label.show()

        self._active_metadata = self._get_current_extraction_metadata()
        self._active_metadata["mode"] = "video"

        output_name = f"{Path(self.video_path).stem}_{start}ms_{end}ms.mp4" # pyrefly: ignore [bad-argument-type]
        output_path = str(self.extraction_dir / output_name)

        assert self.video_path is not None
        self.active_extraction_worker = VideoExtractionWorker(
            video_path=self.video_path,
            start_ms=start,
            end_ms=end,
            output_path=output_path,
            target_size=target_size,
            mute_audio=mute_audio,
            use_ffmpeg=(self.combo_engine.currentText() == "FFmpeg"),
            speed=speed,
            cuts_ms=self.cuts_ms,
        )
        self.active_extraction_worker.signals.progress.connect(
            self.extraction_progress_bar.setValue
        )
        self.active_extraction_worker.signals.finished.connect(self._on_export_finished)
        self.active_extraction_worker.signals.error.connect(self._on_export_error)
        QThreadPool.globalInstance().start(self.active_extraction_worker)

    @Slot(str)
    def _on_export_finished(self, new_path: str):
        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        if new_path and os.path.exists(new_path):
            if new_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                thumb = self._generate_video_thumbnail(new_path)
                if thumb:
                    self._initial_pixmap_cache[new_path] = thumb.toImage()

            # Base class handles list management and loading
            self.start_loading_gallery([new_path], append=True)

            # Keep local list synced
            self.current_extracted_paths = self.gallery_image_paths[:]

            if self._active_metadata:
                self._record_extraction([new_path], self._active_metadata)
            self._active_metadata = None

            QMessageBox.information(
                self, "Success", f"Media created successfully:\n{Path(new_path).name}"
            )

    @Slot(str)
    def _on_export_error(self, error_msg: str):
        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()
        self._active_metadata = None
        if "cancelled" not in error_msg.lower():
            QMessageBox.warning(self, "Export Error", error_msg)

    def _generate_video_thumbnail(self, path: str) -> Optional[QPixmap]:
        """Generate a thumbnail for a single video file."""
        thumbnailer = VideoThumbnailer()
        q_image = thumbnailer.generate(path, self.thumbnail_size)

        if q_image and not q_image.isNull():
            return QPixmap.fromImage(q_image)
        return None

    @Slot(list)
    def _on_extraction_finished(self, new_paths: List[str]):
        if self._active_metadata and new_paths:
            if self.active_extraction_worker and hasattr(
                self.active_extraction_worker, "fps"
            ):
                self._active_metadata["fps"] = self.active_extraction_worker.fps
            self._record_extraction(new_paths, self._active_metadata)

            # Update cache and refresh the source label style
            self._refresh_extracted_stems_cache()
            if self.video_path in self.source_path_to_widget:
                widget = self.source_path_to_widget[self.video_path]
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(self.video_path, label, True)

        self._active_metadata = None

        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        if not new_paths:
            QMessageBox.information(self, "Info", "No frames extracted.")
            return

        self.start_loading_gallery(new_paths, append=True)
        self.current_extracted_paths = self.gallery_image_paths[:]
        self._refresh_source_extracted_indicators()

        QMessageBox.information(
            self,
            "Success",
            f"Extracted {len(new_paths)} images. Total: {len(self.current_extracted_paths)}",
        )

    def _get_current_extraction_metadata(self) -> dict:
        """Collects current UI state as metadata for an extraction run."""
        return {
            "video_path": str(self.video_path),
            "start_ms": self.start_time_ms,
            "end_ms": self.end_time_ms,
            "cuts_ms": self.cuts_ms[:],
            "tags_ms": self.tags_ms[:],
            "output_size": self.combo_extract_size.currentText(),
            "extract_vertical": self.check_extract_vertical.isChecked(),
            "gif_fps": self.spin_gif_fps.value(),
            "mute_audio": self.check_mute_audio.isChecked(),
            "engine": self.combo_engine.currentText(),
            "frame_interval": self.spin_interval.value(),
            "smart_extract": self.check_smart_extract.isChecked(),
            "smart_method": self.combo_smart_method.currentText(),
            "speed": self.combo_speed.currentText(),
            "timestamp": time.time(),
        }

    def _format_time(self, ms: int) -> str:
        fmt = getattr(self, "time_display_format", "m:s:ms")
        if fmt == "h:m:s":
            hours = ms // 3600000
            minutes = (ms // 60000) % 60
            seconds = (ms // 1000) % 60
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        elif fmt == "microseconds":
            return f"{ms * 1000}"
        elif fmt == "milliseconds":
            return f"{ms}"
        else:  # default "m:s:ms"
            seconds = (ms // 1000) % 60
            minutes = (ms // 60000) % 60
            milliseconds = ms % 1000
            return f"{minutes:02}:{seconds:02}:{milliseconds:03}"

    def _parse_time(self, time_str: str) -> Optional[int]:
        """Parses various formats (MM:SS:mmm, HH:MM:SS, pure milliseconds, or microseconds) into milliseconds."""
        try:
            time_str = time_str.strip()
            # If digit only, parse as number of units based on current format
            if time_str.isdigit():
                val = int(time_str)
                fmt = getattr(self, "time_display_format", "m:s:ms")
                if fmt == "microseconds":
                    return val // 1000
                elif fmt == "milliseconds":
                    return val
                else:
                    if val > 100000000:
                        return val // 1000
                    return val

            parts = time_str.replace(",", ".").split(":")
            fmt = getattr(self, "time_display_format", "m:s:ms")
            if len(parts) == 3:
                if fmt == "h:m:s":
                    h, m, s = parts
                    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000
                else:
                    m, s, ms = parts
                    return int(m) * 60000 + int(s) * 1000 + int(ms)
            elif len(parts) == 2:
                # MM:SS or SS.mmm
                if "." in parts[1]:
                    m, s_ms = parts
                    s, ms = s_ms.split(".")
                    return int(m) * 60000 + int(s) * 1000 + int(ms.ljust(3, "0")[:3])
                else:
                    m, s = parts
                    return int(m) * 60000 + int(s) * 1000
            elif len(parts) == 1:
                # SS or SS.mmm
                if "." in parts[0]:
                    s, ms = parts[0].split(".")
                    return int(s) * 1000 + int(ms.ljust(3, "0")[:3])
                else:
                    return int(parts[0]) * 1000
        except Exception:
            pass
        return None

    def refresh_time_display(self):
        if self._media_player is not None:
            pos = self.media_player.position()
            dur = self.media_player.duration()
            if self.lbl_current_time:
                self.lbl_current_time.setText(self._format_time(pos))
            if self.lbl_total_time:
                self.lbl_total_time.setText(self._format_time(dur))

        # Update start, end, cut_start, and cut_end buttons
        if hasattr(self, "btn_set_start") and self.btn_set_start:
            self.btn_set_start.setText(
                f"Start [{self._format_time(self.start_time_ms)}]"
                if self.start_time_ms
                else "Set Start [00:00]"
            )
        if hasattr(self, "btn_set_end") and self.btn_set_end:
            self.btn_set_end.setText(
                f"End [{self._format_time(self.end_time_ms)}]"
                if self.end_time_ms
                else "Set End [00:00]"
            )
        if hasattr(self, "btn_set_cut_start") and self.btn_set_cut_start:
            self.btn_set_cut_start.setText(
                f"Cut Start [{self._format_time(self.cut_start_ms)}]"
                if self.cut_start_ms
                else "Set Cut Start [00:00]"
            )
        if hasattr(self, "btn_set_cut_end") and self.btn_set_cut_end:
            self.btn_set_cut_end.setText(
                f"Cut End [{self._format_time(self.cut_end_ms)}]"
                if self.cut_end_ms
                else "Set Cut End [00:00]"
            )

        # Update cuts and tags UI list
        if hasattr(self, "_update_cuts_label"):
            self._update_cuts_label()
        if hasattr(self, "_update_tags_ui"):
            self._update_tags_ui()

    @Slot()
    def _jump_to_edited_time(self):
        time_str = self.edit_current_time.text() # pyrefly: ignore [missing-attribute]
        ms = self._parse_time(time_str)
        if ms is not None:
            # Clamp to duration
            ms = max(0, min(ms, self.media_player.duration()))
            self.media_player.setPosition(ms)
        self._cancel_time_edit()

    def _cancel_time_edit(self):
        self.edit_current_time.hide() # pyrefly: ignore [missing-attribute]
        self.lbl_current_time.show() # pyrefly: ignore [missing-attribute]


__all__ = ["_ExtractionWorkersMixin"]
