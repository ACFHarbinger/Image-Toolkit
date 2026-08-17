# debug/

Toggleable instrumentation and analysis tooling, built specifically to chase
the gallery directory-switch crash class documented in
[`docs/TROUBLESHOOTING.md`](../docs/TROUBLESHOOTING.md) (`QSocketNotifier`
warning → `deleteOrphaned` SIGSEGV / glibc heap corruption / SIGABRT) and
[`.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`](../.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md).
Sixteen-plus rounds of that investigation relied on ad hoc
`print(..., flush=True)` statements, read out of a terminal dump by eye.
That instrumentation is still in place (it's cheap and it's what proved
several theories wrong) — this directory adds a second, structured layer
next to it, plus tooling to actually analyze the result instead of eyeballing
it.

## The instrumentation: `backend/src/core/telemetry.py`

A toggleable, dependency-light structured event logger. Disabled by default
(near-zero cost — one boolean check per call site). Enable it for a
reproduction run:

```bash
IMAGE_TOOLKIT_TELEMETRY=1 just python
```

Every enabled call writes one JSON line to
`~/.image-toolkit/telemetry/telemetry-<pid>.jsonl`, flushed immediately —
same reasoning as the existing `flush=True` print idiom: a line that made it
to disk survives the process's own SIGSEGV/SIGABRT a moment later, so a
truncated final line is expected on a crashed run, not an error.

Call sites already wired up (additive only — none of the existing
crash-history-sensitive `[thread-lifecycle]`/`[startup-probe-guard]` prints
were removed or altered):

- `backend/src/app.py` — JVM start, JPEG-plugin priming, login success,
  `MainWindow` construction/show.
- `backend/src/core/vault_manager.py` — `jpype.startJVM()` span.
- `backend/src/core/lifecycle_memory.py` — every RSS snapshot.
- `gui/src/utils/guard/startup_probe_guard.py` — probe started/settled.
- The Wallpaper scan pipeline (`_scan_pipeline.py`, `_scanner_lifecycle.py`,
  `system_display_subtab/_config.py`) — every scanner-`QThread`
  start/stop/wait/deleteLater transition, per panel, per worker instance.
- `ExtractorTab`'s equivalent scan path
  (`extractor_tab/_directory_scanning.py`).
- **The suspected native-crash boundary** (Addendum 11 of the crash doc):
  `gui/src/helpers/video/video_thumbnailer.py`'s three
  `QImage().loadFromData(...)` calls — the first video-thumbnail JPEG
  decode in the process lazily loads Qt's JPEG plugin off a worker thread,
  with the JVM already loaded in-process. Also `base.scan_files_multi()` in
  both `image_scan_worker.py` and `video_scan_worker.py`, and the
  `ThreadPoolExecutor` creation/dispatch in `video_scan_worker.py`.

To add more instrumentation at a new call site:

```python
from backend.src.core import telemetry

telemetry.emit("category", "event.name", some_field=value)   # one-shot
with telemetry.span("native", "some_call", path=path):        # start/end/error
    risky_native_call()
```

`emit()`/`span()` are safe to call unconditionally — they no-op when
telemetry is disabled, and never raise (a telemetry write failure is
swallowed, not propagated).

## The analysis tool: `telemetry_analyzer.py`

```bash
python debug/telemetry_analyzer.py                 # latest file, full report
python debug/telemetry_analyzer.py PATH_TO_FILE      # a specific file
python debug/telemetry_analyzer.py --list             # list available files
python debug/telemetry_analyzer.py --tail 40            # just the last 40 events
python debug/telemetry_analyzer.py --category native      # filter by category
```

The full report merges every thread's events into one time-ordered timeline
and flags two things this investigation kept needing and never had tooling
for:

1. **Orphaned spans** — a `telemetry.span()` whose `.start` was recorded but
   never got an `.end`/`.error`. If the run crashed, this is direct evidence
   of which native call was in flight at the moment of the fault, instead of
   the previous method (infer it from which `print()` line happened to be
   last in the terminal).
