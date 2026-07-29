"""CodecScanWorker dispatch and probe-result aggregation/filtering.

Extracted from ``codec_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from .....helpers import CodecScanWorker
from .....utils.sort_utils import natural_sort_key


class _CodecProbeMixin:
    """Probes candidate files' codecs and filters by the active source filters."""

    def _start_codec_probe_scan(self, paths: list[str]):
        if self._codec_scan_worker is not None:
            self._codec_scan_worker.stop()
            self._codec_scan_worker = None

        self._codec_probe_results = {}
        self.scan_progress_bar.setMinimum(0)
        self.scan_progress_bar.setMaximum(len(paths))
        self.scan_progress_bar.setValue(0)
        self.scan_progress_bar.setFormat("Probing codecs... %v/%m")
        self.scan_progress_bar.show()
        self.status_label.setText(f"Probing codecs for {len(paths)} file(s)...") # pyrefly: ignore [missing-attribute]

        worker = CodecScanWorker(paths)
        worker.signals.codec_ready.connect(self._on_codec_probe_result)
        worker.signals.finished.connect(self._on_codec_probe_finished)
        self._codec_scan_worker = worker
        self.thread_pool.start(worker)

    @Slot(str, object, object)
    def _on_codec_probe_result(self, path: str, video_codec, audio_codec):
        self._codec_probe_results[path] = (video_codec, audio_codec)
        self.scan_progress_bar.setValue(len(self._codec_probe_results))

    @Slot()
    def _on_codec_probe_finished(self):
        self.scan_progress_bar.hide()
        self._codec_scan_worker = None

        matched = []
        for path, (video_codec, audio_codec) in self._codec_probe_results.items():
            if self.selected_video_codecs and (
                not video_codec or video_codec not in self.selected_video_codecs
            ):
                continue
            if self.selected_audio_codecs and (
                not audio_codec or audio_codec not in self.selected_audio_codecs
            ):
                continue
            matched.append(path)

        if not matched:
            QMessageBox.information(
                self, "No Files", "No files matched the selected codec filters."
            )
            self.clear_galleries()
            return

        self.start_loading_thumbnails(sorted(matched, key=natural_sort_key))


__all__ = ["_CodecProbeMixin"]
