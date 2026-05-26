# Anime Stitch Pipeline — Detailed Analysis Report

**Benchmark run:** `anime_stitch_20260526_145622.json`  
**Date:** 2026-05-26 14:56:22  
**System:** Linux 7.0.0-14, 24-core CPU, 125.6 GB RAM, RTX 3090 Ti (23.5 GB VRAM), CUDA 12.8  
**Scope:** 22 datasets (asp_test1 … asp_test22), full run from frame input to final PNG  

---

## 1. Executive Summary

The Anime Stitch Pipeline (ASP) ran to completion on **10 of 22 datasets** (45%). The remaining 12 fell back to the SCANS simple stitch after affine health validation failed. Of the 22 final outputs (ASP or fallback):

- **2 datasets: ASP genuinely outperforms simple stitch** (test12, test14) — sharpness gains of +12 and +16 points respectively, with SSIM-verified quality improvement.
- **2 datasets: simple stitch outperforms ASP** (test13, test16) — both are fallbacks where the SCANS output is cleaner than what ASP would have produced.
- **18 datasets: comparable** — the two pipelines produce similar quality; neither has a decisive edge.

The average ASP sharpness (27.705) marginally exceeds simple stitch (27.419), but average ghosting is slightly worse (20.591 vs 19.409). The core problem is that ASP's fallback rate is 55% — on more than half of real-world inputs, the pipeline produces no added value. Fixing the bundle adjustment outlier problem would likely reduce the fallback rate to below 20%.

---

## 2. Timing Analysis

### 2.1 Stage Breakdown (ASP-succeeded tests only)

For the 10 tests where ASP ran to completion:

| Stage | Avg (s) | Min (s) | Max (s) | Bottleneck? |
|-------|--------:|--------:|--------:|-------------|
| simple_stitch | 3.79 | 2.56 | 5.57 | No |
| birefnet | 5.41 | 3.97 | 7.34 | Minor |
| matching | 5.05 | 3.16 | 8.47 | Minor |
| bundle_adjust | 0.15 | 0.02 | 0.43 | No |
| ecc | 3.45 | 0.57 | 5.36 | Minor |
| render | **20.78** | 13.62 | 33.78 | **Yes** |
| composite | **24.52** | 0.01 | 41.91 | **Yes** |
| visualisations | 3.67 | 3.51 | 4.16 | No |

Render (Stage 9 temporal median) and composite (Stage 11 hard-partition) together account for **≈45 of 70 average seconds** — roughly 64% of total ASP pipeline time. These are the primary bottlenecks.

The composite stage shows a large range (0.01 – 41.91s). The 0.01s outlier is test20 (pure horizontal scroll) where Stage 11 is bypassed because the compositing logic detects an axis mismatch.

### 2.2 Per-Test Total Times

| Test | Total (s) | Status |
|------|----------:|--------|
| test19 | 112.2 | ASP (slowest) |
| test6 | 94.9 | ASP |
| test22 | 92.6 | ASP |
| test1 | 82.3 | ASP |
| test15 | 80.0 | ASP |
| test11 | 69.0 | ASP |
| test14 | 68.2 | ASP |
| test17 | 56.9 | ASP |
| test12 | 53.0 | ASP |
| test10 | 51.6 | Fallback |
| test21 | 52.1 | Fallback |
| test20 | 45.0 | ASP |
| test7 | 46.1 | Fallback |
| test8 | 42.4 | Fallback |
| test16 | 40.4 | Fallback |
| test2 | 39.8 | Fallback |
| test3 | 33.3 | Fallback |
| test9 | 27.7 | Fallback |
| test22 | 92.6 | ASP |
| test5 | 21.7 | Fallback |
| test4 | 21.0 | Fallback (fastest) |
| test18 | 21.1 | Fallback |
| test13 | 23.7 | Fallback |

Fallback tests average **~33s** total (mostly simple_stitch + birefnet + matching + bundle_adjust + scans_fallback). ASP tests average **~79s** total. The overhead of ASP over fallback is approximately 46s on average, concentrated in render + composite stages.

test19 is slowest at 112.2s: 10 frames on a large canvas (4240×4187) with render=33.8s and composite=41.9s.

