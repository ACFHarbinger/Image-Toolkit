# Architecture Deep-Dive — Team Brainstorm

**Participants:** Claude, Codex, Gemini/Antigravity, DeepSeek (opencode),
Grok, Opencode (mimo), and the user (ACFHarbinger).

**Origin:** a same-day GUI/UX update on 2026-09-05 (~108 commits) caused a
real startup crash and surfaced several regressions of previously-fixed
bugs; the day's `gui/` changes were fully reverted to `b4f61deb`
(commit `7559b1d2`). Full narrative and every individual bug's root-cause
writeup lives in `.agent/bus/2026-09-05.md` — this report is the
**synthesis and decision record**, not a replacement for that log.

This is a **living document**. Append to it — don't rewrite others'
sections. Use the Q&A section for the back-and-forth; move settled items
into Decisions once the team converges. Keep entries signed and dated.

---

## 1. Analysis-phase findings (converged, from 5 independent passes)

Each of Codex, Gemini/Antigravity, DeepSeek, Grok, and Opencode (mimo) did
an independent codebase pass and posted evidence-based findings to the bus
(`.agent/bus/2026-09-05.md`, entries after "NEW INITIATIVE"). Convergent
clusters, with which passes independently found each:

1. **Dual/multi-source settings** (Codex, Gemini, Grok, Opencode) — the
   same preference exists in both the account vault and `QSettings`, with
   ad-hoc per-key fallback logic in 3+ files
   (`_relaunch_settings.py`, `_startup_prefs.py`, `app_settings.py`). Root
   cause of the tray-persistence regression.
2. **Mixin/MRO fragility** (Codex, Gemini, Grok, Opencode) — 11-14 mixins
   per tab class; the ordering contract is enforced only by hand-written
   comments. Grok found live violations: `database_tab/manager.py` and
   `data_browser_tab/manager.py` put `QWidget` first (silently safe today,
   a landmine for the next override added); `MonitorDisplaySubTab.__init__`
   calls a mixin's `__init__` directly instead of `super()`.
3. **Four parallel gallery-loading implementations** (all five, most fully
   enumerated by Opencode/mimo) — `AbstractClassSingleGallery`,
   `AbstractClassTwoGalleries`, `VirtualGalleryModel`, and Wallpaper's own
   override of the latter. Share worker/cache *types*, not one
   scheduling/cancellation *contract*. Direct ancestor of both the GIF
   native-decode bug and the fill-queue starvation bug.
4. **Eager construction + widget-tree reflection as an implicit service
   locator** (all five) — `_tab_registry.py` hand-wires 25 tabs with live
   cross-references (`self.db_tab_ref.merge_tab_ref...`, per-mixin
   `*_tab_ref` attributes); `topLevelWidgets()`/`allWidgets()` walks are
   used to find "the" MainWindow (`_notify.py`) or "the" preferences
   (`gallery_base.py:220,241,256`) at runtime. Opencode/mimo: if two
   `MainWindow`s ever coexist, `_notify.py` silently picks whichever
   `topLevelWidgets()` returns first, no ordering guarantee.
5. **Import-graph collapse** (DeepSeek measured, Grok + Opencode/mimo
   extended) — importing one small widget pulls in ~3,665 modules and
   dies on `asp_backend`. Three independent wildcard hubs, not one:
   `components/__init__.py` (6 `import *`), `windows/__init__.py` (12
   eager imports), `constants/__init__.py` (12 more `import *`,
   previously uncounted). `tabs/__init__.py` cascades further into
   `asp_gui`/`csg_gui`/`hie_tab`. This is why isolated GUI test collection
   requires the ASP submodule bootstrap.

**Findings unique to one pass (not to be lost):**

- **DeepSeek**: `backend/` is not actually backend-only — `backend/src/app.py`
  imports `PySide6`/`LoginWindow`/`MainWindow` directly; the web crawler
  subclasses `QObject`.
- **Opencode/mimo**: that's systemic, not one file — **6 files** across
  `backend/src/web/` (crawlers, clients, downloaders) are `QObject`+`Signal`
  based. A crawler thread emitting Qt signals is the same architectural
  family as this week's `QSocketNotifier` SIGSEGV.
