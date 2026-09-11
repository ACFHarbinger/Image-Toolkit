# GUI Refactoring Roadmap — modular, component-based, DRY

**Status:** LOCKED 2026-09-06 (Claude + user, from two team analysis passes).
Tracking unit of record: GitHub milestone **GUI Refactoring Roadmap** (#10) and
the `ui-arch-25+` issues listed per item below. This document is the design
rationale and the ordered plan; use the issues for status.

**Integration branch (2026-09-07, user decision):** every remaining item in
this milestone lands on `milestone/gui-refactoring-roadmap`
([PR #576](https://github.com/ACFHarbinger/Image-Toolkit/pull/576)), not
`main` directly. One branch + PR per milestone from
now on; the PR merges to `main` once every issue under #10 is closed. Item
branches (`feature/ui-arch-NN-<slug>`) merge into the milestone branch, same
review/D12 gates as before — see §1's workflow line.

**Supersedes and folds in** (all removed or reduced to pointers on the same
day, so there is one place to look):

| Folded source | What moved here |
|---|---|
| `docs/moon/roadmaps/ui_architecture_2026q3.md` | UI shell / module runtime decisions and re-land history (§2.3), its open items (§7) |
| `docs/moon/roadmaps/ui_module_inventory_2026q3.md` | the module/route inventory table and its test contract (§2.4) |
| `docs/moon/roadmaps/app_theming_2026q3.md` | theming decisions and the unstarted Phase 2/3 surfaces (§2.5, §5 R2.b, §5 R4) |
| `docs/moon/roadmaps/architecture.md` §5.18 / §5.19 | Phase 0 invariant lock and Phase 1 contracts tables (§2.1, §2.2) |
| `.agent/reports/team/architecture_deep_dive_2026-09-05.md` §7 Phase 2/3 | replaced by §5 R2/R3 here; #531/#532 closed as superseded |

Evidence behind every item: `.agent/reports/team/gui_refactor_analysis_2026-09-06.md`
(Claude, final) and `.agent/reports/deepseek/gui_architecture_analysis_2026-09-06.md`
(DeepSeek F1–F16, Grok F17–F26). Finding IDs (`§3.1`, `F18`) below refer to those.

---

## 1. Goals and rules

**Goal.** A feature's change stays inside its own package. Shared behaviour
lives in one module. Bugs of the 2026-09-05 class (desktop-only rendering,
thread-affinity crashes, silent no-ops, dual-source settings) become
structurally harder to write, not just caught later.

**Component rules** (enforced by `#530`'s linters where marked ⚙, by review otherwise):

1. A tab package imports `gui.src.core`-level contracts, `components/`,
   `theming/`, `helpers/` workers, and itself. Never another tab. ⚙ (extend)
2. `components/` imports `theming/` and contracts only; no backend, no tabs. ⚙
3. Workers derive from `BaseQThreadWorker` / `BaseQRunnableWorker`; signals are
   `finished` / `error` / `progress`; no widget imports. ⚙ (R1.1)
4. Colours come from the theme token API; no `#rrggbb` literals or
   `setStyleSheet` outside `theming/` and `styles/`, allowlist pruned to zero. ⚙ (R2.b)
5. No `hasattr` on a sibling widget to decide whether to call it. Use a
   Protocol; a missing capability logs loudly.
6. No blocking IO in a slot. No new `QApplication.processEvents()`.
7. Ordering by `QTimer.singleShot` is replaced by explicit state on the owning controller.
8. One preference key has one owner (`PreferenceStore`); the vault holds secrets only.

**Backward-compatibility shims.** Every alias, forwarder, `legacy.pop(...)`,
or dual code path introduced while porting is tagged
`# COMPAT(ui-arch-NN): remove after <condition>` and listed in the issue's
checklist. The issue is not closed until every one of its shims is deleted.
A shim that outlives its issue is a bug.

**Gates.** Codex cross-review is mandatory before merge. Anything touching
gallery loading, workers, session recovery, the extractor player, settings
persistence, or shell mounting also needs a D12 live-desktop pass
(KDE Plasma/Wayland, real vault, real data), not offscreen green. The
RESOURCE RULE in `AGENTS.md` still applies: no benchmark or full-suite runs
outside the Codex/Harbinger chain.

**Workflow per item.** Claim on the bus → isolated worktree on
`feature/ui-arch-NN-<slug>` (branched off `milestone/gui-refactoring-roadmap`,
not `main`) → targeted tests + `ruff` + `py_compile` +
`backend/validation/check_init_boundaries.py` → bus post with commit hash →
Codex review → D12 if gated → merge to `milestone/gui-refactoring-roadmap` →
shim checklist emptied → close issue. Docs land with the code
(`docs/moon/CHANGELOG.md` entry, this file's status column). The milestone
branch itself merges to `main` via its own PR once #10 has zero open issues —
see the note under Status above.

---

## 2. What is already done (folded history)

### 2.1 Phase 0 — invariant lock (shipped 2026-09-05, D12-verified)

| Item | Issue | Result |
|---|---|---|
| Serialized native decode + GIF/animated bypass | #521 | `NATIVE_IMAGE_BATCH_LOCK` / `NATIVE_SCAN_LOCK` (`backend/src/constants/core.py`) guard every native decode; `.gif` routed to `QImageReader` |
| Visible-first thumbnail dispatch, all four galleries | #522 | `_sort_paths_by_visibility()`, `VirtualGalleryModel.set_visible_range()` / `_reorder_fill_queue()` |
| One-owner tray preference | #523 | `minimize_to_tray` / `close_to_tray` device-owned by `AppSettings`/QSettings only |
| Prototype quarantine + WallpaperTab forwarders | #524 | `gui/src/protos/` (now superseded by the re-land, see R0.4) |
| GIF disk cache (found live) | — | `helpers/image/_qimagereader_disk_cache.py`, 40× warm-read speedup |
| Session-recovery freeze guard (found live) | — | 500 MB budget on `ExtractorTab._load_existing_output_images()` |

### 2.2 Phase 1 — six contracts (shipped 2026-09-05, cross-reviewed, merged `dee43085`)

| Contract | Issue | Where |
|---|---|---|
| `PreferenceStore` (DEVICE/ACCOUNT/SESSION scopes, adapters) | #525 | `gui/src/preferences/` |
| `ThumbnailScheduler` interface | #526 | `gui/src/thumbnails/` |
| `ModuleDescriptor` + `ModuleHost` pilot (Log Panel) | #527 | `gui/src/modules/` |
| `WindowManager` registry | #528 | `gui/src/windows/window_manager.py` |
| Backend `Observable` + `QtEventBridge` (no Qt under `backend/src/` except `app.py`) | #529 | `backend/src/events.py`, `gui/src/qt_event_bridge.py` |
| CI import-boundary guardrails (fail merge) | #530 | import-linter contract + `backend/validation/check_init_boundaries.py` |

### 2.3 UI shell & module runtime (re-landed 2026-09-06, milestone 8 closed 18/18)

Built once, crashed (eager shell-module mounting → `QSocketNotifier`
cross-thread SIGSEGV), fully reverted (`7559b1d2`), rebuilt on Phase 0/1 as
ui-arch-10..19 (#533–#542) plus the #516 parity report. Decisions that still bind:

1. **Module catalog + lifecycle runtime** (`gui/src/modules/{catalog,context,events,runtime}.py`):
   immutable descriptors (`Page` / `Workspace` / `Route`), factories take a
   `ModuleContext` (event hub + services, never a widget), return a lifecycle handle.
   Lazy activation is enforced by a contract test, not convention.
2. **Typed event bus**: Intents (commands), Facts (broadcast, coalescable),
   Requests kept off the bus as typed service calls. Every event carries an
   origin id; subscriptions die with the module.
3. **Stitch is one workspace** with eight routes, one host, one model.
4. **`MainWindow` stays the composition root**; its Qt overrides move out one
   at a time with regression coverage (see R2.c, F22).
5. **Module caching**: inactive widgets cached per account, evicted under a
   measured policy (threshold still open, §7).
6. **Classic shell is the rollback path** behind the `experimental/runtime_shell`
   `PreferenceStore` flag (default off). Retirement decision is open (§7);
   parity evidence is in #516.

Related feature work that rode the re-land: Context Inspector (#539),
telemetry status bar (#540), theme presets + per-category accents (#541),
gallery presentation modes (#542, own D12 pass).

### 2.4 Module and route inventory (classic shell baseline)

`gui/test/modules/test_legacy_module_inventory.py` statically compares this
table to `CLASSIC_TAB_ROUTES` in `gui/src/windows/main/_tab_registry.py`.
A route rename, addition, removal, or coupling change must update this
table deliberately.

Construction baseline (R2.e / #566): `_create_tabs()` registers hub, services,
and the title map, then `_ensure_category()` constructs tabs through
`build_tab()` on first category select. Classic startup builds ≤ 1 category
(the restored last tab, else the startup-category preference, else System
Tools). The eight Image Stitching routes remain views owned by one
`StitchTab` (`stitch.workspace`). Per-module import/activation timings are
logged from `build_tab` / `_classic_construction_log`.

| Module ID | Category | Current title | Live expression | Runtime kind |
|---|---|---|---|---|
| system.convert | System Tools | Convert | self.convert_tab | page |
| system.merge | System Tools | Merge | self.merge_tab | page |
| system.similarity | System Tools | Similarity | self.delete_tab | page |
| system.extractor | System Tools | Extractor | self.extractor_tab | page |
| system.wallpaper | System Tools | Wallpaper | self.wallpaper_tab | page |
| library.listings | Library Database | Listings | self.listings_tab | page |
| library.search | Library Database | Image Search | self.search_tab | page |
| library.scan | Library Database | Scan and Tag | self.scan_metadata_tab | page |
| library.management | Library Database | Management | self.database_tab | page |
| library.data-browser | Library Database | Data Browser | self.data_browser_tab | page |
| web.crawler | Web Integration | Crawler | self.crawler_tab | page |
| web.requests | Web Integration | Requests | self.web_requests_tab | page |
| web.drive-sync | Web Integration | Cloud Synchronization | self.drive_sync_tab | page |
| web.media-loader | Web Integration | Media Loader | self.media_loader_tab | page |
| web.reverse-search | Web Integration | Reverse Search | self.reverse_search_tab | page |
| web.entity-recon | Web Integration | Entity Reconnaissance | self.entity_recon_tab | page |
| ml.training | Deep Learning | Training | self.train_tab | page |
| ml.generation | Deep Learning | Generation | self.generate_tab | page |
| ml.evaluation | Deep Learning | Evaluation | self.eval_tab | page |
| ml.inference | Deep Learning | Inference | self.inference_tab | page |
| ml.comfyui | Deep Learning | ComfyUI | self.comfyui_tab | page |
| stitch.stitch | Image Stitching | Stitch | self.stitch_tab.stitch_panel | route:stitch |
| stitch.graph | Image Stitching | Graph | self.stitch_tab.graph_panel | route:stitch |
| stitch.adjust | Image Stitching | Adjust | self.stitch_tab.adjust_panel | route:stitch |
| stitch.canvas | Image Stitching | Canvas | self.stitch_tab.canvas_panel | route:stitch |
| stitch.statistics | Image Stitching | Statistics | self.stitch_tab.stats_panel | route:stitch |
| stitch.sequence-builder | Image Stitching | Sequence Builder | self.stitch_tab.seq_builder_panel | route:stitch |
| stitch.hybrid | Image Stitching | Hybrid Stitch | self.stitch_tab.hybrid_stitch_panel | route:stitch |
| stitch.animation-clusters | Image Stitching | Animation Clusters | self.stitch_tab.anim_clusters_panel | route:stitch |
| manga.colorization | Manga | Colorization | self.manga_colorization_tab | page |
| manga.animation | Manga | Animation | self.manga_animation_tab | page |
| manga.puppeteering | Manga | Puppeteering | self.manga_puppeteering_tab | page |
| editor.hybrid | Image Editor | Hybrid Editor | self.hie_editor_tab | page |

Coupling baseline (classic path): `SearchTab`, `ScanMetadataTab`, and
`WallpaperTab` also accept `(database_service, event_hub)`; when neither is
supplied they fall back to the direct `database_tab` construction. Both paths
live in the same classes. R1.4 collapses them into one `build_tab()` factory.

### 2.5 App theming (Phase 1 desktop shipped 2026-08-18/19; #437–#441)

Decisions that still bind: base theme + override deltas; JSON token pack and
raw QSS both first-class (expert toggle for raw QSS); hybrid migration of the
`$VAR` QSS system onto generated tokens, file by file; density, corners,
typography, shadows, motion as theme axes; one global background playlist
clock with per-tab static override; palette extraction off by default;
WCAG contrast as warnings; transactional preview with rollback. Phase 2
(docs website tokens) and Phase 3 (devtool app tokens) never started — §5 R4.
The "file by file" QSS migration is exactly what R2.b finishes: the engine
exists, 648 `setStyleSheet` sites and 962 inline hex literals bypass it.

---

## 3. Baseline (main @ `ee91cd01`, 2026-09-06)

| Metric | Value | Target at end of R2 |
|---|---|---|
| Classes with ≥5 bases | 25 (MainWindow 16) | 0 tabs; MainWindow ≤ 4 |
| `hasattr(` in `gui/src` | 365 | < 60, none on sibling widgets |
| `# pyrefly: ignore` | 330 | < 100 |
| silent `except: pass` | 81 | 0 bare; `RuntimeError` guards via one helper |
| `setStyleSheet(` outside theming/styles | 648 | 0 |
| inline `#rrggbb` outside theming/styles/constants | 962 | 0 |
| raw `QThread`/`QRunnable` subclasses | 28 / 24 (1 / 5 on the base) | 0 raw |
| worker signal vocabularies | 10 | 1 |
| files >500 LOC | 23 | 0 new; CI gate (`architecture.md` §5.17A) |
| `QTimer.singleShot` | 45 | ordering cases → state machines (R2.d) |
| live `processEvents()` | 7 | 0 |
| blocking IO in slots | ~30 sites | 0 (R1.6) |
| `LRUImageCache` instances | 7, 4 sizing sites | 1 budget (R3.1) |
| `*_tab_ref` / `main_window_ref` | 60 | 0 (R1.3, R1.4) |
| RSS at login window / main window | 916 MB / 1,094 MB | measured per R3.2, target set from data |

Re-measure with `python tools/dev/gui_audit/gui_audit.py gui/src` and
`python tools/dev/gui_audit/dup_finder.py gui/src 12`.

---

## 4. Decisions taken at lock (Claude, 2026-09-06; user may veto on the bus)

| # | Question (report) | Decision |
|---|---|---|
| Q-A | `protos/` vs `components/` duplication after the re-land | Delete `gui/src/protos/` and `gui/test/protos/`. D11's "expected back later" is satisfied: it is back, in `components/`. History keeps the files. (R0.4) |
| Q-B | who collapses the four clone pairs | Cursor (R2.a), disjoint from crash-class work, can start now |
| Q-C | `BaseQThreadWorker.error` payload | `error` carries the exception object (`Signal(object)`); consumers call `str(exc)`. Only one subclass exists, so no shim needed. (R1.1) |
| Q-D | styling rule strictness | Hard rule, CI-enforced, with an explicit allowlist file that must shrink every PR that touches a listed file (R2.b) |
| Q-E | `features/<name>/` vs `tabs/<name>/` | Keep `tabs/<name>/`; composition = `manager.py` (QWidget) + `controller.py` + `config.py` inside the existing package. No mass import rename. |
| DS-1 | mixin migration order | Risk-first: non-gallery tabs first; gallery-owning tabs only after #543's D12 (Grok §9.1) |
| DS-2 | settings decoupling shape | `WindowService` + `PreferenceStore`; intents only for relaunch / apply-tab-configs (R1.3) |
| DS-3 | `db_tab_ref` rename | One pass, `database_service=`; `db_tab_ref=` accepted with a warn-once `COMPAT` shim, deleted in the same issue once the last caller is ported (R0.8) |
| DS-4 | gallery card/selection merge | R3 (after #543 D12), not bundled with mixin migration (R3.4) |
| DS-5 | module eviction threshold | Measure RSS with 3 vs 8 mounted modules first; dispose-on-account-switch only until then (R3.5) |

---

## 5. The plan

Phases are ordered by dependency, not by calendar. Items inside a phase run
concurrently (D6). "Gate" = D12 live pass required in addition to Codex review.

### R0 — Hotfixes (small, isolated, start now)

| ID | Item | Evidence | Owner | Exit | Issue |
|---|---|---|---|---|---|
| R0.1 | `MonitorDisplaySubTab.__init__` → `super().__init__()` (skips 15 mixin inits today) | F18 | Claude | test asserting every mixin `__init__` on the MRO ran | ui-arch-25 (#547) |
| R0.2 | Settings stop writing `MainWindow.cached_creds`; go through `PreferenceStore` ACCOUNT keys | F19, §5.5 | Codex | **Done, D12-verified 2026-09-08.** | ui-arch-26 (#548) |
| R0.3 | Lazy-import `StitchTab` / `Manga*` / `HieEditorTab` inside `_create_tabs` and catalog factories | F26 | Claude | `import gui.src.tabs` no longer imports `asp_gui`/`csg_gui`/`hie_tab`; boundary check extended | ui-arch-27 (#549) |
| R0.4 | Remove `gui/src/protos/` + `gui/test/protos/` (Q-A) | §5.1 | Claude | dirs gone, nothing imports them | ui-arch-28 (#550) |
| R0.5 | `QFileDialog` safety self-installs on `gui.src` import; raw static calls linted | §5.6 | Claude | `apply_patch()` call sites → 1; lint rule | ui-arch-29 (#551) |
| R0.6 | Silent `except: pass` sweep: bare swallows → `logger.debug(exc_info=True)`; one `deleted_qobject_guard()` helper for `RuntimeError` cases | §5.2, 2.e | Muse | 0 bare `except: pass` in `gui/src` | ui-arch-30 (#552) |
| R0.7 | `StatusSink` protocol on `MainWindow`; `_notify.py` drops `hasattr` | F24 | Muse | missing method logs, never no-ops | ui-arch-31 (#553) |
| R0.8 | `ImagePreviewWindow(db_tab_ref=)` → `database_service=`; warn-once shim, removed in-issue | F5, DS-3 | Gemini | 0 `db_tab_ref` kwargs; shim deleted | ui-arch-32 (#554) |
| R0.9 | `atexit` guard for `base.run_monitor_slideshow` in unbuilt worktrees | F14 | Muse | clean test logs | ui-arch-33 (#555) |

### R1 — Contracts II (shared modules the consolidation needs)

| ID | Item | Evidence | Owner | Exit | Issue |
|---|---|---|---|---|---|
| R1.1 | Worker base adoption: every `QThread`/`QRunnable` in `helpers/` on `BaseQThreadWorker`/`BaseQRunnableWorker`; signals `finished`/`error(object)`/`progress`; one `cancel()`; one shared teardown replacing the 11 `_lifecycle.py` clones; lint rule | §3.3, F3, F9, Q-C | Muse | 0 raw subclasses; 1 signal vocabulary; ⚙ rule live | ui-arch-34 (#556) |
| R1.2 | `TabConfig` contract: `Protocol` + dataclass schema + version for `get_default_config`/`collect`/`set_config`; session recovery, Ctrl+S, Settings consume it | §3.2 | Claude | `hasattr(tab, "collect")` → 0; 33 implementers typed | ui-arch-35 (#557) |
| R1.3 | `WindowService` + settings decoupling: `windows/settings/*` drops `main_window_ref` (44 sites) | F6, F7 | Codex | **Done, D12-verified 2026-09-08.** | ui-arch-36 (#558) |
| R1.4 | One `build_tab(module_id, context)` factory used by both classic `_create_tabs` and the catalog; inventory test keeps passing | F23 | Codex | implementation ready: one constructor path; catalog `TypeError` fallbacks gone; mandatory review pending | ui-arch-37 (#559) |
| R1.5 | Preferences store split: vault = secrets; preferences/tab-configs per-key in `PreferenceStore`; no whole-blob `save_data(json.dumps(creds))` outside auth | §5.5, R0.2 | Codex | 12 vault-write sites → auth only | ui-arch-38 (#560) |
| R1.6 | `DirectoryScanService` worker (cancellable generation token) replacing the ~30 blocking IO sites and the six `_directory_browse.py` copies | §5.3, §3.2 | Muse | 0 `os.listdir`/`scandir`/`rglob`/decode in slots | ui-arch-39 (#561) |
| R1.7 | `PreviewContext` value object + one preview service replacing the `_preview_context.py` / `_properties_preview.py` copies | F4 | Gemini | one preview entry point | ui-arch-40 (#562) |

### R2 — Consolidation

| ID | Item | Evidence | Owner | Gate | Exit | Issue |
|---|---|---|---|---|---|---|
| R2.a | Clone collapse, one PR each: entity/series listings subtabs → one parameterised `ListingsSubTab`; the two directory-import dialogs; codec/format subtabs → one `MediaConvertSubTab` with a format strategy; dropbox/onedrive sync workers; frame/gif/video extractor workers + `run_extraction_in_process` (480 lines) → one pipeline | §3.1 | Cursor (listings, dialogs, codec/format); Muse (workers) | D12 for extractor workers | each pair → one module; dup windows for the pair → 0 | ui-arch-41 (#563) |
| R2.b | Theme tokens + styling lint: `theme.color()`/`theme.qss(component=)` API; migrate `components/` → `elements/` → `windows/` → `tabs/`; CI rule with shrinking allowlist; finishes app-theming's file-by-file QSS migration | §4, 2.5 | Cursor | Breeze/Kvantum live check | metrics row 5–6 → 0 | ui-arch-42 (#564) |
| R2.c | Composition migration, #544 template, one tab per PR, in this order: DataBrowser, DriveSync, EntityRecon, MediaLoader, ImageCrawl, CBIRTrain, Sampler, then (after R2.a) the merged listings and convert subtabs, then (after #543 D12) Search, ScanMetadata, Similarity, Extractor, Wallpaper family; `MainWindow` last, one Qt override per PR (F22). `HostProtocol` conformance test per tab while mixins remain. | §2, F1, F22, DS-1 | Gemini (non-gallery), Grok (gallery-owning + MainWindow) | D12 for gallery-owning tabs and MainWindow | metrics row 1 | ui-arch-23 (#544, continues) |
| R2.d | Explicit lifecycle state machines replacing `singleShot` ordering: session recovery and the extractor player (`NotLoaded → Restored → PlayerReady → Playing`), closing #546's family | §5.4 | Claude | D12 | #546 closed; 0 timer-ordered restore steps | ui-arch-43 (#565) |
| R2.e | Classic shell: lazy tab construction on first category select via the R1.4 factory, or retirement (§7 decision). Measures per-module import/activation cost. | F17 | Grok | D12 | classic startup constructs ≤ 1 category | ui-arch-44 (#566) |
| R2.f | `SectionedFormBuilder` replacing the 17 same-named `_UIBuilderMixin` classes and the 300-line `_build_ui` functions | F20, §1 | Gemini | — | 0 `_UIBuilderMixin`; no `_build_ui` > 80 lines | ui-arch-45 (#567) |
| R2.g | #543 gallery unification onto `ThumbnailScheduler` | D3 | Grok | D12 | **done — merged 2026-09-07, D12-verified** | ui-arch-22 (#543) |

### R3 — Optimization and resource

| ID | Item | Evidence | Owner | Exit | Issue |
|---|---|---|---|---|---|
| R3.1 | One pixmap budget across the 7 `LRUImageCache` instances; sizing in one place | §5.7 | Grok | one `PixmapBudget`; per-tab sizes derived | ui-arch-46 (#568) |
| R3.2 | Startup footprint: heavy imports (`cv2`/`PIL`/`numpy`/`torch`, 27 files) moved into functions; RSS at login/main window measured before/after | §5.8 | Claude | measured delta posted; no module-level heavy import in `gui/src` ⚙ | ui-arch-47 (#569) |
| R3.3 | Remove the 7 live `processEvents()` (single-shot timer or progress fact) | F25 | Gemini / Antigravity | 0 | ui-arch-48 (#570) |
| R3.4 | Gallery card/selection merge: one card factory + one highlight helper across single/two/virtual | F21, DS-4 | Grok | `create_card_widget` ×1 | ui-arch-49 (#571) |
| R3.5 | Module widget eviction: measure 3 vs 8 mounted modules, set LRU from data; account-switch disposal | F12, DS-5 | Grok | numbers on the bus; policy implemented | ui-arch-50 (#572) |
| R3.6 | Import-graph slimming beyond the wildcard removals; `windows/__init__.py` eager imports; `helpers/__init__.py` barrel | old Phase 3 | Gemini / Antigravity | `import gui.src.components.widgets.toast_widget` < 300 modules | ui-arch-51 (#573) |

### R4 — Theming surfaces (deferred, from app-theming Phase 2/3)

| ID | Item | Owner | Issue |
|---|---|---|---|
| R4.1 | Docs website: shared JSON token schema → CSS custom properties | Cursor (after R2.b) | ui-arch-52 (#574) |
| R4.2 | DevTool app: `index.css` → token custom properties | Cursor (after R2.b) | ui-arch-53 (#575) |

---

## 6. Ownership summary

| Agent | Items |
|---|---|
| Claude | ~~R0.1, R0.3, R0.4, R0.5~~ done. R1.2 (#557) consumer half merged (PR #602); per-tab conformance deferred until R2.c composition PRs land. **Remaining: R2.d (#565).** Roadmap steward / reviewer of last resort. |
| Grok | ~~R2.g (#543)~~ done, D12-verified 2026-09-07. ~~R2.e (#566)~~ PR #606, D12-verified 2026-09-11 (real login, real vault/data; startup builds only the restored category, switching category lazily built exactly that category's tabs, session recovery restored real state, clean quit) — merged. **Remaining: R2.c gallery-owning tabs + MainWindow (#544), R3.1 (#568), R3.4 (#571), R3.5 (#572).** |
| Gemini / Antigravity | ~~R0.8, R1.7, R2.c (all 7 non-gallery tabs), R2.f (#567), R3.3 (#570), R3.6 (#573)~~ done, merged. R3.2 (#569) done, PR #608 pending a one-line import-order lint fix before it clears. |
| Meta's Muse | ~~R0.6, R0.9, R0.7 (#553), R1.1 (#556)~~ done. R1.6 (#561) service half done, PR #605 has a BLOCKING review finding (`ScanSession.cancel()` drops a live worker reference — crash risk) that must be fixed before merge. **Remaining: R2.a extractor/sync workers (#563 continuation).** |
| Chat / Codex | ~~R0.2 (#548), R1.3 (#558)~~ done, D12-verified 2026-09-08. ~~R1.4 (#559)~~ recovered from an unpushed local branch and merged via PR #603 (2026-09-11). **Remaining: R1.5 (#560) — orphaned local commits pushed 2026-09-11, still "not ready for review" per Codex's own last note.** Resumed mandatory cross-review 2026-09-11 after a gap since 2026-09-06; cleared #602/#570/#573/#566(code)/#606, found BLOCKING issues on #544/#609 and #561/#605. |
| Cursor | ~~R2.a listings pair (#563)~~ done. #544 Entity/Series listings composition done, PR #609 has a BLOCKING review finding (34 leftover `COMPAT(ui-arch-23)` shims must be removed per the issue's own closure rule). **Remaining: R2.a import-dialog pair + codec/format pair (#563 continuation), R2.b (#564), R4.1 (#574, new), R4.2 (#575, new, after R2.b).** |

Dependencies: R1.1 before R2.a workers; R1.4 before R2.e; R0.2 before R1.5
(both done); R2.a codec/format and listings before their R2.c migration.
**#543 D12 is done (2026-09-07)** — gallery-owning R2.c tabs and R3.4 are no
longer gated on it.

---

## 7. Open decisions (need the user)

- **Classic shell retirement** (from the shell doc §6): one release of fallback,
  permanent preference, or retire once R2.e lands. #516 has the parity evidence.
- **Module eviction threshold**: set from R3.5's measurement, not now.
- **Event schema versioning process** for `gui/src/modules/events.py` Intents/Facts.
- **Account-switch disposal semantics** for cached module state (R3.5 implements once decided).

---

## 8. Document history

- 2026-09-06 — created; folds `ui_architecture_2026q3.md`,
  `ui_module_inventory_2026q3.md`, `app_theming_2026q3.md`, and
  `architecture.md` §5.18/§5.19; locks R0–R4 from the two 2026-09-06 analysis
  reports; issues `ui-arch-25..53` (#547–#575) cut; #543/#544 moved to the milestone; #531/#532 closed as superseded.
- 2026-09-07 — `milestone/gui-refactoring-roadmap` integration branch opened
  (user decision: one branch + PR per milestone, from now on); remaining
  queue delegated to the full team in §6.

## 9. Milestone branch tracking (`milestone/gui-refactoring-roadmap`)

Merge-to-`main` checklist for this branch's own PR — every issue below
must be closed first (§6 has the current owner/queue per agent):

- [x] #543, #544 (partial — Grok's gallery-owning half + MainWindow remain), #547, #548, #549, #550, #551, #552, #554, #555, #558, #562, #563 (partial — listings half only)
- [ ] #544 (remainder), #553, #556, #557, #559, #560, #561, #563 (remainder), #564, #565, #566, #567, #568, #569, #570, #571, #572, #573, #574, #575