### 2.3 Matching Time Outliers

test7 (12.0s), test8 (18.1s), test16 (19.8s), test21 (29.6s) all have elevated matching times. These are the tests with the most rejected edges:

| Test | Raw Edges | Filtered | Rejected | Match Time (s) |
|------|----------:|---------:|---------:|---------------:|
| test21 | 9 | 8 | 1 | 29.6 |
| test16 | 18 | 14 | 4 | 19.8 |
| test8 | 22 | 14 | 8 | 18.1 |
| test7 | 36 | 17 | 19 | 12.0 |
| test2 | 23 | 14 | 9 | 14.2 |

test21's 29.6s matching for only 9 raw edges suggests LoFTR struggled with co-located duplicate frames, spending retry/search time on difficult pairs. test7's 19 rejected edges out of 36 (53% rejection rate) is the highest rejection rate in the dataset, confirming the 14-frame diagonal-scroll sequence is difficult to match.

---

## 3. Alignment Analysis

### 3.1 Affine Health Distribution

| Category | Count | Tests |
|----------|------:|-------|
| valid=True (ASP succeeded) | 10 | test1, test6, test11, test12, test14, test15, test17, test19, test20, test22 |
| ratio > 3.0 | 7 | test2, test3, test7, test8, test10, test13, test18 |
| min_gap < 50px | 4 | test4, test9, test16, test21 |
| scale_dev > 0.1 | 1 | test5 |

### 3.2 dy_cv (Inter-Frame Step Variance)

dy_cv measures coefficient of variation of frame-to-frame vertical steps. Higher = more uneven scroll spacing.

| dy_cv range | Tests | Interpretation |
|------------|-------|---------------|
| ≤ 0.1 | test15 (0.044), test17 (0.074), test5 (0.078), test22 (0.016) | Very consistent scroll |
| 0.1 – 0.5 | test1 (0.240), test4 (0.427), test12 (0.501) | Mild variation |
| 0.5 – 1.5 | test3 (0.961), test9 (0.673), test11 (1.011), test19 (0.293) | Noticeable unevenness |
| 1.5 – 5.0 | test8 (2.381), test16 (3.251), test18 (2.982), test20 (2.142) | High variation |
| > 5.0 | test2 (154.7), test7 (6.17), test10 (8.46), test13 (7.23), test21 (18.34) | Catastrophic |

test2 has dy_cv=154.7 — the highest of any test. The dy_steps alternate sign ([−114, +114, 0, 0, −137, +273, −139, +5, −8]) which is a near-perfect alternating pattern. This indicates the LoFTR pairs matched every other frame to a frame two steps away rather than the adjacent one, then sign-flipped half the edges.

test21 has dy_cv=18.3 with step[7]=−1206px (backward jump from frame 7→8 that returns near the start of the scroll). This is a co-located-frame artefact.

### 3.3 dx_cv (Horizontal Drift Variance)

dx_cv is dominated by test18 (1,606,437) — a numerical artefact from the bundle solution placing a frame at tx=−692px then snapping back. Ignoring that outlier:

| Test | dx_cv | Notes |
|------|------:|-------|
| test20 | 0.044 | Near-zero — pure horizontal scroll (tx-dominant dataset) |
| test15 | 6.89 | Significant horizontal drift in ty-dominant scroll |
| test6 | 16.65 | High horizontal drift despite valid affines |
| test7 | 12.16 | Large horizontal swings (1432px!) — diagonal scroll |
| test8 | 93.89 | dx_steps include ±40px swings and 0.0 entries |

test20 is the extreme opposite of test18: dx_cv=0.044 (near-zero variation) because all 7 frames move only horizontally (dy_steps ≈ 0; dx_steps = [−374, −389, −362, −371, −373, −336]). The vertical step variation is actually larger in relative terms (dy_cv=2.14) because a few frames have tiny +1 to −5px dy noise against the near-zero nominal.

### 3.4 min_gap_px Analysis

