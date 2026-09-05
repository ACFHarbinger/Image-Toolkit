# UI Shell & Module Runtime Architecture (2026 Q3)

**Status:** Locked design; implemented once, crashed, fully reverted;
**re-land pending** on the Phase 0/1 contracts (2026-09-05, same day as the
crash). Tracked under milestone "UI Shell & Module Runtime Architecture"
(#8). Feeds implementation of `docs/moon/roadmaps/gui_ux.md` §2.36-§2.40.

**What actually happened (2026-09-05, all same day):** this design was
built and merged in full — issues #509-514 (module/route inventory,
`ModuleCatalog`+`ModuleContext`+typed event hub+lifecycle runtime,
Database/Listings/Scan typed-intent migration, `StitchWorkspace`,
rail/ribbon shell mount, inspector/telemetry/theming/gallery-modes
integration) plus a further layer of GUI/UX features built on top
(§2.x: MotionKit, per-category theming, command palette, undo/redo, tag
chips, gallery filter/sort, thumbnail zoom, inline rename, contact
sheets, rating/color labels, window layout profiles, QSplitter
persistence, log panel — issues #515-519). It then caused a real,
reproducible crash and was **fully reverted** (`7559b1d2`,
`git checkout b4f61deb -- gui/` + explicit deletion of everything `gui/`
gained since). `docs/` and `.agent/` were deliberately left untouched by
the revert, which is why this document — describing the reverted design
— still reads as current.

**The crash decomposes into two independent causes, only one of which
this document is responsible for:**

1. **Shell-specific, structural, unresolved:** eager module-mounting
   combined with the rest of the day's changes produced a `QSocketNotifier`
   cross-thread violation → SIGSEGV, then a second crash reproducing as
   SIGKILL. This is not this design's first strike either — an earlier,
   narrower attempt at eager mounting
   (`4f95e94e Revert "feat(gui): eagerly mount every runtime-shell module
   instead of lazy activation"`) was already reverted once *before* the
   full revert. **Any re-land must structurally prevent eager mounting of
   shell modules, not merely avoid it by convention** — e.g. a contract
   test asserting lazy activation, not just code review discipline.
2. **Not shell-specific, already fixed:** "general slowness and directory-
   browsing freezes even with the experimental shell disabled" — this was
   the §2.x feature layer's own bugs, and their root causes (unserialized
   native-decode concurrency, non-visible-first thumbnail dispatch, GIF
   decode with no disk-cache participation, an eager unbounded directory
   auto-load) are exactly what Phase 0 of the architecture deep-dive
   (`.agent/reports/team/architecture_deep_dive_2026-09-05.md`) locked
   down and fixed, independently of this document, before this document's
   own re-land could start.

**Net assessment:** this design has one known, still-open structural
defect (eager shell-module mounting) with a two-strike history, and its
independent co-factors are gone. That is different from "this whole
design is unsound" — treat the two causes separately when re-landing;
don't let (2) being fixed be read as evidence (1) is fixed too, and
don't re-litigate the whole design over a defect that's actually
narrow and already understood.

**Foundation now available that did not exist when this crashed:**
Phase 0 (native-decode lock, visible-first dispatch, one-owner tray
preference, non-destructive prototype quarantine) and Phase 1
(`PreferenceStore` — including a natural home for this doc's §6
per-account experimental-shell-setting requirement; `ThumbnailScheduler`
interface; `ModuleDescriptor`+`ModuleHost` pilot; `WindowManager`;
backend `Observable`/`QtEventBridge` Qt-decoupling; CI import-boundary
guardrails) are both complete and merged (`.agent/reports/team/
architecture_deep_dive_2026-09-05.md`, §5-7). D10 in that report records
explicit intent to re-land this design on top of those contracts, not
to re-run it as-is.

**A module-registry naming collision to resolve before any re-land
code lands** (see the git history for exact commits): there are now
**three** separate `ModuleDescriptor`-shaped things, two of them sharing
the literal path `gui/src/modules/`:

