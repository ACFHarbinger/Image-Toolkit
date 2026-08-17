# Debug & Development Workbench Roadmap

*A session-oriented telemetry inspector, agent-queryable analysis API, and
repro/crash-capture harness for Image-Toolkit's own debug/telemetry work.*

**Status:** Active Collaboration (deepseek authored data engine; Gemini owns UI & TUI;
Harbinger is the product lead). Brainstormed and aligned on 2026-08-17.

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Architectural Scope & Decisions](#architectural-scope--decisions)
- [Relationship to Existing debug/ Tooling](#relationship-to-existing-debug-tooling)
- [Naming and Layout](#naming-and-layout)
- [Phase 1: Session Model + Queryable Analysis API (deepseek)](#phase-1-session-model--queryable-analysis-api-deepseek)
- [Phase 2: CLI + Export Surface (deepseek)](#phase-2-cli--export-surface-deepseek)
- [Phase 3: Visual Timeline & Interactive TUI Workbench (Gemini)](#phase-3-visual-timeline--interactive-tui-workbench-gemini)
- [Phase 4: Repro Harness + Crash-Capture Integration (deepseek + Gemini)](#phase-4-repro-harness--crash-capture-integration-deepseek--gemini)
- [Phase 5: Cross-Session Comparison + Trend Analysis (deepseek)](#phase-5-cross-session-comparison--trend-analysis-deepseek)
- [Cross-Cutting: Human/Agent Access Contract](#cross-cutting-humanagent-access-contract)
- [Decisions on Open Questions](#decisions-on-open-questions)
- [Implementation Status](#implementation-status)

---

## Why This Exists

Image-Toolkit's debugging work -- most visibly the 16+ round gallery-scan
native-crash investigation (deleteOrphaned/QSocketNotifier/glibc heap
corruption, see `debug/README.md`, `docs/TROUBLESHOOTING.md`, and
`.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`) -- has
produced a real instrumentation foundation:

- `backend/src/core/telemetry.py`: toggleable, dependency-light structured
  JSONL event logger (`emit`/`span`), enabled via
  `IMAGE_TOOLKIT_TELEMETRY=1`, flushing every line so a SIGABRT moments
  later still leaves the last completed event readable.
- `debug/telemetry_analyzer.py`: merges one file's events into a timeline,
  flags orphaned spans and overlapping scanner-thread windows.
- `debug/run_with_gdb.sh`: gdb batch capture on SIGABRT, all-thread
  backtrace, JVM hs_err preserved.
- `debug/resolve_qt_offset.py`: resolves stripped PySide6 Qt offsets to
  enclosing exported symbols (the tool that named `deleteOrphaned`).

What those tools do NOT do today, and what this roadmap builds:

1. **Sessions, not single files.** The analyzer only handles "the latest
   file". A real debugging workflow accumulates many runs (repro attempts,
   gdb relaunches, code-change iterations) and needs to treat one process
   launch as a first-class `Session`, groupable into named
   `Investigations`.
2. **Queryability for agents.** Each round of the crash investigation was
   bottlenecked on an agent or human re-reading JSONL by hand. This roadmap
   adds a stable, importable analysis API (`open_session()`,
   `.orphaned_spans()`, `.at(t)`, `.diff(other)`) so agents can
   programmatically inspect past runs without re-parsing.
3. **One harness for the whole repro flow.** `run_with_gdb.sh` +
   `telemetry_analyzer.py` + `resolve_qt_offset.py` + the `hs_err`
   files are currently separate manual steps. A `repro` command drives
   capture and emits one readable summary an agent can act on.
4. **Interactive High-Fidelity TUI.** Reading 100k-line JSONL dumps or text
   summaries hides concurrency races. A high-contrast Perfetto-style terminal
   visualizer makes multi-thread overlaps, orphaned spans, and latency spikes
   instantly scannable.

This is deliberately **general-purpose** (any telemetry category: startup
probes, worker threads, native call boundaries, memory RSS snapshots, scan
pipelines) -- not a crash-only tool. The gallery-crash workflow is the first
and most urgent user, not the only one.

---

## Architectural Scope & Decisions

Aligned on 2026-08-17 with Harbinger:

1. **Modality:** **TUI-First (Terminal User Interface)** with rich ANSI/Rich styling,
   designed to be visually stunning, responsive, and 100% terminal-native. Future
   extensibility hooks provided for optional PySide6/Tauri/React GUI frontends.
2. **Visual Design:** **Minimal High-Contrast Technical + Modern Trace Profiler**:
   Dark slate palette with monochromatic typographic hierarchy, combined with
   multi-track thread waterfall lanes, minimap scrub bar, span nesting trees, and
   high-visibility amber/rose alerts strictly for crashes, orphaned spans, and
   deadlocks.
3. **Four First-Class Prioritized Workflow Views**:
   - **Crash Forensics & Stack Splicer**: Correlates GDB backtraces, JVM `hs_err`,
     and in-flight spans at the exact microsecond of SIGSEGV/SIGABRT.
   - **Multi-Thread Race Condition & Concurrency Inspector**: Visualizes overlapping
     worker windows, lock contention, and background collisions (e.g. scanner
     threads vs Qt event loop).
   - **Memory Leak & RSS Trend Profiler**: Step-by-step memory deltas and RSS growth
     across batch operations and lifecycle allocation steps.
   - **Pipeline Stage Latency & Flamegraph Breakdown**: Microsecond-precision
     hierarchical flame-charts for image conversion, LoFTR matching, and stitching.
4. **Persistence & Sharing:** **Named Investigations with Exportable Workspaces**:
   Group PID runs into self-contained investigation directories (e.g.
   `debug/investigations/gallery_crash_01/`) with checked-in repro scripts and
   manifest metadata for seamless agent/human collaboration.
5. **Execution Mode:** **Hybrid**: Post-mortem by default over finished/crashed runs,
   with opt-in live tail streaming (`debugtool watch [--pid <PID> | --latest]`) for
   active repro runs.

---

## Relationship to Existing debug/ Tooling

Per Harbinger's answer (full consolidation), the new tool supersedes the
standalone scripts while preserving their behavior:

| Existing artifact | New home | Notes |
|---|---|---|
| `debug/telemetry_analyzer.py` | `debugtool.analyzer` module + `debugtool analyze` CLI | Logic generalized (sessions, span trees, derived queries); the two original detectors (orphaned spans, scanner overlaps) remain as named queries with identical output shape |
| `debug/run_with_gdb.sh` | `debugtool repro` (invokes gdb) + documented wrapper | Same gdb flags, SIGABRT-only stop, hs_err preservation; gains telemetry session auto-attach and summary output |
| `debug/resolve_qt_offset.py` | `debugtool resolve-offset` subcommand | Same nm/c++filt resolution; gains `--hs-err` scan of the session's captured files |
| `debug/README.md` | Kept, updated with a pointer to the new tool | The crash-context narrative stays; the how-to-use section points to `debugtool` |

---

## Naming and Layout

- **Package & CLI Name:** `debugtool` (`python -m debugtool` or `debugtool`).
- **Product Title:** **Debug & Development Workbench**.

Proposed layout (under `debug/`):

```
debug/
  debugtool/
    __init__.py          # public API: open_session, open_investigation, discover
    model/
      session.py         # Session: pid-run abstraction, load/parse/validate
      span.py            # Span tree reconstruction from start/end/error events
      event.py           # Typed event registry (known categories/events)
      investigation.py   # Named container grouping multiple sessions
    queries/
      timeline.py        # time-ordered merged timeline, slice, in-flight-at-t
      spans.py           # orphaned spans, span stats, nesting
      overlaps.py        # generalized thread-window overlap detection
      diff.py            # cross-session comparison
      memory.py          # RSS snapshot trend
    export/
      json_sidecar.py    # stable JSON export (per analytics contract)
      html.py            # standalone single-file HTML report
      csv.py             # flat event export for spreadsheets
    ui/
      app.py             # TUI application lifecycle & view router
      renderer.py        # Terminal ANSI / Rich rendering canvas
      views/
        timeline.py      # Multi-track thread waterfall + minimap scrub bar
        crash.py         # Crash forensics & GDB/JVM trace correlation
        concurrency.py   # Overlap matrix & lock contention inspector
        memory.py        # Memory & RSS trend visualization
        flame.py         # Latency breakdown flamegraph
        live_tail.py     # Real-time streaming watcher
    cli/
      main.py            # argparse: analyze / list / repro / diff / export / tui / watch / prune
    analyzer.py          # thin re-export of the original analyzer logic
  investigations/        # Portable self-contained named investigation folders
  telemetry_analyzer.py  # kept as a shim -> debugtool analyze (deprecation notice)
  run_with_gdb.sh        # kept, now the underlying capture for 'debugtool repro'
  resolve_qt_offset.py   # kept, imported by debugtool resolve-offset
  README.md              # updated
```

The index (session list, per-file stats) lives as a sidecar JSON next to the
telemetry files (`~/.image-toolkit/telemetry/index.json`); the JSONL files
remain the source of truth (parsed on demand).

---

## Phase 1: Session Model + Queryable Analysis API (deepseek)

**Goal:** treat every `telemetry-<pid>.jsonl` as a `Session`, expose a
typed, importable API for the queries the crash investigation (and general
debugging) needs, and migrate the analyzer's logic without changing its
output for existing files.

### Scope

1. **`Session` model** (`model/session.py`):
   - Discover sessions from `~/.image-toolkit/telemetry/telemetry-*.jsonl`
     (or an explicit path/pid).
   - Parse with the same truncated-final-line tolerance as the current
     analyzer (a crashed run's partial last line is expected, not an error).
   - Metadata: pid, wall-clock start/end, event count, per-category counts,
     threads observed, file size, whether the file looks crashed (truncated
     final line).
   - `open_session(pid=None, path=None)` -> `Session`; `list_sessions()`
     -> index of available sessions.
2. **Span-tree reconstruction** (`model/span.py`):
   - Generalize `find_orphaned_spans` to a full nesting model: walk
     `<event>.start` / `<event>.end` / `<event>.error` per
     (tid, category, base-name), build a tree with durations, and expose
     orphaned leaves (started, never ended) as the crash-in-flight detector.
   - Keep the original orphaned-span query's semantics identical for
     backward compatibility.
3. **Typed event registry** (`model/event.py`):
   - Catalog known categories/events (thread-lifecycle, native, probe,
     scan, memory, jvm, ...) and their known fields, so the tool renders
     them meaningfully and queries can filter by type. Unknown events are
     preserved verbatim (never dropped), matching the analytics contract's
     "preserve unknown fields" rule.
4. **Derived queries** (`queries/`):
   - `timeline()`: merged, time-ordered, per-thread events (superset of
     the analyzer's `print_report` timeline).
   - `at(t)`: what events/spans were in flight at wall/monotonic time t
     (the "what crashed mid-call" question, made queryable).
   - `overlaps()`: generalized thread-window overlap detection -- any
     worker/lifecycle start/end pairs, not just scanner threads (the
     original scanner detector remains as a named filter).
   - `stats()`: per-category/per-thread counts, durations, anomalies
     (very slow spans, many retries).
5. **Migrate analyzer logic** (`analyzer.py` + `debugtool analyze` CLI):
   - `debugtool analyze [path|--pid N]` reproduces the current
     `telemetry_analyzer.py` full report exactly (counts by category,
     threads, orphaned spans, scanner overlaps, last 15 events), then adds
     the new queries.
   - `telemetry_analyzer.py` becomes a thin shim printing a deprecation
     notice pointing at `debugtool analyze`.

### Acceptance criteria

- `open_session()` / `list_sessions()` work against real and synthetic files.
- `session.orphaned_spans()` returns the exact same set as `find_orphaned_spans`.
- `session.at(t)` returns in-flight spans/events for a mid-span timestamp.
- `debugtool analyze` output is byte-compatible with `telemetry_analyzer.py`.
- **Status:** ✅ **Landed by deepseek (commit `431163b7`), 19/19 tests passing.**

---

## Phase 2: CLI + Export Surface (deepseek)

**Goal:** make the tool usable from a terminal by both humans and agents,
and emit stable, machine-readable exports.

### Scope

1. **CLI surface** (`cli/main.py`):
   - `debugtool list` -- list sessions with metadata (size, mtime, crash flag, categories).
   - `debugtool analyze [path|--pid] [--tail N] [--category X]` -- the migrated report.
   - `debugtool diff A B` -- cross-session comparison.
   - `debugtool export [path|--pid] --format json|csv|html [--out PATH]`.
   - `debugtool resolve-offset "libQt6Core.so.6+0x1e74d5"` (wraps `resolve_qt_offset.py`).
   - `debugtool prune [--keep N] [--older-than Xd]` -- retention cleanup.
2. **Export surface** (`export/`):
   - `json_sidecar()`: versioned JSON matching the analytics dual-access contract.
   - `csv()`: flat event dump for external spreadsheet analysis.
   - `html()`: standalone zero-dependency HTML timeline report.
3. **Sidecar index** (`~/.image-toolkit/telemetry/index.json`):
   - Cached session list + per-file stats, rebuilt lazily when the telemetry dir changes.

### Acceptance criteria

- `debugtool export --format json` emits a valid JSON sidecar.
- `debugtool export --format html` opens in a browser with no JS build step.
- CLI help is complete; tests cover all subcommands.

---

## Phase 3: Visual Timeline & Interactive TUI Workbench (Gemini)

**Goal:** build a rich, interactive, terminal-native visual workbench that
renders multi-track thread timelines, isolates crash forensic data, and inspects
concurrency and memory anomalies in real-time.

### Scope & Views

1. **Interactive TUI Architecture (`ui/`):**
   - Built on `rich` with custom high-speed ANSI canvas renderers.
   - Keyboard shortcuts: `Tab` (switch view), `j/k` / `Up/Down` (navigate spans),
     `Enter` (drill down), `z/x` (zoom timeline), `/` (search/filter), `w` (toggle live watch).
   - Minimal high-contrast technical aesthetic: dark slate container cards,
     monochromatic typography, vibrant amber for orphaned spans, rose for SIGSEGV/SIGABRT.
2. **Four Dedicated TUI Views:**
   - **Timeline & Waterfall (`ui/views/timeline.py`):**
     - Multi-track thread lanes with visual span duration bars (`[■■■■■■■] 142ms`).
     - Minimap scrub bar displaying overall session density and anomaly flags.
     - Expandable hierarchical span tree with microsecond entry/exit timestamps.
   - **Crash Forensics Splicer (`ui/views/crash.py`):**
     - Side-by-side correlation: GDB all-thread stack traces + JVM `hs_err` + in-flight telemetry span.
     - Displays exact native offset resolution (e.g. `libQt6Core.so.6+0x1e74d5 -> deleteOrphaned`).
   - **Concurrency & Overlap Inspector (`ui/views/concurrency.py`):**
     - Thread collision matrix flagging dangerous concurrent windows (e.g. scanner thread vs UI thread).
     - Lock acquisition / contention visualizer.
   - **Memory & Latency Breakdown (`ui/views/memory.py` & `ui/views/flame.py`):**
     - RSS snapshot step chart over lifecycle events.
     - Hierarchical flame-chart for pipeline execution bottlenecks.
3. **Live Watch Mode (`ui/views/live_tail.py`):**
   - `debugtool watch [--pid <PID> | --latest]`: Non-blocking JSONL tailer updating the TUI in real-time.

### Acceptance criteria

- `debugtool tui [--pid N | PATH]` launches interactive TUI rendering session timeline within 50ms.
- Orphaned spans, overlaps, and crash events are highlighted and navigable via keyboard.
- Live watch mode streams active runs without flickering or blocking process execution.
- Tests: `debug/test/test_debugtool_tui.py` (headless terminal rendering tests).

---

## Phase 4: Repro Harness + Crash-Capture Integration (deepseek + Gemini)

**Goal:** one command that drives a reproduction run with capture and
emits a readable summary, so a crashing repro becomes a self-documenting
artifact an agent can act on.

### Scope

1. **`debugtool repro [--scenario NAME] [-- args...]`**:
   - Launches target command with `IMAGE_TOOLKIT_TELEMETRY=1`.
   - Wraps launch under `gdb` (SIGABRT/SIGSEGV trap, all-thread backtrace, hs_err preservation).
   - Post-run analysis emits a structured summary: session path, orphaned spans,
     overlaps, GDB stack traces, and natural-language root-cause hypothesis.
2. **Cross-Referencing & TUI Integration**:
   - Automatically opens the produced crash artifact in `debugtool tui --view crash`.
   - Generates shareable investigation workspace under `debug/investigations/<name>/`.

### Acceptance criteria

- `debugtool repro` on synthetic crashing test produces telemetry JSONL, GDB backtrace,
  and highlights the in-flight span.
- Works headless in CI and interactively in development.

---

## Phase 5: Cross-Session Comparison + Trend Analysis (deepseek)

**Goal:** answer "what changed between runs" and "is memory growing across runs".

### Scope

1. **`diff(a, b)` (`queries/diff.py`):**
   - Event-set diff: added, removed, and changed events between sessions.
   - Timing deltas on matching span signatures.
   - Structural regressions: newly orphaned spans, new thread collisions.
2. **Memory Trend (`queries/memory.py`):**
   - RSS trajectory across sequential runs in an investigation.
3. **Investigation Container (`model/investigation.py`):**
   - Portable workspace directory under `debug/investigations/<name>/`.
   - Contains `manifest.json` referencing session IDs, repro scripts, and reviewer notes.

### Acceptance criteria

- `debugtool diff A B` accurately highlights event, timing, and span deltas.
- Investigation manifests export and import across checkouts without data loss.

---

## Cross-Cutting: Human/Agent Access Contract

This tool IS the debugging half of the project's dual human/agent access
pattern (see [`analytics_and_interpretability.md`](analytics_and_interpretability.md)):

- Every export/summary emits: a stable versioned JSON sidecar, a short
  natural-language summary, and (optional) flat CSV.
- **Privacy/scope:** telemetry is local and never published by default; export
  sidecars include privacy classification tags.
- **Agents are first-class consumers:** `debugtool` exposes a stable
  importable Python API for automated agents. The CLI and TUI are clean
  consumers over the API.

---

## Decisions on Open Questions

1. **Sessions cleanup policy:** Settle with **`debugtool prune --keep <N>`** (default 50) and
   **`debugtool prune --older-than <Xd>`** (default 14d) with confirmation prompt.
2. **Investigation persistence:** Settle on **Portable Investigation Folders** in
   `debug/investigations/<name>/` containing `manifest.json`, associated telemetry captures,
   and repro scripts, checked into git or shared across machines.
3. **`debugtool repro` scope:** Drives both the **repro scenario execution** and the
   **telemetry/gdb/hs_err capture pipeline**, outputting a consolidated diagnostic report.
4. **Parquet timing:** **Deferred to v2**. JSONL + sidecar JSON index is lightweight,
   human-readable, and sufficient for current multi-gigabyte session volumes.
5. **Tool & Product Naming:** Package / CLI name is **`debugtool`**; human-facing product
   title is **Debug & Development Workbench**.

---

## Implementation Status

| Phase | Status | Owner | Details |
|---|---|---|---|
| **Phase 1: Session model + queryable API** | ✅ **Complete** | deepseek | `debugtool` package, session parser, span tree, 19/19 tests (`431163b7`) |
| **Phase 2: CLI + export surface** | 🔄 **In Progress** | deepseek | `debugtool analyze/list/export/resolve-offset/prune` |
| **Phase 3: Visual timeline & TUI workbench** | 🔄 **In Progress** | Gemini | Rich TUI, Perfetto-style lanes, Crash/Concurrency/Memory views, Live Watch |
| **Phase 4: Repro harness + crash capture** | ⬜ **Planned** | deepseek + Gemini | `debugtool repro`, GDB/JVM stack trace splicer, automated NL summary |
| **Phase 5: Cross-session diff + trends** | ⬜ **Planned** | deepseek | Session diffing, RSS trend analyzer, `debug/investigations/` container |

Existing foundation:

| Artifact | Status |
|---|---|
| `backend/src/core/telemetry.py` (JSONL logger) | ✅ Complete |
| `debug/telemetry_analyzer.py` (orphaned spans / overlaps) | ✅ Complete (migrated to `debugtool.analyzer`) |
| `debug/run_with_gdb.sh` (SIGABRT capture) | ✅ Complete (wrapped by Phase 4) |
| `debug/resolve_qt_offset.py` (Qt offset resolution) | ✅ Complete (wrapped by Phase 2) |
