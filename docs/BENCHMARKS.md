# Benchmarks

Micro-benchmarks use **Google Benchmark** to measure performance of core functions.

| Target | Tool | Location |
| --- | --- | --- |
| `hybrid_image_editor_benchmark` | Google Benchmark | `logic/benchmark/greet_benchmark.cpp`, `logic/benchmark/solvers_benchmark.cpp` |

Run benchmarks with:

```bash
just bench
# Or directly via cmake:
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_BENCHMARK=ON
cmake --build build --target hybrid_image_editor_benchmark
./build/logic/benchmark/hybrid_image_editor_benchmark
```

## Native solver benchmarks (Track 02, C++)

`logic/benchmark/solvers_benchmark.cpp` measures the native `logic/src/{exact_solvers,
metaheuristics}.cpp` implementations directly (no Python/pybind11 overhead), complementing the
middleware-level report below:

| Benchmark | What it measures |
| --- | --- |
| `BM_SolveSeam/{rows}/{cols}` | Seam DP over a random energy grid, at a small (256×256) and a full-frame (1080×1920) size |
| `BM_SolveAlignmentGnc/{n}` | GNC-TLS alignment with 10% synthetic outliers, at 50/500/5000 correspondences |
| `BM_SolveColorHarmonization` | Single closed-form affine color transfer (no iteration — expect low-nanosecond timing) |
| `BM_PsoSolve/{dim}`, `BM_DeSolve/{dim}` | PSO/DE minimizing Rosenbrock at 2D and 6D — same test function as `middleware/scripts/benchmark_jobs.py`'s Python-level report, so native/reference timings are directly comparable |

Sample run (release build, this environment): seam DP scales from ~113μs (256×256) to ~4ms
(1080×1920); GNC-TLS alignment scales from ~1.4μs (50 correspondences) to ~128μs (5000); color
harmonization is ~4ns (a handful of arithmetic ops, no loop); PSO/DE range from ~39μs (PSO, 2D) to
~788μs (DE, 6D). Absolute numbers are hardware-dependent — rerun locally for real numbers.

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
