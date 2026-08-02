"""Vector-search recommendation dialog and worker dispatch.

Extracted from ``series_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from gui.src.helpers.database.recommendation_worker import RecommendationWorker
from gui.src.database.dialog.recommendation_dialog import _RecommendationDialog
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QDialog, QMessageBox


class _RecommendationMixin:
    """Runs the recommendation worker and applies/clears its results."""

    def _on_recommend_content(self) -> None:
        if not self.vault_manager or not self.vault_manager.raw_password:
            QMessageBox.information(
                self,
                "Secure Access Required",
                "You must be logged in to get personalized recommendations.",
            )
            return

        dlg = _RecommendationDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._run_recommendation(dlg.get_inputs())

    def _run_recommendation(self, inputs: dict) -> None:
        if self._active_rec_worker and self._active_rec_worker.isRunning():
            self._active_rec_worker.terminate()

        worker = RecommendationWorker(
            entries=self._entries,
            all_entities=self._all_entities,
            inputs=inputs,
            top_k=50,
            parent=self,
        )
        worker.sig_finished.connect(self._on_recommendation_results)
        worker.error.connect(
            lambda e: QMessageBox.warning(self, "Recommendation Error", e)
        )
        worker.status.connect(lambda msg: self.stats_label.setText(f"🌟 {msg}"))
        self._active_rec_worker = worker
        self.stats_label.setText("🌟 Running recommendations…")
        worker.start()

    @Slot(list)
    def _on_recommendation_results(self, results: list) -> None:
        self._recommendation_results = results
        self.clear_rec_btn.show()
        self._rebuild_gallery()

    def _clear_recommendations(self) -> None:
        self._recommendation_results = None
        self.clear_rec_btn.hide()
        self._rebuild_gallery()


__all__ = ["_RecommendationMixin"]
