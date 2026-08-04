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

Research basis: [`research/Manga Colorization and Animation Research.md`](../../research/Manga%20Colorization%20and%20Animation%20Research.md) (merged from the prior HITL-deep-learning and mathematical-optimization research passes).

---

## 1. Pre-Processing & Semantic Extraction

### 1.1 Text/Speech-Bubble Detection + Inpainting

**Pain point:** Without removing dialogue text, both diffusion colorizers and quadratic-cost solvers will hallucinate colors onto glyphs, or (for the pattern-continuity solver, §2.2) the text mask breaks the halting function's pattern continuity.

**Recommendation:** CRAFT or PaddleOCR (Python, `paddleocr` package) for bounding-box detection + mask expansion; LaMa (`simple-lama-inpainting` PyPI package) for reconstruction. New `backend/src/models/wrappers/lama_wrapper.py` + `backend/src/manga/text_removal.py`. [Quick Win] for MVP scribble-based colorization (§2.1) if manual masking is offered first; full auto-detection is Medium effort.

### 1.2 Line Art Extraction

**Pain point:** Colorization solvers need a clean structural boundary map, not raw scanned pixels.

**Recommendation:** PiDiNet (lightweight, ONNX-exportable) as the primary edge extractor; Informative-Drawing as a fallback/quality option. New `backend/src/models/wrappers/pidinet_wrapper.py`.

### 1.3 Screentone Gabor Feature Extraction

**Pain point:** Raw pixel intensity is unusable as an affinity signal on screentoned manga (§5.2 of the research report) — local variance is artificially maximized by halftone dots, breaking both the Levin quadratic-cost weighting (§2.1) and naive edge detection.

**Recommendation:** A Gabor filter bank (`cv2.getGaborKernel` bank across orientations/frequencies) computing a per-pixel texture signature $T(x,y)$, implemented in `base/src/manga/gabor_features.cpp` for performance (full-page 4K Gabor convolution in Python/NumPy is too slow for interactive HITL). This is the shared foundation for §2.2's level-set halting function and a stronger affinity signal for §2.3/§2.4's superpixel segmentation.

---

## 2. Reference-Guided Colorization

### 2.1 Levin Quadratic-Cost Scribble Colorizer — ✅ Done (2026-08-04, issue #186)

**Pain point:** No deterministic, from-scratch (no pretrained weights) scribble-based colorization exists in the toolkit today.

**Formulation:** minimize $J(U) = U^T(I-W)^T(I-W)U$ per chrominance channel, $W$ built from intensity-correlation weights (research report §5.1). Solve via sparse Cholesky or preconditioned conjugate gradient.

**Shipped as:** `backend/src/manga/colorization.py` (`build_levin_system()` + `colorize_scribble()`) — **pure Python/NumPy/SciPy**, not the C++ `base::manga`/Eigen kernel this section originally recommended. `scipy.sparse.linalg.splu` solves each chrominance channel; the affinity matrix is assembled via fully-vectorized NumPy (no per-pixel Python loop). A `max_solve_dim` cap (default 640px) solves chrominance at reduced resolution and upsamples it onto full-resolution luminance for large images, keeping solve time roughly constant (~4s) regardless of source size — the quadtree acceleration in §5.2 remains the follow-up for genuinely interactive (sub-second) redraw.

**Why the deviation from the plan:** SciPy's sparse LU solver is fast enough for interactive single-page use, and building the first working version this way avoided opening a new CMake/pybind11 build-system surface (and an unverified Eigen dependency) before proving out the rest of the HITL loop end-to-end. A native `base::manga` port remains open as a follow-up if profiling ever shows it's needed for multi-page batch throughput — tracked as a reopenable scope note on issue #186, not a new issue.

Tests: `backend/test/manga/test_colorization.py` (12).

### 2.2 Screentone-Aware Level-Set Propagation

**Pain point:** §2.1 alone fails on screentoned regions (halftone dot variance breaks the weighting function).

**Formulation:** Level-set PDE $\Phi_t = h \cdot (F_0 + F_1|\nabla\Phi|)$ with halting function $h(x,y) = 1/(1+|D(T_{scribble}, T(x,y))|)$ over the Gabor features from §1.3 (research report §5.2).

