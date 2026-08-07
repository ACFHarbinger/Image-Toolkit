# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
