# Development guide

## Setup

Install Git and `uv`, clone the repository, then run:

```bash
uv sync --all-packages --all-extras --dev
```

No cloud account, API key, Image-Toolkit checkout, CUDA installation, Node,
JVM, Rust, Go, or C++ compiler is required for the current Python product.

## Common commands

| Task | Command |
| --- | --- |
| Core tests | `uv run pytest logic/test` |
| GUI tests | `QT_QPA_PLATFORM=offscreen uv run --package cel-shaded-generator-gui pytest gui/test` |
| Core lint | `uv run ruff check logic/src logic/test` |
| GUI lint | `uv run --package cel-shaded-generator-gui ruff check gui` |
| Core types | `(cd logic && uv run mypy src)` |
| GUI types | `(cd gui && uv run mypy src)` |
| Build both distributions | `uv build --all-packages` |
| Launch demo | `uv run --package cel-shaded-generator-gui cel-shaded-generator` |
| Explicit benchmark | `uv run python logic/benchmark/run_baseline.py --repeats 5` |

`mypy` discovers its config by walking up from the current directory, not
from the checked path, so the core/GUI type-check commands above must run
from inside `logic/`/`gui/` rather than with a root-relative path.

Keep core code independent of Qt and Image-Toolkit. Host integrations consume
public core contracts. Native-heavy built-in operations must use the isolated
execution boundary. Do not serialize arbitrary callables across it.

The committed `frontend/` and `app/` directories are deferred scaffolds, not
active build targets. C++ is the intended long-term engine language, but ports
must be justified by representative measurements first.
