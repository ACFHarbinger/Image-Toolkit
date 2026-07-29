"""Directory/checkpoint browse dialogs.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QLineEdit


class _BrowsersMixin:
    """Browse dialogs for dataset/output/index directories and checkpoints."""

    def _browse_dir(self, line_edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Select directory", line_edit.text() or ".",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            line_edit.setText(d)

    def _browse_checkpoint(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CBIR checkpoint", self._out_dir.text(),
            "PyTorch checkpoints (*.pt *.pth)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._ckpt_path.setText(path)


__all__ = ["_BrowsersMixin"]
