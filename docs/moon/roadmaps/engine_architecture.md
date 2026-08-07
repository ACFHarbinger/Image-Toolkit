# Standalone Engine Architecture Roadmap

## Objective

Create a standalone, offline engine that can serve the Krita plugin first,
Blender and future desktop clients later, and Image-Toolkit only through an
adapter. C++ is the long-term engine language; Python remains the research and
model-development environment.

## Near-term boundary

The initial Python engine exposes typed jobs and results for analysis,
redlining, colorization, and later animation. UI packages do not import private
engine modules, and engine packages do not import Krita, Qt, or Image-Toolkit.

Heavy or unstable native work should run in cancellable worker processes. This
contains CUDA/BLAS/native-extension failures, enables resource scheduling, and
avoids making one global process lock the permanent concurrency model.

## Stable contracts before C++

- Versioned document, layer, stroke, lesson, rubric, review, redline, model,
  job, progress, and provenance schemas.
- Explicit image layout, color space, alpha, coordinate, and ownership rules.
- Deterministic serialization and migrations.
- Cancellation, progress, diagnostics, and structured errors.
- Capability discovery for optional CUDA/models/plugins.
- Golden inputs and outputs for every ported algorithm.

## C++ migration candidates

Port by measured value, not language preference:

1. Tiled image access, compositing, masks, and color conversion.
2. Stroke/curve geometry and deterministic analyzers.
3. Sparse optimization, region segmentation, correspondence, and deformation.
4. Video frame transport and motion-aware processing.
5. GPU scheduling and ONNX Runtime/TensorRT inference adapters.
6. Import/export validation for Blender, Unity, and Unreal workflows.

Use Python bindings for in-process research and a versioned local IPC service
for application isolation. Keep the C ABI narrow enough that alternative
language clients are possible without exposing C++ object ownership.

## Deployment profile

- First platform: Kubuntu/KDE on x86-64.
- Default inference target: consumer NVIDIA GPU with 12 GB VRAM.
- Higher-memory 24 GB development hardware may enable optional models but may
  not become an accidental baseline.
- CPU fallbacks are desirable for deterministic tools and diagnostics, but
  heavyweight ML need not meet interactive targets on CPU in the first alpha.
- No mandatory account, network service, or silent download.

## Model packages

Each package declares identifier/version, compatible engine ABI, files and
hashes, expected VRAM, license/provenance when known, execution provider, and
capabilities. Built-in validated, community-described, and unverified local
packages remain visibly distinct. Users retain the ability to install arbitrary
models.

## Architecture gates

1. **Standalone Python:** installable core and Krita client with no parent
   imports or alias bootstrap.
2. **Isolated jobs:** cancellable worker protocol and crash recovery.
3. **Measured native pilot:** port one proven bottleneck and demonstrate a
   representative improvement without changing output contracts.
4. **C++ engine foundation:** own stable document/compute services; Python
   becomes a plugin/research worker.
5. **Standalone editor decision:** proceed only when Krita limitations are
   demonstrated by validated workflows.

### Gate 5 exception (2026-08-07)

Gate 5's precondition has **not** been met — no Krita limitation has been
demonstrated by a validated workflow. The owner made an explicit, informed
decision to build a standalone full raster editor now anyway, ahead of that
gate, rather than in response to a discovered limitation. This is recorded
here so the history is honest: this is a scope decision, not evidence Krita
has proven insufficient. The reference-coloring Krita Dockers (Character
Colors, Line Art Segmentation, Chapter Queue, Learning Tutor) remain the
primary, actively-developed host; the standalone editor is a second,
independent host built on the same portable `project`/`colorization` core,
not a replacement in progress.

**Toolkit:** PySide6, matching the existing `cel_shaded_generator_gui`
workspace member (`gui/`) — the standalone editor is being built as new
tabs/elements inside that same package rather than a third Qt-binding
dependency.

