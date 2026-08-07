"""Layer-list panel for the standalone editor's layer-stack foundation (see
``docs/moon/roadmaps/engine_architecture.md``'s gate-5 exception).

Owns the only structural mutations a ``LayerStack`` gets: add, remove,
reorder, visibility toggle, and mask add/remove. Emits ``layers_changed``
after every mutation so a bound canvas (``layer_canvas.py``) knows to
re-render, and ``layer_selected`` whenever the current selection changes so
a canvas can paint onto the right layer -- never touches the canvas
directly, keeping this panel reusable without one. If bound with
``set_history``, records an undo checkpoint immediately before each
structural mutation. A layer with a mask shows a "(mask)" suffix in the
list so its state is visible without selecting it.

New feature, not code motion.
"""

from __future__ import annotations

import uuid

from editor import EditHistory, LayerStack
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LayerListPanel(QWidget):
    """Add/remove/reorder/toggle-visibility controls over a bound ``LayerStack``."""

    layers_changed = Signal()
    layer_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layer_stack: LayerStack | None = None
        self._history: EditHistory | None = None

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._add_button = QPushButton("Add Layer", self)
        self._remove_button = QPushButton("Remove Layer", self)
        self._up_button = QPushButton("Move Up", self)
        self._down_button = QPushButton("Move Down", self)
        self._add_mask_button = QPushButton("Add Mask", self)
        self._remove_mask_button = QPushButton("Remove Mask", self)

        self._add_button.clicked.connect(self._add_layer)
        self._remove_button.clicked.connect(self._remove_selected_layer)
        self._up_button.clicked.connect(lambda: self._move_selected_layer(-1))
        self._down_button.clicked.connect(lambda: self._move_selected_layer(1))
        self._add_mask_button.clicked.connect(self._add_mask_to_selected_layer)
        self._remove_mask_button.clicked.connect(self._remove_mask_from_selected_layer)
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.currentItemChanged.connect(self._on_current_item_changed)

        buttons = QHBoxLayout()
        for button in (self._add_button, self._remove_button, self._up_button, self._down_button):
            buttons.addWidget(button)
        mask_buttons = QHBoxLayout()
        for button in (self._add_mask_button, self._remove_mask_button):
            mask_buttons.addWidget(button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addLayout(buttons)
        layout.addLayout(mask_buttons)

    def set_layer_stack(self, layer_stack: LayerStack | None) -> None:
        self._layer_stack = layer_stack
        self._refresh_list()

    def layer_stack(self) -> LayerStack | None:
        return self._layer_stack

    def set_history(self, history: EditHistory | None) -> None:
        self._history = history

    def refresh(self) -> None:
        """Re-sync the list from the bound ``LayerStack``'s current state
        (e.g. after an external mutation such as an undo/redo)."""
        self._refresh_list()

    def selected_layer_id(self) -> str | None:
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def select_layer(self, layer_id: str) -> None:
        """Select ``layer_id`` in the list, emitting ``layer_selected``."""
        self._select_layer(layer_id)

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if self._layer_stack is not None:
            # Top layer first in the list, matching every layer-based editor's
            # stacking convention (the list reads top-to-bottom like the canvas).
            for layer in reversed(self._layer_stack.layers()):
                label = layer.meta.name + (" (mask)" if layer.mask is not None else "")
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, layer.meta.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if layer.meta.visible else Qt.CheckState.Unchecked
                )
                self._list.addItem(item)
        self._list.blockSignals(False)

    def _add_layer(self) -> None:
        if self._layer_stack is None:
            return
        if self._history is not None:
            self._history.record()
        layer_id = "layer-" + uuid.uuid4().hex[:8]
        count = len(self._layer_stack.layers())
        self._layer_stack.add_layer(layer_id, f"Layer {count + 1}")
        self._refresh_list()
        self._select_layer(layer_id)
        self.layers_changed.emit()

    def _remove_selected_layer(self) -> None:
        layer_id = self.selected_layer_id()
        if self._layer_stack is None or layer_id is None:
            return
        if self._history is not None:
            self._history.record()
        if self._layer_stack.remove_layer(layer_id):
            self._refresh_list()
            self.layers_changed.emit()

    def _move_selected_layer(self, direction: int) -> None:
        """``direction`` is -1 (up the list / toward the top of the stack) or
        +1 (down the list / toward the bottom)."""
        layer_id = self.selected_layer_id()
        if self._layer_stack is None or layer_id is None:
            return
        stack_ids = [layer.meta.id for layer in self._layer_stack.layers()]
        current_index = stack_ids.index(layer_id)
        # The list is top-to-bottom but the stack is bottom-to-top, so moving
        # "up" in the list means a higher index in the stack.
        new_index = current_index - direction
        if not 0 <= new_index < len(stack_ids):
            return
        if self._history is not None:
            self._history.record()
        self._layer_stack.reorder_layer(layer_id, new_index)
        self._refresh_list()
        self._select_layer(layer_id)
        self.layers_changed.emit()

    def _add_mask_to_selected_layer(self) -> None:
        layer_id = self.selected_layer_id()
        if self._layer_stack is None or layer_id is None:
            return
        if self._history is not None:
            self._history.record()
        if self._layer_stack.add_mask(layer_id):
            self._refresh_list()
            self._select_layer(layer_id)
            self.layers_changed.emit()

    def _remove_mask_from_selected_layer(self) -> None:
        layer_id = self.selected_layer_id()
        if self._layer_stack is None or layer_id is None:
            return
        if self._history is not None:
            self._history.record()
        if self._layer_stack.remove_mask(layer_id):
            self._refresh_list()
            self._select_layer(layer_id)
            self.layers_changed.emit()

    def _select_layer(self, layer_id: str) -> None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == layer_id:
                self._list.setCurrentItem(item)
                return

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._layer_stack is None:
            return
        layer_id = item.data(Qt.ItemDataRole.UserRole)
        visible = item.checkState() == Qt.CheckState.Checked
        if self._history is not None:
            self._history.record()
        if self._layer_stack.set_visibility(layer_id, visible):
            self.layers_changed.emit()

    def _on_current_item_changed(self, current, _previous) -> None:
        self.layer_selected.emit(
            current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        )


__all__ = ["LayerListPanel"]
