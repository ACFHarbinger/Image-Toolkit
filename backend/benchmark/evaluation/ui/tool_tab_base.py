"""Shared base for "a row of buttons that (re)compute and display one
visual artifact" — both the Visualizations tab and the Comparison Tools tab
are this same pattern (pick a function, run it against the current test's
images, show the result), so the button row / result-area plumbing lives
here once instead of being duplicated per tab.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .mpl_canvas import PlotCanvas
from .panel_base import bgr_to_qimage


class ToolTabBase(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._asp: Optional[np.ndarray] = None
        self._simple: Optional[np.ndarray] = None
        self._gt: Optional[np.ndarray] = None

        self._outer = QVBoxLayout(self)
        self._button_grid = QGridLayout()
        self._outer.addLayout(self._button_grid)
        self._result_holder = QVBoxLayout()
        self._outer.addLayout(self._result_holder, stretch=1)
        self._current_widget: Optional[QWidget] = None
        self._button_col_count = 4
        self._next_button_index = 0

    def set_images(self, asp: Optional[np.ndarray], simple: Optional[np.ndarray], gt: Optional[np.ndarray]) -> None:
        self._asp, self._simple, self._gt = asp, simple, gt

    def _add_button(self, text: str, handler: Callable[[], None]) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(handler)
        row, col = divmod(self._next_button_index, self._button_col_count)
        self._button_grid.addWidget(btn, row, col)
        self._next_button_index += 1
        return btn

    def _clear_result(self) -> None:
        if self._current_widget is not None:
            self._result_holder.removeWidget(self._current_widget)
            self._current_widget.setParent(None)
            self._current_widget = None

    def _show_figure(self, fig: Figure) -> None:
        self._clear_result()
        canvas = PlotCanvas(fig)
        self._result_holder.addWidget(canvas)
        self._current_widget = canvas

    def _show_image(self, img_bgr: np.ndarray) -> None:
        self._clear_result()
        label = QLabel()
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pix = QPixmap.fromImage(bgr_to_qimage(img_bgr))
        label.setPixmap(pix.scaled(900, 700, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self._result_holder.addWidget(label)
        self._current_widget = label

    def _show_widget(self, widget: QWidget) -> None:
        self._clear_result()
        self._result_holder.addWidget(widget)
        self._current_widget = widget

    def _show_text(self, text: str) -> None:
        self._clear_result()
        label = QLabel(text)
        label.setStyleSheet("font-family: monospace; color: #ddd; background: #111; padding: 6px;")
        label.setWordWrap(False)
        self._result_holder.addWidget(label)
        self._current_widget = label
