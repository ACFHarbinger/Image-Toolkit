"""Dataset root browsing and identity-index build dispatch.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from backend.src.web.recon import ReconEngine
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ....helpers.web.recon_worker import IndexBuildWorker

_DIALOG_OPTS = QFileDialog.Option.DontUseNativeDialog


class _DatasetIndexingMixin:
    """Browse for the dataset root and build/track the identity index."""

    def _browse_dataset(self):
        start = self.dataset_edit.text() if os.path.isdir(self.dataset_edit.text()) else ""
        d = QFileDialog.getExistingDirectory(self, "Select Dataset Root", start, _DIALOG_OPTS)
        if d:
            self.dataset_edit.setText(d)
            self._config.dataset_root = d
            # Default the batch target to the dataset root until the user picks
            # a different destination.
            if not self.target_edit.text().strip():
                self.target_edit.setText(d)

    def _browse_target(self):
        start = self.target_edit.text() if os.path.isdir(self.target_edit.text()) else ""
        d = QFileDialog.getExistingDirectory(self, "Select Target Directory", start, _DIALOG_OPTS)
        if d:
            self.target_edit.setText(d)

    def _build_index(self):
        root_dir = self.dataset_edit.text().strip()
        if not root_dir or not os.path.isdir(root_dir):
            QMessageBox.warning(self, "Invalid Dataset", "Select a valid dataset root directory.")
            return
        self._config.dataset_root = root_dir
        self._set_busy(True)
        self._set_status("Loading embedding model...")
        self._warm_embedder()
        self._set_status("Building identity index...")
        worker = IndexBuildWorker(self._config)
        self._run_worker(worker, self._on_index_built)

    def _on_index_built(self, indexer, stats):
        self._indexer = indexer
        self._engine = ReconEngine(self._config, indexer=indexer)
        self._set_busy(False)
        self._set_status(f"Index ready: {stats.get('indexed', 0)} images, {stats.get('labels', 0)} identities.")


__all__ = ["_DatasetIndexingMixin"]
