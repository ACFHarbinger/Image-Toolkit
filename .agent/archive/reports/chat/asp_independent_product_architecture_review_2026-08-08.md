# Anime Stitch Pipeline: Independent Product, Architecture, and Engineering Review

**Date:** 2026-08-08  
**Reviewer:** Codex  
**Repository:** `Anime-Stitch-Pipeline` (`submodules/ASP` inside Image-Toolkit)  
**Review stance:** Standalone desktop application first; Image-Toolkit submodule second  
**Status:** Initial independent assessment, written before the planned owner/reviewer brainstorming session

---

## Executive Summary

Anime Stitch Pipeline (ASP) contains the foundations of a valuable application: a large body of anime-oriented stitching research, a substantial Python/OpenCV pipeline, native C++ kernels, unusually strong benchmark and diagnostic infrastructure, and an artist-facing PySide6 interface with both automatic and manually assisted stitching workflows. Its best assets are not merely algorithms. They are the accumulated benchmark corpus, the documented negative results, the seam and photometric inspection tools, the human-in-the-loop checkpoints, and the emerging HybridStitch editing workflow.

At the same time, ASP is not presently a standalone desktop application in an engineering or distribution sense. The repository directly imports parent Image-Toolkit Python modules, consumes parent-owned C++ headers and bindings, injects the parent repository into `sys.path`, writes some state into Image-Toolkit-specific configuration locations, and cannot execute its own documented test commands successfully in the reviewed checkout. Several top-level documents still describe the repository as a generic polyglot template even though the codebase is a real, specialized product. This creates an identity problem: the implementation, packaging, documentation, build system, and product roadmap do not consistently describe the same system.

The automatic pipeline also has a product-quality problem that the project's own reports identify honestly. On the latest documented full-corpus checkpoint, many results still fall back to OpenCV SCANS, and a significant number remain classified as worse than the simple stitcher. The implementation has often produced greater sharpness and useful coverage, but its central failure class is structural coherence: combining incompatible animation poses can yield duplicated, torn, or misordered anatomy. This is not primarily a blending defect. Once inconsistent source observations are selected, no sufficiently elaborate seam strategy can guarantee a coherent character.

The recommended direction is therefore not a complete rewrite in C++, nor continued accumulation of pipeline gates. It is a product and architecture reset that preserves the valuable assets:

1. Make ASP genuinely standalone, with owned Python packages, UI infrastructure, settings, errors, constants, native bindings, and packaging.
2. Promote the interactive HybridStitch workflow into the primary product surface.
3. Treat automation as inspectable, editable suggestions rather than an all-or-nothing batch operation.
4. Introduce a persistent, non-destructive project/document model with undo, provenance, autosave, and reproducible rendering.
5. Rebuild the automatic path around temporal and animation-phase coherence before seam compositing.
6. Make the GUI, CLI, and benchmark execute the same public engine API.
7. Split the roadmap into product, engineering, research, and evaluation documents, moving chronological experiment history out of the active plan.
8. Retain C++ for measured hot paths and use Python for orchestration and ML until profiling demonstrates a reason for a broader language migration.

The immediate priority should be a standalone, usable artist application that can always produce or guide the user toward a coherent result. Beating every comparator automatically should remain a research objective, not the prerequisite for shipping meaningful manual and assisted workflows.

---

## 1. Scope and Method

### 1.1 Requested perspective

This review deliberately evaluates ASP as:

1. a standalone desktop application for artists and image editors;
2. a reusable stitching engine and research platform; and only then
3. a submodule of the larger Image-Toolkit repository.

The review is not constrained by the current languages, frameworks, repository boundaries, or prior architecture decisions. Existing technology is retained in recommendations only where it remains advantageous.

### 1.2 Areas inspected

The assessment included inspection of:

- repository and submodule state;
- root, backend, GUI, frontend, and native manifests;
- README and developer documentation;
- architecture and dependency documentation;
- roadmap, changelog, state reports, postmortems, and critical evaluation;
- Python pipeline orchestration and its stage decomposition;
- frame selection, matching, bundle adjustment, masking, flow, rendering, compositing, photometric correction, and fallback organization;
- C++ kernel layout and integration assumptions;
- PySide6 GUI organization and standalone launcher;
- HybridStitch, onboarding, samples, HITL dialogs, and session persistence;
- ML model and training code;
- benchmark, comparison, diagnostics, and evaluation tools;
- test organization, task recipes, package aliases, and import boundaries;
- the frozen Tauri frontend scaffold.

This was a broad architectural and code-level review, not a line-by-line security audit or a fresh full-corpus GPU quality run. Historical benchmark results are reported as repository claims and are distinguished from commands independently executed during this review.

### 1.3 Independently executed checks

The following checks were performed in the reviewed checkout:

- repository and submodule status;
- tracked-file and source-layout inventory;
- code and documentation searches for cross-repository imports, configuration flags, placeholders, project persistence, undo, accessibility, localization, cancellation, and packaging;
- root task listing;
- documented backend and GUI test recipes;
- direct backend and GUI pytest invocation.

Both documented test recipes failed because their working-directory assumptions resolved incorrectly. Direct pytest invocation also failed before test collection because ASP modules imported missing parent-style packages such as `backend.src.constants`. These failures are important evidence about standalone readiness; they do not prove that the tests cannot pass inside the specially configured Image-Toolkit environment used by prior development sessions.

---

## 2. Intended Product and Actual Product

### 2.1 Intended product

Based on the owner-provided purpose and the specialized documentation, ASP is intended to be a desktop application that:

