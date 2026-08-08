# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Flattened the core source tree by moving every package and module from
  `src/cel_shaded_generator/` directly into `src/`. Core callers now import
  the top-level domain packages (`colorization`, `learning`, `project`, and
  peers), while the distribution name remains `cel-shaded-generator`. Updated
  the engine entry point, GUI, Krita engine diagnostics, benchmarks, tests, and
  architecture documentation. The independent Krita plugin identifier remains
  `cel_shaded_generator` for host compatibility.

### Milestone

- **Reference-coloring roadmap milestones 1–3 are complete and live-Krita
  verified.** C3 (issue #17, Character Colors Docker authoring/masks/preview),
  C4 (issue #18, manual region-correspondence assignment/propagation/preview),
  and G1 (issue #19, Line Art Segmentation Docker: gap closing, region
  segmentation, speck filtering, adjacency reporting) each passed their full
  live checklist — actual drawing/segmentation/assignment in Krita, not just
  headless tests. All three issues are closed. Milestone 4 (assisted
  correspondence with confidence and correction learning, issue #24) is now
  In review pending a live Krita checklist: deterministic confidence
  signals, a multiplicative-weights correction-learning step (no ML, per
  explicit scoping), and the Character Colors Docker's confidence-ranked
  material dropdown are all implemented; see the `### Added` entries below.
- **Phase 5 (standalone desktop editor, issue #25) started ahead of its
  documented gate.** That gate ("proceed only when Krita limitations are
  demonstrated by validated workflows") has not been met; the owner made an
  explicit decision to start this phase now anyway. See
  `engine_architecture.md`'s "Gate 5 exception (2026-08-07)" note for the
  full rationale — this is a scope decision, not evidence Krita has proven
  insufficient. The Krita plugin remains the primary, actively-developed
  host. Seventeen slices — canvas + layer-stack foundation, brush paint
  tool (issue #26), undo/redo (issue #27), non-destructive layer masks
  (issue #28), line-art segmentation (issue #29), style-bible palette
  application (issue #30), region-to-material correspondence assignment
  (issue #31), canvas document save/load (issue #32), canvas document
  recovery-revision rotation (issue #33), binding a portable project for
  `SignalWeights` correction learning (issue #34), attaching canvas
  documents into a bound project (issue #35), browsing/reopening
  project-bound assets (issue #36), a soft/anti-aliased brush hardness
  option (issue #37), an eraser tool (issue #38), per-layer
  opacity/blend mode UI (issue #39), propagating correspondence to
  explicit target regions (issue #40), and detaching project
  documents/bibles (issue #49) — are all In review pending a manual
  desktop-app check (see the `### Added` entries below).

### Fixed

- Ran a proactive high-effort code review of `docker.py` (the original tutor
  Docker, A1; largest and oldest Docker file, still backing the
  deferred-In-Review A2/A3 checklists #10/#11/#12) and fixed two related
  bugs it found in `_finalize_fresh_capstone_review`:
  - It called `EngineClient.record_attempt_review`/`decide_attempt_review`
    with no `try`/`except`, unlike every other analogous call site in this
    file (`_request_review`, `_run_next_capstone_review`). A `ValueError`
    from either (e.g. a stale attempt id after project state changed) would
    propagate unhandled out of the Qt slot instead of surfacing a status
    message like the rest of the dock does.
  - The rendered preview layer was never assigned to `self._preview_layer`.
    If the artist cancelled the inline decision or rationale dialog, the
    locked preview layer was left in the document with no supported way to
    accept, reject, or remove it — and since the review had already been
    persisted as pending, re-running the capstone flow would create another
    orphaned preview on each retry.
  Now wraps every risky call in `try`/`except` matching the file's existing
  convention, and assigns `self._preview_layer`/`self._review_id` right
  after rendering so the dock's own Accept/Reject Preview buttons can always
  resolve the preview if either dialog is cancelled. Also extracted the
  light-direction/boundary-hardness confirmation dialogs -- previously
  independently duplicated between the lesson and capstone cel-value review
  flows -- into one shared `_confirm_light_and_hardness` helper (both flows'
  mask-sampling logic differs in real ways and was left untouched).
  Verification: 411 tests pass; Ruff and core mypy are clean. `docker.py`
  has no logic-level unit tests of its own (only the canvasChanged/
  entry-point regression tests cover it structurally), so this fix and
  refactor are unverified beyond that until the still-pending A2/A3 live
  checklists (#10/#11/#12) run.
- **Live-discovered bug (issues #17/#18/#19):** the Character Colors and Line
  Art Segmentation Dockers failed to load in Krita at all —
  `NotImplementedError: DockWidget.canvasChanged() is abstract and must be
  overridden`. Krita's PyKrita binding requires every `DockWidget` subclass
  to override `canvasChanged()`; both new Dockers were missing the same
  no-op override the original tutor Docker already had, so only the tutor
  Docker appeared in Settings → Dockers. Added the missing override to both.
  Also added a headless regression test
  (`test_krita_docker_canvas_changed.py`) that imports every Docker module
  against a minimal stub `krita`/`PyQt5` and asserts each `DockWidget`
  subclass defines `canvasChanged` in its own class body — verified it fails
  without the fix and passes with it, closing the gap that let this ship
  undetected (only the Dockers' pure-Python helper modules had headless
  tests before). Also added an `install.py` refuses-to-overwrite discovery:
  reinstalling after pulling submodule updates requires explicit
  uninstall + install, documented via new `just krita-install` /
  `krita-uninstall` / `krita-reinstall` recipes in the parent Image-Toolkit
  repo. Verification: 391 tests pass; Ruff and core mypy are clean.
- Hardened the regression test above with a second check that imports the
  plugin's `__init__.py` entry point itself — the exact path Krita's plugin
  loader takes — against the same stub, asserting all three Dockers register
  and each registered class overrides `canvasChanged`. This catches
  import-time failures (a bad sibling import, a typo in a registered class
  name) that the per-file check couldn't, since that only exercises
  instantiation-time behavior. Verified it fails on an injected bad import
  and passes once reverted. Verification: 392 tests pass; Ruff and core mypy
  are clean.
- Ran a proactive high-effort code review of both Docker files (they carry no
  logic-level unit tests themselves — only their pure-Python helper modules
  do — so a live Krita test is currently the only way this class of bug
  would otherwise surface). Found and fixed one real inconsistency:
  `_create_masks` created the `Material Masks` group and its layers without
  checking `createNode`/`addChildNode` return values, unlike every sibling
  creation path in the same file (`_create_mask_variant`) and in
  `segmentation_docker.py`. A Krita creation/attach failure would have left
  status reporting "ready" while the group was silently unattached or
  missing layers, with every later lookup via `find_named_node` returning
  `None` and no error surfaced. Now guards and reports failure the same way
  every other creation path does. Verification: 392 tests pass; Ruff and
  core mypy are clean.

### Added

- **Standalone editor first slice (issue #25, In review): canvas + layer
  stack foundation.** New `src/editor/` core package: `LayerStack`/`Layer`/
  `LayerMeta` — pure numpy, no Qt, add/remove/reorder/show-hide layers and
  composite them bottom-to-top with `normal`/`multiply` blend modes (the
  multiply mode matches `canvas_editor.py`'s existing line-art-over-color
  convention: white leaves the layer beneath unchanged, black stays black).
  New GUI pieces in the existing `cel_shaded_generator_gui` (PySide6)
  workspace member: `LayerCanvas` (zoomable via mouse wheel, pannable via
  hand-drag, renders a bound `LayerStack`'s live composite, read-only this
  slice), `LayerListPanel` (the only thing that mutates a `LayerStack` here
  — add/remove/reorder/visibility toggle via a checkable `QListWidget`), and
  `ReferenceColoringTab` wiring both together with a New Canvas action,
  added as the desktop app's 4th tab. No paint tools, masks, segmentation,
  or palette-preview UI yet — later slices build on this same foundation,
  mirroring how every Krita Docker was built on Krita's own layer model.
  Verification: 15 new core `editor` tests, 21 new headless-Qt `gui` tests
  (445 core + 120 gui total); Ruff and mypy clean. Needs a manual desktop
  launch to confirm visually — see issue #25's testing comment.
- **Standalone editor second slice (issue #26, In review): brush paint
  tool.** New `src/editor/brush.py`: `stamp_dot`/`stamp_line` — pure numpy,
  no Qt, a hard-edged circular brush composited with straight-alpha "over"
  onto a layer's HxWx4 uint8 buffer, deliberately not anti-aliased so it
  stays simple and pixel-exact-testable; `stamp_line` steps overlapping
  dots along a segment so a fast drag paints a continuous stroke rather
  than isolated dots. `LayerCanvas` gained an explicit `set_tool("pan" |
  "brush")` switch (rather than overloading left-click, since
  `ScrollHandDrag` already claims left-click-drag for panning),
  `set_active_layer_id`/`set_brush_color`/`set_brush_radius`, and real
  mouse press/move/release painting in Brush mode. `LayerListPanel` now
  emits a `layer_selected` signal (plus a public `select_layer(id)`) so the
  canvas always knows which layer to paint onto, and auto-selects newly
  added layers. `ReferenceColoringTab` adds Pan/Brush radio buttons, a
  `QColorDialog` color-swatch button, and a brush-size spin box. Still no
  masks, segmentation, undo/redo, or palette-preview UI — later slices
  build on this same foundation. Verification: 26 new core `editor` tests
  (11 for the brush math, 15 already counted for the layer stack), 16 new
  headless-Qt `gui` tests (459 core + 136 gui total); Ruff and mypy clean.
  Needs a manual desktop launch to confirm visually — see issue #26's
  testing comment.
- **Standalone editor third slice (issue #27, In review): undo/redo.** New
  `src/editor/history.py`: `EditHistory`, a snapshot-based undo/redo stack
  bound to one `LayerStack` — callers call `record()` immediately before a
  discrete mutation, and `undo()`/`redo()` restore or reapply the full
  prior state, bounded by a `max_depth` (default 50) that evicts the
  oldest entries. Deliberately snapshot-based rather than a command/diff
  log — the simplest deterministic contract that stays fully testable,
  since every canvas here is bounded with no infinite-undo requirement.
  `LayerStack` gained `save_state()`/`load_state()`: a deep, in-place copy
  of every layer's full state (ids, names, visibility, opacity, blend
  mode, pixels) so the `LayerStack` object's identity survives an
  undo/redo — nothing needs to rebind to a new object. `LayerCanvas`
  records one checkpoint per brush stroke (at `mousePressEvent`, not per
  dot, so a whole stroke undoes as one step) via new `set_history`.
  `LayerListPanel` records one before each add/remove/reorder/
  visibility-toggle (also via `set_history`) and gained a public
  `refresh()` to re-sync its list after an external mutation like an undo.
  `ReferenceColoringTab` creates one `EditHistory` per canvas and adds
  Undo/Redo buttons (always enabled; clicking with nothing to undo/redo is
  a harmless no-op). Still no masks, segmentation, or palette-preview UI.
  Verification: 12 new core `editor` tests (2 for `save_state`/
  `load_state`, 10 for `EditHistory`), 10 new headless-Qt `gui` tests
  (470 core + 146 gui total); Ruff and mypy clean. Needs a manual desktop
  launch to confirm visually — see issue #27's testing comment.
- **Standalone editor fourth slice (issue #28, In review): non-destructive
  layer masks.** `Layer.mask` is an optional HxW uint8 grayscale buffer
  (`None` when absent), validated to match the layer's pixel size.
  `LayerStack.add_mask`/`remove_mask` attach/detach a fully-opaque mask;
  `composite()` multiplies each layer's alpha by `mask / 255` before
  blending when present — the standard non-destructive mask convention
  every mainstream raster editor uses. `save_state()`/`load_state()`
  round-trip the mask too, so undo/redo (#27) covers mask edits for free
  with no changes there. `src/editor/brush.py` adds `stamp_mask_dot`/
  `stamp_mask_line` — grayscale variants sharing the RGBA brush's circular
  clipping logic (extracted into `_clip_region`) but overwriting to a
  given intensity directly rather than alpha-blending, since blending a
  mask against itself has no useful meaning. `LayerCanvas.set_mask_mode
  (True)` redirects Brush strokes to the active layer's mask, and is a
  no-op on a maskless layer rather than silently falling back to painting
  color. `LayerListPanel` gained Add Mask/Remove Mask buttons and a
  `(mask)` list-item suffix; `ReferenceColoringTab` gained an Edit Mask
  checkbox and a Mask value spin box. Still no segmentation UI; masks here
  are a general raster-editor primitive, not yet tied to the Krita-side
  semantic "material mask" concept. Verification: 12 new core `editor`
  tests, 10 new headless-Qt `gui` tests (486 core + 158 gui total); Ruff
  and mypy clean. Needs a manual desktop launch to confirm visually — see
  issue #28's testing comment.
- **Standalone editor fifth slice (issue #29, In review): line-art
  segmentation.** New `src/editor/segmentation_tools.py` reuses
  `colorization.segmentation` (roadmap milestone 1, issue #19) directly
  rather than reimplementing it — the standalone GUI package already
  depends on numpy, unlike the Krita plugin's `segmentation_masks.py`,
  which has to mirror the same algorithm in pure Python for Krita's "no
  numpy" boundary constraint. `close_line_gaps_in_layer` bridges small
  gaps in a layer's painted ink (its alpha channel) in place.
  `segment_layer_into_regions` segments a layer's painted ink into
  enclosed background regions, each becoming a new, distinctly colored
  layer stacked directly above the source; never mutates the source
  layer, and regions leaking to the canvas border are correctly excluded.
  `region_adjacency_for_regions` computes adjacency pairs from region
  layers' current alpha masks (not a re-derivation from the original line
  art), a building block for a possible later slice connecting the
  standalone editor to something like milestone 4's confidence-ranked
  correspondence workflow — not yet wired into any button.
  `ReferenceColoringTab` adds Close Line Gaps (Max gap spin box) and
  Segment Regions (Min region area spin box) buttons operating on the
  selected layer. Still no palette-preview or correspondence-assignment
  UI. Verification: 11 new core `editor` tests, 4 new headless-Qt `gui`
  tests (497 core + 162 gui total); Ruff and mypy clean. Needs a manual
  desktop launch to confirm visually — see issue #29's testing comment.
- **Standalone editor sixth slice (issue #30, In review): style-bible
  palette application.** New `src/editor/palette_tools.py` reuses
  `colorization.style_bible` (roadmap milestone 2, issue #15) directly,
  the same way #29 reused `colorization.segmentation`. `resolve_palette_color`
  parses a material palette's `#RRGGBB` role into an RGB int tuple, raising
  for an unsupported role or an absent accent — matching the Krita
  Character Colors Docker's existing "absent accents are not offered as
  preview roles" rule rather than silently substituting another role.
  `apply_palette_color_to_region` recolors a layer's currently-opaque
  pixels to that color in place, leaving its alpha/shape untouched — the
  same "shape from segmentation/painting, color from the bible" split the
  Krita Docker's material masks use. `ReferenceColoringTab` adds Bind
  Style Bible (file dialog), a Material combo box, a Role combo box
  (dynamically excludes "accent" when absent), and an Apply Palette Color
  button operating on the selected layer — works on any layer, not only
  region layers from #29; there is no forced connection between the two
  slices yet. Still no correspondence-assignment (a persisted,
  propagatable region-to-material binding) or adjacency-suggested
  defaults; this is a direct "pick a material+role, click apply" action,
  not milestone 4's ranked-suggestion workflow. Verification: 7 new core
  `editor` tests, 6 new headless-Qt `gui` tests (504 core + 168 gui
  total); Ruff and mypy clean. Needs a manual desktop launch to confirm
  visually — see issue #30's testing comment.
- **Standalone editor seventh slice (issue #31, In review):
  region-to-material correspondence assignment.** New
  `src/editor/correspondence_tools.py` reuses `colorization.correspondence`
  and `colorization.confidence` directly, the same way #29/#30 reused
  `colorization.segmentation`/`colorization.style_bible`, connecting the
  fifth slice's region adjacency to the sixth slice's palette application
  the way both slices' notes anticipated. `adjacency_agreement_by_material`
  mirrors the Krita Character Colors Docker's
  `_adjacency_agreement_by_material` (milestone 4, issue #24): the
  fraction of a region's adjacent regions already assigned to each
  material. `rank_material_candidates` combines that with
  `colorization.confidence.name_similarity` via `score_candidate`,
  matching `project.service.rank_correspondence_materials`'s signal
  combination, but always starts from the same fixed 0.5/0.5 weights
  `SignalWeights` itself starts from — the standalone editor has no
  project binding yet, so there is no correction-learning step this
  slice. `assign_region_correspondence` returns a copy of a
  `CorrespondenceSet` with one new region assignment, raising on a
  conflicting existing assignment — the same rule
  `CorrespondenceSet.propagate` enforces. `ReferenceColoringTab` adds a
  Suggest Material button (ranks candidates for the selected region layer
  and pre-selects the top one in the existing Material combo, never
  assigns) and an Assign Correspondence button (records the current
  Material/Role as that region's correspondence in an in-memory
  `CorrespondenceSet` tracked by the tab). Assignment stays in-memory for
  the editing session only — no project persistence for the standalone
  editor yet. Applying the suggested material's palette color remains a
  separate explicit action (Apply Palette Color, #30) rather than
  automatic. Verification: 7 new core `editor` tests, 5 new headless-Qt
  `gui` tests (511 core + 173 gui total); Ruff and mypy clean. Needs a
  manual desktop launch to confirm visually — see issue #31's testing
  comment.
- **Standalone editor eighth slice (issue #32, In review): canvas
  document save/load.** Every prior slice was in-memory only — closing
  the app discarded all work. New `src/editor/document_io.py` adds
  `save_document`/`load_document`: one `.npy` file per layer's pixel
  buffer (and mask, when present) plus a `manifest.json` describing layer
  order, identity, and flags. Deliberately `.npy` rather than PNG —
  `src/editor/` has a strict "pure numpy, no Qt" boundary with no
  image-codec dependency, and adding one (Pillow/Qt) just to persist
  arrays this module already owns as numpy would be new surface for no
  real benefit. `ReferenceColoringTab` gains Save Document/Open Document
  buttons (directory picker). Save Document also writes the tab's
  in-memory `CorrespondenceSet` via the already-existing
  `colorization.correspondence.save_correspondence_set` and its
  region-layer-id bookkeeping (`region_layers.json`) alongside the
  canvas, so the seventh slice's correspondence assignments and the
  fifth slice's region tracking survive a save/reload round trip. Open
  Document resets undo/redo history to the freshly loaded canvas; the
  bound style bible, if any, is left as-is. Not in scope: autosave,
  recovery revisions for the canvas document itself, or integration with
  `src/project`'s learning-progress project model — the standalone
  editor still has no `SignalWeights`/project binding, so correction
  learning (#24/#31) remains unavailable here. Verification: 5 new core
  `editor` tests, 7 new headless-Qt `gui` tests (516 core + 178 gui
  total); Ruff and mypy clean. Needs a manual desktop launch to confirm
  visually — see issue #32's testing comment.
- **Standalone editor ninth slice (issue #33, In review): canvas
  document recovery-revision rotation.** The eighth slice gave the
  canvas document no protection against an accidental overwrite — Save
  Document into an existing folder silently discarded the previous
  state, unlike `colorization.correspondence`/`colorization.style_bible`'s
  own bounded `_rotate_recovery` contract on their JSON assets.
  `document_io.save_document` gained a `recovery_revisions` keyword
  (default 10, validated to `1..100` matching `CorrespondenceSet`/
  `CharacterStyleBible`'s own bound): whenever a document already exists
  at the target directory, its prior on-disk state — the whole
  directory, manifest plus every layer's `.npy` files, since a document
  is multiple files rather than the single JSON file `_rotate_recovery`
  handles elsewhere — rotates into `<directory>/.recovery/1..
  recovery_revisions` before the new save overwrites it; the oldest
  revision is evicted past the bound. A first save into an empty
  directory creates no `.recovery/`. No restore API, matching the
  existing scope of `colorization.correspondence`/
  `colorization.style_bible`'s own rotation — each `.recovery/<n>/` is
  itself a valid document directory `load_document` can read directly.
  No `ReferenceColoringTab` changes were needed — Save Document already
  calls `save_document` with the new default. Verification: 4 new core
  `editor` tests (520 core + 178 gui total); Ruff and mypy clean. Needs a
  manual desktop launch to confirm visually — see issue #33's testing
  comment.
- **Standalone editor tenth slice (issue #34, In review): bind a
  portable project for `SignalWeights` correction learning.**
  Owner-directed follow-up to the seventh/eighth/ninth slices: bind the
  standalone editor's correspondence assignment into a portable
  `project` (`src/project`, the same package the Krita tutor's lesson
  flow uses) so it benefits from `SignalWeights` correction learning,
  the same way the Krita Character Colors Docker's milestone-4 workflow
  (#24) does. New `project.create_project(directory, *, title)` in
  `src/project/service.py`: a bare project manifest with no
  exercise/attempt — `create_exercise_project` is the Krita tutor's own
  entry point and always seeds a lesson attempt, but hosts that only
  need to bind style bibles/correspondence sets (the standalone editor)
  have no attempt to seed, and `Project.progress`/`document_asset` were
  already optional in the schema, so this is the same manifest shape
  without the tutor-specific defaults. `ReferenceColoringTab` gains New
  Project/Bind Project buttons. Once a project is bound: Bind Style
  Bible also attaches the bible into the project
  (`upsert_project_style_bible`); Suggest Material ranks via
  `project.rank_correspondence_materials` (the project's learned
  `SignalWeights`) instead of the fixed 0.5/0.5 local weights; Assign
  Correspondence persists the updated correspondence set into the
  project (`upsert_project_correspondence_set`) and reports the choice
  to `record_correspondence_choice` so `SignalWeights` learn from it.
  Without a bound project, everything behaves exactly as before —
  purely additive. Not in scope: binding the canvas document itself
  (the `.npy`-per-layer format from #32/#33) into the project's asset
  model. Verification: 4 new core `project` tests, 6 new headless-Qt
  `gui` tests (524 core + 184 gui total); Ruff and mypy clean. Needs a
  manual desktop launch to confirm visually — see issue #34's testing
  comment.
- **Standalone editor eleventh slice (issue #35, In review): attach
  canvas documents into a bound project.** Follow-up to the tenth slice:
  the canvas pixel document itself was explicitly left out of the
  project's asset model there. `src/project/model.py` bumps
  `CURRENT_SCHEMA_VERSION` to 14, adds `Project.editor_document_assets:
  list[str]` with the same uniqueness/safe-relative-path validation
  `style_bible_assets`/`correspondence_set_assets` already get, and a
  migration default (`[]`) for older manifests. `src/project/service.py`
  adds `attach_editor_document`/`detach_editor_document`: unlike
  `attach_style_bible`/`attach_correspondence_set`, the asset is a
  directory (`editor.document_io.save_document`'s `manifest.json` +
  per-layer `.npy` files), not a single `colorization`-loadable file —
  this package stays decoupled from `editor`'s exact on-disk format, the
  same way an exercise attempt's opaque `document_asset` `.kra` path is
  never opened by this package either, so only directory existence and
  path safety are validated here. `ReferenceColoringTab`'s Save Document
  now attaches the saved directory as a project asset whenever it's
  saved inside a bound project's own directory; saving elsewhere still
  works exactly as before, just untracked by the project manifest.
  Verification: 4 new core `project` tests, 3 new headless-Qt `gui`
  tests (526 core + 187 gui total); Ruff and mypy clean. Needs a manual
  desktop launch to confirm visually — see issue #35's testing comment.
- **Standalone editor twelfth slice (issue #36, In review): browse and
  reopen project-bound assets.** UX follow-up to the tenth/eleventh
  slices: once a project is bound, its already-attached canvas
  documents and style bibles had no way to be reopened/reloaded except
  by re-navigating a raw file dialog to the exact subpath each time —
  the same convenience gap the Krita Character Colors Docker's own
  bible dropdown (`_refresh_bibles`) already solves for its lesson-flow
  projects. `ReferenceColoringTab` gains two combo boxes, Project
  Documents and Project Bibles, populated from the bound project's
  `editor_document_assets`/`style_bible_assets` (`project.load_project`)
  whenever a project is created/bound, or a new document/bible gets
  attached. Two new buttons: Open Selected Document reopens the
  selected Project Documents entry via the same path the file-dialog
  Open Document flow uses (extracted into a shared
  `_load_document_from_path` helper), no dialog needed; Load Selected
  Bible loads the selected Project Bibles entry via the same path the
  file-dialog Bind Style Bible flow uses (extracted into a shared
  `_apply_loaded_style_bible` helper), no dialog needed, and sets
  `_bible_asset_path` directly since it's already a project-relative
  asset path. Pure refactor-and-extend of existing behavior — the
  file-dialog-driven Open Document/Bind Style Bible flows are unchanged
  and still work with no project bound. Verification: 5 new headless-Qt
  `gui` tests (526 core + 192 gui total); Ruff and mypy clean. Needs a
  manual desktop launch to confirm visually — see issue #36's testing
  comment.
- **Standalone editor thirteenth slice (issue #37, In review):
  soft/anti-aliased brush hardness.** Fulfills the note left in the
  second slice's own docstring since it landed: "a softer brush is a
  later slice on the same `stamp_*` contract." `src/editor/brush.py`
  adds `_circular_falloff(radius, hardness)` — per-pixel coverage in
  `[0, 1]`: fully opaque within `hardness * radius` of the center, then
  linearly fading to transparent at `radius`; `hardness=1.0` is
  pixel-identical to the existing hard `_circular_mask`. `_clip_region`
  is generalized to take a brush coverage array directly (bool or
  float) instead of always computing the hard circular mask internally,
  so hard and soft stamping share one clipping implementation.
  `_blend_color_over_weighted` is the soft-brush counterpart of
  `_blend_color_over`, scaling the stamped color's alpha per-pixel by
  the coverage array before straight-alpha "over" blending. New
  `stamp_dot_soft`/`stamp_line_soft` mirror the existing hard
  `stamp_dot`/`stamp_line` signatures plus a `hardness: float`
  parameter. Mask painting is unchanged and has no soft variant —
  alpha-blending a mask against itself has no useful meaning.
  `LayerCanvas` gains `set_brush_hardness`/`brush_hardness` (default
  `1.0`, unchanged prior behavior) and dispatches to the soft stamping
  functions only when hardness `< 1.0`, keeping the hard-brush path
  byte-identical to before for the default case. `ReferenceColoringTab`
  adds a Hardness spin box (`0.0`–`1.0`, step `0.05`) next to the
  existing brush Size control. Verification: 8 new core `editor` tests,
  6 new headless-Qt `gui` tests (533 core + 197 gui total); Ruff and
  mypy clean. Needs a manual desktop launch to confirm visually — see
  issue #37's testing comment.
- **Standalone editor fourteenth slice (issue #38, In review): eraser
  tool.** A natural raster-editor primitive still missing after the
  brush (second slice) and its soft/hardness variant (thirteenth
  slice). `src/editor/brush.py` adds `_erase_alpha(region, weight)` —
  reduces `region`'s alpha channel in place by a `[0, 1]` coverage
  array (`new_alpha = alpha * (1 - weight)`); RGB is left untouched.
  This needs its own compositing rather than reusing `stamp_*` with a
  transparent color, since an "over" blend with a fully transparent top
  color is a no-op, not an erase. New `erase_dot`/`erase_line` share
  the same circular/falloff coverage (`_circular_mask`/
  `_circular_falloff`) as the existing hard/soft brush, with a
  `hardness` parameter mirroring `stamp_dot_soft`/`stamp_line_soft`.
  Mask painting is unaffected and has no eraser variant — painting a
  mask to 0 already *is* erasing it. `LayerCanvas` accepts `"eraser"`
  as a third explicit tool (alongside `"pan"`/`"brush"`), sharing the
  Brush tool's `NoDrag` mouse handling and the existing brush
  radius/hardness controls, but calling `erase_dot`/`erase_line`
  instead of the color-stamping functions. Mask mode ignores the
  Eraser tool selection and keeps its own direct-overwrite mask
  painting either way. `ReferenceColoringTab` adds an Eraser radio
  button next to the existing Pan/Brush ones. Verification: 8 new core
  `editor` tests, 7 new headless-Qt `gui` tests (541 core + 204 gui
  total); Ruff and mypy clean. Needs a manual desktop launch to confirm
  visually — see issue #38's testing comment.
- **Standalone editor fifteenth slice (issue #39, In review): per-layer
  opacity and blend mode UI.** `LayerMeta.opacity`/`blend_mode` have
  been part of `LayerStack.composite()` since the very first slice
  (issue #25), but there was never any UI to set either — every layer
  was stuck at opacity 1.0 and blend mode "normal". `LayerListPanel`
  gains an Opacity spin box (`0.0`–`1.0`, step `0.05`) and a Blend Mode
  combo (populated from `editor.VALID_BLEND_MODES`, newly exported from
  `editor/__init__.py`), shown below the existing mask buttons. Both
  reflect the *selected* layer's current values — updated on every
  selection change, on `set_layer_stack`, and on `refresh()` (so
  undo/redo stays in sync) — and are disabled when nothing is selected.
  Changing either edits the selected layer's `LayerMeta` in place,
  records an undo checkpoint first (reusing `LayerStack.save_state()`/
  `load_state()`, which already round-trip opacity/blend mode, so
  undo/redo needed no changes), and emits the existing `layers_changed`
  signal so the bound canvas re-renders. Verification: 6 new headless-Qt
  `gui` tests (541 core + 210 gui total); Ruff and mypy clean. Needs a
  manual desktop launch to confirm visually — see issue #39's testing
  comment.
- **Standalone editor sixteenth slice (issue #40, In review):
  propagate correspondence to explicit target regions.** Closes a gap
  the seventh/tenth slices left open: the Krita Character Colors
  Docker's Propagate Correspondence action (milestone C4.1, issue #21)
  was never brought over to the standalone editor, even though the
  underlying `colorization.correspondence.CorrespondenceSet.propagate`
  it uses was already available. `src/editor/correspondence_tools.py`
  extracts `adjacent_region_ids(region_id, adjacency_pairs)` out of
  `adjacency_agreement_by_material` (same logic, now reusable) and
  exports it. `ReferenceColoringTab` adds a Propagate Correspondence
  button: takes the selected region layer's existing correspondence
  entry as the source, suggests (pre-fills, never auto-applies)
  adjacent regions as targets via `adjacent_region_ids`, prompts for an
  explicit comma-separated target list the artist can edit, and calls
  `CorrespondenceSet.propagate` directly — mirroring the Krita docker's
  own flow exactly, including its conflict handling. Persists to the
  bound project (if any) the same way Assign Correspondence does.
  Never recolors anything itself. Verification: 2 new core `editor`
  tests, 8 new headless-Qt `gui` tests (543 core + 217 gui total);
  Ruff and mypy clean. Needs a manual desktop launch to confirm
  visually — see issue #40's testing comment.
- **Standalone editor seventeenth slice (issue #49, In review): detach
  project documents/bibles.** Closes a gap the eleventh/twelfth slices
  left open: `project.attach_editor_document`/`upsert_project_style_bible`
  wired the attach side of Project Documents/Project Bibles, and
  `project.detach_editor_document`/`detach_style_bible` already existed
  in `src/project/service.py`, but nothing in the standalone editor
  ever called them. `ReferenceColoringTab` adds Detach Selected
  Document/Detach Selected Bible buttons next to the existing Project
  Documents/Project Bibles combos. Both remove only the manifest
  binding — the underlying document directory or bible file is never
  deleted, matching those functions' own "detach never deletes"
  contract. Detaching the currently-loaded bible also clears
  `_bible_asset_path`, so a subsequent Suggest Material falls back to
  the fixed-weight local ranking (seventh slice's behavior) instead of
  looking up a `SignalWeights` entry for a bible the project no longer
  tracks. Verification: 4 new headless-Qt `gui` tests (543 core + 221
  gui total); Ruff and mypy clean. Needs a manual desktop launch to
  confirm visually — see issue #49's testing comment.
- **Milestone 4 first slice (issue #24): deterministic confidence scoring
  and correction learning for assisted correspondence.** Portable contract
  only, no Docker UI yet, following the same sequencing every prior
  milestone used. `colorization/confidence.py` adds `name_similarity`
  (Jaccard token similarity between a region id and a material's
  id/aliases) and `score_candidate` (weighted-sum confidence combining that
  with C4.1's existing adjacency-agreement signal) — deterministic and
  stateless, no ML. `project/model.py`'s new `SignalWeights` (schema v13;
  v12 payloads migrate to an even 50/50 split) holds the two signal
  weights plus an `update_count`, project-scoped rather than portable.
  `project/service.py` adds `rank_correspondence_materials` (ranks a bound
  style bible's materials for one region using the project's current
  weights) and `record_correspondence_choice` (an online
  multiplicative-weights update: whichever signal's own top pick matched
  the artist's actual choice gets boosted, the other decays, weights
  renormalize; a no-op with fewer than two real candidates or an
  out-of-band chosen id). Neither function ever assigns anything.
  `learning/engine_protocol.py` and the Krita `engine_client.py` wire both
  operations through the existing JSON-RPC transport. Per explicit scoping,
  any future learned signal added to this framework must be fully
  offline/local and go through the existing local model registry.
  Verification: 430 tests pass; Ruff and mypy are clean.
- **Milestone 4 Docker integration (issue #24, In review): confidence-ranked
  material dropdown and correction learning in Character Colors.** New
  `_adjacency_agreement_by_material` generalizes C4.1's unanimous-or-nothing
  `_suggested_material_index` into a per-material `[0, 1]` agreement
  fraction (how many of a region's adjacent regions are already assigned to
  each candidate material, out of all adjacent regions). `_assign_correspondence`
  now calls the engine's `rank_correspondence_materials` with that plus the
  target region id to order the whole "Canonical material" dropdown by
  confidence, not just its default selection; on any engine failure it falls
  back to the bible's declared material order with the old unanimous-adjacency
  default index, so assignment never blocks on a ranking hiccup. After a
  successful save, it calls `record_correspondence_choice` with the exact
  ranked candidates the artist chose from, so `SignalWeights` learns from
  every explicit assignment — a learning-update failure is swallowed since
  the assignment itself already succeeded. Never auto-assigns anything; the
  dropdown stays fully editable. Verification: 448 tests pass (11 new,
  covering the adjacency-agreement fraction: unanimous, split, and
  no-adjacency cases); Ruff and mypy are clean. Needs a live Krita checklist
  to confirm the ranked dropdown and learning loop behave as intended with
  a real project — see issue #24's testing comment.
- Ran a proactive high-effort code review dedicated to `segmentation_docker.py`
  (previously only reviewed jointly with `color_docker.py`) and fixed two of
  its three findings:
  - **Deduplication**: `_report_adjacency` (Line Art Segmentation) and
    `_adjacent_region_names` (Character Colors) independently scanned a
    document's `Regions` group into the same `labels`/`names` structure,
    risking silent divergence if one copy were patched and not the other.
    Extracted into a shared `region_labels_and_names` in
    `segmentation_masks.py`; both Dockers now call it. Standardized on the
    more lenient of the two prior behaviors for a malformed region-layer
    buffer (skip that region, keep reporting the rest, rather than aborting
    the whole scan).
  - **Algorithmic complexity**: `_segment_regions` rescanned the entire
    label array once per surviving region to build each region layer's
    pixel buffer (O(width × height × region count)). Now buckets every
    pixel into its region's buffer in one pass (O(width × height + region
    count)).
  - **Not fixed, flagged instead**: the review also confirmed that
    `close_line_gaps_bytes`/`segment_regions_bytes`/`region_adjacency_bytes`
    run synchronously on Krita's UI thread inside button-click handlers --
    freezing the Krita event loop for the duration with no progress
    indicator or cancellation, standard PyQt guidance against, and also the
    explicit "all heavy computations must run off the main thread
    (QThread/QRunnable)" rule the parent Image-Toolkit monorepo states for
    its own GUI code (this submodule keeps its own, separate AGENTS.md and
    is not bound by that repo's rules, but the underlying UX problem is real
    regardless of which document states it). This is not a regression from
    this session's work -- every Docker action across all four Dockers that
    calls `EngineClient()` synchronously (dozens of call sites since A1) has
    the identical property, since none of this plugin's Docker code has ever
    used QThread/QRunnable. Fixing `segmentation_docker.py` alone would
    leave the plugin in a worse, inconsistent state (one Docker threaded,
    the rest not) for a cost this session's scope did not budget. This
    needs an owner decision on a plugin-wide async architecture, not a
    scoped patch.
  Verification: 411 tests pass; Ruff and core mypy are clean.
- Advanced milestone-6 issue #22 with a new **Chapter Queue** Docker (same
  one-concern-per-Docker pattern as Character Colors and Line Art
  Segmentation): **Bind Portable Project**, **Add Page to Chapter**,
  **Open Next Pending Page** (`Krita.openDocument`/`window.addView`, marks
  the page in-progress), **Mark Active Page Reviewed/Accepted** (matches the
  active document's file path back to its chapter-page record), and
  **Refresh Queue**. A proactive code review before shipping found and
  fixed a real cross-platform bug: path-relativization used
  `str(Path(...).relative_to(...))`, which yields backslash-separated paths
  on Windows that the engine's POSIX-only asset validation always rejects
  and that can never match the POSIX-stored `document_asset`; fixed to use
  `.as_posix()`. Verification: 411 tests pass; Ruff and core mypy are
  clean. Milestone 6 moves to **In review** pending the live-Krita
  checklist.
- Opened milestone-6 issue #22: a portable, execution-agnostic batch
  chapter-workflow schema. Project schema v12 adds `ChapterPage`
  (id, safe relative document asset, the existing `RegionCorrespondence`
  `panel_id` field so every page's correspondences share one
  `CorrespondenceSet` without colliding across pages, a `PageStatus` of
  pending/in_progress/reviewed/accepted, optional notes) with unique-id/
  unique-asset/unique-panel-id validation. `add_chapter_page` validates the
  document asset exists; `set_chapter_page_status` is explicit and
  idempotent; `next_pending_chapter_page` returns the first not-yet-accepted
  page in queue order. No cross-page correspondence inference and no fixed
  status state machine, per explicit scoping decisions. Privacy-safe
  `project_progress_snapshot` includes a `chapter` section. Wired through
  the engine protocol and Krita `EngineClient`; no Docker/UI surface exists
  yet (Krita queue navigation and an offline batch-tool execution path are
  separate future slices), so no live check applies to this slice.
  Verification: 408 tests pass; Ruff and core mypy are clean.

- Ran a proactive high-effort code review of C4.1's changes to
  `color_docker.py` and fixed one real issue it found: `_assign_correspondence`
  loaded the correspondence set before three sequential modal dialogs
  (material, role, panel id) instead of immediately before the append+save,
  widening the window in which a concurrent write to the same
  `correspondence/<bible-id>.json` could be silently discarded by the
  eventual unconditional overwrite. Now re-reads fresh immediately before
  mutating and saving, same timing as before C4.1's material-default
  suggestion was added. The review's second finding (the adjacency scan's
  pure-Python per-pixel cost, previously paid only by the less-frequent
  Propagate action, now also runs on every Assign click) is documented in
  `_adjacent_region_names`'s docstring rather than fixed with a session
  cache — a cache's staleness tradeoff (a repainted region's alpha changing
  without its layer being renamed) needs a product decision, not a rushed
  fix. Verification: 400 tests pass; Ruff and core mypy are clean.
- Opened C4.1 issue #21: **Propagate Correspondence to Regions** now suggests
  (never auto-applies) target region ids by reading G1's `Regions` group the
  same way Report Region Adjacency does, pre-filling the target field with
  the names of regions touching the source assignment's region. Falls back
  to an empty, fully-manual default when no `Regions` group exists, so this
  is additive over C4's existing typed-target flow, not a new dependency on
  G1. Both underlying features (G1 segmentation/adjacency, C4 correspondence/
  propagation) are independently live-verified, so this connects two
  already-proven pieces rather than building on unvalidated ground.
  `CharacterColorsDocker._adjacent_region_names` is headlessly tested against
  a fake Krita node/document. Verification: 396 tests pass; Ruff and core
  mypy are clean. In review pending the live-Krita checklist.
- Advanced C4.1 issue #21: **Assign Region Correspondence**'s material
  dropdown now defaults to the material of an adjacent region, but only when
  adjacent regions unanimously agree on exactly one material —
  disagreement, no adjacency, or a suggested material no longer in the bible
  all fall back to the prior default (first material in the dropdown).
  `_suggested_material_index` is headlessly tested for all of those cases.
  Verification: 400 tests pass; Ruff and core mypy are clean. Still In
  review pending the live-Krita checklist.
- Opened A4-prep issue #20: a versioned consented study-session schema for
  roadmap A4 (issue #14), which itself remains **Backlog** until live checks
  are intentionally scheduled — this is data-model infrastructure only, not
  the start of the alpha study. Project schema v11 adds `StudyConsent`
  (explicit, revocable, project-local opt-in; opted-in requires a consent
  timestamp, withdrawn consent must not retain one) and `StudySession`
  (baseline attempt id, optional remedial exercise id, optional redraw
  attempt id, optional explanation-usefulness rating reusing the existing
  `AdviceRating` enum, optional completion timestamp — no global artist
  score). `configure_study_consent` mirrors `configure_progress_retention`'s
  explicit-clear-on-withdrawal rule; `record_study_session` accumulates one
  session per baseline attempt as the protocol progresses and validates
  attempt ids against the project. Privacy-safe progress snapshots include a
  `study` section. Wired through the engine protocol and Krita
  `EngineClient`; no Docker/UI surface exists yet, so no live check applies
  and #20 is **Done**. Verification: 388 tests pass; Ruff and core mypy are
  clean.
- Advanced G1 issue #19 with dust-speck filtering: `filter_small_regions`
  clears labeled regions below an artist-chosen minimum area, implemented
  identically in both the numpy engine module and the pure-Python Krita
  adapter. The Line Art Segmentation Docker's **Segment Regions into
  Layers** action now prompts for a minimum area, applies the filter before
  creating layers, and reports how many specks were discarded. Verification:
  379 tests pass; Ruff and core mypy are clean. G1 remains **In review**;
  no deployment occurred.
- Completed G1 issue #19's Docker slice with a new, separate Line Art
  Segmentation Docker. A pure-Python, numpy-free `segmentation_masks.py`
  adapter mirrors `colorization/segmentation.py`'s algorithm on flat Krita
  layer byte buffers in-process (the engine's small JSON-RPC transport is
  unsuited to full-resolution pixel payloads, matching the existing
  `color_masks.py`/`value_masks.py` precedent). **Close Line Art Gaps**,
  **Segment Regions into Layers**, and **Report Region Adjacency** create
  inspectable, renamable layers directly; renamed region layers become the
  region ids C4's Assign Region Correspondence action reads. Verification:
  373 tests pass; Ruff and core mypy are clean. G1 moves to **In review**
  pending the live-Krita checklist; no deployment occurred.
- Opened G1 issue #19 for reference-coloring roadmap milestone 1
  (segmentation and gap-repair tools), previously untouched. Started the
  deterministic baseline in `src/colorization/segmentation.py`:
  `close_line_gaps` (bounded morphological gap closing on line art),
  `segment_regions` (single-radius trapped-ball-style flood fill into
  labeled regions, excluding border-touching non-enclosed background),
  `region_adjacency` (touching-label pairs), and `region_statistics`
  (area/centroid/bounding box per region). Verification: 364 tests pass;
  Ruff and core mypy are clean. Krita Docker wiring is a follow-up slice.
- Completed C4 issue #18's headless slice with a Character Colors Docker
  action set: **Assign Region Correspondence**, **Propagate Correspondence to
  Regions**, and **Preview Region Correspondence Color**. A new host-neutral
  `region_id_from_layer_name` helper normalizes arbitrary layer names into
  kebab-case region ids. Assignment reuses `upsert_project_correspondence_set`
  and refuses competing assignments via the existing model validation;
  propagation targets are explicit and never auto-discovered; preview reuses
  a refactored `_create_preview_layer` helper shared with C3's palette-role
  preview, so accept/reject/single-owned-preview behavior is identical.
  Verification: 355 tests pass; Ruff and core mypy are clean. C4 moves to
  **In review** pending the live-Krita checklist; no deployment occurred.
- Advanced C4 issue #18 with project schema-v10 correspondence-set bindings.
  `attach_correspondence_set`/`detach_correspondence_set`/
  `upsert_project_correspondence_set`/`project_correspondence_set_payload`
  mirror the C2 style-bible operations exactly (safe relative paths, no
  deletion on detach). A new `propagate_project_correspondence` service call
  loads the bound set, applies `CorrespondenceSet.propagate` onto explicit
  artist-selected targets, and saves the result with bounded recovery.
  Privacy-safe project-progress summaries now include correspondence-set
  identity and counts. The engine protocol and Krita `EngineClient` expose
  all five operations end to end. Verification: 353 tests pass; Ruff and core
  mypy are clean. The Docker action, manual region-assignment UI, and the
  live-Krita checklist remain before Review.
- Started C4 issue #18 with a standalone `CorrespondenceSet`/`RegionCorrespondence`
  contract (`src/colorization/correspondence.py`). Region/material/role
  assignments are portable and pixel-free, mirroring the C1 style-bible
  contract. Competing assignments for the same region within a panel context
  are refused rather than guessed. Explicit propagation copies an accepted
  assignment onto artist-selected target regions only, never discovers
  regions automatically, and refuses to overwrite a target with a competing
  assignment. Saves are atomic with bounded JSON recovery. Verification: 348
  tests pass; Ruff and core mypy are clean. Project binding, engine/Docker
  operations, and the live-Krita checklist remain before Review.
- Advanced C2 issue #16 with project schema-v9 style-bible bindings. Validated
  attach/detach operations accept only existing regular non-symlink project
  assets, validate referenced views, remain idempotent, and never delete files.
  Engine/client operations and privacy-safe summaries expose identity and counts
  without pixels. Existing schema-v8 projects migrate to an empty binding list.
- Opened C3 issue #17 in Backlog for offline Krita style-bible authoring and
  explicit per-material palette-role application. Learned correspondence and
  deployment over the reviewed tutor candidate are explicitly out of scope.
  Moved C3 to In Progress and added the separate Character Colors Docker plus
  host-neutral authoring contracts. External references copy atomically into
  `references/` with sanitized content-hash filenames; style bibles validate,
  save, and bind through the engine. `Material Masks/Material — <canonical-id>`
  alpha layers drive local/light/shadow previews in separate locked color layers
  with explicit accept/reject. Source masks, line art, and artwork are unchanged.
  Existing bibles now reopen with prefilled identity, materials, aliases, palette
  roles, optional accents, and references rather than requiring re-entry.
  Unavailable accent roles are omitted from preview choices. Preview creation,
  pixel writes, and owned-layer removal now fail visibly and clean partial state.
  Accepted colors are unlocked, per-material layers grouped under `Character
  Colors`. Preview now blocks ambiguous overlapping semantic masks and reports
  conflict pixel counts. Style-bible schema v2 adds editable controlled reference
  view types and deterministically migrates v1 references to `other`. Materials
  can be split into named mask variants that share a canonical palette; reference
  notes are editable, and accepted layers record the bible ID in Krita metadata
  where supported. Extracted and tested the host-neutral variant-union operation,
  completing the headless semantic workflow gate; only live Krita acceptance
  remains before moving C3 to Done. Mirrored the complete review checklist in
  the Krita integration README for offline use. Added a Docker action for
  creating named material-mask variants with duplicate-name protection.
- Opened C4 issue #18 for the deterministic manual correspondence and
  correction-propagation baseline. It explicitly requires artist-controlled
  previews, portable provenance, ambiguity refusal, and headless recovery tests;
  ML, generative filling, and deployment remain out of scope.
- Started reference-coloring C1 issue #15 with a standalone version-1 character
  style-bible contract. It validates canonical semantic materials, unambiguous
  aliases, uppercase sRGB local/light/shadow/optional-accent roles, safe relative
  reference views, and bounded recovery. JSON writes are atomic; interruption
  preserves the last valid bible. Unknown fields/future versions are rejected,
  and the manifest deliberately excludes pixels, embeddings, inferred identity,
  and model output. Added format and roadmap documentation.
- Moved A3 issue #12 to deferred In Review after completing its headless
  integration. The issue now carries a ten-step live Krita checklist covering
  grouped layers, imports, fresh sequential dispatch, form/cast masks, decisions,
  rationale history, cancellation recovery, dashboard behavior, offline use,
  and artist-layer isolation, with explicit pass-to-Done/fail-to-In-Progress
  rules. The candidate remains undeployed.
- Completed fresh “Run Next Capstone Review” dispatch in structural-leverage
  order: front structure; turned structure; identity retention; expression/
  asymmetry; then cel values. Confirmation opens the rubric-specific landmark
  dialog immediately. Multi-rubric layers run sequentially rather than mixing
  incompatible landmark contracts. The capstone group now includes dedicated
  front/turned form/cast and optional third-value layers. Each fresh review is
  saved, explained, explicitly decided with a rationale, and then advances to
  the next unresolved rubric; cancellation leaves recoverable pending state.
- Added schema v8 compatible capstone-evidence import and a “Run Next Capstone
  Review” Docker action. The action confirms and selects the exact nested rubric
  layer, offers the latest compatible prior review, and otherwise leaves the
  layer ready for fresh evidence. Imports preserve source attempt/review
  provenance, create a new capstone-local ID, and require a new decision and
  rationale rather than inheriting an earlier judgment.
- Reorganized the capstone template into six rubric-oriented layer groups while
  preserving its named drawing layers and locked tutor layout.
- Added project schema v7 and existing-docker controls for editable capstone
  rationales. Editing text never changes the accepted/rejected/deferred decision.
  An independent project setting retains timestamped prior rationale revisions
  and defaults off; disabling it clears history. Rationale content stays in the
  portable project and is excluded from the aggregate-only learner profile.
- Split cel-value form and cast evidence into four explicit named masks: front
  form/cast and turned form/cast. The reviewer retains category-specific scalar
  measurements and derives combined shadow-family readability/consistency.
  Empty form masks are rejected as incomplete; empty cast masks are valid.
- Added a resumable capstone collection plan to the rubric-preserving progress
  dashboard. It tracks front structure, turned structure, identity retention,
  expression/asymmetry, and cel-value grouping as missing, pending-decision, or
  complete; names the exact capstone layer for the next review; and only reports
  readiness for the artist's manual completion after every rubric is resolved.
- Expanded cel-value explanations with descriptive front/turned occupancy,
  consistency limitations, and cause-oriented island guidance. Four concrete
  remedial exercises now match every evaluator route: family consolidation,
  island-cause audit, front-to-turned light transfer, and third-value restraint.
- Added identity-retention correction previews to the selected front/turned
  character-variation review. Failed cranial, feature-span, ear-height,
  lower-face, and identity-card checks now produce provisional tutor-owned
  guides mapped only into the reviewed sheet cell; variants remain descriptive
  and never receive corrective ranking.
- Added the first dedicated cel-value review. The template now uses explicit
  front, turned, and optional third-value mask layers where transparency means
  light and painted alpha means shadow/accent. A local 64×64 sample measures
  area balance, connected fragmentation, isolated islands, edge complexity,
  front/turned consistency, and optional third-value subordination, combined
  with manual light-direction and hardness confirmation. Only scalar results
  are persisted; sampled pixels and colors are discarded.
- Added project schema v6 capstone accountability. Accepted, rejected, and
  deferred capstone suggestions require a non-empty artist rationale; older
  decisions remain compatible through deterministic migration. The progress
  snapshot and existing docker now expose an aggregate capstone dashboard that
  retains the latest measurements and decision state for every underlying
  rubric instead of collapsing the artist into one score.
- Opened A4 issue #14 in Backlog for real-beginner threshold calibration,
  explanation-quality evaluation, compatible repeated-attempt measurement,
  offline Kubuntu/Krita acceptance, and RTX 4080 12 GB latency/VRAM gates. This
  evidence phase is separated from A3 feature construction.
- Began A3 issue #12 with a versioned offline curriculum graph containing nine
  primary anime head-and-face exercises and four targeted remedial exercises.
  Deterministic prerequisites select the next unlocked exercise; normalized
  rubric weaknesses route to focused practice with the observed score,
  threshold, and pedagogical reason. Missing evidence is not treated as
  failure, ties have stable priority, and repeated attempts are compared only
  across identical exercise/method/rubric versions. The comparison reports
  per-dimension improvement, no change, or decline without a global artist
  score or ranking. Added a private progress-summary contract exposing attempts,
  retries, comparable changes, and deliberately skipped incompatible pairs.
  Advice feedback is counted as helpful, unhelpful, incorrect, not applicable,
  or unrated; contradictory classifications, duplicate reports, and references
  to unknown reviews are rejected rather than silently normalized.
  Applied the owner decisions for A3 persistence: project-local learning
  retention is a user setting enabled by default; prerequisites recommend the
  next exercise without locking any lesson; and advice ratings plus optional
  notes live in the portable project. Schema v3 adds deterministic v0/v1/v2
  migration, atomic/recoverable feedback persistence, an idempotent engine
  operation, and refusal to overwrite an existing report. Artwork history and
  global aggregation remain independently disabled by default.
  Added the first A3 progress UI to the existing tutor docker. A bounded engine
  snapshot exposes only portable review metadata; the docker presents attempts,
  reviews, compatible improvement/decline trends, and raw normalized values.
  Raw values are visible by default through an atomic display preference.
  Retention controls let the artist keep data, explicitly clear-and-disable, or
  re-enable it; the engine refuses implicit clearing. Headless formatter,
  settings, client, service, privacy, and recovery tests cover the boundary.
  Made advice feedback editable per owner direction. Portable schema v4 gives
  every revision a monotonic number, keeps or discards prior edits according to
  a per-project history setting (off by default), and enforces a configurable
  1–100,000 character note limit with a 2,000-character default. The existing
  docker now offers all four rating actions, an optional note editor, and policy
  controls. Deterministic v3 migration and atomic engine operations cover both
  current-only and retained-history modes.
  Fully authored the second offline curriculum lesson, head orientation, instead
  of adding shallow placeholders across the remaining sequence. It teaches the
  cranial ball, cross-contour center/eye-lines, near/far-side compression, jaw
  attachment, and profile cranial preservation through four theory sections,
  seven staged steps, three repetition drills, five cause-and-correction mistake
  diagnoses, six completion criteria, and five self-review prompts. Packaged
  content tests enforce stable identity/version and minimum instructional depth.
  Added multi-lesson navigation to the existing docker with an ordered selector
  plus Previous/Next buttons; boundaries stop at the first/last lesson and no
  prerequisite locks browsing. Two original scalable offline SVGs visualize
  cross-contours and the five-view rotation ladder and are selectable in the
  lesson. Completion is an explicit reversible checkbox persisted through the
  bounded engine; reviews never complete an exercise automatically.
  Added the orientation exercise template as a true portable
  `anime-head-orientation` attempt: a 2600 × 1600 landscape document with a
  locked SVG five-cell layout and separate named construction layers for both
  profiles, both three-quarter views, and front. The middle/front layer starts
  active. Completing the front exercise now makes orientation the immediately
  recommended next lesson in the engine snapshot without changing manual
  navigation. Orientation review remains deliberately unimplemented until its
  one-head-at-a-time landmark/rubric contract exists; the front rubric is not
  misapplied to turned heads.
  Added the dedicated selected-head orientation review contract. The active
  named construction layer determines the candidate view and sheet cell; the
  artist must confirm it before a cropped landmark dialog opens. Profiles and
  three-quarter heads use different prompts and geometry. Both return the six
  approved normalized dimensions plus auditable raw measurements through the
  bounded engine, and repeated compatible attempts participate in direction
  comparisons. Thresholds are deliberately documented as provisional until
  tested on real beginner work; the front workflow remains separate.
  Completed the orientation preview loop: every failed dimension emits a
  principle-linked guide in selected-head coordinates. The host maps those
  coordinates into only the confirmed fifth of the landscape sheet without
  mutating the engine response, rasterizes them in the locked tutor group, and
  reuses the existing explicit preview Accept/Reject lifecycle and portable
  decision persistence. Front-cell reviews retain their calibrated front rubric
  identity while receiving the same cell-local mapping.
  Fully authored curriculum lesson three, Cranial Volume and Jaw Variation. It
  teaches a stable parent cranial mass, one-variable design changes, nuanced age
  tendencies, structural jaw attachment, and preservation through rotation via
  four theory sections, seven stages, three drills, five cause/correction
  diagnoses, six completion criteria, five self-review questions, and a final
  labeled variation sheet. Two original SVGs compare four jaw designs and show
  the pinched-cranium failure against a preserved cranium plus attached jaw.
  Added its practical 2800 × 1600 design-sheet workflow with four named front
  variant layers, one selected-variant right-three-quarter layer, and a locked
  five-area SVG layout. Individual review follows only the explicitly confirmed
  active layer. An optional separate paired review compares artist-confirmed
  front and turned landmarks for cranial-volume, lower-face-length, and jaw-
  character retention plus chin alignment and perspective adjustment. It saves
  the auditable raw ratios and normalized dimensions in the portable project;
  provisional thresholds remain subject to beginner-drawing calibration.
  Fully authored lesson four, Eye Placement and Perspective, as a front-to-
  three-quarter beginner progression. It establishes simplified eyeballs and
  sockets before stylized lids, separates structural placement from style and
  expression, and teaches deliberate spacing, far-eye wrapping/compression, and
  expression retention through five theory sections, eight stages, three drills,
  six diagnosed mistakes, seven completion checks, and six self-review prompts.
  Two original offline SVGs support the lesson. Its 2400 × 1600 Krita template
  separates neutral front structure, stylized front expression, neutral turned
  structure, and stylized turned expression into four named layers beneath a
  locked vector layout.
  Added the dedicated selected-eye-study review path. The active named layer
  chooses front/right-three-quarter view, structure/style-expression stage, and
  one of the four sheet cells; explicit confirmation precedes a cropped 16-point
  landmark session. Structure review measures eye-line adherence, axis-relative
  spacing, and projected scale. Style/expression review additionally measures
  lid-opening rhythm and iris-exposure consistency. Raw widths/openings and
  normalized scores persist through the bounded engine and can participate in
  version-compatible retry comparisons. Thresholds are provisional, and this
  slice intentionally emits explanations rather than pretending its first-pass
  geometry can author useful eye redlines.
  Added conservative eye correction previews for every failed applicable
  dimension: cross-contour corner alignment, axis-relative spacing, projected
  far-eye width, normalized lid opening, and iris exposure. Each guide states
  its teaching principle, maps only into the confirmed quarter-sheet cell, and
  reuses the explicit Accept/Reject persistence contract. Projected-width text
  explicitly labels its provisional target as a comparison rather than a tracing
  mandate.
  Fully authored lesson five, Nose, Mouth, and Ear Placement, as another
  front-to-three-quarter progression. It begins with muzzle/nose projection,
  mouth wrapping, and attached ear-cup construction before anime simplification;
  ears receive equal stages, drill space, diagnoses, and completion evidence.
  Five theory sections, nine stages, four drills, seven diagnosed mistakes,
  eight completion checks, and seven self-review prompts include neutral, happy,
  determined, sad, and surprised expression coordination. Two original offline
  SVGs accompany a 2400 × 1800 Krita matrix with separate front/turned layers
  for nose+muzzle, mouth, and ear beneath a locked vector layout.
  Added specialized manual review workflows for all six feature layers. Nose,
  mouth, bilateral front-ear, and near-ear/optional-far-evidence turned-ear
  studies use distinct prompt contracts and rubric dimensions. Front ears are
  measured independently so accidental asymmetry is visible; the turned ear
  receives full near-ear attachment/bowl/side-plane review without requiring an
  unobscured far ear. An optional combined review activates only after all six
  studies and compares nose, mouth, ear, and mouth-expression retention across
  the turn. Raw measurements and normalized dimensions persist and participate
  in version-compatible retry comparison.
  Added feature-specific correction previews for failed nose/muzzle, mouth, and
  ear dimensions. Guides cover facial-axis placement, base/corner relationships,
  perspective wrap/compression, muzzle support, bilateral ear bounds and bowls,
  near-ear attachment, and far-ear occlusion evidence. A row-major mapper places
  every guide only inside the confirmed cell of the 3 × 2 feature matrix, and
  previews reuse explicit Accept/Reject persistence.
  Fully authored lesson six, Controlled Asymmetry. It requires a corrected
  symmetric control before introducing anatomical/design or expression
  imbalance, teaches cause classification and strength ladders, and separates
  authored differences from perspective during three-quarter transfer. Five
  theory sections, eight stages, four drills, six diagnosed mistakes, eight
  completion checks, and seven self-review prompts emphasize preserving identity
  and rejecting unexplained drift. Two original SVGs accompany a 2600 × 1800
  six-layer Krita sheet for control, correction, design/expression variants,
  symmetric turn, and transferred asymmetry.
  Added the controlled-asymmetry comparison workflow. All six layers use a
  shared 14-point relationship set. Later layers compare directly against the
  front symmetric control, except transferred three-quarter asymmetry compares
  against the symmetric three-quarter control. Design, expression, and transfer
  layers require cause, character side, strength, and free-text purpose labels;
  controls and corrected drift keep labels optional. Labels persist as explicit
  artist-confirmation evidence while numeric retention, side, and strength
  measures remain compatible with progress comparisons.
  Added controlled-asymmetry correction previews. Failed cranial, lower-face,
  eye, jaw, mouth, ear, declared-side, and strength dimensions generate
  candidate-local guides derived from the explicitly recorded symmetric control.
  Turned comparisons apply their perspective target before drawing the guide.
  A 3 × 2 matrix transform confines previews to the confirmed study layer and
  reuses Accept/Reject persistence.
  Fully authored lesson seven, Character Variation and Identity Retention. It
  separates identity anchors from declared proportion, feature-shape, age/style,
  and shape-language axes; tests an undecorated lineup; requires a five-to-eight
  anchor identity card; and reconstructs the selected character in front and
  three-quarter views without tracing. Five theory sections, nine stages, four
  drills, seven diagnosed mistakes, eight completion checks, and seven self-
  review prompts target generic-face convergence and decoration dependence. Two
  original SVGs accompany a 2600 × 1800 six-layer identity model sheet.
  Fully authored lessons eight and nine, completing the nine-lesson content
  sequence. Cel-Shaded Value Grouping teaches explicit light statements,
  plane-facing decisions, two-value masks, form/cast causes, restrained third
  values, and front-to-turned consistency through five theory sections, nine
  stages, four drills, and two original diagrams. Its 2600 × 1800 six-layer
  sheet separates plane map, front masks/audit, third-value pass, turned transfer,
  and consistency. The Comprehensive Capstone integrates brief, identity card,
  construction, expression, controlled asymmetry, lighting, review decisions,
  prioritized correction, comparison, and delayed repetition. Two capstone SVGs
  and a 3200 × 2000 six-layer sheet preserve initial evidence, correction pass,
  and final self-review; completion remains explicitly artist-controlled.
  Added project schema v5 portable identity cards. Each card holds five to eight
  unique normalized numeric anchors plus required descriptions, is editable with
  monotonic revisions, and has independently configurable revision-history
  retention defaulting off. The docker authors cards and policy through bounded
  engine operations. Every variation compares descriptively with the undecorated
  baseline; selected front reconstruction compares with baseline; selected
  turned reconstruction compares directly with selected front. Identity-card
  adherence and version-compatible retention measurements stay numeric, while
  the card name/revision is recorded as artist-confirmation evidence.
- Opened A3 issue #12 at In Progress P0/XL for versioned curriculum progression,
  deterministic weakness-to-remediation routing, comparable repeated-attempt
  metrics, and a private local progress view while A2 issues #10/#11 remain in
  owner-deferred Review.
- Moved the deployed A2 lesson/landmark/review/redline slice (#10) to deferred
  owner review with exact live instructions and an explicit status rule: all
  expected behaviors moves it to Done; any failure returns it to In Progress
  with the failing step. Created #11 at In Progress for suggestion decisions
  and persistence so new work does not change the reviewed slice silently.
  Began #11 with an explicit preview decision lifecycle. Suggested redlines use
  a distinct tutor-owned preview name; Accept idempotently retains the layer as
  a locked tutor reference, while Reject removes only a pending owned preview
  and refuses unrelated layers. The default accept shortcut is now unassigned
  rather than stealing Krita's Tab canvas-only action. Persistence, configurable
  shortcuts, and verified undo behavior remain.
  Added portable project schema v2 review records containing only stable
  identities/versions, numeric measurements, explanations, and a final
  pending/accepted/rejected decision. Engine redline geometry, preview metadata,
  and pixels are deliberately excluded. Deterministic v0/v1 migrations add
  empty review lists, repeated identical decisions are idempotent, reversals and
  duplicate review IDs are rejected, and recovery tests retain the prior pending
  revision. Krita project-folder binding remains.
  Bound Krita exercises to the approved portable layout: an explicitly selected
  empty directory receives `artwork/attempt-001.kra` and an atomic root
  `project.json`. The active document has a safe relative `document_asset` and
  remains distinct from opt-in artwork history. Versioned engine operations
  create the manifest, append a privacy-safe review to its stable attempt, and
  persist final decisions with recovery rotation. Unrelated/non-empty targets,
  traversal, missing/ambiguous attempts, and duplicate reviews are refused.
  Completed #11's configurable interaction boundary: Review, Accept, and Reject
  shortcuts default empty, must be valid and unique, and are atomically saved
  without replacing the configured engine. Reconfiguration replaces old Qt
  bindings cleanly. If a layer decision succeeds but manifest persistence fails,
  the same action becomes an explicit retry and the opposite action is blocked;
  no failure is reported as success. Accept retains only a tutor reference and
  never applies pixels to artist artwork, so this slice creates no accepted
  artwork mutation requiring an undo command.
- Started A2 issue #10 by replacing the placeholder lesson with a five-stage,
  locally packaged beginner sequence covering cranial mass, centerline,
  eye-line, jaw/chin construction, structural checking, completion criteria,
  and three non-traced practice attempts. The Krita docker now scrolls long
  explanations and checklists instead of clipping them; adapter coverage checks
  the versioned method and minimum instructional structure.
  Added the first deterministic review service over explicit normalized
  landmarks. Balanced and deliberately flawed fixtures exercise raw axis-angle,
  chin-offset, and jaw-asymmetry measurements, provisional rubric scores,
  geometry-only evidence, actionable explanations, separate redline geometry,
  preview suggestions, and targeted practice routing. It performs no pixel or
  model analysis; Krita landmark placement and layer rendering remain.
  Added the exercise-document adapter and tutor action: it creates a new,
  deliberately unsaved 1600 × 2000 RGBA document without modifying an existing
  document, separates `Construction Guides` and `Artwork`, reserves a locked
  `Tutor Feedback` group, and activates the construction layer. Headless stubs
  verify exact document arguments, layer order/lock state, active layer, view
  attachment, and the missing-window failure path; live verification remains.
  Added the explicit local engine boundary promised in A1: the standalone
  `cel-shaded-generator-engine` handles one bounded, versioned JSON review
  request over standard streams, while a dependency-free Krita client enforces
  executable discovery, a five-second timeout, bounded messages, matching
  protocol/request identifiers, structured errors, and no shell invocation.
  Unknown operations and malformed requests are rejected without traceback
  leakage. Landmark UI and user-facing executable configuration remain.
  Added manual landmark placement over a public `Document.thumbnail()` snapshot.
  The public Python Canvas API has no screen-to-image mapping, so the adapter
  deliberately avoids private Qt canvas internals. The ordered nine-point flow
  labels markers, supports undo/reset/cancel, normalizes coordinates, derives
  cranial radius, and does not modify artwork. Review submission remains.
  Also corrected the live-deployment process check after its command-line search
  could match the checking shell itself; exact process-name inspection confirmed
  Krita was closed and the seven-file plugin was safely reinstalled.
  Completed the first end-to-end explanation path: installation can atomically
  record one explicit executable in XDG configuration, the plugin validates and
  discovers it without shell arguments, and the tutor submits collected
  landmarks with a unique request identifier and displays returned explanations.
  Missing landmarks, engine/configuration failures, and empty explanations are
  actionable UI states. Artwork remains unchanged; redline rendering is next.
  Added Krita 5.x redline rendering without relying on Krita 6-only painting
  methods. Validated normalized geometry is bounded and rasterized as transparent
  U8 BGRA into a newly created, locked tutor-owned layer; the locked feedback
  group is opened only for the scoped insertion and always relocked. Failed
  writes remove their partial layer. Artist construction/artwork layers are
  never selected or written. Live host verification remains.
- Started alpha A1 issue #9: added a Krita 5.2/Snap plugin skeleton with a
  right-default lesson docker, packaged English-only offline placeholder lesson,
  and scoped install/uninstall tool that refuses unknown overwrites.
  Added core versioned contracts for lessons, exercises, rubrics, structured
  review evidence, redlines, preview suggestions, artist feedback, independent
  privacy settings, automation level/shortcuts, and an offline model registry
  with built-in/community/unverified trust labels.
  Added offline self-diagnostics for Krita/Python compatibility, packaged lesson
  presence, and confined core visibility; the docker displays actionable status.
  Documented the verified Krita 5.2.11 Snap install/enable/uninstall workflow and
  explicitly requires A2 to use a real local transport instead of `sys.path`
  injection across Snap confinement.
  Added atomic learning-catalog persistence for lessons, exercises, rubrics,
  privacy/automation settings, and trust-labeled local models, with deterministic
  privacy-preserving v0 migration and unsupported-future-version rejection.
  Installed the plugin into the owner's live Krita Snap user directory and
  verified exact file scope/checksums. The first verification exposed copied
  Python cache artifacts; the installer now excludes `__pycache__`, `.pyc`, and
  `.pyo`, with regression coverage, and the live plugin was cleanly reinstalled.
  Follow-up inspection after the Python Plugin Manager was absent proved the
  Krita 5.2.11 Snap omits the entire Python plugin subsystem. Corrected the
  installer to reject Snap paths and target the official AppImage's standard
  Linux resource directory; the Snap files are inert and cannot be enabled.
  Downloaded the official Krita 5.3.2.1 AppImage, verified its SHA-256 against
  KDE's published value, confirmed it bundles `pykrita`, Scripter, and the plugin
  importer, installed a desktop launcher and the plugin's six intended files,
  and completed a clean startup probe. Interactive enablement and visible-docker
  confirmation subsequently passed. The discovery check also established that
  Krita disables every docker action on its start screen until a document is
  open; onboarding must explain or avoid this otherwise confusing state.
  Completed A1 with a stack-neutral local model-package manifest and bounded,
  non-executing integrity validator. It checks registry identity, schema,
  entrypoint declaration, safe relative paths, regular non-symlink artifacts,
  byte sizes, configurable resource limits, and SHA-256 content while allowing
  extensible custom format names. Documentation keeps integrity distinct from
  built-in/community/unverified provenance and future runtime safety.
- Completed Phase 0 issue #8 and the standalone-foundation phase: replaced the
  template README, contributor/agent guidance, documentation landing page,
  development/testing/dependency/troubleshooting/module guides, glossary,
  Sphinx identity, and placeholder C4 model with truthful project-specific
  content. The historical polyglot ADR is explicitly superseded. Documented
  commands now match the uv core+GUI workspace, current features are separated
  from planned promises, and the Krita head-and-face alpha is the next phase.
- Started Phase 0 issue #6: introduced a host-neutral `JobRequest`/`Operation`
  contract and `IsolatedRunner`, spawning a fresh process for each native-heavy
  job. Hard exits, hangs, cancellation, ordinary exceptions, and pipe EOF are
  converted into recoverable host-side failures; the next worker starts cleanly.
  Adaptive timeouts are capped by user policy, and optional local JSONL
  diagnostics contain only operation, array dimensions, timing, outcome, and
  error type—never pixels or filenames. GUI routing and overhead measurements
  remain before this issue is complete. Diagnostics are enabled by default in
  the XDG state directory, rotate at seven days or 20 MiB, and can be disabled;
  the default maximum job timeout is five minutes.
  Added a restartable persistent isolated worker for latency-sensitive serial
  work and routed Qt ARAP dragging through it. The committed CPU baseline
  measures ~311 ms cold startup but only ~0.04 ms steady-state overhead
  (8.78 ms isolated versus 8.75 ms direct), validating persistence for dragging.
  Completed the built-in host routing: ordinary scribble, screentone,
  reference, incremental-preview, temporal, and graph-refined animation jobs
  now use fresh isolated processes. Arbitrary third-party Python callables keep
  an explicit in-process compatibility fallback until a versioned plugin
  operation registry can replace unsafe callable serialization.
- Completed Phase 0 issue #5's current-engine baseline: deterministic synthetic
  fixtures and directly committed golden arrays now cover scribble/reference
  colorization, temporal propagation, and ARAP. Added documented cross-platform
  regression tolerances, machine-readable anonymized latency/Python-memory
  reports, and an explicitly invoked benchmark workflow. The first CPU baseline
  identifies temporal propagation as the largest fixture workload but does not
  yet justify a C++ rewrite; real-art perceptual and native/GPU-memory measures
  remain incremental requirements as those workloads land.
- Completed Phase 0 issue #4: added the versioned, storage-neutral project and
  learning domain model plus atomic JSON persistence. Projects are portable
  folders with project-local attempts, tutor feedback, and metrics; artwork
  history is rejected unless explicitly enabled. Autosave defaults to ten
  bounded recovery manifests, while opt-in cross-project aggregates live in a
  separate learner profile. Added deterministic privacy-preserving v0→v1
  migration, format documentation, and failure/recovery coverage.
- Started Phase 0 issue #3: replaced dynamic `manga`/`manga_gui` aliases with
  installable `cel_shaded_generator`/`cel_shaded_generator_gui` packages in a
  `uv` workspace; moved native-workload coordination out of Image-Toolkit into
  the core runtime; gave the GUI local file-dialog/image-loading helpers; added
  package-boundary tests, headless GUI CI execution, wheel builds, and a real
  architecture document. The Image-Toolkit adapter now consumes the public
  namespaces rather than defining the submodule's identity.
- Completed Phase 0 issue #3's distribution gate: added the installed
  `cel-shaded-generator` desktop command, extracted a reusable/testable main
  window composition boundary, and made CI install both wheels into a clean
  Python 3.11 environment before constructing the full GUI offscreen. The GUI
  suite now covers the standalone shell with 103 passing tests. Narrowed the
  CI lint boundary to product source/tests (rather than unrelated imported
  template tooling) and resolved all existing core and GUI mypy errors, making
  both declared quality gates executable and green.
- Replaced the imported manga-feature roadmap with an outcome-based product
  roadmap following the 2026-08-06 product review and owner brainstorm. Added
  focused roadmaps for the Krita anime head-and-face learning alpha, standalone
  C++ engine migration, reference-consistent coloring, anime animation, and 2D/
  3D game assets; explicitly deferred browser and mobile clients.
- Defined the offline Linux/NVIDIA deployment target, artist-controlled
  automation levels, opt-in progress/artwork retention, open local-model policy,
  measurable-learning release gates, and Blender/Unity/Unreal integration
  priorities.
- Moved `moon/` and `research/` into `docs/` (`docs/moon/`, `docs/research/`), consolidating all documentation under one directory; extended `docs/mkdocs.yml`'s nav with Roadmap/Changelog/Research sections at the new locations plus a link back to the parent Image-Toolkit project.
- Added `docs/website/` — a Vue 3 + Vite documentation site (same design as Image-Toolkit's own) rendering every `docs/**/*.md` directly, nav/search generated from this repo's own `docs/mkdocs.yml`. Includes a "Related Projects" sidebar section embedding Image-Toolkit's and ASP's own docs sites via iframe. Deployed alongside the MkDocs portal in CI (`.github/workflows/docs.yml` + Forgejo/Gitea/GitLab mirrors) at `/app/`.
- Fixed `.gitlab/.gitlab-ci.yml`, `.gitlab/issue_templates/`, `.gitlab/merge_request_templates/`, and `.devcontainer/` — all still referenced the polyglot template's removed cpp/rust/typescript/kotlin/go dirs, missed when the `src`/`gui` flatten+split landed.
- Imported Manga Colorization & Animation from Image-Toolkit: the Python solvers (`src/manga`), tests (`test/manga`, `test/gui`), the colorization/animation/puppeteering GUI tabs, canvas editor, mesh overlay editor, preference dialog, and workers (`src/manga/gui`), and the roadmap (`moon/ROADMAP.md`).
- Pruned the template to Python only (removed cpp/rust/java/kotlin/typescript/go scaffolding, the template-meta `dev/` tool, and desktop/infra scaffolding) and flattened `python/{src,test,config,validation,benchmark}` up to the repo root since this project is single-language.

### Template scaffolding

- Initial template scaffolding: root files (`LICENSE.md`, `README.md`, `.env.example`, `.pre-commit-config.yaml`, `.gitignore`/`.gitattributes`), `.github/` CI/CD, `git/` (`CONTRIBUTING.md`, `codecov.yaml`), `docs/` documentation portal (MkDocs + Sphinx + Structurizr + ADRs), `moon/` roadmap and changelog.
- `.agent/` LLM coding-agent scaffolding: `AGENTS.md` plus generic rules, workflows, prompts, and skills covering all six supported languages.
- Six language module skeletons (`python/`, `typescript/`, `kotlin/`, `rust/`, `go/`, `cpp/`), root workspace orchestrator files, and merged `python/validation/` dev-tooling.
- `java/` Maven module (7th language), wired into CI/pre-commit/justfile/docs alongside the existing six.
- Root Gradle wrapper and multi-project build files pairing with the existing `settings.gradle.kts`.
- `moon/roadmaps/developer_tools.md`: architecture plan for a polyglot `dev/` developer-assistant tool, synthesized from prior art across the org's other repos.
- GitHub Project (V2) backlog automation (`github/` + `.github/workflows/agent_sync.yml`), ported from Visual-Graph-Programming.
- `infra/{k8s,helm,terraform,ansible}/` infra-as-code scaffolding, alongside the relocated `infra/docker/`.
- `dev/` developer-assistant tool, milestones D1–D5 of `moon/roadmaps/developer_tools.md`: the `input/protobuf/codegraph.proto` schema, a hand-mirrored Python data model (`core/model.py`), a real AST-based Python import-graph parser (`input/python/parser.py`), multi-source graph aggregation (`core/aggregate.py`), layer classification + forbidden-direction violation detection (`core/layers.py`), Tarjan's-SCC circular-dependency detection (`core/cycles.py`), a self-contained vis.js/Jinja2 HTML report generator (`output/html/report.py`), and a `cli.py` tying it together (`report`/`check` subcommands). 13 passing pytest cases, including a fixture project with an intentional import cycle.

### Changed

- Moved `docker/` to `infra/docker/` to make room for other infra-as-code stacks; updated all referencing files.

## [0.1.0] — 2026-07-30

### Added

- Repository created from scratch as a GitHub template.
