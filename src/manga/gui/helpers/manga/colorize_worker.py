"""Off-main-thread runner for the manga scribble colorizers (issue #186/#187/
#195).

A ``QThread`` subclass overriding ``run()`` (not ``QObject`` + ``moveToThread``)
-- the JPype-JVM-safe pattern this codebase already uses for every other
background worker (see e.g. ``gui/src/helpers/web/media_loader_worker.py``).
The solve itself (~1-4s for a full page, see
``backend/src/manga/colorization.py``/``screentone.py``) is pure NumPy/
SciPy/OpenCV, so it carries none of the native-Qt-subsystem crash risk that
pattern guards against -- but running it on the GUI thread would still
freeze the UI for the whole solve, so it's threaded regardless.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

import numpy as np
from manga import colorize_reference, colorize_scribble
from manga.quadtree import colorize_region_incremental
from PySide6.QtCore import QThread, Signal


class ColorizeWorker(QThread):
    """Runs a ``colorize_fn(gray, scribble_rgb, scribble_mask,
    max_solve_dim=...) -> np.ndarray`` off the UI thread. Defaults to
    :func:`manga.colorize_scribble` (the Levin solver) so
    existing single-mode call sites don't need to change; pass a different
    ``colorize_fn`` (e.g. :func:`manga.colorize_scribble_screentone`)
    to run a different colorization mode through the same worker."""

    finished_ok = Signal(np.ndarray)
    error = Signal(str)

    def __init__(
        self,
        gray: np.ndarray,
        scribble_rgb: np.ndarray,
        scribble_mask: np.ndarray,
        max_solve_dim: int = 640,
        colorize_fn: Optional[Callable[..., np.ndarray]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._gray = gray
        self._scribble_rgb = scribble_rgb
        self._scribble_mask = scribble_mask
        self._max_solve_dim = max_solve_dim
        self._colorize_fn = colorize_fn or colorize_scribble

    def run(self) -> None:
        try:
            result = self._colorize_fn(
                self._gray,
                self._scribble_rgb,
                self._scribble_mask,
                max_solve_dim=self._max_solve_dim,
            )
            self.finished_ok.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ReferenceColorizeWorker(QThread):
    """Runs a ``colorize_fn(target_gray, reference_rgb, max_solve_dim=...) ->
    np.ndarray`` off the UI thread -- the reference-image-based counterpart
    to :class:`ColorizeWorker` (issue #188). Kept as a separate class rather
    than generalizing ``ColorizeWorker`` to accept both signatures: the two
    workflows take a genuinely different number/shape of inputs (no
    scribble mask concept applies here), so a shared class would need an
    awkward variadic-args escape hatch for no real benefit -- the run()
    bodies are already this short. Defaults to
    :func:`manga.colorize_reference` (the Optimal-Transport
    solver)."""

    finished_ok = Signal(np.ndarray)
    error = Signal(str)

    def __init__(
        self,
        target_gray: np.ndarray,
        reference_rgb: np.ndarray,
        max_solve_dim: int = 400,
        colorize_fn: Optional[Callable[..., np.ndarray]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._target_gray = target_gray
        self._reference_rgb = reference_rgb
        self._max_solve_dim = max_solve_dim
        self._colorize_fn = colorize_fn or colorize_reference

    def run(self) -> None:
        try:
            result = self._colorize_fn(
                self._target_gray,
                self._reference_rgb,
                max_solve_dim=self._max_solve_dim,
            )
            self.finished_ok.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class IncrementalColorizeWorker(QThread):
    """Runs :func:`manga.quadtree.colorize_region_incremental`
    off the UI thread -- the "live preview" counterpart to
    :class:`ColorizeWorker` (roadmap §5.2, issue #191). Re-solves only the
    quadtree-expanded window around the latest completed stroke and
    composites it into ``prev_result``, instead of re-running a full-page
    solve on every stroke."""

    finished_ok = Signal(np.ndarray)
    error = Signal(str)

    def __init__(
        self,
        gray: np.ndarray,
        scribble_rgb: np.ndarray,
        scribble_mask: np.ndarray,
        prev_result: np.ndarray,
        dirty_bbox: Tuple[int, int, int, int],
        leaves=None,
        colorize_fn: Optional[Callable[..., np.ndarray]] = None,
        max_solve_dim: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._gray = gray
        self._scribble_rgb = scribble_rgb
        self._scribble_mask = scribble_mask
        self._prev_result = prev_result
        self._dirty_bbox = dirty_bbox
        self._leaves = leaves
        self._colorize_fn = colorize_fn or colorize_scribble
        self._max_solve_dim = max_solve_dim

    def run(self) -> None:
        try:
            result = colorize_region_incremental(
                self._gray,
                self._scribble_rgb,
                self._scribble_mask,
                self._prev_result,
                self._dirty_bbox,
                leaves=self._leaves,
                colorize_fn=self._colorize_fn,
                max_solve_dim=self._max_solve_dim,
            )
            self.finished_ok.emit(result)
        except Exception as e:
            self.error.emit(str(e))


__all__ = ["ColorizeWorker", "ReferenceColorizeWorker", "IncrementalColorizeWorker"]