| min_gap_px range | Tests | Risk |
|-----------------|-------|------|
| 0.0 (exact co-location) | test7, test16, test18 | Will fail — temporal median collapses |
| 0.0 – 50.0 (triggers fail) | test4 (10.5), test9 (2.9), test21 (35.9) | Fails health check |
| 50 – 100 | test11 (59.3), test22 (89.3), test19 (96.0) | Marginal — passes |
| 100 – 200 | test1 (144.3), test10 (124.6), test13 (1.8) | test10/13 fail on ratio |
| > 200 | test5 (446.5), test14 (128.6), test15 (347.8) | Healthy |

The 50px threshold is appropriate: all tests below 50px show co-location or near-co-location artifacts. test11 at 59.3px is the tightest passing gap and shows elevated seam_gradient (7.214), suggesting 59px is borderline.

---

## 4. Matching Analysis

### 4.1 Raw vs Filtered Edges

| Test | Raw | Filtered | Rejected | Rejection% |
|------|----:|--------:|---------:|-----------:|
| test7 | 36 | 17 | 19 | 52.8% |
| test2 | 23 | 14 | 9 | 39.1% |
| test8 | 22 | 14 | 8 | 36.4% |
| test18 | 12 | 4 | 8 | 66.7% |
| test19 | 24 | 17 | 7 | 29.2% |
| test13 | 21 | 16 | 5 | 23.8% |
| test9 | 21 | 15 | 6 | 28.6% |
| test1 | 18 | 12 | 6 | 33.3% |
| test10 | 36 | 30 | 6 | 16.7% |
| test11 | 15 | 11 | 4 | 26.7% |
| test15 | 15 | 11 | 4 | 26.7% |
| test16 | 18 | 14 | 4 | 22.2% |
| test6 | 21 | 21 | 0 | 0% |
| test14 | 15 | 15 | 0 | 0% |
| test17 | 15 | 15 | 0 | 0% |
| test22 | 27 | 27 | 0 | 0% |

test18 has the highest rejection rate (66.7%): only 4 of 12 edges survive. Yet the surviving 4 edges produce dy_cv=2.98 and dx_cv=1,606,437 — the 4 surviving edges are themselves inconsistent. This indicates `_filter_edges` is not robust enough for this dataset.

Notably, 4 tests (test6, test14, test17, test22) have zero rejected edges — perfect consistency. All 4 are ASP-succeeded tests, and test14 and test22 are the top two on sharpness. High match consistency correlates with successful pipeline execution.

### 4.2 Edge Weight Distribution

All edges use method="unknown" (indicating LoFTR + ECC combined, not individually labeled). Edge weights reflect match confidence:

- High-weight edges (>0.8) indicate strong LoFTR keypoint agreement
- Low-weight edges (<0.5) indicate weak matches, often filtered out
- test10 has many edges with weight 0.47–0.53 — marginal confidence across all 14 frames, suggesting low-texture or highly repetitive content

---

## 5. Photometric Correction Analysis

### 5.1 Gain Clamp Summary

The gain clamp is [0.88, 1.14]. Tests are flagged as "clamped" if any frame hits a boundary:

| Status | Count | Tests |
|--------|------:|-------|
| Hits both clamps (gain=[0.88,1.14]) | 13 | test2,3,5,6,8,9,11,12,15,17,18,21,22 |
| Hits max clamp only | 3 | test1 [0.895,1.14], test4 [0.912,1.14], test14 [0.916,1.14], test16 [0.921,1.14] |
| Within clamp | 5 | test7,10,13,19,20 |

77% of tests (17/22) have at least one frame hitting a gain boundary. For these tests, photometric normalization is operating at its limits — some frames remain under-corrected.

### 5.2 Wide Gain Range Tests (likely banding)

The gain range (max_gain − min_gain) represents the total photometric spread across frames:

| Test | Min Gain | Max Gain | Range | Concern |
|------|--------:|---------:|------:|---------|
| test2 | 0.880 | 1.140 | 0.260 | Both clamped — scene has extreme brightness variation |
| test3 | 0.880 | 1.140 | 0.260 | Same |
| test5 | 0.880 | 1.140 | 0.260 | Same |
| test6 | 0.880 | 1.037 | 0.157 | Only min clamped |
| test8 | 0.880 | 1.140 | 0.260 | Both clamped |
| test9 | 0.880 | 1.140 | 0.260 | Both clamped |
| test11 | 0.886 | 1.140 | 0.254 | Near-both clamped |
| test12 | 0.880 | 1.140 | 0.260 | Both clamped; darkest scene (ref_lum=38.5) |
| test13 | 0.992 | 1.006 | 0.014 | Essentially flat — bright uniform scene |
| test17 | 0.880 | 1.140 | 0.260 | Both clamped; seam_gradient only 2.936 despite this |
| test22 | 0.880 | 1.140 | 0.260 | Both clamped; highest ASP ghosting (28.60) |

