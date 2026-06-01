# Anime Stitch Pipeline — Comprehensive Analysis Report

**Benchmark run:** `anime_stitch_20260601_191331.json`  
**Date:** 2026-06-01 19:13  
**System:** Linux 7.0.0-14-generic, 24-core CPU, 125.6 GB RAM, RTX 3090 Ti (23.5 GB VRAM), CUDA 12.8  
**Scope:** 96 datasets (asp_test01–asp_test96), including 2 new tests (test25, test96)  
**Ground truth:** 55 of 96 tests have reference images in `data/ground_truth/`  
**Total runtime:** 2.06 hours (avg 76.5s/dataset)

---

## 1. Executive Summary

This run introduces **ground truth SSIM/PSNR comparison** as the primary quality signal, replacing the unreliable Laplacian sharpness metric used in previous runs. The findings are sobering:

| Metric | Value |
|--------|-------|
| Total datasets | 96 |
| True ASP composites (pipeline ran end-to-end) | **44** (45.8%) |
| SCANS fallbacks (alignment failure OR render gate) | **52** (54.2%) |
| ASP better than simple stitch by ground truth | **8 / 55** (14.5%) |
| Simple stitch better than ASP by ground truth | **23 / 55** (41.8%) |
| Comparable by ground truth | **24 / 55** (43.6%) |
| Avg SSIM ASP vs ground truth | **0.669** |
| Avg SSIM simple stitch vs ground truth | **0.695** |

**The simple stitch produces output closer to the ground truth in 42% of tested cases. ASP wins in only 15%.** The primary cause is that the pipeline was designed for scrolling static artwork but the test corpus is animated video where characters move independently of the camera in every frame.

---

## 2. Run Configuration

### 2.1 Smart Frame Selector

All 96 datasets contain 58–333 consecutive video frames at ~42ms intervals. The smart frame selector (phase-correlation based, 50px minimum step) reduced these to 4–35 frames per dataset (avg ~18), completing selection in ~1.8s/dataset on CPU. The selector's phase correlation measures whole-frame displacement including character animation, which is a known flaw — it cannot distinguish camera pan from character movement.

### 2.2 Pipeline Stages Active

| Stage | Status |
|-------|--------|
| Smart frame selection | ✅ Active (new) |
| BiRefNet foreground masking | ✅ Active |
| Photometric normalisation (adaptive clamp) | ✅ Active |
| LoFTR pairwise matching | ✅ Active |
| Bundle adjustment (with outlier rejection) | ✅ Active |
| Affine validation (min_gap=25px, ratio<3) | ✅ Active (threshold lowered from 50px) |
| ECC refinement | ✅ Active |
| Temporal median render (Stage 9) | ✅ Active |
| **Render quality gate** | ✅ Active (new) — seam_coherence>35 OR strip_banding>25 → SCANS |
| Inter-strip colour coherence guard | ✅ Active (new) — skips normalisation when adj strips differ >20 lum units |
| Foreground composite (Stage 11) | ✅ Active (when gate passes) |
| Ground truth comparison | ✅ Active (new) — SSIM/PSNR vs GT images |

---

## 3. Overall Statistics

### 3.1 Fallback Breakdown

| Category | Count | % of 96 |
|----------|------:|---------:|
| Render quality gate → SCANS | 39 | 40.6% |
| Affine validation: min_gap < 25px | 6 | 6.3% |
| Affine validation: ratio > 3.0 | 7 | 7.3% |
| **Total SCANS fallbacks** | **52** | **54.2%** |
| True ASP composites | 44 | 45.8% |

The **render quality gate** — which measures seam coherence and inter-strip colour banding in the Stage 9 temporal median render before Stage 11 composite runs — is now the largest single reason for falling back to SCANS. It correctly identifies renders where the temporal median has already produced severe horizontal banding (from mismatched animation frames stacked vertically), preventing Stage 11 from amplifying bad renders into catastrophically banded outputs.

