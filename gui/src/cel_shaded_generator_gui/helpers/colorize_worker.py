"""Off-main-thread runner for the cel_shaded_generator scribble colorizers (issue #186/#187/
#195).

A ``QThread`` subclass overriding ``run()`` (not ``QObject`` + ``moveToThread``)
-- the JPype-JVM-safe pattern this codebase already uses for every other
background worker (see e.g. ``gui/src/helpers/web/media_loader_worker.py``).
The solve itself (~1-4s for a full page, see
``src/colorization/colorization.py``/``screentone.py``) is pure NumPy/
SciPy/OpenCV, so it carries none of the native-Qt-subsystem crash risk that
pattern guards against -- but running it on the GUI thread would still
freeze the UI for the whole solve, so it's threaded regardless.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from colorization.colorization import colorize_scribble
from colorization.optimal_transport import colorize_reference
from colorization.screentone import colorize_scribble_screentone
from execution import IsolatedRunner, JobRequest, Operation
from PySide6.QtCore import QThread, Signal
from temporal.quadtree import colorize_region_incremental


class ColorizeWorker(QThread):
    """Runs a ``colorize_fn(gray, scribble_rgb, scribble_mask,
    max_solve_dim=...) -> np.ndarray`` off the UI thread. Defaults to
    :func:`colorization.colorization.colorize_scribble` (the Levin solver) so
    existing single-mode call sites don't need to change; pass a different
    ``colorize_fn`` (e.g. :func:`colorization.screentone.colorize_scribble_screentone`)
    to run a different colorization mode through the same worker."""

    finished_ok = Signal(np.ndarray)
    error = Signal(str)

    def __init__(
        self,
        gray: np.ndarray,
        scribble_rgb: np.ndarray,
        scribble_mask: np.ndarray,
        max_solve_dim: int = 640,
        colorize_fn: Callable[..., np.ndarray] | None = None,
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
            operation = (
                Operation.SCREENTONE_COLORIZE
                if self._colorize_fn is colorize_scribble_screentone
                else Operation.SCRIBBLE_COLORIZE
            )
            if self._colorize_fn in (colorize_scribble, colorize_scribble_screentone):
                result = IsolatedRunner().run(
                    JobRequest(
                        operation,
                        {
                            "gray": self._gray,
                            "scribble_rgb": self._scribble_rgb,
                            "scribble_mask": self._scribble_mask,
                        },
                        {"max_solve_dim": self._max_solve_dim},
                    )
                )
            else:
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
    :func:`colorization.optimal_transport.colorize_reference` (the Optimal-Transport
    solver)."""

    finished_ok = Signal(np.ndarray)
    error = Signal(str)

    def __init__(
        self,
        target_gray: np.ndarray,
        reference_rgb: np.ndarray,
        max_solve_dim: int = 400,
        colorize_fn: Callable[..., np.ndarray] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._target_gray = target_gray
        self._reference_rgb = reference_rgb
        self._max_solve_dim = max_solve_dim
        self._colorize_fn = colorize_fn or colorize_reference

    def run(self) -> None:
        try:
            if self._colorize_fn is colorize_reference:
                result = IsolatedRunner().run(
                    JobRequest(
                        Operation.REFERENCE_COLORIZE,
                        {"target_gray": self._target_gray, "reference_rgb": self._reference_rgb},
                        {"max_solve_dim": self._max_solve_dim},
                    )
                )
            else:
                result = self._colorize_fn(
                    self._target_gray, self._reference_rgb, max_solve_dim=self._max_solve_dim
                )
            self.finished_ok.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class IncrementalColorizeWorker(QThread):
    """Runs :func:`temporal.quadtree.colorize_region_incremental`
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
        dirty_bbox: tuple[int, int, int, int],
        leaves=None,
        colorize_fn: Callable[..., np.ndarray] | None = None,
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
            if self._colorize_fn in (colorize_scribble, colorize_scribble_screentone):
                mode = (
                    "screentone"
                    if self._colorize_fn is colorize_scribble_screentone
                    else "scribble"
                )
                result = IsolatedRunner().run(
                    JobRequest(
                        Operation.INCREMENTAL_COLORIZE,
                        {
                            "gray": self._gray,
                            "scribble_rgb": self._scribble_rgb,
                            "scribble_mask": self._scribble_mask,
                            "prev_result": self._prev_result,
                            "dirty_bbox": self._dirty_bbox,
                        },
                        {
                            "leaves": self._leaves,
                            "max_solve_dim": self._max_solve_dim,
                            "colorize_mode": mode,
                        },
                    )
                )
            else:
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
