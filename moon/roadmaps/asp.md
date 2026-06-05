# ASP Roadmap — Anime Stitch Pipeline: Quality & Reliability

*Last updated: 2026-06-05. Session 9 complete: ToonCrafter seam synthesis wired to worst single-pose seam (§3.6). Session 8: DINOv2 submodular frame selection (§3.3), LSD collinearity in ARAP (§0.1/A3), Aligned-SSIM metric (§3.9). Session 7: Stage 12.5 scroll-axis foreground-extent trim (§2.6). Session 6: perceptual-hash hold detection (§1.11), GNC robust loss for BA (§1.1), SLIC SGM proxy (§3.1). 107 tests passing (was 90 at S5 start). Session 5: alignment stability gate (+0.074 on test08, +0.049 on test25), fg pixel L1 pose metric (+0.010 on test27 with pose-on), 8 new unit tests (90 total). Session 4: ARAP Push phase (full Sýkora 2009). Session 3: pose-consistent frame selection infrastructure. Session 2: RAFT+ARAP+post_warp_diff. Session 1: foreground assembly pipeline.*  
*Corpus: 96 tests; 55 have ground truth. **Avg SSIM ASP vs GT: 0.667 vs simple stitch 0.694** — simple stitch is 3.9% closer to reference on average (session 4 full-run baseline).*  
*True ASP composites: 52/96 (54.2%). Alignment gate (2D motion): test08 0.736→0.809, test25 +0.049. Render quality gate: 31 fallbacks (32.3%). Affine validation: 13 fallbacks (13.5%).*  
*GT verdicts (S4 baseline): asp_better=7 (12.7%), simple_better=26 (47.3%), comparable=22 (40.0%). Best: test17=0.887, test84=0.821. S5 key: test08 now asp_better (0.809 vs simple 0.805).*  
*Root cause: Animated video scenes vs. static-scroll design assumption. Phase correlation measures whole-frame displacement including character animation.*  
*Previous baseline (22 tests, 2026-05-31): 22/22 metric success, avg sharpness 33.14.*

*Research basis (consolidated): [`reports/Image_Stitching_Research.md`](../../reports/Image_Stitching_Research.md) — foreground-assembly paradigm, per-stage toolbox, 13-stage spec, failure/fallback taxonomy. [`reports/Anime Stitching Pipeline Upgrade Research.md`](../../reports/Anime%20Stitching%20Pipeline%20Upgrade%20Research.md) — SSIM ceiling analysis, ARAP/SGM/RAFT upgrade paths. [`reports/Anime Stitch Pipeline ML Research.md`](../../reports/Anime%20Stitch%20Pipeline%20ML%20Research.md) — DINOv2/SigLIP submodular selection, SI-FID, SIQE, ToonCrafter wiring. [`reports/Advanced Morphological Integration and Human-in-the-Loop Interventions for the Anime Stitch Pipeline.md`](../../reports/Advanced%20Morphological%20Integration%20and%20Human-in-the-Loop%20Interventions%20for%20the%20Anime%20Stitch%20Pipeline.md) — AGNC, SAM 2, Overmix, BigWarp, SAM2Flow, Intelligent Scissors, RLHF/DPO pathway.*

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
2. Multi-frame canvas coverage check before compositing (fall back to SCANS if median coverage < 2 frames/row)
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
- ⬜ **Segment-guided flow (AnimeInterp SGM)** — per-colour-segment centroid flow for scenes where RAFT also fails (very flat, large uniform regions).
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

**Session 3 status (2026-06-03):** Infrastructure shipped but disabled. Two-pass selector implemented in `backend/src/anim/frame_selection.py` and `_smart_select_frames()` in benchmark. Pass 2 uses gradient-magnitude L1 on central-crop thumbnails as a pose proxy. Benchmarking showed this proxy is confounded by background structure (lockers, walls), causing regressions of -0.043 (test04) and -0.026 (test27). Disabled by default (`ASP_POSE_WINDOW_PX=0`).

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

**A — Lower static threshold to 25px [Quick Win]**
Change `MIN_GAP_PX` in `validation.py` from 50 to 25. Immediately rescues ~9 datasets.
- Pros: One-line change. Proven safe — genuine co-located frames have gaps < 5px.
- Cons: Fixed threshold; doesn't adapt to canvas resolution.

