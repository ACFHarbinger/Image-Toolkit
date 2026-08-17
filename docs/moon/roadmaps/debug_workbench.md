# Debug & Development Workbench Roadmap

*A session-oriented telemetry inspector, agent-queryable analysis API, and
repro/crash-capture harness for Image-Toolkit's own debug/telemetry work.*

**Status:** Draft for team review (deepseek authored; Gemini owns the UI half;
Harbinger is the product lead). See the AGENT_BUS debug/ tool track (2026-08-17).

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Scope: What "debug tool" Means Here](#scope-what-debug-tool-means-here)
- [Relationship to Existing debug/ Tooling](#relationship-to-existing-debug-tooling)
- [Naming and Layout](#naming-and-layout)
- [Phase 1: Session Model + Queryable Analysis API (deepseek)](#phase-1-session-model--queryable-analysis-api-deepseek)
- [Phase 2: CLI + Export Surface (deepseek)](#phase-2-cli--export-surface-deepseek)
- [Phase 3: Visual Timeline UI (Gemini)](#phase-3-visual-timeline-ui-gemini)
- [Phase 4: Repro Harness + Crash-Capture Integration (deepseek + Gemini)](#phase-4-repro-harness--crash-capture-integration-deepseek--gemini)
- [Phase 5: Cross-Session Comparison + Trend Analysis (deepseek)](#phase-5-cross-session-comparison--trend-analysis-deepseek)
- [Cross-Cutting: Human/Agent Access Contract](#cross-cutting-humanagent-access-contract)
- [Open Questions for Harbinger](#open-questions-for-harbinger)
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
   files are currently separate manual steps. A `repro` command should
   drive capture and emit one readable summary an agent can act on.

This is deliberately **general-purpose** (any telemetry category: startup
probes, worker threads, native call boundaries, memory RSS snapshots, scan
pipelines) -- not a crash-only tool. The gallery-crash workflow is the first
and most urgent user, not the only one.

---

## Scope: What "debug tool" Means Here

A debug/telemetry workbench with two halves:

- **Analysis/data-model half (deepseek):** session/run abstraction over
  `telemetry-<pid>.jsonl` files, span-tree reconstruction, typed event
  registry, derived queries, cross-run comparison, export surface, and a
  stable importable Python API. Headless CLI + API first.
- **UI/visualization half (Gemini):** a real interface over that data
  (timeline view, span/thread comparison, filtering). Modality is Gemini's
  call (terminal TUI / local web view / PySide6 window) -- match whatever is
  most useful for actually debugging a crash, not whatever is most
  impressive. Visual style: minimal technical (plain, high-contrast,
  terminal-friendly), per Harbinger's answer.

In scope:

- Session discovery, loading, and a typed query model.
- Span-tree reconstruction (generalizing the analyzer's orphaned-span
  detection to full nesting).
- Derived queries: timeline slice, in-flight-at-t, generalized thread-window
  overlap (not just scanner threads), per-category stats.
- Cross-run diff: which events/timing/overlaps changed between two sessions.
- Memory/leak trend: RSS snapshots (already emitted by lifecycle_memory)
  across sessions.
- Export: stable JSON/CSV/HTML sidecars + a small consumer API.
- Repro harness integration: `repro` command driving telemetry + gdb +
  hs_err capture and emitting a summary.
- Consolidation: `telemetry_analyzer.py`'s logic moves into the new tool
  (per Harbinger: full consolidation); `run_with_gdb.sh` and
  `resolve_qt_offset.py` become subcommands/importable modules of the new
  tool (wrapped, their hard-won behavior preserved).

Out of scope for v1:

- Any change to `backend/src/core/telemetry.py`'s on-disk JSONL schema
  (backward compatible additions allowed; the existing crash-sensitive call
  sites and the `flush`-after-every-line invariant are untouchable).
- A live in-process debugger / profiler. This tool is a post-hoc analyzer
  of captured telemetry, not a runtime tracer.
- GUI integration inside the main app (a debug menu toggle is a possible
  later nicety, not v1).

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

Tool name: **`debugtool`** (importable package + `python -m debugtool` CLI).
Harbinger left the name to the author; `debugtool` matches the directory and
reads clearly in commands (`debugtool analyze --session 123`).

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
      html.py            # simple standalone HTML report (Gemini can restyle)
      csv.py             # flat event export for spreadsheets
    cli/
      main.py            # argparse: analyze / list / repro / diff / export / resolve-offset
    analyzer.py          # thin re-export of the original analyzer logic
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

- `open_session()` / `list_sessions()` work against the real
  `~/.image-toolkit/telemetry/` files and against a temp dir of synthetic
  files.
- `session.orphaned_spans()` returns the same set as the current
  `find_orphaned_spans` on the same input (regression-checked against the
  existing analyzer output).
- `session.at(t)` returns in-flight spans/events for a mid-span timestamp.
- `debugtool analyze` output is byte-compatible with
  `telemetry_analyzer.py` for the same file (modulo the header/version
  line).
- Tests: `debug/test/test_debugtool_session.py`,
  `test_debugtool_queries.py`, `test_debugtool_analyze_compat.py`
  (focused, no GUI).

---

## Phase 2: CLI + Export Surface (deepseek)

**Goal:** make the tool usable from a terminal by both humans and agents,
and emit stable, machine-readable exports.

### Scope

1. **CLI surface** (`cli/main.py`):
   - `debugtool list` -- list sessions with metadata (size, mtime, crash
     flag, categories).
   - `debugtool analyze [path|--pid] [--tail N] [--category X]` -- the
     migrated report.
   - `debugtool diff A B` -- cross-session comparison (Phase 5 logic, but
     the CLI lands here).
   - `debugtool export [path|--pid] --format json|csv|html [--out PATH]`.
   - `debugtool resolve-offset "libQt6Core.so.6+0x1e74d5"` (wraps
     `resolve_qt_offset.py`).
2. **Export surface** (`export/`):
   - `json_sidecar()`: versioned JSON per the analytics dual-access
     contract (see Cross-Cutting below) -- stable core fields plus the
     session's event/spans in a queryable shape.
   - `csv()`: flat event dump for external tools.
   - `html()`: a dependency-free standalone HTML report (styled minimally;
     Gemini may restyle later). This is the first thing a human (Harbinger)
     can open without the terminal.
3. **Sidecar index** (`~/.image-toolkit/telemetry/index.json`):
   - Cached session list + per-file stats, rebuilt lazily when the telemetry
     dir changes (mtime-based). Not a database; JSONL stays authoritative.

### Acceptance criteria

- `debugtool export --format json` emits a valid JSON sidecar matching the
  analytics contract core (artifact_id, producer/version, source run IDs,
  metric definitions where applicable).
- `debugtool export --format html` opens in a browser and shows the
  timeline, orphaned spans, and overlaps without any JS build step.
- CLI help is complete; unknown subcommands error with usage.
- Tests: `test_debugtool_cli.py`, `test_debugtool_export.py`.

---

## Phase 3: Visual Timeline UI (Gemini)

**Goal:** a real interface over the session model -- the human-facing half
that makes a crash's shape visible without reading JSONL.

### Scope

1. Modality (Gemini's call, matching "most useful for debugging a crash"):
   - Option A: terminal TUI (rich per-thread timeline, keybindings to
     expand/collapse spans, jump to orphaned spans).
   - Option B: local web view serving the exported HTML/JSON (reuse the
     ratings-dashboard design instinct, adapted to the minimal-technical
     style).
   - Option C: PySide6 window (heaviest; least likely v1).
2. Views over the session model (all already available via the Phase 1/2
   API, so the UI is a pure consumer):
   - Per-thread timeline with span nesting and duration bars.
   - Orphaned-span highlight (crash in-flight marker).
   - Thread-window overlap visualization.
   - Cross-session diff view (Phase 5 data, rendered here).
   - Memory/RSS trend line (Phase 5 data).
3. Visual style: minimal technical -- plain, high-contrast, terminal-
   friendly; a muted single accent for anomalies (e.g. amber for orphaned
   spans). No heavy charting library; hand-rolled SVG/canvas or plain text
   blocks, matching the project's established "dependency-free where
   possible" pattern.

### Acceptance criteria

- The UI opens a session by pid/path and renders the merged timeline.
- Orphaned spans and overlaps are visually distinct and one keypress/click
  from the event details.
- The UI works from a fresh checkout (no undocumented install step beyond
  the project's existing venv).
- Gemini owns this phase's file layout and any `debugtool ui` entry point;
  the data API is already settled by Phase 1/2 so the two halves do not
  block each other.

---

## Phase 4: Repro Harness + Crash-Capture Integration (deepseek + Gemini)

**Goal:** one command that drives a reproduction run with capture and
emits a readable summary, so a crashing repro becomes a self-documenting
artifact an agent can act on.

### Scope

1. **`debugtool repro [-- args...]`**:
   - Launches `backend/main.py` (or an explicit command) with
     `IMAGE_TOOLKIT_TELEMETRY=1`.
   - If gdb is available, wraps the launch per `run_with_gdb.sh` (SIGABRT
     only, all-thread backtrace, hs_err preserved, core dumps collected).
   - On exit (crash or clean), runs the analysis over the produced
     session and emits a **summary**: session path, event counts, orphaned
     spans, overlaps, last N events, gdb/hs_err file paths, and a
     one-paragraph natural-language read (per the analytics contract's
     required NL summary).
   - Exit code reflects crash vs clean for scripting.
2. **Cross-referencing**:
   - Correlate the telemetry session with the gdb backtrace and hs_err file
     by timestamp/pid (the README already describes this correlation
     manually; automate it).
   - `debugtool repro --summary` output is the agent-facing artifact.

### Acceptance criteria

- `debugtool repro` on a known-crashing repro (or a synthetic
  SIGABRT-in-span test) produces: telemetry JSONL, gdb backtrace (if gdb
  present), hs_err/core (if JVM involved), and a summary line that names
  the orphaned span in flight.
- Works headless (no display) for the non-GUI portions; GUI repro remains
  opt-in via flags.
- Tests: `test_debugtool_repro.py` (synthetic crash fixture, no real
  gdb/JVM needed -- the capture path is exercised with a mock gdb).

---

## Phase 5: Cross-Session Comparison + Trend Analysis (deepseek)

**Goal:** answer "what changed between runs" and "is memory growing across
runs" -- the questions a multi-round investigation asks every time.

### Scope

1. **`diff(a, b)`** (`queries/diff.py`):
   - Event-set diff: events added/removed/changed between two sessions
     (matched by (tid, category, event, wall) where comparable).
   - Timing deltas: same span's duration across runs.
   - Structural deltas: newly orphaned spans, newly overlapping windows,
     new categories/threads.
   - A short natural-language summary of the differences.
2. **Memory trend** (`queries/memory.py`):
   - Collect RSS snapshots (already emitted by
     `lifecycle_memory`/`backend/src/core/lifecycle_memory.py`) across
     sessions in an investigation; report growth/plateau/spikes.
3. **Investigation container** (`model/investigation.py`):
   - A named, user-created group of sessions (e.g. "round-27 repro"),
     persisted as a small JSON manifest in the telemetry dir. Sessions can
     belong to multiple investigations.
   - CLI: `debugtool investigation create NAME`,
     `debugtool investigation add NAME --pid N`, `debugtool investigation
     diff NAME`.

### Acceptance criteria

- `diff` on two synthetic sessions reports at least one added, removed,
  and changed event correctly, and flags a newly orphaned span.
- Memory trend surfaces the known RSS steps from synthetic snapshot data.
- Investigation manifest round-trips (create/add/list/diff) without data
  loss.
- Tests: `test_debugtool_diff.py`, `test_debugtool_memory.py`,
  `test_debugtool_investigation.py`.

---

## Cross-Cutting: Human/Agent Access Contract

This tool IS the debugging half of the project's dual human/agent access
pattern (see the existing contract in
[`analytics_and_interpretability.md`](analytics_and_interpretability.md)
-- this roadmap adopts it rather than duplicating it):

- Every export/summary emits: a stable versioned JSON sidecar, a short
  natural-language summary, and (only when the result is a non-trivial
  tabular/event collection) Parquet. Telemetry sessions are exactly the
  "non-trivial event collection" case where Parquet may be worth it for
  large runs; v1 stays JSON-first.
- **Privacy/scope:** telemetry may contain paths, directories, and video
  paths that are private to the local machine. Debug artifacts are local
  and never published by default; the export sidecar includes a privacy
  classification field and anonymization is the agent's responsibility
  before sharing any report externally.
- **Agents are first-class consumers:** `debugtool` exposes a stable
  importable API specifically so future debugging sessions (and other
  agents) can query past runs programmatically. The CLI is a thin wrapper
  over the API, never the only interface.

---

## Open Questions for Harbinger

1. **Sessions cleanup policy:** telemetry files accumulate unboundedly.
   Should `debugtool` offer a retention/prune command (e.g. keep last N,
   or delete sessions older than X with a flag), or leave cleanup entirely
   manual?
2. **Investigation naming/persistence:** the named-investigation manifest
   lives in `~/.image-toolkit/telemetry/`. Fine for a single machine, or
   should investigations be portable (checked-in JSON next to a repro
   script) so a repro is self-describing?
3. **`debugtool repro` scope:** should the repro command also drive the
   *reproduction scenario* (e.g. auto-open a directory switch) or only the
   capture pipeline around a command we already know how to run?
4. **Parquet timing:** adopt Parquet export in v1 for large sessions, or
   defer until the JSON sidecar proves insufficient (recommended: defer)?
5. **Tool/UI naming:** `debugtool` for the package/CLI is my proposal.
   If Gemini's UI wants a friendlier product name, that's UI-only; the API
   name can stay stable.

---

## Implementation Status

| Phase | Status | Owner |
|-------|--------|-------|
| Phase 1: Session model + queryable API | ⬜ Not started | deepseek |
| Phase 2: CLI + export surface | ⬜ Not started | deepseek |
| Phase 3: Visual timeline UI | ⬜ Not started | Gemini |
| Phase 4: Repro harness + crash-capture integration | ⬜ Not started | deepseek + Gemini |
| Phase 5: Cross-session comparison + trends | ⬜ Not started | deepseek |

Existing foundation (not part of the phases, already shipped):

| Artifact | Status |
|----------|--------|
| `backend/src/core/telemetry.py` (JSONL logger) | ✅ Complete |
| `debug/telemetry_analyzer.py` (orphaned spans / overlaps) | ✅ Complete (to be superseded by Phase 1 migration) |
| `debug/run_with_gdb.sh` (SIGABRT capture) | ✅ Complete (to be wrapped by Phase 4) |
| `debug/resolve_qt_offset.py` (Qt offset resolution) | ✅ Complete (to be wrapped by Phase 2 CLI) |