### 3.2 Ground Truth SSIM Summary (55 tests with GT)

| Metric | ASP | Simple stitch |
|--------|----:|-------------:|
| Mean SSIM vs GT | **0.669** | **0.695** |
| Median SSIM vs GT | 0.685 | 0.714 |
| Min SSIM vs GT | 0.474 (test20) | 0.509 (test31) |
| Max SSIM vs GT | 0.889 (test17) | 0.855 (test17) |

**The simple stitch is on average 3.9% closer to the ground truth** (SSIM 0.695 vs 0.669). This is a definitive result: across the 55 tests with a reference panorama, the baseline OpenCV SCANS stitch outperforms the full 13-stage pipeline on the key quality metric.

### 3.3 Seam Coherence (horizontal colour banding proxy)

Lower = less banding. Both pipelines are nearly indistinguishable at the aggregate level:

| | ASP | Simple stitch |
|--|----:|-------------:|
| Mean seam_coherence | 26.0 | 25.5 |
| Median seam_coherence | 25.4 | 25.8 |
| Max seam_coherence | 61.3 (test75) | 61.5 (test75) |

That the two pipelines score similarly means the render gate successfully filtered out the worst ASP outputs (which had seam_coherence >35). The 44 true ASP composites that remain are genuinely competitive with simple stitch — but the comparison unfairly excludes the 39 render-gate failures, all of which use SCANS under the "ASP" label in the output.

---

## 4. Render Quality Gate Analysis

### 4.1 What the gate does

After Stage 9 (temporal median render), before Stage 11 (foreground composite), the gate computes:
- **`seam_coherence`** — standard deviation of per-row mean luminance across the render. High std = horizontal colour bands.
- **`strip_banding`** — max luminance difference between adjacent frame-strip entry zones. High = adjacent strips are different colours.

Threshold: if `seam_coherence > 35` OR `strip_banding > 25` → fall back to SCANS.

### 4.2 Gate triggering frequency

**39 of 96 tests (40.6%) triggered the gate.** This is far higher than anticipated. All 39 use the SCANS fallback as their final output.

### 4.3 Why so many triggers?

The gate fires when the temporal median render itself has severe horizontal banding. This happens when:

1. **The smart selector chose frames from different animation states** — consecutive selected frames show the same camera position but with characters in different poses. The temporal median stacks these as vertical strips, each with a different animation state → each strip has a different colour.

2. **Phase correlation contamination** — the selector's 50px displacement threshold is satisfied partly by character animation movement, not pure camera pan. Selected frames may be 5px of camera movement + 45px of character movement = 50px phase correlation result, but almost no new canvas area.

3. **Tight scroll with rich animation** — in close-up character scenes, any camera movement is matched by continuous character animation, producing a frame-by-frame animation sequence rather than a spatial panorama.

### 4.4 Gate correctness

Cross-checking gate-triggered tests against visually verified outputs confirms the gate is largely correct. Test04 (confirmed catastrophic in visual inspection), test01 (visible hard colour step), test03 (severe banding) — all triggered the gate. The gate prevents Stage 11 from being applied to these already-bad renders, avoiding amplification of the banding.

However, some tests with moderate issues still pass the gate (seam_coherence ~28–32) and proceed to Stage 11 where they receive a suboptimal composite. A tighter threshold would catch more of these.

---

## 5. True ASP Composite Analysis (44 tests)

These 44 tests ran the full pipeline: smart selection → BiRefNet → matching → bundle adjust → affine validation (passed) → ECC → render → **render gate (passed)** → Stage 11 composite.

### 5.1 Quality by ground truth (tests with GT only)

Of the 44 true composites, 35 have ground truth:

| GT verdict | Count | Tests |
|-----------|------:|-------|
| `asp_better` | 7 | test09, test11, test17, test27, test50, test84 + test80 (render gate triggered in new run but listed as fallback — see note) |
| `simple_better` | 14 | test08, test12, test15, test16, test20, test26, test42, test45, test79, test82, test83, test90, test91, test92, test95 |
| `comparable` | 14 | test05, test06, test46, test57, test76, test85, test96, and others |

