# ADR-0010: Package Renames (`middleware/`, `backend/`) and Submodule Absorption into One CMake Build

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#865](https://github.com/ACFHarbinger/Image-Toolkit/issues/865), [#866](https://github.com/ACFHarbinger/Image-Toolkit/issues/866), [#867](https://github.com/ACFHarbinger/Image-Toolkit/issues/867)

## Context

The Python orchestrator was historically named `backend/` while the C++ `pybind11` core was named `base/`, inverting standard terminology. In addition, four first-party domain libraries — **HIE** (Hybrid Image Editor), **ASP** (Anime Stitch Pipeline), **CSG** (Cel-Shaded Generator), and **CRE** (Content Recommendation Engine) — lived in separate git submodules with fragmented CMake builds, duplicate third-party dependency fetches, and cross-repo `PYTHONPATH` hacks.

## Decision

1. **Sequential mechanical renames (#865, #866):**
   - Rename the Python package `backend/` → `middleware/` first (#865).
   - Rename the C++ `pybind11` module `base/` → `backend/` (`import backend`) second (#866).
2. **Submodule absorption (#867):**
   - Absorb `submodules/{ASP,HIE,CSG,CRE}` into the main repository tree.
   - Expose their Python orchestration through `middleware/src/services/{asp,hie,csg,cre}/`.
   - Unify all C++ sources (ASP matching/bundle-adjust/seam/compositing and HIE render-graph/exact-solvers/metaheuristics), unit tests (`backend_tests` + `hie_solver_tests`), and Google Benchmarks (`base_benchmarks`) into the single `backend/CMakeLists.txt` build tree sharing OpenCV, Eigen3, OpenMP, SQLCipher/libsodium, and OpenSSL linkage.

## Consequences

- `just build::build-base` and `just test-base-cpp` compile and test the entire native C++ surface in one CMake invocation.
- Submodule version skew and cross-repository `sys.path` bootstrapping are eliminated.