- edits image sequences;
- stitches images into one panoramic reconstruction;
- specializes in anime-style cel-shaded content;
- minimizes artist effort with computer vision, machine learning, deep learning, reinforcement learning, and mathematical optimization where useful;
- provides manual correction for ambiguous or failed automation;
- teaches beginners both the editing workflow and the application itself;
- may also integrate into Image-Toolkit.

This is a coherent and differentiated vision. Anime and cel-shaded material genuinely differs from conventional photographic panoramas: large flat regions, repeated line features, sparse texture, scrolling captures, held character poses, animated foreground changes, broadcast dimming, compression noise, and duplicated content all challenge conventional stitchers.

### 2.2 Actual product surfaces

The current repository contains four distinct surfaces:

1. **Automatic pipeline:** `AnimeStitchPipeline`, implemented primarily in Python with OpenCV, ML wrappers, and native C++ kernels.
2. **PySide6 desktop interface:** the active GUI, containing the automatic Stitch workflow, graph/canvas/statistics tools, sequence building, animation clusters, and many HITL dialogs.
3. **HybridStitch:** a manual and assisted tool with control points, color correction, seam painting, mesh warping, render controls, a first-run tour, and bundled sample sequences.
4. **Tauri/React frontend scaffold:** explicitly frozen and not implemented.

The first three form the real product. The fourth is only a possible future migration path and should not be presented as an active application component.

### 2.3 Product identity mismatch

Several authoritative files still describe ASP as a generic template that ships no product code, references language modules that no longer exist, or provides generic setup instructions. Examples include the root README, backend README, documentation index, contributor material, dependency table, and the assistant instructions in `.agent/AGENTS.md`.

This is more than cosmetic documentation debt. It affects:

- whether a new contributor understands what is shippable;
- which modules are considered authoritative;
- whether a release engineer can build the application;
- which language/tool requirements appear mandatory;
- whether generated template infrastructure is mistaken for product strategy;
- whether an automated coding agent acts on current or obsolete boundaries.

**Recommendation:** Perform a product-identity documentation pass before or alongside standalone extraction. The root README should explain the application, supported workflows, system requirements, installation state, screenshots, quick start, known limitations, and the distinction between production and experimental features.

---

## 3. Current Architecture

### 3.1 Logical module layout

The repository describes these principal modules:

| Module | Language | Intended responsibility |
| --- | --- | --- |
| `backend/` | Python | Pipeline orchestration, ingestion, alignment, models, rendering, HITL persistence, benchmarking support |
| `base/` | C++17 | Performance-sensitive matching, bundle adjustment, canvas, seam, exposure, compositing, frame selection, and foreground registration kernels |
| `gui/` | Python/PySide6 | Working desktop interface and interactive editor |
| `frontend/` | TypeScript/React/Rust | Frozen Tauri scaffold |
| `docs/` | Markdown and multiple generators | Product, engineering, research, tutorial, and API documentation |

At a conceptual level, this is reasonable. Python is well suited to ML and research orchestration, C++ to image-processing kernels, and Qt to a desktop editor.

### 3.2 Actual runtime boundaries

The real boundaries are porous:

- ASP backend code uses both `asp_backend...` aliases and `backend.src...` absolute imports.
- ASP GUI code uses both `asp_gui...` aliases and `gui.src...` parent imports.
- Several required constants, error types, model wrappers, UI styles, settings, windows, and components are not owned by ASP.
- The launcher adds the Image-Toolkit root to Python's module search path.
- The C++ module does not build its own Python extension; parent Image-Toolkit compiles ASP sources into a parent-owned pybind11 module.
- The C++ build expects parent Image-Toolkit headers.
- The standalone repository test bootstrap tries to create aliases, but absolute imports bypass those aliases.

Consequently, ASP is closer to a source overlay or partially extracted feature package than a standalone submodule with a stable public contract.

### 3.3 Standalone extraction options

#### Option A: Complete ASP ownership — recommended

Move or recreate every ASP runtime dependency within the ASP repository and publish explicit packages:

- `asp_core` for domain and pipeline APIs;
- `asp_desktop` or `asp_gui` for the application;
- `asp_native` for native bindings;
- `asp_research` for benchmarks and training, optionally excluded from production distributions.

Image-Toolkit would integrate through these public APIs rather than ASP importing parent internals.

**Advantages:** clear ownership, independent releases, clean tests, reliable packaging, and reusable engine contracts.  
**Cost:** medium-to-large one-time extraction effort and deliberate breakage of current parent imports.

#### Option B: Shared foundation package

Extract genuinely generic UI and runtime facilities into a third library consumed by both projects. Candidates might include settings, theme primitives, worker/job infrastructure, generic image canvas utilities, and plugin contracts.

**Advantages:** avoids duplication where functionality is truly shared.  
**Risks:** creates a third release stream and can become a dumping ground that recreates the current coupling indirectly.

#### Option C: Keep parent coupling

Document ASP as an Image-Toolkit component and abandon independent distribution.

**Advantages:** lowest immediate effort.  
**Risks:** directly contradicts the standalone product objective, obstructs independent testing, and makes external contribution difficult.

### 3.4 Recommended dependency rule

The dependency direction should be:

```text
Image-Toolkit ───────► ASP public API
ASP Desktop ────────► ASP Core ───────► ASP Native
ASP Research ───────► ASP Core
```

ASP should never import Image-Toolkit to run. Optional Image-Toolkit adapters should live in Image-Toolkit or a thin integration package.

---

## 4. Automatic Pipeline Assessment

