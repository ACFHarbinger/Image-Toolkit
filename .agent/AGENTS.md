# Coding-agent guidance

Cel-Shaded-Generator is an offline-first anime drawing tutor and cel-shaded art
application, not a repository template. The first product milestone is a narrow
Krita plugin teaching complete beginners one anime head-and-face construction
method. The standalone Linux editor and C++ engine mature afterward.

## Boundaries

- `logic/`: the storage-neutral core workspace member (its own
  `logic/pyproject.toml`, package name `cel-shaded-generator`), never
  imports Qt or Image-Toolkit:
  - `logic/src/`: top-level domain packages (`colorization`, `editor`,
    `learning`, `project`, etc.) plus the `execution`/`runtime` worker
    boundary modules.
  - `logic/test/`: core tests.
  - `logic/benchmark/`: deterministic goldens and explicitly invoked
    performance measurements.
  - `logic/validation/`: module-graph, LoC, and import-hygiene dev tooling.
- `gui/`: the PySide6 demonstration client workspace member (its own
  `gui/pyproject.toml`, package name `cel-shaded-generator-gui`), depends
  on `logic/` via the uv workspace.
- `integrations/krita/`: the Krita plugin bridge; imports the `logic/`
  package but is not installed as part of it.
- `docs/moon/`: authoritative roadmap and changelog.
- `frontend/`, `app/`: deferred scaffolds, not active products.
- The root `pyproject.toml` holds only `[tool.uv.workspace]` (members
  `gui`, `logic`) and a shared `[dependency-groups] dev` group; it is not
  itself an installable package.

The core and GUI are independently installable distributions in one uv
workspace. Image-Toolkit is an optional host. Built-in native-heavy operations
must cross `JobRequest`/`Operation` process isolation; interactive ARAP uses a
persistent restartable worker and batch work uses fresh workers.

## Commands

```bash
uv sync --all-packages --all-extras --dev
uv run ruff check logic/src logic/test
uv run --package cel-shaded-generator-gui ruff check gui
uv run pytest logic/test
QT_QPA_PLATFORM=offscreen uv run --package cel-shaded-generator-gui pytest gui/test
uv build --all-packages
```

`mypy` discovers its `[tool.mypy]` config by walking up from the current
directory, not from the checked path, so it must be run from inside each
workspace member rather than with a root-relative path (running
`uv run mypy logic/src` from the repository root finds no config and
misresolves cross-package imports):

```bash
(cd logic && uv run mypy src)
(cd gui && uv run mypy src)
```

## Product constraints

- Kubuntu/Linux first; browser and mobile are deferred.
- Runtime must remain fully offline.
- Retaining artwork history and contributing to global learner statistics are
  separate opt-ins and default off.
- Suggestions require artist acceptance; automation level is user-selectable.
- Users may install arbitrary local models/plugins, but built-ins must not
  pickle arbitrary callables across the worker boundary.
- Consumer NVIDIA GPUs are future ML targets; current solvers run on CPU.
- C++ is the long-term engine language, selected ports remain evidence-driven.

Keep changes focused, preserve unrelated worktree state, add tests for public
behavior, and update roadmap/changelog when milestone status changes.