**Recommendation:** `base::manga::propagate_screentone()`, consuming §1.3's feature maps. Ship as an alternate/blended mode in the same colorizer entry point as §2.1 (auto-detect screentone density and switch weighting strategy, or expose as a toggle).

### 2.3 Graph-Correspondence QP Reference Colorizer

**Pain point:** Scribbling is not the dominant industrial workflow — artists want to color an entire chapter from one reference sheet.

**Formulation:** superpixel graphs, relaxed Quadratic Assignment ($\min_x x^TQx$ subject to one-to-one marginal constraints), Hungarian-method discretization (research report §5.3).

**Options.** **A** SLIC superpixel segmentation (OpenCV, already likely available) + a QP relaxation solved with `scipy.optimize` or a dedicated C++ QP solver (OSQP) exposed via pybind11. **B** Defer superpixel graph matching entirely and go straight to Optimal Transport (§2.4), which subsumes much of the same use case at lower implementation risk.

**Recommendation:** B first if timeline is tight (OT/Sinkhorn is simpler to implement correctly and is GPU-friendly); A as a follow-up for cases where OT's soft assignment under-performs on sharply bounded regions (e.g. distinct clothing pieces).

### 2.4 Optimal-Transport / Sinkhorn Reference Colorizer

**Pain point:** Same as §2.3 — reference-based full-chapter colorization — via a more GPU-friendly, differentiable formulation.

**Formulation:** entropic-regularized OT, $\min_P \langle P,C\rangle + \epsilon H(P)$, solved by Sinkhorn iteration; Optimal Flow Transport (OFT) variant for occluded/disjoint character regions (research report §5.4).

**Recommendation:** Implement via `POT` (Python Optimal Transport library) for the MVP (`ot.sinkhorn`), with a C++/CUDA reimplementation in `base/` only if profiling shows it's the interactive-latency bottleneck (Sinkhorn's matrix-vector iterations are naturally GPU-parallel — consider `torch`-based Sinkhorn on CUDA before hand-rolling C++). This is Medium-High effort but the highest-value MVP colorization mode for real production use (reference-sheet-driven, matches the dominant manga workflow per the research report).

### 2.5 Diffusion Reference Colorizer (MangaNinja-style) [Research]

