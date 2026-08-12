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
| `BM_SolveSeam_Scalar/{rows}/{cols}` (default build) or `BM_SolveSeam_SIMD/{rows}/{cols}` (`-DHIE_ENABLE_SIMD_SEAM=ON`) | Seam DP over a random energy grid, at 256×256, 1080p, and 4K sizes |
| `BM_SolveAlignmentGnc/{n}` | GNC-TLS alignment with 10% synthetic outliers, at 50/500/5000 correspondences |
| `BM_SolveColorHarmonization` | Single closed-form affine color transfer (no iteration — expect low-nanosecond timing) |
| `BM_PsoSolve/{dim}`, `BM_DeSolve/{dim}` | PSO/DE minimizing Rosenbrock at 2D and 6D — same test function as `middleware/scripts/benchmark_jobs.py`'s Python-level report, so native/reference timings are directly comparable |

Sample run (release build, this environment): GNC-TLS alignment scales from ~1.4μs (50
correspondences) to ~128μs (5000); color harmonization is ~4ns (a handful of arithmetic ops, no
loop); PSO/DE range from ~39μs (PSO, 2D) to ~788μs (DE, 6D). Absolute numbers are
hardware-dependent — rerun locally for real numbers.

### `solve_seam` SIMD fast path (`HIE_ENABLE_SIMD_SEAM`)

`solve_seam`'s DP row fill (the min-of-3-predecessors + argmin per column) is vectorizable across
columns, since each row only reads the previous row — no same-row dependency. An opt-in AVX2 (x86)
/ NEON (ARM) fast path lives behind a CMake option, off by default so the production `base` build
stays portable to CPUs without AVX2:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DHIE_ENABLE_SIMD_SEAM=ON
cmake --build build --target hie_solver_tests
./build/logic/test/hie_solver_tests   # runs test_seam_simd_matches_scalar_reference
```

That test compares the SIMD path against a deliberately separate, non-shared scalar
reimplementation (`logic/test/test_solvers.cpp`) across grid sizes chosen to exercise block-size
boundaries (1, 2, 3, 7, 8, 9, 10, 17, 64, 257 columns × 1, 2, 5 rows, with scattered masked cells)
and asserts bit-for-bit identical output — vectorization here is a performance-only change, not an
algorithm change.

Measured speedup, this environment (built twice — once with the option off, once on — since it's a
compile-time, not runtime, dispatch):

| Grid | Scalar | AVX2 | Speedup |
| --- | --- | --- | --- |
| 256×256 | 186μs | 99μs | ~1.9× |
| 1080×1920 | 7.1ms | 5.2ms | ~1.4× |
| 3840×2160 (4K) | 46.3ms | 43.3ms | ~1.07× |

Speedup shrinks at 4K — the working set (multiple full-frame `float`/`int` rows) likely exceeds
cache at that size, shifting the bottleneck from compute (where AVX2 helps) to memory bandwidth
(where it doesn't). The NEON path is implemented by reasoning from ARM intrinsic semantics but
**not empirically verified** — this development environment is x86_64-only; run
`test_seam_simd_matches_scalar_reference` on real ARM hardware before relying on it.

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
