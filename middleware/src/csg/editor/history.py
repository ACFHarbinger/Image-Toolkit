"""Deterministic undo/redo for a bound ``LayerStack`` (standalone-editor
undo/redo slice; see ``docs/moon/roadmaps/engine_architecture.md``'s gate-5
exception).

Snapshot-based rather than a command/diff log: callers call :meth:`record`
right before a discrete, user-visible mutation (add/remove/reorder/
visibility-toggle, or one completed brush stroke), and this stores the
layer stack's full prior state. This is the simplest deterministic contract
that is still fully testable -- a command-object/diff-based history is a
possible later refinement if per-action snapshot memory ever proves too
costly, but every layer-stack mutation in this project remains cheap enough
(bounded canvas sizes, no infinite-undo requirement) that it is not yet
justified. Pure Python/numpy, no Qt -- ``ReferenceColoringTab`` in
``csg_gui`` owns Undo/Redo buttons and wires them to this.
"""

from __future__ import annotations

from .layer_stack import LayerStack

__all__ = ["EditHistory"]

_DEFAULT_MAX_DEPTH = 50


class EditHistory:
    """Undo/redo stack of ``LayerStack.save_state()`` snapshots."""

    def __init__(self, layer_stack: LayerStack, *, max_depth: int = _DEFAULT_MAX_DEPTH):
        if max_depth < 1:
            raise ValueError("max_depth must be at least one")
        self._layer_stack = layer_stack
        self._max_depth = max_depth
        self._undo_stack: list = []
        self._redo_stack: list = []

    def record(self) -> None:
        """Push the layer stack's current state onto the undo stack and
        clear any redo history -- call this immediately before a mutation,
        not after."""
        self._undo_stack.append(self._layer_stack.save_state())
        if len(self._undo_stack) > self._max_depth:
            del self._undo_stack[0]
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._layer_stack.save_state())
        self._layer_stack.load_state(self._undo_stack.pop())
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._layer_stack.save_state())
        self._layer_stack.load_state(self._redo_stack.pop())
        return True
