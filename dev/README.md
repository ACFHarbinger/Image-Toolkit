# `dev/` — Development Tool

Modular host for telemetry, crash forensics, benchmarks, and plugins.
Everything under `dev/` — the `tool` package, its tests, and the standalone
scripts below — used to be split across `dev/` and `debug/`; both folded
into this one directory (2026-08-17) once `devtool`'s Track A/C build gave
the old `debug/debugtool` package a permanent home instead of a
migrate-later shim.

Plan: [`docs/moon/roadmaps/development_tool.md`](../docs/moon/roadmaps/development_tool.md)

```bash
PYTHONPATH=dev python -m tool               # workspace chooser (no daemon)
PYTHONPATH=dev python -m tool plugins
PYTHONPATH=dev python -m tool list
PYTHONPATH=dev python -m tool analyze [path|--pid N] [--tail N] [--category X]
PYTHONPATH=dev python -m tool tui [path|--pid N] [--view NAME]
PYTHONPATH=dev python -m tool watch [path|--pid N]
PYTHONPATH=dev python -m tool export|diff|prune|resolve-offset|repro ...
```

```python
from tool import open_session, Host, WorkspaceStore
session = open_session(pid=1234)
```

## Why this exists

Grew out of the 16+ round gallery directory-switch crash investigation
(`QSocketNotifier` warning → `deleteOrphaned` SIGSEGV / glibc heap
corruption / SIGABRT — see `docs/TROUBLESHOOTING.md` and
`.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`), which relied on
ad hoc `print(..., flush=True)` statements read out of a terminal dump by
eye. `tool` is the structured, queryable successor: a `Session` model over
the same telemetry JSONL, a visual TUI, crash-capture tooling, and — since
the 2026-08-17 `devtool` build — a plugin host, MCP server, local web
viewer, and benchmark/ASP-evaluator adapters. The gallery-crash workflow
was the first user, not the only one.

## The instrumentation: `backend/src/core/telemetry.py`

A toggleable, dependency-light structured event logger. Disabled by default
(near-zero cost — one boolean check per call site). Enable it for a
reproduction run:

```bash
IMAGE_TOOLKIT_TELEMETRY=1 just python
```

Every enabled call writes one JSON line to
`~/.image-toolkit/telemetry/telemetry-<pid>.jsonl`, flushed immediately —
a line that made it to disk survives the process's own SIGSEGV/SIGABRT a
moment later, so a truncated final line is expected on a crashed run, not
an error. Optional `span_id`/`parent_span_id`/`seq` (D4/D23) let spans nest
into a real tree when the writer opts in; ASP's `PipelineSession` does.

Call sites already wired up: `backend/src/app.py` (JVM start, JPEG-plugin
priming, login success, `MainWindow` construction/show),
`backend/src/core/vault_manager.py` (`jpype.startJVM()`),
`backend/src/core/lifecycle_memory.py` (RSS snapshots),
`gui/src/utils/guard/startup_probe_guard.py`, the Wallpaper scan pipeline
(`_scan_pipeline.py`, `_scanner_lifecycle.py`,
`system_display_subtab/_config.py` — every scanner-`QThread`
start/stop/wait/deleteLater transition), the Extractor tab's equivalent
scan path (`extractor_tab/_directory_scanning.py`), and the suspected
native-crash boundary: `gui/src/helpers/video/video_thumbnailer.py`'s
`QImage().loadFromData(...)` calls plus `base.scan_files_multi()` /
`ThreadPoolExecutor` dispatch in the scan workers.

To add more instrumentation at a new call site:

```python
from backend.src.core import telemetry

telemetry.emit("category", "event.name", some_field=value)   # one-shot
with telemetry.span("native", "some_call", path=path):        # start/end/error
    risky_native_call()
```

`emit()`/`span()` are safe to call unconditionally — they no-op when
telemetry is disabled, and never raise.

## The analysis tools: `tool analyze` / `tool tui` / `tool watch`

```bash
python -m tool list                    # available sessions
python -m tool analyze                 # latest file, full report
python -m tool analyze PATH [--tail 40] [--category native]
python -m tool tui [PATH|--pid N] [--view timeline|crash|concurrency|memory|flame|live]
python -m tool watch [PATH|--pid N]    # btop-style live face
```

