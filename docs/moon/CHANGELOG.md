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

### Added

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
- Added `docs/website/` — a Vue 3 + Vite documentation site (same design as Image-Toolkit's own) rendering every `docs/**/*.md` directly, nav/search generated from this repo's own `docs/mkdocs.yml`. Includes a "Related Projects" sidebar section embedding Image-Toolkit's and Anime-Stitch-Pipeline's own docs sites via iframe. Deployed alongside the MkDocs portal in CI (`.github/workflows/docs.yml` + Forgejo/Gitea/GitLab mirrors) at `/app/`.
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
