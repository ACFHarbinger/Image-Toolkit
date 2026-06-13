# Anime Stitch Pipeline — Issue Tracker & Per-Test Results

> **⚠️ ARCHIVED BASELINE (2026-06-01)**: This document reflects the pipeline state before Sessions 6–28. The figures below (39 render-gate fallbacks, 13 affine-validation fallbacks, 44 true ASP composites) are the S0–S5 pre-improvement baseline. After S11, SCANS fallbacks were reduced from 51/96 → 4/96 genuine fallbacks. **Current pipeline state (Session 80, 498 tests, 97-test corpus) is in `.agent/cache/asp_state_of_the_pipeline.md` (§1–§4) and the Phase 2 Next-Generation architecture (Issue 9 video ingestion, Issue 10 multi-modal HITL) is documented in `reports/ASP_High_Value_Issues_Report.md` Issues 9 & 10.** This document is retained for historical comparison only.

**Last updated:** 2026-06-01 19:13 (96-dataset benchmark with ground truth comparison)  
**Benchmark file:** `backend/benchmark/results/anime_stitch_20260601_191331.json`  
**Relevant codebase:** `backend/src/anim/`  
**Ground truth:** 55/96 tests — `data/ground_truth/asp_testXX.{png,jpg,jpeg}`

---

## 1. Overall Summary

| Metric | Value |
|--------|-------|
| Total datasets | 96 |
| True ASP composites | **44** (45.8%) |
| SCANS fallback — render gate | **39** (40.6%) |
| SCANS fallback — affine validation | **13** (13.5%) |
| GT verdict: asp_better | **8 / 55** (14.5%) |
| GT verdict: simple_better | **23 / 55** (41.8%) |
| GT verdict: comparable | **24 / 55** (43.6%) |
| Avg SSIM ASP vs GT | **0.669** |
| Avg SSIM simple vs GT | **0.695** |
| Avg render time (true ASP) | 30.0s |
| Avg seam_coherence ASP | 26.0 |

**The simple stitch produces output closer to ground truth in 42% of tested cases; ASP wins in only 15%.** The primary root cause is the pipeline assuming static scrolling artwork while the corpus is animated video where characters move every frame.

---

## 2. Per-Test Full Results Table

Columns: FB = fallback type (N=none, RG=render gate, AV=affine validation); Fr = frames after smart selection; SC_A/SC_S = seam coherence ASP/simple (lower=better); Seam∇ = seam gradient (lower=better); GTA/GTS = GT SSIM ASP/simple; GT_V = GT-based verdict; Health = affine validation reason.