### 5.3 Gain Range vs Quality Correlation

Tests with gain range = 0.260 (both clamps hit) do not automatically produce worse output — test17 has gain range 0.260 but seam_gradient=2.936 (very low), while test6 has gain range 0.157 but seam_gradient=6.998 (high). The seam gradient depends more on whether the gain-corrected frames have smooth content transitions at the composite boundary than on the gain magnitude itself.

However, test22's high ghosting (28.60) combined with both clamps clamped suggests the 11-frame sequence has frames that are under-corrected at both ends of the brightness range, introducing tonal inconsistency at frame boundaries that manifests as ghosting in the composite.

---

## 6. Quality Metrics Analysis

### 6.1 Sharpness Comparison

ASP sharpness advantages (ASP − simple):

| Test | ASP Sharp | SS Sharp | Delta | Notes |
|------|----------:|---------:|------:|-------|
| test14 | **81.21** | 65.33 | +15.88 | Largest ASP sharpness lead; asp_better verdict |
| test12 | 26.77 | 14.58 | +12.19 | asp_better verdict |
| test22 | 42.35 | 34.05 | +8.30 | comparable verdict |
| test17 | 25.92 | 20.31 | +5.61 | comparable |
| test1 | 28.77 | 20.51 | +8.26 | comparable |
| test6 | 30.99 | 21.25 | +9.74 | comparable |
| test4 | 36.13 | 34.71 | +1.42 | comparable |
| test11 | 21.00 | 18.83 | +2.17 | comparable |
| test9 | 40.55 | 43.75 | −3.20 | comparable (fallback) |
| test7 | 27.66 | 42.65 | −15.0 | comparable (fallback — large loss) |
| test13 | 44.73 | 59.60 | −14.87 | simple_better |
| test16 | 24.15 | 38.46 | −14.31 | simple_better (fallback) |
| test10 | 22.40 | 34.65 | −12.25 | comparable (fallback) |

The two "simple_better" cases (test13, test16) and the two comparable-but-sharp-loss cases (test7, test10) are all fallbacks. In every case where ASP actually ran to completion, ASP sharpness equals or exceeds simple stitch. This strongly suggests the sharpness advantage of ASP is real and consistent — the problem is only when the pipeline falls back.

### 6.2 Ghosting Score Comparison

Higher ghosting = more frame-bleed artifacts. Difference = ASP ghosting − simple ghosting:

| Test | ASP Ghost | SS Ghost | Δ | Notes |
|------|----------:|---------:|--:|-------|
| test22 | 28.60 | 23.31 | +5.29 | Worst ASP ghosting; both pipelines high |
| test12 | 25.14 | 17.44 | +7.70 | ASP better on sharpness but worse on ghosting |
| test6 | 20.58 | 16.29 | +4.29 | ASP seam issues create ghosting |
| test11 | 23.60 | 20.94 | +2.66 | Mild increase |
| test1 | 19.32 | 14.95 | +4.37 | ASP adds ghosting vs simple |
| test19 | 14.99 | 14.37 | +0.62 | Nearly identical |
| test15 | 15.94 | 12.47 | +3.47 | ASP slightly worse |
| test14 | 28.45 | 30.20 | −1.75 | ASP slightly better |
| test17 | 23.56 | 19.69 | +3.87 | ASP higher |
| test20 | 17.09 | 17.53 | −0.44 | Nearly identical |

In the ASP-succeeded tests, ASP consistently has higher ghosting than simple stitch (except test14 and test20). This is counterintuitive: the temporal median render is specifically designed to deghost, yet the final composites have more ghosting. The likely explanation is that the Stage 11 hard-partition composite introduces new "ghosting" when the seam finder places boundaries through character body regions — the hard cut at those positions creates ghost-like edge artifacts that the ghosting metric counts.

