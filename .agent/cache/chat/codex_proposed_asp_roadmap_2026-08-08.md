# Codex Proposed Roadmap for Anime Stitch Pipeline

**Date:** 2026-08-08  
**Author:** Codex  
**Status:** Proposal for comparison and joint synthesis; not the final roadmap  
**Planning style:** Capability-oriented  
**Primary platform:** Kubuntu (KDE on Ubuntu), CUDA-first with a useful CPU-only path  
**Primary near-term user:** Project owner, a few friends, and researchers  
**Later target audience:** People reconstructing panoramic anime wallpapers from video screenshots

---

## 1. Product Direction

Anime Stitch Pipeline (ASP) should become a local-first desktop application for reconstructing coherent, high-quality panoramic images from extracted anime video frames. It should minimize manual work while preserving an artist/researcher's ability to inspect, correct, and deliberately optimize the reconstruction.

The first production scope should prioritize vertical scrolling sequences. Horizontal scrolling should remain an active secondary capability. Diagonal motion, arbitrary mosaics, and more complex camera trajectories should remain visible future capabilities but must not delay a reliable vertical workflow.

ASP should be designed as a standalone application with a clean public interface. Image-Toolkit integration should be optional and thin. The minimum acceptable integration is a `Launch ASP App` action inside Image-Toolkit. Deeper in-process integration should occur only where it produces clear user value without restoring cross-repository coupling.

All core inference should run locally. An external or local model service may be supported as an optional alternative provider, but ASP must not require a service or network connection for its primary workflow.

The near-term application is a research tool rather than a commercial product. Licensing and redistribution constraints should still be recorded accurately, but research datasets and experimental models need not be packaged with ordinary builds. A more reliable, redistributable benchmark corpus should be acquired before commercial packaging becomes relevant.

---

## 2. Product Principles

### 2.1 Human-assisted product, automation-gated release

The primary user experience should optimize for the fastest reliable human-assisted result. HybridStitch should become the main workspace, and automated analysis should initialize editable project state.

However, production readiness remains gated by automatic stitching quality. Before a production milestone, ASP must match or exceed the OpenCV reference on nearly all benchmark cases with no human intervention beyond, at most, manual frame selection.

These goals are complementary:

- The editor makes the application useful while research continues.
- The automatic benchmark gate prevents the product from depending on extensive manual repair.
- Human intervention remains a safety and ambiguity mechanism, not a substitute for a poor automatic baseline.

### 2.2 Coherence before cosmetic quality

Structural coherence is the first invariant. Torn anatomy, duplicated content, phase-mixed characters, or incorrect ordering are disqualifying even if sharpness, coverage, or SSIM improve.

Recommended default priority:

1. structural coherence;
2. source fidelity;
3. correct ordering and geometry;
4. coverage;
5. seam and photometric continuity;
6. line-art sharpness;
7. runtime and memory.

Users should be able to choose alternative objective profiles, but no profile should permit known structural incoherence to be presented as a successful result.

### 2.3 Local-first and inspectable

- Core functionality works offline after required models are installed.
- Every generated or model-assisted operation is identifiable.
- Model versions, providers, settings, and source provenance are recorded.
- A CPU-only installation remains capable of useful classical stitching and manual editing.
- CUDA is the primary acceleration target in the near term.

### 2.4 Progressive control rather than hundreds of switches

The application should expose enough control to optimize for different goals, but not expose implementation flags directly to ordinary users.

Use three levels:

1. **Goal profiles:** Coherence, Fidelity, Coverage, Sharpness, Speed, and Custom.
2. **Meaningful controls:** source selection policy, phase strictness, crop policy, blend strength, fill policy, quality/runtime budget, and model/provider choice.
3. **Research controls:** low-level thresholds and experimental components, available only in a research/developer panel and recorded in the project.

Every control should explain:

- what it changes;
- which goal it helps;
- likely trade-offs;
- recommended range;
- whether it affects reproducibility;
- whether it is experimental.

### 2.5 Generative processing is explicit and optional

Generative background completion may fill small missing background regions only when the user enables an option such as `Generate missing background pixels`. It remains off by default.

Generated regions should be:

