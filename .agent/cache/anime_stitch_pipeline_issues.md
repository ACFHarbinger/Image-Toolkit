# Anime Stitch Pipeline — Failure Analysis & Issue Tracker

**Last updated:** 2026-05-26 (full benchmark run — 22 datasets, all data from `anime_stitch_20260526_145622.json`)
**Benchmark file:** `backend/benchmark/results/anime_stitch_20260526_145622.json`
**Relevant codebase:** `backend/src/anim/`
**Test suite:** `backend/test/anim/` — run with `pytest backend/test/anim/`
**Test datasets:** `data/asp_testX/` — output images in `data/output/`

---

## 1. Overall Summary

| Metric | Value |
|--------|-------|
| Total datasets | 22 |
| ASP succeeded (used_fallback=false) | **10** |
| Fell back to SCANS simple stitch | **12** |
| Total benchmark time | 1215.8 s (≈20 min) |
| Avg time per dataset | 53.4 s |
| Verdict: asp_better | **2** (test12, test14) |
| Verdict: simple_better | **2** (test13, test16) |
| Verdict: comparable | **18** |
| Avg ASP sharpness | 27.705 |
| Avg simple stitch sharpness | 27.419 |
| Avg ASP ghosting score | 20.591 |
| Avg simple stitch ghosting score | 19.409 |
| Avg ASP coverage | 0.9971 |
| Avg SSIM (ASP vs simple) | 0.8144 |

**System:** Linux 7.0.0-14-generic, 24-core CPU, 125.6 GB RAM, NVIDIA RTX 3090 Ti (23.5 GB VRAM), CUDA 12.8, Python 3.11.14.

**Key takeaway:** ASP is broadly competitive with simple stitch (18 comparable, 2 wins, 2 losses) but only fully runs on 10/22 datasets. The 12 fallbacks fall back to the raw SCANS result, which means ASP produces no added value for 55% of inputs. The primary bottleneck is the affine health validator rejecting unstable bundle-adjusted affines.

---

## 2. Per-Test Summary Table

Tests are sorted numerically (test1 … test22). The JSON stores them in alphabetical order (test1, test10, test11, … test9).

