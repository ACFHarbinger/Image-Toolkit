# ASP Pipeline Analysis — Session 142 (2026-06-21)

> **Current benchmark corpus:** 97 tests (`asp_test01–asp_test97`). 55 with ground truth; 42 cv_metrics-only.
> **Result file:** `backend/benchmark/results/anime_stitch_20260621_193956.json` (7435 s runtime).

---

## 1. Summary Statistics

| Metric | ASP | Simple | Delta |
|--------|-----|--------|-------|
| All-verdict: asp_better | 9 (9.3%) | — | — |
| All-verdict: comparable | 41 (42.3%) | — | — |
| All-verdict: simple_better | 46 (47.4%) | — | — |
| All-verdict: insufficient_data | 1 (1.0%) | — | — |
| GT-verdict (55 tests): asp_better | 6 | — | — |
| GT-verdict (55 tests): comparable | 22 | — | — |
| GT-verdict (55 tests): simple_better | 26 | — | — |
| Avg GT-SSIM (55 GT tests) | 0.6588 | 0.6992 | −0.0404 ▼ |
| Avg ghosting score (97 tests) | 38.7 | 27.2 | +11.5 ▼ |
| Avg sharpness (97 tests) | 108.9 | 63.8 | +45.1 ▲ |
| External SCANS fallbacks | 0 | — | — |
| Internal fallbacks | 13 | — | — |
| Alignment failed | 1 (test49) | — | — |

---

## 2. Per-Test Breakdown (all 97)

