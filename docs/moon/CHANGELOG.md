# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