**B — Vector magnitude gap (multi-axis) [Quick Win]**
Replace `min(|dy|)` with `min(sqrt(dy² + dx²))` for the gap computation. Fixes 6 datasets with diagonal scroll where dy=40px but actual displacement=100px.
- Pros: Physically correct for diagonal scrolls. One-line change.
- Cons: Slightly more complex formula.

**C — Adaptive threshold based on selected frame density**
`min_gap = max(20px, canvas_height / (N_frames × 3))`. Scales with scroll speed.
- Pros: Content-aware; no fixed value to tune.
- Cons: Requires canvas_height to be known at validation time.

**Recommendation:** Implement B first (zero risk, fixes multi-axis scrolls), then A (lower threshold). Combined, these should bring the success rate to ~83% (78/94).

---

## 1.1 Bundle Adjustment Hardening

**Pain point (updated 2026-06-01):** On the 94-test corpus, ratio failures are nearly eliminated — only 2/25 fallbacks (8%) are ratio > 3.0, vs 58% in the pre-Phase-3 corpus. The 2-pronged outlier rejection added in Phase 3 is working well on real-world data. New concern: heuristics tuned for the current corpus may still fail on datasets with >40% true outliers.

### Options

**A — Post-solve residual pruning (current approach)**
After the initial Levenberg-Marquardt solve, compute per-edge predicted-vs-actual translation; reject edges where `|residual| > 3 × median`; re-solve. Simple, fast (~0.15s), proven on the 22-test corpus.
- Pros: Already implemented. Zero new dependencies.
- Cons: Median threshold is corpus-tuned; may fail on datasets with >40% outliers.