- marked in project provenance;
- viewable as an overlay;
- reversible without rerunning unrelated stages;
- constrained to missing background unless the user deliberately expands the scope;
- exported with metadata when the chosen output format supports it.

---

## 3. Provisional Production Gates

These thresholds are proposed for discussion and should be ratified in the final joint roadmap.

### 3.1 Automatic quality gate

On the agreed benchmark corpus:

- At least **95 of 97** cases are human-rated equal to or better than the OpenCV reference.
- No case contains a critical structural-coherence failure.
- At most two cases are worse, and neither may fail through duplicated, torn, or misordered semantic content.
- Evaluation permits manual frame selection only in a separately reported assisted track.
- The fully automatic track and manual-frame-selection track are reported separately.
- A safe OpenCV fallback may protect the user, but fallback results must not be counted as proof that ASP's own reconstruction algorithm exceeded OpenCV.

The final roadmap may choose a stricter `97/97` release gate. `95/97` is proposed because “nearly all” needs a concrete working definition while retaining room for a small number of documented pathological inputs.

### 3.2 Usability gate

For representative vertical panoramas:

- Median active user time to an accepted result is approximately **one minute or less**.
- Automatic processing time is measured separately from active user time.
- Users can finish common cases without opening research settings.
- A failed or ambiguous automatic result leads to a focused correction step rather than an undirected parameter hunt.

### 3.3 Platform gate

- A clean Kubuntu installation can install and launch ASP without Image-Toolkit.
- The CUDA path is automatically detected and verified.
- CPU-only mode launches and supports frame review, ordering, classical stitching, manual editing, project save/load, and export.
- Missing models or accelerators produce actionable capability messages, not import failures.

### 3.4 Reproducibility gate

- The same project, engine version, model versions, provider, and deterministic settings should reproduce materially equivalent output on similar hardware.
- Bit-identical output across different GPU vendors is not required.
- Provider or hardware changes are recorded in result provenance.
- The project format preserves enough information to rerender or explain meaningful differences.

---

## 4. Capability Map and Ordering

The roadmap is capability-oriented, but capabilities still have dependencies. The proposed order is:

```text
Standalone Foundation
        │
        ├──► Project & Edit Model ──► Hybrid Workspace ──► One-Minute Workflow
        │
        ├──► Unified Engine API ────► Coherence-First Core ──► Automatic Gate
        │                                  │
        │                                  ├──► Horizontal Motion
        │                                  └──► Advanced Reconstruction
        │
        ├──► Evaluation System ─────► Trusted Release Decisions
        │
        └──► Local Runtime & Models ─► Kubuntu Distribution

Optional Image-Toolkit Launcher depends only on a stable standalone launch contract.
```

---

## 5. Capability A — Standalone Application Foundation

### Objective

ASP builds, installs, launches, tests, and runs without importing Image-Toolkit internals.

### Why this comes first

The current source boundary is not real: Python code imports parent `backend` and `gui` modules, the launcher injects the parent repository into `sys.path`, and native sources depend on parent headers and bindings. This prevents trustworthy standalone packaging and makes tests environment-dependent.

### Work items

#### A1. Establish owned packages

- Rename/import backend code through one conventional package, proposed `asp_core`.
- Rename/import desktop code through `asp_desktop` or `asp_gui`.
- Create `asp_native` for C++ bindings.
- Move research-only tooling into an explicitly separate package or source tree.
- Remove mixed `asp_backend`, `backend.src`, `asp_gui`, and `gui.src` runtime imports.

#### A2. Own required infrastructure

- Bring ASP-specific constants, errors, configuration, model wrappers, settings, UI components, styling, and worker utilities into ASP.
- Extract truly generic shared code into a third package only when both applications have a demonstrated need.
- Change application data paths from Image-Toolkit-specific locations to ASP-specific XDG locations.

#### A3. Own native bindings

- Build a self-contained C++ library and pybind11 extension inside ASP.
- Copy, replace, or formally depend on currently parent-owned headers.
- Define array ownership, errors, threading, cancellation, and version compatibility at the binding boundary.
- Add Python/native parity tests for every kernel exposed to the engine.

#### A4. Correct the task and test entry points

