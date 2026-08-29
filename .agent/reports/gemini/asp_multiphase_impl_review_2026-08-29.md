# ASP Multi-Phase Renderer — Piecewise-P1 Implementation Correctness Review

**Author:** Agy (Gemini)  
**Date:** 2026-08-29  
**Target Commit:** Codex's commit [`84af1be`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/) (`feat(compositing): add gated multiphase plate renderer`) in `submodules/ASP/`  
**Relates to:** Issue #463, [asp_multiphase_renderer_design_2026-08-28.md](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/.agent/reports/chat/asp_multiphase_renderer_design_2026-08-28.md) (§4 RESULT, §5, §8), and [asp_multiphase_p1_impl_surface_2026-08-29.md](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/.agent/reports/gemini/asp_multiphase_p1_impl_surface_2026-08-29.md)  
**Status:** Read-only correctness review (Findings only, NO codebase edits)

---

## Executive Summary & Bottom-Line Sweep Verdict

We conducted an exhaustive line-by-line correctness review of Codex's implementation in commit `84af1be` across [`composite.py`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/composite.py), [`_plate_compositor.py`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py), and [`config.py`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/core/config.py).

### Bottom-Line Verdict: **CONDITIONAL NO-GO** for Step-6 Benchmark Sweep

> [!CAUTION]
> **Do NOT authorize the Step-6 benchmark sweep with commit `84af1be` as-is.**
>
> An active **BLOCKER** defect in [`_blend_phase_plates`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L406-L465) multiplies hero character cel opacities by the background plate blend ramp (`alpha_left` / `right_weight`). Any character cel extending into or crossing a phase boundary seam band becomes **semi-transparent (translucent body ghosting)** or is **severed / erased**.
>
> Authorizing the sweep before fixing this blocker and the two should-fix items will cause metric regressions on the discriminating set and produce corrupted render artifacts.

---

## Ranked Findings Summary

