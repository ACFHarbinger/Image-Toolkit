# Cel-Shaded-Generator

Offline-first tools for learning anime drawing, coloring line art and manga,
creating cel-shaded animation, and producing game assets. The immediate product
is a narrow Krita learning plugin for complete beginners; the long-term product
is a standalone Linux desktop editor with a C++ compute engine.

## Current state

This repository is pre-alpha. Today it provides independently installable
Python core and PySide6 GUI packages with working prototypes for:

- scribble and screentone-aware colorization;
- reference-palette color transfer;
- temporal color propagation and graph-cut refinement;
- ARAP mesh puppeteering;
- portable offline project/progress storage;
- crash-contained native solver processes and regression benchmarks.

The promised Krita tutorial loop, personalized redlining, reference-consistent
character model, production animation workflow, and game-asset exporters are
not implemented yet. See the [roadmap](docs/moon/ROADMAP.md).

## Supported development target

- Kubuntu/Linux
- Python 3.11+
- Fully offline runtime
- CPU support for current deterministic solvers
- Consumer NVIDIA GPUs are the target for future local ML inference

Browser and mobile clients are not current requirements. Mobile remains a
far-future full tablet-editing target.

## Install and launch

Install [uv](https://docs.astral.sh/uv/), then from the repository root:

```bash
uv sync --all-packages --all-extras --dev
uv run --package cel-shaded-generator-gui cel-shaded-generator
```

The current executable is a demonstration shell, not the learning alpha.
Installed wheels expose the same `cel-shaded-generator` command.

The in-progress Krita 5.2/Snap plugin has separate, scoped installation steps
in [`integrations/krita/README.md`](integrations/krita/README.md). It currently
shows only an offline placeholder lesson and diagnostics.

## Verify and build

```bash
uv run ruff check logic/src logic/test
uv run --package cel-shaded-generator-gui ruff check gui
uv run mypy logic/src
uv run --package cel-shaded-generator-gui mypy gui/src
uv run pytest logic/test
QT_QPA_PLATFORM=offscreen uv run --package cel-shaded-generator-gui pytest gui/test
uv build --all-packages
uv run python logic/benchmark/run_baseline.py --repeats 5
```

Read [development](docs/DEVELOPMENT.md), [testing](docs/TESTING.md),
[architecture](docs/ARCHITECTURE.md), [portable project format](docs/project_format.md),
and [benchmarks](docs/BENCHMARKS.md) before changing their respective areas.

## Repository layout

| Path | Purpose |
| --- | --- |
| `logic/src/` | Storage-neutral top-level core packages and execution boundary |
| `gui/src/` | Flattened PySide6 demonstration client, imported as `csg_gui` |
| `logic/test/`, `gui/test/` | Core and headless GUI tests |
| `logic/benchmark/` | Deterministic goldens and explicit performance runner |
| `logic/validation/` | Module-graph, LoC, and import-hygiene dev tooling |
| `docs/moon/` | Product roadmap and changelog |
| `frontend/`, `app/` | Deferred scaffolds; not working clients |

Cel-Shaded-Generator is usable standalone. Image-Toolkit is an optional host,
not a runtime dependency.

## License

AGPL-3.0 is available in [LICENSE.md](LICENSE.md). A separate commercial license
for proprietary use is described in [LICENSE.txt](LICENSE.txt).
