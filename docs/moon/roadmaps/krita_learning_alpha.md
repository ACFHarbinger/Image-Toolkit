# Krita Anime Head-and-Face Learning Alpha

## Goal

Help a returning complete beginner measurably improve anime head-and-face
construction through a fixed curriculum with adaptive remedial exercises. The
alpha runs offline on Kubuntu/KDE inside Krita and analyzes work only when the
artist requests a review.

## Non-goals

- A complete standalone drawing application.
- Full-body anatomy, finished illustration, animation, or game-asset courses.
- Continuous surveillance or unsolicited live critique.
- Replacing the drawing with model output.
- Supporting multiple construction schools in the first release.
- Accounts, cloud sync, browser, or mobile clients.

## Learning method

Start with one documented construction method so lessons and evaluation share
consistent assumptions. Preserve the method identifier and rubric version in
every exercise result so additional styles can be added later without making
old progress incomparable.

The fixed curriculum establishes progression; adaptive exercises target a
weakness detected during review. Explanations may include text, diagrams,
step-by-step overlays, animated demonstrations, examples, and links between
related concepts. Media is packaged locally.

## Curriculum v1

1. Circle, jaw, centerline, and eye-line construction.
2. Front, profile, and three-quarter head orientation.
3. Cranial volume and jaw variation without losing perspective.
4. Eye placement, scale, and perspective compression.
5. Nose, mouth, ear, and hairline placement.
6. Intentional symmetry and asymmetry.
7. Feature variation while retaining construction.
8. Simple value grouping and two-tone cel-shaded lighting on the head.
9. Review exercise combining construction, features, and simple shading.

## Review contract

Each review returns structured evidence rather than a single opaque score:

- observation and affected region;
- confidence and evidence source (`geometry`, `heuristic`, or `model`);
- explanation of the underlying art principle;
- redline geometry on separate named Krita layers;
- one or more non-destructive suggestions where appropriate;
- a targeted exercise and completion criterion;
- rubric measurements that can be compared with later attempts.

Low-confidence feedback must say so. The artist can mark advice as helpful,
incorrect, or not applicable; that feedback is retained locally only when
progress storage is enabled.

## Krita interaction

- A lesson docker shows the current step, references, demonstrations, and
  completion checklist.
- “Review” captures the selected exercise layer plus declared construction
  metadata and submits an immutable analysis job.
- Results appear as togglable redline, construction, annotation, and suggestion
  layers grouped above the artist's work.
- Suggestions are previews until accepted. Accept/reject/cycle shortcuts are
  configurable and acceptance becomes one undoable document command.
- No artwork is stored in progress history unless separately opted in. By
  default, retain rubric values, exercise/version identifiers, timestamps, and
  artist feedback without image content.

## Analysis avenues

Implement these behind a shared result schema and compare them empirically:

1. **Deterministic geometry:** user-assisted or detected landmarks, ellipse and
   centerline fitting, ratios, symmetry, perspective consistency, and angle
   relationships. Most explainable and suitable for early lessons.
2. **Learned landmark analysis:** a locally deployed line-art/keypoint model
   proposes construction landmarks and confidence. The artist can correct the
   landmarks before accepting the critique.
3. **Vision-language critique:** optional later model generates richer
   explanations from rubric measurements and cropped evidence. It may not be
   the sole source of geometry claims.
4. **Reference comparison:** compare against lesson exemplars using aligned
   landmarks and structural features, never raw pixel similarity alone.

Begin with deterministic geometry plus explicit artist landmark correction.
This yields auditable feedback before enough suitable data exists for a robust
anime-specific evaluator.

## Progress measurement

The primary experiment is repeated-attempt improvement:

1. Complete a baseline attempt without corrective overlay.
2. Request review and consume the explanation.
3. Complete a targeted remedial exercise.
4. Redraw the original prompt without tracing the correction.
5. Compare rubric changes and ask the artist whether the explanation helped.

Candidate rubric dimensions include head-axis consistency, feature placement,
perspective compression, cranial/jaw proportion, construction-line use, and
value grouping. Rubric calibration needs human review; numerical precision is
not evidence of pedagogical validity.

## Delivery milestones

### A1 — plugin skeleton and local data model

- ✅ Krita 5.2+ and Python 3.10+ documented for Kubuntu. The inspected Krita
  5.2.11 Snap omits Python plugin support and is explicitly rejected. The
  checksum-verified official Krita 5.3.2.1 AppImage contains `pykrita`, Scripter,
  and the plugin importer; the plugin was enabled and its docker displayed in a
  live session. Krita disables all docker actions until a document is open, an
  important discovery note for the onboarding flow.
- ✅ Scoped install/uninstall tooling and privacy-safe plugin self-diagnostics.
- ✅ Versioned lesson, exercise, rubric, review, and progress schemas with
  atomic catalog persistence, deterministic v0 migration, and future-version
  rejection.
- ✅ Opt-in settings contracts for progress, artwork retention, and model use.
- 🔄 Local model registry with built-in/community/unverified labels and atomic
  persistence; model-package content validation remains.

### A2 — lesson and overlay vertical slice

- One front-view construction lesson with locally packaged explanations.
- Exercise template creation in Krita.
- Manual landmark placement and deterministic review.
- Structured redline layers and configurable accept/reject interaction.
- Save, reload, migration, and failure recovery tests.

### A3 — curriculum and adaptive remediation

- Curriculum v1 content.
- Rubrics for all supported views.
- Weakness-to-remedial-exercise routing.
- Progress dashboard comparing attempts without ranking the artist globally.
- Feedback reporting for incorrect or unhelpful advice.

### A4 — evaluator assistance and alpha study

- Optional local landmark model with confidence visualization.
- RTX 4080 12 GB as the deployment ceiling for the default model; the RTX 3090
  Ti 24 GB may be used for development but not as the minimum requirement.
- Latency, VRAM, correctness, and explanation-quality evaluation.
- Small beginner study using repeated attempts.

## Alpha release gates

- Fresh Kubuntu/Krita installation succeeds from documented steps.
- All analysis works offline after explicit model/content installation.
- Median requested review reaches an interactive target defined by benchmarks;
  cancellation never corrupts the Krita document.
- Advice has region-level evidence and uncertainty, and can be reported.
- Participants show improvement on held-out repeat prompts more often than an
  agreed baseline and rate explanations as useful.
- No suggestion modifies original artwork without acceptance; every accepted
  operation is undoable.

Exact numerical thresholds must be chosen during A2 after a pilot establishes
honest baselines, rather than invented in advance.
