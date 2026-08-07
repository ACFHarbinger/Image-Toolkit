# Reference-Consistent Character Coloring Roadmap

## Outcome

After the learning alpha, color black-and-white manga or line art consistently
from reusable character references while minimizing correction time and
preserving artist control.

## Core workflow

1. Create a character style bible from one or more reference views.
2. Define named regions/materials such as skin, hair, eyes, clothes, and
   accessories with local-color and lighting palettes.
3. Segment a target drawing into editable regions.
4. Propose region correspondences and colors with confidence.
5. Correct ambiguous matches once and propagate those corrections.
6. Preview, accept, reject, or repaint individual regions.

## Implementation avenues

- **Deterministic:** trapped-ball filling, gap closing, region adjacency graphs,
  palette constraints, user-authored correspondences, and graph optimization.
- **Hybrid:** learned segmentation/dense features propose correspondences;
  deterministic boundaries and palette constraints produce the editable result.
- **Generative:** locally installed reference-guided diffusion proposes missing
  content or shading, reviewed per region and never treated as ground truth.

The existing optimal-transport implementation remains a lightweight
palette/structure-transfer baseline. Gabor features, scribble propagation, and
incremental solving remain experimental components. Promotion requires tests
against pose changes, occlusions, repeated characters, screentones, open gaps,
and user corrections.

## Quality measures

- Time and actions required to reach an acceptable result.
- Region leakage and missed-region rate.
- Character material/palette consistency across pages.
- Correction reuse across subsequent panels.
- Artist acceptance rate per proposed region.
- Peak RAM/VRAM and preview/final latency at representative resolutions.

## Milestones

1. ✅ Editable segmentation and gap-repair tools in Krita. G1 issue #19
   (Done — live Krita checklist passed) implements the deterministic
   baseline plus a Line Art Segmentation Docker: bounded gap closing,
   single-radius trapped-ball-style region segmentation into renamable
   layers, dust-speck filtering, and a region-adjacency report.
2. ✅ Versioned character style-bible format and palette application.
   Issue #15 implements the standalone foundation: semantic materials,
   unambiguous aliases, explicit local/light/shadow/optional-accent sRGB roles,
   safe relative reference views, strict future-version refusal, atomic writes,
   and bounded recovery. C2 issue #16 adds portable project schema-v9 bindings,
   validated attach/detach operations, constrained-host summaries, and recovery
   without deleting assets. C3 issue #17 (Done — live Krita checklist passed)
   adds the Character Colors Docker: authoring, material masks/variants,
   overlap-safe palette-role preview, and accept/reject.
3. ✅ Manual correspondence workflow and deterministic propagation baseline.
   C4 issue #18 (Done — live Krita checklist passed) adds region-to-material
   assignment, explicit-target propagation, and preview/accept/reject in the
   same Character Colors Docker.
4. Assisted correspondence with confidence and correction learning.
5. Optional generative proposals through the local model registry.
6. Batch chapter workflow with review queue and recoverable checkpoints.

## G1 — segmentation and gap-repair baseline

Issue #19 is **Done** — the live Krita checklist passed.
`src/colorization/segmentation.py` provides the deterministic algorithm
baseline named in milestone 1: `close_line_gaps` bridges hand-drawn ink gaps
up to a bounded pixel radius via morphological closing; `segment_regions`
flood-fills the gap-closed background into labeled regions, excluding any
region that still touches the canvas border (not yet enclosed by a drawn
boundary); `region_adjacency` returns the touching-label pairs the roadmap's
region-adjacency-graph avenue calls for; and `region_statistics` reports
per-region area, centroid, and bounding box. The fill is deliberately
single-radius rather than the roadmap's full multi-radius trapped-ball
technique — documented in the module as the first-pass narrowing, upgradeable
later without changing the label/adjacency/statistics contract downstream
callers use.

A new **Line Art Segmentation** Docker (separate from Character Colors,
mirroring how C3 got its own Docker) exposes the same algorithm through a
pure-Python, numpy-free `segmentation_masks.py` adapter — the engine's small
JSON-RPC transport is unsuited to full-resolution pixel payloads, so this
mirrors `color_masks.py`/`value_masks.py`'s existing pattern of operating on
Krita layer bytes in-process rather than round-tripping through the engine
subprocess. **Close Line Art Gaps**, **Segment Regions into Layers**, and
**Report Region Adjacency** create inspectable/renamable layers directly;
region layers a reviewer renames become the region ids C4's **Assign Region
Correspondence** action reads by layer name. Segmentation now takes an artist-chosen minimum region area and discards
dust-speck regions below it (`filter_small_regions`, implemented in both the
numpy engine module and the pure-Python Krita adapter), reporting the
discard count.

## C4 — deterministic manual correspondence baseline

