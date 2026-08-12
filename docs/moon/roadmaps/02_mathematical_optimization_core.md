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
| **Phase 2.4** | Python Middleware Optimization Jobs API | High | Cancellable job contract in `middleware/src/hie_middleware/jobs/base.py`, with `exact_dp.py` (`call_hie_exact_solver`) and `metaheuristics.py` (`call_hie_pso`, `call_hie_de`) providing pure-Python reference implementations. Central `base.hie` pybind11 binding landed (`logic/src/{exact_solvers,metaheuristics}_bindings.cpp`); `middleware/src/hie_middleware/logic_bridge/solvers.py` bridges `pso_solve`/`de_solve`/`solve_seam` to native (opt-in, not defaulted — the reference implementations' incremental progress reporting is preserved for job-contract callers). `solve_color_harmonization`'s native path had a `clamp_beta` sequencing bug (fixed 2026-08-12, see `logic/test/test_solvers.cpp`'s `test_color_harmonization_clamp_beta_sequencing`) but stays unbridged: it clamps `beta` into the valid Lab range and the Python reference doesn't, a semantic mismatch that's a product decision, not a mechanical follow-up. |
