# Benchmarks

Micro-benchmarks use **Google Benchmark** to measure performance of core functions.

| Target | Tool | Location |
| --- | --- | --- |
| `hybrid_image_editor_benchmark` | Google Benchmark | `logic/benchmark/greet_benchmark.cpp` |

Run benchmarks with:

```bash
just bench
# Or directly via cmake:
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_BENCHMARK=ON
cmake --build build --target hybrid_image_editor_benchmark
./build/logic/benchmark/hybrid_image_editor_benchmark
```

## Middleware optimization jobs (Track 02)

`middleware/scripts/benchmark_jobs.py` times `call_hie_pso`/`call_hie_de` (the pure-Python
reference implementations) against `logic_bridge.solvers.native_pso_solve`/`native_de_solve`
(the `base.hie` binding, when the compiled `base` extension is importable) across a small set of
standard test functions (`sphere`, `rosenbrock`) of increasing dimension, reporting wall time and
RMS error from the known optimum. Dependency-free — no `pytest-benchmark` — since it's a report
run on demand, not part of the pytest suite.

```bash
cd middleware && python3 scripts/benchmark_jobs.py
```

Reproducibility (same seed → bit-identical trajectory, required for the document model's
deterministic cache-key/undo-redo goals) is asserted as a real test, not just benchmarked — see
`middleware/test/test_reproducibility.py`.
