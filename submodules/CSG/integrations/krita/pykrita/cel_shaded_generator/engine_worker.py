"""Off-UI-thread runner for Krita Docker engine calls (issue #23).

Every Docker button handler previously called EngineClient() synchronously on
Krita's UI thread, blocking the event loop for the duration of the engine
subprocess round trip (and, in the segmentation Docker, the pure-Python
per-pixel loops). This module provides a reusable QThread subclass that runs
one engine operation off the UI thread, mirroring the parent repo's worker
pattern (a QThread subclass with finished_ok/error signals, not a
QObject+moveToThread) and the ColorizeWorker convention of passing a callable.

Only the pure engine subprocess I/O (or pure-Python buffer computation) moves
off the main thread. Krita's document/node API is NOT thread-safe, so callers
must extract pixel buffers on the UI thread and hand those to the worker, and
apply any document mutation back on the UI thread in the finished handler.
"""

from __future__ import annotations

from typing import Any, Callable

from PyQt5.QtCore import QThread, Signal


class EngineWorker(QThread):
    """Runs call() off the UI thread and reports the result.

    call is a zero-argument callable that performs exactly one engine
    operation (typically a closure over an EngineClient method + request id,
    or a pure-Python buffer computation). The worker owns its EngineClient
    instance per run so a failed/timeout engine never leaks state into the
    next invocation.
    """

    finished_ok = Signal(object)
    error = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, call: Callable[[], Any], parent=None):
        super().__init__(parent)
        self._call = call

    def run(self) -> None:
        self.busy_changed.emit(True)
        try:
            self.finished_ok.emit(self._call())
        except Exception as error:  # noqa: BLE001 - surface every failure to the UI
            self.error.emit(str(error))
        finally:
            self.busy_changed.emit(False)


class WorkerBusyMixin:
    """Shared off-UI-thread routing for Krita Docker button handlers.

    Every Docker that needs to run engine subprocess round trips or pure
    Python buffer computations without freezing Krita's UI thread mixes this
    in, calls _init_worker_state(buttons) from its __init__, and routes each
    handler through _run_worker. The dock's action buttons are disabled for
    the duration of the call (a busy counter keeps them disabled across
    chained calls), failures land in the status label, and the result is
    handed to on_ok on the UI thread.
    """

    def _init_worker_state(self, buttons):
        self._buttons = buttons
        self._worker = None
        self._busy_count = 0

    def _run_worker(self, call, on_ok, error_prefix, on_error=None):
        self._busy_count += 1
        self._set_buttons_enabled(False)
        worker = EngineWorker(call, self)
        worker.finished_ok.connect(on_ok)

        def handle_error(message):
            if on_error is not None:
                on_error(message)
            else:
                self._status.setText(error_prefix + message)

        worker.error.connect(handle_error)
        worker.busy_changed.connect(self._on_busy_changed)
        self._worker = worker  # keep the QThread alive for the duration of the run
        worker.start()

    def _on_busy_changed(self, busy):
        if busy:
            # Buttons were already disabled synchronously in _run_worker.
            return
        self._busy_count = max(0, self._busy_count - 1)
        self._set_buttons_enabled(self._busy_count == 0)

    def _set_buttons_enabled(self, enabled):
        for button in self._buttons:
            button.setEnabled(enabled)


__all__ = ["EngineWorker", "WorkerBusyMixin"]