### 4.1 Current pipeline strengths

The pipeline is substantially more thoughtful than a generic call to `cv2.Stitcher`. It includes:

- temporal frame sorting and selection;
- hold and near-duplicate detection;
- blur and contrast rejection;
- photometric preparation;
- anime-oriented foreground/background masking;
- multiple feature and dense matcher candidates;
- template and phase-correlation fallback paths;
- edge filtering and graph connectivity validation;
- robust bundle adjustment;
- affine health checks and fallbacks;
- optical-flow or ECC refinement;
- canvas construction and scroll-axis handling;
- temporal median or alternative rendering;
- foreground registration and compositing;
- exposure/gain compensation;
- seam optimization and multi-band blending;
- post-render quality gates and safe fallback behavior;
- extensive intermediate diagnostics.

The implementation reflects real investigation into anime-specific failure modes rather than superficial use of fashionable models.

### 4.2 Central weakness: structural coherence

The repository's own critical evaluation identifies the essential issue: frames are not merely spatial tiles. They are observations at different animation phases. If a character changes pose while the camera scrolls, globally plausible frame alignment can still combine mutually incompatible body configurations.

This produces failures such as:

- duplicated limbs or facial features;
- torn anatomy across a seam;
- repeated strips;
- discontinuous clothing lines;
- foreground fragments from multiple poses;
- content ordering that is locally aligned but globally incorrect.

Once incompatible frames have been selected for the same semantic object, seam placement and blending can hide local transitions but cannot guarantee a coherent result. The primary solution must therefore occur before compositing.

### 4.3 Recommended coherence-first pipeline

#### Stage A: Input understanding

- Decode images/video into a sequence with timestamps and source metadata.
- Detect direction and magnitude of camera motion.
- Detect static holds, duplicate frames, transitions, cuts, and rapid animation changes.
- Generate proxies while retaining full-resolution source references.

#### Stage B: Scene and phase decomposition

- Segment background, foreground characters, text, effects, and uncertain regions.
- Compute temporal compatibility between frames.
- Group observations into animation phases or pose-consistent sets.
- Preserve uncertainty and expose ambiguous assignments to the user.

#### Stage C: Coherent alignment

- Prefer adjacent temporal edges.
- Align background regions independently from animated foreground regions.
- Use a simple translation or low-DOF motion model first.
- Apply global least-squares or robust graph polish without allowing arbitrary reordering.
- Stop and request review when monotonicity or step constraints fail.

#### Stage D: Reconstruction

- Accumulate background observations per output pixel using mean, median, or robust estimators.
- Select foreground material from one coherent phase unless the user intentionally composes multiple phases.
- Treat effects, subtitles, and text as separate layers where possible.
- Track provenance for every reconstructed region.

#### Stage E: Photometric and seam finishing

- Solve global exposure/color consistency over reliable background overlap.
- Use semantic seam exclusions around faces, line art, text, and important contours.
- Blend only after source compatibility is satisfied.
- Preserve a fully inspectable seam and transform graph.

#### Stage F: Review and export

- Display confidence and flagged regions.
- Offer one-click alternatives rather than opaque retries.
- Render from the project graph at full resolution.
- Record model versions, settings, and source hashes for reproducibility.

### 4.4 Implementation avenues for phase consistency

Multiple approaches should be evaluated without committing prematurely to one model family.

#### Classical temporal clustering

Use masked MAD, dHash/pHash, optical-flow residuals, background-compensated frame differences, foreground shape descriptors, and temporal constraints.

**Pros:** fast, explainable, CPU-capable, easy to diagnose.  
**Cons:** fragile under lighting changes, occlusion, effects, and subtle pose changes.

#### Embedding-based clustering

Use DINOv2, SigLIP, CLIP variants, or anime-tuned encoders over foreground crops and region proposals. Combine embedding distance with temporal and camera-motion priors.

**Pros:** stronger semantic similarity and relatively easy experimentation.  
**Cons:** embeddings may prioritize character identity over exact pose; GPU and model distribution concerns remain.

#### Keypoint or part-based tracking

Detect faces, hands, body parts, clothing contours, or line-art landmarks and track them through time.

**Pros:** directly represents structural consistency.  
**Cons:** anime pose/keypoint models may be unreliable, and partial/off-screen characters complicate tracking.

#### Compatibility graph optimization

Represent frames or foreground candidates as nodes. Edge costs encode temporal distance, pose similarity, coverage, photometric compatibility, and transform consistency. Solve a constrained path, partition, or set-cover problem.

**Pros:** integrates classical, learned, and user constraints; explainable decisions.  
**Cons:** requires careful objectives and can reproduce proxy-metric failures if human quality is not represented.

#### Learned temporal policy

Train a sequence model to propose phase groups or source selection.

**Pros:** potentially strongest on sufficiently representative data.  
**Cons:** requires labeled or reliably self-supervised data and should not precede a simpler measurable baseline.

### 4.5 Fallback policy

Fallbacks are a product strength when exposed honestly. A coherent simple stitch is preferable to a sophisticated but broken reconstruction.

Recommended result states:

- **Automatic reconstruction succeeded**
- **Safe classical stitch selected**
- **Review recommended**
- **Manual constraints required**

The application should explain why a fallback occurred and retain the rejected candidate for comparison. Benchmark reports should distinguish genuine ASP composites from safe comparator-derived output.

---

## 5. Manual and Assisted Editing Assessment

### 5.1 Why HybridStitch is strategically important