| Test | Frames | FB | ASP Sharp | ASP Ghost | ASP Seam∇ | ASP Cov | SS Sharp | SS Ghost | SSIM | Verdict | Affine Health Reason |
|------|--------|----|---------:|----------:|----------:|--------:|---------:|---------:|-----:|---------|---------------------|
| test1  |  8 | N | 28.77 | 19.32 | 5.063 | 1.0000 | 20.51 | 14.95 | 0.824 | comparable | ok |
| test2  | 10 | Y | 11.70 | 17.85 | 3.452 | 0.9998 | 10.01 | 13.45 | 0.648 | comparable | ratio=86.2 > 3.0 |
| test3  | 11 | Y | 13.27 | 13.45 | 4.277 | 1.0000 | 13.05 | 13.58 | 0.905 | comparable | ratio=5.7 > 3.0 |
| test4  |  7 | Y | 36.13 | 23.00 | 2.703 | 1.0000 | 34.71 | 22.78 | 0.791 | comparable | min_gap=10.5px < 50px |
| test5  |  6 | Y | 10.10 | 12.01 | 3.186 | 0.9997 | 10.96 | 12.45 | 0.898 | comparable | scale_dev=0.121 > 0.1 |
| test6  |  9 | N | 30.99 | 20.58 | 6.998 | 0.9920 | 21.25 | 16.29 | 0.756 | comparable | ok |
| test7  | 14 | Y | 27.66 | 23.85 | 1.894 | 0.9999 | 42.65 | 20.05 | 0.604 | comparable | ratio=61.6 > 3.0 |
| test8  | 11 | Y | 26.96 | 26.87 | 4.571 | 1.0000 | 30.44 | 26.55 | 0.670 | comparable | ratio=5.1 > 3.0 |
| test9  |  9 | Y | 40.55 | 21.85 | 2.213 | 1.0000 | 43.75 | 23.15 | 0.950 | comparable | min_gap=2.9px < 50px |
| test10 | 14 | Y | 22.40 | 16.15 | 4.079 | 1.0000 | 34.65 | 23.46 | 0.720 | comparable | ratio=12.3 > 3.0 |
| test11 |  7 | N | 21.00 | 23.60 | 7.214 | 1.0000 | 18.83 | 20.94 | 0.795 | comparable | ok |
| test12 |  6 | N | 26.77 | 25.14 | 3.747 | 0.9955 | 14.58 | 17.44 | 0.730 | **asp_better** | ok |
| test13 |  9 | Y | 44.73 | 28.41 | 4.369 | 1.0000 | 59.60 | 31.96 | 0.947 | **simple_better** | ratio=31.5 > 3.0 |
| test14 |  7 | N | 81.21 | 28.45 | 5.490 | 0.9931 | 65.33 | 30.20 | 0.749 | **asp_better** | ok |
| test15 |  7 | N | 25.87 | 15.94 | 3.703 | 1.0000 | 25.17 | 12.47 | 0.838 | comparable | ok |
| test16 | 10 | Y | 24.15 | 15.10 | 3.208 | 0.9999 | 38.46 | 18.02 | 0.932 | **simple_better** | min_gap=0.0px < 50px |
| test17 |  7 | N | 25.92 | 23.56 | 2.936 | 0.9992 | 20.31 | 19.69 | 0.886 | comparable | ok |
| test18 |  6 | Y | 12.05 | 11.83 | 1.455 | 1.0000 | 12.66 | 10.55 | 0.751 | comparable | ratio=69.0 > 3.0 |
| test19 | 10 | N | 14.95 | 14.99 | 3.106 | 0.9564 | 16.21 | 14.37 | 0.820 | comparable | ok |
| test20 |  7 | N | 12.62 | 17.09 | 0.895 | 0.9998 |  9.92 | 17.53 | 0.917 | comparable | ok |
| test21 | 10 | Y | 29.36 | 25.36 | 5.241 | 1.0000 | 26.12 | 23.79 | 0.937 | comparable | min_gap=35.9px < 50px |
| test22 | 11 | N | 42.35 | 28.60 | 2.839 | 1.0000 | 34.05 | 23.31 | 0.851 | comparable | ok |

FB = used_fallback (Y = SCANS fallback used; metrics shown are from fallback output). ASP Seam∇ = seam_gradient. ASP Cov = coverage.

---

## 3. Failure Categories

### Category A — Catastrophic Bundle Adjustment (ratio >> 3.0, dy_cv >> 1.0)

Affected: **test2, test7, test10, test13, test18**

These tests have affine ratios far above 3.0 and/or wildly inconsistent dy_steps — the bundle adjuster produced a step sequence that is internally inconsistent (non-monotonic, alternating signs, single huge outlier step).

| Test | Ratio | Min Gap | dy_cv | dx_cv | Key dy anomaly |
|------|------:|--------:|------:|------:|----------------|
| test2 | 86.2 | 0.0 | 154.7 | 3.07 | Alternating ±114, then 272 then ±5–8 — clearly mis-ordered |
| test7 | 61.6 | 0.0 | 6.17 | 12.16 | Non-monotonic: +290, −358, +18, +3, +401, −620 |
| test10 | 12.3 | 124.6 | 8.46 | 3.51 | Step 0→1 = +3653px; steps 1–13 = −143 to −155px |
| test13 | 31.5 | 1.8 | 7.23 | 2.66 | Step 0→1 = −557px; steps 1–8 = +100–127px (sign flip) |
| test18 | 69.0 | 0.0 | 2.98 | 1,606,437 | dy_steps = [552, 552, −1104, 552, 560] — symmetric collapse |