Issue #18 is **Done** — the live Krita checklist passed. The first slice is a standalone
`CorrespondenceSet`/`RegionCorrespondence` contract (`src/colorization/correspondence.py`),
deliberately portable like the C1 style bible: it stores region/material/role
identifiers and optional panel identity only, never pixels, embeddings, or
inferred identity. A region cannot resolve to two different materials within
the same panel context; that ambiguity is refused rather than guessed.
Explicit propagation copies an accepted assignment onto artist-selected target
regions only — it never discovers regions on its own — and refuses to
overwrite a target that already carries a competing assignment. Saves are
atomic with bounded JSON recovery, matching the style-bible persistence
pattern.

Project schema v10 adds portable `correspondence_set_assets` bindings,
mirroring C2's style-bible attach/detach/upsert/read operations exactly:
`attach_correspondence_set`, `detach_correspondence_set`,
`upsert_project_correspondence_set`, `project_correspondence_set_payload`,
and an explicit `propagate_project_correspondence` service call that loads
the bound set, applies `CorrespondenceSet.propagate`, and saves the result
with recovery. Privacy-safe project-progress summaries expose correspondence
identity and counts without pixels. The engine protocol and Krita
`EngineClient` expose all five operations.

The Character Colors Docker now exposes the manual workflow directly:
**Assign Region Correspondence** derives a region id from the active layer's
name and records an artist-chosen material/role/optional-panel assignment,
refusing to silently overwrite a competing assignment for the same region.
**Propagate Correspondence to Regions** applies an existing assignment onto
explicit comma-separated target region ids only. **Preview Region
Correspondence Color** resolves the assigned material/role to a locked
preview under `Character Colors`, sharing the same accept/reject and
single-owned-preview machinery as C3's palette-role preview (refactored into
a shared `_create_preview_layer` helper). The manual-assignment/propagation/
preview/accept-reject checklist passed live in Krita.

### C4.1 — adjacency-suggested defaults

Issue #21 is In review pending the live-Krita checklist. Now that both G1
(segmentation/adjacency) and C4 (correspondence/propagation) are
independently verified, the Character Colors Docker connects them in two
places, neither ever auto-applying anything:

- **Propagate Correspondence to Regions** reads G1's `Regions` group the
  same way the Line Art Segmentation Docker's Report Region Adjacency action
  does, and pre-fills the target-region-ids field with the names of regions
  touching the source assignment's region — a suggestion the artist can
  edit, extend, or clear before confirming.
- **Assign Region Correspondence**'s material dropdown now defaults to the
  material already assigned to an adjacent region, but only when adjacent
  regions unanimously agree on exactly one material; disagreement, no
  adjacency, or a suggested material no longer in the bible all fall back to
  the first material in the dropdown, same as before this issue.

Both fall back to prior behavior when no `Regions` group exists, so this
remains additive and never a required dependency on G1.
`CharacterColorsDocker._adjacent_region_names` and `_suggested_material_index`
are headlessly tested against a fake Krita node/document (touching-only
suggestion, no-group fallback, unknown-source fallback, unanimous vs.
disagreeing adjacent materials, unknown suggested material).

The format is a standalone contract first and a project asset second. It stores
artist-authored semantic color facts, not image pixels, embeddings, inferred
identity, or model output. This lets deterministic segmentation, optional ML,
Blender export, and a future C++ engine consume the same reviewed data. JSON is
preferred for this small Git-friendly manifest; large binary assets remain
adjacent referenced files.

The portable-project binding is implemented. Next slices should provide a Krita
material/palette editor, then apply named palettes to explicit region masks
before attempting learned correspondence.

C3 issue #17 is **Done** — the live Krita checklist passed. It shipped a
separate Character Colors Docker, `Material Masks/Material — <canonical-id>`
alpha layers, and collision-safe project-local reference copies. Bibles are
authored and bound through the engine; missing semantic masks are created;
one explicit palette role at a time is previewed as a separate locked
preview with accept/reject. Accepted colors remain separate editable
`Color — <canonical-id> — <role>` layers inside one `Character Colors`
group. Any material-mask overlap blocks preview and reports per-material
conflict pixels instead of silently applying z-order. Materials may be split
into named variants (`Material — hair — front`, `Material — hair — back`)
that share one canonical palette; variants are unioned before conflict
checks. Reference labels, controlled view types, and notes are editable.
Accepted layers carry the style-bible ID in host metadata when available.
The Docker exposes variant creation directly, including duplicate-name
refusal. Existing bibles reopen prefilled for editing, including aliases,
optional accent roles, and preserved reference views.
Schema v2 deterministically migrates v1 references to `other` without guessing.
Absent accents are not offered as preview roles.
Failed layer creation/write/removal is visible and cleans partial previews.
A proactive code review (before the live pass) found and fixed one
inconsistency: mask-layer creation now checks Krita's node-creation return
values, matching every sibling creation path.
The offline review procedure is mirrored in `integrations/krita/README.md` so a
reviewer can follow it without relying on issue comments.
Learned correspondence is still a later milestone (milestone 4).