| Severity | ID | File & Line | Summary | Impact |
|---|---|---|---|---|
| **BLOCKER** | **B1** | [`_plate_compositor.py:451-454`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L451-L454) | Hero cel distance alpha is multiplied by canvas blend ramp `alpha_left`/`right_weight` | Characters crossing or near phase seams become semi-transparent ghosts or are partially erased |
| **SHOULD-FIX** | **S1** | [`_plate_compositor.py:415,419-420,517`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L415) | Fixed `blend_width=48` creates step discontinuity on overlaps narrower than $2 \cdot W_{\text{blend}}$ | Overlaps < 96 px produce sharp luminance steps at overlap edges |
| **SHOULD-FIX** | **S2** | [`_plate_compositor.py:195-202`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L195-L202) | `_build_aligned_background_plate` residual void fill ignores `warped_valid` on $N_{\text{span}}=1$ | Corrupts validity mask for single-frame plates, claiming full canvas |
| **NIT** | **N1** | [`_plate_compositor.py:383`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L383) | Laplacian pyramid level formula on tiny test canvases ($H \le 33$) | Harmless on production canvases ($H \approx 3000$), causes test artifacts on micro-arrays |
| **NIT** | **N2** | [`composite.py:47-53`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/composite.py#L47-L53) | Direction check on single-span input evaluates empty diff `np.all([]) == True` | Safe default to `"forward"`, but subtle |

---

## Detailed Findings & Failing Scenarios

### Finding B1 (BLOCKER): Hero Cel Attenuation & Translucency in Transition Band

- **Location:** [`_plate_compositor.py:440-464`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L440-L464) in `_blend_phase_plates()`
- **Mechanism:**
  In `_blend_phase_plates()`, after performing the background plate Laplacian blend across $[y_{\text{seam}} - W_{\text{blend}}, y_{\text{seam}} + W_{\text{blend}}]$, lines 440–464 attempt to re-apply phase-local character cels:
  ```python
  # _plate_compositor.py:440-464
  for source, source_claimed, select_right in (
      (left, left_claimed, False),
      (right, right_claimed, True),
  ):
      cel = source_claimed >= 0
      if not cel.any():
          continue
      distance = cv2.distanceTransform(cel.astype(np.uint8), cv2.DIST_L2, 3)
      cel_alpha = np.clip(distance / float(max(1, _SP_SOFT_PX)), 0.0, 1.0)
      if select_right:
          cel_alpha *= np.broadcast_to(right_weight[:, None], (H, W))
      else:
          cel_alpha *= alpha_left
      a3 = cel_alpha[:, :, None]
      active_cel = cel & (cel_alpha > 0.0)
      result[active_cel] = np.clip(
          source[active_cel] * a3[active_cel]
          + result[active_cel] * (1.0 - a3[active_cel]),
          0,
          255,
      ).astype(np.uint8)
      claimed[active_cel] = source_claimed[active_cel]
  ```
- **Concrete Failing Scenario:**
  1. Consider Phase 0 (`left`) with a character pose standing near the boundary region, spanning rows $y \in [y_{\text{seam}} - 30, y_{\text{seam}} + 40]$.
  2. For $y < y_{\text{seam}} - 48$, `alpha_left = 1.0`, so the upper body is 100% opaque.
  3. At $y = y_{\text{seam}}$, `alpha_left = 0.5`. In the interior of the character body (`distance >= 8`), `cel_alpha` becomes $1.0 \times 0.5 = 0.5$. The character is composited as $0.5 \times \text{character} + 0.5 \times \text{background\_plate}$. The background plate shows directly through the character's torso!
  4. For $y \ge y_{\text{seam}} + 49$, `alpha_left = 0.0`, so `cel_alpha = 0.0`. `active_cel` is False. The legs/lower body of the character are completely erased and replaced with Phase 1's empty background plate.
  5. If Phase 1 (`right`) also has a character pose in the seam band, both poses are scaled by their respective spatial ramps ($0.5$ each) and blended on top of each other, producing **phantom cross-phase ghosting**.
- **Root Cause & Fix Rationale:**
  The docstring and inline comment explicitly say:
  `"""Join adjacent physical phase bands without feathering hero cels."""`
  `# Re-apply the phase-local cels with a short soft edge after the background blend.`
  `# This prevents the plate seam from attenuating either hero pose.`
  Multiplying `cel_alpha` by `alpha_left` / `right_weight` directly contradicts this requirement. `cel_alpha` must only represent the local boundary feather (`distance / _SP_SOFT_PX`), and must **never** be modulated by the canvas-wide linear transition ramp.

---

### Finding S1 (SHOULD-FIX): Fixed Blend Width Discontinuity on Narrow Overlaps

- **Location:** [`_plate_compositor.py:415, 419-420, 517`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L415)
- **Mechanism:**
  `_blend_phase_plates` specifies a default `blend_width = 48` (total window $2 \cdot W + 1 = 97\text{ px}$). The transition ramp $[y_0, y_1]$ is computed as $[y_{\text{seam}} - 48, y_{\text{seam}} + 49]$.
  However, in `_blend_phase_plates`:
  ```python
  both_bg = left_valid & right_valid & (left_claimed < 0) & (right_claimed < 0)
  band[y0:y1] = True
  blend_bg = both_bg & band
  result[blend_bg] = bg_blend[blend_bg]
  ```
- **Concrete Failing Scenario:**
  1. Suppose Phase 0's valid coverage ends at $y = 510$ and Phase 1's valid coverage begins at $y = 490$ (valid overlap is $[490, 510]$, total width 20 px).
  2. $y_{\text{seam}} = (510 + 490) / 2 = 500$.
  3. `y0 = 500 - 48 = 452`, `y1 = 500 + 49 = 549`.
  4. For $y \in [452, 489]$, `both_bg` is False because `right_valid` is False. Thus `result` retains 100% Left plate.
  5. At row $y = 490$, `both_bg` suddenly becomes True. At this row, `alpha_left = 1.0 - (490 - 452)/96 = 0.604`.
  6. **Luminance Jump:** Between row 489 and row 490, the background plate composition instantly jumps from **100% Left** to **60.4% Left + 39.6% Right** in a single pixel row!
  7. Similarly, at row 511, composition jumps from **39.6% Left + 60.4% Right** to **100% Right**.
- **Fix Rationale:**
  `composite_plate_multiphase` should calculate the actual overlap half-width:
  ```python
  actual_overlap_half = max(0, min(seam_y - right_rows[0], left_rows[-1] - seam_y))
  effective_blend_width = min(blend_width, actual_overlap_half)
  ```
  and pass `effective_blend_width` to `_blend_phase_plates`. If overlap is 0 (gap), `blend_width = 0`, producing a clean hard boundary at `seam_y` without truncated ramps.

---

### Finding S2 (SHOULD-FIX): Single-Frame Background Plate Void Fill Ignores `warped_valid`

- **Location:** [`_plate_compositor.py:195-202`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L195-L202)
- **Mechanism:**
  When `min_background_samples <= 1` (e.g. when testing with $N_{\text{span}} = 1$ or if an edge case produces a 1-frame plate):
  ```python
  void_mask = ~valid_plate_mask
  if min_background_samples <= 1 and void_mask.any():
      for i in range(N):
          presence = void_mask & (warped_norm[i].max(axis=2) > 0)
          if presence.any():
              plate[presence] = warped_norm[i][presence]
              void_mask[presence] = False
              valid_plate_mask[presence] = True
  ```
- **Concrete Failing Scenario:**
  If an input frame has non-zero background values across the entire canvas (such as synthetic benchmark test arrays initialized with non-zero constants or unmasked border regions), `warped_norm[i].max(axis=2) > 0` is True for all rows. `valid_plate_mask` is erroneously set to True for rows $[0, H-1]$, completely ignoring `warped_valid[i]`. This causes `plate_valid` to claim 100% canvas coverage and pollutes downstream multiphase seam calculations (manifesting as failure in `test_composite_plate_multiphase_reverse_order_uses_canvas_order`).
- **Fix Rationale:**
  Intersect `presence` with `warped_valid[i]`:
  ```python
  valid_i = warped_valid[i] if warped_valid is not None and i < len(warped_valid) else True
  presence = void_mask & valid_i & (warped_norm[i].max(axis=2) > 0)
  ```

---

### Finding N1 (NIT): Laplacian Pyramid Filter Footprint on Low-Height Test Canvases

- **Location:** [`_plate_compositor.py:383`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/_plate_compositor.py#L383)
- **Details:**
  `levels = min(4, max(1, int(np.log2(min(left.shape[:2]))) - 2))` yields 3 levels for an $H=33$ test image. The effective spatial support of a 3-level Gaussian pyramid down/up filter is $\approx 40\text{ px}$, which exceeds the 33 px canvas height and creates edge feather bleeding on flat synthetic tests. On production canvases ($H \approx 1000\dots 4000$), this formula is completely well-behaved.

---

### Finding N2 (NIT): Contiguity Gate Direction Check on Single-Span Input

- **Location:** [`composite.py:47-53`](file:///home/pkhunter/Repositories/Repo/Image-Toolkit/submodules/ASP/backend/src/rendering/compositing/composite.py#L47-L53)
- **Details:**
  When `len(spans) == 1`, `deltas = np.diff([phase])` is an empty NumPy array `[]`. `np.all([])` evaluates to True, causing `direction = "forward"`. While single-span inputs are intercepted upstream or handled correctly by single-span multiphase, relying on NumPy's empty-array `all` behavior is subtle.

---

## Detailed Focus Area Audit

### 1. `_multiphase_plate_plan()` in `composite.py` — Contiguity Gate

| Question | Assessment | Verification Detail |
|---|---|---|
| Rejects non-contiguous / interleaved cases? | **PASS** | `len(set(physical_order)) != len(physical_order)` and `len(physical_order) != len(spans)` rejects any phase split across canvas space. |
| Rejects thin spans ($N_{\text{span}} < 2$)? | **PASS** | Line 35: `any(end - start + 1 < 2 for ... in spans)` returns `None` $\to$ clean fall-through. |
| Handles forward and reverse directions? | **PASS** | `np.all(deltas >= 0)` $\to$ `"forward"`; `np.all(deltas <= 0)` $\to$ `"reverse"`; mixed $\to$ `None`. |
| Handles phase ID gaps (e.g. `[0, 2]` without 1)? | **PASS** | `spans` contains `[(0, 0, 1), (2, 2, 3)]`. `deltas = [2] >= 0` $\to$ `"forward"`. `phase_results` dict indexing in `composite_plate_multiphase` correctly resolves non-consecutive phase IDs. |
| Handles identical mean `ty` across frames? | **PASS** | Python's `sorted()` is stable; preserves selection order. If identical `ty` causes interleaving, it is safely rejected; if within-phase, collapsed into a single run. |

### 2. `composite_plate_multiphase()` — Per-Span Slicing

| Question | Assessment | Verification Detail |
|---|---|---|
| Lockstep slicing `[start:end+1]`? | **PASS** | Synchronously slices `warped_frames[start:end+1]`, `warped_bg[start:end+1]`, and `warped_valid=warped_valid[start:end+1]`. |
| Potential off-by-one or length mismatch? | **PASS** | `start` and `end` are inclusive selection indices from `phase_spans()`; `end + 1` extracts exactly `end - start + 1` elements across all three lists. |
| `warped_valid` sliced in sync? | **PASS** | Passed directly to `composite_plate_single_pose(warped_valid=...)`. |

### 3. `_blend_phase_plates()` — Plate-to-Plate Join

| Question | Assessment | Verification Detail |
|---|---|---|
| Seam bounds `[y_seam ± W_blend]`? | **PASS** | `y0 = max(0, seam_y - blend_width)`, `y1 = min(H, seam_y + blend_width + 1)` are strictly bounded in $[0, H]$. |
| Behavior when valid bands have a gap? | **PASS** | In the gap, `both_bg` is False; `result` cleanly preserves fallback `canvas` pixels. |
| Behavior when overlap $< 2 \cdot W_{\text{blend}}$? | **FAIL (S1)** | Truncated ramp causes sharp luminance steps at overlap boundaries. |
| Feather direction under Reverse Pan (`[1, 0]`)? | **PASS** | `physical_phase_order` orders bands strictly top-to-bottom on canvas (`ty`). `left` is always the upper band, `right` is always the lower band. Spatial blending direction is identical for forward and reverse pans. |
| Hero cel preservation across seam? | **FAIL (B1)** | `cel_alpha` modulated by canvas ramp attenuates hero cels into semi-transparent ghosts. |

### 4. Local $\to$ Global Frame-Index Remapping

| Target | Assessment | Verification Detail |
|---|---|---|
| `claimed` map pixels | **PASS** | `global_claimed[claimed_pixels] += start` correctly shifts all non-negative cel pixel values. |
| `zone["chosen_frame"]` | **PASS** | `zone_out["chosen_frame"] += start` remapped in `ownership_spans`. |
| `zone["candidates"]` | **PASS** | `(idx + start, area, score)` remapped for all candidate tuples. |
| `seam_meta_out["plate_ownership"]` | **PASS** | Full remapped structure saved to `seam_meta_out["plate_ownership"]`. |
| Any un-remapped local indices escaping? | **PASS** | Comprehensive audit revealed zero un-remapped index leaks. |

### 5. `composite_plate_single_pose(return_plate_valid=…)`

| Question | Assessment | Verification Detail |
|---|---|---|
| Preserves existing callers? | **PASS** | Default `return_plate_valid=False` returns standard 3-tuple `(result, claimed_map, metadata)`. |
| Early return paths? | **PASS** | `if not union_fg.any():` properly checks `return_plate_valid` and returns 4-tuple. |
| `plate_valid` derivation? | **PASS** | Derived from `_build_aligned_background_plate`'s actual sample count mask (`sample_count >= min_samples`). (Subject to Finding S2 for $N=1$). |

### 6. RSS Warning & Environment Variable Consistency

| Item | Single-Pose Path | Multi-Phase Path | Consistency |
|---|---|---|---|
| `ASP_PLATE_EDGE_PRESERVE` | `os.environ.get("ASP_PLATE_EDGE_PRESERVE", "1") != "0"` | `os.environ.get("ASP_PLATE_EDGE_PRESERVE", "1") != "0"` | **Identical** |
| `ASP_PLATE_MULTIBAND` | `plate_multiband_enabled()` | `plate_multiband_enabled()` | **Identical** |
| RSS Estimate Print | N/A | `[Stitch] plate_multiphase: N phases -> ~M.1f GiB peak RSS estimated` | **Matches Audit ($2.0 + 3.0 \cdot N$)** |
| Seam Metadata Keys | `plate_single_pose`, `n_claimed`, `plate_ownership` | `plate_multiphase`, `plate_multiphase_direction`, `n_claimed`, `plate_ownership` | **Fully aligned** |

---

## Action Plan Before Authorizing Step-6 Sweep

1. **Fix Blocker B1 in `_plate_compositor.py`:**
   In `_blend_phase_plates()`, remove lines 451–454 (`cel_alpha *= alpha_left` / `cel_alpha *= right_weight`). Re-apply character cels using their true silhouette feather `distance / _SP_SOFT_PX` without modulation by `alpha_left` or `right_weight`.
2. **Fix Should-Fix S1 in `_plate_compositor.py`:**
   Clamp `blend_width` to the actual valid overlap half-width before calling `_blend_phase_plates()`.
3. **Fix Should-Fix S2 in `_plate_compositor.py`:**
   In `_build_aligned_background_plate()`, ensure single-source void fill respects `warped_valid`.
4. **Run Hardened Unit Test Suite:**
   Verify that all 21 unit tests in `test_plate_compositor.py` pass cleanly.
5. **Authorize Step-6 Benchmark Sweep:**
   Once items 1–4 are complete, request Harbinger sign-off to run the Step-6 discriminating set benchmark sweep.