**Root cause:** LoFTR produced gross mismatches for one or more frame pairs. The bundle adjuster has no RANSAC or outlier rejection: a single bad edge with a 1000px+ error pulls all frame positions off. In test10 frame-0→frame-1 gets dy=+3653px (vs ~170px for all other pairs). In test18 dx_cv=1,606,437 indicates an extreme horizontal offset in the bundle solution (pair 0→2 lands at dx=−692px then snaps back).

---

### Category B — Frame Clustering (min_gap < 50px)

Affected: **test4, test9, test16, test21**

These tests failed the min_gap check. Multiple frames were placed at nearly identical canvas positions.

| Test | Ratio | Min Gap | Failure reason | Notable clustering |
|------|------:|--------:|----------------|--------------------|
| test4 | 1.01 | 10.5 | min_gap=10.5px | dy_steps=[−274,−271,−271,−272,−273,**−10.5**] — last pair collapses |
| test9 | 1.38 | 2.9 | min_gap=2.9px | dy_steps=[−142,−374,−374,−447,**−33**,+36,−380,−300] — sign flip at step 5 |
| test16 | 2.13 | 0.0 | min_gap=0.0px | dy_steps=[−110,−143,**+253**,**0.0**,**0.0**,−142,+70,−138,−145] — frames co-located |
| test21 | 1.00 | 35.9 | min_gap=35.9px | dy_steps=[+177×7,**−1206**,+177] — a large backward jump creates near-duplicate at top |

In test16 frames share dy=0.0, 0.0, and dx_steps[6]=335.57 (large horizontal jump). In test21 the −1206 step is a jump back to near the start, creating co-located frames at ty=0. These cause the temporal median to overlay identical canvas rows from multiple frames, creating heavy ghosting.

---

### Category C — Scale/Rotation Deviation (scale_dev or max_rotation exceeds threshold)

Affected: **test5**

| Test | Ratio | Scale Dev | Max Rotation | Reason |
|------|------:|----------:|-------------:|--------|
| test5 | 1.02 | 0.121 | 0.0635 | scale_dev=0.121 > 0.1 |

test5 has healthy spacing (min_gap=446.5px, ratio=1.02) but the affine matrix has significant per-frame scale deviation (12.1%) and rotation (6.35°). The dx_steps show large horizontal motion: [−140, −51, +10, +48, −37]px. This is likely a zoom-with-pan sequence where the camera both scrolls and scales. The health validator correctly rejects it because warping frames with 12% scale mismatch produces blurred/misaligned composites.

---

### Category D — Seam Gradient Issues (seam_gradient > 6.0 in ASP succeeded tests)

Affected: **test6 (6.998), test11 (7.214)**

Both ASP-succeeded tests with high seam gradients have otherwise valid affines. These are cases where Stage 11 compositing produced visible brightness discontinuities despite correct alignment.

| Test | ASP Seam∇ | SS Seam∇ | Gain Range | Notes |
|------|----------:|----------:|-----------:|-------|
| test6 | 6.998 | 3.695 | [0.88, 1.037] | 9 frames; dx_cv=16.65 (high horizontal drift) |
| test11 | 7.214 | 5.048 | [0.886, 1.14] | 7 frames; dy step −301 is anomalous (negative = backward scroll) |

In test6, the large dx_cv=16.65 reflects significant horizontal drift between frames (dx_steps peak at 24.6px), and the gain hits the minimum clamp (0.88). In test11 the last dy_step is −301px (backward), indicating one mismatched pair that affects the strip boundary composite.

---

### Category E — Photometric Ghosting (ghosting_score > 25 in ASP succeeded)

Affected: **test11 (23.60), test12 (25.14), test14 (28.45), test22 (28.60)**

These are ASP-succeeded tests where ghosting is elevated. Note: test22 has the highest ASP ghosting (28.60) of any test, yet is still "comparable" to simple (23.31). High ghosting in both pipelines suggests scene-level issues (fast motion, repeating content) rather than pipeline-introduced artifacts.

