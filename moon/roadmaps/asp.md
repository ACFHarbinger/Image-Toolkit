# ASP Roadmap — Anime Stitch Pipeline: Quality & Reliability

*Last updated: 2026-06-01 19:13. Full 96-test benchmark with ground truth SSIM comparison.*  
*Corpus: 96 tests; 55 have ground truth. **Avg SSIM ASP vs GT: 0.669 vs simple stitch 0.695** — simple stitch is 3.9% closer to reference on average.*  
*True ASP composites: 44/96 (45.8%). Render quality gate: 39 fallbacks (40.6%). Affine validation: 13 fallbacks (13.5%).*  
*GT verdicts: asp_better=8 (14.5%), simple_better=23 (41.8%), comparable=24 (43.6%).*  
*Root cause: Animated video scenes vs. static-scroll design assumption. Phase correlation measures whole-frame displacement including character animation.*  
*Previous baseline (22 tests, 2026-05-31): 22/22 metric success, avg sharpness 33.14.*

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
3. Replace sharpness metric with seam coherence metric (row-mean luminance variance)
4. Seam validation gate after composite (if adjacent strips differ >15 lum units, reject and use SCANS)

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

**D — FracGM (fractional programming for Geman-McClure)**
Reformulates the non-convex Geman-McClure minimisation as a convex dual + linear system. 2025 state-of-the-art for robust rotation/translation estimation.
- Pros: Faster convergence than GNC, empirically better at extreme outlier ratios.
- Cons: New dependency; implementation complexity. Overkill unless C shows plateau.
- Reference: 2025 FracGM paper.

**E — Learned outlier scoring (RLHF-guided)**
Train a small MLP on (edge residuals → is_outlier) using feedback from the existing RLHF infrastructure. Replaces hand-tuned threshold with a learned one.
- Pros: Self-improving with accumulated feedback.
- Cons: Requires labelled outlier data from the feedback loop (see §1.10). Not viable until the RLHF loop is closed.

**Recommendation:** Keep A as baseline. Prototype C as a drop-in scipy swap — if it reaches parity on the 22-test corpus, it generalises better to unseen data. Escalate to B only if C plateau-stalls on a new dataset with >40% bad edges.

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