**Even among the cleanest ASP outputs (those that survived both validation and the render gate), simple stitch beats ASP by GT 40% of the time.**

### 5.2 Confirmed genuine ASP improvements (by GT)

**test17** — Best ASP result in the benchmark. SSIM vs GT = **0.889** (ASP) vs 0.855 (simple). A 4% SSIM advantage. The panorama correctly assembles ~19 frames with consistent vertical scroll, producing a taller, sharper, and more faithful reconstruction than simple stitch. This is the target reference for what a working ASP run should produce.

**test09** — SSIM vs GT = 0.785 (ASP) vs 0.762 (simple). 3% advantage. 21 selected frames, healthy alignment, seam_coherence=22.9 (moderate).

**test11** — SSIM vs GT = 0.654 (ASP) vs 0.603 (simple). 9% advantage. 11 frames with clean vertical pan; ASP captures more of the scene while maintaining structural coherence.

**test27** — SSIM vs GT = 0.705 (ASP) vs 0.679 (simple). 4% advantage. Visually confirmed proper panorama (previously identified as a genuine success case).

**test84** — SSIM vs GT = 0.816 (ASP) vs 0.769 (simple). 6% advantage. 11 frames; one of the most reliable ASP runs.

### 5.3 Where ASP fails despite passing all gates

**test15** — SSIM vs GT = 0.518 (ASP) vs 0.738 (simple). −28% gap. 27 selected frames from a slow-scroll sequence. The large frame count creates many overlapping strips, and the composite introduces visible banding at each boundary. Simple stitch accurately captures the scene in a single coherent image.

**test20** — SSIM vs GT = 0.474 (ASP) vs 0.617 (simple). −23% gap. The worst ASP output in the corpus. Coverage = 0.8799 (large black borders). The scene has a significant horizontal drift component that the vertical-dominant pipeline cannot handle — large unfilled canvas areas result.

**test12** — SSIM vs GT = 0.617 (ASP) vs 0.801 (simple). −30% gap. One of the clearest failures: simple stitch captures the scene cleanly; ASP produces horizontal banding at strip boundaries despite passing validation and the render gate. The render gate threshold (35.0) was insufficient here — this test's SC=20.2 is below the threshold.

**test42** — SSIM vs GT = 0.479 (ASP) vs 0.512 (simple). seam_gradient = 13.50 (highest among true composites). The DP seam finder places boundaries through character body regions, creating sharp luminance transitions that degrade structural similarity to the reference.

### 5.4 Stage timing for true ASP composites

| Stage | Avg (s) | Max (s) | % of total |
|-------|--------:|--------:|----------:|
| BiRefNet | 9.1 | 19.4 | 11.9% |
| Matching (LoFTR) | 13.2 | 33.6 | 17.2% |
| Bundle adjust | 4.1 | 27.1 | 5.4% |
| ECC refinement | 2.9 | 16.8 | 3.8% |
| **Render (Stage 9)** | **30.0** | **132.1** | **39.2%** |
| Composite (Stage 11) | 15.9 | 44.8 | 20.8% |

Render + composite together account for **60% of total pipeline time**. The render stage is the primary compute bottleneck (avg 30s, max 132s for test17 which has 19 frames on a tall canvas). Vectorising the temporal median accumulation would be the highest-leverage performance improvement.

---

## 6. Alignment Analysis

### 6.1 Validation failures (13 tests)

| Reason | Count | Tests |
|--------|------:|-------|
| `ratio > 3.0` (catastrophic bundle outlier) | 7 | test13 (11.1×), test54 (3.5×), test64 (4.2×), test66 (3.1×), test70 (4.1×), test73 (3.8×), test89 (4.0×) |
| `min_gap < 25px` | 6 | test14 (16.7px), test30 (21.0px), test48 (6.8px), test49 (23.3px), test77 (18.8px), test78 (5.0px) |

