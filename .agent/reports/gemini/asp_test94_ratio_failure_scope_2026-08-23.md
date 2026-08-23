# Investigation & Scope: `asp_test94` Affine Ratio Validation Failure

**Date:** 2026-08-23  
**Status:** Scoped / Analysis Only (No Algorithm Defaults Changed)  
**Author:** Agy / Antigravity  

---

## 1. Executive Summary & Root Cause

In the frozen 97-case telemetry corpus, `asp_test94` (one of the 11 human-reviewed known-good cases with `preference: "asp"`) fails before compositing with:
$$\text{fallback\_reason: } \texttt{affine\_invalid:ratio=3.12211 > 3}$$

### 1.1 What the `ratio` Metric Measures
In `submodules/ASP/backend/src/core/validation.py::_validate_affines`:
1. Frames are sorted along the primary scroll axis ($t_y$ or $t_x$).
2. Consecutive Euclidean frame-to-frame displacements $g_i = \sqrt{\Delta x_i^2 + \Delta y_i^2}$ are measured.
3. The metric calculates:
   $$\text{ratio} = \frac{\max(g_i)}{\max(\text{median}(g_i), 1.0)}$$
4. Hard threshold: If $\text{ratio} > \text{max\_ratio}$ (where default $\text{max\_ratio} = 3.0$), the health check fails hard.

### 1.2 Telemetry Analysis for `asp_test94`
- Total frames: $N=13$.
- Bundle adjustment and registration telemetry are exceptionally strong:
  - `raw_edges`: 33, `filtered_edges`: 21 (all observed correspondences, inlier ratios up to 59.4%).
  - `ba_residual_rms`: 70.79 px (passes the frozen $<80.0\text{ px}$ registration gate threshold).
  - `cycle_error_rms`: 210.08 px (passes the frozen $<300.0\text{ px}$ cycle threshold).
  - `seam_visibility`: 2.1 (excellent post-render seam quality).
  - `seam_coherence`: 9.49.
- Measured ratio: $\text{ratio} = 3.12211$ (only **4.07%** above the arbitrary 3.0 floor).
- Why did recovery fail?
  - `_recover_affine_health` attempted **Retry 0** (`_filter_high_conf_edges`), but the high-confidence LoFTR subset still solved to a ratio slightly above 3.0.
  - Retries 1–3 were either bypassed or did not reduce the ratio below 3.0.

---

## 2. Corpus-Wide Impact Analysis

Searching all 97 cases in `anime_stitch_latest_consolidated.json` reveals exactly **two** cases that fail on `affine_invalid:ratio`:
1. `asp_test94`: $\text{ratio} = 3.12211 > 3.0$
   - **Verdict:** True False-Positive. Clean, high-quality pan with non-uniform camera acceleration / frame decimation.
2. `asp_test49`: $\text{ratio} = 4.83229 > 3.0$
   - **Verdict:** True Positive / Severe failure (`ba_residual_rms` = 1187.47 px, non-observed synthetic grid edges, severe graph distortion).

---

## 3. Potential Remediation Options

### Option A: Defer Ratio Failures to `RegistrationRiskGate` (Analogous to `min_gap`)
- **Mechanism:** Extend `ASP_DEFER_MIN_GAP_TO_REGISTRATION_GATE` into `ASP_DEFER_AFFINE_SPACING_TO_GATE` (or a dedicated `ASP_DEFER_RATIO_TO_GATE`).
- **Safety Guarantee:** If `ratio > 3.0`, but BA RMS $<80.0$, Cycle RMS $<300.0$, and Raw Edges $>10$, route the case to `uncertain` for mandatory human review rather than an automatic low-risk pass.
- **Outcome:** Safely rescues `asp_test94` (BA RMS=70.79, Cycle RMS=210.08) while continuing to reject `asp_test49` (BA RMS=1187.47).

### Option B: Calibrated Dynamic Ratio Ceiling / Robust Ratio
- **Mechanism:** Replace hard $3.0\times$ with $\text{p95\_gap} / \text{median\_gap}$ or allow max ratio up to $3.5\times$ when inlier ratios exceed $0.35$ and BA residual is clean.
- **Outcome:** Directly accommodates non-linear acceleration pans without requiring gate deferral.

---

## 4. Next Steps
- Recommend **Option A** (deferring marginal ratio checks to `RegistrationRiskGate` under `uncertain` status) as it strictly preserves the Decision A uncertainty contract without risking silent regression on true catastrophes.
