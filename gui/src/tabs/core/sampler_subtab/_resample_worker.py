"""SamplerWorker config collection and start/progress/finished/error handling.

Extracted from ``sampler_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from ....helpers import SamplerWorker
from ....styles import SHARED_BUTTON_STYLE


class _ResampleWorkerMixin:
    """Starts/reacts to the SamplerWorker background resample job."""

    def _collect_config(self, use_selection: bool) -> dict:
        files = list(self.selected_files) if use_selection else self._collect_paths()
        scale_mode = "factor" if self._radio_factor.isChecked() else "dimensions"
        algo_map = {
            "Lanczos": "lanczos",
            "Bicubic": "bicubic",
            "Bilinear": "bilinear",
            "Nearest Neighbor": "nearest",
        }
        fmt_text = self.out_format_combo.currentText()
        out_fmt = (
            None
            if fmt_text.startswith("Keep") or "---" in fmt_text
            else fmt_text.lower()
        )
        return {
            "files_to_process": files,
            "scale_mode": scale_mode,
            "scale_factor": self.scale_factor_spin.value(),
            "target_width": self.dim_w_spin.value()
            if scale_mode == "dimensions"
            else None,
            "target_height": self.dim_h_spin.value()
            if scale_mode == "dimensions"
            else None,
            "preserve_aspect_ratio": self.preserve_ar_cb.isChecked(),
            "algorithm": algo_map.get(self.algorithm_combo.currentText(), "lanczos"),
            "output_format": out_fmt,
            "output_path": self.out_dir_edit.text().strip() or None,
            "output_filename_prefix": self.prefix_edit.text().strip(),
            "delete_original": self.delete_cb.isChecked(),
            "use_multicore": self.multicore_cb.isChecked(),
        }

    @Slot(bool)
    def _start_worker(self, use_selection: bool):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
            self._on_done(0, "**Resampling cancelled**")
            return

        config = self._collect_config(use_selection)
        if not config["files_to_process"]:
            QMessageBox.warning(self, "No Files", "No files to resample.")
            return

        self.worker = SamplerWorker(config)
        self.worker.sig_finished.connect(self._on_done)
        self.worker.error.connect(self._on_error)
        self.worker.progress_update.connect(self._on_progress)

        self.btn_all.setEnabled(False)
        self.btn_selected.setEnabled(False)
        cancel_btn = self.btn_selected if use_selection else self.btn_all
        cancel_btn.setEnabled(True)
        cancel_btn.setText("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton {  color: white; font-weight: bold; }"
        )

        n = len(config["files_to_process"])
        self.status_label.setText(f"Resampling {n} file(s)…") # pyrefly: ignore [missing-attribute]
        self.progress_bar.show()
        self.worker.start()

    @Slot(int, int)
    def _on_progress(self, completed: int, total: int):
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(completed)
        pct = int(completed / total * 100) if total else 0
        self.status_label.setText(f"Resampling… {pct}% complete") # pyrefly: ignore [missing-attribute]

    @Slot(int, str)
    def _on_done(self, count: int, msg: str):
        self.btn_all.setEnabled(True)
        self.btn_all.setText("Resample All in Directory")
        self.btn_all.setStyleSheet(SHARED_BUTTON_STYLE)
        self.on_selection_changed()
        self.btn_selected.setStyleSheet(SHARED_BUTTON_STYLE)
        self.progress_bar.hide()
        self.progress_bar.setValue(0)
        self.status_label.setText(msg) # pyrefly: ignore [missing-attribute]
        self.worker = None
        if "cancelled" not in msg.lower():
            QMessageBox.information(self, "Complete", msg)

    @Slot(str)
    def _on_error(self, msg: str):
        self._on_done(0, msg)
        QMessageBox.critical(self, "Error", msg)


__all__ = ["_ResampleWorkerMixin"]