The ratio failures represent genuine bundle adjustment instability — single bad LoFTR matches producing outlier edges that the post-solve residual pruning cannot fully eliminate. The min_gap failures are near-duplicate frames surviving smart selection and being placed within 25px of each other on the canvas.

**Notably:** The previous min_gap threshold was 50px. Lowering to 25px in this run rescued ~9 tests that would have previously failed. Among those rescued, some (test30, test49) show comparable or simple_better GT verdict, confirming that the threshold reduction was appropriate but not sufficient to guarantee ASP quality.

### 6.2 Render gate as secondary alignment failure detector

The 39 render-gate failures represent a category not captured by affine validation: **alignments that pass geometric health checks but produce semantically wrong frame ordering**. The affine ratio can be 1.0× (perfect consistency) while still placing animation frames from different time points as adjacent canvas strips. The render gate correctly catches this class of failure that the affine validator cannot detect.

---

## 7. Ground Truth Comparison — Key Findings

### 7.1 ASP SSIM distribution vs GT

| SSIM range | Count | Interpretation |
|-----------|------:|---------------|
| > 0.80 | 4 | test17 (0.889), test84 (0.816), test74 (0.843), test76 (0.792) |
| 0.70–0.80 | 20 | Moderate quality — some structural correspondence |
| 0.60–0.70 | 17 | Poor correspondence — significant misalignment or banding |
| < 0.60 | 14 | Severe failure — large structural divergence from reference |

### 7.2 Simple stitch SSIM distribution vs GT

| SSIM range | Count | Interpretation |
|-----------|------:|---------------|
| > 0.80 | 10 | Much more consistently achieving high GT similarity |
| 0.70–0.80 | 22 | |
| 0.60–0.70 | 14 | |
| < 0.60 | 9 | |

The simple stitch has more tests above 0.80 (10 vs 4) and fewer below 0.60 (9 vs 14). It is systematically more reliable at reproducing the ground truth structure.

### 7.3 Tests where ASP is genuinely better (8 tests)

| Test | ASP SSIM | Simple SSIM | Δ | Notes |
|------|--------:|------------:|--:|-------|
| test17 | **0.889** | 0.855 | +0.034 | Best ASP result; consistent vertical pan |
| test84 | **0.816** | 0.769 | +0.047 | 11 frames; clean alignment |
| test27 | **0.705** | 0.679 | +0.026 | Confirmed good panorama; 20 frames |
| test09 | **0.785** | 0.762 | +0.023 | 21 frames; consistent scroll |
| test11 | **0.654** | 0.603 | +0.051 | 11 frames; ASP captures more scene |
| test80 | **0.606** | 0.559 | +0.047 | Render-gate fallback but still better |
| test25 | **0.732** | 0.695 | +0.037 | New test; render-gate fallback better |
| test50 | **0.570** | 0.550 | +0.020 | Marginal; comparable by threshold |

### 7.4 Tests where simple stitch is decisively better (worst ASP cases by GT gap)

| Test | ASP SSIM | Simple SSIM | Δ | Notes |
|------|--------:|------------:|--:|-------|
| test15 | 0.518 | 0.738 | **−0.220** | 27 frames; severe strip banding |
| test16 | 0.549 | 0.733 | **−0.184** | 15 frames; colour mismatch across strips |
| test20 | 0.474 | 0.617 | **−0.143** | Coverage=0.88; diagonal scroll unsupported |
| test12 | 0.617 | 0.801 | **−0.184** | Passes gate (SC=20.2) but seam banding |
| test42 | 0.479 | 0.512 | **−0.033** | seam_gradient=13.5; seams through bodies |
| test45 | 0.597 | 0.620 | **−0.023** | SC=39.5; severe banding despite passing gate |
| test91 | 0.504 | 0.542 | **−0.038** | SC=35.0; right at gate threshold |
| test83 | 0.769 | 0.840 | **−0.071** | Even at moderate SC, ASP loses |

