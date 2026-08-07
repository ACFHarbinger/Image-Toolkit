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
4. 🔄 Assisted correspondence with confidence and correction learning.
   Issue #24 (In review) implements deterministic confidence scoring, a
   multiplicative-weights correction-learning step, and the Character
   Colors Docker's confidence-ranked "Canonical material" dropdown.
5. Optional generative proposals through the local model registry.
6. 🔄 Batch chapter workflow with review queue and recoverable checkpoints.
   Issue #22 (In review) implements the portable schema plus a Chapter Queue
   Docker: bind a project, add pages, open the next pending page, and mark
   pages reviewed/accepted. The offline/CLI batch-tool execution path
   remains a separate future slice.

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
discard count. `_report_adjacency` and Character Colors' adjacency-suggested
defaults (C4.1) now share one `region_labels_and_names` scan in
`segmentation_masks.py` rather than two independent copies; `_segment_regions`
buckets pixels into per-region buffers in one pass instead of rescanning the
full label array once per region. Issue #23 (Backlog) tracks a real but
deferred finding from the same review: every Docker action across the
plugin runs synchronously on Krita's UI thread, freezing it during heavy
work; fixing this needs a plugin-wide async architecture decision, not a
scoped patch to one Docker.

## Milestone 6 — batch chapter workflow

Issue #22 is In progress. A chapter is a project-scoped ordered list of
pages (`ChapterPage`: id, a safe relative `document_asset`, the existing
`RegionCorrespondence` `panel_id` field so every page's correspondences
share one `CorrespondenceSet` without regions colliding across pages, a
review `PageStatus` of pending/in_progress/reviewed/accepted, and optional
notes). Deliberately execution-agnostic: this only tracks queue position
and status, never how a page reached it, so the same schema serves both an
artist working through pages interactively in Krita today and a future
offline batch tool without rework. Per the owner's explicit scoping
decisions: no cross-page correspondence inference (every page's
`CorrespondenceSet` stays independent, matching C4's existing per-panel
design exactly); status transitions are artist-controlled rather than a
fixed state machine, matching the "artist remains in control" principle.

`add_chapter_page` validates the document asset exists (safe relative path,
existing regular non-symlink file, same `_resolve_project_asset` check style
bibles and correspondence sets already use) and appends to the queue.
`set_chapter_page_status` is explicit and idempotent, matching
`set_attempt_completion`'s pattern. `next_pending_chapter_page` returns the
first not-yet-accepted page in queue order -- the actual "resume where you
left off" mechanic a review queue needs. Project schema v12 adds
`chapter_pages` with unique-id/unique-asset/unique-panel-id validation.
Privacy-safe `project_progress_snapshot` includes a `chapter` section (page
list plus the next pending page id). Wired through the engine protocol and
Krita `EngineClient`; matching every prior milestone's "portable contract
first" sequencing (C1 before C3's Docker, C4 before its Docker).

A new **Chapter Queue** Docker (separate from the other three, same
one-concern-per-Docker pattern) now exposes the interactive path: **Bind
Portable Project**, **Add Page to Chapter** (file-picks an existing page
already inside the project, asks for a panel id), **Open Next Pending
Page** (opens the queue's first not-yet-accepted page via
`Krita.openDocument`/`window.addView`, marking it in-progress), **Mark
Active Page Reviewed/Accepted** (matches the active document's file path
back to its chapter-page record), and **Refresh Queue**. A proactive code
review before shipping found and fixed a real cross-platform bug:
`_relative_to_project` used `str(Path(...).relative_to(...))`, which
yields backslash-separated paths on Windows that the engine's POSIX-only
asset validation always rejects and that can never match the
POSIX-stored `document_asset` when matching the active document back to
its page record; fixed to use `.as_posix()`. The offline/CLI batch-tool
execution path remains a separate future slice on the same schema.

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

## Milestone 4 — assisted correspondence: confidence and correction learning

Issue #24 is In review pending a live Krita checklist. The portable contract
landed first (following the same sequencing as C1-C4/C4.1 and milestone 6's
schema-only first slice), and the Character Colors Docker now consumes it.

`colorization/confidence.py` adds two deterministic, stateless signals:
`name_similarity` (Jaccard token similarity between a region id and a
material's id/aliases, e.g. `hair-front-large` vs. `hair`) and
`score_candidate` (a weighted sum of that name signal and the adjacency
agreement C4.1's material-default suggestion already computes). Neither
signal nor their combination is a trained model — this is the explicit
"deterministic first, ML later" scoping decision, not a placeholder for one.

`project/model.py`'s new `SignalWeights` (schema v13; v12 payloads migrate to
an even 50/50 split) holds the two signal weights plus an `update_count`,
project-scoped rather than portable since it reflects one artist's own
naming and workflow conventions, not a shareable asset. `project/service.py`
adds `rank_correspondence_materials` (ranks a bound style bible's materials
for one target region using the project's current weights, returning the
adjacency/name/confidence breakdown per candidate so it can be replayed
later) and `record_correspondence_choice` (the "correction learning" step:
an online multiplicative-weights update — whichever signal's own top pick
matched what the artist actually chose gets boosted, the other decays,
weights renormalize to sum to one). Fewer than two real candidates, or a
chosen id absent from them, is a no-op — there is nothing to learn from an
assignment with no real alternative. Neither function ever assigns anything;
both exist purely to feed a future Docker's ranked suggestion list, with
assignment remaining an explicit artist action exactly like C4/C4.1.

`learning/engine_protocol.py` and the Krita `engine_client.py` wire
`rank_correspondence_materials`/`record_correspondence_choice` through the
existing JSON-RPC transport, matching every other milestone's engine-boundary
pattern. Per the owner's explicit constraint, any future learned signal added
to this same weighted-signal framework must be fully offline/local and go
through the existing local model registry — never a network call, never
outside that registry.

**Character Colors Docker integration.** `_assign_correspondence`'s
"Canonical material" dropdown is now ordered by confidence rather than only
defaulting one index: it first computes a per-material adjacency-agreement
fraction (`_adjacency_agreement_by_material`, new — how many of the target
region's adjacent regions are already assigned to each candidate material,
out of all adjacent regions, generalizing C4.1's unanimous-or-nothing
`_suggested_material_index` into a `[0, 1]` score per material) and calls
the engine's `rank_correspondence_materials` to order the whole dropdown by
combined confidence, not just its default selection. If the engine call
fails for any reason (offline hiccup, unbound bible), assignment still
works: the dropdown falls back to the bible's declared material order with
`_suggested_material_index`'s old unanimous-adjacency default index,
exactly as it behaved before this milestone. After a successful save, the
Docker calls `record_correspondence_choice` with the exact ranked list the
artist chose from, so the project's `SignalWeights` learn from every
explicit assignment; a learning-update failure is swallowed rather than
surfaced, since the assignment itself already succeeded and correction
learning is feedback, not a requirement. Never auto-assigns anything — the
dropdown remains fully editable, matching every other milestone's decision
boundary.