| Test | ASP Ghost | SS Ghost | Delta | Interpretation |
|------|----------:|----------:|------:|---------------|
| test12 | 25.14 | 17.44 | +7.70 | ASP introduces ghosting vs simple — compositing issue |
| test14 | 28.45 | 30.20 | −1.75 | Both high; scene content driven; ASP slightly better |
| test11 | 23.60 | 20.94 | +2.66 | Mild increase in ASP; borderline |
| test22 | 28.60 | 23.31 | +5.29 | ASP worst absolute ghosting overall; likely seam zone overlap |

test12 is notable: ASP wins on sharpness (26.77 vs 14.58) and SSIM=0.730 marks it asp_better, yet ghosting is 25.14 vs 17.44. The gain is hitting both clamps (0.88–1.14) with a very dark scene (ref_lum=38.52), suggesting the extreme gain corrections are introducing subtle tonal inconsistencies across frame boundaries.

---

### Category F — Low Coverage (coverage < 0.99)

Affected: **test19 (0.9564)**

test19 is the only ASP-succeeded test with coverage below 0.99, at 0.9564 — meaning 4.36% of the canvas is black/empty. The canvas is 4240×4187 but the metrics region 4179×4126 has significant unfilled area. The dx_steps include one large outlier: dx_step[3]=−389.88px, indicating frame 3→4 has a large horizontal jump. This creates a region of the canvas where no frame provides coverage.

---

## 4. Alignment Failure Breakdown (12 Fallback Tests)

| Test | Frames | Ratio | Min Gap | Reason | dy_cv | dx_cv | Key anomaly |
|------|--------|------:|--------:|--------|------:|------:|-------------|
| test2 | 10 | 86.18 | 0.0 | ratio=86.2>3.0 | 154.7 | 3.07 | dy alternates sign; max_rotation=0.022, scale_dev=0.015 |
| test3 | 11 | 5.682 | 284.5 | ratio=5.7>3.0 | 0.961 | 2.97 | dy_step[0]=+1654px; all others +284–294px |
| test4 | 7 | 1.010 | 10.5 | min_gap<50px | 0.427 | 1.69 | Last dy_step only −10.5px (near-zero collapse) |
| test5 | 6 | 1.020 | 446.5 | scale_dev>0.1 | 0.078 | 1.88 | scale_dev=0.121, max_rotation=0.064 |
| test7 | 14 | 61.57 | 0.0 | ratio=61.6>3.0 | 6.17 | 12.16 | Non-monotonic dy, large dx swings (±1432px) |
| test8 | 11 | 5.077 | 24.0 | ratio=5.1>3.0 | 2.381 | 93.89 | Wildly irregular dy; dx_cv=93.9 indicates horizontal chaos |
| test9 | 9 | 1.378 | 2.9 | min_gap<50px | 0.673 | 2.55 | Step[4]=−33, step[5]=+36 (sign flip); max_rotation=0.041 |
| test10 | 14 | 12.326 | 124.6 | ratio=12.3>3.0 | 8.461 | 3.51 | dy_step[0]=+3653px (outlier bundle edge) |
| test13 | 9 | 31.483 | 1.8 | ratio=31.5>3.0 | 7.231 | 2.66 | dy_step[0]=−557px vs +100–127px for rest |
| test16 | 10 | 2.131 | 0.0 | min_gap<50px | 3.251 | 2.83 | Steps 3,4 = 0.0 (co-located); dx_step[6]=335.57px |
| test18 | 6 | 69.0 | 0.0 | ratio=69.0>3.0 | 2.982 | 1,606,437 | dx_cv=1,606,437 — extreme horizontal displacement in bundle |
| test21 | 10 | 1.001 | 35.9 | min_gap<50px | 18.341 | 9.04 | dy_step[7]=−1206px (backward jump); dx_steps oscillate ±33px |