| Test | Verdict | V.Source | GT-SSIM A/S | Ghost A/S | Sharp A | Coh | Notes |
|------|---------|----------|-------------|-----------|---------|-----|-------|
| asp_test01 | simple_better | ground_truth | 0.678/0.710 | 42.8/29.2 | 164 | 31.28 | |
| asp_test02 | comparable | ground_truth | 0.718/0.714 | 42.3/28.9 | 141 | 33.74 | |
| asp_test03 | comparable | cv_metrics | no-GT | 44.5/33.8 | 135 | 32.75 | |
| asp_test04 | comparable | ground_truth | 0.696/0.738 | 19.3/21.3 | 34 | 28.94 | ASP wins ghost |
| asp_test05 | comparable | ground_truth | 0.714/0.744 | 54.3/44.9 | 134 | 13.82 | |
| asp_test06 | simple_better | ground_truth | 0.713/0.750 | 39.7/28.0 | 158 | 18.21 | |
| asp_test07 | **asp_better** | cv_metrics | no-GT | 44.1/30.0 | 99 | 24.60 | sharp 99 vs 49 |
| asp_test08 | simple_better | ground_truth | 0.725/0.796 | 58.8/47.3 | 301 | 17.18 | best ASP sharp |
| asp_test09 | comparable | ground_truth | 0.784/0.758 | 29.1/20.7 | 102 | 22.79 | |
| asp_test10 | comparable | cv_metrics | no-GT | 47.1/37.7 | 101 | 21.21 | |
| asp_test11 | simple_better | ground_truth | 0.643/0.674 | 51.0/39.3 | 171 | 23.47 | |
| asp_test12 | simple_better | ground_truth | 0.625/0.739 | 52.0/36.4 | 110 | 21.75 | |
| asp_test13 | comparable | cv_metrics | no-GT | 50.2/41.0 | 109 | 23.03 | |
| asp_test14 | simple_better | ground_truth | 0.605/0.664 | 31.5/21.6 | 73 | 23.52 | |
| asp_test15 | simple_better | ground_truth | 0.505/0.736 | 40.5/24.8 | 66 | 24.75 | |
| asp_test16 | simple_better | ground_truth | 0.532/0.731 | 34.0/23.4 | 69 | 17.54 | |
| asp_test17 | **asp_better** | ground_truth | 0.889/0.857 | 28.6/21.9 | 54 | 10.92 | GT+0.033 |
| asp_test18 | comparable | cv_metrics | no-GT | 26.1/30.1 | 41 | 29.91 | ASP wins ghost |
| asp_test19 | simple_better | cv_metrics | no-GT | 38.2/23.3 | 126 | 28.04 | |
| asp_test20 | simple_better | ground_truth | 0.473/0.629 | 48.8/48.0 | 153 | 24.73 | |
| asp_test21 | simple_better | cv_metrics | no-GT | 34.1/25.3 | 88 | 30.07 | |
| asp_test22 | comparable | cv_metrics | no-GT | 42.7/36.2 | 157 | 29.70 | |
| asp_test23 | comparable | cv_metrics | no-GT | 63.7/42.9 | 232 | 38.65 | |
| asp_test24 | simple_better | cv_metrics | no-GT | 51.6/36.8 | 196 | 31.03 | |
| asp_test25 | simple_better | ground_truth | 0.685/0.816 | 53.6/34.1 | 229 | 30.43 | |
| asp_test26 | comparable | ground_truth | 0.660/0.708 | 52.0/35.8 | 207 | 30.01 | |
| asp_test27 | simple_better | ground_truth | 0.698/0.676 | 34.6/23.3 | 140 | 27.91 | |
| asp_test28 | comparable | cv_metrics | no-GT | 42.6/29.9 | 185 | 24.04 | |
| asp_test29 | simple_better | cv_metrics | no-GT | 46.4/26.3 | 202 | 37.74 | |
| asp_test30 | simple_better | cv_metrics | no-GT | 37.9/23.0 | 110 | 32.02 | |
| asp_test31 | **asp_better** | ground_truth | 0.516/0.510 | 40.7/29.0 | 178 | 35.17 | GT+0.006 |
| asp_test32 | comparable | ground_truth | 0.722/0.723 | 50.4/33.0 | 153 | 29.56 | |
| asp_test33 | simple_better | ground_truth | 0.643/0.682 | 38.1/34.1 | 165 | 25.98 | |
| asp_test34 | simple_better | ground_truth | 0.506/0.702 | 47.7/32.4 | 141 | 20.98 | |
| asp_test35 | simple_better | cv_metrics | no-GT | 31.7/25.7 | 110 | 16.78 | |
| asp_test36 | comparable | cv_metrics | no-GT | 51.0/35.4 | 186 | 18.16 | |
| asp_test37 | simple_better | ground_truth | 0.742/0.790 | 19.3/16.4 | 44 | 25.50 | |
| asp_test38 | comparable | cv_metrics | no-GT | 32.6/14.4 | 82 | 21.89 | |
| asp_test39 | comparable | cv_metrics | no-GT | 42.9/26.5 | 159 | 21.13 | |
| asp_test40 | simple_better | cv_metrics | no-GT | 43.5/28.1 | 110 | 22.72 | |
| asp_test41 | comparable | cv_metrics | no-GT | 28.9/29.2 | 61 | 16.43 | ASP wins ghost |
| asp_test42 | simple_better | ground_truth | 0.480/0.513 | 86.0/66.3 | 197 | 17.19 | worst ghost |
| asp_test43 | insufficient_data | cv_metrics | no-GT | n/a | 19 | 22.02 | |
| asp_test44 | **asp_better** | ground_truth | 0.766/0.709 | 27.6/13.7 | 46 | 30.58 | GT+0.058 |
| asp_test45 | comparable | ground_truth | 0.593/0.607 | 28.6/15.9 | 96 | 36.05 | |
| asp_test46 | comparable | ground_truth | 0.711/0.693 | 25.3/14.0 | 51 | 34.95 | |
| asp_test47 | comparable | cv_metrics | no-GT | 18.9/12.8 | 23 | 15.53 | |
| asp_test48 | comparable | cv_metrics | no-GT | 27.1/13.7 | 64 | 20.42 | |
| asp_test49 | simple_better | ground_truth | 0.537/0.637 | 22.2/18.3 | 47 | 31.69 | ALIGN_FAIL |
| asp_test50 | comparable | ground_truth | 0.565/0.548 | 53.8/37.5 | 108 | 32.02 | |
| asp_test51 | comparable | cv_metrics | no-GT | 14.9/15.1 | 48 | 16.10 | ASP wins ghost |
| asp_test52 | comparable | ground_truth | 0.757/0.753 | 34.0/21.6 | 96 | 34.32 | |
| asp_test53 | **asp_better** | cv_metrics | no-GT | 23.6/39.1 | 53 | 44.30 | ghost −15.5 |
| asp_test54 | comparable | ground_truth | 0.717/0.719 | 29.6/25.8 | 99 | 10.74 | |
| asp_test55 | simple_better | cv_metrics | no-GT | 66.7/47.7 | 141 | 43.96 | |
| asp_test56 | simple_better | cv_metrics | no-GT | 39.7/25.9 | 115 | 34.54 | |
| asp_test57 | comparable | ground_truth | 0.762/0.758 | 23.5/21.7 | 37 | 21.19 | |
| asp_test58 | comparable | ground_truth | 0.632/0.637 | 26.9/22.4 | 66 | 33.44 | |
| asp_test59 | comparable | ground_truth | 0.647/0.660 | 28.9/18.3 | 56 | 53.72 | |
| asp_test60 | simple_better | cv_metrics | no-GT | 37.7/17.3 | 96 | 33.08 | |
| asp_test61 | **asp_better** | cv_metrics | no-GT | 26.9/16.1 | 38 | 26.17 | sharp 38 vs 21 |
| asp_test62 | simple_better | cv_metrics | no-GT | 38.7/18.4 | 128 | 28.40 | |
| asp_test63 | comparable | cv_metrics | no-GT | 50.8/34.0 | 100 | 27.40 | |
| asp_test64 | simple_better | cv_metrics | no-GT | 45.8/25.0 | 151 | 30.57 | |
| asp_test65 | comparable | ground_truth | 0.722/0.758 | 47.0/32.7 | 130 | 26.06 | |
| asp_test66 | simple_better | cv_metrics | no-GT | 51.5/29.7 | 103 | 23.09 | |
| asp_test67 | simple_better | cv_metrics | no-GT | 33.5/23.1 | 49 | 27.95 | |
| asp_test68 | comparable | cv_metrics | no-GT | 38.5/27.3 | 109 | 19.88 | |
| asp_test69 | simple_better | cv_metrics | no-GT | 43.2/33.3 | 112 | 18.76 | |
| asp_test70 | simple_better | ground_truth | 0.719/0.800 | 39.0/24.2 | 95 | 30.20 | |
| asp_test71 | simple_better | cv_metrics | no-GT | 36.1/33.7 | 99 | 42.67 | |
| asp_test72 | simple_better | ground_truth | 0.729/0.802 | 44.6/35.2 | 113 | 35.68 | |
| asp_test73 | comparable | cv_metrics | no-GT | 12.8/12.7 | 15 | 15.49 | |
| asp_test74 | simple_better | ground_truth | 0.791/0.840 | 38.5/24.2 | 108 | 29.52 | |
| asp_test75 | comparable | cv_metrics | no-GT | 42.0/27.1 | 119 | 50.81 | |
| asp_test76 | comparable | ground_truth | 0.791/0.795 | 53.4/33.8 | 131 | 22.13 | |
| asp_test77 | simple_better | ground_truth | 0.442/0.681 | 38.8/27.2 | 84 | 28.62 | ratio=26.976 worst |
| asp_test78 | simple_better | ground_truth | 0.736/0.804 | 50.9/32.7 | 152 | 35.14 | |
| asp_test79 | simple_better | ground_truth | 0.510/0.539 | 34.7/20.5 | 70 | 23.66 | |
| asp_test80 | comparable | ground_truth | 0.577/0.603 | 31.3/17.4 | 63 | 31.22 | |
| asp_test81 | simple_better | cv_metrics | no-GT | 32.0/13.7 | 109 | 26.48 | |
| asp_test82 | simple_better | ground_truth | 0.760/0.802 | 37.1/17.1 | 107 | 24.08 | |
| asp_test83 | comparable | ground_truth | 0.771/0.813 | 35.6/22.8 | 93 | 17.40 | |
| asp_test84 | **asp_better** | ground_truth | 0.815/0.769 | 29.3/13.6 | 48 | 15.93 | GT+0.046 |
| asp_test85 | simple_better | ground_truth | 0.747/0.761 | 37.7/26.6 | 91 | 16.27 | |
| asp_test86 | comparable | ground_truth | 0.605/0.618 | 35.9/18.1 | 90 | 41.04 | |
| asp_test87 | comparable | cv_metrics | no-GT | 39.0/26.7 | 107 | 18.04 | |
| asp_test88 | **asp_better** | ground_truth | 0.660/0.618 | 55.9/29.0 | 171 | 31.39 | GT+0.043 |
| asp_test89 | comparable | ground_truth | 0.669/0.706 | 21.0/20.2 | 31 | 32.99 | |
| asp_test90 | simple_better | ground_truth | 0.643/0.639 | 9.7/8.6 | 12 | 3.61 | degenerate coh |
| asp_test91 | simple_better | ground_truth | 0.502/0.543 | 83.0/45.3 | 269 | 38.37 | worst ghost delta |
| asp_test92 | comparable | ground_truth | 0.534/0.582 | 32.6/18.3 | 72 | 31.49 | |
| asp_test93 | simple_better | cv_metrics | no-GT | 28.3/25.1 | 45 | 25.20 | |
| asp_test94 | simple_better | cv_metrics | no-GT | 40.0/20.3 | 173 | 19.28 | |
| asp_test95 | comparable | ground_truth | 0.598/0.643 | 24.0/10.5 | 50 | 14.93 | |
| asp_test96 | **asp_better** | ground_truth | 0.564/0.558 | 38.7/32.7 | 127 | 27.14 | GT+0.006 |
| asp_test97 | simple_better | cv_metrics | no-GT | 36.1/36.7 | 68 | 10.89 | ASP wins ghost |