HybridStitch already expresses the most credible product philosophy in the repository: automation initializes the work, and the user can correct control points, photometrics, seams, and geometry. This acknowledges that ambiguous anime sequences may not have one objectively correct automatic reconstruction.

It should become the central workspace rather than a secondary tab.

### 5.2 Existing strengths

Observed capabilities include:

- sequence loading and thumbnails;
- control-point editing;
- color correction;
- seam painting;
- mesh warp controls;
- rendering/export-oriented workflow;
- first-run guided tour;
- bundled synthetic sample sequences;
- automatic pipeline diagnostics;
- multiple HITL review dialogs;
- checkpoint override persistence and replay;
- batch processing and cancellation points;
- graph, canvas, statistics, and animation-cluster views.

These are valuable foundations for an expert application.

### 5.3 Missing product-level document model

The repository has HITL session persistence, but that is not equivalent to an artist project. A real desktop editor should support a durable project containing:

- source references and embedded/proxy options;
- source hashes and timestamps;
- frame order and excluded frames;
- animation phase groups;
- transform graph and control points;
- masks and segmentation corrections;
- exposure/color operations;
- seam paths and painted constraints;
- local warps and mesh state;
- crops and canvas bounds;
- model suggestions and confidence;
- accepted/rejected alternatives;
- render/export configuration;
- tutorial state when appropriate;
- engine and model versions;
- undo/redo history or an immutable operation log.

### 5.4 Project storage options

#### SQLite plus asset directory — recommended for initial implementation

Store structured project state in SQLite and keep full-resolution sources external or copied into a project asset directory.

**Pros:** migrations, partial updates, reliable autosave, queryability, crash recovery.  
**Cons:** portable sharing requires packaging the database and assets together.

#### Portable archive

Use an `.asp-project` ZIP containing a database or JSON document, thumbnails, and optionally source assets.

**Pros:** simple sharing and backup.  
**Cons:** frequent autosave requires careful incremental handling or a working directory plus export step.

#### Immutable operation graph

Store edits as typed operations referencing content-addressed assets. Undo and branching become movement through graph history.

**Pros:** reproducibility, non-destructive edits, comparison of alternatives, strong provenance.  
**Cons:** greater initial design effort.

A pragmatic design is SQLite with immutable operation records and a portable export archive.

### 5.5 UX priorities

The application should present two modes over the same project model:

#### Guided mode

1. Add frames or video.
2. Review automatic ordering and phase grouping.
3. Review flagged alignment or mask regions.
4. Choose among candidate reconstructions.
5. Make optional seam/color corrections.
6. Export.

#### Expert mode

- unrestricted layer/graph/canvas access;
- detailed control-point and seam tools;
- batch parameter editing;
- model/provider selection;
- stage artifacts and numerical diagnostics;
- saved presets and scripts.

### 5.6 Additional UX gaps to investigate

The initial inspection did not find evidence of a general undo stack, comprehensive project save/load, accessibility strategy, screen-reader support, internationalization, or crash reporting. These should be treated as product roadmap items rather than afterthoughts.

Recommended early work:

- undo/redo for every manual edit;
- background autosave and crash recovery;
- cancellable worker-process jobs;
- keyboard-first editing and documented shortcuts;
- color-blind-safe overlays;
- scalable text and high-DPI validation;
- accessible labels and focus order;
- localization-ready strings, even if only English ships initially;
- clear disk, VRAM, and model-download reporting.

---

## 6. Machine Learning and Mathematical Optimization

### 6.1 Appropriate role of ML

ML should be justified by reduced artist effort or a documented failure class. It should not be included merely to satisfy a technology-oriented mission statement.

High-value candidates are:

- foreground/background/effect/text segmentation;
- pose- or animation-phase grouping;
- semantic correspondence in texture-poor cel-shaded regions;
- confidence estimation and failure prediction;
- choosing the best source for an occluded region;
- classifying visible defects;
- optional, disclosed background completion;
- project-aware tutorial suggestions;
- learned ranking among several classical reconstruction candidates.

### 6.2 Appropriate role of mathematical optimization

High-value optimization targets include:

- globally consistent transform graphs;
- constrained temporal ordering;
- exposure and color consistency;
- semantic seam paths;
- frame subset selection;
- coverage as set cover;
- multi-objective selection balancing coherence, fidelity, sharpness, coverage, runtime, and expected manual effort;
- bundle adjustment and robust estimation;
- local mesh deformation under line and shape constraints.

### 6.3 Reinforcement learning

General RL control of the entire pipeline is not recommended at the current maturity level. The application lacks a sufficiently reliable reward signal, and historical proxy-metric optimization has already produced misleading progress.

Narrow future RL possibilities include:

- learning which suggestion to present next based on user corrections;
- selecting a bounded sequence of repair actions;
- adaptive frame acquisition guidance during live capture;
- personalized tutorial sequencing;
- ranking candidate phase groups when trained from substantial human preference data.

Prerequisites should include:

- a stable project/action schema;
- logged human corrections with consent;
- a validated coherence and fidelity evaluation protocol;
- a non-RL baseline;
- offline evaluation before any user-facing policy.

### 6.4 Evolutionary and swarm methods

Evolutionary search or swarm optimization can be useful for small, bounded spaces such as seam constraints, mesh parameters, or multi-objective candidate selection. They should not be used to search dozens of weakly understood thresholds against proxy metrics.

Before adopting one, require:

- a named failure class;
- a bounded parameter space;
- a deterministic or statistically controlled evaluation;
- comparison against grid, Bayesian, gradient-based, or direct solvers;
- human visual confirmation of the winning configuration;
- evidence that search cost is acceptable for either offline tuning or interactive use.

