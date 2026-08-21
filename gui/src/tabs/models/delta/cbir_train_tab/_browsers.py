"""Directory/checkpoint browse dialogs.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtWidgets import QFileDialog, QLineEdit, QWidget

if TYPE_CHECKING:
    from ...protos.cbir_train_tab import CBIRTrainTabHostProtocol


class _BrowsersMixin:
    """Browse dialogs for dataset/output/index directories and checkpoints."""

    def _browse_dir(self: "CBIRTrainTabHostProtocol", line_edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(
            cast(QWidget, self), "Select directory", line_edit.text() or ".",
            QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            line_edit.setText(d)

    def _browse_checkpoint(self: "CBIRTrainTabHostProtocol") -> None:
        path, _ = QFileDialog.getOpenFileName(
            cast(QWidget, self), "Select CBIR checkpoint", self._out_dir.text(),
            "PyTorch checkpoints (*.pt *.pth)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._ckpt_path.setText(path)


__all__ = ["_BrowsersMixin"]
