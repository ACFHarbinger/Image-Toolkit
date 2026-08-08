# Cel-Shaded-Generator Core

Storage-neutral core package (`cel-shaded-generator`): colorization,
correspondence, animation/temporal propagation, ARAP rigging, project
persistence, and the crash-contained native execution boundary. Never
imports Qt or Image-Toolkit; the PySide6 client lives in `../gui/`.

From the repository root:

```bash
uv sync --all-packages --all-extras --dev
uv run ruff check logic/src logic/test
uv run mypy logic/src
uv run pytest logic/test
```

See the top-level [README](../README.md) for the full project overview,
and [docs/moon/](../docs/moon/) for the product roadmap and changelog.