**Pain point:** Pure mathematical optimization cannot hallucinate genuinely new visual data (e.g., the back of a character's head never shown in the reference).

**Recommendation:** Do not build a native wrapper yet. Prototype via existing ComfyUI integration (`comfy_manager.py`) with a MangaNinja or ColorFlow community workflow JSON, gated behind explicit user opt-in given the copyright exposure discussed in the research report §1. Promote to a native `backend/src/models/wrappers/manganinja_wrapper.py` only if the ComfyUI spike proves the quality delta justifies it.

---

## 3. Spatio-Temporal Animation

### 3.1 3D Quadratic-Cost Temporal Propagation

**Pain point:** §2.1's colorizer only handles single frames; animated sequences need scribbles to propagate through time, not just space.

**Recommendation:** Extend `base::manga::colorize_scribble()` (§2.1) to accept a 3D $(x,y,t)$ neighborhood — same solver, expanded affinity graph. Reuses the Eigen sparse-solver investment from §2.1 directly.

### 3.2 Graph-Cut (Boykov-Kolmogorov) Temporal Coherence

**Pain point:** §3.1 degrades under fast motion/occlusion where local intensity tracking breaks down.

**Formulation:** MRF energy $E(L) = \sum_p D_p(L_p) + \sum_{(p,q)} V_{p,q}(L_p,L_q)$, solved via Boykov-Kolmogorov max-flow/min-cut (research report §6.1).

**Recommendation:** Use an existing, well-tested max-flow library (`maxflow`/PyMaxflow wraps the reference Boykov-Kolmogorov C++ implementation) rather than reimplementing graph-cut from scratch — lower risk, same guarantees. Wire the data term from §2.1/§2.4 outputs and the smoothness term from §1.3's Gabor features.

### 3.3 ARAP Mesh Puppeteering

**Pain point:** No mesh-based deformation/animation tool exists; pixel-level color-flow animation (§3.1/§3.2) does not itself move characters, only recolors static frames.

**Formulation:** alternating local step (per-triangle SVD rotation) / global step (sparse Poisson solve), skeleton-length constraint (research report §6.2).

**Recommendation:** `base::manga::arap_deform()` in C++ (SVD via Eigen, sparse solve via the same solver stack as §2.1). This is the highest-effort item in the roadmap (mesh generation, rigging UI, real-time re-solve) but is the deterministic counterpart to Live2D-style puppeteering and the clearest "animate a single manga panel interactively" HITL demo.

### 3.4 Diffusion Inbetweening (ToonCrafter-style) [Research]

**Recommendation:** Same posture as §2.5 — ComfyUI-first spike (ToonCrafter is already referenced elsewhere in the codebase's ASP research for ghost-fill, see `moon/roadmaps/asp.md`); evaluate sharing a wrapper with ASP's `animation/anim_fill.py` ghost-fill path before writing a manga-specific one.

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

### 5.2 Quadtree-Accelerated Interactive Solve

**Pain point:** Full-resolution 4K sparse-solve on every scribble stroke is too slow for interactive feedback.

**Recommendation:** Recursive quadtree partitioning of flat vs. detailed regions (research report §9.3) before building the affinity graph for §2.1–§2.4; re-solve only the dirty quadtree region touched by the latest stroke, not the whole page. Medium-High effort; required for genuine interactivity, deferrable for an initial "solve on demand" (non-live) MVP.

### 5.3 Uncertainty Overlay (MC-Dropout/BALD)

**Recommendation:** Only meaningful for §2.5's diffusion path (MC-Dropout requires a stochastic model); low priority until that path is built. Deterministic solvers (§2.1–§2.4) have no useful uncertainty signal beyond residual energy, which can be surfaced more simply as a "low-confidence region" heatmap from the solver's own residual.

---

## 6. GUI Test Components

New GUI tabs to exercise and validate each backend capability above end-to-end — following the existing tab conventions in `gui/src/tabs/animation/` and `gui/src/tabs/models/gen/`.

### 6.1 Manga Colorization Tab — ✅ Done (2026-08-04, issue #195)

**New file:** `gui/src/tabs/manga/colorization_tab.py`, registered as a new "Manga" category (→ "Colorization") in `gui/src/windows/main/_tab_registry.py`.

**Shipped:** embeds the §5.1 layered canvas editor; line-art file loader (`DIALOG_OPTS`-safe); pen color/width controls; a mode selector listing all four planned colorization modes with only "Scribble (Levin)" enabled (the other three are disabled placeholders pending §2.2/§2.3/§2.4's backends, so the tab won't need reshaping once they land); "Colorize" runs the solver off the UI thread via `gui/src/helpers/manga/colorize_worker.py`'s `ColorizeWorker` (`QThread` subclass overriding `run()`); PNG export. **Not yet shipped** (deferred, not a gap in this pass's scope): reference-image loader (only relevant to §2.3/§2.4's not-yet-built reference-based modes) and a Before/After toggle (the canvas editor's layer stack already shows line art composited live over the result, judged sufficient for the scribble-mode MVP).

Tests: `gui/test/manga/test_colorization_tab.py` (8).

### 6.2 Manga Animation Tab

**New file:** `gui/src/tabs/manga/animation_tab.py`.

**Contents:** frame-sequence loader; scribble-through-time UI reusing §5.1's canvas across a frame scrubber; mode selector (3D quadratic-cost §3.1, Graph-Cut §3.2, ARAP mesh puppeteering §3.3); mesh-vertex control-point overlay for §3.3; playback preview.

### 6.3 Preference Review Dialog (DPO capture)

**New file:** `gui/src/components/manga_preference_dialog.py`.

**Contents:** side-by-side candidate comparison (A/B) with a single-click preference vote, feeding the §4.1/§4.2 pipeline once it exists. Built early (as a stub capturing preferences to a local SQLite/JSON log even before §4 lands) so preference data collection starts as soon as any generative mode (§2.5/§3.4) ships, rather than being retrofitted later.

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

*Created 2026-08-03. Research basis: **[`research/Manga Colorization and Animation Research.md`](../../research/Manga%20Colorization%20and%20Animation%20Research.md)** (merged from the prior "HITL Deep Learning for Manga Colorization and Animation" and "Mathematical Optimization in Manga Colorization and Animation" research passes). Tracked under GitHub Milestone #6 ("Manga Colorization and Animation").*
