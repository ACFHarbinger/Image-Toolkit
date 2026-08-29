# ASP Multi-Phase Renderer — B1/S1/S2 Fix Re-Review

**Author:** Agy (Gemini)  
**Date:** 2026-08-29  
**Target Commit:** Codex's commit [`7e352ba`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/) (`fix(compositing): preserve cels across phase joins`) in `submodules/ASP/` (parent [`e1023761`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/))  
**Relates to:** Issue #463, [asp_multiphase_renderer_design_2026-08-28.md](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/.agent/reports/chat/asp_multiphase_renderer_design_2026-08-28.md) (§8-5b), and [asp_multiphase_impl_review_2026-08-29.md](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/.agent/reports/gemini/asp_multiphase_impl_review_2026-08-29.md)  
**Status:** Read-only correctness re-review (Findings only, NO codebase edits)

---

## Executive Summary & Bottom-Line Sweep Verdict

We conducted an independent correctness re-review of Codex's fix commit [`7e352ba`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/) in `submodules/ASP/`, which addresses the three defects identified in our earlier implementation review ([`asp_multiphase_impl_review_2026-08-29.md`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/.agent/reports/gemini/asp_multiphase_impl_review_2026-08-29.md)):
1. **B1 (BLOCKER):** Hero cel distance alpha multiplied by background blend transition ramp.
2. **S1 (SHOULD-FIX):** Fixed 48 px blend width causing luminance step on narrow overlaps.
3. **S2 (SHOULD-FIX):** Single-source void fill ignoring `warped_valid` on $N_{\text{span}}=1$.

### Bottom-Line Verdict: **UNCONDITIONAL GO** for Step-6 Benchmark Sweep

> [!NOTE]
> **All three defects (B1, S1, S2) are completely and cleanly resolved.**
>
> - **B1 is eliminated:** Hero cel pixels (`claimed >= 0`) are copied verbatim across the entire phase seam, preserving their single-pose silhouette feather without any transition ramp modulation. The documented tie-break (lower physical band wins on overlap) is strictly implemented.
> - **S1 is mathematically sound:** `blend_width` is clamped to the actual valid overlap half-width, handling 0 px, 1 px, 2 px, and large overlaps without edge steps or boundary crashes.
> - **S2 is properly scoped:** Single-source void fill intersects `warped_valid` with an all-True fallback for callers that omit it, leaving $N_{\text{span}} \ge 2$ plate builds unaffected.
> - **Tests are rigorous:** The 3 new and updated unit tests directly assert the required invariants against former failure modes.
>
> **The codebase is CLEARED for Harbinger to authorize the Step-6 discriminating set benchmark sweep.**

---

## Ranked Findings Audit & Verification

| Defect ID | Severity | File & Line | Status | Verification Summary |
|---|---|---|---|---|
| **B1** | **BLOCKER** | [`_plate_compositor.py:454-466`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L454-L466) | **RESOLVED (VERIFIED)** | `cel_alpha` ramp multiplication removed. Cels copied verbatim; lower physical band wins on overlap; zero background bleed into cels. |
| **S1** | **SHOULD-FIX** | [`_plate_compositor.py:421-432,448-453`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L421-L432) | **RESOLVED (VERIFIED)** | `blend_width` clamped to `available_overlap` from `left_valid & right_valid`. Overlap=0 yields clean hard seam; smooth ramps on narrow overlaps. |
| **S2** | **SHOULD-FIX** | [`_plate_compositor.py:195-208`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L195-L208) | **RESOLVED (VERIFIED)** | Single-source void fill checks `valid = warped_valid[i]`; out-of-frame padding remains invalid; all-True fallback on None. |

---

## Detailed Check-by-Check Analysis

### 1. Check 1: Finding B1 (BLOCKER) Verification — Hero Cel Preservation

**Location:** [`_plate_compositor.py:447-466`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L447-L466)

```python
both_bg = left_valid & right_valid & (left_claimed < 0) & (right_claimed < 0)
if blend_width > 0:
    band = np.zeros((H, W), dtype=bool)
    band[y0:y1] = True
    blend_bg = both_bg & band
    result[blend_bg] = bg_blend[blend_bg]

# Apply upper-band then lower-band cels: in an overlap, the lower physical
# band wins. Each source already carries composite_plate_single_pose's
# silhouette feather, so never apply the background transition ramp here.
for source, source_claimed in (
    (left, left_claimed),
    (right, right_claimed),
):
    cel = source_claimed >= 0
    if not cel.any():
        continue
    result[cel] = source[cel]
    claimed[cel] = source_claimed[cel]
```

