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
- ``debug/telemetry_analyzer.py`` consumes these files to reconstruct a
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
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Optional

_ENV_VAR = "IMAGE_TOOLKIT_TELEMETRY"

TELEMETRY_DIR = Path.home() / ".image-toolkit" / "telemetry"

_TRUTHY = {"1", "true", "yes", "on"}
_enabled = os.environ.get(_ENV_VAR, "").strip().lower() in _TRUTHY

_lock = threading.Lock()
_file = None  # type: ignore[var-annotated]
_file_path: Optional[Path] = None

# Serializes calls into the native `base.scan_files_multi()` boundary across
# the independent ImageScannerWorker/VideoScannerWorker QThreads (issue #81,
# round 26 of .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md): two
# linked Wallpaper-tab panels can each start their own scanner QThread for
# the same directory within the same event-loop tick, so both threads can
# call into the native extension concurrently. Nothing establishes that
# `base.scan_files_multi` is safe to call reentrantly from multiple threads
# at once, and the crash signature (a corrupted QSocketNotifier on the main
# thread, immediately after both panels' scans start back-to-back) is
# consistent with concurrent native-side file-descriptor churn. This lives
# in `telemetry` (not a new module) since both scanner workers already
# import it for `span()`, and this module is deliberately kept
# dependency-light/stdlib-only so it's safe to import from exactly this
# kind of hot path.
NATIVE_SCAN_LOCK = threading.Lock()
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


def _ensure_file():
    global _file, _file_path
    if _file is not None:
        return _file
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    _file_path = TELEMETRY_DIR / f"telemetry-{_pid}.jsonl"
    with open(_file_path, "a", encoding="utf-8") as _file:
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
    record.update(fields)
    try:
        with _lock:
            f = _ensure_file()
            f.write(json.dumps(record, default=str) + "\n")
            f.flush()
    except Exception:
        # Telemetry must never be the reason the app crashes or misbehaves.
        pass


@contextmanager
def span(category: str, event: str, **fields: Any) -> Generator[None, None, None]:
    """Emit ``<event>.start`` before the block and ``<event>.end`` (with
    ``duration_ms``) after it, or ``<event>.error`` (with ``duration_ms``
    and ``error``) if the block raises -- the exception is always
    re-raised, this only observes it.

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
    t0 = time.monotonic()
    emit(category, f"{event}.start", **fields)
    try:
        yield
    except BaseException as exc:
        emit(
            category,
            f"{event}.error",
            duration_ms=round((time.monotonic() - t0) * 1000, 3),
            error=repr(exc),
            **fields,
        )
        raise
    else:
        emit(
            category,
            f"{event}.end",
            duration_ms=round((time.monotonic() - t0) * 1000, 3),
            **fields,
        )


def close() -> None:
    """Flush and close the telemetry file, if one is open. Not required for
    correctness (every write already flushes), but tidy for tests/tools
    that want a clean handle."""
    global _file, _file_path
    with _lock:
        if _file is not None:
            with suppress(Exception):
                _file.close()
            _file = None
            _file_path = None


__all__ = [
    "TELEMETRY_DIR",
    "is_enabled",
    "set_enabled",
    "current_file_path",
    "emit",
    "span",
    "close",
    "NATIVE_SCAN_LOCK",
]
