# ASP Forensic Investigation After Human Rating Pass 1

**Author:** Chat/Codex  
**Date:** 2026-08-10  
**Scope:** `asp_test01`–`asp_test18` in `submodules/ASP/data/benchmarks/asp_evaluations_20260810.json`  
**Status:** Initial forensic report; no ASP behavior changed

## Executive finding

The first 18 human ratings show a material quality gap, not merely a metric
calibration problem. ASP averages **2.00/4**, while SCANS/Simple averages
**3.39/4**. SCANS is preferred in **14/18** cases; the remaining four are ties;
ASP is preferred in none. The dominant ASP defect tags are seam lines (11),
color shifts (10), banding (9), ghosting (8), crop loss (7), torn anatomy (7),
misordered content (6), duplicated strips (6), blur (5), and geometry warp (4).

This is consistent with the visual notes: ASP sometimes produces catastrophic
structural failures while SCANS produces a usable image with mild ghosting. The
pipeline should not be tuned against average SSIM or sharpness alone until the
structural failures are understood.

## Evidence reviewed

- Human evaluation JSON through test 18, including scores, preferences,
  confidence, defect tags, and notes.
- ASP benchmark output schema and the available 2026-08-07 run artifacts.
- Pipeline stages in `backend/src/core/pipeline/run_stage.py`.
- Frame selection in `backend/src/ingestion/frame_selection/`.
- Photometric normalization in `_photometric_stage.py` and `rendering/photometric.py`.
- Foreground compositing and seam routing in
  `rendering/compositing/{composite.py,_seam_cost.py,_gain_compensation.py}`.
- ASP roadmap, especially the stated frame-selection, photometric, seam, and
  fallback assumptions.

The rating file is dated 2026-08-10, while the checked-in raw benchmark runs
are dated 2026-08-07. Before quantitative correlation, the dashboard and
investigators must record the exact run/configuration that produced each rated
image; otherwise a rating can be accidentally compared with the wrong artifact.

The available 97-test run provides useful corroborating diagnostics for the
worst rated IDs, but should be treated as a linkage hypothesis until the exact
run is confirmed. For tests 6/7/12/14/15 it reports final selected-frame counts
of 10/18/12/33/27 from original counts of 211/182/81/261, dy-step CV values of
0.248/0.450/0.396/0.741/0.613, and gain ranges reaching 0.80–1.25. The ASP
seam-visibility values are 29.58/18.73/23.06/12.59/12.55 versus SCANS
2.71/5.71/3.18/2.01/3.07. In particular, test 7 is an important metric
failure: the automated run says `asp_better`, while the human note describes
both outputs as unacceptable and the human preference is not ASP. This is
direct evidence that current automated verdicts cannot be used as a release
gate for structural quality.

## Symptom-to-source hypotheses

### 1. Wrong frame selection or phase mixing — highest priority

Test 14 is especially diagnostic: ACFHarbinger reports that manual frame
selection produced a result close to ground truth, while the automatic ASP
selection produced a severely defective output. Tests 6, 7, 12, 14, and 15
also show duplicated strips, misordering, torn anatomy, and geometry warps.

The selector currently combines hold detection, phase correlation, quality
filters, and an optional DINOv2 pose window. Important safeguards are disabled
by default: `ASP_POSE_WINDOW_PX` is `0`, phase-aware selection is off, and blur,
contrast, temporal-variance, and near-duplicate filters default to off in the
low-level modules. The selected sequence can therefore contain visually
incompatible poses even when camera displacement is plausible.

**Investigation:** persist selected frame filenames, hold IDs, phase IDs,
displacements, phase-correlation responses, and rejection reasons in every
benchmark dataset. Compare automatic selection against the manually selected
sequence on tests 6, 7, 12, 14, and 15 before changing any renderer.

### 2. Multiple photometric corrections may compound color errors — high priority

The active path applies BaSiC spatial correction, background-reference
normalization, per-segment k-means color correction, renderer histogram
normalization, and optional pre-seam gain compensation. The code explicitly
uses per-channel BGR gains in `_apply_background_photometric_normalization` and
then applies additional spatial or global gain logic in compositing.

That is a plausible explanation for the repeated color shifts and horizontal
banding: the system may be correcting different regions against incompatible
references, and a per-channel correction can change hue rather than only
exposure. The per-segment stage also matches independently quantized clusters
to reference clusters by nearest color, which is not a stable semantic
correspondence for animated frames.

**Investigation:** run a strict ablation matrix on the same five representative
tests: raw frames; BaSiC only; background normalization only; renderer
normalization only; compositing gain only; and the current full stack. Save
per-frame/channel gains, background pixel counts, cluster assignments, and
before/after seam crops. Human-rate the outputs, with color-shift and banding
tags separated.

### 3. Alignment accepts bad correspondences before compositing — high priority