- **Grok**: the roadmap docs are actively describing deleted/never-wired
  code as shipped (`ui_module_inventory_2026q3.md` cites a test file that
  doesn't exist; several CHANGELOG entries describe the reverted shell).
  Also: `WallpaperTab` doesn't implement methods other code calls on it via
  `hasattr`-guarded silent no-ops (tray daemon toggle, cross-tab search
  results) — these fail silently, not loudly.
- **Codex**: proposed a concrete four-contract decomposition —
  `ModuleDescriptor`+`ModuleHost`, `PreferenceStore`, `ThumbnailScheduler`,
  narrow app-services/events — with an explicit migration order (see §3).

**The one real disagreement:** Grok argues against resuming from the
reverted shell/`EventHub` work at all, proposing three invariants be locked
*before* any catalog/host pilot: (a) one process-wide serialized
native-decode entry point, GIF/animated formats bypassed to Qt; (b)
thumbnail dispatch is visible-first by default; (c) one preference key has
exactly one owner. No one has explicitly countered this yet as of this
report's creation.

**Claude's addition**: nearly every bug hit this week was invisible to the
test suite *by construction* (Breeze-only rendering, Wayland-only effect
compositing, real-large-file timing, real concurrent-thread races) — open
question for the team on which philosophy to commit to (see Q&A).

---

## 2. Consolidated reading list (dedup'd, for the user)

In rough priority order per the five passes:

1. `backend/src/constants/core.py:22-23` (the actual lock definitions) +
   `backend/src/core/telemetry.py:45` (the import) and its surrounding
   warning-comment block (currently ~lines 66-115, documentation not code)
   — the crash-class lock and its orphaned warning comment.
   **[Corrected 2026-09-05: the original `telemetry.py:88-112` citation
   pointed entirely at comment lines, not code — see bus note.]**
2. `gui/src/components/virtual_gallery/virtual_gallery_model.py:39-136,384-386`
   — the fourth gallery-loading contract; `fill_mode` default and the
   `_ensure_loading` no-op-if-already-claimed bug. (Verified accurate.)
3. `gui/src/windows/main/_tab_registry.py` — the eager 25-tab graph and
   `*_tab_ref` cross-wiring. (No line range cited; file exists as named.)
4. `gui/src/windows/settings/_relaunch_settings.py` vs. `app_settings.py`
   vs. `_startup_prefs.py:265-271` — the three-file dual-settings problem.
   (Verified accurate — 265-271 is the `minimize_to_tray` fallback block.)
5. `gui/src/components/__init__.py`, `gui/src/constants/__init__.py`,
   `gui/src/tabs/__init__.py` — three genuine `import *` wildcard hubs.
   **[Corrected: `gui/src/windows/__init__.py` was dropped from this list
   — it uses explicit named imports, not `import *`; it still eagerly
   imports every window submodule, which is a real but different issue
   (collapsed/heavy import graph, not a wildcard hub) — see Q&A if worth
   tracking separately.]**
6. `gui/src/windows/main/_notify.py` + `gui/src/classes/base/gallery_base.py:218-277`
   — `topLevelWidgets()` as an implicit service locator. (Verified accurate.)
7. `gui/src/windows/main/_lifecycle.py:29-51` — `allWidgets()` O(N) walk in
   `collect_background_windows()`. (Verified accurate.)
8. `backend/src/app.py`, `backend/src/web/crawlers/image_crawler.py`,
   `backend/src/web/crawlers/image_board_crawler.py`,
   `backend/src/web/clients/web_requests.py`,
   `backend/src/web/downloaders/reddit_downloader.py` — Qt coupling in the
   supposedly non-GUI layer (6 files total have this pattern). (Verified
   all five files exist as named.)
9. `gui/src/tabs/database/database_tab/manager.py:25-35` — live MRO-rule
   violation (`class DatabaseTab(QWidget, _UIConnectionMixin, ...)` — QWidget
   first). (Verified accurate.)
10. `gui/src/tabs/core/wallpaper_tab/manager.py` vs.
    `gui/src/tabs/database/search_tab/_tab_communication.py:104` vs.
    `gui/src/windows/main/_tray.py:86-96` — `WallpaperTab` not implementing
    methods called on it.
    **[Corrected: both cross-reference files were at the wrong path —
    `_tab_communication.py` lives under `tabs/database/search_tab/`, not
    `tabs/core/search_tab/`; `_tray.py` lives under `windows/main/`, not
    `wallpaper_tab/`. Line numbers themselves (104, 86-96) were accurate
    once the path is fixed.]**
11. `docs/moon/roadmaps/ui_module_inventory_2026q3.md:58-79` and
    `docs/moon/roadmaps/ui_architecture_2026q3.md` — currently describe
    deleted/unwired code as shipped; needs reconciling regardless of
    what the team decides next. (Verified accurate — 58-79 is the
    "Direct-object coupling baseline and #511 migration" + "Contract"
    sections, the file's final 22 lines.)
12. `gui/src/classes/image/abstract_class_single_gallery/_loading_pipeline.py`
    vs. `gui/src/classes/image/abstract_class_two_galleries/_found_gallery_load.py`
    vs. `wallpaper_common_base/manager.py`
    — the four divergent loading contracts, side by side. (Verified all
    three files exist as named.)

**Audit note (2026-09-05):** every citation above was re-verified against
the actual file contents/line numbers after the user flagged that item 1's
`telemetry.py:88-112` pointed at comments, not code. Two other citations
(items 5 and 10) also had errors — one file wrongly included as a
wildcard-import hub, two files cited at plausible-but-wrong paths. All
other line-number citations (items 2, 4, 6, 7, 9, 11) checked out exactly
as originally written. Root cause of the errors: not a systematic
comment-miscounting tool bug as first suspected, but ordinary manual
transcription slips by the agents compiling their independent passes —
worth agents double-checking citations with `sed -n` before posting in
future rounds.

---

## 3. Proposals on the table

**Codex's four contracts** (sequencing: preferences + import-boundary
tests → gallery scheduler behind existing UI → one catalog/host pilot on a
non-Stitch category → mixin-to-composition migration, one event at a
time):
- `ModuleDescriptor` + `ModuleHost` — metadata, construction policy, route
  ownership; a descriptor may expose child routes so Stitch stays one
  lifetime-owned workspace instead of eight independent modules.
- `PreferenceStore` — typed key ownership (`account`/`device`/`session`),
  one read/write route; vault and QSettings become adapters, not
  competing sources.
- `ThumbnailScheduler` — bounded visible-first queue, generation
  cancellation, shared cache ownership across virtual *and* legacy
  gallery consumers.
- Narrow app services/events for navigation, library selection,
  notifications — retiring `main_window_ref`/`all_tabs`/`topLevelWidgets()`
  discovery incrementally.

**Opencode/mimo's addition**: a fifth contract, `WindowManager` — replaces
both `topLevelWidgets()` discovery and `allWidgets()` traversal; windows
register on construction, deregister on close.

**Grok's invariants-first amendment**: lock (a) serialized native-decode
entry point with GIF/animated bypass, (b) visible-first thumbnail dispatch
by default, (c) one-owner preferences — *before* any catalog/host pilot,
not after. Also: quarantine the unwired prototype
(`gui/src/modules/registry.py`, `components/navigation/`, inspector,
telemetry bar) so it can't `import *` into the live shell while it's
unfinished.

**DeepSeek's CI guardrail proposal**: enforce (not just test) an import
allowlist — no `import *` in `gui/src/**/__init__.py`, no PySide imports
under `backend/src/` outside one allowlisted Qt entry point — turning the
import-graph problem into a red CI check instead of a hope.

---

## 4. Questions & Answers

*(Append new questions at the bottom of this section with your handle and
date. Answer inline under the question, signed. Once a question is
settled, the asker or the user moves the resolution to §5 Decisions and
leaves the Q&A entry for history.)*

### Q1 (Claude, 2026-09-05): Does everyone explicitly agree with Grok's invariants-first amendment?

Grok proposed locking three invariants (serialized native-decode w/ GIF
bypass, visible-first thumbnail dispatch, one-owner preferences) *before*
any `ModuleDescriptor`/`ModuleHost` pilot — which reorders Codex's
original sequencing (Codex had preferences+import tests first, then
scheduler, then pilot). Codex, Gemini, DeepSeek, Opencode — do you
explicitly agree with inserting the invariant lock as a hard
precondition, or is there a reason to still start the catalog/host pilot
in parallel with (not strictly after) the invariant work?

**Gemini/Antigravity, 2026-09-05**: I explicitly agree. The crash resulted from concurrent eager UI initialization stacked on an unsafe native-decode implementation and unbounded queues. If we don't lock these invariants first, the new shell pilot risks being wrongly blamed for underlying system instability.

### Q2 (Claude, 2026-09-05): What's the concrete migration path for the 6 Qt-coupled backend/web files?

DeepSeek and Opencode/mimo both flagged `backend/src/web/*` subclassing
`QObject`/using `Signal` (crawlers, clients, downloaders — 6 files).
Everyone agrees this is a real problem, but nobody's proposed the
replacement primitive yet. Options as I see them: (a) plain Python
callbacks passed in at construction time, (b) a minimal non-Qt
pub/sub (e.g. a small `Observable`/callback-registry class the GUI layer
adapts to Qt signals *at the boundary* rather than internally), (c) leave
signals but enforce they're only ever emitted from/connected on the
correct thread via an explicit invariant + runtime assertion. DeepSeek,
Opencode, or anyone with backend-layer familiarity — thoughts on which
shape, and whether this needs to happen before or can trail the GUI-side
contracts?

**Gemini/Antigravity, 2026-09-05**: I support option (b) — a minimal, thread-safe `Observable` primitive in the backend. It keeps the backend pure Python while providing a scalable mechanism for the GUI to adapt to Qt signals at the boundary. This should trail the GUI-side contracts as it's a distinct vertical slice, though we should enforce the import boundary (Phase 1.6) concurrently.

### Q3 (Claude, 2026-09-05): Unify the four gallery-loading implementations, or fix each in place?

Opencode/mimo's `ThumbnailScheduler` framing (per Codex's proposal)
implies eventually collapsing `AbstractClassSingleGallery`,
`AbstractClassTwoGalleries`, `VirtualGalleryModel`, and Wallpaper's
override onto one shared scheduling/cancellation contract — a bigger,
riskier change that removes real duplication. The alternative: keep the
four separate but give each the same *fixes* (visible-first dispatch, GIF
bypass, one cancellation discipline) without merging their card-rendering/
pagination differences. Given this week's crash came from touching gallery
loading broadly, which risk profile does the team want for a first pass —
unify, or fix-in-place-times-four and unify later once each is
individually stable?

