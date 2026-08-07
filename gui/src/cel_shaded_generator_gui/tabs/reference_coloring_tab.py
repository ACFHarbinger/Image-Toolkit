"""Standalone Reference Coloring editor tab -- canvas + layer stack
foundation (roadmap: standalone editor, gate-5 exception; see
``docs/moon/roadmaps/engine_architecture.md``).

First slice only: create a blank canvas of a chosen size and add/remove/
reorder/show-hide layers, seeing the composite update live. No paint tools,
masks, segmentation, or palette preview yet -- those are later slices built
on top of this same ``editor.LayerStack``/``LayerCanvas``/``LayerListPanel``
foundation, mirroring how the Krita Dockers built on Krita's own layer model.

New feature, not code motion.
"""

from __future__ import annotations

from editor import LayerStack
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..elements.layer_canvas import LayerCanvas
from ..elements.layer_list_panel import LayerListPanel

_DEFAULT_WIDTH = 1200
_DEFAULT_HEIGHT = 1600


class ReferenceColoringTab(QWidget):
    """Standalone canvas + layer stack editor foundation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = QLabel("No canvas yet. Click New Canvas to begin.", self)
        self._status.setWordWrap(True)
        self._new_canvas_button = QPushButton("New Canvas", self)
        self._new_canvas_button.clicked.connect(self._new_canvas)

        self._canvas = LayerCanvas(self)
        self._layer_panel = LayerListPanel(self)
        self._layer_panel.layers_changed.connect(self._canvas.refresh)
        self._layer_panel.layers_changed.connect(self._update_status)

        controls = QHBoxLayout()
        controls.addWidget(self._new_canvas_button)
        controls.addStretch(1)

        right = QVBoxLayout()
        right.addLayout(controls)
        right.addWidget(self._layer_panel)
        right.addWidget(self._status)

        root = QHBoxLayout(self)
        root.addWidget(self._canvas, stretch=3)
        right_container = QWidget(self)
        right_container.setLayout(right)
        root.addWidget(right_container, stretch=1)

    def _new_canvas(self) -> None:
        width, accepted = QInputDialog.getInt(
            self, "New Canvas", "Width (px):", _DEFAULT_WIDTH, 1, 16384
        )
        if not accepted:
            return
        height, accepted = QInputDialog.getInt(
            self, "New Canvas", "Height (px):", _DEFAULT_HEIGHT, 1, 16384
        )
        if not accepted:
            return
        layer_stack = LayerStack(width, height)
        layer_stack.add_layer("layer-1", "Layer 1")
        self._canvas.set_layer_stack(layer_stack)
        self._layer_panel.set_layer_stack(layer_stack)
        self._update_status()

    def _update_status(self) -> None:
        layer_stack = self._canvas.layer_stack()
        if layer_stack is None:
            self._status.setText("No canvas yet. Click New Canvas to begin.")
            return
        self._status.setText(
            f"Canvas {layer_stack.width}x{layer_stack.height}, "
            f"{len(layer_stack.layers())} layer(s)."
        )

    def canvas(self) -> LayerCanvas:
        return self._canvas

    def layer_panel(self) -> LayerListPanel:
        return self._layer_panel


__all__ = ["ReferenceColoringTab"]