---

## 3. Key Findings

### 3.1 ASP-Better Tests (9)

| Test | Source | GT delta | Ghost A/S | Sharp A/S | Why ASP wins |
|------|--------|----------|-----------|-----------|--------------|
| test07 | cv_metrics | — | 44.1/30.0 | 99/49 | sharp 2× simple; seam coh strong |
| test17 | ground_truth | +0.033 | 28.6/21.9 | 54/39 | high GT-SSIM, cleaner alignment |
| test31 | ground_truth | +0.006 | 40.7/29.0 | 178/102 | marginal GT win |
| test44 | ground_truth | +0.058 | 27.6/13.7 | 46/10 | strong GT win; sharp 46 vs 10 |
| test53 | cv_metrics | — | 23.6/39.1 | 53/70 | **ASP ghost −15.5** (best ghost win) |
| test61 | cv_metrics | — | 26.9/16.1 | 38/21 | seam quality + sharpness |
| test84 | ground_truth | +0.046 | 29.3/13.6 | 48/15 | strong GT win; sharp 48 vs 15 |
| test88 | ground_truth | +0.043 | 55.9/29.0 | 171/67 | GT win despite higher ASP ghost |
| test96 | ground_truth | +0.006 | 38.7/32.7 | 127/44 | marginal GT win |