**Note on test3:** ratio=5.7 is caused by a single large first step (dy_step[0]=+1654px) while all 10 remaining steps are 284–294px (very consistent). This is a case where frame 0 vs frame 1 matching produced a grossly wrong result but the rest of the sequence is fine. A single-outlier-rejection rule would fix this test.

**Note on test10:** Same single-outlier pattern: dy_step[0]=+3653px, all others −142 to −201px. Frame 0→1 matching failed.

**Note on test16:** min_gap=0.0 means exact frame co-location. dy_steps[3]=0.0, dy_steps[4]=0.0 plus dx_step[6]=335.57 indicate the bundle adjuster placed three frames at the same canvas position while simultaneously computing an unexplained 335px horizontal jump.

---

## 5. Root Causes

### 5.1 Single bad match poisons bundle adjustment

Tests test3, test10, test13 each have one catastrophically bad pairwise match that dominates the bundle solution. The bundle adjuster uses weighted least squares with no outlier rejection — one edge with a 1000px error in a chain of 10 edges with ~170px correct values will pull every subsequent frame position by hundreds of pixels.

**Evidence:** test3 dy_step[0]=1654px vs median 289px (5.7× outlier); test10 dy_step[0]=3653px vs median 174px (21× outlier); test13 dy_step[0]=−557px (wrong sign) vs median +113px.

**Fix needed:** Post-bundle-adjustment residual check with `3×median` threshold; remove outlier edges and re-solve.

### 5.2 Near-zero / zero-translation matches from co-located frames

Tests test4, test9, test16, test21 fail the min_gap check. The bundle adjuster places two or more frames at dy=0 (or within 10–35px) of each other. The source is LoFTR returning near-zero dy matches for frame pairs that show nearly identical content (possible duplicate or near-duplicate source frames).

**Evidence:** test16 has dy_steps[3]=0.0 exactly; test21 has frames 0,8,9 co-located at the same canvas position (dy_step[7]=−1206px jump back to start).

**Fix needed:** Filter edges with `|dy| < min_expected_step` (e.g. 50px) before bundle adjustment; deduplicate source frames.

### 5.3 Scale/rotation from zoom or perspective sequences

test5 has scale_dev=0.121 (12%) and max_rotation=0.064 (6°). This is a zoom-and-pan sequence. The pipeline's translation-only canvas model cannot handle scale or rotation changes between frames.

**Fix needed:** Detect scale/rotation in affines and either (a) apply full affine warp per frame, or (b) fall back to OpenCV projective stitcher.

### 5.4 Large dx offset in bundle solution (horizontal displacement)

test18 has dx_cv=1,606,437 — an essentially infinite horizontal coefficient of variation. The bundle solution produced a tx offset of −692px for frame 1 that snaps back to ~0 by frame 2. This likely means the LoFTR match for pair 0→2 had a large spurious horizontal component that propagated into the bundle.

### 5.5 Stage 11 composite seam gradient

For ASP-succeeded tests, the seam_gradient is elevated in test6 (6.998) and test11 (7.214) compared to simple stitch (3.695 and 5.048). These are cases where the gain-corrected compositing creates visible brightness bands. Both tests hit the gain clamp (min=0.88 or max=1.14), meaning the photometric normalization is at its limits.

---

## 6. Photometric Correction Observations

The gain clamp is [0.88, 1.14] (−12% / +14%). Of 22 tests:

- **17 hit at least one clamp boundary** (gain_min ≤ 0.881 or gain_max ≥ 1.139)
- **5 stay within clamp:** test7 [0.938, 1.082], test10 [0.942, 1.077], test13 [0.992, 1.006], test19 [0.967, 1.129], test20 [0.968, 1.137]

Tests hitting both clamps (gain=[0.88, 1.14] exactly):
**test2, test3, test5, test6, test8, test9, test11, test12, test15, test17, test18, test21, test22** — 13 tests. These have a full 26% brightness swing across frames, and the clamp is the limiting constraint on correction quality.