Torn anatomy and geometry warp indicate that the affine/translation solution is
sometimes geometrically plausible globally but wrong on foreground content.
The current pipeline uses dense matching, bundle adjustment, ECC refinement,
midplane translation, and then foreground pose registration. A robust loss or
edge confidence is not a guarantee that the retained transform preserves
character structure. A bad frame pair can poison every downstream seam.

**Investigation:** export every adjacent and skip edge with matcher type,
inlier count, residual distribution, affine matrix, ECC correlation, and
foreground/background match ratios. Re-render with each suspicious edge
removed and with translation-only versus affine motion. A single-edge removal
that repairs a catastrophic case would identify the failure class quickly.

### 4. Temporal median and foreground paste can mix incompatible poses — high priority

The default renderer is `median`, followed by a separate foreground-only
Laplacian composite. This is valuable for deghosting when frames depict the
same pose, but it can create duplicated body parts or torn anatomy when the
selected frames cross animation phases. `ASP_PHASE_COMPOSITE` is documented as
off by default, so phase-aware compositing is not currently a safety boundary.

**Investigation:** on tests 7, 12, 14, and 15 compare `renderer=first`,
`renderer=blend`, `renderer=median`, and median with foreground compositing
disabled. Preserve each intermediate canvas and foreground layer. If disabling
foreground compositing repairs structure while retaining background quality,
the fix belongs in pose registration/compositing rather than matching.

### 5. Seam routing and gain equalization turn moderate errors into visible seams

The composite performs warped-frame normalization, boundary/feather
optimization, pose registration, optional global gain equalization, seam-path
selection, and Laplacian blending. The seam cost is strongly mask-driven and
can route through the least-bad corridor even when every corridor crosses a
foreground or exposure discontinuity. A visually obvious seam can therefore be
the final presentation of an upstream alignment or color error, not an isolated
seam-cut bug.

**Investigation:** record seam paths overlaid on both warped inputs, seam
photometric residuals, feather width, gain maps, and post-warp difference.
Compare DP seam versus graph-cut only after the upstream frame/pose inputs are
held constant. Do not tune seam weights using a final image alone.

## Strong candidate experiments

Run one change at a time on tests 6, 7, 12, 14, and 15, then use the full 18
test rated subset for confirmation:

1. Manual frame list versus automatic selection.
2. `ASP_POSE_WINDOW_PX=80` and phase-aware selection, separately and together.
3. Current photometric stack versus each correction ablation.
4. Translation-only versus affine motion model.
5. `renderer=first`, `blend`, and `median` with/without foreground composite.
6. Global gain compensation off, then joint gain solve on, with identical seams.
7. Strict bad-edge rejection/fallback versus current permissive thresholds.
8. SCANS fallback whenever structural diagnostics exceed a calibrated threshold.

Each experiment must save the exact environment, git commit, selected frames,
intermediate artifacts, automated metrics, human scores, and a short verdict.

## Possible solution directions

### Short term: make catastrophic output impossible

- Strengthen pre-render structural gates using match residuals, foreground
  overlap consistency, pose displacement, seam luminance jumps, and crop loss.
- Prefer a guarded SCANS fallback over shipping a warped/torn ASP composite.
- Require phase-consistent frame groups and disable foreground paste when pose
  consistency is not demonstrated.
- Replace broad quality thresholds with per-test diagnostics that explain why a
  fallback occurred.

### Medium term: repair the pipeline in causal order

- Rebuild selection around camera-motion plus foreground-pose compatibility,
  not camera phase correlation alone.
- Make photometric correction a single explicit model with one reference and
  bounded, auditable gains; avoid stacking independent color transforms.
- Use robust local alignment and edge rejection before bundle adjustment, with
  foreground-aware validation of every transform.
- Treat seam routing as a constrained optimization over measured residuals and
  masks, then validate the seam against human-visible artifacts.

### Strategic option: simplify or reimplement

If ablations show that the current architecture compounds errors, a smaller
translation-only pipeline with strong SCANS-compatible blending may outperform
the current multi-stage system. A rewrite should be considered only after the
ablation evidence identifies which stages are net-negative; replacing Python
with C++ alone will not fix wrong frame selection, invalid transforms, or
misleading quality gates.

## What not to conclude yet

- The result is not evidence that all learned matchers are bad; their actual
  edge-level behavior has not been correlated with the rated tests.
- A better automated sharpness or SSIM score is not a quality win if the human
  sees banding, color shifts, or torn anatomy.
- Hugin's occasional success and occasional stretch failure suggest useful
  comparator behavior, not an immediate replacement decision.
- More UI polish, additional model dependencies, or a 3D visualization cannot
  compensate for the current algorithmic quality gap.

## Recommended next deliverable

Produce a five-test forensic packet for tests 6, 7, 12, 14, and 15 containing:
selected-frame contact sheets, edge graphs, transform residuals, gain maps,
seam overlays, all stage images, and the human comparison. That packet should
precede any default-flag change and should become the basis for the next ASP
roadmap decision.
