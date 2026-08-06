# **Comprehensive Visual Analytics & Interpretability Roadmap**

*Targeting Codebase Topology, ML Interpretability, Pipeline Diagnostics, and Omniscient Debugging*

---

## Table of Contents

- [Implementation Status](#implementation-status)
- [Phase 1: The Interactive Meta-Graph (Codebase Topology)](#phase-1-the-interactive-meta-graph-codebase-topology)
- [Phase 2: ML Model & Loss Landscape Visualizer](#phase-2-ml-model--loss-landscape-visualizer)
- [Phase 3: ASP Stage-by-Stage CV Diagnostics](#phase-3-asp-stage-by-stage-cv-diagnostics)
- [Phase 4: Statistical & Information-Theoretic Failure Analysis](#phase-4-statistical--information-theoretic-failure-analysis)
- [Phase 5: Resource, Latency, and Causal Profiling](#phase-5-resource-latency-and-causal-profiling)
- [Phase 6: Semantic Code Analysis & Vulnerability Discovery](#phase-6-semantic-code-analysis--vulnerability-discovery)
- [Phase 7: Omniscient Debugging & Deterministic Replay](#phase-7-omniscient-debugging--deterministic-replay)
- [Phase 8: Distributed Observability & High-Cardinality Telemetry](#phase-8-distributed-observability--high-cardinality-telemetry)
- [Phase 9: Formal Verification & State Space Visualization](#phase-9-formal-verification--state-space-visualization)
- [Phase 10: Topological Data Analysis (TDA) of Pipeline Architecture](#phase-10-topological-data-analysis-tda-of-pipeline-architecture)
- [Architectural Blueprint: A Zero-Copy Analytics Pipeline](#architectural-blueprint-a-zero-copy-analytics-pipeline)
- [Phase 11: ASP Benchmark Analytics & Visual Diagnostics](#phase-11-asp-benchmark-analytics--visual-diagnostics)
- [Phase 12: Benchmark Coverage Expansion](#phase-12-benchmark-coverage-expansion)

---

## Implementation Timeline

> **Legend** — *Node fill:* new feature (blue) · augmentation (violet) · infrastructure (cyan) · performance (orange) · research (slate) · security (dark red) · testing (amber) · docs (green) — *Node border:* ✅ complete (green, thick) · 🔄 in-progress (amber, thick) · ⬜ planned (slate, thin) · 🚫 blocked (red) · ⏸ on hold (purple) — *Edges:* `==>` critical blocking dependency · `-->` sequential dependency · `-.->` alternative/independent research track · `---` complements (parallel work)

```mermaid
flowchart TD
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px

    %% ── Completed Infrastructure ──────────────────────────────────────────
    RUST["🦀 Rust Math Backbone
    base/src/math/
    6 modules · 49 unit tests ✅"]:::infra:::done

    TS["📘 TypeScript Math Backbone
    frontend/src/math/
    7 modules + benchmark.ts ✅"]:::infra:::done

    DASH["📊 Benchmark Dashboard
    Streamlit → Tauri/React
    7-page SVG charts ✅"]:::feature:::done

    %% ── Planned Foundation ────────────────────────────────────────────────
    ARCH["🏗️ Architectural Blueprint
    Zero-Copy Analytics Pipeline
    Rust aggregation · TS GPU render"]:::infra:::planned

    %% ── Planned Feature Phases ────────────────────────────────────────────
    P1["Phase 1
    Interactive Meta-Graph
    Codebase Topology"]:::feature:::planned

    P2["Phase 2
    ML Loss Landscape Visualizer
    Weight/gradient landscape"]:::feature:::planned

    P3["Phase 3
    ASP Stage-by-Stage
    CV Diagnostics"]:::augment:::planned

    P4["Phase 4
    Statistical & Info-Theoretic
    Failure Analysis"]:::research:::planned

    P5["Phase 5
    Resource, Latency &
    Causal Profiling"]:::perf:::planned

    P6["Phase 6
    Semantic Code Analysis
    & Vulnerability Discovery"]:::security:::planned

    P7["Phase 7
    Omniscient Debugging
    & Deterministic Replay"]:::feature:::planned

    P8["Phase 8
    Distributed Observability
    & High-Cardinality Telemetry"]:::infra:::planned

    P9["Phase 9
    Formal Verification
    & State Space Visualization"]:::research:::planned

    P10["Phase 10
    Topological Data Analysis
    TDA of Pipeline Architecture"]:::research:::planned

    P11["Phase 11
    ASP Benchmark Analytics
    & Visual Diagnostics"]:::testing:::planned

    P12["Phase 12
    Benchmark Coverage
    Expansion"]:::testing:::planned

    %% ── Dependency Edges ──────────────────────────────────────────────────
    RUST  ==> ARCH
    TS    ==> ARCH
    RUST  ==> P1
    TS    ==> P1
    ARCH  --> P1

    P1    --> P2
    P1    --> P3
    P1    --> P10
    DASH  --> P11

    P3    --> P4
    P4    --- P5
    P5    --> P7
    P7    --> P8

    P3    --> P11
    P11   --> P12

    P6    -.-> P9
```

---

## Implementation Status

| Layer | Status | Details |
|-------|--------|---------|
| **Rust math backbone** (`base/src/math/`) | ✅ Complete | 6 modules, 49 unit tests passing |
| **TypeScript math backbone** (`frontend/src/math/`) | ✅ Complete | 7 modules + `benchmark.ts`, `tsc --noEmit` clean |
| **Benchmark dashboard migration** (Streamlit → Tauri/React) | ✅ Complete | Tauri commands, SVG charts, 7-page dashboard, `App.tsx` wired |
| Phase 1–10 feature implementation | ⬜ Not started | Backbone provides all mathematical primitives |
| **ASP Benchmark Analytics (Phase 11)** | ✅ Complete (2026-07-30) | 11.1–11.5 (per-test) done in the ASP evaluation tool, issue #123; 11.6/11.7/11.8/11.9/11.10 (corpus-wide) done in `bench_anime_stitch.py`'s report, issue #69 |
| **Benchmark Coverage Expansion (Phase 12)** | 🔄 Partial (2026-07-30) | 12.1/12.2/12.3/12.5/12.6/12.7 shipped; 12.4 rescoped (see §12.4); 12.8 rescoped (see §12.8) |

### Rust backbone — `base/src/math/`

| Module | Contents |
|--------|----------|
| `linalg` | `Matrix`, PCA via power iteration, dot/norm/normalize, gram-schmidt |
| `stats` | mean/variance/stddev/percentile/histogram/covariance matrix/pearson |
| `information` | Shannon entropy, KL/JS divergence, mutual information (NMI), cross-entropy |
| `distance` | Euclidean/Manhattan/Cosine/Bhattacharyya/Hellinger/pairwise/condensed matrix |
| `graph` | `Graph`/`UnionFind`, BFS/DFS, Kahn topo sort, Tarjan SCC, Kruskal MST/max-MST |
| `dim_reduce` | Classical MDS, geodesic distances (Dijkstra), t-SNE affinity calibration |

### TypeScript backbone — `frontend/src/math/`

| Module | Contents |
|--------|----------|
| `linalg` | Vec2/Vec3/VecN ops, Mat3/Mat4, clamp/saturate |
| `stats` | mean/variance/percentile/pearson/normalize01/z-score/histogram |
| `colormap` | viridis/plasma/magma/inferno/coolwarm (17-stop lookup tables + `applyColormap`) |
| `distance` | euclidean/cosine/manhattan/hamming/pairwise/condensed |
| `graph` | `Graph`/`GraphNode`/`GraphEdge`, BFS, topo sort, Fruchterman-Reingold layout |
| `signal` | Cooley-Tukey FFT/IFFT, power spectrum, Hann/Hamming windows, autocorrelation |
| `index` | Barrel re-exports for all sub-modules |

---

This roadmap outlines the development of a suite of interactive, highly optimized tools designed to give developers and researchers a profound understanding of the Image Toolkit codebase, specifically the Anime Stitch Pipeline (ASP) and its underlying Neural Networks.

Leveraging a Rust backend for time-efficient data parsing/aggregation and a TypeScript frontend for visually stunning, GPU-accelerated dashboards, these tools will expose the hidden geometries, failure modes, and execution topologies of the system.

See [`research/Analytics and Codebase Visualization Research.md`](../../research/Analytics%20and%20Codebase%20Visualization%20Research.md) for the full technical research underpinning every item on this roadmap.

---

## **Phase 1: The Interactive Meta-Graph (Codebase Topology)**

**Goal:** Build a semantic "graph of graphs" allowing zooming from high-level architecture down to granular function execution and AST parsing.

* **1.1 Rust-Powered AST & Dependency Parser:**
  * Develop a Rust CLI/daemon utilizing **tree-sitter** to statically parse the Python (`backend/src/animation`) and Rust codebases.
  * Extract semantic relationships: module imports, class inheritance, function calls, and data flow.
  * **Option A — SCIP Semantic Indexing:** Emit a **SCIP** (Source Code Intelligence Protocol) protobuf index via `scip-python` and `rust-analyzer`. Ingest into Rust via `nusy-codegraph` / `code-graph-cli` — produces Apache Arrow RecordBatches enabling sub-millisecond blast-radius queries (e.g., transitive impact of modifying `bundle_adjust.py`).
  * **Option B — tree-sitter-graph DSL:** Use the declarative `tree-sitter-graph` crate to write AST-to-graph mapping rules that extract pipeline-specific semantics (stage transitions, telemetry emission sites) without full SCIP indexing.

* **1.2 GPU-Accelerated Force-Directed Dashboard:**
  * **Primary Option — Cosmograph (cosmos.gl):** 100% GPU-bound force-directed simulation via WebGL 2.0 compute/fragment shaders. Ingests Apache Arrow buffers directly into GPU memory; 60fps semantic zooming through 1M+ nodes. Pairs with **DuckDB-WASM** for in-browser SQL filtering of graph nodes by failure impact or algorithmic complexity.
  * **Fallback Option — sigma.js / WebGL:** Viable for graphs up to ~10k nodes; high customization for node glyphs and imagery.
  * **Simple DAG Option — react-flow:** HTML/SVG DOM rendering (~1k nodes); ideal for the explicit, user-editable pipeline DAG view.
  * Implement **Semantic Zooming:** Zoom 0 = modules (`animation`, `rlhf`, `mfsr`); Zoom 1 = files (`compositing.py`, `bundle_adjust.py`); Zoom 2 = classes and functions; Zoom 3 = AST or call graph.
  * Implement **Edge Bundling:** **Skeleton-Based Edge Bundling (SBEB)** clusters edges by directional sector and iteratively routes long-distance architectural dependencies along shared skeleton paths, preventing visual clutter without losing directional information.

* **1.3 Software Cartography (Semantic Layout):**
  * Apply **Latent Semantic Indexing (LSI)** to codebase vocabulary (function names, comments, string literals) to map source code into a high-dimensional vector space.
  * Project via **Multidimensional Scaling (MDS)** into 2D, minimizing a stress function so semantically related modules cluster together physically (e.g., `feature_matching.py` and `bundle_adjust.py`).
  * Render as a topographic map rather than a node-link diagram — modules become landmasses, dependencies become edges on geographic terrain.

* **1.4 Dependency Structure Matrix (DSM) — DONE, already implemented, 2026-07-27.** Checked before building anything (per this session's established discipline): a full equivalent already exists and is actively enforced, just not via the imagined Lattix/IntelliJ tooling or a literal matrix rendering — a stronger, automated form of the same idea.
  * **Cyclic-dependency detection** (the matrix's "above-diagonal" violations): `backend/src/utils/validation/check_circular_imports.py` — full AST-based module-import graph builder + iterative Tarjan's SCC algorithm, with an optional interactive `pyvis` HTML visualization. Wired into `just check-circular-imports` and `just module-graph`. Verified working end-to-end this session: 0 cycles across 210 `backend/src` modules and 0 cycles across 236 `gui/src` modules.
  * **Layered-architecture violations** (the matrix's "valid layered dependencies" half): `import-linter` (`pyproject.toml [tool.importlinter]`, §5.11A/A.17) already declares 3 `forbidden`-type contracts (backend core must not import GUI; `gui.src.utils` must not import other GUI layers; `gui.src.classes` must not import `gui.src.tabs`) and enforces them via `lint-imports`. Verified working this session: 578 files / 1147 dependencies analyzed, all 3 contracts kept, 0 broken.
  * Not done, out of scope for this item: any ISO 26262 compliance-report generation (no evidence this project targets that certification) — flagged as an unsupported claim in the original text, not something to build speculatively.

* **1.5 Dynamic Execution Tracing:**
  * Overlay dynamic execution paths onto the static graph. Trace a single ASP run from `video_ingestion.py` through `flow_refine.py` to `sr_stitcher.py`, highlighting active nodes in real-time or via a playback slider.

---

## **Phase 2: ML Model & Loss Landscape Visualizer** {: #phase-2-ml-model--loss-landscape-visualizer }

**Goal:** Open the "black box" of the deep learning models (e.g., Reward Models in RLHF, GANs, LoRAs) by visualizing weight evolution and objective function geometry.

* **2.1 Loss Landscape 3D Surface Plotter:**
  * Implement **Filter Normalization** (Li et al., 2018) to project the high-dimensional loss/reward surface into a 2D/3D visualizable space without scale-invariance distortion from Batch Normalization layers.
  * Plot the trajectory of the optimizer (e.g., AdamW8bit, Adafactor) across the non-convex loss surface using a TS-based 3D renderer (e.g., Three.js or Plotly.js).
  * Libraries: **`loss-landscapes`** (PyPI), **`loss-landscape-analysis` (LLA)**, or **DeepCAVE** for hyperparameter landscape exploration.

* **2.2 Hessian-Based Landscape Geometry (PyHessian):**
  * Compute the **Hessian Trace** via Hutchinson's algorithm (`Tr(H) ≈ E[z^T H z]` using Rademacher random vectors) to measure local loss landscape sharpness.
  * Compute **Eigenvalue Spectral Density (ESD)** via Stochastic Lanczos Quadrature (SLQ) — builds a tridiagonal matrix whose Ritz values approximate extremal Hessian eigenvalues.
  * Flat minima (low Tr(H)) indicate robust generalization; sharp minima indicate propensity to overfit on out-of-distribution pipeline inputs.
  * Library: **PyHessian** (GPU-accelerated, integrates with PyTorch training loops).

* **2.3 Weight & Gradient Trajectory Tracking:**
  * Track the evolution of network weights and gradients during training (e.g., in `stitch_trainer.py`).
  * Use **PCA**, **t-SNE**, or **UMAP** dimensionality reduction (computed rapidly in Rust) to visualize how latent representations separate different domains over epochs.
  * Platforms: **MLflow**, **TensorBoard**, or **DeepCAVE** for programmatic access to optimization trajectories and hyperparameter importance.
  * Architecture visualization: **Netron** for static network architecture inspection.

* **2.4 Activation Atlases & Feature Inversion:**
  * **Activation Atlases:** Aggregate millions of spatial activations across the benchmark dataset → UMAP → explorable grid of learned visual concepts. Exposes what compositional features the seam-blending model has encoded.
  * **CPPN Feature Inversion:** Use **Compositional Pattern Producing Networks (CPPNs)** as image parameterization during feature inversion. CPPNs generate resolution-independent, highly cohesive visualizations revealing what specific neural pathways respond to during seam-blending and synthesis phases.

* **2.5 Attention & Feature Map Overlays:**
  * For diffusion models and transformers, generate interactive heatmaps of self-attention and cross-attention layers.
  * Overlay these maps directly onto input images in the GUI to see *where* the model focuses when assessing seam quality or filling backgrounds.

---

## **Phase 3: ASP Stage-by-Stage CV Diagnostics**

**Goal:** Create visual debuggers for classic Computer Vision algorithms that interact within the pipeline, diagnosing why specific mathematical transformations fail.

* **3.1 Rerun.io as the Unified CV Telemetry Engine:**
  * Integrate the **rerun-sdk** Python logger throughout the ASP. Rerun uses an Entity-Component-System (ECS) architecture purpose-built for spatial and CV data:
    * `Transform3D` + `Pinhole` archetypes log exact translation, rotation, and camera intrinsics of the Bundle Adjustment step.
    * `Points3D` archetype logs 3D inliers, auto-projecting world coordinates via the pinhole camera matrix.
    * `Tensor` archetype logs FFT profiles and Sobel heatmaps, mapped to custom color scales and overlaid on source imagery.
  * Define temporal timelines (e.g., `frame_index`, `gnc_optimization_step`) enabling scrubbing through a single optimization pass to observe DP seam evolution at 60fps.
  * Embed the **Rerun WebAssembly viewer** in the React dashboard — no install required, streams `.rrd` files over the network.

* **3.2 Feature Matching & Inlier Geometry (The "Bones"):**
  * Visualize SIFT/ORB/LoFTR keypoint matches between frames.
  * Plot fundamental matrix/homography residual errors as a heatmap to instantly spot where rigid body assumptions break (e.g., character movement vs. background panning).
  * Render **2D quiver plots** of sub-pixel alignment errors overlaid on source frames — arrow direction and magnitude represent disparity between estimated homography and true feature locations.

* **3.3 Bundle Adjustment Residual Graphs:**
  * Visualize reprojection errors before and after GNC-TLS Bundle Adjustment (`bundle_adjust.py`).
  * Show camera poses (translations/rotations) in a 3D coordinate space to ensure the virtual camera path is smooth and continuous.

* **3.4 Seam Blending & Frequency Domain Mismatch (The "Skin"):**
  * **Spatial Diagnostics:** Render the intelligent scissors routing over the DP seam.
  * **Frequency Diagnostics:** Visualize FFT spatial-frequency profiles (referencing `_seam_freq_profile` in `compositing.py`) to show low/high-frequency mismatches at stitching boundaries.
  * **Gradient Diagnostics:** Display Sobel gradient-direction coherence vectors as a quiver plot across the seam. Circular distance `d_c(∇a, ∇b) = 1 - cos(∇a - ∇b)` rendered as a heatmap highlights photometric tearing regions.

---

## **Phase 4: Statistical & Information-Theoretic Failure Analysis** {: #phase-4-statistical--information-theoretic-failure-analysis }

**Goal:** Analyze the entire ASP test suite/benchmark corpus (97+ tests) to mathematically cluster failure modes and identify compounding errors.

* **4.1 Information Theory Metrics:**
  * Calculate **Mutual Information (MI)** between pipeline stage outputs and ultimate failure. Does a high residual in Stage 2 (Registration) absolutely dictate a failure in Stage 11 (Compositing), or does the pipeline recover?
  * Use **Shannon Entropy** `H(X) = -Σ P(x) log P(x)` to measure per-frame uncertainty. High-entropy frames (complex foliage) require aggressive RANSAC thresholds; low-entropy frames (flat sky) lack features for rigid alignment.
  * **KL Divergence** tracks data drift through pipeline stages; MI evaluates non-linear dependency between stage outputs.

* **4.2 Formal Causal Discovery (Root Cause Analysis):**
  * Move beyond simple correlation clustering to **causal discovery** — mathematically proving that a failure in Stage 2 *causes* a failure in Stage 11.
  * **Constraint-Based Methods (PC algorithm):** Uses conditional independence tests (Fisher-z, HSIC) to iteratively prune a fully connected graph into a causal skeleton. Implementation: **causal-learn** (Python, CMU Tetrad).
  * **Score-Based Methods (GES):** Greedy Equivalence Search optimizes BIC over Markov equivalence classes. Also available in causal-learn.
  * **Gradient-Based Methods (NOTEARS, DAG-GNN):** Gradient-based causal structure learning scalable via PyTorch GPU. Implementation: **gcastle** (Huawei), ingests Parquet telemetry logs.
  * **Unified API:** **dodiscover** (PyWhy ecosystem) provides a wrapper for systematic algorithm application across these backends.
  * Emit telemetry as **Apache Arrow / Parquet** from benchmark runs for ingestion by causal discovery backends.

* **4.3 Sub-System Destructive Interference Detection:**
  * Implement ablation study visualizations. Map the performance of Algorithm A alone vs. B alone vs. A+B.
  * Highlight benchmark tests where A and B engage in **destructive interference** — measuring negative **Average Treatment Effect (ATE)** on the global success metric (e.g., color correction Stage 4.5 undoing geometric alignment Stage 3, verified via causal DAG).

* **4.4 Failure Mode Clustering:**
  * Aggregate test results and use unsupervised learning (K-Means, DBSCAN) to cluster failures based on pipeline telemetry as a complement to causal discovery.
  * Auto-generate cluster narratives: *"Cluster A failures occur when Frame Entropy < 0.2 AND Reprojection Error > 1.5px. Origin: `fg_register.py`, cascading to `_check_seam_rms_contrast_gate` in `compositing.py`."*

---

## **Phase 5: Resource, Latency, and Causal Profiling**

**Goal:** Track the physical constraints of the pipeline and go beyond "where time is spent" to answer "what actually matters for throughput."

* **5.1 Flame Graphs & Icicle Charts:**
  * **Flame Graphs** (Brendan Gregg): y-axis = stack depth, x-axis = alphabetically sorted sample population (not time), width = relative CPU consumption. Generated via **py-spy** (speedscope JSON/SVG, minimal overhead) or **VizTracer** (C functions, GC, asyncio events — multi-threaded concurrent timelines).
  * **Icicle Charts:** Inverted flame graphs (root at top) — better for deep stacks where entry points remain fixed; superior for top-down bottleneck attribution.
  * Rendered via **Perfetto's tracing UI** for interactive timeline exploration.

* **5.2 Causal Profiling (coz — Virtual Speedups):**
  * Flame graphs identify *where* CPU time is spent but cannot answer: *"Will optimizing this hot path actually speed up the program?"* In concurrent systems, accelerating one thread often moves the wait to the next synchronization barrier.
  * **coz** (Causal Profiling) applies "virtual speedups": to simulate a 20% speedup of Function A, it forces all other concurrent threads to sleep for an equivalent relative duration. By applying this stochastically across thousands of source lines, coz generates a causal impact curve predicting exact throughput gain per unit of localized optimization — using Little's Law for latency estimation.
  * Extensions: **COZ+** (what-if analysis for JS parsing, Chromium); **SLOWPOKE** (distributed microservice-level causal profiling via network-selective slowdowns).

* **5.3 VRAM/RAM Memory Arenas:**
  * Real-time visualization of memory allocation, crucial for identifying leaks in the streaming image merger or SAM-2 interactive masking stages.

---

## **Phase 6: Semantic Code Analysis & Vulnerability Discovery** {: #phase-6-semantic-code-analysis--vulnerability-discovery }

**Goal:** Enable deep semantic querying of the codebase using Code Property Graphs — unifying AST, control flow, and data flow into a single queryable database to detect anti-patterns, data flow violations, and security vulnerabilities.

* **6.1 Code Property Graph (CPG) Architecture:**
  * Generate a CPG merging three classical program representations:
    * **AST:** Hierarchical syntactic structure.
    * **Control Flow Graph (CFG):** Execution order and branching.
    * **Program Dependence Graph (PDG):** Data flow and control dependencies across non-adjacent code.
  * CPGs enable queries impossible on isolated ASTs: verifying that an untrusted input source (PDG) reaches a sensitive sink (AST/PDG) without passing through sanitization (CFG).

* **6.2 Joern (OverflowDB + Scala DSL):**
  * **Joern** generates CPGs via language-specific frontends (including Python and binary via Ghidra) using **fuzzy parsing** — no working build environment required.
  * Stores the CPG in **OverflowDB**, a specialized high-performance graph database replacing Neo4j.
  * Queries via a Scala-based DSL with imperative and functional traversals; identifies specific parameter indices, dispatch types, and polymorphic method resolution chains.

* **6.3 CodeQL (Datalog-Driven Variant Analysis):**
  * Compiles the subject program into a relational database (AST + DFG + CFG).
  * Queries written in **QL** — a declarative Datalog-derived language using first-order logic with recursion; naturally suited for taint-tracking and points-to analysis.
  * **Variant analysis:** A single query discovers every variant of a vulnerability across the full codebase (Python + Rust).
  * **Incremental Datalog solvers** (iQL on Viatra Queries) reduce analysis update time to seconds for differential PR review.

| CPG Engine | Database | Query Language | Compilation | Primary Strength |
|---|---|---|---|---|
| **Joern** | OverflowDB (Graph) | Scala DSL | Fuzzy (no build required) | Fast ingestion, extensible traversal |
| **CodeQL** | Relational Database | QL (Datalog) | Strict compilation required | Whole-program depth, variant analysis, taint tracking |

---

## **Phase 7: Omniscient Debugging & Deterministic Replay** {: #phase-7-omniscient-debugging--deterministic-replay }

**Goal:** Eliminate non-reproducible failures entirely by recording instruction-accurate execution traces and exposing them as queryable databases rather than linear replay logs.

* **7.1 Deterministic Replay with rr (Mozilla):**
  * **rr** captures all non-deterministic inputs to user-space processes from the Linux kernel — system calls, thread scheduling, RDTSC instructions — enabling perfect instruction-level replay with identical memory/register layout.
  * Enables **deterministic reverse execution**: place a hardware data watchpoint on a corrupted canvas pixel and step backward in time to the exact instruction that erroneously overwrote it.
  * Zero code modification required; pairs with GDB for familiar debugging workflow.

* **7.2 Pernosco — The Queryable Execution Database:**
  * **Pernosco** compiles the rr execution trace into an indexed, queryable database. Instead of stepping through time, developers execute relational queries across the temporal axis.
  * Click any `printf` output → instantly retrieve every historical instance that line was executed, with exact stack frames, local variables, and memory state.
  * **Bug Capsules:** Content-addressable replayable bundles (event log + filesystem snapshots + network packets). Integrate into CI/CD: when a flaky test fails, an AI pipeline loads the capsule, queries for suspicious interleavings, delta-debugs the trace, and proposes a bisected patch.

---

## **Phase 8: Distributed Observability & High-Cardinality Telemetry** {: #phase-8-distributed-observability--high-cardinality-telemetry }

**Goal:** Provide production-grade observability across multi-process ASP runs and expose statistical outliers across high-cardinality benchmark dimensions.

* **8.1 OpenTelemetry — Unified Metrics, Logs, and Traces:**
  * Instrument the ASP pipeline with the **OpenTelemetry** SDK (vendor-neutral standard for metrics + logs + distributed traces).
  * Each pipeline stage runs as a **span** with a `trace_id` and `span_id` injected into the execution context — revealing exact causal relationships and stage latency distribution.
  * Export to **Jaeger** (traces), **Prometheus** (metrics), or any OTLP-compatible backend.

* **8.2 Honeycomb BubbleUp — High-Cardinality Root Cause Analysis:**
  * For benchmark telemetry with high-cardinality dimensions (unique test IDs, feature flag combinations, frame content hashes), deploy **Honeycomb BubbleUp**.
  * Statistically compares the distribution of all high-cardinality attributes within an anomalous subset against the baseline to surface the exact combination of variables causing performance degradation — without requiring engineers to know which dimensions to investigate first.

---

## **Phase 9: Formal Verification & State Space Visualization** {: #phase-9-formal-verification--state-space-visualization }

**Goal:** Formally specify and model-check critical concurrent ASP subsystems (e.g., the thread-pool seam computation, async RLHF batch scheduling) to prove safety and liveness invariants before deployment.

* **9.1 TLA+ Specifications + ModelWisdom:**
  * Write **TLA+** (Temporal Logic of Actions) specifications for critical concurrent subsystems — proving that thread-pool seam cache writes are linearizable and that the RLHF feedback loop terminates.
  * **TLC model checker** explores the full finite state machine.
  * **ModelWisdom** renders the state-transition graph with tree-based structuring, node folding, color-highlighted property violations, and interactive click-through from graphical transitions back to triggering TLA+ formulas.
  * **TLA+ Debugger** supports Watch expressions and backward/forward state-space stepping.

* **9.2 Symbolic Execution & Concolic Testing:**
  * Apply **Concolic Testing** (KLEE / SAGE) to critical validation functions (`_validate_affines`, `_filter_edges`) to auto-generate test inputs guaranteed to cover all conditional branches.
  * SMT solver generates concrete inputs for each path condition; the concolic engine substitutes concrete values when constraints become intractable (e.g., hash functions, floating-point saturation).
  * Visualize symbolic exploration as a branching timeline of path conditions.

* **9.3 SMT Solver Interpretability:**
  * **Axiom Profiler:** Parses Z3 telemetry to reconstruct the causal graph of quantifier instantiations — identifies **matching loops** (infinite instantiation cycles from overly permissive E-matching triggers) visually.
  * **Z3Hydrant:** Maps SMT solver execution telemetry to audio signals via sonification. A matching loop produces characteristic rapid-fire clicking; the human auditory system's superior temporal pattern recognition summarizes millions of solver events in seconds.

---

## **Phase 10: Topological Data Analysis (TDA) of Pipeline Architecture**

**Goal:** Apply algebraic topology to extract scale-invariant structural signatures from the ASP's function call graphs and execution traces — enabling malware-resistant code attribution and robust anomaly detection.

* **10.1 Persistent Homology over Function Call Graphs:**
  * Embed FCG nodes using LLM-generated code embeddings → construct a Vietoris-Rips filtration as the distance threshold ε increases.
  * Track birth/death of topological features by **Betti numbers**:
    * **β₀:** Connected components (isolated subgraphs).
    * **β₁:** One-dimensional loops/cycles (recursive call patterns).
    * **β₂:** Two-dimensional voids (missing dependency layers).
  * Long-lived features on the **persistence barcode** represent fundamental architectural invariants; short-lived features are noise.
  * Libraries: **Ripser**, **Gudhi**, or **Giotto-TDA**.

* **10.2 TDA-Based Behavioral Fingerprinting:**
  * The persistence of specific loop structures (β₁) in the call graph acts as a topological signature of programmer style or module behavior — robust to code obfuscation, renaming, and control-flow flattening.
  * Integrate TDA persistence signatures as features into a **GNN classifier** for detecting architectural regressions or unexpected behavioral drift across pipeline versions.

* **10.3 TDA on ASP Execution Traces:**
  * Apply persistent homology to dynamic memory allocation traces and benchmark telemetry point clouds (each benchmark run = a point in high-dimensional stage-metric space).
  * β₀ changes (new connected components) indicate novel failure modes never before seen; β₁ changes (new cycles) indicate inter-stage feedback loops forming under new conditions.

---

## **Architectural Blueprint: A Zero-Copy Analytics Pipeline**

| Architectural Layer | Core Technologies | Responsibilities |
|---|---|---|
| **Data Generation** (Python) | PyTorch, OpenCV, PyHessian, causal-learn, rerun-sdk, OpenTelemetry | ML execution, CV transforms, Hessian trace, causal DAG, telemetry emission |
| **Aggregation Backend** (Rust) | tokio, tree-sitter, nusy-codegraph, SCIP crate, gRPC/WebSockets | AST parsing, semantic graph construction, Arrow zero-copy aggregation, streaming |
| **Visual Analytics** (TypeScript/React) | cosmos.gl, Three.js, Rerun Wasm, DuckDB-WASM, Perfetto UI | GPU force graphs, 3D surfaces, temporal scrubbing, SQL filtering, flame graphs |

---

## **Phase 11: ASP Benchmark Analytics & Visual Diagnostics** {: #phase-11-asp-benchmark-analytics--visual-diagnostics }

**Goal:** Transform the benchmark dashboard from a summary viewer into a root-cause analysis tool — every failure in the pipeline should be diagnosable from the dashboard without needing to rerun or inspect raw JSON files.

**Priority: HIGH — directly supports ASP quality improvement loop.**

> **Scope split, 2026-07-29 (S266, issue #123).** The *per-test* half of this
> phase — 11.1–11.5 — is **DONE**, implemented inside the ASP evaluation tool
> rather than here, because those five charts answer "why did *this* test score
> badly" while a human is looking at that test, which is precisely the moment
> the answer is useful. They live in
> `backend/benchmark/evaluation/logic/diagnostics.py`, render in the inspector's
> Diagnostics tab (`just asp-benchmark-assess`), and are built from
> `evaluation/other/metrics_view.py`'s flattened series — no metric is
> recomputed, so a chart can never disagree with the report or the verdict logic.
> Per-item notes are inline below.
>
> The **corpus-wide** items stayed here: 11.6 (stage memory waterfall), 11.9
> (cross-run regression dashboard — the evaluation tool has a per-test slice
> of this via a baseline-run selector, but not the corpus view), and 11.10
> (experiment tracker). 11.7 and 11.8 were already done in the static report;
> as of 2026-07-30 (issue #69), 11.6/11.9/11.10 are too — see their entries
> below.

### 11.1 Per-Seam Quality Strip Visualizer — DONE (2026-07-29, issue #123)
Implemented as `diagnostics.seam_quality_figure`: one bar per inter-strip seam
boundary per comparator, with the worst seam annotated. **Deviation from the
spec below, deliberately**: the colour bands use the pipeline's *own* ghost
thresholds (clean < 30, ghost likely 30–60, ghost confirmed ≥ 60, from
`_compute_cqas`) rather than the generic ≥0.80 / 0.60–0.80 / <0.60 split this
item proposed — `ghost_seam_scores` is a 0–100 SIQE scale where lower is
better, so the proposed bands would have been both inverted and unanchored.
Renders an explanation rather than an empty axes when a test has no per-seam
scores, which is the normal case for a SCANS fallback (it has no ASP seams to
score). Linking the driving seam to the DP seam-path cache key is *not* done —
the cache key isn't in the results JSON.

### 11.1 (original spec)
- Render ghost-score, NCC coherence, and Bhattacharyya color-similarity as per-seam bar charts (one bar per seam boundary) instead of only showing the worst-case scalar.
- Color-code each bar: green (≥0.80), amber (0.60–0.80), red (<0.60) — maps directly to the composite quality thresholds.
- ASP-specific: highlight the seam that drives `composite_quality` down and link it to the DP seam path cache key.

### 11.2 Alignment Drift Diagnostic Chart — DONE (2026-07-29, issue #123)
`diagnostics.alignment_drift_figure`: per-frame `tx`/`ty` as a line chart above a
bar chart of the `dy_steps`/`dx_steps` inter-frame deltas, with any step past 2×
the median magnitude flagged in red and both `dy_cv`/`dx_cv` in the title. All
three spec bullets as written.

### 11.3 Photometric Correction Profile — DONE (2026-07-29, issue #123)
`diagnostics.photometric_figure`: `bg_lums` as bars against `applied_gains` on a
twin axis, reference luminance as a guide line, gains deviating from 1.0 by more
than 15% marked with an ✗, and "N/total frames corrected, gain range [min, max]"
in the title. All three spec bullets as written.

### 11.4 Edge Quality & Matching Breakdown — DONE (2026-07-29, issue #123)
`diagnostics.matching_figure`: donut of `matching.methods` beside a
`weight`-vs-`n_pts` scatter, points coloured by frame gap (`j − i`) — a failing
skip-link is a different problem from a failing adjacent pair, which the flat
scatter in the spec would have hidden — and raw/filtered counts plus the kept-%
in the title. The last bullet (flagging datasets with fewer than N−1
high-confidence edges) is **not** done: "high-confidence" has no threshold
defined anywhere in the pipeline, and inventing one here would put a number in
the UI that no gate agrees with.

### 11.5 Ground Truth Comparison Panel — DONE (2026-07-29, issue #123)
Two halves, in the place each belongs. The **table** is
`evaluation/ui/metrics_panel.py`'s ground-truth section (all four GT metrics ×
ASP/Simple, winner tinted by direction). The **chart** is
`diagnostics.gt_comparison_figure`: grouped bars normalized per row, since PSNR
in dB sits an order of magnitude above the SSIM rows and the comparison that
matters is ASP-vs-Simple *within* a row. **Regression detection** is done via a
baseline-run selector in the Diagnostics tab: pick any older
`anime_stitch_*.json` and metrics that moved against their good direction by
more than 3% are called out — the same 3% margin `_gt_verdict` itself uses to
avoid noise-driven verdict flips, rather than this item's unqualified ">3%".

### 11.6 Stage-Level Memory Profiling — DONE (2026-07-30, issue #69)
The RSS tracking already existed as `_log_resource(tag)`'s console-only
prints (§2.6 instrumentation, added for a host-freeze diagnosis); it wasn't
attached to the result JSON. `_log_resource` now takes an optional `store`
dict, `process_dataset` threads a per-dataset `stage_memory_rss_mb: Dict[str,
float]` accumulator through all 9 of its call sites (`dataset_start` through
`dataset_end`), and `_build_result` emits it as
`stage_memory_rss_mb: {stage_name: rss_mb}` in the benchmark JSON — exactly
the schema this item specced. `_report_stage_memory_waterfall()` renders a
waterfall PNG (`stage_memory_waterfall.png`) of RSS averaged per stage
across every dataset in the run, plus a table with the delta from the
previous stage and a callout naming the single largest-growth stage.

### 11.7 Frame Selection Telemetry — DONE (2026-07-27, issue #69)
- Capture and emit `frame_selection: {original_count, smart_select_count, spatial_dedup_count, final_count, selection_mode}` in the benchmark JSON. — data capture already existed pre-#69 (`_build_result()` in `bench_anime_stitch.py`); no pipeline changes needed.
- Dashboard: stacked bar showing frames kept vs dropped at each stage of frame reduction. — added: `_report_frame_selection_telemetry()` renders an aggregate "Frame Selection Telemetry" section (once, near the top of the report) with a matplotlib stacked-bar PNG (`frame_selection_telemetry.png`, kept/dropped per stage per dataset) plus a per-dataset markdown table (original/smart-select/spatial-dedup/final counts, drop counts, drop %, selection mode).
- Identify datasets where smart selection drops >40% of frames (indicates extreme frame redundancy or selection bugs). — added: any dataset over the 40% threshold gets its drop-% bolded in the table and is called out in a summary callout line with links to its `#asp_testNN` section.

### 11.8 Fallback Root Cause Classifier — DONE (2026-07-27, issue #69)
- Classify each SCANS fallback by its trigger gate: `alignment_failed`, `composite_gate_sc`, `composite_gate_sb`, `ghost_gate`, `render_exception` (plus `seam_vis_gate`, a 6th trigger site added to the pipeline after this list was written — the classifier discovers it dynamically rather than hardcoding exactly 5 gates). — data capture already existed pre-#69 (`_fallback_reason` assignments throughout the dataset loop, surfaced as `fallback_reason` in `_build_result()`); no pipeline changes needed.
- Emit `fallback_reason` in the dataset result JSON. — already existed.
- Dashboard: aggregate fallback cause distribution across all datasets — shows which gate is causing the most fallbacks. — added: `_report_fallback_breakdown()` renders a "Fallback Root Cause Breakdown" section (once, near the top of the report) with a total-fallback count, a per-gate count table (parsed from the `fallback_reason` prefix before the first `:`), and a per-gate list of which datasets hit it, linked to their `#asp_testNN` anchor.

### 11.9 Cross-Run Regression Dashboard — DONE (2026-07-30, issue #69)
`detectRegressions()` in `frontend/src/math/benchmark.ts` operates on the
generic `GeneralBenchmark` schema (`{time.avg_sec, memory.avg_peak_mb}`),
which doesn't match `bench_anime_stitch.py`'s ASP-specific per-dataset
fields (`metrics_asp.composite_quality`, `metrics_asp.ghosting_siqe`,
`time.total_sec`) — calling it directly wasn't an option, so
`detect_regressions()` (Python) is a same-threshold reimplementation (5%
quality drop / 10% ghosting increase / 20% time increase, this item's own
numbers) against those fields instead. `_find_latest_baseline()` picks the
most recent prior `anime_stitch_*.json` from `backend/benchmark/output/`
(there's no `--baseline` CLI flag — this auto-discovers it, since
`generate_report()` always runs before the current run's own JSON is
written). `_report_regression_dashboard()` renders a 🔴/🟢 per-dataset table
with the delta % for each of the three metrics.

### 11.10 Comparative Seam Configuration Experiment Tracker — DONE (2026-07-30, issue #69)
`_build_result()` now stamps every dataset with
`experiment_label: os.environ.get("ASP_EXPERIMENT_LABEL")` (unset/`None` by
default) — one label per run rather than per-dataset tagging, since a run is
the unit an experiment actually varies. `_report_experiment_comparison()`
groups datasets by label and renders a comparison table (dataset count, mean
`composite_quality`, mean `total_sec` per label) with a callout naming the
best-quality and fastest labels; runs with no label set (the common case)
get a one-line note instead of an empty table.

---

## **Phase 12: Benchmark Coverage Expansion**

**Goal:** Identify all unmonitored performance-critical and correctness-critical code paths across the Rust core, Python backend, GUI, and mobile layers, then instrument them with targeted benchmarks.

**Current gap analysis:**

| Module | Current Coverage | Impact of Blindspot |
|--------|-----------------|---------------------|
| `base/src/image_converter.rs` | ❌ None | Cannot detect Rust image conversion regressions |
| `base/src/image_merger.rs` | ❌ None | Merge quality and speed unknown at scale |
| `base/src/image_finder.rs` | ❌ None | File-system scan performance on large directories |
| `base/src/file_system.rs` | ❌ None | Bulk file enumeration bottlenecks |
| `gui/src/helpers/image/image_loader_worker.py` | ❌ None | LRU thumbnail cache RAM/throughput unknowns |
| `backend/src/animation/compositing.py` (isolated) | ⚠️ Via ASP | Seam DP, DSFN ramp, Poisson blend not individually profiled |
| `backend/src/animation/matching.py` (isolated) | ⚠️ Via ASP | LoFTR vs phase-correlation trade-off not quantified |
| `backend/src/animation/bundle_adjust.py` (isolated) | ⚠️ Via ASP | Spanning-tree filter and GNC re-solve overhead unknown |
| PostgreSQL + pgvector query latency | ⚠️ Partial | Vector similarity search at 10k/100k image scale not benchmarked |
| App startup time | ❌ None | JVM + Qt + Rust cold-start latency unmonitored |
| App memory (full lifecycle) | ❌ None | Gallery RAM with 100/500/1000 images not tracked |
| Web crawlers (Selenium) | ❌ None | Crawl throughput and timeout rate not measured |
| Mobile (Kotlin/Swift) | ❌ None | Android/iOS render and network performance untouched |

### 12.1 Rust Core Image Processing Benchmarks (HIGH PRIORITY) — **DONE, 2026-07-27**
**Stale premise found and corrected before implementing**: this bullet's
"Create `backend/benchmark/bench_rust_image_processing.py`" is wrong on two
counts — the Rust `base` module was fully retired to C++ well before this
phase was written (see `project_cpp_migration` history), and the file it
asks to create already exists as `backend/benchmark/bench_cpp_image_processing.py`.
That file was silently broken: 5 of its 8 benchmarks called C++ binding
names that don't exist (`cpp_core.convert_image`, `cpp_core.merge_images`,
`cpp_core.scan_directory`), each suppressed with a `# pyrefly: ignore
[missing-attribute]` comment rather than fixed — meaning static analysis
already knew about the gap and nobody acted on it (flagged, not fixed, by
an earlier session this same day; see issue #76/Performance 3.6). Fixed all
5 to the real API (`convert_single_image`, `merge_images_vertical`/
`_horizontal`, `scan_files_single`), also correcting stale "Rayon" doc
references (Rust-only, the real C++ path uses OpenMP). **Verified**: ran
the full corrected file end-to-end — all 10 benchmarks pass (all ✓, no
exceptions), confirming this is a genuine fix, not just a name swap that
happens to parse.

### 12.2 ASP Stage Isolation Benchmarks (HIGH PRIORITY) — **DONE, 2026-07-30**
Created `backend/benchmark/bench_asp_stages.py`, 9 benchmarks on synthetic
panning frames: `_pairwise_match` classical-chain vs with a real
`LoFTRWrapper` attached (guarded — skips cleanly if no GPU/weights);
`_bundle_adjust_affine` with vs without `_spanning_tree_inlier_filter`
(§1.1B); `_composite_foreground` with a cold vs a pre-warmed
`seam_path_cache` dict; `_ecc_refine` at `ECC_MAX_ITER` = 20/50/80 via a
module-attribute monkeypatch (the constant is read fresh from the `ecc`
module on every call, not captured at import time, so this varies it
without touching the pipeline). **Stale premise found**: "with/without
Poisson seam blend" isn't benchmarkable — `_poisson_seam_blend` was removed
from the active compositing module in the 2026-07-09 "great trim" (S200)
along with GraphCut (measured worse than the DP seam path by that same
trim); it survives only in `backend/src/core/image_merger/_legacy_compositing.py`,
a different (non-ASP) feature. Not implemented; documented in the file's
own module docstring rather than silently dropped. **Verified**: ran the
file end-to-end, all 9 benchmarks pass (LoFTR variant included — a real
GPU+weights were available in the verifying environment).

### 12.3 GUI Thumbnail Loading Benchmarks (HIGH PRIORITY) — **DONE, 2026-07-27**
Created `backend/benchmark/bench_gui_thumbnails.py` exactly per spec:
time/memory for `base.load_image_batch()` at N={100, 500, 1000}; LRU
cache miss-then-fill (1000 images through a maxsize=300
`LRUImageCache`, exercising eviction) vs a warm-cache hit path (100
images, repeated lookups, no decode); a direct QImage-vs-QPixmap memory
comparison for 300 cached 180px thumbnails. Runs under
`QT_QPA_PLATFORM=offscreen` (no visible window, per this project's GUI
benchmark convention) — a real `QGuiApplication` instance is still
needed for `QPixmap` construction, kept alive process-wide via a module
global. **Verified**: ran end-to-end, all 6 benchmarks pass. The
QImage/QPixmap comparison produced a genuinely useful number, not just
a smoke-test pass: 300 thumbnails cost 26.1MB as QImage alone, +37.2MB
more once QPixmap copies are also created (63.3MB total) — a direct,
measured confirmation of `LRUImageCache`'s own design rationale
(storing QImage, not QPixmap, to avoid the platform backing-store
copy), not previously measured, only asserted in a docstring.

### 12.4 Database Query Profiling at Scale (MEDIUM) — **rescoped, 2026-07-27**
**Checked before extending anything**: this bullet's premise
(`pgvector` ANN search, `HNSW` vs `IVFFlat`) targets
`backend/src/database/image_database.py::PgvectorImageDatabase`, the
legacy Postgres-backed image database. Per
`unified_database.md`'s own DB.6 status ("Postgres retirement... mostly
done (S211)") and the still-open archival item (issue #64, "archive
legacy Postgres code"), this is an actively-retiring system — building
new benchmark investment against it (Bulk insert, HNSW/IVFFlat
comparison work that Postgres-side code is slated to be deleted) would
not be a good use of this phase's effort. **Not implemented as
originally scoped.** The forward-looking equivalent already exists and
is a better target for a future session: `search_repo.py`'s new
`filter_media()`/`filter_entities()` SQL methods (shipped this session,
issue #63/`unified_database.md` §DB.5) already have correctness tests
in `backend/test/database/test_unified_repos.py` but no *scale*
benchmark (10k/100k-row FTS/filter query latency) — that's the item to
build once someone picks this back up, not a pgvector ANN benchmark for
a database half-way out the door. No code shipped for this sub-item;
this note is the deliverable.

### 12.5 App Lifecycle Memory Profiling (MEDIUM) — **DONE, 2026-07-30**
New `backend/src/core/lifecycle_memory.py`: a phase-tagged RSS logger
(`snapshot(phase)`, `history()`, `alerts()`) mirroring the ASP pipeline's own
`_log_resource()` pattern but for the GUI app's lifecycle. Wired into
`backend/src/app.py::launch_app` at the three phases that fire on every real
run without needing synthetic credentials: `qt_init` (right after
`QApplication(sys.argv)`), `login_window_shown`, and `main_window_shown`
(which, since `VaultManager`/JVM start happens inside the login flow between
those two points, captures the cumulative JVM-start + first-window-construct
cost). Alerts when a phase grows RSS by more than `LIFECYCLE_RSS_ALERT_MB`
(default 200MB, this item's own number; env-var overridable). The "after
gallery load (100/500/1000 images)" phase this item also names can't be
driven from a fixed app.py lifecycle point (it depends on whatever
tab/directory a user opens first) — instead, `backend/benchmark/bench_app_lifecycle.py`
covers it in a controlled, repeatable way via the same `base.load_image_batch()`
path §12.3 already benchmarks for throughput, now wrapped in
`lifecycle_memory.snapshot()` so the alert logic runs against real RSS
deltas. **Verified**: both files run end-to-end (unit tests for the alert
threshold logic in `backend/test/core/test_lifecycle_memory.py`; the
benchmark script ran live, e.g. observed +16MB/+26MB/+12MB for the
100/500/1000-image phases on real image batches — under the 200MB
threshold, so no alert fired, which is itself a useful negative result).

### 12.6 Compositing Component Isolation (MEDIUM) — **DONE, 2026-07-30**
New `backend/benchmark/bench_compositing_components.py`: `_seam_cut()` (S10
vectorized DP) at the item's own 96-seam count, across three canvas heights
(100/500/2000px); `_soft_seam_weight()` (S17 per-pixel DSFN) at canvas
widths 500/2000/5000px; `_build_seam_cost_map()` (S33 column barrier) at
foreground-mask fractions 10%/50%/90% (an exact controllable split, not a
noisy random mask). `_poisson_seam_blend()` (S21) isn't benchmarked here for
the same reason it isn't in §12.2 — removed in the S200 trim, nothing left
in the active pipeline to measure. **Verified**: ran end-to-end, all 9
benchmarks pass with real scaling visible (e.g. `_seam_cut` at h=2000 took
~7x longer than at h=100, consistent with its per-pixel DP cost).

### 12.7 Web Crawler Telemetry (LOW-MEDIUM) — **DONE (scoped down), 2026-07-30**
**Premise partially stale on inspection**: the actual HTTP requests happen
inside the compiled `base` C++ extension (`base.run_board_crawler`), which
only calls back into Python once per successful download (`on_image_saved`)
and via free-form `on_status` progress strings — there is no per-request
hook crossing the pybind boundary, so true per-request timing and
response-code tracking isn't available from Python without new C++-side
instrumentation (out of scope here). What's built instead, in
`ImageBoardCrawler` (`backend/src/web/crawlers/image_board_crawler.py`):
exact whole-crawl `elapsed_sec`/`images_per_sec` (from the real
`on_image_saved` count), plus best-effort `timeout_count`/`captcha_count`/
`error_count` derived by substring-matching `on_status` text — coarse (only
as good as whatever the C++ side happens to emit), documented as such in
the module docstring rather than presented as real response-code data.
`backend/benchmark/bench_web_crawlers.py` drives this against the three
real crawlers and saves a General-suite JSON, gated behind
`RUN_LIVE_CRAWLER_BENCHMARK=1` (unset by default — this file makes real
outbound requests to third-party image boards, not something to run
unattended/in CI). **Verified**: 8 unit tests on the telemetry counters
(`backend/test/web/test_image_board_crawler.py`) pass with a mocked
`base.run_board_crawler`; the benchmark script's default (opted-out) path
ran end-to-end with zero network calls made.

### 12.8 Mobile Performance Baselines (LONG-TERM) — **rescoped, 2026-07-30**
**Not implemented — three independent blockers found, all checked before
writing anything**:
- **Android FPS/scroll benchmarking** needs `androidx.benchmark.macro`
  Macrobenchmark instrumented tests running against a real device or
  emulator; `app/android/build.gradle.kts` has no such dependency
  configured, and this environment has no `adb`/emulator reachable (`adb
  devices` fails — command not found). Gradle/Kotlin toolchains ARE present
  (`gradle`, `kotlinc`), so the Gradle module/dependency setup itself is
  buildable — there's just nothing to execute it against here.
- **"Glide vs Coil thumbnail load time"** has no first side to benchmark:
  neither Glide nor Coil is a dependency anywhere in `app/android/build.gradle.kts`;
  the one place image loading is mentioned
  (`ImagePreviewFragment.kt:141`) is a mocked stub with a comment reading
  "Real app uses Glide/Coil" — aspirational, not implemented. There's no
  A/B to measure yet.
- **iOS is unbuildable in this environment at all**: this is a Linux host
  with no Xcode/macOS toolchain (`xcodebuild`: not found), so no XCTest or
  Instruments run can happen here regardless of app state. Independently,
  `app/ios/Package.swift` declares an `ImageToolkitTests` test target and a
  `Cryptography` target whose directories (`app/ios/ImageToolkitTests/`,
  `app/ios/Cryptography/`) don't exist on disk — the SwiftPM manifest itself
  doesn't resolve today, before any benchmark-specific work would even
  start.

No code shipped for this sub-item; this note is the deliverable (same
approach as §12.4's rescope). The path back to this, in order: (1) populate
the missing iOS SwiftPM targets so the package builds at all, on a
macOS+Xcode host; (2) integrate a real thumbnail loader (Glide or Coil) into
the Android app before there's anything to A/B; (3) add the
`androidx.benchmark.macro` Gradle module and run it against a connected
device/emulator, which this sandboxed Linux CI-style environment doesn't
have.
