"""Off-main-thread runner for the Levin scribble colorizer (issue #186/#195).

A ``QThread`` subclass overriding ``run()`` (not ``QObject`` + ``moveToThread``)
-- the JPype-JVM-safe pattern this codebase already uses for every other
background worker (see e.g. ``gui/src/helpers/web/media_loader_worker.py``).
The solve itself (~1-4s for a full page, see
``backend/src/manga/colorization.py``) is pure NumPy/SciPy/OpenCV, so it
carries none of the native-Qt-subsystem crash risk that pattern guards
against -- but running it on the GUI thread would still freeze the UI for
the whole solve, so it's threaded regardless.
"""

from __future__ import annotations

import numpy as np
from backend.src.manga import colorize_scribble
from PySide6.QtCore import QThread, Signal


class ColorizeWorker(QThread):
    """Runs :func:`backend.src.manga.colorize_scribble` off the UI thread."""

    finished_ok = Signal(np.ndarray)
    error = Signal(str)

    def __init__(
        self,
        gray: np.ndarray,
        scribble_rgb: np.ndarray,
        scribble_mask: np.ndarray,
        max_solve_dim: int = 640,
        parent=None,
    ):
        super().__init__(parent)
        self._gray = gray
        self._scribble_rgb = scribble_rgb
        self._scribble_mask = scribble_mask
        self._max_solve_dim = max_solve_dim

    def run(self) -> None:
        try:
            result = colorize_scribble(
                self._gray,
                self._scribble_rgb,
                self._scribble_mask,
                max_solve_dim=self._max_solve_dim,
            )
            self.finished_ok.emit(result)
        except Exception as e:
            self.error.emit(str(e))


__all__ = ["ColorizeWorker"]