**Very dark scenes** (ref_lum < 70): test2 (41.8), test5 (81.3), test6 (74.5), test8 (65.5), test12 (38.5), test18 (51.5). Dark scenes see the largest proportional gain swings because even modest absolute luminance differences produce large ratios.

**test13 special case:** gain_range=[0.992, 1.006] — essentially no correction applied (frames_corrected=0). This is the scene with the highest ref_lum (207.16), indicating a very bright/uniform scene where per-frame luminance variation is negligible.

**Likely banding artifacts from gain clamping:** Tests where ASP ghosting exceeds simple by >5 points (test12: +7.70, test22: +5.29) and gain hits both clamps are the most likely candidates for visible gain-induced banding. The gain step between adjacent frames cannot be bridged smoothly when the correction is capped 6% short of the needed value.

---

## 7. Recommended Pipeline Improvements

### Priority 1 — Outlier-robust bundle adjustment

Add per-edge residual computation after initial LS solve; reject edges where `|residual| > 3 × median(residuals)`; re-solve with clean edges. This would fix test3, test10, and possibly test13 without any matching changes.

### Priority 2 — Near-zero edge filter before bundle adjustment

In `_filter_edges` (or a pre-bundle-adjust step): reject any edge where `|dy| < 50px AND |dx| < 50px`. These are either co-located frames (test16, test21) or failed LoFTR matches (test4). This would reduce min_gap failures.

### Priority 3 — Single-outlier affine step detection

Post-bundle, compute `gap_ratio = step_i / median(all_steps)` for each step. If any step is >10× the median, flag as single-outlier failure and attempt re-solve excluding the frame pair responsible. This is a targeted fix for test3/test10 where one match is bad but the rest are excellent.

### Priority 4 — Scale/rotation handling

For test5 (scale_dev=0.121), the full 2×3 affine matrix contains genuine scale and rotation that the translation-only canvas model cannot handle. Add a fallback path: if `max_scale_dev > 0.05` or `max_rotation > 0.03`, use per-frame full affine warp instead of translation-only placement.

### Priority 5 — Gain clamp widening with hue-safe correction

17/22 tests hit the gain clamp. Widening from [0.88, 1.14] to [0.80, 1.20] would allow larger corrections for dark scenes, but risks hue shifts. Use the existing bg-only BT.601 scalar correction (which is already hue-safe) to justify widening the clamp.

### Priority 6 — Seam gradient improvement for high-dx-cv tests

test6 (dx_cv=16.65) and test11 (dy_step anomaly: −301px) have the highest seam gradients. These represent cases where the composite boundary falls on content that changes dramatically between adjacent frames. Consider using a wider feather zone (proportional to the absolute luminance difference) to smooth these transitions.

---

## 8. Key File Locations

| File | Purpose |
|------|---------|
| `backend/src/anim/pipeline.py` | Pipeline orchestration, `_filter_edges`, fallback logic |
| `backend/src/anim/bundle_adjust.py` | Bundle adjustment (no outlier rejection — highest priority fix) |
| `backend/src/anim/compositing.py` | Stage 11 composite (gain, seam, feather) |
| `backend/src/anim/rendering.py` | Stage 9 temporal median render |
| `backend/src/anim/matching.py` | LoFTR/ECC pairwise matching |
| `backend/src/anim/canvas.py` | Canvas geometry, translation-only placement |
| `backend/src/anim/masking.py` | BiRefNet foreground masking |
| `backend/src/core/image_merger.py` | Simple stitch (SCANS fallback reference) |
| `backend/benchmark/results/anime_stitch_20260526_145622.json` | Full benchmark data |
| `data/output/` | All 44 final output PNGs (22 ASP + 22 simple) |
| `data/asp_testX/output/plots/` | Per-test visualisation plots |
| `data/asp_testX/output/panorama_stages/` | Intermediate stage outputs |