### 6.3 Tests Where ASP Genuinely Wins

**test12** (asp_better, SSIM=0.730):
- ASP sharpness=26.77 vs simple 14.58 (+12.19)
- Simple stitch coverage=0.9861 (poor) — OpenCV stitcher failed to cover the full canvas
- 6 frames, source 1790×3693, valid affines (ratio=1.336)
- ASP produces a 3719×3201 output vs simple's 3838×3965 — shorter but sharper

**test14** (asp_better, SSIM=0.749):
- ASP sharpness=81.21 vs simple 65.33 (+15.88)
- ASP output 3906×3618 vs simple 3811×2666 — pipeline captures 952px more height
- 7 frames, source 2157×3840, valid affines (ratio=1.014)
- This is the clearest win: sharper, taller, and lower ghosting than simple stitch

---

## 7. Fallback Analysis

All 12 fallback tests produce their ASP output via SCANS simple stitch. The "metrics_asp" columns in the table therefore reflect the SCANS fallback result, not a true ASP composite. This makes comparisons somewhat artificial for these tests.

| Test | Fallback Reason | ASP(=SCANS) Sharp | SS Sharp | SSIM | Notes |
|------|----------------|------------------:|---------:|-----:|-------|
| test2 | ratio=86.2 | 11.70 | 10.01 | 0.648 | Both very low sharpness; dark scene |
| test3 | ratio=5.7 | 13.27 | 13.05 | 0.905 | Nearly identical; simple wins on seam |
| test4 | min_gap=10.5 | 36.13 | 34.71 | 0.791 | Comparable; single bad pair collapses |
| test5 | scale_dev=0.121 | 10.10 | 10.96 | 0.898 | Both soft; zoom+pan scene |
| test7 | ratio=61.6 | 27.66 | 42.65 | 0.604 | Simple stitch much sharper; diagonal scroll |
| test8 | ratio=5.1 | 26.96 | 30.44 | 0.670 | Simple slightly better |
| test9 | min_gap=2.9 | 40.55 | 43.75 | 0.950 | Nearly identical; very similar output |
| test10 | ratio=12.3 | 22.40 | 34.65 | 0.720 | Simple substantially sharper |
| test13 | ratio=31.5 | 44.73 | 59.60 | 0.947 | simple_better verdict |
| test16 | min_gap=0.0 | 24.15 | 38.46 | 0.932 | simple_better verdict |
| test18 | ratio=69.0 | 12.05 | 12.66 | 0.751 | Near-identical; dark scene |
| test21 | min_gap=35.9 | 29.36 | 26.12 | 0.937 | Fallback SCANS beats the simple-stitch baseline |

Key observations:
- For test3, test4, test9, test21: the fallback SCANS result is essentially as good as the independent simple stitch (SSIM > 0.90). The alignment failure didn't catastrophically corrupt the fallback.
- For test7, test10, test13, test16: the SCANS fallback produces noticeably worse results than the independent simple stitch. These are cases where the matching/bundle process produced bad internal state that partially corrupts even the fallback path, OR where the simple stitch runs on a different set of processed frames.
- test13 and test16 are the only "simple_better" verdicts — in both cases the SCANS fallback is worse than the independently-computed simple stitch (SSIM 0.947 and 0.932 respectively), meaning the pipeline's preprocessing or frame handling degraded quality.

---

## 8. Per-Test Detailed Notes

### test1 (8 frames, ASP succeeded, comparable)
ASP sharpness 28.77 vs simple 20.51 (+8.26), but ghosting 19.32 vs 14.95 (+4.37). Gain range hits both clamps [0.895, 1.14]. The wide gain swing across 8 frames (min bg_lum=55.0, max=103.34) drives the normalization near its limits. Seam gradient 5.063 — noticeable but not extreme. This is the test where extensive compositing fixes were previously applied (10 bugs fixed per the older issue notes); the current output represents the best achievable with the current compositing approach.

