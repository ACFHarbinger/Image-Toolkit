# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- HIE restoration foundations: optional `DeblurAdapter` and consent-gated `WatermarkRemovalAdapter`, plus cancellable injected restoration jobs for blind/non-blind deblurring and mask-guided inpainting. No model weights or heavy runtimes are bundled.
- Multi-modal IPC media support for still sources and validated multi-frame sequences with FPS, frame duration, and metadata preservation.
- Stateful `PipelineSession`, versioned frontend IPC envelopes, in-memory IPC service, PySide6/Tauri frontend surfaces, and default Phase 1 capability registration.

- **Multi-Modal Document Schema (`logic/include/document.hpp`):** Defined versioned value types (`MediaAsset`, `Frame`, `FrameSequence`, `Layer`, `ModifierNode`, `ModifierEdge`, `Document`). Supports 1-frame degenerate sequence representation for still images without data model refactoring for video clips.
- **Topological DAG Render Graph (`logic/include/render_graph.hpp`, `logic/src/render_graph.cpp`):** Built C++ DAG evaluator using Kahn’s topological sorting algorithm, tile-based rendering callbacks, per-node cache invalidation, and BFS downstream dirty propagation.
- **C++ Exact Numerical Solvers (`logic/include/exact_solvers.hpp`, `logic/src/exact_solvers.cpp`):** Min-Cut / Viterbi DP seam routing with external character exclusion mask barriers (`1e9` infinite penalty), GNC-TLS 2D Translation + Scale alignment (`[tx, ty, scale]`) with Cauchy robust weighting schedule, and Reinhard convex color harmonization in CIELab space with non-clipping constraints.
- **C++ Metaheuristic Solvers (`logic/include/metaheuristics.hpp`, `logic/src/metaheuristics.cpp`):** Particle Swarm Optimization (PSO) for non-convex filter stack tuning and Differential Evolution (DE) for spatial layout packing.
- **C++ Solver Test Suite (`logic/test/test_solvers.cpp`):** Comprehensive unit tests for exact and metaheuristic solvers (100% passing).
- **Python Middleware Package (`middleware/src/hie_middleware/`):** Document manager (`document.py`), versioned contracts (`contracts.py`), neural model adapters (`models/`), RL policy agents (`policies/`), optimization jobs (`jobs/`), pipeline orchestrator (`pipeline/`), acceptance service (`acceptance.py`), session manager (`session.py`), and IPC service (`ipc_service.py`).
- **PySide6 Desktop GUI Integration (`gui/src/tabs/editor/hie_editor_tab.py`):** Wrapped `HieTab` into Image-Toolkit's desktop app, registering the new **Image Editor** category containing the **Hybrid Editor** tab in `_tab_registry.py` and `_relaunch_settings.py`.
- **React/Tauri App UI Integration (`frontend/src/tabs/editor/HieEditorTab.tsx`):** Built HIE editor component and registered the new **Image Editor** category containing the **Hybrid Editor** tab in `App.tsx`.
- Created templates and placeholder documents for research and reports directories under `docs/research/` and `docs/reports/`.
- Created a beautiful, interactive Vue documentation portal in `docs/website/` that parses and displays all repository documentation files dynamically with search, dark mode, alert styling, and navigation.
- Created `website/javascript/` workspace similar to the typescript/ directory but for JavaScript, and added it to root workspace settings and `justfile` tasks.
- Populated `langs/sql`, `langs/graphql`, `langs/mjml`, `r/`, and `ruby/` directories with comprehensive multi-language code snippets.
- Populated `website/html/` (with a premium dark-themed landing page), `website/php/`, and `website/css/` (with a modular CSS framework architecture).
- Populated all `libraries/` subdirectories (including Prisma ORM, Fastlane, Rails, LESS, SASS, SCSS, Stylus, Delta Lake, PHPMailer, Expo, Firebase, TensorFlow for `flow`, PyTorch for `torch`, and Jinja templates).
- Populated package manager configuration examples in the `env/` directory and its subdirectories (including Bower, Conda, C++ CMakeLists.txt/Qt GUI `.pro` files, Gopm, Gradle, Maven, NPM, Pixi, and UV configurations).
- Populated Jupyter notebook examples in `notebooks/` utilizing `notebook_setup.py` utility.
- Added editor settings templates for IntelliJ IDEA, Obsidian, and Sublime Text under the `settings/` directory.
- Initial template scaffolding: root files (`LICENSE`, `README.md`, `.env.example`, `.pre-commit-config.yaml`, `.gitignore`/`.gitattributes`), `.git/` CI/CD, `git/` (`CONTRIBUTING.md`, `codecov.yaml`), `docs/` documentation portal (MkDocs + Sphinx + Structurizr + ADRs), `moon/` roadmap and changelog.
- `.agent/` LLM coding-agent scaffolding: `AGENTS.md` plus generic rules, workflows, prompts, and skills covering all six supported languages.
- Six language module skeletons (`python/`, `typescript/`, `kotlin/`, `rust/`, `go/`, `cpp/`), root workspace orchestrator files, and merged `python/validation/` dev-tooling.
- `java/` Maven module (7th language), wired into CI/pre-commit/justfile/docs alongside the existing six.
- Root Gradle wrapper and multi-project build files pairing with the existing `settings.gradle.kts`.
- `docs/moon/roadmaps/developer_tools.md`: architecture plan for a polyglot `dev/` developer-assistant tool, synthesized from prior art across the org's other repos.
- GitHub Project (V2) backlog automation (`git/` + `.git/workflows/agent_sync.yml`).
- `infra/{k8s,helm,terraform,ansible}/` infra-as-code scaffolding, alongside the relocated `infra/global/docker/`.
- `dev/` developer-assistant tool, milestones D1–D5 of `docs/moon/roadmaps/developer_tools.md`: the `input/protobuf/codegraph.proto` schema, a hand-mirrored Python data model (`core/model.py`), a real AST-based Python import-graph parser (`input/python/parser.py`), multi-source graph aggregation (`core/aggregate.py`), layer classification + forbidden-direction violation detection (`core/layers.py`), Tarjan's-SCC circular-dependency detection (`core/cycles.py`), a self-contained vis.js/Jinja2 HTML report generator (`output/html/report.py`), and a `cli.py` tying it together (`report`/`check` subcommands). 13 passing pytest cases, including a fixture project with an intentional import cycle.

### Changed

- Restoration and watermark-removal proposals remain preview-only. Watermark inpainting requires a user mask and explicit confirmation that the image may be edited.

- Moved `moon/` directory into `docs/` to integrate with the documentation portal, and updated all referencing files.
- Moved `docker/` to `infra/global/docker/` to make room for other infra-as-code stacks; updated all referencing files.

## [0.1.0] — 2026-07-30

### Added

- Repository created from scratch as a GitHub template.
