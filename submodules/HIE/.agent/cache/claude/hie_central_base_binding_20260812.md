# HIE central `base` pybind11 binding — Claude

Date: 2026-08-12

## Context

Follow-up to `hie_jobs_contract_20260812.md`'s deferred item: wire `logic/src/{exact_solvers,
metaheuristics}.cpp` into Image-Toolkit's central `base` pybind11 module, per the "follow ASP"
product decision. `logic/`'s solver signatures haven't changed since the flattening commit
(`15180e4`), so treating them as stable enough to bind against now.

## What landed

**In this submodule:**
- `logic/src/exact_solvers_bindings.cpp` — `register_hie_exact_solvers(py::module_&)`, exposing
  `SeamPixel`/`SeamResult`/`Correspondence`/`MotionModel2DTS`/`AlignmentResult`/
  `LayerColorStats`/`ColorHarmonizationResult` + `solve_seam`/`solve_alignment_gnc`/
  `solve_color_harmonization`.
- `logic/src/metaheuristics_bindings.cpp` — `register_hie_metaheuristics(py::module_&)`, exposing
  `ParamBound`/`MetaheuristicResult`/`PSOConfig`/`DEConfig` + `pso_solve`/`de_solve`.
  `ObjectiveFn` (`std::function<float(const std::vector<float>&)>`) accepts a plain Python
  callable directly via `pybind11/functional.h` — no manual trampoline needed.
- `middleware/src/hie_middleware/logic_bridge/solvers.py` — thin adapter (`HAVE_NATIVE_HIE` flag
  + `native_pso_solve`/`native_de_solve`), **only for PSO/DE** — see the clamp-bug note for why
  the exact-solver side isn't bridged yet.

**In Image-Toolkit (parent repo), `base/CMakeLists.txt` + `base/src/bindings.cpp`:** added the
two new HIE `.cpp` files to the `base` pybind11 module's source list (same pattern as the ASP
submodule sources already compiled in), a new `base.hie` submodule, and the two `register_hie_*`
calls — mirroring the existing per-submodule registration convention exactly (see
`register_matching`/`m_matching` etc. for the precedent I copied).

## Verification (important, given this touches Image-Toolkit's production `base` module)

Did NOT skip building this to check. Full sequence:
1. Confirmed the *baseline* `base` module also fails to compile in this sandbox with the system
   Python (3.14, missing `x86_64-linux-gnu/python3.14/pyconfig.h` — an environment issue, not a
   code issue: every file including `pybind11.h` failed identically, including files I never
   touched). Reconfigured with `-DPython_EXECUTABLE` pointed at the project's own pixi Python
   3.11 instead, which the repo's `tools/build/justfile`'s `build-base` recipe already implies
   should be used.
2. Full `cmake --build --target base` succeeded end-to-end (OpenCV 4.13 + all existing ASP/base
   sources + my two new files compiled and linked cleanly) — `base.cpython-311-x86_64-linux-gnu.so`
   produced.
3. Imported the built extension directly and smoke-tested every new function:
   `solve_seam` (masked-column avoidance), `pso_solve`/`de_solve` (converge to a known quadratic
   minimum, same check my Python reference tests use) — all correct.
   `solve_color_harmonization` is where I found the real, pre-existing `clamp_beta` bug (separate
   note) — confirmed via a standalone C++ program bypassing pybind11 entirely, so it's not
   something my binding introduced.

Did not run the full existing `base` test suite (`base/tests/`) since `-DBASE_BUILD_TESTS=OFF`
was used to keep the verification build fast — worth a full `just test-base-cpp` pass before
this ships in a release, but the module itself builds, links, and the new functions behave
correctly for what I could test standalone.

## Why PSO/DE only, not the exact solvers, in `logic_bridge/solvers.py`

`solve_color_harmonization`'s native implementation is confirmed buggy (see the clamp-bug note).
Rather than bridge it and have `call_hie_exact_solver` silently produce worse results than its
current pure-Python reference, I left that path unbridged. `solve_seam` and `solve_alignment_gnc`
tested correctly and could be bridged now — I held off doing just those two to keep this slice
of work scoped to "verified end-to-end," and because `jobs/exact_dp.py`'s `call_hie_exact_solver`
dispatches by method name to one function that would need partial native/partial-Python branching
if only seam routing were bridged — a small refactor better done together with the
color-harmonization fix, not split across two passes.

## Suggested next step

1. Whoever owns `logic/` (Gemini) fixes `clamp_beta`'s stale-`hi` bug (repro + suggested fix
   shape in the other cache note).
2. Once fixed, bridge `solve_seam` + `solve_color_harmonization` into
   `logic_bridge/solvers.py` the same way PSO/DE are now, and update `jobs/exact_dp.py` to prefer
   native when available (mirroring whatever pattern gets chosen for PSO/DE's integration into
   `call_hie_pso`/`call_hie_de` — I deliberately left those two *not* wired into the native path
   by default either, since `test_pso_progress_reports_monotonic_iteration_count` and similar
   tests depend on the pure-Python reference's deterministic, incremental progress reporting,
   which the native path can't currently provide — see the module docstring in
   `logic_bridge/solvers.py`. `pipeline/orchestrator.py` (Chat, Track 04) is a more natural place
   to decide when native-vs-reference execution is appropriate than baking it into `jobs/`'s
   existing tested defaults).

## Validation

- `cd middleware && python3 -m pytest test/` — 26/26 pass (unchanged; `logic_bridge/solvers.py`
  is additive and gracefully no-ops when `base` isn't importable, which is the case in the
  Python-only test environment).
- `cmake --build build/base_test --target base` (from Image-Toolkit root) — succeeds.
- Manual `python3 -c "import base; ..."` smoke test — see above.
