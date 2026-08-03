"""Source-image browsing, loading, and click-to-segment handling.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFileDialog

from ....constants import DIALOG_OPTS, RECON_IMAGE_FILTER

logger = logging.getLogger(__name__)


class _SourceImageMixin:
    """Loads the source image and dispatches click-to-segment requests."""

    def _browse_source(self):
        start = os.path.dirname(self._source_path) if self._source_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Select Source Image", start, RECON_IMAGE_FILTER, options=DIALOG_OPTS)
        if path:
            self._load_source(path)

    def _load_source(self, path: str):
        import cv2

        if not path or not os.path.isfile(path):
            return
        img = cv2.imread(path)
        if img is None:
            self._set_status("Could not read image.")
            return
        self._source_path = path
        self._source_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._cur_alpha = None
        self._cur_bbox = None
        h, w = self._source_rgb.shape[:2]
        pix = QPixmap.fromImage(QImage(self._source_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())
        self.image_label.set_source_pixmap(pix, w, h)
        self._set_status(f"Loaded {os.path.basename(path)}. Click a subject to segment.")

    def _on_image_clicked(self, x: int, y: int):
        if self._source_rgb is None:
            return
        from backend.src.web.recon import segmenter

        try:
            alpha, bbox = segmenter.segment_at_point(self._source_rgb, x, y)
        except Exception as e:  # noqa: BLE001 - segmentation is best-effort
            logger.warning("Segmentation failed: %s", e)
            self._set_status(f"Segmentation failed: {e}")
            return
        self._cur_alpha = alpha
        self._cur_bbox = bbox
        self._show_overlay(alpha)
        self._set_status("Subject selected. Press 'Resolve Identity'.")

    def _show_overlay(self, alpha):
        import numpy as np

        overlay = self._source_rgb.copy()  # pyrefly: ignore [missing-attribute]
        mask = alpha > 0
        tint = np.zeros_like(overlay)
        tint[mask] = (88, 101, 242)
        overlay[mask] = (0.55 * overlay[mask] + 0.45 * tint[mask]).astype(np.uint8)
        h, w = overlay.shape[:2]
        pix = QPixmap.fromImage(QImage(overlay.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())
        self.image_label.set_source_pixmap(pix, w, h)


__all__ = ["_SourceImageMixin"]