2. **Overlapping scanner-thread windows** — two `ImageScannerWorker`/
   `VideoScannerWorker` (or the Extractor tab's equivalent) lifetimes
   overlapping in time. This is the shape every root-cause theory in the
   crash doc has pointed at (deleteOrphaned races, stale `scan_finished`
   deliveries, linked-panel cross-talk), surfaced automatically instead of
   traced by hand across a wall of prints.

## The crash-capture tool: `run_with_gdb.sh`

Both docs explicitly name this as the next step once Python-level
instrumentation stops localizing the crash further: *"the next step is
external process tracing (`strace -f`, or GDB attached ahead of time), not
more Python print statements."*

```bash
IMAGE_TOOLKIT_TELEMETRY=1 debug/run_with_gdb.sh
```

Runs `backend/main.py` under `gdb -batch`, stopping **only on SIGABRT** — glibc's
malloc-corruption abort, the `corrupted size vs. prev_size` crash this tool
exists for — and dumping an all-thread backtrace (`thread apply all bt full`)
to `~/.image-toolkit/telemetry/gdb-backtrace-<timestamp>.txt`, then
re-delivering the same signal to the process so the JVM's own
`hs_err_pid*.log` still gets written for the same crash (gdb stopping the
process first would otherwise silently suppress it). Correlate the gdb
file's timestamp with the matching `telemetry-<pid>.jsonl` (same run,
telemetry enabled) via `telemetry_analyzer.py`, and cross-reference both
against the `hs_err` file's own frame dump.

**SIGSEGV is deliberately left to pass through untouched** (`handle SIGSEGV
nostop noprint pass`) — HotSpot JVMs raise SIGSEGV *on purpose* as part of
normal operation (implicit null-pointer checks and safepoint polling are
both implemented by letting the CPU fault intentionally, then the JVM's own
installed handler catches it and recovers). An earlier version of this
script stopped on SIGSEGV too, which made gdb intercept every one of these
benign, self-handled JVM signals and produced a misleading "the app crashes
before the login window even opens" symptom that never happens without gdb
in the way. See Addendum 19 in the crash doc for the full story — including
why the "matching JIT-codecache address" finding from Addendum 18 turned
out to be this same artifact, not a real lead. `libc6-dbg`/`python3-dbg`
were never the missing piece either — `just python` runs a uv-managed,
already-unstripped CPython build, not the system one debug-symbol packages
would target.

Requires `gdb` installed (`sudo apt install gdb` on Debian/Ubuntu). Extra
arguments are forwarded to `backend/main.py` (e.g.
`debug/run_with_gdb.sh --no-dropdown`).

The script also raises the core-dump size limit (`ulimit -c unlimited`)
before launching, and collects any `hs_err_pid*.log`/`core.<pid>` files the
JVM writes into `~/.image-toolkit/telemetry/` afterward (they'd otherwise
land in the repo root — both are `.gitignore`d).

## Resolving a Qt crash offset: `resolve_qt_offset.py`

PySide6 ships its own private Qt build, fully stripped of local symbols —
`Problematic frame: C [libQt6Core.so.6+0x1e74d5]` in an `hs_err_pid*.log`
is as far as the JVM's own fatal-error handler gets on its own, and no
system debug-symbol package matches it (it isn't the system Qt). The
*dynamic* symbol table survives stripping, though, and this tool resolves
a raw offset to its nearest enclosing exported C++ symbol using it:

```bash
python debug/resolve_qt_offset.py --hs-err ~/.image-toolkit/telemetry/hs_err_pid12345.log
python debug/resolve_qt_offset.py "libQt6Core.so.6+0x1e74d5"
```

This is exactly how Addendum 20 of the crash doc resolved two
long-mysterious crash offsets to `QObjectPrivate::ConnectionData::deleteOrphaned(...)`
and `QObjectPrivate::connect(...)` — confirming, for the first time with
hard evidence, that this crash class is a real QObject connection-list
corruption bug, not whatever the raw offset happened to coincide with in
earlier guesses. Requires `nm`/`c++filt` (binutils — installed alongside
`gdb`/build-essential on most distros).

## Reproducing the crash

Per the crash doc, the most reliable repro is: let the app auto-restore a
previously browsed directory on startup, then immediately (manually or via
the Wallpaper tab's browse button) switch to a directory containing videos —
image → video is the trigger; video → video or image → image has not
reproduced it.

## The workbench: debugtool

Phase 1 of the debug workbench roadmap (docs/moon/roadmaps/debug_workbench.md)
adds a session-oriented analysis layer over the same telemetry files:

    python -m debugtool list                     # list available sessions
    python -m debugtool analyze [path|--pid N]   # full report for one session
    python -m debugtool analyze [path] --tail N  # last N events only

Or as a library from any agent/tool:

    from debugtool import open_session
    session = open_session(pid=1234)      # or open_session(path=...)
    session.orphaned_spans()              # what was in flight at a crash
    session.in_flight_at(t)               # spans active at a moment
    session.overlapping_windows()         # generalized worker-window overlaps

telemetry_analyzer.py is now a compatibility shim that delegates to
debugtool analyze; run_with_gdb.sh and resolve_qt_offset.py will be
wrapped by later phases.
