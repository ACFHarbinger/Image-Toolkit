"""
gui/src/helpers/base.py
=======================
Abstract base classes for all GUI worker threads.

Classes
-------
BaseQThreadWorker
    Base for heavy ``QThread`` workers (``ConversionWorker``,
    ``DeletionWorker``, ``StitchWorker``, …).  Provides:
      - ``finished``, ``error``, ``progress`` signals.
      - ``cancel()`` / ``stop()`` — sets ``self._cancelled = True``.
      - ``run()`` — wraps ``_execute()`` in a try/except so unhandled
        exceptions always route to ``error`` rather than crashing silently.
    Subclasses implement ``_execute()``; complex workers that need more
    control may override ``run()`` directly.

_WorkerSignals
    Shared signal carrier for ``QRunnable``-based workers.  ``QRunnable``
    does not inherit ``QObject``, so signals live in a separate QObject.

BaseQRunnableWorker
    Base for short ``QRunnable`` tasks (``SearchWorker``, image-loader
    tasks, …).  Provides the same ``_execute()`` / ``cancel()`` contract
    as ``BaseQThreadWorker``, accessed via ``self.signals``.

Usage
-----
``QThread`` subclass::

    class MyWorker(BaseQThreadWorker):
        finished = Signal(str)   # narrow type

        def __init__(self, path: str) -> None:
            super().__init__()
            self._path = path

        def _execute(self) -> None:
            result = do_work(self._path)
            self.finished.emit(result)

``QRunnable`` subclass::

    class MyTask(BaseQRunnableWorker):
        def __init__(self, path: str) -> None:
            super().__init__()
            self._path = path

        def _execute(self) -> None:
            result = do_work(self._path)
            self.signals.finished.emit(result)
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QRunnable, QThread, Signal, Slot

if TYPE_CHECKING:
    from backend.src.exceptions import ImageToolkitError

logger = logging.getLogger(__name__)


class BaseQThreadWorker(QThread):
    """
    Abstract base for ``QThread`` workers.

    Signals
    -------
    finished : Signal(object)
        Emitted when ``_execute()`` completes.  Subclasses typically
        re-declare this with a narrower type.
    error : Signal(str)
        Emitted when an unhandled exception escapes ``_execute()``.
    progress : Signal(int)
        Emitted with 0–100 completion percentage.
    """

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the worker to stop at the next cancellation checkpoint."""
        self._cancelled = True

    # alias — callers that use stop() continue to work
    stop = cancel

    @abstractmethod
    def _execute(self) -> None:
        """Worker logic.  Override this instead of ``run()``."""

    def run(self) -> None:
        try:
            self._execute()
        except Exception as exc:
            self._handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> None:
        """Three-tier error handler.

        Tier 1 — ``AlignmentFailedError`` / ``CanvasError``: recoverable pipeline
            failures; logged at WARNING (expected on tricky inputs).
        Tier 2 — any other ``PipelineError`` / ``ModelLoadError`` / ``ConfigError``:
            application-domain errors; logged at ERROR.
        Tier 3 — unexpected ``Exception``: logged at ERROR with full traceback.
        """
        try:
            from backend.src.exceptions import (
                AlignmentFailedError,
                CanvasError,
                PipelineError,
                ModelLoadError,
                ConfigError,
            )
            if isinstance(exc, (AlignmentFailedError, CanvasError)):
                logger.warning("%s: %s", type(exc).__name__, exc)
            elif isinstance(exc, (PipelineError, ModelLoadError, ConfigError)):
                logger.error("%s: %s", type(exc).__name__, exc)
            else:
                logger.error("Unhandled exception in worker", exc_info=exc)
        except ImportError:
            logger.error("Unhandled exception in worker", exc_info=exc)
        self.error.emit(str(exc))


class _WorkerSignals(QObject):
    """
    Signal carrier for ``QRunnable`` workers.

    ``QRunnable`` does not inherit ``QObject`` so signals must live in a
    separate ``QObject`` instance stored as ``worker.signals``.
    """

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int)
    cancelled = Signal()


class BaseQRunnableWorker(QRunnable):
    """
    Abstract base for short ``QRunnable`` tasks.

    Access signals via ``self.signals`` (a ``_WorkerSignals`` instance).

    Lifecycle
    ---------
    1. ``run()`` checks ``self._cancelled`` before calling ``_execute()``.
    2. ``_execute()`` contains the task logic; unhandled exceptions are
       routed to ``self.signals.error``.
    3. ``cancel()`` sets ``self._cancelled = True``; ``_execute()`` can
       poll this flag for cooperative early exit.
    """

    def __init__(self) -> None:
        super().__init__()
        self.signals = _WorkerSignals()
        self._cancelled = False
        self.setAutoDelete(True)

    def cancel(self) -> None:
        """Signal the task to stop before its next cancellation checkpoint."""
        self._cancelled = True

    @abstractmethod
    def _execute(self) -> None:
        """Task logic.  Override this instead of ``run()``."""

    @Slot()
    def run(self) -> None:
        if self._cancelled:
            self.signals.cancelled.emit()
            return
        try:
            self._execute()
        except Exception as exc:
            self.signals.error.emit(str(exc))
