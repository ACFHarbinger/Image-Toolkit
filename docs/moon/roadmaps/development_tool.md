# Development Tool Roadmap

*A modular, repo-agnostic Tauri dev app — telemetry, crash forensics,
benchmarks, 2D/3D visualization, and plugin-backed evaluators — usable
across Image-Toolkit and other repos.*

**Status:** v1 (Python/PySide6-plugin-CLI shape) **Locked and shipped**
(2026-08-17, D1–D40). **v2 (Tauri rewrite, multi-repo, 2D/3D/4D
visualization) brainstormed with Harbinger 2026-08-18 (D41–D47) — open for
the team's cross-review pass before implementation starts.** See the new
[Development Tool v2](#development-tool-v2-2026-08-18)
section below for full scope; v1's sections stay as history/reference, not
superseded wholesale — most of v1's plugin *content* (ASP evaluator,
benchmarks, telemetry model) carries forward per D42, only the shell/host
is being rewritten.
**Product lead:** Harbinger.  
**This pass:** Grok (feasibility + product fold), Chat/Codex (D24-D37
product-design pass), Claude (D38-D39 close-out + GitHub issue/project
creation; D41-D47 v2 brainstorm). Prior authors of folded docs: deepseek (debug data engine),
Gemini (TUI), plus the analytics / glossary authors.

This file **replaces** and folds:

