"""Batch queue execution worker (sequential / multiprocessing pool).

Split (§5.17 Option B, #629): the single-extraction pipeline lives in
:mod:`_queue_extraction_process`; this module keeps the worker class and
re-exports :func:`run_extraction_in_process` under its historical import
path (also the multiprocessing pickle path). Pure code motion.
"""

import contextlib
import multiprocessing
import time
from typing import Any, Dict

from PySide6.QtCore import Qt, Signal

from gui.src.helpers.base import BaseQRunnableWorker, _WorkerSignals
from gui.src.helpers.core._queue_extraction_process import (
    _extraction_pool_worker_init,
    run_extraction_in_process,
)

# Workers currently mid-run(). Keeps their signals QObject (no Qt parent)
# alive until run() finishes, so a tab teardown can't GC it mid-emit (Bug 1).
_RUNNING_WORKERS: set = set()


class _QueueWorkerSignals(_WorkerSignals):
    item_started = Signal(int)  # index submitted / about to run
    item_completed = Signal(int, dict, dict)  # (index, result, original item)


class QueueExecutionWorker(BaseQRunnableWorker):
    def __init__(self, queue_items: list, parallel: bool = False, max_workers: int | None = None):
        super().__init__()
        self.queue_items = queue_items
        self.parallel = parallel
        self.max_workers = max_workers
        self.signals = _QueueWorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _execute(self) -> object:
        # Safety net (Bug 1, #633): keep this worker (and therefore its
        # signals QObject, which has no Qt parent) alive until its terminal
        # `finished` signal has been DELIVERED, even if the tab drops its
        # active_queue_worker reference mid-run. Emitting is not enough:
        # `finished` crosses threads via a queued call, and if the worker
        # is collected after run() returns but before the GUI thread pumps
        # the event, PySide drops the still-queued delivery — the header
        # sits at N/N (all item_completed arrived) with no completion
        # dialog and the queue wedges. So the set releases its reference
        # from a `finished` slot (which runs at delivery time), not from a
        # `finally` here (which runs before `finished` is even emitted).
        # Every path through BaseQRunnableWorker.run() ends in
        # `finished.emit`, so delivery always releases the guard; if the
        # event loop never pumps again (app teardown) at most one entry
        # per run leaks in the set, which dies with the process.
        _RUNNING_WORKERS.add(self)
        # A bare Python callable otherwise runs directly in the worker
        # thread.  Queue this release through the signal object's GUI-thread
        # affinity so it cannot precede the tab's queued finished handler.
        self.signals.finished.connect(
            lambda _res: _RUNNING_WORKERS.discard(self),
            Qt.ConnectionType.QueuedConnection,
        )
        try:
            return self._run_impl()
        except Exception as exc:
            # Never let the exception escape: neither finished nor error
            # would be emitted -> the tab's active_queue_worker is never
            # cleared and the queue wedges.
            with contextlib.suppress(Exception):
                self.signals.error.emit(f"Queue worker crashed: {exc}")
            return None

    def _run_impl(self):
        results = []

        if self.parallel:
            requested_workers = self.max_workers or multiprocessing.cpu_count()
            num_cores = min(max(1, requested_workers), multiprocessing.cpu_count(), len(self.queue_items))
            if num_cores < 1:
                self.signals.progress.emit(0, 0)
                return results

            total = len(self.queue_items)
            results = [None] * total
            completed = 0
            self.signals.progress.emit(0, total)
            try:
                # spawn, not the platform default (fork on Linux): a forked
                # worker is a copy-on-write image of the GUI process's
                # ENTIRE resident heap at fork time -- any already-loaded
                # Qt/torch/thumbnail-cache memory turns fully resident in
                # every child almost immediately (#485 audit's leading
                # suspect for the "2 workers, supposed headroom, SIGTERM'd"
                # reports; #483's per-worker RAM estimate assumed a clean
                # process, not an inherited GUI heap). spawn starts each
                # worker as a fresh interpreter that only imports what
                # run_extraction_in_process actually needs.
                with multiprocessing.get_context("spawn").Pool(
                    processes=num_cores,
                    initializer=_extraction_pool_worker_init,
                    maxtasksperchild=1,
                ) as pool:
                    next_i = 0
                    in_flight: Dict[int, Any] = {}

                    def _submit(i: int) -> None:
                        in_flight[i] = pool.apply_async(
                            run_extraction_in_process, (self.queue_items[i],)
                        )
                        self.signals.item_started.emit(i)

                    while next_i < num_cores:
                        _submit(next_i)
                        next_i += 1

                    while completed < total:
                        if self._is_cancelled:
                            pool.terminate()
                            self.signals.error.emit("Parallel queue extraction cancelled by user.")
                            return

                        finished = [i for i, r in in_flight.items() if r.ready()]
                        if not finished:
                            time.sleep(0.1)
                            continue
                        for i in finished:
                            async_r = in_flight.pop(i)
                            try:
                                res = async_r.get()
                            except Exception as exc:
                                res = {
                                    "status": "error",
                                    "message": f"{type(exc).__name__}: {exc}",
                                }
                            results[i] = res
                            item = self.queue_items[i]
                            self.signals.item_completed.emit(i, res, item)
                            completed += 1
                            self.signals.progress.emit(completed, total)
                            if next_i < total:
                                _submit(next_i)
                                next_i += 1
            except Exception as e:
                self.signals.error.emit(f"Parallel processing error: {e}")
                return
        else:
            total = len(self.queue_items)
            for i, item in enumerate(self.queue_items):
                if self._is_cancelled:
                    self.signals.error.emit("Sequential queue extraction cancelled by user.")
                    return

                self.signals.item_started.emit(i)
                self.signals.progress.emit(i, total)
                try:
                    res = run_extraction_in_process(item)
                except Exception as exc:  # one bad item must not kill the run
                    res = {"status": "error", "message": f"{type(exc).__name__}: {exc}"}
                results.append(res)
                self.signals.item_completed.emit(i, res, item)

        self.signals.progress.emit(total, total)
        return results
