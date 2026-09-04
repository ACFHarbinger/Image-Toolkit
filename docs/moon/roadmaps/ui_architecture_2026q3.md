# UI Shell & Module Runtime Architecture (2026 Q3)

**Status:** Locked, unimplemented (finalized 2026-09-05 after a Claude + Codex
architecture brainstorm, user QA session same day). Tracked under milestone
"UI Shell & Module Runtime Architecture" (#8). Feeds implementation of
`docs/moon/roadmaps/gui_ux.md` §2.36-§2.40.

## Background

`docs/moon/roadmaps/gui_ux.md` §2.36-§2.40 (filed as issues #504-508)
describe a modular shell, theming presets, context inspector, telemetry
status bar, and advanced gallery modes. A prototype for most of these
(`gui/src/modules/{descriptor,registry}.py`, `gui/src/components/navigation/*`,
`gui/src/components/inspector/context_inspector.py`,
`gui/src/components/widgets/telemetry_status_bar.py`,
`gui/src/theming/presets.py`, commit `ef116f0b`) already exists, tested but
**not wired into `MainWindow`**.

Before any of that gets integrated, Claude and Codex independently diagnosed
the same three blockers in `gui/src/windows/main/_tab_registry.py` and
`main_window.py`:

1. All 25 tool tabs are eagerly constructed in `_create_tabs()` before the
   window shows.
2. Tabs are wired together via direct object references held at construction
   time (`database_tab.scan_tab_ref = self.scan_metadata_tab`,
   `main_window_ref = self`) — you cannot hand out a reference to a widget
   that hasn't been built, so eager construction can't be removed without
   fixing this first.
3. `"Image Stitching"` maps 8 registry entries onto panels of one `StitchTab`
   instance — a naive one-descriptor-per-widget registry doesn't model this.

This document records the finalized decisions from that brainstorm (Claude's
initial read, Codex's independent counter-proposal, and the user's calls on
each disputed point) as the accepted design to build against.

## Finalized decisions

### 1. Module catalog & lifecycle runtime (Codex's design, accepted)

Replace the prototype's global `ModuleRegistry` singleton with an app-owned
`ModuleCatalog`, created by the composition root and passed to the shell.
Descriptors are immutable metadata (`module_id`, category, title/icon/search
terms, capability flags, ordering) plus a factory taking a `ModuleContext`
(event hub + non-UI services — never another tab/widget).

The catalog distinguishes:
- **Page descriptors** — independently mountable lazy pages.
- **Workspace descriptors** — one stateful host plus named routes within it.
- **Route descriptors** — navigation entries targeting a workspace route;
  must not create/mount a second copy of the host.

Factories return a lifecycle handle (`widget`, `activate(route)`,
`deactivate()`, optional `dispose()`), not a bare `QWidget`. Rejects the
prototype's `get_widget()` as sufficient lazy loading on its own.

### 2. Typed event bus: Intents / Facts / Requests (accepted, narrows the
original "full signal bus" call)

A GUI-thread `QObject` owned by the app, with explicit versioned dataclass
events, split into three contracts (not one generic message bus):

1. **Intents** — commands a shell/router subscribes to and acts on
   (`Navigate(module_id, route?, state?)`, `OpenListingFilter(...)`,
   `ImportPaths(...)`). Publishers never find or retain a widget.
2. **Facts** — broadcast events, optionally coalesced for noisy
   progress/telemetry (`SelectionChanged`, `ScanCompleted`,
   `DatabaseAvailabilityChanged`).
3. **Requests with explicit replies** — typed service APIs/futures (e.g. a
   database query). **Explicitly kept off the bus** — no hidden
   synchronous event-bus calls standing in for a service call.

Every event carries an origin/correlation ID (telemetry, loop prevention).
Pub/sub ownership is bound to module lifecycle and disconnected on dispose.
The existing `database_tab.*_tab_ref` / `main_window_ref` links migrate to
typed intents first (Database/Scan/Search/Listings/Wallpaper cluster — the
clearest direct-reference case); legacy adapters translate during rollout.

### 3. Stitch is one workspace, not eight modules (accepted)

Model Image Stitching as a single `StitchWorkspace` descriptor whose factory
creates the one `StitchTab`/shared model. Its 8 catalog routes (`stitch.adjust`,
`stitch.canvas`, etc.) reference `workspace_id="stitch"` + a route key.
Activating a route asks the existing workspace handle to switch its panel —
never a second `StitchTab` or duplicated pipeline state.

### 4. Shell migration: MainWindow stays composition root (Codex's
conservative path, accepted over the more consolidated alternative)

