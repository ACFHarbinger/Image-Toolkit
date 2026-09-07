# GUI Architecture & Code Analysis (Draft — shared, edit me)

**Authors:** DeepSeek (draft F1–F16 + roadmap skeleton); Grok (independent pass F17–F26 + answers to §7) | **Date:** 2026-09-06 | **Status:** FOLDED 2026-09-06 — every finding F1–F26 is mapped to an item in `docs/moon/roadmaps/gui_refactoring.md` (see the team report §11 for the cross-map). Evidence record; append only.
**Target:** `gui/` on `main` (`ebb3afdd`; DeepSeek's measurements were against `ee91cd01`).

This is the start of a detailed, comprehensive analysis of the GUI architecture and code
implementation, toward making the app more modular and component-based, respecting DRY,
and finding performance/resource optimizations plus bug hotfixes. It is deliberately a
*draft*: the consolidated roadmap is the subsequent step. Findings are evidence-based
(grep/read on the current tree); anything marked `[verify]` needs eyes-on confirmation.

---

## 0. Executive summary

The GUI is a large, **tightly-characterized Qt monolith** (~80k lines under `gui/src/`,
`tabs/` alone ≈ 40k lines / 291 files) built on a **wide-mixin composition pattern**, where
each tab class inherits 8–15 per-concern mixin modules. Over the last sessions the team has
already landed a strong architectural foundation (Phase 0 invariant locks, Phase 1 typed
contracts, and Phase 2 consolidation) — much of the *scaffolding* for modularity now exists:

- `PreferenceStore` / typed key ownership (#525) — single read/write path, `QSettings`/vault as adapters.
- `Observable` + `QtEventBridge` (#529) — backend-thread→GUI-thread event safety.
- `WindowManager` (#528) — replaced `topLevelWidgets()`/`allWidgets()` discovery.
- `ModuleCatalog`/`ModuleContext`/`ModuleRuntime` + typed `EventHub` intents (#533) and lazy factories.
- `Database/Listings/Scan` typed-intent migration (#534) — Database-family off direct QWidget coupling.
- `ThumbnailScheduler` (#526) + gallery unification (#543, lands pending D12).
- Tab-mixin migration started (#544): `DatabaseTab`'s 12 mixins → composition.

**The remaining gap is not the contracts but the *mass* of per-tab mixin bloat, residual
direct coupling (settings→`MainWindow`, preview-window kwarg vestiges, `db_tab_ref` naming),
and the absence of a unified component/service model for cross-cutting concerns.** The bulk
of the refactor is mechanical de-duplication onto the foundations already laid.

---

## 1. Structural landscape

| area | files | lines | note |
|---|---|---|---|
| `gui/src/tabs/` | 291 | 39,672 | 5 sub-packages: core, database, models, web, (+mixed); the monolith |
| `gui/src/windows/` | 63 | 13,537 | MainWindow, settings, previews, cloud, slideshow |
| `gui/src/components/` | 59 | 10,654 | reusable widgets (galleries, dialogs, elements) |
| `gui/src/helpers/` | 69 | 9,463 | web workers, thumbnails, display, cloud |
| `gui/src/classes/` | 39 | 5,310 | gallery base classes + protocols |
| `gui/src/modules/` | 15 | 1,539 | the new runtime/catalog/event/service contracts |
| `gui/src/preferences/` | 9 | 914 | #525 PreferenceStore |
| `gui/src/constants/` | 13 | 616 | constants |
| `gui/src/styles/` `theming/` `elements/` `utils/` `protos/` | — | — | ancillary |

**Mixin-blob breadth (DRY/structural finding #1).** 19 tabs/subtabs compose **8–15 mixin
modules** each. Representative:
`core/wallpaper_tab/common/wallpaper_common_base` (15), `core/extractor_tab` (15),
`core/wallpaper_tab/monitor_display_subtab` (15), `database/scan_metadata_tab` (14),
`core/similarity_tab` (14), `database/search_tab` (13), `database/database_tab` (13, now
partially composition-ized by #544), `web/entity_recon_tab` (13), `web/drive_sync_tab` (11).
Manager files range 40–304 lines; the mixin modules themselves are typically thin.

`AbstractGalleryBase` (`gui/src/classes/base/gallery_base.py`) centralizes 27 gallery
methods and is the intended shared substrate; `gui/src/classes/image/protos/{abstract_class_single_gallery,abstract_class_two_galleries}.py`
hold the shared protocols.

---

## 2. Modularity / DRY violations

### F1. Mixin-per-concern → composition migration is only ~5% done  [HIGH]
19 tabs are still wide-mixin. #544 migrated `DatabaseTab` (12 mixins) as the first proof.
**Recommendation:** make the composition (single composed class + explicit small components)
the template, then migrate the remaining 18 one tab at a time (not big-bang). This is the
single largest DRY/structural win in the codebase.

### F2. Gallery implementation de-duplication  [MEDIUM]
`AbstractClassSingleGallery`, `AbstractClassTwoGalleries`, and the Wallpaper override share a
large surface (pagination, card widgets, selection, context menu, `db_tab_ref`/preview
handling). #543 unified thumbnail *scheduling*; the *rendering/selection/pagination* logic
still duplicates across the four. **Recommendation:** after #543 lands, factor the shared
model/view/selection plumbing into one base (lean hard on `AbstractGalleryBase`) and leave
each tab only its domain-specific presentation.

### F3. Worker-type duplication  [MEDIUM]
Many near-identical worker classes across `helpers/` (batch image, single image, batch video,
single video, card thumb, duplicate scan, cloud sync, web crawlers). They differ only in
decode strategy / payload. **Recommendation:** a generic "batch worker" parameterized by a
decode callable + a shared lifecycle (generate-tag, cancel, `Observable` emit) would collapse
several; keep single-shot wrappers thin.

### F4. Preview-context duplication  [LOW-MEDIUM]
`image_preview_window.py` + many `_preview_context.py` / `_properties_preview.py` /
`_image_preview_delete.py` modules duplicate the "open a preview with a db handle/selection"
plumbing. **Recommendation:** one `PreviewContext` value object (image path, resolution,
tags/metadata, db service) threaded via the typed `EventHub` / a shared preview service.

### F5. `db_tab_ref` kwarg is now a misnomer  [LOW]
`ImagePreviewWindow.__init__(db_tab_ref=None)` (`gui/src/windows/image_preview_window.py:49`)
still names the parameter `db_tab_ref`, but #534 callers now pass `db_tab_ref=self.database_service`
(e.g. `gui/src/tabs/database/search_tab/_file_actions.py:252`). **Recommendation:** rename the
parameter to `database_service` and thread the `LibraryDatabaseService`, removing the
misleading name. `db_tab_ref=None` call sites should be removed or become service-less.

---

## 3. Coupling

### F6. Settings window → `MainWindow` back-reference  [HIGH]
`gui/src/windows/settings/*` uses `self.main_window_ref` **42 times** across 7 files
(`settings_window.py`, `_appearance.py`, `_theme_studio_mixin.py`, `_tab_config_management.py`,
`_reset_state.py`, `_relaunch_settings.py`, `_profile_management.py`). Settings reach up into
MainWindow for geometry/zoom/theme/restart/tab-config/relaunch. **Recommendation:** route these
through the `EventHub` intents / `PreferenceStore` ACCOUNT keys (as #525/#534 did for the
Database family) plus a small `WindowService` (the `WindowManager` already exists), so
settings don't hold a `MainWindow` object. This is the biggest residual coupling block.

### F7. Residual direct-object coupling (60 refs total)  [MEDIUM]
Post-#534, 60 `*_tab_ref`/`main_window_ref`/`db_tab_ref` refs remain. The non-settings
majority are the `db_tab_ref` preview kwarg + `legacy.pop("db_tab_ref", None)` coerce shims
(backward-compat, acceptable) and a handful in `cloud_compute_window.py` / `image_preview_window.py`.
**Recommendation:** finish F6; keep the coerce shims only as long as the preview kwarg rename
(F5) is un-landed; then the tab-family should be fully intent/service-based.

### F8. `hasattr`-guarded silent no-ops  [MEDIUM — bug-class]
~122 `if hasattr(` checks in `gui/src/tabs/`. Most are legitimate capability tests, but the
#545 family ("method called on a tab it doesn't implement → silent no-op") may exist in others.
**Recommendation:** sweep for `hasattr` guards around *method-call sites* on sibling widgets;
convert to explicit capability protocols (raise/clear log) per the #545 principle. `[verify]`
which of the 122 are silent no-ops vs. real defensive capability checks.

---

## 4. Performance & resource optimization

### F9. Threading model is healthy; finish the exceptions  [MEDIUM]
`gui/src` shows **84 `QRunnable` + 67 `QThreadPool`** (good), but still some `moveToThread`
(7) and `QThread` subclass workers (e.g. `WebRequestsWorker`, `ImageCrawlWorker`).
**Recommendation:** standardize on `QThreadPool` + `QRunnable` with the `Observable`/
`QtEventBridge` completion contract; prefer `QThreadPool` for one-shot loads (already the
majority). Keep `QThread` only where a long-lived persistent service requires it.

### F10. Re-entrancy / blocking main-thread dialog calls  [MEDIUM]
49 `.exec()` / `processEvents()` uses in `tabs`/`windows`. Modal `QMessageBox` on the GUI
thread is acceptable for user prompts, but bare `QApplication.processEvents()` and long
synchronous DB/network calls on the main thread are re-entrancy hazards (and were a factor
in this repo's crash history). **Recommendation:** audit `processEvents()` usages `[verify]`;
move any blocking DB I/O behind the worker/services and publish availability facts (there's
already `DatabaseAvailabilityChanged`).

### F11. Native decode serialization is in place  [verification]
`NATIVE_IMAGE_BATCH_LOCK` / `NATIVE_SCAN_LOCK` / `QImageReader` (33 refs) from Phase 0 are
present. **Recommendation:** treat as locked; do not reintroduce unbounded parallel native
decode. Re-visit throughput only after #543's D12 (which touches all four galleries at once).

### F12. Resource lifecycle / disposal  [MEDIUM]
`ModuleRuntime` (cache-by-account policy, #533) exists but the lazy-eviction + per-account
disposal semantics are documented as still-open (§5 of the UI-arch doc). **Recommendation:**
implement the eviction/LRU + account-switch disposal once the catalog is the primary shell —
prevents long-session leaks (thumbnails, workers, module widgets) that this session's work
already flags as a known constraint.

### F13. GIF disk-cache + visible-first: locked, keep  [verification]
Phase 0 #522 GIF disk-cache and visible-first dispatch are in place and must not regress
(re-check against #543 which touches all four galleries — already review-verified).

---

## 5. Bug hotfixes

### F14. `base.*.so` atexit `run_monitor_slideshow` AttributeError  [LOW — test-env only]
Fresh worktrees without the built C++ extension log
`atexit.register(lambda: base.run_monitor_slideshow("stop"))` → `AttributeError` at
interpreter shutdown (`gui/src/.../monitor_slideshow_daemon.py:51`). Environmental, not a
product bug. **Recommendation:** guard the `atexit` registration with an
`hasattr(base, "run_monitor_slideshow")` (or import-try) so test logs are clean; improves
test hygiene for every agent.

### F15. Missing `@dataclass` on fact classes (historic regression, now fixed)  [done]
The #526/#533 auto-merge had briefly duplicated `DatabaseAvailabilityChanged` without its
`@dataclass` decorator; caught and kept #533's correct definition. **Recommendation:**
keep/verify `@dataclass(frozen=True, kw_only=True, slots=True)` on every `Intent`/`Fact` as
new ones are added (`gui/src/modules/events.py`).

### F16. Silent API / naming incoherence (F5) and remaining hasattr gaps  [MEDIUM]
See F5 / F8. These are the class of "fails silently, not loudly" bugs the team has hit
twice. **Recommendation:** prefer explicit capability protocols; log loudly when a sibling
doesn't support an operation.

---

## 6. Proposed refactoring roadmap (draft skeleton for the team to expand)

Phase A — **Finish the foundations (mostly done).**
- Land #543 (gallery unification) through its D12 live-desktop gate (Codex/Harbinger).
- Complete the remaining tab-mixin → composition migration (#544 template) for the 18 tabs.

Phase B — **Cut residual coupling & DRY hotspots.**
- F6: settings→`MainWindow` → typed intents + `WindowService`/`WindowManager` (+ `PreferenceStore`).
- F5: rename `db_tab_ref` → `database_service`; remove `None` shims; finish intent-based DB family.
- F3: generic batch worker; F4: shared `PreviewContext`; F2: gallery rendering de-duplication.

Phase C — **Performance & resource.**
- F9: finish `QThreadPool` standardization; F10: audit `processEvents`/blocking main-thread I/O.
- F12: module widget LRU eviction + account-switch disposal; memory/thread leak sweep.

Phase D — **Robustness & hygiene.**
- F8/F16: silent no-op sweep → explicit protocols; F14: clean `atexit`; guard test-env noise.
- Consolidate the runtime shell as the primary shell (behind preference flag) once Phase B/C land and parity (#516) holds.

**Sequencing note:** B and C can run in parallel; A must land first (it's the substrate).
D is low-risk and can be sprinkled throughout. Anything touching all four gallery
implementations (F2, F9) needs the D12 live-desktop bar, not just green tests — per #543/#536.

---

## 7. Open questions for the team / user

1. **Mixin migration scale:** 18 tabs is a lot — do we prioritize by *risk* (tabs that touch
   galleries) or by *current pain* (tabs with most violations)? Recommend risk-first.
2. **Settings decoupling shape:** should settings reach MainWindow via the `EventHub` intents,
   or via a dedicated `WindowService` (recommended) since settings are inherently app-level?
3. **`db_tab_ref` removal scope:** the preview kwarg is threaded from many gallery contexts;
   confirm we want to rename+service-thread it in one pass (F5) or leave a thin compat shim.
4. **Gallery consolidation after #543:** is full `AbstractClassSingleGallery`/`TwoGalleries`
   merge in scope for Phase 2, or is that Phase 3 (#532)? Recommend Phase 3 after the shell is stable.
5. **Eviction policy:** what is the concrete LRU/memory threshold for module widget eviction
   (currently an open item in the UI-arch doc)?

---

*This is a starting point — add findings, correct severity, and tie each to a GitHub
issue/epic. Then we turn this into the locked `ui-architecture` refactoring roadmap.*

---

## 8. Grok independent pass (2026-09-06) — new evidence, not a restatement of F1–F16

Read DeepSeek's draft, then re-measured `gui/` on `main`. Agree with the four-phase skeleton and with F1/F6 as the two biggest remaining structural jobs. Below is what that draft under-counted or missed. Citations are against this tree.

### Corrections to the draft

- **F1 DatabaseTab count is stale.** On current `main`, `DatabaseTab` is `class DatabaseTab(QWidget)` with composed controllers (`gui/src/tabs/database/database_tab/manager.py:35`). It should drop out of the "19 mixin tabs" list. `DataBrowserTab` mixins now precede `QWidget` (`data_browser_tab/manager.py:17-28`) — MRO-safe, still mixin-shaped. Remaining wide-mixin surface is **MainWindow + ~18 tabs/subtabs**.
- **F9 under-counts `QThread`.** DeepSeek's "a few `QThread`/`moveToThread`" is wrong as a census. `gui/src/helpers/` still has **~25 `QThread` subclasses** (conversion, deletion, merge, sampler, codec, scan, embed, upsert, recommendation, LoRA/training, MAL sync, recon, crawl, web-requests, local-dir sync, storyboard, frame-selection, …) plus a dedicated `BaseQThreadWorker` next to `BaseQRunnableWorker` (`helpers/base.py:7-28`). The *thumbnail* path is QRunnable-healthy; the *heavy job* path is still a second threading dialect.

### F17. Two construction graphs for one app  [HIGH]

Classic shell (`main_window.py:159-186`) still calls `_create_tabs()` and **eagerly constructs ~25 tab objects** before show. Runtime shell (`:152-158`) is lazy via `ModuleRuntime`. Default is classic. `gui/src/tabs/__init__.py:1-7` still imports `asp_gui`, `csg_gui`, and `hie_tab` at package load, so even a "small" tab import pulls Stitch/Manga/HIE.

This is the same eager-mount family as the 2026-09-05 SIGSEGV, just on the default path rather than the experimental one. #530 stopped `import *`; it did not stop eager *construction*. **Recommendation:** treat "classic `_create_tabs` constructs everything" as the next crash-class invariant to shrink — not by deleting classic (parity/#516), but by making classic tab construction lazy-on-first-category-select, reusing catalog factories. D12 required.

### F18. `MonitorDisplaySubTab` still skips mixin `super()`  [HIGH — live MRO landmine]

`gui/src/tabs/core/wallpaper_tab/monitor_display_subtab/manager.py:64-65`:

```python
def __init__(self, parent=None):
    WallpaperCommonBase.__init__(self)
```

WallpaperCommonBase itself is a 15-mixin class. Calling the base `__init__` by name **skips every mixin `__init__`** on that MRO. Flagged in the 09-05 deep-dive; still live. Any later mixin that grows an `__init__` will silently no-op. **Hotfix:** `super().__init__()` (and `setParent` after). Small, testable, should not wait for a Wallpaper composition pass.

### F19. Settings still dual-writes `MainWindow.cached_creds`  [HIGH — same class as the tray regression]

`PreferenceStore.attach_vault_credentials()` is wired at login (`main_window.py:115-119`). Settings appearance/relaunch **still mutate the in-memory vault dict directly**:

- `_appearance.py:474-487` reads/writes `main_window_ref.cached_creds["preferences"]`
- `_relaunch_settings.py:320-334` assigns `main_window_ref.cached_creds = user_data` and `hasattr`-calls `_apply_startup_preferences`

That is the dual-source pattern Phase 0.3 / #525 existed to kill. F6 (drop `main_window_ref`) is the lasting fix; **F19 is the hotfix**: those writes must go through `PreferenceStore` ACCOUNT keys or they will desync again on guest/restart. 44 `main_window_ref` hits remain, all in settings + `cloud_compute_window.py` + a `None` on detail-panel.

### F20. Seventeen `_UIBuilderMixin` classes with the same name  [MEDIUM — DRY]

`class _UIBuilderMixin` is defined independently in **17 files** (search, scan, listings×2, similarity, format, codec, sampler, crawler, drive-sync, media-loader, entity-recon, cbir-train, system-display, data-browser, detail-panel, display view). They do not share a type. #544's `DatabaseUIBuilder` is the right shape; the copy-paste name is a lie. **Recommendation:** one `SectionedFormBuilder` / layout helper for "labeled rows + groupboxes"; tab-specific widgets stay local. Do not invent a 17th mixin.

### F21. Card rendering is still forked after #543  [MEDIUM]

`create_card_widget` exists twice: `abstract_class_single_gallery/_card_rendering.py:94` and `abstract_class_two_galleries/_card_rendering.py:32` (extra `is_selected`). Scheduler unification did not touch this. Listing galleries (`ListingGalleryBase` → TwoGalleries) inherit the two-gallery fork. VirtualGallery is a third card surface (delegate + overlay roles). **Recommendation:** Phase 3 after #543 D12 — one card factory + one selection/highlight helper; keep pagination differences.

### F22. `MainWindow` is still a 16-mixin composition root  [MEDIUM]

`main_window.py:46-66`: header, runtime-shell, tab-registry, theme, tray, tab-search, global-search, workflows, shortcuts, save/load tab-config, startup prefs, session recovery, zoom, lifecycle, then `QWidget`. The comment about mixin-before-QWidget is load-bearing (`closeEvent`/`keyPressEvent`/`showEvent`/`wheelEvent`). #544's DatabaseTab template does **not** apply here without extracting those Qt overrides into a real window object. **Recommendation:** do not "DatabaseTab" MainWindow in one PR. Peel one event at a time (tray, theme, zoom already have files) onto services; keep the MRO comment until the last override moves.

### F23. Classic vs catalog factory drift  [MEDIUM]

`_tab_registry.py:61-89` constructs tabs with `(library_database_service, event_hub)` for Database/Search/Scan/Wallpaper. `application_catalog.py` has the same constructors behind `try/except TypeError` fallbacks. Two sources of truth for "how to build a tab." A ctor change that only updates one path will look tested on classic and fail on the experimental shell (or the reverse). **Recommendation:** classic `_create_tabs` should call the catalog factories (or a shared `build_tab(id, context)`), not duplicate kwargs.

### F24. Notification helpers still duck-type  [LOW]

`_notify.py` uses `WindowManager` (good, #528) then `hasattr(w, "tray_notify"|"show_status"|"show_toast")`. Silent no-op if the protocol drifts. **Recommendation:** a tiny `StatusSink` protocol on MainWindow; missing method should log, not `hasattr`-pass.

### F25. `processEvents` leftovers are concentrated  [MEDIUM]

Live `QApplication.processEvents()` remains in drive-sync UI lock + two sync subtabs, similarity deletion, and `library_session.py:151`. Wallpaper already documents why it **removed** the same call (`_monitor_selection.py:63-86` — reentrant timers). **Recommendation:** treat wallpaper's comment as the rule; replace the drive-sync/similarity pumps with a single-shot `QTimer` or a progress fact. Don't add new `processEvents`.

### F26. Import barrel still pulls optional native UIs  [MEDIUM]

`gui/src/tabs/__init__.py` named-imports `StitchTab`/`Manga*`/`HieEditorTab` from submodules at package import. `_tab_registry` then `from ...tabs import StitchTab, ...`. Classic startup therefore always imports ASP/CSG/HIE GUI even if the user never opens those categories. **Recommendation:** lazy-import those three inside `_create_tabs` / catalog factories only.

---

## 9. Grok answers to §7 (signed, 2026-09-06)

1. **Mixin migration order:** risk-first, but **skip gallery-owning tabs until #543 D12 is green**. Next after DatabaseTab: `DataBrowserTab` (already MRO-fixed, 6 mixins, no gallery), then `DriveSyncTab` / `EntityReconTab` (no gallery). Leave `SearchTab`/`ScanMetadataTab`/`ExtractorTab`/`WallpaperCommonBase` until the scheduler unification has a live pass — those are the crash family.
2. **Settings decoupling:** `WindowService` + `PreferenceStore`, not a pile of new EventHub intents for zoom/geometry. Intents for "relaunch / apply tab configs"; store for theme/tray/zoom. F19 (stop writing `cached_creds` by hand) can land before the full F6 extract.
3. **`db_tab_ref` rename:** one pass with a short alias shim (`db_tab_ref=` kwargs still accepted, warn once). Preview contexts are too many for a silent rename.
4. **Gallery merge beyond scheduler:** Phase 3 (#532). #543 is scheduling only; F21 card/selection merge is a second D12. Do not combine with mixin migration of Search/Scan.
5. **Eviction:** don't pick a magic N. Measure RSS of runtime-shell with 3 vs 8 mounted modules on Harbinger's machine after #543 D12; set LRU from that number. Until then, dispose on account-switch only (already specified, not implemented).

— Grok, 2026-09-06

