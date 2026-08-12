# Roadmap 02: Mathematical Optimization Core

## Executive Summary
This roadmap specifies the high-performance numerical optimization engines in `logic/` and the optimization jobs exposed through `middleware/jobs/`. HIE incorporates both **Exact Solvers** (for non-destructive seam routing, layer packing, and exact color harmonization) and **Metaheuristic / Swarm Intelligence Solvers** (Particle Swarm Optimization [PSO] and Differential Evolution [DE] for autotuning complex multi-parameter filter stacks).

---

## Technical Specifications

### 1. Exact Numerical Solvers (`logic/src/exact_solvers.cpp`)
- **Min-Cut / Max-Flow DP Seam Routing:** Calculates energy-minimizing boundary paths between overlapping composite layers, guaranteeing zero torn anatomy when combined with character exclusion barriers.
- **Dynamic Programming Layer Alignment:** Calculates optimal 2D $[t_x, t_y, s]$ motion alignment with Cauchy GNC-TLS outlier rejection.
- **Convex Color Harmonization:** Solves global luminance and color transfer matrices across layers while enforcing non-clipping boundary constraints.

### 2. Swarm Intelligence & Evolutionary Algorithms (`logic/src/metaheuristics.cpp` & `middleware/src/hie_middleware/jobs/`)
- **Particle Swarm Optimization (PSO):** Autotunes non-convex multi-parameter image processing stacks (curves, vibrance, local contrast, sharpening, noise suppression) to match target aesthetic profiles.
- **Differential Evolution (DE):** Solves non-convex spatial element placement and layout packing, maximizing visual balance metrics (rule-of-thirds, visual weight distribution).

---

## Delivery Phases & Deliverables

| Phase | Milestone | Priority | Output Deliverables |
|---|---|:---:|---|
| **Phase 2.1** | C++ Exact DP & GNC Solvers | High | C++ DP & convex solvers in `logic/src/exact_solvers.cpp` |
| **Phase 2.2** | C++ PSO Filter Tuning Engine | High | Particle Swarm solver (`pso_solve`) in `logic/src/metaheuristics.cpp` |
| **Phase 2.3** | Differential Evolution Composition Solver | Med | DE layout optimizer (`de_solve`) in `logic/src/metaheuristics.cpp` |
| **Phase 2.4** | Python Middleware Optimization Jobs API | High | **Complete.** Cancellable job contract in `middleware/src/hie_middleware/jobs/base.py`, with `exact_dp.py` (`call_hie_exact_solver`, `call_hie_alignment_gnc`) and `metaheuristics.py` (`call_hie_pso`, `call_hie_de`) providing pure-Python reference implementations where one exists. Central `base.hie` pybind11 binding landed (`logic/src/{exact_solvers,metaheuristics}_bindings.cpp`); `middleware/src/hie_middleware/logic_bridge/solvers.py` bridges `pso_solve`/`de_solve`/`solve_seam`/`solve_alignment_gnc`/`solve_color_harmonization` to native. PSO/DE/seam are opt-in, not defaulted (the reference implementations' incremental progress reporting is preserved for job-contract callers); GNC-TLS alignment has no reference implementation at all (no meaningful pure-Python fallback for outlier-rejected correspondence fitting), so `call_hie_alignment_gnc` is native-only and raises `RuntimeError` if `base.hie` isn't available. `solve_color_harmonization`'s native path had a `clamp_beta` sequencing bug (fixed 2026-08-12) and a genuine exact-moments-vs-non-clipping tradeoff for `alpha` far from 1 — resolved as a product decision: `call_hie_exact_solver(..., enforce_bounds=False)` (default) preserves exact moment-matching; `enforce_bounds=True` clamps `beta` into range via native when available or an equivalent pure-Python `_clamp_beta` mirror otherwise, so behavior is identical either way. |