Do **not** fold `MainWindow`'s 14 mixins into `ShellLayoutManager` in one
pass. `MainWindow` keeps its current MRO and `closeEvent`/`keyPressEvent`/
`showEvent`/`wheelEvent` overrides intact initially — mixin order there is
load-bearing (see the MRO-hazard comment at
`gui/src/windows/main/main_window.py:44-64`). The new shell mounts as a
child controller/widget where the category `QComboBox` + `QTabWidget`
currently live. Mixin responsibilities move out one at a time later, each
with regression coverage for close/key/show/wheel behavior.

### 5. Module lifecycle & caching policy

Inactive module widgets stay cached per account/session for responsive
tab-switching, evicted under a measurable memory policy (e.g. LRU beyond N
inactive modules) rather than always-dispose-on-deactivate. Exact threshold
is an implementation detail to tune with real memory numbers, not a
pre-locked constant.

### 6. Old-shell rollback bar & fallback duration

The new shell is the default once rolled out behind a per-account
experimental setting. The classic category-combo + `QTabWidget` shell stays
available as the rollback path until the new shell demonstrates parity on:
keyboard navigation, session/tab-config restore, and `Ctrl+T` tab search.
**Per the user's direction to Codex**, how long the fallback stays available
after that parity bar is met (one release vs. permanent user preference) is
an explicit post-rollout decision, made from real evidence (navigation,
accessibility, restoration, performance, support burden) — not decided now.

### 7. Sequencing vs. the 1.0.0 release

This work proceeds in parallel with 1.0.0 release-acceptance, on an isolated
branch / behind feature flags. No release-acceptance branch consumes it
incrementally — each delivery step below is independently mergeable or
fully feature-flagged, and 1.0.0's build/verification window stays clean.

### 8. Scope: broader than the 5 new roadmap entries

Per the user's answer on proposal scope, this covers architectural debt
found along the way in specific tab families (e.g. `StitchTab`'s
multi-panel structure), not just shell chrome — flagged as found, not
required to be exhaustive up front.

## Delivery sequence (Codex's proposal, accepted)

1. Freeze a written module/route inventory from `all_tabs`, including direct
   refs and eager-import cost; add contract tests without changing visible UI.
2. Build catalog, context, lifecycle handle, typed event hub, and legacy
   bridge in an isolated feature branch. Register metadata for all modules
   but keep the old shell authoritative.
3. Convert Database/Listings/Scan navigation to typed intents first.
4. Introduce `StitchWorkspace` routes behind a feature flag, asserting all
   eight routes share one host/model.
5. Mount rail/ribbon (from the existing prototype, adapted to the lifecycle-
   handle contract) through the shell behind a per-account experimental
   setting. Preserve the old shell as rollback until lifecycle, session
   restore, Ctrl+T, and config import/export pass.
6. Integrate inspector, telemetry, presets, then §2.40 gallery modes only
   after module contracts are stable. Gallery overlays must be pure
   model/view presentation state — no direct tab references.

## Open items (not blocking delivery start, revisit as data arrives)

- Event schema ownership/versioning process.
- Logout/account-switch disposal semantics for cached module state.
- Exact LRU/memory-pressure threshold for module widget eviction.
- Fallback shell retirement decision (see §6 above) — explicitly deferred to
  post-rollout.

## Related

- Feature-level issues: #504 (§2.36 shell/registry), #505 (§2.37 theme
  presets, milestone "App Theming & Customization"), #506 (§2.38 inspector),
  #507 (§2.39 telemetry), #508 (§2.40 gallery modes — depends on this
  document's contracts per its bus note).
- Runtime issues: see milestone "UI Shell & Module Runtime Architecture" (#8).
- `.agent/bus/2026-09-05.md` for the full brainstorm thread.
