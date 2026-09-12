"""gui/src/services/directory_scan_service.py
=============================================
Shared directory-scan service (ui-arch-39 / #561, R1.6).

One cancellable file-collection implementation replacing the six
``_directory_browse.py`` walk blocks (codec/format/sampler/similarity/…)
and the near-duplicate ``_scan_flat``/``_scan_recursive`` pairs in the
image/video scanner workers.

Layout
------
- :class:`ScanRequest` — value object: path, extension filter, recursion,
  hidden-file and symlink policy.
- :func:`normalize_extensions` — ``{"JPG", ".png", " .gif "}`` → ``{"jpg",
  "png", "gif"}`` (no dots, lowered, stripped).
- :func:`collect_files` — pure ``os.scandir`` walk. No Qt, no app imports,
  headless-testable. Unreadable directories are skipped, never raised
  (``os.walk`` parity: its default ``onerror=None`` also ignores them).
- :class:`ScanSession` — cancellable generation token for GUI slots: each
  new scan cancels the previous worker and bumps the generation; stale
  deliveries are dropped. The worker class is imported lazily so this
  module never pulls the heavy ``gui.src.helpers`` barrel.

Threading: call :func:`collect_files` / the worker off the GUI thread.
Per-entry ``is_cancelled`` checkpoints make huge trees abort promptly.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Collection
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal

from gui.src.qt_object_guard import deleted_qobject_guard

#: Emit progress heartbeats every N matched files.
PROGRESS_STRIDE = 256


@dataclass(frozen=True)
class ScanRequest:
    """Value object describing one directory scan."""

    path: str
    extensions: Collection[str] = field(default_factory=tuple)
    recursive: bool = False
    skip_hidden: bool = False
    follow_symlinks: bool = False
    accept_single_file: bool = False


def normalize_extensions(extensions: Collection[str] | None) -> frozenset[str]:
    """Normalize an extension filter to dot-less lowercase names."""
    if not extensions:
        return frozenset()
    return frozenset(e.strip().lstrip(".").lower() for e in extensions if e and e.strip())


def _matches(name: str, wanted: frozenset[str], skip_hidden: bool) -> bool:
    if skip_hidden and name.startswith("."):
        return False
    if not wanted:
        return True
    return os.path.splitext(name)[1].lstrip(".").lower() in wanted


def _never_cancelled() -> bool:
    """Default cancellation poll that never fires."""
    return False


class _Collector:
    """Cancellation/progress bookkeeping for one scan."""

    def __init__(
        self,
        is_cancelled: Callable[[], bool] | None,
        on_progress: Callable[[int], None] | None,
    ) -> None:
        self._is_cancelled = is_cancelled or _never_cancelled
        self._on_progress = on_progress
        self.found: list[str] = []
        self._matched = 0

    def cancelled(self) -> bool:
        """Whether the scan should stop at the next checkpoint."""
        return self._is_cancelled()

    def note_match(self, path: str) -> None:
        """Record one matched path, emitting periodic heartbeats."""
        self.found.append(path)
        self._matched += 1
        if self._on_progress is not None and self._matched % PROGRESS_STRIDE == 0:
            self._on_progress(self._matched)


def _scan_flat(path: str, wanted: frozenset[str], request: ScanRequest, out: _Collector) -> None:
    try:
        with os.scandir(path) as it:
            for entry in it:
                if out.cancelled():
                    return
                try:
                    is_file = entry.is_file(follow_symlinks=True)
                except OSError:
                    continue
                if is_file and _matches(entry.name, wanted, request.skip_hidden):
                    out.note_match(entry.path)
    except OSError:
        pass


def _scan_recursive(path: str, wanted: frozenset[str], request: ScanRequest, out: _Collector) -> None:
    stack = [path]
    while stack:
        if out.cancelled():
            return
        try:
            with os.scandir(stack.pop()) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            if out.cancelled():
                return
            try:
                if entry.is_dir(follow_symlinks=request.follow_symlinks):
                    hidden = entry.name.startswith(".")
                    if not (request.skip_hidden and hidden):
                        stack.append(entry.path)
                elif entry.is_file(follow_symlinks=True) and _matches(entry.name, wanted, request.skip_hidden):
                    out.note_match(entry.path)
            except OSError:
                continue


def collect_files(
    request: ScanRequest,
    is_cancelled: Callable[[], bool] | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> list[str]:
    """Collect matching file paths under ``request.path``.

    Returns paths in filesystem order (callers apply ``natural_sort_key``).
    A single file path returns ``[path]`` only when
    ``accept_single_file`` is set; a missing path returns ``[]``.
    Stops early on cancellation, returning what was found so far.

    File matching always follows symlinks (the old ``entry.is_file()``
    and ``os.walk`` filename behavior); ``follow_symlinks`` only governs
    whether recursion descends into symlinked directories.
    """
    out = _Collector(is_cancelled, on_progress)
    if out.cancelled():
        return []
    path = request.path
    if os.path.isfile(path):
        if request.accept_single_file and _matches(
            os.path.basename(path),
            normalize_extensions(request.extensions),
            request.skip_hidden,
        ):
            out.note_match(path)
        return out.found
    if not os.path.isdir(path):
        return []
    wanted = normalize_extensions(request.extensions)
    if request.recursive:
        _scan_recursive(path, wanted, request, out)
    else:
        _scan_flat(path, wanted, request, out)
    return out.found


class _ScanRelay(QObject):
    """GUI-thread delivery relay for one :class:`ScanSession`."""

    ready = Signal(object)  # (generation, payload) tuples


class ScanSession:
    """Cancellable generation-token guard for GUI scan slots.

    Each :meth:`scan` cancels the in-flight worker (if any), bumps the
    generation, and starts a new :class:`DirectoryScanWorker`. Delivery
    is re-emitted through a GUI-thread relay, so ``on_finished`` always
    runs on the GUI thread. Deliveries from older generations — and
    ``None`` (cancel/failure) payloads — are dropped before reaching
    ``on_finished``.

    Lifetime: the session holds every in-flight worker until its thread
    has exited (verified with ``wait()`` on the GUI thread) before
    dropping the reference. Dropping the last Python reference of a
    ``QThread`` while it is still running aborts the process
    (``QThread: Destroyed while thread is still running``), so a worker
    whose bounded join times out is *retained* — in both ``cancel()``
    and delivery — and retired by a later scan/cancel/delivery.
    """

    #: Bounded join when retiring a worker (ms). Workers checkpoint
    #: cancellation per directory entry, so this returns promptly.
    JOIN_TIMEOUT_MS = 5000

    def __init__(self) -> None:
        self._generation = 0
        self._workers: dict[int, object] = {}
        self._callbacks: dict[int, Callable[[list], None]] = {}
        self._relay = None  # lazy _ScanRelay; GUI-thread affinity
        self._relay_connected = False

    @property
    def generation(self) -> int:
        """Current generation (bumped once per :meth:`scan`)."""
        return self._generation

    def _release(self, worker: object) -> bool:
        """Bounded join; True when the worker reference may be dropped."""
        wait = getattr(worker, "wait", None)
        if callable(wait):
            try:
                wait(self.JOIN_TIMEOUT_MS)
            except RuntimeError as exc:
                deleted_qobject_guard(exc, "ScanSession worker join")
        is_running = getattr(worker, "isRunning", None)
        return not callable(is_running) or not is_running()

    def cancel(self) -> None:
        """Cancel all in-flight scans and join their threads (bounded).

        A worker still alive after the join is retained for later safe
        retirement, never released while running.
        """
        workers = self._workers
        self._workers = {}
        for worker in workers.values():
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                cancel()
        for generation, worker in workers.items():
            if self._release(worker):
                self._callbacks.pop(generation, None)
            else:
                # Join timed out with the thread still alive: retain the
                # reference (and its callback) for a later scan/cancel/
                # delivery to retire — releasing it here would destroy a
                # running QThread and abort the process.
                self._workers[generation] = worker

    def scan(
        self,
        request: ScanRequest,
        on_finished: Callable[[list], None],
    ) -> int:
        """Start an async scan; return its generation.

        ``on_finished`` runs on the GUI thread with the path list. Stale
        or ``None`` deliveries never reach it. Must be called on the GUI
        thread (the delivery relay takes the caller's thread affinity).
        """
        from gui.src.helpers.core.directory_scan_worker import (
            DirectoryScanWorker,
        )

        self.cancel()
        self._generation += 1
        generation = self._generation
        if self._relay is None:
            # Created here, on the caller's (GUI) thread, so delivery
            # via ``ready`` is queued back to the GUI thread.
            self._relay = _ScanRelay()
        relay = self._relay
        if not self._relay_connected:
            relay.ready.connect(self._on_ready)
            self._relay_connected = True
        worker = DirectoryScanWorker(request)
        self._workers[generation] = worker
        self._callbacks[generation] = on_finished
        worker.finished.connect(lambda payload, _gen=generation: relay.ready.emit((_gen, payload)))
        worker.start()
        return generation

    def _on_ready(self, item: object) -> None:
        """GUI-thread delivery: retire the worker, then forward or drop."""
        generation, payload = item  # type: ignore[misc]
        worker = self._workers.pop(generation, None)
        callback = self._callbacks.pop(generation, None)
        if worker is not None and not self._release(worker):
            # Join timed out with the thread still alive: keep the
            # reference (retired on the next scan/cancel) rather than
            # destroy a running QThread, which aborts the process.
            self._workers[generation] = worker
            if callback is not None:
                self._callbacks[generation] = callback
        if generation != self._generation:
            return
        if payload is None or callback is None:
            return
        callback(list(payload))  # type: ignore[arg-type]


__all__ = [
    "PROGRESS_STRIDE",
    "ScanRequest",
    "ScanSession",
    "collect_files",
    "normalize_extensions",
]
