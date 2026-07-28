"""Shared guard against the Qt Multimedia startup-probe race (issue #81).

Qt Multimedia's FFmpeg/PipeWire backend probes audio devices on its own
thread the first time anything triggers it (see backend/src/app.py's
_startup_audio_prime). Starting any other QThread (a gallery scanner
worker, for example) while that probe is still in flight -- with the
JPype JVM already loaded in-process -- reliably corrupts the heap
("QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread", followed by a SIGABRT/SIGSEGV inside libQt6Core).

Round 11 gated every scanner-thread call site behind a fixed 1.5s
elapsed-time floor measured from the probe's actual start. That STILL
did not close the crash (round 12, identical libQt6Core.so.6+0x1df7c9
offset, three times running now) -- meaning either the probe takes
longer than 1.5s on this machine, or the 1.5s window was never actually
the operative constraint (e.g. JVM+vault startup alone already exceeds
it, so the guard had nothing left to defer by the time any scan could
start) and this crash isn't purely a "give it more time" problem at all.

This module now does two things instead of guessing a bigger number:
1. Tracks real, positive confirmation that the probe finished, via
   QMediaDevices' audioOutputsChanged/audioInputsChanged signals (wired
   up in app.py) -- so a fast probe doesn't force a needless wait, and a
   slow probe genuinely gets waited out instead of being cut off by an
   arbitrary ceiling.
2. Prints timestamped diagnostics (flush=True, so they survive a SIGSEGV
   moments later) at every decision point, so the *next* crash report
   gives direct evidence of what this guard actually did, instead of
   requiring another round of inference from an unrelated stdout dump.
"""

import time
from typing import Optional

# Upper bound if QMediaDevices never confirms (backend doesn't emit the
# signal, or emits it before we've connected). Deliberately larger than
# round 11's 1.5s, which was shown insufficient -- this is a ceiling to
# fall back to, not the expected wait in the common case (the signal
# should fire well before this and let callers proceed sooner).
_STARTUP_SETTLE_CEILING_SECONDS = 5.0

_probe_start_monotonic: Optional[float] = None
_probe_settled: bool = False
_probe_settled_at_elapsed_s: Optional[float] = None


def mark_startup_probe_started() -> None:
    """Call once, as early as possible, right when the Qt Multimedia
    backend is first triggered (e.g. constructing the startup QAudioOutput
    prime in launch_app())."""
    global _probe_start_monotonic, _probe_settled, _probe_settled_at_elapsed_s
    _probe_start_monotonic = time.monotonic()
    _probe_settled = False
    _probe_settled_at_elapsed_s = None
    print(
        f"[startup-probe-guard] t=0.000s probe started "
        f"(ceiling={_STARTUP_SETTLE_CEILING_SECONDS}s)",
        flush=True,
    )


def mark_startup_probe_settled(source: str = "unknown") -> None:
    """Call when positive confirmation is available that the startup
    probe has actually finished -- e.g. QMediaDevices' first
    audioOutputsChanged/audioInputsChanged signal firing. Lets
    startup_settle_remaining_ms() return 0 immediately instead of always
    waiting out the full ceiling, and records when this happened for
    diagnostics."""
    global _probe_settled, _probe_settled_at_elapsed_s
    if _probe_settled:
        return
    _probe_settled = True
    elapsed = (
        time.monotonic() - _probe_start_monotonic
        if _probe_start_monotonic is not None
        else -1.0
    )
    _probe_settled_at_elapsed_s = elapsed
    print(
        f"[startup-probe-guard] t={elapsed:.3f}s probe confirmed settled "
        f"(source={source})",
        flush=True,
    )


def startup_settle_remaining_ms() -> int:
    """Milliseconds still needed before it's safe to start a new QThread
    that could race the startup probe. Returns 0 once either the probe
    has been positively confirmed settled, or the fallback ceiling has
    elapsed, or if mark_startup_probe_started() was never called (e.g.
    under test, or any entry point that doesn't go through launch_app())."""
    if _probe_settled:
        return 0
    if _probe_start_monotonic is None:
        return 0
    elapsed = time.monotonic() - _probe_start_monotonic
    remaining = _STARTUP_SETTLE_CEILING_SECONDS - elapsed
    return max(0, int(remaining * 1000))