The report/TUI merge every thread's events into one time-ordered timeline
and flag two things this investigation kept needing: **orphaned spans** (a
`span()` whose `.start` was recorded but never got an `.end`/`.error` —
direct evidence of which native call was in flight at the moment of a
fault) and **overlapping scanner-thread windows** (two
`ImageScannerWorker`/`VideoScannerWorker` lifetimes overlapping — the shape
every root-cause theory in the crash doc has pointed at).

`tool/debug/` keeps the original `debugtool` public API
(`open_session`, `list_sessions`, `render_session_view`, `run_tui`) and the
human-readable `analyzer.py` report generator as their own small
subpackage, distinct from the host's own `model`/`queries`/`ui` — the
former standalone `debugtool` package's identity, not deleted, just no
longer a separate top-level import.

## The crash-capture tool: `tool repro` / `run_with_gdb.sh`

```bash
python -m tool repro --scenario media-loader-stress
python -m tool repro -- backend/main.py --no-dropdown   # any command
IMAGE_TOOLKIT_TELEMETRY=1 dev/run_with_gdb.sh
```

`run_with_gdb.sh` runs `backend/main.py` under `gdb -batch`, stopping
**only on SIGABRT** — glibc's malloc-corruption abort, the
`corrupted size vs. prev_size` crash this tool exists for — and dumping an
all-thread backtrace to
`~/.image-toolkit/telemetry/gdb-backtrace-<timestamp>.txt`, then
re-delivering the same signal so the JVM's own `hs_err_pid*.log` still gets
written (gdb stopping the process first would otherwise suppress it).

**SIGSEGV is deliberately left to pass through untouched**
(`handle SIGSEGV nostop noprint pass`) — HotSpot JVMs raise SIGSEGV *on
purpose* as part of normal operation (implicit null-pointer checks and
safepoint polling are both implemented by letting the CPU fault
intentionally, then the JVM's own installed handler catches it and
recovers). An earlier version of this script stopped on SIGSEGV too, which
made gdb intercept every one of these benign, self-handled JVM signals and
produced a misleading "the app crashes before the login window even opens"
symptom that never happens without gdb in the way — see Addendum 19 in the
crash doc for the full story. `libc6-dbg`/`python3-dbg` were never the
missing piece either — `just python` runs a uv-managed, already-unstripped
CPython build, not the system one debug-symbol packages would target.

Requires `gdb` installed (`sudo apt install gdb` on Debian/Ubuntu). Extra
arguments are forwarded to `backend/main.py`. The script raises the
core-dump size limit (`ulimit -c unlimited`) and collects any
`hs_err_pid*.log`/`core.<pid>` files into
`~/.image-toolkit/telemetry/` afterward (both `.gitignore`d, land in the
repo root otherwise).

## Resolving a Qt crash offset: `tool resolve-offset`

PySide6 ships its own private Qt build, fully stripped of local symbols —
`Problematic frame: C [libQt6Core.so.6+0x1e74d5]` in an `hs_err_pid*.log`
is as far as the JVM's own fatal-error handler gets on its own. The
*dynamic* symbol table survives stripping, though, and this resolves a raw
offset to its nearest enclosing exported C++ symbol using it:

```bash
python -m tool resolve-offset --hs-err ~/.image-toolkit/telemetry/hs_err_pid12345.log
python -m tool resolve-offset "libQt6Core.so.6+0x1e74d5"
```

This is exactly how Addendum 20 of the crash doc resolved two
long-mysterious crash offsets to `QObjectPrivate::ConnectionData::deleteOrphaned(...)`
and `QObjectPrivate::connect(...)` — confirming, for the first time with
hard evidence, that this crash class is a real QObject connection-list
corruption bug. Requires `nm`/`c++filt` (binutils — installed alongside
`gdb`/build-essential on most distros).

## Reproducing the gallery crash

Per the crash doc, the most reliable repro is: let the app auto-restore a
previously browsed directory on startup, then immediately (manually or via
the Wallpaper tab's browse button) switch to a directory containing videos
— image → video is the trigger; video → video or image → image has not
reproduced it.
