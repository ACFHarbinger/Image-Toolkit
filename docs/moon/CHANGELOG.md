# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Started Phase 0 issue #6: introduced a host-neutral `JobRequest`/`Operation`
  contract and `IsolatedRunner`, spawning a fresh process for each native-heavy
  job. Hard exits, hangs, cancellation, ordinary exceptions, and pipe EOF are
  converted into recoverable host-side failures; the next worker starts cleanly.
  Adaptive timeouts are capped by user policy, and optional local JSONL
  diagnostics contain only operation, array dimensions, timing, outcome, and
  error type—never pixels or filenames. GUI routing and overhead measurements
  remain before this issue is complete.
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