**First slice (issue #25, In review pending a manual desktop-app check):**
a canvas + layer-stack foundation — `src/editor/`'s
`LayerStack` (pure numpy, no Qt, mirrors the "portable contract first"
pattern every other milestone in this project uses) plus a
`ReferenceColoringTab` in `gui/` wiring a zoomable/pannable `LayerCanvas`
to an add/remove/reorder/show-hide `LayerListPanel`. No paint tools, masks,
segmentation, or palette preview yet — those are later slices built on this
same foundation, the same way every Krita Docker was built on Krita's own
layer model.

**Second slice (issue #26, In review pending a manual desktop-app check):
brush paint tool.** `src/editor/brush.py` adds `stamp_dot`/`stamp_line` —
pure numpy, no Qt, a hard-edged circular brush composited with straight
alpha "over", deliberately not anti-aliased so it stays simple and
pixel-exact-testable; a softer brush is a later slice on the same contract.
`LayerCanvas` gained an explicit Pan/Brush tool switch (`set_tool`) rather
than overloading left-click, since `QGraphicsView.DragMode.ScrollHandDrag`
already claims left-click-drag for panning; painting targets whichever
layer `LayerListPanel` reports as selected (`layer_selected` signal, new).
`ReferenceColoringTab` adds Pan/Brush radio buttons, a color-swatch button
(`QColorDialog`), and a brush-size spin box. Still no masks, segmentation,
or palette-preview UI — those remain later slices on this same foundation.

**Third slice (issue #27, In review pending a manual desktop-app check):
undo/redo.** `src/editor/history.py` adds `EditHistory`, a snapshot-based
undo/redo stack bound to one `LayerStack` — callers call `record()`
immediately before a discrete mutation, and `undo()`/`redo()` restore or
reapply the full prior state, bounded by a `max_depth` that evicts the
oldest entries. Deliberately snapshot-based rather than a command/diff log:
the simplest deterministic contract that stays fully testable, since every
canvas in this project is bounded with no infinite-undo requirement.
`LayerStack.save_state()`/`load_state()` back this with a deep, in-place
copy so the `LayerStack` object's identity survives an undo/redo — nothing
needs to rebind to a new object. `LayerCanvas` records one checkpoint per
brush stroke (at `mousePressEvent`, not per dot, so a whole stroke undoes
as one step); `LayerListPanel` records one before each add/remove/reorder/
visibility-toggle and gained a public `refresh()` to re-sync after an
external mutation. `ReferenceColoringTab` creates one `EditHistory` per
canvas and adds Undo/Redo buttons. Still no masks, segmentation, or
palette-preview UI.

**Fourth slice (issue #28, In review pending a manual desktop-app check):
non-destructive layer masks.** `Layer.mask` is an optional HxW uint8
grayscale buffer (`None` when absent), validated to match the layer's
pixel size. `LayerStack.add_mask`/`remove_mask` attach/detach a
fully-opaque mask; `composite()` multiplies each layer's alpha by
`mask / 255` before blending when present, the standard non-destructive
mask convention every mainstream raster editor uses. `save_state()`/
`load_state()` round-trip the mask too, so undo/redo (#27) covers mask
edits for free without any changes there. `src/editor/brush.py` adds
`stamp_mask_dot`/`stamp_mask_line` -- grayscale variants sharing the RGBA
brush's circular-clipping logic (extracted into `_clip_region`) but
overwriting to a given intensity directly rather than alpha-blending
(blending a mask against itself has no useful meaning).
`LayerCanvas.set_mask_mode(True)` redirects Brush strokes to the active
layer's mask, and is a no-op on a maskless layer rather than silently
falling back to painting color. `LayerListPanel` gained Add Mask/Remove
Mask buttons and a `(mask)` list-item suffix; `ReferenceColoringTab` gained
an Edit Mask checkbox and a Mask value spin box. Still no segmentation or
palette-preview UI; masks here are a general raster-editor primitive, not
yet tied to the Krita-side semantic "material mask" concept.

**Fifth slice (issue #29, In review pending a manual desktop-app check):
line-art segmentation.** `src/editor/segmentation_tools.py` reuses
`colorization.segmentation` (roadmap milestone 1, issue #19) directly
rather than reimplementing it -- unlike the Krita plugin's
`segmentation_masks.py`, which mirrors the same algorithm in pure Python
for Krita's "no numpy" boundary constraint, the standalone GUI package
already depends on numpy, so there is nothing to mirror.
`close_line_gaps_in_layer` bridges small gaps in a layer's painted ink (its
alpha channel) in place. `segment_layer_into_regions` segments a layer's
painted ink into enclosed background regions, each becoming a new,
distinctly colored layer stacked directly above the source; it never
mutates the source layer, and regions that leak to the canvas border are
correctly excluded (matching `colorization.segmentation.segment_regions`'s
existing contract). `region_adjacency_for_regions` computes adjacency
pairs from region layers' *current* alpha masks (not a re-derivation from
the original line art), so it reflects any manual repainting since
segmentation -- a building block for a possible later slice connecting the
standalone editor to something like milestone 4's confidence-ranked
correspondence workflow, not yet wired into any button.
`ReferenceColoringTab` adds Close Line Gaps (with a Max gap spin box) and
Segment Regions (with a Min region area spin box) buttons operating on the
selected layer. Still no palette-preview or correspondence-assignment UI.

**Sixth slice (issue #30, In review pending a manual desktop-app check):
style-bible palette application.** `src/editor/palette_tools.py` reuses
`colorization.style_bible` (roadmap milestone 2, issue #15) directly, the
same way #29 reused `colorization.segmentation`. `resolve_palette_color`
parses a material palette's `#RRGGBB` role into an RGB int tuple, raising
for an unsupported role or an absent accent -- matching the Krita
Character Colors Docker's existing "absent accents are not offered as
preview roles" rule rather than silently substituting another role.
`apply_palette_color_to_region` recolors a layer's currently-opaque pixels
to that color in place, leaving its alpha/shape untouched -- the same
"shape from segmentation/painting, color from the bible" split the Krita
Docker's material masks use. `ReferenceColoringTab` adds Bind Style Bible
(file dialog), a Material combo box, a Role combo box (dynamically
excludes "accent" when absent), and an Apply Palette Color button
operating on the selected layer -- works on any layer, not only ones
`segment_layer_into_regions` created; there is no forced connection
between the two slices yet. Still no correspondence-assignment (a
persisted, propagatable region-to-material binding) or
adjacency-suggested defaults; this is a direct "pick a material+role,
click apply" action, not milestone 4's ranked-suggestion workflow.
Connecting the two remains a possible later slice.

**Seventh slice (issue #31, In review pending a manual desktop-app
check): region-to-material correspondence assignment.** New
`src/editor/correspondence_tools.py` reuses `colorization.correspondence`
and `colorization.confidence` directly, the same way #29/#30 reused
`colorization.segmentation`/`colorization.style_bible`, connecting the
fifth slice's region adjacency (#29) to the sixth slice's palette
application (#30) the way both slices' notes anticipated.
`adjacency_agreement_by_material` mirrors the Krita Character Colors
Docker's `_adjacency_agreement_by_material` (milestone 4, issue #24): the
fraction of a region's adjacent regions already assigned to each
material. `rank_material_candidates` combines that with
`colorization.confidence.name_similarity` via `score_candidate`, matching
`project.service.rank_correspondence_materials`'s signal combination, but
always starts from the same fixed 0.5/0.5 weights `SignalWeights` itself
starts from -- the standalone editor has no project binding yet, so there
is no correction-learning step this slice; wiring one in is a later
slice, after the standalone editor gains project persistence at all.
`assign_region_correspondence` returns a copy of a `CorrespondenceSet`
with one new region assignment, raising on a conflicting existing
assignment, the same rule `CorrespondenceSet.propagate` enforces.
`ReferenceColoringTab` adds a **Suggest Material** button (ranks
candidates for the selected region layer and pre-selects the top one in
the existing Material combo, never assigns anything) and an **Assign
Correspondence** button (records the current Material/Role as that
region's correspondence in an in-memory `CorrespondenceSet` tracked by
the tab). Assignment stayed in-memory for the editing session only as of
this slice -- the eighth slice below adds disk persistence. Applying the
suggested material's palette color remains a separate explicit action
(Apply Palette Color, #30) rather than automatic.

**Eighth slice (issue #32, In review pending a manual desktop-app
check): canvas document save/load.** Every prior slice was in-memory
only -- closing the app discarded all work. New `src/editor/document_io.py`
adds `save_document`/`load_document`: one `.npy` file per layer's pixel
buffer (and mask, when present) plus a `manifest.json` describing layer
order, identity, and flags. Deliberately `.npy` rather than PNG --
`src/editor/` has a strict "pure numpy, no Qt" boundary with no
image-codec dependency (`layer_stack.py`, `brush.py`), and adding one
(Pillow/Qt) just to persist arrays this module already owns as numpy
would be new surface for no real benefit. `ReferenceColoringTab` gains
**Save Document**/**Open Document** buttons (directory picker). Save
Document also writes the tab's in-memory `CorrespondenceSet` via the
already-existing `colorization.correspondence.save_correspondence_set`
and its region-layer-id bookkeeping (`region_layers.json`) alongside the
canvas, so the seventh slice's correspondence assignments and the fifth
slice's region tracking survive a save/reload round trip. Open Document
resets undo/redo history to the freshly loaded canvas; the bound style
bible, if any, is left as-is, since a document does not carry its own
bible reference. Not in scope as of this slice: autosave, recovery
revisions for the canvas document itself (the correspondence set already
got those for free from `colorization.correspondence`), or integration
with `src/project`'s learning-progress project model -- the standalone
editor still has no `SignalWeights`/project binding, so correction
learning (#24/#31) remains unavailable here.

**Ninth slice (issue #33, In review pending a manual desktop-app
check): canvas document recovery-revision rotation.** The eighth slice
gave the canvas document no protection against an accidental overwrite --
Save Document into an existing folder silently discarded the previous
state, unlike `colorization.correspondence`/`colorization.style_bible`'s
own bounded `_rotate_recovery` contract on their JSON assets.
`document_io.save_document` gained a `recovery_revisions` keyword
(default 10, validated to `1..100` matching `CorrespondenceSet`/
`CharacterStyleBible`'s own bound): whenever a document already exists at
the target directory, its prior on-disk state -- the whole directory,
manifest plus every layer's `.npy` files, since a document is multiple
files rather than the single JSON file `_rotate_recovery` handles
elsewhere -- rotates into `<directory>/.recovery/1..recovery_revisions`
before the new save overwrites it; the oldest revision is evicted past
the bound. A first save into an empty directory creates no `.recovery/`,
since there is nothing to protect yet. No restore API, matching the
existing scope of `colorization.correspondence`/`colorization.style_bible`'s
own rotation -- each `.recovery/<n>/` is itself a valid document
directory `load_document` can read directly, so recovering one is a
manual copy for now. No `ReferenceColoringTab` changes were needed: Save
Document already calls `save_document` with the new default, so rotation
is automatic and transparent.

**Tenth slice (issue #34, In review pending a manual desktop-app
check): bind a portable project for `SignalWeights` correction
learning.** Owner-directed follow-up to the seventh/eighth/ninth slices:
bind the standalone editor's correspondence assignment into a portable
`project` (`src/project`, the same package the Krita tutor's lesson flow
uses) so it benefits from `SignalWeights` correction learning, the same
way the Krita Character Colors Docker's milestone-4 workflow (#24) does
-- closing the gap the seventh slice's notes left open. New
`project.create_project(directory, *, title)` in
`src/project/service.py`: a bare project manifest with no
exercise/attempt. `create_exercise_project` is the Krita tutor's own
entry point and always seeds a lesson attempt; hosts that only need to
bind style bibles/correspondence sets (the standalone editor) have no
attempt to seed, and `Project.progress`/`document_asset` were already
optional in the schema -- this is the same manifest shape without the
tutor-specific defaults. `ReferenceColoringTab` gains **New
Project**/**Bind Project** buttons. Once a project is bound: **Bind
Style Bible** also attaches the bible into the project
(`upsert_project_style_bible`, tracked as `_bible_asset_path`);
**Suggest Material** ranks via `project.rank_correspondence_materials`
(using the project's learned `SignalWeights`) instead of the fixed
0.5/0.5 local weights, keeping the ranked candidates; **Assign
Correspondence** persists the updated correspondence set into the
project (`upsert_project_correspondence_set`) and reports the artist's
choice to `record_correspondence_choice`, so `SignalWeights` learn from
it. Without a bound project, everything behaves exactly as before
(in-memory, fixed weights) -- purely additive, no behavior change for
the unbound case. Not in scope as of this slice: binding the canvas
document itself (the `.npy`-per-layer format from #32/#33) into the
project's asset model -- the eleventh slice below closes that gap.

**Eleventh slice (issue #35, In review pending a manual desktop-app
check): attach canvas documents into a bound project.** Follow-up to
the tenth slice: the canvas pixel document itself was explicitly left
out of the project's asset model there. `src/project/model.py` bumps
`CURRENT_SCHEMA_VERSION` to 14, adds `Project.editor_document_assets:
list[str]` with the same uniqueness/safe-relative-path validation
`style_bible_assets`/`correspondence_set_assets` already get, and a
migration default (`[]`) for older manifests. `src/project/service.py`
adds `attach_editor_document`/`detach_editor_document`: unlike
`attach_style_bible`/`attach_correspondence_set`, the asset is a
directory (`editor.document_io.save_document`'s `manifest.json` + per-
layer `.npy` files), not a single `colorization`-loadable file -- this
package stays decoupled from `editor`'s exact on-disk format, the same
way an exercise attempt's opaque `document_asset` `.kra` path is never
opened by this package either, so only directory existence and path
safety are validated here. `ReferenceColoringTab`'s Save Document now
attaches the saved directory as a project asset whenever it's saved
inside a bound project's own directory; saving elsewhere still works
exactly as before, just untracked by the project manifest.

**Twelfth slice (issue #36, In review pending a manual desktop-app
check): browse and reopen project-bound assets.** UX follow-up to the
tenth/eleventh slices: once a project is bound, its already-attached
canvas documents and style bibles had no way to be reopened/reloaded
except by re-navigating a raw file dialog to the exact subpath each
time -- the same convenience gap the Krita Character Colors Docker's own
bible dropdown (`_refresh_bibles`) already solves for its lesson-flow
projects. `ReferenceColoringTab` gains two combo boxes, **Project
Documents** and **Project Bibles**, populated from the bound project's
`editor_document_assets`/`style_bible_assets` (`project.load_project`)
whenever a project is created/bound, or a new document/bible gets
attached. Two new buttons: **Open Selected Document** reopens the
selected `Project Documents` entry via the same path the file-dialog
Open Document flow uses (extracted into a shared
`_load_document_from_path` helper), no dialog needed; **Load Selected
Bible** loads the selected `Project Bibles` entry via the same path the
file-dialog Bind Style Bible flow uses (extracted into a shared
`_apply_loaded_style_bible` helper), no dialog needed, and sets
`_bible_asset_path` directly since it's already a project-relative
asset path (no re-attach needed). Pure refactor-and-extend of existing
behavior -- the file-dialog-driven Open Document/Bind Style Bible flows
are unchanged and still work with no project bound.

**Thirteenth slice (issue #37, In review pending a manual desktop-app
check): soft/anti-aliased brush hardness.** Fulfills the note left in
the second slice's own docstring since it landed: "a softer brush is a
later slice on the same `stamp_*` contract." `src/editor/brush.py` adds
`_circular_falloff(radius, hardness)` -- per-pixel coverage in
`[0, 1]`: fully opaque within `hardness * radius` of the center, then
linearly fading to transparent at `radius`; `hardness=1.0` is
pixel-identical to the existing hard `_circular_mask`.
`_clip_region` is generalized to take a brush coverage array directly
(bool or float) instead of always computing the hard circular mask
internally, so hard and soft stamping share one clipping
implementation. `_blend_color_over_weighted` is the soft-brush
counterpart of `_blend_color_over`, scaling the stamped color's alpha
per-pixel by the coverage array before straight-alpha "over" blending.
New `stamp_dot_soft`/`stamp_line_soft` mirror the existing hard
`stamp_dot`/`stamp_line` signatures plus a `hardness: float` parameter.
Mask painting (`stamp_mask_dot`/`stamp_mask_line`) is unchanged and has
no soft variant -- alpha-blending a mask against itself has no useful
meaning, so a soft mask edit isn't a well-defined concept yet.
`LayerCanvas` gains `set_brush_hardness`/`brush_hardness` (default
`1.0`, unchanged prior behavior) and dispatches to the soft stamping
functions only when hardness `< 1.0`, keeping the hard-brush path
byte-identical to before for the default case. `ReferenceColoringTab`
adds a Hardness spin box (`0.0`-`1.0`, step `0.05`) next to the
existing brush Size control.

**Fourteenth slice (issue #38, In review pending a manual desktop-app
check): eraser tool.** A natural raster-editor primitive still missing
after the brush (second slice) and its soft/hardness variant
(thirteenth slice). `src/editor/brush.py` adds `_erase_alpha(region,
weight)` -- reduces `region`'s alpha channel in place by a `[0, 1]`
coverage array (`new_alpha = alpha * (1 - weight)`); RGB is left
untouched. This needs its own compositing rather than reusing
`stamp_*` with a transparent color, since an "over" blend with a fully
transparent top color is a no-op, not an erase. New `erase_dot`/
`erase_line` share the same circular/falloff coverage
(`_circular_mask`/`_circular_falloff`) as the existing hard/soft brush,
with a `hardness` parameter mirroring `stamp_dot_soft`/`stamp_line_soft`.
Mask painting is unaffected and has no eraser variant -- painting a
mask to 0 already *is* erasing it. `LayerCanvas` accepts `"eraser"` as
a third explicit tool (alongside `"pan"`/`"brush"`), sharing the Brush
tool's `NoDrag` mouse handling and the existing brush radius/hardness
controls, but calling `erase_dot`/`erase_line` instead of the
color-stamping functions. Mask mode ignores the Eraser tool selection
and keeps its own direct-overwrite mask painting either way.
`ReferenceColoringTab` adds an Eraser radio button next to the
existing Pan/Brush ones.

**Fifteenth slice (issue #39, In review pending a manual desktop-app
check): per-layer opacity and blend mode UI.** `LayerMeta.opacity`/
`blend_mode` have been part of `LayerStack.composite()` since the very
first slice (issue #25), but there was never any UI to set either --
every layer was stuck at opacity 1.0 and blend mode "normal".
`LayerListPanel` gains an Opacity spin box (`0.0`-`1.0`, step `0.05`)
and a Blend Mode combo (populated from `editor.VALID_BLEND_MODES`,
newly exported from `editor/__init__.py`), shown below the existing
mask buttons. Both reflect the *selected* layer's current values --
updated on every selection change, on `set_layer_stack`, and on
`refresh()` (so undo/redo stays in sync) -- and are disabled when
nothing is selected. Changing either edits the selected layer's
`LayerMeta` in place, records an undo checkpoint first (reusing
`LayerStack.save_state()`/`load_state()`, which already round-trip
opacity/blend mode, so undo/redo needed no changes), and emits the
existing `layers_changed` signal so the bound canvas re-renders.