| Test | FB | Fr | SC_A | SC_S | Seam∇ | GTA | GTS | GT_V | Health |
|------|----|----|-----:|-----:|------:|----:|----:|------|--------|
| test01 | RG | 16 | 23.9 | 25.6 | 6.94 | 0.689 | 0.710 | **simple_better** | ok |
| test02 | RG | 21 | 28.1 | 25.9 | 7.23 | 0.733 | 0.730 | comparable | ok |
| test03 | RG | 5 | 35.3 | 32.2 | 5.10 | — | — | — | ok |
| test04 | RG | 23 | 29.1 | 29.1 | 4.93 | 0.633 | 0.739 | **simple_better** | ok |
| test05 | N | 16 | 13.9 | 20.3 | 12.99 | 0.734 | 0.744 | comparable | ok |
| test06 | N | 10 | 18.7 | 17.8 | 10.89 | 0.714 | 0.731 | comparable | ok |
| test07 | N | 11 | 31.9 | 29.9 | 10.15 | — | — | — | ok |
| test08 | N | 14 | 16.9 | 11.9 | 7.69 | 0.731 | 0.778 | **simple_better** | ok |
| test09 | N | 21 | 22.9 | 17.2 | 6.09 | **0.785** | 0.762 | **asp_better** | ok |
| test10 | N | 8 | 21.4 | 29.9 | 4.23 | — | — | — | ok |
| test11 | N | 11 | 23.6 | 12.0 | 9.99 | **0.654** | 0.603 | **asp_better** | ok |
| test12 | N | 13 | 20.2 | 25.6 | 5.68 | 0.617 | 0.801 | **simple_better** | ok |
| test13 | AV | 14 | 23.9 | 33.5 | 2.98 | — | — | — | ratio=11.1>3.0 |
| test14 | AV | 16 | 10.8 | 13.7 | 6.70 | 0.622 | 0.654 | **simple_better** | min_gap=16.7px |
| test15 | N | 27 | 25.2 | 16.3 | 9.41 | 0.518 | 0.738 | **simple_better** | ok |
| test16 | N | 15 | 18.2 | 35.7 | 5.89 | 0.549 | 0.733 | **simple_better** | ok |
| test17 | N | 19 | 10.9 | 8.2 | 6.07 | **0.889** | 0.855 | **asp_better** | ok |
| test18 | N | 19 | 30.0 | 29.5 | 1.55 | — | — | — | ok |
| test19 | N | 17 | 28.3 | 26.9 | 8.91 | — | — | — | ok |
| test20 | N | 14 | 24.2 | 16.3 | 8.73 | 0.474 | 0.617 | **simple_better** | ok |
| test21 | RG | 18 | 25.5 | 24.6 | 5.82 | — | — | — | ok |
| test22 | RG | 13 | 29.2 | 29.3 | 8.24 | — | — | — | ok |
| test23 | RG | 15 | 45.1 | 55.5 | 9.45 | — | — | — | ok |
| test24 | N | 9 | 27.6 | 29.1 | 5.07 | — | — | — | ok |
| test25 | RG | 10 | 32.2 | 32.5 | 5.66 | **0.732** | 0.695 | **asp_better** | ok |
| test26 | N | 11 | 29.6 | 29.7 | 11.43 | 0.661 | 0.707 | **simple_better** | ok |
| test27 | N | 20 | 28.5 | 24.8 | 7.00 | **0.705** | 0.679 | **asp_better** | ok |
| test28 | N | 21 | 24.6 | 37.0 | 9.89 | — | — | — | ok |
| test29 | RG | 24 | 35.4 | 36.0 | 9.80 | — | — | — | ok |
| test30 | AV | 12 | 30.8 | 31.3 | 7.38 | — | — | — | min_gap=21.0px |
| test31 | RG | 22 | 40.1 | 41.1 | 7.96 | 0.514 | 0.509 | comparable | ok |
| test32 | RG | 11 | 33.2 | 32.8 | 8.12 | 0.733 | 0.728 | comparable | ok |
| test33 | RG | 12 | 21.7 | 21.3 | 7.91 | 0.675 | 0.681 | comparable | ok |
| test34 | RG | 17 | 30.4 | 32.2 | 7.14 | 0.718 | 0.714 | comparable | ok |
| test35 | RG | 6 | 9.0 | 9.7 | 5.00 | — | — | — | ok |
| test36 | N | 18 | 17.4 | 20.9 | 11.35 | — | — | — | ok |
| test37 | RG | 26 | 35.0 | 35.0 | 4.91 | 0.793 | 0.791 | comparable | ok |
| test38 | N | 14 | 21.6 | 17.8 | 7.54 | — | — | — | ok |
| test39 | N | 14 | 20.7 | 23.5 | 9.94 | — | — | — | ok |
| test40 | RG | 18 | 11.9 | 12.6 | 5.58 | — | — | — | ok |
| test41 | RG | 10 | 16.5 | 19.2 | 5.96 | — | — | — | ok |
| test42 | N | 19 | 16.7 | 17.4 | 13.50 | 0.479 | 0.512 | **simple_better** | ok |
| test43 | RG | 23 | 22.5 | 21.6 | 2.96 | 0.706 | 0.691 | comparable | ok |
| test44 | RG | 7 | 20.6 | 20.1 | 3.79 | 0.708 | 0.710 | comparable | ok |
| test45 | N | 16 | 39.5 | 40.8 | 6.93 | 0.597 | 0.620 | **simple_better** | ok |
| test46 | N | 14 | 39.4 | 32.8 | 3.25 | 0.681 | 0.696 | comparable | ok |
| test47 | N | 10 | 14.2 | 20.3 | 5.18 | — | — | — | ok |
| test48 | AV | 9 | 30.1 | 31.9 | 1.80 | — | — | — | min_gap=6.8px |
| test49 | AV | 21 | 31.8 | 26.8 | 4.61 | 0.538 | 0.639 | **simple_better** | min_gap=23.3px |
| test50 | N | 11 | 32.4 | 24.3 | 8.84 | **0.570** | 0.550 | **asp_better** | ok |
| test51 | RG | 9 | 16.3 | 11.2 | 2.87 | — | — | — | ok |
| test52 | RG | 4 | 31.1 | 31.1 | 4.19 | 0.752 | 0.752 | comparable | ok |
| test53 | RG | 11 | 44.4 | 44.3 | 2.56 | — | — | — | ok |
| test54 | AV | 13 | 12.0 | 10.4 | 5.08 | 0.726 | 0.722 | comparable | ratio=3.5>3.0 |
| test55 | N | 18 | 44.9 | 30.2 | 11.76 | — | — | — | ok |
| test56 | RG | 17 | 36.1 | 38.1 | 6.32 | — | — | — | ok |
| test57 | N | 26 | 25.0 | 21.7 | 8.31 | 0.738 | 0.756 | comparable | ok |
| test58 | RG | 27 | 35.6 | 41.2 | 4.02 | 0.631 | 0.646 | comparable | ok |
| test59 | RG | 8 | 16.6 | 16.7 | 3.80 | 0.521 | 0.518 | comparable | ok |
| test60 | RG | 16 | 22.8 | 32.3 | 5.12 | — | — | — | ok |
| test61 | RG | 19 | 17.2 | 29.9 | 4.75 | — | — | — | ok |
| test62 | N | 14 | 28.2 | 18.5 | 7.26 | — | — | — | ok |
| test63 | RG | 10 | 33.2 | 33.2 | 8.10 | — | — | — | ok |
| test64 | AV | 25 | 25.6 | 27.7 | 2.80 | — | — | — | ratio=4.2>3.0 |
| test65 | RG | 18 | 27.5 | 27.5 | 9.43 | 0.757 | 0.758 | comparable | ok |
| test66 | AV | 14 | 20.2 | 18.0 | 0.21 | — | — | — | ratio=3.1>3.0 |
| test67 | N | 16 | 28.5 | 21.2 | 9.18 | — | — | — | ok |
| test68 | RG | 9 | 25.2 | 21.5 | 8.76 | — | — | — | ok |
| test69 | RG | 9 | 17.1 | 15.6 | 9.50 | — | — | — | ok |
| test70 | AV | 23 | 12.6 | 22.0 | 2.33 | 0.685 | 0.769 | **simple_better** | ratio=4.1>3.0 |
| test71 | RG | 9 | 27.6 | 27.4 | 7.03 | — | — | — | ok |
| test72 | RG | 16 | 27.5 | 26.0 | 13.72 | 0.780 | 0.801 | comparable | ok |
| test73 | AV | 14 | 15.2 | 15.4 | 4.59 | — | — | — | ratio=3.8>3.0 |
| test74 | RG | 23 | 32.4 | 32.1 | 6.08 | 0.843 | 0.840 | comparable | ok |
| test75 | RG | 15 | 61.3 | 61.5 | 9.41 | — | — | — | ok |
| test76 | N | 12 | 24.8 | 18.4 | 11.30 | 0.792 | 0.785 | comparable | ok |
| test77 | AV | 26 | 31.4 | 25.6 | 8.09 | 0.627 | 0.682 | **simple_better** | min_gap=18.8px |
| test78 | AV | 23 | 26.2 | 23.2 | 6.78 | 0.799 | 0.805 | comparable | min_gap=5.0px |
| test79 | N | 30 | 24.4 | 28.2 | 9.76 | 0.513 | 0.538 | **simple_better** | ok |
| test80 | RG | 16 | 37.4 | 40.4 | 6.44 | **0.606** | 0.559 | **asp_better** | ok |
| test81 | RG | 22 | 21.8 | 20.8 | 4.11 | — | — | — | ok |
| test82 | N | 23 | 23.7 | 15.2 | 8.15 | 0.751 | 0.777 | **simple_better** | ok |
| test83 | N | 11 | 17.1 | 16.4 | 8.65 | 0.769 | 0.840 | **simple_better** | ok |
| test84 | N | 11 | 16.9 | 21.3 | 5.92 | **0.816** | 0.769 | **asp_better** | ok |
| test85 | N | 21 | 16.3 | 10.7 | 8.78 | 0.741 | 0.761 | comparable | ok |
| test86 | RG | 29 | 38.9 | 39.9 | 5.97 | 0.625 | 0.616 | comparable | ok |
| test87 | N | 8 | 20.9 | 22.6 | 8.05 | — | — | — | ok |
| test88 | AV | 7 | 29.5 | 30.0 | 10.40 | 0.663 | 0.717 | **simple_better** | ratio=4.0>3.0 |
| test89 | AV | 22 | 32.7 | 28.5 | 4.06 | 0.704 | 0.735 | **simple_better** | ratio=4.0>3.0 |
| test90 | N | 16 | 28.2 | 9.2 | 10.18 | 0.607 | 0.639 | **simple_better** | ok |
| test91 | N | 17 | 35.0 | 26.1 | 12.89 | 0.504 | 0.542 | **simple_better** | ok |
| test92 | N | 23 | 30.5 | 26.9 | 9.16 | 0.532 | 0.582 | **simple_better** | ok |
| test93 | N | 15 | 23.7 | 26.5 | 10.93 | — | — | — | ok |
| test94 | N | 11 | 19.4 | 11.9 | 8.96 | — | — | — | ok |
| test95 | N | 17 | 15.0 | 13.2 | 7.95 | 0.603 | 0.650 | **simple_better** | ok |
| test96 | N | 35 | 27.4 | 30.5 | 8.41 | 0.557 | 0.559 | comparable | ok |

