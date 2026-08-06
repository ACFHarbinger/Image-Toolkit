# Coding-agent guidance

Cel-Shaded-Generator is an offline-first anime drawing tutor and cel-shaded art
application, not a repository template. The first product milestone is a narrow
Krita plugin teaching complete beginners one anime head-and-face construction
method. The standalone Linux editor and C++ engine mature afterward.

## Boundaries

- `src/cel_shaded_generator/`: storage-neutral core; never import Qt or
  Image-Toolkit.
- `gui/src/cel_shaded_generator_gui/`: PySide6 demonstration client.
- `test/`, `gui/test/`: core and headless GUI tests.
- `benchmark/`: deterministic goldens and explicitly invoked measurements.
- `docs/moon/`: authoritative roadmap and changelog.
- `frontend/`, `app/`: deferred scaffolds, not active products.

The core and GUI are independently installable distributions in one uv
workspace. Image-Toolkit is an optional host. Built-in native-heavy operations
must cross `JobRequest`/`Operation` process isolation; interactive ARAP uses a
persistent restartable worker and batch work uses fresh workers.

## Commands

```bash
uv sync --all-packages --all-extras --dev
uv run ruff check src test
uv run --package cel-shaded-generator-gui ruff check gui
uv run mypy src
uv run --package cel-shaded-generator-gui mypy gui/src
uv run pytest test
QT_QPA_PLATFORM=offscreen uv run --package cel-shaded-generator-gui pytest gui/test
uv build --all-packages
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