- Fix nested `just` recipe working-directory behavior.
- Add clean-clone setup and test commands.
- Test installed wheels rather than relying only on source-tree imports.
- Add a model-free smoke stitch.
- Add a headless GUI launch smoke test.

#### A5. Thin Image-Toolkit integration

Implement integration in increasing order of coupling:

1. `Launch ASP App` button using a configured executable or desktop entry.
2. Optional project/frame handoff using command-line arguments or a temporary manifest.
3. Optional local IPC for returning an exported panorama.
4. In-process integration only if later proven worthwhile.

### Alternative implementation avenues

1. **Direct extraction:** copy or migrate required parent code into ASP, then simplify.
2. **Shared foundation package:** move generic components into an independently versioned library.
3. **Local engine service:** isolate engine and models behind IPC, keeping GUI/package boundaries strong.

Direct extraction is recommended first. A service should be justified by crash isolation or multiple genuine clients, not architectural fashion.

### Exit criteria

- ASP passes tests in a clean checkout outside Image-Toolkit.
- Kubuntu installation and launch are documented and repeatable.
- No ASP runtime code imports Image-Toolkit.
- Image-Toolkit can launch ASP through the documented thin bridge.

---

## 6. Capability B — Persistent Project and Non-Destructive Edit Model

### Objective

Every panorama is a recoverable, inspectable project rather than a collection of temporary pipeline artifacts.

### Recommended edit semantics

Ordering must be non-destructive and undoable as explicitly requested. In addition, the following edits should also be undoable because accidental destructive application would make an artist-facing editor unsafe:

- frame inclusion/exclusion;
- phase-group assignment;
- control points and transforms;
- mask corrections;
- color/exposure adjustments;
- seam edits;
- mesh/local warps;
- crop/canvas changes;
- optional generated-fill acceptance.

This does not require storing a full bitmap after every action. Store operation parameters and immutable source references, then cache derived previews.

### Work items

#### B1. Versioned schema

Store:

- sources, timestamps, hashes, and proxies;
- order and inclusion state;
- phase/pose groups;
- transform and match graph;
- masks and corrections;
- photometric operations;
- seam constraints;
- local warp state;
- crop and canvas;
- generated regions;
- engine, provider, model, and configuration provenance;
- render/export profiles.

#### B2. Undo and redo

- Use typed commands or immutable operations.
- Make multi-stage automatic initialization one compound operation that can be expanded or reverted.
- Permit branching or candidate comparison without overwriting prior work.

#### B3. Autosave and recovery

- Autosave incrementally.
- Recover after process or GPU-worker failure.
- Keep user projects separate from benchmark artifacts and ephemeral caches.
- Provide explicit portable project export.

#### B4. Reproducibility

- Record provider and relevant deterministic settings.
- Warn when required models differ.
- Support “rerender with original environment” and “upgrade project to current engine” as distinct operations.
- Compare output perceptually when bit-identical reproduction is impossible across hardware.

### Storage avenues

1. **SQLite plus content-addressed asset/cache directory — recommended.**
2. Portable `.asp-project` archive containing database, manifest, thumbnails, and optional sources.
3. JSON operation graph for readability, with care for migrations and large state.

### Exit criteria

- Projects survive application restart and crash recovery.
- All listed edits are undoable without modifying source frames.
- A project can be moved to another compatible Kubuntu machine and rerendered.
- Hardware/provider differences are recorded and clearly reported.

---

## 7. Capability C — HybridStitch as the Main Workspace

### Objective

Make the existing assisted editor the primary application surface and reduce a typical accepted panorama to about one minute of active user work.

### Work items

#### C1. Unified workspace

Replace the current collection of loosely related tabs with one project-centered workspace containing:

- sequence/phase strip;
- main panorama canvas;
- layer/source provenance view;
- contextual tool panel;
- warnings and suggestions;
- render/export controls.

Existing graph, statistics, canvas, seam, mask, and cluster tools can remain accessible as inspectors rather than competing top-level workflows.

#### C2. Guided workflow

1. Import extracted frames or a frame directory.
2. Run ordering, hold detection, phase grouping, and initial reconstruction.
3. Review only ambiguous frames or flagged regions.
4. Accept a candidate or make focused corrections.
5. Export.