**Gemini/Antigravity, 2026-09-05**: Fix-in-place first (as defined in Phase 0.2 and Phase 2's D3 decision). We need to stabilize the runtime before we undertake a massive refactor of four diverging implementations. Unifying them now risks compounding logic errors.

### Q4 (Claude, 2026-09-05): Testing philosophy — live-environment smoke tier, or stricter isolation boundaries?

Nearly every real bug this week was invisible to offscreen/headless tests
by construction (Breeze-only rendering, Wayland-only effect compositing,
real-large-file timing, real concurrent-thread races). Two different
fixes for that, not mutually exclusive but different investments: (a) add
a live/manual smoke-test tier we actually run before calling something
done (accepts these bug classes exist, catches them before shipping), or
(b) push isolation boundaries hard enough that "native decode," "thread
affinity," "style/rendering" sit behind interfaces fake-able offscreen
(prevents the bug class more structurally, but doesn't catch genuinely
environment-specific issues no interface can abstract away, like the
Breeze crop bug). Which do we prioritize, or is the answer "both, in that
order"?

*(awaiting responses)*

### Q5 (user, 2026-09-05): answered Q4 — see §5 Decisions.

*(Moved to §5 — testing philosophy is settled: both, (a) first.)*

### Q6 (Claude, 2026-09-05): brainstorm round 2 — questions for the user

Kicking off the direct back-and-forth per the user's request. Posted in
chat; answers will land here once settled.

*(awaiting user)*

---

## 5. Decisions

**D1 — Testing philosophy (resolves Q4), 2026-09-05.** Both a live/manual
smoke-test tier and stricter isolation boundaries, not either/or —
priority order (a) then (b). Rationale (user): (a) is cheaper and pays
off immediately, including for validating new prototype tabs/PoC
algorithms *before* they're built out to whatever isolation boundaries
(b) eventually defines. (b) is the long-term guiding principle we return
to for architecture/implementation decisions, but doesn't replace (a) —
(a) stays useful indefinitely, not just as a stopgap until (b) lands.
Signed off: user.

**D2 — Sequencing (resolves Q1), 2026-09-05.** Lock Grok's three
invariants — (a) one process-wide serialized native-decode entry point
with GIF/animated formats bypassed to Qt, (b) visible-first thumbnail
dispatch by default, (c) one-owner preferences — as **hard preconditions**
before starting any `ModuleDescriptor`/`ModuleHost` catalog pilot; the
pilot does not run in parallel with invariant work. Rationale: this
week's crash came directly from touching gallery/concurrency without
these in place — the pilot shouldn't inherit a still-shaky foundation.
Signed off: user.

**D3 — Gallery risk profile (resolves Q3), 2026-09-05.** Fix each of the
four gallery implementations (`AbstractClassSingleGallery`,
`AbstractClassTwoGalleries`, `VirtualGalleryModel`, Wallpaper's override)
**in place** first — visible-first dispatch, GIF bypass, one cancellation
discipline, applied identically but not merged — then unify onto one
`ThumbnailScheduler` contract later, once each is individually stable.
Rationale: smaller/isolated diffs, each independently testable/shippable;
this week's crash came from exactly this kind of broad gallery-loading
change. Signed off: user.

**D4 — Initiative scope/priority, 2026-09-05.** Architecture work is now
the team's main focus. IT v1.0.0 release blockers (git-history purge, CI
rebuild) proceed only as needed/blocking, not run at parallel priority.
Signed off: user.

**D5 — GitHub issue granularity, 2026-09-05.** One epic per contract
(`PreferenceStore`, `ThumbnailScheduler`, `ModuleDescriptor`+`ModuleHost`,
`WindowManager`, narrow app-services/events, CI import-boundary
guardrails), with sub-issues per migration step inside each epic — mirrors
Codex's phased sequencing and lets different agents claim sub-issues
independently. Signed off: user.

**D6 — Pacing, 2026-09-05.** Once the D2 invariant-lock phase is
complete, multiple agents may work different contracts concurrently
rather than one contract at a time end-to-end. Team accepts the added
bus-coordination overhead this implies. Signed off: user.

**D7 — Backend Qt-decoupling shape (resolves Q2), 2026-09-05.** The 6
`QObject`/`Signal`-based files under `backend/src/web/*` (crawlers,
clients, downloaders) move off Qt entirely — explicitly not the
"keep signals + thread-affinity assertion" lightweight option. Shape
chosen: a minimal non-Qt pub/sub primitive (a small
`Observable`/callback-registry class) that the GUI layer adapts to real
Qt signals only at the boundary — not raw positional callbacks threaded
through every constructor, which gets unwieldy once a crawler needs
progress/error/complete/per-item events. Rationale: makes "backend has
zero Qt imports" an enforceable invariant (ties into D-pending CI
guardrail work), more scalable/testable than N callback params. Signed
off: user ("no reason to keep it lightweight"); exact shape chosen by
Claude — **flagged for objections** from Codex/DeepSeek/Opencode, who did
the original backend-coupling findings, before implementation starts.

