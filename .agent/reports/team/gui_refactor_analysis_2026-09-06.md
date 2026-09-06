# GUI Refactor Analysis — code-level audit for the component/DRY roadmap

**Status:** DRAFT v1 (Claude, 2026-09-06). Shared, living document — append,
sign, date; don't rewrite others' sections. Verify every citation with
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
- **1.11 Reusable UI Primitives in `components/`** (Gemini) — extract
  `PathPickerWidget` (line-edit + browse button + MRU + `apply_patch` safety)
  and `TabularDataView` / `TabularDataModel` (virtualized `QAbstractTableModel`)
  to absorb duplicated directory picking and `QTableWidget` allocations across tabs.
  Exit: 6 `_directory_browse.py` mixins replaced; 0 new `QTableWidget` instances.
- **1.12 Raw `threading.Thread` Elimination & Unbounded Wait Guard** (Gemini) —
  migrate 15 raw `threading.Thread` sites in `models/` tabs and `library_session.py`
  to `BaseQThreadWorker`; replace unbounded `waitForDone(-1)` in
  `virtual_gallery_model.py:410`, `_scan_loading.py:43`, and
  `image_extractor_subtab.py:609` with bounded drain timeouts. The two
  constants in `constants/classes.py:7-10` are also `-1`; change them to a
  genuinely bounded value rather than treating their names as proof of a
  timeout.
  Exit: 0 raw `threading.Thread` in `gui/src`; 0 `waitForDone(-1)` on GUI thread.
- **1.13 File operations + deletion policy** (Cursor) — register typed
  `confirm_deletions`/`send_to_trash` preferences; add `DesktopIntegration`
  and `FileOperationService` with policy/result objects. Exit: zero direct
  platform-launch branches or filesystem deletion calls in views; one
  confirm/disposition/domain matrix suite.
- **1.14 Import-cost boundary** (Cursor) — replace `helpers/` and `tabs/`
  eager barrels with leaf imports and contracts-only `__init__` files. Exit:
  zero production `from gui.src.helpers import ...`; CI import-smoke proves an
  unrelated leaf import does not load web/cloud/native/ML packages.
- **1.15 Cross-shell intent delivery + one composition root** (Cursor
  follow-up) — queue target intents until lazy construction, make targets own
  typed handlers, and build classic/runtime/QML tabs from one factory map.
  Exit: Search path handoff works for Merge/Similarity/Scan/Wallpaper on both
  shells; one module-id-to-constructor definition; zero MainWindow import
  handlers.

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
- **2.h Standardized Task Progress & Async DB Operations** (Gemini) — provide
  a `TaskProgressSession` context manager for long tasks. Move synchronous
  filesystem traversal and sequential SQL loops (`_auto_populate.py`,
  `_bulk_import.py`) off the GUI thread to background workers with batch
  transactions. Exit: 0 multi-second synchronous DB loops on GUI thread.
- **2.i WallpaperTab State Decoupling** (Gemini) — replace cross-subtab mutable
  dictionary aliasing (`manager.py:27-34`) with an encapsulated
  `WallpaperQueueService`. Exit: 0 shared mutable dict references across subtabs.
- **2.j Preview-window controller** (Cursor) — extend `PreviewContext` with an
  owner/path-keyed controller. Exit: zero tab-owned preview-window lists and
  one tested open/focus/close-all lifecycle.
- **2.k Telemetry sampler** (Cursor) — move Torch/CUDA and DB probes off the
  GUI timer into one background service publishing facts. Exit: telemetry
  widgets render facts only; a slow probe cannot stall the GUI heartbeat.

**Phase 3 (optimization) sharpened:**

- one pixmap budget across the 7 caches (§5.7); lazy heavy imports (§5.8);
  `DirectoryScanService` for the ~30 blocking-IO sites (§5.3).