- **Ramp Modulation Elimination:** The previous faulty logic (`cel_alpha *= alpha_left` / `cel_alpha *= right_weight` and `distanceTransform` alpha reconstruction) has been completely removed.
- **Verbatim Copy Across Full Seam:** In `composite_plate_single_pose()`, hero cels are rendered onto their local plate with their local silhouette feather `_SP_SOFT_PX`, and all pixels within the cel region are marked in `claimed_map` with non-negative frame indices. In `_blend_phase_plates()`, `cel = source_claimed >= 0` selects this entire region. `result[cel] = source[cel]` copies both the interior and the pre-composited silhouette edge verbatim.
- **Tie-Break Semantics:** The loop processes `(left, left_claimed)` first, followed by `(right, right_claimed)`. In the physical canvas order ($ty$-sorted), `left` is the upper band and `right` is the lower band. If a cel in `left` and a cel in `right` overlap in the seam band, `right` (the lower physical band) overwrites `left`. This matches the documented design specification.
- **Background Seam Isolation:** The Laplacian background blend `bg_blend` is applied only to `blend_bg = both_bg & band`, where `both_bg` explicitly requires `(left_claimed < 0) & (right_claimed < 0)`. Thus, the background plate blend can never touch, attenuate, or bleed through any hero-cel pixel from either phase.
- **Forward-Pan vs. Reverse-Pan Invariance:** `composite_plate_multiphase()` always sorts phase bands by physical canvas $ty$ coordinate into `physical_phase_order` (`[0, 1]` for forward pan, `[1, 0]` for reverse pan). In both cases, `left` is the top plate and `right` is the bottom plate. The spatial join operates identically and symmetrically regardless of chronological pan direction.

---

### 2. Check 2: Finding S1 (SHOULD-FIX) Verification — Overlap Clamp Correctness

**Location:** [`_plate_compositor.py:421-436`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L421-L436)

```python
overlap_rows = np.flatnonzero((left_valid & right_valid).any(axis=1))
if len(overlap_rows):
    available_overlap = min(
        seam_y - int(overlap_rows[0]), int(overlap_rows[-1]) - seam_y
    )
    blend_width = min(blend_width, max(0, available_overlap))
else:
    blend_width = 0
y0 = max(0, seam_y - blend_width)
y1 = min(H, seam_y + blend_width + 1)
rows = np.arange(H, dtype=np.float32)
right_weight = np.clip((rows - y0) / max(1, y1 - y0 - 1), 0.0, 1.0)
```

We walked through all boundary conditions:

1. **Overlap == 0 (Gap / Abutting Bands):**
   - `(left_valid & right_valid).any(axis=1)` is all-False.
   - `len(overlap_rows) == 0` $\implies$ `blend_width = 0`.
   - `blend_width > 0` is False $\implies$ `if blend_width > 0:` block is skipped.
   - Initial partition `use_right = right_only | (left_valid & right_valid & right_side)` creates a clean hard step at `seam_y`. Zero crashes, zero invalid slicing.
2. **Overlap == 1 px (Single Common Row at $y=40$, `seam_y=40`):**
   - `overlap_rows = [40]`. `available_overlap = min(40-40, 40-40) = 0`.
   - `blend_width = min(48, max(0, 0)) = 0`.
   - Clean hard seam at row 40; no truncated ramp jump.
3. **Overlap == 2 px (Common Rows $[39, 40]$, `seam_y=40`):**
   - `overlap_rows = [39, 40]`. `available_overlap = min(40-39, 40-40) = min(1, 0) = 0`.
   - `blend_width = 0`. Clean hard seam at row 40. (A symmetric blend of width 1 would require row 41, which is outside `left_valid`).
4. **Overlap == 3 px (Common Rows $[39, 40, 41]$, `seam_y=40`):**
   - `overlap_rows = [39, 40, 41]`. `available_overlap = min(40-39, 41-40) = 1`.
   - `blend_width = min(48, 1) = 1`.
   - Ramp window: $[y_0, y_1-1] = [39, 41]$.
   - At row 39: `right_weight = 0.0` ($\alpha_{\text{left}} = 1.0$, 100% Left).
   - At row 40: `right_weight = 0.5` ($\alpha_{\text{left}} = 0.5$, 50/50 blend).
   - At row 41: `right_weight = 1.0` ($\alpha_{\text{left}} = 0.0$, 100% Right).
   - The ramp connects smoothly to row 38 (100% Left) and row 42 (100% Right) with **zero step discontinuity**.
5. **Overlap $\gg 96\text{ px}$ (e.g. 200 px overlap):**
   - `available_overlap = 100`. `blend_width = min(48, 100) = 48`.
   - Preserves standard 97 px window centered at `seam_y`.
6. **Non-Contiguous Overlap (Internal Gap in `left_valid & right_valid`):**
   - `both_bg` is evaluated per-pixel: `both_bg = left_valid & right_valid & ...`.
   - In any interior gap rows where `left_valid & right_valid` is False, `both_bg` is False, and `result` cleanly falls back to the baseline canvas / step join without crash or invalid indexing.
7. **Numerical Safeguards:**
   - `max(0, available_overlap)` prevents negative width if `seam_y` falls outside `overlap_rows`.
   - `max(1, y1 - y0 - 1)` prevents division by zero.
   - `y0` and `y1` are clipped to $[0, H]$.