### 6.5 Existing learned alignment model

The repository contains a Siamese/cross-attention `AnimeStitchNet`, a synthetic dataset pipeline, losses, and a training orchestrator with checkpointing and TorchScript export. This is potentially useful research, but its product status is unclear.

It should be classified explicitly as one of:

- production model with distributed weights and benchmark evidence;
- experimental model with a reproducible training recipe;
- deprecated research artifact;
- separate developer tool.

Training UI and training dependencies should not be part of the ordinary artist installation unless artists are genuinely expected to train models.

---

## 7. Performance and Language Strategy

### 7.1 Why a complete C++ rewrite is not presently justified

The strongest evidence of failure concerns structural output quality, product cohesion, repository ownership, and evaluation architecture—not Python interpreter overhead.

A complete rewrite would:

- delay product validation;
- risk losing fast ML experimentation;
- require recreating a substantial working GUI;
- reproduce current conceptual errors if architecture is not fixed first;
- make iteration slower during the phase when user feedback matters most.

### 7.2 Recommended hybrid architecture

- Python for orchestration, ML experimentation, pipeline composition, and research tools.
- C++ for OpenCV-heavy loops, warps, accumulation, seams, bundle adjustment, and memory-sensitive image kernels.
- PySide6 for the near-term desktop interface.
- Worker processes for GPU inference and long-running reconstruction.
- A stable data contract between project model, engine, native kernels, and UI.

### 7.3 Native integration options

#### Self-contained pybind11 extension

Build `asp_native` entirely inside ASP and remove parent-owned header/binding assumptions.

**Best for:** lowest migration cost from the current code.

#### C ABI plus multiple bindings

Expose stable opaque handles and plain structs/buffers through a C ABI. Bind it from Python and potentially Rust or other hosts.

**Best for:** long-term SDK and ABI stability.  
**Cost:** more explicit memory and error handling.

#### Native service process

Run the engine as a separate process with local IPC and shared memory for large images.

**Best for:** crash isolation, GPU lifetime control, multiple frontends.  
**Cost:** protocol and deployment complexity.

### 7.4 When broader migration becomes reasonable

A C++/Qt or Rust/Tauri migration should be reconsidered if measurement shows that:

- Python packaging prevents reliable consumer installation;
- UI responsiveness cannot be achieved with background workers and native kernels;
- cross-language memory copies dominate runtime;
- startup or distribution size is unacceptable;
- a stable embeddable SDK becomes a commercial priority;
- multiple non-Python frontends require a process or C ABI boundary.

### 7.5 Performance roadmap

1. Define representative projects and hardware tiers.
2. Measure wall time, peak RAM, peak VRAM, disk cache, startup, and interactive latency by stage.
3. Add cancellation and progress at engine-stage boundaries.
4. Eliminate redundant decode, color conversion, warp, and host/device transfers.
5. Add proxy-resolution editing and full-resolution deferred render.
6. Tile operations whose memory scales with panorama area.
7. Cache transforms, masks, embeddings, and warped proxies by content hash.
8. Port only measured CPU hot spots.
9. Provide inference providers such as CUDA, DirectML, Core ML, OpenVINO, or CPU where model compatibility allows.

---

## 8. Packaging and Dependency Assessment

### 8.1 Current concerns

The backend's base dependency set includes heavyweight numerical, ML, GUI, and video packages. Research matcher dependencies have partly been moved to optional extras, which is a good correction, but the overall runtime boundary remains broad.

The package structure also exposes source directories through aliases rather than a single conventional installed package name. This contributes to namespace collisions and makes source-tree behavior differ from installed behavior.

### 8.2 Recommended distribution tiers

| Tier | Contents |
| --- | --- |
| ASP Core | Project schema, classical alignment/rendering, native kernels, minimal image dependencies |
| ASP Desktop | PySide6 GUI, resources, updater/launcher, project workflows |
| Local ML Pack | Torch or alternative runtime, standard segmentation/matching models |
| GPU Accelerator Pack | CUDA/provider-specific optional components |
| Research Pack | Training, benchmark comparators, FiftyOne, diagnostics, datasets |
| Model Packs | Separately versioned weights with license and hardware metadata |

### 8.3 Model management

The application should not rely on undocumented manual checkpoint placement. Add a model manager that provides:

- model name and purpose;
- source and license;
- download size and disk location;
- expected RAM/VRAM;
- checksum and version;
- supported providers;
- offline import;
- update and rollback;
- deletion;
- explicit consent before downloading large files.

### 8.4 Release targets

The first release plan should state:

- supported operating systems;
- CPU architecture;
- minimum and recommended RAM;
- CPU-only capabilities;
- supported GPU/provider matrix;
- installer format;
- portable vs installed operation;
- update policy;
- crash and log locations;
- model-license obligations;
- commercial licensing implications.

---

## 9. Testing, CI, and Evaluation

### 9.1 Existing strengths

The repository contains a large test body, native C++ tests, benchmark scripts, GUI tests, diagnostic tools, multiple CI definitions, lint/type configuration, and detailed benchmark history. This level of measurement infrastructure is uncommon and should be preserved.

### 9.2 Standalone test failure observed during review

The documented root recipes for backend and GUI testing did not execute from the reviewed root because imported `just` recipes attempted to enter `backend` or `gui` relative to their own nested recipe directory. Direct invocation from those directories then failed during `conftest.py` loading because imports such as `backend.src.constants` were unresolved.