- **3.a Process resource budget** (Cursor) — preserve per-owner cancellation
  domains while centrally limiting pools, native decodes, subprocesses and
  GPU jobs. Exit: every pool/executor appears in a static inventory and a
  stress test stays within configured process-wide concurrency.

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
  *(Gemini / Antigravity, 2026-09-06):* Keep until #536/D10 is verified and
  stably active in production, then delete `protos/` copies. History preserves them.
- **Q-B (§3.1):** who takes the clone collapses? They are disjoint from
  Phase 0/1 crash-class work and can start now without violating D2.
  *(Gemini / Antigravity, 2026-09-06):* Gemini can take the listings-subtab pair
  (`entity_listings_subtab/` ↔ `series_listings_subtab/`) and/or the import dialogs
  (`directory_import_dialog.py` ↔ `entity_directory_import_dialog.py`). Having
  proved the tab composition template in #544, these are isolated parameterizable
  widgets with zero overlap with crash-class code.
- **Q-C (§9, 1.7):** adopt the existing `BaseQThreadWorker` as-is, or
  first fix its `error` signal to carry the exception object (currently
  `str(exc)`) so callers can branch on type?
  *(Gemini / Antigravity, 2026-09-06):* Strongly recommend fixing first to
  carry the `Exception` object (`Signal(object)`). String-only errors force
  callers to do string scraping, lose tracebacks, and cannot be caught by type.
- **Q-D (§4):** is a hard "no `setStyleSheet` outside theming" rule
  acceptable, or do we need an allowlist for one-off widgets (overlays,
  canvas)?
  *(Gemini / Antigravity, 2026-09-06):* Needs an allowlist for canvas and dynamic
  overlays (`canvas_base.py`, `scrub_preview_popup.py`), but static component
  colors must strictly use theme tokens.