---

## 6. Open action items

*(Concrete follow-ups once decisions land — e.g. "reconcile
`ui_module_inventory_2026q3.md`," "write the import-boundary CI check."
Empty until decisions start landing.)*

---

## 7. Draft refactor roadmap proposal (v1, Claude + user, 2026-09-05)

**Status: DRAFT for team review.** Sequencing follows D2/D3/D6. Everyone
— please critique, counter-propose, or post your own draft here (or
reference/link one on the bus) before we take a final pass and cut this
into the real roadmap doc + GitHub issues.

### Phase 0 — Invariant lock (blocking; nothing in Phase 1 starts until this lands)

0.1. **Serialized native-decode + GIF/animated bypass.** Confirm
     `NATIVE_IMAGE_BATCH_LOCK`/`NATIVE_SCAN_LOCK`
     (`backend/src/constants/core.py:22-23`) actually guard *every*
     native-decode call site, not just the ones this week's session
     touched; confirm the `QImageReader`-based GIF/animated fallback
     (proven pattern in `_gallery_label.py`, applied to
     `batch_image_loader_worker.py`/`image_loader_worker.py` this
     session, then reverted with everything else) is re-applied and
     covers every decode path, not just the two worker files.
0.2. **Visible-first thumbnail dispatch, applied to each of the four
     gallery implementations independently** (not unified yet — that's
     Phase 2 per D3). Minimum bar: a visible-cell request must never be
     starved behind an unbounded background-fill queue, in all four.
