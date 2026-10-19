# Contributing to Cel-Shaded-Generator

Cel-Shaded-Generator is pre-alpha and currently targets an offline Kubuntu/Krita
learning workflow. Check the [roadmap](../docs/moon/ROADMAP.md) and an existing
issue before starting broad work; narrow, independently verifiable changes are
preferred.

## Setup and verification

```bash
uv sync --all-packages --all-extras --dev
uv run ruff check logic/src logic/test
uv run --package cel-shaded-generator-gui ruff check gui
(cd logic && uv run mypy src)
(cd gui && uv run mypy src)
uv run pytest logic/test
QT_QPA_PLATFORM=offscreen uv run --package cel-shaded-generator-gui pytest gui/test
```

New public behavior requires tests and documentation. Numerical changes need
meaningful correctness tolerances and, where performance claims motivate the
change, an updated explicit baseline. Preserve offline operation and privacy
defaults. Never make artwork retention, global learning statistics, telemetry,
or uploads implicit.

Core code must not import Qt or Image-Toolkit. Built-in native-heavy work must
cross the isolated operation boundary. Treat `frontend/` and `app/` as deferred
scaffolds unless their roadmap status changes. Do not begin a C++ rewrite without
representative evidence and a stable contract to port.

Use focused commits, keep unrelated worktree changes intact, complete the pull
request template, and report the commands used for verification.