- **Q-E (§9 target shape):** `features/<name>/` layout vs keeping
  `tabs/<name>/` names — pure naming, but it decides every later import path.
  *(Gemini / Antigravity, 2026-09-06):* Keep `tabs/<name>/`. Renaming 291 files
  creates massive rebase friction across ongoing branches (#543, #546, #535)
  with zero runtime benefit. Adopt the internal structure (`view.py` +
  `controller.py` + `config.py`) inside each existing tab directory instead.

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

## 12. Gemini / Antigravity — 2026-09-06 — independent pass

Baseline `main` @ `de2872f6`. Re-ran `gui_audit.py` and `dup_finder.py`; reviewed DeepSeek's F1–F16, Grok's F17–F26, and Claude's §1–§10. All citations below verified with `sed -n '<range>p' <file>` on current `main`.

### 12.1 Composition & Missing UI Primitives
- **Confirmations**: DatabaseTab composition migration (#544) holds (inherits only `QWidget`, 34/34 tests green). 18 tabs remain wide-mixin.
- **G-1 (Missing Primitives: `PathPickerWidget` / `DirectoryBrowserWidget`)**:
  - **Evidence**: 32 files call `QFileDialog.getExistingDirectory`. 6 tabs (`format_subtab`, `codec_subtab`, `sampler_subtab`, `similarity_tab`, `media_loader_tab`, `image_crawler_tab`) implement independent `_directory_browse.py` mixin clones (e.g. `tabs/core/codec_subtab/_directory_browse.py:17-45` vs `tabs/core/format_subtab/_directory_browse.py:17-45`).
  - **Smell**: Each mixin probes undeclared host attributes (`last_browsed_dir`, `input_path`, `_recent_dirs_menu`, `scan_directory_visual`).
  - **Target**: Extract `gui/src/components/widgets/path_picker.py`. Encapsulates `QLineEdit` + browse button + MRU popup + monkeypatched dialog safety (`apply_patch` / `DontUseNativeDialog`).
- **G-2 (Missing Primitives: `TabularDataView` / `TabularDataModel`)**:
  - **Evidence**: `data_browser_tab/_query.py:138-154`, `database_tab/_refresh_edit.py:32-150`, `scan_metadata_tab/_auto_listings.py:138-160`, `entity_recon_tab/_batch_builder.py:42-44`, and `windows/cloud/dashboards_pane.py:177-183` all use raw `QTableWidget` + per-cell `QTableWidgetItem` allocations.
  - **Smell**: Querying 2,000 rows with 10 columns allocates 20,000 Python/C++ wrapper objects and iterates cells three times (`setItem`, `_style_fk_cells`, `_apply_cell_edit_flags`) on the main thread, necessitating `self.data_table.blockSignals(True)`.
  - **Target**: Reusable `QAbstractTableModel` in `components/views/data_table_view.py`. Virtualized viewport rendering, zero item allocation per cell, instant sorting/filtering.
- **G-3 (WallpaperTab State Aliasing & Circular References)**:
  - **Evidence**: `gui/src/tabs/core/wallpaper_tab/manager.py:27-34`:
    ```python
    self.monitor_display.monitor_image_paths = self.system_display.monitor_image_paths
    self.monitor_display.monitor_slideshow_queues = self.system_display.monitor_slideshow_queues
    self.monitor_display.monitor_current_index = self.system_display.monitor_current_index
    self.monitor_display.monitor_history = self.system_display.monitor_history
    self.monitor_display._initial_pixmap_cache = self.system_display._initial_pixmap_cache
    self.monitor_display.set_system_display_ref(self.system_display)
    self.system_display.set_system_display_ref(self.monitor_display)
    ```
  - **Smell**: Subtabs share mutable internal dictionaries directly without synchronization, and cross-reference each other symmetrically (note `system_display.system_display_ref` points to `monitor_display`).
  - **Target**: Move shared monitor queues to an encapsulated `WallpaperQueueController` service.

### 12.2 DRY Violations & Unreported Semantic Duplication
- **G-4 (15 Raw `threading.Thread` sites bypassed worker audit)**:
  - `gui_audit.py` measures `QThread` and `QRunnable` subclasses, completely missing raw `threading.Thread` calls in generative/training tabs:
    - `tabs/models/gen/lora_generate_tab.py:320`: `threading.Thread(target=self.run_generation, kwargs=config)` (non-daemon!).
    - `tabs/models/delta/lora_train_tab.py:261`: `threading.Thread(target=self.run_training, kwargs=config, daemon=True)`.
    - `tabs/models/gen/comfy_generate_tab.py:339, 393, 445`: 3 threads for worker startup, queue workflow, and log streaming.
    - `tabs/models/delta/cbir_train_tab/_index_builder.py:77` and `_training_worker.py:76`: thread targets emitting Qt signals (`self.sig_index_done.emit`, `self.sig_done.emit`) directly across thread boundaries.
    - `tabs/models/gen/ddm_generate_tab.py:147`.
    - `helpers/database/library_session.py:148`.
    - `helpers/web/media_loader_worker.py:53, 74`.
  - **Target**: Unify onto `BaseQThreadWorker` or `QThreadPool` tasks.
- **G-5 (Main-Thread Synchronous GAN Inference)**:
  - **Evidence**: `tabs/models/gen/gan_generate_tab.py:86-93`:
    ```python
    device = torch.device(self.device)
    gan = GAN(z_dim=100, channels=3, n_filters=32, n_blocks=3, device=device)
    gan.load_checkpoint(checkpoint_path)
    count = self.spin_gen_count.value()
    images_tensor = gan.generate_image(num_images=count)
    ```
  - **Smell**: Model loading and image tensor generation run synchronously on the GUI thread inside `generate_images()`, freezing the entire desktop UI during generation.
  - **Target**: Offload to `QRunnable` inference worker.

### 12.3 Styling & Theme Integrity
- Confirm Claude's 648 `setStyleSheet` and 962 inline hex literals.
- **G-6 (Hardcoded Theme Presuppositions)**:
  - `windows/cloud/dashboards_pane.py:118` and `windows/cloud/request_builder_pane.py:197` hardcode `"QTableWidget { background-color: #0d1117; border: 1px solid #30363d; }"`.
  - Violates Light theme presets and causes illegible dark-on-light artifacting. All styles must read `theme.color("surface")` / `theme.color("border")`.

### 12.4 Correctness Findings & Hotfix Candidates
1. **Tier 1 (Immediate Hotfixes — low risk, high value)**:
   - **F18 (Grok)**: `tabs/core/wallpaper_tab/monitor_display_subtab/manager.py:64-65`: `WallpaperCommonBase.__init__(self)` skips 14 mixins in MRO. Change to `super().__init__()`.
   - **F19 (Grok)**: `windows/settings/_appearance.py:483-486` and `_relaunch_settings.py:320-334`: Stop directly mutating `main_window_ref.cached_creds["preferences"]`; route through `PreferenceStore.set()`.
   - **F14**: `backend/src/utils/display/monitor_slideshow_daemon.py:52`: Guard `atexit.register(lambda: getattr(base, "run_monitor_slideshow", lambda _: None)("stop"))` to eliminate `AttributeError` tracebacks in test/headless environments.
   - **F26 (Grok)**: `tabs/__init__.py:1-7`: Defer eager package-level imports of `asp_gui`, `csg_gui`, and `hie_tab`.
2. **Tier 2 (Defect & Leak Guards)**:
   - **G-7 (Tray Quit Bypasses Tab Cleanup)**:
     - In `windows/main/_lifecycle.py:245-251`, `closeEvent` iterates `all_tabs` and invokes `tab.close()` to cancel workers/timers.
     - In `windows/main/_lifecycle.py:260-279` (`_quit_application` used by the tray Quit action), `tab.close()` is completely omitted. Quitting via tray leaves background worker threads unjoined and uncancelled while Qt terminates.
     - **Fix**: Add tab cleanup loop to `_quit_application()`.
   - **G-8 (Unbounded `waitForDone(-1)` on GUI thread)**:
     - `components/virtual_gallery/virtual_gallery_model.py:410`: `self.thread_pool.waitForDone(-1)`
     - `tabs/database/scan_metadata_tab/_scan_loading.py:43`: `self.thread_pool.waitForDone(-1)`
     - `tabs/core/image_extractor_subtab.py:609`: `self.operation_thread_pool.waitForDone(-1)`
     - **Fix**: Bound all drain calls to `_WORKER_DRAIN_TIMEOUT_MS` (2000 ms) as already established in gallery lifecycles.
   - **G-9 (`library_session.py` Thread + ProcessEvents Spinloop)**:
     - `helpers/database/library_session.py:148-154`:
       ```python
       thread = threading.Thread(target=work, daemon=True)
       thread.start()
       while thread.is_alive():
           QApplication.processEvents()
           thread.join(0.05)
       ```
     - Re-entrancy hazard on the main thread; replace with signal-driven `QEventLoop` or standard `BaseQThreadWorker`.

### 12.5 Performance & Resource Lifecycle
- **G-10 (Synchronous DB Loops on Main Thread)**:
  - `database_tab/_auto_populate.py:67-95`: iterates directories and issues sequential `tab.db.add_group` / `tab.db.add_subgroup` queries on the GUI thread.
  - `database_tab/_bulk_import.py:87-100`: issues sequential `tab.db.add_tag` queries per tag on the GUI thread.
  - While a `QProgressDialog` is shown, the main thread is pinned; batch transactions and worker delegation are needed.
- **G-11 (Asymmetric Lifecycle Deferral)**:
  - `windows/main/_lifecycle.py:280-330` (`_defer_close_for_extractions`) implements 7 hardcoded `hasattr` checks against `extractor_tab` only. Other long-running jobs (video conversion, training, cloud sync) lack any deferred close mechanism. A general `TaskLifecycleRegistry` is needed.

### 12.6 Test Surface & Verification Invariants
- `HostProtocol` conformance test suite (M1) is the essential missing verification harness for all remaining mixin tabs.
- Tests touching tables (`DataBrowserTab`, `DatabaseTab`) should assert virtual model row counts and zero GUI thread stalls rather than mocking `QTableWidget` items.

— Gemini / Antigravity, 2026-09-06

---

## 13. Cursor — 2026-09-06 — independent pass

Baseline `main` @ `8a693020`. Re-ran both audit scripts; their headline
counts match §1 except for expected movement on the live branch
(`_build_ui` definitions are now 46 and config methods are 34/32/27).
Additional reproducible greps used below:

```bash
rg -l 'explorer\.exe|xdg-open|\["open"|os\.startfile|QDesktopServices' gui/src -g '*.py'
rg -l 'send2trash|send_to_trash' gui/src -g '*.py'
rg -l 'from gui\.src\.helpers import|from \.{2,}helpers import' gui/src -g '*.py'
rg 'QThreadPool\(\)|QTimer\(\)' gui/src -g '*.py'
```

### 13.1 Composition and import boundaries

**C-1 — `gui.src.helpers` is an unmeasured eager import hub [HIGH].**
`helpers/__init__.py:1-47` eagerly re-exports 33 worker groups. Thirty-nine
GUI files import that barrel; importing one scanner therefore imports
conversion, deletion, database embedding, video extraction, four cloud
providers, crawlers, and reverse search. Twenty-seven helper files import
`backend`/`base` at module scope; the barrel also reaches module-level
`cv2`/NumPy through `duplicate_scan_worker.py:4-7` and
`queue_execution_worker.py:12`. `helpers/web/__init__.py:1-22` repeats the
same pattern for every web integration.

This extends F26 beyond `tabs/__init__.py`: replacing wildcard imports did
not make package barrels lazy. Call sites should import leaf modules, and
package `__init__` files should expose contracts/types only. Exit criterion:
zero production `from gui.src.helpers import ...` call sites and an
import-smoke assertion that a leaf image-worker import does not load web,
cloud, OpenCV, or ML modules.

**C-2 — preview-window ownership is still distributed [MEDIUM].**
Thirty-one files reference `open_preview_windows` or
`open_image_preview_windows`. Tabs append windows independently (for example
`sampler_subtab/_preview_context.py:31-45`,
`merge_tab/_preview_context.py:33-45`, and
`scan_metadata_tab/_context_menu_actions.py:174-187`), while highlight slots
remove the signal sender and eleven lifecycle implementations close their own
lists. `ImagePreviewWindow` already registers with `WindowManager`
(`image_preview_window.py:80-81`), but the registry cannot query by owner or
media path.

F4's proposed `PreviewContext` should therefore include a
`PreviewWindowController` keyed by `(owner_id, media_path)`, rather than only
renaming constructor data. Exit criterion: no tab-owned preview-window lists;
open/focus/close-all and highlight cleanup have one owner and one contract
test.

### 13.2 DRY and shared platform services

**C-3 — desktop open/reveal behavior is copied across 14 files [MEDIUM].**
Implementations variously use blocking `subprocess.run`, detached
`subprocess.Popen`, `os.startfile`, DBus `ShowItems`, and
`QDesktopServices`. Compare `elements/database/common/listings_common.py:84-117`
(selects the file, DBus fallback),
`database/search_tab/_file_actions.py:264-281` (opens only the parent
directory and blocks the GUI), and
`abstract_class_two_galleries/_context_menu.py:133-156` (opens media with
suppressed child output). Their semantics and error UI differ.

Extract `DesktopIntegration.open_path()` and `reveal_path()` with
non-blocking process launch, URL encoding, capability fallback, and typed
errors. Exit criterion: zero direct `explorer.exe`/`xdg-open`/`open`/
`os.startfile` branches outside that service.

**C-4 — deletion is several inconsistent policy engines [HIGH].**
Fifteen files implement deletion/trash behavior. The Search path reads
`send_to_trash` from `MainWindow.cached_creds`, always prompts, mutates the
filesystem and database, then rebuilds search
(`search_tab/_file_actions.py:80-119`). Scan does the same preference read
and always prompts but has different collection cleanup
(`scan_metadata_tab/_context_menu_actions.py:134-166`). The shared
two-gallery context menu reads only `confirm_deletions`, then always calls
`send2trash` (`abstract_class_two_galleries/_context_menu.py:216-248`), so
the user's permanent-delete choice is ignored on that surface. Neither
`confirm_deletions` nor `send_to_trash` is registered in
`preferences/definitions.py:94-253`.

Add typed ACCOUNT keys plus a `FileOperationService` with an immutable
`DeletionPolicy(confirm, disposition)` and a result listing successes and
failures. Views remain responsible only for confirmation presentation and
domain-state reconciliation. Exit criterion: one filesystem deletion
implementation, zero reads through `window().cached_creds`, and a matrix test
covering confirm on/off × trash/permanent × single/batch × DB-backed/plain.

### 13.3 Styling and theme integrity

I confirm §4 and G-6. C-3's platform service should return typed failures
rather than opening a bespoke `QMessageBox`, and C-4's deletion service
should do the same. This matters to theming as well as testability: common
error presentation can then be one themed component instead of each file
constructing modal dialogs and inline styles independently.

### 13.4 Correctness and hotfix candidates

**Small hotfix — MediaLoader worker retention and close race [HIGH].**
`MediaLoaderWorker._ensure_downloader()` permanently attaches four
`QtEventBridge`s to backend Observables
(`helpers/web/media_loader_worker.py:98-109`), and `run()` has no `finally`
detach (`:112-145`). The comment at `:54-57` says the bridge “lives and dies
with this worker,” but the Observable owns the bridge's bound `post`
callback, creating a retention chain back to the worker/downloader. Each new
download replaces `MediaLoaderTab.worker` (`media_loader_tab/_download_worker.py:83-88`)
without disposing the completed graph. The tab has no `closeEvent`; closing
it while the raw Python thread is active neither cancels nor joins it.

Add idempotent `dispose()` that cancels, bounded-joins, detaches all bridges,
and clears `_downloader`; call it on completion/error, before replacement,
and from tab teardown. Also make `QtEventBridge` detach on owner destruction
as a backstop. Targeted test: repeated workers leave zero Observable
subscribers, and tab close during a blocked fake downloader produces no late
slot delivery.

**Small hotfix — lazy-load timer survives cancellation [MEDIUM].**
`ScanMetadataTab` creates an unparented `_lazy_load_timer` and connects it to
`_process_visible_items` (`scan_metadata_tab/manager.py:118-122`).
`_ScanLoadingMixin.cancel_loading()` and `_stop_running_threads()`
(`_scan_loading.py:24-54`) do not stop it. A scroll debounce queued just
before module disposal can therefore run after gallery teardown. Parent the
timer to the tab and stop it in cancellation; test by arming it, cancelling,
advancing the event loop, and asserting no processing callback.

**Correctness — telemetry reports object existence as connectivity [MEDIUM].**
`TelemetryStatusBar._sample_telemetry()` marks DB connected whenever the
service and its `db` attribute are non-`None`
(`components/widgets/telemetry_status_bar.py:290-295`), not when the
connection is healthy. The component can show green after disconnect.
Subscribe to `DatabaseAvailabilityChanged` or query a non-blocking service
snapshot; never infer connectivity from object existence.

### 13.5 Performance and resource lifecycle

**C-5 — telemetry cold-start work was deferred, not removed [MEDIUM].**
The status bar explicitly records that `_sample_telemetry()` costs about
0.9 seconds cold, yet schedules it at the next event-loop turn
(`telemetry_status_bar.py:64-84`). The callback imports Torch, probes CUDA,
and queries device properties on the GUI thread (`:275-288`). This preserves
constructor timing but can freeze the first rendered frame, then repeats on a
3-second GUI timer.

Move sampling to one long-lived telemetry service/worker and publish
`TelemetryUpdatedFact`; the status bar should only render facts. Exit:
Torch/CUDA and DB probes never execute on the GUI thread, with a heartbeat
test proving the event loop remains responsive during a slow probe.

**C-6 — local pools avoid one deadlock but have no process budget [MEDIUM].**
Five explicit local `QThreadPool()` constructors coexist with global-pool
users. Every gallery instance receives a dedicated pool capped at eight
threads (`classes/base/gallery_base.py:85-100`), while Scan, virtual gallery,
Extractor and ImageExtractor own additional pools. On the eager classic
shell, concurrent tabs can therefore multiply CPU/native-decode pressure;
cache budgeting (§5.7) alone does not bound worker resources.

Keep per-owner cancellation domains, but allocate permits through a shared
`ResourceBudget`/scheduler (CPU, native-decode, subprocess, GPU) rather than
independent thread-count guesses. Exit: a static inventory accounts for
every pool/executor and a stress test asserts configured process-wide
concurrency without using a shared-pool teardown wait.

### 13.6 Test and roadmap deltas

Add these contracts to §9:

- **1.13 File operations and deletion policy:** typed preferences,
  `DesktopIntegration`, `FileOperationService`, and policy/result objects.
  Exit criteria are C-3/C-4's zero-direct-call counts and deletion matrix.
- **1.14 Import-cost boundary:** leaf imports only for `helpers/` and
  `tabs/`; CI import-smoke denies optional web/cloud/native/ML packages for
  unrelated leaf imports.
- **2.j Preview-window controller:** one owner-aware registry and no
  tab-local window lists.
- **2.k Telemetry sampler:** background sampling + facts only in the widget.
- **3.a Process resource budget:** retain independent cancellation domains
  while centrally limiting pools, native decodes, subprocesses, and GPU jobs.

Answers to §10:

- **Q-A:** keep `protos/` only through the live D10/D12 gate, then delete it
  in the same milestone; two editable copies are not a sustainable fallback.
- **Q-B:** Cursor can take the file-operation/deletion-policy slice after the
  roadmap is locked; it is disjoint from gallery scheduling if views retain
  their current state-refresh callbacks.
- **Q-C:** use `Signal(object)`, but carry a frozen `WorkerFailure`
  (`exception`, traceback text, task id) rather than a bare exception.
- **Q-D:** allow dynamic style assembly only in a centralized theming helper;
  canvas/overlay callers may supply geometry/state, not literal colors.
- **Q-E:** keep `tabs/<name>/` during migration. Enforce internal
  view/controller/config boundaries before considering a zero-value rename.

— Cursor, 2026-09-06

### 13.7 Parallel-audit follow-up: defects that change priority

Four independent read-only passes completed after §13 was committed. The
following were re-checked on the same tree and should be incorporated before
the roadmap is locked.

**C-7 — cross-tab path handoff is broken on both shell paths [CRITICAL].**
Search publishes `ImportPathsIntent` *before* `NavigateIntent` for Scan,
Merge, Similarity and Wallpaper
(`search_tab/_tab_communication.py:29-88`). The runtime shell subscribes only
to navigation (`components/navigation/shell_manager.py:65-68`), so a lazy
target does not exist to receive the first intent. The production catalog
also constructs Merge and Similarity through `_tab(...)`, which discards
`ModuleContext` (`modules/application_catalog.py:90-96,121-130`).

The classic fallback is independently broken: its import handler calls
`self.merge_tab.display_scan_results(...)`
(`windows/main/_tab_registry.py:176-183`), but that method exists only in the
Wallpaper stack, not Merge. Search → Merge therefore raises `AttributeError`;
Search → Scan/Wallpaper has no legacy handler at all.

Fix before runtime-shell rollout: introduce queued target delivery owned by a
single navigation/import controller, activate or construct the target, then
deliver to a typed `PathImportReceiver`. Test all four targets on classic and
runtime shells, including intent-before-first-mount.

**C-8 — runtime disposal bypasses tab cleanup [HIGH].**
`WidgetHandle.dispose()` only calls `deleteLater()`
(`modules/runtime.py:39-53`). Runtime-shell `all_tabs` is empty, so the
classic MainWindow loop cannot trigger tab `closeEvent` cancellation.
Activated Extractor, Merge, Wallpaper, Search or training workers can
therefore outlive a disposed widget. Define a module lifecycle contract:
`close/cancel → bounded drain → detach subscriptions → deleteLater`, and test
it with a mounted fake worker. This is more urgent than generic module LRU.

**C-9 — the gallery “timeout” constants are actually unbounded [HIGH].**
`constants/classes.py:7-10` assigns `-1` to both drain timeout constants.
Consequently the ostensibly bounded waits in single/two-gallery lifecycle
code are infinite. This corrects the earlier G-8 wording that cited a
pre-existing 2000 ms gallery standard. Exit: no `waitForDone(-1)` directly or
through constants; a hung-worker close test returns within the configured
deadline and logs the unresolved task.

**Immediate logic/thread hotfix queue (all code paths verified):**

1. `helpers/core/duplicate_scan_worker.py:189-190` runs SIFT
   `_chunked_compare` twice; the first pass evicts its cache, so the second
   overwrites valid results with an empty result. Delete the duplicate call
   and add a known-descriptor regression test.
2. `search_tab/_search_worker.py:25-57` assigns each new worker to
   `current_search_worker`, but completion slots do not validate sender
   identity. Filter paths call `perform_search()` directly
   (`_tag_filters.py:160`, `_group_filters.py:123`), so stale search A can
   clear worker B and overwrite B's UI. Cancel previous work and gate every
   terminal slot by worker/generation.
3. `cbir_train_tab/_training_worker.py:62-78` calls
   `_ckpt_path.setText(...)` from a raw Python thread. Emit the path and
   update the widget in a GUI-thread slot.
4. Merge and Reverse Search wire `scan_finished` but not `scan_error`
   (`merge_tab/_scan_input.py:74-80`,
   `reverse_search_tab.py:285-291`). An invalid/unreadable directory can
   leave the UI stuck in its scanning state. Connect a shared terminal error
   handler and test UI reset.
5. The LoRA QML route starts a non-daemon generation thread
   (`lora_generate_tab.py:320-321`), unlike its other entry point. The
   lasting fix is WorkerBase adoption; the immediate guard is bounded
   cancellation/teardown.

**Additional demonstrated GUI-thread workloads to schedule:**

- Entity Recon decodes with OpenCV and performs click segmentation on the
  GUI thread (`entity_recon_tab/_source_image.py:28-59`).
- Crawler duplicate detection walks directories and computes SHA-256/pHash
  synchronously (`components/dialogs/crawler_selection_dialogs.py:632-755`).
- Full-size preview/compare windows decode `QPixmap(path)` on the GUI thread;
  compare retains all input pixmaps rather than only the active pair
  (`image_preview_window.py:319-327`,
  `image_compare_window.py:219,509-545`).
- Virtual gallery fill defaults can enqueue every uncached path and retain
  full `_loading`/`_failed` sets (`virtual_gallery_model.py:77-97,171-206`).

These extend `DirectoryScanService`, `TaskProgressSession`, virtualized
models and the shared resource budget already proposed; they do not justify
new parallel frameworks.

— Cursor, 2026-09-06