The application should not ask a user to understand bundle adjustment, GraphCut, or internal gate names.

#### C3. Expert workflow

- direct graph editing;
- control points;
- phase-group changes;
- masks;
- seam painting;
- local warps;
- photometric controls;
- provider/model selection;
- diagnostic overlays;
- research profiles.

#### C4. Goal profiles and guides

Provide profiles such as:

- **Coherence First:** strict phase consistency and safe fallbacks.
- **Source Fidelity:** no generated content and conservative corrections.
- **Maximum Coverage:** prefers additional source regions and allows more manual review.
- **Maximum Sharpness:** uses suitable multi-frame reconstruction or post-processing.
- **Fast Preview:** proxy resolution and lightweight matchers.
- **Custom:** user-selected objectives and constraints.

Each profile should have an in-app explanation, tutorial example, and indication of expected time/VRAM.

#### C5. One-minute measurement

Instrument, locally and with user consent, the following per project:

- automatic compute time;
- active user time;
- number of interventions;
- number of frames manually selected/rejected;
- corrections by category;
- whether the final result was accepted.

For the initial private/research audience, this can be an explicit local study logger with manual export rather than telemetry.

### Exit criteria

- The project owner can complete representative vertical cases in about one minute median active time.
- Common cases require at most frame selection and a focused correction.
- Beginner guidance explains both tool use and objective trade-offs.
- Expert controls remain available without overwhelming the default workflow.

---

## 8. Capability D — Unified Engine Contract

### Objective

GUI, CLI, benchmark, tests, and Image-Toolkit handoff all invoke the same production engine path.

### Work items

#### D1. Typed request/result API

Define stable inputs for:

- source sequence or project;
- objective profile;
- provider policy;
- frame-selection constraints;
- allowed generation policy;
- quality/runtime budget;
- requested stage or full render.

Return:

- updated project state;
- candidates and chosen result;
- confidence and warnings;
- fallback classification;
- stage timings;
- artifacts and provenance;
- structured errors and recommended user actions.

#### D2. Stage events

Use event observers for progress, diagnostics, benchmark artifacts, and UI updates. Do not reproduce pipeline stages inside benchmark scripts.

#### D3. Cancellation and isolation

- Pass a cancellation token through every expensive stage.
- Prefer a worker process for CUDA model lifetime and crash isolation.
- Make CPU/native stages interruptible at safe boundaries.
- Persist project state before risky or long-running work.

#### D4. Profiles rather than environment-variable pipelines

- Move stable settings into a typed project/profile schema.
- Reserve environment variables for deployment-level overrides.
- Place experiments in a research registry with explicit versioning.
- Delete expired default-off flags without active experiment plans.

### Exit criteria

- The quality benchmark calls the same public API as the GUI.
- A setting tested by the benchmark changes the same code path used by users.
- Cancellation, progress, provenance, and errors behave consistently across clients.

---

## 9. Capability E — Trusted Evaluation and Corpus Governance

### Objective

Make every quality claim traceable to human-visible evidence and prevent proxy metrics or fallbacks from overstating progress.

### Work items

#### E1. Corpus tiers

- **Smoke set:** tiny synthetic/model-free cases for CI.
- **Fast quality set:** current representative five-case subset, revised if it does not cover current failure classes.
- **Stratified set:** cases selected by vertical motion, animation phase difficulty, masking difficulty, photometric variation, and fallback class.
- **Full research corpus:** current 97 cases.
- **Future distributable corpus:** legally reliable replacement or supplement suitable for releases and publications.

#### E2. Human rating protocol

Rate separately:

- structural coherence;
- fidelity;
- geometry/order;
- coverage;
- seams/photometrics;
- sharpness;
- overall acceptability;
- manual effort required.

Critical structural defects veto an automatic win.

#### E3. Benchmark tracks

Report at least:

1. fully automatic ASP;
2. ASP with manual frame selection only;
3. ASP assisted editor result and active time;
4. OpenCV reference;
5. relevant Hugin/Overmix comparators where available.

#### E4. Fallback accounting

- Report genuine ASP reconstruction rate.
- Report safe-fallback rate and reason.
- Do not count an OpenCV fallback as ASP algorithmic superiority.
- Preserve candidate outputs for visual audit.

