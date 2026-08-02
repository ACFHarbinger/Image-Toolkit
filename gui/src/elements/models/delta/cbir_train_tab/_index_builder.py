"""FAISS index-build background thread dispatch.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import threading

from PySide6.QtWidgets import QMessageBox

try:
    from backend.src.models.tuning.cbir_index_builder import build_cbir_index

    _INDEX_OK = True
except ImportError:
    _INDEX_OK = False
    build_cbir_index = None  # type: ignore[assignment]


class _IndexBuilderMixin:
    """Starts the background FAISS index-build thread."""

    def _start_build_index(self) -> None:
        if not _INDEX_OK or build_cbir_index is None:
            QMessageBox.critical(
                self, "Missing dependencies",
                "Could not import build_cbir_index.\n"
                "Ensure faiss-cpu and transformers are installed.",
            )
            return

        ckpt = self._ckpt_path.text().strip()
        if not ckpt:
            QMessageBox.warning(
                self, "No checkpoint",
                "Please specify a checkpoint file (cbir_best.pt) before building the index.",
            )
            return

        img_dir = self._index_img_dir.text().strip() or self._img_dir.text().strip()
        if not img_dir:
            QMessageBox.warning(self, "No image directory", "Please specify the image library directory.")
            return

        out_dir = self._index_out_dir.text().strip()
        self._btn_build_index.setEnabled(False)
        self._index_progress.setValue(0)
        self._index_progress.setVisible(True)
        self._on_log(f"Building FAISS index from: {ckpt}")
        self._on_log(f"  Image library : {img_dir}")
        self._on_log(f"  Output dir    : {out_dir}")

        def _run() -> None:
            try:
                n, index_path = build_cbir_index(
                    checkpoint_path=ckpt,
                    image_dir=img_dir,
                    output_dir=out_dir or None,
                    on_progress=lambda d, t: self.sig_index_progress.emit(d, t),
                )
                self.sig_index_done.emit(
                    "ok",
                    f"Index built successfully.\n"
                    f"{n} images indexed.\n"
                    f"FAISS index: {index_path}",
                )
            except Exception as exc:
                self.sig_index_done.emit("error", str(exc))

        self._index_thread = threading.Thread(target=_run, daemon=True)
        self._index_thread.start()


__all__ = ["_IndexBuilderMixin"]
