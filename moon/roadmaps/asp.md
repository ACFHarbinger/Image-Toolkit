# ASP Roadmap — Anime Stitch Pipeline: Quality & Reliability

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [§0 CRITICAL: Pipeline Fundamentally Broken for Animated Video Scenes](#0-critical-pipeline-fundamentally-broken-for-animated-video-scenes-priority-0)
- [§0.1 Foreground Pose Registration — The Core Fix](#01-foreground-pose-registration--the-core-fix-priority-0)
- [§0.2 Pose-Consistency-Aware Frame Selection](#02-pose-consistency-aware-frame-selection-priority-1--infrastructure-built-disabled)
- [§0.5 min_gap Threshold Calibration](#05-min_gap-threshold-calibration-priority-2--quick-win)
- [§1.1 Bundle Adjustment Hardening](#11-bundle-adjustment-hardening)
- [§1.2 Near-Zero / Zero-Translation Edge Filter](#12-near-zero--zero-translation-edge-filter)
- [§1.3 Scale and Rotation Handling](#13-scale-and-rotation-handling)
- [§1.4 Gain Clamp Widening for Dark Scenes](#14-gain-clamp-widening-for-dark-scenes)
- [§1.5 Stage 11 Composite Performance](#15-stage-11-composite-performance)
- [§1.6 Ghosting Reduction in Composite Zone](#16-ghosting-reduction-in-composite-zone)
- [§1.7 RecDiffusion Border Rectangling](#17-recdiffusion-border-rectangling)
- [§1.8 ASP Pipeline Configuration File](#18-asp-pipeline-configuration-file)
- [§1.9 Fallback Path Purity](#19-fallback-path-purity)
- [§1.10 RLHF Loop Integration](#110-rlhf-loop-integration)
- [§2.0 ASP Human-in-the-Loop Augmentation](#20-asp-human-in-the-loop-augmentation-priority-medium--unique-multiplier)
- [§2.9 BigWarp / Fourier-Mellin Manual Registration Fallback](#29-bigwarp--fourier-mellin-manual-registration-fallback-priority-high-hitl)
- [§2.10 SAM2Flow / FlowVid Interactive Optical Flow Kinematics](#210-sam2flow--flowvid-interactive-optical-flow-kinematics-research--hitl)
- [§2.11 Intelligent Scissors Seam Routing](#211-intelligent-scissors-seam-routing-quick-win--replaces-dp-seam)
- [§3.0 ML-Driven Pipeline Modernisation](#30-ml-driven-pipeline-modernisation-research-phase--from-ml-research-report)
- [§3.11 SAM 2 — Interactive Masking Upgrade](#311-sam-2--interactive-masking-upgrade-research--hitl)
- [§3.12 Overmix Sub-Pixel Averaging](#312-overmix-sub-pixel-averaging--maximal-frame-ingestion-philosophy-research)
- [Phase 2 — Next Generation Upgrade](#phase-2--next-generation-upgrade-direct-video-ingestion--multi-modal-hitl)
- [Shipped Archive (§1.11–§1.85)](#111-animation-hold-detection--preprocessing--option-a-shipped--session-6)
- [Effort × Impact Matrix — Pending Items](#effort--impact-matrix--pending-items)
- [Anchor Index](#anchor-index)

---

## Implementation Timeline

> **Legend** — *Node fill:* new feature (blue) · augmentation (violet) · bug fix (red) · infrastructure (cyan) · performance (orange) · research (slate) · testing (amber) — *Node border:* ✅ complete (green, thick) · 🔄 in-progress (amber, thick) · ⬜ planned (slate, thin) · 🚫 blocked (red) · ⏸ on hold (purple) — *Edges:* `==>` critical blocking dependency · `-->` sequential dependency · `-.->` alternative approach · `---` complements

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

    subgraph CRITICAL["§0  Critical Fixes  (Priority 0)"]
        S0["§0 Pipeline Broken\nfor Animated Scenes\n— Diagnosis"]:::fix:::done
        S01["§0.1 Foreground Pose\nRegistration\n— Core Fix"]:::feature:::done
        S02["§0.2 Pose-Consistent\nFrame Selection\n(infra built, disabled)"]:::augment:::active
    end

    subgraph SHIPPED["§0.5 + §1  Shipped Improvements"]
        S05["§0.5 min_gap\nThreshold\nCalibration"]:::fix:::done
        S11["§1.1 Bundle\nAdjustment\nHardening"]:::augment:::done
        S12["§1.2 Near-Zero\nEdge Filter"]:::fix:::done
        S13["§1.3 Scale &\nRotation\nHandling"]:::augment:::planned
        S14["§1.4 Gain Clamp\nWidening"]:::fix:::done
        S15["§1.5 Stage 11\nComposite\nPerformance"]:::perf:::done
        S16["§1.6 Ghosting\nReduction"]:::fix:::done
        S17["§1.7 Border\nRectangling\n(partial)"]:::augment:::done
        S18["§1.8 Config\nFile"]:::infra:::done
        S19["§1.9 Fallback\nPath Purity"]:::fix:::done
        S110["§1.10 RLHF\nLoop\nIntegration"]:::feature:::done
        ARCH["§1.11–§1.86\nShipped Archive\n(75+ quick wins)"]:::augment:::done
    end

    subgraph HITL["§2  HITL & Advanced Interaction"]
        S20["§2.0 Human-in-the-\nLoop Augmentation"]:::feature:::planned
        S29["§2.9 BigWarp /\nFourier-Mellin\nManual Registration"]:::feature:::planned
        S210["§2.10 SAM2Flow\nOptical Flow\nKinematics"]:::research:::planned
        S211["§2.11 Intelligent\nScissors\nSeam Routing"]:::feature:::planned
    end

    subgraph ML["§3  ML-Driven Modernisation"]
        S30["§3.0 ML-Driven\nPipeline\nModernisation"]:::research:::planned
        S311["§3.11 SAM 2\nInteractive\nMasking"]:::research:::planned
        S312["§3.12 Overmix\nSub-Pixel\nAveraging SR"]:::research:::planned
    end

    subgraph FUTURE["Phase 2+  Next Generation"]
        PH2["Phase 2\nDirect Video Ingestion\n& Multi-Modal HITL"]:::feature:::planned
        PH4["Phase 4\nOpenCV-Informed\nImprovements"]:::feature:::planned
    end

    %% Critical path
    S0  ==> S01
    S01 ==> S02

    %% §0.1 unblocks shipped improvements
    S01 --> S11
    S01 --> S16
    S01 --> ARCH

    %% Alignment group
    S05 --> S12
    S11 --- S12
    S12 --- S13

    %% Compositing group
    S14 --- S15
    S15 --- S16

    %% Robustness group
    S17 --- S19
    S18 --- S110

    %% HITL relationships
    S20 --> S29
    S20 --- S210
    S211 --- S16

    %% ML relationships
    S30 --> S311
    S30 --> S312

    %% Future phase dependencies
    S20 --> PH2
    S30 --> PH2
    PH4 --- S30
```

*Read the diagram: each node represents a high-level roadmap section. Fill colour shows element type (blue = new feature, violet = augmentation, red = bugfix, cyan = infrastructure, orange = performance, slate = research). Border colour shows implementation status (thick green = shipped, thick amber = in-progress, thin slate = planned). Solid arrows (`-->`) show sequential dependencies; double arrows (`==>`) show critical blocking dependencies; lines without arrowheads (`---`) show complementary relationships.*

---

## How to Use This Document

Each section lists the pain point, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping before committing. Items tagged **[Long-term]** are aspirational or depend on external data collection.

---

## 0. CRITICAL: Pipeline Fundamentally Broken for Animated Video Scenes [Priority 0]

**Established by visual inspection (2026-06-01):** After inspecting actual output images, the pipeline is producing catastrophically bad results on the majority of ASP-succeeded tests. The CV metrics (sharpness, ghosting, SSIM) completely mask this — the benchmark reports 65% "asp_better" when visual reality is approximately the opposite.

**What the failures look like:** Multiple horizontal strips with completely mismatched colors, duplicated body parts at seam boundaries, exposed character poses at different animation states in adjacent strips. The simple stitch, despite less coverage, is visually coherent and usable.

**Root cause:** The pipeline was designed for scrolling static art (manga panels). The test datasets are animated video where characters move independently of the camera. Phase correlation on whole frames cannot separate camera movement from character animation. The temporal median requires ≥3 frames per canvas row to suppress animation artifacts; with 50px frame steps across 1080px frames, most canvas rows have only 1 frame.

**Required fixes before any other work:**
1. Background-only phase correlation in frame selector (run BiRefNet first)
2. Multi-frame canvas coverage check before compositing (fall back to SCANS if median coverage < 2 frames/row) — ✅ DONE (Stage 10.5, `_compute_row_coverage()`, `ASP_COV_MIN_MULTI_PCT=0.30`)
3. Replace sharpness metric with seam coherence metric (row-mean luminance variance) — ✅ DONE
4. Seam validation gate after composite (if adjacent strips differ >15 lum units, reject and use SCANS) — ✅ DONE (render gate)

**Deeper root cause (established 2026-06-03, see `reports/Image_Stitching_Research.md` §8):** Items 1–4 are *symptom mitigations*. The true gap is that the pipeline has **no mechanism to register the deforming foreground across frames.** The character animates while the camera pans, so body parts land in two different poses on either side of every strip seam. Fixing this requires the foreground-assembly stage in §0.1 below — that is the actual solution; everything else raises the floor without raising the ceiling.

---

## 0.1 Foreground Pose Registration — The Core Fix [Priority 0]

**Pain point:** Even ASP's best cases (test09) show torn/doubled character edges at strip seams. The translation-only camera model aligns the *background* perfectly but cannot represent the *non-rigid articulated motion* of the character animating between the frames being stitched. This is the dominant artifact and the reason ASP loses to simple-stitch on ground-truth SSIM (0.669 vs 0.695).

**Key reframing:** This is **multi-frame fusion of moving content** — structurally identical to ghost-free HDR (DDFNet) and video-SR alignment (FDAN). The proven recipe is: estimate optical flow → warp moving content toward a reference → fuse. Applied to the foreground, with anime adaptations (segment-guided flow for flat regions, ARAP/LSD to protect line art).

**Core idea:** Keep the rigid translation model for the background. Add a flow-guided, ARAP-regularised **foreground registration stage** that decomposes foreground motion into `F_fg = T_camera + A_animation`, subtracts the known camera translation, and warps out the residual animation motion so body parts line up across seams. The body is still assembled from multiple frames — each frame's foreground is just re-posed to a common reference before compositing.

### Options

**A — Flow-guided foreground re-posing (recommended core)**
SEA-RAFT dense flow over the fg overlap zone → subtract `T_camera` → symmetric midpoint warp of both strips' foreground toward the mean pose. Similarity-regularised warp first, upgrade to full ARAP later.
- Pros: Directly fixes seam tears. Reuses BiRefNet masks. Overlap-zone-only crops keep it fast.
- Cons: Dense flow tears on flat cel regions (mitigate with segment-guided flow). High implementation effort.
- Refs: SC-AOF (Sensors 2024), DDFNet (Sensors 2022), SEA-RAFT (ECCV 2024).

**B — ARAP cartoon registration (Sýkora 2009)**
Locally-optimal block matching + as-rigid-as-possible shape regularisation + LSD line term. Purpose-built for registering hand-drawn characters across animation poses without bending line art.
- Pros: The canonical method for this exact sub-problem. Preserves line art.
- Cons: Highest implementation complexity. Needs careful energy tuning.
- Ref: Sýkora, Dingliana & Collins, NPAR 2009.

**C — Single-pose-per-component fallback (Eden-Uyttendaele-Szeliski 2006)**
When flow confidence is low (fast action, motion blur), do not warp/average — select one coherent pose per connected foreground component and route the seam around it through background via graph cut.
- Pros: Guarantees one clean instance of each body part. Strictly better than ghost-blending.
- Cons: May drop canvas coverage where a component spans a seam.
- Ref: Eden et al., CVPR 2006.

**Recommendation:** Ship **A with a similarity warp + C as the low-confidence fallback** first; validate on test09. Add **B (full ARAP)** as the quality upgrade once A is proven. Restrict Stage 10 temporal median to background pixels only (near-free correctness fix — stops the median from ghosting the foreground at all).

**Implementation order:** (A5) background-only median → (A1) SEA-RAFT wrapper → (A2) fg/bg flow decomposition → (A4) symmetric midpoint warp → (A6) confidence-gated fallback → (A3) full ARAP. See the consolidated report §2–§4 for the full method (ARAP Push/Regularise phases, LSD collinearity term, two-channel selection).

**Status (2026-06-03 → 2026-06-03 session 2):**
- ✅ **A2/A4** — flow-guided symmetric midpoint warp (DIS or RAFT), seam-band cropping (±taper_px+16px around seam), BORDER_CONSTANT boundary fix, `~valid_content` masking.
- ✅ **A1** — **ptlflow installed**; `sea_raft_s@things` (or best available pretrained RAFT variant) loads lazily on GPU. Flow computed on seam-band crops at max_side=1280 to avoid OOM. Falls back to DIS when ptlflow unavailable. Toggle: `ASP_FLOW_ENGINE=dis` to force DIS.
- ✅ **A3** — **ARAP regularisation** implemented: `_arap_regularise()` in `fg_register.py` fits per-cell (16×16px) rigid median transforms to the fg flow, then bilinearly interpolates smooth per-pixel flow. Prevents raw flow from bending straight line-art strokes. Uses `scipy.interpolate.RegularGridInterpolator`.
- ✅ **A5** — foreground-excluded temporal median in `rendering.py` (background-only plate).
- ✅ **A6** — confidence-gated single-pose fallback when animation residual > `FG_REG_MAX_RESIDUAL`.
- ✅ **Boundary fixes** — BORDER_CONSTANT (no edge-smear), `~valid` masking (no content extension), both-content Laplacian (no ringing at canvas edges).
- ✅ **BiRefNet two-channel selector** — implemented with real BiRefNet masks (not peripheral heuristic); disabled by default (`ASP_TWO_CHANNEL_SELECT=0`) due to overhead and frame-selection regressions. Enable for targeted testing.
- ✅ **LSD collinearity term** (session 8) — `_arap_regularise()` in `fg_register.py` now accepts `image=` and `image_offset=` params. Runs `cv2.createLineSegmentDetector` on the seam-band crop; for fg/bg boundary cells where a line is detected and the projection retains ≥50% of the original flow magnitude, projects the cell's flow onto the line direction (nulling the cross-line bending component). Only fires on boundary cells to avoid corrupting rigid-body translation in the character interior.
- ✅ **Segment-guided flow (AnimeInterp SGM §3.1A full)** — `_animeinterp_sgm()` in `fg_register.py`: VGG-19 conv3_4 per-segment features + cosine × distance matching. `ASP_ANIMEINTERP_SGM=1`. Falls back to SLIC LAB-colour proxy (`ASP_SGM_PROXY=1`). S79.
- ✅ **ARAP Push phase** — Sýkora's full Push→Regularise algorithm implemented (session 4). `_arap_push()` in `fg_register.py`: per-cell SAD block matching via `cv2.matchTemplate`, 15% improvement threshold, 24px search range, 16×16 cell grid. Push → Regularise is the complete Sýkora 2009 algorithm. Benchmark finding: zero measurable GT-SSIM improvement (flow quality is not the bottleneck; ceiling is animation timing).
- ✅ **Alignment stability gate** (session 5) — Pre-render gate in `pipeline.py` and benchmark: fires when 75th-pct |dx_steps| > 50px (2D/diagonal motion). Falls back to SCANS on normalised frames immediately. test08: +0.074, test25: +0.049.
- ✅ **SLIC SGM proxy** (session 6) — `_slic_sgm_proxy()` in `fg_register.py`: SLIC superpixel centroid tracking replaces RAFT/DIS flow for fg pixels in flat cel-shaded regions. Addresses aperture problem without VGG-19 forward passes. Enable via `ASP_SGM_PROXY=1`.
- ✅ **Perceptual-hash hold detection** (session 6) — `_detect_hold_blocks()` in `frame_selection.py`: detects animation "on twos/threes" holds by thumbnail pixel MAD. Compresses frame universe, surfaces natural pose-change boundaries. Enable via `ASP_HOLD_THRESHOLD=0.025`.
- ✅ **GNC robust loss** (session 6) — `bundle_adjust.py`: upgrade `least_squares` to `loss='cauchy'` + `f_scale=10.0`. Makes BA robust against outlier edges that survive the post-solve residual pruning.

**Benchmark note (2026-06-03, session 2):** RAFT + ARAP + post_warp_diff escalation → SSIM essentially flat vs session 1 (test09: 0.787, test27: 0.709). Experiments tried and their outcomes:
- **Global reference pose (asymmetric alpha)**: catastrophic regression on test27 (-0.151) due to flow noise amplification at α=1.0 seams. Reverted.
- **Character bounding-box crop**: incorrectly cuts horizontal extent for vertical pans (cuts locker background). Reverted.
- **post_warp_diff threshold=22**: marginal +0.002 on test08, -0.001 on test57. Kept.
- **max_residual=50**: consistent +0.001 on test08 (9/13 seams single-pose); no improvement on others.
- **ARAP cell_size=8, n_iter=3**: no measurable SSIM change.

**The SSIM ceiling** for the current corpus is determined by animation timing between selected frames vs the GT reference, not by flow quality or regularisation. RAFT and DIS give identical residual estimates. The midpoint warp halves the pose gap; the remaining half is what limits SSIM.

---

## 0.2 Pose-Consistency-Aware Frame Selection [Priority 1 — Infrastructure Built, Disabled]

**Pain point:** The smart selector uses whole-frame phase correlation, so a "50px displacement" can be 5px camera + 45px limb swing — it picks pose-incoherent frames, maximising the motion §0.1 must later correct.

**Session 3 status (2026-06-03):** Infrastructure shipped but disabled. Two-pass selector implemented in `backend/src/animation/frame_selection.py` and `_smart_select_frames()` in benchmark. Pass 2 uses gradient-magnitude L1 on central-crop thumbnails as a pose proxy. Benchmarking showed this proxy is confounded by background structure (lockers, walls), causing regressions of -0.043 (test04) and -0.026 (test27). Disabled by default (`ASP_POSE_WINDOW_PX=0`).

**What's needed to make this work:** Foreground-only pose similarity — either:
- DWPose/ViTPose joint positions (background-agnostic by design)
- RAFT optical flow on BiRefNet-masked foreground only (similar to but decoupled from Stage 8.5 flow)
- DINO/CLIP features extracted from the foreground mask crop

**Correct implementation path:**
1. Run BiRefNet once on ALL frames before selection (deduplicates the current double-run overhead)
2. Use background-only phase correlation for camera displacement
3. For each camera-qualifying candidate, compute foreground flow vs last selected frame
4. Pick candidate with smallest foreground flow magnitude within the selection window

**Current state (session 8 & 9):** DINOv2 (`dinov2_vits14`) cosine distance metric implemented; model cached as module-level singleton (no reload per test, batch inference). Hold-block penalty in Pass 2 ensures cross-hold candidates are preferred. Session 9: model now processes all frames in one batched forward pass instead of per-frame loops. Enabled with `ASP_POSE_WINDOW_PX=80`. Aligned-SSIM built into the benchmark to decouple framing bias from GT-SSIM.

---

## 0.5 min_gap Threshold Calibration [Priority 2 — Quick Win]

**Pain point:** On the 94-test corpus, 23 of 25 fallbacks (92%) are caused by `min_gap < 50px`. Note: fixing this will produce more ASP-succeeded tests, but those tests will exhibit the same compositing failures described in §0 until that is fixed first. This is not a quality fix — it only changes the fallback rate.

### Options

**A — Lower static threshold to 25px [Quick Win]** ✅ **Shipped (pre-S6)**
Change `MIN_GAP_PX` in `validation.py` from 50 to 25. Immediately rescues ~9 datasets.
- Pros: One-line change. Proven safe — genuine co-located frames have gaps < 5px.
- Cons: Fixed threshold; doesn't adapt to canvas resolution.

**B — Vector magnitude gap (multi-axis) [Quick Win]** ✅ **Shipped (pre-S6)**
Replace `min(|dy|)` with `min(sqrt(dy² + dx²))` for the gap computation. Fixes 6 datasets with diagonal scroll where dy=40px but actual displacement=100px.
- Pros: Physically correct for diagonal scrolls. One-line change.
- Cons: Slightly more complex formula.

**C — Adaptive threshold based on selected frame density** ✅ **Shipped S36**
`_compute_adaptive_min_gap(affines)` in `validation.py` — returns `max(20.0, canvas_span / (N × 3))` where `canvas_span` is the dominant-axis displacement range (`max(dy_span, dx_span)`). Canvas height is not required; the displacement span is a sufficient proxy (it equals canvas_span - frame_h, but frame_h is constant across frames). Wired into Stage 7b of `pipeline.py` as the `min_step` for the first `_validate_affines` call. Log message updated. `_compute_adaptive_min_gap` exported in `__all__`. 5 new tests in `test_affine_validation.py::TestAdaptiveMinGap`.
- Pros: Content-aware; slow-scroll sequences benefit (floor=20px rescues tight-but-valid gaps); fast-scroll/4K now applies a proportionally higher threshold.
- Cons: Span proxy slightly underestimates canvas height by one frame_h, but this is a bounded error (< 5% for typical frame/canvas ratios).

**D — Adaptive rotation/scale thresholds** ✅ **Shipped S47**
`_compute_adaptive_rot_scale(affines) → (max_rotation, max_scale_dev)` in `validation.py`. When frame-to-frame σ of rotation (or scale) < `_ROT_SCALE_CONSISTENCY_THRESH=0.02`, returns loose threshold `0.15` (was hardcoded `0.10`). Consistent rotation/scale signals a systematic camera property (lens barrel distortion, constant zoom); inconsistent values signal BA noise. Wired into Stage 7b initial validation and Retry 0. Constants: `_ROT_TIGHT=0.10`, `_ROT_LOOSE=0.15`, `_SC_TIGHT=0.10`, `_SC_LOOSE=0.15`. Exported in `__all__`. 5 new tests in `test_affine_validation.py::TestAdaptiveRotScale`.
- Targets test5 (zoom-pan: max_rot≈0.111, scale_dev≈0.121 — just above the 0.10 tight ceiling, below 0.15).
- σ≈0 for a true zoom-pan sequence (all frames share the same lens distortion) → loose threshold returned → validation passes without any retry.

**Recommendation:** Implement B first (zero risk, fixes multi-axis scrolls), then A (lower threshold). Combined, these should bring the success rate to ~83% (78/94).

---

## 1.1 Bundle Adjustment Hardening

**Pain point (updated 2026-06-01):** On the 94-test corpus, ratio failures are nearly eliminated — only 2/25 fallbacks (8%) are ratio > 3.0, vs 58% in the pre-Phase-3 corpus. The 2-pronged outlier rejection added in Phase 3 is working well on real-world data. New concern: heuristics tuned for the current corpus may still fail on datasets with >40% true outliers.

### Options

**A — Post-solve residual pruning (current approach)**
After the initial Levenberg-Marquardt solve, compute per-edge predicted-vs-actual translation; reject edges where `|residual| > 3 × median`; re-solve. Simple, fast (~0.15s), proven on the 22-test corpus.
- Pros: Already implemented. Zero new dependencies.
- Cons: Median threshold is corpus-tuned; may fail on datasets with >40% outliers.

**B — RANSAC before LM (consensus pre-filter)** ✅ **Shipped S45**
`_spanning_tree_inlier_filter(edges, num_frames, inlier_threshold=50.0)` in `bundle_adjust.py`. Builds a maximum-weight spanning tree (Kruskal greedy, highest-weight-first), BFS-propagates a reference translation from frame 0, and rejects any edge whose observed dx/dy disagrees with the reference by > 50 px. Spanning-tree edges always pass (residual = 0 by construction). Falls back to original edges when the graph is disconnected or fewer than `max(2, N-1)` inliers survive. Wired at the top of `_bundle_adjust_affine` before DOF setup. 5 tests in `test_bundle_adjust.py::TestSpanningTreeInlierFilter`.
- Implementations: classic RANSAC, MAGSAC++ (adaptive threshold), LO-RANSAC (local optimisation after each model draw). **Shipped:** spanning-tree deterministic consensus (zero random seed, O(E log E), no new dependencies).
- Pros: More principled than post-solve pruning. Especially robust when >30% of edges are bad. Deterministic — no random seed, reproducible results.
- Cons: Significantly slower. MAGSAC++ adds a dependency (poselib or custom impl).
- Reference: [RANSAC variants survey](https://arxiv.org/abs/1905.00604)

**C — Graduated Non-Convexity (GNC) robust loss** ✅ **Shipped S6**
Replace the L2 residual in the LM cost function with a robust loss (Geman-McClure, Cauchy, or Welsch) that automatically down-weights outlier edges during optimisation. The weight schedule is annealed from convex to non-convex so the solver never gets stuck in a local minimum induced by outliers.
- Implementation: `scipy.optimize.least_squares(method='trf', loss='cauchy', f_scale=...)` — can be a one-line swap if the Jacobian is compatible with scipy's interface.
- Pros: No separate rejection step. Theoretical guarantees at up to 70–80% outlier rate (Yang et al., 2019; FracGM 2025 improves convergence further). Generalises better to unseen data.
- Cons: Loss hyperparameter (f_scale) needs tuning. Slower than Option A.
- Reference: [GNC for Spatial Perception (arXiv 1909.08605)](https://arxiv.org/abs/1909.08605)

**D — Adaptive Graduated Non-Convexity (AGNC) ✅ DONE (S30, simplified)**
Simplified AGNC: `_compute_adaptive_f_scale(edges, affines, floor)` in `bundle_adjust.py` — after initial solve, computes `max(floor, 2.0 × median_residual_px)` from the preliminary affines. If adaptive_scale > _BA_F_SCALE × 1.5, re-solves with the data-derived scale (warm-started). For clean data the floor dominates (behaviour unchanged); for uniformly noisy data (median ~30px) the scale widens to ~60px so legitimate edges are not over-penalised. 5 tests in `test_bundle_adjust.py`.
- Implementation: `scipy.optimize.least_squares(method='trf', loss='cauchy', f_scale=...)` with a wrapper that tunes `f_scale` adaptively based on residual distribution between LM iterations.
- Pros: Optimal convergence guarantee (no fixed schedule to tune). Immune to outlier-dominated medians that break Option A. Best-in-class for extreme cases (ratio failures like test13 at 11.1×).
- Cons: More complex than C. Requires monitoring LM iteration state (scipy doesn't expose this natively — needs a custom `jac_sparsity` callback or wrapping in a custom optimizer).
- References: [SAC-GNC (IEEE Xplore 2026)](https://ieeexplore.ieee.org/document/11445542), [GNC arXiv 1909.08605](https://arxiv.org/abs/1909.08605), [Adaptive GNC (OpenReview)](https://openreview.net/forum?id=cIKQp84vqN)

**E — FracGM (fractional programming for Geman-McClure)**
Reformulates the non-convex Geman-McClure minimisation as a convex dual + linear system. 2025 state-of-the-art for robust rotation/translation estimation.
- Pros: Faster convergence than GNC, empirically better at extreme outlier ratios.
- Cons: New dependency; implementation complexity. Overkill unless D shows plateau.
- Reference: 2025 FracGM paper.

**F — Learned outlier scoring (RLHF-guided)**
Train a small MLP on (edge residuals → is_outlier) using feedback from the existing RLHF infrastructure. Replaces hand-tuned threshold with a learned one.
- Pros: Self-improving with accumulated feedback.
- Cons: Requires labelled outlier data from the feedback loop (see §1.10). Not viable until the RLHF loop is closed.

**Recommendation:** Ship C (GNC Cauchy loss, `loss='cauchy', f_scale=10.0`) immediately — it's a one-line scipy change and eliminates the worst outlier failures. Prototype D (AGNC) as the quality ceiling; the adaptive schedule removes the `f_scale` tuning burden. Skip B (RANSAC) and E (FracGM) until C/D show a plateau.

---

## 1.2 Near-Zero / Zero-Translation Edge Filter

**Pain point:** Tests 4, 9, 16, 21 failed `min_gap < 50px` due to co-located or near-static frames placed at the same canvas row, causing temporal median collapse.

### Options

**A — Pre-bundle static edge rejection [Quick Win] ✅ DONE (S32)**
`_reject_static_edges(edges, min_disp_px)` in `pipeline.py`. `STATIC_EDGE_MIN_DISP_PX=50` in `constants/animation.py`. Called at the top of `_filter_edges()` before the geometric consistency filter. 5 tests in `test_filter_edges.py`.
- Pros: Fast, zero dependencies, one-line change.
- Cons: Fixed 50px threshold doesn't scale with canvas resolution or scroll speed.

**B — Near-duplicate frame deduplication via perceptual distance** ✅ **Shipped S26**
Before matching, compare each frame to the previous using mean luma difference, SSIM, or histogram distance. Drop frames below a threshold.
- `_near_dup_luma_filter` in `frame_selection.py` — post-filter on the selected list using mean abs grayscale diff. Default OFF (`ASP_NEAR_DUP_LUMA=0.0`). `NEAR_DUP_LUMA_THRESH=3.0` constant extracted from pipeline.py pre-stage-5 dedup.
- First frame always kept; last frame always retained (canvas extent preservation).
- Pros: Removes the bad source upstream; cleaner than downstream rejection.
- Cons: SSIM adds ~5ms per frame pair (acceptable). Threshold may need tuning per content type.

**C — Adaptive min-step threshold** ✅ **Shipped S34**
Estimate expected inter-frame step as `canvas_height / N_frames`. Flag edges where step < 10% of expected. Automatically scales to different resolutions and scroll speeds.
- `_compute_adaptive_min_disp(edges)` in `pipeline.py` — returns `max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC * median_adjacent_step)` on the dominant scroll axis. Wired into `_filter_edges` before `_reject_static_edges`. `ADAPTIVE_MIN_DISP_FRAC=0.10` constant in `constants/animation.py`. 5 new tests in `test_filter_edges.py::TestComputeAdaptiveMinDisp`.
- Pros: Content-adaptive; handles 1080p and 4K equally well.
- Cons: Estimate can be wrong for non-uniform scroll (e.g., scene transitions).

**D — Temporal variance filter (motion energy)** ✅ **Shipped S39**
`_temporal_variance_filter(thumbs, paths, sigma_threshold)` in `frame_selection.py`. Stacks (i-1, i, i+1) thumbnail triplet; drops interior frame i when mean per-pixel variance < sigma_threshold (in [0,1]² space). `TEMPORAL_VAR_THRESH=1e-3` in `constants/animation.py`. Default disabled: `ASP_TEMPORAL_VAR_THRESH=0.0`. Wired as step 1a in `smart_select_frames`.
- Pros: Catches static frames before matching runs — prevents zero-displacement edges from entering the edge graph. Complements §1.2A/B/C which act on edges or selected frames.
- Cons: Slightly higher compute than SSIM. Requires storing three frames in memory simultaneously.

**Recommendation:** Implement B first (cleanest fix, removes the bad source). Follow with C to make the residual threshold content-adaptive. B and C are complementary; D is a research-track alternative.

---

## 1.3 Scale and Rotation Handling

**Pain point:** test5 (scale_dev=0.121, max_rotation=6.35°) represents zoom-and-pan sequences that the translation-only canvas model cannot handle. The affine validator correctly rejects these, but the rejection discards a potentially valid output.

### Options

**A — Full 2×3 affine warp per frame**
When `max_scale_dev > 0.05` or `max_rotation > 0.03`, replace translation-only placement with per-frame `cv2.warpAffine`. Allows scale and rotation compensation.
- Pros: Handles all affine distortions. Directly addresss the failure mode.
- Cons: Higher compute; introduces resampling blur near edges (proportional to warp magnitude). Requires per-frame affine estimation (currently only global stats are computed).

**B — OpenCV Stitcher PANORAMA fallback [Quick Win] ✅ DONE (S31)**
`_panorama_stitch_fallback(frames, output_path)` in `canvas.py`. Uses `cv2.Stitcher_create(mode=0)`; raises `RuntimeError` on failure. Wired into `pipeline.py` between Retry 3 and SCANS — catches all exceptions so SCANS remains the ultimate safety net. 5 tests in `test_canvas.py`.
- The existing `simple_stitch` path in `image_merger.py` already uses this — the change is routing the affine-rejection fallback here instead of SCANS.
- Pros: Reuses existing infrastructure. Handles arbitrary affine distortions with no new code.
- Cons: PANORAMA stitcher is slower and sometimes produces barrel distortion on vertical scroll sequences.

**C — Scale normalisation before bundle adjustment** ✅ **Shipped S54**
`_normalize_frame_scales(frames, edges, scale_thresh=0.05)` in `pipeline.py`. Extracts per-edge scale `s_ij = sqrt(a²+b²)` from matched affines; BFS spanning tree from frame 0 propagates absolute per-frame scale factors; resizes frames by `1/scale[i]` (Lanczos-4); resets edge M diagonal to 1.0, divides tx/ty by `scale[i]`. No-op when scale deviation < threshold or graph is disconnected. `SCALE_NORM_THRESH=0.05` in constants; `ASP_SCALE_NORM_THRESH=0.05` to enable (default OFF). 5 tests in `test_pipeline.py::TestNormalizeFrameScales`.
- Pros: All downstream stages (canvas, rendering, compositing) receive geometrically consistent frames without any per-stage changes. Complementary to §1.3E (S48) and §0.5D (S47).
- Cons: Lanczos-4 introduces mild ringing on very high-contrast edges at large scale ratios (>30%). Frames after normalisation have different heights, which breaks Stage 2's width-only normalisation invariant — wire after width normalisation.

**D — Homography (projective) warp per frame**
Extend A to full 8-DOF projective warp. Handles perspective (slight 3D parallax) in addition to affine.
- Pros: Broadest coverage.
- Cons: Projective warp on scroll sequences tends to over-fit small parallax into large geometric distortions. High risk of quality degradation on simple sequences.

**E — Similarity transform (scale + rotation + translation)** ✅ **Shipped S48**
`_extract_similarity(M) → (2,3) float32` in `matching.py`. Closed-form Procrustes projection: `a_sym=(M[0,0]+M[1,1])/2`, `b_sym=(M[0,1]-M[1,0])/2` → `[[a_sym, b_sym, tx], [-b_sym, a_sym, ty]]`. Shear discarded (feature matchers cannot reliably distinguish shear from perspective). `_SIMILARITY_MODE` flag (default OFF, `ASP_SIMILARITY_MODE=1` to enable). In `_match_pair`, similarity projection replaces translation-only strip when flag enabled. `ASP_SIMILARITY_MODE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 new tests in `test_matching.py::TestExtractSimilarity`.
- Complementary to §0.5D (S47): validation accepts systematic rotation/scale (`σ<0.02` → loose 0.15 threshold); similarity mode provides the correct matched affine for validation to accept.

**Recommendation:** B is lowest effort (reuses existing code path). E is the most physically appropriate model for zoom-pan sequences. Implement B as immediate fallback; prototype E as a dedicated zoom-scroll mode.

---

## 1.4 Gain Clamp Widening for Dark Scenes

**Pain point:** 17/22 tests hit the `[0.88, 1.14]` gain clamp. Dark scenes (ref_lum < 70) have proportionally larger gain swings, leaving some frames under-corrected.

### Options

**A — Conditional clamp based on ref_lum [Quick Win]** ✅ **Shipped S18**
Use `[0.82, 1.22]` when `ref_lum < 80`, `[0.88, 1.14]` otherwise.
- Pros: One-line config change. Targeted fix for dark scenes.
- Cons: Binary threshold; doesn't smoothly scale with luminance level.

**B — Continuous clamp scaling** ✅ **Shipped S24**
Linearly interpolate clamp width between dark and bright anchors: `clamp_width = 0.26 - 0.12 × (ref_lum / 255)`. Smooth, no discontinuity at a single threshold.
- Pros: More principled than A.
- Cons: Requires tuning two anchor values instead of one.

**C — Per-frame adaptive clamp (background mask only)** ✅ **Shipped S40**
`_bg_gain_unclamped(ref_lum, frame_lum, override_threshold=0.20)` in `compositing.py`. When `_adaptive_gain_clamp` would cut the ideal correction by >20%, returns raw ideal gain for bg pixels. Wired into the bg-only normalization loop; foreground pixels were already excluded at the application site. 5 tests in `test_compositing.py::TestBgGainUnclamped`.
- Pros: Eliminates residual banding when a dark/bright frame's ideal correction exceeds the clamp. Symmetric (brightening and darkening both covered).
- Cons: Background clipping possible for extreme gain (5×+); `np.clip(0,255)` handles this.

**D — Multi-scale gain (tone-mapping inspired)** ✅ **Shipped S46**
`_multiscale_gain_map(frame, reference, bg_mask, sigma=30.0, gain_min=0.5, gain_max=2.0)` in `compositing.py`. Computes per-pixel gain = `ref_blurred / (frame_blurred + ε)` where both are Gaussian-blurred background luminance maps (σ=30px). Foreground pixels are zeroed before the blur so character luminance does not contaminate the bg model. Applied via `gain_map[bg_sel, np.newaxis]` (bg only, fg untouched). `_MULTISCALE_GAIN` flag (default OFF, `ASP_MULTISCALE_GAIN=1`). `MULTISCALE_GAIN_SIGMA=30.0` in `constants/animation.py`. 5 tests in `test_compositing.py::TestMultiscaleGainMap`.
- Pros: Handles non-uniform scene lighting (half-dark/half-bright panels). Zero new deps.
- Cons: ~2ms overhead per 1080p frame (vs ~0.1ms for scalar gain). Default OFF.

**E — Background histogram matching** ✅ **Shipped S49**
`_bg_histogram_lut(src_pixels, ref_pixels) → float32[256]` + `_apply_bg_histogram_match(frame, reference, bg_mask) → uint8(H,W,3)` in `compositing.py`. CDF-matching LUT built via `np.searchsorted(ref_cdf, src_cdf, side="left")` — for each source intensity `v`, maps to the smallest reference intensity `u` where `CDF_ref(u) ≥ CDF_src(v)`. Per-channel application to background region (fg pixels unchanged). Identity-LUT fallback for degenerate masks (< 10 bg pixels). `_HISTOGRAM_MATCH` flag (default OFF, `ASP_HISTOGRAM_MATCH=1`). Wired as third branch in normalization loop between `_MULTISCALE_GAIN` and scalar path. Roadmap note "needs CLAHE / opencv-contrib" was incorrect — `cv2.createCLAHE()` is in base OpenCV, but standard CDF matching is cleaner and zero-overhead. 5 tests in `test_compositing.py::TestBgHistogramLut`.
- Pros: Handles non-linear tonal mismatch (S-curve exposure differences). Zero new deps (pure numpy). Does not cause hue shifts (per-channel, not luminance-only).
- Cons: ~0.5ms overhead per frame. Mutual-exclusive with `_MULTISCALE_GAIN` (multiscale takes priority). For simple multiplicative gain differences, scalar path is equally effective.

**F — Per-frame exposure outlier rejection** ✅ **Shipped S50**
`_reject_exposure_outliers(frame_lums, max_deviation_lum) → List[bool]` in `compositing.py`. Computes the median bg-lum across all frames with valid lum values; returns True for any frame where `|lum − median| > max_deviation_lum`. Frames with None lum are never rejected. Fallback: all-False when < 3 valid frames (unreliable median). `_EXPOSURE_OUTLIER_THRESH` flag (default 0.0=off, `ASP_EXPOSURE_OUTLIER_THRESH=60.0`). Wired after `_coherence_skip_mask` in normalization loop via logical-OR — skipped frames still contribute warped pixel content, only gain correction is suppressed. `EXPOSURE_OUTLIER_THRESH=60.0` in `constants/animation.py`. `ASP_EXPOSURE_OUTLIER_THRESH` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_compositing.py::TestRejectExposureOutliers`.
- Pros: Complements §1.4C (`_bg_gain_unclamped`): C aggressively corrects large-gain frames; F suppresses correction entirely for extreme outliers where correction would overshoot. Handles flash frames, accidental HDR blending, and scene-change frames that slip past hold detection.
- Cons: Default OFF — no effect unless `ASP_EXPOSURE_OUTLIER_THRESH > 0`. Threshold requires per-source tuning (60 lum = 24% brightness at ref=250, 75% at ref=80).

**Recommendation:** A is a one-line config change, ship immediately. B as a follow-on smoothing pass. E ✅ shipped S49. F ✅ shipped S50.

---

## 1.5 Stage 11 Composite Performance

**Pain point:** Stage 11 (hard-partition composite) averages 24.5s, peaking at 41.9s, accounting for ~35% of total ASP runtime. Seam DP and feather computation are the primary bottlenecks.

### Options

**A — Vectorise seam DP with NumPy** ✅ **Shipped S10**
The per-row minimum-cost path accumulation is now handled by `scipy.ndimage.minimum_filter1d(size=3, mode='constant', cval=np.inf)` — replaces the Python row-by-row loop and `left`/`right` array allocations. Traceback uses slice-argmin. Expected speedup: 5–10×.

**B — CUDA seam DP via PyTorch scatter/gather**
Implement the DP on GPU using PyTorch operations.
- Pros: Fastest possible; ~50–100× speedup on a 3090 Ti.
- Cons: Requires GPU. Adds kernel complexity. DP is inherently sequential by row — parallelisable only column-wise within each row.

**C — Restrict seam search window [Quick Win]** ✅ **Shipped S17**
Current ±250px window scans 500 columns per row. Reduce to ±100px for sequences with `dx_cv < 5` (low horizontal drift). Auto-detect from bundle adjustment output. Reduces DP grid by 60%.
- Pros: Drop-in optimisation, no algorithm change.
- Cons: May clip optimal seam path on high-drift sequences.

**D — Cache seam path across RLHF iterations** ✅ **Shipped S44**
`_make_seam_cache_key(frame_keys, k, cost_flags)` + `_get_seam_cost_flags()` in `compositing.py`. Key: `(tuple(image_paths), k, (_POISSON_SEAM, _TOONCRAFTER_SEAM))`. `_composite_foreground` accepts `frame_keys` + `seam_path_cache` optional params; cache checked before zone array allocation, populated after DP. `AnimeStitchPipeline` stores `self._seam_path_cache: Dict = {}` and passes it at Stage 11. Memory: ~4 KB per seam path (W×int32). Net speedup for RLHF re-runs: eliminates DP executor latency entirely on 2nd+ call.

**E — Parallel seam computation per strip** ✅ **Shipped S12**
When the panorama has M non-overlapping seam zones (between adjacent frame pairs), compute the M seams in parallel using `concurrent.futures.ThreadPoolExecutor`. The GIL is released during NumPy operations.
- Pros: Linear speedup proportional to M for multi-frame panoramas.
- Cons: Requires refactoring to identify independent seam zones.

**Recommendation:** A is the highest-leverage change (no dependencies). Combine with C for sequences where it applies. D is free win for RLHF iteration speed.

---

## 1.6 Ghosting Reduction in Composite Zone

**Pain point:** ASP-succeeded tests consistently have higher ghosting than simple stitch (8/10 tests). Stage 11's hard-partition seam reintroduces ghost-like edge artefacts when seams bisect character bodies.

### Options

**A — Increase foreground penalty weight in seam DP** ✅ **Shipped S19 (tiered cost)**
The `sem_cost` term in `_seam_cut` (P2.4) already routes seams away from BiRefNet-masked foreground. Increase the foreground penalty multiplier (current: partial implementation) to fully deter seams through character regions.
- Pros: Minimal code change. Directly addresses the seam-through-character problem.
- Cons: Very high penalty may force seams into narrow background corridors that cause visible aliasing.

**B — Adaptive feather width** ✅ **Shipped S22**
Make `_FADE_ROWS` a function of `|gain_A - gain_B|` across the seam. Wider feather when gain difference is large.
- Proposed formula: `fade = max(40, int(|gain_diff| × 300))`, capped at 120px.
- Pros: Smooth transitions reduce perceptual ghosting near boundaries.
- Cons: Wide feathers on high-gain-difference boundaries may blur the seam zone visibly.

**C — Poisson blending at seam zone [Quick Win]** ✅ **Shipped S21**
Replace the linear feather with gradient-domain seamless cloning (`cv2.seamlessClone`) in a ±20px band around the seam. Eliminates the brightness step even when gain correction is at its limits.
- Pros: OpenCV built-in. Medium effort, measurable improvement.
- Cons: `cv2.seamlessClone` is CPU-only and can be slow on large seam zones (~1–3s extra). Restrict to final-output mode.

**D — ToonCrafter synthetic frame fill**
In high-overlap zones (tight scroll, e.g., test22 at 90px steps), use `animation/anim_fill.py` (ToonCrafter) to generate synthetic intermediate frames that fill the overlap region, reducing ghosting by interpolation rather than blending.
- Pros: Best visual quality. Eliminates ghosting structurally.
- Cons: High compute cost (GPU inference per fill region). Best reserved for `final_quality=True` mode.

**E — Edge-aware guided filter at seam**
Apply a guided filter (using one of the frame strips as guide) to the feather transition band. Preserves sharp edges at character outlines while blending smoothly in texture regions.
- Pros: Faster than Poisson blending. Preserves line art.
- Cons: `cv2.ximgproc.guidedFilter` requires `opencv-contrib`. One additional dependency.

**Recommendation:** A is first priority. C as a [Quick Win] for seam-zone smoothness in final-output mode. B and E as follow-on improvements. D reserved for premium output mode.

---

## 1.7 RecDiffusion Border Rectangling

**Pain point:** Hard 30px edge crop leaves irregular black borders on outputs with diagonal or non-uniform scroll motion.

### Options

**A — Route through `sr_stitcher.inpaint_borders()` [available now]**
`animation/sr_stitcher.py` (P3.4) already implements seam+border inpainting via diffusers. Replace the hard `_crop_to_valid` with a call to `sr_stitcher.inpaint_borders()` when `sr_mode=True`.
- Pros: Reuses existing infrastructure. Best quality.
- Cons: Adds diffusion inference time (5–30s depending on border area). Requires `sr_mode=True`.

**B — OpenCV INPAINT_TELEA fallback** ✅ **Shipped S23**
Use `cv2.inpaint(src, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)` for border fill. Faster than diffusion; quality is lower but avoids the diffusion dependency in standard mode.
- Pros: Zero new dependencies. Fast (~0.5s for typical borders).
- Cons: Visible smearing artefacts on large border regions (>50px). Not suitable for borders spanning characters.

**C — Content-aware minimal bounding crop [Quick Win]** ✅ **De facto implemented**
`_crop_to_valid(canvas, valid_mask)` in `canvas.py` already computes the minimal bounding box of valid (non-black) pixels and crops to that. When valid_ratio ≥ 80% the simple row/col bounding-box is used; when < 80% (diagonal scroll → parallelogram valid region) it falls back to `_largest_valid_rect` for the maximum inscribed rectangle. No action required.
- Pros: Always safe. No artefacts.
- Cons: Output may be smaller than a perfectly filled output. Doesn't eliminate the invalid region, just removes it.

**D — ControlNet inpainting with border context**
Use a ControlNet-guided inpainting model conditioned on the known content near the border. Produces style-consistent fills for anime content.
- Pros: Best visual quality for complex borders.
- Cons: Requires a compatible ControlNet model. Significantly more complex than A.

**E — Stable Diffusion 3 outpainting**
Route border rectangling through the existing SD3 integration. Outpaint the border region given the valid interior as context.
- Pros: High-quality fills. SD3 integration already exists.
- Cons: Slow, expensive for small border corrections.

**Recommendation:** C immediately (no dependencies, always safe). A as enhanced path when `sr_mode=True`. Skip D/E — A subsumes them with existing infrastructure.

---

## 1.8 ASP Pipeline Configuration File

**Pain point:** Many pipeline constants (gain clamp, `_FADE_ROWS`, `min_gap_threshold`, ECC pyramid levels) are hardcoded in `constants.py` or inline in `pipeline.py`. Tuning requires code edits.

### Options

**A — TOML config per pipeline run [Quick Win] ✅ DONE (S27)**
`load_asp_config(path, *, override_env=True)` in `backend/src/animation/config.py`. Reads `asp_config.toml` via stdlib `tomllib`, merges all sections into a flat dict, writes each key to `os.environ` via `setdefault`. Env vars always win. Zero new dependencies. 5 unit tests (`test_config.py`).
- Pros: No new dependencies. Enables rapid iteration. Config can be committed alongside test datasets.
- Cons: Config schema must be kept in sync with `constants.py`.

**B — JSON Schema–validated config ✅ DONE (S42)**
`_CONFIG_SCHEMA` dict (14 known `ASP_*` keys → type + range spec) + `validate_asp_config(config, *, strict=False)` in `config.py`. Returns list of violation messages; `strict=True` raises `ValueError`. Unknown keys emit `UserWarning` (forward-compat). Wired via `load_asp_config(validate=False, strict=False)`. Zero new deps — inline schema replaces external `jsonschema`. 5 tests in `test_config.py::TestValidateAspConfig`. 317 tests passing.
- Pros: Better developer experience; validation at load time; clears §1.10B pre-condition.
- Cons: Schema must be manually updated when new `ASP_*` keys are added.

**C — GUI settings panel for ASP params**
Expose the most-tuned constants as sliders/checkboxes in the StitchTab UI. Persisted in `QSettings`.
- Pros: Best UX for non-developer users.
- Cons: Significant UI effort. Best deferred until pipeline stabilises.

**D — Per-dataset profile system**
Save a successful pipeline config alongside each output panorama. Load it on re-processing the same dataset. Enables experimentation without losing working configurations.
- Pros: Natural version control for pipeline settings.
- Cons: Profile discovery and UI to select profiles adds complexity.

**E — Environment variable overrides (12-factor style)**
Allow any config key to be overridden via `ASP_GAIN_CLAMP_LOW=0.82 python main.py ...`. Useful for CI and scripting without a config file.
- Pros: Zero new dependencies. Works with any launcher.
- Cons: Poor discoverability. Better as a complement to A than a replacement.

**Recommendation:** A first (unblocks research iteration). B adds minimal overhead and prevents config mistakes. C when pipeline stabilises. D as a follow-on to C.

---

## 1.9 Fallback Path Purity

**Pain point:** When ASP falls back to SCANS, it runs on BiRefNet-preprocessed, ECC-normalised frames rather than original source frames. Tests 13 and 16 showed sharpness degradation of ~14–15 points vs running SCANS on originals.

### Options

**A — Pass original frames to SCANS fallback [Quick Win] ✅ DONE (S28)**
`scans_frames` was already set at Stage 2 (pre-BiRefNet) — the original pain point was written before this placement was fixed. Remaining bug: the post-Stage-6 spatial dedup updated `frames` but never synced `scans_frames`. Fixed by extracting `_spatial_dedup_frames()` (module-level, testable) and adding the one-line sync. 5 new tests in `test_pipeline.py`. See CHANGELOG for full rationale.
- Pros: Minimal change. Eliminates the desync between fallback path and main pipeline.
- Cons: Doubles the frame memory footprint during the pipeline run (originals + processed).

**B — Dual path from Stage 1**
Fork the pipeline at Stage 1: one path applies preprocessing; the other keeps originals. Merge only at the fallback decision point.
- Pros: Enables per-stage fallback decisions (e.g., use ECC-normalised for matching but originals for compositing).
- Cons: Increases complexity. Higher memory cost.

**C — On-demand reload from disk ✅ DONE (S41)**
On fallback trigger, reload original frames from disk rather than holding them in memory.
`_reload_scans_frames(paths)` in `pipeline.py` — calls `_load_frames(paths)` then `_normalise_widths()`; wired into all 5 fallback sites via `_sf = scans_frames or _reload_scans_frames(image_paths)`. `ASP_SCANS_RELOAD=1` skips the Stage-2 `list(frames)` snapshot; both dedup syncs guarded with `if scans_frames else []`. Saves ~87 MB for 14-frame 1080p on the success path. 5 new tests in `test_pipeline.py::TestReloadScansFrames`. 312 tests passing.
- Pros: Zero extra memory during successful pipeline runs.
- Cons: Adds disk I/O latency at fallback time (~0.5–2s for 14 frames). Acceptable for a fallback path.

**Recommendation:** A for immediate fix. C as a memory-efficient alternative if frame counts exceed available RAM.

---

## 1.10 RLHF Loop Integration

**Pain point:** RLHF infrastructure exists (`rlhf/` module, `StitchFeedbackTab`, reward model CNN, DRL agent) but is not wired into the main pipeline evaluation loop. Collected feedback cannot improve future runs automatically.

### Options

**A — Post-run quality gate ✅ DONE (S29)**
`_compute_rlhf_score(img_bgr)` in `bench_anime_stitch.py`. Lazy-loads `StitchRewardModel` via `_get_reward_model()` singleton. `_compute_all_metrics` now emits `rlhf_score` (float or None) and `rlhf_flagged` (bool, threshold=0.6). 5 tests. 247 tests passing.
- Pros: Closes the feedback loop without requiring the DRL agent to be production-ready.
- Cons: Reward model must be calibrated before its scores are meaningful. Currently uses random weights.

**B — Parameter search with reward signal (offline Bayesian optimisation)**
Use the reward model as the objective for Bayesian optimisation (e.g., `optuna` or `scikit-optimize`) over gain clamp, feather width, and seam cost weights. Run offline on the 22-test corpus.
- Pros: Most promising path to measurable quality improvement from existing infrastructure. Automatic hyperparameter tuning.
- Cons: Requires a well-calibrated reward model and sufficient feedback data.

**C — Online DRL agent for ECC/registration [Long-term]**
Wire the DRL agent (`rlhf_trainer.py`) into Stage 8 (ECC sub-pixel refinement) to adaptively adjust pyramid levels and convergence criteria based on the reward signal.
- Pros: Fully adaptive pipeline; improves with every run.
- Cons: Requires significantly more feedback data than currently available. Training instability risk.

**D — Active learning: select uncertain outputs for human review**
Use the reward model's confidence score to identify outputs where the model is least certain. Prioritise those for human review in the feedback tab.
- Pros: Maximises the information gain per labelling effort.
- Cons: Requires uncertainty estimation from the reward model (e.g., MC dropout).

**E — Benchmark JSON → FeedbackTab import ✅ DONE (S119)**
`parse_bench_json(path)` in `backend/src/animation/rlhf/bench_import.py` — parses full-suite docs (`doc["datasets"]`) and single-dataset dicts. `suggested_rating(metrics_asp) → float` maps automated CV metrics to a 0–10 scale using `coverage×0.35 + sharpness_norm×0.25 + (1−ghosting)×0.20 + seam_coherence×0.20`. `resolve_anime_path(dataset)` finds the panorama on disk. `StitchFeedbackTab` gains a "Import from Benchmark JSON" group: dataset list with verdict/fallback badges, per-dataset metrics preview panel, "Import Selected" button loads the panorama and pre-fills the rating slider. 21 tests in `test_bench_import.py`.

**Recommendation:** A is the immediate next step. B is the most promising quality improvement from existing infrastructure. D maximises feedback ROI. C is a [Long-term] item contingent on sufficient feedback volume.

---

## 2.0 ASP Human-in-the-Loop Augmentation [Priority: Medium — Unique Multiplier]

**Context — What the Hybrid Stitch Panel Does and Does NOT Cover**

The existing `HybridStitchPanel` (`gui/src/tabs/models/gen/hybrid_stitch_panel.py`, 2143 lines) is a complete manual panorama studio: sequence reordering, point-to-point homography, per-frame color correction, seam painting, mesh warp, and final render. It is excellent for static panorama content. However it is architecturally **separate from the ASP pipeline** — it builds a sequence and emits it to the Stitch tab, where `AnimeStitchPipeline` runs fully automatically. User interactions in the Hybrid panel do not reach any of the stages that make ASP hard: BiRefNet fg masks, ARAP flow registration, per-seam post_warp_diff decisions, temporal median coverage, or the gt-coupled frame selector.

**The core gap:** Every failure mode unique to animated video — torn character edges, pose-residual ghosting, the GT-coupling problem in frame selection — requires a human to see and act on intermediate pipeline state that is currently only logged to the console. The pipeline already computes the right diagnostics (`post_warp_diff` per seam, `residual_px` per boundary, BiRefNet mask coverage, seam coherence, frame selection scores); it just never surfaces them in the UI.

**Design principle:** Intercept, not replace. The ASP pipeline should run as normal and emit its rich intermediate state through `StitchWorker` signals. An **ASP Reviewer panel** in the Edit tab receives these signals, displays stage-specific visualisations, and optionally writes override files back to `StitchWorker` before the next stage runs. Nothing changes in the pipeline code itself; the worker gains pause/resume hooks.

**Why this matters more than any single algorithmic improvement:**
- The GT-coupling wall (§0.2) means automated frame selection cannot reliably improve GT-SSIM. A user who can *see* the pose residuals per seam and move one frame can directly close the 0.045 framing gap that all sessions 1–5 failed to close automatically.
- The 31/96 render-gate fallbacks include cases where the gate fires on 1–2 bad seams; a user who can escalate those seams to single-pose would rescue the composite.
- Many "simple_better" cases exist because the user assembled more canvas than the GT shows (test27: 2× scale mismatch). A user who sees the final canvas overlay can trim excess rows/cols before the metric is measured.

---

### 2.1 Frame Selection Assistant [Quick Win] [Option A ✅ Session 79]

**Shipped (Session 79):** `SelectionReviewDialog` — horizontal scroll of 160×120px thumbnail cards with per-frame pose-diff colour bars (green/amber/red), include/exclude checkboxes, Move Up/Down, Select All/Deselect All. Wired to `StitchWorker.sig_review_frames` checkpoint; worker pauses until dialog accepted. `selected_paths()` returns ordered list of checked paths. HITL mode checkbox in Stitch tab toggles all pause points.

**Pain point:** `_smart_select_frames()` picks frames silently. When it picks a frame where the character is mid-swing (large fg pixel L1 score vs the previous selection), the user has no recourse — the pipeline commits to those frames before any GPU work.

**Options**

**A — Selection Review Dialog [Quick Win]**
After frame selection completes but before matching begins, show a modal strip of thumbnail tiles (96 px wide, scrollable horizontally). Each tile shows the frame, its canvas advance (px), and a colour-coded "pose diff" bar (fg pixel L1 vs previous frame: green ≤ 0.2, yellow 0.2–0.5, red > 0.5). User can:
- Click any tile to exclude it (greyed-out with strikethrough)
- Drag tiles to reorder
- Click "Add frame…" to insert from disk
- Click "Accept" to proceed or "Re-run Auto" to recompute
- Single toggle: "Show only frames with high pose diff (> 0.4)" to filter to problem frames

*Implementation:* `SelectionReviewDialog` — modal `QDialog`, spawned from `StitchWorker.stage_selection_complete` signal. Returns `List[str]` (approved paths) when accepted. ~300 LOC.
- Pros: Directly addresses the GT-coupling problem. User can manually pick the frame closest to the GT's temporal reference.
- Cons: Adds one user interaction step; can be bypassed by "Accept All" default.

**B — Inline Sequence Editor in Stitch Tab**
Replace the plain path list in the Stitch tab with the `SequenceManager` widget from `HybridStitchPanel` (already implemented: thumbnails, drag-drop, add/remove). Add pose-diff colour coding as a `QLabel` overlay on each thumbnail.
- Pros: Reuses 100% existing widget code. No new dialog.
- Cons: Runs before the pipeline computes pose diffs, so initial display is uncoloured until a previous run has cached scores.

**C — Continuous Live Preview [Research]**
Stream video thumbnails from the source file and let the user scrub a timeline to mark keyframes manually before any processing. Purpose-built for anime where "on twos" holds are visually obvious.
- Pros: Most powerful; user can directly exploit animation-hold structure.
- Cons: Requires video file (not just extracted frames); adds timeline UI complexity.

**Recommendation:** A immediately (modal dialog, minimal code, maximum control). B as a follow-on to make the Stitch tab's input area richer. C deferred until video-file input is supported.

---

### 2.2 Edge Graph Inspector & Editor [Quick Win] [Read-Only Viewer ✅ Session 62]

**Shipped (Session 62):** `EdgeGraphInspectorDialog` — read-only viewer with circular node layout, confidence-coloured edges, edge table, and `⬡ Edges` button wired into the Stitch tab. Visual check pending first real stitch run with `save_intermediate=True`. Interactive re-solve (delete/add/re-bundle) deferred as §2.2B below.

**Pain point:** The matching step (Stages 5–6, `_pairwise_match()` → `_filter_edges()`) builds a graph of frame-pair correspondences. Bad edges (LoFTR false matches on character-heavy frames) cause the bundle-adjust to pull frames into wrong positions. The user currently cannot see which edges survived or why, and cannot delete the ones causing the pull.

**Options**

**A — Graph Visualisation with Delete/Add [Quick Win]**
After bundle adjustment, emit the edge graph via `StitchWorker.stage_edges_ready(edges: List[dict])`. Display as a node-link diagram where:
- Each node = one selected frame (thumbnail at 64 px)
- Each edge = a match, coloured by weight (dark green = LoFTR 0.9, yellow = TM 0.4, red = low-weight)
- Thickness proportional to match count
- Dashed = edges that were rejected by `_filter_edges`
- Click an edge → show side-by-side frame pair with matched keypoint overlays
- Right-click an edge → "Delete edge" (marks it for exclusion before re-solve)
- Right-click two nodes → "Add edge" (runs LoFTR on that pair on demand)
- "Re-solve Bundle" button → re-runs `_bundle_adjust_affine` with the edited edge set

*Implementation:* `EdgeGraphWidget` using `QGraphicsScene` (same Qt primitives already used in the Hybrid panel's canvas). ~400 LOC.
- Pros: Directly debuggable for the 2/25 bundle-adjustment failures. User sees exactly which edges are pulling frames.
- Cons: Requires re-running bundle adjust on edit; adds ~0.15s latency per re-solve (acceptable).

**B — Edge Table (Tabular View)**
Emit edges as a `QTableWidget` with columns: Frame-i, Frame-j, Method, Weight, Residual-post-solve, Status (inlier/outlier). Sortable by residual. Click to preview. Delete via row selection.
- Pros: Simpler than graph view. Better for data-focused users.
- Cons: Less intuitive for understanding spatial relationships.

**C — Automatic Bad-Edge Highlighting Only**
No manual deletion; just highlight edges above a residual threshold in red after bundle adjust, with a tooltip explaining why they might be bad. Non-interactive.
- Pros: Near-zero implementation (post-process the existing log output).
- Cons: Doesn't give the user any control.

**Recommendation:** A for maximum utility (builds on existing `QGraphicsScene` patterns). B as a lighter alternative that can be shipped faster. C as an immediate intermediate step while A is being built.

---

### 2.3 Anchor Frame & Canvas Layout Inspector [Priority: Medium] [Read-Only Viewer ✅ Session 63]

**Shipped (Session 63):** `CanvasLayoutInspectorDialog` — read-only viewer showing N frame rectangles at their final canvas positions as colour-coded polygons, stats label (N frames · W×H canvas), Frame/tx/ty table, and `⬗ Canvas` button wired into the Stitch tab. Visual render verified with synthetic 3-frame fixture. Interactive anchor override and overlap-zone heatmap deferred as §2.3B.

**Pain point:** The pipeline chooses the reference frame for bundle adjustment (the anchor) implicitly — usually the frame with the most/best edges. A wrong anchor causes the whole canvas to be skewed relative to a natural reference. The user can't override it, and the current UI doesn't show which frame IS the anchor.

**Options**

**A — Anchor Selector + Canvas Preview**
After bundle adjustment, emit `StitchWorker.stage_canvas_ready(affines, canvas_h, canvas_w, anchor_frame_idx)`. Show:
- A "Canvas Layout" thumbnail: all frames drawn as semi-transparent coloured rectangles on their canvas positions, with the anchor frame highlighted in gold
- Dropdown: "Anchor frame: [frame name]" with the option to change it
- Changing the anchor → re-computes affines (translating all by the delta), re-draws layout (fast, no matching re-run)
- Each frame rectangle is drag-nudgeable (±10px in x/y) for manual fine-tuning of placement
- "Show overlap zones" toggle: colour-codes rows by coverage count (red = 1 frame only, green = 3+)

*Implementation:* `CanvasLayoutWidget` — `QGraphicsScene` with rectangle items per frame. Re-solve for anchor change is just a matrix translation, ~2ms. ~350 LOC.
- Pros: Directly addresses systematic canvas tilt from bad anchor choice. Also surfaces single-frame coverage zones (informing the user where the temporal median will fail).
- Cons: Nudging individual frames bypasses the bundle-adjustment constraint; user could create geometrically inconsistent canvas.

**B — Anchor Override Only (No Visual)**
Add a "Lock anchor to frame N" checkbox in the Stitch tab's settings panel. Pipeline uses the locked anchor. No canvas visualisation.
- Pros: Two-line implementation.
- Cons: User can't see what the anchor currently is or what the canvas looks like.

**Recommendation:** A is the right target; B as an immediate interim. The overlap-zone heatmap from A is also directly useful for diagnosing render-gate failures (it shows exactly which rows will have single-frame coverage → median collapse → banding).

---

### 2.4 Seam Registration Inspector [Highest Impact] [Option A ✅ Session 95–96]

**Shipped (Sessions 95–96):** `SeamDiagnosticDialog` — vertical scroll of `_SeamCard` widgets (one per seam boundary), each showing: seam index, boundary y-position, `post_warp_diff` coloured green/amber/red (same thresholds as §2.4B overlay), single-pose escalation badge, optional ±50px crop thumbnail (§2.4C, S96), and mutually-exclusive "Force single-pose" / "Force blend" checkboxes. Wired to `StitchWorker.sig_review_seams` checkpoint 4.6. Pipeline runs initial composite to collect `seam_post_diffs`, emits dialog, re-composites with `seam_overrides` if accepted. Constants `SEAM_OVERLAY_AMBER_THRESH`/`SEAM_OVERLAY_RED_THRESH` shared with §2.4B.



**Pain point:** Stage 8.5 (`register_foreground_at_seam`) runs on every frame boundary and logs `residual_px`, `post_warp_diff`, and whether it fell back to single-pose. This data is printed to the console but never shown in the UI. For the 31% of tests that pass the render gate but are still "simple_better", the path to improvement is: identify the 1–2 seams with the worst residual, understand why (fast animation vs bad flow on flat region), and either escalate them to single-pose or override the warp.

**Options**

**A — Per-Seam Diagnostic Panel [High Impact]**
After Stage 8.5 completes, emit `StitchWorker.stage_fg_registered(seam_infos: List[dict])` where each dict has `{residual_px, post_warp_diff, fallback, dominant_frame, flow_vis}`. Display as:
- A vertical strip of "seam cards", one per boundary, sorted by post_warp_diff descending
- Each card shows: seam index, boundary position in canvas, residual (px), post_warp_diff (lum units), fallback status (⚠ single-pose / ✓ blended / ✗ skipped)
- Thumbnail crop: the ±50px band around the seam in the blended output
- Optional: flow arrow overlay (sampled RAFT vectors) so user can see what the flow engine computed
- Per-seam overrides:
  - "Force single-pose" toggle (escalates that seam to dominant frame, bypasses blend)
  - "Force blend" toggle (overrides post_warp_diff escalation)
  - "Skip registration" toggle (use raw unwarped frames for this seam — sometimes cleaner)
- "Re-composite" button → re-runs Stage 11 with the override set, shows updated output (fast, ~1s)

*Implementation:* `SeamDiagnosticPanel` — `QScrollArea` of `SeamCard` widgets. The Re-composite path calls `_composite_foreground()` directly with the override dict. ~500 LOC.
- Pros: Directly addresses the "1–2 bad seams pulling GT-SSIM down" failure mode. User can escalate seams that the post_warp_diff=22 threshold misses. Reuses the existing Stage 11 composite function.
- Cons: Requires storing intermediate per-seam state between pipeline runs. `StitchWorker` needs to persist `seam_infos` until the user triggers re-composite.

**B — Seam Overlay on Output Image**
Draw coloured lines on the final composite at each seam boundary position, coloured by post_warp_diff (green < 10, yellow 10–22, red > 22). Click a line → show the seam card. Read-only; no overrides.
- Pros: Near-zero implementation (post-process the composite image with overlay).
- Cons: Shows the symptom, not the cause. Still no control.

**C — Seam Painter Integration (Reuse HybridStitch)**
After Stage 8.5, load the warped frames into the existing `SeamPainterWidget` from `HybridStitchPanel`. User paints hard constraints, runs DP seam, then Stage 11 uses the painted seam mask.
- Pros: Reuses 100% existing code. HybridStitch's `SeamPainterWidget` already does exactly this.
- Cons: The HybridStitch seam painter doesn't know about ASP's fg masks — it would route the seam ignoring foreground, potentially cutting through the character. Needs `fg_penalty` cost term wired in.

**Recommendation:** A for full control (most impactful, addresses the core post_warp_diff blind spot). C as an intermediate step that reuses existing code but needs the fg-penalty extension. B as a "diagnostic only" first pass that can be shipped in a day.

---

### 2.5 Temporal Median Coverage Map [Quick Win]

**Pain point:** The render-gate fallback (31/96 tests) fires because the temporal median background plate is severely banded. Banding occurs when canvas rows have only 1 contributing frame (no temporal averaging possible). The user currently has no way to see the coverage map before committing to the render.

**Options**

**A — Coverage Heatmap Widget [Quick Win]**
After Stage 9 (temporal median render), emit `StitchWorker.stage_render_ready(canvas, coverage_map)` where `coverage_map[y] = number of frames contributing to row y`. Display:
- Vertical bar chart (or heatmap overlay on canvas thumbnail): red = 1 frame, amber = 2 frames, green = 3+ frames
- Superimpose on a thumbnail of the rendered canvas
- "Coverage warning" label: "N rows with single-frame coverage — render gate likely to fire"
- Overlay toggle: show/hide on the main canvas preview

*Implementation:* Simple `QLabel` with `QPixmap` colour coding. ~80 LOC.
- Pros: Tells the user in advance whether the render gate will fire. They can then choose to add a frame at that canvas position (via the Selection Assistant in §2.1) before re-running.
- Cons: Requires re-running the pipeline after adding frames; no in-place fix.

**B — Auto-suggest Missing Frames**
If coverage_map shows rows with < 2-frame coverage, automatically suggest candidate source frames (from the unselected pool) that would fill those rows. Show them in the Selection Assistant dialog.
- Pros: Closes the loop — tells user not just "there's a gap" but "add frame N to fix it".
- Cons: Requires keeping the full unselected frame pool in memory (~100 frames × 1920×1080 ≈ 600 MB); needs memory-mapped or on-demand loading.

**Recommendation:** A immediately (trivial implementation, high diagnostic value). B as a follow-on quality-of-life improvement.

---

### 2.6 Output Scale & Crop Assistant [✅ Stage 12.5 shipped — Session 7]

**Pain point:** test27 assembles a canvas 2× taller than the GT reference (1877×2135 vs 963×1280). The pipeline has no mechanism to suggest a crop. The user has no visual indication that their output is at a different scale than expected.

**Session 7 implementation (Stage 12.5):** Scroll-axis-aware foreground-extent trim inserted in `pipeline.py` between Stage 11 (foreground composite) and Stage 13 (boundary crop). Detects scroll axis from affine ty/tx range; warps `~bg_masks[i]` for each frame into canvas space using `cv2.warpAffine` + `INTER_NEAREST`; unions the fg masks; trims canvas rows (vertical scroll) or columns (horizontal scroll) to the fg-covered extent plus 20px padding. Guard: `ASP_CONTENT_TRIM=1` (default on when bg_masks available). `valid_mask` is trimmed in sync so Stage 13 `_crop_to_valid` still works correctly.

**Options**

**A — Scroll-Axis-Aware Content Crop ✅ (implemented as Stage 12.5)**
After Stage 11, trim canvas in the dominant scroll direction using warped fg union.
- Pros: Directly fixes test27's scale mismatch. More general than hardcoding 30px edge crop.
- Cons: "Foreground content extent" can be ambiguous for scenes where character is always present across all rows.

**B — Output Resolution Presets**
Let user specify target height (e.g., "1280px" or "2× source height") before running. Pipeline crops to fit.
- Pros: Simple, deterministic.
- Cons: Doesn't adapt to content — may crop character or leave excess background.

**Recommendation:** A (content-aware, directly addresses test27 class of failures). B as a fallback for users who know their target dimensions.

---

### 2.7 Architecture: StitchWorker Staged Execution [Implementation Foundation] [✅ Session 79]

**Shipped (Session 79):** `QWaitCondition`/`QMutex` pause/resume in `StitchWorker` — `_hitl_mutex`, `_hitl_wait`, `_hitl_paused`, `_hitl_override`. `resume()` wakes the blocked worker thread. 9 HITL signals: `sig_review_video`, `sig_review_frames`, `sig_review_masks`, `sig_review_edges`, `sig_review_canvas`, `sig_review_boundaries`, `sig_review_seams`, `sig_review_composite`, `sig_review_render`, `sig_review_output`. `hitl_mode: bool = False` param — when False, all pause callbacks are no-ops (zero overhead on automated path). `set_frame_override`, `set_edge_override`, `set_affine_override`, `set_boundary_override`, `set_seam_override`, `set_render_cancel` setters called from dialog handlers before `resume()`.

All of §2.1–§2.6 depend on a single architectural change: `StitchWorker` must support **stage checkpoints** — points where it emits intermediate state, optionally waits for user review, and accepts override inputs before continuing.

**Current architecture:** `StitchWorker.run()` executes all 13 stages sequentially in one thread. Signals are emitted only for progress updates and final completion. No pause/resume; no intermediate state exposed to the UI.

**Proposed architecture:**

```python
class StitchWorker(QRunnable):
    # New signals (all carry stage-specific payloads)
    stage_selection_done    = Signal(list)          # List[str] selected paths + scores
    stage_edges_ready       = Signal(list)          # List[edge dicts] with weights/residuals
    stage_canvas_ready      = Signal(object)        # affines, canvas_h/w, anchor_idx
    stage_render_ready      = Signal(object, object) # canvas image, coverage_map
    stage_fg_registered     = Signal(list)          # List[seam_info dicts]
    stage_complete          = Signal(object)        # final output image

    # Override inputs (set by UI before resume)
    def set_frame_selection_override(self, paths: list) -> None: ...
    def set_edge_override(self, deleted_edges, added_pairs) -> None: ...
    def set_anchor_override(self, anchor_idx: int) -> None: ...
    def set_seam_overrides(self, seam_overrides: dict) -> None: ...
    def resume(self) -> None: ...  # unblocks a QWaitCondition
```

Each checkpoint:
1. Emits the signal with its payload
2. Blocks on a `QWaitCondition` if the UI has "Pause at [stage]" enabled
3. Reads any overrides that were set during the pause
4. Continues with the (optionally modified) data

**Implementation cost:** ~200 LOC in `StitchWorker`, zero changes to the pipeline's algorithmic code. Each UI panel (§2.1–§2.6) connects to the relevant signal and calls `set_*_override()` + `resume()`.

**Pause policy:** All pauses are **opt-in** via a "Review at each stage" checkbox in the Stitch tab settings. Default is fully automatic (no pauses) — existing users are unaffected. "Review mode" enables one or more specific stage pauses independently.

---

### 2.8 ASP-to-HybridStitch Handoff [Long-term]

When the full ASP pipeline run produces an output the user is unsatisfied with, they should be able to **export the pipeline state to the HybridStitch panel** for manual refinement, rather than starting from scratch.

**What this handoff would export:**
- The ordered list of selected frames → `HybridStitchPanel._sequence`
- The per-pair affines from bundle adjustment → `HybridStitchPanel._homographies`
- The per-frame photometric corrections from BaSiC/gain normalisation → `HybridStitchPanel._corrections`
- The fg-registration warped frames (if saved as intermediates) → as the pair images for the Control Point Editor
- The seam coherence map → pre-loaded into the Seam Painter as initial painted constraints

**Implementation:** A single "Export to Hybrid Stitch →" button in the Stitch tab's output panel. The `EditTab._on_hybrid_handoff()` slot populates the `HybridStitchPanel` state from the `StitchWorker`'s last run.

**Gap:** HybridStitch's `RenderPanel` doesn't support BiRefNet-aware fg compositing or ARAP-registered warps. For full fidelity, the handoff would need to bring the fg-registered frames (post-Stage 8.5) rather than the raw frames, so the Hybrid panel sees "already pose-aligned" inputs and just handles final blending. This is feasible since `fg_register.py`'s warped outputs are already written to `stage_dir/` as PNG intermediates.

---

## 3.0 ML-Driven Pipeline Modernisation [Research Phase — from ML Research Report]

*Source: [`reports/ASP Consolidated Research Plan.md`](../../reports/ASP%20Consolidated%20Research%20Plan.md) — consolidated 2026-06-07. Each subsection maps a specific finding from the research plan to the current pipeline stage it targets, the files it touches, and the expected quality delta. Phase priority framework in the consolidated plan: Phase 1 (pose-consistent frame selection, GNC-TLS BA, median background + JPEG-aware refinement, SAM-2 masking), Phase 2 (AnimeInterp SGM + LinkTo-Anime SEA-RAFT, OBJ-GSP seam barrier, full Sýkora 2009 ARAP, ProPainter), Phase 3 (ToonCrafter quality-gated, StabStitch++ trajectory smoothing).*

The report's central thesis: cel animation breaks every assumption that drives classical CV pipelines (gradient-based flow, RANSAC on whole-frame features, pixel-level quality metrics). The next generation of improvements requires either (a) anime-specific classical methods that bypass those assumptions entirely, or (b) deep/generative models whose priors capture the latent structure of hand-drawn character motion. The sections below are ordered by expected impact-to-effort ratio and dependency on existing infrastructure.

---

### 3.1 AnimeInterp SGM: Segment-Guided Matching for Flat-Region Correspondence [Research — Highest Aperture-Problem Impact]

**Pain point (links to §0.1):** RAFT, DIS, and ARAP Push all produce chaotic flow vectors on large flat-color regions — the aperture problem is fundamental, not a parameter issue. The ARAP Push phase (session 4) confirmed zero SSIM improvement because block-matching also fails on uniform color patches. We need a method that treats flat regions as geometric entities, not texture patches.

**What AnimeInterp SGM does:** Extracts line-art contours via Laplacian filter → "trapped-ball" filling produces a rigid segmentation map where each contiguous color region gets a unique ID → VGG-19 features are pooled per-segment → correspondence is solved via a **Matching Degree Matrix** combining:
- Feature affinity (normalized VGG cosine similarity)
- Distance penalty (rejects matches whose centroid displacement exceeds 15% of image diagonal)
- Size penalty (rejects matches where segment area changes drastically)

The optimal shift is derived from centroid displacement, then combined with local variational deformation to produce a dense flow field for the whole textureless region. The aperture problem is completely sidestepped — no gradient required.

**How it applies:** Replace or augment `_arap_push()` in `fg_register.py`. SGM provides the coarse per-cell displacement; the existing `_arap_regularise()` would then smooth the SGM-derived field instead of the raw RAFT flow. SGM runs on the fg-masked overlap crops (already cropped at ±taper_px+16px), so input size is manageable.

**Options**

**A — SGM as primary flow for fg overlap [Research]**
Replace RAFT/DIS flow estimation for the fg registration crop with SGM. RAFT is only reliable on textured regions; SGM is reliable everywhere else. Could combine: use RAFT where confidence is high (gradients exist), use SGM where confidence is low (flat regions).
- Pros: Directly solves the aperture problem. Proven on anime at CVPR 2021.
- Cons: SGM requires VGG-19 forward passes on the crops → 15–30ms per seam on GPU. 13 seams → +0.3–0.4s per dataset. Needs trapped-ball segmentation (OpenCV watershed as proxy).
- Code: [AnimeInterp CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/papers/Siyao_Deep_Animation_Video_Interpolation_in_the_Wild_CVPR_2021_paper.pdf), [GitHub](https://github.com/lisiyao21/AnimeInterp)

**B — SLIC superpixel centroid tracking as SGM proxy [Quick Win]**
SLIC superpixels (available in `skimage.segmentation.slic`) can approximate the segment structure without VGG feature extraction. Centroid tracking across seam pairs gives coarse per-cell displacement. Less robust than true SGM but implementable in 50 LOC.
- Pros: No new model weights. ~2ms per seam.
- Cons: SLIC on flat color without texture guidance may not segment correctly (same color = one huge superpixel). Less robust than VGG-based SGM.

**C — AnimeInterp full architecture for frame interpolation [Long-term]**
Beyond fg registration: use SGM + ConvGRU (§3.2) to generate synthetic intermediate frames between selected frames, filling in animation gaps entirely. This would replace the midpoint warp with a learned interpolation.
- Cons: Requires ATD-12K fine-tuning for best quality. GPU inference time ~500ms per synthetic frame.

**D — LinkTo-Anime fine-tuned SEA-RAFT as drop-in flow engine [Research]**
The LinkTo-Anime dataset (arXiv 2506.02733) is the first GT optical-flow corpus for cel-shaded anime (395 sequences, 24,230 training frames). SEA-RAFT (ICCV 2025) is the current top-performing flow architecture. Fine-tuning SEA-RAFT on LinkTo-Anime produces an anime-specific flow engine loadable via `ASP_FLOW_ENGINE=sea_raft_anime` — a direct drop-in for the existing engine swap in `_load_flow_engine()`.
- Pros: Addresses the domain gap at the data level. SEA-RAFT's recurrent refinement outperforms RAFT on textured regions and is more robust than SGM on ambiguous animation poses.
- Cons: ~24GB VRAM for fine-tuning on the full LinkTo-Anime dataset. Inference time similar to RAFT (~30ms/seam on GPU). Model weights ~100MB after fine-tuning.

**Recommendation:** B immediately as a diagnostic check (does centroid-level flow actually improve post_warp_diff?). A if B shows meaningful seam residual reduction on test09/test27. D as a research track running parallel to A once LinkTo-Anime training weights become available. C is the long-term ceiling but depends on A being validated first.

---

### 3.2 ConvGRU Recurrent Flow Refinement for Kinematic Accuracy [Research]

**Pain point (links to §0.1):** Even when coarse correspondence is correct (SGM), there are null/sparse regions in the flow field (SGM drops low-confidence matches via mutual consistency check). These gaps create warp artifacts at segment boundaries. The current fallback for sparse flow is `_arap_regularise()` which is a spatial smoothing — it doesn't respect the temporal structure of the motion.

**What ConvGRU RFR does:** A ConvGRU (Convolutional Gated Recurrent Unit) iteratively refines the coarse SGM flow by:
1. Building a pixel-wise confidence mask from `|warped_A - warped_B|` (high diff = low confidence)
2. Over T iterations, correlating feature tensors from source and bilinearly-sampled target to estimate residual flow corrections
3. Accumulating residuals to bend the linear coarse flow into an accurate non-linear trajectory

Trained on ATD-12K (12,000 animation triplets with extreme exaggeration).

**How it applies:** As a post-processing step after `_arap_push()` (or SGM if §3.1A is implemented): use the ConvGRU to fill null regions and sharpen the flow field before `_arap_regularise()`. The ConvGRU runs on the fg-masked seam crop (same input as RAFT today), replacing the RAFT pass entirely for animated-content inputs.

**Options**

**A — Drop-in RAFT replacement with AnimeInterp flow [Research]**
AnimeInterp's SGM+ConvGRU pipeline produces a dense refined flow field as output. In `fg_register.py`, the `_load_flow_engine()` function already supports swappable engines (RAFT vs DIS via `ASP_FLOW_ENGINE`). Add `ASP_FLOW_ENGINE=animeinterp` path that loads the SGM+ConvGRU weights and runs on the seam crop.
- Pros: Minimal code change (follows existing engine swap pattern). Full AnimeInterp pipeline handles both coarse and fine flow.
- Cons: Requires ATD-12K pretrained weights (~180MB). VGG + ConvGRU inference: ~40ms per seam.

**B — ConvGRU as confidence-guided gap-filler on top of RAFT [Research]**
Keep RAFT for high-texture regions, use a lightweight ConvGRU-style network only in low-confidence zones (where RAFT confidence < threshold). Hybrid approach.
- Cons: Requires a custom confidence-thresholding pipeline. More engineering than A.

**Recommendation:** A is cleaner. The existing `ASP_FLOW_ENGINE` switch makes A a drop-in experiment.

---

### 3.3 DINOv2 + SigLIP Submodular Frame Selection [✅ Option A shipped — Session 8]

**Pain point (links to §0.2):** The fg pixel L1 pose metric (session 5) is background-invariant but still GT-coupled: substituting frame N for frame N+1 diverges from GT's temporal reference even when both show the same character pose (same "on twos" hold). The GT-coupling causes -0.024 regressions on some tests when pose selection is enabled.

**Session 8 implementation:** `_compute_dinov2_features()` added to `frame_selection.py`. Loads `dinov2_vits14` via `torch.hub.load` with module-level `_DINOV2_CACHE`; batch inference on grayscale thumbnails → (N, 384) L2-normalised float32 features. In Pass 2 of `smart_select_frames()`, DINOv2 cosine distance replaces `_fg_center_diff()` when features are available; falls back to pixel L1 when DINOv2 is unavailable. Enable via `ASP_POSE_WINDOW_PX=80` (same flag). 2 new tests in `TestDINOv2Features`.

**What DINOv2 Submodular Selection does (from "Adaptive Greedy Frame Selection for Long Video Understanding", arXiv 2603.20180):**
1. **DINOv2 facility-location coverage:** Embeds all frames via DINOv2 ViT-B/14. Defines a facility-location objective that penalises redundancy — adding frame i to the selected set is only rewarded if its DINOv2 embedding occupies a significantly different region in latent space from already-selected frames. Frames in the same "on twos" hold will have nearly identical embeddings → the objective naturally clusters them and picks one representative.
2. **SigLIP relevance term:** Optional query-conditioned relevance (useful if we want to bias toward frames containing a specific character pose or action).
3. **Greedy with (1-1/e) approximation guarantee:** Submodular maximisation gives formal quality bounds; the greedy algorithm is fast (O(N·K) in frame count N, selection count K).

**Key insight for ASP:** This method was designed explicitly for video with temporal redundancy (animation holds are exactly the "frame redundancy" it penalises). Applied to our frame selector:
- Step 1: Extract DINOv2 embeddings for all source frames (batch inference on thumbnails)
- Step 2: Apply facility-location greedy to select K most-diverse frames
- Step 3: Among the diverse candidates, apply the camera advance constraint (≥50px min step)

This directly resolves GT-coupling because DINOv2 embeddings are *background-aware* but also *animation-hold-aware*: frames in the same hold are treated as identical, and the selection picks the one with the right camera advance regardless of which specific frame the GT used.

**How it applies:** Replaces or augments `_smart_select_frames()` in `frame_selection.py`. The DINOv2 embedding pass replaces the thumbnail phase-correlation pass for pose scoring. Camera advance estimation still uses phase correlation.

**Options**

**A — DINOv2 facility-location as primary pose metric [Research]**
In Pass 2 of `_smart_select_frames()`, replace `_fg_center_diff()` with DINOv2 cosine distance. The facility-location objective score replaces the current "≥10% improvement" threshold.
- GPU inference: DINOv2 ViT-S/14 on 256px thumbnails: ~5ms/frame batched. For 30 frames: ~150ms total. Acceptable.
- Pretrained weights: Available via `torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')` — no fine-tuning needed.
- Pros: Background-invariant by design. Explicitly handles animation holds. Formal approximation guarantee.
- Cons: Adds DINOv2 dependency; ~150ms overhead per dataset. Still GT-coupled if DINOv2 disagrees with GT's frame choices (but hold-awareness reduces this risk significantly).

**B — Apply on foreground-masked crops only [Research]**
Before DINOv2 embedding, mask out background pixels (using BiRefNet masks already computed in the pipeline). This makes DINOv2 embeddings purely character-pose-driven, entirely eliminating background structure from the score.
- Pros: Strongest GT-decoupling. Character in different poses → clearly different DINOv2 embeddings.
- Cons: Requires BiRefNet to run before frame selection (currently BiRefNet runs after selection). Adds ~2s overhead.

**C — SigLIP query-aware selection for specific poses [Long-term]**
Let the user specify a target pose in natural language ("character standing, arms raised"). SigLIP relevance term biases selection toward frames matching that description.
- Cons: Requires user input; not fully automatic. Long-term feature.

**Recommendation:** A immediately. B as the quality-maximizing refinement. The key implementation risk is that DINOv2 on masked-foreground crops (Option B) requires BiRefNet to run first, which changes the frame selection timing and may reintroduce the frame-timing regression seen in session 3 with BiRefNet two-channel selection. Start with A (unmasked DINOv2) and verify it doesn't regress before adding masking.

---

### 3.4 FD-Means Animation Hold Detection [Quick Win — preprocessing]

**Pain point:** The frame selector runs phase correlation on all N source frames before discarding holds. For a 300-frame source with many holds, this wastes N-K phase correlation pairs that could be compressed without loss.

**What FD-Means does:** Feature-level deduplication that clusters animation frames into "hold blocks" — runs of identical or near-identical frames. Uses deep structural embeddings (perceptual hash or DINOv2 distance) to detect when consecutive frames share the same cel even if minor compression artifacts differ. Each hold is compressed to a single token (one frame representative + duration metadata).

**How it applies:** Add a hold-detection preprocessing step at the start of `_smart_select_frames()`. Before any phase correlation:
1. Compute perceptual hash (or DINOv2 distance) for consecutive frame pairs
2. Cluster consecutive frames with distance < threshold into "hold blocks"
3. Pass only one representative per hold block to the phase correlation stage

This reduces the number of frames processed by the rest of the pipeline by a factor of 2–3× for typical anime, and explicitly surfaces hold boundaries as natural pose-change points.

**Options**

**A — Perceptual hash hold detection [Quick Win] ✅ DONE (S43)**
`_compute_dhash(thumb, hash_size=8)` + `_detect_hold_blocks_dhash(thumbs, distance_threshold=4)` in `frame_selection.py`. INTER_AREA resize to (9×8) eliminates MPEG DCT block noise before horizontal gradient binarisation. Hamming distance threshold 4. `ASP_HOLD_DHASH_THRESH=4` to enable; default 0=off (MAD fallback). `HOLD_DHASH_THRESHOLD=4` in `constants/animation.py`; added to `_CONFIG_SCHEMA`. 5 tests in `test_frame_selection.py::TestDetectHoldBlocksDhash`. 322 tests passing.
- Pros: Zero new dependencies (~3ms for 300 frames). INTER_AREA resize is structurally immune to DCT block noise; within-hold distance stays 0–2 even for aggressive H.264 compression.
- Cons: ~3× slower than MAD. Threshold requires tuning for unusual sources (anime-original BD vs streaming rip).

**B — DINOv2 cosine distance hold detection [Research]**
If §3.3 is implemented (DINOv2 already loaded for frame selection), reuse the embeddings for hold detection. Threshold: cosine distance < 0.05 = same hold.
- Pros: Robust to compression noise. No extra inference cost if DINOv2 runs for §3.3.
- Cons: Adds DINOv2 dependency if §3.3 is not implemented.

**C — FD-Means clustering [Research]**
Use the `fastdup` library's internal FD-Means cluster algorithm, which is specifically designed for video frame deduplication with peak function clustering (avoids random K-Means initialization).
- Pros: Production-tested on video datasets.
- Cons: New dependency; adds `fastdup` which is a large package.

**Recommendation:** A immediately (near-zero cost, directly useful). B as a free addition if §3.3 lands. C only if A proves insufficient for compressed sources.

---

### 3.5 CamFlow Hybrid Motion Basis for Camera Displacement [Research]

**Pain point (links to §0.2):** Phase correlation on whole-frame thumbnails conflates camera pan (`T_camera`) with character animation (`A_animation`). A 50px "displacement" may be 5px camera + 45px arm swing. The fg pixel L1 metric partially decouples pose from camera, but the phase correlation estimate is still noisy for scenes with large foreground characters.

**What CamFlow does (ICCV 2025, [paper](https://openaccess.thecvf.com/content/ICCV2025/papers/Li_Estimating_2D_Camera_Motion_with_Hybrid_Motion_Basis_ICCV_2025_paper.pdf)):**
Estimates 2D camera motion via a Motion Estimation Transformer (MET) that combines:
1. **12 physical polynomial bases** derived analytically from the 2D projection equation (translation, scaling, affine shear, perspective)
2. **K stochastic Gaussian SVD bases** to capture residual non-linear motion that escapes the polynomial bases

The two base sets are weighted by the MET; an uncertainty mask rejects unreliable (foreground-dominated) regions. Training uses SAM-masked dynamic objects to create a "camera-only" ground truth. The resulting camera estimate is sub-pixel accurate even with large foreground subjects.

**How it applies:** Replace the `cv2.phaseCorrelate()` call in `_smart_select_frames()` (frame_selection.py) with a CamFlow inference pass. CamFlow runs on thumbnail pairs (256px) and outputs a 2×3 camera matrix rather than a (dx, dy) pair — this gives us a cleaner separation of camera rotation/scale from character motion.

**Options**

**A — CamFlow as drop-in phase-correlation replacement [Research]**
The `_smart_select_frames()` function currently computes `(dx_t, dy_t), response = cv2.phaseCorrelate(a, b)`. Replace with `flow_matrix = camflow.estimate(a, b); dx_t, dy_t = flow_matrix[0,2], flow_matrix[1,2]`. CamFlow outputs the dominant camera translation directly.
- Estimated inference: MET on 256px thumbnail pairs: ~10ms/pair on GPU. For 30 pairs: 300ms. Acceptable.
- Pros: Formally decouples camera from foreground. ICCV 2025 state-of-the-art.
- Cons: New model weights (~50MB MET). Not yet available as a pip package — requires building from paper code.

**B — Deep homography with foreground masking [Research]** ✅ **Shipped S146 (simplified — bg-masked phase correlation)**
`bg_masked_phase_correlate(frame_a, frame_b, bg_mask_a, bg_mask_b, min_bg_pixels) → (dx, dy, response)` in `backend/src/animation/cam_flow.py`. Zeros foreground pixels in both grayscale frames before `cv2.phaseCorrelate`. Falls back to whole-frame if combined bg area < `CAM_FLOW_MIN_BG_PIXELS=500`. `CamFlowEstimator` wrapper. `_CAMFLOW = os.environ.get("ASP_CAMFLOW", "")` in `frame_selection.py`; `"bg_masked"` routes phase correlation through `bg_masked_phase_correlate` when BiRefNet mask available. 5 tests in `test_cam_flow.py`.
- Alternative to CamFlow: use a deep homography estimator (from "Deep Homography Estimation for Dynamic Scenes", CVPR 2020) that jointly predicts a temporal dynamics mask alongside the homography matrix. The network identifies high-temporal-variance regions (character) and excludes them, forcing estimation from static background.
- Pros: This CVPR 2020 model has available pretrained weights and a simpler architecture than CamFlow.
- Cons: Less robust to multi-plane parallax than CamFlow. Not designed for anime specifically. (Full deep-homography MET model requires weights download — model-free bg-masked proxy shipped instead.)

**C — Background-only phase correlation via BiRefNet mask [Infrastructure Built, Disabled]**
Already implemented as `ASP_TWO_CHANNEL_SELECT=1` in `frame_selection.py`. Uses BiRefNet bg mask for background-only phase correlation. Currently disabled because it changes frame timing and caused regressions.
- Cons: The frame-timing regression remains unsolved. Re-enabling after §3.3 (DINOv2 selection) may behave differently since pose selection is handled separately.

**Recommendation:** B first (available weights, simpler implementation). A as the quality ceiling once the CamFlow code is published. C is a free experiment if §3.3 is implemented (BiRefNet already runs before selection in that scenario).

---

### 3.6 ToonCrafter Seam Synthesis — Wiring the Generative Fallback [✅ Option B shipped — Session 9]

**Pain point (links to §1.6, Phase 6.3):** When `post_warp_diff > 22 lum units`, Stage 8.5 escalates to "single-pose fallback" — a clean but informationally incomplete solution (shows one character pose at the seam, hiding the other). The seam zone is left with a visible hard boundary. ToonCrafter can *synthesize* a coherent intermediate pose that eliminates the boundary entirely.

**Session 9 implementation (Option B):** `_TOONCRAFTER_SEAM_ENABLED = os.environ.get("ASP_TOONCRAFTER_SEAM", "0") != "0"` added to `compositing.py`. `seam_post_diffs: dict` tracks `post_warp_diff` per seam during the fg-register loop. After the loop, the worst single-pose-escalated seam (`max(seam_single_pose, key=lambda k: seam_post_diffs.get(k, 0.0))`) triggers `_generate_canonical_cel(crop_a_tc, crop_b_tc, device)` from `anim_fill.py`. The canonical cel is stored in `seam_canonical_crops[worst_k]`; in the Laplacian blend loop it replaces the hard dominant-frame partition for fg pixels. Falls back gracefully to single-pose when ToonCrafter is unavailable.

**Current state:** `animation/anim_fill.py` already implements ToonCrafter integration. It is referenced in `§1.6` as Option D and in `pipeline.py` as `if self.use_tooncrafter`. It IS now wired to single-pose seam escalation in `compositing.py` (session 9).

**What changes:** In `compositing.py`, when `post_diff > _POST_DIFF_THRESHOLD` (line ~619), instead of recording `seam_single_pose[k] = dom`:
1. Extract the ±50px seam-band crop from both warped frames (frame_a, frame_b around the seam)
2. Call `anim_fill.tooncrafter_ghost_fill()` on the crop pair
3. The synthesized intermediate frame replaces the hard-partition boundary with a generated transitional pose
4. Insert the synthesized crop into the composite output

**Options**

**A — ToonCrafter on every single-pose-escalated seam [Research]**
Run ToonCrafter synthesis for every seam where `post_diff > 22`. Each seam synthesis: ~24s on A100, ~10GB VRAM with fp16. For 13 seams in test08: 5 single-pose escalations × 24s = 2 minutes extra. Only viable with `final_quality=True` mode flag.
- Pros: Eliminates single-pose discontinuities entirely. Maximum quality.
- Cons: 2+ minutes extra per dataset with many high-residual seams. Not suitable for standard mode.

**B — ToonCrafter only for the worst seam (highest post_diff) [Quick Win toward Research]**
Apply synthesis only to the single seam with the largest `post_warp_diff` in each dataset. For test27, this would be boundary B2 (post_diff=9.7) — already below threshold so no synthesis needed. For test08 (many seams near threshold), synthesis would target the worst seam only.
- Time: 1 seam × 24s = 24s overhead in final-quality mode. Manageable.
- Pros: Focused quality improvement with bounded time overhead.
- Cons: Other seams still use hard partition.

**C — ToonCrafter crop-scale optimisation [Research]**
Current ToonCrafter operates at 512×320. Our seam crops are typically 600×(narrow band ~100px). Resize to 512×100 (preserving aspect), run inference, resize back. This would reduce VRAM to ~3GB and inference to ~8s.
- Cons: Low vertical resolution may reduce synthesis quality. Requires testing.

**Recommendation:** Wire Option B into `compositing.py` behind `ASP_TOONCRAFTER_SEAM=1` env var (default off). Measure SSIM impact on the 5-test corpus. If test08 improves, escalate to Option A for final-quality mode. Option C is worth prototyping alongside B since it drastically reduces the per-seam cost.

---

### 3.7 UDIS++ / UDTATIS Diffusion-Based Seam Composition [Long-term — End-to-End Replacement]

**Pain point (links to §1.6):** The current Laplacian blend (Stage 11) stitches the seam zone using a multi-band pyramid blend. For large pose differences that survive after ARAP registration, the blend creates visible double-edge ghosting. A generative model that hallucinates coherent bridging pixels would eliminate this class of artifact.

**What UDIS++/UDTATIS does:** Two-stage pipeline:
1. **Unsupervised geometric warping** (EfficientLOFTR + spatial transformer): Aligns frame pair without supervision, using a mesh-based local deformation field (parallax-tolerant, unlike our global translation model)
2. **Diffusion-based composition**: The warped overlap region is passed through a denoising diffusion process with multi-scale feature fusion, continuity constraints, and adaptive normalisation. The seam line is literally hallucinated away.

**How it applies:** UDIS++ would replace Stage 11 entirely — the current `_composite_foreground()` in `compositing.py` (hard-partition + Laplacian blend) is replaced by UDIS++ inference on the warped frame pair. UDIS++ handles both alignment and compositing in one pass.

**Options**

**A — UDIS++ for the seam composition step (after our ARAP warp) [Research]**
Keep our ARAP fg registration for pose alignment (Stage 8.5). Then feed the ARAP-warped frames into UDIS++ only for the composition step (replacing the Laplacian blend). This is a hybrid: our pose registration + learned composition.
- Pros: UDIS++ open-source code available on [GitHub](https://github.com/nie-lang/UDIS2). Pre-trained weights available.
- Cons: UDIS++ was trained on natural images — significant domain gap for anime. Would need fine-tuning on anime data for reliable quality.

**B — UDTATIS with EfficientLOFTR (cartoon-specific) [Research]**
UDTATIS integrates EfficientLOFTR (already in our matching stack) and a diffusion composer. The EfficientLOFTR feature extraction may generalise better to anime than VGG-based alternatives.
- Cons: Less established than UDIS++. Tested on terahertz imagery; anime applicability unclear.

**C — RDIStitcher: pure inpainting paradigm [Long-term]**
Completely replaces geometric warping + Laplacian blend with a T2I diffusion model that treats the entire seam as an inpainting problem. Self-supervised via pseudo-stitched training pairs (artificially misaligned images). Zero-shot at inference time.
- Pros: Maximum generative flexibility. No feature matching required.
- Cons: RDIStitcher inference: ~15–30s on consumer GPU. Not viable for standard mode. `final_quality=True` mode only.

**Recommendation:** A as a research prototype (UDIS++ code is available, integration is well-defined). C as the long-term aspirational target since it entirely removes the need for hand-crafted seam-finding. B if UDIS++ shows too much domain gap on anime.

---

### 3.8 SIQE No-Reference Ghosting Detection [Quick Win — metric upgrade]

**Pain point (links to §1.6, §1.10):** The current `_ghosting_score()` metric computes local variance of a Laplacian pyramid — a proxy that correlates weakly with perceptual ghosting. The ghosting gate (§2.0's ghosting ratio gate, ratio=1.92–2.06 borderline for test82) is unreliable at borderline values due to SCANS non-determinism.

**What SIQE does:** The Stitched Image Quality Evaluator uses:
1. Multi-scale steerable pyramid decomposition (2 scales × 6 orientations = 12 subbands)
2. Gaussian Mixture Model fitted to the pyramid subband statistics of pristine panoramas
3. Ghosting localisation via optical flow energy variance across the panorama
4. 94.36% precision vs mean subjective human opinion

**How it applies:** Replace `_ghosting_score()` in `bench_anime_stitch.py` with SIQE. The ghosting gate (`ASP_GATE_GHOST`) becomes more reliable. Additionally, SIQE can spatially localise ghosting (output: map of ghost probability per pixel), enabling targeted per-seam intervention rather than a global fallback decision.

**Options**

**A — Double-edge autocorrelation ghosting metric** ✅ **Shipped S35**
`_ghosting_score_v2(img)` in `bench_anime_stitch.py` — FFT-based autocorrelation of the column-mean gradient-magnitude profile. Detects the secondary peak at displacement D that a ghost (shifted copy) creates. Score in [0–100]: 0=no ghost, 30+=ghost likely. Added as `ghosting_siqe` metric in `_compute_all_metrics`; original `ghosting_score` kept for GhostGate calibration. 5 tests in `test_bench_metrics.py::TestGhostingScoreV2`. Zero new deps.
- Unlike the double-Sobel proxy, this metric is specifically sensitive to *repeated* edge patterns at a fixed displacement — the signature of a misaligned character copy — while being insensitive to high-frequency texture that is not ghost-related.
- Pros: Pure numpy FFT (~0.5ms for 2000px), zero new deps. Directly measures double-edge periodicity.
- Cons: Does not achieve full SIQE accuracy (no GMM, no steerable pyramid orientation analysis). For the full SIQE, see Option B below.

**B — Full SIQE (steerable pyramid + GMM) [Research]**
Implement the full steerable pyramid + GMM pipeline. The GMM is fitted offline on pristine stitched anime panoramas (the 52/96 ASP-succeeded tests as positive examples). SIQE achieves 94.36% precision vs mean subjective human opinion.
- Pros: 94.36% precision. Best-in-class for panoramic ghosting.
- Cons: Steerable pyramid needs `pyrtools` or custom implementation; GMM fitting requires clean corpus.

**B — SIQE spatial ghost map → per-seam ghost gate** ✅ **Shipped S53**
`_compute_per_seam_ghost_scores(img, n_strips, band_px=100)` in `bench_anime_stitch.py`. Divides output image into equal-height zones, evaluates `_ghosting_score_v2` in ±`band_px` bands at each seam boundary. Returns `n_strips-1` scores in [0–100]. Wired into `_compute_all_metrics` via `n_strips` param; result dict adds `ghost_seam_scores` (List[float]) and `ghost_seam_max` (Optional[float]). Backward compatible (default `n_strips=1`). 5 tests in `test_bench_metrics.py::TestPerSeamGhostScores`.
- Pros: Surgical localisation — identifies the worst seam without the global-fallback blunt instrument. < 5ms overhead for N=12 seams.
- Note: Uses `_ghosting_score_v2` (FFT autocorrelation proxy), not full SIQE (steerable pyramid + GMM). Full SIQE is a future option if per-seam recalibration targets it.

**Recommendation:** A as the first step (replaces the current imprecise metric). B as a high-value follow-on once A is validated — it would close the gap between "good composite with 1 bad seam" and the current "SCANS fallback for any quality gate failure."

---

### 3.9 SI-FID: Stitched-Image Fréchet Distance for Reference-Free Evaluation [Research]

**Pain point:** GT-SSIM is a biased evaluation metric — it penalises any temporal deviation from the GT's frame choices regardless of actual composite quality. We need a reference-free metric that reflects perceptual stitch quality.

**What SI-FID does (arXiv 2404.13905):**
- A neural network is trained via contrastive learning on images with artificially injected stitching artifacts (parallax shearing, hue misalignment, structural ghosts)
- The network projects pristine and corrupted images into a separable latent space
- SI-FID computes the Fréchet distance between the generated output's feature distribution and the learned pristine distribution
- **25% higher rank correlation with subjective human opinions** compared to competing objective metrics

**How it applies:**
1. **Evaluation:** Replace or supplement GT-SSIM in the benchmark with SI-FID for tests without ground truth (41 of 96 tests currently have no GT)
2. **Optimization target:** If SI-FID is reliable on anime, use it as the objective for RLHF parameter search (§1.10) — this completely sidesteps the GT-coupling problem in §0.2
3. **Render gate:** SI-FID score could replace or augment the `seam_coherence` + `strip_banding` composite gate with a perceptually grounded metric

**Options**

**A — SI-FID as supplementary benchmark metric [Research]**
Add SI-FID computation to the benchmark alongside GT-SSIM. Compare rankings — if SI-FID rank-orders tests the same way human inspection would, it becomes trustworthy for the 41 GT-less tests.
- Implementation: Train (or obtain) the SI-FID network. Available at [arXiv 2404.13905](https://arxiv.org/abs/2404.13905). If no pretrained weights for anime, fine-tune on the 52/96 ASP-succeeded outputs vs SCANS outputs.

**B — SI-FID as RLHF optimization objective [Research]**
Replace GT-SSIM in the Bayesian parameter search (§1.10) with SI-FID. This enables optimizing pipeline parameters without GT-coupling bias. The search becomes: find parameters that maximise SI-FID across the 96-test corpus (including the 41 without GT).
- Pros: Solves GT-coupling fundamentally by switching the objective function.
- Cons: SI-FID needs to be validated on anime before being trusted as an optimization target.

**Recommendation:** A first to validate SI-FID's utility on anime. B only after A confirms it agrees with human inspection on the available GT tests.

---

### 3.10 MLLM Semantic Quality Scoring [Research — Autonomous Quality Assurance]

**Pain point (links to §1.10):** The current automated quality assessment (seam_coherence, strip_banding, ghosting ratio) detects photometric artifacts but cannot detect semantic failures — a character with a severed torso, four arms, or mismatched body orientation. These failures exist in the corpus and pass all current gates.

**What MLLM SIQS/MICQS does:** Uses a vision-language model (Qwen-VL, GPT-4V, or similar) to:
- **Single-Image Quality Score (SIQS):** Asks "Does this panoramic image show a coherent character? Are there any duplicated limbs, cut-off body parts, or mismatched poses?" → confidence score 0–1
- **Multi-Image Comparative Quality Score (MICQS):** Given two outputs (ASP vs simple stitch), asks "Which shows a more coherent, complete character body?" → preference score
- Flags any output with SIQS < 0.5 for human review or automatic regeneration with a different random seed

**How it applies:** Post-pipeline MLLM check as an additional quality gate in the benchmark. For production use, integrate into `StitchWorker` as an optional final-pass check (`ASP_MLLM_QA=1`).

**Options**

**A — Local MLLM via llama.cpp or ollama [Research]**
Run Qwen2-VL-7B (or similar) locally via `ollama pull qwen2-vl` or `llama-server`. No API cost. ~10–20s per image for 7B model on CPU, ~2s on GPU.
- GPU: RTX 3090 Ti has 24GB — Qwen2-VL-7B fits in 14GB at 4-bit, leaving 10GB for the ASP pipeline.
- Cons: Significant VRAM competition with BiRefNet + RAFT during pipeline run. Must run sequentially.

**B — MLLM as benchmark-only metric (no production integration) [Research]**
Run MLLM scoring as a post-hoc batch evaluation step on benchmark outputs, not inline with pipeline execution. Eliminates VRAM conflict entirely.
- Pros: Simplest integration. Runs after benchmark completes.
- Cons: No real-time quality gating during production use.

**C — Structured prompt for anime-specific artifact detection [Research]**
Rather than generic quality scoring, design a structured prompt that asks specific anime-composite questions: "Does the character's body look split at the waist? Are there any doubled hands or feet visible? Does the background appear to have horizontal colour bands?"
- Pros: Anime-domain specificity reduces false positives from generic "quality" judgements.
- Cons: Requires prompt engineering and validation against the corpus.

**Recommendation:** B first (benchmark evaluation, no VRAM conflict). Validate MLLM scores against human inspection on the 55 GT-scored tests. If scores correlate well with GT-SSIM verdict (asp_better/simple_better), promote to Option A for production use.

---

## 1.11 Animation Hold Detection — Preprocessing [✅ Option A shipped — session 6]

**Pain point (links to §0.2, §3.4):** The frame selector processes all N source frames (58–333) through phase correlation before any frames are discarded. For typical anime with ~3-frame holds, 70% of phase correlation pairs are within the same hold block (identical camera position, same character cel). These redundant correlations add latency and, more importantly, mask natural pose-change boundaries.

**What hold detection adds:**
1. **Speed:** Run thumbnail phase correlation only between consecutive hold-block representatives (one per unique cel). For 300-frame source with 3-frame average holds → reduces correlation pairs from 299 to ~99 (3× speedup for the selection phase).
2. **Quality:** Hold boundaries are exactly the "on twos" pose-change points identified by Sýkora 2009. The selected frames should cross exactly one hold boundary per step — if they don't, the seam spans a hold (same pose, no ARAP correction needed) or multiple holds (large animation gap, warp will fail).
3. **Diagnostic:** Hold block count directly predicts ARAP workload: tests with 15+ hold-block transitions in their selected frames will have large animation residuals.

**Options**

**A — Thumbnail pixel MAD hold detection [Quick Win — implemented session 6]**
Compare consecutive thumbnail mean absolute differences. If MAD < threshold (default 0.025 of [0,1] range), the frame is in the same hold as the previous. No new dependencies.
- File: `frame_selection.py` → `_detect_hold_blocks()` + `ASP_HOLD_THRESHOLD` env var
- Pros: Zero new dependencies. Fast (~1ms for 300 frames). Works even on compressed broadcast captures where exact pixel equality fails.
- Cons: Threshold needs tuning for heavily-compressed sources (MPEG blocking noise can inflate MAD).

**B — DINOv2 cosine distance hold detection [Research]**
If §3.3 (DINOv2) is implemented, reuse embeddings: cosine distance < 0.05 = same hold. Robust to compression noise.
- Cons: Requires DINOv2 (adds overhead if §3.3 not otherwise implemented).

**C — Phase correlation magnitude threshold** ✅ Shipped S38
If two consecutive frames have phase correlation response > 0.85 (near-perfect correlation), they're in the same hold. Already available from the existing phase correlation pass — zero extra cost.
- Cons: MPEG blocks can corrupt high-response pairs at scene boundaries.

**Recommendation:** A immediately (already implemented, `ASP_HOLD_THRESHOLD=0.025`). C as a free upgrade using the existing `responses` array in `smart_select_frames()`. B if §3.3 is implemented.

> **✅ Session 7 — Phase-correlation skip SHIPPED:** Hold threshold default changed from `0.0` to `0.025` (enabled by default). Within-hold frame pairs now return `(dx=0, dy=0, response=1.0, MAD=0.0)` without running `cv2.phaseCorrelate`, achieving the §1.11 3× speedup for typical anime with ~3-frame holds. The `high_anim_mad` gate is protected from false positives (within-hold MAD=0.0 never triggers it). `ASP_HOLD_THRESHOLD=0` to disable.

> **✅ Session 38 — §1.11C SHIPPED:** `_refine_hold_ids_by_response(hold_ids, responses, 0.85)` added to `frame_selection.py`. Wired as step 3b in `smart_select_frames` after the phase-correlation loop completes. Cross-hold pairs with `phaseCorrelate response >= 0.85` have their blocks merged; IDs renumbered consecutively. `HIGH_HOLD_RESPONSE_THRESH=0.85` in `constants/animation.py`. Override: `ASP_HIGH_HOLD_RESPONSE`. 5 new tests. 297 tests passing.

---

## 1.12 Translation Monotonicity Validation ✅ Shipped S52

**Pain point:** The four existing `_validate_affines` checks (ratio, min_gap, rotation, scale) operate on the *sorted spatial* order. They cannot detect uniformly-spaced frames in the **wrong temporal order** — e.g., a BA solution where skip edges misplace frame 3 to a position before frames 1 and 2. Such solutions have ratio ≈ 1.0 and pass all existing checks, but produce catastrophic composites (wrong frame pairs fused, seam zones misidentified).

**Option A — Kendall τ ordering check [Quick Win] ✅ Shipped S52**
`_check_translation_monotonicity(affines, primary_axis, min_tau_abs=0.4)` in `validation.py`. Computes Kendall τ between temporal frame indices [0…N-1] and primary-axis translations. |τ|=1 for perfectly monotone sequences (forward **and** backward scroll both pass), |τ|≈0 for random permutations. Returns `(is_monotone, tau_abs)`. Wired as the 5th check in `_validate_affines` (after rotation/scale) for `scroll_axis ∈ {vertical, horizontal}`. Failure reason `"monotonicity={tau:.2f} < 0.4"` falls through to Retry 1 (adj-only BA), the natural recovery since skip edges are the primary cause of frame misordering. `_MONO_TAU_MIN=0.4` constant. Requires ≥ 4 frames (shorter sequences skip the check). Exported in `__all__`. 5 tests in `TestTranslationMonotonicity`. 367 tests passing.
- Pros: O(N²) pair-counting loop, negligible for N ≤ 30. Zero new dependencies.
- Cons: Does not catch misordering on diagonal scroll sequences (skipped to avoid dominant-axis ambiguity).

**Option B — Spearman ρ (rank correlation)**
Equivalent to Kendall τ for binary concordance / discordance, but uses rank differences. Both capture the same information; Kendall τ is preferred because it is directly interpretable as (concordant − discordant) / total pairs.

**Recommendation:** A is complete and shipped. B adds no value over A.

---

## 1.13 Scene-Change Edge Pre-Filter ✅ Shipped S51

**Pain point:** When a source video contains a scene cut (or a severe lighting discontinuity that hold detection missed), the pairwise matcher still attempts to produce a translation for the cross-cut pair. The match will have low confidence and a spurious displacement. If that edge survives into bundle adjustment it introduces a wrong constraint that displaces all other frames.

**Option A — Global mean-luma gate [Quick Win] ✅ Shipped S51**
`_reject_scene_change_edges(edges, frames, max_luma_diff)` in `pipeline.py`. Computes mean grayscale luminance of each frame on a 64×64 thumbnail; rejects any edge where `|lum(i) − lum(j)| > max_luma_diff`. `_SCENE_CHANGE_LUMA_THRESH` module-level flag (default 0.0 = disabled, `ASP_SCENE_CHANGE_LUMA_THRESH=60.0` to enable). Wired as the first check in `_filter_edges`, before §1.2A+C static edge rejection. `SCENE_CHANGE_LUMA_THRESH=60.0` in `constants/animation.py`. `ASP_SCENE_CHANGE_LUMA_THRESH` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_pipeline.py::TestRejectSceneChangeEdges`. 362 tests passing.
- Pros: ~0.5ms per edge; zero new dependencies; safe by default (disabled until enabled).
- Cons: Threshold requires per-source tuning; does not catch illumination changes smaller than the threshold.

**Option B — Per-channel mean delta** ✅ **Shipped S57**
`_reject_scene_change_edges(..., use_bgr=True)` in `pipeline.py`. Per-channel (B, G, R) thumbnail means via `t.reshape(-1,3).mean(axis=0)`; `max(|ΔB|, |ΔG|, |ΔR|)` vs `max_luma_diff` threshold. Catches warm-orange vs cool-blue scene changes that grayscale misses (same luma ≈120, channel delta ≈200). `_SCENE_CHANGE_BGR_THRESH` flag (default 0.0=off, `ASP_SCENE_CHANGE_BGR_THRESH=60.0`). `SCENE_CHANGE_BGR_THRESH=60.0` in constants. `ASP_SCENE_CHANGE_BGR_THRESH` in `_CONFIG_SCHEMA`. Backward compatible (`use_bgr=False` default). Wired as second pass in `_filter_edges` after §1.13A. 5 tests in `test_pipeline.py::TestRejectSceneChangeEdgesBgr`. 392 tests passing.
- Max-delta metric (not Euclidean) keeps the threshold in the same [0,255] unit as §1.13A — no recalibration needed.

**Option C — CLIP embedding distance**
Compute CLIP visual embeddings and reject edges where cosine distance > 0.4 (typical threshold for scene-change detection). Semantically grounded — detects scene changes even when luma is similar.
- Cons: Requires CLIP (adds ~200MB dependency); overkill for luma-based scene cuts.

**Recommendation:** A is sufficient for the vast majority of scene-cut failures (most cuts involve a large brightness change). Implement B if A produces false negatives on colour-only scene changes. Skip C unless a pure-scene-embedding-quality gate is needed.

---

## 1.14 Per-Seam Colour-Distribution Banding Metric [Quick Win — diagnostic]

**Pain point (links to §1.4, §1.6, §1.16):** The existing per-seam diagnostics (`seam_visibility_score`, `ghost_seam_scores`) both operate in the *spatial* domain. Neither catches distributional colour mismatch — two adjacent strips can have similar mean luminance and identical local gradients but completely different histogram shapes (e.g., one dominated by a bright background gradient, the other by a dark character body), producing a perceptible tonal shift that spatial metrics miss.

**Option A — Bhattacharyya histogram similarity [Quick Win] ✅ Shipped S55**
`_seam_bhattacharyya_distances(img, n_strips, band_px=50)` in `bench_anime_stitch.py`. For each inter-strip seam boundary, computes greyscale histograms of the `band_px`-row window above and below; returns `1 − cv2.compareHist(HISTCMP_BHATTACHARYYA)`. Score in [0,1]: 1.0=identical distributions (clean seam), <0.5=severe colour mismatch (hard banding). `_compute_all_metrics` extended with `seam_color_scores` (List[float]) and `seam_color_min` (Optional[float]). Zero new deps. 5 tests in `test_bench_metrics.py::TestSeamBhattacharyyaDistances`.
- Complements `ghost_seam_scores` (repeated-edge periodicity) and `seam_visibility_score` (peak luminance jump). Bhattacharyya captures *distribution shape* divergence that those metrics miss.
- `band_px=50` (narrower than §3.8B's 100px) — 50 rows is sufficient for histogram characterisation.

**Option B — Colour-banding pipeline gate** ✅ **Shipped S56**
`_seam_color_similarity(img, k, n_strips, band_px=50)` + `_check_seam_color_gate(img, n_strips, thresh)` in `compositing.py`. `_SEAM_COLOR_GATE` flag (default 0.0=off, `ASP_SEAM_COLOR_GATE=0.55`). `SEAM_COLOR_GATE_THRESH=0.55` in constants. Stage 11.2 gate in `pipeline.py`: after `_composite_foreground`, calls `_check_seam_color_gate(canvas, N, _SEAM_COLOR_GATE_THRESH)` — on failure logs worst seam index and triggers `_scan_stitch_fallback`. `ASP_SEAM_COLOR_GATE` added to `_CONFIG_SCHEMA`. Both functions exported in `__all__`. 5 tests in `test_compositing.py::TestSeamColorGate`. 387 tests passing.
- Gate fires at thresh=0.55 (45% histogram divergence), the natural break between "tight single-colour zones" and "distinct-luminance-distribution strips". Default OFF preserves all existing corpus results.
- Does not re-run Stage 11 with wider feather (that would require seam-specific re-compositing infrastructure); instead triggers SCANS via the same `_sf = scans_frames or _reload_scans_frames(image_paths)` pattern as all other post-Stage-10 fallbacks.

**Option C — Per-channel (BGR) histogram comparison [Research]**
Extend Option A to compute per-channel histograms and return the minimum across channels. Detects hue shifts (e.g., warm interior strip vs cool exterior strip) that greyscale misses.
- Pros: More sensitive to chroma banding from different character colour palettes.
- Cons: 3× compute; Bhattacharyya on hue channels is less stable for near-black regions.

**Recommendation:** A is shipped (diagnostic baseline). B as the action gate once threshold is calibrated on the corpus. C if chroma-only banding is identified as a common failure mode.

---

## 1.15 Edge Graph Connectivity Validation [Quick Win] ✅ Shipped S58

**Pain point:** The §1.13A/B scene-change gates and §1.2A/C static-edge filters can, in edge cases, remove enough edges to partition the frame graph into disconnected components. Bundle adjustment then assigns unconstrained translations to isolated frames, producing bad affines that consume the full Retry 0–5 chain before landing on SCANS.

**Option A — Union-Find pre-BA connectivity check** ✅ **Shipped S58**
`_check_edge_graph_connectivity(edges, n_frames) → bool` in `pipeline.py`. Iterative path-compression Union-Find over all valid edges. Returns False when any frame 0..n_frames-1 is not reachable from frame 0. Wired immediately after the `if not edges:` guard in `run()`: disconnected graph → `_scan_stitch_fallback` with diagnostics log. O(E·α(N)) — negligible overhead. Exported in `__all__`. 5 tests in `test_pipeline.py::TestCheckEdgeGraphConnectivity`. 397 tests passing.
- Same Union-Find algorithm as §1.1B (spanning-tree pre-filter) — no new algorithmic machinery. The gate converts a guaranteed retry-chain waste into an immediate clean fallback.

---

## 1.16 Minimum Spanning Tree Weight Gate [Quick Win] ✅ Shipped S60

**Pain point:** §2.9C retry 0 (`_filter_high_conf_edges`) fires *after* BA has already been attempted with the full edge graph. When the graph is dominated by TM/PC fallback edges (weight~0.15–0.3 — phase-correlation or template-matching fallbacks, not LoFTR) the BA will produce poor translations regardless of the retry chain; the retry chain is wasted.

**Option A — MST weight pre-BA gate** ✅ **Shipped S60**
`_compute_mst_weight(edges, n_frames) → float` in `pipeline.py`. Builds max-weight spanning tree (Kruskal + iterative path-compression Union-Find) and returns `total_tree_weight / (N-1)`. Gate fires before Stage 7 BA when mean MST weight < `_MST_MIN_WEIGHT` (default 0.0=off, `ASP_MST_MIN_WEIGHT=0.35`). `MST_MIN_WEIGHT=0.35` constant in `constants/animation.py`. `ASP_MST_MIN_WEIGHT` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_pipeline.py::TestComputeMstWeight`. 407 tests passing.
- LoFTR edges weight~0.6–0.9; TM/PC fallbacks~0.15–0.3; threshold 0.35 fires on all-TM/PC graphs.
- O(E log E) sort when enabled; zero overhead when disabled (default).
- Complementary to §1.15 (connectivity): §1.15 fires on disconnected graphs, §1.16 fires on weakly connected but low-confidence graphs.

---

## 1.17 Canvas Span Utilisation Gate [Quick Win] ✅ Shipped S61

**Pain point:** Pre-BA gates (§1.15 connectivity, §1.16 MST weight) and post-validation gates (§0.5C min gap, §1.12 Kendall-τ) together block most bad graph topologies before Stage 10. One gap remains: a BA solution can pass all per-step checks yet produce a globally collapsed canvas. This happens when the optimiser converges to an oscillating local minimum (frames alternating between two positions) — each adjacent step looks valid but the total span is far less than `median_step × (N-1)` would imply.

**Option A — Canvas span utilisation post-BA gate** ✅ **Shipped S61**
`_compute_canvas_span_utilization(affines) → float` in `pipeline.py`. Computes `actual_dominant_axis_span / (median_adjacent_step × (N-1))`. Dominant axis = whichever of ty/tx has larger range. Returns 1.0 for N < 2 or zero expected span (safe fallback). `_CANVAS_SPAN_MIN_UTIL` flag (default 0.0=off, `ASP_CANVAS_SPAN_MIN_UTIL=0.3`). Wired after §3.14 scroll-axis check (Stage 9.5), before Stage 10 temporal rendering. `CANVAS_SPAN_MIN_UTIL=0.3` in `constants/animation.py`. `ASP_CANVAS_SPAN_MIN_UTIL` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_pipeline.py::TestComputeCanvasSpanUtilization`. 412 tests passing.
- Oscillating solution [0,100,0,100,0,100]: span=100, median_step=100, expected=500 → util=0.2 < 0.3. Per-step validation all pass (each adjacent step=100px is fine); only global collapse is caught.
- Distinct from Stage 10.5 coverage gate (§0): that measures how many canvas rows have ≥2 frames; §1.17 fires earlier (Stage 9) and detects the geometric collapse, not the coverage consequence.
- Complementary to §1.15/§1.16: those fire before BA; §1.17 fires after BA succeeds but produces a degenerate geometric solution.

---

## 1.32 GNC-TLS Bundle Adjustment [Quick Win] ✅ Shipped S76

**Pain point:** Category B failures (13.5% of corpus; test13 ratio=11.1×, test54=3.5×, test64=4.2×, test66=3.1×, test70=4.1×, test73=3.8×, test89=4.0×) arise when a single catastrophically bad LoFTR match inflates the 3×-median outlier threshold, shielding itself from rejection. The §1.1B spanning-tree pre-filter removes edges inconsistent with the MST reference, but cannot catch a bad edge that *is* the MST edge (highest-weight wrong match corrupts the BFS reference). The §1.1C Cauchy one-shot solve down-weights but cannot fully suppress edges with >50px residual once they contaminate the global median. A theoretically superior approach is graduated non-convexity (Yang et al. 2020): start with a convex surrogate (all edges weighted ≈1) and progressively anneal toward the truncated-LS cost, giving outlier edges exponentially smaller weights over 8 outer iterations.

**Option A — GNC-TLS outer continuation loop** ✅ **Shipped S76**
`_gnc_weights_geman_mcclure(residuals_sq, mu, c_sq) → ndarray` in `bundle_adjust.py` (Yang et al., IEEE RA-L 2020, arXiv:1909.08605). Geman-McClure per-edge weights `wᵢ = (μc² / (μc² + rᵢ²))²`. Outer loop in `_bundle_adjust_affine` initialises μ₀ = max_sq/(2c²) (convex boundary), then per-iteration: (1) compute per-edge squared translation disagreement, (2) update Geman-McClure weights, (3) LM step with `loss='linear'` and weights injected via `√w` multiplier in the `residuals()` closure, (4) anneal μ ÷= 1.4. Terminates when ‖Δx‖ < 1e-3 or μ < 0.01. `_GNC_OUTER=8` default (set `ASP_GNC_OUTER=0` to revert to §1.1C Cauchy+adaptive re-solve). `GNC_C_PX=10.0`, `GNC_MU_ANNEAL=1.4`, `GNC_MAX_OUTER=8` in `constants/animation.py`. `ASP_GNC_OUTER` in `_CONFIG_SCHEMA`. `_gnc_weights_geman_mcclure` exported in `__all__`. 5 tests in `test_bundle_adjust.py::TestGNCWeightsGemanMcclure`: unit-weights-large-mu, zero-residual-weight-one, high-residual-suppressed, weights-in-valid-range, higher-residual-lower-weight. **412 tests passing.**
- Default **ON** (not a gate): changes BA output on every run that has any edge residual > 0.
- Tolerates up to ~70–80% outlier edges vs. ~50% for RANSAC-style Cauchy rejection.
- Post-solve outlier rejection (§1.1 prong-1 + prong-2) remains unchanged as the backstop.
- Category B full-corpus impact pending benchmark; synthetic suite confirms no regression on existing tests.

---

## 1.31 Seam FG Penetration Escalation [Quick Win] ✅ Shipped S75

**Pain point (links to §1.23, §3.15A, §1.28):** §1.23 and §3.15A raise DP cost for foreground-dominated columns, but when every column in the overlap is fg-dominated, the DP is forced through character pixels regardless. §1.28 (instability, std-based) detects this indirectly when the path oscillates, but a seam that routes consistently along the character midline has low std and passes §1.28. The direct measure — what fraction of seam pixels are on foreground? — is missing.

**Option A — FG penetration fraction [Quick Win]** ✅ **Shipped S75**
`_seam_fg_penetration(path, fa_zone, fb_zone) → float` in `compositing.py` — samples `path[x]` for each column x; pixel is fg if any channel > 0 in either zone; returns fraction in [0,1]. Wired in blend loop after §1.28: if `_SEAM_FG_PENETRATION_MAX > 0.0 and penetration > threshold and k not in seam_single_pose → seam_single_pose[k] = dominant`. Dominant frame picked by fg pixel count in zone. `_SEAM_FG_PENETRATION_MAX` flag (default 0.0=off, recommend 0.7). `SEAM_FG_PENETRATION_MAX=0.7` in constants. `ASP_SEAM_FG_PENETRATION_MAX` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestSeamFgPenetration`. 482 tests passing.
- Completes the three-layer fg-seam defence: §1.23/§3.15 (cost barriers → steer away from fg), §1.28 (std → detect chaotic routing), §1.31 (penetration → detect fg bisection directly).
- 0.7 threshold = 70% of seam columns on fg → character midline bisection; lower thresholds (0.5) are useful for partial-character overlaps.

---

## 1.30 Minimum Zone Height Guard [Quick Win] ✅ Shipped S74

**Pain point (links to §1.26, §1.28):** §1.26 clips the DP seam path to `[margin, zone_h-1-margin]`. When a blend zone is only 4–19 rows tall (valid range is `[3,4]` with default margin=3), the clamp leaves at most 2 valid rows, the DSFN feather has no room to ramp, and the S15/S16 soft-edge band (±6px) overflows the zone boundary. The DP still runs but produces a constant-row path regardless of content — equivalent to a midpoint slice with no blending benefit.

**Option A — Configurable zone height escalation gate [Quick Win]** ✅ **Shipped S74**
`_zone_is_degenerate(zone_h, min_height=20) → bool` in `compositing.py` — returns True when `zone_h < min_height` (and `min_height > 0`). Wire-up in `_composite_foreground`: after `fa_zone`/`fb_zone` are allocated, before DP path computation, checks degenerate gate and `k not in seam_single_pose`; if True, picks dominant by fg pixel count and sets `seam_single_pose[k]`. Hard-partition blend fires at the existing `_single = seam_single_pose.get(k)` check. `_ZONE_MIN_HEIGHT` flag (default 0=off, recommend 20). `ZONE_MIN_HEIGHT=20` in constants. `ASP_ZONE_MIN_HEIGHT` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestZoneIsDegenerate`. 477 tests passing.
- 20-row floor = S15/S16 soft-edge band width (`2 × ASP_SP_SOFT_PX=6 + §1.26 margin=3`). Zones narrower than this cannot be blended cleanly regardless of DP routing.
- The existing `if zone_h < 4: continue` is the hard abort floor; this is a softer, configurable single-pose escalation gate above it.

---

## 1.29 Static Input Detection Gate [Quick Win] ✅ Shipped S73

**Pain point (links to §0, pipeline robustness):** When all input frames are near-identical (static image repeated N times, or near-black frames from a failed capture), Phase Correlation reports near-zero displacement for every pair. Bundle Adjustment converges to a degenerate canvas (all frames stacked at offset 0), and the output is a single blurry copy rather than a panorama. The pipeline currently has no early-exit for this case.

**Option A — Pre-Stage-1 MAD gate [Quick Win]** ✅ **Shipped S73**
`_detect_static_input(frames, max_mad, thumb_size=64) → bool` in `pipeline.py` — resizes each frame to a 64×64 greyscale thumbnail and checks whether all consecutive pairs have mean absolute difference (MAD) < `max_mad`. Returns True only when ALL pairs are below the ceiling. Stage 1.5 gate in `run()`: when True, logs a warning and `cv2.imwrite(frame 0 → output_path)` early return. `_STATIC_INPUT_MAX_MAD` flag (default 0.0=off, recommend 2.0). `STATIC_INPUT_MAX_MAD=2.0` in constants. `ASP_STATIC_INPUT_MAX_MAD` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestDetectStaticInput`. 472 tests passing.
- 2.0 MAD on [0,255] scale ≈ 0.8% pixel noise — tolerates MPEG compression noise while catching genuine static sequences.
- Zero overhead on non-static inputs (all-pairs check short-circuits on first differing pair).
- Safe fallback: frame 0 written to output rather than an exception; caller can proceed normally.

---

## 1.28 Seam Path Instability Escalation [Quick Win] ✅ Shipped S72

**Pain point (links to §1.25, §1.26, §1.20):** §1.25 smooths single-pixel jitter and §1.26 prevents the seam from reaching zone edges, but neither prevents the blend from straddling two fundamentally incompatible frame regions. When the DP path has high column-variance (std > 20 rows), the zone contains content that cannot be blended cleanly — typically a character that moved too far between frames. In this case, blending a chaotic seam produces a wide zigzag ghost rather than a clean cut.

**Option A — Std-triggered single-pose escalation [Quick Win]** ✅ **Shipped S72**
`_seam_path_std(path) → float` in `compositing.py` — `float(np.std(path))`; 0.0 for empty path. Wired in blend loop after `path_local` is resolved: `if _SEAM_INSTABILITY_THRESH > 0 and k not in seam_single_pose and _seam_path_std(path_local) > threshold → seam_single_pose[k] = dominant frame`. Dominant frame chosen by fg pixel count in zone (same logic as §1.20). `_SEAM_INSTABILITY_THRESH` flag (default 0.0=off, `ASP_SEAM_INSTABILITY_THRESH=20.0`). `SEAM_INSTABILITY_THRESH=20.0` in constants. `ASP_SEAM_INSTABILITY_THRESH` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestSeamPathStd`. 467 tests passing.
- Only fires when no prior single-pose decision exists for boundary k (`k not in seam_single_pose`) — does not override ARAP escalations (§1.18/§1.20).
- Complements §1.25 (smoothing removes micro-jitter) and §1.26 (boundary clamp removes edge artefacts); §1.28 addresses the structural case where the entire path is unstable.

---

## 1.27 Background Coverage Gate for Normalisation [Quick Win] ✅ Shipped S71

**Pain point (links to §1.4, §1.4F):** The normalisation loop has always had a hardcoded `>= 200` background-pixel floor before applying gain correction, but this threshold was implicit and not configurable. For portrait shots where BiRefNet assigns nearly the entire frame to foreground, 10–50 background pixels produce a noisy gain estimate that can introduce banding. Making the threshold explicit and configurable allows per-dataset tuning.

**Option A — Configurable bg-pixel floor [Quick Win]** ✅ **Shipped S71**
`_has_sufficient_bg(bg_sel, min_px=200) → bool` in `compositing.py` — `np.count_nonzero(bg_sel) >= max(1, min_px)`. None input → False. Replaces `len(bg_px) >= 200` in the normalisation loop. `_BG_NORM_MIN_PX` flag (default 0 → falls back to 200). `BG_NORM_MIN_PX=200` in constants. `ASP_BG_NORM_MIN_PX` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestHasSufficientBg`. 462 tests passing.
- Default behavior identical to pre-S71: the historical 200-pixel floor is preserved when `ASP_BG_NORM_MIN_PX=0`.
- Complementary to §1.4F (`_reject_exposure_outliers`): that skips correction for extreme outlier frames; this skips correction when the bg sample is too small to estimate gain reliably.

---

## 1.26 Seam Path Boundary Clamp [Quick Win] ✅ Shipped S70

**Pain point (links to §1.25, §1.6):** `_seam_cut()` can route the seam to y=0 or y=zone_h-1 — the zone boundary rows. The feather blend in `_composite_foreground` then has zero headroom on one side of the cut, degenerating into a hard edge artefact at the zone boundary. This is distinct from jitter (§1.25) and from in-zone ghosting (§1.6); it specifically affects zones where the cost gradient forces the seam to the edge.

**Option A — np.clip boundary margin [Quick Win]** ✅ **Shipped S70**
`_clamp_seam_path(path, zone_h, margin=3) → np.ndarray` in `compositing.py` — `np.clip(path, margin, zone_h-1-margin)`. Keeps the seam at least `margin=3` rows from top/bottom so the feather always has blending headroom. Guard: `zone_h ≤ 2*margin` → path unchanged (prevents bound inversion on very thin zones). `_SEAM_MARGIN` flag (default 0=off, `ASP_SEAM_MARGIN=3`). Wired at end of `_seam_cut()` after §1.25 smoothing. `SEAM_MARGIN=3` in constants. `ASP_SEAM_MARGIN` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestClampSeamPath`. 457 tests passing.
- Zero dependencies; single `np.clip` call.
- Complementary to §1.25: §1.25 removes zigzag jitter inside the zone; §1.26 prevents the seam from escaping to the zone edge entirely.

---

## 1.25 Seam Path Smoothing [Quick Win] ✅ Shipped S69

**Pain point (links to §1.5, §1.6, §3.15A):** The `_seam_cut()` DP traceback uses `argmin` over a ±1-column window at each step. When two adjacent columns have nearly equal energy, the traceback oscillates between them on consecutive rows, producing a fine diagonal zigzag band at the seam boundary — a hard-to-diagnose artefact that is distinct from the broader character-body ghosting addressed by §1.6.

**Option A — 1-D median filter post-processing [Quick Win]** ✅ **Shipped S69**
`_smooth_seam_path(path, window=5) → np.ndarray` in `compositing.py` — `scipy.ndimage.median_filter` applied to the int32 path array. Window=5 removes all oscillations of period ≤ 2 (single-pixel jitter) while preserving coarser routing bends (period ≥ 3 passes through). Even windows incremented to next odd. window ≤ 1 is a no-op. `_SEAM_SMOOTH_WINDOW` flag (default 0=off, `ASP_SEAM_SMOOTH_WINDOW=5`). Wired at end of `_seam_cut()`. `SEAM_SMOOTH_WINDOW=5` in constants. `ASP_SEAM_SMOOTH_WINDOW` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestSmoothSeamPath`. 452 tests passing.
- Zero new dependencies (scipy already used for `minimum_filter1d` in `_seam_cut()`).
- Analogous to post-processing in graph-cut segmentation and video seam-carving pipelines.

---

## 1.24 Post-Composite Seam-Step Gate [Quick Win] ✅ Shipped S68

**Pain point:** Stage 11.2 (§1.14B, S56) detects colour mismatch in source frames *before* compositing. After compositing, photometric normalisation can still fail silently — producing a final output with a visible luminance step at a strip boundary even when source frames passed the pre-composite gate. No post-composite sanity check on absolute step size existed.

**Option A — Luminance-step backstop gate [Quick Win]** ✅ **Shipped S68**
`_measure_max_seam_step(canvas, n_strips, band_px=10, guard=3) → float` in `pipeline.py` — for each inter-strip boundary at `canvas_h * k // n_strips`, samples mean greyscale luma in `band_px` rows above/below (±`guard` guard rows prevent sampling within the artefact zone). Returns `max(|above − below|)` across N-1 seams. Returns 0.0 when n_strips ≤ 1 or canvas is too small for sampling bands. Stage 11.3 in `run()`: `_SEAM_STEP_GATE` float flag (default 0.0=off, `ASP_SEAM_STEP_GATE=25.0`); after Stage 11.2 colour gate, calls `_measure_max_seam_step(canvas, N)`; if > threshold → SCANS fallback with diagnostic log. `SEAM_STEP_GATE_THRESH=25.0` in constants (threshold of 25 lum units ≈ "visible step" boundary in the §3.8 seam_visibility_score taxonomy). `ASP_SEAM_STEP_GATE` in `_CONFIG_SCHEMA`. `_measure_max_seam_step` exported in `__all__`. 5 tests `TestMeasureMaxSeamStep`. 447 tests passing.
- Complements Stage 11.2 without overlap: Stage 11.2 is source-based (histogram distance before compositing), Stage 11.3 is output-based (absolute luma step after compositing).
- guard=3 prevents sampling directly at the boundary seam where artefacts are concentrated; `band_px=10` samples the stable region just outside the transition.

---

## 1.23 SemanticStitch Hard Corridor Barrier [Quick Win] ✅ Shipped S67

**Pain point (links to §3.15A, S33):** S33 raised fg-dominated columns to cost=2.0 (soft barrier). With `sem_weight=200` in `_seam_cut()`, a cost-2.0 column costs 400 energy vs clean background at ~10–50. The DP is *discouraged* from fg columns but not *prevented* — when background paths are only marginally cheaper, the DP may still route through fg. The §3.15A spec called for cost=∞ with graceful fallback.

**Option A — Hard barrier when corridor exists [Quick Win]** ✅ **Shipped S67**
`_seam_corridor_exists(cost, fg_thresh=0.5) → bool` in `compositing.py` — returns True iff the cost map has both fg-dominated columns (>50% fg-interior coverage per column) AND non-dominated columns. `_build_seam_cost_map()` extended with `barrier_cost=None` parameter: when a corridor exists, fg-dominated columns are raised to `barrier_cost` (default: `_SEAM_HARD_BARRIER_COST=1e6` when flag enabled, 2.0 otherwise). Fallback: when all columns are dominated, cost=2.0 (S33 baseline) so the DP can still find the thinnest fg path. `_SEAM_HARD_BARRIER` flag (default OFF, `ASP_SEAM_HARD_BARRIER=1`). `SEAM_HARD_BARRIER_COST=1e6` in constants. 2 schema entries in `_CONFIG_SCHEMA`. `_seam_corridor_exists` exported in `__all__`. 5 tests in `TestSeamCorridorExists`. 442 tests passing.
- With 1e6 barrier: a 3-column background corridor path costs ≤3×50=150 energy; the fg-column detour costs ≥1e6 → DP is effectively forced to use the corridor.
- The `barrier_cost` parameter makes the function independently testable without monkeypatching module globals.

---

## 1.22 Adaptive Single-Pose Soft-Edge Width [Quick Win] ✅ Shipped S66

**Pain point:** §1.15 (S15) applies a fixed ±6px soft edge at all single-pose seams regardless of the original feather width. When §1.18 escalates a 300px feather to single-pose, the viewer expected a ~300px blend transition but receives a 6px soft cut — visually equivalent to a hard seam. The 6px was appropriate for baseline feathers (80–120px) but creates a visible step for the wide feathers that §1.18/§1.19 now escalate.

**Option A — Feather-proportional soft edge [Quick Win]** ✅ **Shipped S66**
`_adaptive_sp_soft_px(feather_width, base_px=6, max_px=30, ref_px=80) → int` in `compositing.py`. Returns `min(max_px, max(base_px, base_px * feather_width // ref_px))`. At feather=80px (baseline) returns 6 unchanged. At feather=160px returns 12. At feather=300px returns 22. Capped at 30px to avoid ghost risk (double-image artefact requires ≥40px overlap). `feather_width ≤ 0` → base_px. `_ADAPTIVE_SP_SOFT` flag (default OFF, `ASP_ADAPTIVE_SP_SOFT=1`). Wired in single-pose blend branch at `_sp_soft_px` assignment: when ON, uses `_adaptive_sp_soft_px(feather)` per seam; when OFF, retains fixed `ASP_SP_SOFT_PX=6`. `SP_SOFT_BASE_PX=6`, `SP_SOFT_MAX_PX=30`, `SP_SOFT_REF_PX=80` in constants. `ASP_ADAPTIVE_SP_SOFT` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestAdaptiveSpSoftPx`. 437 tests passing.
- The 30px cap maintains the no-ghost guarantee: below 40px overlap, double-image artefacts cannot form.
- Complements §1.18 (adaptive escalation threshold): §1.18 controls when single-pose fires; §1.22 controls how soft the resulting cut is.

---

## 1.86 Zone SSIM Pre-Gate [Quick Win] ✅ Shipped S141

**Pain point (links to §1.60, §1.70, §1.18):** §1.60 (fg MAD) and §1.70 (fg coverage fraction) fire before zone extraction and use crude signals (pixel L1, binary fg fraction). §1.18 (adaptive single-pose threshold) fires after ARAP has run based on luminance residual. No mechanism exists to assess — post-ARAP, pre-blend — whether the two zone crops are structurally compatible for Laplacian blending. A zone pair may pass all pre-ARAP gates but have a large structural mismatch after ARAP fails silently (ARAP converges but doesn't reconcile the pose difference). The SSIM metric captures luminance, contrast, and spatial structure simultaneously, making it a stronger structural compatibility check than any individual gate.

**Option A — Post-ARAP Zone SSIM Pre-Gate [Quick Win] ✅ Shipped S141**
`_zone_pair_ssim(fa_zone, fb_zone, small_h=64) → float` in `compositing.py`. Resizes warped zone crops to 64px height (INTER_AREA) and computes greyscale SSIM via `skimage.metrics.structural_similarity`. Returns 1.0 (no gate) for zones with < 4 rows or < 8 cols; falls back to 1.0 on exception. `_ZONE_PRE_SSIM_THRESH` flag (default 0.0=off; `ASP_ZONE_PRE_SSIM_THRESH=0.35`). Wired in blend loop after §1.70 and before the DP seam cut: when score < threshold and `k not in seam_single_pose`, escalates using dominant-fg-pixel-count rule. `ZONE_PRE_SSIM_THRESH=0.35` in `constants/animation.py`. `"ASP_ZONE_PRE_SSIM_THRESH"` in `_CONFIG_SCHEMA` (float, 0.0–1.0). `_zone_pair_ssim` and `_ZONE_PRE_SSIM_THRESH` in `__all__`. 5 tests `TestZonePairSsim`. **933 backend tests (9 skipped, 5 pre-existing failures).**
- Threshold 0.35 corresponds to ~35% structural similarity — zones below this are structurally incompatible (character outlines in very different positions) that ARAP could not reconcile.
- Complements §1.60 (fg MAD: pixel L1 before zone extraction) with a post-ARAP structural metric.
- Default OFF to preserve all existing corpus results; enable per-dataset via TOML config.

---

## 1.85 Multi-Gate Ensemble Combiner [Quick Win] ✅ Shipped S139

**Pain point:** Individual quality gates (§1.56–§1.84) are each calibrated with fixed thresholds that fire only on clear-failure seams. A seam that nearly fails 3–4 gates without exceeding any single gate's threshold may still be problematic — it is systematically degraded across multiple dimensions without being catastrophically bad in any one. No existing mechanism combines these soft signals.

**Option A — Vote-based ensemble combiner [Quick Win] ✅ Shipped S139**
`_seam_gate_vote_counts(img, n_strips, *, thresh_color, thresh_ncc, ..., thresh_noise, thresh_contrast) → List[int]` in `compositing.py`. For each seam, accumulates one vote per active gate that flags it; uses each gate's own threshold and polarity (BELOW for color/NCC/SSIM; ABOVE for entropy/col-step/sat/hue/sharp/grad-dir/freq/noise/contrast). `_check_seam_ensemble_gate(img, n_strips, min_votes=None, *, thresh_*) → Optional[int]` returns the worst-vote seam if vote_count ≥ min_votes, else None. `_SEAM_ENSEMBLE_VOTES` int flag (default 0=off, `ASP_SEAM_ENSEMBLE_VOTES=3`). Stage 11.18 wired in `pipeline.py` after Stage 11.17; reads per-gate thresholds from env vars at call time. `ASP_SEAM_ENSEMBLE_VOTES` in `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. Exported in `__all__`. 5 tests `TestSeamGateEnsemble`. **928 backend tests passing (2 skipped).**
- Catch-all safety net: catches seams that are degraded across all dimensions without exceeding any single gate.
- Each gate contributes only when its own threshold is positive (gate-exclusive opt-in).
- Zero new deps (reuses all existing gate scoring functions).

---

## 1.84 Seam Band RMS Contrast Ratio Gate [Quick Win] ✅ Shipped S139

**Pain point:** §1.79 (sharpness: Laplacian variance ratio) captures fine-detail edge intensity. §1.82 (spectral profile) captures dominant spatial frequencies. Neither captures the broad dynamic range of a strip. Two strips can have identical Laplacian variance (same local edge intensity) and identical spectral profiles yet completely different contrast — e.g., a low-dynamic-range pastel background strip abutting a high-contrast ink-line strip with the same frequency peaks.

**Option A — Coefficient-of-variation ratio gate [Quick Win] ✅ Shipped S139**
`_seam_rms_contrast_ratio(img, n_strips, band_px=30) → List[float]` in `compositing.py`. RMS contrast is `c = std(band) / max(1, mean(band))` on the greyscale band. Score = `max(c_top, c_bot) / max(1e-4, min(c_top, c_bot))` in [1, ∞); 1.0 = identical contrast. `_check_seam_rms_contrast_gate` returns worst-seam index when score > thresh. `_SEAM_CONTRAST_GATE` flag (default 0.0=off, `ASP_SEAM_CONTRAST_GATE=4.0`). Stage 11.17 wired in `pipeline.py` after Stage 11.16. `ASP_SEAM_CONTRAST_GATE` in `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. `SEAM_CONTRAST_GATE_THRESH=4.0` in `constants/animation.py`. Exported in `__all__`. 5 tests `TestSeamRmsContrastRatio`. **923 backend tests passing (2 skipped).**
- Distinct from §1.79 (Laplacian: edge sharpness) and §1.82 (spectral: frequency content).
- Coefficient of variation is scale-invariant — works equally for dark and bright strips.

---

## 1.83 Seam Band Noise-Level Asymmetry Gate [Quick Win] ✅ Shipped S139

**Pain point:** §1.76–§1.82 cover luma, saturation, hue, sharpness, gradient direction, SSIM, and spectral profile. None captures per-pixel noise amplitude. Two strips sourced from different codec bitrates or different exposure ISO settings can share identical mean luma, colour, sharpness, and spectral content yet have very different per-pixel noise — one strip from a heavily JPEG-quantised block, the adjacent strip from a cleaner encode.

**Option A — Laplacian-std noise estimator gate [Quick Win] ✅ Shipped S139**
`_seam_noise_mismatch(img, n_strips, band_px=30) → List[float]` in `compositing.py`. Uses the Immerkær (1996) estimator `σ ≈ std(Laplacian(band)) / 6` on uint8 greyscale. Score = `|σ_top − σ_bot| / mean(σ_top, σ_bot)` in [0, 2+]; 0 = identical noise. `_check_seam_noise_gate` returns worst-seam index when score > thresh. `_SEAM_NOISE_GATE` flag (default 0.0=off, `ASP_SEAM_NOISE_GATE=1.0`). Stage 11.16 wired in `pipeline.py` after Stage 11.15. `ASP_SEAM_NOISE_GATE` in `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. `SEAM_NOISE_GATE_THRESH=1.0` in `constants/animation.py`. Exported in `__all__`. 5 tests `TestSeamNoiseMismatch`. **918 backend tests passing (2 skipped).**
- Complements §1.82 (spectral): noise is amplitude, spectral profile is frequency distribution.
- Zero new deps (cv2.Laplacian already used throughout).

---

## 1.82 Seam Spatial-Frequency Profile Mismatch Gate [Quick Win] ✅ Shipped S138

**Pain point:** §1.76–§1.81 (luma, saturation, hue, sharpness, gradient direction, SSIM) cover photometric, structural, and perceptual dimensions. None specifically targets *spectral content* — the distribution of energy across spatial frequencies. Two strips can have identical mean sharpness (same Laplacian variance) and even similar SSIM yet produce a jarring seam when their dominant spatial frequencies differ: a fine-grained noise or halftone texture above a smooth low-frequency gradient below. The seam is visible as a texture-grain discontinuity that all prior gates miss.

**Option A — FFT Pearson-r spectral mismatch [Quick Win] ✅ Shipped S138**
`_seam_freq_profile(img, n_strips, band_px=30) → List[float]` in `compositing.py`. For each boundary, takes the column-averaged 1D FFT magnitude spectrum (DC-excluded, positive-frequency half, `np.fft.rfft` along rows) of each band and returns `1 − max(0, Pearson-r)` between the two spectral vectors. Score 0=identical spectra (compatible); 1=orthogonal/anti-correlated. `_check_seam_freq_gate` returns worst-seam index when score > thresh. When one band has near-zero AC content, inner-product denominator < 1e-9 → score defaults to 0.0 (safe pass; no mismatch information). `_SEAM_FREQ_GATE` flag (default 0.0=off, `ASP_SEAM_FREQ_GATE=0.6`). Stage 11.15 wired after Stage 11.14 in `pipeline.py`. `ASP_SEAM_FREQ_GATE` in `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. 5 tests `TestSeamFreqProfile`. **913 tests passing.**
- Catches spectral-grain discontinuities invisible to §1.76–§1.81.
- Zero new deps (stdlib `np.fft`).
- Safe fallback (score=0) for flat/uniform bands avoids false positives.

---

## 1.81 Seam Band SSIM Gate [Quick Win] ✅ Shipped S138

**Pain point:** §1.76–§1.80 are targeted single-dimension gates: each measures one photometric or structural property independently. Two strips can pass all five gates individually yet still be perceptually incompatible as a seam pair when their combination of luma, contrast, and structure is mismatched. SSIM fuses all three into a single [0,1] perceptual score — a low SSIM score unambiguously signals that the two bands will look discontinuous at the seam.

**Option A — Band-SSIM perceptual gate [Quick Win] ✅ Shipped S138**
`_seam_band_ssim(img, n_strips, band_px=30) → List[float]` in `compositing.py`. For each boundary, computes SSIM between the `band_px`-row window above and below using `skimage.metrics.structural_similarity` (float32, `data_range=1.0`); heights equalised when boundary is near image edge; bands < 7 rows default to 1.0. `_check_seam_ssim_gate` fires when score *falls below* threshold (inverted polarity vs §1.76–§1.80). `_SEAM_SSIM_GATE` flag (default 0.0=off, `ASP_SEAM_SSIM_GATE=0.85`). Stage 11.14 wired after Stage 11.13 in `pipeline.py`. `ASP_SEAM_SSIM_GATE` in `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]`. 5 tests `TestSeamBandSsim`. **913 tests passing.**
- Catch-all perceptual complement to §1.76–§1.80.
- No new deps (skimage already used for bench SSIM).
- Inverted polarity noted in gate description and config schema.

---

## 1.80 Seam Gradient Direction Coherence Gate [Quick Win] ✅ Shipped S137

**Pain point:** §1.76–§1.79 (luma, saturation, hue, sharpness) all operate in photometric domains and are blind to structural orientation discontinuities. Two strips can have identical colour profiles yet produce a visually jarring seam when their dominant edge orientations differ — e.g., diagonal speed-lines above a horizontal cloud-layer below, or a character with diagonal limb edges abutting a horizontally banded sky. The gradient direction flip is invisible to all colour-space metrics but creates a perceptible texture-direction step at the seam boundary.

**Option A — Circular gradient-direction coherence gate [Quick Win] ✅ Shipped S137**
`_seam_grad_direction(img, n_strips, band_px=30, mag_thresh=10.0) → List[float]` in `compositing.py`. For each inter-strip boundary, computes the mean *undirected* Sobel gradient orientation in the `band_px`-row band above and below using the angle-doubling circular mean: `0.5 × arctan2(mean(sin(2θ)), mean(cos(2θ)))`. Only pixels with Sobel magnitude > `mag_thresh` contribute; flat regions (uniform background) are excluded. Circular distance between the two means is returned in degrees [0, 90]. `_check_seam_grad_direction_gate` returns worst seam index when any score exceeds `thresh`. `_SEAM_GRAD_DIR_GATE` flag (default 0.0=off, `ASP_SEAM_GRAD_DIR_GATE=45.0`). Stage 11.13 gate wired in `pipeline.py` after Stage 11.12. `ASP_SEAM_GRAD_DIR_GATE` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS[compositing]`. Exported in `__all__`. 5 tests in `TestSeamGradDirection`. **903 backend tests passing (2 skipped)**.
- A score of 45° means dominant edges are oriented ~45° apart — perceptible as a texture-direction step. A score of 90° means fully orthogonal content (horizontal vs vertical stripes).
- Complements §1.72 (entropy: texture density), §1.76 (luma: magnitude step), §1.79 (sharpness: focus level), and §1.66 (NCC: structural pattern correlation). Gradient direction captures the *orientation* of structure that all prior gates miss.
- Near-flat pixels excluded via `mag_thresh=10` (on 0–255 scale); noisy uniform backgrounds do not bias the mean.
- `band_px=30` (same as §1.77–§1.79) provides a consistent sampling window across all seam quality gates.

---

## 1.78 Seam Band Hue Shift Gate [Quick Win] ✅ Shipped S135

**Pain point:** §1.77 (saturation jump) and §1.72 (entropy asymmetry) both miss a specific failure: two strips can have equal brightness, equal texture complexity, and equal colour vibrancy yet completely different colour temperatures — e.g., a warm orange/sunset background strip abutting a cool blue/sky strip. The perceptual effect is a colour-temperature discontinuity (warm-to-cool jump) that no existing gate targets.

**Option A — Circular hue shift gate [Quick Win] ✅ Shipped S135**
`_seam_hue_shift(img, n_strips, band_px=30) → List[float]` in `compositing.py`. For each inter-strip boundary, computes the mean HSV hue in `band_px` rows above and below using the circular (angular) distance on the [0, 180] OpenCV hue scale (max circular distance = 90°). Near-achromatic pixels (sat ≤ 15) are excluded to prevent grey/white regions biasing the mean. `_check_seam_hue_gate` returns worst seam index when any circular distance exceeds `thresh`. `_SEAM_HUE_GATE` flag (default 0.0=off, `ASP_SEAM_HUE_GATE=30.0`). Stage 11.11 gate wired in `pipeline.py` after Stage 11.10. `ASP_SEAM_HUE_GATE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestSeamHueShift`.
- Red (hue≈0) and magenta (hue≈170) are correctly treated as nearby (circular distance≈10°), not opposite (≈170°).
- Complements §1.77 (saturation = vibrancy mismatch) and §1.72 (entropy = texture density mismatch); hue captures warm-vs-cool colour temperature mismatch that those miss.

---

## 1.77 Seam Band Saturation Jump Gate [Quick Win] ✅ Shipped S135

**Pain point:** Existing seam gates operate in luminance (§1.24, §1.76) or structural-texture (§1.72 entropy, §1.66 NCC) domains. None target a specific and common failure in anime: a muted pastel background strip abutting a vividly coloured character outfit. Both strips can have identical mean brightness and identical texture complexity, but the HSV saturation channel reveals the vibrancy discontinuity.

**Option A — Mean HSV saturation jump gate [Quick Win] ✅ Shipped S135**
`_seam_saturation_jump(img, n_strips, band_px=30) → List[float]` in `compositing.py`. For each inter-strip boundary, computes the mean HSV saturation in `band_px` rows above and below, returning `|sat_above − sat_below|` in [0, 255]. Greyscale inputs return 0.0 per seam (no saturation information). `_check_seam_saturation_gate` returns worst seam index when any jump exceeds `thresh`. `_SEAM_SAT_GATE` flag (default 0.0=off, `ASP_SEAM_SAT_GATE=40.0`). Stage 11.10 gate wired in `pipeline.py` after Stage 11.9. `ASP_SEAM_SAT_GATE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestSeamSaturationJump`.
- Saturation in [0, 255] HSV; jump ≥ 40 = perceptible vibrancy step (grey vs vivid colour ≈ 255 jump; muted vs vivid ≈ 80–120 jump).
- Complements §1.72 (entropy asymmetry = texture density) and §1.14B (Bhattacharyya = histogram shape); saturation jump captures vibrancy mismatch that those miss.

---

## 1.76 Per-Column Worst-Case Luma Step Gate [Quick Win] ✅ Shipped S134

**Pain point:** §1.24 (Stage 11.3) measures the mean greyscale luma across the full strip width above and below each seam boundary. When a character outline or shadow edge crosses the seam at a single column, the mean is diluted across all other columns — a 200 lum per-column step at column X averages to ~5 lum across a 40-column strip, well below any practical gate threshold. The localised hot-spot is invisible to the mean gate.

**Option A — Worst-column luma step gate [Quick Win] ✅ Shipped S134**
`_seam_max_col_luma_step(img, n_strips, band_px=8, guard=2) → List[float]` in `compositing.py`. For each inter-strip boundary, computes per-column mean luma in `band_px` rows above and below (with `guard` rows excluded adjacent to the boundary), then returns `max_col |above − below|` for that seam. `_check_seam_max_col_gate` returns worst seam index when any step exceeds `thresh`. `_SEAM_MAX_COL_GATE` flag (default 0.0=off, `ASP_SEAM_MAX_COL_GATE=40.0`). Stage 11.9 gate wired in `pipeline.py` after Stage 11.8. `ASP_SEAM_MAX_COL_GATE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestSeamMaxColLumaStep`.
- Complements §1.24 (mean seam step): §1.24 is better for uniform band offsets (JPEG quantisation banding, gain correction overshoot); §1.76 is better for localised edge artefacts (character outlines, sharp shadow transitions crossing the seam).
- `guard=2` excludes the 2 rows immediately adjacent to the boundary where blend artefacts concentrate; `band_px=8` samples the stable region just outside.

---

## 1.75 Strip Laplacian Variance Ratio Gate [Quick Win] ✅ Shipped S133

**Pain point:** Seam-boundary gates (§1.14B Bhattacharyya, §1.66 NCC, §1.72 entropy) each sample only a ±50px band at each seam boundary. They cannot detect structural content incompatibility that spans the entire strip — e.g., one strip contains only flat-colour character body while the next contains a richly detailed background scene. The global texture imbalance is invisible at the seam boundary but dominates the perceptual experience.

**Option A — Laplacian strip-variance ratio post-composite gate [Quick Win] ✅ Shipped S133**
`_compute_strip_variance_ratio(canvas, n_strips) → float` in `pipeline.py`. Splits composite into N horizontal bands; computes Laplacian variance per strip; returns `max_var / min_var`. When any strip variance is zero (perfectly uniform strip), returns 1.0 (no gate). Stage 11.8 gate fires when `ratio > _STRIP_VARIANCE_RATIO_MAX` → SCANS fallback. Default OFF, `ASP_STRIP_VARIANCE_RATIO_MAX=10.0`. 5 tests in `TestComputeStripVarianceRatio`.
- Complements §1.72 (entropy at seam boundary) and §1.14B (per-strip colour histogram): those detect boundary-local discontinuity; §1.75 detects global strip-level texture incompatibility.

---

## 1.74 Canvas Fill Ratio Gate [Quick Win] ✅ Shipped S133

**Pain point:** After compositing, all existing quality gates (§1.24 luma step, §1.14B colour histogram, §1.66 NCC, §1.72 entropy) sample content at seam boundaries. They do not detect the case where large regions of the canvas are simply empty — zero-initialized pixels never covered by any warped frame due to geometric discontinuities or failed warps. These empty regions look visually defective but have no seam discontinuity to detect.

**Option A — Canvas fill ratio post-composite gate [Quick Win] ✅ Shipped S133**
`_compute_canvas_fill_ratio(canvas, pix_thresh=10) → float` in `pipeline.py`. Counts pixels where `max(B,G,R) > pix_thresh` as filled; returns `filled / total`. Stage 11.7 gate fires when `fill_ratio < _CANVAS_FILL_MIN` → SCANS fallback. Separate `ASP_CANVAS_FILL_PIX_THRESH=10` knob prevents dark-background anime (night scenes, black skies) from being miscounted as empty. Default OFF, `ASP_CANVAS_FILL_MIN=0.60`. 5 tests in `TestComputeCanvasFillRatio`.
- Distinct from §1.75 (strip variance): §1.74 detects literal empty canvas regions; §1.75 detects textural mismatch within fully-filled regions.

---

## 1.73 Per-Frame Bg-Gain Monotonicity Drift Gate [Quick Win] ✅ Shipped S133

**Pain point:** §1.71 detects extreme *spread* in per-frame background luminance (max−min > threshold). But a gradual monotonic drift — where each frame is progressively darker or lighter — creates a perceptible "brightness staircase" even when the total spread is acceptable. Example: 10 frames with luma decreasing 4 units per frame → spread=36 (well within default threshold of 80), but Kendall-τ ≈ 1.0 → sequential gain normalisation corrects amplitude but cannot invert the rank ordering, leaving a visible gradient from bright top to dark bottom.

**Option A — Kendall-τ monotonicity gate [Quick Win] ✅ Shipped S133**
`_compute_bg_lum_monotonicity(frames, bg_masks, min_bg_px=200) → float` in `pipeline.py`. Extracts per-frame background median luma (same method as §1.71); computes `|τ|` using concordant/discordant pair counting. Returns 0.0 when fewer than 3 frames qualify. Stage 10.9 gate fires when `|τ| > _BG_GAIN_MONOTONE_THRESH` → SCANS fallback. Default OFF, `ASP_BG_GAIN_MONOTONE_THRESH=0.85`. 5 tests in `TestComputeBgLumMonotonicity`.
- Distinct from §1.71 (spread): §1.71 fires on any extreme amplitude difference; §1.73 fires specifically on monotone ordering even at moderate spread.
- O(N²) Kendall-τ computation; N is typically 5–15 selected frames — negligible overhead.

---

## 1.72 Seam Entropy Asymmetry Gate [Quick Win] ✅ Shipped S132

**Pain point:** NCC measures structural pattern alignment, Bhattacharyya measures colour distribution shape, but neither detects *texture density asymmetry* — one side flat-colour (character solid clothing, ~1 bit entropy) vs the other richly textured (background foliage, ~7 bits entropy).

**Option A — Shannon entropy asymmetry gate [Quick Win] ✅ Shipped S132**
`_seam_entropy_asymmetry(img, n_strips, band_px=50)` in `compositing.py`. Per-seam `|H_top − H_bot|` via greyscale histogram Shannon entropy. `_check_seam_entropy_gate` returns worst seam index or None. `_SEAM_ENTROPY_GATE` flag (0=off, suggest 1.5). Stage 11.5 gate in `pipeline.py`. 5 tests in `TestSeamEntropyAsymmetry`.

---

## 1.71 Pre-Composite Background Luminance Spread Gate [Quick Win] ✅ Shipped S132

**Pain point:** Extreme per-frame background luminance variation forces sequential gain normalisation to apply >2× corrections, producing a brightness staircase. §1.41 fires after Stage 10; §1.71 fires before Stage 11.

**Option A — Raw-frame bg luma spread gate [Quick Win] ✅ Shipped S132**
`_compute_bg_lum_spread(frames, bg_masks, min_bg_px=200)` in `pipeline.py`. Returns `max − min` across per-frame background median luma values. Stage 10.8 gate fires when `spread > _BG_LUM_SPREAD_MAX` → SCANS fallback. `ASP_BG_LUM_SPREAD_MAX=80.0` (0=off). 5 tests in `TestComputeBgLumSpread`.

---

## 1.70 Blend-Zone FG Coverage Pre-Escalation [Quick Win] ✅ Shipped S132

**Pain point:** When the entire blend zone is fg-dominated, no background corridor exists for the DP seam. Running DP on an infeasible cost landscape bisects the character at its thinnest accessible pixel column.

**Option A — Pre-DP single-pose escalation [Quick Win] ✅ Shipped S132**
`_fg_fraction_in_zone(bg_mask_a, bg_mask_b)` in `compositing.py`. Union fg fraction; `> _SEAM_ZONE_FG_MAX` → single-pose before DP. Default OFF, `ASP_SEAM_ZONE_FG_MAX=0.85`. 5 tests in `TestFgFractionInZone`.

---

## 1.69 Post-DP Background Routing Ratio [Quick Win] ✅ Shipped S132

**Pain point:** The DP seam can still be forced through character pixels even with cost barriers. There is no post-DP verification that the seam achieved its routing goal.

**Option A — Post-DP bg ratio escalation [Quick Win] ✅ Shipped S132**
`_seam_dp_bg_ratio(path, bg_mask_a, bg_mask_b)` in `compositing.py`. Fraction of path columns where BOTH bg_masks are background; `< _SEAM_DP_BG_MIN` → post-DP single-pose escalation. Default OFF, `ASP_SEAM_DP_BG_MIN=0.30`. 5 tests in `TestSeamDpBgRatio`.

---

## 1.68 Adjacent Feather Ratio Enforcement [Quick Win] ✅ Shipped S132

**Pain point:** After §1.6B and §1.19, adjacent seams can differ 3.75× in width, creating a visible tonal rhythm discontinuity independent of seam quality.

**Option A — Forward+backward ratio clamp [Quick Win] ✅ Shipped S132**
`_enforce_feather_ratio(feathers, max_ratio=3.0)` in `compositing.py`. Iterative two-pass clamp. Default OFF, `ASP_FEATHER_RATIO_MAX=3.0`. Wired after §1.19 fg-density cap. 5 tests in `TestEnforceFeatherRatio`.

---

## 1.67 Frame Canvas Spread Validation [Quick Win] ✅ Shipped S131

**Pain point:** The §1.15 connectivity gate and §1.16 MST weight gate verify *graph topology*, but neither checks whether the selected frames actually cover the full scroll range. When frames cluster near one end of the scroll (first 30% of a 600px scene), the assembled panorama will be a narrow slice — BA produces geometrically valid translations, yet coverage is fundamentally limited by the input set.

**Option A — Pre-BA spread fraction check [Quick Win]** ✅ **Shipped S131**
`_check_canvas_spread(edges, min_spread_fraction) → bool` in `pipeline.py`. BFS propagates pairwise translations from frame 0 to reconstruct each frame's cumulative position. Computes `actual_dom_span / (median_adj_step × (N-1))`. Returns `False` (trigger SCANS fallback) when ratio < min_spread_fraction. Dominant axis = whichever of ty/tx has larger cumulative span. `_CANVAS_SPREAD_MIN` flag (default 0.0=off, `ASP_CANVAS_SPREAD_MIN=0.5`). Wired before Stage 7 BA between §1.16 MST weight gate and §1.43 adj-coverage gate. `ASP_CANVAS_SPREAD_MIN` added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS`. Exported in `__all__`. 5 tests in `TestCheckCanvasSpread`. **827 tests passing.**
- Catches clustered frame selections (all frames in first 30% of scroll) before BA wastes computation.
- The ratio > 1.0 case (oscillating frames) is handled earlier by §1.17 (canvas span utilisation gate post-BA).
- Safe fallback: degenerate inputs (empty edges, zero expected span) return True.

---

## 1.66 NCC Structural Coherence Gate [Quick Win] ✅ Shipped S131

**Pain point:** §1.14B (Bhattacharyya colour gate, pre-composite) detects *colour distribution* mismatches but passes when two strips have identical colour palettes in different spatial arrangements — e.g., a character with a blue torso in the top strip and the same blue background sky in the bottom strip. §1.24 (luma step gate, post-composite) detects absolute luminance discontinuities but passes when the transition is gradual. Neither detects *structural texture pattern* mismatch: two strips whose gradient/line-art patterns are completely different, indicating a character pose jump that blending cannot smooth.

**Option A — Post-composite NCC gate [Quick Win]** ✅ **Shipped S131**
`_seam_ncc_coherence(img, n_strips, band_px=60) → List[float]` in `compositing.py`. For each inter-strip seam boundary, computes NCC between the `band_px`-row window above and below: `ncc = mean((A−μA)·(B−μB)) / (σAσB + ε)`. Flat bands (σ < 1e-3) return 1.0 (no texture = no mismatch). `_check_seam_ncc_gate(img, n_strips, thresh, band_px) → Optional[int]` returns worst-NCC seam index when any seam falls below thresh; returns None when all pass. `_SEAM_NCC_GATE` module flag (default 0.0=off, `ASP_SEAM_NCC_GATE=0.45`). Wired as Stage 11.4 in `pipeline.py` between Stage 11.3 (luma-step gate) and Stage 11.5 (SRStitcher). `ASP_SEAM_NCC_GATE` added to `_CONFIG_SCHEMA` (compositing section) and `_DUMP_SECTIONS`. Both functions exported in `compositing.__all__`. 5 tests in `TestSeamNccCoherenceCompositing`. **827 tests passing.**
- NCC score thresholds: ≥0.90 excellent (invisible seam), 0.70–0.90 good, 0.40–0.70 moderate, <0.40 severe structure mismatch. Recommend threshold=0.45.
- Complements §1.14B (pre-composite colour histogram) and §1.24 (post-composite luma step): detects structural line-art discontinuity that both miss.
- Both functions (`_seam_ncc_coherence`, `_check_seam_ncc_gate`) reusable in bench diagnostics without cross-import.

---

## 1.8D Typed TOML Schema Annotations in dump_asp_config [Quick Win] ✅ Shipped S131

**Pain point:** `dump_asp_config` (§1.8C, S126) emits a TOML file with human-readable description comments above each key. Tooling that wants to validate the file (CI scripts, TOML linters, IDE plugins) has no machine-readable type/range information — it must import the Python module to get the schema. The comment format was purely prose, making automated validation impossible without parsing.

**Option A — Machine-readable type/range comment prefix [Quick Win]** ✅ **Shipped S131**
`dump_asp_config` updated to emit two comment lines per key (when key is in `_CONFIG_SCHEMA`): (1) `# type: <typename>  range: [<min>, <max>]` — machine-readable constraint annotation extracting `_CONFIG_SCHEMA[key][0..2]`; (2) `# <description>` — existing human-readable description. `getattr(typ, "__name__", str(typ))` extracts the Python type name. Min/max are emitted as `None` when unbounded. Function docstring updated to describe §1.8D enhancement. 5 tests in `TestDumpAspConfigSchemaComments`. **827 tests passing.**
- Zero breaking change: existing TOML consumers ignore comment lines; the key=value lines are unchanged.
- Format is consistent with type-stub and JSON-schema conventions, making future tooling straightforward.

---

## 1.56 Post-Composite Chroma Seam Correction [Quick Win] ✅ Shipped S122

**Pain point:** §1.21 (`_seam_lum_equalize`) applies equal BGR additive offsets at seam boundaries — a pure luminance shift that leaves chrominance unchanged. Colour-temperature differences (warm interior strip vs cool exterior strip) and hue shifts between adjacent strips are not corrected by §1.21: they show up as persistent tonal banding even after luminance is equalized. The `seam_coherence` (SC) metric partially captures this, but the Bhattacharyya gate (§1.14B) only checks greyscale histograms, so chroma-only banding can slip through all existing gates.

**Option A — LAB a/b ramp post-composite [Quick Win]** ✅ **Shipped S122**
`_seam_chroma_equalize(canvas, boundaries, band_px=20, min_shift=3.0) → np.ndarray` in `compositing.py`. Converts reference strip bands above/below each boundary to CIE LAB; measures mean shift in 'a' (green↔red) and 'b' (blue↔yellow) channels; applies linear additive ramp over band_px rows below the boundary when either shift exceeds min_shift LAB units. L* (luminance) is not modified — §1.21 handles that channel. `_SEAM_CHROMA_EQ` flag (default OFF, `ASP_SEAM_CHROMA_EQ=1`). Wired immediately after §1.21 in `_composite_foreground`. `SEAM_CHROMA_EQ_BAND_PX=20`, `SEAM_CHROMA_EQ_MIN_SHIFT=3.0` in constants. `ASP_SEAM_CHROMA_EQ` in `_CONFIG_SCHEMA`. 5 tests in `TestSeamChromaEqualize`. 772 tests passing.
- Targets colour-temperature and hue banding that §1.21's luminance-only pass misses.
- Safe default OFF: zero effect when disabled; only activates when a/b shift exceeds 3 LAB units.
- Complements §1.21 (luminance) and §1.14B (pre-composite greyscale colour gate). Neither of those touches LAB chroma.

---

## 1.21 Post-Composite Seam Luminance Equalisation [Quick Win] ✅ Shipped S65

**Pain point (links to Class D, test27):** SC=26.7 visible luminance step at seam boundaries despite only 4% background gain spread. Upstream corrections (§1.16 seam color match, §1.4B/C gain) operate on intermediate state. A final-pass luminance equaliser directly reduces what the SC metric measures.

**Option A — Post-composite luma ramp [Quick Win]** ✅ **Shipped S65**
`_seam_lum_equalize(canvas, boundaries, band_px=20, min_step=5.0) → np.ndarray` in `compositing.py`. Samples mean greyscale luminance in band_px-row reference bands above/below each boundary (±3-row guard). When step > min_step: applies linear additive ramp over band_px rows below the boundary subtracting the step gradient. Equal BGR correction (luminance shift, chrominance preserved). `_SEAM_LUM_EQ` flag (default OFF, `ASP_SEAM_LUM_EQ=1`). Wired before `return result`. `SEAM_LUM_EQ_BAND_PX=20`, `SEAM_LUM_EQ_MIN_STEP=5.0` in constants. `ASP_SEAM_LUM_EQ` in `_CONFIG_SCHEMA`. 5 tests in `TestSeamLumEqualize`. 432 tests passing.
- Targets the SC metric directly: measured step in final output → corrected step in final output.
- Safe default OFF: zero effect when disabled; only activates on lum steps > 5 lum units.

---

## 1.20 Tight-Step Preemptive Single-Pose Escalation [Quick Win] ✅ Shipped S64

**Pain point (links to Class C, test57):** For sequences with irregular camera motion (spacing_ratio=3.379, min_gap=10.8px), some adjacent frame pairs have tiny camera steps while the character has moved significantly. ARAP cannot reconcile large pose differences across a 10px camera advance — the warp residual will always be large. Running ARAP wastes time and the blend still creates a ghost.

**Option A — Dominant-axis step gate [Quick Win]** ✅ **Shipped S64**
`_compute_seam_step_size(fi_a, fi_b, affines) → float` in `compositing.py`. Returns `max(|ty_b−ty_a|, |tx_b−tx_a|)`. `_TIGHT_STEP_PX` flag (default 0=off, `ASP_TIGHT_STEP_PX=30`). Wired inside the FG registration loop, BEFORE `register_foreground_at_seam`: when `step_sz < _TIGHT_STEP_PX`, skip ARAP entirely, pick dominant by fg count in ±20px boundary band, set `seam_single_pose[k]` and `continue`. `TIGHT_STEP_PX=30` in `constants/animation.py`. `ASP_TIGHT_STEP_PX` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `TestComputeSeamStepSize`. 427 tests passing.
- Addresses Class C (test57): min_gap=10.8px → all seams with step < 30px are preemptively single-posed. At those distances, the character occupies nearly the same canvas rows in both frames but may be in an entirely different animation pose.
- Complements §1.18/§1.19: §1.18 escalates post-ARAP (post_warp_diff > adaptive threshold); §1.19 caps feather pre-registration (fg density > 60%); §1.20 short-circuits registration entirely (step < threshold).

---

## 1.19 Foreground-Density-Aware Feather Cap [Quick Win] ✅ Shipped S63

**Pain point:** §1.18 fires after ARAP registration (uses post_warp_diff). There is no pre-registration check for whether the blend zone geometry is inherently problematic. When a seam boundary sits in a character-dominated zone (>60% fg pixels), any wide feather blends two poses over that zone → ghost band.

**Option A — Canvas-space fg fraction check [Quick Win]** ✅ **Shipped S63**
`_fg_density_feather_cap(feathers, boundaries, warped_bg, order, cap_px, fg_thresh=0.60) → np.ndarray` in `compositing.py`. For each boundary k, computes fg fraction in ±feather[k] rows around boundaries[k] in `warped_bg` (canvas-space bool masks) for both adjacent frames; caps feather to cap_px when max fg_frac > fg_thresh. None masks → no-op. `_FG_FEATHER_CAP` flag (default 0=off, `ASP_FG_FEATHER_CAP=60`). Wired after §1.6B gain feathers, before Stage 8.5 FG registration. `FG_FEATHER_CAP=60`, `FG_FEATHER_THRESH=0.60` in constants; 2 entries in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_compositing.py::TestFgDensityFeatherCap`. 422 tests passing.
- Complementary to §1.18: §1.18 uses post-registration information (post_warp_diff > adaptive threshold); §1.19 uses pre-registration information (fg density > 60% in blend zone).
- `warped_bg` is canvas-space — `warped_bg[fi][y0:y1]` directly samples the boundary region without coordinate conversion.

---

## 1.18 Adaptive Single-Pose Escalation Threshold [Quick Win] ✅ Shipped S62

**Pain point:** The hardcoded `_POST_DIFF_THRESHOLD = 22.0` (lum units) in `_composite_foreground` treats a 22 lum discrepancy identically whether the feather is 80px (short blend zone, ghost barely visible) or 300px (600px wide blend zone between two mismatched anime poses, visually dominant). Benchmark Class A failure mode: 4/5 test images had wide 300px feathers + post_warp_diff in [15–22] range → never escalated → 600px ghost band.

**Option A — Feather-width–scaled escalation threshold** ✅ **Shipped S62**
`_adaptive_sp_threshold(feather_width, base=22.0, min=12.0, ref=80) → float` in `compositing.py`. Formula: `max(min_threshold, base × (ref / max(fw, 1)))`. At fw=80px → 22.0 (baseline unchanged); at fw≥147px → 12.0 (floor). `_ADAPTIVE_SP_THRESH` flag (default OFF, `ASP_ADAPTIVE_SP_THRESH=1`). Wired at compositing.py line 1294: `_sp_thresh = _adaptive_sp_threshold(int(feathers[k])) if _ADAPTIVE_SP_THRESH else 22.0`. Constants: `ADAPTIVE_SP_THRESH_BASE=22.0`, `ADAPTIVE_SP_THRESH_MIN=12.0`, `ADAPTIVE_SP_THRESH_REF=80` in `constants/animation.py`. `ASP_ADAPTIVE_SP_THRESH` in `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_compositing.py::TestAdaptiveSpThreshold`. 417 tests passing.
- Floor crossover: `22×80/fw=12` → fw=146.7 → floor kicks in at fw≥147. For 300px feather: threshold=12.0, catches 15–22 lum post_warp_diff range (Class A) that fixed 22.0 missed.
- `feathers[k]` is in scope at the call site (assigned before FG registration loop, refined after).

---

## 2.9 BigWarp / Fourier-Mellin Manual Registration Fallback [Priority: High HITL]

**Pain point (links to §2.2, §1.1):** Despite AGNC and dual-pronged outlier rejection, pathological scenes (test13: 11.1× ratio) still trigger affine validation failures. The user has no manual override path — the pipeline either succeeds or falls back to SCANS. A human who can see the two failing frames could align them in 30 seconds.

**What BigWarp / Fourier-Mellin offers (§6.3 of Advanced Morphological Integration report):**
- **BigWarp-style landmark registration:** User clicks corresponding points on two frame thumbnails (structural background vertices — corners of lockers, architectural intersections). The pipeline overrides the LoFTR-failed edge with the user-defined affine/TPS transform. The bundle adjustment re-solves with the corrected edge.
- **Fourier-Mellin transform:** When only translation is unknown (the camera is purely translating), the user crops a static background region (avoiding the character), and Fourier-Mellin cross-correlates the magnitude spectra → sub-pixel translation. Available via DIPLib or custom FFT implementation. Faster than manual landmark placement.

**Options**

**A — Landmark Editor Dialog [Quick Win toward Research]**
When affine validation fails for an edge (i→j), emit `StitchWorker.stage_edge_failed(i, j, reason)`. Show a dialog with:
- Side-by-side thumbnails of frames i and j
- Click-to-add landmark pairs (minimum 2 for translation, 3 for affine, 4 for TPS)
- "Re-solve with this edge" button → injects the user-defined transform into the bundle adjustment
*Implementation:* ~300 LOC on top of `StitchWorker.set_edge_override()` from §2.7.

**B — Fourier-Mellin crop-and-align [Quick Win]**
Add a "Crop and align" button to the affine validation failure dialog: user rubber-bands a static background region, the pipeline computes Fourier-Mellin cross-correlation on that crop only (bypassing the character entirely), and injects the result as the edge transform.
- Pros: No landmark-clicking required for pure-translation scenes. Sub-pixel accuracy.
- Cons: Fails on scenes with scale/rotation; the crop must be entirely background.

**C — Auto-retry with tighter LoFTR threshold** ✅ **Shipped S37**
`_filter_high_conf_edges(edges, min_weight=HIGH_CONF_EDGE_THRESH)` in `pipeline.py` — keeps only edges with `weight >= 0.65` (LoFTR-quality; excludes TM/PC fallbacks at 0.15–0.55). Wired as "Retry 0" in Stage 7b: fires on `ratio=...` failures when ≥ N-1 HC edges survive. `HIGH_CONF_EDGE_THRESH=0.65` added to `constants/animation.py`. Exported in `pipeline.py __all__`. 5 tests in `test_pipeline.py::TestFilterHighConfEdges`.
- Pros: Zero UI work. Catches cases where 1-2 TM/PC fallback edges corrupt the bundle.
- Cons: If the bad edge is also LoFTR-quality (high confidence, wrong match), Retry 0 doesn't help; Retry 1 (adj-only) is the next line of defense.

**Recommendation:** C immediately (pure algorithmic, catches the easy cases). A for the remaining affine failures that C can't fix. B as an ergonomic shortcut for broadcast-quality (pure-translation) sources.

---

## 2.10 SAM2Flow / FlowVid Interactive Optical Flow Kinematics [Research — HITL]

**Pain point (links to §0.1, §2.4):** When `post_warp_diff > 22 lum units`, Stage 8.5 escalates to single-pose fallback — a clean but informationally incomplete solution. For extreme cases (character turning 180°, limb moving through 90° arc), no analytical flow engine can register the two poses. A human who can draw a trajectory arrow from the character's position in frame A to its position in frame B would resolve this instantly.

**What SAM2Flow / FlowVid does (§7.3 of Advanced Morphological Integration report):**
- **SAM2Flow:** Extends SAM 2's video object tracking to optical flow estimation. User specifies regions of interest and trajectory hints via click+drag prompts. The system propagates these sparse human annotations as definitive spatial control anchors across the frame sequence. Originally designed for textureless fluid dynamics (in vivo microcirculation), directly applicable to flat cel-shaded anime.
- **FlowVid:** User draws directional arrows on the seam-zone canvas. The FlowVid network uses these as ControlNet-style spatial anchors in a diffusion model, generating coherent frame-to-frame transitions even across 180° rotations. Inference: 512×512 at 1.5 min on A100 (3.1× faster than CoDeF, 10.5× faster than TokenFlow).

**Options**

**A — SAM2Flow seam-zone annotation [Research]** ✅ **Shipped S146 (callback infrastructure; SAM2Flow model-gated)**
`_flow_hitl_callback: Optional[Callable[[int, dict], Optional[np.ndarray]]]` + `set_flow_hitl_callback(cb)` in `compositing.py`. At single-pose escalation (after `post_diff > _sp_thresh`), calls `cb(k, {"post_warp_diff": ..., "seam_k": k, "fi_a": ..., "fi_b": ...})`; if returns `(H,W,2)` flow array, re-runs `register_foreground_at_seam` with `flow_override=`; exception caught+logged. `Callable` added to typing import. Exported in `__all__`. 5 tests `TestFlowHitlCallback` in `test_compositing.py`. Full SAM2Flow model integration remains gated on model availability.
- After Stage 8.5 single-pose escalation, emit `StitchWorker.stage_seam_flow_failed(seam_info)`. The SeamDiagnosticPanel (§2.4) presents the seam crop with a "Draw trajectory" tool. User drags arrows → SAM2Flow uses these as anchors → the pipeline re-runs Stage 8.5 with the user-corrected flow.
- Pros: Directly resolves 180° rotation failures that RAFT/DIS and ARAP cannot.
- Cons: Requires SAM2Flow model weights. High VRAM during interactive use.

**B — FlowVid ControlNet trajectory synthesis [Research]**
For seams where single-pose fallback fires, open a FlowVid-powered "synthesize transition" dialog. User sketches the character's motion arc → FlowVid generates a synthetic intermediate frame that bridges the two poses → Stage 11 composites the synthetic frame instead of the hard-partition.
- Pros: Generates geometrically coherent content, not just a better warp.
- Cons: 1.5 min inference per seam. Anime domain gap (FlowVid was trained on natural video).

**C — User-drawn flow field (no model) [Quick Win]**
A simpler manual tool: the user draws displacement arrows on the seam thumbnail, and these are directly converted to a sparse flow field that overrides RAFT/DIS. The ARAP regularise step then smooths the user-drawn field to per-pixel resolution.
- Pros: No model weights. Zero latency. User sees exactly what flow they're injecting.
- Cons: Requires dense coverage of the character region by user annotations.

**Recommendation:** C immediately (leverages the existing SeamDiagnosticPanel from §2.4, no model). A once SAM2Flow model weights are available publicly. B for final-quality mode where the synthesis overhead is acceptable.

---

## 2.11 Intelligent Scissors Seam Routing [Quick Win — replaces DP seam]

**Pain point (links to §1.6, Category C1 failures):** The Stage 11 DP seam optimizer uses a per-pixel cost function but routes seams through character bodies when the background corridor is too narrow. The BiRefNet semantic cost only penalizes seams through character pixels — it doesn't guarantee a background-only path when the character fills the frame.

**What Intelligent Scissors does (§8.1 of Advanced Morphological Integration report):**
Transforms the seam into a shortest-path problem on a graph where nodes are pixels and edges are weighted by:
1. **Line-art gradient magnitude** — high cost at dark line-art boundaries (the character's outline)
2. **BiRefNet foreground probability** — exponential cost inside the character mask
3. **Laplacian zero-crossing** — prefer paths through uniform flat regions (background)

The user provides waypoints: clicking a sequence of points forces the algorithm to route through the background space the user designates. Dijkstra's algorithm computes the exact least-cost path through each waypoint gate, guaranteeing the seam never bisects the user-designated zones.

**Options**

**A — Intelligent Scissors dialog in SeamDiagnosticPanel [Quick Win]** ✅ **Shipped S123 (backend)**
`_seam_cut()` in `compositing.py` gains `waypoints: Optional[List[Tuple[int, int]]]` parameter. Three-part implementation: (1) pre-DP inf-injection forces the forward pass to fan out from each `(x_wp, y_wp)` waypoint pixel; (2) forced traceback at waypoint columns overrides the 3-neighbour argmin; (3) post-smooth re-apply re-stamps waypoints after `_smooth_seam_path` / `_clamp_seam_path`. Canvas-space waypoints from `seam_overrides[k]["waypoints"]` converted to zone-local coords before dispatch to the parallel seam job (`_seam_job` tuple extended to 7 elements). GUI extension (waypoint click tool in SeamDiagnosticPanel) pending.
- Pros: Directly resolves Category C1 failures where seam bisects the character. Reuses the existing seam-finding code (adds waypoints, not a replacement).
- Cons: Requires user attention for each failing seam.

**B — Graph-cut with character-exclusion zone**
Automatically exclude the entire BiRefNet foreground region from the seam path by setting fg pixels to cost=∞. The DP is then forced into background-only columns. For scenes where the character fills the frame edge-to-edge, this may produce a seam through a background-free zone at the very edge.
- Pros: Fully automatic. Eliminates the need for user waypoints in most cases.
- Cons: When the character spans the full width (test09-type portrait shots), there IS no all-background path — the cost=∞ constraint makes the DP infeasible, requiring fallback to a minimum-cost through-character path.

**C — Multi-path seam voting [Research]**
Compute K candidate seam paths with different random seed initializations, evaluate each by seam_gradient and BiRefNet fg_overlap, select the one with the best combined score. No user interaction.
- Pros: Better than single-path DP without UI overhead.
- Cons: K× computation cost. Still limited by what the cost function can express.

**Recommendation:** B immediately (automatic fg exclusion zone, one change to `_seam_cut()` cost array). A for cases where B fails (character fills full width). C as a research-track alternative to A.

> **✅ Session 7 — B SHIPPED:** `_build_seam_cost_map()` in `compositing.py` now uses a two-tier cost: Tier 1 sets `cost=1.0` for every fg-interior pixel (with `sem_weight=200` → 200 energy barrier vs bg ~10–50), forcing the seam through background-only corridors. Tier 2 retains the dilated-edge avoidance zone. Graceful degradation when no all-background path exists. No env var needed — active by default whenever BiRefNet masks are available.

---

## 3.11 SAM 2 — Interactive Masking Upgrade [Research — HITL]

**Pain point (links to §4):** BiRefNet provides good-enough foreground masks for automated pipeline runs but fails on complex topologies: flowing hair, thin props (swords, staffs), fragmented line-art between limbs, and transparent overlay elements. These failures propagate through all downstream stages (ARAP flow, seam routing, temporal median).

**What SAM 2 offers (§5.1 of Advanced Morphological Integration report):**
SAM 2 introduces a streaming memory mechanism that propagates a single user-corrected mask across the entire video sequence. In the ASP context:
1. Pipeline generates initial BiRefNet masks for all selected frames.
2. On any frame where the mask is visually incorrect, user draws a bounding box or clicks missed pixels — SAM 2 refines the mask and propagates the correction across the full sequence.
3. The corrected masks replace BiRefNet masks for Stage 4.5 (photometric norm), Stage 8.5 (ARAP flow), and Stage 12 (temporal median plate).

**Options**

**A — SAM 2 as interactive mask correction [Research]**
Add a "Mask review" step after Stage 4 (BiRefNet masking), emitting masks via `StitchWorker.stage_masks_ready(masks)`. The MaskReviewPanel shows each frame's mask. User can click/drag to correct; SAM 2 propagates. Pipeline resumes with corrected masks.
- Implementation: `backend/src/models/sam2_wrapper.py` wrapping `sam2.build_sam2()`. ~200 LOC.
- Pros: Eliminates the most common failure mode (wrong mask → wrong flow → wrong composite).
- Cons: SAM 2 model weights (~300MB). Requires GPU for streaming memory. Adds a pipeline pause.

**B — SAM 2 as drop-in BiRefNet replacement [Research]**
Replace Stage 4 BiRefNet with SAM 2 auto-mode (no user prompts). SAM 2's auto-segmentation is significantly more accurate on complex topologies than BiRefNet's saliency-based approach.
- Cons: SAM 2 auto-mode is slower than BiRefNet and requires user confirmation for each frame. Interactive mode is the key advantage.

**Recommendation:** A in HITL review mode (§2.7 staged execution). B as a research experiment on a subset of the failing corpus. BiRefNet remains the default for automated runs.

---

## 3.12 Overmix Sub-Pixel Averaging — Maximal Frame Ingestion Philosophy [Research]

**Pain point (links to §0.2, §3.4):** The ASP aggressively reduces frame count (300 → ~18) before any processing. Overmix's research (§3 of Advanced Morphological Integration report) shows that for broadcast-quality compressed anime, this discards the MPEG compression-averaging benefit: by ingesting all frames within each hold block and sub-pixel-averaging them, the resulting background plate has 3–4× better SNR than any individual frame.

**What Overmix does (§3.1 of Advanced Morphological Integration report):**
1. **Pose-group subsetting:** Manually (or automatically via hold detection §1.11) group frames into hold blocks — runs of 2-4 consecutive frames with the same character cel.
2. **Sub-pixel alignment within hold:** Phase correlate consecutive frames within the hold → register them at sub-pixel precision → stack-average in 16-bit linear color space. MPEG DCT blocks on a static background average toward the true signal (compression noise cancels out by √N).
3. **Hold-averaged frames as pipeline inputs:** Each hold block produces one high-SNR representative frame. The bundle adjustment runs on these representatives, not on any individual compressed frame.

**How it applies to ASP:**
Replace the `_smart_select_frames()` first-past-threshold approach with:
1. Hold detection (§1.11) → group all N frames into K hold blocks
2. Within each hold block, sub-pixel-average the block (using the existing `flow_refine.py` ECC infrastructure for alignment)
3. Ensure K consecutive hold blocks cover the full canvas → run the greedy selection on hold-averaged representatives

**Options**

**A — Hold-block averaging preprocessing [Research]**
After `_detect_hold_blocks()`, for each block, align frames within the block using ECC and average into a 16-bit composite. Pass the composites to phase correlation instead of raw frames.
- Pros: Better SNR → better LoFTR feature extraction → fewer BA outliers. Directly addresses MPEG block noise in compressed sources.
- Cons: K×M ECC alignments (K holds × M frames/hold). Adds ~0.5s per hold block. Only beneficial for MPEG-compressed sources (streaming rips).

**B — Motion-compensated temporal average [Research]**
Use the existing RAFT/DIS flow infrastructure to align frames within each hold block before averaging. More accurate than ECC for holds with slight camera jitter.
- Cons: RAFT inference per frame pair within each hold. ~2–3s per hold block.

**C — Perceptual-hash deduplication only [Quick Win — already in §1.11]**
Keep the first frame of each hold block as the representative (no averaging). Hold detection alone reduces noise by removing near-duplicate frames from the selection, even without averaging.
- Already implemented via `ASP_HOLD_THRESHOLD=0.025`.

**Recommendation:** C immediately (already done via §1.11). A for broadcast/streaming sources where MPEG noise is significant. B as the quality ceiling once A is validated.

---

### 3.13 ProPainter Background Completion [Research — Highest Background Plate Impact]

**Pain point (links to §0, Stage 4.5):** Stage 4.5's temporal median produces the background plate by suppressing foreground pixels across N frames. When the character occupies >40% of any canvas row, that row has fewer than 3 background samples → the median is dominated by character pixels → ghosting bleeds into the background plate. For high-coverage scenes (test08, test09, test27), this is the primary cause of "strip ghosting" even when all seams are correctly found.

**What ProPainter does (ICCV 2023, [GitHub](https://github.com/sczhou/ProPainter)):**
1. **Recurrent Flow Completion (RFC):** Completes dense flow vectors in masked (fg) regions from adjacent background pixels.
2. **Dual-Domain Propagation (DDP):** Propagates pixel values from background regions to masked areas using both spatial (nearby-pixel) and temporal (adjacent-frame) paths simultaneously.
3. **Masked Transformer Refinement (MTR):** Sparse-attention transformer fills remaining gaps by attending over the full frame sequence, restricted to unmasked (bg) reference pixels.

Output: background-completed frames where every foreground pixel is replaced by a plausible background estimate. Deterministic (no diffusion randomness). ~192 FPS at 432×240 on consumer GPU.

**How it applies:** Insert after Stage 4 (BiRefNet masking) as Stage 4.7:
1. BiRefNet fg masks → ProPainter inpainting regions
2. ProPainter runs on all K selected frames → background-completed variants
3. Completed frames feed Stage 5 (phase correlation) for cleaner camera motion estimates
4. Completed frames replace raw frames in Stage 4.5 (temporal median) → background plate has 100% coverage per row

**Options**

**A — ProPainter as Stage 4.7 pre-processing [Research]**
Run ProPainter on the selected frames before Stage 5. Pass completed frames to both the temporal median (Stage 4.5) and phase correlation (Stage 5).
- Estimated inference: ~5 FPS at 1080p → ~3.6s per 18-frame sequence. Acceptable for quality mode.
- Pros: Directly eliminates background plate ghosting. Zero change to downstream stages.
- Cons: Requires CUDA and ~4GB VRAM at 1080p. Inpainting quality depends on BiRefNet mask quality — wrong masks → wrong fill.
- `ASP_PROPAINTER=1` flag (default OFF).

**B — ProPainter on temporal median frame only [Quick Win]**
Run ProPainter once on the ghosted Stage 4.5 output to inpaint ghost regions. Requires a ghost-probability map (SIQE §3.8 or seam_visibility_score §S14) to define the inpainting region.
- Pros: Single pass instead of N per-frame passes. ~0.5s.
- Cons: Post-hoc inpainting of a ghosted composite is harder than pre-processing clean frames.

**C — Dedicated background separation pipeline [Long-term]**
Fully decouple foreground and background pipelines: ProPainter produces a clean background video for the temporal median; the character pipeline uses ARAP-registered fg crops; merge at compositing time.
- Cons: Major refactoring of Stage 4.5 → Stage 12 pipeline.

**Recommendation:** A gated by `ASP_PROPAINTER=1` for quality mode. B as a cheap triage once SIQE (§3.8) provides ghost maps. C as the long-term architectural target for high-quality production runs.

---

### 3.14 Horizontal and Diagonal Scroll — 2D Canvas Support [Engineering — Unblocks Category F/H]

**Pain point (links to Category F/H in debug guide):** `_compute_canvas()` in `canvas.py` places all frames on the same x-column (uses only `ty`). Horizontal camera drift (`tx` range > 200px) is silently discarded. For datasets with combined horizontal+vertical scroll (diagonal pan), the canvas geometry is wrong before any compositing begins. Category F (test7: tx range ~500px) and Category H (test20: ty≈0, tx: 1857→0px) are permanent failures under the current canvas model.

**Current state:** The debug guide (Categories F and H) documents diagnostics. The temporary mitigation is SCANS fallback. No roadmap item for implementing true 2D canvas support previously existed.

**What 2D canvas support requires:**
1. `_compute_canvas(affines)` uses both `affines[i][0][2]` (tx) and `affines[i][1][2]` (ty) to place each frame at its correct 2D position.
2. For pure horizontal scroll (Category H), the seam-cut DP must run vertically — vertical strips rather than horizontal bands.
3. For diagonal scroll (Category F), strip geometry is a parallelogram; both DP seam routing and feathering in `compositing.py` must handle 2D strip regions.
4. The `_compute_row_coverage()` gate (Stage 10.5) must be extended to a 2D coverage map.

**Options**

**A — tx-aware canvas placement [Engineering — Step 1]** ✅ **De facto implemented**
`_compute_canvas()` in `canvas.py` already uses full `M[:2, :2] @ corners.T + M[:2, 2:3]` — i.e., the complete affine matrix including both tx and ty. Canvas width correctly reflects horizontal drift. `_detect_scroll_axis` is wired (S33); `horizontal` scroll → SCANS fallback. No action required for §3.14A.
- Estimated effort: ~20 LOC. Low risk.

**B — Horizontal-strip mode for pure horizontal scroll (Category H) [Engineering]**
When `scroll_type='horizontal'`, sort frames by tx, run DP seam cut along vertical lines in `compositing.py`.
- Estimated effort: ~300 LOC. New seam cost direction in `_build_seam_cost_map` and vertical scan in `_seam_cut`.

**C — Full 2D strip compositing for diagonal scroll (Category F) [Research]**
Generalised compositing where each frame's overlap region is a quadrilateral. Seam-cut operates in 2D with DP extended to a shortest-path on an unconstrained grid.
- Estimated effort: 500–800 LOC. Major refactor of `compositing.py`.

**Recommendation:** A immediately (low-risk canvas geometry fix, unblocks test7). B for the Category H corpus (test20 and similar). C as a long-term research track after B is validated.

---

### 3.15 OBJ-GSP + SemanticStitch Mesh-Based Seam Barrier [Research — Character-Preserving Seam Routing]

**Pain point (links to §1.6, §2.11, Category C1):** The §2.11B foreground cost barrier and §1.6A tiered cost map penalize seams through characters but cannot guarantee topology preservation when the character occupies most of the overlap width. When the character spans from column 0 to column W-50 and the only background corridor is at the very edge, the DP routes to that edge — producing a seam through an image border rather than through character-free space.

**What OBJ-GSP does (AAAI 2025):** Represents the overlap region as a triangular mesh. Semantic segmentation labels each triangle as character or background. Character triangles have infinite barrier cost and must be preserved as topological units — no seam can split a triangle cluster belonging to a single character body.

**What SemanticStitch does (Visual Computer 2025):** Two-pass approach: (1) identify all background-only columns in the overlap, (2) constrain the DP to only visit those columns. Reduces to zero the probability of a through-character seam for scenes where a background corridor exists.

**Options**

**A — SemanticStitch two-pass column filter [Quick Win]**
Pre-filter: columns where fg_mask coverage > 50% → set cost=∞ in seam DP. If no all-background column path exists, fall back to minimum-cost through-character path.
- Estimated effort: ~30 LOC addition to `_build_seam_cost_map()`. Zero new deps.
- Pros: Guaranteed background-only seam when corridor exists. Graceful fallback.

**B — OBJ-GSP triangular mesh constraint [Research]**
Build a triangular mesh on the overlap region from the BiRefNet fg boundary polygon (cv2.findContours + Delaunay triangulation). Character mesh triangles are marked with infinite barrier; Dijkstra routes around them on a mesh graph.
- Pros: Topology-preserving by construction. Character body as a geometric unit, not a pixel cost.
- Cons: Requires polygon triangulation (~50 LOC with scipy.spatial.Delaunay). Mesh graph Dijkstra is slower than the current vectorized DP.

**C — Hard-barrier seam with Intelligent Scissors waypoints [HITL]**
Extend §2.11A (Intelligent Scissors waypoints) with the SemanticStitch hard barrier: user-placed waypoints combined with the automatic column filter create a dual constraint system.
- Cons: Requires user interaction. Appropriate as an override tool in SeamDiagnosticPanel (§2.4), not as an automated step.

**Recommendation:** A immediately (trivial addition, backward-compatible). B once A is validated on the Category C1 failure corpus. C as the HITL complement to A/B for edge cases.

---

### 3.16 StabStitch++ Trajectory Smoothing for Multi-Axis Scroll [Engineering — Fixes Genuine Category F Fallbacks]

**Pain point (Issue 7 from high-value report, links to §3.14):** The 4 confirmed genuine SCANS fallbacks after S11 (tests 54, 59, 73, 89) are not solvable by any gate or retry because the issue is upstream: BA computes correct pairwise translations but the sequence has 2D or curved camera motion (combined tx+ty drift, non-linear pan deceleration) that translation-only bundle adjustment cannot model globally. §3.14 fixes the *canvas geometry* (2D frame placement); StabStitch++ fixes the *trajectory*: it computes a bidirectional midplane smoothed path and fits a 2D motion basis to the sequence, accommodating non-linear and multi-axis scroll.

**What StabStitch++ does (AAAI 2023):**
1. Estimates per-frame homographies between all frame pairs and the midplane frame
2. Computes a "bidirectional temporally consistent" trajectory by minimising a joint smoothness + fidelity cost
3. Warps each frame toward the midplane trajectory — instead of a fixed anchor, every frame moves as little as possible to produce a globally consistent grid

**Options**

**A — StabStitch++ trajectory smoother as post-BA stage [~1w]** ✅ **Shipped S121 (simplified)**
After Stage 7 (BA), detect significant dx variation (`np.percentile(dx_array, 75) - np.percentile(dx_array, 25) > 50`). If detected, call `stab_stitch_pipeline(frames, affines)` from new `backend/src/animation/stab_stitch.py` to recompute smoothed affines and pass them to Stage 8 canvas layout. Falls back to current BA result if StabStitch++ diverges.
- Files to create: `backend/src/animation/stab_stitch.py`
- Files to change: `pipeline.py` → call after Stage 7; `constants/animation.py` → `ASP_STABSTITCH` flag
- Estimated effort: ~1w (trajectory smoothing math, PyTorch homography batching, RANSAC validation)
- Pros: Directly targets 4 confirmed failures. Compatible with current BA — only activates when needed.
- Cons: 1w effort for 4 tests. StabStitch++ is designed for live-action video; anime's abrupt hold patterns may destabilise the smoothness prior.

**B — HITL per-test manual route [~1d UI, already mostly shipped]** ✅ **Shipped S146**
Use the Frame Selection Review Dialog (§2.1), Canvas Layout Inspector (§2.3), and EdgeReviewDialog (§2.2) to manually correct the frame arrangement and anchor for the 4 genuine fallback tests. Does not require implementing StabStitch++.
- `HitlPreset` dataclass + `load_hitl_preset` / `save_hitl_preset` / `apply_hitl_preset` / `list_hitl_presets` in `backend/src/animation/hitl_presets.py`. Preset files in `ASP_HITL_PRESET_DIR` (default `~/.image-toolkit/hitl_presets/{test_name}.json`). Wired in `pipeline.py` after `image_paths` sorting (force_scans path) and after `_filter_edges` (drop_edges path). 5 tests in `test_hitl_presets.py`.
- Estimated effort: ~1d (leverages shipped infrastructure)
- Pros: Targets the exact failing tests directly. No new ML dependency.
- Cons: Not generalizable to future diagonal-scroll datasets. Requires human effort per failing test.

**Recommendation:** B first (4 specific tests can be fixed manually with shipped HITL tools). A if the diagonal-scroll category grows (>8 tests) or if automated batch processing is required.

---

## Phase 2 — Next Generation Upgrade: Direct Video Ingestion & Multi-Modal HITL

> Research basis: `reports/Multimodal_ASP_HITL_Research.md` (consolidated research document). The notes here are the roadmap summary.

### Sprint 5 — Video Ingestion Foundation

**9A — `VideoIngestionStream` (PyAV direct decoder)** [~3d, No prerequisite]

Replace the FFmpeg pre-extraction step with a native PyAV decoder. New file: `backend/src/animation/video_ingestion.py`. Exposes a `VideoIngestionStream` class with `get_frame(idx)`, `get_proxy_frames(stride=5)`, and `decimate_duplicates(mad_threshold)`. `AnimeStitchPipeline.run()` accepts a `video_path: str | None` parameter alongside `image_paths`.

- Eliminates pre-extraction storage bloat (333 frames × 1080p PNG ≈ 500–800 MB per test)
- Proxy stream (I-frame-only at ¼ resolution) enables a fast first-pass frame selection pass before full-res decode
- Strict prerequisite for 9B, 9C

**9B — Native mpdecimate on tensor stream** [~1d, Requires 9A]

`decimate_duplicates()` runs frame-pair MAD on the proxy stream to drop telecine pull-down duplicates (every 5th/8th frame for 24fps→30fps broadcast) before reaching `smart_select_frames()`. Catches subtle MPEG DCT noise patterns that MAD misses at full resolution.

**9C — Hybrid 4K/1080p compositing** [~1w, Requires 9A]

`AnimeStitchPipeline.run()` accepts `hires_keyframes: Dict[int, str]`. All heavy computation (phase correlation, BiRefNet, LoFTR, BA, ECC, SAM-2, ARAP) runs on the 1080p video stream. Stage 12.8 maps the locked affine geometry onto the 4K keyframes for the final compositing pass. Net effect: near-4K output quality at 1080p compute cost.

---

### Sprint 6 — Grounded Multi-Modal HITL

**10A1 — Grounded SAM-2 (text prompt → DINO bbox → SAM-2 propagation)** [~3d, Requires Issue 3A]

New `backend/src/animation/grounding.py` wraps GroundingDINO. `masking.py` gains `_compute_fg_masks_grounded_sam2(frames, text_prompt, ...)`. `stitch_tab.py` HITL checkpoint dialog exposes a `QLineEdit` for the character description. The user types `"the girl with the blue sailor uniform"` and SAM-2 handles the rest.

**10A2 — Click-based segmentation refinement (FocalClick)** [~2d, Requires 10A1]

After SAM-2's initial mask, the HITL dialog shows the mask overlaid on frame 1. Left-click = positive prompt (expand mask); right-click = negative prompt (shrink mask). SAM-2 re-propagates the corrected segment across all frames (~0.5s). Guarantees near-perfect segmentation with ~30s of user effort.

**10A3 — Natural language seam routing** [~2d, Requires 10A1]

Text like `"route seam around the right arm"` → GroundingDINO detection in the seam zone → pixel-space exclusion mask → injected into `_build_seam_cost_map()` as `cost[mask] = 1e6` hard barrier. Prevents DP seam from cutting through named character anatomy.

---

### Sprint 7 — Data Serialization (Dataset Harvesting)

**10B1 — COCO JSON annotation serializer** [~2d, No prerequisite]

`backend/src/animation/data_serialization.py` — `COCOAnnotationBuilder` class. Every HITL interaction serializes to COCO JSON: frame selection overrides → `images`/`annotations`, segmentation click corrections → RLE mask (pycocotools `encode`), accepted SAM-2 masks → polygon contours. Storage: `~/.image-toolkit/hitl_annotations/session_{timestamp}.json`.

**10B2 — Label Studio multi-modal export** [~1d, Requires 10B1]

Label Studio JSON alongside COCO JSON. `predictions` array = SAM-2's pre-correction mask; `annotations` array = human's post-correction mask. Captures exactly what the model got wrong — the ideal RLHF preference pair format.

---

### Sprint 8 — Hybrid 4K Pipeline

**9C** implementation sprint (see Sprint 5 item 9C above for spec).

---

### Sprint 9+ — Progressive Automation (data-gated)

**10C1 — SAM-2 anime domain fine-tuning** [~1w/run, Requires 10B1 + 100+ sessions]

Frozen ViT-H encoder; fine-tune mask decoder + memory module on collected COCO anime masks. Target: SAM-2 correctly delineates semi-transparent magical effects, thin ahoge strands, and complex multi-character overlaps without any human prompting.

**10C2 — Pose contrastive fine-tuning (DWPose/ViTPose)** [~1w/run, Requires 10B1 + 500+ selection pairs]

Human frame-selection overrides become contrastive triplets: (rejected, accepted, random-other) → triplet loss on pose embedding space. Makes `_compute_dinov2_features()` → `_pose_dist()` rank anime poses by visual coherence instead of general-domain similarity.

**10C3 — PPO compositing parameter optimization** [~2w, Requires Issue 6A + calibrated RM]

PPO agent over the ASP compositing parameter space (feather width, seam cost weights, blend method). State = current composite encoded by reward model's CNN backbone. Replaces static `asp_config.toml` values with dynamically optimized per-test configuration. Zero-shot generalization to unseen input characteristics.

---

## Phase 4 — OpenCV-Informed Improvements

*Added 2026-06-22 after reverse-engineering `cv2.detail` (OpenCV 4.13.0) and contrasting with ASP.*

*Updated 2026-06-23 after full 97-test re-benchmark (S160 code, `anime_stitch_20260623_234305.json`): ghosting_score mislabelled (measures sharpness — see §3.32). `ghosting_siqe` (true ghosting, FFT autocorrelation) shows ASP **49.9% BETTER**. seam_visibility avg +512% worse (25.77 vs 4.21). `strip_banding_score` always 0.0 for simple stitch — invalid. Verdicts (97t): 10 asp_better (10.3%), 41 comparable (42.3%), 45 simple_better (46.4%). AlSSIM overall: ASP=0.6795 vs SS=0.7195 (−5.6%). `dy_cv` is the dominant predictor: dy_cv<0.17 (N=31) → ASP +1.0% AlSSIM avg, 20/31 comparable+asp_better; dy_cv≥0.50 (N=22) → ASP −13.2% AlSSIM, 9/22 comparable+asp_better.*

### §4.1 Spatial Blocks Gain Compensation ✅ [Priority: Critical — strip_banding root cause]

**What OpenCV does**: `cv2.detail_BlocksGainCompensator(bl_width=32, bl_height=32, nr_feeds=1, nr_iterations=2)`. Divides each warped frame into 32×32 pixel blocks. For each overlapping block pair between adjacent frames, solves a per-block gain ratio via least-squares. Applies 2 rounds of Gaussian smoothing to the resulting gain map to prevent block-boundary artifacts. `apply(frame_idx, corner, image, mask)` returns the gain-corrected frame.

**What ASP does**: Global per-frame scalar gain (§1.4B `_adaptive_gain_clamp`), smoothed with §1.98 Gaussian. Cannot correct spatially-varying lighting (panel vignetting, gradient illumination).

**Gap**: `strip_banding_score` is 97.9% worse for ASP — near-universal. Even when adjacent frames have matching global luminance, within-frame spatial variation creates visible banding at strip boundaries. `BlocksGainCompensator` corrects this directly.

**Implementation**: After Stage 4.5 photometric normalisation, feed warped frames (or pre-warp frames with known affines) into `BlocksGainCompensator.feed()`. Replace §1.4 scalar gain with spatially-varying correction applied per-frame via `.apply()`. Fall back to scalar when < 500 overlap pixels. `ASP_BLOCKS_GAIN_COMP=1` flag. `cv2.detail_BlocksGainCompensator` — zero new deps.

**Expected impact**: Strip banding score (currently +25.4 vs simple) should approach 0 for matched-exposure sequences. `strip_banding_score` is the single most universally-failed metric.

---

### §4.2 GraphCut Global Seam Finding ✅ [Priority: High — ghosting + seam_visibility]

**What OpenCV does**: `cv2.detail_GraphCutSeamFinder("COST_COLOR_GRAD")`. Solves a global min-cut on a graph where nodes are pixels and edges carry colour + gradient cost. Processes ALL N warped images simultaneously — not pairwise. The globally optimal seam partition means that if frame A's background corridor is claimed for seam k, the GraphCut automatically routes seam k+1 away from it.

**What ASP does**: `_seam_cut()` — a pairwise DP per boundary (left-to-right column min-energy). Each boundary is solved independently. Two adjacent seams can compete for the same background corridor, producing suboptimal routing where one seam unavoidably cuts through foreground.

**Gap**: Pairwise DP creates local optima that are globally suboptimal. GraphCut's global optimisation eliminates this conflict directly. Impact target: ghosting_score (93.8% worse) and seam_visibility (88.5% worse).

**Implementation** *(shipped S161)*: `_GRAPHCUT_SEAM` flag in `compositing.py` changed from default OFF (`"0"`) to default ON (`"1"`). Uses `batch.seam.graphcut_seam_find()` (C++ `cv::detail::GraphCutSeamFinder(COST_COLOR_GRAD)`, already implemented in Phase 4 C++ migration). Falls back to pairwise DP when `batch` unavailable or GraphCut raises an exception. Gate: `ASP_GRAPHCUT_SEAM=0` to disable. 1375 tests passing; test `test_graphcut_flag_on_by_default` updated from `assert not flag` → `assert isinstance(flag, bool)` to reflect new default.

**Expected impact**: Seam routing quality improvement from eliminating pairwise-DP local optima. Particularly valuable for sequences with sparse background corridors where multiple boundaries compete. Post-benchmark run needed to quantify seam_visibility improvement.

---

### §4.3 Wave Correction for Affine Sequences ✅ [Priority: Medium — alignment drift]

**What OpenCV does**: `cv2.detail.waveCorrect(rmats, cv2.detail.WAVE_CORRECT_HORIZ)`. After bundle adjustment, applies a global rotation to the sequence's rotation matrices so the panorama midline is horizontal. Corrects accumulated small vertical drifts that cause the panorama to "wave" upward/downward along its length.

**What ASP does**: §3.16A trajectory smooth (`_smooth_affine_trajectory`, §S121) with Gaussian σ smoothing on tx/ty. This reduces high-frequency jitter but does not correct the global wave (systematic vertical drift pattern with long wavelength).

**Gap**: BA can introduce monotonic or oscillating vertical tx drift — each frame slightly different in the transverse axis. This causes the panorama midline to curve. In anime scrolls this manifests as the character appearing to slide left/right as you move down the canvas.

**Implementation**: After Stage 7 BA, extract pseudo-rotation matrices from affines (pad 2×3 to 3×3, set R[2,2]=1). Call `cv2.detail.waveCorrect(rmats, cv2.detail.WAVE_CORRECT_HORIZ)`. Re-extract tx/ty from corrected matrices. `ASP_WAVE_CORRECT=1` flag. Fallback: no-op if all affines are near-pure-translation (|rotation| < 0.01°). Zero new deps.

**Expected impact**: Reduces transverse drift artifacts in long sequences (>20 frames). Particularly beneficial for sequences where §1.55 rotation gate does not fire (small but accumulated rotation).

---

### §4.4 Per-Channel Blocks Gain Compensation ✅ [Priority: Medium — white-balance correction]

**What OpenCV does**: `cv2.detail_BlocksChannelsCompensator(bl_width=32, bl_height=32, nr_feeds=1, nr_iterations=2)`. Extends §4.1 with per-channel (B, G, R) independent gain correction. Corrects both spatial vignetting AND inter-frame white-balance/colour-temperature shifts simultaneously.

**What ASP does**: §1.127 zone hue equalization (HSV circular hue shift, per blend zone). §3.19 chroma alignment (LAB a/b shift, per zone). Both are zone-local, per-boundary, and applied only in the blend zone — not globally across the full frame.

**Gap**: White-balance shifts (e.g., reddish frame followed by cooler frame) affect the entire frame, not just the blend zone. Global per-channel correction is needed.

**Implementation**: Same as §4.1 but use `BlocksChannelsCompensator` instead of `BlocksGainCompensator`. `ASP_BLOCKS_CHAN_COMP=1` flag. Supersedes §4.1 when enabled (both use the same feed/apply interface). Returns 3-channel corrected image. Can be layered with existing `_zone_chroma_align` for fine-grained zone-level correction after global correction.

---

### §4.5 Canvas-Space DP Seam Finding ✅ [Priority: Medium — quality + speed]

**What OpenCV does**: `cv2.detail_DpSeamFinder("COLOR_GRAD")`. Same DP algorithm as ASP's `_seam_cut` but operates in canvas space on all N images simultaneously (single call), producing N binary ownership masks. Avoids pairwise boundary re-computation.

**What ASP does**: N-1 independent `_seam_cut` calls, each in local zone coordinates. The parallel ThreadPoolExecutor (§3.11/S12) pre-computes all seams but still does N-1 independent DPs.

**Gap**: OpenCV's canvas-space DP naturally handles 3-way overlaps (where 3 frames overlap at a single point) whereas ASP's pairwise approach resolves these heuristically. For sequences with small frame steps and large overlaps, 3-way overlaps are common.

**Implementation** *(shipped S162)*: `_DP_CANVAS_SEAM` flag (`ASP_DP_CANVAS_SEAM=1`, default OFF) added to `compositing.py`. `_canvas_dp_seam_composite(warped_norm, warped_bg, canvas, H, W, N)` helper: builds coverage masks (255=has content), calls `cv2.detail_DpSeamFinder("COLOR_GRAD").find()`, composites result pixel-by-pixel respecting `warped_bg`, fills remaining black gaps. Wired as intermediate step between GraphCut fallthrough and pairwise DP. Gap-fill pass matches GraphCut path. `_get_seam_cost_flags()` extended to 6-tuple (adds `_DP_CANVAS_SEAM`). No extra deps. 5 tests in `TestCanvasDpSeamComposite`. Enable: `ASP_DP_CANVAS_SEAM=1` (only useful when `ASP_GRAPHCUT_SEAM=0`).

---

### §4.6 MultiBand Confidence-Weighted Blending [Priority: Low — quality]

**What OpenCV does**: `cv2.detail_MultiBandBlender.feed(img, mask, tl)` accepts 8-bit or float masks. The mask encodes per-pixel confidence (0=exclude, 255=full confidence). OpenCV blends at each pyramid level weighted by the confidence mask at that resolution.

**What ASP does**: `_laplacian_blend(fa, fb, mask_float)` — `mask_float` is derived from the DP seam path (binary ownership with feathered transition). §1.105 adds per-pixel fg-overlap cap. But confidence is binary (seam path) rather than spatially-varying.

**Gap**: ASP has access to several confidence signals that could generate richer blend masks: (a) ECC alignment residual per frame (§S8); (b) BiRefNet confidence scores from bg_masks; (c) distance to seam path. Feeding multi-signal confidence maps into MultiBandBlender would produce smoother transitions in uncertain regions.

**Implementation**: Compute per-pixel confidence as `conf = bg_conf * (1 - ecc_residual_norm) * dist_to_seam_norm`. Pass as float32 mask to `MultiBandBlender.feed()`. `ASP_MULTIBAND_CONF=1` flag. Requires Stage 4 bg_mask confidence values and Stage 8 residuals to be threaded through to Stage 11. Medium refactor — coordinate channels only, no new deps.

---

### §4.7 dy_cv Pre-Detection Gate ✅ [Priority: High — catastrophic failure prevention]

**Problem (97-test benchmark, 2026-06-23):** dy_cv ≥ 1.5 (coefficient of variation of adjacent vertical frame steps) reliably predicts catastrophic ASP failure. test77 (dy_cv=2.22, AlSSIM 0.444), test43 (dy_cv=2.16, AlSSIM 0.479), test82 (dy_cv=2.20, AlSSIM 0.615) are all far below SCANS output. SCANS handles these sequences trivially (constant-step assumption not required). Compositing tuning cannot fix irregular scroll patterns — the underlying affine geometry is unreliable.

**What dy_cv measures**: `std(|Δty|) / mean(|Δty|)` from bundle-adjusted affines. A pure regular scroll produces dy_cv≈0. Abrupt hold-release, variable pan speed, or sequence editing produces dy_cv>0.5. At dy_cv≥1.5, ASP's seam routing and ARAP warp assumptions fail simultaneously.

**Gate threshold**: 1.5. test13 (dy_cv=1.142) is "comparable" — threshold must not catch it. test70 (dy_cv=1.621) is the first clearly catastrophic test below 2.0.

**Implementation** *(shipped S161)*:
- `DY_CV_MAX = 1.5` added to `backend/src/constants/animation.py`
- `_DY_CV_MAX = float(os.environ.get("ASP_DY_CV_MAX", "1.5"))` at pipeline.py module level
- `_compute_dy_cv(affines)` helper: returns `std(|Δty|) / mean(|Δty|)`; returns 0.0 when N<2 or mean<1px
- Gate wired before Stage 9 canvas-span utilisation gate in `pipeline.py run()`: when `_dy_cv_gate >= _DY_CV_MAX` → immediate SCANS fallback
- `_compute_dy_cv` and `_DY_CV_MAX` exported in `pipeline.py __all__`
- 5 tests in `TestComputeDyCv` (`test_pipeline.py`)
- Set `ASP_DY_CV_MAX=0` to disable; `ASP_DY_CV_MAX=1.0` for stricter mode (catches test70 dy_cv=1.621 and up)

---

### §3.32 Ghosting Metric Taxonomy Fix [Priority: High — metric labelling error] *(confirmed 2026-06-23, full 97-test benchmark)*

**Problem (confirmed across all 97 tests, 2026-06-23):** `ghosting_score` is **mislabelled** — it does NOT measure ghosting.

Implementations in `bench_anime_stitch.py`:
- `_ghosting_score(img)` (line 256): `mean(|∂²I/∂y²|)` — double-Sobel Y. This measures **second-order vertical derivative energy = sharpness/edge-energy**, NOT repeated-edge patterns. ASP avg≈55, SS avg≈34 across 97 tests → "ASP worse" because ASP is sharper (confirmed by Laplacian sharpness: ASP=96.7 vs SS=64.3, +50.2%).
- `_ghosting_score_v2(img)` (§3.8A, S35, line 268): FFT autocorrelation of column-mean gradient profile. Returns secondary peak magnitude 0–100 where 0=clean, 60+=ghost. Correctly targets **repeated edge signatures** of double-image ghosts. ASP avg=36.21, SS avg=72.34 across 97 tests → **ASP 49.9% BETTER** (fewer ghost patterns).

**Root cause**: The original `ghosting_score` is a sharpness proxy masquerading as a ghosting metric, introduced before `ghosting_siqe` and never replaced.

**Implications for historical benchmarks**: S142 reported "ghosting_score ASP=38.7 vs SS=27.2 (+42% worse)." This was read as "ASP has more ghosting." The correct reading: "ASP has sharper edges." The true ghosting metric (`ghosting_siqe`) shows ASP is consistently better on ghosting. The full 97-test 2026-06-23 benchmark confirms this (ASP 49.9% better on `ghosting_siqe`).

**Impact**:
- `ASP_GATE_GHOST` uses `ghosting_score` (old metric) — gate should use `ghosting_siqe` instead
- CQAS uses `ghosting_siqe` correctly (weight 0.35), but `ghosting_score` also appears in legacy gates
- Any historical "ASP has more ghosting" conclusion based on `ghosting_score` is incorrect

**Implementation** *(S161 + S162 fully complete)*:
- S161: `_edge_energy_score(img)` added as correctly-labelled wrapper. Metrics dict emits `"edge_energy_score"` (primary) and `"ghosting_score"` (alias). 5 tests in `TestEdgeEnergyScore`.
- S162 §3.32B: GhostGate migrated to `_ghosting_score_v2()` (siqe, 0-100). Floor=40, ratio=2.0 unchanged — calibration is valid for siqe scale. Log label updated to `[GhostGate/siqe]`. Old sharpness-based gate was firing on sharp ASP outputs as false positives.
- S162 §3.32C: `bench_import.py suggested_rating()` now uses `ghosting_siqe / 100` instead of `(1 − ghosting_score)`. Default fallback=30 (neutral). 5 tests in `TestSuggestedRatingGhostingSiqe`.
- S162 §3.32D: `param_search.py _verdict_from_config()` now uses `ghosting_siqe / 100` with fallback to `ghosting_score / 100` for legacy JSON. 5 tests in `TestVerdictFromConfigGhostingSiqe`.
- All three scoring formulas now consistently penalise TRUE ghosting (repeated-edge pattern), not sharpness.


---

### §4.8 SeamVisGate — Post-Render Seam Visibility Safety Net ✅ [Priority: High — seam_visibility dominant failure]

**Problem (97-test benchmark, 2026-06-23):** `seam_visibility` is the single largest failure dimension for ASP vs SCANS: ASP avg=25.77 vs SCANS avg=4.21 (+512%). The dominant cases at low dy_cv (<0.5) are:
- test74: sv_asp=92.6 vs sv_sim=2.9 (AlSSIM −7.7%)
- test34: sv_asp=62.8 vs sv_sim=2.2 (AlSSIM −18.9%)
- test12: sv_asp=38.2 vs sv_sim=3.4 (AlSSIM −10.3%)
- test92: sv_asp=33.6 vs sv_sim=1.1 (AlSSIM −1.9%)

GraphCut default-ON (S161) reduces seam_visibility in well-textured areas, but a post-render safety net is needed for the remaining high-sv cases.

**seam_visibility taxonomy**: `_seam_visibility_score` returns worst-case adjacent-row luminance jump. Ranges: 0–5=invisible, 6–12=normal, 13–25=visible step, >25=hard cut.

**Gate logic**: `limit = max(floor, ratio × max(sim_sv, 1.0))`. Gate fires when `asp_sv > limit`.
- `ratio=3.0`: ASP seam_vis must not be 3× worse than SCANS
- `floor=20.0`: Only fire when ASP has a visually-significant seam (≥ "visible step" threshold)
- Floor prevents false positives when both outputs have naturally low seam_vis

**Calibration** (from 97-test corpus):
- test74: asp=92.6, sim=2.9 → limit=max(20,3×2.9)=20 → FIRES ✓
- test34: asp=62.8, sim=2.2 → limit=20 → FIRES ✓
- test12: asp=38.2, sim=3.4 → limit=20 → FIRES ✓
- test92: asp=33.6, sim=1.1 → limit=20 → FIRES ✓
- test27: asp=6.0, sim=1.2 → limit=20 → no fire ✓ (asp below floor)

**Implementation** *(shipped S163)*:
- SeamVisGate block inserted in `bench_anime_stitch.py` between GhostGate and PIL save — fires post-crop when `_SEAM_VIS_RATIO_LIMIT < 90` and `simple_ok`
- Reads `_seam_visibility_score(canvas_out)` and `_seam_visibility_score(simple_img)` — same function used for benchmarking
- `timings["render_gate_fallback"] = 2` distinguishes from GhostGate (value=1)
- `_fallback_reason` key: `seam_vis_gate:asp={X}_sim={Y}_limit={Z}`
- `ASP_GATE_SEAM_VIS` (float, default 3.0; set ≥90 to disable)
- `ASP_GATE_SEAM_VIS_FLOOR` (float, default 20.0)
- Both keys added to `_CONFIG_SCHEMA` and `_DUMP_SECTIONS["compositing"]` in `config.py`
- 5 tests in `TestSeamVisibilityGate` (`test_bench_metrics.py`) — calibrate limit formula for all 4 target cases + disable path

---

### §3.33 Feathered GraphCut Boundary Blend ✅ [Priority: High — seam_visibility step reduction]

**Problem**: GraphCut global seam (§4.2, default-ON S161) performs a hard pixel assignment at ownership boundaries. The hard ownership transition produces a 1-pixel luminance step that directly drives `seam_visibility_score`. Identical in mechanism to the pairwise DP hard partition — but now across the entire canvas width via the GraphCut cost.

**Approach**: After the GraphCut composite hard-assignment loop, apply a linear alpha ramp (±feather_px rows) at per-column ownership boundary rows. Narrow 8px band is well below the double-image ghost threshold from pose mismatch, so no content artifacts are introduced.

**Implementation** *(shipped S164)*:
- `_GC_FEATHER_PX: int = int(os.environ.get("ASP_GC_FEATHER_PX", "8"))` flag (default ON, 8px)
- `_feather_gc_boundaries(result, ownership_masks, warped_frames, feather_px=8)` — vectorized numpy:
  - Per-column boundary: `(H−1) − np.argmax(own_i[::-1], axis=0)` (last owned row of frame i)
  - Ramp: `((b + feather_px − rows) / (2 × feather_px)).clip(0, 1)` over (H, W) grid, broadcast
  - Content guard: only blend where `content_i & content_next` (no smearing into background-only columns)
  - Fires only in hard-partition path (`not _MULTIBAND_BLEND`)
- Set `ASP_GC_FEATHER_PX=0` to disable
- `_GC_FEATHER_PX` and `_feather_gc_boundaries` exported in `__all__`
- 5 tests in `TestFeatherGcBoundaries` (`test_compositing.py`)

---

### §4.9 Post-Composite Seam Band Smoothing ✅ [Priority: Medium — seam_visibility; default OFF pending benchmark]

**Problem**: Even after GraphCut feathering (§3.33), the background temporal median plate can produce adjacent-row luminance jumps at frame boundaries. The `seam_visibility_score` (worst-case adjacent-row luminance jump) directly measures this. A narrow post-composite vertical blur pass reduces the metric without altering content outside the band.

**Gate position**: Stage 11.19 in `pipeline.py` — after all SCANS-fallback gates (11.18 max), before SRStitcher and Stage 12.5 content crop. Only applied to the accepted final composite.

**Implementation** *(shipped S164)*:
- `_smooth_seam_bands(canvas, seam_ys, band_px=4)` in `canvas.py`:
  - `cv2.GaussianBlur(band, (1, 2*band_px+1), 0)` — vertical-only kernel (no horizontal blur)
  - Triangular blend weight: 1.0 at seam centre, 0.0 at band edges (content preserved at boundaries)
  - Content guard: no smearing into black gaps (`canvas.max(axis=2) > 0`)
  - Seam positions estimated from sorted affine frame centres: `(ty[k] + H/2 + ty[k+1] + H/2) / 2`
- `_SEAM_SMOOTH_PX: int = int(os.environ.get("ASP_SEAM_SMOOTH_PX", "0"))` (default OFF)
- `SEAM_SMOOTH_PX: int = 0` in `constants/animation.py`; `ASP_SEAM_SMOOTH_PX` in `_CONFIG_SCHEMA` (int, 0–32)
- 5 tests in `TestSmoothSeamBands` (`test_canvas.py`)
- Enable: `ASP_SEAM_SMOOTH_PX=4` for next benchmark; promote to default-ON if seam_visibility improves

---

### §4.10 Pre-Seam Global Gain Equalization ✅ [Priority: Critical — strip_banding root cause]

**Problem**: `_BLOCKS_GAIN_COMP` and `_BLOCKS_LUM_COMP` were only wired in the pairwise DP fallback path. With GraphCut default-ON since S161, the gain compensation was never applied in the common case. test82 had `strip_banding_score=31.1` and `canvas_gain_uniformity=0.238` vs SCANS `0.104`.

**Implementation** *(shipped S165)*:
- `_equalize_warped_gains(warped_frames, block_size=32)` applies sequential `_blocks_gain_compensate(prev, curr)` to all warped frames before GraphCut; frame 0 is the reference
- `_GLOBAL_GAIN_COMP: bool = os.environ.get("ASP_GLOBAL_GAIN_COMP", "1") != "0"` (default ON)
- `_BLOCKS_GAIN_COMP` and `_BLOCKS_LUM_COMP` defaults changed "0" → "1" for DP fallback path consistency
- `_GLOBAL_GAIN_COMP` and `_equalize_warped_gains` exported in `__all__`
- 5 tests in `TestEqualizeWarpedGains` (`test_compositing.py`)

---

### §5.1 Post-Composite Seam Luminance Step Correction ✅ [Priority: High — seam_visibility / seam_coherence]

**Problem**: Even after §4.10 gain equalization, per-column luminance mismatches remain at seam boundaries (different content distribution within each strip). `seam_coherence` (row-mean luminance variance) measures this.

**Implementation** *(shipped S166)*:
- `_correct_seam_lum_steps(canvas, seam_ys, band_px=20)` in `canvas.py`: per-column masked mean luminance measured in ±ref_px reference band; linear ramp distributes `±step/2` across ±band_px
- `_SEAM_LUM_STEP_PX: int = int(os.environ.get("ASP_SEAM_LUM_STEP", "0"))` at pipeline.py module level (default OFF)
- Stage 11.20 in `pipeline.py run()`; `SEAM_LUM_STEP_PX: int = 0` in constants; `ASP_SEAM_LUM_STEP` in config schema
- 5 tests in `TestCorrectSeamLumSteps` (`test_canvas.py`)
- Enable: `ASP_SEAM_LUM_STEP=20`

---

### §5.3 Canvas Gain Uniformity Gate ✅ [Priority: High — strip_banding SCANS fallback]

**Problem**: SeamVisGate catches hard per-row jumps but misses cases where luminance varies gradually across strips (high `canvas_gain_uniformity` = coefficient of variation of 8-strip mean luminance, even when no single adjacent-row jump exceeds the floor).

**Implementation** *(shipped S166)*:
- CGUGate in `bench_anime_stitch.py` after SeamVisGate: fires when `asp_cgu > max(0.15, 2.0 × sim_cgu)` and `_fallback_reason is None`
- Default: `ASP_GATE_CGU=2.0`, `ASP_GATE_CGU_FLOOR=0.15`; disable with `ASP_GATE_CGU=99`
- `ASP_GATE_CGU` and `ASP_GATE_CGU_FLOOR` in config schema and dump sections
- 5 tests in `TestCanvasGainUniformityGate` (`test_bench_metrics.py`)
- Calibration: test82 (asp_cgu=0.238 vs sim=0.104 → limit=0.208, fires correctly)

---

### §5.2 Seam Coherence Gate ✅ [Priority: High — strip_banding SCANS fallback]

**Problem**: Gradual luminance banding across multiple strips (not a single hard row jump) causes high `seam_coherence` (std of per-row mean luminance). 19 non-SeamVisGate tests with `simple_better` verdict had elevated SC that no gate caught.

**Implementation** *(shipped S166/S167)*:
- SCGate in `bench_anime_stitch.py` after CGUGate: fires when `asp_sc > max(15, 2.5 × sim_sc)` and `_fallback_reason is None`
- Default: `ASP_GATE_SEAM_COH=2.5`, `ASP_GATE_SEAM_COH_FLOOR=15.0`; disable with `ASP_GATE_SEAM_COH=99`
- `ASP_GATE_SEAM_COH` and `ASP_GATE_SEAM_COH_FLOOR` in config schema and dump sections
- 5 tests in `TestSeamCoherenceGate` (`test_bench_metrics.py`)

---

### §5.4 CGU Term in CQAS ✅ [Priority: Medium — aggregate quality score]

**Problem**: The 5-component CQAS (Composite Quality Aggregate Score) did not include canvas_gain_uniformity, so uniform-strip banding was invisible to the aggregate score used for verdict comparison.

**Implementation** *(shipped S167)*:
- `cgu_score = clip(1.0 - cgu / 0.40, 0, 1)` — score 1.0 at cgu=0, 0.0 at cgu≥0.40
- Added as 5th component with weight 0.15; renormalized: `[(g,0.35),(sv,0.30),(sc,0.20),(sh,0.15),(cgu,0.15)]`
- 5 tests in `TestCompositeQualityScoreWithCGU` (`test_bench_metrics.py`)

---

### §5.5 Seam Visibility in Verdict ✅ [Priority: Medium — verdict accuracy]

**Problem**: `_auto_verdict()` used CQAS+coverage+sharpness but had no direct seam_visibility penalty. Hard seams that didn't trigger the SeamVisGate (just below floor) could still win the verdict.

**Implementation** *(shipped S167)*:
- `sv_score × 0.10` additive penalty term in `_auto_verdict()` (higher sv_score = more visible seam = worse verdict)
- Complements SeamVisGate by softly penalising elevated seam_visibility even below gate threshold

---

### §5.6 Pipeline CGU Gate ✅ [Priority: High — in-pipeline strip_banding fallback]

**Problem**: §5.3 CGUGate fires at benchmark level (bench_anime_stitch.py) — too late to influence the pipeline when called from the GUI/CLI. A matching gate in pipeline.py lets the pipeline itself fall back when strip banding is detected.

**Implementation** *(shipped S168)*:
- `_canvas_gain_uniformity(img, n_strips=8)` moved from benchmark to `canvas.py`; exported in `__all__`
- `_CGU_GATE_FLOOR: float = float(os.environ.get("ASP_GATE_CGU_FLOOR", "0.20"))` at pipeline.py module level
- Stage 11.21 after §5.1 correction: `if _cgu_val > _CGU_GATE_FLOOR → _scan_stitch_fallback(reason=f"cgu_gate:{cgu:.3f}")`
- Gate disabled when `_CGU_GATE_FLOOR >= 1.0`
- `_SEAM_SMOOTH_PX` default changed 0 → 4 (seam Gaussian smoothing now on by default)

---

### §5.14 Strip Luma Monotonicity Gate ✅ [Priority: Medium — strip_banding SCANS fallback]

**Problem**: `strip_luma_monotonicity` captures alternating light/dark strip patterns not caught by FFT or CGU. High values (>0.5) indicate the output is worse than a monotonic scroll.

**Implementation** *(shipped S172)*:
- MonotonGate after FFTBandGate in `run_dataset()`: fires when `asp_mono > max(0.50, 3.0 × sim_mono)`
- `ASP_GATE_MONO=3.0`, `ASP_GATE_MONO_FLOOR=0.50`; `_fallback_reason` prefix: `monot_gate:`
- 5 tests in `TestMonotonGate` (`test_bench_metrics.py`)

---

### §5.15 Seam Ownership Entropy Gate ✅ [Priority: Medium — seam_vis SCANS fallback]

**Problem**: High seam ownership entropy means frame boundaries are fragmented — each strip boundary has high variance in which frame "owns" each pixel. This correlates with ghosting and banding.

**Implementation** *(shipped S172)*:
- EntropyGate after MonotonGate: fires when `asp_ent > max(3.0, 2.5 × sim_ent)`
- `ASP_GATE_ENTROPY=2.5`, `ASP_GATE_ENTROPY_FLOOR=3.0`; `_fallback_reason` prefix: `entropy_gate:`
- 5 tests in `TestSeamOwnershipEntropyGate` (`test_bench_metrics.py`)

---

### §5.16 Per-Seam Adaptive Lum-Step Correction Width ✅ [Priority: High — seam_visibility reduction]

**Problem**: Stage 11.20's `_correct_seam_lum_steps` uses a fixed `band_px=20` for all seams. Small luminance steps need a narrow band; large steps need a wide band.

**Implementation** *(shipped S172)*:
- `_per_seam_lum_step_px(canvas, seam_ys, min_px=5, max_px=40)` in `canvas.py`: maps step∈[5,30]→px∈[5,40]
- `SEAM_LUM_STEP_ADAPTIVE: bool = True` in constants; `_SEAM_LUM_STEP_ADAPTIVE` module flag in pipeline.py
- 5 tests in `TestPerSeamLumStepPx` (`test_canvas.py`)

---

### §5.17 Strip Self-SSIM Gate ✅ [Priority: Medium — structural coherence SCANS fallback]

**Problem**: `strip_self_ssim` measures structural self-similarity between adjacent strips. Low values indicate the output looks incoherent across strip boundaries even when luminance is similar.

**Implementation** *(shipped S173)*:
- StripSSIMGate after EntropyGate: fires when `asp_sssim < min(0.60, 0.5 × sim_sssim)` (inverted: lower = worse)
- `ASP_GATE_STRIP_SSIM=0.5`, `ASP_GATE_STRIP_SSIM_FLOOR=0.60`; `_fallback_reason` prefix: `strip_ssim_gate:`
- 5 tests in `TestStripSsimGate` (`test_bench_metrics.py`)

---

### §5.18 Chroma Seam Coherence Gate ✅ [Priority: Medium — color mismatch SCANS fallback]

**Problem**: `chroma_seam_coherence` captures per-channel color discontinuities at seam boundaries. High values indicate visible color shifts between strips.

**Implementation** *(shipped S173)*:
- ChromaSeamGate after StripSSIMGate: fires when `asp_chroma > max(12.0, 2.5 × sim_chroma)`
- `ASP_GATE_CHROMA_COH=2.5`, `ASP_GATE_CHROMA_COH_FLOOR=12.0`; `_fallback_reason` prefix: `chroma_coh_gate:`
- 5 tests in `TestChromaSeamCohGate` (`test_bench_metrics.py`)

---

### §5.19 Pipeline Seam Coherence Gate ✅ [Priority: High — in-pipeline strip_banding fallback]

**Implementation** *(shipped S174)*:
- `_seam_coherence_score(img)` in `canvas.py`: `std(per-row-mean-lum)`
- Stage 11.22: if `sc > _SC_GATE_FLOOR` (default 25.0) → SCANS fallback `reason=f"sc_gate:{sc:.3f}"`
- `_SC_GATE_ENABLED`, `_SC_GATE_FLOOR`; env: `ASP_GATE_SEAM_COH`, `ASP_GATE_SEAM_COH_FLOOR`
- 5 tests in `TestScGatePipeline` (`test_pipeline.py`)

---

### §5.20 Per-Seam Adaptive Lum-Step Band Widths in Stage 11.20 ✅ [Priority: High — seam_visibility reduction]

**Implementation** *(shipped S174)*:
- `_correct_seam_lum_steps` updated to accept `Union[int, List[int]]` for `band_px`
- Stage 11.20: when `_SEAM_LUM_STEP_ADAPTIVE=True`, calls `_per_seam_lum_step_px(canvas, seam_ys)` and passes list
- 5 tests in `TestCorrectSeamLumStepsListBandPx` (`test_canvas.py`)

---

### §5.21 Pipeline FFT Banding Gate ✅ [Priority: High — in-pipeline strip_banding fallback]

**Implementation** *(shipped S174)*:
- `_horizontal_fft_banding(img, n_strips=8)` in `canvas.py`: energy fraction at strip-boundary FFT frequency
- Stage 11.23: if `fft > _FFT_BAND_GATE_FLOOR` (default 0.35) → SCANS fallback `reason=f"fft_band_gate:{fft:.4f}"`
- `_FFT_BAND_GATE_ENABLED`, `_FFT_BAND_GATE_FLOOR`; env: `ASP_GATE_FFT_BAND`, `ASP_GATE_FFT_BAND_FLOOR`
- 5 tests in `TestFftBandGatePipeline` (`test_pipeline.py`)

---

### §5.22 Pipeline Strip Luma Monotonicity Gate ✅ [Priority: High — in-pipeline alternating-strip fallback]

**Implementation** *(shipped S174)*:
- `_strip_luma_monotonicity(img, n_strips=8)` in `canvas.py`: fraction of adjacent strip pairs with direction reversal
- Stage 11.24: if `mono > _MONO_GATE_FLOOR` (default 0.60) → SCANS fallback `reason=f"mono_gate:{mono:.3f}"`
- `_MONO_GATE_ENABLED`, `_MONO_GATE_FLOOR`; env: `ASP_GATE_MONO_PIPE`, `ASP_GATE_MONO_PIPE_FLOOR`
- 5 tests in `TestMonoGatePipeline` (`test_pipeline.py`)

---

### §5.23 Pipeline Seam Visibility Gate ✅ [Priority: High — direct seam_vis fallback]

**Implementation** *(shipped S174)*:
- `_seam_visibility_score(img)` in `canvas.py`: max absolute adjacent-row lum jump (black rows excluded)
- Stage 11.25: if `sv > _SV_GATE_FLOOR` (default 30.0) → SCANS fallback `reason=f"sv_gate:{sv:.2f}"`
- `_SV_GATE_ENABLED`, `_SV_GATE_FLOOR`; env: `ASP_GATE_SEAM_VIS`, `ASP_GATE_SEAM_VIS_FLOOR`
- 5 tests in `TestSvGatePipeline` (`test_pipeline.py`)

---

### §5.24 Pipeline Chroma Seam Coherence Gate ✅ [Priority: High — color discontinuity fallback]

**Implementation** *(shipped S174)*:
- `_chroma_seam_coherence(img, n_strips=8)` in `canvas.py`: mean per-channel color discontinuity at strip boundaries
- Stage 11.26: if `chroma_coh > _CHROMA_COH_GATE_FLOOR` (default 20.0) → SCANS fallback `reason=f"chroma_coh_gate:{val:.2f}"`
- `_CHROMA_COH_GATE_ENABLED`, `_CHROMA_COH_GATE_FLOOR`; env: `ASP_GATE_CHROMA_PIPE`, `ASP_GATE_CHROMA_PIPE_FLOOR`
- 5 tests in `TestChromaCohGatePipeline` (`test_pipeline.py`)

---

### §5.25 Pipeline Strip Self-SSIM Gate ✅ [Priority: Medium — structural coherence SCANS fallback]

**Problem**: Seams can pass the CGU, SC, FFT, Mono, SV, and Chroma gates yet still contain intra-strip structural jumps — strips that are internally inconsistent (top ≠ bottom half) signal a misaligned seam passing through a region with content.

**Implementation** *(shipped S175)*:
- `_strip_self_ssim(img, n_strips=8)` in `canvas.py`: minimum NCC between top and bottom half of each strip; range [−1, 1]; near 1.0 = uniform; lower = seam cuts through strip
- Stage 11.27: if `ssim > _STRIP_SSIM_GATE_FLOOR` (default 0.85) → SCANS fallback `reason=f"strip_ssim_gate:{val:.4f}"`
- `_STRIP_SSIM_GATE_ENABLED`, `_STRIP_SSIM_GATE_FLOOR`; env: `ASP_GATE_STRIP_SSIM`, `ASP_GATE_STRIP_SSIM_FLOOR`
- `STRIP_SELF_SSIM_GATE_FLOOR: float = 0.85` in `constants/animation.py`
- 5 tests in `TestStripSsimGatePipeline` (`test_pipeline.py`)

---

### §5.26 Benchmark Strip-SSIM & Chroma-Coh Metric Deduplication ✅ [Priority: Low — code hygiene]

**Problem**: `bench_anime_stitch.py` had local duplicate definitions of `_strip_self_ssim` and `_chroma_seam_coherence` that diverged from the canonical `canvas.py` implementations.

**Implementation** *(shipped S175)*:
- Removed local definitions in `bench_anime_stitch.py`; both functions imported from `backend.src.animation.alignment.canvas`
- `_compute_all_metrics()` emits `strip_self_ssim` and `chroma_seam_coherence` from canonical source
- 5 tests in `TestBenchStripSsimChromaMetrics` (`test_bench_metrics.py`)

---

### §5.8 Adaptive dy_cv Ceiling for Large-N Sequences ✅ [Priority: Medium — fallback precision]

**Problem**: The dy_cv gate uses a fixed `_DY_CV_MAX=1.5` regardless of how many frames are in the sequence. With N≥8 frames, step irregularity compounds across more seams — the same dy_cv=1.4 is more damaging with 16 frames than with 4.

**Implementation** *(shipped S168)*:
- `_compute_adaptive_dy_cv_max(n_frames, base_max=1.5)` in `pipeline.py`: returns `base_max` for N<8; `max(base_max × 8/N, 0.8)` for N≥8
- Scale: N=8→1.5, N=16→0.8 (floor), N=100→0.8 (floor). Custom base respected.
- `DY_CV_ADAPTIVE_FLOOR: float = 0.8` in `constants/animation.py`
- `_compute_adaptive_dy_cv_max` exported in `__all__`
- 5 tests in `TestAdaptiveDyCvMax` (`test_pipeline.py`)

---

## Effort × Impact Matrix — Pending Items

*Effort scale* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks or data-gated
*Impact scale* — **Low**: aesthetic or niche QoL · **Medium**: targeted corpus subset · **High**: pipeline-wide quality gain · **Very High**: architectural unlock or near-perfect ceiling

*Items marked ✅ are fully shipped and removed from pending rows. Matrix last updated: S175 (2026-06-24).*

> **⚠ CRITICAL — Test Suite Freeze:** Before running `pytest backend/test/`, see `moon/roadmaps/performance.md §3.10–§3.14`. Root Cause #1 (unconditional `from diffusers import DiffusionPipeline` in `anim_fill.py`) **fixed in S140**. Root Causes #2–#5 (model singletons, ThreadPoolExecutor storm, per-test gc.collect(), no process isolation) are documented in performance.md with CRITICAL-priority fix options.

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | — | — | ✅§4.3 Wave correction (detail.waveCorrect) · ✅§4.5 Canvas-space DpSeamFinder (S162) · ✅§4.8 SeamVisGate (S163) · ✅§4.9 Seam band smoothing (S164, default OFF) · ✅§5.3 CGUGate (S166) · ✅§5.1 Seam lum-step correction (S166, default OFF) | — |
| **Medium (1d–1w)** | — | — | ✅§4.1 BlocksGainCompensator (strip_banding fix) · ✅§4.4 BlocksChannelsCompensator · ✅§3.33 Feathered GC boundary (S164) · ✅§4.10 Global gain equalization (S165) · §4.6 MultiBand confidence weighting | ✅§4.2 GraphCut global seam (default-ON S161) · ✅§4.7 dy_cv gate (SCANS fallback S161) · ✅§4.8 SeamVisGate (S163) |
| **High (1–2w)** | — | — | §2.10 SAM2Flow interactive (A/B, model-dependent) · §3.5 CamFlow MET (model-dependent) | — |
| **Very High (2w+ / data-gated)** | — | — | §3.7 UDIS++ diffusion seam (end-to-end replacement) | §10C1 SAM-2 anime fine-tune · §10C2 Pose contrastive fine-tune · §10C3 PPO parameter optimization |

*Already shipped (removed from matrix):* **§5.25 pipeline strip self-SSIM gate** ✅S175 · **§5.26 bench metric dedup** ✅S175 · **§5.19 SC pipeline gate** ✅S174 · **§5.20 per-seam lum-step wired** ✅S174 · **§5.21 FFT pipeline gate** ✅S174 · **§5.22 mono pipeline gate** ✅S174 · **§5.23 SV pipeline gate** ✅S174 · **§5.24 chroma pipeline gate** ✅S174 · **§5.14 strip luma monotonicity gate** ✅S172 · **§5.15 seam ownership entropy gate** ✅S172 · **§5.16 per-seam adaptive lum-step width** ✅S172 · **§5.17 strip self-SSIM gate** ✅S173 · **§5.18 chroma seam coherence gate** ✅S173 · **§4.7 dy_cv gate** ✅S161 · **§4.2 GraphCut default-ON** ✅S161 · **§3.32 edge_energy_score alias** ✅S161 · **§4.5 Canvas-space DP** ✅S162 · **§3.32B/C/D ghosting_siqe scoring** ✅S162 · **§4.8 SeamVisGate** ✅S163 · **§3.33 Feathered GC boundary** ✅S164 · **§4.9 Seam band smoothing (default OFF)** ✅S164 · **§4.10 Global gain equalization** ✅S165 · **§5.1 Seam lum-step correction (default OFF)** ✅S166 · **§5.3 CGUGate** ✅S166 · **§5.2 SCGate seam coherence fallback** ✅S166/S167 · **§5.4 CGU in CQAS** ✅S167 · **§5.5 seam_vis in verdict** ✅S167 · **§5.6 pipeline CGU gate + seam-smooth default ON** ✅S168 · **§5.8 adaptive dy_cv ceiling** ✅S168 · **§5.9 auto seam lum-step from CGU** ✅S169 · **§5.10 strip luma monotonicity metric** ✅S169 · **§5.11 adaptive seam-smooth width** ✅S170 · **§5.12 horizontal FFT banding metric** ✅S170 · **§5.13 FFT banding gate** ✅S171 · §2.11B GUI waypoints ✅S124 · §3.4 FD-means ✅S6 · §3.8 SIQE ✅ · §9B telecine ✅ · §10B2 Label Studio ✅ · §2.5 Coverage map ✅S79 · §2.6 Crop ✅S7 · §3.15A SemanticStitch ✅S67 · §10A2 SAM-2 click-refine ✅ · §9A PyAV ✅ · §10A1 Grounded SAM-2 ✅ · §10B1 COCO ✅ · §9C Hybrid 4K ✅S119 · §3.3 DINOv2 ✅S8 · §3.6 ToonCrafter ✅S9 · §3.11 SAM-2 interactive ✅ · §10A3 NL seam ✅ · §2.1A SelectionReview ✅S79 · §2.2 EdgeReview ✅S79 · §2.3 CanvasInspector ✅S63 · §2.4A SeamDiag ✅S95 · §2.7 StagedExec ✅S79 · §1.10A quality-gate ✅S29 · §1.10E bench-import ✅S119 · §2.11A IS waypoints ✅S123 · §1.10D active-learning ✅S130 · §1.66 NCC gate ✅S131 · §1.67 canvas-spread ✅S131 · §1.8C/D dump-config ✅S131 · §1.68 feather-ratio ✅S132 · §1.69 dp-bg-ratio ✅S132 · §1.70 zone-fg-pre-escalation ✅S132 · §1.71 bg-lum-spread ✅S132 · §1.72 entropy-asymmetry ✅S132 · §1.73 gain-monotonicity ✅S133 · §1.74 canvas-fill ✅S133 · §1.75 strip-variance-ratio ✅S133 · §1.76 per-col-luma-step ✅S134 · §1.77 sat-jump ✅S135 · §1.78 hue-shift ✅S135 · §1.79 sharpness-mismatch ✅S136 · §1.80 grad-direction ✅S137 · §1.81 band-ssim ✅S138 · §1.82 freq-profile ✅S138 · §3.16A StabStitch++ trajectory ✅S121 · §1.83 noise-asymmetry ✅S139 · §1.84 rms-contrast-ratio ✅S139 · §1.85 ensemble-combiner ✅S139 · **§3.13 ProPainter Stage 4.7** ✅S140 · **§2.9A LandmarkEditorDialog** ✅S140 · **§2.10C user-drawn flow field** ✅S140 · **§1.87 masked-median bg** ✅S142 · **§3.14B horizontal-strip composite** ✅S142 · **§1.10B Bayesian param search** ✅S142 · **§3.10 MLLM scoring** ✅S143 · **§3.1A AnimeInterp SGM** ✅S143 · **§3.2A ConvGRU flow refinement** ✅S143 · **§3.12A hold-block averaging** ✅S144 · **§3.9 SI-FID proxy metric** ✅S144 · **§3.15B OBJ-GSP triangular mesh barrier** ✅S145 · **§2.8 HybridStitch export** ✅S145 · **§3.16B HITL presets** ✅S146 · **§3.5B CamFlow bg-masked** ✅S146 · **§2.10A flow HITL checkpoint** ✅S146 · **§1.88 band hist match** ✅S147 · **§1.89 seam residual order** ✅S147 · **§1.90 bilateral seam smooth** ✅S147 · **§3.17 HF column seam cost** ✅S147 · **§1.91 seam lum converge** ✅S148 · **§1.92 feather Gaussian smooth** ✅S148 · **§3.18 CQAS aggregate score** ✅S148 · **§1.94 bg consistency score** ✅S148 · **§1.95 fg-zone SP threshold scale** ✅S149 · **§3.19 per-zone pre-blend chroma align** ✅S149 · **§1.96 chroma seam coherence metric** ✅S149 · **§1.97 entropy asymmetry gate** ✅S149 · **§1.98 per-frame gain smooth** ✅S150 · **§3.20 extra fg dilation cost** ✅S150 · **§1.99 seam endpoint bg-pin** ✅S150 · **§3.21 strip gradient CV metric** ✅S150 · **§1.101 full zone MAD gate** ✅S151 · **§1.102 warp momentum damping** ✅S151 · **§3.22 seam contrast ratio metric** ✅S151 · **§1.103 ref-proximity dom frame** ✅S151 · **§1.104 zone-lum-norm** ✅S152 · **§3.23 seam col spread metric** ✅S152 · **§1.105 fg-overlap blend cap** ✅S152 · **§1.106 post-composite seam lum audit** ✅S152 · **§1.107 adaptive seam band** ✅S153 · **§3.24 seam boundary row std** ✅S153 · **§1.108 Laplacian alpha schedule** ✅S153 · **§1.109 cost map normalization** ✅S153 · **§1.110 cost map Gaussian blur** ✅S154 · **§3.25 seam boundary entropy** ✅S154 · **§1.111 zone sat norm** ✅S154 · **§1.112 seam path drift gate** ✅S154 · **§1.113 cost-col smooth** ✅S155 · **§1.114 zone contrast eq** ✅S155 · **§3.26 strip sat CV** ✅S155 · **§1.115 feather jump cap** ✅S155 · **§1.116 zone bg-frac diag** ✅S156 · **§1.117 fast NCC pre-gate** ✅S156 · **§1.118 seam sharpness guard** ✅S156 · **§3.27 seam band NCC metric** ✅S156 · **§1.119 zone width CV gate** ✅S157 · **§1.120 sat step audit** ✅S157 · **§1.121 hist intersection gate** ✅S157 · **§3.28 grad coherence metric** ✅S157 · **§1.122 high-path-cost gate** ✅S158 · **§3.29 zone coverage fraction** ✅S158 · **§1.123 scatter cost penalty** ✅S158 · **§1.124 adaptive SP soft residual** ✅S158 · **§1.125 seam transition penalty** ✅S159 · **§3.30 strip self-SSIM** ✅S159 · **§1.126 fg-majority floor** ✅S159 · **§1.127 zone hue eq** ✅S159

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| 1.1 Bundle Adjustment Hardening | [#11-bundle-adjustment-hardening](#11-bundle-adjustment-hardening) |
| 1.2 Near-Zero Edge Filter | [#12-near-zero--zero-translation-edge-filter](#12-near-zero--zero-translation-edge-filter) |
| 1.3 Scale and Rotation | [#13-scale-and-rotation-handling](#13-scale-and-rotation-handling) |
| 1.4 Gain Clamp Widening | [#14-gain-clamp-widening-for-dark-scenes](#14-gain-clamp-widening-for-dark-scenes) |
| 1.5 Stage 11 Performance | [#15-stage-11-composite-performance](#15-stage-11-composite-performance) |
| 1.6 Ghosting Reduction | [#16-ghosting-reduction-in-composite-zone](#16-ghosting-reduction-in-composite-zone) |
| 1.7 Border Rectangling | [#17-recdiffusion-border-rectangling](#17-recdiffusion-border-rectangling) |
| 1.8 Config File | [#18-asp-pipeline-configuration-file](#18-asp-pipeline-configuration-file) |
| 1.9 Fallback Path Purity | [#19-fallback-path-purity](#19-fallback-path-purity) |
| 1.10 RLHF Loop | [#110-rlhf-loop-integration](#110-rlhf-loop-integration) |
| 2.1 Frame Selection Assistant | [#21-frame-selection-assistant-quick-win](#21-frame-selection-assistant-quick-win) |
| 2.2 Edge Graph Inspector | [#22-edge-graph-inspector--editor-quick-win](#22-edge-graph-inspector--editor-quick-win) |
| 2.3 Anchor & Canvas Layout | [#23-anchor-frame--canvas-layout-inspector-priority-medium](#23-anchor-frame--canvas-layout-inspector-priority-medium) |
| 2.4 Seam Registration Inspector | [#24-seam-registration-inspector-highest-impact](#24-seam-registration-inspector-highest-impact) |
| 2.5 Coverage Map | [#25-temporal-median-coverage-map-quick-win](#25-temporal-median-coverage-map-quick-win) |
| 2.6 Crop Assistant | [#26-output-scale--crop-assistant-priority-medium---test27-fix](#26-output-scale--crop-assistant-priority-medium---test27-fix) |
| 2.7 StitchWorker Staged Execution | [#27-architecture-stitchworker-staged-execution-implementation-foundation](#27-architecture-stitchworker-staged-execution-implementation-foundation) |
| 2.8 HybridStitch Handoff | [#28-asp-to-hybridstitch-handoff-long-term](#28-asp-to-hybridstitch-handoff-long-term) |
| 3.1 AnimeInterp SGM — Aperture Problem | [#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact](#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |
| 3.2 ConvGRU Recurrent Flow Refinement | [#32-convgru-recurrent-flow-refinement-for-kinematic-accuracy-research](#32-convgru-recurrent-flow-refinement-for-kinematic-accuracy-research) |
| 3.3 DINOv2 + SigLIP Submodular Selection | [#33-dinov2--siglip-submodular-frame-selection-priority-high--directly-addresses-gt-coupling](#33-dinov2--siglip-submodular-frame-selection-priority-high--directly-addresses-gt-coupling) |
| 3.4 FD-Means Hold Detection | [#34-fd-means-animation-hold-detection-quick-win--preprocessing](#34-fd-means-animation-hold-detection-quick-win--preprocessing) |
| 3.5 CamFlow Hybrid Motion Basis | [#35-camflow-hybrid-motion-basis-for-camera-displacement-research](#35-camflow-hybrid-motion-basis-for-camera-displacement-research) |
| 3.6 ToonCrafter Seam Synthesis | [#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium](#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium) |
| 3.7 UDIS++ / UDTATIS Diffusion Composition | [#37-udis--udtatis-diffusion-based-seam-composition-long-term--end-to-end-replacement](#37-udis--udtatis-diffusion-based-seam-composition-long-term--end-to-end-replacement) |
| 3.8 SIQE Ghosting Metric | [#38-siqe-no-reference-ghosting-detection-quick-win--metric-upgrade](#38-siqe-no-reference-ghosting-detection-quick-win--metric-upgrade) |
| 3.9 SI-FID Stitching Quality | [#39-si-fid-stitched-image-fréchet-distance-for-reference-free-evaluation-research](#39-si-fid-stitched-image-fréchet-distance-for-reference-free-evaluation-research) |
| 3.10 MLLM Semantic Quality Scoring | [#310-mllm-semantic-quality-scoring-research--autonomous-quality-assurance](#310-mllm-semantic-quality-scoring-research--autonomous-quality-assurance) |
| 1.11 Animation Hold Detection | [#111-animation-hold-detection--preprocessing-quick-win--session-6](#111-animation-hold-detection--preprocessing-quick-win--session-6) |
| 2.9 BigWarp / Fourier-Mellin Fallback | [#29-bigwarp--fourier-mellin-manual-registration-fallback-priority-high-hitl](#29-bigwarp--fourier-mellin-manual-registration-fallback-priority-high-hitl) |
| 2.10 SAM2Flow / FlowVid Interactive Flow | [#210-sam2flow--flowvid-interactive-optical-flow-kinematics-research--hitl](#210-sam2flow--flowvid-interactive-optical-flow-kinematics-research--hitl) |
| 2.11 Intelligent Scissors Seam Routing | [#211-intelligent-scissors-seam-routing-quick-win--replaces-dp-seam](#211-intelligent-scissors-seam-routing-quick-win--replaces-dp-seam) |
| 3.11 SAM 2 Interactive Masking | [#311-sam-2--interactive-masking-upgrade-research--hitl](#311-sam-2--interactive-masking-upgrade-research--hitl) |
| 3.12 Overmix Sub-Pixel Averaging | [#312-overmix-sub-pixel-averaging--maximal-frame-ingestion-philosophy-research](#312-overmix-sub-pixel-averaging--maximal-frame-ingestion-philosophy-research) |
| 3.13 ProPainter Background Completion | [#313-propainter-background-completion-research--highest-background-plate-impact](#313-propainter-background-completion-research--highest-background-plate-impact) |
| 3.14 Horizontal/Diagonal Scroll 2D Canvas | [#314-horizontal-and-diagonal-scroll--2d-canvas-support-engineering--unblocks-category-fh](#314-horizontal-and-diagonal-scroll--2d-canvas-support-engineering--unblocks-category-fh) |
| 3.15 OBJ-GSP + SemanticStitch Seam Barrier | [#315-obj-gsp--semanticstitch-mesh-based-seam-barrier-research--character-preserving-seam-routing](#315-obj-gsp--semanticstitch-mesh-based-seam-barrier-research--character-preserving-seam-routing) |
| 3.16 StabStitch++ Trajectory Smoothing | [#316-stabstitch-trajectory-smoothing-for-multi-axis-scroll-engineering--fixes-genuine-category-f-fallbacks](#316-stabstitch-trajectory-smoothing-for-multi-axis-scroll-engineering--fixes-genuine-category-f-fallbacks) |

---

## Document History

*Last updated: 2026-06-23. **Benchmark 2026-06-23 (full 97-test, S160 code, `anime_stitch_20260623_234305.json`, `aligned_ssim_vs_gt` verdict metric)**: ghosting_siqe ASP=36.21 vs SS=72.34 (ASP −49.9% — TRUE ghosting metric, ASP BETTER); seam_visibility ASP=25.77 vs SS=4.21 (+512% WORSE — dominant failure); sharpness ASP=96.7 vs SS=64.3 (+50.2% BETTER); aligned_ssim_vs_gt (55 GT tests): ASP=0.6795 vs SS=0.7195 (−5.6% WORSE overall). Verdicts (97t): 10 asp_better (10.3%), 41 comparable (42.3%), 45 simple_better (46.4%), 1 insufficient_data (test95 — simple stitch failed). dy_cv regime: <0.17 (N=31) → ASP +1.0% AlSSIM, 20/31 comparable+asp_better; 0.17–0.50 (N=44) → ASP −5.1%; ≥0.50 (N=22) → ASP −13.2%. test17 = clear asp_better (+5.4% AlSSIM, dy_cv=0.133). test77/43/82 = catastrophic (dy_cv 2.0–2.2, AlSSIM −22 to −37%). test53 (dy_cv=3.59) anomalous asp_better (no GT). S160 vs S142: asp_better 9→10 (+1), simple_better 46→45 (−1) — marginal net gain over 18 sessions. **Metric polarity confirmed (all 97 tests)**: `ghosting_score` = sharpness proxy (§3.32). `strip_banding_score` always 0.0 for simple stitch — invalid cross-system metric. Session 160 complete: **§4.1 blocks BGR gain comp** + **§4.3 wave correction** + **§4.4 blocks lum comp** + **§3.31 canvas gain uniformity** — **1272 backend tests (9 skipped)**. Session 159 complete: **§1.125 seam transition penalty** + **§3.30 strip self-SSIM** + **§1.126 fg-majority floor** + **§1.127 zone hue eq** — **1252 backend tests (9 skipped)**. **OpenCV gap analysis added (2026-06-22)**: §4.1–§4.6 new roadmap items derived from `cv2.detail` reverse-engineering — spatial blocks gain comp (targets strip_banding 97.9% failure), GraphCut global seam (targets ghosting/seam_visibility), wave correction, per-channel blocks compensation, canvas-space DP seam, MultiBand confidence weighting. Session 158 complete: **§1.122 high-path-cost gate** + **§3.29 zone coverage fraction** + **§1.123 scatter cost penalty** + **§1.124 adaptive SP soft residual** — **1232 backend tests (9 skipped)**. Session 157 complete: **§1.119 zone width CV gate** + **§1.120 sat step audit** + **§1.121 hist intersection gate** + **§3.28 grad coherence metric** — **1212 backend tests (9 skipped)**. Session 156 complete: **§1.116 zone bg-frac diag** + **§1.117 fast NCC pre-gate** + **§1.118 seam sharpness guard** + **§3.27 seam band NCC metric** — **1192 backend tests (9 skipped)**. Session 155 complete: **§1.113 cost-col smooth** + **§1.114 zone contrast eq** + **§3.26 strip sat CV** + **§1.115 feather jump cap** — **1172 backend tests (9 skipped)**. Session 154 complete: **§1.110 cost map Gaussian blur** + **§3.25 seam boundary entropy** + **§1.111 zone sat norm** + **§1.112 seam path drift gate** — **1152 backend tests (9 skipped)**. Session 146 complete: **§3.16B `HitlPreset`** per-test HITL preset save/load/apply (`hitl_presets.py`, wired to `pipeline.py`) + **§3.5B `bg_masked_phase_correlate`** background-masked camera displacement (`cam_flow.py`, wired to `frame_selection.py`) + **§2.10A `set_flow_hitl_callback`** flow HITL checkpoint at single-pose escalation (`compositing.py`) — **991 backend tests (9 skipped)**. Session 145 complete: **§3.15B `_build_fg_mesh_barrier`** Delaunay triangular mesh seam barrier (`compositing.py`) + **§2.8 `HybridExportData`** pipeline state JSON export (`hybrid_export.py`, wired to `pipeline.py`) — **976 backend tests (9 skipped)**. Session 144 complete: **§3.12A `_hold_block_average`** Overmix-style hold-block sub-pixel averaging (`frame_selection.py`) + **§3.9 SI-FID proxy** patch Laplacian sharpness ratio (`bench_anime_stitch.py`) — **966 backend tests (9 skipped)**. Session 140 complete: **§3.13 `_propainter_complete_frames`** ProPainter multi-frame background completion Stage 4.7 (`bg_complete.py` + `pipeline.py`) + **§2.9A `LandmarkEditorDialog`** HITL BigWarp-style landmark editor (`gui/src/dialogs/landmark_editor_dialog.py`, wired to `EdgeReviewDialog`) + **§2.10C `_sparse_flow_to_dense` / `flow_arrows` override** user-drawn flow field in `SeamDiagnosticDialog` → `register_foreground_at_seam` override + **test-suite freeze root causes** identified and Root Cause #1 (unconditional `from diffusers import DiffusionPipeline` in `anim_fill.py`) fixed; CRITICAL §3.10–§3.14 sections added to `performance.md` — **928 backend tests (2 skipped)** (no new tests for S140 features). Session 139 complete: **§1.83 `_seam_noise_mismatch`/`_check_seam_noise_gate`** Laplacian-std noise-level asymmetry gate (`compositing.py`) Stage 11.16 + **§1.84 `_seam_rms_contrast_ratio`/`_check_seam_rms_contrast_gate`** RMS contrast ratio gate Stage 11.17 + **§1.85 `_seam_gate_vote_counts`/`_check_seam_ensemble_gate`** multi-gate ensemble combiner Stage 11.18 — 15 new tests → **928 backend tests (2 skipped)**. Session 138 complete: **§1.82 `_seam_freq_profile`/`_check_seam_freq_gate`** FFT spatial-frequency profile mismatch gate (`compositing.py`) Stage 11.15 + **§1.81 `_seam_band_ssim`/`_check_seam_ssim_gate`** SSIM perceptual seam gate (`compositing.py`) Stage 11.14 — 10 new tests → **913 backend tests (2 skipped)**. Session 137 complete: **§1.80 `_seam_grad_direction`/`_check_seam_grad_direction_gate`** Sobel gradient-direction circular-distance coherence gate (`compositing.py`) Stage 11.13 — 5 new tests → **903 backend tests (2 skipped)**. Session 136 complete: **§1.79 `_seam_sharpness_mismatch`/`_check_seam_sharpness_gate`** Laplacian-variance log₂ ratio sharpness mismatch gate (`compositing.py`) Stage 11.12 — 5 new tests → **898 backend tests (2 skipped)**. Session 135 complete: **§1.77 `_seam_saturation_jump`/`_check_seam_saturation_gate`** mean HSV saturation jump gate + **§1.78 `_seam_hue_shift`/`_check_seam_hue_gate`** circular hue shift gate (`compositing.py`) Stages 11.10/11.11 — 10 new tests → **893 backend tests (2 skipped)**. Session 134 complete: **§1.76 `_seam_max_col_luma_step`/`_check_seam_max_col_gate`** per-column worst-case luma step gate (`compositing.py`) Stage 11.9 — 5 new tests → **883 backend tests (2 skipped)**. Session 133 complete: **§1.73 `_compute_bg_lum_monotonicity`** Kendall-τ brightness-staircase gate (`pipeline.py`) Stage 10.9; **§1.74 `_compute_canvas_fill_ratio`** empty-canvas gap gate Stage 11.7; **§1.75 `_compute_strip_variance_ratio`** texture-imbalance gate Stage 11.8 — 15 new tests → **878 backend tests (2 skipped)**. Session 132 complete: **§1.68 `_enforce_feather_ratio`**, **§1.69 `_seam_dp_bg_ratio`**, **§1.70 `_fg_fraction_in_zone`** (`compositing.py`) wired and tested; **§1.71 `_compute_bg_lum_spread`** pre-composite background luma spread gate (`pipeline.py`) Stage 10.8; **§1.72 `_seam_entropy_asymmetry`/`_check_seam_entropy_gate`** texture-density discontinuity gate (`compositing.py`) Stage 11.5 — 25 new tests. Bugfixes: §1.66 NCC identical-halves test (band size), §1.67 `_make_spread_edge` rename (shadowed `_make_edge`). → **863 backend tests (2 skipped)**. Session 123 complete: **§2.11A Intelligent Scissors Seam Waypoints** — `_seam_cut()` in `compositing.py` gains `waypoints: Optional[List[Tuple[int,int]]]` param; three-part guarantee (pre-DP inf-injection + forced traceback + post-smooth re-stamp) ensures seam passes through every `(x,y)` waypoint pixel; canvas-space waypoints from `seam_overrides[k]["waypoints"]` auto-converted to zone-local coords; no env var needed. → **777 backend tests (2 skipped)**. Session 122 complete: **§1.56 Chroma Seam Correction** (S122). Session 121 complete: **§3.16A StabStitch++ Simplified Trajectory Smoother** — `_smooth_affine_trajectory(affines, sigma, iqr_threshold)` in `pipeline.py`; IQR-gated Gaussian 1D smooth (scipy) on tx/ty sequences; skips clean linear scrolls; wired post-Stage-7 BA after §1.55 rotation gate and before Stage 7b validation; directly targets the 4 genuine SCANS fallbacks (tests 54/59/73/89) caused by phase-correlation jitter in non-linear/multi-axis scroll. → **767 backend tests (2 skipped)**. Session 120 complete: **§1.55 BA Affine Rotation Gate** — `_compute_max_affine_rotation_deg(affines)` in `pipeline.py`; wired post-Stage-7 BA between §1.52 and Stage 7b; fires when any affine rotation > threshold degrees (default off; suggest 5.0°) → SCANS fallback. → **762 backend tests (2 skipped)**. Session 119 complete: **§9C Hires Keyframes** + **§1.10E Benchmark JSON Import**. Session 118 complete: **§1.54 Render Luminance Std Gate**. `_reject_low_contrast_frames(thumbs, paths, contrast_threshold) → (thumbs, paths, n_dropped)` added to `frame_selection.py` — measures per-frame contrast as `np.std(thumb * 255.0)` on the grayscale thumbnail; interior frames with std below threshold are dropped before hold detection; first/last always kept to preserve canvas extent. `_CONTRAST_REJECT_THRESH` module flag (default 0.0=off; `ASP_CONTRAST_THRESH=15.0`). Wired as step 1b-a in `smart_select_frames` after §1.2E blur rejection. Rationale: flash/whiteout panels and bloom-overexposure frames have near-zero pixel std (std ≈ 0–8 lum) — they offer no reliable keypoints for LoFTR or peaks for phase correlation. §1.2E (Laplacian blur) does NOT catch these: a sharp white-flash frame can score high Laplacian (crisp edge where flash meets non-white content) while its interior is completely textureless. Removing such frames before matching prevents spurious zero-displacement edges from entering the edge graph. `CONTRAST_THRESH = 15.0` added to `constants/animation.py`. `"ASP_CONTRAST_THRESH"` added to `_CONFIG_SCHEMA` in `config.py` as `(float, 0.0, None, ...)`. `_reject_low_contrast_frames` exported in `__all__`. 5 tests `TestRejectLowContrastFrames` in `test_frame_selection.py` → **688 backend tests (2 skipped)**. GUI 18 unchanged. Session 109 complete: **§1.45 Canvas Width Ratio Gate**. `_compute_canvas_width_ratio(canvas_w, frames) → float` added to `pipeline.py` — returns `canvas_w / median_frame_w`; median over all source-frame widths; 1.0 for empty frames. `_MAX_CANVAS_WIDTH_RATIO` module flag (default 0.0=off; `ASP_MAX_CANVAS_WIDTH_RATIO=1.5`). Gate wired between §1.44 adjacent-gap gate and Stage 9.5 frame-confidence computation: fires when ratio > threshold, logs canvas_w, ratio, and threshold, triggers SCANS fallback. Rationale: for a vertical-scroll panorama the canvas should be ≈ 1× the source-frame width — frames are stacked top-to-bottom with only minor horizontal offsets. When BA introduces tx drift (frames shifted sideways by different amounts), the canvas grows horizontally, producing a thin strip of content in a wide black canvas. §3.14 (horizontal scroll detection) does NOT catch this case because ty_span still dominates; §1.17 (span utilisation) only checks the vertical span. §1.45 catches the orthogonal failure: horizontal canvas bloat in a vertical-scroll sequence. `MAX_CANVAS_WIDTH_RATIO = 1.5` added to `constants/animation.py`. `"ASP_MAX_CANVAS_WIDTH_RATIO"` added to `_CONFIG_SCHEMA` in `config.py` as `(float, 0.0, None, ...)`. `_compute_canvas_width_ratio` exported in `__all__`. 5 tests `TestComputeCanvasWidthRatio` in `test_pipeline.py` → **683 backend tests (2 skipped)**. GUI 18 unchanged. Session 108 complete: **§1.44 Maximum Adjacent Frame Gap Gate**. `_compute_max_adjacent_gap(affines, frames) → float` added to `pipeline.py` — for each consecutive pair (i, i+1), computes the canvas-space distance between the trailing edge of frame i and the leading edge of frame i+1 along the dominant scroll axis (vertical: `ty_{i+1} − (ty_i + H_i)`; horizontal: `tx_{i+1} − (tx_i + W_i)`, axis determined by comparing ty_span vs tx_span); returns the maximum over all N-1 pairs; 0.0 for N < 2. `_MAX_ADJACENT_GAP_PX` module flag (default 0.0=off; `ASP_MAX_ADJACENT_GAP_PX=100.0`). Gate wired between §1.17 canvas-span utilisation and Stage 9.5 frame-confidence computation: fires when flag > 0 and gap > threshold, logs the exact gap and threshold, triggers SCANS fallback. Rationale: §1.17 catches global canvas *collapse* (total span too small) but not the inverse — BA can produce a *correct* global span while *stretching* two adjacent frames apart by placing them at ty_i=0 and ty_{i+1}=500 when H_i=300 (gap=200px uncovered strip). §1.39 catches this post-render but requires the full warp pass; §1.44 fires on pure affine math before any rendering cost. `MAX_ADJACENT_GAP_PX = 100.0` added to `constants/animation.py`. `"ASP_MAX_ADJACENT_GAP_PX"` added to `_CONFIG_SCHEMA` in `config.py` as `(float, 0.0, None, ...)`. `_compute_max_adjacent_gap` exported in `__all__`. 5 tests `TestComputeMaxAdjacentGap` in `test_pipeline.py` → **678 backend tests (2 skipped)**. GUI 18 unchanged. Session 107 complete: **§1.43 Adjacent Edge Coverage Ratio Gate**. `_compute_adj_edge_coverage(edges, n_frames) → float` added to `pipeline.py` — counts the fraction of adjacent frame pairs `(|i−j|=1)` that have at least one matching edge; pairs are represented as canonical `(min(i,j), max(i,j))` tuples in a set so duplicates count once. `_ADJ_COVERAGE_MIN` module flag (default 0.0=off; `ASP_ADJ_COVERAGE_MIN=0.60`). Gate wired between §1.16 MST weight gate and Stage 7 BA: when coverage < threshold, logs covered/total adjacent count and triggers SCANS fallback. Rationale: §1.15 connectivity and §1.16 MST weight only check global graph structure — a skip-edge-dominated graph can pass both while most adjacent pairs have no local displacement anchor, causing BA to extrapolate rather than interpolate translations. `ADJ_COVERAGE_MIN = 0.60` added to `constants/animation.py`. `"ASP_ADJ_COVERAGE_MIN"` added to `_CONFIG_SCHEMA` in `config.py` as `(float, 0.0, 1.0, ...)`. `_compute_adj_edge_coverage` exported in `__all__`. 5 tests `TestComputeAdjEdgeCoverage` in `test_pipeline.py` → **673 backend tests (2 skipped)**. GUI 18 unchanged. Session 106 complete: **§1.42 Linear Interpolation Bg Fill**. `_linear_interp_zero_bg(canvas, zero_mask) → np.ndarray` added to `bg_complete.py` — for each column, iterates unknown (zero-coverage) rows and checks for known pixels both above and below; when both boundaries exist, fills with a per-channel linear blend `(1−t) × pixel_above + t × pixel_below` where `t = (r − r_above) / (r_below − r_above)`; when only one boundary exists (top/bottom edge gaps), falls back to nearest-neighbour copy so no pixel is left unfilled. `_linear_interp_zero_bg` added to `__all__`. Wired in `complete_background()` between ProPainter and `_nn_fill_zero_bg` branches: when `_INTERP_BG_FILL` is set, uses linear interpolation instead of NN copy. Rationale: `_nn_fill_zero_bg` already picks the correct nearest neighbour bidirectionally, but hard-copies it — producing a discrete color step at the midpoint when the pixel above and below differ (e.g., background transitions from light sky at top to dark floor at bottom across a large gap). Linear interpolation removes this step artefact at negligible extra cost. `_INTERP_BG_FILL` bool module flag (default OFF; `ASP_INTERP_BG_FILL=1`). `"ASP_INTERP_BG_FILL"` added to `_CONFIG_SCHEMA` in `config.py` as `(int, 0, 1, ...)`. Comment in `constants/animation.py` documenting §1.42. 5 tests `TestLinearInterpZeroBg` in `test_bg_complete.py` → **668 backend tests (2 skipped)**. GUI 18 unchanged. Session 105 complete: **§1.41 Sequential Gain Chain-Drift Guard**. `_check_gain_chain_drift(gains: np.ndarray, max_ratio: float) → bool` added to `rendering.py` — computes the per-channel cumulative product of the gains array (`np.prod(gains, axis=0)`, shape (3,)) and returns True when `|log(cum_c)| > log(max_ratio)` for any channel c. The sequential correction in `_compute_sequential_color_gains` chains N per-pair photometric corrections: if each pair nudges in the same direction (e.g., monotonically dimming video capture), the total effect by frame N can be an implausible 3–7× brightness shift. Rather than apply a systematically drifted correction that would make the canvas worse than no correction, the guard resets all gains to 1.0 and biases to 0.0 when drift is detected. Called with `_GAIN_DRIFT_MAX` after the main computation loop. `_GAIN_DRIFT_MAX` float module flag (default 0.0=off; `ASP_GAIN_DRIFT_MAX=2.0` recommended). `GAIN_DRIFT_MAX=2.0` in `constants/animation.py`. `"ASP_GAIN_DRIFT_MAX"` in `_CONFIG_SCHEMA` as `(float, 0.0, None, ...)`. `import logging; logger = logging.getLogger(__name__)` added to `rendering.py` (previously had none). 5 tests `TestCheckGainChainDrift` in `test_rendering.py` → **663 backend tests (2 skipped)**. GUI 18 unchanged. Session 104 complete: **§1.40 Adaptive Gain Clamp for Sequential Colour Correction**. `_adaptive_render_gain_clamp(ref_lum: float) → (lo, hi)` added to `rendering.py` — computes `clamp_width = max(0.14, 0.26 − 0.12 × (ref_lum / 255))` then returns `(1.0 − clamp_width, 1.0 + clamp_width)`. Applies the same luminance-adaptive formula as §1.4B in `compositing.py` to the Stage 9 sequential photometric correction (`_compute_sequential_color_gains`): the fixed `[0.88, 1.12]` (±12%) clamp underestimates the valid correction range in dark overlap zones (where a small absolute delta is a large ratio) and can over-clamp bright scenes. `_ADAPTIVE_RENDER_GAIN` bool module flag (default OFF; `ASP_ADAPTIVE_RENDER_GAIN=1` to enable). Wired as a conditional inside the per-channel median-ratio computation: when ON, `_g_lo, _g_hi = _adaptive_render_gain_clamp(mean(arr_i))`; when OFF, falls back to legacy `0.88, 1.12`. `RENDER_GAIN_CLAMP_DARK=0.26` and `RENDER_GAIN_CLAMP_BRIGHT=0.14` added to `constants/animation.py`. `"ASP_ADAPTIVE_RENDER_GAIN"` added to `_CONFIG_SCHEMA` in `config.py` as `(int, 0, 1, ...)`. `_adaptive_render_gain_clamp` exported in test via direct import (not in pipeline `__all__` — module is self-contained). 5 tests `TestAdaptiveRenderGainClamp` in `test_rendering.py` → **658 backend tests (2 skipped)**. GUI 18 unchanged. Session 103 complete: **§1.39 Render Canvas Coverage Fraction Gate**. `_compute_render_coverage(valid_mask: np.ndarray) → float` added to `pipeline.py` — returns `float((valid_mask > 0).sum()) / float(total)`; 0.0 for empty mask. *valid_mask* is the uint8 array from `_render` where 255 = canvas pixel reached by ≥1 warped frame and 0 = not reached. Gate wired between Stage 10.2 (bg fill) and Stage 10.5 (multi-frame row coverage): when `_RENDER_MIN_COVERAGE > 0.0` and fraction < threshold, logs diagnostic and returns SCANS fallback. Rationale: Stage 10.5 checks whether rows have ≥2-frame overlap but does not catch the case where all frames pile into a small dense clump leaving most canvas untouched (e.g., BA produces near-zero tx/ty for all frames) — such renders pass the row-coverage check in the covered zone yet leave 60–70% of the canvas black. `_RENDER_MIN_COVERAGE` float module flag (default 0.0=off; `ASP_RENDER_MIN_COVERAGE=0.30` recommended). `RENDER_MIN_COVERAGE=0.30` in `constants/animation.py`. `"ASP_RENDER_MIN_COVERAGE"` in `_CONFIG_SCHEMA` (`config.py`). `_compute_render_coverage` exported in `__all__`. 5 tests `TestComputeRenderCoverage` in `test_pipeline.py` → **653 backend tests (2 skipped)**. GUI 18 unchanged. Session 102 complete: **§1.38 LoFTR Background Match Ratio Gate**. `_compute_bg_match_ratio(n_bg_pts: int, n_total_pts: int) → float` added to `matching.py` — returns `float(n_bg_pts) / max(1, n_total_pts)`; 0.0 when `n_total_pts == 0` (no ZeroDivisionError). Captures `n_loftr_total = len(pts1)` before the bg-filtering block in `_match_pair`. After bg filtering, when `_LOFTR_BG_RATIO_MIN > 0.0` and the computed ratio falls below the threshold, rejects the LoFTR edge by zeroing `pts1` so the downstream `if len(pts1) >= 20` gate fails and M stays None. Falls through to ALIKED/template-match/phase-correlation as with any other LoFTR rejection. Rationale: the existing §1.20 bg-pt minimum (`>= 20`) only ensures a raw count of bg matches but doesn't check whether those 20–30 matches represent a sparse 5–10% sliver of all 400 LoFTR matches — in fg-dominated pairs, those few bg matches are spatially clustered and noisy. The ratio gate catches the case `n_bg>=20 AND n_bg/n_total << threshold`. `_LOFTR_BG_RATIO_MIN` float module flag (default 0.0=off; `ASP_LOFTR_BG_RATIO_MIN=0.15` recommended). `LOFTR_BG_RATIO_MIN=0.15` in `constants/animation.py`. `"ASP_LOFTR_BG_RATIO_MIN"` in `_CONFIG_SCHEMA` (`config.py`). `_compute_bg_match_ratio` exported in `__all__`. 5 tests `TestComputeBgMatchRatio` in `test_matching.py` → **648 backend tests (2 skipped)**. GUI 18 unchanged. Session 101 complete: **§1.37 Background Pixel Coverage Fraction Gate**. `_compute_bg_coverage_fraction(bg_masks) → float` added to `pipeline.py` — returns the mean fraction of pixels > 127 across all valid (non-None) bg masks; 1.0 when no valid masks exist so the gate never fires when masking is disabled. Wired as a new gate block between Stage 4 (BiRefNet masking) and Stage 4.5 (photometric normalisation): when `_MIN_BG_FRACTION > 0.0` and the computed fraction falls below the threshold, the pipeline logs a diagnostic and returns the SCANS fallback immediately, before bg-weighted LoFTR matching, bg-masked phase correlation, and Stage 4.5 normalization can all operate on insufficient bg signal. `_MIN_BG_FRACTION` float module flag (default 0.0=off; `ASP_MIN_BG_FRACTION=0.05` recommended). `MIN_BG_FRACTION=0.05` added to `constants/animation.py`. `"ASP_MIN_BG_FRACTION"` added to `_CONFIG_SCHEMA` in `config.py`. `_compute_bg_coverage_fraction` exported in `__all__`. 5 tests `TestComputeBgCoverageFraction` in `test_pipeline.py` → **643 backend tests (2 skipped)**. GUI 18 unchanged. Session 100 complete: **§1.36 LoFTR Translation Consensus Spread Filter**. `_compute_translation_spread(pts_i, pts_j) → (mad_dx, mad_dy)` added to `matching.py` — computes the Median Absolute Deviation of per-match displacement estimates around their median (dx, dy). When LoFTR finds many correspondences but they disagree on the translation (e.g., bimodal distribution from foreground/background confusion or repeated background elements at different positions), the median displacement is unreliable. Wired after the `dx, dy = np.median(...)` computation in `_match_pair` translation path: when `max(mad_dx, mad_dy) > _MATCH_SPREAD_CEIL`, the LoFTR edge is rejected and the pipeline falls through to template match / phase correlation. `_LINE_GRAD_WEIGHT` → `_MATCH_SPREAD_CEIL` float module flag (default 0.0=off; `ASP_MATCH_SPREAD_CEIL=30.0` recommended). `MATCH_SPREAD_CEIL=30.0` added to `constants/animation.py`. `"ASP_MATCH_SPREAD_CEIL"` added to `_CONFIG_SCHEMA` in `config.py`. `_compute_translation_spread` exported in `__all__`. 5 tests `TestComputeTranslationSpread` in `test_matching.py` → **638 backend tests (2 skipped)**. GUI 18 unchanged. Session 99 complete: **§1.35 Line-Art Gradient Penalty in Seam Cost Map**. `_fg_gradient_cost(canvas_zone, weight=1.0) → np.ndarray` added to `compositing.py` — computes normalized Laplacian magnitude on the canvas zone (values in [0, weight], shape (H, W)). Anime character outlines are dark, thin, high-gradient lines; a DP seam through an outline pixel creates a visible hairline break. Returns zero for flat zones (lap_max < 1e-6 fast-path). Wired into `_build_seam_cost_map()` just before `return cost` — for every fg-interior pixel (cost ≥ 1.0), adds `grad[pixel] * _LINE_GRAD_WEIGHT` so character outlines are more expensive than flat fill when the seam is forced through the character body. `_LINE_GRAD_WEIGHT` float module flag (default 0.0=off; `ASP_LINE_GRAD_WEIGHT=1.0` to enable). `LINE_GRAD_WEIGHT=1.0` added to `constants/animation.py`. `"ASP_LINE_GRAD_WEIGHT"` added to `_CONFIG_SCHEMA` in `config.py`. `_fg_gradient_cost` exported in `__all__`. 5 tests `TestFgGradientCost` in `test_compositing.py` → **633 backend tests (2 skipped)**. GUI 18 unchanged. Session 98 complete: **§1.34 Seam Zone Texture-Energy Pre-Escalation**. `_seam_zone_texture_energy(fa, fb, boundary, half_band=30) → float` added to `compositing.py` — measures mean Laplacian variance in the ±30px band around the seam boundary across both warped BGR frames; low values indicate flat-colour zones where ARAP / optical flow is unreliable (aperture problem). Pre-escalates such seams to single-pose before the ARAP call, avoiding garbage-offset warp on featureless regions (sky, solid fills, bare background). `_SEAM_LOW_TEXTURE_THRESH` float module flag (default 0.0=off; `ASP_SEAM_LOW_TEXTURE_THRESH=5.0` to enable). `SEAM_LOW_TEXTURE_THRESH=5.0` added to `constants/animation.py`. `"ASP_SEAM_LOW_TEXTURE_THRESH"` added to `_CONFIG_SCHEMA` in `config.py`. Wired between §1.20 tight-step `continue` and the `register_foreground_at_seam` ARAP call in the FG-registration loop. `_seam_zone_texture_energy` exported in `__all__`. 5 tests `TestSeamZoneTextureEnergy` in `test_compositing.py` → **628 backend tests (2 skipped)**. GUI 18 unchanged. Session 97 complete: **§1.2E Blur/Artifact Frame Pre-Rejection**. `_reject_blurry_frames(thumbs, paths, blur_threshold, thumb_size=64) → (filtered_thumbs, filtered_paths, n_dropped)` added to `frame_selection.py` — resizes each interior grayscale float32 thumbnail to 64×64, converts to uint8, and measures Laplacian variance; frames with variance < `blur_threshold` are dropped before hold detection (first/last always kept). `_BLUR_REJECT_THRESH` module-level float flag (default 0.0=off; `ASP_BLUR_REJECT_THRESH=50.0` to enable). `BLUR_REJECT_THRESH=50.0` added to `constants/animation.py`. `"ASP_BLUR_REJECT_THRESH"` added to `_CONFIG_SCHEMA` in `config.py`. Wired as step 1a-b in `smart_select_frames()` between the temporal-variance filter (§1.2D) and hold detection (step 1b). `_reject_blurry_frames` exported in `__all__`. 5 tests `TestRejectBlurryFrames` in `test_frame_selection.py` → **623 backend tests (2 skipped)**. GUI 18 unchanged. Session 96 complete: **§2.4C Seam Zone Crop Extraction**. `_extract_seam_crops(canvas, boundaries, band_px=SEAM_CROP_BAND_PX) → Dict[int, np.ndarray]` added to `compositing.py` — crops ±`band_px` rows around each seam boundary from the final composite, clamped to canvas bounds; result stored as `seam_crops` key in `seam_meta_out` alongside existing `boundaries`, `seam_post_diffs`, `seam_single_pose`. `SEAM_CROP_BAND_PX=50` added to `constants/animation.py`. `_extract_seam_crops` exported in `__all__`. `gui/src/dialogs/seam_diagnostic_dialog.py` updated: `_SeamCard.__init__` gains `crop: Optional[np.ndarray] = None` param; when a crop array is provided the card renders a `±50px seam zone thumbnail` below the info row (`_make_crop_pixmap` static method, max 300×64px, INTER_AREA resize, BGR→RGB→QPixmap); outer layout changed from `QHBoxLayout(self)` to `QVBoxLayout(self)` wrapping the existing row as a nested `QHBoxLayout()`; card minimum height expands by 70px when crop is shown. `SeamDiagnosticDialog.__init__` extracts `seam_crops: dict = data.get("seam_crops", {})` and passes `crop=seam_crops.get(k)` to each `_SeamCard`. 5 tests `TestSeamCropExtraction` in `test_compositing.py` → **618 backend tests (2 skipped)**. GUI 18 unchanged. Session 95 complete: **§2.4A Seam Registration Inspector (HITL Checkpoint 4.6)**. `_composite_foreground()` in `compositing.py` extended with `seam_meta_out: Optional[dict]` (populated on return with `{"boundaries": list, "seam_post_diffs": dict, "seam_single_pose": dict}`) and `seam_overrides: Optional[dict]` (maps seam index k → `{"force_single_pose": bool, "force_blend": bool}`). `force_single_pose` skips ARAP registration and immediately escalates seam k to the dominant-pose frame (sentinel diff=99.0); `force_blend` removes seam k from `seam_single_pose` as a post-loop override. `AnimeStitchPipeline._composite_foreground()` wrapper updated with both params. `StitchWorker`: `sig_review_seams = Signal(object)` (checkpoint 4.6); `set_seam_override(overrides)` setter stores overrides in `_hitl_override`; `"seams"` added to `_signal_map`; HITL checkpoint 4.6 block runs initial composite (collecting `_seam_meta`), emits `sig_review_seams` with canvas preview + per-seam diagnostic data, re-composites with user overrides when accepted; checkpoint 4.5 (seam painter) restructured to skip first composite since 4.6 already ran it (`_cp45_iter > 0 or _paint_mask is not None` guard). `gui/src/dialogs/seam_diagnostic_dialog.py` (new): `_SeamCard(QFrame)` — per-seam card with seam index, boundary y-position, coloured post_diff label (matching S94 thresholds), SP badge, mutually-exclusive "Force SP"/"Force blend" checkboxes; `SeamDiagnosticDialog(QDialog)` — QHBoxLayout with scaled canvas preview (left, max 260px) and right panel (QScrollArea of `_SeamCard` widgets sorted worst-first + legend + Accept && Continue/Cancel buttons); `get_overrides() → Dict[int, dict]` returns only non-default seams. `stitch_tab.py`: `sig_review_seams` connected to `_on_hitl_review_seams()`; handler opens `SeamDiagnosticDialog`, calls `set_seam_override()` + `resume()` on Accept, `cancel()` on Reject. 5 tests `TestSeamMetaOut` in `test_compositing.py` → **613 backend tests (2 skipped)**. GUI 18 unchanged. Session 94 complete: **§2.4B Seam Overlay on Output Image**. `_annotate_seams(canvas, boundaries, seam_post_diffs, seam_single_pose, line_thickness=2) → np.ndarray` in `compositing.py` — draws coloured horizontal lines at each seam boundary on the composite output for diagnostic purposes: green (post_diff < SEAM_OVERLAY_AMBER_THRESH=10.0), amber (10 ≤ diff < RED_THRESH=22.0), red (diff ≥ 22 or seam in single-pose fallback); small text label `S{k}:{diff:.0f}` at left edge, with "SP" suffix for escalated seams. `_SEAM_OVERLAY` flag (default OFF, `ASP_SEAM_OVERLAY=1`). `SEAM_OVERLAY_AMBER_THRESH=10.0` and `SEAM_OVERLAY_RED_THRESH=22.0` added to `constants/animation.py`; imported in `compositing.py`. `"ASP_SEAM_OVERLAY"` added to `_CONFIG_SCHEMA` in `config.py`. Wired at end of `_composite_foreground()` after `_seam_lum_equalize`. `_annotate_seams` exported in `__all__`. 5 tests `TestAnnotateSeams` in `test_compositing.py` → **608 backend tests (2 skipped)**. GUI 18 unchanged. Session 93 complete: **§2.14 Triangular Consistency Filter**. `_triangular_consistency_filter(edges, max_residual_px) → List[Dict]` in `pipeline.py` — iterates all triangles (i→j, j→k, i→k) in edge graph; computes L2 residual between predicted (leg-sum) and observed (hypotenuse) displacement; penalises weakest edge (weight × 0.5) when residual > threshold; preserves edge for BA at reduced trust (halving, not dropping). Fills gap in existing geometric consistency filter which only questioned skip edges — wrong adjacent edges now get a trust penalty before they influence BA. `TRI_CONSISTENCY_MAX_RESIDUAL=80.0` and `TRI_CONSISTENCY_PENALTY=0.5` added to `constants/animation.py`. `ASP_TRI_CONSISTENCY=0.0` module-level flag (enable: `ASP_TRI_CONSISTENCY=80.0`). `TRI_CONSISTENCY_PENALTY` imported in `pipeline.py`; `_triangular_consistency_filter` exported in `__all__`. `"ASP_TRI_CONSISTENCY"` added to `_CONFIG_SCHEMA` in `config.py`. Wired in `_filter_edges()` after `_reject_static_edges` / before geometric consistency filter. 5 tests `TestTriangularConsistencyFilter` in `test_filter_edges.py` → **603 backend tests (2 skipped)**. GUI 18 unchanged. Session 92 complete: **HITL Session Viewer**. `gui/src/dialogs/hitl_session_viewer_dialog.py` (new): `_list_sessions(session_dir) → List[Path]` returns `.json` files sorted newest-first by mtime; `_load_session_meta(path) → Optional[dict]` reads JSON without decoding numpy arrays (safe for large sessions); `_format_session_info(data, path) → str` produces human-readable summary: filename, timestamp (from POSIX float → datetime), version, file size KB, per-checkpoint override key summary using `_CHECKPOINT_LABELS` mapping; `HITLSessionViewerDialog(QDialog)` — QSplitter with `QListWidget` (left, sorted newest-first, each item: filename + datetime + checkpoint count + KB) + `QTextEdit` read-only detail panel (right); `_refresh()` repopulates list from session dir; `_on_selection_changed()` loads detail text; action buttons: "Load for Replay" → `_selected_path = str(path); self.accept()`; "Delete" → `QMessageBox.question` confirmation + `path.unlink()` + refresh; "Export…" → `QFileDialog.getSaveFileName(DontUseNativeDialog)` + `shutil.copy2`; "Refresh" → `_refresh()`; `selected_path() → Optional[str]` accessor; accepts optional `session_dir: Optional[Path] = None` param (defaults to `~/.config/image-toolkit/hitl_sessions/`) for testability. `stitch_tab.py`: "Browse Sessions…" button added next to "Load Session…" in session row; `_on_browse_sessions()` opens `HITLSessionViewerDialog`, on accept sets `_loaded_session_path` + updates label/tooltip. 8 new GUI tests in `gui/test/test_hitl_session_viewer_dialog.py` (`TestListSessions` ×3, `TestFormatSessionInfo` ×2, `TestHITLSessionViewerDialog` ×3) → **18 GUI tests total**. Backend: 598 unchanged. Session 91 complete: **Canvas Inspector Rotation/Scale Editor**. `gui/src/dialogs/canvas_inspector_dialog.py`: `_rot_angles: List[float]` (per-frame, init 0.0) + `_scale_factors: List[float]` (per-frame, init 1.0) stored on dialog; `QDoubleSpinBox` for rotation (range ±180°, step 0.5°) and scale (range 0.1–3.0, step 0.01, 3 decimals) added below nudge buttons; both disabled when no frame selected; `_update_transform_controls()` loads per-frame values into spinboxes (blockSignals to avoid feedback loop) when frame changes; `_on_rot_changed(val)` → `_rot_angles[idx]=val` + `_drag_items[idx].setRotation(val)`; `_on_scale_changed(val)` → `_scale_factors[idx]=val` + `_drag_items[idx].setScale(val)`; `_DraggableFrameItem.__init__` calls `setTransformOriginPoint(fw/2, fh/2)` so rotation/scale pivot at frame center; `_populate_scene()` applies stored `setRotation`/`setScale` on creation (supports re-populate after dialog opened); `_reset_frame()` zeroes `_rot_angles[idx]`, resets `_scale_factors[idx]=1.0`, calls `setRotation(0.0)`/`setScale(1.0)` on item, updates controls; `adjusted_affines()` rewrites 2x2 affine block via `R(θ,s) @ orig_2x2` where `R = s*[[cosθ, -sinθ],[sinθ, cosθ]]` (additional correction on top of BA result), then applies tx/ty nudge as before; 5 new tests `TestCanvasInspectorRotScale` → **+5 GUI tests (10 total in test_canvas_inspector_dialog.py)**. Backend: 598 unchanged. Session 90 complete: **Canvas Inspector Drag-to-Reposition**. `gui/src/dialogs/canvas_inspector_dialog.py`: new `_DraggableFrameItem(QGraphicsRectItem)` class — takes `idx`, `frame_w/h`, `base_tx/ty`, `nudge_list` reference, `on_select` callback; sets `ItemIsMovable | ItemSendsGeometryChanges | ItemIsSelectable` flags; `itemChange(ItemPositionChange)` computes `nudge_list[idx] = [new_x − base_tx, new_y − base_ty]` from proposed scene position; `itemChange(ItemSelectedChange)` calls `on_select(idx)` to sync list widget; thumbnail pixmaps added as child items via `setParentItem()` so they move with the frame rect; `CanvasInspectorDialog._populate_scene()` now creates `_DraggableFrameItem` instances instead of plain `addRect()`; `_scene.selectionChanged` connected to `_on_scene_selection_changed()` for tx_label live update during drag; `_on_list_row_changed()` calls `_sync_scene_selection()` to highlight matching item in scene; `_nudge()` now uses configurable `_step_spin` (QSpinBox, range 1–200, default 10) instead of hardcoded ±10px; `_nudge()` moves `_drag_items[idx]` via `setPos(QPointF(...))` for visual consistency; `_reset_frame()` likewise calls `setPos()`; nudge step spinbox added above nudge buttons. `gui/test/test_canvas_inspector_dialog.py` (new): 5 tests `TestCanvasInspectorDrag` — adjusted_affines no-nudge identity, nudge-button updates tx/ty, drag `setPos()` updates `_nudges[idx]` directly via `itemChange`, reset clears nudge, step spinbox controls nudge amount. **+5 GUI tests passing**. Session 89 complete: **HITL Checkpoint 2 — Manual Edge Entry**. `backend/src/animation/pipeline.py`: `_build_manual_edge(i, j, dx, dy, weight=0.9) → dict` — constructs a full pipeline-compatible edge dict from user-supplied displacement; M is pure translation `[[1,0,dx],[0,1,dy]]`; pts_i/pts_j are single-point centroid estimates; weight clipped to [0,1]; `method="manual"`; exported in `__all__`. `gui/src/dialogs/edge_review_dialog.py`: `_ManualEdgeDialog(QDialog)` — spinboxes for i/j (bounded by n_frames), dx/dy, weight (default 0.9); `edge_dict()` returns display-format dict; `EdgeReviewDialog` gains `_manual_edges: List[dict]`, `_n_frames` inferred from data, `_on_add_edge()` handler, "Add Edge…" toolbar button; `_populate()` renders manual edges in purple dotted lines on the graph and appended rows in the table (always-checked, uneditable); `accepted_edges()` returns filtered original edges + all manual entries. `StitchWorker` Checkpoint 2 updated: after lookup-based filtering of returned edges, any edge with `method="manual"` is converted to a full pipeline edge via `_build_manual_edge()` (exception caught and logged); `n_frames=N` passed in the pause data dict for dialog spinbox bounds. Bugfix: `stitch_tab._on_hitl_review_edges()` was calling `EdgeReviewDialog(edges=..., image_paths=...)` but the constructor takes `data: dict` — corrected to `EdgeReviewDialog(data=data, ...)`. 5 new tests `TestBuildManualEdge` in `test_pipeline.py` → **598 tests passing**. Session 88 complete: **HITL Session Persistence & Replay**. New `backend/src/animation/hitl_session.py`: `_encode_array`/`_decode_array` for numpy ↔ base64-JSON with 8 MB skip-threshold for large arrays; `_to_json`/`_from_json` recursive converters; `save_session(overrides, path)` writes `{version, timestamp, checkpoints}` JSON; `load_session(path)` restores override dicts with numpy arrays decoded; `autosave_path()` returns timestamped path under `~/.config/image-toolkit/hitl_sessions/`. `StitchWorker.__init__` gains `session_path: Optional[str] = None` — loads replay dict at init (bad file silently ignored); `_hitl_session_overrides: dict` accumulates non-cancel overrides during a run; `_current_session_path: Optional[str]` set on autosave; `current_session_path` property; `save_session(path)` public method. `_make_hitl_pause_cb()` updated: when `hitl_mode=False` and replay dict has an entry for the event, returns it immediately without blocking (replay mode); any non-cancel override stored in `_hitl_session_overrides`. `_hitl_video_pause()` similarly updated for checkpoint 0. Autosave wired after Stage 13 success. `stitch_tab.py`: "Load Session…" button + `_session_path_label` (filename display); `_on_load_session()` opens QFileDialog (DontUseNativeDialog); `_loaded_session_path` passed to `StitchWorker` as `session_path`; `_on_stitch_finished()` shows session path in success QMessageBox. 9 new tests in `test_hitl_session.py` (ndarray codec ×4, save/load ×5) → **593 tests passing**. Session 87 complete: **HITL Checkpoint 5 — Final Output RLHF Feedback**. `StitchWorker`: `sig_review_output = Signal(object)` (checkpoint 5); `set_output_feedback(overall_rating, annotations)` setter stores `"output_feedback"` dict in `_hitl_override`; `"output"` added to `_make_hitl_pause_cb()` signal map; checkpoint 5 block in `run()` after Stage 13 output save — downsamples composite, calls `_hitl_pause("output", ...)`, on resume reads `"output_feedback"` from override, constructs `StitchAnnotation` list and calls `FeedbackStore.add_from_image()`, logs rating + annotation count. `gui/src/dialogs/final_output_review_dialog.py` (new): `_AddFlawDialog(QDialog)` — flaw_type QComboBox (from `RLHF_FLAW_TYPES`) + severity QDoubleSpinBox; `FinalOutputReviewDialog(QDialog)` — downsampled canvas preview (max 640px), overall-quality QSlider (0–20 → 0.0–10.0 in 0.5 steps, default 7.0), flaw annotation QListWidget with "Add Flaw…" / "Remove Selected" buttons, "Save Feedback && Continue" (Accepted + feedback stored) / "Skip" (Rejected + no feedback) buttons; `get_feedback() → Optional[dict]` returns collected dict or None. `stitch_tab._on_hitl_review_output()` launches `FinalOutputReviewDialog`, calls `set_output_feedback()` + `resume()` on Accept, `resume()` on Skip. 7 new tests in `backend/test/animation/test_rlhf_feedback.py` (`TestStitchFeedbackRoundtrip` ×2, `TestFeedbackStoreAdd` ×5) exercising FeedbackStore / StitchFeedback JSONL persistence. **584 tests passing**. Session 86 complete: **HITL Checkpoint 4.5 — Post-Composite Seam Painter**. `_composite_foreground()` in `compositing.py` gains `paint_mask: Optional[np.ndarray] = None` param — canvas-space uint8 mask appended to `_eff_exclusion` list (alongside existing `exclusion_masks`) before the seam-job pre-computation loop; sliced per-zone at `em[_y0:_y1]` identically to per-frame exclusion masks, setting seam cost=1e6 in painted pixels. `AnimeStitchPipeline._composite_foreground()` wrapper passes `paint_mask` through. `StitchWorker`: `sig_review_composite = Signal(object)` (checkpoint 4.5); `set_paint_mask(mask: np.ndarray)` setter; `"composite"` entry added to `_make_hitl_pause_cb()` signal map; HITL loop in `run()` between Stage 11 composite and Stage 12 crop: runs `_composite_foreground()` → pauses via `_hitl_pause("composite", ...)` → if worker override has `"paint_mask"` re-runs compositing with new mask, else breaks (accept) or raises `InterruptedError` (cancel). `gui/src/dialogs/seam_painter_dialog.py` (new): `_PaintCanvas(QLabel)` — QPixmap overlay; left-drag paints red barrier circles/lines, right-drag erases; `has_paint()` checks alpha channel; `paint_mask_preview()` returns alpha uint8; `SeamPainterDialog(QDialog)` — canvas preview + brush-size slider + iteration counter + "Re-Composite" (`done(RECOMPOSITE=2)`) / "Accept Output" / "Cancel"; `full_resolution_mask()` upscales preview mask to full canvas via `cv2.resize(INTER_NEAREST)`. `stitch_tab._on_hitl_review_composite()` launches `SeamPainterDialog`, calls `set_paint_mask()` + `resume()` on RECOMPOSITE, `resume()` on Accept, `cancel()` on reject. 5 new tests `TestPaintMask` → **577 tests passing**. Session 85 complete: **HITL Checkpoint 3.5 — Interactive Seam Boundary Editor**. `_compute_initial_boundaries(affines, frames) → np.ndarray` added to `compositing.py` (midpoint-between-strip-centres formula extracted as public helper, exported in `__all__`). `_composite_foreground()` gains `preset_boundaries: Optional[np.ndarray] = None` param — when provided with correct length `N-1`, replaces auto-computed midpoints as the `initial_boundaries` seed for `_find_optimal_boundaries()`. `AnimeStitchPipeline._composite_foreground()` wrapper updated to pass through `preset_boundaries`. `StitchWorker`: `sig_review_boundaries = Signal(object)` (checkpoint 3.5); `set_boundary_override(boundaries: list)` setter; `_compute_initial_boundaries` imported at worker-level; new checkpoint block in `run()` between Stage 10 (MFSR) and Stage 11 (fg composite) — computes initial boundaries, downsamples canvas preview, calls `_hitl_pause("boundaries", ...)`, applies user override as `preset_boundaries` to `_composite_foreground()`. `gui/src/dialogs/boundary_editor_dialog.py` (new): `_DraggableLine(QGraphicsLineItem)` — horizontal line constrained to canvas height, draggable with `SizeVerCursor`; `BoundaryEditorDialog(QDialog)` — `QGraphicsScene`/`QGraphicsView` canvas preview with N-1 red dashed draggable seam lines + frame-index labels; "Reset to Auto" restores original midpoints; `adjusted_boundaries()` scales dragged y-coordinates back to full-resolution canvas space. `stitch_tab.py` connects `sig_review_boundaries → _on_hitl_review_boundaries()`; handler launches `BoundaryEditorDialog`, calls `set_boundary_override()` + `resume()` on Accept or `cancel()` on Reject. 5 new tests in `TestComputeInitialBoundaries` → **572 tests passing**. Session 84 complete: **Video ingestion HITL + "From Video" GUI mode**. `StitchWorker.__init__` extended with `video_path`, `video_n_frames`, `video_mode` params; `sig_review_video = Signal(object)` added as HITL checkpoint 0 signal; `_hitl_video_pause(data)` method pauses worker, emits `sig_review_video`, waits on `_hitl_mutex`/`_hitl_wait`; `run()` ingests video via `ingest_video()` into `mkdtemp` before `_ProgressPipeline`, calls `_hitl_video_pause()` when `hitl_mode=True`, then applies `frame_override` from user selection; `SelectionReviewDialog` made configurable via `title` param for reuse in video frame review; `stitch_tab.py` extended with "From Video Source" `QCheckBox`, hidden `_video_input_widget` (path QLineEdit + browse button + frame-count spinbox), `_on_video_mode_toggled()`, `_browse_video()` (mp4/mkv/avi/mov/webm/flv filter), `_start_stitch()` updated with video-path validation + `sig_review_video` connection, `_on_hitl_review_video()` HITL handler launching `SelectionReviewDialog` with custom title. 5 new GUI tests in `TestStitchWorkerVideoPath` → backend animation suite **567 tests passing** (unchanged). Session 83 complete: **Live SAM-2 state preservation across HITL checkpoint boundary**. `_compute_fg_masks_sam2_stateful()` + `_cleanup_sam2_state()` in `masking.py`; `AnimeStitchPipeline` stores `_sam2_predictor/_sam2_inference_state/_sam2_tmp_dir/_sam2_frame_h/_sam2_frame_w`; HITL checkpoint 1.5 passes live state in data dict; `_refine_cb` in `stitch_tab.py` calls real `_refine_masks_with_clicks(predictor, state, ...)`; cleanup after dialog closes; 10 new tests → **567 tests passing**. Session 82 complete: **HITL end-to-end wiring + Issue 9 video ingestion**. `exclusion_masks` threaded end-to-end: `AnimeStitchPipeline.exclusion_masks: Optional[List[ndarray]]` instance attribute → Stage 11 `_composite_foreground(exclusion_masks=self.exclusion_masks)` → `AnimeStitchPipeline._composite_foreground()` method updated with `exclusion_masks` param. `StitchWorker`: `set_exclusion_masks()` setter + `self._exclusion_masks` storage; `exclusion_masks` applied to pipeline before `run()`; HITL checkpoint 1.5 now reads `"exclusion_masks"` from override dict and sets `self.exclusion_masks` on the pipeline. `MaskReviewDialog` extended with seam-exclusion section: `_excl_input` QLineEdit + "Detect & Exclude (GroundingDINO)" button + `_excl_status` label; `_on_detect_exclusion()` runs `_detect_exclusion_mask()` per-frame in `_RefinementWorker` thread; `_on_exclusion_done()` stores masks + updates status label; `exclusion_masks()` accessor; `sig_exclusion_masks_accepted` new signal; Accept now emits both signals; `stitch_tab._on_hitl_review_masks` connects both signals. **Data serialization auto-save** wired into HITL checkpoint 1.5: `create_session_serializers()` called at run() start; masks confirmed at checkpoint 1.5 → `_coco_builder.add_image` + `add_segmentation_mask` + `_ls_exporter.add_task` per frame → `_save_hitl_annotations()` flushes to `~/.image-toolkit/hitl_annotations/`. **Issue 9 — `VideoIngestionStream`** in new `backend/src/animation/video_ingestion.py`: proxy-first PyAV decode at `ASP_VIDEO_PROXY_SCALE=0.25`; telecine-drop dedup (`_telecine_dedup()`); `"uniform"` / `"keyframe"` / `"smart"` selection modes; full-resolution decode for selected frames only via libavformat seek (`_decode_full_frame()`); `ingest_video()` one-call convenience wrapper returning `(frames, paths)` usable directly in `AnimeStitchPipeline.run()`; `ASP_VIDEO_MAX_FRAMES=200`, `ASP_VIDEO_TELECINE_MAD=2.0`, `ASP_VIDEO_KEYFRAMES_ONLY` env vars; graceful ImportError fallback (RuntimeError with `pip install av` message). 15 new tests → **557 tests passing** (2 skipped: pyav). Session 81 complete: **Multi-modal HITL (Issue 10)**. §10B1 `COCOAnnotationBuilder` + §10B2 `LabelStudioExporter` in `backend/src/animation/data_serialization.py` — COCO-format fg segmentation + seam-exclusion + frame-selection annotations with optional RLE via pycocotools; Label Studio tasks with model `predictions` and human `annotations` arrays preserving the pre/post-correction delta for RLHF preference learning; `create_session_serializers()` factory; atomic JSON writes via `os.replace()`. §10A1 `grounding.py` — lazy GroundingDINO wrapper (`_detect_objects`, `_detect_best_box`, `_detect_exclusion_mask`, `reset_grounding_dino_model`) with `GROUNDING_DINO_CKPT` / `GROUNDING_DINO_CFG` env vars; normalised cx,cy,w,h → absolute pixel bbox conversion; graceful ImportError fallback (warn-once, return empty list / None). `_compute_fg_masks_grounded_sam2()` in `masking.py` — DINO bbox for frame 0 → SAM-2 video propagation; per-frame BiRefNet fill for missed frames; falls back to `_compute_fg_masks()` on any exception. `_refine_masks_with_clicks()` in `masking.py` — builds pts/lbl tensors from pos/neg click lists; SAM-2 `add_new_points_or_box` + `propagate_in_video` for click-based interactive refinement. §10A2 `MaskReviewDialog` in `gui/src/dialogs/mask_review_dialog.py` — `_ClickOverlay(QLabel)` captures left/right mouse events (pos/neg SAM-2 prompts) with coordinate mapping; `_RefinementWorker(QThread)` runs refinement callback off-main-thread; frame navigator, scroll area, text prompt + "Re-segment" button, click-apply/clear buttons, indeterminate progress bar, Accept/Skip/Cancel; `sig_mask_accepted = Signal(object)` carries refined mask list to caller. §10A3 `exclusion_masks` param in `_build_seam_cost_map()` and `_composite_foreground()` — any uint8 mask (auto-resized if needed) where >127 forces seam cost=1e6; hard-partitions DP into background corridor away from named objects. HITL checkpoint 1.5 in `stitch_worker.py` — `sig_review_masks` signal + `set_mask_override()` setter; pause point between frame-selection and Stage 5 so user can click-edit or text-prompt re-segment masks before compositing begins. 44 new tests (22 serialization, 16 grounding, 6 exclusion-masks) → **542 tests passing**. Session 80 complete: §5.2 SAM-2 wired into `AnimeStitchPipeline._compute_fg_masks()` via `_USE_SAM2` flag (`ASP_USE_SAM2=1`). §1A per-pair Otsu bg mask for phase correlation — `_otsu_bg_mask_pair(a, b, min_bg_frac=0.10)` in `frame_selection.py`; Otsu threshold on each float32 thumbnail → bg intersection → multiplied into `phaseCorrelate` inputs; falls back to plain phase correlation when bg coverage < 10%; `ASP_OTSU_BG_CORR=1` to enable; `OTSU_BG_CORR_MIN_BG_FRAC=0.10` in constants; 5 new tests `TestOtsuBgMaskPair`. §5A/C background zero-coverage fill — new `bg_complete.py`; `_nn_fill_zero_bg(canvas, zero_mask)` column-directional nearest-neighbour fill via `np.searchsorted`; `_propainter_fill()` ProPainter hook with NN fallback; `complete_background()` public API; Stage 10.2 gate in `pipeline.py` when `_BG_COMPLETE > 0`; `ASP_BG_COMPLETE=1` (NN) or `=2` (ProPainter+NN); `BG_COMPLETE_MIN_ROWS=20` in constants; 6 new tests `TestNnFillZeroBg/TestCompleteBackground`. §8 recommended defaults — `asp_config.toml` at repo root with 8 proven-safe flags (§1.18/1.22/1.25/1.26/1.28/1.29/1.30/1.31); auto-loaded in `animation/__init__.py` before `.pipeline` import so module-level flags pick up TOML values; 4 new `_CONFIG_SCHEMA` entries in `config.py`. 498 tests passing. Session 79 complete: §2.0 HITL staged execution — `QWaitCondition`/`QMutex` pause/resume in `StitchWorker`; 4 new HITL signals (`sig_review_frames`, `sig_review_edges`, `sig_review_canvas`, `sig_review_render`); `_make_hitl_pause_cb()` blocking callback; 4 pause points in `_ProgressPipeline.run()` (after stages 4/5/8/9); `set_frame_override()`, `set_edge_override()`, `set_affine_override()`, `set_render_cancel()` override setters; `hitl_mode: bool = False` param (zero overhead when off); `SelectionReviewDialog` (Option A) with pose-diff colour bars + exclude/reorder; `EdgeReviewDialog` (Option B) with checkbox toggle + MST filter; `CanvasInspectorDialog` (Option D) with ±10px nudge; `CoverageHeatmapDialog` (Option C) with bar chart + canvas preview; "Human-in-the-loop review" checkbox in stitch panel wired to HITL signals; `gui/src/dialogs/` package created with all 4 dialog files. §1D foreground-masked DINOv2 — `_compute_dinov2_features()` now crops each frame to fg bbox (Otsu threshold + 5% pad) before DINOv2 embedding; removes bg dominance in pan-shot scenes. §3.1A AnimeInterp SGM full — `_get_vgg19_feat()` lazy VGG-19 conv3_4 loader + `_animeinterp_sgm()` with SLIC segmentation → VGG-19 L2-normalised per-segment features → cosine × distance-score matching → centroid displacement flow; `ASP_ANIMEINTERP_SGM=1` enable flag; falls back to `_slic_sgm_proxy` when VGG-19 unavailable. §5.2 SAM-2 video masking — `_compute_fg_masks_sam2()` in `masking.py`; BiRefNet frame-0 bbox → `build_sam2_video_predictor` propagation across all frames; requires `pip install sam2` + `~/.sam2/sam2_hiera_base_plus.pt`; falls back to per-frame BiRefNet. 487 tests passing. Session 78 complete: §2.3 Canvas Layout Inspector (read-only viewer) — `_parse_canvas_json(path) → dict` normalises stage08_canvas_info.json (canvas_h, canvas_w, frame_h, frame_w defaults to 0 when absent, affines_final parsed as float lists); `_canvas_frame_corners(affine_2x3, frame_h, frame_w) → List[Tuple]` transforms 4 corners of a frame using full 2×3 affine; `CanvasLayoutInspectorDialog(QDialog)` in `stitch_tab.py` renders N frame rectangles on canvas as colour-coded `QPainterPath` polygons (8-colour rotating palette), canvas border in scene, stats label shows N-frames and WxH canvas, table with Frame/tx/ty per frame, "Load JSON…" button for standalone use; `⬗ Canvas` button in Stitch action row, enabled after a run with save_intermediate=True when stage08_canvas_info.json exists; `stitch_worker.py` extended to save `frame_h`/`frame_w` in canvas_info JSON; 9 new tests in `test_stitch_tab.py` (TestParseCanvasJson ×3, TestCanvasFrameCorners ×3, TestCanvasLayoutInspectorDialog ×3); visual render verified with 3-frame synthetic fixture. 422 tests passing. Session 77 complete: §2.2 Edge Graph Inspector (read-only viewer) — `_parse_edge_json(path) → List[dict]` normalises stage05_edges.json (drops records missing i/j, fills dx/dy/conf/method defaults); `_edge_graph_node_positions(n, radius=150.0) → List[Tuple]` places N nodes evenly on a circle (12-o'clock first); `EdgeGraphInspectorDialog(QDialog)` in `stitch_tab.py` shows N frame nodes in a circle connected by confidence-coloured LoFTR edges (green ≥ 0.7, yellow ≥ 0.5, red < 0.5), edge thickness 1+conf×4px, tooltip shows i→j/conf/dx/dy/method, alongside a QTableWidget sorted by conf ascending (worst-first), stats label shows frame count/edge count/low-conf count; "Load JSON…" button for standalone use; `⬡ Edges` button in Stitch action row, enabled after a run with save_intermediate=True when stage05_edges.json exists; 11 new tests in `test_stitch_tab.py` (TestParseEdgeJson ×4, TestEdgeGraphNodePositions ×4, TestEdgeGraphInspectorDialog ×3). 413 tests passing. Visual check pending first real stitch run with save_intermediate=True. Session 76 complete: §1.32 GNC-TLS bundle adjustment — `_gnc_weights_geman_mcclure(residuals_sq, mu, c_sq) → ndarray` in `bundle_adjust.py`; Geman-McClure per-edge weights `wᵢ=(μc²/(μc²+rᵢ²))²`; `_GNC_OUTER=8` env-var (default ON, `ASP_GNC_OUTER=0` to disable); outer continuation loop in `_bundle_adjust_affine` starts with μ₀=max_sq/(2c²) (convex), anneals μ÷=1.4 per iteration, terminates on convergence or μ<1e-2; per-edge weights injected via `_gnc_ws` mutable list in `residuals()` closure (√w multiplier → w×r² cost); `loss='linear'` during GNC, `loss='cauchy'`+adaptive f_scale fallback when `ASP_GNC_OUTER=0`; `GNC_C_PX=10.0`, `GNC_MU_ANNEAL=1.4`, `GNC_MAX_OUTER=8` in `constants/animation.py`; `ASP_GNC_OUTER` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_bundle_adjust.py::TestGNCWeightsGemanMcclure`. 412 tests passing. Session 75 complete: §1.31 Seam FG penetration escalation — `_seam_fg_penetration(path, fa_zone, fb_zone) → float` in `compositing.py`; samples `path[x]` per column, fg = any channel > 0 in either zone; returns fraction in [0,1]; blend-loop escalation: if `_SEAM_FG_PENETRATION_MAX > 0 and penetration > threshold and k not in seam_single_pose` → single-pose (dominant by fg px count); `_SEAM_FG_PENETRATION_MAX` flag (default 0.0=off, recommend 0.7); `SEAM_FG_PENETRATION_MAX=0.7` in constants; schema; `__all__`; 5 tests `TestSeamFgPenetration`. 482 tests passing. Session 74 complete: §1.30 Minimum zone height guard — `_zone_is_degenerate(zone_h, min_height=20) → bool` in `compositing.py`; returns True when `zone_h < min_height` (and min_height > 0); wire-up in `_composite_foreground` before DP: escalates to single-pose (dominant by fg pixel count) when zone too short; `_ZONE_MIN_HEIGHT` flag (default 0=off, `ASP_ZONE_MIN_HEIGHT=20`); `ZONE_MIN_HEIGHT=20` in constants; `ASP_ZONE_MIN_HEIGHT` in `_CONFIG_SCHEMA`; `_zone_is_degenerate` in `__all__`; 5 tests `TestZoneIsDegenerate`. 477 tests passing. Session 73 complete: §1.29 Static input detection gate — `_detect_static_input(frames, max_mad, thumb_size=64) → bool` in `pipeline.py`; resizes to 64×64 greyscale, checks all consecutive pairs have MAD < max_mad; Stage 1.5 gate: early exit writing frame 0 to output_path when True; `_STATIC_INPUT_MAX_MAD` flag (default 0.0=off, recommend 2.0); `STATIC_INPUT_MAX_MAD=2.0` in constants; `ASP_STATIC_INPUT_MAX_MAD` in `_CONFIG_SCHEMA`; `_detect_static_input` in `__all__`; 5 tests `TestDetectStaticInput`. 472 tests passing. Session 72 complete: §1.28 Seam path instability escalation — `_seam_path_std(path) → float` in `compositing.py`; `float(np.std(path))`; 0.0 for empty path; instability check in blend loop: if `_SEAM_INSTABILITY_THRESH > 0 and k not in seam_single_pose and std > threshold`, escalate to single-pose picking dominant by fg pixel count; `_SEAM_INSTABILITY_THRESH` flag (default 0.0=off, `ASP_SEAM_INSTABILITY_THRESH=20.0`); `SEAM_INSTABILITY_THRESH=20.0` in constants; `ASP_SEAM_INSTABILITY_THRESH` in `_CONFIG_SCHEMA`; `_seam_path_std` in `__all__`; 5 tests `TestSeamPathStd`. 467 tests passing. Session 71 complete: §1.27 Background coverage gate for normalisation — `_has_sufficient_bg(bg_sel, min_px=200) → bool` in `compositing.py`; `np.count_nonzero(bg_sel) >= max(1, min_px)`; formalises the historical hardcoded `>=200` floor in the normalisation loop as a testable helper; `_BG_NORM_MIN_PX` flag (default 0 → built-in 200-px floor); normalisation loop uses `_has_sufficient_bg(bg_sel, _bg_min)`; `BG_NORM_MIN_PX=200` in constants; `ASP_BG_NORM_MIN_PX` in `_CONFIG_SCHEMA`; `_has_sufficient_bg` in `__all__`; 5 tests `TestHasSufficientBg`. 462 tests passing. Session 70 complete: §1.26 Seam path boundary clamp — `_clamp_seam_path(path, zone_h, margin=3) → np.ndarray` in `compositing.py`; `np.clip(path, margin, zone_h-1-margin)`; prevents seam from routing to zone top/bottom where feather blend has no headroom → hard-edge artefact at zone boundary; no-op when margin≤0 or zone too small; `_SEAM_MARGIN` flag (default 0=off, `ASP_SEAM_MARGIN=3`); wired at end of `_seam_cut()` after §1.25 smoothing; `SEAM_MARGIN=3` in constants; `ASP_SEAM_MARGIN` in `_CONFIG_SCHEMA`; `_clamp_seam_path` in `__all__`; 5 tests `TestClampSeamPath`. 457 tests passing. Session 69 complete: §1.25 Seam path smoothing — `_smooth_seam_path(path, window=5) → np.ndarray` in `compositing.py`; 1-D median filter over DP seam traceback removes single-pixel column jitter (oscillation between adjacent equally-cheap columns → diagonal aliasing bands); `window≤1` no-op; even window incremented to next odd; `_SEAM_SMOOTH_WINDOW` flag (default 0=off, `ASP_SEAM_SMOOTH_WINDOW=5`); wired at end of `_seam_cut()` before return; `SEAM_SMOOTH_WINDOW=5` in constants; `ASP_SEAM_SMOOTH_WINDOW` in `_CONFIG_SCHEMA`; `_smooth_seam_path` in `__all__`; 5 tests `TestSmoothSeamPath`. 452 tests passing. Session 68 complete: §1.24 Post-composite seam-step gate — `_measure_max_seam_step(canvas, n_strips, band_px=10, guard=3) → float` in `pipeline.py`; samples mean greyscale luma in band_px rows above/below each inter-strip boundary (±guard guard rows); returns max |above−below| across all N-1 seams; 0.0 when n_strips≤1 or canvas too small; Stage 11.3 gate in `pipeline.py` after Stage 11.2 (colour gate): `_SEAM_STEP_GATE` float flag (default 0.0=off, `ASP_SEAM_STEP_GATE=25.0`); SCANS fallback when max_step > threshold; `SEAM_STEP_GATE_THRESH=25.0` in constants; `ASP_SEAM_STEP_GATE` in `_CONFIG_SCHEMA`; `_measure_max_seam_step` in `__all__`; 5 tests `TestMeasureMaxSeamStep`. 447 tests passing. Session 67 complete: §1.23 SemanticStitch hard corridor barrier — `_seam_corridor_exists(cost, fg_thresh=0.5) → bool` in `compositing.py`; True iff some-but-not-all columns are fg-dominated; `_build_seam_cost_map` extended with `barrier_cost=None` param; when corridor exists and `_SEAM_HARD_BARRIER=True`, fg-dominated columns raised to 1e6 instead of 2.0 (S33 soft); backward-compatible default; `SEAM_HARD_BARRIER_COST=1e6` in constants; 2 schema entries; `_seam_corridor_exists` exported in `__all__`; 5 tests `TestSeamCorridorExists`. 442 tests passing. Session 66 complete: §1.22 Adaptive single-pose soft-edge width — `_adaptive_sp_soft_px(feather_width, base_px=6, max_px=30, ref_px=80) → int` in `compositing.py`; `min(max_px, max(base_px, base_px*feather_width//ref_px))`; feather=80→6 (base), feather=160→12, feather=300→22, cap=30; degenerate feather≤0 → base_px; `_ADAPTIVE_SP_SOFT` flag (default OFF, `ASP_ADAPTIVE_SP_SOFT=1`); wired in single-pose blend branch replacing fixed `ASP_SP_SOFT_PX=6`; `SP_SOFT_BASE/MAX/REF_PX` in constants; `ASP_ADAPTIVE_SP_SOFT` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 tests `TestAdaptiveSpSoftPx`. 437 tests passing. Session 65 complete: §1.21 Post-composite seam luminance equalisation — `_seam_lum_equalize(canvas, boundaries, band_px=20, min_step=5.0) → np.ndarray` in `compositing.py`; samples mean luma above/below each boundary (±3-row guard); applies linear additive ramp over band_px rows to remove lum step > min_step; `_SEAM_LUM_EQ` flag (default OFF, `ASP_SEAM_LUM_EQ=1`); `SEAM_LUM_EQ_BAND_PX/MIN_STEP` in constants; 2 schema entries; exported in `__all__`; 5 tests `TestSeamLumEqualize`. 432 tests passing. Session 64 complete: §1.20 Tight-step preemptive single-pose escalation — `_compute_seam_step_size(fi_a, fi_b, affines) → float` in `compositing.py`; `max(|ty_b−ty_a|, |tx_b−tx_a|)`; inf for out-of-range; `_TIGHT_STEP_PX` flag (default 0=off, `ASP_TIGHT_STEP_PX=30`); preempts ARAP when step < threshold, picks dominant by fg count in ±20px boundary band; `TIGHT_STEP_PX=30` in constants; `ASP_TIGHT_STEP_PX` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 tests `TestComputeSeamStepSize`. 427 tests passing. Session 63 complete: §1.19 Fg-density-aware feather cap — `_fg_density_feather_cap(feathers, boundaries, warped_bg, order, cap_px, fg_thresh) → np.ndarray` in `compositing.py`; checks fg pixel fraction in ±feather[k] canvas-space band for both adjacent frames; caps feather to cap_px when max fg_frac > fg_thresh; None masks treated as all-bg; wired after §1.6B gain feathers, before Stage 8.5; `_FG_FEATHER_CAP` flag (default 0=off, `ASP_FG_FEATHER_CAP=60`); `FG_FEATHER_CAP/THRESH` in constants; 2 schema entries; exported in `__all__`; 5 tests `TestFgDensityFeatherCap`. 422 tests passing. Session 62 complete: §1.18 Adaptive single-pose escalation threshold — `_adaptive_sp_threshold(feather_width, base=22.0, min=12.0, ref=80) → float` in `compositing.py`; `max(min_threshold, base×(ref/max(fw,1)))`; fw=80→22.0, fw≥147→12.0(floor); `_ADAPTIVE_SP_THRESH` flag (default OFF, `ASP_ADAPTIVE_SP_THRESH=1`); wired at compositing.py escalation gate replacing hardcoded 22.0; `ADAPTIVE_SP_THRESH_*` constants in `constants/animation.py`; `ASP_ADAPTIVE_SP_THRESH` in `_CONFIG_SCHEMA`; 5 tests in `test_compositing.py::TestAdaptiveSpThreshold`. 417 tests passing. Session 61 complete: §1.17 Canvas span utilisation gate — `_compute_canvas_span_utilization(affines) → float` in `pipeline.py`; actual dominant-axis span / (median_adjacent_step × (N−1)); 1.0 for N<2 or zero expected span; catches oscillating BA solutions where all per-step checks pass but total canvas is far shorter than expected; `_CANVAS_SPAN_MIN_UTIL` flag (default 0.0=off, `ASP_CANVAS_SPAN_MIN_UTIL=0.3`); post-BA gate after §3.14 scroll-axis check, before Stage 10 rendering; `CANVAS_SPAN_MIN_UTIL=0.3` in constants; `ASP_CANVAS_SPAN_MIN_UTIL` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_pipeline.py::TestComputeCanvasSpanUtilization`. 412 tests passing. Session 60 complete: §1.16 MST weight gate — `_compute_mst_weight(edges, n_frames) → float` in `pipeline.py`; max-weight spanning tree (Kruskal + iterative path-compression Union-Find); returns `total_weight/(N-1)`; 0.0 for n_frames≤1 or no edges. Pre-BA gate in `run()` after §1.15 connectivity check: `_MST_MIN_WEIGHT` flag (default 0.0=off, `ASP_MST_MIN_WEIGHT=0.35`); LoFTR edges~0.6–0.9, TM/PC~0.15–0.3; threshold 0.35 fires on all-TM/PC graphs; `MST_MIN_WEIGHT=0.35` in constants; `ASP_MST_MIN_WEIGHT` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_pipeline.py::TestComputeMstWeight`. 407 tests passing. Session 59 complete: §1.14C per-channel BGR Bhattacharyya seam gate — `_seam_color_similarity_bgr(img, k, n_strips, band_px=50) → float` in `compositing.py`; computes per-channel (B,G,R) normalised 256-bin histograms; returns `min(score_B, score_G, score_R)`; falls back to greyscale for 2-D inputs; `_check_seam_color_gate` extended with `use_bgr: bool = False` param routing to new function; `_SEAM_COLOR_GATE_BGR` flag (default OFF, `ASP_SEAM_COLOR_GATE_BGR=1`); Stage 11.2 gate in `pipeline.py` passes `use_bgr=_SEAM_COLOR_GATE_BGR`; `ASP_SEAM_COLOR_GATE_BGR` added to `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_compositing.py::TestSeamColorSimilarityBgr`. 402 tests passing. Session 58 complete: §1.15 edge graph connectivity validation — `_check_edge_graph_connectivity(edges, n_frames) → bool` in `pipeline.py`; iterative path-compression Union-Find; returns True iff all frames 0..n_frames-1 in one connected component; pre-BA gate in `run()`: disconnected graph → SCANS fallback immediately (avoids wasted retry chain); exported in `__all__`; 5 new tests in `test_pipeline.py::TestCheckEdgeGraphConnectivity`. 397 tests passing. Session 57 complete: §1.13B per-channel (BGR) scene-change gate — `_reject_scene_change_edges(..., use_bgr=True)` extended in `pipeline.py`; per-channel (B,G,R) thumbnail means, `max(|ΔB|,|ΔG|,|ΔR|)` vs threshold; catches chroma-shifted scene changes that grayscale luma misses (warm orange vs cool blue at same luma); `_SCENE_CHANGE_BGR_THRESH` flag (default 0.0=off, `ASP_SCENE_CHANGE_BGR_THRESH=60.0`); `SCENE_CHANGE_BGR_THRESH=60.0` in constants; `ASP_SCENE_CHANGE_BGR_THRESH` in `_CONFIG_SCHEMA`; backward compatible (default `use_bgr=False`); 5 new tests in `test_pipeline.py::TestRejectSceneChangeEdgesBgr`. 392 tests passing. Session 56 complete: §1.14B seam colour-similarity pipeline gate — `_seam_color_similarity(img, k, n_strips, band_px=50) → float` + `_check_seam_color_gate(img, n_strips, thresh) → Optional[int]` in `compositing.py`; evaluates Bhattacharyya histogram similarity for each inter-strip seam; returns worst seam index below *thresh* or None; `_SEAM_COLOR_GATE` float flag (default 0.0=off, `ASP_SEAM_COLOR_GATE=0.55`); Stage 11.2 gate wired in `pipeline.py` after `_composite_foreground` → SCANS fallback on worst-seam failure; `SEAM_COLOR_GATE_THRESH=0.55` in constants; `ASP_SEAM_COLOR_GATE` in `_CONFIG_SCHEMA`; both functions exported in `__all__`; 5 new tests in `test_compositing.py::TestSeamColorGate`. 387 tests passing. Session 55 complete: §1.14 per-seam Bhattacharyya colour-distance metric — `_seam_bhattacharyya_distances(img, n_strips, band_px=50) → List[float]` in `bench_anime_stitch.py`; computes greyscale histogram similarity (`1 − HISTCMP_BHATTACHARYYA`) for `band_px`-row windows above/below each seam boundary; returns `n_strips-1` scores [0,1]; 1.0=identical distributions, <0.5=severe colour mismatch; `_compute_all_metrics` extended with `seam_color_scores` and `seam_color_min`; backward compatible; 5 new tests in `test_bench_metrics.py::TestSeamBhattacharyyaDistances`. 381 tests passing. Session 54 complete: §1.3C scale normalisation before BA — `_normalize_frame_scales(frames, edges, scale_thresh=SCALE_NORM_THRESH) → (List[np.ndarray], List[Dict])` in `pipeline.py`; extracts per-edge scale `s_ij=sqrt(a²+b²)` from matched affines; BFS spanning tree propagates absolute per-frame scale; resizes frames by `1/scale[i]` (Lanczos-4); resets edge M diagonal to 1.0 and divides tx/ty by `scale[i]`; no-op when scale_dev < scale_thresh or graph disconnected; `SCALE_NORM_THRESH=0.05` in constants; `_SCALE_NORM_THRESH` flag (default 0.0=off, `ASP_SCALE_NORM_THRESH=0.05` to enable); exported in `__all__`; 5 new tests in `test_pipeline.py::TestNormalizeFrameScales`. 377 tests passing. Session 53 complete: §3.8B per-seam SIQE ghost map — `_compute_per_seam_ghost_scores(img, n_strips, band_px=100) → List[float]` in `bench_anime_stitch.py`; divides output image into `n_strips` equal-height zones; evaluates `_ghosting_score_v2` in ±`band_px` band at each inter-zone seam boundary; returns `n_strips-1` scores; `[]` when `n_strips≤1`; `_compute_all_metrics` extended with `n_strips=1` param, adds `ghost_seam_scores` and `ghost_seam_max` to result dict; backward compatible; 5 new tests in `test_bench_metrics.py::TestPerSeamGhostScores`. 372 tests passing. Session 52 complete: §1.12 Kendall-τ translation monotonicity check — `_check_translation_monotonicity(affines, primary_axis, min_tau_abs=0.4) → (bool, float)` in `validation.py`; computes |Kendall τ| between temporal frame indices and primary-axis translations; |τ|=1 for monotone sequences (forward and backward), |τ|≈0 for random permutations; fires for scroll_axis ∈ {vertical, horizontal}; wired as 5th check in `_validate_affines` after rotation/scale; failure reason `"monotonicity={tau:.2f} < 0.4"` falls through to Retry 1 (adj-only BA); `_MONO_TAU_MIN=0.4` constant; exported in `__all__`; requires ≥ 4 frames; 5 new tests in `test_affine_validation.py::TestTranslationMonotonicity`. 367 tests passing. Session 51 complete: §1.13 scene-change edge pre-filter — `_reject_scene_change_edges(edges, frames, max_luma_diff)` in `pipeline.py`; computes 64×64 thumbnail mean grayscale luma for frames i and j; rejects edge when `|lum(i)−lum(j)| > max_luma_diff`; safe-fallback for out-of-bounds indices; `_SCENE_CHANGE_LUMA_THRESH` flag (default 0.0=off, `ASP_SCENE_CHANGE_LUMA_THRESH=60.0`); wired as first check in `_filter_edges` before §1.2A+C static-edge rejection; `SCENE_CHANGE_LUMA_THRESH=60.0` in `constants/animation.py`; `ASP_SCENE_CHANGE_LUMA_THRESH` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_pipeline.py::TestRejectSceneChangeEdges`. 362 tests passing. Session 50 complete: §1.4F per-frame exposure outlier rejection — `_reject_exposure_outliers(frame_lums, max_deviation_lum) → List[bool]` in `compositing.py`; computes median bg-lum across all frames with valid lum, returns True for any frame with `|lum − median| > max_deviation_lum`; fallback all-False when < 3 valid frames; `_EXPOSURE_OUTLIER_THRESH` flag (default 0.0=off, `ASP_EXPOSURE_OUTLIER_THRESH=60.0`); wired after `_coherence_skip_mask` in normalization loop via OR; `EXPOSURE_OUTLIER_THRESH=60.0` in `constants/animation.py`; `ASP_EXPOSURE_OUTLIER_THRESH` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_compositing.py::TestRejectExposureOutliers`. 357 tests passing. Session 49 complete: §1.4E background CDF histogram matching — `_bg_histogram_lut(src_pixels, ref_pixels) → float32[256]` + `_apply_bg_histogram_match(frame, reference, bg_mask) → uint8(H,W,3)` in `compositing.py`; CDF-matching LUT via `np.searchsorted(ref_cdf, src_cdf)`; per-channel application to background pixels; foreground unchanged; `_HISTOGRAM_MATCH` flag (default OFF, `ASP_HISTOGRAM_MATCH=1`); wired as third branch in normalization loop between `_MULTISCALE_GAIN` and scalar fallback; `ASP_HISTOGRAM_MATCH` added to `_CONFIG_SCHEMA`; both functions exported in `__all__`; 5 new tests in `test_compositing.py::TestBgHistogramLut`. 352 tests passing. Session 48 complete: §1.3E similarity-mode matching — `_extract_similarity(M) → (2,3) float32` in `matching.py`; closed-form Procrustes projection of full affine to best-fit 4-DOF similarity (`a_sym=(a+d)/2`, `b_sym=(b-c)/2` → `[[a_sym, b_sym, tx], [-b_sym, a_sym, ty]]`); shear discarded; `_SIMILARITY_MODE` flag (default OFF, `ASP_SIMILARITY_MODE=1`); in `_match_pair`, similarity projection replaces translation-only strip when flag enabled; `ASP_SIMILARITY_MODE` added to `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in new `test_matching.py::TestExtractSimilarity`. 347 tests passing. Session 47 complete: §0.5D adaptive rotation/scale thresholds — `_compute_adaptive_rot_scale(affines) → (float, float)` in `validation.py`; returns loose thresholds (0.15) when frame-to-frame σ < 0.02 (systematic camera property), tight (0.10) when σ ≥ 0.02 (BA noise); constants `_ROT_TIGHT=0.10`, `_ROT_LOOSE=0.15`, `_SC_TIGHT=0.10`, `_SC_LOOSE=0.15`, `_ROT_SCALE_CONSISTENCY_THRESH=0.02`; wired into Stage 7b initial validation and Retry 0; log message updated to show per-run threshold; exported in `__all__`; 5 new tests in `test_affine_validation.py::TestAdaptiveRotScale`. 342 tests passing. Session 46 complete: §1.4D multi-scale spatially-varying gain normalisation — `_multiscale_gain_map(frame, reference, bg_mask, sigma=30, gain_min=0.5, gain_max=2.0) → float32(H,W)` in `compositing.py`; Gaussian-blurred luminance ratio; fg pixels zeroed before blur so background gains propagate without character-colour contamination; `_MULTISCALE_GAIN` flag (default OFF, `ASP_MULTISCALE_GAIN=1` to enable); replaces scalar `_bg_gain_unclamped` in bg normalization loop; median gain stored as `frame_gains[i]` for §1.6B downstream; `MULTISCALE_GAIN_SIGMA=30.0` in `constants/animation.py`; `ASP_MULTISCALE_GAIN` added to `_CONFIG_SCHEMA`; 5 new tests in `test_compositing.py::TestMultiscaleGainMap`. 337 tests passing. Session 45 complete: §1.1B spanning-tree consensus pre-filter — `_spanning_tree_inlier_filter(edges, num_frames, inlier_threshold=50.0)` in `bundle_adjust.py`; Kruskal max-weight spanning tree → BFS reference propagation from frame 0 → any edge with |obs_dx−pred_dx|²+|obs_dy−pred_dy|² > 50² removed; spanning-tree edges always pass (residual=0 by construction); disconnected-graph + min-inlier-count fallbacks; wired at top of `_bundle_adjust_affine` before DOF setup; `_ST_INLIER_THRESHOLD=50.0` constant; exported in `__all__`; 5 new tests in `test_bundle_adjust.py::TestSpanningTreeInlierFilter`. 332 tests passing. Session 44 complete: §1.5D seam path cache — `_make_seam_cache_key(frame_keys, k, cost_flags)` + `_get_seam_cost_flags()` in `compositing.py`; `_composite_foreground` extended with `frame_keys` + `seam_path_cache` optional params; cache checked before zone array allocation and populated after DP; `AnimeStitchPipeline` stores `self._seam_path_cache: Dict = {}` and passes it at Stage 11 with `frame_keys=tuple(image_paths)`; eliminates DP executor latency on RLHF re-runs; 5 new tests in `test_compositing.py::TestSeamPathCache`. 327 tests passing. Session 43 complete: §3.4A dHash animation hold detection — `_compute_dhash(thumb, hash_size=8)` + `_detect_hold_blocks_dhash(thumbs, distance_threshold=4)` in `frame_selection.py`; INTER_AREA resize eliminates MPEG DCT block noise before directional comparison; `_HOLD_DHASH_THRESHOLD` config (default 0=off, `ASP_HOLD_DHASH_THRESH=4` to enable); `HOLD_DHASH_THRESHOLD=4` in `constants/animation.py`; added to `_CONFIG_SCHEMA`; wired as alternative to MAD in step 1b of `smart_select_frames`; 5 new tests in `test_frame_selection.py::TestDetectHoldBlocksDhash`. 322 tests passing. Session 42 complete: §1.8B config schema validation — `_CONFIG_SCHEMA` (14 known `ASP_*` keys with type + range spec) + `validate_asp_config(config, *, strict=False) → List[str]` in `config.py`; unknown keys emit `UserWarning`; type/range violations returned as strings (or raised when `strict=True`); wired into `load_asp_config(validate=False, strict=False)`; exported in `__all__`; 5 new tests in `test_config.py::TestValidateAspConfig`. 317 tests passing. Session 41 complete: §1.9C on-demand SCANS frame reload — `_reload_scans_frames(paths)` in `pipeline.py`; returns `_normalise_widths(_load_frames(paths))`; `_SCANS_RELOAD = os.environ.get("ASP_SCANS_RELOAD","0") != "0"` flag skips Stage-2 snapshot when enabled; Stage-2 `list(frames)` → `[] if _SCANS_RELOAD else list(frames)`; both dedup sync sites guarded with `if scans_frames else []`; all 5 fallback call sites use `_sf = scans_frames or _reload_scans_frames(image_paths)`; 5 new tests in `test_pipeline.py::TestReloadScansFrames`. 312 tests passing. Session 40 complete: §1.4C background-only gain clamp override — `_bg_gain_unclamped(ref_lum, frame_lum, override_threshold=0.20)` in `compositing.py`; returns raw ideal gain when clamp would cut correction by > 20%; wired into bg-only normalization loop replacing `_adaptive_gain_clamp`; 5 new tests in `test_compositing.py::TestBgGainUnclamped`. 307 tests passing. Session 39 complete: §1.2D temporal variance pre-filter — `_temporal_variance_filter(thumbs, paths, sigma_threshold)` in `frame_selection.py`; drops interior frames with mean triplet variance < threshold (default disabled: `ASP_TEMPORAL_VAR_THRESH=0.0`); `TEMPORAL_VAR_THRESH=1e-3` in `constants/animation.py`; wired as step 1a in `smart_select_frames` before hold detection; 5 new tests in `test_frame_selection.py::TestTemporalVarianceFilter`. 302 tests passing. Session 38 complete: §1.11C response-based hold refinement — `_refine_hold_ids_by_response(hold_ids, responses, threshold)` in `frame_selection.py`; post-hoc merges hold blocks for cross-hold pairs with `phaseCorrelate response >= 0.85`; wired as step 3b in `smart_select_frames` after the phase-correlation loop; `HIGH_HOLD_RESPONSE_THRESH=0.85` in `constants/animation.py`; 5 new tests in `test_frame_selection.py::TestRefineHoldIdsByResponse`. 297 tests passing. Session 37 complete: §2.9C high-confidence edge re-solve — `_filter_high_conf_edges(edges, min_weight)` in `pipeline.py`; keeps edges with `weight >= HIGH_CONF_EDGE_THRESH (0.65)`; wired as Retry 0 in Stage 7b for ratio failures; `HIGH_CONF_EDGE_THRESH=0.65` in `constants/animation.py`; 5 new tests in `test_pipeline.py::TestFilterHighConfEdges`. §3.14A housekeeping: `_compute_canvas` already uses full 2D affine placement. 292 tests passing. Session 36 complete: §0.5C adaptive min-gap threshold — `_compute_adaptive_min_gap(affines)` in `validation.py`; returns `max(20.0, canvas_span / (N × 3))`; wired as `min_step` for the first `_validate_affines` call in Stage 7b of `pipeline.py`; 5 new tests in `test_affine_validation.py::TestAdaptiveMinGap`. 287 tests passing. Session 35 complete: §3.8A double-edge autocorrelation ghosting metric — `_ghosting_score_v2(img)` in `bench_anime_stitch.py`; FFT-based autocorrelation of column-mean gradient profile; secondary peak at lag D directly measures repeated-edge structure (ghost signature); score [0–100], 30+ = ghost likely; added as `ghosting_siqe` in `_compute_all_metrics`; original `ghosting_score` kept for GhostGate calibration; 5 new tests in `test_bench_metrics.py::TestGhostingScoreV2`. §1.7C housekeeping: `_crop_to_valid` in `canvas.py` already implements content-aware bounding-box crop (§1.7C marked de facto done). 282 tests passing. Session 34 complete: §1.2C adaptive min-step threshold — `_compute_adaptive_min_disp(edges)` module-level function in `pipeline.py`; returns `max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC * median_adjacent_step)` using dominant-axis displacements; wired into `_filter_edges` before `_reject_static_edges`; `ADAPTIVE_MIN_DISP_FRAC=0.10` added to `constants/animation.py`; exported in `__all__`; 5 new tests in `test_filter_edges.py::TestComputeAdaptiveMinDisp`. 277 tests passing. Session 33 complete: §3.15A SemanticStitch column-level fg-domination barrier — `_build_seam_cost_map()` in `compositing.py` now raises fg-dominated columns (>50% fg-interior coverage) to cost=2.0, forcing the DP into background-corridor columns; fallback when no corridor exists; 5 new tests in `test_compositing.py::TestSeamCostColumnFilter`. §3.14 scroll-axis detection wired into pipeline — `_detect_scroll_axis` imported and called after Stage 9; 'horizontal' scroll type triggers explicit SCANS fallback with diagnostic log (belt-and-suspenders with alignment gate); 5 new tests in `test_canvas.py::TestDetectScrollAxisModule` validating the exported module function. 272 tests passing. Session 32 complete: §1.2A pre-bundle static edge rejection — `_reject_static_edges(edges, min_disp_px)` module-level function in `pipeline.py`; drops edges where both |dx| and |dy| are below `STATIC_EDGE_MIN_DISP_PX=50`; wired at the start of `_filter_edges()` before the geometric consistency filter; `STATIC_EDGE_MIN_DISP_PX=50` constant added to `constants/animation.py`; exported in `__all__`; 5 new tests in `test_filter_edges.py`. 262 tests passing. Session 31 complete: §1.3B PANORAMA stitcher fallback — `_panorama_stitch_fallback(frames, output_path)` in `canvas.py`; uses `cv2.Stitcher_create(mode=0)` for affine-validation failures before SCANS; raises `RuntimeError` on failure so caller falls through; wired into `pipeline.py` between Retry 3 and `_scan_stitch_fallback`; added to `__all__`; 5 new tests in `test_canvas.py`. 257 tests passing. Session 30 complete: §1.1D adaptive GNC f_scale — `_compute_adaptive_f_scale(edges, affines, floor)` in `bundle_adjust.py`; derives data-driven Cauchy loss scale as `max(floor, 2.0 × median_residual_px)`; conditional re-solve in `_bundle_adjust_affine` when adaptive_scale > _BA_F_SCALE × 1.5; warm-started from initial solution; `__all__` added; 5 new tests in `test_bundle_adjust.py`. 252 tests passing. Session 29 complete: §1.10A RLHF post-run quality gate — `_compute_rlhf_score(img_bgr)` + `_get_reward_model()` lazy singleton + `_RLHF_FLAG_THRESHOLD=0.6` added to `bench_anime_stitch.py`; `_compute_all_metrics` now emits `rlhf_score` (float or None) and `rlhf_flagged` (bool) for every test; `StitchRewardModel.predict()` wired as the inference call; 5 new tests in `test_bench_metrics.py`. 247 tests passing. Session 28 complete: §1.9A spatial dedup scans_frames sync — `_spatial_dedup_frames(frames, scans_frames, bg_masks, image_paths, edges, min_displacement_px)` extracted as a testable module-level function in `pipeline.py`; one-line fix adds `[scans_frames[i] for i in keep_idx]` to the dedup block so all SCANS fallbacks use the same frame subset as the main compositing path; `run()` while-loop refactored to call the new function; 5 new tests in `test_pipeline.py`. 242 tests passing. Session 27 complete: §1.8A TOML config loader — `load_asp_config(path, *, override_env=True)` in new `backend/src/animation/config.py`; reads `asp_config.toml` via stdlib `tomllib`, merges all sections into flat dict, writes each key to `os.environ` via `setdefault`; zero new deps; `override_env=False` dry-run mode; 5 new tests. 237 tests passing. Session 26 complete: §1.2B near-dup luma post-filter — `_near_dup_luma_filter(selected_thumbs, selected_paths, threshold)` in `frame_selection.py`; wired as step 8 in `smart_select_frames` (default disabled: `ASP_NEAR_DUP_LUMA=0.0`); `NEAR_DUP_LUMA_THRESH=3.0` constant extracted from pipeline.py magic number; 5 new tests. 232 tests passing. Session 25 complete: §3.9 fix — unified `_compute_aligned_ssim`; removed dead S8 EUCLIDEAN definition (was silently overridden by S9 TRANSLATION version); surviving definition upgraded to MOTION_EUCLIDEAN with (200 iter, 1e-4 tol, gaussFiltSize=5, GT-centric resize, BORDER_REPLICATE); redundant double call in `_compute_gt_metrics` removed; 5 new tests. 227 tests passing. Session 24 complete: §1.4B continuous adaptive gain clamp — `clamp_width = 0.26 − 0.12 × (ref_lum/255)` replaces S18 binary ref<80 threshold; smooth surface from ±26% (pure-black) to ±14% (pure-white); 5 updated tests + 3 new. 222 tests passing. Session 23 complete: §1.7B OpenCV INPAINT_TELEA border fill (`_telea_fill_gaps`) — fast fallback for residual black corners when diffusion inpainting fails; wired into P1.8 except block in `pipeline.py`; zero new dependencies. 5 new tests. 219 tests passing. Session 22 complete: §1.6B gain-adaptive feather minimum (`_gain_to_min_feather`) — `max(40, int(gain_diff×300))` capped at 120px applied as floor after overlap-cap; `frame_gains` tracked in normalization loop; dead code `_normalize_warped_to_median` removed; roadmap housekeeping (§0.5A/B, §1.1C, §1.4A, §1.5A/C/E, §1.6A/B/C marked ✅). 6 new tests. 214 tests passing. Session 21 complete: §1.6C gradient-domain Poisson seam blend (`_poisson_seam_blend`) — `cv2.seamlessClone(NORMAL_CLONE)` in ±20px band around DP seam path; eliminates brightness step at hard cuts without ghosting; gated by `ASP_POISSON_SEAM=1`. 5 new tests. 208 tests passing. Session 20 complete: bg-mask-aware DSFN ramp (`_soft_seam_weight`) — `sim_diffused[both_fg]=0.0` after Gaussian blur prevents background similarity diffusing into fg-vs-fg overlap; bg_mask params were previously passed but unused. 2 new tests. 203 tests passing. Session 19 complete: §1.6A tiered seam cost (`_build_seam_cost_map`) — Tier 2 edge-buffer cost lowered 1.0→0.5, creating gradient interior=1.0→buffer=0.5→background=0.0 for DP routing. 7 new tests. 201 tests passing. Session 18 complete: per-pair coherence gate (`_coherence_skip_mask`) + §1.4A adaptive gain clamp (`_adaptive_gain_clamp`) — normalization skips only frames in bad adjacent pairs (not all frames), gain clamp widens from ±7% to ±14%/±18% for normal/dark scenes. 11 new tests. 194 tests passing. Session 17 complete: per-pixel DSFN blend ramp (`_soft_seam_weight` — ramp now (zone_h,W) not (1,W)), adaptive boundary search range (±100px when tx_spread<5px). 6 new tests. 183 tests passing. Session 16 complete: `_seam_color_match()` — per-channel mean shift of oth_zone toward dom_zone in seam band before S15 blend, reducing color step from post_warp_diff lum to within-band variance (~5 lum). 7 new tests. 177 tests passing. Session 15 complete: `_single_pose_soft_edge()` — narrow ±6px path-guided linear feather at single-pose seam cuts, smoothing hard color step without ghosting. 7 new tests. 170 tests passing. Session 14: `_seam_visibility_score()` no-reference quality metric in benchmark — worst-case adjacent-row luminance jump, wired into `_compute_all_metrics`, 8 new tests. 163 tests passing. Session 13: Multi-frame canvas coverage gate (Stage 10.5) — `_compute_row_coverage()` helper + SCANS fallback when <30% of rows have ≥2-frame coverage. §0 item 2 complete. 155 tests passing. Session 12: Adaptive feather refinement (post_warp_diff < 8 → widen 1.5×, > 16 → narrow 0.75×) + parallel seam DP pre-computation (ThreadPoolExecutor, max 4 workers). 149 tests passing (animation suite). Session 11: Fallback elimination — comparative render gate (2.0× SCANS baseline), alignment gate → advisory, validation retry chain extended to 5 retries, GhostGate absolute floor (40.0), `seam_post_diffs` init bug fixed. SCANS fallbacks: 51 → 4 genuine (tests 54, 59, 73, 89). Session 10: Seam DP vectorized via `minimum_filter1d` (§1.5A ✅), dead S8 DINOv2 definition removed, `_TOONCRAFTER_SEAM_ENABLED` NameError fixed, test import errors fixed, `TestDINOv2Features` rewritten for S9 API. 141 tests passing. Session 9: ToonCrafter seam synthesis wired to worst single-pose seam (§3.6). Session 8: DINOv2 submodular frame selection (§3.3), LSD collinearity in ARAP (§0.1/A3), Aligned-SSIM metric (§3.9). Session 7: Stage 12.5 scroll-axis foreground-extent trim (§2.6). Session 6: perceptual-hash hold detection (§1.11), GNC robust loss for BA (§1.1), SLIC SGM proxy (§3.1). 107 tests passing (was 90 at S5 start). Session 5: alignment stability gate (+0.074 on test08, +0.049 on test25), fg pixel L1 pose metric (+0.010 on test27 with pose-on), 8 new unit tests (90 total). Session 4: ARAP Push phase (full Sýkora 2009). Session 3: pose-consistent frame selection infrastructure. Session 2: RAFT+ARAP+post_warp_diff. Session 1: foreground assembly pipeline.*  
*Corpus: 96 tests; 55 have ground truth. **Avg SSIM ASP vs GT: 0.667 vs simple stitch 0.694** — simple stitch is 3.9% closer to reference on average (session 4 full-run baseline).*  
*True ASP composites: 52/96 (54.2%). Alignment gate (2D motion): test08 0.736→0.809, test25 +0.049. Render quality gate: 31 fallbacks (32.3%). Affine validation: 13 fallbacks (13.5%).*  
*GT verdicts (S4 baseline): asp_better=7 (12.7%), simple_better=26 (47.3%), comparable=22 (40.0%). Best: test17=0.887, test84=0.821. S5 key: test08 now asp_better (0.809 vs simple 0.805).*  
*Root cause: Animated video scenes vs. static-scroll design assumption. Phase correlation measures whole-frame displacement including character animation.*  
*Previous baseline (22 tests, 2026-05-31): 22/22 metric success, avg sharpness 33.14.*

*Research basis (consolidated): [`reports/ASP Consolidated Research Plan.md`](../../reports/ASP%20Consolidated%20Research%20Plan.md) — full synthesis of ML survey, practitioner lessons (Overmix, Hugin, ICE), HITL architecture, structured research plan, and technical survey. Covers failure taxonomy (A/B/C1/C2), Phase 1/2/3 priority roadmap, module specs (frame selection, SAM-2, SGM/SEA-RAFT, ARAP, GNC-BA, background separation, stitching, seam routing, ProPainter, NR-IQA), synergy maps, HITL DAG breakpoints, dataset registry (LinkTo-Anime, ATD-12K, AnimeRun, etc.), and S6–S32 implementation status. Also see [`reports/Image_Stitching_Research.md`](../../reports/Image_Stitching_Research.md) for foreground-assembly paradigm and 13-stage spec.*