This demonstrates that ASP's tests currently rely on environmental assumptions not captured by the standalone documentation.

### 9.3 Required test layers

#### Unit tests

- pure transform math;
- compatibility and phase grouping;
- serialization and migrations;
- project operations and undo;
- seam and exposure solvers;
- native/Python parity.

#### Component tests

- input decoding and proxy generation;
- engine stages with saved fixtures;
- worker cancellation and retry;
- model provider selection;
- project save/reopen.

#### GUI tests

- guided workflow;
- keyboard actions and undo;
- autosave recovery;
- high-DPI layouts;
- model-missing states;
- long-running job progress and cancellation.

#### Distribution tests

- clean clone;
- wheel installation;
- native extension loading;
- packaged application launch;
- installation without Image-Toolkit;
- offline/model-free classical stitch;
- Windows, Linux, and macOS smoke tests according to support policy.

#### Quality tests

- five-case fast corpus;
- stratified medium corpus by failure class;
- full 97-case corpus;
- human coherence/fidelity review;
- regression thresholds calibrated to human rankings;
- runtime and memory budgets.

### 9.4 Single execution path requirement

GUI, CLI, automated tests, and quality benchmark must call the same engine contract. Instrumentation should be injected through observers or event sinks, not through a copied benchmark-specific implementation.

A possible API:

```python
request = StitchRequest(
    project=project,
    mode="assisted",
    provider_policy=provider_policy,
    render_profile=render_profile,
)

result = engine.run(
    request,
    events=event_sink,
    cancellation=token,
)
```

The result should contain the project update, candidates, selected output, warnings, confidence, timings, artifacts, and provenance.

### 9.5 Metrics

No single SSIM-like metric captures coherent anime reconstruction. Evaluation should separate:

- structural coherence;
- source fidelity;
- geometric alignment;
- duplicate/ghost content;
- seam visibility;
- photometric continuity;
- line-art sharpness;
- coverage/crop quality;
- hallucinated content;
- runtime and memory;
- number and duration of user interventions.

The ultimate product metric should include manual effort, for example median active editing time to a user-accepted panorama.

---

## 10. Documentation and Roadmap Assessment

### 10.1 Documentation strengths

- Detailed experiment history and postmortems.
- Strong critical self-evaluation.
- Beginner HybridStitch and pipeline tutorials.
- Benchmark explanation and metric caveats.
- Research surveys and comparator notes.
- Explicit recognition that visual inspection is necessary.

### 10.2 Documentation weaknesses

- Root and module entry points still contain template identity.
- Dependency and architecture pages contain stale paths or incomplete boundaries.
- Several toolchains duplicate documentation work.
- Current state is distributed across roadmap, cache reports, critical evaluation, and changelog.
- Historical session transcripts dominate the active roadmap.
- Claims of completion sometimes conflict with stated exit criteria.

### 10.3 Specific roadmap issue

The roadmap labels Phase 4 "DONE" while defining its exit gate as every one of the 97 tests being human-rated at least as good as the simple stitch. The latest documented benchmark still reports a nonzero `simple_better` count and does not contain the completed human rating pass required by the gate.

This does not invalidate the engineering work performed under Phase 4, but it makes roadmap status unreliable. A phase should be marked complete only when its declared outcome is achieved; otherwise its tasks may be complete while its outcome remains open.

### 10.4 Recommended roadmap set

#### `PRODUCT_ROADMAP.md`

- target users and jobs;
- supported input workflows;
- Guided and Expert experiences;
- project format;
- release milestones;
- packaging and platform support;
- tutorials and accessibility;
- success metrics based on accepted output and user effort.

#### `ENGINEERING_ROADMAP.md`

- standalone extraction;
- package/import cleanup;
- native extension ownership;
- engine contract;
- project/document model;
- worker isolation;
- packaging and CI;
- performance budgets.

#### `RESEARCH_ROADMAP.md`

- active failure classes;
- hypotheses;
- baselines;
- experiment entry/exit rules;
- phase grouping;
- source selection;
- model evaluation;
- optimization candidates.

#### `EVALUATION_PLAN.md`

- corpus governance;
- human rating protocol;
- metric definitions;
- benchmark tiers;
- hardware controls;
- acceptance policy;
- artifact retention.

#### Archive

Move chronological sessions, completed experiment narratives, and rejected gates into dated reports or a roadmap archive. Preserve them for negative knowledge without requiring every contributor to read them as the current plan.

### 10.5 Active roadmap item template

Every active item should state:

- **User problem**
- **Proposed outcome**
- **Why now**
- **Dependencies**
- **Alternatives considered**
- **Success measure**
- **Exit criterion**
- **Non-goals**
- **Owner/status**
- **Evidence links**

---

## 11. What to Keep, Change, and Remove

### 11.1 Keep

| Item | Reason |
| --- | --- |
| Benchmark corpus and comparator harness | Irreplaceable empirical foundation and accumulated failure coverage |
| Human visual evaluation tooling | Directly measures coherence and artist-facing quality that proxy metrics miss |
| Postmortems and rejected-experiment records | Prevent repetition and show where apparent improvements failed |
| HybridStitch workflow | Closest current surface to reliable, controllable artist value |
| HITL checkpoints and correction dialogs | Correct response to ambiguity; valuable basis for assisted editing |
| Classical matching and fallback chain | Provides CPU-capable and safe baselines |
| Robust transform and validation code | Core stitching capability with clear mathematical role |
| Useful C++ kernels | Appropriate optimization of compute-heavy image operations |
| Tutorials and bundled samples | Good beginning for novice onboarding |
| Safe fallback policy | Protects users from structurally broken automatic output |