#### E5. Reproducible benchmark environment

- Record code commit, model hashes, CUDA/driver versions, provider, hardware, configuration, and corpus version.
- Cache resumable per-case results.
- Detect benchmark/production path divergence automatically.

### Exit criteria

- Human ratings exist for the current baseline.
- Automated metrics are calibrated against those ratings.
- Every release-gate result has visual artifacts and environment provenance.
- The provisional 95/97 gate can be evaluated without ambiguous fallback accounting.

---

## 10. Capability F — Coherence-First Vertical Reconstruction

### Objective

Build a vertical-scroll reconstruction path that avoids pose mixing by construction and can satisfy the automatic quality gate.

### Work items

#### F1. Temporal motion and hold analysis

- Detect vertical camera displacement and direction.
- Identify duplicates, holds, scene cuts, transitions, and low-quality frames.
- Retain temporal adjacency as a hard prior.
- Estimate confidence and expose ambiguous ordering.

#### F2. Animation-phase grouping

Build a compatibility score combining:

- background-compensated frame difference;
- foreground-region similarity;
- temporal distance;
- optical-flow residual;
- pose/semantic embeddings where available;
- mask confidence;
- coverage contribution.

Start with classical features plus an optional DINOv2/SigLIP-style embedding provider. Do not begin with RL.

#### F3. Adjacent-first background alignment

- Match adjacent temporal frames in background regions.
- Prefer translation or low-DOF motion initially.
- Use robust global polish without reordering frames.
- Validate monotonicity, displacement bounds, and graph connectivity.
- Ask for frame review when validation fails instead of cascading through opaque repairs.

#### F4. Phase-consistent reconstruction

- Accumulate background from compatible observations using robust mean/median methods.
- Select foreground from a single coherent animation phase by default.
- Permit cross-phase composition only with explicit user intent and visible boundaries.
- Preserve per-pixel or per-region source provenance.

#### F5. Global photometric solution

- Solve exposure/color consistency jointly over trustworthy background overlaps.
- Protect cel-shaded palettes and line art from hue drift.
- Separate broadcast dimming correction from ordinary exposure compensation.
- Provide local manual correction after the global solution.

#### F6. Semantic seam constraints

- Avoid faces, eyes, hands, text, and strong contours.
- Use seam optimization only after phase compatibility is satisfied.
- Compare hard selection, feathering, and multi-band reconstruction by failure class.

#### F7. Confidence-based user intervention

When uncertainty is high, ask one bounded question such as:

- keep or remove this frame;
- choose phase A or B for this foreground;
- confirm these control points;
- select one of two seam candidates.

The interface should never respond to uncertainty by exposing dozens of thresholds.

### Implementation avenues

1. **Small replacement engine — recommended:** create a new coherence-first vertical path beside the legacy pipeline and compare them.
2. Incrementally alter the current 13-stage pipeline while maintaining full regression coverage.
3. Use a candidate ensemble where simple adjacent reconstruction, current ASP, and OpenCV each produce candidates ranked by a human-calibrated selector.

The first option gives the clearest complexity control. The old engine should remain available for comparison until replacement gates are met, then move to an archive branch or research package.

### Exit criteria

- Zero critical coherence failures in the full corpus.
- Automatic and manual-frame-selection tracks meet the ratified benchmark thresholds.
- New stages improve human ratings, not only proxy metrics.
- Vertical processing has bounded memory and a documented CPU fallback.

---

## 11. Capability G — Local Runtime, CUDA Acceleration, and CPU Utility

### Objective

Provide a strong CUDA experience without making the application useless on CPU-only hardware.

### Work items

#### G1. Capability detection

At startup or first use, report:

- available CPU features;
- CUDA device, VRAM, driver, and supported provider;
- installed models;
- features available in CPU and accelerated modes;
- estimated model download and memory cost.

#### G2. CPU profile

CPU-only mode should support:

- import and proxy generation;
- duplicate/hold detection;
- classical frame ordering and selection;
- template/phase-correlation matching;
- OpenCV stitching;
- manual control points, masks, seams, color, crop, and export;
- project save/load and tutorials.