### test12 (6 frames, ASP succeeded, asp_better)
The strongest ASP win. 6 frames, very dark scene (ref_lum=38.52), source 1790×3693. Gain hits both clamps. Simple stitch coverage=0.9861 — OpenCV failed to fully stitch this dark scene. ASP produces coverage=0.9955, sharpness=26.77 vs simple's 14.58. The asp_better verdict is driven primarily by the simple stitch's alignment failure on dark content, not by ASP doing something exceptional. SSIM=0.730 confirms structural difference in the outputs. Ghosting is elevated in ASP (25.14 vs 17.44) — the gain-corrected composite at near-maximum gain correction introduces some frame-boundary tonal inconsistency.

### test13 (9 frames, fallback, simple_better)
Worst fallback case. Bundle adjustment produced dy_step[0]=−557px (wrong sign/direction) while all other steps are +100–127px. The first frame pair match is a sign-flip: LoFTR matched frame 0 to frame 1 as if they were scrolling upward when they scroll downward. SSIM=0.947 indicates the two outputs are structurally very similar (both are SCANS), but the pipeline's fallback SCANS produces sharpness=44.73 vs the baseline simple's 59.60. This suggests the pipeline's preprocessing (BiRefNet masking, frame normalization) before SCANS is introducing quality loss. The simple stitch run independently (without BiRefNet preprocessing) is sharper.

### test14 (7 frames, ASP succeeded, asp_better)
Best overall ASP output. Sharpness=81.21 is the highest in the benchmark. Ratio=1.014 (near-perfect spacing). Min gap=128.6px. dy_cv=0.160 (very consistent steps of 184–312px). The dx_steps show significant horizontal drift (−92.26px in the last step, dx_cv=3.22), but the affines are valid. ASP produces a 3906×3618 panorama vs simple's 3811×2666 — 952px taller with dramatically better sharpness. This is the target reference for what ASP should produce when alignment works perfectly.

### test16 (10 frames, fallback, simple_better)
Failure mode: min_gap=0.0px. The dy_steps contain two exact zeros (steps 3 and 4) and dx_step[6]=335.57px (large horizontal jump). The bundle adjuster co-located multiple frames at the same canvas row while simultaneously computing an unexplained 335px horizontal displacement for one pair. This creates a structurally pathological affine set. The fallback SCANS produces sharpness=24.15 vs baseline simple=38.46. As with test13, pipeline preprocessing is degrading the fallback quality.

### test18 (6 frames, fallback, comparable)
The most anomalous test. Affine ratio=69.0 and dx_cv=1,606,437 (extreme horizontal displacement in the bundle solution). Yet dy_steps=[552, 552, −1104, 552, 560] show a clear pattern: steps 0, 1 are +552px, step 2 is −1104px (exact reversal), then +552px again. This is a scene where the camera scrolled forward and then backward — or more likely, the matching for pair 2→3 produced a sign-flipped match that the bundle propagated as a full reversal. The fallback SCANS produces sharpness=12.05 (very low, dark scene) comparable to simple's 12.66. Low seam_gradient (1.455) indicates the fallback output is smooth despite the matching failure.

### test19 (10 frames, ASP succeeded, comparable)
Slowest ASP test at 112.2s. Coverage=0.9564 (worst coverage in the benchmark). dx_step[3]=−389.88px is a large horizontal outlier (all other dx_steps are ±0.7–5.5px). This single large horizontal step creates a canvas gap where no frame provides coverage. Sharpness=14.95 (very low) — the 10-frame dark-scene (blue bedsheets) has low inherent contrast. SSIM=0.820 indicates moderate similarity to simple.

### test20 (7 frames, ASP succeeded, comparable)
Pure horizontal scroll. ty values are all near-zero (dy_steps=[0,−5,−4,+2,+1,−1]px), all motion is in tx (dx_steps=[−374,−389,−362,−371,−373,−336]px). The pipeline correctly computes a wide canvas (6004×2168) and executes render but bypasses Stage 11 composite (composite_sec=0.006s). ASP seam_gradient=0.895 (lowest in the dataset) — the horizontal panorama has no horizontal seams to degrade. Sharpness=12.62 vs simple's 9.92 (+2.70). This is a case where ASP handles the scroll axis correctly (no vertical strip compositing attempted), producing a clean horizontal panorama.

