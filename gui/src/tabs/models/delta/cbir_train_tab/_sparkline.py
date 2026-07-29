"""``_SparkLine`` -- rolling unicode sparkline widget for the loss chart.

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class _SparkLine(QLabel):
    """Rolling unicode sparkline showing up to MAX_POINTS scalar values."""

    MAX_POINTS = 64
    _BLOCKS = " ▁▂▃▄▅▆▇█"

    def __init__(self, label: str = "loss") -> None:
        super().__init__()
        self._label = label
        self._values: list = []
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(20)
        self.setStyleSheet("font-family: monospace; font-size: 11px;")

    def push(self, v: float) -> None:
        self._values.append(v)
        if len(self._values) > self.MAX_POINTS:
            self._values.pop(0)
        self._redraw()

    def reset(self) -> None:
        self._values.clear()
        self.setText("")

    def _redraw(self) -> None:
        if not self._values:
            return
        lo, hi = min(self._values), max(self._values)
        span = hi - lo or 1e-9
        bar = "".join(
            self._BLOCKS[min(8, int(((v - lo) / span) * 8))] for v in self._values
        )
        self.setText(f"{self._label}  {bar}  {self._values[-1]:.4f}")


__all__ = ["_SparkLine"]