---

## 3. Failure Category Details

### Category A — Render Quality Gate (39 tests — 40.6%)

Triggered when the Stage 9 temporal median render shows seam_coherence > 35 OR inter-strip colour difference > 25 luminance units. These are tests where the frame selector chose frames from different animation states, producing a temporal collage rather than a spatial panorama. All fall back to SCANS before Stage 11 runs.

Affected: test01, test02, test03, test04, test21, test22, test23, test25, test29, test31, test32, test33, test34, test35, test37, test40, test41, test43, test44, test51, test52, test53, test56, test58, test59, test60, test61, test63, test65, test68, test69, test71, test72, test74, test75, test80, test81, test86, test88

Root cause: Phase correlation in the smart frame selector measures whole-frame displacement including character animation. The selector accepts frames where 45px of the 50px displacement is character movement, not camera pan.

### Category B — Affine Validation (13 tests — 13.5%)

**Ratio > 3.0 (7 tests):** test13 (11.1×), test54 (3.5×), test64 (4.2×), test66 (3.1×), test70 (4.1×), test73 (3.8×), test89 (4.0×)

Single catastrophically bad LoFTR match dominates the bundle solution. Current post-solve residual pruning handles most cases but fails when the bad edge's residual is within 3× of the median (corrupting the median itself). GNC robust loss would eliminate this failure mode.