1. `gui/src/protos/modules/{descriptor,registry}.py` — the original
   quarantined prototype (`ef116f0b`), simple one-descriptor-per-widget
   model, non-destructively parked per D11.
2. The reverted runtime's `gui/src/modules/{catalog,context,events,
   runtime,legacy_bridge}.py` (`a9d01085` et al., recoverable via
   `git show <commit>:<path>` even though absent from the working tree)
   — the actual implementation of *this* document's design: `Page`/
   `Workspace`/`Route` descriptor kinds (directly solving §3's "Stitch is
   one workspace, not eight modules"), `ModuleContext` (event hub +
   non-widget services), lifecycle handles. Its `events.py` is a
   GUI-thread `QObject`-based `EventHub` (Intents/Facts dataclasses,
   versioned schema) — this is a *different, complementary* layer from
   Phase 1's `Observable`, not a competing one: `Observable` solves
   backend-thread-to-GUI-thread safety (the crash-class concern),
   `EventHub` solves GUI-thread module-to-module coordination (widget
   decoupling). They can coexist.
3. Phase 1's shipped `gui/src/modules/{descriptor,host,registry}.py` +
   `pilots/` (#527) — built fresh, independently of (2) since (2) was
   invisible (quarantined+reverted) at the time, for a narrower
   immediate goal (proving the `ModuleHost` pattern against the Log
   Panel). Its `ModuleDescriptor` has `singleton`/`construction_policy`/
   `child_routes` but no `Page`/`Workspace`/`Route` distinction — it
   cannot yet model Stitch's 8-routes-one-host case the way (2) can.

**Recommendation (not yet decided — needs sign-off before code):**
treat (2)'s catalog/context/runtime design as the source of truth for
re-landing this document's contract (it *is* this document, already
built), rebased onto current `ModuleHost`/`WindowManager`/
`PreferenceStore`/`Observable` rather than cherry-picked as-is (it
predates all of Phase 0/1 and reintroduces their fixed bugs if
reapplied verbatim). Fold Phase 1 #527's useful, narrower additions
(the Log Panel pilot itself, its `singleton`/`construction_policy`
fields where they don't conflict) into the richer model rather than
maintaining two `ModuleDescriptor`s. This is a real fork point, not a
detail — get explicit confirmation before writing code that depends on
either lineage.

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

- Feature-level issues: #504 (§2.36 shell/registry, still open — the
  parent tracking issue), #505 (§2.37 theme presets, closed, milestone
  "App Theming & Customization"), #506 (§2.38 inspector, open), #507
  (§2.39 telemetry, open), #508 (§2.40 gallery modes, open — depends on
  this document's contracts per its bus note).
- Runtime issues (all closed, all reverted): ui-arch-1..6 / #509-514,
  plus follow-ups #515-519. See milestone "UI Shell & Module Runtime
  Architecture" (#8).
- Revert: `7559b1d2` (`git checkout b4f61deb -- gui/` + deletion of
  everything gained since); the reverted implementation commits remain
  recoverable via `git show <commit>:<path>` (e.g. `a9d01085` for the
  runtime layer) even though absent from the working tree.
- `.agent/bus/2026-09-05.md` for the full brainstorm thread **and** the
  later crash/revert/root-cause narrative in the same file.
- `.agent/reports/team/architecture_deep_dive_2026-09-05.md` — the
  post-revert root-cause analysis and Phase 0/1 rebuild this document's
  re-land now depends on. D10 records explicit re-land intent; D11
  records the prototype-quarantine non-destructive intent.
- `docs/moon/roadmaps/ui_module_inventory_2026q3.md` — the #509 baseline
  inventory; still factually accurate against the live (reverted-to)
  `_tab_registry.py`, but its own contract test
  (`gui/test/modules/test_legacy_module_inventory.py`) was lost in the
  revert and needs recreating before this document's step 1 restarts.