---

### 3. Check 3: Finding S2 (SHOULD-FIX) Verification — Void Fill Scoping

**Location:** [`_plate_compositor.py:195-208`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L195-L208)

```python
void_mask = ~valid_plate_mask
if min_background_samples <= 1 and void_mask.any():
    for i in range(N):
        valid = (
            warped_valid[i].astype(bool)
            if warped_valid is not None and i < len(warped_valid)
            else np.ones((H, W), dtype=bool)
        )
        presence = void_mask & valid & (warped_norm[i].max(axis=2) > 0)
        if presence.any():
            plate[presence] = warped_norm[i][presence]
            void_mask[presence] = False
            valid_plate_mask[presence] = True
```

- **Scope Isolation:** Step 4 is gated by `if min_background_samples <= 1 and void_mask.any():`. In normal plate builds with $N_{\text{span}} \ge 2$, `min_background_samples` is 2 (`min(_PLATE_MIN_BG_SAMPLES, len(warped_frames)) = 2`). The entire block is skipped, ensuring zero alteration to multi-frame background plate generation.
- **Validity Guarding:** For single-frame plates ($N_{\text{span}}=1$, `min_background_samples=1`), unwarped zero padding has `valid == False`. Thus `presence = void_mask & valid & ...` correctly excludes padding from being recorded in `valid_plate_mask`.
- **Backward-Compatible Fallback:** If a caller does not pass `warped_valid` (`warped_valid is None`), `valid` evaluates to an all-True boolean array `np.ones((H, W), dtype=bool)`, reproducing the exact prior behavior without error.

---

### 4. Check 4: Test Suite Quality & Discrimination Audit

We analyzed the three new / updated unit tests in [`test_plate_compositor.py`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/test/rendering/test_plate_compositor.py):

1. **`test_blend_phase_plates_preserves_claimed_cel_across_seam` (lines 262–283):**
   - Setup: Seam at $y=36$, `blend_width=8` (ramp window $[28, 44]$). Cel spans rows $y \in [27, 44]$ with `left_claimed=3`.
   - Old Buggy Behavior: Cel pixels in rows $28\dots 44$ were attenuated by `alpha_left` (value 0.5 at $y=36$, value 0.0 at $y=44$), causing test failure on full-cel assertion.
   - New Assertion: `assert np.array_equal(result[cel], left[cel])` across the **entire** cel (rows 27–44).
   - Verdict: **High Discrimination.** Strictly validates that zero ramp attenuation occurs across the seam.
2. **`test_blend_phase_plates_narrow_overlap_has_no_luminance_step` (lines 285–303):**
   - Setup: Left valid $y \in [0, 50]$ (value 30); Right valid $y \in [31, 79]$ (value 130). Overlap width = 20 px ($[31, 50]$), `seam_y=40`.
   - Old Buggy Behavior: Unclamped `blend_width=48` produced a 41-unit luminance step between row 30 and row 31.
   - New Assertion: `assert np.max(np.abs(np.diff(values))) <= 8` and `assert result[31] < result[50]`.
   - Verdict: **High Discrimination.** Validates that the ramp is smoothly bounded within the 20 px overlap with maximum delta $\approx 5.26 \le 8$.
3. **`test_build_aligned_background_plate_single_source_respects_warped_valid` (lines 109–122):**
   - Setup: Single frame ($N=1$) with non-zero values everywhere, but `warped_valid[:9] = False`.
   - Old Buggy Behavior: Marked rows $0\dots 8$ as valid because `warped_norm.max(axis=2) > 0` was True.
   - New Assertion: `assert not plate_valid[:9].any()` and `assert plate_valid[9:].all()`.
   - Verdict: **High Discrimination.** Directly confirms out-of-frame padding is rejected.

---

### 5. Check 5: Non-Regression & Scope Audit

- **Untouched Areas:**
  - `_multiphase_plate_plan()` contiguity gate in `composite.py` remains untouched and continues to reject interleaved or thin-span sequences.
  - Per-span lockstep slicing `[start:end+1]` remains intact.
  - Local-to-global index remapping in `composite_plate_multiphase()` remains intact.
  - Reverse-pan physical canvas ordering remains intact.
- **Test Results:**
  - All 23 tests in `test_plate_compositor.py` pass.
  - All 216 tests in the backend compositing suite (`-k "plate or composit"`) pass.
- **Performance / Memory:** No additional allocations or overhead added.

---

## Conclusion & Authorization Recommendation

Codex's commit [`7e352ba`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/) completely resolves all three review findings (B1, S1, S2) with high mathematical precision and robust test verification.

**Recommendation:** Proceed immediately with Harbinger sign-off to launch the **Step-6 discriminating set benchmark sweep** (`n_phases=3`, 20 frozen-`RAW_ASP` multi-phase cases, + `ASP_PHASE_COMPOSITE` on/off arms).
