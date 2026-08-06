# Testing guide

Run the core and GUI suites separately:

```bash
uv run pytest test
QT_QPA_PLATFORM=offscreen uv run --package cel-shaded-generator-gui pytest gui/test
```

Core tests use real NumPy/SciPy/OpenCV implementations. GUI tests run Qt
offscreen and mock selected native calls where the GUI fixture deliberately
replaces OpenCV. Installed-wheel construction is smoke-tested in CI.

Every public behavior needs tests. Numerical work should assert meaningful
invariants and tolerances rather than only shape or absence of exceptions.
Native execution changes must test crash, timeout, cancellation, and next-job
recovery when applicable. Project-format changes require round-trip, migration,
privacy-default, and interrupted-write coverage.

Deterministic golden regressions live under `benchmark/goldens/`; performance
measurements are explicit and do not run as timing gates in ordinary CI. See
[BENCHMARKS.md](BENCHMARKS.md).
