"""Toggleable, structured event telemetry for the gallery-scan crash class
documented in ``docs/TROUBLESHOOTING.md`` (``deleteOrphaned`` /
``QSocketNotifier`` / glibc heap-corruption family) and
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md``.

Sixteen-plus rounds of that investigation relied on ad hoc
``print(..., flush=True)`` statements, scattered across whichever file
happened to be under suspicion that round, read by eye out of a terminal
dump after the fact. That works, but it doesn't compose: there's no way to
merge events from `app.py`, the scanner-thread files, and the native
`QImage` decode boundary into one ordered timeline, and every round pays the
cost of re-adding/removing prints. This module is a single, always-available
sink for that same kind of instrumentation:

- Disabled by default (near-zero cost: one boolean check per call site).
- Enabled via ``IMAGE_TOOLKIT_TELEMETRY=1`` (or ``set_enabled(True)``), so a
  reproduction run can be instrumented without editing code.
- Writes newline-delimited JSON to ``~/.image-toolkit/telemetry/telemetry-<pid>.jsonl``,
  flushed after every line (same "survive a SIGABRT/SIGSEGV moments later"
  reasoning as the existing ``flush=True`` print idiom this replaces/
  augments) -- a partial file from a crashed run is still fully readable up
  to the last completed event.
- ``dev/telemetry_analyzer.py`` consumes these files to reconstruct a
  merged, per-thread timeline and flag exactly the kind of overlap
  (concurrent scanner threads, native calls in flight when the log stops)
  that previously had to be found by eye.

Deliberately dependency-light (stdlib only) so it's safe to import from
hot paths -- worker threads, the native ``base`` module call boundary, even
before the vault/JVM is up -- without adding a new failure mode of its own.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from typing import Any, Optional

from backend.src.constants.core import _ENV_VAR, _TRUTHY, NATIVE_IMAGE_BATCH_LOCK, NATIVE_SCAN_LOCK, TELEMETRY_DIR

_enabled = os.environ.get(_ENV_VAR, "").strip().lower() in _TRUTHY

_lock = threading.Lock()
_file = None  # type: ignore[var-annotated]
_file_context = ExitStack()
_file_path: Optional[Path] = None
_seq = 0
_tls = threading.local()

# Serializes calls into backend/src/manga/{colorization,screentone}.py's
# OpenCV-heavy solve path (cv2.filter2D/GaussianBlur/resize + cvtColor,
# plus the scipy sparse LU factorization) across independent
# ColorizeWorker QThreads. Prompted by a "Mean of empty slice"/"Degrees of
# freedom <= 0" RuntimeWarning observed only when two ColorizeWorker
# threads' solves overlapped in wall-clock time (back-to-back GUI tests
# each starting a real worker) -- never seen with a single solve run in
# isolation, and every dedicated backend/test/manga/ correctness test
# (which never overlaps two solves) passes reliably. Consistent with this
# project's own established, previously-confirmed pattern for this exact
# risk class -- see NATIVE_IMAGE_BATCH_LOCK's docstring/history for the
# same "concurrent native-touching calls from independent QThreads"
# mechanism, there for base.load_image_batch(). Manga colorization is a
# single-shot "click Colorize and wait ~4s" operation (the UI disables the
# button while a solve is in flight), so serializing concurrent solves
# costs nothing in real usage.
MANGA_COLORIZE_LOCK = threading.Lock()

# Serializes calls into the native `base.scan_files_multi()` boundary across
# the independent ImageScannerWorker/VideoScannerWorker QThreads (issue #81,
# round 26 of .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).
# Round 26's own hypothesis (Gemini-delegated, marked unverified at the
# time because the native `base` extension failed to import in that
# session) turned out to target the wrong function once the C++ source was
# actually readable: `base::image::scan_files`/`scan_files_multi`
# (base/src/image/scan_files.cpp) only touches local `std::vector`s and
# `std::filesystem` iterators -- no global/static mutable state -- so it is
# reentrant by construction and was never the real race. This lock is kept
# anyway (cheap, harmless, and scans are infrequent) rather than removed,
# so as not to re-open a "confirmed safe without a live regression test"
# gap purely on static-code-reading confidence.

# Serializes calls into the native `base.load_image_batch()` boundary
# (base/src/image/image_batch.cpp, called from
# gui/src/helpers/image/batch_image_loader_worker.py::native_load_batch,
# which both `BatchImageLoaderWorker` and `ImageLoaderWorker` funnel
# through) -- the actual root cause this project's SIGSEGV/QSocketNotifier
# crash class (see NATIVE_SCAN_LOCK above and
# .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md) was chasing.
# Unlike `scan_files_multi`, `load_image_batch` releases the GIL
# (`py::gil_scoped_release`) and runs `cv::imread`/`cv::imdecode`/
# `cv::resize`/`cv::imwrite` across an internal OpenMP thread team
# (`#pragma omp parallel for`) to fill/read a *shared, unlocked* on-disk
# thumbnail cache directory. It is called concurrently and frequently --
# every `QThreadPool` worker across every open gallery tab funnels through
# it, e.g. two linked Wallpaper-tab panels finishing their scans back to
# back both immediately queue `BatchImageLoaderWorker` runnables. Nothing
# in this call establishes it is safe to have two independent OpenMP
# thread teams (each spawned by a different host thread) alive at once
# inside libopencv/libjpeg, nor that two threads racing to
# read-then-write the same cache file (mtime-invalidated, no lock) can't
# corrupt each other's I/O -- both are consistent with the observed
# `QSocketNotifier: Socket notifiers cannot be enabled or disabled from
# another thread` + `SIGSEGV` inside `QString::vasprintf` signature.
# Serializing this call costs little: a single call already parallelizes
# internally via OpenMP across all cores, so multiple *concurrent* Python
# entries were never adding real parallelism, only race risk.
_pid = os.getpid()
_t0 = time.monotonic()


def is_enabled() -> bool:
    """Whether telemetry is currently active (checked once per emit() call)."""
    return _enabled


def set_enabled(value: bool) -> None:
    """Toggle telemetry at runtime -- e.g. from a settings checkbox or a
    debug menu action, without requiring the env var / a restart."""
    global _enabled
    _enabled = value


def current_file_path() -> Optional[Path]:
    """The telemetry file this process is writing to, once it has emitted at
    least one event (None before that, or if telemetry has never been
    enabled this process)."""
    return _file_path


def _span_stack() -> list[dict[str, Any]]:
    stack = getattr(_tls, "spans", None)
    if stack is None:
        stack = []
        _tls.spans = stack
    return stack


def _new_span_id() -> str:
    return secrets.token_hex(4)


def _ensure_file():
    global _file, _file_context, _file_path
    if _file is not None and not _file.closed:
        return _file
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    _file_path = TELEMETRY_DIR / f"telemetry-{_pid}.jsonl"
    _file = _file_context.enter_context(_file_path.open("a", encoding="utf-8"))
    return _file


def emit(category: str, event: str, **fields: Any) -> None:
    """Record one structured telemetry event, if telemetry is enabled.

    A cheap no-op (single boolean check) when disabled -- safe to call
    unconditionally from hot paths (scanner threads, native call
    boundaries) rather than guarding every call site with ``if
    telemetry.is_enabled():`` first.

    Every event automatically carries: monotonic offset from process start
    (``t``, seconds), wall-clock time (``wall``), pid, OS thread id
    (``tid``) and name (``tname``) -- exactly the fields needed to merge
    events from multiple threads/files into one ordered timeline. Extra
    context (panel id, directory, worker id, ...) goes in ``**fields``.
    """
    if not _enabled:
        return
    record = {
        "t": round(time.monotonic() - _t0, 6),
        "wall": time.time(),
        "pid": _pid,
        "tid": threading.get_ident(),
        "tname": threading.current_thread().name,
        "category": category,
        "event": event,
    }
    stack = _span_stack()
    if "span_id" not in fields and stack:
        record["span_id"] = stack[-1]["span_id"]
    record.update(fields)
    try:
        with _lock:
            global _seq
            if "seq" not in record:
                _seq += 1
                record["seq"] = _seq
            record.setdefault("runtime", "python")
            f = _ensure_file()
            f.write(json.dumps(record, default=str) + "\n")
            f.flush()
    except Exception:
        # Telemetry must never be the reason the app crashes or misbehaves.
        pass


def begin_span(category: str, event: str, **fields: Any) -> Optional[str]:
    """Allocate a ``span_id``, emit ``<event>.start``, and push the span.

    Returns the id, or ``None`` when telemetry is disabled (no-op, no
    stack mutation). Nested calls set ``parent_span_id`` from the open
    parent. Old JSONL readers ignore the new fields.
    """
    if not _enabled:
        return None
    stack = _span_stack()
    parent = stack[-1]["span_id"] if stack else None
    span_id = fields.pop("span_id", None) or _new_span_id()
    extra = dict(fields)
    extra["span_id"] = span_id
    if parent is not None:
        extra.setdefault("parent_span_id", parent)
    extra.setdefault("runtime", "python")
    stack.append({"span_id": span_id, "t0": time.monotonic(), "event": event})
    emit(category, f"{event}.start", **extra)
    return span_id


def end_span(
    category: str,
    event: str,
    *,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
    **fields: Any,
) -> None:
    """Pop the current span and emit ``<event>.end`` or ``<event>.error``."""
    if not _enabled:
        return
    stack = _span_stack()
    span_id = fields.pop("span_id", None)
    t0 = None
    if stack and (span_id is None or stack[-1]["span_id"] == span_id):
        frame = stack.pop()
        span_id = frame["span_id"]
        t0 = frame["t0"]
    elif span_id is not None:
        for i in range(len(stack) - 1, -1, -1):
            if stack[i]["span_id"] == span_id:
                t0 = stack.pop(i)["t0"]
                break
    extra = dict(fields)
    if span_id is not None:
        extra["span_id"] = span_id
    if stack:
        extra.setdefault("parent_span_id", stack[-1]["span_id"])
    if duration_ms is None and t0 is not None:
        duration_ms = round((time.monotonic() - t0) * 1000, 3)
    if duration_ms is not None:
        extra["duration_ms"] = duration_ms
    if error is not None:
        extra["error"] = error
        emit(category, f"{event}.error", **extra)
    else:
        emit(category, f"{event}.end", **extra)


@contextmanager
def span(category: str, event: str, **fields: Any) -> Generator[None, None, None]:
    """Emit ``<event>.start`` before the block and ``<event>.end`` (with
    ``duration_ms``) after it, or ``<event>.error`` (with ``duration_ms``
    and ``error``) if the block raises -- the exception is always
    re-raised, this only observes it.

    Allocates a ``span_id`` and nests via ``parent_span_id`` (D4 / D23).
    Disabled telemetry is a plain no-op.

    Intended for exactly the kind of call this investigation has repeatedly
    needed visibility into but never had: a native call boundary
    (``base.scan_files_multi``, ``QImage.loadFromData``) where the process
    might not survive to see a normal ``.end`` event at all -- if the
    ``.start`` line is the last one in the file, that itself is the
    finding.
    """
    if not _enabled:
        yield
        return
    begin_span(category, event, **fields)
    try:
        yield
    except BaseException as exc:
        end_span(category, event, error=repr(exc), **fields)
        raise
    else:
        end_span(category, event, **fields)


def close() -> None:
    """Flush and close the telemetry file, if one is open. Not required for
    correctness (every write already flushes), but tidy for tests/tools
    that want a clean handle."""
    global _file, _file_context, _file_path
    with _lock:
        if _file is not None:
            with suppress(Exception):
                _file_context.close()
            _file = None
            _file_context = ExitStack()
            _file_path = None
    _tls.spans = []


__all__ = [
    "TELEMETRY_DIR",
    "is_enabled",
    "set_enabled",
    "current_file_path",
    "emit",
    "begin_span",
    "end_span",
    "span",
    "close",
    "NATIVE_SCAN_LOCK",
    "NATIVE_IMAGE_BATCH_LOCK",
    "MANGA_COLORIZE_LOCK",
]
