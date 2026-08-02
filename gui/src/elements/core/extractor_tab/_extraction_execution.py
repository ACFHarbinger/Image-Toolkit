"""Single-frame snapshot and range extraction triggers (queue-aware),
target-resolution resolution, and the FrameExtractionWorker dispatch path.

Extracted from ``extractor_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
from PySide6.QtCore import Qt, QThreadPool, Slot
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QDialog, QMessageBox, QStyle

from ....components import ClickableLabel, FrameSelectionDialog
from ....helpers import FrameExtractionWorker


class _ExtractionExecutionMixin:
    """Snapshot/range extraction triggers, target-resolution resolution,
    and the FrameExtractionWorker dispatch path."""

    # --- NEW HELPER: Resolution Swapping ---
    def _get_target_size(self) -> Optional[Union[Tuple[int | str, int | str], str]]:
        selected_key = self.combo_extract_size.currentText()
        target_size = self.extraction_res_map.get(selected_key)
        if selected_key == "Native":
            if self.video_path and os.path.exists(self.video_path):
                cap = cv2.VideoCapture(self.video_path)
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                target_size = (w, h) if w > 0 and h > 0 else None
            else:
                target_size = None
        # If vertical output is checked, flip dimensions
        if target_size and self.check_extract_vertical.isChecked():
            return (target_size[1], target_size[0])
        return target_size

    # ---------------------------------------

    @Slot()
    def extract_single_frame(self):
        if not self.video_path:
            return

        # Pause player if running
        if (
            self.use_internal_player
            and self.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )

        # Use current player position as starting point if possible
        start_ms = (
            self.media_player.position()
            if self.use_internal_player
            else self.start_time_ms
        )

        dlg = FrameSelectionDialog(self.video_path, start_ms=start_ms, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            timestamp_ms = int(dlg.selected_frame_idx / dlg.fps * 1000)
            if self.extraction_queue_enabled:
                config = {
                    "type": "single",
                    "video_path": self.video_path,
                    "start_ms": timestamp_ms,
                    "end_ms": timestamp_ms,
                    "output_dir": str(self.extraction_dir),
                    "target_resolution": self._get_target_size(),
                    "cuts_ms": [],
                    "frame_interval": 1,
                    "smart_extract": False,
                    "smart_method": "",
                    "fps": getattr(dlg, "fps", 23.976),
                    "mute_audio": False,
                    "use_ffmpeg": True,
                    "speed": "1.0",
                }
                self.extraction_queue.append(config)
                self._update_queue_ui()
                self.extraction_status_label.setText(
                    f"Added snapshot to queue. Queue size: {len(self.extraction_queue)}"
                )
                self.extraction_status_label.show()
                return

            if dlg.selected_image:
                self.extraction_status_label.setText("Saving snapshot...")
                self.extraction_status_label.show()
                self.qml_extraction_status.emit("Saving snapshot...")

                # Use target size logic if not "Native"
                target_size = self._get_target_size()
                img = dlg.selected_image
                if target_size:
                    img = img.scaled(
                        target_size[0],
                        target_size[1],
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )

                filename = f"{Path(self.video_path).stem}_snap_{timestamp_ms}ms.png"
                out_path = self.extraction_dir / filename

                if img.save(str(out_path)):
                    self.extraction_status_label.setText(f"Snapshot saved: {filename}")
                    self.extraction_status_label.show()

                    # Record metadata
                    metadata = self._get_current_extraction_metadata()
                    metadata["mode"] = "snapshot"
                    metadata["start_ms"] = timestamp_ms
                    metadata["end_ms"] = timestamp_ms
                    metadata["fps"] = getattr(dlg, "fps", 23.976)
                    self._record_extraction([str(out_path)], metadata)

                    # Update cache and refresh the source label style
                    self._refresh_extracted_stems_cache()
                    if self.video_path in self.source_path_to_widget:
                        widget = self.source_path_to_widget[self.video_path]
                        label = widget.findChild(ClickableLabel)
                        if label:
                            self._update_source_label_style(
                                self.video_path, label, True
                            )

                    self.start_loading_gallery([str(out_path)], append=True)
                    self.current_extracted_paths = self.gallery_image_paths[:]
                else:
                    QMessageBox.critical(self, "Error", "Failed to save snapshot.")

    def _set_extraction_buttons_enabled(self, enabled: bool):
        """Helper to enable/disable all extraction-related buttons."""
        self.btn_snapshot.setEnabled(enabled and self.video_path is not None)
        self.btn_set_start.setEnabled(enabled and self.video_path is not None)
        self.btn_set_end.setEnabled(enabled and self.video_path is not None)
        self.btn_set_cut_start.setEnabled(enabled and self.video_path is not None)
        self.btn_set_cut_end.setEnabled(enabled and self.video_path is not None)

        # We handle btn_add_cut and btn_clear_cuts logic independently based on internal states
        # but if we disable extraction entirely, disable those too
        if not enabled:
            self.btn_add_cut.setEnabled(False)
            self.btn_clear_cuts.setEnabled(False)
        else:
            self._validate_cut_range()
            self._update_cuts_label()

        self.btn_extract_range.setEnabled(
            enabled and self.end_time_ms > self.start_time_ms
        )
        self.btn_extract_gif.setEnabled(
            enabled and self.end_time_ms > self.start_time_ms
        )
        self.btn_extract_video.setEnabled(
            enabled and self.end_time_ms > self.start_time_ms
        )

        # Also disable browsing while extracting to avoid path changes
        self.btn_browse.setEnabled(enabled)
        self.btn_browse_extract.setEnabled(enabled)

        # Show/hide action buttons vs cancel button
        self.btn_extract_range.setVisible(enabled)
        self.btn_extract_video.setVisible(enabled)
        self.btn_extract_gif.setVisible(enabled)

        self.btn_cancel_extraction.setVisible(not enabled)
        if not enabled:
            self.btn_cancel_extraction.setEnabled(True)

    @Slot()
    def cancel_extraction(self, enabled: bool = True):
        if self.active_extraction_worker:
            self.active_extraction_worker.cancel()
            self.active_extraction_worker = None

        # The worker returns without emitting finished/error on cancellation, so
        # re-enable the UI here rather than waiting for a signal that never arrives.
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()
        self.line_edit_dir.setEnabled(True)
        self.btn_add_tag.setEnabled(self.video_path is not None)
        self.btn_clear_tags.setEnabled(len(self.tags_ms) > 0)

    @Slot()
    def extract_range(self):
        if not self.video_path:
            return
        if self.use_internal_player:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        self._run_extraction(self.start_time_ms, self.end_time_ms, is_range=True)

    @Slot()
    def extract_range_as_gif(self):
        if not self.video_path:
            return
        if self.use_internal_player:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        self._run_gif_extraction(self.start_time_ms, self.end_time_ms)

    @Slot()
    def extract_range_as_video(self):
        if not self.video_path:
            return
        if self.use_internal_player:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        self._run_video_extraction(self.start_time_ms, self.end_time_ms)

    def _run_extraction(self, start: int, end: int, is_range: bool):
        target_size = self._get_target_size()

        if self.extraction_queue_enabled:
            config = {
                "type": "range" if is_range else "single",
                "video_path": self.video_path,
                "start_ms": start,
                "end_ms": end,
                "output_dir": str(self.extraction_dir),
                "target_resolution": target_size,
                "cuts_ms": self.cuts_ms[:],
                "frame_interval": self.spin_interval.value(),
                "smart_extract": self.check_smart_extract.isChecked(),
                "smart_method": self.combo_smart_method.currentText(),
                "fps": 23.976,
                "mute_audio": False,
                "use_ffmpeg": True,
                "speed": 1.0,
            }
            self.extraction_queue.append(config)
            self._update_queue_ui()
            self.extraction_status_label.setText(
                f"Added frame range to queue. Queue size: {len(self.extraction_queue)}"
            )
            self.extraction_status_label.show()
            return

        self._set_extraction_buttons_enabled(False)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText("Extracting frames...")
        self.extraction_status_label.show()

        self._active_metadata = self._get_current_extraction_metadata()
        self._active_metadata["mode"] = "range" if is_range else "single"

        assert self.video_path is not None
        self.active_extraction_worker = FrameExtractionWorker(
            video_path=self.video_path,
            output_dir=str(self.extraction_dir),
            start_ms=start,
            end_ms=end,
            is_range=is_range,
            target_resolution=target_size,
            cuts_ms=self.cuts_ms,
            frame_interval=self.spin_interval.value(),
            smart_extract=self.check_smart_extract.isChecked(),
            smart_method=self.combo_smart_method.currentText(),
        )
        self.active_extraction_worker.signals.progress.connect(
            self.extraction_progress_bar.setValue
        )
        self.active_extraction_worker.signals.finished.connect(
            self._on_extraction_finished
        )
        self.active_extraction_worker.signals.error.connect(
            lambda e: self._on_extraction_error(e)
        )
        QThreadPool.globalInstance().start(self.active_extraction_worker)

    def _on_extraction_error(self, error_msg: str):
        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()
        self._active_metadata = None
        if "cancelled" not in error_msg.lower():
            QMessageBox.warning(self, "Extraction Error", error_msg)


__all__ = ["_ExtractionExecutionMixin"]
