# Roadmap 02: Mathematical Optimization Core

## Executive Summary
This roadmap specifies the high-performance numerical optimization engines in `logic/` and the optimization jobs exposed through `middleware/jobs/`. HIE incorporates both **Exact Solvers** (for non-destructive seam routing, layer packing, and exact color harmonization) and **Metaheuristic / Swarm Intelligence Solvers** (Particle Swarm Optimization [PSO] and Differential Evolution [DE] for autotuning complex multi-parameter filter stacks).

---

## Technical Specifications

### 1. Exact Numerical Solvers (`logic/src/exact_solvers.cpp`)
- **Min-Cut / Max-Flow DP Seam Routing:** Calculates energy-minimizing boundary paths between overlapping composite layers, guaranteeing zero torn anatomy when combined with character exclusion barriers.
- **Dynamic Programming Layer Alignment:** Calculates optimal 2D $[t_x, t_y, s]$ motion alignment with Cauchy GNC-TLS outlier rejection.
- **Convex Color Harmonization:** Solves global luminance and color transfer matrices across layers while enforcing non-clipping boundary constraints.

### 2. Swarm Intelligence & Evolutionary Algorithms (`logic/src/metaheuristics.cpp` & `middleware/jobs/`)
- **Particle Swarm Optimization (PSO):** Autotunes non-convex multi-parameter image processing stacks (curves, vibrance, local contrast, sharpening, noise suppression) to match target aesthetic profiles.
- **Differential Evolution (DE):** Solves non-convex spatial element placement and layout packing, maximizing visual balance metrics (rule-of-thirds, visual weight distribution).

---

## Delivery Phases & Deliverables

| Phase | Milestone | Priority | Output Deliverables |
|---|---|:---:|---|
| **Phase 2.1** | C++ Exact DP & GNC Solvers | High | C++ DP & convex solvers in `logic/src/exact_solvers.cpp` |
| **Phase 2.2** | C++ PSO Filter Tuning Engine | High | Particle Swarm solver in `logic/src/pso_solver.cpp` |
| **Phase 2.3** | Differential Evolution Composition Solver | Med | DE layout optimizer in `logic/src/de_solver.cpp` |
| **Phase 2.4** | Python Middleware Optimization Jobs API | High | `middleware/jobs/solvers.py` with central `base` pybind11 integration |
