"""Off-main-thread runner for the manga temporal/animation solvers (issue
#196, roadmap §6.2).

A ``QThread`` subclass overriding ``run()`` -- the same JPype-JVM-safe
pattern :class:`manga.gui.helpers.manga.colorize_worker.ColorizeWorker` already
uses. Runs :func:`manga.colorize_scribble_sequence` (issue #192)
and, optionally, a follow-up :func:`manga.graph_cut_temporal_refine`
pass (issue #193) off the UI thread so a multi-frame solve (tens of seconds
for even a short sequence, per ``temporal.py``'s own docstring) doesn't
freeze the GUI.
"""

from __future__ import annotations

import numpy as np
from manga import colorize_scribble_sequence, graph_cut_temporal_refine
from PySide6.QtCore import QThread, Signal


class AnimationColorizeWorker(QThread):
    """Runs ``colorize_scribble_sequence(gray_stack, scribble_rgb_stack,
    scribble_mask_stack, ...)`` off the UI thread, then optionally
    ``graph_cut_temporal_refine(gray_stack, result, ...)`` as a second pass
    over the same result when ``refine`` is True."""

    finished_ok = Signal(np.ndarray)
    error = Signal(str)

    def __init__(
        self,
        gray_stack: np.ndarray,
        scribble_rgb_stack: np.ndarray,
        scribble_mask_stack: np.ndarray,
        win_rad: int = 1,
        t_rad: int = 1,
        max_solve_dim: int = 128,
        refine: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._gray_stack = gray_stack
        self._scribble_rgb_stack = scribble_rgb_stack
        self._scribble_mask_stack = scribble_mask_stack
        self._win_rad = win_rad
        self._t_rad = t_rad
        self._max_solve_dim = max_solve_dim
        self._refine = refine

    def run(self) -> None:
        try:
            result = colorize_scribble_sequence(
                self._gray_stack,
                self._scribble_rgb_stack,
                self._scribble_mask_stack,
                win_rad=self._win_rad,
                t_rad=self._t_rad,
                max_solve_dim=self._max_solve_dim,
            )
            if self._refine:
                result = graph_cut_temporal_refine(self._gray_stack, result)
            self.finished_ok.emit(result)
        except Exception as e:
            self.error.emit(str(e))


__all__ = ["AnimationColorizeWorker"]