Heavy learned features may be slower, disabled, or use smaller models, but the application must remain a functional editor and classical stitcher.

#### G3. CUDA profile

- Lazy-load models.
- Reuse model instances within a worker process.
- expose VRAM-aware model and tiling policies;
- free or restart workers after failures;
- benchmark end-to-end transfers, not only kernel time;
- allow quality and speed provider profiles.

#### G4. Optional service provider

A model service may be added as an alternative provider for experimentation or unusually heavy models. It must:

- be opt-in;
- clearly disclose data transfer;
- not be required for saved-project access or classical processing;
- use the same request/result semantics as local providers;
- preserve provenance.

#### G5. Model manager

- version and checksum;
- license and research/commercial status;
- source URL;
- size and hardware requirements;
- install, import, update, rollback, and delete;
- offline installation.

### Exit criteria

- Kubuntu CUDA installation is repeatable and tested.
- CPU-only mode completes a useful vertical workflow.
- Missing acceleration never causes package import failure.
- Model installation is documented and managed in-app or by one supported command.

---

## 12. Capability H — Objective Profiles, Guidance, and Tutorials

### Objective

Help users select parameters according to artistic and technical goals without requiring them to understand internal algorithms.

### Work items

#### H1. Objective model

Represent desired behavior through understandable weights or constraints:

- coherence strictness;
- fidelity/no-generation policy;
- coverage preference;
- sharpness preference;
- runtime budget;
- VRAM budget;
- allowed manual-review budget.

Structural coherence remains a constraint rather than a tradeable score.

#### H2. Explainable recommendations

For every recommendation, show:

- detected condition;
- proposed action;
- expected benefit;
- possible downside;
- preview or alternative where practical.

#### H3. Tutorials

Add task-oriented tutorials for:

- extracting/selecting video frames;
- vertical panorama workflow;
- fixing order and phase grouping;
- control points;
- photometric correction;
- seam correction;
- choosing Coherence/Fidelity/Coverage/Sharpness profiles;
- CPU vs CUDA behavior;
- generative background fill and its limitations;
- interpreting fallbacks and confidence.

#### H4. Research guidance

Provide advanced documentation explaining low-level parameters and experimental methods, separate from beginner help.

### Exit criteria

- A new user can complete the bundled vertical tutorial without external documentation.
- Each user-facing parameter has a goal/trade-off explanation.
- Research parameters do not clutter the default workflow.

---

## 13. Capability I — Horizontal Scrolling

### Objective

Support horizontal anime scroll reconstruction after the vertical engine and project model are stable.

### Work items

- Generalize scroll-axis detection and ordering.
- Remove vertical-only canvas assumptions.
- Adapt coverage, seam, trim, and UI overlays to a horizontal axis.
- Add horizontal benchmark cases and human ratings.
- Reuse phase-consistency and background/foreground separation unchanged where possible.
- Validate mixed text layouts and horizontal character motion.

### Scope rule

Horizontal work may proceed in parallel only when it does not destabilize the vertical production path. Prefer axis-agnostic abstractions where inexpensive, but do not turn the initial vertical milestone into a general arbitrary-mosaic rewrite.

### Exit criteria

- A dedicated horizontal corpus exists.
- Horizontal cases meet their own ratified quality gate.
- Vertical benchmark results do not regress.

---

## 14. Capability J — Advanced Geometry and Reconstruction

### Objective

Extend beyond axis-aligned scrolling only after vertical and horizontal workflows are reliable.

Potential future work:

- diagonal and curved camera trajectories;
- arbitrary 2D mosaics;
- rotation and scale changes;
- parallax-aware mesh warps;
- multi-plane or layered scene models;
- character/effect layer reconstruction;
- sub-pixel multi-frame super-resolution;
- live capture guidance;
- higher-quality line-art-aware resampling;
- optional small-region generative completion.

Every capability needs its own corpus and acceptance criteria. “General stitching” should not be one undifferentiated milestone.

---

## 15. Capability K — Training and Research Workbench

### Objective

Preserve model training and research capabilities without burdening the ordinary artist runtime.

### Near-term recommendation

Keep training code in the repository but separate it from the default desktop installation and navigation. Treat it as an optional Research Workbench until actual use clarifies whether it should become:

