"""Shared guard against the Qt Multimedia startup-probe race (issue #81).

Qt Multimedia's FFmpeg/PipeWire backend probes audio devices on its own
thread the first time anything triggers it (see backend/src/app.py's
_startup_audio_prime). Starting any other QThread (a gallery scanner
worker, for example) while that probe is still in flight -- with the
JPype JVM already loaded in-process -- reliably corrupts the heap
("QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread", followed by a SIGABRT/SIGSEGV inside libQt6Core).

Deferring MainWindow's own construction by a fixed 400ms (app.py) reduces
how often this is hit, but doesn't guarantee a minimum margin from the
probe's actual start time: if login/vault-unlock happens quickly (a
remembered/fast auth flow) and the user then acts immediately, the total
elapsed time since the probe started can still be well under however long
the probe actually takes on a given machine. This module tracks the
probe's real start time and gives every scanner-thread call site a way to
compute how much longer, if any, it should defer itself -- a floor
measured from the actual probe start, not from window-construction timing
that can vary independently of it.
"""

import time
from typing import Optional

# Empirically, 400ms alone was observed to be insufficient at least once
# (round 11 of the deleteOrphaned/startup-race investigation -- see
# .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md). This is a
# one-time cost paid once per app launch, not a recurring UX delay, so a
# generous margin costs nothing perceptible in exchange for closing the
# race outright.
_STARTUP_SETTLE_SECONDS = 1.5

_probe_start_monotonic: Optional[float] = None


def mark_startup_probe_started() -> None:
    """Call once, as early as possible, right when the Qt Multimedia
    backend is first triggered (e.g. constructing the startup QAudioOutput
    prime in launch_app())."""
    global _probe_start_monotonic
    _probe_start_monotonic = time.monotonic()


def startup_settle_remaining_ms() -> int:
    """Milliseconds still needed before it's safe to start a new QThread
    that could race the startup probe. Returns 0 once the settle window
    has elapsed, or if mark_startup_probe_started() was never called
    (e.g. under test, or any entry point that doesn't go through
    launch_app())."""
    if _probe_start_monotonic is None:
        return 0
    elapsed = time.monotonic() - _probe_start_monotonic
    remaining = _STARTUP_SETTLE_SECONDS - elapsed
    return max(0, int(remaining * 1000))