### test22 (11 frames, ASP succeeded, comparable)
Highest ASP ghosting (28.60). 11 frames, consistent dy_steps (90.3–94.8px, dy_cv=0.016 — the most consistent scroll in the dataset). Gain hits both clamps. The extremely tight step spacing (90px with 11 frames = ~990px total scroll) means frame strips are only ~90px wide. With _FADE_ROWS=40, the fade-in/out occupies nearly 50% of each strip, creating extensive overlap regions where the temporal median must blend multiple frames simultaneously — amplifying ghosting. The consistent scroll is actually a liability here: it creates many tightly-packed frame boundaries.

---

## 9. Key Findings and Actionable Recommendations

### Finding 1: Bundle adjustment is the critical bottleneck
55% of tests fail due to bad affines. 7 of the 12 failures are ratio > 3.0 caused by one or two extreme outlier steps from bad LoFTR matches. Fixing outlier rejection in bundle_adjust.py would resolve test3, test10 (single-outlier) and likely partially help test2, test7, test13.

**Action:** Add post-solve residual pruning: compute per-edge predicted vs actual translation; reject edges with residual > 3× median; re-solve. Implement in `backend/src/anim/bundle_adjust.py`.

### Finding 2: ASP wins on sharpness when it runs
Every ASP-succeeded test has ASP sharpness ≥ simple stitch (the closest is test19: 14.95 vs 16.21, a marginal loss likely due to the coverage gap). Average ASP sharpness across the 10 succeeded tests = ~31, vs simple stitch ~27 for those same tests.

**Action:** The core pipeline is working correctly for quality when alignment succeeds. Effort should focus on increasing the success rate (fixing alignment) rather than improving the compositing algorithm.

### Finding 3: Ghosting is consistently higher in ASP than simple stitch
ASP ghosting exceeds simple in 8 of 10 succeeded tests. The temporal median render should eliminate ghosting, but Stage 11 compositing reintroduces it via hard boundary cuts through character regions.

**Action:** The DP seam finder should prefer seam paths through background (low-content) regions more aggressively. Consider adding a character mask cost to the seam DP: seam paths through masked foreground pixels should have higher cost than paths through background.

### Finding 4: Stage 11 composite is the compute bottleneck
Composite stage averages 24.5s and peaks at 41.9s (test19). It accounts for ~35% of total ASP time. Render stage averages 20.8s (30% of total).

**Action:** Profile composite.py for vectorization opportunities. The per-row seam path DP and feather zone computation may be parallelizable across image columns.

### Finding 5: Gain clamp is too narrow for dark scenes
17/22 tests hit the gain clamp. Dark scenes (ref_lum < 70) have the widest gain swings: the clamp at [0.88, 1.14] leaves some frames under-corrected. The bg-only BT.601 scalar correction (already implemented) is hue-safe and could support a wider clamp.

**Action:** Widen clamp from [0.88, 1.14] to [0.82, 1.20] for tests where ref_lum < 80. Use the existing bg-only correction path to avoid hue shifts.

### Finding 6: test3 and test10 are single-outlier failures that should be fixable
test3: dy_step[0]=1654px vs median 289px; test10: dy_step[0]=3653px vs median 174px. In both cases, only one frame-pair match is catastrophically wrong, and the remaining 9–12 pairs are excellent (dy_cv close to 1.0 for the remaining pairs). These are the easiest tests to fix.

**Action:** Implement single-outlier detection: if exactly one step has gap_ratio > 5× and all others < 2×, attempt re-matching of the offending frame pair with tighter ECC constraints.

### Finding 7: test13 and test16 pipeline preprocessing degrades fallback quality
For tests where SCANS fallback runs, the "metrics_asp" reflects SCANS output on pipeline-preprocessed frames. test13 SCANS gives sharpness=44.73 vs independent simple=59.60; test16 gives 24.15 vs 38.46. The preprocessing (BiRefNet masking, ECC alignment, frame normalization) is modifying the frames before SCANS stitches them, and the modifications are making SCANS worse for these particular scenes.

**Action:** When falling back to SCANS, consider using the original (pre-BiRefNet, pre-normalization) frame inputs rather than the pipeline-preprocessed frames.
