"""Tiered-similarity-engine scan dispatch, lifecycle, and cluster application.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import List

from backend.src.core.similarity import SimilarityEngine, SimilarityReport, auto_select
from gui.src.helpers.core.similarity_scan_worker import SimilarityScanWorker
from PySide6.QtCore import Qt, Slot

from ....utils.sort_utils import natural_sort_key


class _SimilarityScanMixin:
    """Start/cancel the tiered similarity scan worker and apply its clusters."""

    @Slot(str)
    def start_similarity_scan_qml(self, target_dir: str):
        if self._scan_running:
            return
        if not target_dir or not os.path.isdir(target_dir):
            self.scan_status_changed.emit("Invalid target directory.")
            return
        self._sim_config.target_dir = target_dir
        if self.dropdown and self.selected_extensions:
            self._sim_config.extensions = list(self.selected_extensions)
        self.target_path.setText(target_dir)
        self._set_running(True)
        self.scan_progress_bar.show()
        self.status_label.setText("Starting similarity scan...")
        self.scan_status_changed.emit("Starting similarity scan...")

        # SimilarityScanWorker is a QThread subclass (overrides run(), no event
        # loop) — the plain-QThread + moveToThread pattern spins a glib event
        # dispatcher in the worker thread which SIGSEGVs under the live JVM.
        self._sim_worker = SimilarityScanWorker(self._sim_config)
        self._sim_worker.status.connect(self._on_sim_status)
        self._sim_worker.progress.connect(self.scan_progress)
        self._sim_worker.sig_finished.connect(self._on_sim_scan_finished)
        self._sim_worker.error.connect(self._on_sim_scan_error)
        self._sim_worker.cancelled.connect(self._on_sim_scan_cancelled)
        self._sim_worker.start()

    @Slot(str, str)
    def start_duplicate_scan_qml(self, target_dir, method="Exact Match"):
        """Back-compat wrapper: map the old method string to tiers and scan."""
        if not target_dir or not os.path.isdir(target_dir):
            return
        idx = self.scan_method_combo.findText(method, Qt.MatchFlag.MatchContains)
        if idx >= 0:
            self.scan_method_combo.setCurrentIndex(idx)
        self.target_path.setText(target_dir)
        self.start_duplicate_scan()

    @Slot()
    def cancel_similarity_scan(self):
        if self._sim_worker and self._sim_worker.isRunning():
            self._sim_worker.requestInterruption()
            self.scan_status_changed.emit("Cancelling scan...")

    def _set_running(self, running: bool):
        if self._scan_running != running:
            self._scan_running = running
            self.scan_running_changed.emit(running)
        if hasattr(self, "btn_scan"):
            # The scan button doubles as the cancel button while a scan runs.
            self.btn_scan.setText(self._cancel_label if running else self._scan_label)
            self.btn_reset.setEnabled(not running)
        if not running:
            self.scan_progress_bar.hide()

    @Slot(str)
    def _on_sim_status(self, message: str):
        self.status_label.setText(message)
        self.scan_status_changed.emit(message)

    def _finalize_scan(self):
        """Common teardown for every terminal outcome (done/error/cancelled).
        The worker (a QThread) lives in the main thread's affinity, so it is safe
        to wait() and deleteLater() it from here."""
        worker = self._sim_worker
        self._sim_worker = None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self._set_running(False)

    @Slot(object)
    def _on_sim_scan_finished(self, report: SimilarityReport):
        self._report = report
        self._ref_set = set()
        if self._sim_config.reference_dir:
            ref = os.path.abspath(self._sim_config.reference_dir)
            self._ref_set = {
                p for p in report.files
                if os.path.commonpath([ref, os.path.abspath(p)]) == ref
            }
        self._apply_clusters(report.clusters)
        n_files = sum(c["size"] for c in report.clusters)
        msg = (f"Scan complete: {len(report.clusters)} clusters, {n_files} files "
               f"({report.stats.get('cache_hits', 0)} cache hits).")
        self.status_label.setText(msg)
        self.scan_status_changed.emit(msg)
        self.duplicate_results = {c["id"]: c["paths"] for c in report.clusters}
        flattened = [p for c in report.clusters for p in c["paths"]]
        self._finalize_scan()
        if flattened:
            self.start_loading_thumbnails(sorted(flattened, key=natural_sort_key))

    @Slot(str)
    def _on_sim_scan_error(self, message: str):
        self._finalize_scan()
        self.status_label.setText(f"Scan failed: {message}")
        self.scan_status_changed.emit(f"Scan failed: {message}")

    @Slot()
    def _on_sim_scan_cancelled(self):
        self._finalize_scan()
        self.status_label.setText("Scan cancelled.")
        self.scan_status_changed.emit("Scan cancelled.")

    def _apply_clusters(self, clusters: List[dict]):
        protected = self._ref_set
        for c in clusters:
            keeper, _ = auto_select(c["paths"], self._triage_rules, protected)
            c["keeper"] = keeper or ""
        self._cluster_model.set_clusters(clusters)
        self.clusters_changed.emit()

    @Slot(float)
    def set_confidence_threshold(self, value: float):
        value = max(0.0, min(1.0, float(value)))
        if abs(value - self._sim_config.confidence_threshold) < 1e-9:
            return
        self._sim_config.confidence_threshold = value
        self.confidence_threshold_changed.emit(value)
        if self._report is not None:
            clusters = SimilarityEngine.regroup(self._report, value, self._ref_set)
            self._apply_clusters(clusters)


__all__ = ["_SimilarityScanMixin"]