**min_gap < 25px (6 tests):** test14 (16.7px), test30 (21.0px), test48 (6.8px), test49 (23.3px), test77 (18.8px), test78 (5.0px)

Near-duplicate frames survive smart selection and are placed within 25px of each other on the canvas. These would cause temporal median collapse. The 25px threshold correctly rejects them.

### Category C — True ASP Composite Failures (in 44 composites)

Among the 44 true ASP composites, 14 tests with GT are `simple_better`. Primary sub-causes:

**C1 — Seam through character bodies** (high seam_gradient): test42 (13.5), test05 (13.0), test55 (11.8), test36 (11.4), test91 (12.9). The DP seam path cuts through character regions despite the BiRefNet foreground cost term.

**C2 — Colour mismatch at strip boundaries despite passing gate**: test15, test16, test12, test45, test91. Seam_coherence is below the gate threshold (35) but inter-strip colour differences are still visible and reduce GT SSIM significantly.

**C3 — Diagonal / horizontal scroll unsupported**: test20 (coverage=0.88), test90 (seam∇=10.2). The vertical-dominant pipeline cannot correctly handle scenes with significant horizontal camera drift.

---

## 4. Files and Locations

| File | Purpose |
|------|---------|
| `backend/benchmark/bench_anime_stitch.py` | Full benchmark with GT comparison, selective runner, render quality gate |
| `backend/src/anim/validation.py` | Affine validation (min_gap=25px, vector magnitude gaps) |
| `backend/src/anim/compositing.py` | Stage 11 composite with inter-strip coherence guard |
| `backend/src/anim/rendering.py` | Stage 9 temporal median render |
| `backend/src/anim/pipeline.py` | Full 13-stage orchestrator |
| `backend/benchmark/results/anime_stitch_20260601_191331.json` | Latest 96-test benchmark results |
| `data/ground_truth/` | 55 reference panoramas for GT SSIM/PSNR evaluation |
| `data/output/` | All 192 final output PNGs (96 ASP + 96 simple) |
