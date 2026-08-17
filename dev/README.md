# `dev/` — Development Tool

Modular host for telemetry, crash forensics, benchmarks, and plugins.

Plan: [`docs/moon/roadmaps/development_tool.md`](../docs/moon/roadmaps/development_tool.md)

```bash
PYTHONPATH=dev:debug python -m devtool            # workspace chooser (no daemon)
PYTHONPATH=dev:debug python -m devtool plugins    # name / version / surfaces
PYTHONPATH=debug python -m debugtool list         # Track A analysis (until C2)
```

C1 host: `dev/devtool/host/` (store + settings + discovery). First-party
plugin: `telemetry_workbench`. Session analysis still lives in
`debug/debugtool` until C2 lands the `devtool` alias.