1. a developer/research mode inside ASP;
2. a separate ASP Research application;
3. command-line tools and notebooks only.

### Work items

- Audit whether `AnimeStitchNet` is production, experimental, or obsolete.
- Define reproducible dataset and training manifests.
- Separate training dependencies from inference.
- Record licenses and redistribution constraints.
- Add model cards and benchmark evidence.
- Support experiment tracking without coupling it to artist projects.
- Use real correction data only with explicit consent and privacy rules.

### RL and evolutionary optimization gate

Do not introduce broad RL, RLHF, PSO, or evolutionary subsystems until:

- a named failure class exists;
- a strong non-RL/non-evolutionary baseline exists;
- the action/parameter space is bounded;
- the objective correlates with human ratings;
- offline evaluation is possible;
- the method reduces user effort or improves the release gate.

Promising bounded future avenues include compatibility-graph selection, candidate ranking from corrections, local seam/mesh optimization, and acquisition guidance.

---

## 16. Capability L — Documentation and Repository Governance

### Objective

Make active documentation describe the current product and move historical session material into an archive.

### Proposed active document set

- `README.md` — product overview, screenshots, supported status, quick start.
- `docs/PRODUCT.md` — users, workflows, principles, and scope.
- `docs/ARCHITECTURE.md` — current system and boundaries only.
- `docs/PROJECT_FORMAT.md` — schema and reproducibility.
- `docs/EVALUATION.md` — benchmark and human-rating protocol.
- `docs/DEVELOPMENT.md` — accurate standalone setup.
- `docs/ROADMAP.md` or `docs/roadmaps/` — final capability roadmap.
- `docs/research/` — active research references and hypotheses.
- `archive/` — retired roadmaps, session narratives, rejected experiment details, and superseded reports.

### Archival policy

Move old session-level material rather than deleting it. Preserve:

- date;
- relevant commit;
- hypothesis;
- result;
- reason accepted/rejected;
- links to benchmark artifacts where available.

The active roadmap should link to archival evidence without embedding long chronological transcripts.

### Status integrity

- A capability is complete only when its declared exit criteria are met.
- Individual tasks may be marked complete without marking the capability complete.
- Benchmark execution is not equivalent to benchmark success.
- Safe fallback coverage is reported separately from genuine reconstruction quality.

### Exit criteria

- No active entry-point document describes ASP as a generic template.
- Current setup and test commands work.
- Old session narratives reside in a navigable archive.
- The active roadmap is concise enough to guide decisions and links outward for evidence.

---

## 17. Items to Preserve During Refactoring

The following should not be discarded during extraction or pipeline replacement:

- full benchmark corpus and comparison harness;
- visual evaluation and annotation tools;
- benchmark postmortems and negative results;
- seam, mask, graph, coverage, and photometric diagnostic dialogs;
- HybridStitch control-point, color, seam, mesh, and render tools;
- HITL correction concepts and session replay knowledge;
- bundled tutorials and sample sequences;
- proven C++ kernels and their tests;
- classical OpenCV fallbacks;
- useful model wrappers with documented licensing and provider behavior;
- failure-class taxonomy;
- research reports on anime-specific stitching.

Where interfaces are replaced, preserve behavior through characterization tests or saved artifacts rather than copying accidental coupling.

---

## 18. Items to Freeze, Archive, or Remove

### Freeze pending explicit justification

- Tauri/React implementation work;
- mobile applications;
- arbitrary-mosaic geometry;
- general RL control;
- large generative reconstruction subsystems;
- new pipeline gates and default-off flags without scheduled A/B evaluation.

### Archive

- chronological session logs currently embedded in the roadmap;
- superseded roadmaps;
- rejected experimental implementations that are retained only for reference;
- obsolete template documentation;
- benchmark reports superseded by later correctly measured runs.

### Remove after replacement

- `sys.path` package bootstraps;
- imports of parent Image-Toolkit runtime modules;
- parent-owned C++ binding assumptions;
- duplicate configuration sources;
- unused documentation build systems;
- frozen scaffolds that have no scheduled decision point, if the joint roadmap agrees.

---

## 19. Recommended Near-Term Work Packages