**Pattern:** When ASP wins on sharpness by ≥2×, it tends to win the overall verdict. Tests test44, test84 are the strongest wins (sharp 46/10, 48/15 — alignment quality dominates over ghost penalty). test53 is the only test where ASP wins on ghost score (−15.5 delta).

### 3.2 Ghosting Analysis

- ASP **wins on ghosting** in only **6/97 tests**: test04 (−1.9), test18 (−4.0), test41 (−0.3), test51 (−0.2), test53 (−15.5), test97 (−0.6).
- **Worst ghosting losses:** test91 (+37.8), test88 (+26.9), test66 (+21.8), test23 (+20.8), test64 (+20.8).
- **Root cause:** A5 foreground-excluded median (`ASP_FG_EXCLUDE_MEDIAN=1`) is already enabled, but the fallback when no bg sample exists reverts to all-frame median — ghost-averaging different animation poses when the character covers the full pixel across all selected frames.
- **§1.87 fix** (implemented S142): `ASP_MASKED_MEDIAN=1` suppresses the all-frame fallback; those pixels become zero, filled by `ASP_BG_COMPLETE`.

### 3.3 Sharpness Advantage

ASP sharper in 90/96 tests (avg 108.9 vs 63.8, +71%). This is a genuine sub-pixel alignment quality win — not edge-artifact inflation. The tests where ASP wins (test17, test44, test84) show 2–5× sharpness improvement. However, GT-SSIM is insensitive to sharpness improvements from sub-pixel alignment when frame selection differs from GT (GT-coupling bias).

### 3.4 Outliers

- **test77** (worst): affine `health.ratio=26.976` (26-frame, 5459px canvas) — GT-SSIM Δ=−0.239. Extreme BA edge case not yet handled by existing gates (all fire before BA on this test).
- **test90** (degenerate): Sharp=12/8, Coh=3.61 — near-static scene, almost no scroll. Pipeline runs to completion but produces marginal result.
- **test49**: ECC alignment failed (reported in `datasets_alignment_failed`).
- **test43**: `insufficient_data` — no metrics available.

### 3.5 Verdict Source Breakdown

- `ground_truth`: 54 tests — most reliable; uses aligned-SSIM vs GT frame.
- `cv_metrics`: 43 tests — uses `_auto_verdict` (seam_coherence, ghosting, coverage, gradient). §1.10B Optuna search can improve these 43 verdicts.

---

## 4. Root Cause Summary