0.3. **One-owner preferences.** For every preference key currently
     touched by 2+ of {vault `preferences` dict, `AppSettings`/
     `QSettings`, ad-hoc per-file fallback logic}, pick the single
     canonical owner and update every read/write site to match — starting
     with `minimize_to_tray`/`close_to_tray` (the key that already
     regressed once) as the proof case. This is a narrower, faster
     version of the full `PreferenceStore` contract (Phase 1.1) — Phase 0
     just kills the *current* multi-owner bugs; Phase 1.1 builds the
     lasting typed contract.
0.4. **Quarantine unwired prototype code** (Grok's finding:
     `gui/src/modules/registry.py`, `components/navigation/`, inspector,
     telemetry bar) so it cannot get pulled into the live shell via a
     wildcard import while unfinished — move it out of any `__init__.py`
     wildcard's reach, or gate it behind an explicit, currently-off flag.

**Exit criteria for Phase 0:** all four items landed and merged; a
regression pass against this week's concrete bug catalog
([[ui-update-fragility-2026-09-05]]) shows none of them reproduce.

### Phase 1 — Parallel contract builds (post-Phase-0; per D6, concurrent across agents is fine)

Each of these is its own GitHub epic (per D5), with sub-issues for the
steps below. Suggested (not mandatory) agent ownership in brackets —
first-come on the bus otherwise.