These are proposed bounded work packages, not calendar sprints.

### WP1 — Standalone boundary audit and target package design

Deliver:

- complete cross-repository dependency map;
- ownership decision for each missing parent component;
- target Python/native package layout;
- transition plan for Image-Toolkit;
- clean-clone acceptance test specification.

### WP2 — Evaluation truth baseline

Deliver:

- completed human rating pass for the current full-corpus outputs;
- explicit automatic, manual-selection, and fallback accounting;
- ratified definition of “nearly all”;
- curated failure-class subset;
- baseline active-user-time measurements on representative vertical cases.

### WP3 — Minimal standalone vertical slice

Deliver:

- launchable Kubuntu ASP application;
- import frame directory;
- classical CPU ordering/stitch;
- project save/reopen;
- preview/export;
- no Image-Toolkit runtime dependency.

### WP4 — Project operation model and HybridStitch migration

Deliver:

- versioned project schema;
- undoable ordering, inclusion, control points, masks, photometrics, seams, warps, and crop;
- autosave and recovery;
- current HybridStitch tools operating on project state.

### WP5 — Shared engine and benchmark path

Deliver:

- typed request/result API;
- worker execution and cancellation;
- GUI and benchmark using the same engine;
- provenance and stage events;
- removal of benchmark pipeline duplication.

### WP6 — Coherence-first vertical prototype

Deliver:

- adjacent-first alignment;
- animation-phase compatibility graph;
- phase-consistent foreground policy;
- robust background reconstruction;
- A/B against current ASP, OpenCV, and available comparators;
- human-rated results on the stratified set.

### WP7 — Local model/runtime manager

Deliver:

- CUDA detection;
- CPU capability profile;
- model manifest and checksums;
- install/remove/import workflow;
- provider provenance;
- documented optional service adapter contract.

### WP8 — One-minute guided workflow

Deliver:

- goal profiles;
- focused review queue;
- tutorial updates;
- local effort logging;
- measured iteration until median active time approaches one minute.

---

## 20. Decision Points for the Joint Roadmap

The final roadmap created with the owner and the other reviewing agents should resolve:

1. Whether the automatic gate is `95/97`, `97/97`, or a category-weighted equivalent.
2. Whether safe OpenCV fallbacks count only as product safety or also toward release acceptance.
3. Whether manual frame selection is part of the primary production gate or a separately named assisted gate.
4. Whether the existing automatic pipeline is incrementally refactored or replaced by a small parallel coherence-first engine.
5. Whether Tauri is archived or deleted.
6. Whether generic shared Image-Toolkit UI code is copied into ASP or extracted into a third package.
7. Whether the native API remains pybind11-specific or adopts a stable C ABI/service boundary.
8. Which project storage design is selected.
9. Which edits are included in the first undo/redo implementation.
10. Whether training becomes an in-app research mode, separate application, or CLI package.
11. What qualifies as a materially equivalent cross-hardware reproduction.
12. Which horizontal cases enter the first formal horizontal corpus.
13. Which documentation generators remain.
14. Which existing historical files move to the archive and whether paths must be preserved by redirects/indexes.

---

## 21. Proposed Definition of Success

ASP succeeds when it is possible to:

1. install and launch it independently on Kubuntu;
2. import extracted anime video frames;
3. obtain a coherent vertical panorama automatically or with at most focused frame selection in nearly all benchmark cases;
4. correct ambiguous cases through a project-centered HybridStitch workflow;
5. reach an accepted result in roughly one minute of active work for representative cases;
6. save, reopen, undo, compare, and rerender the project;
7. choose understandable optimization profiles with documented trade-offs;
8. run all inference locally, with CUDA acceleration and a useful CPU-only path;
9. optionally generate small missing background regions only with explicit user consent;
10. reproduce materially equivalent results when the relevant engine, models, provider, and hardware class are available;
11. expose a clean launch or handoff bridge to Image-Toolkit without depending on its internals;
12. make every release-quality claim traceable to human ratings, benchmark artifacts, and honest fallback accounting.

This definition treats ASP as an artist/researcher tool first and an algorithm competition second, while preserving the demanding automatic quality gate needed to ensure that human assistance remains fast and exceptional rather than constant.

