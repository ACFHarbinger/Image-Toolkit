# Changelog

Notable changes to Image-Toolkit documentation, tooling, and product surfaces.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed

- Re-wired root `just asp-benchmark-assess` (and related ASP benchmark/triage recipes) after Anime-Stitch-Pipeline moved to `submodules/ASP`. Dispatch now calls `submodules/ASP/backend/src/cli/eval_dispatch.py` via the Image-Toolkit venv with a correct `PYTHONPATH`, avoiding broken `backend/controllers/bench_eval_dispatch.py` and bare workspace `uv run` failures on CSG’s workspace-only pyproject.
- Added compatibility shim at `backend/controllers/bench_eval_dispatch.py` for older scripts/docs.

### Added

- Docs stubs: `DEVELOPMENT.md`, `SECURITY.md`, `TESTING.md`, `GLOSSARY.md`, this changelog.
- Agent coordination for docs/website migration under `.agent/cache/AGENT_BUS.md` and `.agent/reports/grok/`.
