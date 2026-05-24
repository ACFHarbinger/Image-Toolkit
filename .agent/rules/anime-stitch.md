---
trigger: anime_stitch
description: Rules for modifying the AnimeStitchPipeline — compositing, rendering, alignment, and photometric correction code in backend/src/anim/.
---

You are working on the anime image stitching pipeline in `backend/src/anim/`. Apply the following rules at all times.

---

## Iteration & Testing

- **Run the unit test suite first.** Before and after any change to `backend/src/anim/`, run `pytest backend/test/anim/ -q`. The suite has 105 tests covering all issue categories with no GPU dependency (~7s). A regression here is a hard blocker.
- **Update tests when fixing documented bugs.** Tests that document broken behavior (e.g. near-zero edge clustering) have a comment saying "update this assertion after the fix". Find the test and flip the assertion to verify the corrected behavior.
- **Always use the fast iteration loop.** Do not re-run BiRefNet or LoFTR to test compositing changes. Load pre-computed stages from `data/asp_test1/output/panorama_stages/` via `archive/run_pipeline_v2.py`. Only re-run full GPU stages when changing Stages 1–8.
- **View the output image after every run.** Use the Read tool on the `.png` output to visually inspect the result before claiming success. Do not rely solely on printed gain/delta values.
- **Compare against the simple stitch.** The reference target is `data/asp_test1/output/simple_stitch.png`. No horizontal bands, no brightness discontinuities, no block artifacts.
- **Test all datasets.** A fix that helps `asp_test1/` (8 frames) must not break `asp_test6/` (the positive baseline), `asp_test3/` (11 frames, Stage 9 failure), `asp_test2/` (10 frames, alignment failure), or the datasets asp_test4–asp_test22.

---

## Photometric Corrections

- **LS normalization clamp must stay tight.** The LS gain clamp in `_global_gain_normalize` is `(0.95, 1.05)`. Do NOT widen it without a clear reason. The natural scene brightness gradient between panels is real and should not be treated as calibration error. A 53% gain range across 8 frames from the same scene indicates measurement contamination, not genuine camera drift.
- **No per-zone gain correction.** The `gain_seam` measurement in `_composite_foreground` compares different scene elements at the same canvas row — it measures scene content, not photometric calibration. Keep it as `gain_seam = np.ones(3)`.
- **No post-composite seam ramp inside feather zones.** `_apply_canvas_seam_correction` was designed for the hard-partition-only case. When wide feather blends are active, the ramp correction applies inside the blend zone and creates new visible bands. It is intentionally disabled.
- **Do not re-enable** any of these without first verifying on all three test datasets.

---

## Feather Zones

- **Allow feather zone overlap.** Adjacent feather zones are allowed to overlap. The `num/denom` accumulation in the composite chunk loop handles this correctly by averaging contributions. Do NOT add a boundary-spacing cap that prevents overlap.
- **Cap feathers by natural overlap only.** Use `min(nat_overlap // 2, _FEATHER_MAX)`. The `nat_overlap` is the physical overlap between adjacent frames (typically ~1895px for these datasets), not the boundary spacing.
- **The DP seam path governs gain taper, not blend alpha.** `d_seam` (per-column seam path distance) is used for `t_blend` (gain correction taper). The blend alpha `t_lin` must use `d_flat = local_ys - float(y_cut)` (flat horizontal). Never use the seam path for the blend alpha — it causes irregular brightness boundaries.

---

## Alignment

- **Bundle adjustment output must be validated.** After `_bundle_adjust_affine`, check that the sorted `ty` values form a monotonically increasing sequence with roughly equal spacing (within a 3× factor of the median gap). If not, flag alignment failure and fall back to the simple stitch. Do not let broken affines propagate to Stage 9.
- **Never assume frame input order equals scroll order.** The pairwise matcher must detect the scroll direction from the data, not from filename order.
- **RANSAC-style outlier rejection is needed in bundle adjust.** After initial LM solve, compute per-edge residuals. Edges with residual > 3× median should be removed and the system re-solved. This prevents a few bad LoFTR matches from collapsing the entire alignment.
- **Reject near-zero dy matches in `_filter_edges`.** Any pairwise match with `|dy| < 50px` is a near-zero match — either the same frame matched against itself, a wrong-direction match, or a repeated-content false positive. These produce frame clustering (multiple frames at essentially the same canvas y-position) and must be discarded before bundle adjustment.
- **Stage 9 ghosting is always caused by bad affines.** If the temporal render is ghosted, do not debug `_render_median` first — check the affines in `stage08_canvas_info.json`. The rendering logic is correct; overlapping frames mean the canvas geometry is wrong.
- **Diagonal scroll (tx drift) is not yet supported.** Datasets where the camera pans both vertically and horizontally will always fail until `_compute_canvas` in `canvas.py` is updated to use the full affine tx offset. Symptom: simple_stitch is wider than the pipeline panorama and has staircase black borders. Test7 is the canonical example.
- **Check the full affine matrix, not just ty/tx.** test18 has ratio=1.1× with min_gap=327px but catastrophic Stage 9 ghosting because the off-diagonal elements of the affine matrices indicate large rotation. `_validate_affines` must check `|a[0][1]|` and `|a[1][0]|` (off-diagonal); if either exceeds 0.1, the frame has problematic rotation and must be flagged.
- **Detect scroll axis before compositing.** If `ty_range < 0.1 * tx_range`, the source frames represent a horizontal scroll (like test20: tx=0–1857px, ty≈0). Applying vertical strip compositing to a horizontal scroll produces horizontal seam bands. Log a warning and either fall back to `_merge_images_scan_stitch` or switch to horizontal strip mode.
- **Detect co-located duplicate frames.** Before bundle adjustment, reject frame pairs where both `|dy| < min_step` AND `|dx| < min_step`. In `_validate_affines`, flag any dataset where `min_gap == 0` — it has co-located frames that will ghosting the top/bottom strips.
- **Seven positive baselines exist.** test4, test6, test11, test14, test15, test19, test22 all produce clean outputs. Any change that degrades these datasets is a regression. Test against at least test6, test11, and test22 after any alignment or compositing change.

---

## Rendering (Stage 9)

- **MFSR is disabled in test scripts — not in production.** The `run_pipeline_v2.py` test script skips MFSR because DCT-based MFSR introduces 8×8 block artifacts in flat cel-shaded regions. The production pipeline exposes a GUI toggle. Do not remove the MFSR code; keep it behind the toggle.
- **The rendering gain clamp `(0.88, 1.12)` in `_render_median` is independent** from the LS clamp in `_composite_foreground`. These are different correction passes on different data — do not conflate them.

---

## Code Quality

- **No Qt imports in `backend/src/anim/`.** These modules must be importable from headless scripts.
- **Do not change `_composite_foreground`'s public signature.** It is called from the pipeline, the GUI worker, and test scripts. All changes must be backward-compatible.
- **Print diagnostic output for every meaningful decision.** The `[Stitch]` prefix print statements (boundary positions, feather sizes, LS gains, DP path ranges) are essential for diagnosing issues in logs. Do not remove or silence them.
- **Module constants at the top of `compositing.py`** (`_FEATHER_MAX`, `_FEATHER_MIN`, `_GAIN_CLAMP`, `_SEAM_RAMP_HALF`, etc.) must be documented with units and the reason for their values. Do not change these silently.
