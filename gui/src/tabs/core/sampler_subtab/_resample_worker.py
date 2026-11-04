"""SamplerWorker config collection and start/progress/finished/error handling."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QDialog, QMessageBox

from ....helpers import SamplerWorker
from ....theming.theme_api import qss
from . import no_gpu_window as no_gpu_mod
from ._tab_bound import TabBoundController


class _GifPreflightThread(QThread):
    """Runs the GIF estimate off the GUI thread and returns a plan."""

    decided = Signal(object)

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._config = config

    def run(self) -> None:
        try:
            decision = no_gpu_mod.plan_slow_gif(self._config)
        except Exception as exc:
            decision = no_gpu_mod.SlowGifPlan("fail", message=str(exc))
        self.decided.emit(decision)


class _PreflightDeliver(QObject):
    """Lives on the GUI thread so the plan arrives through a queued signal."""

    def __init__(self, controller: SamplerWorkerController, config: dict[str, Any], selection: bool) -> None:
        super().__init__(QCoreApplication.instance())
        self._controller = controller
        self._config = config
        self._selection = selection

    @Slot(object)
    def deliver(self, decision: object) -> None:
        try:
            self._controller._on_preflight(decision, self._config, self._selection)
        finally:
            self._controller._forget_preflight(self)
            self.deleteLater()


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

        if self._preflight_busy():
            return
        config = self._collect_config(use_selection)
        if not config["files_to_process"]:
            QMessageBox.warning(self.tab, "No Files", "No files to resample.")
            return
        self.btn_all.setEnabled(False)
        self.btn_selected.setEnabled(False)
        self.status_label.setText("Estimating…")  # pyrefly: ignore [missing-attribute]
        thread = _GifPreflightThread(config)
        deliver = _PreflightDeliver(self, config, bool(use_selection))
        thread.decided.connect(deliver.deliver, Qt.ConnectionType.QueuedConnection)
        live = getattr(self, "_gif_preflight_live", None)
        if live is None:
            live = []
            self._gif_preflight_live = live
        live.append((thread, deliver))
        thread.start()

    def _preflight_busy(self) -> bool:
        """True while an estimate thread is running or its plan is not handled yet."""
        return bool(getattr(self, "_gif_preflight_live", None))

    def _forget_preflight(self, deliver: _PreflightDeliver) -> None:
        self._gif_preflight_live = [
            pair for pair in list(getattr(self, "_gif_preflight_live", ()) or ()) if pair[1] is not deliver
        ]

    def _on_preflight(self, decision: object, config: dict[str, Any], selection: bool) -> None:
        if not isinstance(decision, no_gpu_mod.SlowGifPlan):
            self._release_after_preflight("Estimate failed")
            return
        if decision.action == "fail":
            QMessageBox.critical(self.tab, "GIF estimate failed", decision.message or "Estimate failed")
            self._release_after_preflight("Estimate failed")
            return
        if decision.action == "prompt":
            dialog = no_gpu_mod.NoGpuWindow(
                decision.estimate,
                use_multicore=bool(config.get("use_multicore")),
                source_name=decision.source_name,
                parent=self.tab,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._release_after_preflight("Cancelled")
                return
            no_gpu_mod.apply_no_gpu_choice(config, dialog.choice, decision.settings)
        self._launch_resample(config, selection)

    def _release_after_preflight(self, message: str) -> None:
        """Re-enable the buttons. Does not retire a worker."""
        self.btn_all.setEnabled(True)
        self.btn_all.setText("Resample All in Directory")
        self.btn_all.setStyleSheet(qss("shared_button"))
        if hasattr(self, "on_selection_changed"):
            self.on_selection_changed()
        else:
            self.btn_selected.setEnabled(True)
        self.btn_selected.setStyleSheet(qss("shared_button"))
        self.status_label.setText(message)  # pyrefly: ignore [missing-attribute]

    def _launch_resample(self, config: dict[str, Any], use_selection: bool) -> None:
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