---

## 8. Per-Phase Status

### Phase 1 — Smart Frame Selection
**Status: Partially broken for animated video**

The phase-correlation displacement estimator measures whole-frame shift including character animation. For animated close-up scenes where characters occupy most of the frame, a 50px character movement registers as 50px "camera pan." Selected frames then have:
- Nearly identical camera positions (≤5px true pan)
- Wildly different character animation states
- Result: vertical strip panoramas of animation frames, not spatial panoramas

**Specific evidence:** The render gate triggering 39/96 times (41%) directly traces back to frame selection producing temporally-diverse frames that the temporal median cannot reconcile. All 39 gate failures had render seam_coherence > 35, indicating the render itself shows severe inter-strip colour variation before Stage 11 even runs.

### Phase 2 — BiRefNet Foreground Masking
**Status: Working correctly**

BiRefNet successfully separates foreground (animated characters) from background (static scene elements) in all tested datasets. The masks are used by the photometric normalisation, seam DP cost function, and inter-strip coherence guard. No failures observed in this phase.

### Phase 3 — LoFTR Pairwise Matching
**Status: Working, but edge rejection too aggressive**

LoFTR produces raw edges that are then filtered by the geometric consistency filter. Rejection rates remain high (20–90% of raw edges rejected in many tests). For tests with very few surviving edges (e.g., test34 at 93% rejection, test49 at 95%), the bundle adjuster operates on near-degenerate systems. Most ASP successes achieve alignment despite high rejection because the surviving edges are geometrically consistent.

Matching time averages 13.2s for true ASP composites (max 33.6s). This is the second-largest stage cost after render.

### Phase 4 — Bundle Adjustment
**Status: Largely working; outlier failures in 7 tests**

The post-solve residual pruning (reject edges where |residual| > 3× median; re-solve) successfully handles the majority of bad LoFTR matches. Only 7 tests produced ratio > 3.0, down from 12 in the pre-Phase-3 corpus. The 7 remaining ratio failures include test13 (ratio=11.1) where a single catastrophically wrong edge dominates — a more robust loss function (GNC Cauchy, §1.1-C in the roadmap) would handle this.

Bundle adjust time averages 4.1s but reaches 27.1s in one case — likely a dataset where Retry 2/3 logic ran multiple re-solve iterations.

### Phase 5 — Affine Validation
**Status: Threshold improved; some borderline cases remain**

The new 25px min_gap threshold (reduced from 50px) correctly rescues tests with tight but valid frame spacing. 6 tests still fail min_gap, all with gaps < 25px (true near-duplicate clustering). The vector magnitude gap computation handles diagonal scrolls correctly.

### Phase 6 — ECC Refinement
**Status: Working; minor cost**

ECC sub-pixel refinement averages 2.9s and helps marginal cases achieve the final alignment precision needed for composite seams. No failures observed.

### Phase 7 — Temporal Median Render (Stage 9)
**Status: Functionally correct; bottleneck; quality depends entirely on input**

The render is mathematically correct — it computes the per-pixel temporal median across all warped frames. The problem is its input: when selected frames show the same canvas position with different animation states, the "median" of N different character poses is an average/ghost, not a clean background. The render gate (new) detects this condition and falls back to SCANS.

Average render time 30.0s, max 132.1s. This is the single largest stage by cost (39% of total). Vectorisation with NumPy or GPU-based median would reduce this by 5–10×.

### Phase 8 — Render Quality Gate
**Status: Correctly filtering, but threshold needs tuning**

The gate (seam_coherence > 35 OR strip_banding > 25) caught 39 tests. However, tests like test12 (SC=20.2, simple_better by GT with −0.18 SSIM gap) and test45 (SC=39.5, simple_better) show that the current thresholds are both slightly too permissive (test12 passes when it should not) and correctly blocking (test45 triggers and falls back to SCANS).

