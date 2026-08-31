"""Extractor-tab → Google Cloud Run offload (#487, Cloud Compute PoC).

One button: package the current range exactly like the local GIF path, upload
the source, run the extraction on GCD, pull the result into the gallery, and
record a usage row for the Cloud Compute Dashboards tab.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, cast

from PySide6.QtWidgets import QMessageBox, QWidget

from ....helpers.core.cloud_extraction_worker import (
    CloudConfigError,
    CloudExtractionWorker,
    build_dispatcher,
)

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class _CloudDispatchMixin:
    """"☁ Run on GCD" — mirrors the local GIF path but on Google Cloud Run."""

    _cloud_worker = None

    def _current_cloud_config(self: "VideoExtractorSubTabHostProtocol", mode: str = "gif") -> Dict[str, Any]:
        start = int(getattr(self, "start_time_ms", 0) or 0)
        end = int(getattr(self, "end_time_ms", 0) or 0)
        fps = self.spin_gif_fps.value()
        if getattr(self, "fps_clamp", 0) > 0:
            fps = min(fps, self.fps_clamp)
        try:
            speed = float(self.combo_speed.currentText().replace("x", ""))
        except ValueError:
            speed = 1.0
        return {
            "type": mode,
            "video_path": self.video_path,
            "start_ms": start,
            "end_ms": end,
            "output_dir": str(self.extraction_dir),
            "target_resolution": self._get_target_size(),
            "cuts_ms": list(getattr(self, "cuts_ms", []) or []),
            "frame_interval": 1,
            "fps": fps,
            "use_ffmpeg": self.combo_engine.currentText() == "FFmpeg",
            "speed": speed,
        }

    def run_current_on_gcd(self: "VideoExtractorSubTabHostProtocol", mode: str = "gif") -> None:
        if self._cloud_worker is not None:
            QMessageBox.information(cast(QWidget, self), "Cloud Extraction",
                                   "A cloud extraction is already running.")
            return
        if not getattr(self, "video_path", None):
            QMessageBox.warning(cast(QWidget, self), "No Video", "Load a video first.")
            return
        start = int(getattr(self, "start_time_ms", 0) or 0)
        end = int(getattr(self, "end_time_ms", 0) or 0)
        if end <= start:
            QMessageBox.warning(cast(QWidget, self), "No Range",
                                "Set a start and end point for the range first.")
            return

        vault = getattr(self.window(), "vault_manager", None)
        try:  # fail early with a helpful message if config is missing
            build_dispatcher(vault, str(self.extraction_dir))
        except CloudConfigError as exc:
            QMessageBox.warning(cast(QWidget, self), "Cloud Not Configured", str(exc))
            return

        if QMessageBox.question(
            cast(QWidget, self),
            "Upload to Google Cloud?",
            f"This uploads '{Path(self.video_path).name}' to your Google Cloud "
            "Storage bucket and runs the extraction on Cloud Run. Continue?",
        ) != QMessageBox.StandardButton.Yes:
            return

        config = self._current_cloud_config(mode)
        worker = CloudExtractionWorker(
            config, vault_manager=vault, output_dir=str(self.extraction_dir)
        )
        self._cloud_worker = worker
        if hasattr(self, "btn_run_on_gcd"):
            self.btn_run_on_gcd.setEnabled(False)
        self.extraction_status_label.setText("Running extraction on Google Cloud Run…")
        self.extraction_status_label.show()
        worker.signals.finished.connect(lambda r, w=worker: self._on_cloud_dispatch_finished(r, w))
        worker.signals.error.connect(lambda m, w=worker: self._on_cloud_dispatch_error(m, w))
        self.operation_thread_pool.start(worker)

    def _clear_cloud_worker(self: "VideoExtractorSubTabHostProtocol", worker) -> bool:
        if worker is not self._cloud_worker:
            return False
        self._cloud_worker = None
        if hasattr(self, "btn_run_on_gcd"):
            self.btn_run_on_gcd.setEnabled(True)
        return True

    def _on_cloud_dispatch_finished(self: "VideoExtractorSubTabHostProtocol", result: dict, worker=None) -> None:
        if not self._clear_cloud_worker(worker):
            return
        paths = [p for p in result.get("paths", []) if p]
        if paths:
            self._add_queue_results_to_gallery(paths)
            metadata = self._get_current_extraction_metadata()
            metadata["mode"] = self._current_cloud_config().get("type", "gif")
            metadata["cloud_provider"] = result.get("usage", {}).get("provider", "gcd")
            self._record_extraction(paths, metadata)
        usage = result.get("usage", {})
        dur = usage.get("duration_seconds", 0.0)
        self.extraction_status_label.setText(
            f"Cloud extraction complete — {len(paths)} file(s) in {dur:.1f}s "
            f"(job {result.get('job_id', '?')})."
        )
        self.extraction_status_label.show()

    def _on_cloud_dispatch_error(self: "VideoExtractorSubTabHostProtocol", message: str, worker=None) -> None:
        if not self._clear_cloud_worker(worker):
            return
        self.extraction_status_label.setText("Cloud extraction failed.")
        self.extraction_status_label.show()
        QMessageBox.warning(cast(QWidget, self), "Cloud Extraction Failed", message)


__all__ = ["_CloudDispatchMixin"]
