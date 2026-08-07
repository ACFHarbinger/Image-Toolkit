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

**Status: complete.** The next implementation milestone is A2.

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
- ✅ Local model registry with built-in/community/unverified labels, atomic
  persistence, and non-executing manifest, path, size, symlink, and SHA-256
  validation. Integrity and provenance remain explicitly separate.

### A2 — lesson and overlay vertical slice

**Status:** deployed lesson/review slice is in owner-deferred review in issue
#10; suggestion decisions and persistence continue in issue #11.

- 🔄 One front-view construction lesson with locally packaged explanations;
  the five-stage beginner lesson is deployed.
- 🔄 Exercise template creation in Krita; the tested adapter creates an unsaved
  1600 × 2000 document with separate construction, artwork, and locked tutor
  feedback layers. Live host verification remains.
- 🔄 Manual landmark placement and deterministic review; the host-neutral core
  now validates normalized artist-confirmed landmarks and measures centerline,
  eye-line, chin centering, and jaw symmetry. A versioned bounded JSON process
  protocol and defensive Krita client now cross the AppImage/engine boundary
  without imports or shell execution. A projection-snapshot editor collects nine
  ordered points with undo/reset and derives normalized review landmarks without
  private canvas internals. Atomic XDG engine configuration and review submission
  now display the returned explanations; redline rendering remains.
- 🔄 Structured redline layers and configurable accept/reject interaction. The
  Krita 5.x adapter rasterizes validated normalized geometry into a new locked
  tutor-owned preview without touching artwork. Explicit idempotent buttons
  accept it as a locked reference or reject only the owned preview. Unique
  shortcuts are opt-in and atomically persisted; none is assigned by default
  because Tab belongs to Krita. Failed decision persistence retains a same-action
  retry state and blocks the opposite decision. Owner review remains in #11.
- 🔄 Save, reload, migration, and failure recovery: portable schema v4 persists
  privacy-safe review versions, measurements, explanations, and final decisions
  plus one final structured advice rating and optional local note, with
  deterministic v0/v1/v2/v3 migration and recovery coverage. Project-local
  learning retention is a setting enabled by default; artwork history and
  global aggregation remain independently disabled by default. The Krita adapter
  now binds an empty directory to `project.json` plus
  `artwork/attempt-001.kra`, and engine operations atomically record the review
  and decision. Automated implementation is complete; live verification is
  owner-deferred in issues #10 and #11.

### A3 — curriculum and adaptive remediation

**Status: in progress — issue #12.** Core work proceeds while A2 owner checks
remain deferred in Review.

- 🔄 Curriculum v1 content: the versioned core catalog now defines all nine
  primary anime head-and-face exercises plus four focused remedial exercises.
  The front-construction and head-orientation lessons are fully authored. Head
  orientation includes spatial theory, seven construction stages, three drills,
  five diagnosed common mistakes, measurable completion criteria, self-review,
  and delayed repetition. Remaining lessons, rich media, and multi-lesson Krita
  content remain; each lesson will be authored fully rather than stubbed. The
  existing docker now provides an ordered selector, Previous/Next navigation,
  and selectable scalable SVG diagrams for authored lessons without locking
  later content.
- 🔄 Head-orientation exercise template: the docker creates a 2600 × 1600
  landscape rotation sheet with five labeled work areas and separate layers for
  left profile, left three-quarter, front, right three-quarter, and right
  profile. The locked vector layout is separate from artist layers. The active
  named layer selects one head, the docker asks for confirmation, and the dialog
  crops to that work area. Profiles and three-quarter views have distinct manual
  landmark prompts and deterministic review contracts. Provisional tolerances
  still require calibration with real beginner drawings; front orientation uses
  the separately calibrated front workflow rather than pretending all views
  share evidence.
- ✅ Prerequisites control only the recommended next exercise. All lesson
  content remains browsable so the tutor never turns progression into a lock.
- ✅ Completion is an explicit, reversible artist action after consulting the
  checklist. Review evidence is shown separately and never auto-completes an
  exercise; repeated identical marks are idempotent and atomically persisted.
- ✅ Completing the front attempt changes the engine's recommended next
  exercise to head orientation immediately. This recommendation is displayed in
  Project Progress and does not change the manually selected lesson.
- 🔄 Rubrics for all supported views: stable normalized dimensions now cover
  axes, jaw/chin structure, perspective compression, feature placement, and
  value grouping. Profile and three-quarter evaluators now measure centerline
  placement, far-side compression/depth, chin alignment, cross-contour
  consistency, jaw attachment, and preserved cranial volume. Their provisional
  thresholds remain explicitly uncalibrated pending owner/beginner evidence.
- ✅ Deterministic prerequisite progression and explainable
  weakness-to-remedial-exercise routing, including stable tie-breaking and
  explicit treatment of missing evidence as unknown rather than failure.
- 🔄 Progress dashboard comparing attempts without ranking the artist globally:
  the core now reports improved, unchanged, and declined dimensions only for
  matching exercise, method, and rubric versions. It also reports retry count,
  unrated advice, and the number of incompatible pairs it intentionally skipped.
  Project persistence is complete. The existing tutor docker now shows attempts,
  reviews, latest compatible improvement/decline trends, and optionally raw
  normalized values. Raw values default visible and the preference is atomic.
  Live host presentation remains unverified.
- 🔄 Feedback reporting for incorrect or unhelpful advice: the private summary
  distinguishes helpful, unhelpful, incorrect, not-applicable, and unrated
  reviews, rejects contradictory classifications, and creates no aggregate
  artist score. Schema v4 persists an editable classification and optional note
  directly in each portable project with atomic recovery. Revision-history
  retention is configurable and defaults off; the note limit is configurable
  from 1 to 100,000 characters and defaults to 2,000. Rating/note controls and
  policy settings now live in the existing docker; live confirmation remains.
- 🔄 Retention controls live in the existing tutor docker. Users may keep
  retention enabled, explicitly clear history and disable it, or re-enable it;
  a project with history cannot be disabled through the engine without the
  explicit clear flag. Live host confirmation remains.

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