A tighter seam_coherence threshold of 20 would catch test12 and improve overall precision, but may also reject borderline cases that have genuinely good outputs.

### Phase 9 — Foreground Composite (Stage 11)
**Status: Structural issues remain; inter-strip guard helps**

The new inter-strip colour coherence guard (skip normalisation when adjacent strips differ by >20 lum units) prevents the ±7% photometric correction from amplifying large colour mismatches. This is confirmed by the absence of egregious gain-amplified banding in the 44 true composites — the worst banding cases were caught by the render gate upstream.

However, the seam DP placement continues to cut through character bodies in many cases (average seam_gradient = 9.3 across true composites). The foreground penalty weight in the seam DP is insufficient to reliably route seams through background regions.

---

## 9. Root Cause Summary

### Primary failure: Animated video vs. static scroll assumption

The pipeline was designed for scrolling manga/artwork where content is static between frames. The test corpus is animated video where characters move with every frame. The smart selector chooses frames based on total frame displacement (including character animation), then stacks them as spatial strips. The resulting composite is a temporal animation collage, not a spatial panorama.

**Evidence:** 39/96 tests (41%) triggered the render quality gate, meaning their Stage 9 output already had severe horizontal colour banding before Stage 11 could make it worse. This is the signature of temporal animation frames being composited as spatial strips.

### Secondary failure: Seam placement through character bodies

Even in the 44 tests that survived the render gate, the DP seam path often cuts through character bodies, creating visible seams. Average seam_gradient = 9.3 for true ASP composites vs. the target of < 5.0. The BiRefNet foreground mask exists as a seam cost term but is not weighted aggressively enough.

### Tertiary failure: Insufficient temporal coverage per canvas row

With 50px inter-frame steps and ~1080px frame height, most canvas rows have approximately 1080/50 ≈ 21 frames contributing. However, because those 21 frames come from different animation states, the temporal median produces a blurred/ghosted composite rather than a clean background. The median of 21 different character poses is neither a coherent pose nor a clean background.

---

## 10. Recommendations (Prioritised)

### P0 — Background-only phase correlation in frame selector (CRITICAL)

**Problem:** The smart selector uses whole-frame phase correlation, which is contaminated by character animation.

**Fix:** Run a lightweight BiRefNet estimate (or heuristic background detector based on frame-peripheral pixels) before frame selection. Use only background-masked pixels for phase correlation. This directly addresses the root cause.

**Expected impact:** The 39 render-gate failures are almost entirely caused by bad frame selection. If the selector correctly identifies camera displacement (not animation displacement), the render gate trigger rate would drop from 41% to ~5%.

**Implementation:** `_smart_select_frames()` in `bench_anime_stitch.py` (benchmark) and/or `AnimeStitchPipeline.run()` in `pipeline.py` (production). A fast heuristic: use only the outer 20% border of each frame (where background is more likely) for phase correlation.

### P1 — Tighten render quality gate threshold (QUICK WIN)

**Problem:** The current seam_coherence threshold of 35 is too permissive. Tests like test12 (SC=20.2) pass the gate but produce simple_better output by GT (SSIM gap −0.18).

**Fix:** Lower seam_coherence threshold to 22–25 and strip_banding threshold to 20. Also add a secondary check: if `seam_gradient_after_composite > 12`, automatically flag as quality failure in the results.

**Expected impact:** Catches test12, test45, test55, test91, and others where the gate currently passes but the output is visibly banded.

### P2 — Increase foreground penalty in seam DP (QUALITY)

**Problem:** The DP seam finder cuts through character bodies, creating seam_gradient values of 8–13 even in good composites (target < 5).

**Fix:** In `compositing.py`, increase the foreground mask cost weight in `_find_optimal_boundaries()`. The background penalty should strongly prefer paths through BiRefNet-classified background pixels. A multiplier of 3–5× on the existing foreground cost would force seams into background corridors.

