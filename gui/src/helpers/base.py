"""
gui/src/helpers/base.py
=======================
Abstract base classes for all GUI worker threads.

Classes
-------
BaseQThreadWorker
    Base for heavy ``QThread`` workers (``ConversionWorker``,
    ``DeletionWorker``, ``StitchWorker``, …).  Provides:
      - ``finished``, ``error(object)``, ``progress`` signals (rule 3, R1.1).
      - ``cancel()`` / ``stop()`` — sets ``self._cancelled = True``.
      - ``run()`` — wraps ``_execute()`` in a try/except so unhandled
        exceptions always route to ``error`` rather than crashing silently,
        with the cyclic GC disabled for the whole run (the #478 crash
        class — see ``gc_safe.py``).
    Subclasses implement ``_execute()``; complex workers that need more
    control may override ``run()`` directly — if they allocate heavily
    (JSON / listings), the override should carry ``@gc_disabled_run``.

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

from .gc_safe import gc_disabled_run

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BaseQThreadWorker(QThread):
    """
    Abstract base for ``QThread`` workers.

    Signals
    -------
    finished : Signal(object)
        Emitted once at thread end with the ``_execute()`` return value
        (``None`` when there is no payload, or when ``_execute()`` raised
        and ``error`` fired instead). Payload slots must tolerate ``None``.
        Subclasses typically re-declare this with a narrower type.
    error : Signal(object)
        Emitted with the exception object when an unhandled exception
        escapes ``_execute()`` (Q-C, R1.1). Connecting slots call
        ``str(exc)`` themselves.
    progress : Signal(int, int)
        Emitted as ``(completed, total)`` (see §5.9 Option C,
        ``docs/moon/roadmaps/architecture.md``). Connecting slots should call
        ``progress_bar.setMaximum(total)`` then ``.setValue(completed)``.
    """

    finished = Signal(object)
    error = Signal(object)
    progress = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._cancelled = False

    def cancel(self) -> None:
        """Signal the worker to stop at the next cancellation checkpoint."""
        self._cancelled = True

    # alias — callers that use stop() continue to work
    stop = cancel

    @abstractmethod
    def _execute(self) -> object:
        """Worker logic. Override this instead of ``run()``.

        The return value is delivered to ``finished`` subscribers. Return
        ``None`` when there is no result payload.
        """

    @gc_disabled_run
    def run(self) -> None:
        # ``finished`` fires at thread end like the native QThread signal it
        # replaces (same timing: teardown/cleanup slots keep working), with
        # the ``_execute()`` return value as payload — ``None`` on failure,
        # so payload slots must tolerate ``None``. Failures additionally
        # emit ``error`` with the exception object.
        try:
            result = self._execute()
        except Exception as exc:
            self._handle_exception(exc)
            result = None
        self.finished.emit(result)

    def _handle_exception(self, exc: Exception) -> None:
        """Three-tier error handler.

        Tier 1 — ``AlignmentFailedError`` / ``CanvasError``: recoverable pipeline
            failures; logged at WARNING (expected on tricky inputs).
        Tier 2 — any other ``PipelineError`` / ``ModelLoadError`` / ``ConfigError``:
            application-domain errors; logged at ERROR.
        Tier 3 — unexpected ``Exception``: logged at ERROR with full traceback.
        """
        try:
            from backend.src.errors import (
                AlignmentFailedError,
                CanvasError,
                ConfigError,
                ModelLoadError,
                PipelineError,
            )

            if isinstance(exc, (AlignmentFailedError, CanvasError)):
                logger.warning("%s: %s", type(exc).__name__, exc)
            elif isinstance(exc, (PipelineError, ModelLoadError, ConfigError)):
                logger.error("%s: %s", type(exc).__name__, exc)
            else:
                logger.error("Unhandled exception in worker", exc_info=exc)
        except ImportError:
            logger.error("Unhandled exception in worker", exc_info=exc)
        self.error.emit(exc)


class _WorkerSignals(QObject):
    """
    Signal carrier for ``QRunnable`` workers.

    ``QRunnable`` does not inherit ``QObject`` so signals must live in a
    separate ``QObject`` instance stored as ``worker.signals``.
    """

    finished = Signal(object)
    error = Signal(object)
    progress = Signal(int, int)  # (completed, total) — see §5.9 Option C
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
        """Task logic. Override this instead of ``run()``."""

    @gc_disabled_run
    @Slot()
    def run(self) -> None:
        if self._cancelled:
            self.signals.cancelled.emit()
            return
        try:
            self._execute()
        except Exception as exc:
            self.signals.error.emit(exc)