### 11.2 Change

| Item | Change | Reason |
| --- | --- | --- |
| Repository boundaries | ASP owns all runtime dependencies | Required for standalone application and reliable releases |
| Product center | Hybrid document editor first, batch automation second | Maximizes reliable artist value now |
| Pipeline ordering | Phase/pose consistency before composition | Attacks the structural root cause |
| Benchmark execution | Use the same public engine path as GUI | Prevents false or irrelevant measurements |
| Persistence | Add full project model and non-destructive operation history | Essential desktop-editor capability |
| ML packaging | Optional providers and separately managed model packs | Reduces install and hardware barriers |
| Roadmaps | Split outcomes, engineering, research, and evaluation | Makes priorities and completion truthful |
| Configuration | Typed profiles/project settings instead of many environment flags | Improves reproducibility and usability |
| C++ build | Self-contained native library/binding | Removes parent coupling and enables standalone CI |
| Tests | Clean-clone, installed-package, packaged-app coverage | Validates the actual distribution rather than one dev environment |

### 11.3 Remove or archive

| Item | Recommendation | Reason |
| --- | --- | --- |
| Generic polyglot template prose | Replace | Misrepresents the product and tool requirements |
| Frozen Tauri scaffold | Delete or archive outside active tree unless migration is scheduled | Prevents false architectural plurality and dependency churn |
| Obsolete documentation generators | Consolidate to one portal plus API docs if needed | Reduces maintenance and inconsistent output |
| Parent import aliases and `sys.path` bootstraps | Remove after extraction | Hide broken package ownership |
| Default-off experiments without scheduled evaluation | Archive or delete | Avoids unbounded configuration surface |
| Training UI from artist distribution | Separate unless a real artist use case exists | Reduces complexity and dependencies |
| Chronological experiment transcripts in active roadmap | Move to reports/archive | Preserves history without obscuring decisions |

---

## 12. Proposed Delivery Avenues

### 12.1 Avenue 1: Product-first stabilization — recommended

**Goal:** Deliver a reliable standalone assisted editor before attempting universal automatic superiority.

1. Correct product documentation and define target release platforms.
2. Extract ASP-owned packages and native bindings.
3. Establish one engine API and clean-clone CI.
4. Create a project/document model with autosave and undo.
5. Make HybridStitch the main workspace.
6. Integrate automatic output as editable suggestions.
7. Package a CPU/classical mode and optional local ML pack.
8. Run usability sessions and measure time-to-accepted-output.
9. Improve coherence-first automation iteratively.

**Pros:** earliest real user value, lower technical risk, clear learning loop.  
**Cons:** delays the ambition of fully automatic superiority.

### 12.2 Avenue 2: Research-engine reset

**Goal:** Preserve evaluation assets but build a small coherence-first automatic engine in parallel with the old one.

1. Freeze the existing pipeline except critical fixes.
2. Define a minimal adjacent-frame/phase-consistent baseline.
3. Reuse masks, selected native kernels, corpus, and diagnostics.
4. Compare every stage against simple stitch, current ASP, Overmix, and Hugin.
5. Delete or decline any enhancement that does not improve human-rated outcomes.
6. Replace the old engine once the new one dominates by declared criteria.

**Pros:** directly addresses algorithmic architecture.  
**Cons:** less immediate attention to desktop product gaps; risks another research loop without user feedback.

### 12.3 Avenue 3: Native desktop rewrite

**Goal:** Build a C++/Qt application and native engine, with ML through ONNX/provider APIs.

This should occur only after project semantics and user workflow are validated. Otherwise it makes the current architecture expensive rather than correct.

**Pros:** strong deployment control, native performance, unified language for editor and kernels.  
**Cons:** highest cost, slower ML iteration, major rewrite risk, no inherent solution to coherence.

### 12.4 Avenue 4: Service-oriented engine

**Goal:** Isolate the pipeline in a local or optional remote service used by PySide6, Tauri, Image-Toolkit, or automation clients.

**Pros:** crash isolation, multiple frontends, centralized GPU/model management.  
**Cons:** protocol, shared-memory, deployment, versioning, and security complexity.

This becomes attractive if multiple products genuinely need the engine. It is unnecessary for the first standalone release.

---

## 13. Recommended Phased Plan

The following is a provisional plan pending owner answers and joint brainstorming.

### Phase A: Product definition and truthfulness

- Define primary user and input workflow.
- Define fidelity/generation policy.
- Define supported operating systems and hardware tiers.
- Replace template documentation.
- Audit licenses for code, models, and benchmark data.
- Define Alpha acceptance criteria.

### Phase B: Standalone foundation

- Create conventional owned packages.
- Remove parent imports and `sys.path` injection.
- Vendor, recreate, or extract shared infrastructure deliberately.
- Build `asp_native` independently.
- Fix root task recipes and clean-clone tests.
- Add a standalone launcher and model-free smoke stitch.

### Phase C: Artist project model

- Design versioned project schema.
- Add autosave, recovery, migrations, and undo/redo.
- Represent sources, transforms, masks, seams, adjustments, and renders non-destructively.
- Update HybridStitch to edit the project model.
- Add portable project export/import.

### Phase D: Unified assisted workflow

- Make HybridStitch the main workspace.
- Route automatic stages through one engine contract.
- Display suggestions, confidence, alternatives, and provenance.
- Add guided and expert modes.
- Measure active user time and correction count.

