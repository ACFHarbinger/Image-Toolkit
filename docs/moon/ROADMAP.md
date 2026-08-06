# Cel-Shaded-Generator Product Roadmap

## Product direction

Cel-Shaded-Generator is an offline-first assistant for learning and producing
anime-style art, cel-shaded animation, manga colorization, and game assets. It
must augment the artist rather than silently replace their work: generated
changes are previews until explicitly accepted, every accepted change is
undoable, and automation can be reduced or disabled in settings.

The first user is a returning complete beginner. The first supported platform
is Linux (Kubuntu/KDE), initially as a Krita plugin. Browser and mobile clients
are not current requirements. The long-term product may become a standalone
desktop editor, but it must earn that expansion with a polished narrow alpha.

## Product principles

1. **Teach, do not merely score.** Feedback explains what was observed, why it
   matters, how to correct it, and what exercise should come next.
2. **Measure learning.** Success means repeated attempts improve, not that a
   model produces an attractive replacement image.
3. **Artist remains in control.** Analysis is on demand in the alpha. Redlines
   and suggestions live on separate layers and require explicit acceptance.
4. **Local and offline by default.** Core workflows run without an account or
   network connection. Model installation is explicit and never silent.
5. **Open model ecosystem.** Built-in models are documented and validated, but
   users may install arbitrary community or local models with clear trust and
   license metadata.
6. **Standalone boundaries.** Image-Toolkit integration is an adapter; the core
   engine, project model, and Krita plugin may not depend on Image-Toolkit
   internals.
7. **Prototype before porting.** Python remains useful for research. Proven,
   profiled kernels and stable domain services migrate to a long-term C++
   engine.

## Roadmap at a glance

| Phase | Outcome | Status |
| --- | --- | --- |
| 0 | Truthful, installable standalone foundation | In progress |
| 1 | Krita anime head-and-face learning alpha | Planned |
| 2 | Reference-consistent character coloring | Planned |
| 3 | Anime frame-by-frame animation assistance | Deferred |
| 4 | 2D and 3D game-asset workflows | Deferred |
| 5 | Standalone professional desktop application | Conditional |
| 6 | Tablet/mobile editing | Far future |

## Phase 0 — standalone foundation

This phase blocks the alpha. It is intentionally about product integrity, not
new algorithms.

- Replace template-era README, contributing, agent, benchmark,
  and setup documentation with the real project state.
- ✅ Replace the placeholder architecture document with the real current and
  target boundaries.
- ✅ Adopt conventional `cel_shaded_generator` and
  `cel_shaded_generator_gui` packages; remove dynamic alias bootstrapping.
- ✅ Remove imports from `backend.src.*` and the parent `gui.src.*` package.
- ✅ Make the current GUI an explicit workspace client of the core package.
- ✅ Run core and headless GUI tests in CI, build both wheels, and smoke-test
  the installed packages and desktop composition in a clean environment.
- ✅ Define a versioned local project/exercise/progress data model, portable
  project folders, bounded multi-revision autosave, opt-in artwork retention,
  separate global learner profiles, and deterministic migration policy.
- ✅ Establish deterministic synthetic correctness fixtures, committed goldens,
  anonymized latency/Python-memory baselines, and a separate manual benchmark
  workflow. Add real-art perceptual fixtures and native/GPU memory capture as
  their respective workloads land; current data does not justify a C++ port.
- 🔄 Contain native-library crashes behind spawned, killable workers with
  adaptive user-capped timeouts, cancellation, restart-on-next-job behavior,
  and metadata-only local diagnostics. Core boundary complete; GUI/Krita
  routing and measured overhead remain before removing the compatibility lock.
  Persistent ARAP lifecycle and Qt mesh-editor routing are complete; measured
  warm overhead is negligible on the initial baseline. Batch Qt workers remain.

**Exit gate:** a new Kubuntu environment can install, launch, and exercise the
core without an Image-Toolkit checkout or undocumented imports.

## Phase 1 — Krita learning alpha

The first curriculum teaches one consistent anime head-and-face construction
method. See [Krita Learning Alpha](roadmaps/krita_learning_alpha.md).

The complete loop is: lesson → guided exercise → draw in Krita → request review
→ receive explanation and redline → preview a suggestion → accept/reject →
repeat → compare progress.

**Exit gate:** a small beginner study demonstrates both improved repeated
attempts and useful explanations. Feature count alone cannot satisfy this gate.

## Phase 2 — reference-consistent coloring

Build a character style bible and correction-oriented coloring workflow after
the learning loop is polished. See
[Reference-Consistent Coloring](roadmaps/reference_coloring.md).

The existing scribble, Gabor, optimal-transport, graph-cut, quadtree, and
preference-log modules remain experimental baselines. Their mathematical
claims, numerical behavior, output quality, and correction time must be
benchmarked before promotion to user-facing production tools.

## Phase 3 — anime animation assistance

Target the Japanese animation workflow: storyboard/layout, key poses,
breakdowns, inbetweens, cleanup, color, shading, and compositing. The initial
emphasis is frame-by-frame limited animation rather than mesh puppeteering.
See [Anime Animation](roadmaps/anime_animation.md).

The existing 3D same-coordinate propagation and binary graph-cut refinement
are research baselines, not a production temporal pipeline. Motion-aware
correspondence and occlusion handling are prerequisites.

## Phase 4 — game assets

Provide separate 2D and Blender-centered 3D workflows, with Unity and Unreal
interchange as the first engine integrations. See
[Game Assets](roadmaps/game_assets.md).

## Phase 5 — standalone desktop editor

This phase is conditional. Reassess only after the Krita plugin proves which
workflows require ownership of the canvas, document model, rendering engine,
or timeline. The likely architecture is a C++ engine, GPU-backed canvas, and
isolated Python research/model workers; its staged boundary and migration gates
are defined in the [Engine Architecture Roadmap](roadmaps/engine_architecture.md).
Browser support is not a justification for choosing the desktop architecture.

## Deferred clients

- Freeze the Tauri frontend scaffold; do not build a second incomplete UI.
- Freeze Android and iOS scaffolds.
- If mobile resumes, target full tablet editing rather than a review-only
  companion, after desktop document and engine contracts are stable.

## Automation levels

| Level | Behavior |
| --- | --- |
| Manual tools | Analysis and ML assistance disabled |
| Tutor only | Explanations and redlines; no modified-art preview |
| Suggest | Preview available only after an explicit review request |
| Guided assist | Suggestions may appear at suitable checkpoints |
| Batch assist | Multiple coloring/animation proposals queued for review |

All levels preserve the original, require acceptance before modifying artwork,
and use ordinary undoable Krita/application commands. The accept shortcut must
be configurable because Krita already assigns Tab to canvas-only mode.

## Evaluation hierarchy

1. Improvement between repeated attempts.
2. Helpfulness and correctness of teaching explanations.
3. Time and number of manual corrections required.
4. Interaction latency and stability.
5. Conventional image/model metrics, used only where they reflect the workflow.

## Licensing and model policy

The project remains AGPL-3.0 with a commercial licensing option. It should
publish provenance and license metadata for supplied models and datasets while
allowing users to install arbitrary local models. Unverified models must be
clearly distinguished from built-in validated packages.

## Decision record

This roadmap incorporates the product review and owner brainstorming of
2026-08-06. Data under `~/Downloads/Data` is explicitly out of scope until it
is separately inventoried; no roadmap assumption is based on its contents.