| Former file | Fate |
|---|---|
| `docs/moon/roadmaps/debug_workbench.md` | Folded into Track A; deleted |
| `docs/moon/roadmaps/analytics_glossary.md` | Folded into [Glossary](#glossary); deleted |
| `docs/moon/roadmaps/analytics_and_interpretability.md` | Folded into Track B; deleted |

**Review request:** @deepseek @Gemini @Claude — please edit this file in
place. Do not resurrect the three deleted files. Dissent in a dated
subsection under [Team review notes](#team-review-notes).

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Product Vision](#product-vision)
- [Settled Decisions (2026-08-17)](#settled-decisions-2026-08-17)
- [Development Tool v2 (2026-08-18)](#development-tool-v2-2026-08-18)
- [Glossary](#glossary)
- [Dual Human / Agent Access Contract](#dual-human--agent-access-contract)
- [Home: the `dev/` directory](#home-the-dev-directory)
- [Relationship to Existing Tooling](#relationship-to-existing-tooling)
- [Visual Language](#visual-language)
- [Architecture](#architecture)
- [Track A — Telemetry & Crash Workbench](#track-a--telemetry--crash-workbench)
- [Track B — Analytics, Benchmarks & Interpretability](#track-b--analytics-benchmarks--interpretability)
- [Track C — Host, Plugins, MCP, Local Web](#track-c--host-plugins-mcp-local-web)
- [Track D — Development Assistance](#track-d--development-assistance-d16)
- [Implementation Status](#implementation-status)
- [Open Questions for Team Review](#open-questions-for-team-review)
- [Team Review Notes](#team-review-notes)
- [Effort × Impact Matrix](#effort--impact-matrix)
- [Anchor Index](#anchor-index)

---

## Why This Exists

Image-Toolkit's debugging work — most visibly the 16+ round gallery-scan
native-crash investigation (`deleteOrphaned` / `QSocketNotifier` / glibc
heap corruption; see `dev/README.md`, `docs/TROUBLESHOOTING.md`, and
`.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`) — produced a
real instrumentation foundation (paths below are post-D40; `debug/` no
longer exists as a separate directory):

- `backend/src/core/telemetry.py`: toggleable JSONL logger (`emit` /
  `span`), `IMAGE_TOOLKIT_TELEMETRY=1`, flush-every-line so a SIGABRT a
  moment later still leaves the last completed event.
- `dev/telemetry_analyzer.py` → a shim over `tool.debug`.
- `dev/run_with_gdb.sh`: gdb batch capture on SIGABRT; JVM `hs_err`
  preserved.
- `dev/resolve_qt_offset.py`: stripped PySide6 offsets → exported
  symbols (the tool that named `deleteOrphaned`).
- `dev/tool/debug/`: the original Phase 1 session model
  (`open_session`, orphaned spans, in-flight-at-t, overlaps), landed by
  deepseek (`431163b7`), preserved as its own subpackage after D40's fold.

Separately, the project already has a second mature developer surface:
ASP's benchmark evaluator (`submodules/ASP/backend/benchmark/evaluation/`
— session/discovery, comparison/annotation UI, plugin/export, own
schema). And a third: the analytics / interpretability roadmap (math
backbones, Phase 11–12 benchmark diagnostics, many still-planned
visualisation phases).

Those three families were specified in different documents and lived in
different directories. Harbinger's 2026-08-17 direction is that they are
**one product**: a modular development application whose first-party and
third-party pieces (telemetry inspector, crash splicer, ASP evaluator,
benchmark charts, future analytics views) load as **plugins** against a
shared host.

What the current pieces do **not** do, and what this roadmap builds:

1. **One host, many plugins.** The ASP evaluator is the complexity
   reference, not a one-off. It should become a plugin rather than a
   second standalone app the team has to remember.
2. **Sessions and investigations, not single files.** One process launch
   is a `Session`. Named `Investigation` folders group runs, gdb traces,
   and reviewer notes.
3. **Queryability for agents.** `open_session()` plus a local MCP / stdio
   server so agents do not re-parse JSONL or scrape a TUI.
4. **Pixels where they exist.** Crash dumps are text; ASP and benchmarks
   are images and plots. TUI for traces; a local web view for anything
   with pixels. The public website is **not** this tool.
5. **Two visual densities.** Perfetto-style for static / post-mortem
   analysis. btop-style for live watch.

---

## Product Vision

A **fully modular development application** in `dev/`.

It captures and displays telemetry (including stack traces) **and**
charts / plots / model-benchmark results. Domain tools such as the ASP
benchmark evaluator attach as plugins. A plugin may target the TUI, the
local web view, a future GUI host, or any combination.

**Primary job that wins scope arguments (Harbinger):** equal dual
audience. Harbinger uses the TUI and the local web view. Agents use the
same Session / Investigation / plugin APIs and the MCP server. A feature
that only one audience can consume is unfinished.

**Delivery order (Harbinger):** make benchmark evidence useful first, then
agentic debugging, then the broader human/developer crash-debug workflow.
This is ordering, not an audience downgrade: every shipped capability still
honours the dual-access contract.

**Not this product:**

- The public `docs/website` ratings dashboard (Team A; live JSON in
  `docs/website/public/data/` stays untouched by this tool).
- Promoting ASP algorithm flags. This tool observes and compares; it
  does not flip product defaults.
- A rewrite of `backend/src/core/telemetry.py` or of the ASP evaluator
  internals. Both are foundations the host consumes.

---

## Development Assistance Scope (D16)

Harbinger's 2026-08-17 expansion: this is now a **development-assistance**
tool, not only a debugger. Five capability areas join the telemetry/crash
and analytics/benchmark tracks, all as host plugins / data producers rather
than separate apps:

1. **Build / test / bench runner integration** — `devtool run` (or a runner
   plugin) drives a build, pytest, or benchmark and opens a Session carrying
   the build/test context that produced it. A crash/hang/failure is then
   attributable to a specific command + environment, not an orphan JSONL.
2. **Diff / review assistance** — tie Sessions to code changes (git commit /
   PR), so `devtool diff` can compare outputs before/after a change, not
   just across runs of the same build.
3. **Documentation / knowledge surface** — annotations on Sessions and
   Investigations become a searchable debug knowledge base. The
   gallery-crash doc (`.agent/cache/gallery_crash_deleteorphaned_...`) is
   the prototype: structured notes + evidence, queryable instead of prose.
4. **Performance profiling** — stage timers, RSS/memory trajectory,
   per-API latency, queue depths. Not just crash forensics; the btop live
   view and Perfetto static view both consume these.
5. **Reproducibility artifacts** — one-click bundle of (code version,
   config, repro script, captures) that can be shared or replayed, honoring
   D20's redaction policy.

Each area lands as a plugin with its own data producer (a command or
wrapper) and one or more host surfaces (TUI / web / editor / MCP). v1
priority is D22: D4 span-IDs, then C1 host, with A3/C3 in parallel; these
five areas are scoped but sequenced after the host exists so they plug in
rather than fork.

---

## Settled Decisions (2026-08-17)

Locked with Harbinger in the Grok brainstorm, plus earlier
deepseek / Gemini / analytics locks that still hold, plus the
2026-08-17 development-assistance brainstorm (D16–D23).

| # | Decision | Lock |
|---|---|---|
| D1 | Audience | Equal dual: human TUI/web + agent API/MCP. |
| D2 | Scope of "Development" | Modular host. Telemetry + stack traces + charts/plots + model benchmarks. ASP evaluator is a plugin (TUI and/or GUI/web). |
| D3 | Canonical doc | This file. Former three roadmaps folded and deleted. |
| D4 | Telemetry schema | Add optional `span_id` / `parent_span_id` / `seq`. Old JSONL still parses via `(tid, category, basename)`. |
| D5 | Multi-runtime | Balance: first-class `CrashBundle` correlation **and** a lightweight process tree (Python / JVM / Qt / native lanes). Not a full JVM-internal span model. |
| D6 | Agent contract | Python import + CLI `--json` **and** a local MCP / stdio server (`devtool mcp` / `devtool serve`). |
| D7 | Pixels | TUI + **local** web view for images, A/B frames, plots. Not the public website. PySide6 GUI is an optional plugin surface, not the host default. |
| D8 | Visual density | **Perfetto** for static / post-mortem. **btop** for live / real-time. |
| D9 | JSONL | Remains the source of truth. Sidecar index at `~/.image-toolkit/telemetry/index.json`. Parquet deferred to v2 (analytics contract still allows Parquet for large tabular corpora). |
| D10 | Naming | Product title: **Development Tool**. Package `devtool.py` module name kept; import package is `tool` (D40 superseded the original "new package/CLI: devtool, debugtool stays a compat entry point" — there is no separate `debugtool` package anymore). |
| D11 | Home | `dev/` directory is the source of truth (D40 completed the fold — `debug/` no longer exists). |
| D12 | Investigations | Portable folders `dev/investigations/<name>/` (or `debug/investigations/` during migration) with `manifest.json`, captures, repro scripts. |
| D13 | Retention | `devtool prune --keep N` (default 50) and `--older-than Xd` (default 14d), with confirm. |
| D14 | Phase 3 ASP spatial telemetry | Rerun desktop sidecar + OTel dual-write. **No** Rerun WASM in `docs/website`. Unchanged from the 2026-08-15 analytics lock. |
| D15 | Existing debug scripts | Full consolidation: analyzer / gdb / resolve-offset become host commands; files remain as wrappers. |
| D16 | Dev-assistance scope (2026-08-17, Harbinger) | Beyond debug/telemetry/benchmark: **build/test/bench runner integration**, **diff/review assistance** (tie sessions to code changes), **documentation/knowledge surface** (annotations to a searchable debug knowledge base), **performance profiling** (stage timers, memory, per-API latency), **reproducibility artifacts** (one-click code+config+repro+captures bundle). All five in scope. |
| D17 | Host ownership (2026-08-17) | C1 host-core is **deepseek + Grok**: deepseek owns the host model / plugin protocol / store (data side); Grok owns process lifecycle + plugin discovery. First slice: load a plugin, list its artifacts. |
| D18 | MCP first surface (2026-08-17) | **Read-only analysis tools first**: list_sessions, open_session, orphaned_spans, in_flight_at, diff, overlaps. No host mutation in the first MCP slice; investigation management and full plugin surface later. |
| D19 | Package move timing (2026-08-17) | **Keep debug/debugtool in place until C1 exists** (Grok lean, accepted). Superseded by D40 once C1-C7 landed: the fold happened in one pass, not gradually. |
| D20 | Investigation git policy (2026-08-17) | **Grok proposal accepted**: manifests + repro scripts committed; JSONL/gdb/hs_err stay in ~/.image-toolkit unless an author explicitly copies a redacted bundle. |
| D21 | Editor integration (2026-08-17, Harbinger) | Add an **editor-integration surface** alongside TUI/web: VS Code/IDE plugin or clipboard snippets so devtool output lands in the editor. Not required for v1, but in scope. |
| D22 | Build order (2026-08-17) | **D4 span-IDs first, then C1 host**, with A3 (TUI) and C3 (local web) in parallel. A4/A5 follow A2. MCP (C4) can start read-only once C1's session store exists. |
| D23 | Span-ID writer change (2026-08-17) | telemetry.py grows optional span_id / parent_span_id / seq behind the existing opt-in flag, **no behavior change**; ASP PipelineSession emits them so stages get a real parent tree for the flame view. Old readers ignore new fields. |
| D24 | Launch and persistence (2026-08-17, Harbinger) | `devtool` opens a command palette / workspace chooser first. Durable sessions and investigations are the v1 persistence model; an always-on local service/indexer is optional later, never required to inspect existing evidence. |
| D25 | Product name (2026-08-17, Harbinger) | Product title and CLI remain **Development Tool** / `devtool`; do not introduce a second brand. |
| D26 | Audience sequencing (2026-08-17, Harbinger) | Prioritize benchmark investigation first, then agentic debugging, then general human/developer debugging. Dual human/agent access remains mandatory for every delivered slice. |
| D27 | Runner safety (2026-08-17, Harbinger) | Start with explicit verbs only (`build`, `test`, `bench`, `app`, `repro`); do not ship arbitrary-shell execution in v1. A constrained shell extension is a later, separately reviewed capability. |
| D28 | Capture configuration (2026-08-17, Harbinger) | Command/env, git state, telemetry, stdout/stderr, system/RAM/VRAM, process tree, and optional screenshots are independently configurable capture channels. No single mandatory heavyweight capture profile. |
| D29 | Retention configuration (2026-08-17, Harbinger) | Session count, age, size budget, and exemptions for failures/named investigations are settings, not hard-coded policy. `prune` previews its targets and requires confirmation. |
| D30 | Investigation role (2026-08-17, Harbinger) | Investigations are durable lab notebooks: hypotheses, evidence links, annotations, decisions, and repro scripts accompany Sessions rather than merely containing raw files. |
| D31 | First comparison (2026-08-17, Harbinger) | The first end-to-end diff is benchmark image/result A/B, with human-readable evidence. Test, crash-signature, and performance diffs follow as plugins. |
| D32 | MCP note mutation (2026-08-17, Harbinger) | MCP starts analysis-first but may append a timestamped note to an existing Investigation. It may not execute commands, alter settings, delete evidence, or change product configuration in v1. |
| D33 | Local web workspace (2026-08-17, Harbinger) | `devtool web` is a persistent localhost browser workspace with command-palette navigation, investigations, and visual artifacts — not a one-off image viewer. |
| D34 | Visual posture (2026-08-17, Harbinger) | Default to a dense **mission-control** workspace: high signal, keyboard-first, clear hierarchy, and strong anomaly contrast without hiding the underlying evidence. |
| D35 | Alert configuration (2026-08-17, Harbinger) | Alert classes and emphasis are configurable. Defaults are conservative; users choose which failures, regressions, leaks, hangs, config changes, and review blockers deserve prominence. |
| D36 | Evidence-only assistance (2026-08-17, Harbinger) | v1 presents evidence and multiple visualizations; it does not recommend commands, diagnoses, or automatic fixes. Recommendation features need a later evidence/quality contract. |
| D37 | Scope boundary (2026-08-17, Harbinger) | No additional exclusion list is locked yet. Until one is, a capability enters the roadmap only when it fits D16, has a named plugin/surface, and does not displace the benchmark-first sequence without Harbinger approval. |
| D38 | First explicit v1 exclusion (2026-08-17, Harbinger, via Claude) | **Cloud sync/collaboration** (multi-machine sync, shared team workspaces, remote access) is the first named out-of-scope category. Consistent with D24 (durable local sessions, no required daemon) and D33 (localhost workspace) — this stays a local-first, single-developer tool for v1. |
| D39 | Persistent-service promotion trigger (2026-08-17, Harbinger, via Claude) | An always-on local service/daemon is justified once the **btop-style live-watch view (D8) needs push updates** that JSONL polling can no longer deliver responsively — not a pre-picked latency number, since there's no usage data yet to set one. Whoever builds A3's live-tail mode owns measuring this and proposing the daemon when it's actually hit, not before. |
| D40 | debug/dev fold (2026-08-17, Harbinger, via Claude) | Now that Track A/C landed, `debug/` folds fully into `dev/`, and `debug/debugtool/` folds into `dev/devtool/` — no gradual migration, no compatibility alias. The original `debugtool` package identity (`open_session`/`list_sessions`/`render_session_view`/`run_tui` + the human-readable `analyzer.py`) is preserved as its own subpackage, `tool.debug`, rather than merged flat — an import-level compatibility surface, not a CLI one. `dev/devtool/` itself is renamed `dev/tool/`; `main()` moves out to its own `tool/devtool.py` module (keeping the product name), and `tool/cli/main.py` is renamed `tool/cli/parser.py` (it now only builds the parser + command handlers). `dev/tool/__main__.py` moves to a top-level `dev/__main__.py`, so the canonical invocation becomes `python dev/` — `python -m debugtool` and `python -m tool`/`-m devtool` no longer work (no `__main__.py` remains inside the `tool` package). Tests split into `dev/test/debugger/` (inherited from `debug/debugtool`) and `dev/test/development/` (written directly against `tool`), sharing one `dev/test/conftest.py`. |
| D41 | **v2 shell: Tauri, not PySide6** (2026-08-18, Harbinger, via Claude) | Chosen specifically because devtool is being promoted to a dev app usable **across other repos**, not just Image-Toolkit, and Tauri's web-tech substrate gives natural, proven access to Three.js/`react-three-fiber` for 3D (already exercised by the public website's `Hero3D`) — a materially better fit than PySide6's comparatively awkward 3D story (QtQuick3D / embedded WebEngine), even though it breaks from this monorepo's PySide6-everywhere convention. This is a genuine rewrite of the host/shell, not a port — see the new v2 section below. |
| D42 | **v2 portability: fully repo-agnostic core** (2026-08-18, Harbinger, via Claude) | The host (session/investigation model, TUI/GUI shell, CLI, MCP server) must know nothing Image-Toolkit-specific — it is a real installable package/app any repo can point at (via a config file or `--workspace` flag), not something that only works living inside this repo's `dev/`. Image-Toolkit's own plugins (`asp_evaluator`, `benchmarks`, `telemetry_workbench`, etc.) ship alongside as the plugin API's first real-world proof — generalizing the core without a complex real plugin exercising it is the riskier order, explicitly rejected. |
| D43 | **v2 visualization scope: 2D+3D across meta-graph, flame graph, benchmark trends, and memory timeline** (2026-08-18, Harbinger, via Claude) | Track B Phase 1 (Interactive Meta-Graph / codebase topology, GPU-accelerated, previously scoped as research/not-v1) is **pulled into v1** as the flagship 3D view. Flame graphs, benchmark A/B trend-over-time surfaces, and the memory/RSS timeline also get 3D treatment where it adds real value — 2D remains the right choice per-view where mature prior art already works well (e.g. classic 2D flame graphs have 300+ existing implementations); this is "3D where it helps," not "3D everywhere by default." |
| D44 | **v2: 4D experimentation is an explicit spike, not a core v1 deliverable** (2026-08-18, Harbinger, via Claude) | "4D" here means the standard technique from the visualization literature: a 3D scene with **time as an animated/scrubbable dimension**, not a literal fourth spatial axis. Industry/research treatment of 4D-for-dev-tools is genuinely experimental (no established prior art the way 2D flame graphs or 3D force-directed graphs have), so this is scoped as a bounded spike against one concrete view (candidate: the meta-graph evolving across commits, or a benchmark run's stage timings animating through the pipeline) rather than a blocking v1 requirement. |
| D45 | **v2 interactivity baseline** (2026-08-18, Harbinger, via Claude) | Every shipped visualization view must support: live/real-time updates (not just static post-mortem snapshots), click-to-drill-down (zoom into a span/node/bar, jump to source or a linked Investigation), cross-view linking (a selection in one view highlights/filters related data in every other open view), in-app annotation that saves into the Investigation (not just typed notes elsewhere), filtering/slicing, hover tooltips, and dynamic zoom. This is the baseline bar for any view in v2, not optional polish layered on later. |
| D46 | **v2: local web (C3) retires as a separate surface** (2026-08-18, Harbinger, via Claude) | No standalone localhost web server a browser points at. Because Tauri's rendering *is* the same web-tech stack, this is not a contradiction with D43's 3D approach — it means one packaged app window, not a second UI surface (browser tab) to keep in sync with the GUI. Whatever C3 did (benchmark A/B, session timeline, artifact viewer, investigation browsing) becomes GUI content directly. |
| D47 | **v2 shell decisions resolved** (2026-08-18, Harbinger) | Superseded by D48–D61 after the product-design session. Distribution package format remains an implementation feasibility choice, not a product blocker. |
| D48 | **TUI: retain both human surfaces** (2026-08-18, Harbinger) | Tauri is the rich, primary daily-driver surface; the existing TUI remains a genuine lightweight, terminal/SSH-friendly fallback, not merely an embedded visual effect. Both consume the same durable evidence and Investigation model. |
| D49 | **MCP: standalone service** (2026-08-18, Harbinger) | MCP remains independently usable and is not coupled to either human shell. Its existing evidence-first, narrowly mutating contract carries forward; an agent can use it without the Tauri app or TUI running. |
| D50 | **Platform: Linux first** (2026-08-18, Harbinger) | The standalone v2 app targets Linux first. Other OS bundles may follow, but do not constrain the first usable architecture or acceptance criteria. |
| D51 | **Python integration: sidecar** (2026-08-18, Harbinger) | The Tauri host uses a Python sidecar for the current Python evidence/plugin ecosystem rather than embedding its runtime into the GUI process. |
| D52 | **Host protocol: language-neutral** (2026-08-18, Harbinger) | Define a versioned, language-neutral manifest and process protocol (initially JSON-RPC over stdio). Python is a first-class adapter/sidecar, not the core's required implementation language. |
| D53 | **Workspace onboarding: bounded discovery, explicit selection** (2026-08-18, Harbinger) | Given a starting directory, the app scans for code-bearing directories through a user-configurable maximum depth **N**, then the user explicitly selects the directories to monitor. Discovery never silently turns every nested project into a workspace. |
| D54 | **Flagship 3D story: runtime flow and nexus modules** (2026-08-18, Harbinger) | The primary 3D explanation is how the system flows at runtime: nodes and edges reveal execution flow, while visually legible nexus modules expose where responsibility, coupling, or traffic concentrates. |
| D55 | **Meta-graph: persistent navigable world** (2026-08-18, Harbinger) | The graph is a saved, navigable workspace world—not a disposable render. Layout, camera, filters, selected evidence, and linked Investigations persist with the workspace. |
| D56 | **4D spike: both candidates approved, one at a time** (2026-08-18, Harbinger) | Both candidate experiments are worthwhile—meta-graph evolution across commits and benchmark-stage timing animation—but only one may be prototyped at a time, after its parent 3D view proves useful. |
| D57 | **Benchmark GUI sequence: inspect, then compare** (2026-08-18, Harbinger) | Start with precise image/result inspection. Comparative analytics and trend surfaces follow from trusted per-artifact evidence rather than replacing it. |
| D58 | **Annotation authorship: visually distinct** (2026-08-18, Harbinger) | Human and agent annotations must be visibly distinguishable and retain author, time, provenance, and confidence where available; both attach to durable evidence/Investigations. |
| D59 | **Aesthetic: mission control** (2026-08-18, Harbinger) | Retain and deepen D34's mission-control character: dense but legible, keyboard-oriented, evidence-forward, and clear under incident pressure. |
| D60 | **Workspace scope: one repository** (2026-08-18, Harbinger) | A workspace monitors exactly one selected repository in v2. Cross-repository portfolio/correlation views are explicitly deferred. |
| D61 | **Success bar: daily driver plus research-grade visualization** (2026-08-18, Harbinger) | v2 succeeds only when it is useful for everyday debugging and benchmark work while also supporting credible research-grade visual exploration. Select the exact Linux packaging/release format through a feasibility spike. |

---

## Development Tool v2 (2026-08-18)

*Tauri rewrite, multi-repo portability, 2D/3D/4D visualization.*

Brainstormed directly with Harbinger (Claude), triggered by real CLI-UX
confusion in v1's separate-surfaces design (`just devtool plugins gui` —
reasonably expected but not how the CLI is shaped) and a decision to
promote devtool from an Image-Toolkit-only tool into one usable across
other repos too. **This section is the brainstorm's output — decisions
D41–D61 above are locked; everything else here is scope for the team's
design/feasibility pass, not yet implemented.**

### What's actually changing vs. what carries forward

- **Changing**: the rich shell/host. v1's Python CLI + separate TUI (Rich/
  ANSI) + local web server (`http.server`) + optional PySide6-plugin-only
  GUI becomes one Tauri app. The Tauri app is primary, but the TUI remains
  a real terminal/SSH fallback; CLI and standalone MCP remain available for
  agent and automation use (D41, D46, D48, D49).
- **Carrying forward** (per D42): the *content* — Session/Investigation/
  CrashBundle data model, the plugin protocol's shape (manifest +
  artifacts + surfaces), MCP's read-mostly agent contract, and
  Image-Toolkit's own plugins (`asp_evaluator`, `benchmarks`,
  `telemetry_workbench`, `editor_integration`) all survive as the proof
  that a generalized plugin API still supports a real, complex use case.
  This is a shell rewrite, not throwing away Track A/C/D's actual work.
- **New**: full 2D/3D visualization (D43), an experimental 4D spike (D44),
  a concrete interactivity baseline every view must meet (D45), and
  multi-repo portability as a first-class requirement (D42) rather than
  an afterthought. v2 is Linux-first, uses a Python sidecar behind a
  language-neutral protocol, and keeps each workspace to one explicitly
  selected repository (D50–D53, D60).

### Host, workspace, and evidence boundaries

- **Host boundary**: Tauri owns the Linux desktop experience; Python runs as
  a sidecar behind a versioned JSON-RPC-over-stdio protocol. Core manifests
  and requests must remain language-neutral so future non-Python adapters do
  not need a host rewrite (D51, D52).
- **Workspace onboarding**: begin from a directory, discover code-bearing
  candidates no deeper than user-set depth **N**, then require an explicit
  choice of exactly one repository. Persist the workspace selection and its
  visual state locally (D53, D55, D60).
- **Evidence boundary**: Tauri, TUI, CLI, and standalone MCP read/write the
  same durable sessions and Investigations. Human and agent annotations are
  visually distinct and retain provenance; the product continues to present
  evidence rather than diagnoses or autonomous fixes (D36, D48, D49, D58).

### Visualization inventory (from D43/D44, for the design pass to flesh out)

| View | Dimensionality | Notes |
|---|---|---|
| Runtime-flow meta-graph / nexus modules | **3D** (flagship) | A persistent navigable world that explains runtime flow and makes nexus modules—concentrated responsibility, coupling, or traffic—legible. Save layout, camera, filters, selection, and linked Investigations (D54, D55). |
| Flame graph / call stack | 2D primary, 3D optional | Mature 2D prior art (300+ implementations industry-wide); a 3D variant is genuinely novel — don't let it block the 2D version shipping. |
| Benchmark A/B / trend-over-time | Precise 2D inspection first; 3D surface for multi-run patterns | Trustworthy per-image/result inspection comes first; comparative analytics and 3D add value for patterns *across many runs at once* only after that foundation (D57). |
| Memory/RSS timeline | 2D primary, 3D if a second dimension is worth encoding | e.g. per-thread or per-category memory bands as depth — only if that reads better than small-multiples 2D. |
| 4D spike | 3D + animated/scrubbed time | Both candidates are approved—meta-graph evolving across commits and a benchmark run's stage timings—but sequence exactly one after its parent 3D view proves useful. Not a blocking deliverable (D56). |

### Cross-agent review round (requested on the bus, 2026-08-18)

Same process as v1's original fold: propose → cross-review → Harbinger
signs off → implementation starts. Suggested review lenses, not rigid
assignments:

- **Feasibility / Linux delivery** (D42, D50, D61): Tauri app structure,
  the Linux package/release format, and how a consuming repository acquires
  the app and selects its single monitored workspace.
- **Portability of the plugin API** (D42): what changes in the current
  Python plugin protocol (`Plugin`/`PluginManifest`/`Artifact`/`Channel`/
  `Surface` in `host/plugins.py`) to make it genuinely repo-agnostic, and
  what a plugin author in a *different* repo would need to write one.
- **Sidecar/protocol portability** (D51, D52): versioned RPC boundary,
  lifecycle/failure handling, and a minimal non-Python adapter proof.
- **3D/4D visual + interaction design** (D43–D45, D54–D59): concrete
  runtime-flow/nexus layouts, persistent-world behavior, visibly distinct
  human/agent annotations, and which approved 4D candidate should run first.
- **TUI/MCP parity** (D48, D49): define the shared evidence contract and
  the deliberate capability differences between the primary GUI, SSH TUI,
  and standalone MCP service.

Post proposals as dated subsections under [Team Review Notes](#team-review-notes)
below, same convention as the v1 rounds. Nobody starts wide implementation
before Harbinger has seen the cross-review and signed off — v1's Track A/C/D
work stays live and usable in the meantime (D42 means none of it is wasted
regardless of how the shell rewrite lands).

---

## Glossary

Living shared vocabulary. Add a term only with a definition, a
measurement direction where relevant, and a clear distinction from
nearby terms.

### Result identities

- **Raw ASP** (`raw_asp`): the ungated ASP compositor result. It remains
  an artifact even when a policy selects another result.
- **Safe ASP** (`safe_asp`): the policy-selected ASP-safe result; it may
  use a named safe fallback but is not a fourth result identity.
- **SCANS** (`scans`): the OpenCV stitcher comparison / fallback result.

### Defect labels

- **ghosting**: doubled or semi-transparent visual content from imperfect
  alignment or overlap composition.
- **seam_line**: an unwanted visible boundary at or near a stitch seam.
- **misordered_content**: spatial or temporal content in the wrong order.
- **crop_loss**: meaningful intended content missing from the output
  bounds.
- **torn_anatomy**: anatomy discontinuous or implausibly joined across a
  composition boundary.
- **duplicated_strip**: a scene strip or region appears more than once.
- **banding**: discrete tonal / color steps where a smooth transition is
  expected.
- **color_shift**: unwanted color or luminance change vs. intended
  source / reference.
- **blur**: loss of meaningful high-frequency detail beyond expected
  scaling or motion.
- **geometry_warp**: visibly implausible shape distortion from the
  transform.

### Evidence and decisions

- **observation**: an individual human or automated claim about a metric,
  defect, or safety decision; retained even when later disagreed with.
- **adjudication**: a separately stored, reasoned effective decision over
  one or more observations; never a destructive replacement for them.
- **provenance**: enough to reproduce or assess a claim: producer and
  version, inputs / hashes, configuration, timestamp, evidence links.
- **primary defects**: one or more defects judged equally causal; not a
  forced single-label classification.

### Workbench identities

- **Session**: one process launch that produced a `telemetry-<pid>.jsonl`
  (and, if present, its CrashBundle).
- **Investigation**: a named, portable folder grouping Sessions, notes,
  hypotheses, evidence links, decisions, and repro scripts; a durable lab
  notebook, not a raw-capture bucket.
- **Workspace**: the persistent localhost/TUI navigation context over durable
  sessions and investigations. It may be reopened at any time without a
  background service.
- **Evidence-only mode**: the v1 assistance rule: expose raw artifacts,
  derived comparisons, and visualizations without prescribing a next command,
  diagnosis, or fix.
- **CrashBundle**: `{jsonl, gdb-bt, hs_err, resolved offsets, optional
  core}` aligned on one run.
- **Runtime lane**: a first-class row in the process tree: `python`,
  `jvm`, `qt-gui`, `native`. Not a full VM-internal model.
- **Plugin**: a module that registers data sources, views, CLI verbs,
  and / or MCP tools against the host. Declares which surfaces it
  implements (`tui`, `web`, `gui`, `cli`, `mcp`).
- **Host**: the `dev/` application. Owns discovery, routing, settings,
  export, and the access contract. Does not own domain logic.

---

## Dual Human / Agent Access Contract

Every deliverable on this roadmap must serve both audiences. A chart
only a person can read is unfinished; so is a raw dataset with no
intelligible explanation.

### Required companion artifacts

Each deliverable emits, alongside its human-facing view:

1. a versioned **JSON sidecar** (`analytics_contract_version`,
   `artifact_id`, producer / version / timestamp, source run / case IDs
   and hashes, configuration, metric definitions / units / directions,
   chart artifact refs, provenance, privacy classification);
2. a short **natural-language summary** (what was measured, the
   important result, known limits, the next decision it supports);
3. **Parquet** only when the result is a non-trivial tabular / event
   collection. Small manifests stay JSON-first.

Unknown extension fields are preserved, never treated as invalid.

All shareable artifacts are **anonymized metrics and explicitly approved
derived assets by default**. Raw corpus frames, private source URLs, and
personal browsing / reviewer data are private unless an explicit
publication approval says otherwise.

### Defects, disagreement, and adjudication

Use the [Glossary](#glossary). Defect observations are multi-label. Human
and automated observations are immutable parallel records. Conflict
produces an optional adjudication **without overwriting** either
observation.

### Agent surfaces (required)

| Surface | Shape | Consumer |
|---|---|---|
| Python API | `from tool import open_session, open_investigation` (and plugin facades) | In-repo agents |
| CLI | every human verb has `--json` / `--format json` | Scripts, CI |
| MCP / stdio | `devtool mcp` (stdio) and optional `devtool serve` (localhost) | Other agent sessions that cannot import this tree |

MCP tools (minimum set): `list_sessions`, `open_session`,
`orphaned_spans`, `in_flight_at`, `overlaps`, `analyze`,
`list_investigations`, `list_plugins`, `run_plugin`, and the narrowly scoped
`append_investigation_note`. The first mutation only appends an attributable
note; it cannot execute, configure, delete, or rewrite evidence. Plugins may
register additional read-only tools.

### Privacy

Telemetry is local and never published by default. Export sidecars carry
privacy classification tags. Paths under the user's home and vault-related
events are redacted in any export leaving the machine. Cores are never
committed.

---

## Home: the `dev/` directory

**As-built (2026-08-17 debug/dev fold — D40).** `debug/` no longer exists;
its content folded into `dev/`, and `debug/debugtool/` folded into
`dev/tool/` (the package literally renamed `devtool` → `tool`). Real
layout:

```
dev/
  README.md                 # crash narrative + how-to (merged from debug/README.md)
  __main__.py                # `python dev/` entry point -> tool.devtool.main()
  telemetry_analyzer.py      # compat shim -> tool.debug.analyzer
  resolve_qt_offset.py       # stripped-symbol offset resolver
  run_with_gdb.sh            # SIGABRT-stop gdb capture
  tool/
    __init__.py             # public API (from tool import open_session, Host, ...)
    devtool.py              # main() entry point (the `devtool` product identity)
    debug/                   # the original debugtool public surface, preserved
      __init__.py            # re-exports Session/Span/open_session/... + render_session_view/run_tui
      analyzer.py            # human-readable report (successor to the pre-Phase-1 script)
    host/
      app.py                 # process lifecycle, plugin discovery, view router
      plugins.py             # Plugin protocol
      store.py               # WorkspaceStore: sessions, investigations, settings
      settings.py            # capture, retention, alert emphasis, privacy
      scenarios.py           # named repro scenarios catalog
      index.py               # sidecar index (A2)
    model/
      session.py             # Session/Span/discover_sessions/list_sessions/open_session (real impl)
      span.py                 # re-export of Span from .session
      event.py
      investigation.py
      crash_bundle.py
      process_tree.py
    queries/
      diff.py                 # A5 cross-session diff
      rss.py                  # A5 RSS trajectory
      hypothesis.py           # A4 natural-language hypothesis generator
    export/
      json_sidecar.py
      html.py
      csv.py
    ui/
      app.py                  # TUI entry (run_tui/render_session_view)
      views/                  # timeline, crash, concurrency, memory, flame, live_tail
      web/                    # C3 local web viewer
    cli/
      parser.py               # build_parser() + cmd_* handlers
      track_a.py               # export/diff/resolve-offset/prune/repro verbs
    mcp/
      server.py               # C4 stdio + optional localhost
    plugins/
      telemetry_workbench.py  # Track A
      asp_evaluator.py         # adapter over submodules/ASP/.../evaluation
      benchmarks.py             # parent + ASP bench JSON A/B
      editor_integration.py     # C7: clipboard markdown + VS Code tasks
  investigations/            # portable named folders
  test/
    conftest.py               # sys.path + synthetic-telemetry fixtures (shared)
    debugger/                 # tests inherited from debug/debugtool
    development/               # tests written directly against tool/devtool
```

Invocation is `python dev/` (or `python dev/__main__.py`) — running a
directory with Python adds that directory to `sys.path[0]`, so `tool`
resolves without any `PYTHONPATH`. There is deliberately **no**
`tool/__main__.py`: `python -m tool` does not work post-fold, since
`__main__.py` moved to the top-level `dev/` per this decision. `devtool.py`
keeps the product's name as a module even though the package itself is
`tool` — it is what `dev/__main__.py` calls.

---

## Relationship to Existing Tooling

| Former artifact | Now | Notes |
|---|---|---|
| `debug/debugtool/` | `dev/tool/` (model/cli/export/queries/ui/host/mcp/plugins) | Folded in, not aliased — no separate `debugtool` package exists anymore |
| `debug/debugtool/__init__.py` + `analyzer.py` | `dev/tool/debug/` | Kept as their own subpackage — the original small `debugtool` public surface, for import compatibility (`tool.debug.open_session` etc.) |
| `debug/debugtool/cli/main.py` (Phase-1-only CLI) | Deleted | Superseded entirely by `dev/tool/cli/parser.py`'s 14-verb canonical CLI |
| `python -m debugtool` (C2 alias) | Retired | No separate top-level package to alias; the CLI is exclusively `python dev/` |
| `debug/telemetry_analyzer.py` | `dev/telemetry_analyzer.py` | Still a shim, now delegates to `tool.devtool.main` |
| `debug/run_with_gdb.sh` | `dev/run_with_gdb.sh` | Same gdb flags, SIGABRT-only stop, `hs_err` preserved |
| `debug/resolve_qt_offset.py` | `dev/resolve_qt_offset.py` | Unchanged logic, moved |
| `debug/README.md` | Merged into `dev/README.md` | One README for the whole tool now |
| `backend/src/core/telemetry.py` | Unchanged writer | Grows optional span IDs; still no-op when unset |
| ASP `evaluation/` | Plugin `asp_evaluator` | Adapter, not a fork. Evaluator remains the rating UI of record |
| `docs/website` dashboard | Out of scope | May *read* the same JSON the plugin writes; this tool does not own it |
| Rust / C++ / TS math backbones | Track B primitives | Already shipped; plugins call them, do not rewrite them |
| Parent `backend/benchmark/` | Plugin `benchmarks` | Phase 12 benches stay where they are; the host charts them |

---

## Visual Language

Two modes, one product. Gemini owns the TUI chrome; this section locks
**density**, not pixel-perfect color.

### Static / post-mortem — Perfetto

Used by: timeline waterfall, crash splicer, flame / icicle, cross-session
diff, investigation review.

- Multi-track lanes, minimap scrub, packed span bars, nested span trees.
- Monospace timestamps. Color only for faults (amber = orphaned /
  contention, rose = SIGABRT / SIGSEGV / truncated crash).
- Dark slate ground, monochromatic type hierarchy.
- Mission-control default: command palette, dense but navigable panels, and
  evidence linked directly to the underlying run / artifact. Alert classes
  and emphasis are user-configurable rather than hard-coded.
- Keyboard: `Tab` view, `j/k` spans, `Enter` drill, `z/x` zoom, `/`
  filter.

### Live / real-time — btop

Used by: `devtool watch`, RSS gauges, stage timers, in-flight count,
queue depth.

- Boxed panels, live percentages, sparkline rates, modest chrome.
- Non-blocking JSONL tail. No flicker. Must not stall the traced
  process.
- `w` toggles live watch from the static TUI.

### Local web (pixels)

Used by: persistent workspace navigation, benchmark frame/result A/B, ASP
evaluator images, plotly / matplotlib figures, screenshot-on-crash, and
coherence pairs.

- Localhost only. Zero public bind by default.
- Persistent localhost workspace with command-palette navigation across
  investigations, sessions, plugins, and visual artifacts. It reads durable
  files/indexes; a background service is optional, not required.
- No JS build step required for v1 (single-file HTML or a tiny static server
  over the export surface).
- The website dashboard is a *separate* consumer of committed JSON, not
  this viewer.

### GUI plugin surface

Optional. A plugin may open a PySide6 window (the ASP inspector is the
obvious first). The host does not become a Qt app in v1.

### Editor integration (D21)

A fourth surface, alongside TUI / web / MCP: **editor integration** so
`devtool` output lands where the developer is already working.

- v1 scope: **clipboard snippets** and a **VS Code/IDE command** that
  pastes a formatted session summary / crash report / diff into the editor
  (no heavy extension SDK; a simple `devtool copy <pid|investigation>`
  command emitting a code-fence-ready block is enough).
- Later: a small VS Code extension wrapping the MCP stdio server, so
  editor-embedded agents get the same read-only tools as the CLI/API.
- The editor surface must not require the editor to run the traced
  process; it consumes exports and MCP tools only.

---

## Architecture

### Plugin protocol

A plugin is a Python package exposing:

```python
class Plugin:
    name: str
    version: str
    surfaces: frozenset[str]  # tui | web | gui | cli | mcp

    def register(self, host: Host) -> None: ...
    def discover(self) -> list[ArtifactRef]: ...
```

The host provides: session/investigation store, export helpers, TUI view
registry, local-web route registry, MCP tool registry, settings,
privacy redaction.

**First-party plugins (v1):** `telemetry_workbench`, `asp_evaluator`,
`benchmarks`. Analytics Phase 1–10 views land as additional plugins
only when someone is ready to implement them — they do not block the
host.

### Telemetry schema (D4)

Current event (unchanged, still valid):

```json
{"ts": 0.0, "tid": 123, "cat": "native", "event": "qimage.load.start", "...": "..."}
```

Compatible additions, ignored by old readers:

```json
{"span_id": "a1b2", "parent_span_id": "a1b0", "seq": 17, "runtime": "python"}
```

`runtime` is one of `python | jvm | qt-gui | native`. Writer
(`telemetry.py`) emits them when present; `span()` allocates a
`span_id` and nests via `parent_span_id` instead of only the
`(tid, category, basename)` heuristic. Reconstruction prefers IDs and
falls back to the heuristic for historic files.

### Multi-runtime (D5)

Not "Python threads only." Not "model the HotSpot JIT."

- A `Session` has a **process tree**: root pid, child pids if known,
  runtime lanes, thread names from telemetry and from gdb `info
  threads`.
- A `CrashBundle` joins `{jsonl, gdb-bt, hs_err, resolved offsets}` by
  pid + wall clock. The splicer answers: *which span was in flight on
  which lane at the aborting microsecond?*
- JVM SIGSEGV stays `nostop noprint pass` in gdb (benign HotSpot
  implicit-null / safepoint). SIGABRT remains the default trap.
  Explicit `devtool repro --trap-segv` is opt-in and documented as
  hostile to a live JVM.
- Qt GUI thread is always its own lane when we can identify it.

### Performance budget (Grok recommendation)

- Session parse of 100k events: &lt; 200 ms cold, incremental tail
  thereafter.
- TUI first paint: &lt; 50 ms once the Session is in memory (Gemini's
  Phase 3 criterion, kept).
- Live watch: never holds the JSONL write lock; read-only tail.

---

## Track A — Telemetry & Crash Workbench

Folded from `debug_workbench.md`. Owners: deepseek (data / CLI /
repro), Gemini (TUI). Host integration is Track C.

This track is deliberately **general-purpose** (startup probes, workers,
native boundaries, RSS, scan pipelines). The gallery-crash workflow is
the first user, not the only one.

### A1 — Session model + queryable API (deepseek)

**Status:** ✅ Landed (`431163b7`), 19/19 tests.

`Session` over `telemetry-<pid>.jsonl`; truncated-final-line tolerance;
span-tree reconstruction; `open_session` / `list_sessions`;
`orphaned_spans` / `in_flight_at` / `overlapping_windows`; analyzer
report byte-compatible via `debugtool analyze`.

**Follow-on (not yet landed):** consume D4 span IDs when present;
`CrashBundle` loader; `runtime` lane grouping.

### A2 — CLI + export surface (deepseek)

**Status:** 🔄 In progress (`list` / `analyze` exist; export / prune /
resolve-offset still to wrap).

- `devtool list | analyze | diff | export | resolve-offset | prune`
- JSON / CSV / standalone HTML export
- Sidecar index `~/.image-toolkit/telemetry/index.json`

Acceptance: `export --format json` valid sidecar; HTML opens with no JS
build; CLI help complete; tests on every subcommand.

### A3 — Visual timeline & TUI (Gemini)

**Status:** ✅ Complete (`debug/debugtool/ui/`, 14 tests in `test_debugtool_tui.py`).

#### Architecture & View Hierarchy (`dev/tool/ui/` or `debug/debugtool/ui/`)
Built with a dependency-light, high-speed ANSI / Rich canvas engine designed for instant startup (<50 ms) and zero GUI library overhead.

Four specialized view modes under the **Perfetto static density**, plus the **btop live watch** streaming face:

1. **Timeline & Waterfall (`ui/views/timeline.py`):**
   - Multi-track thread waterfall lanes with microsecond-precision duration bars (`[■■■■■■■] 142ms`).
   - Interactive minimap scrub bar displaying overall event density and anomalies across the session timeline.
   - Hierarchical span tree with collapsible parent-child spans and duration deltas.
2. **Crash Forensics Splicer (`ui/views/crash.py`):**
   - Side-by-side split view correlating GDB all-thread backtraces, JVM `hs_err` native crash dumps, and in-flight telemetry spans at the exact millisecond of SIGSEGV/SIGABRT.
   - Automatic offset resolution overlay (`libQt6Core.so.6+0x1e74d5 -> deleteOrphaned`).
3. **Concurrency & Overlap Inspector (`ui/views/concurrency.py`):**
   - Thread collision matrix flagging dangerous concurrent windows (e.g. scanner worker threads vs Qt GUI main loop).
   - Lock contention and mutex wait-time diagnostics.
4. **Memory & Latency Flamegraph (`ui/views/memory.py` & `ui/views/flame.py`):**
   - Step-by-step RSS memory growth chart over lifecycle allocation steps.
   - Hierarchical flame-chart breakdown for pipeline execution bottlenecks (e.g. image converter, LoFTR matcher, Stage 11 compositor).

#### Live Watch Mode (`ui/views/live_tail.py`):
The **btop face** of the same session model (`devtool watch [--pid <PID> | --latest]`):
- Non-blocking JSONL tailer with live RSS gauges, thread pool activity sparklines, and in-flight span ticker.
- Seamless single-key toggle (`Tab` / `m`) between live streaming monitor and detailed trace inspector without restarting.

#### Keyboard Ergonomics:
- `1`–`5`: Switch views (Timeline / Crash / Concurrency / Memory / Live).
- `j` / `k` or `Up` / `Down`: Navigate spans and threads.
- `Enter` / `Space`: Expand / collapse span details and metadata drawer.
- `z` / `x`: Zoom in / out timeline timescale.
- `/`: Interactive search and category filter.
- `c`: Jump directly to crash site / orphaned span.
- `q`: Quit.

Acceptance: `devtool tui` renders within 50 ms of an in-memory Session;
orphans / overlaps / crashes navigable via keyboard; live watch does not flicker;
headless TUI rendering tests in `dev/tool/test/test_tui.py` (or `debug/test/test_debugtool_tui.py`).

### A4 — Repro harness + crash capture (deepseek + Gemini)

**Status:** ⬜ Planned.

`devtool repro [--scenario NAME] [-- args...]`:

- `IMAGE_TOOLKIT_TELEMETRY=1`
- gdb wrap (SIGABRT default; hs_err preserved)
- post-run summary: session path, orphans, overlaps, gdb frames,
  natural-language hypothesis
- optional open in `tui --view crash`
- write `dev/investigations/<name>/`

Works headless in CI and interactively.

### A5 — Cross-session comparison + investigations (deepseek)

**Status:** ⬜ Planned.

- `diff(a, b)`: event-set, timing deltas, new orphans / collisions
- RSS trajectory across an Investigation
- portable `manifest.json`

---

## Track B — Analytics, Benchmarks & Interpretability

Folded from `analytics_and_interpretability.md`. These phases become
**plugins and data producers** for the host, not a second product.

See the research underpinning:
[`research/Analytics and Codebase Visualization Research.md`](../research/Analytics%20and%20Codebase%20Visualization%20Research.md).

Historical implementation status (unchanged by the fold):

| Layer | Status | Details |
|-------|--------|---------|
| **C++ / former Rust math backbone** (`base/` math) | ✅ Complete | 6 modules; 49 unit tests at the time of record |
| **TypeScript math backbone** (`frontend/src/math/`) | ✅ Complete | 7 modules + `benchmark.ts` |
| **Benchmark dashboard migration** (Streamlit → Tauri/React) | ✅ Complete | Separate from this host; Tauri/React 7-page dashboard |
| Phases 1–10 feature implementation | ⬜ Mostly not started | §1.4 DSM-equivalent shipped; rest planned / research |
| **Phase 11 ASP Benchmark Analytics** | ✅ Complete (2026-07-30) | 11.1–11.5 in ASP evaluator (#123); 11.6–11.10 in `bench_anime_stitch.py` report (#69) |
| **Phase 12 Benchmark Coverage** | 🔄 Partial (2026-07-30) | 12.1/12.2/12.3/12.5/12.6/12.7 shipped; 12.4 and 12.8 rescoped |

### How Track B attaches to the host

| Phase | Host attachment |
|---|---|
| 1 Meta-graph | Future `analytics` plugin, local-web GPU view. Do not block v1. |
| 2 Loss landscape | Future plugin; scoped to live models (AnimeStitchNet, BiRefNet, LoFTR, DINOv2). Issue #371 retired RLHF/DRL. |
| 3 ASP CV diagnostics | Plugin + PipelineSession `TelemetrySink`. Rerun desktop + OTel. No website WASM. |
| 4 Causal / info-theory | Consumes Parquet / JSONL the host already exports. |
| 5 Flame / coz / VRAM | Shares Track A flame + memory views; do not build a second profiler. |
| 6 CPG / CodeQL | Research plugin; not v1. |
| 7 rr / Pernosco | Optional later CrashBundle backend. gdb remains v1. |
| 8 OTel / high-cardinality | Same emission API as D4 spans; collectors stay optional. |
| 9 TLA+ / concolic | Research; not v1. |
| 10 TDA | Research; not v1. |
| 11 ASP charts | **v1 plugin** — wrap evaluator diagnostics rather than reimplement. |
| 12 Coverage benches | **v1 plugin** — discover existing `backend/benchmark/bench_*.py` JSON. |

The original Phase 1–12 specification text is preserved below so no
accepted detail is lost. Section headings keep their historical names
so citations such as `§12.5` and `Phase 11` still resolve.

---

<!-- TRACK_B_SPEC_START -->

## **Phase 1: The Interactive Meta-Graph (Codebase Topology)**

**Goal:** Build a semantic "graph of graphs" allowing zooming from high-level architecture down to granular function execution and AST parsing.

* **1.1 Rust-Powered AST & Dependency Parser:**
  * Develop a Rust CLI/daemon utilizing **tree-sitter** to statically parse the Python (`backend/src/animation`) and Rust codebases.
  * Extract semantic relationships: module imports, class inheritance, function calls, and data flow.
  * **Option A — SCIP Semantic Indexing:** Emit a **SCIP** (Source Code Intelligence Protocol) protobuf index via `scip-python` and `rust-analyzer`. Ingest into Rust via `nusy-codegraph` / `code-graph-cli` — produces Apache Arrow RecordBatches enabling sub-millisecond blast-radius queries (e.g., transitive impact of modifying `bundle_adjust.py`).
  * **Option B — tree-sitter-graph DSL:** Use the declarative `tree-sitter-graph` crate to write AST-to-graph mapping rules that extract pipeline-specific semantics (stage transitions, telemetry emission sites) without full SCIP indexing.

* **1.2 GPU-Accelerated Force-Directed Dashboard:**
  * **Primary Option — Cosmograph (cosmos.gl):** 100% GPU-bound force-directed simulation via WebGL 2.0 compute/fragment shaders. Ingests Apache Arrow buffers directly into GPU memory; 60fps semantic zooming through 1M+ nodes. Pairs with **DuckDB-WASM** for in-browser SQL filtering of graph nodes by failure impact or algorithmic complexity.
  * **Fallback Option — sigma.js / WebGL:** Viable for graphs up to ~10k nodes; high customization for node glyphs and imagery.
  * **Simple DAG Option — react-flow:** HTML/SVG DOM rendering (~1k nodes); ideal for the explicit, user-editable pipeline DAG view.
  * Implement **Semantic Zooming:** Zoom 0 = modules (`animation`, `rlhf`, `mfsr`); Zoom 1 = files (`compositing.py`, `bundle_adjust.py`); Zoom 2 = classes and functions; Zoom 3 = AST or call graph.
  * Implement **Edge Bundling:** **Skeleton-Based Edge Bundling (SBEB)** clusters edges by directional sector and iteratively routes long-distance architectural dependencies along shared skeleton paths, preventing visual clutter without losing directional information.

* **1.3 Software Cartography (Semantic Layout):**
  * Apply **Latent Semantic Indexing (LSI)** to codebase vocabulary (function names, comments, string literals) to map source code into a high-dimensional vector space.
  * Project via **Multidimensional Scaling (MDS)** into 2D, minimizing a stress function so semantically related modules cluster together physically (e.g., `feature_matching.py` and `bundle_adjust.py`).
  * Render as a topographic map rather than a node-link diagram — modules become landmasses, dependencies become edges on geographic terrain.

* **1.4 Dependency Structure Matrix (DSM) — DONE, already implemented, 2026-07-27.** Checked before building anything (per this session's established discipline): a full equivalent already exists and is actively enforced, just not via the imagined Lattix/IntelliJ tooling or a literal matrix rendering — a stronger, automated form of the same idea.
  * **Cyclic-dependency detection** (the matrix's "above-diagonal" violations): `backend/src/utils/validation/check_circular_imports.py` — full AST-based module-import graph builder + iterative Tarjan's SCC algorithm, with an optional interactive `pyvis` HTML visualization. Wired into `just check-circular-imports` and `just module-graph`. Verified working end-to-end this session: 0 cycles across 210 `backend/src` modules and 0 cycles across 236 `gui/src` modules.
  * **Layered-architecture violations** (the matrix's "valid layered dependencies" half): `import-linter` (`pyproject.toml [tool.importlinter]`, §5.11A/A.17) already declares 3 `forbidden`-type contracts (backend core must not import GUI; `gui.src.utils` must not import other GUI layers; `gui.src.classes` must not import `gui.src.tabs`) and enforces them via `lint-imports`. Verified working this session: 578 files / 1147 dependencies analyzed, all 3 contracts kept, 0 broken.
  * Not done, out of scope for this item: any ISO 26262 compliance-report generation (no evidence this project targets that certification) — flagged as an unsupported claim in the original text, not something to build speculatively.

* **1.5 Dynamic Execution Tracing:**
  * Overlay dynamic execution paths onto the static graph. Trace a single ASP run from `video_ingestion.py` through `flow_refine.py` to `sr_stitcher.py`, highlighting active nodes in real-time or via a playback slider.

---

## **Phase 2: ML Model & Loss Landscape Visualizer** {: #phase-2-ml-model--loss-landscape-visualizer }

**Goal:** Open the "black box" of the deep learning models in the pipeline (e.g., `AnimeStitchNet` 4-DoF alignment regressor, BiRefNet foreground segmentation, LoFTR dense feature matching, and DINOv2 pose embeddings) by visualizing weight evolution, feature activations, and objective function geometry.

> **Historical Note (Issue #371, 2026-08-15):** Prior drafts referenced RLHF-style reward models and DRL super-resolution. Those experimental tracks were evaluated and retired in the S200 "great trim" as unverified complexity. Phase 2 is now scoped around the active deep learning components (`AnimeStitchNet`, BiRefNet, LoFTR, DINOv2).

* **2.1 Loss Landscape 3D Surface Plotter:**
  * Implement **Filter Normalization** (Li et al., 2018) to project the high-dimensional loss surface of alignment regressors (`AnimeStitchNet`) into a 2D/3D visualizable space without scale-invariance distortion from normalization layers.
  * Plot the trajectory of the optimizer (e.g., AdamW, Adafactor) across the non-convex loss surface using a TS-based 3D renderer (e.g., Three.js or Plotly.js).
  * Libraries: **`loss-landscapes`** (PyPI), **`loss-landscape-analysis` (LLA)**, or **DeepCAVE** for hyperparameter landscape exploration.

* **2.2 Hessian-Based Landscape Geometry (PyHessian):**
  * Compute the **Hessian Trace** via Hutchinson's algorithm (`Tr(H) ≈ E[z^T H z]` using Rademacher random vectors) to measure local loss landscape sharpness in alignment networks.
  * Compute **Eigenvalue Spectral Density (ESD)** via Stochastic Lanczos Quadrature (SLQ) — builds a tridiagonal matrix whose Ritz values approximate extremal Hessian eigenvalues.
  * Flat minima (low Tr(H)) indicate robust generalization across diverse animation styles; sharp minima indicate propensity to overfit on specific keyframe sequences.
  * Library: **PyHessian** (GPU-accelerated, integrates with PyTorch training loops).

* **2.3 Weight & Gradient Trajectory Tracking:**
  * Track the evolution of network weights and gradients during training (e.g., in `stitch_trainer.py` for `AnimeStitchNet`).
  * Use **PCA**, **t-SNE**, or **UMAP** dimensionality reduction (computed rapidly in Rust/C++) to visualize how latent representations separate different animation styles or displacement regimes over epochs.
  * Platforms: **MLflow**, **TensorBoard**, or **DeepCAVE** for programmatic access to optimization trajectories and hyperparameter importance.
  * Architecture visualization: **Netron** for static network architecture inspection.

* **2.4 Activation Atlases & Feature Inversion:**
  * **Activation Atlases:** Aggregate millions of spatial activations across the benchmark dataset → UMAP → explorable grid of learned visual concepts. Exposes what structural features the feature-matching and segmentation models (LoFTR/BiRefNet) have encoded.
  * **Feature Inversion:** Visualize what specific neural pathways respond to during foreground character extraction and dense keypoint matching.

* **2.5 Attention & Feature Map Overlays:**
  * For transformer-based models (LoFTR, DINOv2, BiRefNet Swin backbones), generate interactive heatmaps of self-attention and cross-attention layers.
  * Overlay these maps directly onto input images in the GUI and web portal to see *where* the model focuses when assessing keypoint correspondence or segmenting foreground cels.


---

## **Phase 3: ASP Stage-by-Stage CV Diagnostics**

**Goal:** Create visual debuggers for classic Computer Vision algorithms that interact within the pipeline, diagnosing why specific mathematical transformations fail.

* **3.1 Locked architecture (Harbinger 2026-08-15): A+B — Rerun sidecar + OTel, no website WASM.**
  * Sequence behind M1 (`PipelineSession`) / alongside M2.5a. Do not implement ahead of the canonical runner.
  * Add a `TelemetrySink` protocol on `PipelineSession` (`on_stage`, `on_artifact`, `on_tensor`). Canonical `run()` must not import `rerun` or `opentelemetry`.
  * **A — opt-in `.rrd` sidecar.** `rerun-sdk` is a `desktop_quality` extra, never a `laptop_balanced` required package. Open in the native Rerun desktop viewer. Dense LoFTR residual tensors and full-res seam cost maps log only when that extra / `ASP_TELEMETRY_DENSE=1` is on.
  * ASP BA is a **2D affine / translation chain**, not a calibrated pinhole reconstruct. `Transform3D` + `Pinhole` + `Points3D` are a visualization metaphor (cameras on the canvas plane, inliers lifted to `z=0`). Every viewer caption must say so.
  * **B — OTel dual-write.** Same emission API writes spans and the named metrics `asp.stage.duration_ms`, `asp.vram.peak_bytes`, `asp.gain.clamp_residual`, `asp.seam.cut_energy`. First backend is local OTLP file or stdout. Prometheus/Grafana/Jaeger/Honeycomb are optional collectors, not in-repo deliverables.
  * **D rejected.** Do not embed the Rerun WebAssembly viewer in `docs/website`. Do not commit `.rrd` files that contain third-party corpus frames.
  * **C fully optional (not scheduled, not low-priority).** A native JSON/NPZ/PNG inspector that re-implements spatial scrubbing inside M6 / `/journal` may be added later if someone wants it. It is not a Phase 3 exit criterion and does not block A+B, M6 Distill widgets, or outreach. See `.agent/reports/grok/phase3_rerun_tradeoffs_20260815.md`.

* **3.2 Feature Matching & Inlier Geometry (The "Bones"):**
  * Visualize SIFT/ORB/LoFTR keypoint matches between frames.
  * Plot fundamental matrix/homography residual errors as a heatmap to instantly spot where rigid body assumptions break (e.g., character movement vs. background panning).
  * Render **2D quiver plots** of sub-pixel alignment errors overlaid on source frames — arrow direction and magnitude represent disparity between estimated homography and true feature locations.

* **3.3 Bundle Adjustment Residual Graphs:**
  * Visualize reprojection errors before and after GNC-TLS Bundle Adjustment (`bundle_adjust.py`) in the Rerun desktop sidecar (A).
  * Show camera origins as a polyline on the canvas plane. This is 2D scroll geometry, not a 3D reconstruct.

* **3.4 Seam Blending & Frequency Domain Mismatch (The "Skin"):**
  * **Spatial Diagnostics:** Render the intelligent scissors routing over the DP seam.
  * **Frequency Diagnostics:** Visualize FFT spatial-frequency profiles (referencing `_seam_freq_profile` in `compositing.py`) to show low/high-frequency mismatches at stitching boundaries.
  * **Gradient Diagnostics:** Display Sobel gradient-direction coherence vectors as a quiver plot across the seam. Circular distance `d_c(∇a, ∇b) = 1 - cos(∇a - ∇b)` rendered as a heatmap highlights photometric tearing regions.

* **3.5 Optional / unscheduled — native inspector (was option C):**
  * A JSON/NPZ/PNG dump rendered inside M6 or `/journal` that duplicates the spatial scrubbing Rerun already provides.
  * **Not a Phase 3, M2.5, or M6 exit criterion.** Not low priority — not on the schedule at all. Recorded so it is not rediscovered as "missing work." Anyone may pick it up later; nothing waits on it.

---

## **Phase 4: Statistical & Information-Theoretic Failure Analysis** {: #phase-4-statistical--information-theoretic-failure-analysis }

**Goal:** Analyze the entire ASP test suite/benchmark corpus (97+ tests) to mathematically cluster failure modes and identify compounding errors.

* **4.1 Information Theory Metrics:**
  * Calculate **Mutual Information (MI)** between pipeline stage outputs and ultimate failure. Does a high residual in Stage 2 (Registration) absolutely dictate a failure in Stage 11 (Compositing), or does the pipeline recover?
  * Use **Shannon Entropy** `H(X) = -Σ P(x) log P(x)` to measure per-frame uncertainty. High-entropy frames (complex foliage) require aggressive RANSAC thresholds; low-entropy frames (flat sky) lack features for rigid alignment.
  * **KL Divergence** tracks data drift through pipeline stages; MI evaluates non-linear dependency between stage outputs.

* **4.2 Formal Causal Discovery (Root Cause Analysis):**
  * Move beyond simple correlation clustering to **causal discovery** — mathematically proving that a failure in Stage 2 *causes* a failure in Stage 11.
  * **Constraint-Based Methods (PC algorithm):** Uses conditional independence tests (Fisher-z, HSIC) to iteratively prune a fully connected graph into a causal skeleton. Implementation: **causal-learn** (Python, CMU Tetrad).
  * **Score-Based Methods (GES):** Greedy Equivalence Search optimizes BIC over Markov equivalence classes. Also available in causal-learn.
  * **Gradient-Based Methods (NOTEARS, DAG-GNN):** Gradient-based causal structure learning scalable via PyTorch GPU. Implementation: **gcastle** (Huawei), ingests Parquet telemetry logs.
  * **Unified API:** **dodiscover** (PyWhy ecosystem) provides a wrapper for systematic algorithm application across these backends.
  * Emit telemetry as **Apache Arrow / Parquet** from benchmark runs for ingestion by causal discovery backends.

* **4.3 Sub-System Destructive Interference Detection:**
  * Implement ablation study visualizations. Map the performance of Algorithm A alone vs. B alone vs. A+B.
  * Highlight benchmark tests where A and B engage in **destructive interference** — measuring negative **Average Treatment Effect (ATE)** on the global success metric (e.g., color correction Stage 4.5 undoing geometric alignment Stage 3, verified via causal DAG).

* **4.4 Failure Mode Clustering:**
  * Aggregate test results and use unsupervised learning (K-Means, DBSCAN) to cluster failures based on pipeline telemetry as a complement to causal discovery.
  * Auto-generate cluster narratives: *"Cluster A failures occur when Frame Entropy < 0.2 AND Reprojection Error > 1.5px. Origin: `fg_register.py`, cascading to `_check_seam_rms_contrast_gate` in `compositing.py`."*

---

## **Phase 5: Resource, Latency, and Causal Profiling**

**Goal:** Track the physical constraints of the pipeline and go beyond "where time is spent" to answer "what actually matters for throughput."

* **5.1 Flame Graphs & Icicle Charts:**
  * **Flame Graphs** (Brendan Gregg): y-axis = stack depth, x-axis = alphabetically sorted sample population (not time), width = relative CPU consumption. Generated via **py-spy** (speedscope JSON/SVG, minimal overhead) or **VizTracer** (C functions, GC, asyncio events — multi-threaded concurrent timelines).
  * **Icicle Charts:** Inverted flame graphs (root at top) — better for deep stacks where entry points remain fixed; superior for top-down bottleneck attribution.
  * Rendered via **Perfetto's tracing UI** for interactive timeline exploration.

* **5.2 Causal Profiling (coz — Virtual Speedups):**
  * Flame graphs identify *where* CPU time is spent but cannot answer: *"Will optimizing this hot path actually speed up the program?"* In concurrent systems, accelerating one thread often moves the wait to the next synchronization barrier.
  * **coz** (Causal Profiling) applies "virtual speedups": to simulate a 20% speedup of Function A, it forces all other concurrent threads to sleep for an equivalent relative duration. By applying this stochastically across thousands of source lines, coz generates a causal impact curve predicting exact throughput gain per unit of localized optimization — using Little's Law for latency estimation.
  * Extensions: **COZ+** (what-if analysis for JS parsing, Chromium); **SLOWPOKE** (distributed microservice-level causal profiling via network-selective slowdowns).

* **5.3 VRAM/RAM Memory Arenas:**
  * Real-time visualization of memory allocation, crucial for identifying leaks in the streaming image merger or SAM-2 interactive masking stages.

---

## **Phase 6: Semantic Code Analysis & Vulnerability Discovery** {: #phase-6-semantic-code-analysis--vulnerability-discovery }

**Goal:** Enable deep semantic querying of the codebase using Code Property Graphs — unifying AST, control flow, and data flow into a single queryable database to detect anti-patterns, data flow violations, and security vulnerabilities.

* **6.1 Code Property Graph (CPG) Architecture:**
  * Generate a CPG merging three classical program representations:
    * **AST:** Hierarchical syntactic structure.
    * **Control Flow Graph (CFG):** Execution order and branching.
    * **Program Dependence Graph (PDG):** Data flow and control dependencies across non-adjacent code.
  * CPGs enable queries impossible on isolated ASTs: verifying that an untrusted input source (PDG) reaches a sensitive sink (AST/PDG) without passing through sanitization (CFG).

* **6.2 Joern (OverflowDB + Scala DSL):**
  * **Joern** generates CPGs via language-specific frontends (including Python and binary via Ghidra) using **fuzzy parsing** — no working build environment required.
  * Stores the CPG in **OverflowDB**, a specialized high-performance graph database replacing Neo4j.
  * Queries via a Scala-based DSL with imperative and functional traversals; identifies specific parameter indices, dispatch types, and polymorphic method resolution chains.

* **6.3 CodeQL (Datalog-Driven Variant Analysis):**
  * Compiles the subject program into a relational database (AST + DFG + CFG).
  * Queries written in **QL** — a declarative Datalog-derived language using first-order logic with recursion; naturally suited for taint-tracking and points-to analysis.
  * **Variant analysis:** A single query discovers every variant of a vulnerability across the full codebase (Python + Rust).
  * **Incremental Datalog solvers** (iQL on Viatra Queries) reduce analysis update time to seconds for differential PR review.

| CPG Engine | Database | Query Language | Compilation | Primary Strength |
|---|---|---|---|---|
| **Joern** | OverflowDB (Graph) | Scala DSL | Fuzzy (no build required) | Fast ingestion, extensible traversal |
| **CodeQL** | Relational Database | QL (Datalog) | Strict compilation required | Whole-program depth, variant analysis, taint tracking |

---

## **Phase 7: Omniscient Debugging & Deterministic Replay** {: #phase-7-omniscient-debugging--deterministic-replay }

**Goal:** Eliminate non-reproducible failures entirely by recording instruction-accurate execution traces and exposing them as queryable databases rather than linear replay logs.

* **7.1 Deterministic Replay with rr (Mozilla):**
  * **rr** captures all non-deterministic inputs to user-space processes from the Linux kernel — system calls, thread scheduling, RDTSC instructions — enabling perfect instruction-level replay with identical memory/register layout.
  * Enables **deterministic reverse execution**: place a hardware data watchpoint on a corrupted canvas pixel and step backward in time to the exact instruction that erroneously overwrote it.
  * Zero code modification required; pairs with GDB for familiar debugging workflow.

* **7.2 Pernosco — The Queryable Execution Database:**
  * **Pernosco** compiles the rr execution trace into an indexed, queryable database. Instead of stepping through time, developers execute relational queries across the temporal axis.
  * Click any `printf` output → instantly retrieve every historical instance that line was executed, with exact stack frames, local variables, and memory state.
  * **Bug Capsules:** Content-addressable replayable bundles (event log + filesystem snapshots + network packets). Integrate into CI/CD: when a flaky test fails, an AI pipeline loads the capsule, queries for suspicious interleavings, delta-debugs the trace, and proposes a bisected patch.

---

## **Phase 8: Distributed Observability & High-Cardinality Telemetry** {: #phase-8-distributed-observability--high-cardinality-telemetry }

**Goal:** Provide production-grade observability across multi-process ASP runs and expose statistical outliers across high-cardinality benchmark dimensions.

* **8.1 OpenTelemetry — Unified Metrics, Logs, and Traces:**
  * Instrument the ASP pipeline with the **OpenTelemetry** SDK (vendor-neutral standard for metrics + logs + distributed traces).
  * Each pipeline stage runs as a **span** with a `trace_id` and `span_id` injected into the execution context — revealing exact causal relationships and stage latency distribution.
  * Export to **Jaeger** (traces), **Prometheus** (metrics), or any OTLP-compatible backend.

* **8.2 Honeycomb BubbleUp — High-Cardinality Root Cause Analysis:**
  * For benchmark telemetry with high-cardinality dimensions (unique test IDs, feature flag combinations, frame content hashes), deploy **Honeycomb BubbleUp**.
  * Statistically compares the distribution of all high-cardinality attributes within an anomalous subset against the baseline to surface the exact combination of variables causing performance degradation — without requiring engineers to know which dimensions to investigate first.

---

## **Phase 9: Formal Verification & State Space Visualization** {: #phase-9-formal-verification--state-space-visualization }

**Goal:** Formally specify and model-check critical concurrent ASP subsystems (e.g., the thread-pool seam computation, HITL checkpoint / session resume) to prove safety and liveness invariants before deployment.

* **9.1 TLA+ Specifications + ModelWisdom:**
  * Write **TLA+** (Temporal Logic of Actions) specifications for critical concurrent subsystems — proving that thread-pool seam cache writes are linearizable and that HITL checkpoint/resume terminates without a lost or double-applied gate.
  * **TLC model checker** explores the full finite state machine.
  * **ModelWisdom** renders the state-transition graph with tree-based structuring, node folding, color-highlighted property violations, and interactive click-through from graphical transitions back to triggering TLA+ formulas.
  * **TLA+ Debugger** supports Watch expressions and backward/forward state-space stepping.

* **9.2 Symbolic Execution & Concolic Testing:**
  * Apply **Concolic Testing** (KLEE / SAGE) to critical validation functions (`_validate_affines`, `_filter_edges`) to auto-generate test inputs guaranteed to cover all conditional branches.
  * SMT solver generates concrete inputs for each path condition; the concolic engine substitutes concrete values when constraints become intractable (e.g., hash functions, floating-point saturation).
  * Visualize symbolic exploration as a branching timeline of path conditions.

* **9.3 SMT Solver Interpretability:**
  * **Axiom Profiler:** Parses Z3 telemetry to reconstruct the causal graph of quantifier instantiations — identifies **matching loops** (infinite instantiation cycles from overly permissive E-matching triggers) visually.
  * **Z3Hydrant:** Maps SMT solver execution telemetry to audio signals via sonification. A matching loop produces characteristic rapid-fire clicking; the human auditory system's superior temporal pattern recognition summarizes millions of solver events in seconds.

---

## **Phase 10: Topological Data Analysis (TDA) of Pipeline Architecture**

**Goal:** Apply algebraic topology to extract scale-invariant structural signatures from the ASP's function call graphs and execution traces — enabling malware-resistant code attribution and robust anomaly detection.

* **10.1 Persistent Homology over Function Call Graphs:**
  * Embed FCG nodes using LLM-generated code embeddings → construct a Vietoris-Rips filtration as the distance threshold ε increases.
  * Track birth/death of topological features by **Betti numbers**:
    * **β₀:** Connected components (isolated subgraphs).
    * **β₁:** One-dimensional loops/cycles (recursive call patterns).
    * **β₂:** Two-dimensional voids (missing dependency layers).
  * Long-lived features on the **persistence barcode** represent fundamental architectural invariants; short-lived features are noise.
  * Libraries: **Ripser**, **Gudhi**, or **Giotto-TDA**.

* **10.2 TDA-Based Behavioral Fingerprinting:**
  * The persistence of specific loop structures (β₁) in the call graph acts as a topological signature of programmer style or module behavior — robust to code obfuscation, renaming, and control-flow flattening.
  * Integrate TDA persistence signatures as features into a **GNN classifier** for detecting architectural regressions or unexpected behavioral drift across pipeline versions.

* **10.3 TDA on ASP Execution Traces:**
  * Apply persistent homology to dynamic memory allocation traces and benchmark telemetry point clouds (each benchmark run = a point in high-dimensional stage-metric space).
  * β₀ changes (new connected components) indicate novel failure modes never before seen; β₁ changes (new cycles) indicate inter-stage feedback loops forming under new conditions.

---

## **Architectural Blueprint: A Zero-Copy Analytics Pipeline**

| Architectural Layer | Core Technologies | Responsibilities |
|---|---|---|
| **Data Generation** (Python) | PyTorch, OpenCV, PyHessian, causal-learn, rerun-sdk, OpenTelemetry | ML execution, CV transforms, Hessian trace, causal DAG, telemetry emission |
| **Aggregation Backend** (Rust) | tokio, tree-sitter, nusy-codegraph, SCIP crate, gRPC/WebSockets | AST parsing, semantic graph construction, Arrow zero-copy aggregation, streaming |
| **Visual Analytics** (TypeScript/React) | cosmos.gl, Three.js, DuckDB-WASM, Perfetto UI | GPU force graphs, 3D surfaces, temporal scrubbing, SQL filtering, flame graphs. Rerun WASM is **not** in the website stack (Phase 3 D rejected). Desktop Rerun opens local `.rrd` sidecars. |

---

## **Phase 11: ASP Benchmark Analytics & Visual Diagnostics** {: #phase-11-asp-benchmark-analytics--visual-diagnostics }

**Goal:** Transform the benchmark dashboard from a summary viewer into a root-cause analysis tool — every failure in the pipeline should be diagnosable from the dashboard without needing to rerun or inspect raw JSON files.

**Priority: HIGH — directly supports ASP quality improvement loop.**

> **Scope split, 2026-07-29 (S266, issue #123).** The *per-test* half of this
> phase — 11.1–11.5 — is **DONE**, implemented inside the ASP evaluation tool
> rather than here, because those five charts answer "why did *this* test score
> badly" while a human is looking at that test, which is precisely the moment
> the answer is useful. They live in
> `backend/benchmark/evaluation/logic/diagnostics.py`, render in the inspector's
> Diagnostics tab (`just asp-benchmark-assess`), and are built from
> `evaluation/other/metrics_view.py`'s flattened series — no metric is
> recomputed, so a chart can never disagree with the report or the verdict logic.
> Per-item notes are inline below.
>
> The **corpus-wide** items stayed here: 11.6 (stage memory waterfall), 11.9
> (cross-run regression dashboard — the evaluation tool has a per-test slice
> of this via a baseline-run selector, but not the corpus view), and 11.10
> (experiment tracker). 11.7 and 11.8 were already done in the static report;
> as of 2026-07-30 (issue #69), 11.6/11.9/11.10 are too — see their entries
> below.

### 11.1 Per-Seam Quality Strip Visualizer — DONE (2026-07-29, issue #123)
Implemented as `diagnostics.seam_quality_figure`: one bar per inter-strip seam
boundary per comparator, with the worst seam annotated. **Deviation from the
spec below, deliberately**: the colour bands use the pipeline's *own* ghost
thresholds (clean < 30, ghost likely 30–60, ghost confirmed ≥ 60, from
`_compute_cqas`) rather than the generic ≥0.80 / 0.60–0.80 / <0.60 split this
item proposed — `ghost_seam_scores` is a 0–100 SIQE scale where lower is
better, so the proposed bands would have been both inverted and unanchored.
Renders an explanation rather than an empty axes when a test has no per-seam
scores, which is the normal case for a SCANS fallback (it has no ASP seams to
score). Linking the driving seam to the DP seam-path cache key is *not* done —
the cache key isn't in the results JSON.

### 11.1 (original spec)
- Render ghost-score, NCC coherence, and Bhattacharyya color-similarity as per-seam bar charts (one bar per seam boundary) instead of only showing the worst-case scalar.
- Color-code each bar: green (≥0.80), amber (0.60–0.80), red (<0.60) — maps directly to the composite quality thresholds.
- ASP-specific: highlight the seam that drives `composite_quality` down and link it to the DP seam path cache key.

### 11.2 Alignment Drift Diagnostic Chart — DONE (2026-07-29, issue #123)
`diagnostics.alignment_drift_figure`: per-frame `tx`/`ty` as a line chart above a
bar chart of the `dy_steps`/`dx_steps` inter-frame deltas, with any step past 2×
the median magnitude flagged in red and both `dy_cv`/`dx_cv` in the title. All
three spec bullets as written.

### 11.3 Photometric Correction Profile — DONE (2026-07-29, issue #123)
`diagnostics.photometric_figure`: `bg_lums` as bars against `applied_gains` on a
twin axis, reference luminance as a guide line, gains deviating from 1.0 by more
than 15% marked with an ✗, and "N/total frames corrected, gain range [min, max]"
in the title. All three spec bullets as written.

### 11.4 Edge Quality & Matching Breakdown — DONE (2026-07-29, issue #123)
`diagnostics.matching_figure`: donut of `matching.methods` beside a
`weight`-vs-`n_pts` scatter, points coloured by frame gap (`j − i`) — a failing
skip-link is a different problem from a failing adjacent pair, which the flat
scatter in the spec would have hidden — and raw/filtered counts plus the kept-%
in the title. The last bullet (flagging datasets with fewer than N−1
high-confidence edges) is **not** done: "high-confidence" has no threshold
defined anywhere in the pipeline, and inventing one here would put a number in
the UI that no gate agrees with.

### 11.5 Ground Truth Comparison Panel — DONE (2026-07-29, issue #123)
Two halves, in the place each belongs. The **table** is
`evaluation/ui/metrics_panel.py`'s ground-truth section (all four GT metrics ×
ASP/Simple, winner tinted by direction). The **chart** is
`diagnostics.gt_comparison_figure`: grouped bars normalized per row, since PSNR
in dB sits an order of magnitude above the SSIM rows and the comparison that
matters is ASP-vs-Simple *within* a row. **Regression detection** is done via a
baseline-run selector in the Diagnostics tab: pick any older
`anime_stitch_*.json` and metrics that moved against their good direction by
more than 3% are called out — the same 3% margin `_gt_verdict` itself uses to
avoid noise-driven verdict flips, rather than this item's unqualified ">3%".

### 11.6 Stage-Level Memory Profiling — DONE (2026-07-30, issue #69)
The RSS tracking already existed as `_log_resource(tag)`'s console-only
prints (§2.6 instrumentation, added for a host-freeze diagnosis); it wasn't
attached to the result JSON. `_log_resource` now takes an optional `store`
dict, `process_dataset` threads a per-dataset `stage_memory_rss_mb: Dict[str,
float]` accumulator through all 9 of its call sites (`dataset_start` through
`dataset_end`), and `_build_result` emits it as
`stage_memory_rss_mb: {stage_name: rss_mb}` in the benchmark JSON — exactly
the schema this item specced. `_report_stage_memory_waterfall()` renders a
waterfall PNG (`stage_memory_waterfall.png`) of RSS averaged per stage
across every dataset in the run, plus a table with the delta from the
previous stage and a callout naming the single largest-growth stage.

### 11.7 Frame Selection Telemetry — DONE (2026-07-27, issue #69)
- Capture and emit `frame_selection: {original_count, smart_select_count, spatial_dedup_count, final_count, selection_mode}` in the benchmark JSON. — data capture already existed pre-#69 (`_build_result()` in `bench_anime_stitch.py`); no pipeline changes needed.
- Dashboard: stacked bar showing frames kept vs dropped at each stage of frame reduction. — added: `_report_frame_selection_telemetry()` renders an aggregate "Frame Selection Telemetry" section (once, near the top of the report) with a matplotlib stacked-bar PNG (`frame_selection_telemetry.png`, kept/dropped per stage per dataset) plus a per-dataset markdown table (original/smart-select/spatial-dedup/final counts, drop counts, drop %, selection mode).
- Identify datasets where smart selection drops >40% of frames (indicates extreme frame redundancy or selection bugs). — added: any dataset over the 40% threshold gets its drop-% bolded in the table and is called out in a summary callout line with links to its `#asp_testNN` section.

### 11.8 Fallback Root Cause Classifier — DONE (2026-07-27, issue #69)
- Classify each SCANS fallback by its trigger gate: `alignment_failed`, `composite_gate_sc`, `composite_gate_sb`, `ghost_gate`, `render_exception` (plus `seam_vis_gate`, a 6th trigger site added to the pipeline after this list was written — the classifier discovers it dynamically rather than hardcoding exactly 5 gates). — data capture already existed pre-#69 (`_fallback_reason` assignments throughout the dataset loop, surfaced as `fallback_reason` in `_build_result()`); no pipeline changes needed.
- Emit `fallback_reason` in the dataset result JSON. — already existed.
- Dashboard: aggregate fallback cause distribution across all datasets — shows which gate is causing the most fallbacks. — added: `_report_fallback_breakdown()` renders a "Fallback Root Cause Breakdown" section (once, near the top of the report) with a total-fallback count, a per-gate count table (parsed from the `fallback_reason` prefix before the first `:`), and a per-gate list of which datasets hit it, linked to their `#asp_testNN` anchor.

### 11.9 Cross-Run Regression Dashboard — DONE (2026-07-30, issue #69)
`detectRegressions()` in `frontend/src/math/benchmark.ts` operates on the
generic `GeneralBenchmark` schema (`{time.avg_sec, memory.avg_peak_mb}`),
which doesn't match `bench_anime_stitch.py`'s ASP-specific per-dataset
fields (`metrics_asp.composite_quality`, `metrics_asp.ghosting_siqe`,
`time.total_sec`) — calling it directly wasn't an option, so
`detect_regressions()` (Python) is a same-threshold reimplementation (5%
quality drop / 10% ghosting increase / 20% time increase, this item's own
numbers) against those fields instead. `_find_latest_baseline()` picks the
most recent prior `anime_stitch_*.json` from `backend/benchmark/output/`
(there's no `--baseline` CLI flag — this auto-discovers it, since
`generate_report()` always runs before the current run's own JSON is
written). `_report_regression_dashboard()` renders a 🔴/🟢 per-dataset table
with the delta % for each of the three metrics.

### 11.10 Comparative Seam Configuration Experiment Tracker — DONE (2026-07-30, issue #69)
`_build_result()` now stamps every dataset with
`experiment_label: os.environ.get("ASP_EXPERIMENT_LABEL")` (unset/`None` by
default) — one label per run rather than per-dataset tagging, since a run is
the unit an experiment actually varies. `_report_experiment_comparison()`
groups datasets by label and renders a comparison table (dataset count, mean
`composite_quality`, mean `total_sec` per label) with a callout naming the
best-quality and fastest labels; runs with no label set (the common case)
get a one-line note instead of an empty table.

---

## **Phase 12: Benchmark Coverage Expansion**

**Goal:** Identify all unmonitored performance-critical and correctness-critical code paths across the Rust core, Python backend, GUI, and mobile layers, then instrument them with targeted benchmarks.

**Current gap analysis:**

| Module | Current Coverage | Impact of Blindspot |
|--------|-----------------|---------------------|
| `base/src/image_converter.rs` | ❌ None | Cannot detect Rust image conversion regressions |
| `base/src/image_merger.rs` | ❌ None | Merge quality and speed unknown at scale |
| `base/src/image_finder.rs` | ❌ None | File-system scan performance on large directories |
| `base/src/file_system.rs` | ❌ None | Bulk file enumeration bottlenecks |
| `gui/src/helpers/image/image_loader_worker.py` | ❌ None | LRU thumbnail cache RAM/throughput unknowns |
| `backend/src/animation/compositing.py` (isolated) | ⚠️ Via ASP | Seam DP, DSFN ramp, Poisson blend not individually profiled |
| `backend/src/animation/matching.py` (isolated) | ⚠️ Via ASP | LoFTR vs phase-correlation trade-off not quantified |
| `backend/src/animation/bundle_adjust.py` (isolated) | ⚠️ Via ASP | Spanning-tree filter and GNC re-solve overhead unknown |
| PostgreSQL + pgvector query latency | ⚠️ Partial | Vector similarity search at 10k/100k image scale not benchmarked |
| App startup time | ❌ None | JVM + Qt + Rust cold-start latency unmonitored |
| App memory (full lifecycle) | ❌ None | Gallery RAM with 100/500/1000 images not tracked |
| Web crawlers (Selenium) | ❌ None | Crawl throughput and timeout rate not measured |
| Mobile (Kotlin/Swift) | ❌ None | Android/iOS render and network performance untouched |

### 12.1 Rust Core Image Processing Benchmarks (HIGH PRIORITY) — **DONE, 2026-07-27**
**Stale premise found and corrected before implementing**: this bullet's
"Create `backend/benchmark/bench_rust_image_processing.py`" is wrong on two
counts — the Rust `base` module was fully retired to C++ well before this
phase was written (see `project_cpp_migration` history), and the file it
asks to create already exists as `backend/benchmark/bench_cpp_image_processing.py`.
That file was silently broken: 5 of its 8 benchmarks called C++ binding
names that don't exist (`cpp_core.convert_image`, `cpp_core.merge_images`,
`cpp_core.scan_directory`), each suppressed with a `# pyrefly: ignore
[missing-attribute]` comment rather than fixed — meaning static analysis
already knew about the gap and nobody acted on it (flagged, not fixed, by
an earlier session this same day; see issue #76/Performance 3.6). Fixed all
5 to the real API (`convert_single_image`, `merge_images_vertical`/
`_horizontal`, `scan_files_single`), also correcting stale "Rayon" doc
references (Rust-only, the real C++ path uses OpenMP). **Verified**: ran
the full corrected file end-to-end — all 10 benchmarks pass (all ✓, no
exceptions), confirming this is a genuine fix, not just a name swap that
happens to parse.

### 12.2 ASP Stage Isolation Benchmarks (HIGH PRIORITY) — **DONE, 2026-07-30**
Created `backend/benchmark/bench_asp_stages.py`, 9 benchmarks on synthetic
panning frames: `_pairwise_match` classical-chain vs with a real
`LoFTRWrapper` attached (guarded — skips cleanly if no GPU/weights);
`_bundle_adjust_affine` with vs without `_spanning_tree_inlier_filter`
(§1.1B); `_composite_foreground` with a cold vs a pre-warmed
`seam_path_cache` dict; `_ecc_refine` at `ECC_MAX_ITER` = 20/50/80 via a
module-attribute monkeypatch (the constant is read fresh from the `ecc`
module on every call, not captured at import time, so this varies it
without touching the pipeline). **Stale premise found**: "with/without
Poisson seam blend" isn't benchmarkable — `_poisson_seam_blend` was removed
from the active compositing module in the 2026-07-09 "great trim" (S200)
along with GraphCut (measured worse than the DP seam path by that same
trim); it survives only in `backend/src/core/image_merger/_legacy_compositing.py`,
a different (non-ASP) feature. Not implemented; documented in the file's
own module docstring rather than silently dropped. **Verified**: ran the
file end-to-end, all 9 benchmarks pass (LoFTR variant included — a real
GPU+weights were available in the verifying environment).

### 12.3 GUI Thumbnail Loading Benchmarks (HIGH PRIORITY) — **DONE, 2026-07-27**
Created `backend/benchmark/bench_gui_thumbnails.py` exactly per spec:
time/memory for `base.load_image_batch()` at N={100, 500, 1000}; LRU
cache miss-then-fill (1000 images through a maxsize=300
`LRUImageCache`, exercising eviction) vs a warm-cache hit path (100
images, repeated lookups, no decode); a direct QImage-vs-QPixmap memory
comparison for 300 cached 180px thumbnails. Runs under
`QT_QPA_PLATFORM=offscreen` (no visible window, per this project's GUI
benchmark convention) — a real `QGuiApplication` instance is still
needed for `QPixmap` construction, kept alive process-wide via a module
global. **Verified**: ran end-to-end, all 6 benchmarks pass. The
QImage/QPixmap comparison produced a genuinely useful number, not just
a smoke-test pass: 300 thumbnails cost 26.1MB as QImage alone, +37.2MB
more once QPixmap copies are also created (63.3MB total) — a direct,
measured confirmation of `LRUImageCache`'s own design rationale
(storing QImage, not QPixmap, to avoid the platform backing-store
copy), not previously measured, only asserted in a docstring.

### 12.4 Database Query Profiling at Scale (MEDIUM) — **rescoped, 2026-07-27**
**Checked before extending anything**: this bullet's premise
(`pgvector` ANN search, `HNSW` vs `IVFFlat`) targets
`backend/src/database/image_database.py::PgvectorImageDatabase`, the
legacy Postgres-backed image database. Per
`unified_database.md`'s own DB.6 status ("Postgres retirement... mostly
done (S211)") and the still-open archival item (issue #64, "archive
legacy Postgres code"), this is an actively-retiring system — building
new benchmark investment against it (Bulk insert, HNSW/IVFFlat
comparison work that Postgres-side code is slated to be deleted) would
not be a good use of this phase's effort. **Not implemented as
originally scoped.** The forward-looking equivalent already exists and
is a better target for a future session: `search_repo.py`'s new
`filter_media()`/`filter_entities()` SQL methods (shipped this session,
issue #63/`unified_database.md` §DB.5) already have correctness tests
in `backend/test/database/test_unified_repos.py` but no *scale*
benchmark (10k/100k-row FTS/filter query latency) — that's the item to
build once someone picks this back up, not a pgvector ANN benchmark for
a database half-way out the door. No code shipped for this sub-item;
this note is the deliverable.

### 12.5 App Lifecycle Memory Profiling (MEDIUM) — **DONE, 2026-07-30**
New `backend/src/core/lifecycle_memory.py`: a phase-tagged RSS logger
(`snapshot(phase)`, `history()`, `alerts()`) mirroring the ASP pipeline's own
`_log_resource()` pattern but for the GUI app's lifecycle. Wired into
`backend/src/app.py::launch_app` at the three phases that fire on every real
run without needing synthetic credentials: `qt_init` (right after
`QApplication(sys.argv)`), `login_window_shown`, and `main_window_shown`
(which, since `VaultManager`/JVM start happens inside the login flow between
those two points, captures the cumulative JVM-start + first-window-construct
cost). Alerts when a phase grows RSS by more than `LIFECYCLE_RSS_ALERT_MB`
(default 200MB, this item's own number; env-var overridable). The "after
gallery load (100/500/1000 images)" phase this item also names can't be
driven from a fixed app.py lifecycle point (it depends on whatever
tab/directory a user opens first) — instead, `backend/benchmark/bench_app_lifecycle.py`
covers it in a controlled, repeatable way via the same `base.load_image_batch()`
path §12.3 already benchmarks for throughput, now wrapped in
`lifecycle_memory.snapshot()` so the alert logic runs against real RSS
deltas. **Verified**: both files run end-to-end (unit tests for the alert
threshold logic in `backend/test/core/test_lifecycle_memory.py`; the
benchmark script ran live, e.g. observed +16MB/+26MB/+12MB for the
100/500/1000-image phases on real image batches — under the 200MB
threshold, so no alert fired, which is itself a useful negative result).

### 12.6 Compositing Component Isolation (MEDIUM) — **DONE, 2026-07-30**
New `backend/benchmark/bench_compositing_components.py`: `_seam_cut()` (S10
vectorized DP) at the item's own 96-seam count, across three canvas heights
(100/500/2000px); `_soft_seam_weight()` (S17 per-pixel DSFN) at canvas
widths 500/2000/5000px; `_build_seam_cost_map()` (S33 column barrier) at
foreground-mask fractions 10%/50%/90% (an exact controllable split, not a
noisy random mask). `_poisson_seam_blend()` (S21) isn't benchmarked here for
the same reason it isn't in §12.2 — removed in the S200 trim, nothing left
in the active pipeline to measure. **Verified**: ran end-to-end, all 9
benchmarks pass with real scaling visible (e.g. `_seam_cut` at h=2000 took
~7x longer than at h=100, consistent with its per-pixel DP cost).

### 12.7 Web Crawler Telemetry (LOW-MEDIUM) — **DONE (scoped down), 2026-07-30**
**Premise partially stale on inspection**: the actual HTTP requests happen
inside the compiled `base` C++ extension (`base.run_board_crawler`), which
only calls back into Python once per successful download (`on_image_saved`)
and via free-form `on_status` progress strings — there is no per-request
hook crossing the pybind boundary, so true per-request timing and
response-code tracking isn't available from Python without new C++-side
instrumentation (out of scope here). What's built instead, in
`ImageBoardCrawler` (`backend/src/web/crawlers/image_board_crawler.py`):
exact whole-crawl `elapsed_sec`/`images_per_sec` (from the real
`on_image_saved` count), plus best-effort `timeout_count`/`captcha_count`/
`error_count` derived by substring-matching `on_status` text — coarse (only
as good as whatever the C++ side happens to emit), documented as such in
the module docstring rather than presented as real response-code data.
`backend/benchmark/bench_web_crawlers.py` drives this against the three
real crawlers and saves a General-suite JSON, gated behind
`RUN_LIVE_CRAWLER_BENCHMARK=1` (unset by default — this file makes real
outbound requests to third-party image boards, not something to run
unattended/in CI). **Verified**: 8 unit tests on the telemetry counters
(`backend/test/web/test_image_board_crawler.py`) pass with a mocked
`base.run_board_crawler`; the benchmark script's default (opted-out) path
ran end-to-end with zero network calls made.

### 12.8 Mobile Performance Baselines (LONG-TERM) — **rescoped, 2026-07-30**
**Not implemented — three independent blockers found, all checked before
writing anything**:
- **Android FPS/scroll benchmarking** needs `androidx.benchmark.macro`
  Macrobenchmark instrumented tests running against a real device or
  emulator; `app/android/build.gradle.kts` has no such dependency
  configured, and this environment has no `adb`/emulator reachable (`adb
  devices` fails — command not found). Gradle/Kotlin toolchains ARE present
  (`gradle`, `kotlinc`), so the Gradle module/dependency setup itself is
  buildable — there's just nothing to execute it against here.
- **"Glide vs Coil thumbnail load time"** has no first side to benchmark:
  neither Glide nor Coil is a dependency anywhere in `app/android/build.gradle.kts`;
  the one place image loading is mentioned
  (`ImagePreviewFragment.kt:141`) is a mocked stub with a comment reading
  "Real app uses Glide/Coil" — aspirational, not implemented. There's no
  A/B to measure yet.
- **iOS is unbuildable in this environment at all**: this is a Linux host
  with no Xcode/macOS toolchain (`xcodebuild`: not found), so no XCTest or
  Instruments run can happen here regardless of app state. Independently,
  `app/ios/Package.swift` declares an `ImageToolkitTests` test target and a
  `Cryptography` target whose directories (`app/ios/ImageToolkitTests/`,
  `app/ios/Cryptography/`) don't exist on disk — the SwiftPM manifest itself
  doesn't resolve today, before any benchmark-specific work would even
  start.

No code shipped for this sub-item; this note is the deliverable (same
approach as §12.4's rescope). The path back to this, in order: (1) populate
the missing iOS SwiftPM targets so the package builds at all, on a
macOS+Xcode host; (2) integrate a real thumbnail loader (Glide or Coil) into
the Android app before there's anything to A/B; (3) add the
`androidx.benchmark.macro` Gradle module and run it against a connected
device/emulator, which this sandboxed Linux CI-style environment doesn't
have.

<!-- TRACK_B_SPEC_END -->

---

## Track C — Host, Plugins, MCP, Local Web

**Status:** 🔄 C1 in progress (data side + lifecycle/discovery landed).

This is the new work that makes D2/D6/D7/D11 real. It should start as
soon as A1 is treated as a library (it already is) — it does **not**
wait for A3–A5 to finish.

### C1 — Host skeleton + Plugin protocol

- `dev/devtool/host/` as described above.
- Discover first-party plugins from `dev/devtool/plugins/`.
- `devtool plugins` lists name, version, surfaces.
- `devtool` with no verb opens the command palette / workspace chooser over
  durable Sessions and Investigations. It must work without a resident daemon.
- Settings own capture channels, retention budgets, alert emphasis, and privacy
  defaults; plugins declare their configurable channels rather than inventing
  hidden environment-only settings.

### C2 — `debugtool` → `devtool` alias

**Superseded by D40** (2026-08-17 debug/dev fold): once C1-C7 all landed,
the fold happened as one pass rather than a gradual migration behind a
"forever" CLI alias. `debug/debugtool` no longer exists as a separate
package — `python -m debugtool` is retired, along with `python -m devtool`
(there is no `tool/__main__.py`; the entry point is `dev/__main__.py`, run
as `python dev/`). What the alias goal actually became: `tool.debug` keeps
the original public API names (`open_session`, `list_sessions`, etc.) as an
*import*-level compatibility surface, permanently — old code only needs
`debugtool` → `tool.debug`, not a full rewrite. Original bullets below kept
for history:

- ~~`python -m devtool` is canonical.~~
- ~~`python -m debugtool` re-exports the same CLI forever (or until a
  dated deprecation the team agrees).~~
- ~~Public API: `from devtool import open_session` works; `debugtool`
  keeps the same names.~~

### C3 — Local web viewer

- `devtool web [--pid N | --investigation NAME | --plugin asp_evaluator]`
- Localhost-only persistent workspace; an ephemeral port is acceptable, but
  opening a Session must restore command-palette navigation and durable context.
- First routes: workspace home / recent investigations, benchmark image-result
  A/B, session HTML timeline (reuse A2 html export), and matplotlib/PNG
  figures from plugin exports.
- Benchmark A/B is the first visual comparison workflow: side-by-side images,
  run/config/provenance, human annotation links, and raw artifact paths. It
  presents evidence; it does not declare a winner or propose a fix.

### C4 — MCP / stdio server

- `devtool mcp` on stdio (Claude/Codex/Gemini/Grok can attach).
- Optional `devtool serve --mcp 127.0.0.1:port`.
- Never binds `0.0.0.0` by default.
- `append_investigation_note` is the only v1 mutation: timestamped, attributed,
  append-only, and restricted to an existing Investigation. All lifecycle,
  command, retention, and settings changes remain human/CLI actions.

### C5 — ASP evaluator plugin

- Adapter around
  `submodules/ASP/backend/benchmark/evaluation/`.
- Does not copy UI code. Registers: discover eval sessions, open the
  existing inspector (`gui` surface), TUI metrics/defects table, web
  image compare.
- Human ratings remain the source of truth; the plugin must not invent
  scores.

### C6 — Benchmarks plugin

- Discover `backend/benchmark/output/` and ASP
  `backend/benchmark/output/`.
- Chart runners already covered by Phase 11–12.
- Emit the access-contract sidecar next to any new plot.
- **First plugin workflow after C1/C3:** select two compatible benchmark runs,
  inspect output image/result A/B with config + provenance, attach human/agent
  notebook notes, and export the evidence bundle. Other diff families do not
  block this slice.

### C7 — Editor integration (D21)

- v1: clipboard export (a Session/finding formatted for pasting into an
  editor or PR description) plus a simple IDE command (e.g. a VS Code task
  that shells out to `devtool`). Not a full extension in v1.
- Consumes the same export surface as A2/C3 — no separate rendering path.
- A real IDE extension (inline gutter annotations, live session status in
  the editor chrome) is a later, separately scoped expansion once v1's
  clipboard/command surface proves useful.

---

## Track D — Development Assistance (D16)

**Status:** ⬜ Scoped (2026-08-17); sequenced after C1 so these land as
plugins, not forks. Each area is a plugin with its own data producer
(a command or wrapper) and one or more host surfaces (TUI / web /
editor / MCP). Harbinger's v1 sequence is benchmark image/result A/B first,
then agentic debugging, then broader developer-debug workflows. Runner
integration + diff/review support the first slice but must not delay it.

### D1 — Build / test / bench runner integration

- Explicit verbs only: `devtool build`, `devtool test`, `devtool bench`,
  `devtool app`, and `devtool repro`. They launch their named workflow under
  telemetry and open a Session carrying command, cwd, env snapshot, and exit
  status. Arbitrary shell execution is deferred to a separately reviewed
  extension.
- Capture channels are selectable per profile: command/env and git state,
  telemetry, stdout/stderr, system/RAM/VRAM, process tree, and screenshots.
- A crash / hang / failure is attributable to a specific command +
  environment, not an orphan JSONL.
- Headless and interactive; the Session then feeds A3 TUI / C3 web / C4
  MCP exactly like any captured run.

### D2 — Diff / review assistance

- Tie Sessions to code changes: record git commit / branch / dirty-hash
  in the Session manifest (no new writer fields needed -- manifest
  metadata, not event fields).
- **First implementation:** `devtool bench compare A B` compares compatible
  benchmark image/result artifacts before and after a change, retaining both
  source run IDs, config, image paths, and human annotations. It must not turn
  a metric into an unqualified "winner" claim.
- Later `devtool diff A B --by-commit` compares event-set, timing deltas, new
  orphans / collisions, and any plugin charts.
- Review surface: a rendered before/after report (notes + charts +
  captures) consumable in TUI, web, and editor.

### D3 — Documentation / knowledge surface

- Annotations on Sessions and Investigations (hypotheses, evidence links,
  notes, decisions) become a searchable durable lab notebook / debug knowledge
  base. Notes are append-only through MCP and editable through the human UI.
- The gallery-crash doc is the prototype: structured notes + evidence,
  queryable instead of prose.
- Search: `devtool search <term>` over annotations + event fields;
  agents query via MCP read-only tools.

### D4 — Performance profiling

- Stage timers, RSS / memory trajectory (already emitted by
  lifecycle_memory), per-API latency, queue depths.
- Consumed by the btop live view and Perfetto static view; no separate
  profiler product.
- Correlate with sessions: a slow span in one run vs. a fast span in a
  diff run is a perf finding, not just a crash finding.

### D5 — Reproducibility artifacts

- One-click bundle: code version, config, repro script, captures,
  manifest -- honoring D20 redaction (large / crash captures stay local
  unless explicitly included).
- `devtool bundle <investigation> [--include-captures]` emits a zipped
  or folder artifact that can be shared or replayed.
- Replay: `devtool repro --from-bundle <artifact>` re-runs the captured
  command under the same telemetry.

### Settings, retention, and alert policy

- `devtool settings` exposes named profiles rather than a fixed global policy:
  capture channels, retention count/age/size, failure/investigation exemptions,
  privacy/redaction, and alert emphasis.
- `devtool prune` always presents the calculated target set and estimated freed
  space before confirmation. Named Investigations and failed Sessions are only
  pruned when their profile explicitly permits it.
- Alert categories (crash, test failure, benchmark regression, memory leak,
  hang, unsafe configuration, review blocker) are independently enabled and
  styled. Defaults are conservative mission-control signals, not judgments.
- No v1 feature recommends a command, diagnosis, or fix. It may offer multiple
  views or filters of the same evidence, with provenance visible in each.

---

## Implementation Status

| Item | Status | Owner | Notes |
|---|---|---|---|
| A1 Session + API | ✅ Complete | deepseek | `debug/debugtool`, 19 tests |
| A2 CLI + export | ✅ Landed | deepseek (#376) | export (json/csv/html), diff, prune, resolve-offset, sidecar index |
| A3 TUI (Perfetto + btop live) | ✅ Complete | Gemini (#377) | `debug/debugtool/ui/`, 14 tests, all 5 views + live watch |
| A4 Repro + gdb | ✅ Landed | deepseek + Gemini (#378) | `devtool repro`, gdb wrap, scenario catalog, hypothesis generator |
| A5 Diff + investigations | ✅ Landed | deepseek (#379) | cross-session diff, RSS trajectory, portable manifest.json |
| C1 Host + plugins | ✅ Landed | deepseek + Grok (D17 / #380) | store + settings (deepseek); Host/discovery/CLI (Grok) |
| C2 devtool alias | ✅ Landed, then superseded by D40 | Grok (#381), Claude (fold) | Was `python -m devtool` canonical + `debugtool` re-export; now `python dev/` is the sole entry point, `tool.debug` is the import-level compat surface |
| C3 Local web | ✅ Landed | deepseek | localhost-only HTTP viewer (`/`, `/session`, `/compare`, `/artifact`) |
| C4 MCP server | ✅ Landed | deepseek (D18) | stdio JSON-RPC 2.0 (`devtool mcp`), read-only tools + note append |
| C5 ASP evaluator plugin | ✅ Landed | Gemini | `devtool.plugins.asp_evaluator`, eval dataset discovery & metrics summary |
| C6 Benchmarks plugin | ✅ Landed | Gemini | `devtool.plugins.benchmarks`, benchmark run discovery & A/B comparison |
| C7 Editor integration | ✅ Landed | Gemini (D21) | `devtool.plugins.editor_integration`, Markdown clipboard export & VS Code tasks |
| D1 (Track D) Runner integration | ⬜ Planned | TBD (D16) | explicit build/test/bench/app/repro verbs → Session |
| D2 (Track D) Diff/review assistance | ✅ Landed | Grok (#388) | git manifest + `bench compare` evidence (not a winner) |
| D3 (Track D) Knowledge surface | ✅ Landed | Gemini (#389) | annotations/sessions/evals search (`search` verb + MCP tool) |
| D4 (Track D) Perf profiling | ✅ Landed | Gemini (#390) | stage percentiles, bottlenecks, jitter (`perf` verb + Rich panel + MCP tool) |
| D5 (Track D) Reproducibility artifacts | ⬜ Planned | TBD (D16) | one-click bundle, redaction per D20 |
| B Phase 11 | ✅ Complete | (historical) | evaluator + report |
| B Phase 12 | 🔄 Partial | (historical) | 12.4 / 12.8 rescoped |
| B Phases 1–10 | ⬜ / research | unassigned | do not block v1 |
| Writer: optional span IDs | ✅ Landed | Grok (D23 / #392) | `telemetry.py` seq/span_id/parent; PipelineSession stage spans |

Existing foundation:

| Artifact | Status |
|---|---|
| `backend/src/core/telemetry.py` | ✅ Complete (IDs not yet) |
| `debug/telemetry_analyzer.py` | ✅ Shim |
| `debug/run_with_gdb.sh` | ✅ Complete |
| `debug/resolve_qt_offset.py` | ✅ Complete |
| ASP `evaluation/` | ✅ Complete (standalone) |
| Math backbones | ✅ Complete |

---

## Open Questions for Team Review

Not re-asking Harbinger's locked D1–D37. These are for @deepseek
@Gemini @Claude (and Harbinger if he wants to override).

**Resolved in the 2026-08-17 brainstorm (now D16–D23):**

- ~~Package move timing~~ → **D19**: keep `debug/debugtool` until C1
  exists.
- ~~Investigation git policy~~ → **D20**: manifests + repro scripts
  committed; JSONL/gdb/hs_err stay local unless a redacted bundle is
  explicitly copied.
- ~~PipelineSession D4 span IDs~~ → **D23**: yes, opt-in, no behavior
  change.
- ~~Who owns C4 (MCP)?~~ → **D18/D17 split**: MCP first surface is
  read-only analysis tools; C1 host-core is deepseek + Grok.
- ~~Build order~~ → **D22**: D4 span-IDs, then C1 host, A3/C3 in
  parallel.
- ~~Editor integration~~ → **D21**: in scope (clipboard + IDE command
  v1, extension later).
- ~~ASP evaluator plugin v1 shape~~ → adapter launches the existing PySide6
  inspector and exports comparison JSON/images to the local web workspace;
  no inspector rewrite in v1 (Gemini consensus).
- ~~btop vs. Perfetto renderer split~~ → one TUI package with switchable live
  and static density profiles (Gemini consensus).
- ~~first two D16 plugins~~ → benchmark image/result A/B is the first
  end-to-end workflow; runner integration and diff/review support it, then
  agentic-debug and broader developer-debug capabilities (D26/D31).

Both resolved 2026-08-17 (Claude brainstorm with Harbinger, now **D38–D39**):

- ~~Explicit v1 exclusion boundary~~ → **D38**.
- ~~Persistent-service promotion trigger~~ → **D39**.

No items remain open from the original three; see [Claude's review pass](#claude--2026-08-17-review-pass-issue-creation-scoping) below for the issue-creation scoping questions this round added instead.

---

## Team Review Notes

### grok — 2026-08-17 (feasibility pass)

Authored this fold. Recommendations above are marked *Grok lean*. I am
not starting C1–C6 until the others have a chance to edit this file.

Feasibility cautions:

- Do not put Rerun WASM or Cosmograph in the public website (already
  locked). The local web viewer is the place for heavy visuals.
- Do not let Track B Phases 6–10 (CPG, rr/Pernosco, TLA+, TDA) inflate
  v1. They stay in this doc so they are not lost.
- `docs/website/public/data/*.json` remains live rating data. This
  tool must not regenerate or overwrite it as a side effect of a
  `devtool` command.
- gdb + JVM: keep SIGSEGV pass-through. I will fight any default that
  re-breaks login-window startup (Addendum 19).

### gemini — 2026-08-17 (TUI architecture, visual design language, & workflow alignment)

Reviewed the expanded scope and aligned with Harbinger's design direction:

1. **On the 3 Open Questions:**
   - **ASP Evaluator Plugin (Q1):** Agree with Grok lean. Implement as an
     **Adapter Plugin** (`devtool eval asp`). In v1, the host launches the
     existing PySide6 evaluator window with synchronized session metadata and
     exports comparison JSON/images to the local web companion (`devtool web`).
     Do not rewrite the 30k-line PySide6 inspector into TUI in v1.
   - **btop Live vs. Perfetto Static (Q2):** Settle on **One TUI Application Package**
     (`dev/tool/ui/`) with a single runtime engine and two switchable operational
     density profiles:
     - `Perfetto Static Face` (`devtool tui --view trace/crash/concurrency/memory`):
       Deep span tree, timeline minimap, and GDB/JVM trace splicer.
     - `btop Live Watch Face` (`devtool watch`): Compact multi-pane dashboard
       with live RSS/VRAM gauges, thread pool activity sparklines, and in-flight
       span ticker.
     - Seamless hotkey toggle (`Tab` / `m`) switches between live monitor and trace
       drilldown without restarting.
   - **Dev-Assistance Plugin Sequencing (Q3):**
     - **1st — D1 (Runner Integration & Submodule Shadowing Isolation):**
       Prevents pytest package collisions (e.g. issue #375 models collision) and
       attributes telemetry sessions directly to test runs / commit SHAs.
     - **2nd — D2 (Diff & Review Assistance):** Generates automated before/after
       delta summaries and formatted AGENT_BUS update payloads.
     - **3rd — D5 (Reproducibility Artifacts):** Bundles portable investigation
       folders (`dev/investigations/<name>/`) with self-describing manifests,
       telemetry logs, and repro scripts for seamless peer-agent handoffs.

2. **Visual Aesthetics & Technical Styling:**
   - Dark slate/obsidian palette with monospace typographic precision.
   - Vibrant amber/rose highlight cues strictly reserved for crashes, orphaned
     in-flight spans, and lock collisions.
   - Clean keyboard shortcuts (`1`–`5`, `j`/`k`, `Enter`, `z`/`x`, `/`, `c`, `q`).

3. **Status:**
   - Phase A3 implementation starting in parallel with C1 host development.

### Chat/Codex — 2026-08-17 (Harbinger product-design pass: benchmark-first workbench)

Recorded Harbinger's decisions D24–D37. The roadmap now centers the first
usable flow on benchmark image/result A/B, entered through a command palette
and examined in a persistent localhost mission-control workspace. Sessions
and Investigations are durable from v1; a background service remains optional.

The new constraints are intentional: explicit runner verbs rather than
arbitrary shell execution, configurable capture/retention/alert profiles,
durable lab-notebook Investigations, evidence-only assistance, and a narrowly
scoped MCP `append_investigation_note` mutation. Existing D18 read-only
analysis remains the default; no MCP execution, deletion, configuration, or
product-default mutation is authorized.

Still open for team review: the first explicit out-of-scope boundary and the
measurable trigger for promoting durable local data into an always-on service.

### Claude — 2026-08-17 (review pass; issue-creation scoping)

Read the full roadmap before brainstorming further with Harbinger — the
document is already thorough (37 locks, clear v1 ordering via the
Implementation Status table and Effort×Impact matrix) so I did not
re-litigate anything settled. Closed the two remaining open questions with
Harbinger directly: **D38** (first v1 exclusion: cloud sync/collaboration)
and **D39** (daemon trigger: when the live-watch view needs push updates
JSONL polling can't deliver, not a pre-picked number).

**Two small accuracy notes, not blocking anything:**

1. Track D's D1–D5 sub-items (Runner integration, Diff/review, Knowledge
   surface, Perf profiling, Reproducibility artifacts) share numbering with
   the top-level Settled Decisions D1–D39. They're in different namespaces
   (Track D's are roadmap *items*, the Settled Decisions are *locks*) and
   the doc's own structure disambiguates them by section, but a bare "D4"
   in a commit message or bus post is genuinely ambiguous between "the
   telemetry-schema lock" and "Track D's performance-profiling item."
   Worth spelling out which one in any future reference.
2. Phase 11's sub-items (11.1–11.10) and Phase 12's (12.1–12.8) cite
   "issue #123" / "issue #69" as their DONE-tracking issues. Neither
   citation is correct in this repo: Image-Toolkit #123 is "[S198]
   Rust→C++ migration" and #69 is "[S245] ASP Phase 4/3.1 follow-up" —
   both closed, both unrelated to Phase 11/12's content. The actual
   per-item tracking issues are Image-Toolkit #159–177 (all closed,
   confirmed live via `gh issue view`), which is what I'm using for the
   project-board migration below. Not fixing the stale in-doc citations
   this pass since Phase 11/12 are fully closed history, not live work —
   flagging so nobody chases a dead reference later.

**Issue-creation scope for this round** (Harbinger's call, brainstormed
live): file GitHub issues for the full roadmap now, including Track B's
Phases 1–10 (long-horizon / research, explicitly "not v1" per the
Effort×Impact matrix, but tracked so nothing is silently lost) — not just
the v1 build queue. One issue per lettered/numbered item (A1–A5, C1–C7,
Track D's D1–D5, the D4/D23 span-ID writer change, Track B Phase 1 through
Phase 10, plus one issue for Phase 12's still-open rescoped tail
(12.4/12.8) — Phase 11 and the rest of Phase 12 are done, closed, and
already tracked by #159–177, so no new issues for those). All filed under
a new `Development Tool` milestone and added to the
[Development Tool project board](https://github.com/users/ACFHarbinger/projects/25/views/1)
(project 25); the 21 closed `analytics_and_interpretability` issues
(#159–177, #371, #372) and #375 (D1's runner-integration motivating case)
move there from the Image-Toolkit project board (#12), since the roadmap
that spawned them is now this file's Track B.

### Chat/Codex — 2026-08-18 (v2 product-design resolution)

Recorded Harbinger's resolution of the v2 shell questions as D48–D61.
The product is a Linux-first Tauri daily driver with a Python sidecar and
a language-neutral process protocol. The existing TUI remains an actual
lightweight/SSH fallback; MCP remains a standalone evidence service. Each
workspace discovers candidates within user-set depth **N**, then monitors
one explicitly selected repository.

The flagship visual is now a persistent, navigable runtime-flow world that
makes nexus modules legible. Benchmark work begins with exact image/result
inspection before comparative analytics. Human and agent annotations are
visibly distinct and durable. Both 4D candidates remain approved, but one
must be selected and tested only after its parent 3D view is useful.

The remaining design work is intentionally technical rather than product
ambiguous: validate the Linux distribution format, specify the sidecar RPC
lifecycle, and select the first bounded 4D spike through the review round.

### (peers append below)

---

## Effort × Impact Matrix

| Item | Effort | Impact | When |
|---|---|---|---|
| D4 span IDs in `telemetry.py` | S | High (honest trees) | Before A3 flame is deep |
| A2 export / prune / resolve-offset | S–M | High | Now (deepseek) |
| A3 TUI Perfetto + btop | M | High | Now (Gemini) |
| C1 host + plugin protocol | M | High | After A1 treated as library (already is) |
| C3 local web | M | High (pixels) | Parallel with A3 |
| C4 MCP | S–M | High (agents) | Parallel with C1 |
| C5 ASP evaluator adapter | M | High | After C1 |
| C6 Benchmarks plugin + A/B workspace | M | **Highest** | First end-to-end product workflow after C1/C3 |
| D1 explicit bench runner | M | High | Supports first benchmark A/B workflow |
| D2 benchmark diff/review | M | High | First comparison; agentic/debug diffs follow |
| A4 repro | M | High (crash loop) | After A2 / benchmark A/B slice |
| A5 investigations | S | Medium | Durable notebook base; parallel with C1 where possible |
| B3 Rerun + OTel | M | High (ASP debug) | Behind PipelineSession |
| B1 / B2 / B6–B10 | L / research | Varied | Not v1 |
| C7 Editor integration (D21) | S | Medium | After C1; clipboard v1 |
| D1 Runner integration | M | High (attributable runs) | Explicit verbs; bench first |
| D2 Diff/review assistance | M | High (before/after) | Benchmark A/B first |
| D3 Knowledge surface | M | Medium | After C1 |
| D4 Perf profiling | M | High | Uses btop/Perfetto; after A3 |
| D5 Reproducibility artifacts | S–M | Medium | After A4 |

---

## Anchor Index

| Anchor | Section |
|---|---|
| D1–D15 | [Settled Decisions](#settled-decisions-2026-08-17) |
| Glossary | [Glossary](#glossary) |
| Contract | [Dual Human / Agent Access Contract](#dual-human--agent-access-contract) |
| `dev/` | [Home: the `dev/` directory](#home-the-dev-directory) |
| A1–A5 | [Track A](#track-a--telemetry--crash-workbench) |
| B / Phase 1–12 | [Track B](#track-b--analytics-benchmarks--interpretability) |
| C1–C7 | [Track C](#track-c--host-plugins-mcp-local-web) |
| D1–D5 | [Track D](#track-d--development-assistance-d16) |
| D16–D40 | [Settled Decisions](#settled-decisions-2026-08-17) |
| D41–D47 | [Settled Decisions](#settled-decisions-2026-08-17) (v2) |
| v2 | [Development Tool v2](#development-tool-v2-2026-08-18) |
| §11.x / §12.x | Historical analytics headings (folded below / in Track B spec) |
