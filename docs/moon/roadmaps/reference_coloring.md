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

1. Editable segmentation and gap-repair tools in Krita.
2. 🔄 Versioned character style-bible format and palette application.
   Issue #15 implements the standalone v1 foundation: semantic materials,
   unambiguous aliases, explicit local/light/shadow/optional-accent sRGB roles,
   safe relative reference views, strict future-version refusal, atomic writes,
   and bounded recovery. C2 issue #16 adds portable project schema-v9 bindings,
   validated attach/detach operations, constrained-host summaries, and recovery
   without deleting assets. Krita authoring and palette application remain.
3. Manual correspondence workflow and deterministic propagation baseline.
4. Assisted correspondence with confidence and correction learning.
5. Optional generative proposals through the local model registry.
6. Batch chapter workflow with review queue and recoverable checkpoints.

## C1 — portable style-bible foundation

The format is a standalone contract first and a project asset second. It stores
artist-authored semantic color facts, not image pixels, embeddings, inferred
identity, or model output. This lets deterministic segmentation, optional ML,
Blender export, and a future C++ engine consume the same reviewed data. JSON is
preferred for this small Git-friendly manifest; large binary assets remain
adjacent referenced files.

The portable-project binding is implemented. Next slices should provide a Krita
material/palette editor, then apply named palettes to explicit region masks
before attempting learned correspondence.

C3 issue #17 is In Progress with the approved boundary: a separate Character
Colors Docker, `Material Masks/Material — <canonical-id>` alpha layers, and
collision-safe project-local reference copies. The first headless slice authors
and binds bibles through the engine, creates missing semantic masks, and previews
one explicit palette role as a separate locked layer with accept/reject. Live
Krita confirmation, editing existing bibles without re-entering fields, aliases,
optional accent UI, and stronger undo/reconciliation evidence remain. Learned
correspondence is still a later milestone.
