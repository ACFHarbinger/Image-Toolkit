# **Comprehensive Visual Analytics & Interpretability Roadmap**

*Targeting Codebase Topology, ML Interpretability, Pipeline Diagnostics, and Omniscient Debugging*

---

## Implementation Status

| Layer | Status | Details |
|-------|--------|---------|
| **Rust math backbone** (`base/src/math/`) | ✅ Complete | 6 modules, 49 unit tests passing |
| **TypeScript math backbone** (`frontend/src/math/`) | ✅ Complete | 7 modules, `tsc --noEmit` clean |
| Phase 1–10 feature implementation | ⬜ Not started | Backbone provides all mathematical primitives |

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

See [`reports/Analytics and Codebase Visualization Research.md`](../../reports/Analytics%20and%20Codebase%20Visualization%20Research.md) for the full technical research underpinning every item on this roadmap.

---

## **Phase 1: The Interactive Meta-Graph (Codebase Topology)**

**Goal:** Build a semantic "graph of graphs" allowing zooming from high-level architecture down to granular function execution and AST parsing.

* **1.1 Rust-Powered AST & Dependency Parser:**
  * Develop a Rust CLI/daemon utilizing **tree-sitter** to statically parse the Python (`backend/src/anim`) and Rust codebases.
  * Extract semantic relationships: module imports, class inheritance, function calls, and data flow.
  * **Option A — SCIP Semantic Indexing:** Emit a **SCIP** (Source Code Intelligence Protocol) protobuf index via `scip-python` and `rust-analyzer`. Ingest into Rust via `nusy-codegraph` / `code-graph-cli` — produces Apache Arrow RecordBatches enabling sub-millisecond blast-radius queries (e.g., transitive impact of modifying `bundle_adjust.py`).
  * **Option B — tree-sitter-graph DSL:** Use the declarative `tree-sitter-graph` crate to write AST-to-graph mapping rules that extract pipeline-specific semantics (stage transitions, telemetry emission sites) without full SCIP indexing.

* **1.2 GPU-Accelerated Force-Directed Dashboard:**
  * **Primary Option — Cosmograph (cosmos.gl):** 100% GPU-bound force-directed simulation via WebGL 2.0 compute/fragment shaders. Ingests Apache Arrow buffers directly into GPU memory; 60fps semantic zooming through 1M+ nodes. Pairs with **DuckDB-WASM** for in-browser SQL filtering of graph nodes by failure impact or algorithmic complexity.
  * **Fallback Option — sigma.js / WebGL:** Viable for graphs up to ~10k nodes; high customization for node glyphs and imagery.
  * **Simple DAG Option — react-flow:** HTML/SVG DOM rendering (~1k nodes); ideal for the explicit, user-editable pipeline DAG view.
  * Implement **Semantic Zooming:** Zoom 0 = modules (`anim`, `rlhf`, `mfsr`); Zoom 1 = files (`compositing.py`, `bundle_adjust.py`); Zoom 2 = classes and functions; Zoom 3 = AST or call graph.
  * Implement **Edge Bundling:** **Skeleton-Based Edge Bundling (SBEB)** clusters edges by directional sector and iteratively routes long-distance architectural dependencies along shared skeleton paths, preventing visual clutter without losing directional information.

* **1.3 Software Cartography (Semantic Layout):**
  * Apply **Latent Semantic Indexing (LSI)** to codebase vocabulary (function names, comments, string literals) to map source code into a high-dimensional vector space.
  * Project via **Multidimensional Scaling (MDS)** into 2D, minimizing a stress function so semantically related modules cluster together physically (e.g., `feature_matching.py` and `bundle_adjust.py`).
  * Render as a topographic map rather than a node-link diagram — modules become landmasses, dependencies become edges on geographic terrain.

* **1.4 Dependency Structure Matrix (DSM):**
  * Render the N×N dependency matrix where marks below the diagonal represent valid layered dependencies; marks **above** the diagonal instantly flag architectural violations or cyclic dependencies.
  * Tools: **Lattix** or **IntelliJ IDEA DSM plugin** for automated generation and permutation analysis.
  * Enables ISO 26262 compliance checks across the Python/Rust multi-language codebase.

* **1.5 Dynamic Execution Tracing:**
  * Overlay dynamic execution paths onto the static graph. Trace a single ASP run from `video_ingestion.py` through `flow_refine.py` to `sr_stitcher.py`, highlighting active nodes in real-time or via a playback slider.

---

## **Phase 2: ML Model & Loss Landscape Visualizer**

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

## **Phase 4: Statistical & Information-Theoretic Failure Analysis**

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

## **Phase 6: Semantic Code Analysis & Vulnerability Discovery**

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

## **Phase 7: Omniscient Debugging & Deterministic Replay**

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

## **Phase 8: Distributed Observability & High-Cardinality Telemetry**

**Goal:** Provide production-grade observability across multi-process ASP runs and expose statistical outliers across high-cardinality benchmark dimensions.

* **8.1 OpenTelemetry — Unified Metrics, Logs, and Traces:**
  * Instrument the ASP pipeline with the **OpenTelemetry** SDK (vendor-neutral standard for metrics + logs + distributed traces).
  * Each pipeline stage runs as a **span** with a `trace_id` and `span_id` injected into the execution context — revealing exact causal relationships and stage latency distribution.
  * Export to **Jaeger** (traces), **Prometheus** (metrics), or any OTLP-compatible backend.

* **8.2 Honeycomb BubbleUp — High-Cardinality Root Cause Analysis:**
  * For benchmark telemetry with high-cardinality dimensions (unique test IDs, feature flag combinations, frame content hashes), deploy **Honeycomb BubbleUp**.
  * Statistically compares the distribution of all high-cardinality attributes within an anomalous subset against the baseline to surface the exact combination of variables causing performance degradation — without requiring engineers to know which dimensions to investigate first.

---

## **Phase 9: Formal Verification & State Space Visualization**

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
