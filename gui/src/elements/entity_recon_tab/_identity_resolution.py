"""Identity resolution dispatch, result rendering, and provenance-item activation.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

from backend.src.web.recon.config import SCOPE_BOTH, SCOPE_LOCAL
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QTreeWidgetItem

from ...helpers.web.recon_worker import ResolveWorker

logger = logging.getLogger(__name__)


class _IdentityResolutionMixin:
    """Resolves the current subject and renders the result/provenance tree."""

    def _resolve(self):
        if self._source_rgb is None:
            self._set_status("Load an image first.")
            return
        if self._engine is None:
            QMessageBox.information(self, "No Index", "Build the identity index first.")
            return
        from backend.src.web.recon import segmenter

        if self._cur_alpha is not None:
            cutout = segmenter.alpha_cutout(self._source_rgb, self._cur_alpha)
        else:
            # whole-frame fallback: opaque alpha
            import numpy as np

            full = np.full(self._source_rgb.shape[:2], 255, dtype=np.uint8)
            cutout = segmenter.alpha_cutout(self._source_rgb, full)
        cutout_rgb = cutout[:, :, :3]
        png = segmenter.cutout_to_png_bytes(cutout)

        self._set_busy(True)
        # Local/both scopes embed the cutout; warm the model on the main thread
        # first (web-only skips embedding, so no need to load torch).
        if getattr(self._config, "search_scope", SCOPE_LOCAL) in (SCOPE_LOCAL, SCOPE_BOTH):
            self._set_status("Loading embedding model...")
            self._warm_embedder()
        self._set_status("Resolving identity...")
        worker = ResolveWorker(self._engine, cutout_rgb, png)
        self._run_worker(worker, self._on_resolved)

    def _on_resolved(self, res):
        self._set_busy(False)
        self._report = res.report
        self.name_label.setText(res.name or "Unknown")
        self.conf_bar.setValue(int(round(res.confidence * 100)))
        self.method_label.setText(f"Method: {res.method or '—'}")
        self.origin_label.setText(f"Origin: {res.origin or 'none'}")

        self.prov_tree.clear()
        if res.origin == "local":
            for m in res.local_matches:
                item = QTreeWidgetItem([m["label"].replace("_", " "), f"{m['score'] * 100:.0f}%"])
                item.setData(0, Qt.ItemDataRole.UserRole, ("local", m["path"]))
                child = QTreeWidgetItem([m["path"], ""])
                child.setData(0, Qt.ItemDataRole.UserRole, ("local", m["path"]))
                item.addChild(child)
                self.prov_tree.addTopLevelItem(item)
        else:
            for d in res.web_domains:
                parent = QTreeWidgetItem([f"{d['domain']} ({d['count']})", ""])
                for url in d.get("urls", []):
                    child = QTreeWidgetItem([url, ""])
                    child.setData(0, Qt.ItemDataRole.UserRole, ("web", url))
                    parent.addChild(child)
                self.prov_tree.addTopLevelItem(parent)
        self.prov_tree.expandAll()
        self._set_status(f"Identity: {res.name or 'Unknown'} ({res.confidence * 100:.0f}%) via {res.method or '—'}")

    def _on_prov_activated(self, item: QTreeWidgetItem, _col: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, target = data
        if kind == "web":
            QDesktopServices.openUrl(QUrl(target))
        else:
            self._open_in_file_manager(target)

    def _open_in_file_manager(self, path: str):
        if not path:
            return
        directory = path if os.path.isdir(path) else os.path.dirname(path)
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", directory])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", directory])
            elif sys.platform.startswith("win"):
                os.startfile(directory)  # noqa: S606
        except Exception as e:  # noqa: BLE001
            logger.warning("open_in_file_manager failed: %s", e)


__all__ = ["_IdentityResolutionMixin"]