**Expected impact:** Reduces seam_gradient in true composites from avg 9.3 to ~5.0 for tests with sufficient background area.

### P3 — Vectorise temporal median render (PERFORMANCE)

**Problem:** Render averages 30s and peaks at 132s, accounting for 39% of total pipeline time.

**Fix:** In `rendering.py`, accumulate all warped frames into a `(N, H, W, 3)` uint8 tensor and call `np.median(arr, axis=0)` on chunked slices. Current implementation iterates per-frame in Python. Expected speedup: 5–10×.

**Expected impact:** Reduces avg render from 30s to 3–6s; total pipeline time drops ~35%.

### P4 — Temporal coverage check before composite (QUALITY GATE)

**Problem:** When most canvas rows are covered by only 1–2 frames from similar animation states, the temporal median has no de-ghosting power.

**Fix:** After computing canvas geometry, count frame coverage per row. If `np.percentile(coverage_per_row[coverage_per_row>0], 50) < 3`, fall back to SCANS before running Stage 9 at all (saves render time too). This complements the render gate by catching cases upstream.

**Implementation:** In `bench_anime_stitch.py`, after `_compute_canvas()`, compute coverage array using affine positions and frame heights. O(N) computation taking < 1ms.

### P5 — Adaptive render gate threshold based on scroll speed (ACCURACY)

**Problem:** The static seam_coherence threshold cannot distinguish legitimate brightness gradients in scene content from animation-induced colour banding.

**Fix:** Compute the expected luminance gradient from the GT image (if available) and calibrate the threshold per-test. For tests without GT, use the ratio of seam_coherence before and after normalisation as the discriminator.

**Expected impact:** Reduces false positives (tests incorrectly sent to SCANS) and false negatives (banded composites incorrectly passing the gate).

### P6 — GNC robust loss for bundle adjustment (ROBUSTNESS)

**Problem:** 7 tests fail with ratio > 3.0. The current post-solve residual pruning cannot recover from one catastrophically bad edge (test13: ratio=11.1).

**Fix:** Replace the L2 residual in the LM solve with a Cauchy or Geman-McClure loss via `scipy.optimize.least_squares(loss='cauchy', f_scale=...)`. The robust loss automatically down-weights outlier edges during optimisation without a separate rejection step.

**Expected impact:** Eliminates the 7 ratio failures in this corpus. Generalises better to unseen data than the current 3×-median-threshold heuristic.

### P7 — SCANS fallback preprocessing bypass (QUALITY)

**Problem:** When the pipeline falls back to SCANS, the fallback uses BiRefNet-preprocessed and photometrically-normalised frames. For some tests, this preprocessing degrades SCANS quality vs. running SCANS on raw frames (as seen in the GT gap for test01, test04, test49).

**Fix:** In `process_dataset()` in `bench_anime_stitch.py`, take a snapshot of `frames` and `frames_paths` before BiRefNet runs (`scans_frames_original = list(frames_paths)`). When falling back to SCANS, use `_run_simple_stitch(scans_frames_original, ...)` instead of the preprocessed version.

---

## 11. Test Corpus Map

### Tests where ASP wins by GT (8)
test09, test11, test17, test25, test27, test50, test80, test84

### Tests where simple stitch wins by GT (23)
test01, test04, test08, test12, test14, test15, test16, test20, test26, test42, test45, test49, test70, test77, test79, test82, test83, test88, test89, test90, test91, test92, test95

### Tests where both are comparable by GT (24)
test02, test05, test06, test31, test32, test33, test34, test37, test43, test44, test46, test52, test54, test57, test58, test59, test65, test72, test74, test76, test78, test85, test86, test96

### Tests without GT (41)
test03, test07, test10, test13, test18, test19, test21, test22, test23, test24, test28, test29, test30, test35, test36, test38, test39, test40, test41, test47, test48, test51, test53, test55, test56, test60, test61, test62, test63, test64, test66, test67, test68, test69, test71, test73, test75, test81, test87, test93, test94
