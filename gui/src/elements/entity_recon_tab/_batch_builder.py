"""Batch dataset builder: suggest identities for many images, then move them.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from ...helpers.web.recon_worker import BatchSuggestWorker

logger = logging.getLogger(__name__)

_DIALOG_OPTS = QFileDialog.Option.DontUseNativeDialog
_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp)"


class _BatchBuilderMixin:
    """Suggests identities for a batch of images and moves approved ones."""

    def _browse_batch(self):
        if self._engine is None:
            QMessageBox.information(self, "No Index", "Build the identity index first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", _IMAGE_FILTER, options=_DIALOG_OPTS)
        paths = [p for p in paths if os.path.isfile(p)]
        if not paths:
            return
        self._set_busy(True)
        self._set_status("Loading embedding model...")
        self._warm_embedder()
        self._set_status(f"Analyzing {len(paths)} images...")
        worker = BatchSuggestWorker(self._engine, paths)
        self._run_worker(worker, self._on_batch)

    def _on_batch(self, suggestions):
        self._set_busy(False)
        self._batch_rows = suggestions
        self.batch_table.setRowCount(len(suggestions))
        for row, s in enumerate(suggestions):
            self.batch_table.setItem(row, 0, QTableWidgetItem(os.path.basename(s.get("path", ""))))
            self.batch_table.setItem(row, 1, QTableWidgetItem((s.get("suggested_label") or "—").replace("_", " ")))
            self.batch_table.setItem(row, 2, QTableWidgetItem(f"{s.get('score', 0.0) * 100:.0f}%"))
        matched = sum(1 for s in suggestions if s.get("suggested_label"))
        self.btn_approve.setEnabled(matched > 0)
        self._set_status(f"{matched}/{len(suggestions)} images matched an identity.")

    def _approve_batch(self):
        import shutil

        # A user-specified target root overrides the per-row default (which puts
        # identity folders next to each source image).
        target_root = self.target_edit.text().strip()
        moved = 0
        for row in self._batch_rows:
            path = row.get("path")
            label = row.get("suggested_label")
            target = os.path.join(target_root, label) if target_root and label else row.get("target_dir")
            if not target or not path or not os.path.isfile(path):
                continue
            try:
                os.makedirs(target, exist_ok=True)
                dest = os.path.join(target, os.path.basename(path))
                if os.path.abspath(dest) != os.path.abspath(path):
                    shutil.move(path, dest)
                    moved += 1
            except OSError as e:
                logger.warning("Batch move failed for %s: %s", path, e)
        self._batch_rows = []
        self.batch_table.setRowCount(0)
        self.btn_approve.setEnabled(False)
        self._set_status(f"Moved {moved} images into identity folders.")


__all__ = ["_BatchBuilderMixin"]
