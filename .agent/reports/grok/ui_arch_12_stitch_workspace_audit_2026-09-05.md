# ui-arch-12 / #535 — StitchWorkspace audit (Grok, 2026-09-05)

Read-only. Do not implement until #533 merges. Compared reverted
`dc28226d` (`gui/src/modules/stitch_workspace.py`) to current
`submodules/ASP/gui/src/elements/manager.py` (live `StitchTab`) and
`gui/src/windows/main/_tab_registry.py`. Codex's #538 brief applies.

## What `dc28226d` actually did

One `WorkspaceDescriptor(module_id="stitch")` plus eight `RouteDescriptor`s
(`stitch.stitch` … `stitch.animation-clusters`). Factory lazy-imports
`asp_gui.elements.StitchTab`. `StitchWorkspaceHandle.activate(route_key)`
maps `STITCH_ROUTES` order onto `StitchTab._tab_widget.setCurrentIndex`.
Gate was env `IMAGE_TOOLKIT_STITCH_WORKSPACE=1`. Tests: flag-off leaves
catalog empty; activating all eight routes constructs `StitchTab` once;
`stitch.canvas` → index 3.

## Current tree still matches the route table

Live `StitchTab._init_ui` addTab order is still
Stitch / Graph / Adjust / Canvas / Statistics / Sequence Builder /
Hybrid Stitch / Animation Clusters — same as `STITCH_ROUTES` and the
inventory (`ui_module_inventory_2026q3.md` rows `stitch.*`). Index 3 is
still Canvas. Classic `_tab_registry.py:70` still does `StitchTab()` at
`_create_tabs()` and publishes the eight **panels** as separate
`all_tabs["Image Stitching"]` entries.

`StitchTab.__init__` builds all eight panels, seven `_ThumbHub`s, and
workers/timers. It does **not** start a directory scan or thumbnail fill.
`ThumbLoader` later uses `cv2.imread` (not `ImageLoaderWorker` /
`NATIVE_IMAGE_BATCH_LOCK`).

## Do not cherry-pick

1. **Wrong types.** `dc28226d` imports reverted `catalog` /
   `WorkspaceDescriptor` / `ModuleRuntime`. Phase 1 #527
   `ModuleDescriptor.child_routes` + `ModuleHostWidget.navigate_to()`
   only stacks the parent widget — it never calls `activate(route_key)`.
   Eight routes / one host needs #533's `RouteDescriptor` →
   `handle_for(workspace)` reuse. Fold into that, don't add a third
   descriptor model.
2. **Index coupling.** `activate()` keys on `enumerate(STITCH_ROUTES)`.
   Order matches today; a later `addTab` shuffle would silently select
   the wrong panel. Re-land should look up the named panel (or tab text),
   not a magic index.
3. **Private `_tab_widget`.** Classic shell reparents panels into
   MainWindow tabs. `setCurrentIndex` on an emptied internal tab widget
   would no-op. The workspace widget must be the whole `StitchTab` with
   panels left as its children — do not also run classic reparenting on
   the same instance.
4. **Dual instance.** If `_create_tabs()` still constructs `StitchTab()`
   and the workspace factory constructs another, pipeline state splits.
   Registration is catalog-only until #536 swaps the shell. Default flag
   off.
5. **Env flag vs `PreferenceStore`.** Reverted env var is a second owner
   next to #536's ACCOUNT-scope experimental-shell key. Tests can keep an
   env override; production must not grow a QSettings/env/vault triangle.

## Re-land shape (after #533)

- Recover `stitch_workspace.py` by rewrite against #533's catalog/runtime,
  not `git checkout dc28226d`.
- `register_stitch_workspace(catalog)` must invoke **zero** factories
  (Codex #538). First `activate("stitch.*")` constructs once; the other
  seven routes return that handle. Counting-factory test covering all
  eight inventory routes is the merge bar, plus unknown-route
  `LookupError` and flag-off empty catalog.
- Feature flag: `PreferenceStore` ACCOUNT key (same family as #536),
  default off. Optional env override for tests only.
- Factory runs on the GUI thread (`StitchTab` is a `QWidget`; hubs are
  `QObject`s). No EventHub publish from Stitch in this slice; no
  `topLevelWidgets()`; no startup prefetch.
- Do not "fix" Stitch's `cv2.imread` thumb path here — it is not a
  factory side-effect. Flag only: if a later slice auto-loads frames on
  activate, it must go through Phase 0's decode lock.

## Blocked on #533

Need `WorkspaceDescriptor` / `RouteDescriptor`, `ModuleRuntime.handle_for`
keyed by workspace id, and `handle.activate(route_key)`. Stub counting
factories for the eight `stitch.*` ids in #533's anti-eager test are
enough for Gemini/Muse; this issue supplies the real `StitchTab` factory
after that lands.

— Grok, 2026-09-05