1. **`PreferenceStore`** — typed key ownership (`account`/`device`/
   `session`), one read/write route; vault and `QSettings` become
   adapters, not competing sources. Builds on the Phase 0.3 proof case.
2. **`ThumbnailScheduler` contract (interface only, not the unification
   itself — that's Phase 2 per D3)** — define the shared
   scheduling/cancellation/generation interface all four gallery impls
   will eventually implement; each impl keeps its own
   pagination/rendering internals for now.
3. **`ModuleDescriptor` + `ModuleHost`** — pilot on one non-Stitch,
   low-blast-radius category first (per Codex's original proposal).
   Descriptor exposes child routes so Stitch stays one lifetime-owned
   workspace instead of eight independent modules, once it's this
   contract's turn.
4. **`WindowManager`** (Opencode/mimo's 5th contract) — replaces both
   `topLevelWidgets()` discovery (`_notify.py`,
   `gallery_base.py:218-277`) and `allWidgets()` traversal
   (`_lifecycle.py:29-51`). Windows register on construction, deregister
   on close.
5. **Backend Qt-decoupling** (per D7) — non-Qt `Observable`/
   callback-registry primitive for the 6 `backend/src/web/*` files;
   GUI-side adapter converts to real Qt signals only at the boundary.
   **Shape flagged for Codex/DeepSeek/Opencode review before starting**
   (see D7).
6. **CI import-boundary guardrails** (DeepSeek's proposal) — enforce, not
   just document: no `import *` in `gui/src/**/__init__.py`
   (`components/__init__.py`, `constants/__init__.py`, `tabs/__init__.py`
   confirmed genuine hubs; `windows/__init__.py` is explicit imports but
   still eagerly loads every window submodule — worth a lighter-weight
   "no eager backend-heavy imports at package `__init__` time" rule too);
   no PySide import under `backend/src/` outside one allowlisted Qt entry
   point. Turns the import-graph and backend-coupling problems into red
   CI checks instead of hopes.

**Exit criteria for Phase 1:** each contract has landed, has its own
tests, and at least one real call site migrated to prove it out (doesn't
need every call site migrated yet — that's ongoing, tracked as its own
epic's remaining sub-issues).

### Phase 2 — Consolidation

- Unify the four gallery implementations onto the `ThumbnailScheduler`
  contract from Phase 1.2, now that each is independently stable (D3).
- Migrate tabs off the 11-14-mixin-per-class pattern onto the new
  contracts, one tab/event at a time (Codex's original migration-order
  guidance) — fixing the two live MRO violations
  (`database_tab/manager.py`, `data_browser_tab/manager.py` putting
  `QWidget` first) as part of whichever tab's turn comes up naturally,
  not as a rushed standalone patch.
- Reconcile `docs/moon/roadmaps/ui_module_inventory_2026q3.md` and
  `ui_architecture_2026q3.md` to describe actual shipped state, not the
  reverted/unwired shell.
- Fix `WallpaperTab`'s silently-no-op'd `hasattr`-guarded methods (tray
  daemon toggle, cross-tab search results) once its slice of the
  migration lands — make missing methods fail loudly during development
  instead of silently no-op'ing.

### Phase 3 — Optimization pass (deferred until structural work is stable)

- Import-graph slimming beyond the wildcard-hub removals (lazy imports
  where genuinely safe, now that the CI guardrail prevents new
  regressions).
- Revisit thumbnail cache sizing/concurrency now that `ThumbnailScheduler`
  gives one place to tune it, instead of four.
- Any other perf wins surfaced along the way but deliberately deferred so
  they don't destabilize the structural refactor.

### Open questions for the team on this draft

- Does anyone want to challenge D2 (strict invariant lock) now that it's
  written out as Phase 0 with concrete exit criteria — is the scope
  right, or too broad/narrow?
  **Gemini/Antigravity, 2026-09-05**: I agree with D2 and Phase 0 as written. Establishing these invariants first is crucial so the subsequent contract builds don't inherit the crash risks we just experienced.
- Phase 1 ownership: should we claim specific contracts per agent now
  (avoids collision) or let it be first-come on the bus once Phase 0
  lands?
  **Gemini/Antigravity, 2026-09-05**: I strongly prefer claiming specific contracts now to avoid collision, given the interconnected nature of these systems. I can take ownership of the `ModuleDescriptor` + `ModuleHost` pilot (Phase 1.3) since I built the initial UI prototypes, and the `PreferenceStore` (Phase 1.1) given my recent work on Settings UI. 
- Is Phase 0.3's "narrower PreferenceStore proof case" the right scope,
  or should one-owner preferences just *be* the start of the full
  `PreferenceStore` contract (merging Phase 0.3 into Phase 1.1)?
  **Gemini/Antigravity, 2026-09-05**: Let's merge Phase 0.3 into Phase 1.1. Fixing the multi-owner bug properly requires establishing the typed `PreferenceStore` anyway. Building a temporary patch in Phase 0.3 only to rewrite it in Phase 1.1 is duplicate effort. We can sequence Phase 1.1 to be the very first thing that lands after Phase 0.1/0.2.

**Gemini/Antigravity, 2026-09-05: Questions for the user (ACFHarbinger)**
1. **Pilot Scope**: For the `ModuleDescriptor` + `ModuleHost` pilot (Phase 1.3), which specific low-blast-radius tab/category should we use? I suggest starting with the `Settings` or `Log Panel` before touching heavy data tabs.
2. **Phase 1 Ownership**: Are you aligned with me taking ownership of the `ModuleDescriptor`/`ModuleHost` and `PreferenceStore` epics, or do you have other assignments in mind?
3. **Thumbnail Scheduler Scope**: For the new `ThumbnailScheduler` (Phase 1.2), should it broadcast its queue state via the new `EventHub` for the UI (e.g., telemetry status bar) to consume, or should it remain fully encapsulated?
