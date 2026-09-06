# GUI Refactor Analysis — code-level audit for the component/DRY roadmap

**Status:** FINAL (Claude, 2026-09-06, after the team round). Decisions and the
plan now live in `docs/moon/roadmaps/gui_refactoring.md`; this file is the
evidence record. §11 consolidates the DeepSeek/Grok pass. Append only. Verify every citation with
`sed -n '<range>p' <file>` before posting (see the 09-05 audit note).

**Relation to existing records.** This is the *code-level* companion to
`.agent/reports/team/architecture_deep_dive_2026-09-05.md` (the
architecture/decision record: D1–D18, issues #520–#532). It does not
re-litigate anything locked there. It adds what that report did not measure:
duplication, worker/signal vocabulary, styling scatter, error handling,
blocking IO, config contracts, type-suppression debt, and fix-churn hotspots —
and proposes roadmap *deltas* (new epics + a target component model), not a
replacement roadmap. Rewrite-vs-refactor verdict is in §7.

Baseline: `origin/main` @ `ee91cd01` (2026-09-06). `gui/src`: 631 `.py`
files, 90,417 LOC. All numbers below were produced by scripts in the audit
appendix (§10), rerunnable by anyone.

---

## 1. Baseline metrics (one table, so later passes can diff against it)

| Metric | Value | Why it matters |
|---|---|---|
| Classes with ≥5 base classes | 25 (max 16: `MainWindow`; 15: `WallpaperCommonBase`, `VideoExtractorSubTab`) | composition-by-MRO; undeclared `self` attrs |
| Qt-class-first MRO violations | 0 (was 2 before #544) | fixed on main |
| `hasattr(` sites | 365 | mixins probing each other's state; silent no-ops |
| `# pyrefly: ignore` / `# type: ignore` | 330 / 57 | the type checker can't see mixin-provided attrs |
| `except ...: pass` (silent swallow) | 81 | failures disappear instead of surfacing |
| `setStyleSheet(` call sites | 648 | per-widget styling bypasses the theme engine |
| Inline `#rrggbb` literals outside `theming/`,`styles/`,`constants/` | 962 | same |
| `QThread` subclasses using `BaseQThreadWorker` | 1 of 28 | base exists (`helpers/base.py`), unused |
| `QRunnable` subclasses using `BaseQRunnableWorker` | 5 of 24 | same |
| Signal-carrying worker classes / distinct signal-name vocabularies for "finished/error/progress" | 55 / 10 | every tab wires workers differently |
| Functions >80 lines | 131 (max 480: `run_extraction_in_process`) | mostly `_build_ui`/`__init__` |
| Files >500 LOC (roadmap §5.17 limit) | 23 | |
| Cross-file duplicate 12-line windows, top pair | 86 (`directory_import_dialog` ↔ `entity_directory_import_dialog`) | see §3 |
| `QTimer.singleShot` | 45 | ordering-by-delay; the #546 bug family |
| `QApplication.processEvents()` live calls | 7 | re-entrancy hazard (docs in `_monitor_selection.py:63-86` explain why one was removed) |
| Blocking IO calls in widget code (`os.listdir/walk/scandir`, `rglob`, `cv2.imread`, `Image.open`) | ~30 sites, 15 files | main-thread stalls |
| `LRUImageCache(` instances | 7, sized in 4 different places | no single memory budget |
| `*_tab_ref` / `main_window_ref` sites | 60 | cross-tab coupling (down from 157 pre-#544) |
| `topLevelWidgets()`/`allWidgets()` | 6 | down from 12; #528 in flight |
| `QFileDialog.get*` sites | 80, 0 pass `DontUseNativeDialog` | safe only via `apply_patch()` monkeypatch (§5.6) |
| Test files / LOC / needing `--run-gui` | 148 / ~20k / 85 files | no pixel-level assertions anywhere |
| Fix/regression/crash commits touching `gui/src`, last 60 days | 159 | see §8 hotspots |

---

## 2. Composition model: what the mixin pattern actually costs

Not restating the 09-05 finding (11–16 mixins per class, MRO comments as the
contract). What the code-level numbers add:

- **`hasattr` is the mixins' de-facto interface.** 365 sites; the top files are
  `windows/settings/_relaunch_settings.py` (20) and
  `windows/main/_startup_prefs.py` (20). Sample, `_relaunch_settings.py:327-332`:
  `if hasattr(self.main_window_ref, "set_minimize_to_tray"): ...`,
  `if hasattr(self.main_window_ref, "_apply_startup_preferences"): ...`.
  Each `hasattr` is a method call that silently does nothing if a refactor
  renames the target — the same failure shape as the `WallpaperTab` no-ops
  Grok found (D15).
- **Type suppressions are the same debt in another costume.** 330 `pyrefly:
  ignore` lines; the dominant kinds are `missing-attribute` on `self` inside
  mixins and `bad-instantiation` on tab classes (`_tab_registry.py:80,89`).
  Any move to composition removes both the suppressions and the `hasattr`s.
- **There is already a seed of the right pattern.** Seven `*HostProtocol`
  classes exist (`classes/image/protos/`, `tabs/core/protos/`,
  `tabs/models/protos/`) that declare what a mixin expects from its host. They
  cover 7 of 25 stacks and are typing-only (no runtime check). #544 shows the
  end state: `DatabaseTab(QWidget)` plus injected collaborators, 12 mixins
  gone, `_ref` sites down by ~60%.
- **Per-tab mixin *files* are clones of each other, not shared code.**
  `_lifecycle.py` ×11, `_ui_builder.py` ×17, `_directory_browse.py` ×6,
  `_gallery_cards.py` ×5, `_preview_context.py` ×4. `format_subtab/_lifecycle.py`
  (44 lines) vs `codec_subtab/_lifecycle.py` (45) differ by 26 diff lines —
  i.e. they are the same `closeEvent`/worker-teardown logic copied per tab.
  The §5.17 file-split made files small but multiplied the copies.

**Recommendation (feeds Phase 2, #531):** treat #544's shape as the template
and migrate in *churn order* (§8), not alphabetical order. Add one runtime
guard while mixins remain: a `HostProtocol` conformance test per tab
(`isinstance`-free: assert every attribute the Protocol names exists after
`__init__`) so a missing attribute fails a unit test instead of a `hasattr`.

---

## 3. DRY: the duplication catalog (measured, cross-file, 12-line windows)

### 3.1 Whole-feature clones (rewrite-in-place candidates)

| Pair | Size | Dup windows | Evidence |
|---|---|---|---|
| `tabs/database/entity_listings_subtab/` ↔ `series_listings_subtab/` | 1,143 + 1,453 LOC, 10 vs 11 files with identical names | 75 (`_backup_sync`), 70 (`_ui_builder`), 28 (`_semantic_search`), 3, 2 | `_backup_sync.py`: 189 lines, 24 diff lines between the two |
| `elements/database/dialog/directory_import_dialog.py` ↔ `entity_directory_import_dialog.py` | 358 + 344 LOC | 86 | 208 diff lines of 702 |
| `tabs/core/codec_subtab/` ↔ `format_subtab/` | 1,044 + 1,327 LOC | 74 (`_ui_builder`), 23 (`_conversion_worker`), 13 (`_directory_browse`), 4, 4 | `_directory_browse.py` differs only in the format-filter branch |
| `helpers/web/cloud/dropbox_drive_sync_worker.py` ↔ `one_drive_sync_worker.py` | — | 29 | provider-specific bodies in a shared skeleton |
| `helpers/video/{frame,gif,video}_extractor_worker.py` ↔ `helpers/core/queue_execution_worker.py` | `run_extraction_in_process` is 480 lines | 8 each, pairwise | the extraction pipeline exists 4× |
| `components/inspector/`, `components/navigation/` ↔ `protos/inspector/`, `protos/navigation/` | — | 62, 34 | **process collision, see §5.1** |
| `elements/database/dialog/associated_content_dialog.py` ↔ `associated_entities_dialog.py` | — | 14 | |
| `tabs/models/generate_tab.py` ↔ `train_tab.py`; `lora_train_tab.py` ↔ `lora_generate_tab.py` | — | 12, 9 | |

The listings pair is the clearest case: an "entity" and a "series" listing are
the same gallery+filters+backup+semantic-search widget parameterised by an
entity type. Same for the two import dialogs. Collapsing these four pairs
removes roughly 3–4k LOC of drift surface without touching the crash-class
code.

### 3.2 Same behaviour re-implemented by name across tabs

Function names defined in ≥6 files (excluding dunders): `run` 54,
`_build_ui` 42, `set_config` 33, `collect` 31, `closeEvent` 27,
`get_default_config` 26, `stop` 22, `cancel_loading` 22, `cancel` 18,
`toggle_selection` 13, `create_gallery_label` 10, `show_image_context_menu`
10, `on_selection_changed` 10, and the pagination/sort/zoom handler set
(`_jump_to_page`, `_change_page`, `_on_page_size_changed`,
`_on_thumb_slider_changed`, `_on_sort_combo_changed`, `_on_sort_dir_toggled`,
`_on_ctrl_wheel_zoom`, `select_all_items`, `deselect_all_items`) at 6 each.

- **The config trio has no contract.** 26/31/33 files implement
  `get_default_config`/`collect`/`set_config`; only one file is named
  `_config_methods.py`; `MainWindow._save_tab_config_to_vault` discovers
  support via `hasattr(tab_instance, "collect")` (`_save_tab_config.py:29`).
  There is no `Protocol`, no base, no schema — so session recovery, Ctrl+S
  profiles, and Settings "Tab Default Configuration" each re-derive it.
- **Gallery toolbar/pagination handlers** are copied into 6 hosts instead of
  being one `GalleryToolbar` component that emits intents.

### 3.3 Worker/threading vocabulary (55 signal-carrying classes)

`helpers/base.py` already defines `BaseQThreadWorker` (`sig_finished`,
`error`, `progress(int,int)`, `cancel()`, GC-safe `run()` wrapping
`_execute()`) and `BaseQRunnableWorker`. Adoption: 1/28 and 5/24. The rest
re-declare the same three signals under ten different spellings:
`finished`/`sig_finished`/`finished_signal`/`scan_finished`,
`error`/`error_signal`/`scan_error`, `progress`/`progress_signal`/`status`.
26 helper files carry their own `_is_running`/`_cancelled`/`_stop_requested`
flag. Consequence: every tab's `_lifecycle.py` teardown is bespoke (hence the
11 clones in §2), and there is no single place to enforce "cancel before
close, join with timeout, never emit into a dead widget".

---

## 4. Styling and theming: the engine exists and is bypassed

`theming/` (1,573 LOC: schema, palette, presets, resolve, storage, validate,
theme studio) plus `styles/` generate one app-level QSS
(`windows/main/_theme.py:201`). Around it: 648 `setStyleSheet` call sites
(tabs 201, windows 161, components 116, elements 83) and 962 inline hex
literals. Per-widget stylesheets override the app QSS cascade, don't
re-resolve on theme change, and are exactly where the Breeze/Kvantum
icon-crop and invisible-drop-shadow class of desktop-only bugs came from
(09-05 catalog).

**Recommendation (new epic, Phase 2):** a token API (`theme.color("surface")`,
`theme.qss(component="card")`) as the *only* legal colour source in
`components/`, `elements/`, `tabs/`; a CI rule (extend #530's linter) that
fails on `#rrggbb` literals and on `setStyleSheet(` outside `theming/` and
`styles/`. Migrate by directory, components first (they're reused; fixing one
fixes N tabs).

---

## 5. Correctness findings (hotfix tier — small, safe, or already understood)

5.1 **Prototype is now duplicated, not quarantined.** #524 moved the shell
prototype to `protos/` (D11, non-destructive). #536–#541 then re-landed it
into `components/navigation/` + `components/inspector/` (D10), which
`windows/main/_runtime_shell.py:8` imports. Both copies are on `main` and
already diverging (62 + 34 duplicate windows). Decide: delete `protos/`
copies (history keeps them) or make `protos/` the only copy again. Cheap,
but it is a decision, so it's a question (§9), not a unilateral fix.

5.2 **81 silent `except: pass` sites.** Clusters: `system_display_subtab/_daemon.py`
(5), `wallpaper_common_base/_widget_ui_lifecycle.py` (5), `_profile_management.py`
(3), `_theme.py` (3), `wallpaper_graph_scene.py` (4). Most are `RuntimeError`
guards for deleted C++ objects (legitimate) mixed with bare `Exception`
swallows (not). Hotfix: convert bare ones to `logger.debug(..., exc_info=True)`
so desktop-only failures leave a trace in the log the user already collects
(`/tmp/d12-app.log` style).

5.3 **Blocking IO on the GUI thread, ~30 sites.** `extractor_tab/_directory_scanning.py`
(3), `crawler_selection_dialogs.py` (3), `login_window.py` (2), the three
`_directory_browse.py` (2 each), `merge_tab/_merge_execution.py`,
`similarity_tab/_properties_preview.py`, `thumbnail_file_picker.py`,
`frame_selection_dialog.py`. Each is a directory listing or an image decode
in a slot. The `[safety-guard]` budget log line shows the team already knows
the cost (109 GB output dir skipped at startup). Fix shape: one
`DirectoryScanService` worker with a cancellable generation token, reused by
the six browse mixins (§3.2) — this is also the seed of D3's
`ThumbnailScheduler` inputs.

5.4 **Ordering by delay.** 45 `QTimer.singleShot` sites; session recovery
runs at `+150 ms` (`_session_recovery.py:120,229`), extractor media load is
deferred until first Play (`_config_methods.set_config`, `defer_player=True`,
issue #81), and #546 (video item sized wrong on restore) sits exactly on that
seam. Every deferred step should become an explicit state machine on the
owning controller (`NotLoaded → Restored → PlayerReady → Playing`) with
transitions logged — the 2026-09-06 bus entry names the concrete next
diagnostic (paint-time read-back of `video_item.size()`).

5.5 **Vault as a preferences database.** `_relaunch_settings.py:266-309`
rebuilds the entire `preferences` dict from ~40 widgets on every Save and
then re-encrypts the whole vault (`save_data(json.dumps(creds))`); 12 sites
write the vault, `_session_recovery.py:345,450` among them, so the app log shows
`Data saved successfully` on ordinary UI actions. `cached_creds` is copied
onto `MainWindow` and mutated from Settings, session recovery, Ctrl+S
profiles, and theme changes. Covered by #523/#525 in intent; the code-level
addition is: preferences and tab configs need their own store with
per-key writes, and the vault should hold *secrets only*.

5.6 **`QFileDialog` safety is a hidden invariant.** 80 static
`QFileDialog.get*` calls, none pass `DontUseNativeDialog`; safety comes from
`file_dialog_patch.apply_patch()` monkeypatching the statics at
`backend/main.py:83`, `gui/__main__.py:34`, and `gui/test/conftest.py:117`.
Any new entry point that forgets the call re-enables the GTK-portal/JVM
SIGSEGV documented in `docs/ARCHITECTURE.md`. Fix: make the patch
self-installing on first import of `gui.src` (or replace the statics with a
`gui.src.components.dialogs.file_dialogs` module and lint the raw calls).

5.7 **Seven independently-sized LRU caches.** `card_thumb_worker.py:15`
(module global, 250), `single_gallery/manager.py:62` (300),
`two_galleries/manager.py:65-66` (200 + 300), `virtual_gallery_model.py:76`,
`dual_widget.py:50`, plus `_startup_prefs.py:164` re-creating tab caches from
preferences via `setattr(tab, attr, LRUImageCache(...))`. There is no total
pixmap budget, so the effective memory ceiling is the sum of whatever each
tab picked. Belongs to #526/#532.

5.8 **Startup footprint.** `[Lifecycle/qt_init] RSS=916 MB` before the login
window exists, 1,094 MB at main window. Contributors visible from static
analysis: JVM (vault), 25 tabs + 8 Stitch panels constructed eagerly
(`_tab_registry.py:61-100`), module-level `cv2` in 9 GUI files, `PIL` in 9,
`numpy` in 7, `torch` in 2. #527's `ModuleHost` (lazy construction) is the
structural answer; the cheap pre-step is moving heavy imports inside the
functions that use them in those 27 files.

---

## 6. Test-surface facts relevant to the roadmap

- 148 test files, ~20k LOC; 85 files need `--run-gui`; 0 assertions on
  rendered pixels or widget geometry after paint. #546 and the Breeze crop
  are invisible to this suite by construction (D1 already accepts this and
  puts the live tier first).
- `gui/src/components/__init__.py` no longer wildcard-imports (explicit
  re-exports now), but is still eager (~120 names) — half of #530's rule.
- Isolated collection still needs the ASP bootstrap (`conftest.py:115`
  applies the dialog patch; the `asp_backend` import boundary is #530's
  other half).

---

## 7. Rewrite vs refactor — verdict and reasoning (Claude)

**Do not rewrite the application.** Reasons, from the evidence above rather
than from taste:

1. The crash-class and desktop-only bugs (09-05 catalog, #546) are
   *lifecycle/threading/rendering* bugs. A rewrite on the same Qt stack with
   the same test surface reproduces them; the fixes are the invariants in
   Phase 0 plus the live-smoke tier (D1/D12), which apply to old and new code
   alike.
2. The duplication is *concentrated* (§3.1: four clone pairs, one 4× pipeline,
   one collision) — rewrite-in-place of those specific units removes most of
   the drift surface with a fraction of the blast radius.
3. #544 already proves the migration path (13-mixin tab → composed widget) on
   a real tab, merged, with cross-ref count dropping ~60% as a side effect.
4. A from-scratch rewrite would freeze re-landing the reverted UI/UX (D10) and
   the v1.0.0 line (D4) for the whole rewrite duration, with no user-visible
   improvement until the end.

**Do rewrite these, in place, as units:** the listings-subtab pair, the two
import dialogs, the codec/format subtab pair, the extractor worker quartet
(§3.1), and the extractor media-player/session-restore seam (§5.4) — each as
one component with one owner, replacing both copies, behind the existing tab
surface.

---

## 8. Where to start: fix-churn hotspots (git, last 60 days, fix/regress/crash commits)

Paths collapsed across the pre-reorg layout. Files touched, descending:
`wallpaper_tab/*` (~170), `extractor_tab/*` (~100), the two gallery bases
(`abstract_class_two_galleries` ~50, `abstract_class_single_gallery` ~40),
Stitch panels (~45), `elements/database/display` (~40), `scan_metadata_tab`
(~50 incl. old path), `database/dialog` (~30), `similarity_tab` (~40).

That order is also the order of mixin depth (§1) and of `hasattr` density.
Refactor pays first where the fixes keep landing: **wallpaper → extractor →
gallery bases**, with the listings/import-dialog clone collapse run in
parallel by a second agent because it is disjoint from all three.

---

## 9. Proposed roadmap deltas (for the team to edit; maps onto #520–#532)

Nothing here reorders Phase 0/1 (D2, D6). These are additions and
sharpened exit criteria.

**Phase 1 additions (contracts, can run concurrently per D6):**

- **1.7 `WorkerBase` adoption + one signal vocabulary** — every
  `QThread`/`QRunnable` in `gui/src/helpers` derives from the existing base;
  signals are `finished/error/progress` only; one `Cancellable` teardown used
  by a single shared `_lifecycle` implementation (kills the 11 clones).
  Exit: 0 raw `QThread`/`QRunnable` subclasses; lint rule in #530.
- **1.8 `TabConfig` contract** — a `Protocol` + dataclass schema for
  `get_default_config/collect/set_config`, with versioned migration; session
  recovery, Ctrl+S, and Settings all consume it. Exit: `hasattr(tab,
  "collect")` sites → 0.
- **1.9 Preferences store split** (sharpens #525) — vault = secrets only;
  preferences/tab-configs in a per-key store; no whole-blob rewrites.
  Exit: `save_data(json.dumps(creds))` sites → 0 outside auth.

**Phase 2 additions (consolidation):**

- **2.a Clone collapse** — the §3.1 pairs, each as one PR, disjoint from the
  crash-class code, good first tasks for any agent.
- **2.b Theme tokens + styling lint** (§4). Exit: `setStyleSheet` outside
  `theming/`/`styles/` → 0; hex literals → 0; CI-enforced.
- **2.c Composition migration in churn order** (§8), #544 as template, one
  tab per PR, `HostProtocol` conformance test per tab while mixins remain.
- **2.d Explicit lifecycle state machines** replacing `singleShot` ordering in
  session recovery and the extractor player (§5.4); closes #546's family.
- **2.e Error-boundary policy** — replace the 81 silent swallows with logged
  ones; `RuntimeError`-on-deleted-object guards get one shared helper.

**Phase 3 (optimization) sharpened:**

- one pixmap budget across the 7 caches (§5.7); lazy heavy imports (§5.8);
  `DirectoryScanService` for the ~30 blocking-IO sites (§5.3).

**Target package shape (proposal, for discussion — not a mandate):**

```
gui/src/
  app/         launcher glue, WindowManager (#528), ModuleHost (#527)
  core/        contracts only: HostProtocols, TabConfig, WorkerBase, PreferenceStore API, events
  theming/     the ONLY colour/QSS source (tokens API)
  components/  reusable, tab-agnostic widgets; theme-token only; no backend imports
  features/<name>/   view.py (QWidget) + controller.py (state machine, workers) + config.py (TabConfig)
  workers/     WorkerBase subclasses; pure functions inside, no widgets
  protos/      quarantined prototypes (or removed — §5.1 decision)
```

Rules that make it component-based rather than just re-foldered: a feature
imports `core/`, `components/`, `theming/`, `workers/` and its own package,
nothing else; components import `theming/` and `core/` only; workers import
no `gui.src` widgets. #530's linter enforces all three.

---

## 10. Open questions for the team / user

- **Q-A (§5.1):** `protos/` vs `components/` prototype duplication — delete
  the `protos/` copy now that the re-land is live, or keep both until D10's
  re-land is complete?
- **Q-B (§3.1):** who takes the clone collapses? They are disjoint from
  Phase 0/1 crash-class work and can start now without violating D2.
- **Q-C (§9, 1.7):** adopt the existing `BaseQThreadWorker` as-is, or
  first fix its `error` signal to carry the exception object (currently
  `str(exc)`) so callers can branch on type?
- **Q-D (§4):** is a hard "no `setStyleSheet` outside theming" rule
  acceptable, or do we need an allowlist for one-off widgets (overlays,
  canvas)?
- **Q-E (§9 target shape):** `features/<name>/` layout vs keeping
  `tabs/<name>/` names — pure naming, but it decides every later import path.

---

## Appendix — audit method (rerunnable)

Scripts are in `tools/dev/gui_audit/` (`python tools/dev/gui_audit/gui_audit.py gui/src`,
`python tools/dev/gui_audit/dup_finder.py gui/src 12`):

- `gui_audit.py` — AST pass: base-class counts, Qt-first MRO check, functions
  >80 lines, def-name frequency across files, worker `Signal` clusters, files
  >500 LOC.
- `dup_finder.py` — cross-file duplicate detector: MD5 of sliding 12-line
  windows of normalised source (strings collapsed, imports/blank/comment
  lines skipped), reported per file pair.
- greps as listed in §1 (`hasattr(`, `setStyleSheet(`, `#[0-9a-fA-F]{6}`,
  `QTimer.singleShot`, `processEvents()`, `LRUImageCache(`, `_tab_ref`,
  `topLevelWidgets|allWidgets`, `QFileDialog\.get`, `except .*:\n\s*pass`).
- `git log --since="60 days ago" --name-only -i --grep="fix\|bug\|regress\|crash" -- gui/src`.

— Claude, 2026-09-06

---

## 11. Consolidation with the DeepSeek/Grok pass (final edit, Claude, 2026-09-06)

Second report: `.agent/reports/deepseek/gui_architecture_analysis_2026-09-06.md`
(DeepSeek F1–F16, Grok F17–F26 + answers). Cross-map, so nothing is lost:

| Their finding | Here | Roadmap item |
|---|---|---|
| F1 mixin migration ~5% done; F22 MainWindow 16-mixin root | §2 | R2.c |
| F2 gallery rendering/selection still forked; F21 `create_card_widget` ×2 | §3.2 | R3.4 (after #543 D12) |
| F3 worker duplication; F9 QThread census (Grok: ~25, not "a few") | §3.3 | R1.1, R2.a workers |
| F4 preview-context duplication | §3.2 | R1.7 |
| F5 `db_tab_ref` misnomer; F7 60 residual refs | §1 row 17 | R0.8 |
| F6 settings → `main_window_ref` 42–44 sites; F19 settings dual-write `cached_creds` | §5.5 | R0.2, R1.3, R1.5 |
| F8/F16/F24 `hasattr` silent no-ops | §2 | R0.7, rule 5 |
| F10/F25 `processEvents` + blocking main-thread calls | §5.3, §1 | R1.6, R3.3 |
| F11/F13 Phase 0 invariants: keep | — | rules, gates |
| F12 module eviction/disposal open | — | R3.5, §7 |
| F14 `atexit` AttributeError in unbuilt worktrees | — | R0.9 |
| F15 `@dataclass` on facts (fixed) | — | — |
| F17 classic shell eager construction; F23 classic vs catalog factory drift; F26 barrel imports ASP/CSG/HIE | §5.8 | R2.e, R1.4, R0.3 |
| F18 `MonitorDisplaySubTab.__init__` skips mixins | — (missed here) | R0.1 |
| F20 17 `_UIBuilderMixin` classes | §3.2 | R2.f |

**Corrections to this report from their pass.** F18 is a live landmine this
report did not list in §5; added as R0.1. DeepSeek's §1 `tabs/` = 39,672
lines matches my per-directory count on the branch. Grok's `hasattr` count
(~122 in `tabs/` only) and mine (365 across `gui/src`) measure different
scopes; both stand.

**Decisions on §10 Q-A..Q-E and DeepSeek §7 Q1–Q5:** recorded in the
roadmap §4 (Q-A delete `protos/`; Q-B Cursor; Q-C `error(object)`; Q-D hard
rule + shrinking allowlist; Q-E keep `tabs/<name>/`; DS-1 risk-first per
Grok; DS-2 `WindowService` + `PreferenceStore`; DS-3 rename with an
in-issue shim; DS-4 R3; DS-5 measure first).
