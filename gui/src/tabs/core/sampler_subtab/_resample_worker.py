"""SamplerWorker config collection and start/progress/finished/error handling."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt, QTimer, Slot
from PySide6.QtWidgets import QMessageBox

from ....helpers import SamplerWorker
from ....theming.theme_api import qss
from ._tab_bound import TabBoundController
from .no_gpu_window import confirm_slow_gif


class SamplerWorkerController(TabBoundController):
    """Starts/reacts to the SamplerWorker background resample job."""

    def _collect_config(self, use_selection: bool) -> dict:
        files = list(self.selected_files) if use_selection else self._collect_paths()
        scale_mode = "factor" if self._radio_factor.isChecked() else "dimensions"
        fmt_text = self.out_format_combo.currentText()
        out_fmt = None if fmt_text.startswith("Keep") or "---" in fmt_text else fmt_text.lower()
        algorithm = self.algorithm_combo.currentData()
        return {
            "files_to_process": files,
            "scale_mode": scale_mode,
            "scale_factor": self.scale_factor_spin.value(),
            "target_width": self.dim_w_spin.value() if scale_mode == "dimensions" else None,
            "target_height": self.dim_h_spin.value() if scale_mode == "dimensions" else None,
            "preserve_aspect_ratio": self.preserve_ar_cb.isChecked(),
            "algorithm": str(algorithm or "lanczos"),
            "output_format": out_fmt,
            "output_path": self.out_dir_edit.text().strip() or None,
            "output_filename_prefix": self.prefix_edit.text().strip(),
            "delete_original": self.delete_cb.isChecked(),
            "use_multicore": self.multicore_cb.isChecked(),
        }

    @Slot(bool)
    def _start_worker(self, use_selection: bool):
        if self.worker and self.worker.isRunning():
            # Never wait() here: this is the GUI thread. The worker stops at its next progress
            # checkpoint and its finished signal resets the buttons through _on_done.
            self.worker.cancel()
            cancel_btn = self.btn_selected if use_selection else self.btn_all
            cancel_btn.setEnabled(False)
            cancel_btn.setText("Cancelling…")
            self.status_label.setText("Cancelling…")  # pyrefly: ignore [missing-attribute]
            return

        config = self._collect_config(use_selection)
        if not config["files_to_process"]:
            QMessageBox.warning(self.tab, "No Files", "No files to resample.")
            return
        if not confirm_slow_gif(config, self.tab):
            return

        self.worker = SamplerWorker(config)
        # Queued: these slots touch widgets and must not run inside run().
        queued = Qt.ConnectionType.QueuedConnection
        self.worker.finished.connect(self._on_done, queued)
        self.worker.error.connect(self._on_error, queued)
        self.worker.progress_update.connect(self._on_progress, queued)
        self.worker.stage_update.connect(self._on_stage, queued)

        self.btn_all.setEnabled(False)
        self.btn_selected.setEnabled(False)
        cancel_btn = self.btn_selected if use_selection else self.btn_all
        cancel_btn.setEnabled(True)
        cancel_btn.setText("Cancel")
        cancel_btn.setStyleSheet(qss("btn_cancel_active"))

        n = len(config["files_to_process"])
        self.status_label.setText(f"Resampling {n} file(s)…")  # pyrefly: ignore [missing-attribute]
        self.progress_bar.show()
        self.tab.worker.start()

    @Slot(int, int)
    def _on_progress(self, completed: int, total: int):
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(min(max(completed, 0), max(total, 1)))

    @Slot(str)
    def _on_stage(self, text: str):
        self.status_label.setText(text)  # pyrefly: ignore [missing-attribute]

    @Slot(object)
    def _on_done(self, result):
        if result is None:  # failure — error path already reported
            return
        _count, msg = result
        self._reset_controls(msg)
        if "cancelled" not in msg.lower():
            QMessageBox.information(self.tab, "Complete", msg)

    def _reset_controls(self, msg: str) -> None:
        self.btn_all.setEnabled(True)
        self.btn_all.setText("Resample All in Directory")
        self.btn_all.setStyleSheet(qss("shared_button"))
        self.on_selection_changed()
        self.btn_selected.setStyleSheet(qss("shared_button"))
        self.progress_bar.hide()
        self.progress_bar.setValue(0)
        self.status_label.setText(msg)  # pyrefly: ignore [missing-attribute]
        # finished is emitted from inside run(), before the thread has stopped.
        # Dropping the last reference there destroys the QThread and aborts
        # the process ("QThread: Destroyed while thread is still running").
        self._retire_worker(self.tab.worker)

    def _retire_worker(self, worker) -> None:
        self.tab.worker = None
        if worker is None:
            return
        retired = getattr(self.tab, "_retired_workers", None)
        if retired is None:
            retired = []
            self.tab._retired_workers = retired
        if worker not in retired:
            retired.append(worker)
        self._drain_retired_workers()

    def _drain_retired_workers(self) -> None:
        retired = list(getattr(self.tab, "_retired_workers", ()) or ())
        if not retired:
            return
        alive = []
        for worker in retired:
            try:
                running = bool(worker.isRunning())
            except RuntimeError:
                continue
            if running:
                alive.append(worker)
        self.tab._retired_workers = alive
        if not alive:
            return
        app = QCoreApplication.instance()
        if app is None:
            return
        # context=app posts the callback to the GUI thread, even when this
        # slot ran directly inside the worker's run().
        QTimer.singleShot(50, app, self._drain_retired_workers)

    @Slot(object)
    def _on_error(self, err):
        msg = str(err)
        self._reset_controls(msg)
        QMessageBox.critical(self.tab, "Error", msg)


# COMPAT(ui-arch-23): legacy mixin alias
_ResampleWorkerMixin = SamplerWorkerController

__all__ = ["SamplerWorkerController", "_ResampleWorkerMixin"]