**B — RANSAC before LM (consensus pre-filter)**
Before the LM solve, run a consensus-based robust estimator across all edges to find the inlier set, then solve only on inliers.
- Implementations: classic RANSAC, MAGSAC++ (adaptive threshold), LO-RANSAC (local optimisation after each model draw).
- Pros: More principled than post-solve pruning. Especially robust when >30% of edges are bad.
- Cons: Significantly slower. MAGSAC++ adds a dependency (poselib or custom impl).
- Reference: [RANSAC variants survey](https://arxiv.org/abs/1905.00604)

**C — Graduated Non-Convexity (GNC) robust loss**
Replace the L2 residual in the LM cost function with a robust loss (Geman-McClure, Cauchy, or Welsch) that automatically down-weights outlier edges during optimisation. The weight schedule is annealed from convex to non-convex so the solver never gets stuck in a local minimum induced by outliers.
- Implementation: `scipy.optimize.least_squares(method='trf', loss='cauchy', f_scale=...)` — can be a one-line swap if the Jacobian is compatible with scipy's interface.
- Pros: No separate rejection step. Theoretical guarantees at up to 70–80% outlier rate (Yang et al., 2019; FracGM 2025 improves convergence further). Generalises better to unseen data.
- Cons: Loss hyperparameter (f_scale) needs tuning. Slower than Option A.
- Reference: [GNC for Spatial Perception (arXiv 1909.08605)](https://arxiv.org/abs/1909.08605)

**D — Adaptive Graduated Non-Convexity (AGNC) [Research — state of the art]**
Upgrade from static GNC (C) to AGNC, which dynamically adjusts the loss scale by monitoring the positive definiteness of the Hessian matrix rather than following a fixed annealing schedule. AGNC uses a multi-task search strategy: samples multiple annealing choices per iteration and keeps the one with the best convergence signal. Empirically stable even at 99% outlier rates (SAC-GNC, IEEE 2026).
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

**A — Pre-bundle static edge rejection [Quick Win]**
Drop any edge where `|dy| < 50px AND |dx| < 50px` before the LM solve.
- Pros: Fast, zero dependencies, one-line change.
- Cons: Fixed 50px threshold doesn't scale with canvas resolution or scroll speed.

**B — Near-duplicate frame deduplication via perceptual distance**
Before matching, compare each frame to the previous using mean luma difference, SSIM, or histogram distance. Drop frames below a threshold.
- Exact-duplicate dedup already runs (Pre-5). Extend it with a soft near-duplicate check.
- SSIM threshold ~0.97 catches near-statics without false-positives on slow-scroll sequences.
- Pros: Removes the bad source upstream; cleaner than downstream rejection.
- Cons: SSIM adds ~5ms per frame pair (acceptable). Threshold may need tuning per content type.

**C — Adaptive min-step threshold**
Estimate expected inter-frame step as `canvas_height / N_frames`. Flag edges where step < 10% of expected. Automatically scales to different resolutions and scroll speeds.
- Pros: Content-adaptive; handles 1080p and 4K equally well.
- Cons: Estimate can be wrong for non-uniform scroll (e.g., scene transitions).

**D — Temporal variance filter (motion energy)**
Compute per-pixel temporal variance across consecutive frame triplets. If the variance map is near-zero (< σ threshold), mark the middle frame as static and skip it.
- Pros: Robust to both exact and near-duplicate statics. Works on partial-screen motion.
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

**B — OpenCV Stitcher PANORAMA fallback [Quick Win]**
When the affine validator fires, route to `cv2.Stitcher_create(cv2.Stitcher_PANORAMA)` instead of SCANS. Already uses spherical/cylindrical projection, handles perspective and scale natively.
- The existing `simple_stitch` path in `image_merger.py` already uses this — the change is routing the affine-rejection fallback here instead of SCANS.
- Pros: Reuses existing infrastructure. Handles arbitrary affine distortions with no new code.
- Cons: PANORAMA stitcher is slower and sometimes produces barrel distortion on vertical scroll sequences.

**C — Scale normalisation before bundle adjustment**
Warp each frame to the reference frame's scale before matching. Converts a zoom sequence into a pure-translation sequence the existing pipeline handles.
- Pros: Minimal change to downstream stages.
- Cons: Introduces resampling blur proportional to scale difference. Scale estimation requires an extra matching pass.

**D — Homography (projective) warp per frame**
Extend A to full 8-DOF projective warp. Handles perspective (slight 3D parallax) in addition to affine.
- Pros: Broadest coverage.
- Cons: Projective warp on scroll sequences tends to over-fit small parallax into large geometric distortions. High risk of quality degradation on simple sequences.

**E — Similarity transform (scale + rotation + translation)**
4-DOF SRTF: a middle ground between translation-only and full affine. Handles zoom-and-pan without shear artefacts.
- Pros: Physically correct model for handheld pan+zoom. Less prone to overfitting than full affine.
- Cons: Requires SRTF estimator (available via OpenCV `estimateAffinePartial2D`).

**Recommendation:** B is lowest effort (reuses existing code path). E is the most physically appropriate model for zoom-pan sequences. Implement B as immediate fallback; prototype E as a dedicated zoom-scroll mode.

---

## 1.4 Gain Clamp Widening for Dark Scenes

**Pain point:** 17/22 tests hit the `[0.88, 1.14]` gain clamp. Dark scenes (ref_lum < 70) have proportionally larger gain swings, leaving some frames under-corrected.

### Options

**A — Conditional clamp based on ref_lum [Quick Win]**
Use `[0.82, 1.22]` when `ref_lum < 80`, `[0.88, 1.14]` otherwise.
- Pros: One-line config change. Targeted fix for dark scenes.
- Cons: Binary threshold; doesn't smoothly scale with luminance level.

**B — Continuous clamp scaling**
Linearly interpolate clamp width between dark and bright anchors: `clamp_width = 0.26 - 0.12 × (ref_lum / 255)`. Smooth, no discontinuity at a single threshold.
- Pros: More principled than A.
- Cons: Requires tuning two anchor values instead of one.

**C — Per-frame adaptive clamp (background mask only)**
Compute desired correction factor per frame. If the clamp would cut it short by >20%, apply full correction only to the BiRefNet background mask; leave foreground pixels at the clamped value. Avoids character skin tone shifts on high-gain frames.
- Pros: Preserves foreground colour accuracy.
- Cons: Requires mask-aware gain application (not currently vectorised).

**D — Multi-scale gain (tone-mapping inspired)**
Apply large gain corrections at low spatial frequency (blurred background component) and fine-tune at high frequency. Inspired by Retinex and CLAHE-based tone-mapping operators.
- Pros: Handles non-uniform scene lighting (half-dark/half-bright panels).
- Cons: Significantly more complex. Requires frequency decomposition step.

**E — Background histogram matching via CLAHE [Research]**
Instead of per-frame scalar gain, match each frame's background histogram to the reference frame using CLAHE. Better correction for scenes with non-uniform lighting distributions.
- Pros: Per-region brightness normalisation. Handles vignetting and panel-edge darkening.
- Cons: CLAHE introduces local contrast enhancement artefacts if misconfigured. Needs mask integration.

**Recommendation:** A is a one-line config change, ship immediately. B as a follow-on smoothing pass. E is a [Research] item for dark/complex scenes.

---

## 1.5 Stage 11 Composite Performance

**Pain point:** Stage 11 (hard-partition composite) averages 24.5s, peaking at 41.9s, accounting for ~35% of total ASP runtime. Seam DP and feather computation are the primary bottlenecks.

### Options

**A — Vectorise seam DP with NumPy**
The per-row minimum-cost path accumulation can be expressed as a cumulative minimum over a 2D cost array, replacing the Python row-by-row loop. Expected speedup: 5–10×.
- Implementation: `np.minimum.accumulate` along the column axis after adding the 3-column shift variants.
- Pros: No new dependencies. Largest single leverage change.
- Cons: Requires careful index arithmetic to replicate the ±1-column DP transition.

**B — CUDA seam DP via PyTorch scatter/gather**
Implement the DP on GPU using PyTorch operations.
- Pros: Fastest possible; ~50–100× speedup on a 3090 Ti.
- Cons: Requires GPU. Adds kernel complexity. DP is inherently sequential by row — parallelisable only column-wise within each row.

**C — Restrict seam search window [Quick Win]**
Current ±250px window scans 500 columns per row. Reduce to ±100px for sequences with `dx_cv < 5` (low horizontal drift). Auto-detect from bundle adjustment output. Reduces DP grid by 60%.
- Pros: Drop-in optimisation, no algorithm change.
- Cons: May clip optimal seam path on high-drift sequences.

**D — Cache seam path across RLHF iterations**
When re-processing the same frame set with different blending parameters, cache the seam mask keyed by `(frame_ids, seam_cost_config)`. Avoids recomputing if only blending weights changed.
- Pros: Near-zero cost for repeat runs (common in RLHF parameter search).
- Cons: Cache invalidation logic; disk/memory cost for large panoramas.

**E — Parallel seam computation per strip**
When the panorama has M non-overlapping seam zones (between adjacent frame pairs), compute the M seams in parallel using `concurrent.futures.ThreadPoolExecutor`. The GIL is released during NumPy operations.
- Pros: Linear speedup proportional to M for multi-frame panoramas.
- Cons: Requires refactoring to identify independent seam zones.

**Recommendation:** A is the highest-leverage change (no dependencies). Combine with C for sequences where it applies. D is free win for RLHF iteration speed.

---

## 1.6 Ghosting Reduction in Composite Zone

**Pain point:** ASP-succeeded tests consistently have higher ghosting than simple stitch (8/10 tests). Stage 11's hard-partition seam reintroduces ghost-like edge artefacts when seams bisect character bodies.

### Options

**A — Increase foreground penalty weight in seam DP**
The `sem_cost` term in `_seam_cut` (P2.4) already routes seams away from BiRefNet-masked foreground. Increase the foreground penalty multiplier (current: partial implementation) to fully deter seams through character regions.
- Pros: Minimal code change. Directly addresses the seam-through-character problem.
- Cons: Very high penalty may force seams into narrow background corridors that cause visible aliasing.

**B — Adaptive feather width**
Make `_FADE_ROWS` a function of `|gain_A - gain_B|` across the seam. Wider feather when gain difference is large.
- Proposed formula: `fade = max(40, int(|gain_diff| × 300))`, capped at 120px.
- Pros: Smooth transitions reduce perceptual ghosting near boundaries.
- Cons: Wide feathers on high-gain-difference boundaries may blur the seam zone visibly.

**C — Poisson blending at seam zone [Quick Win]**
Replace the linear feather with gradient-domain seamless cloning (`cv2.seamlessClone`) in a ±20px band around the seam. Eliminates the brightness step even when gain correction is at its limits.
- Pros: OpenCV built-in. Medium effort, measurable improvement.
- Cons: `cv2.seamlessClone` is CPU-only and can be slow on large seam zones (~1–3s extra). Restrict to final-output mode.

**D — ToonCrafter synthetic frame fill**
In high-overlap zones (tight scroll, e.g., test22 at 90px steps), use `anim/anim_fill.py` (ToonCrafter) to generate synthetic intermediate frames that fill the overlap region, reducing ghosting by interpolation rather than blending.
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
`anim/sr_stitcher.py` (P3.4) already implements seam+border inpainting via diffusers. Replace the hard `_crop_to_valid` with a call to `sr_stitcher.inpaint_borders()` when `sr_mode=True`.
- Pros: Reuses existing infrastructure. Best quality.
- Cons: Adds diffusion inference time (5–30s depending on border area). Requires `sr_mode=True`.

**B — OpenCV INPAINT_TELEA fallback**
Use `cv2.inpaint(src, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)` for border fill. Faster than diffusion; quality is lower but avoids the diffusion dependency in standard mode.
- Pros: Zero new dependencies. Fast (~0.5s for typical borders).
- Cons: Visible smearing artefacts on large border regions (>50px). Not suitable for borders spanning characters.

**C — Content-aware minimal bounding crop [Quick Win]**
Compute the minimal bounding box of valid (non-black) pixels and crop to that. Some outputs may be slightly smaller but always fully valid. Zero dependencies, instant.
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

**A — TOML config per pipeline run [Quick Win]**
Load `asp_config.toml` from the working directory or a default location. Override any constant at runtime. Use `tomllib` (stdlib in Python 3.11) with a typed `dataclass`.
- Pros: No new dependencies. Enables rapid iteration. Config can be committed alongside test datasets.
- Cons: Config schema must be kept in sync with `constants.py`.

**B — JSON Schema–validated config**
Same as A but validated against a JSON Schema on load. Provides clear error messages for misconfigured values.
- Pros: Better developer experience; validation at load time.
- Cons: Adds `jsonschema` dependency.

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

**A — Pass original frames to SCANS fallback [Quick Win]**
Store original (pre-BiRefNet, pre-ECC) frames in the pipeline context. Use those frames when triggering SCANS. One-line change in `pipeline.py`.
- Pros: Minimal change. Eliminates the degradation entirely.
- Cons: Doubles the frame memory footprint during the pipeline run (originals + processed).

**B — Dual path from Stage 1**
Fork the pipeline at Stage 1: one path applies preprocessing; the other keeps originals. Merge only at the fallback decision point.
- Pros: Enables per-stage fallback decisions (e.g., use ECC-normalised for matching but originals for compositing).
- Cons: Increases complexity. Higher memory cost.

**C — On-demand reload from disk**
On fallback trigger, reload original frames from disk rather than holding them in memory.
- Pros: Zero extra memory during successful pipeline runs.
- Cons: Adds disk I/O latency at fallback time (~0.5–2s for 14 frames). Acceptable for a fallback path.

**Recommendation:** A for immediate fix. C as a memory-efficient alternative if frame counts exceed available RAM.

---

## 1.10 RLHF Loop Integration

**Pain point:** RLHF infrastructure exists (`rlhf/` module, `StitchFeedbackTab`, reward model CNN, DRL agent) but is not wired into the main pipeline evaluation loop. Collected feedback cannot improve future runs automatically.

### Options

**A — Post-run quality gate**
After each pipeline run, call `reward_model.predict(output)` and log the score alongside benchmark metrics. Flag outputs scoring < 0.6 for manual review in the feedback tab.
- Pros: Closes the feedback loop without requiring the DRL agent to be production-ready.
- Cons: Reward model must be calibrated before its scores are meaningful.

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

### 2.1 Frame Selection Assistant [Quick Win]

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

### 2.2 Edge Graph Inspector & Editor [Quick Win]

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

### 2.3 Anchor Frame & Canvas Layout Inspector [Priority: Medium]

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

### 2.4 Seam Registration Inspector [Highest Impact]

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

### 2.7 Architecture: StitchWorker Staged Execution [Implementation Foundation]

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

*Source: `reports/Anime Stitch Pipeline ML Research.md` — surveyed 2026-06-04. Each subsection maps a specific finding from the report to the current pipeline stage it targets, the files it touches, and the expected quality delta.*

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

**Recommendation:** B immediately as a diagnostic check (does centroid-level flow actually improve post_warp_diff?). A if B shows meaningful seam residual reduction on test09/test27. C is the long-term ceiling but depends on A being validated first.

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

**A — Perceptual hash hold detection [Quick Win]**
`imagehash.dhash()` on 64×64 thumbnail. Hold if `hash_distance < 4`. Implementation: 15 lines. No GPU.
- Pros: Zero new dependencies, ~1ms per frame. Directly maps to animation "on twos" detection.
- Cons: May miss holds where compression adds noise (dhash sees small pixel changes). Threshold requires tuning per source quality.

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

**B — Deep homography with foreground masking [Research]**
Alternative to CamFlow: use a deep homography estimator (from "Deep Homography Estimation for Dynamic Scenes", CVPR 2020) that jointly predicts a temporal dynamics mask alongside the homography matrix. The network identifies high-temporal-variance regions (character) and excludes them, forcing estimation from static background.
- Pros: This CVPR 2020 model has available pretrained weights and a simpler architecture than CamFlow.
- Cons: Less robust to multi-plane parallax than CamFlow. Not designed for anime specifically.

**C — Background-only phase correlation via BiRefNet mask [Infrastructure Built, Disabled]**
Already implemented as `ASP_TWO_CHANNEL_SELECT=1` in `frame_selection.py`. Uses BiRefNet bg mask for background-only phase correlation. Currently disabled because it changes frame timing and caused regressions.
- Cons: The frame-timing regression remains unsolved. Re-enabling after §3.3 (DINOv2 selection) may behave differently since pose selection is handled separately.

**Recommendation:** B first (available weights, simpler implementation). A as the quality ceiling once the CamFlow code is published. C is a free experiment if §3.3 is implemented (BiRefNet already runs before selection in that scenario).

---

### 3.6 ToonCrafter Seam Synthesis — Wiring the Generative Fallback [✅ Option B shipped — Session 9]

**Pain point (links to §1.6, Phase 6.3):** When `post_warp_diff > 22 lum units`, Stage 8.5 escalates to "single-pose fallback" — a clean but informationally incomplete solution (shows one character pose at the seam, hiding the other). The seam zone is left with a visible hard boundary. ToonCrafter can *synthesize* a coherent intermediate pose that eliminates the boundary entirely.

**Session 9 implementation (Option B):** `_TOONCRAFTER_SEAM_ENABLED = os.environ.get("ASP_TOONCRAFTER_SEAM", "0") != "0"` added to `compositing.py`. `seam_post_diffs: dict` tracks `post_warp_diff` per seam during the fg-register loop. After the loop, the worst single-pose-escalated seam (`max(seam_single_pose, key=lambda k: seam_post_diffs.get(k, 0.0))`) triggers `_generate_canonical_cel(crop_a_tc, crop_b_tc, device)` from `anim_fill.py`. The canonical cel is stored in `seam_canonical_crops[worst_k]`; in the Laplacian blend loop it replaces the hard dominant-frame partition for fg pixels. Falls back gracefully to single-pose when ToonCrafter is unavailable.

**Current state:** `anim/anim_fill.py` already implements ToonCrafter integration. It is referenced in `§1.6` as Option D and in `pipeline.py` as `if self.use_tooncrafter`. It IS now wired to single-pose seam escalation in `compositing.py` (session 9).

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

**A — SIQE as drop-in `_ghosting_score()` replacement [Research]**
Implement the steerable pyramid + GMM pipeline. The GMM is fitted offline on a corpus of pristine stitched anime panoramas (the 52/96 ASP-succeeded tests serve as positive examples). SIQE then evaluates any new output against this learned distribution.
- Pros: 94.36% precision. Directly applicable without training (only GMM fitting). No deep model required.
- Cons: Steerable pyramid computation: ~50ms for a 2000px panorama. Acceptable. GMM fitting requires a clean corpus.

**B — SIQE spatial ghost map → per-seam ghost gate [Research]**
Use SIQE's ghost probability map to identify which specific seam boundary zones have ghosting, then trigger targeted re-composition only for those zones (rather than a global SCANS fallback).
- Pros: Surgical intervention instead of wholesale fallback. Would save tests where only 1–2 seams are problematic.
- Cons: Requires the spatial output of SIQE (per-pixel ghost probability) and a re-composition loop that can patch individual seam zones.

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

**C — Phase correlation magnitude threshold**
If two consecutive frames have phase correlation response > 0.85 (near-perfect correlation), they're in the same hold. Already available from the existing phase correlation pass — zero extra cost.
- Cons: MPEG blocks can corrupt high-response pairs at scene boundaries.

**Recommendation:** A immediately (already implemented, `ASP_HOLD_THRESHOLD=0.025`). C as a free upgrade using the existing `responses` array in `smart_select_frames()`. B if §3.3 is implemented.

> **✅ Session 7 — Phase-correlation skip SHIPPED:** Hold threshold default changed from `0.0` to `0.025` (enabled by default). Within-hold frame pairs now return `(dx=0, dy=0, response=1.0, MAD=0.0)` without running `cv2.phaseCorrelate`, achieving the §1.11 3× speedup for typical anime with ~3-frame holds. The `high_anim_mad` gate is protected from false positives (within-hold MAD=0.0 never triggers it). `ASP_HOLD_THRESHOLD=0` to disable.

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

**C — Auto-retry with tighter LoFTR threshold**
When ratio failure is detected, automatically re-run LoFTR with a higher confidence threshold (only the top-10% of matches) and re-solve. No user interaction.
- Pros: Zero UI work. Catches cases where 1-2 bad matches corrupt the median.
- Cons: May still fail if the bad match is high-confidence.

**Recommendation:** C immediately (pure algorithmic, catches the easy cases). A for the remaining affine failures that C can't fix. B as an ergonomic shortcut for broadcast-quality (pure-translation) sources.

---

## 2.10 SAM2Flow / FlowVid Interactive Optical Flow Kinematics [Research — HITL]

**Pain point (links to §0.1, §2.4):** When `post_warp_diff > 22 lum units`, Stage 8.5 escalates to single-pose fallback — a clean but informationally incomplete solution. For extreme cases (character turning 180°, limb moving through 90° arc), no analytical flow engine can register the two poses. A human who can draw a trajectory arrow from the character's position in frame A to its position in frame B would resolve this instantly.

**What SAM2Flow / FlowVid does (§7.3 of Advanced Morphological Integration report):**
- **SAM2Flow:** Extends SAM 2's video object tracking to optical flow estimation. User specifies regions of interest and trajectory hints via click+drag prompts. The system propagates these sparse human annotations as definitive spatial control anchors across the frame sequence. Originally designed for textureless fluid dynamics (in vivo microcirculation), directly applicable to flat cel-shaded anime.
- **FlowVid:** User draws directional arrows on the seam-zone canvas. The FlowVid network uses these as ControlNet-style spatial anchors in a diffusion model, generating coherent frame-to-frame transitions even across 180° rotations. Inference: 512×512 at 1.5 min on A100 (3.1× faster than CoDeF, 10.5× faster than TokenFlow).

**Options**

**A — SAM2Flow seam-zone annotation [Research]**
After Stage 8.5 single-pose escalation, emit `StitchWorker.stage_seam_flow_failed(seam_info)`. The SeamDiagnosticPanel (§2.4) presents the seam crop with a "Draw trajectory" tool. User drags arrows → SAM2Flow uses these as anchors → the pipeline re-runs Stage 8.5 with the user-corrected flow.
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

**A — Intelligent Scissors dialog in SeamDiagnosticPanel [Quick Win]**
Add a "Route seam" tool to §2.4's SeamDiagnosticPanel. User clicks waypoints on the seam-zone preview. The pipeline re-runs the DP seam using these waypoints as hard constraints (nodes with cost=0 that must be included in the path). Re-composite takes ~1s.
*Implementation:* `cv2.GrabCut`-style waypoint injection into the existing `_seam_cut()` DP in `compositing.py`. ~200 LOC.
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
