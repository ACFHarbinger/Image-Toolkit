# HIE Middleware Jobs (`middleware/jobs/`)

The `jobs` package hosts high-level wrappers for mathematical optimization workflows, bridging Python job orchestration with performance-critical C++ numerical solvers in `logic/`.

## Optimization Methods

- **Exact Numerical Methods (`jobs/exact_dp.py`):**
  - **Dynamic Programming Seam Routing:** Calculates energy-minimizing boundary paths across overlapping composite layers, incorporating character exclusion masks to prevent visual tearing.
  - **GNC Alignment:** Dynamic programming $2\text{D}$ transformation alignment $[t_x, t_y, s]$ with Graduated Non-Convexity Cauchy M-estimators.
  - **Convex Color Harmonization:** Solves global luminance and color transfer matrices with non-clipping boundary constraints.

- **Metaheuristic & Swarm Solvers (`jobs/metaheuristics.py`):**
  - **Particle Swarm Optimization (PSO):** Multi-parameter filter stack autotuning (curves, vibrance, local contrast, sharpening, noise suppression).
  - **Differential Evolution (DE):** Non-convex spatial element placement and layout packing maximizing visual balance metrics.

## Job Lifecycle

Jobs support asynchronous execution, progress reporting callbacks, intermediate parameter sampling, and user cancellation via the standard middleware contract.