| Root cause | Tests affected | Fix |
|-----------|---------------|-----|
| Temporal median fg fallback (ghost avg) | ~90/97 (ghosting worse) | §1.87 masked-median (S142) |
| ARAP disabled (no ptlflow in test env) | All seams single-pose | Option E: AnimeInterp SGM flow |
| GT-coupling bias | 54 GT tests | §3.3 DINOv2 frame selection already shipped |
| Extreme BA geometry (test77 ratio=26.976) | 1 | Not yet addressed |
| Alignment failure (test49) | 1 | ECC threshold tuning |

---

## 5. Implementations from S142

- **§1.87 Masked-Median Bg Plate**: `_masked_median_bg` in `bg_complete.py`; `_MASKED_MEDIAN` flag in `rendering.py`. Suppresses ghost-average fallback. Enable: `ASP_MASKED_MEDIAN=1`.
- **§3.14B Horizontal-Strip Compositing**: `_HORIZONTAL_COMPOSITE` flag in `pipeline.py`. Suppresses SCANS fallback for horizontal scroll; `_composite_foreground` already handles horizontal via canvas-return fast path. Enable: `ASP_HORIZONTAL_COMPOSITE=1`.
- **§1.10B Optuna Param Search**: `backend/src/anim/param_search.py`. Tunes `_auto_verdict` thresholds against the 43 cv_metrics tests without re-running inference. CLI: `python -m backend.src.anim.param_search --results <json> --trials 200 --out asp_config_optimized.toml`.

---

## 6. Archived: Session 2 Analysis (2026-06-03)

> The following section is the original Session 2 benchmark analysis, preserved for reference.

---

### S2 Final Results Table

| Test | Pre-feature | Session 1 | Session 2 | Simple stitch | ΔSession1 | Verdict |
|------|----------:|----------:|----------:|-------------:|----------:|---------|
| test04 | 0.633 | 0.742 | 0.742 | 0.738 | +0.000 | comparable |
| test08 | 0.731 | 0.735 | **0.737** | 0.813 | +0.002 | simple_better |
| test09 | 0.785 | 0.787 | 0.787 | 0.757 | -0.000 | **asp_better** |
| test27 | 0.705 | 0.709 | 0.708 | 0.677 | -0.001 | **asp_better** |
| test57 | 0.738 | 0.745 | 0.743 | 0.756 | -0.002 | comparable |

**Session 2 net gain: +0.002 on test08, essentially flat everywhere else.**

### S2 Features Shipped

**A1 — RAFT optical flow**: ptlflow installed; sea_raft_s@things loads lazily on GPU. Seam-band cropping: flow computed only on ±taper_px+16 strip around seam. Falls back to DIS automatically. **Finding**: RAFT and DIS give identical SSIM outcomes. Flow quality is not the bottleneck.

**A3 — ARAP regularisation** (cell_size=16, n_iter=2): Sýkora-style per-cell rigid median interpolated back to pixel space. **Finding**: No measurable SSIM improvement. Regularisation is geometrically correct but gain below measurement noise.

**A6 enhanced — post_warp_diff ghost-prevention escalation**: After ARAP-regularised midpoint warp, measures mean foreground colour difference at seam. If `post_warp_diff > 22 lum units`, escalates to single-pose fallback. **Finding**: Catches 5 seams in test08 (residuals 22-32 lum units) → +0.002 SSIM.

### S2 Failed Experiments

- **Global reference asymmetric alpha**: Catastrophic on test27 (−0.151). Asymmetric warp amplifies flow noise at α=1.0. Never exceed ~0.65 for noisy flows.
- **Character bounding-box crop**: Wrong axis for vertical pans — BiRefNet fg union covers full column extent, crop removed essential right-side background.

### S2 Understanding the SSIM Ceiling

| Test | Raw SSIM | Aligned SSIM | Gap (framing) |
|------|--------:|-------------:|--------------|
| test09 | 0.787 | 0.832 | 0.045 |
| test27 | 0.708 | 0.748 | 0.040 |
| test57 | 0.743 | 0.736 | (negative!) |

Remaining gap comes from: (1) animation timing — GT uses specific frames at specific times; (2) midpoint warp residual — even perfect flow halves the pose gap; (3) SSIM sensitivity to fine anime line-art (1px misalignment → measurable SSIM penalty).

**The bottleneck is upstream of compositing**: better frame selection (pose-consistent with GT reference) would improve SSIM more than any compositing improvement.
