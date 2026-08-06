# Manga Colorization & Animation Roadmap — HITL Deep Learning + Mathematical Optimization

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [0. Current State](#0-current-state-what-already-exists)
- [1. Pre-Processing & Semantic Extraction](#1-pre-processing--semantic-extraction)
- [2. Reference-Guided Colorization](#2-reference-guided-colorization)
- [3. Spatio-Temporal Animation](#3-spatio-temporal-animation)
- [4. HITL Alignment (DPO / LoRA)](#4-hitl-alignment-dpo--lora)
- [5. Client-Side Architecture & HITL Canvas](#5-client-side-architecture--hitl-canvas)
- [6. GUI Test Components](#6-gui-test-components)
- [Phased Execution Sequence](#phased-execution-sequence)
- [Effort × Impact Matrix](#effort--impact-matrix)

---

## Implementation Timeline

> **Legend** — *Node fill:* new feature (blue) · augmentation (violet) · infrastructure (cyan) · research (slate) · integration (pink) — *Node border:* ✅ complete (green, thick) · ⬜ planned (slate, thin) — *Edges:* `==>` critical blocking dependency · `-->` sequential dependency · `-.->` alternative approach · `---` complements

```mermaid
flowchart TD
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef integration fill:#9d174d,color:#fff
    classDef planned     stroke:#64748b,stroke-width:2px

    S0["§0 Current State — none; greenfield feature"]:::infra:::planned

    subgraph PRE["§1 Pre-Processing"]
        direction TB
        S11["§1.1 Text/Speech-Bubble Detection + Inpainting (CRAFT/PaddleOCR + LaMa)"]:::feature:::planned
        S12["§1.2 Line Art Extraction (PiDiNet/Informative-Drawing)"]:::feature:::planned
        S13["§1.3 Screentone Gabor Feature Extraction"]:::feature:::planned
    end

    subgraph COLOR["§2 Reference-Guided Colorization"]
        direction TB
        S21["§2.1 Levin Quadratic-Cost Scribble Colorizer [C++]"]:::feature:::planned
        S22["§2.2 Screentone-Aware Level-Set Propagation"]:::augment:::planned
        S23["§2.3 Graph-Correspondence QP Reference Colorizer"]:::feature:::planned
        S24["§2.4 Optimal-Transport / Sinkhorn Reference Colorizer"]:::feature:::planned
        S25["§2.5 Diffusion Reference Colorizer (MangaNinja-style) [Research]"]:::research:::planned
    end

    subgraph ANIM["§3 Spatio-Temporal Animation"]
        direction TB
        S31["§3.1 3D Quadratic-Cost Temporal Propagation"]:::feature:::planned
        S32["§3.2 Graph-Cut (Boykov-Kolmogorov) Temporal Coherence"]:::augment:::planned
        S33["§3.3 ARAP Mesh Puppeteering"]:::feature:::planned
        S34["§3.4 Diffusion Inbetweening (ToonCrafter-style) [Research]"]:::research:::planned
    end

    subgraph HITL["§4 HITL Alignment"]
        direction TB
        S41["§4.1 LocalDPO Region Preference Fine-Tuning [Research]"]:::research:::planned
        S42["§4.2 LoRA Feedback Adapter Update Loop"]:::augment:::planned
    end

    subgraph CANVAS["§5 Client-Side / HITL Canvas"]
        direction TB
        S51["§5.1 Layered Canvas Editor (Multiply blend, scribble + mask layers)"]:::feature:::planned
        S52["§5.2 Quadtree-Accelerated Interactive Solve"]:::infra:::planned
        S53["§5.3 Uncertainty Overlay (MC-Dropout/BALD)"]:::augment:::planned
    end

    subgraph GUITEST["§6 GUI Test Components"]
        direction TB
        S61["§6.1 Manga Colorization Tab"]:::integration:::planned
        S62["§6.2 Manga Animation Tab"]:::integration:::planned
        S63["§6.3 Preference Review Dialog (DPO capture)"]:::integration:::planned
    end

    S0 ==> S11
    S11 --> S12
    S12 --> S13
    S13 ==> S21
    S13 ==> S22
    S21 --> S22
    S12 --> S23
    S12 --> S24
    S23 -.-> S24
    S22 --> S51
    S21 --> S51
    S23 --> S51
    S24 --> S51
    S25 -.-> S23
    S25 -.-> S24

    S21 --> S31
    S31 --> S32
    S12 --> S33
    S33 --> S62
    S32 --> S62
    S34 -.-> S32

    S51 --> S52
    S51 --> S53
    S51 ==> S61
    S23 --> S61
    S24 --> S61
    S22 --> S61

    S53 --> S41
    S41 --> S42
    S42 --> S63
    S61 --> S63
    S62 --> S63
```

*Reading guide: follow `==>` arrows (thick) for must-have blockers. Thin `-->` arrows show feature dependencies within phases. Dashed `-.->` marks alternative (deep-learning) approaches to the same problem the mathematical-optimization node already solves. Lines without arrowheads (`---`) mark complementary features.*

---

## How to Use This Document

Each section: pain point → mathematical/DL formulation → options with trade-offs → recommendation. Tags: **[Quick Win]** (<1 day), **[Research]** (prototype first), **[Long-term]** (depends on external data/infra). Phased execution sequence is summarised at the end and mirrored into the [Master Roadmap](../ROADMAP.md).

---

## 0. Current State (what already exists)

This is a **greenfield feature area** — the repository has no manga colorization or animation code today. It does have directly reusable infrastructure:

| Component | Location | Relevance |
|---|---|---|
| **C++ `base` pybind11 core** | `base/src/` | Home for the new sparse-linear-solver / graph-cut / Sinkhorn / ARAP kernels (§2, §3) — same pattern as `base.similarity`, `base.recon`. |
| **Model wrapper ABC + registry** | `backend/src/models/wrappers/` (`birefnet_wrapper.py`, `esrgan_wrapper.py`, `sd3_wrapper.py`, …) | Pattern to follow for the diffusion reference colorizer (§2.5) and any DiT inbetweening wrapper (§3.4). |
| **LoRA tuner** | `backend/src/models/tuning/lo_ra_tuner_v2.py` | Base for the DPO/LoRA feedback loop (§4.2) — same rank-decomposition mechanism, new loss. |
| **ComfyUI integration** | `backend/src/models/comfy_manager.py`, `gui/.../comfy_generate_tab.py` | Reusable for §2.5/§3.4 diffusion research spikes before native wrapper investment. |
| **Text/OCR pipeline (nhentai/manga context)** | `backend/src/web/` | No dedicated bubble-text OCR yet; CRAFT/PaddleOCR/Comic-Text-Detector integration is new (§1.1). |
| **Similarity/HNSW infra** | `base/src/similarity/` (via `feature_similarity_finder`) | Reusable for CLIP-embedding retrieval in a future retrieval-augmented colorizer, not required for MVP. |
| **GUI tab conventions** | `gui/src/tabs/animation/`, `gui/src/tabs/models/gen/` | Pattern for the new Manga Colorization/Animation tabs (§6). |

**Gap analysis:** everything in §1–§5 is new work. The mathematical-optimization track (§2.1–§2.4, §3.1–§3.3) is prioritized first — it needs no pretrained weights, carries no training-data copyright exposure, and is the natural extension of existing C++ solver infrastructure. The deep-learning track (§2.5, §3.4) is explicitly scoped as [Research] follow-on, reusing the existing ComfyUI integration before any native wrapper is written.

Research basis: [`research/Manga Colorization and Animation Research.md`](../research/Manga%20Colorization%20and%20Animation%20Research.md) (merged from the prior HITL-deep-learning and mathematical-optimization research passes).

---

## 1. Pre-Processing & Semantic Extraction

### 1.1 Text/Speech-Bubble Detection + Inpainting

**Pain point:** Without removing dialogue text, both diffusion colorizers and quadratic-cost solvers will hallucinate colors onto glyphs, or (for the pattern-continuity solver, §2.2) the text mask breaks the halting function's pattern continuity.

**Recommendation:** CRAFT or PaddleOCR (Python, `paddleocr` package) for bounding-box detection + mask expansion; LaMa (`simple-lama-inpainting` PyPI package) for reconstruction. New `backend/src/models/wrappers/lama_wrapper.py` + `backend/src/manga/text_removal.py`. [Quick Win] for MVP scribble-based colorization (§2.1) if manual masking is offered first; full auto-detection is Medium effort.

### 1.2 Line Art Extraction

**Pain point:** Colorization solvers need a clean structural boundary map, not raw scanned pixels.

**Recommendation:** PiDiNet (lightweight, ONNX-exportable) as the primary edge extractor; Informative-Drawing as a fallback/quality option. New `backend/src/models/wrappers/pidinet_wrapper.py`.

### 1.3 Screentone Gabor Feature Extraction — ✅ Done (2026-08-04, issue #185)

**Pain point:** Raw pixel intensity is unusable as an affinity signal on screentoned manga (§5.2 of the research report) — local variance is artificially maximized by halftone dots, breaking both the Levin quadratic-cost weighting (§2.1) and naive edge detection.

**Shipped as:** `backend/src/manga/gabor.py` (`gabor_feature_bank()`) — a Gabor filter bank (`cv2.getGaborKernel` across orientations/frequencies) computing a per-pixel texture signature, **pure Python/OpenCV, not the C++ `base/src/manga/gabor_features.cpp` this section originally recommended** — same rationale as §2.1's deviation (avoid a new build-system surface before the rest of the HITL loop is proven out; a native port is a valid follow-up if profiling shows it's needed for full-page 4K interactive use). Each filter response is converted to a locally-smoothed "Gabor energy" map (`cv2.GaussianBlur` over the response magnitude) rather than raw per-pixel response — raw Gabor magnitude is phase-sensitive at the pixel level (two adjacent pixels in the *same* halftone pattern can land on opposite dot-grid phases and score very differently), so this smoothing step was necessary to get a genuine regional texture signature rather than phase noise; verified quantitatively (a same-region pixel pair scores a much smaller feature-space distance than a pair straddling a screentone/flat boundary). Feeds §2.2's texture-affinity colorizer directly.

Tests: `backend/test/manga/test_gabor.py` (7).

---

## 2. Reference-Guided Colorization

### 2.1 Levin Quadratic-Cost Scribble Colorizer — ✅ Done (2026-08-04, issue #186)

**Pain point:** No deterministic, from-scratch (no pretrained weights) scribble-based colorization exists in the toolkit today.

**Formulation:** minimize $J(U) = U^T(I-W)^T(I-W)U$ per chrominance channel, $W$ built from intensity-correlation weights (research report §5.1). Solve via sparse Cholesky or preconditioned conjugate gradient.

**Shipped as:** `backend/src/manga/colorization.py` (`build_levin_system()` + `colorize_scribble()`) — **pure Python/NumPy/SciPy**, not the C++ `base::manga`/Eigen kernel this section originally recommended. `scipy.sparse.linalg.splu` solves each chrominance channel; the affinity matrix is assembled via fully-vectorized NumPy (no per-pixel Python loop). A `max_solve_dim` cap (default 640px) solves chrominance at reduced resolution and upsamples it onto full-resolution luminance for large images, keeping solve time roughly constant (~4s) regardless of source size — the quadtree acceleration in §5.2 remains the follow-up for genuinely interactive (sub-second) redraw.

**Why the deviation from the plan:** SciPy's sparse LU solver is fast enough for interactive single-page use, and building the first working version this way avoided opening a new CMake/pybind11 build-system surface (and an unverified Eigen dependency) before proving out the rest of the HITL loop end-to-end. A native `base::manga` port remains open as a follow-up if profiling ever shows it's needed for multi-page batch throughput — tracked as a reopenable scope note on issue #186, not a new issue.

Tests: `backend/test/manga/test_colorization.py` (12).

### 2.2 Screentone-Aware Level-Set Propagation — ✅ Done (2026-08-04, issue #187)

**Pain point:** §2.1 alone fails on screentoned regions (halftone dot variance breaks the weighting function).

**Formulation:** Level-set PDE $\Phi_t = h \cdot (F_0 + F_1|\nabla\Phi|)$ with halting function $h(x,y) = 1/(1+|D(T_{scribble}, T(x,y))|)$ over the Gabor features from §1.3 (research report §5.2).

**Shipped as:** `backend/src/manga/screentone.py` (`build_texture_affinity_system()` + `colorize_scribble_screentone()`) — **not a separate level-set PDE solver**, a deliberate reuse of §2.1's already-shipped, already-tested convex quadratic-cost graph-Laplacian solver with pixel affinity weights swapped from intensity correlation to a Gaussian kernel over Gabor texture-feature distance (`w_rs = exp(-||T(r)-T(s)||^2 / (2*sigma^2))`, row-normalized). Both formulations are monotonically-decreasing functions of a local pattern-distance measure — the graph weight is the direct discrete graph-Laplacian analog of the level-set halting function — so this achieves the same observable goal (propagation halts at screentone-pattern boundaries, not raw-intensity boundaries) without a second, separate PDE time-stepping solver and its own stability/reinitialization concerns. Full doc-string rationale in the module itself. Same `max_solve_dim` resolution cap and Dirichlet-constraint machinery as §2.1; same worker/UI wiring (§6.1) via `ColorizeWorker`'s new pluggable `colorize_fn` parameter. Wired into the Manga Colorization Tab as the "Screentone-aware (Gabor texture)" mode.

Tests: `backend/test/manga/test_screentone.py` (10).

### 2.3 Graph-Correspondence QP Reference Colorizer

**Pain point:** Scribbling is not the dominant industrial workflow — artists want to color an entire chapter from one reference sheet.

**Formulation:** superpixel graphs, relaxed Quadratic Assignment ($\min_x x^TQx$ subject to one-to-one marginal constraints), Hungarian-method discretization (research report §5.3).

**Options.** **A** SLIC superpixel segmentation (OpenCV, already likely available) + a QP relaxation solved with `scipy.optimize` or a dedicated C++ QP solver (OSQP) exposed via pybind11. **B** Defer superpixel graph matching entirely and go straight to Optimal Transport (§2.4), which subsumes much of the same use case at lower implementation risk.

**Recommendation:** B first if timeline is tight (OT/Sinkhorn is simpler to implement correctly and is GPU-friendly); A as a follow-up for cases where OT's soft assignment under-performs on sharply bounded regions (e.g. distinct clothing pieces).

### 2.4 Optimal-Transport / Sinkhorn Reference Colorizer — ✅ Done (2026-08-05, issue #188)

**Pain point:** Same as §2.3 — reference-based full-chapter colorization — via a more GPU-friendly, differentiable formulation.

**Formulation:** entropic-regularized OT, $\min_P \langle P,C\rangle + \epsilon H(P)$, solved by Sinkhorn iteration; Optimal Flow Transport (OFT) variant for occluded/disjoint character regions (research report §5.4).

**Shipped as:** `backend/src/manga/optimal_transport.py` (`sinkhorn()` + `colorize_reference()`). Both the reference image and the target line art are over-segmented into SLIC superpixels; each superpixel is described by a structural feature vector (§1.3's Gabor texture signature + normalized centroid position, matched on structure since the target has no color yet); `sinkhorn()` solves for a soft reference→target correspondence under a squared-Euclidean structural cost; each target superpixel's color is the transport-plan-weighted average of reference superpixel colors. Target luminance is preserved exactly, matching §2.1/§2.2's contract. Same `max_solve_dim` resolution-cap pattern as §2.1/§2.2 (both images are independently downscaled for the solve, chrominance is upsampled back via nearest-neighbor onto full-resolution luminance) and the same `MANGA_COLORIZE_LOCK` native-call serialization. Wired into the Manga Colorization Tab (§6.1) as "Reference / Optimal-Transport", with a dedicated "Load Reference…" button (enabled only in that mode) and `ReferenceColorizeWorker` (`gui/src/helpers/manga/colorize_worker.py`) — kept as a separate `QThread` subclass rather than generalizing `ColorizeWorker`, since the reference workflow's inputs (two images, no scribble mask) don't fit that worker's signature.

**Deviations from the original plan, made transparently:**
- **Hand-written NumPy Sinkhorn instead of the `POT` library.** The algorithm is ~15 lines (Gibbs kernel + alternating row/column rescaling); pulling in a new third-party dependency for something this self-contained wasn't justified. `POT` remains a reasonable follow-up if a more feature-complete OT toolkit (unbalanced OT, GPU dispatch, the OFT occluded-region variant) is ever needed — the module docstring says so explicitly.
- **Gabor texture + normalized position matching instead of CLIP embeddings.** The research report's retrieval-augmented pipelines (ColorFlow etc.) match via a pretrained vision-language model; this stays dependency-light and assumes the reference and target share a roughly similar pose/composition (the common case for a single-character reference sheet applied to consecutive panels of that same character) — a real, documented limitation, not a hidden one.
- **No CUDA/C++ reimplementation.** Profiling never showed Sinkhorn itself as the bottleneck — SLIC segmentation and per-pixel Gabor feature extraction dominate, and both are already bounded by `max_solve_dim`; solve time for a downscaled page is ~1-2s, well within the interactive budget the recommendation was guarding against.

**Bug found and fixed during implementation:** `sinkhorn()`'s early-stopping residual check was tautological in an earlier draft (`u_new * kv` is trivially `≈ mu` by construction of `u_new = mu / kv`, so it broke after the first iteration regardless of actual convergence). Fixed by tracking iterate stability (`|v_new - v|`) instead, which only shrinks to ~0 once both marginals are actually satisfied — caught by `test_marginals_are_approximately_satisfied` before this shipped.

Tests: `backend/test/manga/test_optimal_transport.py` (13), `gui/test/manga/test_colorization_tab.py` (+6 reference-mode cases, 25 total).

### 2.5 Diffusion Reference Colorizer (MangaNinja-style) [Research]

**Pain point:** Pure mathematical optimization cannot hallucinate genuinely new visual data (e.g., the back of a character's head never shown in the reference).

**Recommendation:** Do not build a native wrapper yet. Prototype via existing ComfyUI integration (`comfy_manager.py`) with a MangaNinja or ColorFlow community workflow JSON, gated behind explicit user opt-in given the copyright exposure discussed in the research report §1. Promote to a native `backend/src/models/wrappers/manganinja_wrapper.py` only if the ComfyUI spike proves the quality delta justifies it.

---

## 3. Spatio-Temporal Animation

### 3.1 3D Quadratic-Cost Temporal Propagation — ✅ Done (2026-08-05, issue #192)

**Pain point:** §2.1's colorizer only handles single frames; animated sequences need scribbles to propagate through time, not just space.

**Recommendation:** Extend `base::manga::colorize_scribble()` (§2.1) to accept a 3D $(x,y,t)$ neighborhood — same solver, expanded affinity graph. Reuses the Eigen sparse-solver investment from §2.1 directly.

**Shipped as:** `backend/src/manga/temporal.py` (`build_levin_system_3d()` + `colorize_scribble_sequence()`) — a direct dimensional generalization of §2.1's `build_levin_system()`/`colorize_scribble()` to a 3D `(t, y, x)` neighborhood, same intensity-correlation weighting and Dirichlet-constraint scribble pinning, solved as one combined sparse system across the whole sequence (not per-frame), so color naturally diffuses along the temporal axis through unscribbled in-between frames. Pure Python/SciPy, same pragmatic choice as §2.1 over a native `base::manga` kernel.

**Scaling caveat found during implementation:** the 3D system's sparse-LU fill-in grows much faster than linearly with the temporal window. A 10-frame 400x400 sequence OOM'd at `max_solve_dim=256` (the single-frame colorizer's proportional default) but solved in ~36s / ~4.4GB at `max_solve_dim=128` — so `colorize_scribble_sequence()`'s default `max_solve_dim` is 128, not 640/256. This is scoped correctly for issue #192's stated use case (short in-between spans at modest resolution), not full-episode timelines; a chunked/windowed solve is a documented, not-yet-built follow-up for larger sequences.

Tests: `backend/test/manga/test_temporal.py` (14) — 54 backend manga tests total.

### 3.2 Graph-Cut (Boykov-Kolmogorov) Temporal Coherence — ✅ Done (2026-08-05, issue #193)

**Pain point:** §3.1 degrades under fast motion/occlusion where local intensity tracking breaks down.

**Formulation:** MRF energy $E(L) = \sum_p D_p(L_p) + \sum_{(p,q)} V_{p,q}(L_p,L_q)$, solved via Boykov-Kolmogorov max-flow/min-cut (research report §6.1).

**Recommendation:** Use an existing, well-tested max-flow library (`maxflow`/PyMaxflow wraps the reference Boykov-Kolmogorov C++ implementation) rather than reimplementing graph-cut from scratch — lower risk, same guarantees. Wire the data term from §2.1/§2.4 outputs and the smoothness term from §1.3's Gabor features.

**Shipped as:** `backend/src/manga/graph_cut.py` (`build_temporal_coherence_graph()` + `graph_cut_temporal_refine()`) — a second refinement pass that takes §3.1's already-solved sequence output (`colorize_scribble_sequence()`) as a label hypothesis and uses `PyMaxflow`'s `GraphFloat` (the recommended, not-reimplemented Boykov-Kolmogorov binding) to decide per pixel whether to keep it. **Deliberate simplification:** rather than the roadmap's fully general multi-label MRF (which would need alpha-expansion — real scope creep for a first pass, per issue #193's own stated latitude), this ships a **2-label binary graph-cut per frame**: label `OWN` (trust this frame's own solved chrominance) vs. label `BLEND` (fall back to the mean of its temporal neighbor frame(s)' chrominance at the same spatial location). The data term weighs `flicker` (the OWN/BLEND chrominance disagreement) by `motion` (normalized grayscale intensity difference to the temporal neighbor(s) — a direct proxy for where §3.1's intensity-correlation-based tracking is least trustworthy): high motion + high flicker pushes toward `BLEND`, low motion + high flicker keeps `OWN` (the disagreement is real signal, not a tracking failure). The smoothness term reuses §2.2's *exact* Gabor-affinity Gaussian kernel (`exp(-||T(p)-T(q)||^2/(2*sigma^2))`) as a symmetric Potts penalty over the standard 4-connected pixel grid — submodular by construction, which is exactly what gives Boykov-Kolmogorov's binary min-cut an *exact* (not approximate) solution, unlike general multi-label alpha-expansion. `PyMaxflow` installed cleanly from a prebuilt manylinux wheel (added to `backend/pyproject.toml`, alphabetically), so the "no C++ toolchain" `scipy.sparse.csgraph.maximum_flow` fallback contemplated for this item wasn't needed.

Tests: `backend/test/manga/test_graph_cut.py` (19) — 73 backend manga tests total.

### 3.3 ARAP Mesh Puppeteering — ✅ Done (2026-08-05, issue #194)

**Pain point:** No mesh-based deformation/animation tool exists; pixel-level color-flow animation (§3.1/§3.2) does not itself move characters, only recolors static frames.

**Formulation:** alternating local step (per-triangle SVD rotation) / global step (sparse Poisson solve), skeleton-length constraint (research report §6.2).

**Recommendation:** `base::manga::arap_deform()` in C++ (SVD via Eigen, sparse solve via the same solver stack as §2.1). This is the highest-effort item in the roadmap (mesh generation, rigging UI, real-time re-solve) but is the deterministic counterpart to Live2D-style puppeteering and the clearest "animate a single manga panel interactively" HITL demo.

**Shipped so far:** `backend/src/manga/arap.py` (`generate_mesh()` + `arap_deform()`) — the deterministic algorithmic core. `generate_mesh(mask, grid_step)` samples a regular grid inside a caller-supplied binary mask, Delaunay-triangulates it, discards triangles whose centroid falls outside the mask, and drops/reindexes any vertex left unreferenced. `arap_deform(vertices, triangles, anchors, n_iters)` alternates the local step (per-triangle optimal rotation via 2D orthogonal Procrustes/SVD) and global step (a sparse graph-Laplacian solve over the mesh's edges, anchors pinned via the same Dirichlet row-replacement trick `colorization.py`'s `_solve_chrominance` already uses for scribbled pixels — the Laplacian itself doesn't depend on the rotations, so it's factorized once via `splu` and reused across iterations).

**Verified correct, not just plausible-sounding:** with every boundary vertex of a mesh anchored to a rigidly-rotated (20°) target position, the *free* interior vertices converge to their own analytically-rotated positions to well under 1% of the mesh's own scale (mean error ~0.0018px against a ~127px mesh diagonal in one manual run) — exactly the property a correct ARAP implementation must have (it reproduces rigid motion exactly when nothing contradicts it). A single moved anchor with the rest of the mesh free produces a finite, smoothly-decaying local deformation (no blow-up/NaN), matching the intended "locally rigid, globally flexible" behavior.

**Deviations from the roadmap's plan, documented transparently:** (1) pure Python/NumPy/SciPy, not the originally-proposed C++ `base::manga::arap_deform()` Eigen kernel — same deliberate, already-established deviation as `colorization.py`/`temporal.py`/etc., for the same reason (avoids a new build-system surface before the algorithm is proven correct; SciPy's sparse LU + NumPy's SVD are fast enough at interactive scale — ~33ms for a single-anchor solve on a ~100-vertex mesh). (2) no automatic character-isolation dependency on issue #184 (line art extraction, itself unbuilt) — `generate_mesh()` accepts any caller-supplied binary mask, matching the roadmap's own established "manual-mask MVP first" pattern used at §1.1. (3) the "skeleton-length constraint for anatomical regularity" mentioned in the formulation is not implemented — it's an optional refinement on top of the core ARAP energy (constraining specific bone-like edge lengths to stay fixed), not required for the base algorithm to be correct, and no rigging/skeleton UI exists yet to define what those constrained edges would even be.

**Rigging UI + real-time GUI wiring, shipped in a follow-up session (mirroring issue #191's own two-part delivery pattern):** `gui/src/elements/manga/mesh_overlay_editor.py::MeshOverlayEditor` (a `QGraphicsView`, architecturally parallel to `MangaCanvasEditor`) lets a user load an image, paint a binary mask (reusing the same freehand-paint interaction as the scribble layer), generate a mesh over it via `generate_mesh()`, and drag any mesh vertex to pose it -- every mouse-move during a drag re-solves `arap_deform()` **synchronously on the GUI thread**, deliberately not via the usual `QThread`-worker pattern every other manga solver in this codebase uses: an async dispatch would let the displayed pose lag behind the mouse, actually hurting drag responsiveness, and empirical timing (~17ms mean for a ~64-vertex mesh) makes synchronous solving the pragmatic choice. Each drag call is solved from the *original* rest pose against the full accumulated anchor set (not incrementally from the previous frame), matching `arap_deform()`'s own contract. New "Manga Puppeteering" tab (`gui/src/tabs/manga/puppeteering_tab.py::MangaPuppeteeringTab`) wires this into a third "Manga" category tab alongside Colorization and Animation, following the same "test/exercise harness for the already-built solver" posture as the Animation Tab (issue #196) -- no skeleton/bone hierarchy UI, no keyframe timeline, no per-triangle pixel image warping (the mesh wireframe overlays the static image; actually deforming the *pixels* is a real, separate follow-up, not attempted here).

**Real intermittent native-crash hazard found and mitigated during development, documented transparently:** this module is the first in `backend/src/manga/` to call `np.linalg.svd` (every other solver only uses `scipy.sparse.linalg.splu`). Running the new test suite's SVD-heavy cases (~2,700+ SVD calls in one test) under the full `backend/test/` pytest collection (which loads ~140 native extension modules in-process, including PySide6/Shiboken, torch, av, jpype) intermittently (~40% of runs) crashed with a `SIGSEGV` inside `numpy.linalg.svd`, or occasionally a bizarre downstream `SystemError`/`TypeError` in unrelated stdlib code -- classic symptoms of native heap corruption surfacing unpredictably after the fact, not a bug in the ARAP math itself (the algorithm's own correctness was independently verified via the rigid-rotation-reproduction test, which passed every time it *did* run). Confirmed via elimination: (1) never reproduces calling `np.linalg.svd` in isolation, even with PySide6 and every heavy library `conftest.py` imports already loaded; (2) never reproduces across 5 repeated runs of the other 95 pre-existing manga tests (zero `np.linalg.svd` calls between them); (3) reproduces only when this module's SVD-heavy tests run as part of the full pytest collection. Mitigated two ways: added the same `telemetry.MANGA_COLORIZE_LOCK` serialization every other manga solver already uses (`arap_deform()` and `generate_mesh()`'s `Delaunay()` call, both native-heavy), and reduced the two heaviest tests' SVD call volume (smaller test meshes, fewer iterations) to a level that still validates the exact same properties. 15/15 clean runs after both changes (10 standalone + 5 full-suite), versus roughly 40% failure before. The underlying native co-loading fragility is not fully root-caused or eliminated -- a genuine, documented residual risk for future SVD-heavy manga code, not something this session could responsibly claim to have "fixed."

Tests: `backend/test/manga/test_arap.py` (14), `gui/test/manga/test_mesh_overlay_editor.py` (18), `gui/test/manga/test_puppeteering_tab.py` (12) — 109 backend manga tests, 93 GUI manga tests total.

Tests: `backend/test/manga/test_arap.py` (14) — 109 backend manga tests total.

### 3.4 Diffusion Inbetweening (ToonCrafter-style) [Research]

**Recommendation:** Same posture as §2.5 — ComfyUI-first spike (ToonCrafter is already referenced elsewhere in the codebase's ASP research for ghost-fill, see `docs/moon/roadmaps/asp.md`); evaluate sharing a wrapper with ASP's `animation/anim_fill.py` ghost-fill path before writing a manga-specific one.

---

## 4. HITL Alignment (DPO / LoRA)

### 4.1 LocalDPO Region Preference Fine-Tuning [Research]

**Pain point:** Only relevant once §2.5/§3.4 diffusion paths exist — mathematical-optimization modes (§2.1–§2.4, §3.1–§3.3) are deterministic and have no learned weights to align.

**Recommendation:** Gate entirely behind §2.5/§3.4 landing. If/when a native diffusion wrapper exists, implement region-masked Diffusion-DPO loss (research report §7.1–§7.2) reusing the bounding-box mask primitive already needed for §5.1's canvas masking layer.

### 4.2 LoRA Feedback Adapter Update Loop

**Recommendation:** Same gating as §4.1. Reuses `LoRATunerV2` (`backend/src/models/tuning/lo_ra_tuner_v2.py`) infrastructure — new loss function only, not new training infra.

---

## 5. Client-Side Architecture & HITL Canvas

### 5.1 Layered Canvas Editor (Multiply blend, scribble + mask layers) — ✅ Done (2026-08-04, issue #190)

**Pain point:** Every colorization mode (§2.1–§2.4) needs the same interaction primitive: an artist draws scribbles/reference points on top of line art and sees results composited live.

**Shipped as:** `gui/src/elements/manga/canvas_editor.py` (`MangaCanvasEditor`, `QGraphicsView`-based) with three `QGraphicsPixmapItem` layers exactly as recommended — generated/solved color at the bottom, line art above it via a `_MultiplyPixmapItem` subclass overriding `paint()` to set `QPainter.CompositionMode_Multiply`, and a semi-transparent scribble overlay on top (painted live into a backing `QImage`, read back as an RGB array + alpha-channel mask for the solver). This is the shared UI investment §6.1 (Manga Colorization Tab) now builds on; §6.2 (Manga Animation Tab) remains a follow-up consumer once an animation backend (§3.x) exists.

Found and fixed along the way: `QPainter.drawLine()` renders nothing for a zero-length line even with a round-cap pen, which would have silently dropped single-click dots — fixed by drawing a filled circle instead when a stroke's two endpoints coincide.

Tests: `gui/test/manga/test_canvas_editor.py` (10).

### 5.2 Quadtree-Accelerated Interactive Solve — ✅ Done (2026-08-05, issue #191)

**Pain point:** Full-resolution 4K sparse-solve on every scribble stroke is too slow for interactive feedback.

**Recommendation:** Recursive quadtree partitioning of flat vs. detailed regions (research report §9.3) before building the affinity graph for §2.1–§2.4; re-solve only the dirty quadtree region touched by the latest stroke, not the whole page. Medium-High effort; required for genuine interactivity, deferrable for an initial "solve on demand" (non-live) MVP.

**Shipped in two parts.** **(1) Backend mechanism:** `backend/src/manga/quadtree.py` (`build_quadtree()` + `colorize_region_incremental()`). `build_quadtree()` recursively subdivides a grayscale image into flat-vs-detailed leaf regions by local intensity variance (detailed/screentone regions subdivide into small leaves, flat regions stay as large ones — verified: a stroke landing in a finely-partitioned detailed region re-solves a window ~56x56px in ~0.01s vs. a full-page ~3.5s solve, a ~300x speedup for that case). `colorize_region_incremental()` takes a "dirty" bounding box (the latest stroke's extent), expands it to the union of whichever quadtree leaves it touches plus a halo, re-solves only that window via any existing §2.1/§2.2/§2.4 colorizer, and composites the result into a previously-solved full-canvas output — everything outside the window is copied through unchanged. **(2) Live GUI wiring:** `MangaCanvasEditor` (§5.1) gained pixel-space stroke-bounding-box tracking (`_accumulate_stroke_bbox()` during a stroke, finalized on `mouseReleaseEvent` into `get_last_stroke_bbox()`, padded by half the pen width and clipped to canvas bounds). The Manga Colorization Tab (§6.1) gained a "Live Preview" checkbox (scribble-based modes only — the reference mode's two-image signature doesn't fit `colorize_region_incremental`'s contract) that connects to `MangaCanvasEditor.scribble_changed` and dispatches a new `IncrementalColorizeWorker` (`QThread`, same pattern as `ColorizeWorker`) per completed stroke, seeding a baseline with one ordinary full solve on the first stroke (`colorize_region_incremental` has no "solve from nothing" path) and re-solving only the touched quadtree window on every stroke after that.

**Design choices, documented transparently:** a stroke completing while a previous solve is still in flight is silently skipped rather than queued — the scribble bitmap already has the new stroke painted onto it, so the next completed solve still reflects it, just one stroke later than fully live; a best-effort trade-off appropriate for a HITL preview, not a correctness gap. The quadtree leaves are cached per loaded image (`self._quadtree_leaves`, built once on first use) rather than recomputed per stroke, since the leaf structure only depends on the static line-art image, not the scribbles painted on top of it.

**Real pre-existing solver limitation found during development, documented not fixed:** an early test fixture using a dense high-contrast striped synthetic pattern (every 4th column dark) reproducibly triggered `RuntimeError: Factor is exactly singular` inside `colorize_scribble`'s SuperLU factorization for some sub-window crops of that specific pattern -- a real numerical edge case in `build_levin_system`'s Levin-weight construction for a pathological repeating structure, not something introduced by this module. Not fixed here (`colorization.py` is out of scope for this issue); worked around in this module's own tests by using a sparse-dot screentone pattern instead (matching `test_screentone.py`'s already-established `_screentone_gray` fixture), which doesn't trigger it. Worth a dedicated follow-up investigation if a real scribbled image ever hits the same structure.

**Manually verified end-to-end with real threads and real cv2** (outside pytest, since `gui/test/conftest.py` globally mocks `cv2` and a real background `QThread` running the real solver against that mock is a documented crash hazard, per issue #196's own finding): seed stroke → Live Preview toggled on → full solve seeds a baseline → second stroke elsewhere → incremental worker dispatched → result correctly composited and the baseline updated, all via genuine cross-thread Qt signal delivery (`QThread.wait()` + `app.processEvents()` to flush the queued connection, not a synchronous call).

Tests: `backend/test/manga/test_quadtree.py` (13), `gui/test/manga/test_canvas_editor.py` (+6 stroke-bbox cases), `gui/test/manga/test_colorization_tab.py` (+13 live-preview cases) — 95 backend manga tests, 63 GUI manga tests total.

Tests: `backend/test/manga/test_quadtree.py` (13) — 95 backend manga tests total.

### 5.3 Uncertainty Overlay (MC-Dropout/BALD)

**Recommendation:** Only meaningful for §2.5's diffusion path (MC-Dropout requires a stochastic model); low priority until that path is built. Deterministic solvers (§2.1–§2.4) have no useful uncertainty signal beyond residual energy, which can be surfaced more simply as a "low-confidence region" heatmap from the solver's own residual.

---

## 6. GUI Test Components

New GUI tabs to exercise and validate each backend capability above end-to-end — following the existing tab conventions in `gui/src/tabs/animation/` and `gui/src/tabs/models/gen/`.

### 6.1 Manga Colorization Tab — ✅ Done (2026-08-04, issue #195)

**New file:** `gui/src/tabs/manga/colorization_tab.py`, registered as a new "Manga" category (→ "Colorization") in `gui/src/windows/main/_tab_registry.py`.

**Shipped:** embeds the §5.1 layered canvas editor; line-art file loader (`DIALOG_OPTS`-safe); pen color/width controls; a mode selector listing all four planned colorization modes with only "Scribble (Levin)" enabled (the other three are disabled placeholders pending §2.2/§2.3/§2.4's backends, so the tab won't need reshaping once they land); "Colorize" runs the solver off the UI thread via `gui/src/helpers/manga/colorize_worker.py`'s `ColorizeWorker` (`QThread` subclass overriding `run()`); PNG export. **Not yet shipped** (deferred, not a gap in this pass's scope): reference-image loader (only relevant to §2.3/§2.4's not-yet-built reference-based modes) and a Before/After toggle (the canvas editor's layer stack already shows line art composited live over the result, judged sufficient for the scribble-mode MVP).

Tests: `gui/test/manga/test_colorization_tab.py` (8).

### 6.2 Manga Animation Tab — ✅ Done (2026-08-05, issue #196)

**New file:** `gui/src/tabs/manga/animation_tab.py`.

**Contents:** frame-sequence loader; scribble-through-time UI reusing §5.1's canvas across a frame scrubber; mode selector (3D quadratic-cost §3.1, Graph-Cut §3.2, ARAP mesh puppeteering §3.3); mesh-vertex control-point overlay for §3.3; playback preview.

**Shipped as:** a test/exercise harness for §3.1/§3.2's already-built solvers, per the issue's own title framing — not the production timeline editor the original brainstorm above sketched (mode selector across all three animation backends, mesh-vertex overlay). Loads a frame sequence via a multi-select file picker (`QFileDialog.getOpenFileNames`, sorted by filename — simpler than a directory-scan, reusing the single-image tab's `load_qimage`/`IMAGE_FILE_DIALOG_FILTER`); reuses §5.1's `MangaCanvasEditor` as a single shared widget across frames, with a small per-frame-index scribble-overlay dict (`MangaAnimationTab._scribble_images`) saving/restoring the canvas's scribble layer on every frame-slider move — the editor itself wasn't touched (out of scope for this issue), so this reaches into its private `_scribble_qimage`/`_scribble_item` attributes, the same ones `test_colorization_tab.py` already pokes at directly. "Colorize Sequence" dispatches a new `gui/src/helpers/manga/animation_worker.py::AnimationColorizeWorker` (`QThread` subclass, same pattern as `ColorizeWorker`) running `colorize_scribble_sequence()` (§3.1, issue #192) and, when a "Graph-cut refine" checkbox is ticked, chaining `graph_cut_temporal_refine()` (§3.2, issue #193) as a second pass — both already-built backends wired, not just one. A second slider scrubs the solved result over a plain `QLabel` (not the editable canvas), and "Export…" writes the sequence as `frame_%04d.png` into a chosen directory (`QFileDialog.getExistingDirectory`, `DIALOG_OPTS`-safe).

**Deliberate scope line vs. the original brainstorm:** no ARAP mesh puppeteering mode (§3.3 has no backend yet — MCA.12 is unbuilt) and no mesh-vertex control-point overlay (meaningless without it); the mode selector accordingly reduced to the "Graph-cut refine" toggle rather than a 3-way backend picker, since only two backends exist to pick between and one is strictly a refinement pass over the other's output, not an alternative from-scratch mode. Both reductions are the natural consequence of "test the already-built solvers," not an oversight.

Tests: `gui/test/manga/test_animation_tab.py` (18), `gui/test/manga/test_animation_worker.py` (5) — 46 GUI manga tests total (up from 25). A confirmed, documented environment hazard shaped several tests: `gui/test/conftest.py` globally mocks `cv2` (`sys.modules["cv2"] = MagicMock()`), and running `colorize_scribble_sequence()`/`graph_cut_temporal_refine()` (both call `cv2.cvtColor()` internally) from a real background `QThread` against that mock reproducibly corrupted memory ("double free or corruption") during development — confirmed via a minimal repro, not guessed. GUI tests for this tab therefore mock `AnimationColorizeWorker`/the backend functions rather than letting a real thread run them (dispatch-args/button-state coverage only, matching this session's established "cross-thread signal delivery is unreliable inside a test's own control flow" constraint); real end-to-end correctness (including the full load→scribble→solve→preview round trip against the *real* cv2) was manually verified via a standalone script outside pytest.

### 6.3 Preference Review Dialog (DPO capture) — ✅ Done (2026-08-05, issue #197)

**New file:** `gui/src/components/manga_preference_dialog.py`.

**Contents:** side-by-side candidate comparison (A/B) with a single-click preference vote, feeding the §4.1/§4.2 pipeline once it exists. Built early (as a stub capturing preferences to a local SQLite/JSON log even before §4 lands) so preference data collection starts as soon as any generative mode (§2.5/§3.4) ships, rather than being retrofitted later.

**Shipped as:** `MangaPreferenceDialog` (`gui/src/components/manga_preference_dialog.py`) shows two candidate colorizations side by side with "Prefer A" / "Tie / Skip" / "Prefer B" buttons; a vote both emits `preference_recorded` and calls `log_preference()` (`backend/src/manga/preference_log.py`), which appends one JSON line (`{timestamp, source_a, source_b, winner, metadata}`) to `~/.image-toolkit/manga_preferences.jsonl` — the same `~/.image-toolkit/` local-app-data convention `gui/src/utils/manager/shortcut_manager.py`'s `keybindings.json` already uses. `read_preferences()` reads the log back for a future training script. **Deviation:** JSON-lines instead of SQLite (the roadmap's own text allows either) — an append-only vote log has no query/update/deletion requirements, so SQLite's transactional/query machinery would go unused; JSONL is human-inspectable, needs no new dependency, and is trivially concatenable across installs. **Deliberately not wired into any existing tab** (e.g. an automatic "Compare Modes" trigger in the Colorization Tab that runs two solvers and opens this dialog) — issue #197's own scope is the dialog + log file, not tab integration; the dialog is a standalone, directly-instantiable component (`MangaPreferenceDialog(candidate_a, candidate_b, source_a=..., source_b=..., metadata=...)`) any future caller (a tab, a batch-review script, §4's eventual training loop) can drive without further plumbing.

Tests: `backend/test/manga/test_preference_log.py` (9), `gui/test/components/test_manga_preference_dialog.py` (7) — 82 backend manga tests, 55 GUI manga+components tests total.

---

## Phased Execution Sequence

| Phase | Items | Effort |
|---|---|---|
| **MCA-1 (Foundation)** | §1.1 text/bubble removal (manual-mask MVP) · §1.2 line art extraction · §1.3 Gabor features · §2.1 Levin scribble colorizer · §5.1 layered canvas editor | 1–2 wk/item |
| **MCA-2 (Core Colorization)** | §2.2 screentone level-set · §2.4 Optimal-Transport reference colorizer · §6.1 Manga Colorization Tab · §5.2 quadtree acceleration | 1–2 wk/item |
| **MCA-3 (Animation)** | §3.1 3D quadratic-cost propagation · §3.2 graph-cut temporal coherence · §6.2 Manga Animation Tab | 1–2 wk/item |
| **MCA-4 (Advanced Mesh + Alt Colorization)** | §3.3 ARAP mesh puppeteering · §2.3 graph-correspondence QP (if OT proves insufficient) | 2+ wk/item |
| **MCA-5 (Generative Research)** | §2.5 diffusion reference colorizer [Research] · §3.4 diffusion inbetweening [Research] · §6.3 preference dialog · §4.1/§4.2 DPO/LoRA alignment | research |

Dependencies: §1.3 (Gabor features) blocks §2.2 and materially strengthens §2.3/§2.4's segmentation; §2.1's Eigen sparse-solver investment is reused directly by §3.1; §5.1's canvas editor is the shared UI substrate for both GUI test tabs (§6.1/§6.2) and must land before either. The generative track (§2.5/§3.4/§4/§6.3) is deliberately sequenced last — it is explicitly [Research], carries the copyright exposure discussed in the research report's introduction, and should only be resourced once the deterministic MVP (MCA-1–MCA-3) has validated the HITL canvas/UX loop.

---

## Effort × Impact Matrix

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks or research prototype
*Impact* — **Low**: marginal · **Medium**: noticeable quality/UX improvement · **High**: major capability unlock · **Very High**: differentiating feature unavailable in comparable tools

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | — | — | — | — |
| **Medium (1d–1w)** | — | §1.2 line art extraction | §1.1 text/bubble removal (manual-mask MVP) · §1.3 Gabor features | §2.1 Levin scribble colorizer (unlocks entire MVP loop) |
| **High (1–2w)** | — | §5.3 uncertainty overlay (deferred) | §2.2 screentone level-set · §3.1 3D temporal propagation · §3.2 graph-cut coherence · §5.1 layered canvas editor · §6.1/§6.2 GUI tabs | §2.4 Optimal-Transport reference colorizer (dominant industrial workflow) |
| **Very High (2w+)** | — | §2.3 graph-correspondence QP (fallback path) | §5.2 quadtree acceleration | §3.3 ARAP mesh puppeteering · §2.5 diffusion reference colorizer [Research] · §3.4 diffusion inbetweening [Research] |

---

## Document History

*Created 2026-08-03. Research basis: **[`research/Manga Colorization and Animation Research.md`](../research/Manga%20Colorization%20and%20Animation%20Research.md)** (merged from the prior "HITL Deep Learning for Manga Colorization and Animation" and "Mathematical Optimization in Manga Colorization and Animation" research passes). Tracked under GitHub Milestone #6 ("Manga Colorization and Animation").*