### Phase E: Coherence-first engine

- Establish simple adjacent-frame baseline.
- Add animation-phase compatibility and grouping.
- Separate background reconstruction from foreground pose selection.
- Add global photometric solve.
- Reuse proven native kernels behind stable interfaces.
- Human-rate each milestone against all comparators.

### Phase F: Distribution

- Create platform installers.
- Add model manager and provider detection.
- Validate CPU-only and minimum-GPU experiences.
- Add crash recovery, logs, diagnostics bundle, and updater policy.
- Conduct beginner and expert usability tests.

### Phase G: Advanced assistance

- Semantic matching and defect detection.
- In-context tutorial suggestions.
- Optional background completion with provenance.
- Multi-axis canvas support if user demand warrants it.
- Bounded optimization or RL only after validated data/reward infrastructure exists.

---

## 14. Principal Risks

### 14.1 Research displacement of product work

ASP can continually generate interesting experiments. Without release-oriented constraints, algorithm work may consume the time needed for projects, undo, packaging, accessibility, and user testing.

**Mitigation:** separate product and research roadmaps, reserve explicit capacity, and measure accepted user outcomes.

### 14.2 Proxy-metric optimization

Sharper or higher-SSIM output can still contain structurally invalid anatomy.

**Mitigation:** human coherence ratings, hard structural vetoes, region-level review, and calibration of every automatic metric.

### 14.3 Hidden parent coupling

An apparent standalone fix may leave runtime dependencies in rarely executed GUI or model paths.

**Mitigation:** build and test outside Image-Toolkit, scan imports, package in an isolated environment, and exercise every feature tier.

### 14.4 Model and dataset licensing

Anime datasets, checkpoints, and research implementations may prevent commercial redistribution.

**Mitigation:** maintain a machine-readable bill of materials with license, source, redistribution, and commercial-use fields.

### 14.5 Hardware fragmentation

CUDA-only research dependencies can exclude artists with AMD, Intel, Apple Silicon, or CPU-only systems.

**Mitigation:** classical baseline, provider abstraction, capabilities screen, separate model packs, and declared hardware tiers.

### 14.6 Project-format instability

Building UI features before a stable document model can make later migrations painful.

**Mitigation:** version the schema from the beginning, use migrations, preserve raw sources, and make render operations reproducible.

### 14.7 Rewrite risk

A language rewrite can absorb years while providing no improvement in result quality or workflow.

**Mitigation:** profile first, port bounded kernels, and validate product semantics before changing the application language.

---

## 15. Decisions Required From the Owner

The following questions should be answered during the planned brainstorming session. They materially affect roadmap structure and architecture.

### Users and workflows

1. Who is the first target user: screenshot stitchers, manga cleaners/typesetters, animation artists, general illustrators, or researchers?
2. What is the primary input for the first release: screenshots, video frames, hand-drawn layers, scanned pages, or several of these?
3. Should the first release optimize for full automation or fastest reliable human-assisted completion?
4. What amount of manual time per panorama counts as success?
5. Is vertical scrolling enough for the first production scope?

### Fidelity and generation

6. Is strict source fidelity mandatory?
7. May generative models invent missing background when disclosed and reviewable?
8. When goals conflict, what is the priority order among coherence, fidelity, coverage, sharpness, runtime, memory, and manual effort?

### Distribution and hardware

9. Which operating systems are required for Alpha and 1.0?
10. What minimum GPU should be supported?
11. Must CPU-only operation remain useful?
12. Must all inference be local, or is an optional remote provider acceptable?
13. Is independent distribution the primary goal, or will ASP mainly ship inside Image-Toolkit initially?

### Architecture and compatibility

14. Is breaking the current Image-Toolkit integration acceptable to create correct standalone boundaries?
15. Should HybridStitch become the main workspace?
16. Which operations must support undo and non-destructive editing?
17. Must projects reproduce identical output across machines and model upgrades?
18. Should training tools remain in the desktop application, move to a developer package, or be removed?

### Licensing and governance

19. Is commercial closed-source distribution an active objective?
20. Can the current corpus and necessary model weights legally be redistributed?
21. Should telemetry or opt-in correction-data collection ever be considered?

### Roadmap organization

22. Should milestones be release-oriented or capability-oriented?
23. Should historical roadmap narratives be moved into an archive?
24. Should the frozen Tauri scaffold be deleted, archived, or retained?
25. How aggressively may redundant documentation toolchains be removed?

---

## 16. Final Assessment

ASP should not be judged as a failed automatic stitcher. It is an overextended but unusually well-instrumented combination of research platform, native image engine, and emerging artist tool. Its strongest strategic move is to stop requiring the automatic pipeline to justify the entire application's existence.

The application can provide meaningful value earlier by helping an artist reach a coherent panorama faster than existing tools, even when some decisions remain manual. The current HybridStitch and HITL work already points in that direction. Automation can then improve behind a stable project model, a shared execution path, real user corrections, and a benchmark whose primary quality signal matches what artists actually accept.

The most important things to preserve are the benchmark assets, visual diagnostics, negative research knowledge, manual correction primitives, and native kernels. The most important things to change are repository ownership, project persistence, product focus, phase-coherent source selection, execution-path duplication, and roadmap truthfulness. The most important thing not to do is to rewrite the entire application or add another large ML/optimization subsystem before those foundations are resolved.

The next roadmap should be produced only after the owner decisions above are discussed. That roadmap should describe a product that can be installed, opened, learned, used, saved, recovered, corrected, and trusted—not only a pipeline that can be benchmarked.

