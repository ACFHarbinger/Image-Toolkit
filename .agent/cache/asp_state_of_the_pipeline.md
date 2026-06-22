# ASP — State of the Pipeline: What Works, What Failed, What's Next

*Date: 2026-06-22. Updated through S159 (§1.125 seam transition penalty + §3.30 strip self-SSIM + §1.126 fg-majority floor + §1.127 zone hue eq).*  
*Primary benchmark corpora: 97 tests (`asp_test01–96` + `asp_test97`), 55 with ground truth in `data/ground_truth/`. 5-test subset (`test04/08/09/27/57`) used for rapid iteration.*

**S159 (2026-06-22):** §1.125 Seam Transition Straightness Penalty. `_SEAM_TRANSITION_PEN` (default 0.0) adds a row-distance-from-midline cost to the energy matrix in `_seam_cut` before the DP forward pass. Distance normalised to [0, 1] over zone height — scale-invariant. Creates mild prior toward straight seam paths. `ASP_SEAM_TRANSITION_PEN=<float>` to enable (e.g. 5.0). §3.30 Per-Strip Top/Bottom NCC Self-Consistency. `_strip_self_ssim(img, n_strips=8) → float` in `bench_anime_stitch.py` — splits each strip in half, computes NCC between halves at 32px thumbnail height, returns min across strips. Near 1.0 = smooth strips; lower = brightness jump at seam. Added as `strip_self_ssim` to all benchmark result dicts. §1.126 Fg-Majority Column Floor. `_FG_MAJORITY_FLOOR` (default 0.0 = off) — in `_build_seam_cost_map`, when zone is >60% fg, raises columns >80% fg to at least the floor value to push DP toward minority bg corridor. Guard: skipped when all columns heavy. `ASP_FG_MAJORITY_FLOOR=<float>` to enable (e.g. 1.5). §1.127 Zone Hue Equalization. `_zone_hue_eq(fa_zone, fb_zone) → ndarray` in `compositing.py` — circular-mean hue shift in HSV to match fb_zone mean hue to fa_zone; clamp [−30°, +30°]; threshold `ZONE_HUE_EQ_MIN_DIFF_DEG=5°`. Chained after `_zone_contrast_eq` when `ASP_ZONE_HUE_EQ=1`. Default OFF. `SEAM_TRANSITION_PEN_DEFAULT=0.0`, `FG_MAJORITY_FLOOR_DEFAULT=0.0`, `ZONE_HUE_EQ_MIN_DIFF_DEG=5.0` in `constants/anim.py`. 3 schema entries in `config.py`. 20 new tests. **1252 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S158 (2026-06-22):** §1.122 High Seam Path Cost Escalation. `_mean_path_cost(path_local, cost_map) → float` in `compositing.py` — samples cost map at each path column, returns mean. When `ASP_HIGH_PATH_COST_THRESH > 0` and mean cost exceeds threshold, escalates to single-pose (dominant fg frame). Gate wired after §1.69 dp-bg-ratio check. `HIGH_PATH_COST_THRESH_DEFAULT=0.6` in constants. §3.29 Blend Zone Coverage Fraction. `_zone_coverage_fraction(img, n_strips=8) → float` in `bench_anime_stitch.py` — `(n_strips−1) × 2 × (strip_h // 3) / H` capped at 1.0. Added as `zone_coverage_fraction` to all benchmark result dicts. §1.123 Local Scatter Penalty. When `ASP_SCATTER_COST=1`, adds per-pixel 3×3 box-filter variance normalised to `_SCATTER_COST_WEIGHT` as additive cost before DP. Routes seam away from high-frequency noise/debris. `SCATTER_COST_WEIGHT_DEFAULT=0.3` in constants. §1.124 Adaptive SP Soft Residual. When `ASP_ADAPTIVE_SP_SOFT=1`, post-diff > 30 lum → clips to `_ADAPTIVE_SP_SOFT_MIN` (default 3px); post-diff < 10 lum → widens to `_ADAPTIVE_SP_SOFT_MAX` (default 10px). Extends §1.22 feather-based adaptation. 7 schema entries in `config.py`. 20 new tests. **1232 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S157 (2026-06-22):** §1.119 Seam Zone Width Variance Gate. `_zone_width_cv(boundaries) → float` in `compositing.py` — std/mean of adjacent boundary gaps. High CV = uneven layout (some zones very narrow). When `ASP_ZONE_WIDTH_CV_MAX > 0` and CV exceeds threshold, pre-escalates the narrowest seam (argmin widths) to single-pose before DP. Gate wired before the blend loop. `ZONE_WIDTH_CV_MAX_DEFAULT=0.5` in constants. §1.120 Post-Composite Saturation Step Audit. `_audit_seam_sat_steps(result, boundaries, band_px=5, warn_thresh=0.0) → Dict[int, float]` in `compositing.py` — converts canvas to HSV, measures mean saturation difference in ±5px bands above/below each seam boundary (guard=2px). Logs warning when step > `_SEAM_SAT_WARN_THRESH`. Stores `seam_sat_steps` and `max_seam_sat_step` in `seam_meta_out`. Analogous to §1.106 lum audit but catches chromatic banding. §1.121 Zone Histogram Intersection Pre-gate. `_zone_hist_intersection(fa_zone, fb_zone) → float` in `compositing.py` — 32-bin per-channel histogram intersection, mean across 3 channels, [0,1]. When `ASP_ZONE_HIST_THRESH > 0` and score < threshold, pre-escalates to single-pose (dominant fg). Catches colour-palette shifts that §1.117 NCC misses. §3.28 Seam Boundary Gradient Direction Coherence. `_seam_row_grad_coherence(img, n_strips=8, band_px=8) → float` in `bench_anime_stitch.py` — circular mean resultant length R = |mean(exp(2jθ))| for Sobel gradient angles in ±8px boundary bands. R near 1.0 = dominant orientation; R near 0 = isotropic. Returns minimum R. Added as `seam_grad_coherence_min` to all benchmark result dicts. 4 schema entries in `config.py`. 20 new tests. **1212 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S156 (2026-06-22):** §1.116 Zone Blend Bg-Fraction Diagnostic. Computes `1 - _fg_fraction_in_zone(bg_a, bg_b)` for every blend zone and stores in `debug_context["zone_bg_fracs"]` when `ASP_ZONE_BG_FRAC_DIAG=1`. Pure observability: reveals how much of each blend zone is background vs character pixels, guiding calibration of §1.95/§1.101 fg-density gates. `ZONE_BG_FRAC_DIAG_KEY="zone_bg_fracs"` in `constants/anim.py`. §1.117 Fast Thumbnail NCC Structural Pre-gate. `_zone_pair_ncc(fa_zone, fb_zone, thumb_size=32) → float` in `compositing.py` — downsizes both zone crops to 32×32 and computes normalized cross-correlation. Returns 1.0 for empty/degenerate inputs. In blend loop, when `ASP_ZONE_FAST_NCC_THRESH > 0` and NCC falls below threshold on a non-escalated seam, escalates to single-pose (dominant fg frame). Catches structurally different zones before the heavier §1.97 entropy gate. `ZONE_FAST_NCC_THUMB_SIZE=32` in `constants/anim.py`. §1.118 Seam Band Laplacian Sharpness Guard. `_measure_seam_sharpness(result, boundaries, band_px=5) → Dict[int, float]` in `compositing.py` — after compositing, measures Laplacian variance in a ±5px band around each boundary in the final canvas. Low variance = blur artifact at seam. When `ASP_SEAM_SHARP_MIN > 0`, logs a per-boundary warning for blurred seams. Stores `seam_sharpness` and `max_seam_blur` in `seam_meta_out`. `SEAM_SHARP_BAND_PX=5` in `constants/anim.py`. §3.27 Seam Band NCC Benchmark Metric. `_seam_band_ncc(img, n_strips=8, band_px=10) → float` in `bench_anime_stitch.py` — splits output image into strips and computes NCC between 10px bands immediately above/below each inter-strip boundary. Returns minimum across all boundaries. Values near 1.0 = smooth transitions; low values = abrupt seam. Added as `seam_band_ncc_min` to all benchmark result dicts. 3 schema entries in `config.py`. 20 new tests in `test_compositing_s156.py` + `test_bench_metrics_s156.py`. **1192 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S155 (2026-06-22):** §1.113 Seam Cost Map Column-wise Gaussian Smooth. After §1.110 row blur in `_build_seam_cost_map`, applies `scipy.ndimage.gaussian_filter1d` along axis=1 (horizontal) on soft-cost region (< 1e5). Creates lateral cost gradients preventing DP zigzag between adjacent equal-cost columns. Hard barriers preserved. `ASP_COST_COL_SMOOTH_SIGMA=1.5` (default 0.0=OFF). §1.114 Zone RMS Contrast Equalization Before Blend. `_zone_contrast_eq(fa_zone, fb_zone) → ndarray` in `compositing.py` — computes luminance std over non-black pixels in each zone; scales `fb_zone` so contrast matches `fa_zone`. Scale clamped [0.5, 2.0]; skips when ratio deviation < 5% or std_b < 1. Chained after `_zone_sat_norm` in normal blend path. Corrects contrast-wash banding that §1.104 (mean lum) cannot fix. `ASP_ZONE_CONTRAST_EQ=1`. Default OFF. §3.26 Per-Strip Saturation CV Benchmark Metric. `_strip_sat_cv(img, n_strips=8) → float` in `bench_anime_stitch.py` — converts to HSV, measures mean saturation per strip, returns std/mean across strips. High CV = photometric banding invisible to lum/chroma metrics. Added as `strip_sat_cv` field to all benchmark result dicts. §1.115 Absolute Feather Jump Cap. `_cap_feather_jumps(feathers, max_jump) → ndarray` — two-pass (forward + backward) clamp: no adjacent feather pair may differ by more than `max_jump` pixels. Wired after §1.92 Gaussian smooth. Complements §1.68 (ratio-based). `ASP_FEATHER_JUMP_MAX=150` (default 0=OFF). Constants: `COST_COL_SMOOTH_SIGMA=1.5`, `ZONE_CONTRAST_EQ_CLAMP=2.0`, `FEATHER_JUMP_MAX_DEFAULT=150` in `constants/anim.py`. 3 schema entries in `config.py`. 20 new tests in `test_compositing_s155.py` + `test_bench_metrics_s155.py`. **1172 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S154 (2026-06-22):** §1.110 Seam Cost Map Gaussian Blur. After §1.109 L-inf normalization in `_build_seam_cost_map`, applies `scipy.ndimage.gaussian_filter` to the soft-cost region (cost < 1e5). Smooths tier-boundary transitions so DP has a gradient slope toward background corridors instead of a binary step — prevents argmin oscillation between equal-energy tier-boundary columns. Hard barriers (≥ 1e5) preserved unchanged. `ASP_COST_MAP_BLUR_SIGMA=2.0` (default 0.0=OFF). §3.25 Seam Boundary Entropy Benchmark Metric. `_seam_boundary_entropy(img, n_strips=8, band_px=15) → List[float]` in `bench_anime_stitch.py` — Shannon entropy of 256-bin greyscale histogram in ±15px row band at each inter-strip boundary, normalised by log2(256)=8 to [0, 1]. High entropy = complex texture at seam. Added as `seam_boundary_entropies` (List[float]) and `seam_boundary_entropy_max` (Optional[float]) to all benchmark result dicts. §1.111 Zone Background HSV Saturation Normalization. `_zone_sat_norm(fa_zone, fb_zone) → ndarray` in `compositing.py` — converts zones to HSV, matches mean saturation of background (non-black) pixels in `fb_zone` to `fa_zone` via scalar gain clamped [0.5, 2.0]. Skips when deviation < 2%. Chained after `_zone_lum_norm` (§1.104) in normal blend path. `ASP_ZONE_SAT_NORM=1`. Default OFF. §1.112 Seam Path Vertical Drift Gate. `_seam_path_drift(path) → float` — returns `max(|path[i+1]-path[i]|)` across consecutive path columns. In blend loop, after §1.31 FG penetration check: when drift > `_SEAM_DRIFT_THRESH` and not already single-pose, escalates to single-pose (dominant by fg count). `ASP_SEAM_DRIFT_THRESH=15.0` (default 0.0=OFF). Constants: `COST_MAP_BLUR_SIGMA=2.0`, `ZONE_SAT_NORM_GAIN_CLAMP=2.0`, `SEAM_DRIFT_THRESH=15.0`, `SEAM_BOUNDARY_ENTROPY_BAND_PX=15` in `constants/anim.py`. 4 schema entries in `config.py`. 21 new tests in `test_compositing_s154.py` + `test_bench_metrics_s154.py`. **1152 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S153 (2026-06-22):** §1.107 Adaptive Seam Band Width from Zone Height. `_adaptive_seam_band(zone_h, base_band, max_band=40) → int` in `compositing.py` — returns `min(max_band, max(base_band, zone_h // 6))`. Replaces the fixed `_sp_soft_px + 4` in the single-pose colour correction path with a computed `_band_px_sp` variable, passed to `_seam_color_match`, `_seam_band_hist_match`, and `_seam_lum_converge`. For tall zones (zone_h=600 → band=40px); short zones fall back to base. `ASP_ADAPTIVE_SEAM_BAND=1`. Default OFF. §3.24 Seam Boundary Row Std Benchmark Metric. `_seam_row_std(img, n_strips=8) → float` in `bench_anime_stitch.py` — for each inter-strip boundary row computes std of BGR pixel values across full width; returns max std / 255. High value = strong horizontal variation at boundary = visible seam. Added as `seam_row_std` field to all benchmark result dicts. §1.108 Laplacian Blend Alpha Schedule. Added `alpha_schedule: bool = False` parameter to `_laplacian_blend` in `stateless.py`. When enabled, mixes a sharp-masked version (`mask²`, 30%) with normal Laplacian result (70%). Reduces HF colour bleeding at character cel edges while preserving smooth low-frequency transitions. Wired via `_LAPLACIAN_ALPHA_SCHEDULE` flag (`ASP_LAPLACIAN_ALPHA_SCHEDULE=1`). Default OFF. §1.109 Seam Cost Map L-inf Normalization. At end of `_build_seam_cost_map` (after §1.99 pin rows), L-inf normalizes non-barrier (< 1e5) costs to [0, 1]. Preserves hard barriers unchanged. Ensures stable relative cost tiers when additive §3.17 or §1.35 terms push values above 1.0. `ASP_COST_MAP_NORM=1`. Default OFF. Constants: `ADAPTIVE_SEAM_BAND_MAX=40`, `LAPLACIAN_ALPHA_FINE_WEIGHT=0.3`, `COST_MAP_NORM_BARRIER=1e5` in `constants/anim.py`. 5 schema entries in `config.py`. 20 new tests in `test_compositing_s153.py` + `test_bench_metrics_s153.py`. **1131 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S152 (2026-06-22):** §1.104 Per-Zone Luminance Normalization Before Blend. `_zone_lum_norm(fa_zone, fb_zone) → ndarray` in `compositing.py` — computes mean grayscale lum of non-black pixels in each zone; applies scalar gain (clamped [0.5, 2.0]) to `fb_zone` when ratio deviation > 1%. Chained after `_zone_chroma_align` (§3.19) in the normal blend path: `_fb_for_blend = fb_zone → chroma_align → lum_norm`. Skips when either zone is all-black. `ASP_ZONE_LUM_NORM=1`. Default OFF. §3.23 Seam-Path Column Spread Benchmark Metric. `_seam_col_spread(img, n_strips=8) → float` in `bench_anime_stitch.py` — for each strip finds column of max Sobel-X energy (most likely seam column); returns `std(peaks) / W`. Low = concentrated routing (bad); high = spread across columns (good bg routing). Added as `seam_col_spread` field to all benchmark result dicts. §1.105 Fg-Overlap Laplacian Blend Weight Cap. Before `_laplacian_blend`, computes per-pixel fg-overlap mask (both zones have fg > 0) and lum-diff mask (diff > 10). When `ASP_FG_OVERLAP_BLEND_CAP > 0.0` and pixel meets both, caps `mask_float` at the configured value (e.g. 0.3), weighting strongly toward dominant zone. Prevents double-image ghost in fg-overlap pixels. `_mask_for_blend` used in `_laplacian_blend` call. Default 0.0 (OFF). §1.106 Post-Composite Seam Lum Step Audit. `_audit_seam_lum_steps(result, boundaries, band_px=5, warn_thresh=8.0) → Dict[int, float]` in `compositing.py` — after §1.90 bilateral smooth, measures mean abs lum diff in ±5px rows at each boundary. Logs `§1.106 seam-step WARNING` for steps > threshold. Populates `seam_meta_out` with `seam_lum_steps` dict and `max_seam_lum_step` scalar. Always runs (negligible overhead). `ASP_POST_SEAM_WARN_THRESH=8.0`. Constants: `ZONE_LUM_NORM_GAIN_CLAMP=2.0`, `FG_OVERLAP_BLEND_CAP_DEFAULT=0.3`, `POST_SEAM_WARN_THRESH=8.0` in `constants/anim.py`. 3 schema entries in `config.py`. 20 new tests in `test_compositing_s152.py` + `test_bench_metrics_s152.py`. **1111 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S151 (2026-06-22):** §1.101 Full Blend-Zone MAD Pre-Escalation. In blend loop after §1.97 entropy gate, computes `mean(|fa_zone − fb_zone|)` over the full zone; when MAD > `_ZONE_MAD_THRESH`, escalates to single-pose before DP. Catches colour-shift differences across the entire zone including bg region (unlike §1.60 which restricts to shared fg pixels). `ASP_ZONE_MAD_THRESH=30.0` to enable. Default 0.0 (OFF). §1.102 Warp Residual Momentum Damping. In fg-registration loop, after computing `_sp_thresh`: when `ASP_WARP_MOMENTUM_DAMP=1` and `k-1 in seam_single_pose`, multiplies `_sp_thresh` by `_WARP_MOMENTUM_FACTOR` (default 0.85). Adjacent seams sharing a frame often share the same pose discontinuity; lower threshold catches them earlier. Runs before §1.95 fg-fraction scaling block. Default OFF. §3.22 Seam Contrast Ratio Benchmark Metric. `_seam_contrast_ratio(img, n_strips=8, band_px=10) → float` in `bench_anime_stitch.py` — measures mean absolute Laplacian energy in ±band_px rows around inter-strip boundaries vs. interior; returns seam/interior ratio. Values near 1.0 = no artifact; > 1.5 = visible seam sharpness step. Added as `seam_contrast_ratio` field to all benchmark result dicts. §1.103 Reference-Proximity Dominant Frame Selection. In `post_diff > _sp_thresh` escalation path only: when `ASP_SP_REF_PROX=1`, selects `dom` as whichever of `fi_a`/`fi_b` is temporally closest to `ref_fi` (central reference frame, least warp drift). Does not affect fallback or pre-escalation paths. Default OFF. Constants: `ZONE_MAD_THRESH_DEFAULT=30.0`, `WARP_MOMENTUM_FACTOR=0.85`, `SP_REF_PROX_DEFAULT=False` in `constants/anim.py`. 4 schema entries in `config.py`. 20 new tests in `test_compositing_s151.py` + `test_bench_metrics_s151.py`. **1091 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S150 (2026-06-22):** §1.98 Per-Frame Gain Normalization Smoothing. `_smooth_gain_array(gains, sigma=1.0)` in `compositing.py` — scipy `gaussian_filter1d` over `frame_gains` list; after normalization loop, re-applies smoothed/raw ratio to bg pixels of `warped_norm` when ratio deviation > 0.5%. Prevents abrupt inter-strip brightness staircase from outlier gain corrections. `ASP_SMOOTH_GAIN=1`, `ASP_SMOOTH_GAIN_SIGMA=1.0`. Default OFF. §3.20 Extra Fg-Boundary Outer Dilation Cost Ring. In `_build_seam_cost_map`, after Tier-2 buffer (cost=0.5), dilates fg by `_EXTRA_FG_DILATION` px and adds cost=0.3 outer ring. Creates gradient 0→0.3→0.5→1.0 from background to fg-interior. `ASP_EXTRA_FG_DILATION=8` to enable. Default 0 (OFF). §1.99 Seam Endpoint Bg-Preference. At end of `_build_seam_cost_map`, amplifies fg pixel costs by 10× in top/bottom `_SEAM_PIN_ROWS` rows of zone. Steers DP seam entry/exit through background columns. Guard: `zone_h > 2 * _SEAM_PIN_ROWS`. `ASP_SEAM_PIN_ROWS=3` to enable. Default 0 (OFF). §3.21 Per-Strip Gradient Energy CV Metric. `_strip_gradient_cv(img, n_strips=8) → float` in `bench_anime_stitch.py` — splits image into N strips, computes mean absolute Laplacian energy per strip, returns CV (std/mean). High CV = seam-induced sharpness discontinuities. Added as `strip_gradient_cv` field to all benchmark result dicts. Constants: `SMOOTH_GAIN_SIGMA=1.0`, `EXTRA_FG_DILATION_DEFAULT=8`, `SEAM_PIN_ROWS_DEFAULT=3` in `constants/anim.py`. 4 schema entries in `config.py`. 20 new tests in `test_compositing_s150.py` + `test_bench_metrics_s150.py`. **1071 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S149 (2026-06-22):** §1.95 Fg-Zone Single-Pose Threshold Scaling. After computing `_sp_thresh` in the fg-registration loop, slices `warped_bg[fi_a/fi_b]` to zone extent, calls `_fg_fraction_in_zone`, and multiplies threshold by `_SP_THRESH_FG_FACTOR` (default 0.7) when fraction > `_SP_FG_FRAC_THRESH` (default 0.5). Fg-dominated zones produce worse ghosts when blended; lowering the threshold catches them for single-pose escalation earlier. `ASP_SP_THRESH_FG_SCALE=1` to enable. Default OFF. §3.19 Per-Zone Pre-Blend Chroma Alignment. `_zone_chroma_align(fa_zone, fb_zone) → ndarray` — computes LAB a/b mean over non-black pixels; when either delta > 2 LAB units, applies global additive shift to `fb_zone`. Wired before `_laplacian_blend` in the normal (non-single-pose) path when `ASP_ZONE_CHROMA_ALIGN=1`. Distinct from §1.56 post-composite correction and §1.88 seam-band histogram match. §1.96 Chroma Seam Coherence Benchmark Metric. `_chroma_seam_coherence(img, n_strips=8) → float` in `bench_anime_stitch.py` — converts to LAB, computes per-strip mean |a+b|, returns max adjacent-strip step. Added as `chroma_seam_coherence` field to all benchmark result dicts. §1.97 Seam Zone Entropy Asymmetry Gate. `_zone_entropy(zone)` + `_seam_zone_entropy_gap(fa_zone, fb_zone)` — Shannon entropy from grayscale histogram; when gap > `_ENTROPY_GAP_THRESH` (bits), pre-escalates to single-pose before DP. `ASP_ENTROPY_GAP_THRESH=1.5` to enable. Default 0.0 (OFF). Wired in blend loop after §1.86 SSIM check. Constants in `constants/anim.py`: `SP_THRESH_FG_FACTOR=0.7`, `SP_FG_FRAC_THRESH=0.5`, `ZONE_CHROMA_ALIGN_MIN_SHIFT=2.0`, `ENTROPY_GAP_THRESH_DEFAULT=1.5`. Schema entries added to `config.py`. 20 new tests in `test_compositing_s149.py` + `test_bench_metrics_s149.py`. **1051 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S148 (2026-06-22):** §1.91 Iterative Seam Luminance Convergence. `_seam_lum_converge(dom, oth, path, band_px, target_delta=5.0, max_iters=2)` in `compositing.py` — measures residual mean-delta in blend band after S16+§1.88; re-applies `_seam_color_match` until delta < target. Wired in single-pose path after `_seam_band_hist_match` when `ASP_SEAM_LUM_CONVERGE=1`. §1.92 Gaussian Feather Smoothing. `_smooth_feather_array(feathers, sigma=1.0, feather_min, feather_max)` — 1D Gaussian smooth via `scipy.ndimage.gaussian_filter1d`; re-clamps to `[FEATHER_MIN, FEATHER_MAX]`. Wired after `_enforce_feather_ratio` when `ASP_SMOOTH_FEATHER=1`. §3.18 CQAS Aggregate Score. `_compute_cqas(metrics)` in `bench_anime_stitch.py` — weighted combination: ghosting_siqe×0.35 + seam_visibility×0.30 + seam_coherence×0.20 + sharpness×0.15; normalized to [0,1]; added as `cqas` field to all benchmark result dicts. Single quality signal for 43 GT-less tests. §1.94 Background Consistency Score. `_bg_consistency_score(img, n_strips=1)` — per-strip row-mean lum std; added as `bg_consistency_score` to benchmark result dicts. `ASP_SEAM_LUM_CONVERGE`/`ASP_SEAM_LUM_CONVERGE_TARGET`/`ASP_SMOOTH_FEATHER`/`ASP_SMOOTH_FEATHER_SIGMA` in `_CONFIG_SCHEMA`. Constants in `constants/anim.py`. 20 new tests in `test_compositing_s148.py`. **1031 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S147 (2026-06-22):** §1.88 Band Histogram Matching. `_seam_band_hist_match(dom_zone, oth_zone, path_local, band_px)` in `compositing.py` — per-channel ECDF histogram transfer in seam blend band using `scipy.interpolate.interp1d`; falls back to mean-shift when scipy unavailable or < 10 band pixels. Wired in single-pose path after `_seam_color_match` when `ASP_HIST_MATCH_SEAM=1`. §1.89 Seam Residual Order. `_SEAM_ORDER_RESIDUAL` flag (`ASP_SEAM_ORDER=residual`) — sorts blend loop by ascending `seam_post_diffs[k]` so lowest-residual seams process first. Wired just before the blend loop. §1.90 Post-Seam Bilateral Smoothing. `_bilateral_seam_smooth(canvas, seam_paths, band_px=5, sigma_space=3.0, sigma_color=20.0)` — applies `cv2.bilateralFilter` in ±5px band around each DP seam path after compositing. `ASP_BILATERAL_SEAM=1`. Wired before seam overlay annotation. §3.17 High-Frequency Column Seam Cost. `_hf_column_cost(zone_a, zone_b, hf_threshold=50.0, hf_boost=0.5)` — Laplacian-energy-per-column additive cost in `_build_seam_cost_map`; columns with `mean(|∇²I|) > hf_threshold` get +0.5 cost. `ASP_HF_SEAM_COST=1`. All four default OFF. `ASP_HIST_MATCH_SEAM`/`ASP_SEAM_ORDER`/`ASP_BILATERAL_SEAM`/`ASP_HF_SEAM_COST` in `_CONFIG_SCHEMA`. `HIST_MATCH_SEAM_BAND_PX`/`SEAM_ORDER_RESIDUAL`/`BILATERAL_SEAM_*`/`HF_SEAM_COST_*` in `constants/anim.py`. All 4 exported in `__all__`. 20 new tests in `test_compositing_s147.py`. **1011 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S146 (2026-06-22):** §3.16B HITL Per-Test Preset System. `HitlPreset` dataclass + `save_hitl_preset` / `load_hitl_preset` / `apply_hitl_preset` / `list_hitl_presets` in new `backend/src/anim/hitl_presets.py` — preset JSON files in `ASP_HITL_PRESET_DIR` (default `~/.image-toolkit/hitl_presets/{test_name}.json`). Fields: `test_name`, `forced_frame_indices`, `drop_edges` (list of (src, dst) tuples), `forced_boundaries`, `scroll_axis_override`, `force_scans`, `notes`. Wired in `pipeline.py`: `load_hitl_preset(parent_dir_name)` after `image_paths` sorting; `force_scans` → immediate SCANS; `drop_edges` applied after `_filter_edges`. §3.5B CamFlow Background-Masked Phase Correlation. `bg_masked_phase_correlate(frame_a, frame_b, bg_mask_a, bg_mask_b, min_bg_pixels=500) → (dx, dy, response)` + `CamFlowEstimator` in new `cam_flow.py` — zeros fg pixels in both grayscale frames before `cv2.phaseCorrelate`; falls back to whole-frame if combined bg < 500px. Wired in `frame_selection.py` as `_CAMFLOW` flag (`ASP_CAMFLOW=bg_masked`); routes phase correlation through `bg_masked_phase_correlate` when BiRefNet mask available. Formalizes and extends the prototype `ASP_TWO_CHANNEL_SELECT` path. §2.10A Flow HITL Callback Checkpoint. `_flow_hitl_callback: Optional[Callable[[int, dict], Optional[ndarray]]]` + `set_flow_hitl_callback(cb)` in `compositing.py` — at single-pose escalation (after `post_diff > _sp_thresh`), calls callback with `(k, {"post_warp_diff": ..., "seam_k": k, "fi_a": ..., "fi_b": ...})`; if returns flow array, re-runs `register_foreground_at_seam(flow_override=...)`; exception guarded. Exported in `__all__`. `Callable` added to typing imports. `"ASP_HITL_PRESET_DIR"` + `"ASP_CAMFLOW"` added to `_CONFIG_SCHEMA`. `HITL_PRESET_DIR_DEFAULT` + `CAM_FLOW_MIN_BG_PIXELS=500` in `constants/anim.py`. 15 new tests (5 `TestHitlPreset` in `test_hitl_presets.py`, 5 `TestBgMaskedPhaseCorrelate` in `test_cam_flow.py`, 5 `TestFlowHitlCallback` in `test_compositing.py`). **991 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures unchanged).**

**S145 (2026-06-21):** §3.15B OBJ-GSP Triangular Mesh Barrier. `_build_fg_mesh_barrier(apply_mask, min_area_px=100) → np.ndarray` in `compositing.py` — `cv2.findContours` on combined fg mask → `scipy.spatial.Delaunay` triangulation of contour points → `cv2.fillConvexPoly` each simplex with cost=1e6 hard barrier, forcing DP seam into bg-only corridors. Returns zeros for empty/tiny (<100px) masks or degenerate contours (<4 points). Wired in `_build_seam_cost_map` after §3.15A column filter via `np.maximum`. `_MESH_BARRIER` module flag (`ASP_MESH_BARRIER=1`, default OFF). `MESH_BARRIER_MIN_AREA_PX=100` in `constants/anim.py`. `"ASP_MESH_BARRIER"` in `_CONFIG_SCHEMA`. §2.8 HybridStitch Export. `HybridExportData` dataclass in new `hybrid_export.py` — `image_paths`, `affines` (flat 6-float lists from numpy 2×3 arrays), `photometric_gains`, `photometric_biases`, `canvas_w/h`, `seam_boundaries`, `seam_post_diffs` (str keys), `timestamp` (UTC ISO-8601), `asp_version="S145"`. `build_hybrid_export(state_dict)`, `save_hybrid_export(data, path)` (JSON indent=2, creates parent dirs), `load_hybrid_export(path)` (raises `FileNotFoundError` if missing). Wired in `AnimeStitchPipeline.run()` after final save, try/except wrapped. `_HYBRID_EXPORT_PATH` module flag (`ASP_HYBRID_EXPORT_PATH`, default empty=disabled). `"ASP_HYBRID_EXPORT_PATH"` in `_CONFIG_SCHEMA`. 10 new tests (5 `TestMeshBarrier` in `test_compositing.py`, 5 `TestHybridExport` in `test_pipeline.py`). **976 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures unchanged).**

**S144 (2026-06-21):** §3.12A Overmix Hold-Block Sub-Pixel Averaging. `_hold_block_average(frames, hold_ids, paths) → Tuple[List[ndarray], List[str]]` in `frame_selection.py` — ECC-aligns all frames within each animation hold block (`MOTION_TRANSLATION`, 20 iters, 1e-3 eps) and stack-averages with `np.mean(...).clip(0,255)`; cv2.error fallback to raw frame. Achieves √N SNR improvement (N=2: +3 dB). Wired as step 3c in `smart_select_frames` after `_refine_hold_ids_by_response`; rebinds `thumbs`/`frames_paths`/`N`/`hold_ids`. Gate: `ASP_HOLD_AVERAGE=1` + hold detection active. Added to `__all__`. `HOLD_AVERAGE_ECC_ITERS=20`, `HOLD_AVERAGE_ECC_EPS=1e-3` in `constants/anim.py`. `"ASP_HOLD_AVERAGE"` in `_CONFIG_SCHEMA`. §3.9 SI-FID Proxy Metric. `_compute_si_fid_score(asp_img, sim_img, patch_size=128, n_patches=32)` in `bench_anime_stitch.py` — samples N random patch pairs at identical locations; computes Laplacian variance per patch; returns `mean(asp_var)/mean(sim_var)` (>1.0 = ASP sharper; None when images are None or smaller than patch_size). `ASP_SI_FID=1` to enable; `si_fid` emitted as `comparison.si_fid` in every benchmark result dict. `SI_FID_PATCH_SIZE=128`, `SI_FID_N_PATCHES=32` in `constants/anim.py`. `"ASP_SI_FID"` in `_CONFIG_SCHEMA`. 10 new tests (`TestHoldBlockAverage` × 5, `TestSiFidProxy` × 5). **966 backend tests (9 skipped, 5 pre-existing fg_register torch/ptlflow failures).**

**S143 (2026-06-21):** §3.10 MLLM Semantic Quality Scoring. `MllmScorer` + `MllmScores` + `score_composite` in new `mllm_scorer.py` — calls Qwen2-VL-7B via ollama HTTP (`ASP_MLLM_SCORER=1`); `_encode_image` (JPEG base64, ≤1024px), `_parse_scores` (JSON + regex fallback); zero new deps. Adds `mllm_body_coherence/seam_quality/bg_consistency/overall` fields to all benchmark result dicts. `avg_mllm_overall` in summary. Enables semantic verdict for 43 GT-less tests. §3.1A+§3.2A AnimeInterp SGM + ConvGRU flow engine in new `animeinterp_flow.py` — `trapped_ball_segment` (LAB flood-fill, no ML), `compute_region_features` (VGG-19/LAB fallback), `build_mdm` (cosine×spatial MDM, rows→1), `ConvGRUCell` (torch module, try/except guarded), `compute_animeinterp_flow` (full pipeline, n_gru_iters=0 skips GRU). Wired into `fg_register.py` as `ASP_FLOW_ENGINE=animeinterp`. **Key unlock**: ARAP now activates in test env without ptlflow — entire §1.56–§1.86 seam gate stack becomes active for the first time. 10 new tests. **956 backend tests (9 skipped).**

**S142 (2026-06-21) — Full 97-Test Benchmark (`anime_stitch_20260621_193956.json`, 7435s runtime).** No new §X.YZ implementation. Pure evaluation pass to establish full-corpus baseline after S141. **Results (97 tests, all-verdict):** asp_better=9 (9.3%), simple_better=46 (47.4%), comparable=41 (42.3%), insufficient_data=1. **GT-verdict (55 tests):** asp_better=6, simple_better=26, comparable=22, insufficient=1. **Avg GT-SSIM:** ASP=0.6588 vs Simple=0.6992 (ASP −0.0404). **Avg ghosting score:** ASP=38.7 vs Simple=27.2 (ASP 42% worse; wins on only 6/97 tests). **Avg sharpness:** ASP=108.9 vs Simple=63.8 (ASP 71% sharper — genuine advantage from sub-pixel alignment). **Fallbacks:** 0 external SCANS, 13 internal. **Worst outlier:** test77 (SSIM Δ=−0.2384, affine ratio=26.976, 26-frame/5459px canvas — extreme BA edge case). **Root cause of ghosting regression:** ARAP disabled in test env (no `ptlflow`) → 100% single-pose seam escalation → Stage 4.5 temporal median generates ghost average of different animation poses when fg covers >50% of rows. Sharpness advantage is real (alignment subpixel quality) and not captured by GT-SSIM (GT-coupling bias). **Next priority: §1.87 Masked-Median Background Plate** (replace Stage 4.5 zero-fill with `np.ma.median` + cross-frame stability voting — directly eliminates #1 ghosting root cause without GPU deps). **933 backend tests (9 skipped).**

**S141 (2026-06-21):** §1.86 Zone SSIM Pre-Gate. `_zone_pair_ssim(fa_zone, fb_zone, small_h=64) → float` added to `compositing.py` — resizes warped zone crops to 64px height, converts to grayscale, computes SSIM via `skimage.metrics.structural_similarity`; returns 1.0 (no gate) for zones with < 4 rows or < 8 cols; falls back to 1.0 on exception. `_ZONE_PRE_SSIM_THRESH` flag in `compositing.py` (default 0.0=off; `ASP_ZONE_PRE_SSIM_THRESH=0.35`). Wired in the blend loop after §1.70 (blend-zone fg-coverage gate) and before the DP seam cut: when score < threshold and `k not in seam_single_pose`, escalates to single-pose using dominant-fg-pixel-count rule. Complements §1.60 (fg MAD, pixel L1) and §1.70 (fg coverage fraction) which fire before zone extraction and use cruder signals; §1.86 fires after ARAP has run and uses full SSIM (luminance + contrast + structure) to catch poses that ARAP could not reconcile. `ZONE_PRE_SSIM_THRESH=0.35` in `constants/anim.py`. `"ASP_ZONE_PRE_SSIM_THRESH"` in `_CONFIG_SCHEMA` (`config.py`, float, 0.0–1.0) and `_DUMP_SECTIONS["compositing"]`. `_zone_pair_ssim` and `_ZONE_PRE_SSIM_THRESH` exported in `__all__`. 5 tests `TestZonePairSsim` in `test_compositing.py`. **5-test benchmark results (2026-06-21, ARAP disabled in test env — no ptlflow):** test04 GT-SSIM=0.680/0.738 (simple_better), test08=0.725/0.810 (simple_better), test09=0.785/0.756 (comparable, ASP better raw), test27=0.698/0.680 (simple_better aligned-SSIM), test57=0.721/0.755 (simple_better). Ghosting scores consistently higher for ASP (test04: 41.2 vs 21.4; test08: 58.8 vs 46.0; test09: 29.1 vs 20.8; test27: 34.6 vs 23.2; test57: 43.6 vs 24.1) — root cause is temporal median ghost-averaging of different animation poses, not seam artifacts. **933 backend tests (9 skipped, 5 pre-existing fg_register failures unchanged).**

**§3.15 (2026-06-18):** Non-anim import isolation — `image_merger.py` had 6 unconditional model imports (BiRefNetWrapper→transformers, LoFTRWrapper→kornia, AnimeStitchPipeline→full anim pipeline; ~3s+ at collection). All replaced with `find_spec()` probes + lazy imports inside `_get_*()` methods and `perfect_stitch()`. `vault_manager.py` `import jpype` wrapped in `try/except ImportError` (`_JPYPE_OK` flag). `check_import_times.py` extended to 16 modules (`CORE_MODULES` group added): `image_merger` 0.50s net, `vault_manager` 0.47s net — both pass 1.5s threshold. 8 image_merger+vault_manager tests pass (0 regressions). Roadmap §3.10 header updated to ✅; anchor index updated.

**§3.14 Phase 3 (2026-06-18):** Import-time sweep — all 14 anim modules now pass the 1.5s threshold (net 0.67–0.80s above baseline, down from 1.6–2.4s). Key fixes: `pipeline.py` 5 heavy wrapper try/except → `find_spec` probes + lazy instantiation (BiRefNetWrapper, LoFTRWrapper, EfficientLoFTRWrapper, ALIKEDLightGlueWrapper, unused AnimeStitchNet removed). `backend/src/models/__init__.py` cleared of all 8 eager wrapper re-exports (only base utilities remain). `fg_register.py` torchvision.models → lazy inside `_get_vgg19_feat()`. `test_canvas.py` pre-existing test bug fixed (RuntimeError→CanvasError). `scripts/check_import_times.py` CI gate green. **917 anim tests pass (0 new failures); 5 pre-existing fg_register failures unchanged.**

**S140 (2026-06-18):** §3.13 ProPainter Stage 4.7 + §2.9A LandmarkEditorDialog + §2.10C user-drawn flow field + test-suite freeze root cause analysis & fix. `_propainter_complete_frames(frames, bg_masks, device)` added to `bg_complete.py` — wraps `ProPainterInference.inpaint()` with NN-fill fallback; wired as Stage 4.7 in `pipeline.py` (`ASP_PROPAINTER=1`, `ASP_PROPAINTER_DEVICE`). `_build_landmark_affine(i, j, pairs, weight)` added to `pipeline.py` — 1 pair: centroid translation; 2 pairs: `estimateAffinePartial2D`; 3+ pairs: `estimateAffine2D` LMEDS. `LandmarkEditorDialog` (~260 lines PySide6) added to `gui/src/dialogs/` with alternating click pairs and color-coded markers; wired into `EdgeReviewDialog` via "Landmark Editor…" button. `_sparse_flow_to_dense(flow_arrows, H, W)` added to `fg_register.py` (RBFInterpolator thin-plate-spline, NN fallback); `register_foreground_at_seam` gains `flow_override` param; `_FlowArrowCanvas` added to `SeamDiagnosticDialog` for user-drawn displacement arrows. **Critical test-freeze fix:** `from diffusers import DiffusionPipeline` moved from module-level in `anim_fill.py` to inside `_load_tooncrafter()` — eliminates 800 MB–1.5 GB HuggingFace import at pytest collection time. Duplicate imports in `compositing.py` (lines 29–32) deduplicated. Root Causes #2–#5 (module-level ML singletons, ThreadPoolExecutor storm, 931× gc.collect(), no process isolation) documented in `performance.md §3.10–§3.14` with CRITICAL priority. 5 new tests `TestProPainterCompleteFrames` → **928 backend tests (2 skipped)**.

**S123 (2026-06-15):** §2.11A Intelligent Scissors Seam Waypoints. `_seam_cut()` in `compositing.py` gains `waypoints: Optional[List[Tuple[int, int]]] = None` parameter — list of `(x, y)` zone-local coordinates that the seam must pass through. Implementation: (1) pre-DP inf-injection: before the DP forward pass, all rows except `y_wp` in column `x_wp` are set to `+inf` in the accumulated-cost matrix `E`, forcing the seam to fan out from the forced pixel rightward; (2) forced traceback: during right→left traceback, column `x_wp` overrides the normal 3-neighbour argmin with `y_wp` directly, ensuring the seam lands exactly on the waypoint even if the traceback arrives from a distant row; (3) post-smooth re-apply: after `_smooth_seam_path` and `_clamp_seam_path`, all waypoint positions are re-stamped onto the path so that smoothing (e.g. `ASP_SEAM_SMOOTH_WINDOW=5`) cannot displace hard constraints. Waypoints threaded through the parallel pre-computation path (`_seam_job` tuple extended to 7-element `(_k, _fa_z, _fb_z, _sem, W, _zh, _wps)`); canvas-space `(x, canvas_y)` waypoints from `seam_overrides[k]["waypoints"]` are converted to zone-local coords via `y_zone = canvas_y - y0_zone` before dispatch. Inline fallback seam cut in the blend loop updated identically. Problem solved: the autonomous DP seam routes through the minimum-energy path which may bisect a character or cross an undesirable region; user-placed waypoints (from the SeamDiagnosticDialog in a future HITL checkpoint extension) can force the seam through a specific background corridor, resolving Category C1 failures without requiring a full re-composite. No env var — waypoints are always honoured when provided; `[]` or `None` is a no-op with identical output to baseline. 5 tests `TestSeamCutWaypoints` in `test_compositing.py` → **777 backend tests (2 skipped)**. GUI 18 unchanged.

**S122 (2026-06-15):** §1.56 Post-Composite Chroma Seam Correction. `_seam_chroma_equalize(canvas, boundaries, band_px, min_shift) → np.ndarray` added to `compositing.py` — natural complement to §1.21 (`_seam_lum_equalize`). Converts reference strip bands above and below each seam boundary to CIE LAB colour space; measures mean shift in the 'a' (green↔red) and 'b' (blue↔yellow) channels; when either shift exceeds `min_shift` LAB units, applies a linear additive ramp over `band_px` rows below the boundary to close the chroma gap. Luminance (L*) is left unchanged (handled by §1.21). Problem solved: `_seam_lum_equalize` applies equal BGR additive offsets (pure luminance shift, chrominance unchanged), so colour-temperature differences (warm interior strip vs cool exterior strip) and hue shifts between adjacent strips are not corrected by §1.21 — they show up as persistent tonal banding even after luminance is equalized. `_SEAM_CHROMA_EQ` bool flag (default OFF; `ASP_SEAM_CHROMA_EQ=1`). Wired in `_composite_foreground` immediately after §1.21 lum-equalize. `SEAM_CHROMA_EQ_BAND_PX=20`, `SEAM_CHROMA_EQ_MIN_SHIFT=3.0` in `constants/anim.py`. `"ASP_SEAM_CHROMA_EQ"` in `_CONFIG_SCHEMA`. `_seam_chroma_equalize` in `__all__`. 5 tests `TestSeamChromaEqualize` in `test_compositing.py` → **772 backend tests (2 skipped)**. GUI 18 unchanged.

**S121 (2026-06-15):** §3.16A StabStitch++ Simplified Trajectory Smoother. `_smooth_affine_trajectory(affines, sigma, iqr_threshold) → (smoothed_affines, was_applied)` added to `pipeline.py` — extracts tx/ty sequences from BA-solved affines, computes IQR of absolute adjacent steps in dominant axis; if `max(IQR_tx, IQR_ty) > iqr_threshold`, applies `scipy.ndimage.gaussian_filter1d(mode='nearest')` independently on both sequences; rotation and scale components copied unchanged; returns `(affines, False)` unchanged when IQR ≤ threshold or sigma=0 or N<3. `_TRAJ_SMOOTH_SIGMA` float module flag (default 0.0=off; `ASP_TRAJ_SMOOTH_SIGMA=1.5`). `_TRAJ_SMOOTH_IQR_THRESH` float flag (default 10.0px; `ASP_TRAJ_SMOOTH_IQR_THRESH`). Gate wired after §1.55 rotation gate and before Stage 7b affine validation. Problem solved: phase-correlation noise on non-linear/multi-axis scroll sequences (deceleration, combined tx+ty drift) produces jitter in BA translations that passes §1.50/§1.52 residual gates but causes Stage 7b ratio/min_gap failures — the 4 confirmed genuine SCANS fallbacks (tests 54, 59, 73, 89) show this pattern. Gaussian smooth with σ≈1.5 frames removes high-frequency jitter while preserving the global pan trajectory. `mode='nearest'` avoids boundary attenuation at the first/last affine. `TRAJ_SMOOTH_SIGMA=1.5`, `TRAJ_SMOOTH_IQR_THRESH=10.0` in `constants/anim.py`. `"ASP_TRAJ_SMOOTH_SIGMA"` and `"ASP_TRAJ_SMOOTH_IQR_THRESH"` in `_CONFIG_SCHEMA`. `_smooth_affine_trajectory` in `__all__`. 5 tests `TestSmoothAffineTrajectory` in `test_pipeline.py` → **767 backend tests (2 skipped)**. GUI 18 unchanged.

**S120 (2026-06-15):** §1.55 BA Affine Rotation Gate. `_compute_max_affine_rotation_deg(affines) → float` added to `pipeline.py` — extracts rotation angle from each 2×3 affine via `arctan2(M[1,0], M[0,0])`; returns max absolute value in degrees; 0.0 for empty list. `_MAX_AFFINE_ROTATION_DEG` float module flag (default 0.0=off; `ASP_MAX_AFFINE_ROTATION_DEG=5.0`). Gate wired between §1.52 BA weighted-mean residual and Stage 7b affine validation: fires when max rotation > threshold → SCANS fallback. Problem solved: LoFTR can latch onto a rotationally-similar texture patch (repeated decorative border, mirrored panel, landscape panel in portrait scroll) producing a valid-looking affine (low BA residual) that encodes a large rotation component — the translation portion is unreliable even though §1.50/§1.52 see no red flags. Pure-scroll captures have near-zero rotation on all affines; anything > 5° is a match error. `MAX_AFFINE_ROTATION_DEG=5.0` in `constants/anim.py`. `"ASP_MAX_AFFINE_ROTATION_DEG"` in `_CONFIG_SCHEMA` (`float, 0.0, 90.0`). `_compute_max_affine_rotation_deg` in `__all__`. 5 tests `TestComputeMaxAffineRotationDeg` in `test_pipeline.py` → **762 backend tests (2 skipped)**. GUI 18 unchanged.

**S110 (2026-06-14):** §1.46 Low-Contrast Frame Pre-Rejection. `_reject_low_contrast_frames(thumbs, paths, contrast_threshold) → (thumbs, paths, n_dropped)` added to `frame_selection.py` — `np.std(thumb * 255.0)` on each grayscale thumbnail; interior frames below threshold dropped; first/last always kept. `_CONTRAST_REJECT_THRESH` float flag (default 0.0=off; `ASP_CONTRAST_THRESH=15.0`). Wired as step 1b-a in `smart_select_frames` between §1.2E blur rejection and hold detection. Problem solved: flash/whiteout panels have near-zero pixel std (≈0–8 lum) — no keypoints for LoFTR, no peak for phase corr; §1.2E Laplacian blur does NOT catch these (a sharp white-flash frame has high Laplacian at its border but zero interior texture). Removing such frames prevents zero-displacement spurious edges from entering the edge graph. `CONTRAST_THRESH=15.0` in `constants/anim.py`; `"ASP_CONTRAST_THRESH"` in `_CONFIG_SCHEMA` `(float, 0.0, None)`; `_reject_low_contrast_frames` in `__all__`. 5 tests `TestRejectLowContrastFrames` in `test_frame_selection.py` → **688 backend tests (2 skipped)**. GUI 18 unchanged.

**S109 (2026-06-14):** §1.45 Canvas Width Ratio Gate. `_compute_canvas_width_ratio(canvas_w, frames) → float` added to `pipeline.py` — `canvas_w / median(frame.shape[1] for frame in frames)`; returns 1.0 for empty frame list. `_MAX_CANVAS_WIDTH_RATIO` float module flag (default 0.0=off; `ASP_MAX_CANVAS_WIDTH_RATIO=1.5`). Gate wired between §1.44 adjacent-gap gate and Stage 9.5 frame-confidence: fires when ratio > threshold; logs canvas_w, ratio, and threshold; SCANS fallback. Problem solved: BA can introduce monotonic tx drift (each frame slightly shifted right) while ty_span still dominates the scroll direction — §3.14 scroll-axis check does NOT fire (vertical scroll), §1.17 span-utilisation only checks vertical span, yet the canvas grows to 2–4× frame width with mostly black side columns. `MAX_CANVAS_WIDTH_RATIO=1.5` in `constants/anim.py`; `"ASP_MAX_CANVAS_WIDTH_RATIO"` in `_CONFIG_SCHEMA` (`float, 0.0, None`); `_compute_canvas_width_ratio` in `__all__`. 5 tests `TestComputeCanvasWidthRatio` in `test_pipeline.py` → **683 backend tests (2 skipped)**. GUI 18 unchanged.

**S108 (2026-06-14):** §1.44 Maximum Adjacent Frame Gap Gate. `_compute_max_adjacent_gap(affines, frames) → float` added to `pipeline.py` — iterates N-1 consecutive pairs; dominant axis determined by comparing ty_span vs tx_span; gap = `ty_{i+1} - (ty_i + H_i)` (vertical) or `tx_{i+1} - (tx_i + W_i)` (horizontal); returns max gap; 0.0 for N<2. `_MAX_ADJACENT_GAP_PX` float module flag (default 0.0=off; `ASP_MAX_ADJACENT_GAP_PX=100.0`). Gate wired after §1.17 canvas-span utilisation and before Stage 9.5 frame-confidence computation: logs gap and threshold, triggers SCANS fallback. Problem solved: §1.17 catches global canvas collapse (small total span) but not the inverse — BA can place two adjacent frames with a large uncovered strip between them while the total span looks correct. §1.39 catches this post-render (expensive); §1.44 fires on pure affine math. `MAX_ADJACENT_GAP_PX=100.0` in `constants/anim.py`; `"ASP_MAX_ADJACENT_GAP_PX"` in `_CONFIG_SCHEMA` (`float, 0.0, None`); `_compute_max_adjacent_gap` in `__all__`. 5 tests `TestComputeMaxAdjacentGap` in `test_pipeline.py` → **678 backend tests (2 skipped)**. GUI 18 unchanged.

**S107 (2026-06-14):** §1.43 Adjacent Edge Coverage Ratio Gate. `_compute_adj_edge_coverage(edges, n_frames) → float` added to `pipeline.py` — counts distinct adjacent pairs `(|i−j|=1)` with ≥1 edge using canonical `(min(i,j), max(i,j))` set keys (duplicates count once), returns `len(covered) / (n_frames - 1)`; vacuously 1.0 for n_frames ≤ 1. `_ADJ_COVERAGE_MIN` float module flag (default 0.0=off; `ASP_ADJ_COVERAGE_MIN=0.60`). Gate wired between §1.16 MST weight gate and Stage 7 BA: fires when flag > 0.0 and coverage < threshold, logs `covered/total` counts, triggers SCANS fallback. Problem solved: §1.15 connectivity and §1.16 MST weight only check global graph structure — a skip-edge-dominated graph (e.g., edges only between frames 0↔2, 1↔3, 2↔4) can pass both while no adjacent pair has a local displacement anchor, causing BA to extrapolate rather than interpolate. `ADJ_COVERAGE_MIN = 0.60` in `constants/anim.py`. `"ASP_ADJ_COVERAGE_MIN"` in `_CONFIG_SCHEMA` (`float, 0.0, 1.0`). `_compute_adj_edge_coverage` in `__all__`. 5 tests `TestComputeAdjEdgeCoverage` in `test_pipeline.py` → **673 backend tests (2 skipped)**. GUI 18 unchanged.

**S106 (2026-06-14):** §1.42 Linear Interpolation Bg Fill. `_linear_interp_zero_bg(canvas, zero_mask) → np.ndarray` added to `bg_complete.py` — per-column, for each unknown row finds the nearest known pixel above (`above_idx = searchsorted(known_rows, r) - 1`) and below (`below_idx = searchsorted(known_rows, r, side="right")`); when both exist, fills with `(1-t)*canvas[r_above] + t*canvas[r_below]` where `t = (r - r_above) / (r_below - r_above)`; when only one side exists, copies that side (NN fallback). Added to `__all__`. Wired in `complete_background()` before `_nn_fill_zero_bg` branch when `_INTERP_BG_FILL` is True. Problem solved: `_nn_fill_zero_bg` hard-copies the nearest known pixel, producing a visible discrete color step at the midpoint between above/below boundary pixels when they differ (common in vertical panoramas that transition from sky to floor). Linear interpolation eliminates this step at negligible cost. `_INTERP_BG_FILL` bool flag (default OFF; `ASP_INTERP_BG_FILL=1`). `"ASP_INTERP_BG_FILL"` in `_CONFIG_SCHEMA` (`int, 0, 1`). 5 tests `TestLinearInterpZeroBg` in `test_bg_complete.py` → **668 backend tests (2 skipped)**. GUI 18 unchanged.

**S105 (2026-06-14):** §1.41 Sequential Gain Chain-Drift Guard. `_check_gain_chain_drift(gains, max_ratio) → bool` added to `rendering.py` — computes `cum = np.prod(gains, axis=0)` (per-channel product of all N gains) then returns `any(|log(cum_c)| > log(max_ratio))`. Called at the end of `_compute_sequential_color_gains` when `_GAIN_DRIFT_MAX > 0.0`; on True, resets `gains` to ones and `biases` to zeros before return (identity = no correction). Rationale: per-pair ±26% clamps (§1.40) cap each step but allow cumulative drift; 10 frames each at the ±26% ceiling could produce a 10× total shift. Real-world case: monotonically dimming scan capture where every pair pushes in the same direction. Better to apply no correction than a wildly drifted chain. Also added `import logging; logger = logging.getLogger(__name__)` to `rendering.py` (the module had no logger). `_GAIN_DRIFT_MAX` float module flag (default 0.0=off; `ASP_GAIN_DRIFT_MAX=2.0`). `GAIN_DRIFT_MAX=2.0` in `constants/anim.py`. `"ASP_GAIN_DRIFT_MAX"` in `_CONFIG_SCHEMA` (`float, 0.0, None`). 5 tests `TestCheckGainChainDrift` in `test_rendering.py` → **663 backend tests (2 skipped)**. GUI 18 unchanged.

**S104 (2026-06-14):** §1.40 Adaptive Gain Clamp for Sequential Colour Correction. `_adaptive_render_gain_clamp(ref_lum: float) → (lo, hi)` added to `rendering.py` — `clamp_width = max(0.14, 0.26 − 0.12 × (ref_lum / 255))`; returns `(1 − w, 1 + w)`. Same continuous formula as §1.4B in `compositing.py` but applied to Stage 9 `_compute_sequential_color_gains`. The fixed [0.88, 1.12] (±12%) clamp was too tight for dark overlap zones (a small absolute delta is a large ratio when ref_lum ≈ 20–40) and slightly too loose for bright scenes. With ASP_ADAPTIVE_RENDER_GAIN=1: dark zones (ref_lum=0) widen to ±26%, bright zones (ref_lum=255) keep ±14%. `_ADAPTIVE_RENDER_GAIN` bool module flag (default OFF; `ASP_ADAPTIVE_RENDER_GAIN=1`). Wired inside the per-channel gain computation replacing `np.clip(median, 0.88, 1.12)` with `np.clip(median, _g_lo, _g_hi)`. `RENDER_GAIN_CLAMP_DARK=0.26`, `RENDER_GAIN_CLAMP_BRIGHT=0.14` in `constants/anim.py`. `"ASP_ADAPTIVE_RENDER_GAIN"` in `_CONFIG_SCHEMA` (`config.py`) as `(int, 0, 1, ...)`. 5 tests `TestAdaptiveRenderGainClamp` in `test_rendering.py` → **658 backend tests (2 skipped)**. GUI 18 unchanged.

**S103 (2026-06-14):** §1.39 Render Canvas Coverage Fraction Gate. `_compute_render_coverage(valid_mask: np.ndarray) → float` added to `pipeline.py` — `float((valid_mask > 0).sum()) / float(total)`; returns 0.0 for empty mask. *valid_mask* is the uint8 map produced by `_render` (255=covered, 0=uncovered). Gate wired between Stage 10.2 (bg fill) and Stage 10.5 (multi-frame row gate): when `_RENDER_MIN_COVERAGE > 0.0` and fraction < threshold → SCANS fallback. Catches the case where BA collapses all frames into a small overlap clump leaving most canvas untouched — such renders pass Stage 10.5 row-coverage check within the dense zone yet leave 60–70% of canvas black. Stage 10.5 requires ≥2-frame coverage per row (animation ghost suppression); §1.39 requires the canvas to be covered at all (geometry sanity). Complementary — §1.39 fires first for total geometry failure; Stage 10.5 fires for single-frame-only coverage. `_RENDER_MIN_COVERAGE` float module flag (default 0.0=off; `ASP_RENDER_MIN_COVERAGE=0.30` recommended). `RENDER_MIN_COVERAGE=0.30` in `constants/anim.py`. `"ASP_RENDER_MIN_COVERAGE"` in `_CONFIG_SCHEMA` (`config.py`). `_compute_render_coverage` exported in `__all__`. 5 tests `TestComputeRenderCoverage` in `test_pipeline.py` → **653 backend tests (2 skipped)**. GUI 18 unchanged.

**S102 (2026-06-14):** §1.38 LoFTR Background Match Ratio Gate. `_compute_bg_match_ratio(n_bg_pts: int, n_total_pts: int) → float` added to `matching.py` — returns `float(n_bg_pts) / max(1, n_total_pts)`; 0.0 when `n_total_pts == 0`. `n_loftr_total = len(pts1)` captured before bg-filtering block in `_match_pair`. After bg filtering, when `_LOFTR_BG_RATIO_MIN > 0.0` and `bg_ratio < threshold`, rejects LoFTR edge by setting `pts1 = np.empty((0,2))` so `if len(pts1) >= 20` fails and M stays None (falls through to ALIKED/template-match/phase-corr). Catches fg-dominated pairs where n_bg ≥ 20 but n_bg/n_total is tiny (5–10%): those sparse bg matches are spatially clustered and produce a noisy median displacement even after passing the §1.20 minimum count check. `_LOFTR_BG_RATIO_MIN` float module flag (default 0.0=off; `ASP_LOFTR_BG_RATIO_MIN=0.15` recommended). `LOFTR_BG_RATIO_MIN=0.15` in `constants/anim.py`. `"ASP_LOFTR_BG_RATIO_MIN"` in `_CONFIG_SCHEMA` (`config.py`). `_compute_bg_match_ratio` exported in `__all__`. 5 tests `TestComputeBgMatchRatio` in `test_matching.py` → **648 backend tests (2 skipped)**. GUI 18 unchanged.

**S101 (2026-06-14):** §1.37 Background Pixel Coverage Fraction Gate. `_compute_bg_coverage_fraction(bg_masks: List[Optional[np.ndarray]]) → float` added to `pipeline.py` — iterates all non-None masks, computes `(mask > 127).sum() / mask.size` for each, returns the mean; returns 1.0 when the list is empty or all entries are None so the gate never fires when BiRefNet masking is disabled. Wired between Stage 4 (BiRefNet masking) and Stage 4.5 (photometric normalisation) as `§1.37: Background pixel coverage fraction gate` comment block. When `_MIN_BG_FRACTION > 0.0` and `_bg_frac < _MIN_BG_FRACTION`, logs `[Stitch] §1.37: bg coverage fraction … < … — fg-dominant scene, bg normalisation unreliable → SCANS fallback.` and returns `_scan_stitch_fallback()`. Rationale: BiRefNet-masked bg phase correlation, BA edge weighting, and Stage 4.5 mean-bg normalization all silently degrade when fg dominates the scene (< 5% bg pixels); with near-zero bg signal, mean-bg scaling amplifies noise and LoFTR bg-subset matching becomes meaningless. `_MIN_BG_FRACTION` float module flag (default 0.0=off; `ASP_MIN_BG_FRACTION=0.05` recommended). `MIN_BG_FRACTION=0.05` in `constants/anim.py`. `"ASP_MIN_BG_FRACTION"` in `_CONFIG_SCHEMA` (`config.py`) with range `(float, 0.0, 1.0, ...)`. `_compute_bg_coverage_fraction` exported in `__all__`. 5 tests `TestComputeBgCoverageFraction` in `test_pipeline.py` → **643 backend tests (2 skipped)**. GUI 18 unchanged.

**S100 (2026-06-14):** §1.36 LoFTR Translation Consensus Spread Filter. `_compute_translation_spread(pts_i, pts_j) → (mad_dx, mad_dy)` added to `matching.py`. Computes the Median Absolute Deviation (MAD) of per-match displacement vectors `(dx, dy)` around their median. When LoFTR finds many correspondences but they scatter around different translation hypotheses (foreground animation polluting bg matches, repeated background elements confusing the matcher), the median is between modes and wrong. `_MATCH_SPREAD_CEIL` float module flag (default 0.0=off; `ASP_MATCH_SPREAD_CEIL=30.0` recommended). Wired in translation path of `_match_pair`: after computing `dx, dy = np.median(dxs, dys)` and building M, immediately checks `max(_mad_dx, _mad_dy) > _MATCH_SPREAD_CEIL` — if triggered, sets `M = None` and logs the rejection, causing the pipeline to fall through to template match or phase correlation. `MATCH_SPREAD_CEIL=30.0` in `constants/anim.py`. `"ASP_MATCH_SPREAD_CEIL"` in `_CONFIG_SCHEMA` (`config.py`). `_compute_translation_spread` exported in `__all__`. 5 tests `TestComputeTranslationSpread` in `test_matching.py` → **638 backend tests (2 skipped)**. GUI 18 unchanged.

**S99 (2026-06-14):** §1.35 Line-Art Gradient Penalty in Seam Cost Map. `_fg_gradient_cost(canvas_zone, weight=1.0) → np.ndarray` added to `compositing.py`. Computes normalized Laplacian magnitude (values in [0, weight], shape (H, W)) on the canvas zone blend. Anime character outlines are dark, thin, high-gradient lines; a DP seam bisecting an outline pixel creates a visible hairline break. Fast-path: returns zero array when `canvas_zone.size == 0` or `weight <= 0.0`; also returns zeros when `lap_max < 1e-6` (flat zone, avoids division by zero). Wired into `_build_seam_cost_map()` after exclusion-mask injection, before `return cost`. Activation condition: `_LINE_GRAD_WEIGHT > 0.0 and canvas_zone.size > 0`; for fg-interior pixels (`cost >= 1.0`), adds `grad[pixel]` (in [0, weight]) to cost so character outline pixels are more expensive than flat fill when the DP is forced through the character body. Background pixels (cost = 0 or 0.5) are unaffected — the gradient penalty only fires for fg-interior pixels. `_LINE_GRAD_WEIGHT` float module flag (default 0.0=off; `ASP_LINE_GRAD_WEIGHT=1.0` recommended). `LINE_GRAD_WEIGHT=1.0` in `constants/anim.py`. `"ASP_LINE_GRAD_WEIGHT"` in `_CONFIG_SCHEMA` (`config.py`). `_fg_gradient_cost` exported in `__all__`. 5 tests `TestFgGradientCost` in `test_compositing.py` → **633 backend tests (2 skipped)**. GUI 18 unchanged.

**S98 (2026-06-14):** §1.34 Seam Zone Texture-Energy Pre-Escalation. `_seam_zone_texture_energy(fa, fb, boundary, half_band=30) → float` added to `compositing.py` — measures mean Laplacian variance in the ±30px band around the seam boundary across both warped BGR (or grayscale) frames. Returns 0.0 for empty/degenerate bands. Low values indicate flat-colour zones where optical flow / ARAP is unreliable (aperture problem: no gradient signal for flow to track). `_SEAM_LOW_TEXTURE_THRESH` float module-level flag (default 0.0=off; `ASP_SEAM_LOW_TEXTURE_THRESH=5.0` recommended). `SEAM_LOW_TEXTURE_THRESH=5.0` in `constants/anim.py`. `"ASP_SEAM_LOW_TEXTURE_THRESH"` in `_CONFIG_SCHEMA` (`config.py`). When triggered: picks dominant pose by fg-pixel count in ±feather-band, adds to `seam_single_pose`, stores texture score in `seam_post_diffs[k]`, prints `flat-zone single-pose` diagnostic. Wired between the §1.20 tight-step `continue` and the `register_foreground_at_seam` ARAP call in the FG-registration loop (`_composite_foreground`). `_seam_zone_texture_energy` exported in `__all__`. 5 tests `TestSeamZoneTextureEnergy` in `test_compositing.py` → **628 backend tests (2 skipped)**. GUI 18 unchanged.

**S97 (2026-06-14):** §1.2E Blur/Artifact Frame Pre-Rejection. `_reject_blurry_frames(thumbs, paths, blur_threshold, thumb_size=64) → (filtered_thumbs, filtered_paths, n_dropped)` added to `frame_selection.py`. Resizes each interior grayscale float32 thumbnail to 64×64 uint8 and computes `cv2.Laplacian(gray_u8, cv2.CV_32F).var()`. Frames with Laplacian variance < `blur_threshold` are dropped before hold detection; first/last frames always kept to preserve canvas extent. `_BLUR_REJECT_THRESH` float module flag (default 0.0=off; `ASP_BLUR_REJECT_THRESH=50.0` to enable). `BLUR_REJECT_THRESH=50.0` in `constants/anim.py`. `"ASP_BLUR_REJECT_THRESH"` in `_CONFIG_SCHEMA` (`config.py`). Wired as step 1a-b in `smart_select_frames()` between §1.2D temporal-variance filter and step 1b hold detection. Exported in `__all__`. 5 tests `TestRejectBlurryFrames` in `test_frame_selection.py` → **623 backend tests (2 skipped)**. GUI 18 unchanged.

**S96 (2026-06-14):** §2.4C Seam Zone Crop Extraction. `_extract_seam_crops(canvas, boundaries, band_px=SEAM_CROP_BAND_PX) → Dict[int, np.ndarray]` added to `compositing.py` — crops ±`band_px` rows around each seam boundary from the final composite result, clamped to canvas bounds (edge seams produce narrower crops rather than raising an error). Result stored as `seam_crops` key in `seam_meta_out` alongside `boundaries`, `seam_post_diffs`, `seam_single_pose`. `SEAM_CROP_BAND_PX=50` in `constants/anim.py`. `_extract_seam_crops` exported in `__all__`. `gui/src/dialogs/seam_diagnostic_dialog.py`: `_SeamCard.__init__` gains `crop: Optional[np.ndarray] = None` param; when a crop is provided, `_make_crop_pixmap(crop, max_width=300, max_height=64)` renders it as a `QLabel` thumbnail below the info row (INTER_AREA resize, BGR→RGB→QPixmap); outer layout switched from `QHBoxLayout(self)` to `QVBoxLayout(self)` with nested `QHBoxLayout()`; card `setMinimumHeight` expanded by 70px when crop shown. `SeamDiagnosticDialog` extracts `seam_crops = data.get("seam_crops", {})` and passes `crop=seam_crops.get(k)` to each `_SeamCard`. 5 tests `TestSeamCropExtraction` in `test_compositing.py` → **618 backend tests (2 skipped)**. GUI 18 unchanged.

**S95 (2026-06-13):** §2.4A Seam Registration Inspector (HITL Checkpoint 4.6). `_composite_foreground()` in `compositing.py` extended with `seam_meta_out: Optional[dict]` (populated on return with `{"boundaries": list, "seam_post_diffs": dict, "seam_single_pose": dict}`) and `seam_overrides: Optional[dict]` (maps seam index k → `{"force_single_pose": bool, "force_blend": bool}`). `force_single_pose` skips ARAP and immediately sets `seam_single_pose[k]` with sentinel diff 99.0; `force_blend` removes k from `seam_single_pose` as a post-loop override. `AnimeStitchPipeline._composite_foreground()` wrapper updated. `StitchWorker`: `sig_review_seams = Signal(object)` (checkpoint 4.6); `set_seam_override(overrides)` setter; `"seams"` in `_signal_map`; HITL checkpoint 4.6 block runs initial composite, collects `_seam_meta`, emits `sig_review_seams`, re-composites with overrides when accepted; checkpoint 4.5 restructured with `_cp45_iter` guard to skip initial re-composite. `gui/src/dialogs/seam_diagnostic_dialog.py` (new): `_SeamCard` (per-seam card — index label, boundary y, coloured post_diff, SP badge, mutually-exclusive "Force SP"/"Force blend" checkboxes) + `SeamDiagnosticDialog` (canvas preview + scrollable seam cards sorted worst-first + legend + Accept && Continue/Cancel; `get_overrides()` returns non-default seams). `stitch_tab.py`: `sig_review_seams → _on_hitl_review_seams()` handler (opens `SeamDiagnosticDialog`; calls `set_seam_override()` + `resume()` on Accept; `cancel()` on Reject). 5 tests `TestSeamMetaOut` in `test_compositing.py` → **613 backend tests (2 skipped)**. GUI 18 unchanged. (S96 extended `seam_meta_out` with `seam_crops` key and updated `SeamDiagnosticDialog` to display thumbnails.)

**S94 (2026-06-13):** §2.4B Seam Overlay on Output Image. `_annotate_seams(canvas, boundaries, seam_post_diffs, seam_single_pose, line_thickness=2) → np.ndarray` added to `compositing.py`. Draws coloured horizontal diagnostic lines at each seam boundary on the composite: green (post_diff < 10.0), amber (10 ≤ diff < 22.0), red (diff ≥ 22.0 or seam in single-pose fallback). Small text label `S{k}:{diff:.0f}` (plus "SP" for escalated seams) at left edge. `_SEAM_OVERLAY` flag (default OFF, `ASP_SEAM_OVERLAY=1`). `SEAM_OVERLAY_AMBER_THRESH=10.0` and `SEAM_OVERLAY_RED_THRESH=22.0` in `constants/anim.py`. `"ASP_SEAM_OVERLAY"` in `_CONFIG_SCHEMA`. Wired after `_seam_lum_equalize` at end of `_composite_foreground()`. `_annotate_seams` in `__all__`. 5 tests `TestAnnotateSeams` → **608 backend tests (2 skipped)**.

**S93 (2026-06-13):** §2.14 Triangular Consistency Filter. `_triangular_consistency_filter(edges, max_residual_px) → List[Dict]` added to `pipeline.py`. For every triangle (i→j, j→k, i→k) present in the edge graph, computes L2 residual between predicted hypotenuse displacement (sum of two shorter legs) and observed hypotenuse; penalises the weakest edge (weight × `TRI_CONSISTENCY_PENALTY=0.5`) when residual > threshold. Addresses the gap where wrong adjacent edges were not questioned by the geometric consistency filter — which only tests skip edges. Edge penalisation (not dropping) preserves the edge for BA at reduced trust. Gated by `_TRI_CONSISTENCY_MAX_RESIDUAL` (default 0.0=off; enable: `ASP_TRI_CONSISTENCY=80.0`). `TRI_CONSISTENCY_MAX_RESIDUAL=80.0` and `TRI_CONSISTENCY_PENALTY=0.5` added to `constants/anim.py`. `"ASP_TRI_CONSISTENCY"` added to `_CONFIG_SCHEMA` in `config.py`. `TRI_CONSISTENCY_PENALTY` imported from constants in `pipeline.py`. Wired in `_filter_edges()` after `_reject_static_edges` and before geometric consistency filter. `_triangular_consistency_filter` exported in `__all__`. 5 new tests in `backend/test/anim/test_filter_edges.py::TestTriangularConsistencyFilter` → **603 tests passing** (2 skipped).

**S92 (2026-06-13):** HITL Session Viewer. `gui/src/dialogs/hitl_session_viewer_dialog.py` (new): `_list_sessions()` (mtime-sorted), `_load_session_meta()` (JSON without numpy decode), `_format_session_info()` (human-readable checkpoint summary with `_CHECKPOINT_LABELS` map); `HITLSessionViewerDialog` — QSplitter list/detail, Load-for-Replay / Delete (QMessageBox confirm + unlink) / Export (shutil.copy2) / Refresh; `selected_path()` accessor; `session_dir` param for testability. `stitch_tab.py`: "Browse Sessions…" button + `_on_browse_sessions()`. 8 new GUI tests in `test_hitl_session_viewer_dialog.py` → **18 GUI tests**. Backend 598 unchanged.

**S91 (2026-06-13):** Canvas Inspector Rotation/Scale Editor. `_rot_angles: List[float]` + `_scale_factors: List[float]` per-frame lists added to `CanvasInspectorDialog`; `QDoubleSpinBox` for rotation (±180°, step 0.5°) and scale (0.1–3.0, step 0.01) in right panel; `_update_transform_controls()` populates spinboxes on frame select; `_on_rot_changed(val)` / `_on_scale_changed(val)` update list + call `setRotation()`/`setScale()` on drag item; `_DraggableFrameItem.__init__` calls `setTransformOriginPoint(fw/2, fh/2)` for center-pivot rotation; `_reset_frame()` resets rot/scale to 0°/1.0 and calls item setters; `adjusted_affines()` applies `R(θ,s) @ orig_2x2` before adding tx/ty nudge. 5 new tests `TestCanvasInspectorRotScale` → **10 GUI tests in test_canvas_inspector_dialog.py**. Backend 598 unchanged.

**S90 (2026-06-13):** Canvas Inspector Drag-to-Reposition. `gui/src/dialogs/canvas_inspector_dialog.py`: new `_DraggableFrameItem(QGraphicsRectItem)` — `ItemIsMovable | ItemSendsGeometryChanges | ItemIsSelectable`; `itemChange(ItemPositionChange)` writes `nudge_list[idx] = [new_x − base_tx, new_y − base_ty]`; `itemChange(ItemSelectedChange)` calls `on_select(idx)` to sync list widget; thumbnail pixmaps as child items (`setParentItem()`) move with frame rect; `_populate_scene()` creates `_DraggableFrameItem` instances; `_scene.selectionChanged → _on_scene_selection_changed()` for live tx_label update; `_on_list_row_changed() → _sync_scene_selection()` highlights matching scene item; `_nudge()` uses `QSpinBox` step (range 1–200, default 10) and calls `setPos()` on drag item; `_reset_frame()` likewise. `gui/test/test_canvas_inspector_dialog.py` (new): 5 tests `TestCanvasInspectorDrag` — identity no-nudge, nudge updates affines, drag `setPos()` updates nudge via `itemChange`, reset zeroes nudge, spinbox controls step amount. **+5 GUI tests**. Backend: 598 passing (unchanged).

**S89 (2026-06-13):** HITL Checkpoint 2 — Manual Edge Entry. `_build_manual_edge(i, j, dx, dy, weight=0.9) → dict` added to `pipeline.py` (pure-translation M, single-point pts, method="manual", weight clipped [0,1], exported). `edge_review_dialog.py`: `_ManualEdgeDialog` (i/j spinboxes bounded by n_frames, dx/dy, weight 0.9 default); `EdgeReviewDialog` gains `_manual_edges` list, `_n_frames`, "Add Edge…" button; manual edges rendered purple dotted in graph + purple table rows (always-on); `accepted_edges()` returns filtered originals + manual. `StitchWorker` Checkpoint 2: manual-method edges in override list → `_build_manual_edge()` → full pipeline edge (exc caught). Bugfix: `_on_hitl_review_edges()` was calling `EdgeReviewDialog(edges=..., image_paths=...)` with wrong kwargs — fixed to `EdgeReviewDialog(data=data, ...)`. 5 tests `TestBuildManualEdge` → **598 tests passing**.

**S88 (2026-06-13):** HITL Session Persistence & Replay. `backend/src/anim/hitl_session.py` (new): `_encode_array`/`_decode_array` (numpy ↔ base64-JSON, 8 MB skip threshold); `save_session(overrides, path)` writes `{version, timestamp, checkpoints}` JSON; `load_session(path)` restores with numpy arrays decoded; `autosave_path()` timestamped path under `~/.config/image-toolkit/hitl_sessions/`. `StitchWorker`: `session_path` param → loads replay dict at init; `_hitl_session_overrides` accumulates non-cancel overrides; autosaves after Stage 13 success; `current_session_path` property; `save_session(path)` public method. `_make_hitl_pause_cb()` / `_hitl_video_pause()` in replay mode (hitl_mode=False, replay dict non-empty): return stored override without emitting signal or blocking. `stitch_tab.py`: "Load Session…" button + label; `_on_load_session()` file dialog; `_on_stitch_finished()` shows session path. 9 new tests in `test_hitl_session.py` → **593 tests passing**.

**S87 (2026-06-13):** HITL Checkpoint 5 — Final Output RLHF Feedback. `StitchWorker`: `sig_review_output = Signal(object)` (checkpoint 5); `set_output_feedback(overall_rating, annotations)` setter; `"output"` in signal map; checkpoint 5 block after Stage 13 — downsamples composite, calls `_hitl_pause("output", ...)`, on resume calls `FeedbackStore.add_from_image()` with `StitchAnnotation` list (lazy import; exception caught and logged). `final_output_review_dialog.py` (new): `_AddFlawDialog` — flaw_type QComboBox + severity QDoubleSpinBox; `FinalOutputReviewDialog` — canvas preview + overall-quality slider (0–10 in 0.5 steps) + flaw annotation list + "Save Feedback && Continue" / "Skip". `stitch_tab.py`: `sig_review_output → _on_hitl_review_output()`. 7 new tests in `test_rlhf_feedback.py` (FeedbackStore JSONL roundtrip, add, multi-record, add_from_image, empty iter, malformed-line tolerance) → **584 tests passing**.

**S86 (2026-06-13):** HITL Checkpoint 4.5 — Post-Composite Seam Painter. `_composite_foreground()` gains `paint_mask: Optional[np.ndarray] = None` — canvas-space uint8 mask merged into `_eff_exclusion` list before seam-job loop (cost=1e6 hard barrier in painted pixels). `AnimeStitchPipeline._composite_foreground()` wrapper passes it through. `StitchWorker` `sig_review_composite` + `set_paint_mask()` + `"composite"` in signal map + HITL re-composite loop (runs Stage 11 repeatedly until user accepts or cancels). `seam_painter_dialog.py` (new): `_PaintCanvas(QLabel)` with red overlay + left/right drag + alpha mask; `SeamPainterDialog` with brush slider + iteration label + "Re-Composite"(2)/Accept/Cancel; `full_resolution_mask()` upscales via INTER_NEAREST. `stitch_tab._on_hitl_review_composite()` wired. 5 new tests `TestPaintMask` → **577 tests passing**.

**S85 (2026-06-13):** HITL Checkpoint 3.5 — Interactive Seam Boundary Editor. `_compute_initial_boundaries(affines, frames) → np.ndarray` extracted to `compositing.py` as a public helper (midpoint formula); `_composite_foreground()` gains `preset_boundaries: Optional[np.ndarray] = None` — overrides auto-computed midpoints when provided with `len == N-1`; `AnimeStitchPipeline._composite_foreground()` wrapper passes it through. `StitchWorker`: `sig_review_boundaries = Signal(object)` + `set_boundary_override(boundaries)` + HITL checkpoint 3.5 block between Stage 10 and Stage 11 (computes initial boundaries, emits canvas preview, applies user override as `preset_boundaries`). `gui/src/dialogs/boundary_editor_dialog.py` (new): `_DraggableLine(QGraphicsLineItem)` (constrained vertical drag) + `BoundaryEditorDialog` (QGraphicsScene/View canvas preview with N-1 red dashed draggable lines + frame labels + "Reset to Auto" + `adjusted_boundaries()`). `stitch_tab.py` wired with `_on_hitl_review_boundaries()`. 5 new tests `TestComputeInitialBoundaries` → **572 tests passing**.

**S84 (2026-06-13):** Video ingestion HITL + "From Video" GUI mode. `StitchWorker.__init__` gains `video_path`, `video_n_frames`, `video_mode` params; `sig_review_video = Signal(object)` is HITL checkpoint 0; `_hitl_video_pause(data)` pauses on `_hitl_mutex`/`_hitl_wait` and emits `sig_review_video`; `run()` ingests video via `ingest_video()` into `mkdtemp`, calls `_hitl_video_pause()` in HITL mode, then applies `frame_override` from user selection; final `_video_tmp_dir` cleaned up in `finally`. `SelectionReviewDialog` gains configurable `title` param for reuse in video frame review. `stitch_tab.py`: "From Video Source" `QCheckBox` in Source Frames group; hidden `_video_input_widget` (path QLineEdit + browse button + frame-count spinbox); `_on_video_mode_toggled()` shows/hides widget, enables/disables frame-list buttons; `_browse_video()` opens file dialog (mp4/mkv/avi/mov/webm/flv); `_start_stitch()` validates video path OR frame count, connects `sig_review_video → _on_hitl_review_video` when HITL+video; `_on_hitl_review_video()` launches `SelectionReviewDialog` with `title=f"Video Frame Review — {vname}"`. 5 new GUI tests in `TestStitchWorkerVideoPath` (`gui/test/test_stitch_tab.py`) → backend anim suite **567 tests passing** (2 skipped, unchanged).

**S83 (2026-06-13):** Live SAM-2 state preservation across HITL checkpoint boundary (fixes S81 known limitation). `_compute_fg_masks_sam2_stateful()` + `_cleanup_sam2_state()` added to `masking.py` — stateful variant uses `mkdtemp()` (not TemporaryDirectory), skips `reset_state`/`del predictor`, returns `(masks, predictor, inference_state, tmp_dir, H, W)` 6-tuple; fallback paths return `None` state with correct mask list. `AnimeStitchPipeline.__init__` gains `_sam2_predictor/_sam2_inference_state/_sam2_tmp_dir/_sam2_frame_h/_sam2_frame_w`; `_compute_fg_masks()` calls stateful variant and stores tuple on `self`; `_cleanup_sam2_state()` method calls masking module cleanup + zeroes attributes. HITL checkpoint 1.5 data dict in `_ProgressPipeline.run()` now includes `sam2_predictor/sam2_inference_state/sam2_frame_h/sam2_frame_w`; `_cleanup_sam2_state()` called immediately after `_hitl_pause` returns (before Stage 5). `_refine_cb` in `stitch_tab._on_hitl_review_masks` now calls `_refine_masks_with_clicks(predictor, state, ...)` with the live state when SAM-2 is active; falls back to `list(orig_masks)` when predictor is None. 10 new tests in `backend/test/anim/test_masking.py` → **567 tests passing** (2 skipped).

**S82 (2026-06-13):** HITL end-to-end wiring + Issue 9 video ingestion. `exclusion_masks` threaded through `AnimeStitchPipeline` instance attribute → Stage 11 → `_composite_foreground`; `AnimeStitchPipeline._composite_foreground()` method updated. `StitchWorker.set_exclusion_masks()` + `self._exclusion_masks` storage; applied to pipeline before `run()`; HITL checkpoint 1.5 reads `"exclusion_masks"` from override. `MaskReviewDialog` seam-exclusion section: GroundingDINO detect button + `sig_exclusion_masks_accepted` signal + `exclusion_masks()` accessor. Data serialization auto-save at HITL checkpoint 1.5 (COCO + Label Studio JSON → `~/.image-toolkit/hitl_annotations/`). `video_ingestion.py` (new): `VideoIngestionStream` + `ingest_video()` — PyAV proxy-first decode, telecine dedup, uniform/keyframe/smart selection, full-res per-frame decode, `pip install av` graceful fallback. 15 new tests → **557 tests passing** (2 skipped).

**S81 (2026-06-13):** Multi-modal HITL (Issue 10). `backend/src/anim/data_serialization.py` (new) — `COCOAnnotationBuilder` (fg segmentation, seam-exclusion, frame-selection annotations; atomic JSON write) + `LabelStudioExporter` (model predictions + human annotations arrays for RLHF delta) + `create_session_serializers()` factory. `backend/src/anim/grounding.py` (new) — lazy GroundingDINO wrapper (`_detect_objects`, `_detect_best_box`, `_detect_exclusion_mask`); graceful ImportError fallback; `GROUNDING_DINO_CKPT`/`CFG` env vars. `masking.py` extended: `_compute_fg_masks_grounded_sam2()` (DINO bbox + SAM-2 propagation, BiRefNet per-frame fill, exception fallback) + `_refine_masks_with_clicks()` (pos/neg click → SAM-2 re-propagate). `compositing.py` extended: `_build_seam_cost_map()` + `_composite_foreground()` gain `exclusion_masks: Optional[List[np.ndarray]]` param — masks auto-resized, cost=1e6 hard barrier for NL seam routing. `gui/src/dialogs/mask_review_dialog.py` (new) — `MaskReviewDialog` with `_ClickOverlay` (left=pos, right=neg SAM-2 prompts) + `_RefinementWorker(QThread)`. `stitch_worker.py` — `sig_review_masks` signal + `set_mask_override()` + HITL checkpoint 1.5. 44 new tests → **542 tests passing**.

**S80 (2026-06-13):** §1A per-pair Otsu bg-only phase correlation (`_otsu_bg_mask_pair()` in `frame_selection.py`, `ASP_OTSU_BG_CORR=1`). §5A/C background zero-coverage fill (`complete_background()` in new `bg_complete.py`; NN fill default, ProPainter hook when installed; Stage 10.2 in `pipeline.py`, `ASP_BG_COMPLETE=1/2`). §8 recommended defaults shipped in `asp_config.toml` (8 flags enabled: ADAPTIVE_SP_SOFT/THRESH, SEAM_SMOOTH_WINDOW, SEAM_MARGIN, SEAM_FG_PENETRATION_MAX, ZONE_MIN_HEIGHT, SEAM_INSTABILITY_THRESH, STATIC_INPUT_MAX_MAD). `anim/__init__.py` auto-loads TOML before module flags are read. SAM-2 wiring completed (`ASP_USE_SAM2=1` in `pipeline.py`). Issue report marked with implementation status. 498 tests passing.

**S79 (2026-06-13):** HITL staged execution architecture shipped: `QWaitCondition` pause/resume in `StitchWorker`; 4 checkpoint signals (frames/edges/canvas/render); 4 new dialog files in `gui/src/dialogs/` (SelectionReviewDialog, EdgeReviewDialog, CanvasInspectorDialog, CoverageHeatmapDialog); "Human-in-the-loop review" checkbox in stitch panel. Algorithm improvements: §1D fg-masked DINOv2 crop (Otsu bbox before embedding), §3.1A AnimeInterp SGM full (`_animeinterp_sgm()` in `fg_register.py`, `ASP_ANIMEINTERP_SGM=1`), §5.2 SAM-2 video masking (`_compute_fg_masks_sam2()` in `masking.py`). 487 tests passing.

---

## 1. The Core Problem

The Anime Stitch Pipeline (ASP) assembles a character's full body from sequential frames of an anime pan shot — frames where the character is only partially visible in any single frame. The fundamental challenge that every other problem traces back to:

> **The character is *animating* while the camera pans.** Frames captured 300–800 ms apart show the same camera position offset but with the character in a completely different animation pose. A rigid translation model aligns the *background* perfectly but leaves body parts in mismatched poses on either side of every strip seam.

Concretely: when frames `a` (at time *t*) and `b` (at time *t+400ms*) are placed adjacent on the canvas, the background panels behind the character are pixel-perfect, but the character's arm in `a` is reaching to the left while in `b` it's pointing right. The seam cuts through both → the canonical torn/doubled-edge artifact.

This is *structurally* the same problem as ghost-free HDR imaging (multiple exposures of a moving person) or video super-resolution (aligning frames with moving objects). The established solution is: **measure optical flow → warp moving content toward a reference → fuse**. The ASP now implements this, but with anime-specific complications: flat cel shading creates the aperture problem for flow estimation, and line-art must not be bent by the warp.

---

## 2. What Is Currently Implemented

### 2.1 Smart Frame Selection

**Files:** `backend/benchmark/bench_anime_stitch.py` → `_smart_select_frames()`;  `backend/src/anim/frame_selection.py` → `smart_select_frames()` (pipeline-usable backend module added in session 3)

Source datasets contain 58–333 consecutive video frames at ~42ms intervals. The selector reduces these to ~5–37 frames per dataset for pipeline processing. Four rejection gates:

1. **Displacement sufficiency**: frame is kept only when cumulative background camera displacement ≥ 50px from last selected frame (ensures new canvas area is revealed).
2. **Direction consistency**: backward-direction frames are not counted as forward progress. Frames that re-expose already-covered canvas rows (where character animation has changed) are skipped.
3. **High-animation / low-movement filter**: frame is dropped if displacement < 8px but thumbnail MAD > 0.10 (camera nearly stationary, character animating heavily).
4. **Phase-correlation quality gate**: pairs with response < 0.04 (motion blur, scene cut) are skipped.

**Architecture (two-pass, session 3):** Pass 1 runs the v1 greedy selection above. Pass 2 (disabled by default) scans ±2 frames around each selected frame for a pose-consistent alternative. See §4.8 for why Pass 2 previously failed and §2.11 for DINOv2 (session 8) which replaces the gradient metric.

**DINOv2 submodular selection (§3.3, session 8):** When `ASP_POSE_WINDOW_PX > 0` and ≥3 frames are selected in Pass 1, Pass 2 uses `_compute_dinov2_features()` — `dinov2_vits14` loaded via `torch.hub.load` with module-level `_DINOV2_CACHE` to avoid repeated loads. Returns (N, 384) L2-normalised feature vectors. In Pass 2, the `_pose_dist(i, j)` helper replaces `_fg_center_diff`: uses `1 − dot(feat_i, feat_j)` (cosine distance). Falls back to `_fg_center_diff` when DINOv2 is unavailable. Model weights are pre-downloaded at `~/.cache/torch/hub/facebookresearch_dinov2_main/`.

**Backend module (`frame_selection.py`):** Extracted to `backend/src/anim/frame_selection.py` as a clean, pipeline-usable API so the GUI and pipeline can call `smart_select_frames()` without re-implementing the logic.

**Corpus result:** 16,329 raw frames → 1,692 selected (10× reduction, ~18 per dataset). Selection takes ~1.8s per dataset on CPU using parallel thumbnail loading + OpenCV phase correlation.

**Animation hold detection (§1.11, session 6):** `_detect_hold_blocks(thumbs, hold_threshold=0.025)` in `frame_selection.py` groups consecutive frames with MAD < threshold into the same hold block. Within-hold pairs skip `phaseCorrelate` (response set to synthetic 1.0). Default `ASP_HOLD_THRESHOLD=0.025`.

**Hold refinement (§1.11C, session 38):** `_refine_hold_ids_by_response(hold_ids, responses, 0.85)` runs after the phase-correlation loop (step 3b). Cross-hold pairs whose `phaseCorrelate response >= 0.85` are near-identical frames that MPEG noise caused MAD to split incorrectly; they are merged back into the same hold block. IDs renumbered consecutively. Default `ASP_HIGH_HOLD_RESPONSE=0.85`. `HIGH_HOLD_RESPONSE_THRESH=0.85` in `constants/anim.py`.

**Temporal variance pre-filter (§1.2D, session 39):** `_temporal_variance_filter(thumbs, paths, sigma_threshold)` in `frame_selection.py`. Wired as step 1a (before hold detection). For each interior frame i, computes mean per-pixel variance of the (i-1, i, i+1) thumbnail triplet in [0,1] space. If variance < threshold, the frame carries no new motion information and is dropped pre-matching. Default disabled (`ASP_TEMPORAL_VAR_THRESH=0.0`). `TEMPORAL_VAR_THRESH=1e-3` in `constants/anim.py`.

**Known limitation:** Phase correlation measures whole-frame displacement including character animation, so a "50px camera step" may actually be 5px camera + 45px limb swing. The two-channel BiRefNet-based refinement was implemented but regresses results (see §4.2) because it changes which frames are selected. Gradient-based pose refinement (session 3) also regresses due to confounding by background structure (see §4.10).

---

### 2.2 Pipeline Stages (fully implemented)

The 13-stage pipeline in `backend/src/anim/pipeline.py`:

| Stage | What it does | Key file |
|---|---|---|
| 1 | Load, trim, dark-border detection | `canvas.py` |
| 2 | Width normalisation (Lanczos-4) | `canvas.py` |
| 3 | BaSiC flat-field correction (optional) | `photometric.py` |
| 4 | **BiRefNet foreground masking** | `masking.py` |
| 4.5 | Background photometric normalisation (bg-only, scalar, ±7%) | `pipeline.py` |
| 5–6 | Pairwise matching (EfficientLoFTR → ALIKED+LightGlue → Template Match → Phase Correl → RoMa) + edge filter | `matching.py` |
| post-6 | Spatial dedup: drop consecutive frames with displacement < 25px | `pipeline.py` |
| 7 | Translation-only global bundle adjustment (LM, 2-pronged outlier rejection) | `bundle_adjust.py` |
| 7b | Affine validation gate (ratio < 3, min_gap > adaptive_floor px, rotation/scale checks); §0.5C adaptive floor = `max(20, canvas_span/(N×3))` | `validation.py` |
| 8 | SEA-RAFT / ECC sub-pixel refinement | `ecc.py`, `flow_refine.py` |
| **8.5** | **Foreground pose registration** (Stage 8.5 — the new core feature) | `fg_register.py` |
| 9 | Canvas construction + bidirectional midplane | `canvas.py` |
| **10** | **Foreground-excluded temporal median** (A5) | `rendering.py` |
| **11** | **Foreground assembly composite** (Laplacian blend + DSFN seam + semantic cost routing) | `compositing.py` |
| 12.5 | **Scroll-axis-aware content trim** (Session 7) | `pipeline.py` |
| 13 | Morphological crop | `canvas.py` |

---

### 2.3 Foreground Pose Registration (Stage 8.5) — The Core Fix

**File:** `backend/src/anim/fg_register.py`

After warping to canvas coordinates (background aligned), the residual optical flow on the foreground IS the animation motion `A_animation`. For each adjacent strip seam:

**Flow estimation:**
- Primary: **RAFT** (`sea_raft_s@things` via ptlflow) — pretrained on optical flow datasets, confident over flat regions where DIS's gradient-based estimation fails (aperture problem). Computed on the seam-band crop only (±`taper_px` + 16px, downscaled to max 1280px side) to avoid VRAM OOM on 2000+ px canvases.
- Fallback: **OpenCV DISOpticalFlow** (MEDIUM preset, no extra dependency).
- Toggle: `ASP_FLOW_ENGINE=dis` env var.

**ARAP Push phase (session 4 addition, Sýkora 2009 §3.2):**
`_arap_push(img_a, img_b, fg_mask, initial_flow, cell_size=16, search_range=24)` — per-cell SAD block matching to find better rigid translations BEFORE the Regularise phase smooths them. The Push phase decouples neighbouring cells so each can independently jump to its local appearance optimum. Critical for flat cel-shaded regions where RAFT/DIS gradient-based flow is ambiguous (aperture problem). The research report (§9.1) identified this as "crucially omitted" from the original implementation. Enable/disable: `ASP_ARAP_PUSH=1` (default) / `=0`. Unit tests: `TestARAPPush` in `backend/test/anim/test_fg_register.py`.

**ARAP regularisation (A3, Sýkora 2009 §3.1):**
`_arap_regularise(flow, fg_mask, cell_size=16, n_iter=2, image=None, image_offset=(0,0))` — fits per-cell (16×16px) rigid median translations to the fg flow, then bilinearly interpolates back to pixel space via `scipy.interpolate.RegularGridInterpolator`. Prevents raw per-pixel flow from bending straight line-art strokes by enforcing a smooth, locally-rigid warp field. Now called AFTER the Push phase (Push → Regularise = full Sýkora algorithm).

**LSD collinearity term in ARAP (§0.1/A3, session 8):** After the bilinear interpolation loop, OpenCV `createLineSegmentDetector(0)` is run on the seam-band crop passed via `image=crop_a`. Two guards prevent regressions: (1) **boundary-cell only** — only cells containing BOTH fg AND bg pixels get the LSD constraint (interior cells have diagonal stripe texture that confused the detector); (2) **50% magnitude guard** — `if proj_mag < orig_mag * 0.5: skip` — vertical line segments would project horizontal flow to zero, failing the threshold and being ignored. The call site in `register_foreground_at_seam()` passes `image_offset=(y0_crop, 0)` for vertical pans and `(0, x0_crop)` for horizontal, converting LSD coordinates to canvas space. 3 new tests: `TestArapRegulariseLSDCollinearity` in `test_fg_register.py`.

**Symmetric midpoint warp:**
Frame `a` moves by `+0.5·flow` (toward `b`) and frame `b` by `-0.5·flow` (toward `a`). This halves the maximum distortion applied to either frame (StabStitch++ bidirectional principle). The warp is tapered to zero at ±`taper_px` (220px) from the seam so it only affects the boundary zone.

**Single-pose fallback (A6):**
When `med_residual > FG_REG_MAX_RESIDUAL` (90px): the animation gap is too large to warp safely. The *dominant frame* (more foreground pixels in the seam band) is recorded; the compositor takes the seam-zone foreground from it exclusively — no blending of two different poses.

**Post-warp ghost-prevention escalation:**
After the warp, `post_warp_diff` measures mean foreground colour difference in a narrow strip at the seam centre. If `post_warp_diff > 22 lum units` even after warping (pose still significantly different), escalates to the single-pose fallback to prevent the Laplacian blend from creating a double-image ghost.

**Boundary safety:**
- `BORDER_CONSTANT` (not `BORDER_REPLICATE`) prevents edge-smear artifacts.
- `adj[~valid_content] = 0` prevents warp from extending pixels into previously-empty canvas regions.

---

### 2.4 Foreground-Excluded Temporal Median (A5)

**File:** `backend/src/anim/rendering.py`

The Stage-9 temporal median now uses **background pixels only** (from BiRefNet masks) to build the background plate. Where a canvas pixel has no background sample across any frame (character always there), it falls back to the geometric median.

This prevents the median from averaging different animation poses of the character into a translucent ghost on the background plate. Stage 11 then composites properly-registered foreground over the clean background.

Verified by 3 unit tests: `backend/test/anim/test_rendering.py::TestForegroundExcludedMedian`.

---

### 2.5 Composite Quality Gate (post-Stage-11)

**File:** `backend/benchmark/bench_anime_stitch.py`

After Stage 11 completes, measures the final composite:
- `seam_coherence`: std of per-row mean luminance (horizontal banding proxy, lower = better)
- `strip_banding`: max luminance jump between adjacent frame-strip entry zones

If `seam_coherence > 38` OR `strip_banding > 30` → fall back to SCANS on the pre-processed frames. This catches composites where the temporal median plate was already severely banded (typical for animated-video scenes where A5 can't find clean background).

On the 96-test corpus: **39/96 tests (41%) triggered the gate**. These are scenes where the character fills most of the frame with high-amplitude animation — the temporal median is inherently inadequate.

---

### 2.6 Affine Validation (min_gap threshold)

**File:** `backend/src/anim/validation.py`

Threshold lowered from 50px to **25px** (vector magnitude `sqrt(dy² + dx²)`, not axis-specific). This rescued ~9 tests that were unnecessarily rejected when the diagonal displacement exceeded 25px per axis but < 50px total.

---

### 2.7 Benchmark Infrastructure

**File:** `backend/benchmark/bench_anime_stitch.py`

- **Selective runner**: `--tests`, `--range`, `--first N`, `--skip-done` flags
- **Ground-truth comparison**: SSIM/PSNR vs `data/ground_truth/` reference images (55 of 96 tests)
- **Seam coherence metric**: replaces misleading Laplacian sharpness
- **GT-based verdict**: `asp_better` / `simple_better` / `comparable` from GT SSIM
- **Aligned-SSIM (session 8)**: `_compute_aligned_ssim()` in `bench_anime_stitch.py` — `cv2.findTransformECC(MOTION_EUCLIDEAN)` aligns the output to the GT before computing SSIM, removing scale/framing bias. Stored as `aligned_ssim_vs_gt` in result dicts. Falls back to raw SSIM if ECC diverges. This is the "true content quality" ceiling (test27: 0.748 aligned vs 0.709 raw — the 0.039 delta is purely scale mismatch).

Available via `just asp-benchmark-verify` (5 test quick-check) or `just asp-benchmark` (full 96-test run).

---

### 2.8 Supporting Infrastructure

- **SEA-RAFT / RAFT flow** (`flow_refine.py`): overlap-zone-only flow for background sub-pixel refinement (Stage 8)
- **Confidence-weighted temporal median**: LoFTR-aligned frames outweigh template-match frames
- **DSFN soft-seam weight** (`compositing.py`): spatially-adaptive Laplacian blend width (photometric similarity → wide blend in flat background, narrow in character outline)
- **Semantic seam routing**: BiRefNet edge-confidence cost in the DP seam-finding prevents seams from bisecting character outlines
- **Both-content Laplacian**: Laplacian blend only where both frames have actual canvas content; single-frame-only zones take that frame directly (avoids ringing at canvas boundaries)
- **Inter-strip colour coherence guard**: skips per-strip photometric normalization when adjacent strips differ by > 20 lum units (prevents normalization from amplifying colour mismatch)
- **ToonCrafter** (`anim/anim_fill.py`): anime-style generative inbetweening — wired to worst seam in `compositing.py` via `ASP_TOONCRAFTER_SEAM=1` (session 9); see §2.15
- **SRStitcher** (`anim/sr_stitcher.py`): diffusion-based seam/border inpainting (`sr_mode=True`)
- **Real-ESRGAN anime_6B** (`anim/super_res.py`): post-process 2–4× upscaling
- **Unit tests**: **292 passing** in `backend/test/anim/` (S37: +5 `TestFilterHighConfEdges`; S36: +5 `TestAdaptiveMinGap`; S35: +5 `TestGhostingScoreV2`; S34: +5 `TestComputeAdaptiveMinDisp`; S33: +10 `TestSeamCostColumnFilter`/`TestDetectScrollAxisModule`; S32: +5 `TestRejectStaticEdges`; earlier sessions: fg_register, rendering, bundle_adjust, filter_edges, affine_validation, frame_selection, bench_metrics, config, pipeline, canvas, compositing)
- **New metrics**: `ghosting_siqe` (§3.8A) added to `_compute_all_metrics` alongside `ghosting_score`, `seam_visibility`, `rlhf_score`
- **New pipeline functions**: `_filter_high_conf_edges` (pipeline.py §2.9C), `_compute_adaptive_min_gap` (validation.py §0.5C), `_compute_adaptive_min_disp`, `_reject_static_edges`, `_spatial_dedup_frames`, `_compute_row_coverage`, `_detect_scroll_axis` (from canvas), `_panorama_stitch_fallback`, `_telea_fill_gaps`

---

### 2.9 Alignment Stability Gate (session 5 — pre-render)

**Files:** `backend/benchmark/bench_anime_stitch.py`, `backend/src/anim/pipeline.py`

Before the temporal render, checks whether the assembled canvas has unreliable horizontal alignment:

- **Metric**: 75th-percentile of `|dx_steps|` where `dx_steps[i] = |affine_tx[i+1] - affine_tx[i]|`
- **Threshold**: 50px (disable via `ASP_ALIGN_GATE_DX=99`)
- **Action on fire**: fall back to SCANS on width-normalised frames (better than trying to composite with incoherent background plate)

**Why this helps:** Tests with 2D/diagonal camera motion (test08, test25) have alternating large horizontal offsets (±100px per step). The translation-only canvas model places frames at different horizontal positions, making the temporal median background incoherent. Previous behaviour: the render gate fired AFTER spending 2.5s on compositing; new behaviour: falls back immediately (before rendering, saving 2.5s).

**Results:** test08: +0.074 (0.736 → 0.809, simple_better → **asp_better**), test25: +0.049 (0.697 → 0.746). Both now use SCANS-on-normalised-frames as the output, which scores better than the ASP composite was producing.

**Calibration:** Pure vertical pans (test09: 75th-pct |dx| ≈ 0.5px) never fire. Good ASP tests (test17, test84, test44) never fire. Only genuinely irregular 2D-motion tests fire.

---

### 2.10 Fg Pixel L1 Pose Metric (session 5)

**Files:** `backend/src/anim/frame_selection.py`, `backend/benchmark/bench_anime_stitch.py`

Upgraded `_fg_center_diff()` from gradient-weighted L1 (confounded by background) to **fg pixel L1 with per-frame gain normalisation**:

- Hard-thresholds the BiRefNet fg mask (`> 0.3`) to binary `fg_bin`
- Zeroes out all background pixels in both thumbnails before comparison
- Independently normalises each thumbnail's fg pixels (zero mean, unit std) to remove inter-frame gain variation
- Result: background pixels contribute exactly 0 — camera-panning locker/wall structure cannot influence the score

**Previous problem (gradient approach):** `np.dot(gradient_diff.ravel(), fg_mask.ravel())` — gradient is computed on the FULL image, then dot-producted with the soft fg_mask. Background pixels with mask weight 0.05–0.1 still contributed proportionally, causing the selector to confound pose change with background scroll.

**Session 5 results (with `ASP_POSE_WINDOW_PX=80`):**
- test27: 0.709 → 0.719 (**+0.010** — meaningful improvement)
- test09: 0.787 → 0.788 (+0.001 — marginal, GT-coupling limits further gain)

**Status:** Pose selection remains disabled by default (`ASP_POSE_WINDOW_PX=0`). GT-coupling still causes some regressions (test04 regressed -0.024 with ±2 range, test57 regressed -0.015). With DINOv2 (S8) the pose metric is now background-agnostic. Enable via `ASP_POSE_WINDOW_PX=80` for experiments.

---

### 2.11 Hold Detection (session 6)

**File:** `backend/src/anim/frame_selection.py` → `_detect_hold_blocks()`

Detects "animation hold" blocks — consecutive frames where the character is frozen (minimal per-pixel MAD). Hold blocks indicate the animator held a pose for multiple frames; within-hold pairs contribute near-zero animation residual, so warping them is unnecessary.

- **Algorithm:** FD-Means — for each consecutive thumbnail pair, compute MAD. If `MAD < hold_threshold` (default `ASP_HOLD_THRESHOLD=0.025`) → same block. Returns start indices of each block.
- **Integration in smart_select_frames:** Within-hold pairs skip phase correlation in Pass 2; Pass 2 prefers candidates from *different* hold blocks (cross-hold candidates have guaranteed animation change, making hold boundary detection more reliable).
- **Env var:** `ASP_HOLD_THRESHOLD=0.025` (set to 0 to disable)

---

### 2.12 GNC Robust Loss in Bundle Adjustment (session 6)

**File:** `backend/src/anim/bundle_adjust.py`

Bundle adjustment (`scipy.optimize.least_squares`) now uses `loss='cauchy', f_scale=10.0` instead of the default linear loss. The Cauchy (M-estimator) loss down-weights large residuals, making the BA solver robust to outlier matches that survived the edge filter. This prevents a single bad match from biasing the camera model.

- **Override:** `ASP_BA_F_SCALE=<float>` env var (default 10.0)
- **Why Cauchy not Huber:** Cauchy has heavier tails at intermediate residuals (5–30px), which matches the noise profile of remaining anime-texture mismatches better.

---

### 2.13 SLIC SGM Proxy in fg_register (session 6)

**File:** `backend/src/anim/fg_register.py` → `_slic_sgm_proxy()`

Superpixel centroid tracking for flat cel-shaded regions where per-pixel flow (RAFT/DIS) fails due to the aperture problem. SLIC segments the seam-band crop into `n_segments=200` superpixels, then matches segment centroids between frame A and frame B using colour+position similarity. The centroid displacements are used as the initial flow estimate for the ARAP Push phase.

- **Enable:** `ASP_SGM_PROXY=1` (default OFF — still experimental)
- **Why not default ON:** In regions with fine line-art, SLIC over-segments and the centroid matching adds noise. The benefit is concentrated in large uniform-colour areas (skin, solid costume panels) where it replaces genuinely wrong RAFT flow.

---

### 2.14 Stage 12.5 Scroll-Axis Content Trim (session 7)

**File:** `backend/src/anim/pipeline.py` (between Stage 12 and Stage 13)

Trims canvas rows or columns where no foreground character content is present in any frame, reducing the assembled panorama to the character's actual extent. This addresses the test27 scale mismatch (2× output vs GT) without the axis-confusion bug of the earlier character bounding-box crop (§4.4).

**Key design — scroll-axis awareness:** Determines dominant scroll direction from the affine translation spread (`ty_range` vs `tx_range`). Trims only in the SCROLL AXIS (vertical trim for vertical pans, horizontal for horizontal pans). Never trims the cross-axis — avoids removing valid background extent.

**Implementation:**
1. Warp all fg masks to canvas space using the pipeline's affines
2. Compute the union of warped fg masks (`fg_union_canvas`)
3. Find the outermost rows (or cols) with any fg content
4. Crop canvas + valid_mask to `[fg_row_first - 20px : fg_row_last + 20px]` (20px padding)

- **Env var:** `ASP_CONTENT_TRIM=1` (default ON; set to `0` to disable)
- **Expected gain:** test27: raw SSIM +0.010–0.039 by reducing scale mismatch

---

### 2.15 ToonCrafter Seam Synthesis (session 9)

**File:** `backend/src/anim/compositing.py`

Wires `_generate_canonical_cel()` from `anim/anim_fill.py` to the **single worst seam** (max `post_warp_diff` among single-pose-escalated seams). Instead of the hard dominant-frame partition, a synthesised intermediate pose is used for the fg pixels at that seam, structurally eliminating the most severe ghost.

**Design — bound inference cost to 1 seam:** Only the worst seam triggers ToonCrafter inference. Typical clips have 8–15 seams; inferring on all would be 8–15× slower for marginal gain on lower-residual seams.

**Tracking:** `seam_post_diffs: dict` records `post_warp_diff` per seam in the fg-register loop (for warped seams) and `float(info.get("residual", 0.0))` for fallback seams. After the loop: `worst_k = max(seam_single_pose, key=lambda k: seam_post_diffs.get(k, 0.0))`.

**In the Laplacian blend loop:** `seam_canonical_crops.get(k)` is checked; if a canonical cel is available AND the seam is single-pose-escalated, the synthesised cel replaces the dominant frame's fg in the blend zone. Gaps in the synthesised cel (transparency/black) are filled from the dominant frame.

- **Env var:** `ASP_TOONCRAFTER_SEAM=1` (default OFF — requires GPU for inference)

---

### 2.16 Seam DP Vectorization (session 10)

**File:** `backend/src/anim/compositing.py` — `_seam_cut()`

Replaced the W_e-iteration Python forward pass with `scipy.ndimage.minimum_filter1d(E[i-1], size=3, mode='constant', cval=np.inf)`. This C-level kernel computes the 3-neighbour row minimum in a single compiled pass, eliminating two per-iteration numpy array allocations (`left`, `right`). The traceback also replaced Python list construction + `argmin` over a Python list with a NumPy slice-argmin (`E[i, j_lo:j_hi].argmin()`). Expected speedup: 5–10× for Stage 11.

**Also fixed in S10:**
- Dead S8 `_compute_dinov2_features(thumbs: List[np.ndarray])` definition removed from `frame_selection.py` (was silently shadowed by S9 version; tests now test the real S9 path-based API)
- `_TOONCRAFTER_SEAM_ENABLED` NameError at compositing.py:743 corrected to `_TOONCRAFTER_SEAM`
- `test_compositing.py` and `test_canvas.py` fixed: `_FEATHER_MAX`/`_FEATHER_MIN`/`_FEATHER_TABLE`/`_CANVAS_MAX_DIM` imported with wrong underscore prefix; now properly aliased from `backend.src.constants`
- `TestDINOv2Features` rewritten to test S9 API (file paths in, not numpy arrays); uses `tmp_path` pytest fixture + `cv2.imwrite`

**Test count:** 141 passing (was 107; 34 additional tests previously failed at collection due to the import errors above).

---

### 2.17 Fallback Elimination — Comparative Gates + Validation Retry Chain (session 11)

**Files:** `backend/benchmark/bench_anime_stitch.py`, `backend/src/anim/compositing.py`, `backend/src/anim/pipeline.py`

**Objective:** Reduce 51 SCANS fallbacks to the irreducible minimum (cases where SCANS genuinely produces better output).

**Changes shipped:**

1. **Comparative render gate**: Limits are now `max(floor, scans_value * 2.0)` instead of absolute thresholds. `_SC_FLOOR=38`, `_SB_FLOOR=35` as absolute minimums. `ASP_GATE_SC` / `ASP_GATE_SB` env vars for override. Key insight: many tests have inherently high-variance content; what matters is whether ASP is worse than SCANS, not whether it exceeds an absolute threshold.

2. **Alignment gate → advisory**: The `75th-pct |dx| > limit` check in `bench_anime_stitch.py` no longer raises `RuntimeError`. Default threshold in `pipeline.py` raised from 50px → 200px (`ASP_ALIGN_GATE_DX`). Tests with diagonal/2D motion proceed to the comparative render gate.

3. **Validation Retry 4**: `_validate_affines(_seq, min_step=3.0, max_ratio=10.0, max_rotation=0.3, max_scale_dev=0.3)`. For slow-pan sequences with fine-grained sampling — test48 (min_gap=6.8px), test14 (19.1px), test78 (5.0px), test13 (ratio=10.73), test66 (ratio=3.84).

4. **Validation Retry 5**: `min_step=0.5, max_ratio=50.0, max_rotation=0.5, max_scale_dev=0.5`. For extreme-clustering cases where the sequential chain itself has ratio > 10 (test77 ratio=27.0). Added diagnostic print when Retry 4 fails.

5. **GhostGate absolute floor**: `_ghost_limit = max(_GHOST_ABS_FLOOR=40.0, ratio_limit * sim_ghost)`. Prevents false positives when both outputs have low ghosting in absolute terms. test81 (asp=30.5 < 40.0) and test82 (asp=37.4 < 40.0) now pass. Env var: `ASP_GATE_GHOST_FLOOR`.

6. **`seam_post_diffs` init fix** (`compositing.py`): `seam_post_diffs: dict = {}` was missing from declarations. Its absence caused a NameError on first assignment inside the FG-registration try block, silently skipping the entire FG pose registration step on every run.

**Benchmark results:**

| Metric | S10 | S11 |
|--------|-----|-----|
| SCANS fallbacks | 51/96 | 4/96 |
| Validation retries needed | 3 | 5 |

*4 confirmed genuine SCANS cases: test54 (2D drift, sb=56.0 >> limit 36.0), test59 (sc=50.2 >> limit 38.0), test73 (sequential chain ratio=18.4, sb=68.3 >> 35.0), test89 (sb=122.3 >> 48.7).*

---

### 2.18 Adaptive Feather Refinement + Parallel Seam DP (session 12)

**Files:** `backend/src/anim/compositing.py`, `backend/test/anim/test_compositing.py`

**Objective:** Improve Laplacian blend quality using per-seam FG registration quality signal, and reduce seam DP wall-clock time via parallelism.

**Changes shipped:**

1. **Adaptive feather refinement** (inserted after FG registration block, before Laplacian blend):
   - `seam_post_diffs[k] < 8.0` → widen feather 1.5× (cap at `FEATHER_MAX=300`). Excellent ARAP alignment → broad, smooth blend.
   - `seam_post_diffs[k] > 16.0` → narrow feather 0.75× (floor at `FEATHER_MIN=80`). Poor alignment → tight cut to prevent ghosting.
   - Seams in `seam_single_pose` (diff > 22, already escalated) are skipped.
   - Overlap cap re-applied after modification: `_max_f = max(5, min(_nat_ov // 2, FEATHER_MAX))`.
   - Requires the `seam_post_diffs` init fix from S11 — this was the first session where adaptive feather could actually fire.
   - Observed: test09 and test27 — all 19–20 seams had post_diff 2–8; all feathers widened from overlap-capped 250px to 300px.

2. **Parallel seam DP pre-computation** (inserted after hard-partition loop):
   - Zone arrays + `sem_cost` maps collected for all boundaries into `_seam_jobs`.
   - `len(_seam_jobs) > 1`: dispatch via `concurrent.futures.ThreadPoolExecutor(max_workers=min(N-1, 4))`.
   - Single-boundary (N=2): inline path, no executor overhead.
   - Results stored in `_precomp_paths: dict` keyed by boundary index k.
   - Blend loop: `path_local = _precomp_paths.get(k)` with inline fallback for misses.
   - Thread safety: `warped_norm` is read-only; `result` is complete before pre-compute block; `.copy()` on zone slices prevents aliasing.

**Benchmark results:**

| Metric | S11 | S12 |
|--------|-----|-----|
| SCANS fallbacks | 4/96 | 4/96 (unchanged) |
| Tests passing (anim suite) | 141 | 149 |
| Adaptive feather | inactive (seam_post_diffs was always empty) | active — all low-diff seams widened |
| Seam DP | sequential | parallel (max 4 workers) |

---

### 2.19 Multi-Frame Canvas Coverage Gate (session 13)

**Files:** `backend/src/anim/pipeline.py`, `backend/test/anim/test_canvas.py`

**Objective:** Implement §0 item 2 — fall back to SCANS when temporal median coverage is too sparse to suppress animation ghosting.

**Changes shipped:**

1. **`_compute_row_coverage(affines, frames, canvas_h)`** — pure helper function at module level in `pipeline.py`. Computes per-row frame coverage by summing frame extents derived from `affines[i][1,2]` (ty) + `frames[i].shape[0]`. Returns `(row_cov, pct_multi, median_cov)`.

2. **Stage 10.5 coverage gate** — inserted after Stage 10 (temporal render), before Stage 11 (fg composite). Calls `_compute_row_coverage()`, logs `N_multi/N_total rows (pct%)` diagnostic, then falls back to SCANS when `pct_multi < ASP_COV_MIN_MULTI_PCT` (default `0.30`). Conservative default prevents false positives: all 92 currently-passing tests have dense overlap well above 30%. The gate catches genuinely degenerate cases (e.g., 2 frames separated by nearly the full canvas height) where the temporal median is just "first-frame-wins" and compositing would amplify ghosting.

**Unit tests:** 6 tests in `TestComputeRowCoverage` — fully-overlapping frames, non-overlapping, dense stack, output shape, empty canvas, non-negative counts.

| Metric | S12 | S13 |
|--------|-----|-----|
| Tests passing (anim suite) | 149 | 155 |
| §0 items complete | 3 | 4 (item 2 ✅) |

---

### 2.20 Soft-Edge Single-Pose Seam (session 15)

**Files:** `backend/src/anim/compositing.py`, `backend/test/anim/test_compositing.py`

**Objective:** Reduce the visible hard color step at single-pose escalated seams without reintroducing the double-image ghosting that single-pose was designed to prevent.

**Problem:** Single-pose seams (escalated when `post_warp_diff > 22 lum units` after FG registration) use a binary partition: dominant frame fills fg pixels it owns, other frame fills only where dominant has no content. The transition from one frame's content to the other's shows as an abrupt color/brightness step at the DP seam line, perceptible at differences as small as 10–20 lum units.

**Changes shipped:**

1. **`_single_pose_soft_edge(dom_zone, oth_zone, path_local, apply_mask, sp_soft_px)`** — standalone helper added before `_composite_foreground`. Computes per-pixel distance to the seam path, applies a linear blend weight `w_oth = clip(1 − dist/sp_soft_px, 0, 1) × 0.5` in the band, and returns a modified copy of `dom_zone`. Maximum blend at seam centre: 50% other. Outside the band: pure `dom_zone`. Only pixels where both frames have non-zero content AND `apply_mask` is True are modified. Added to `__all__` for testability.

2. **Wired into single-pose composite branch** (`_composite_foreground`): after the hard `take_dom`/`take_oth` fill, `_single_pose_soft_edge()` is called and written back via `_both_for_sp = dom_has & oth_has & fg_apply` mask. This mask ensures `_sp_zone` values outside the blend band (which equal `dom_zone`) don't overwrite `take_oth` pixels. Controlled by `ASP_SP_SOFT_PX` (default 6, set to 0 to disable).

3. **7 unit tests** (`TestSinglePoseSoftEdge` in `test_compositing.py`): shape/dtype, disabled at sp_soft_px=0, seam row 50/50 blend, outside-band pixels unchanged, in-band values strictly between dom and oth, apply_mask=False → no modification, zero oth content → no modification.

| Metric | S14 | S15 |
|--------|-----|-----|
| Tests passing (anim suite) | 163 | 170 |
| Single-pose seam rendering | hard binary cut | ±6px path-guided linear ramp |

---

### 2.21 Seam Band Color Matching (session 16)

**Files:** `backend/src/anim/compositing.py`, `backend/test/anim/test_compositing.py`

**Objective:** Reduce the residual color step at single-pose seams after S15's ±6px blend by normalising the channel means of the two zones before blending.

**Problem:** S15 applies a 50%-max linear ramp at the seam. If `post_warp_diff = 30 lum`, the blend at the seam centre is still `0.5 × 30 = 15 lum` — visible. The mean colour difference between dom_zone and oth_zone at the seam band is the root cause.

**Changes shipped:**

1. **`_seam_color_match(dom_zone, oth_zone, path_local, band_px)`** — standalone helper before `_single_pose_soft_edge` in `compositing.py`. Computes per-channel mean of content pixels within `band_px` rows of `path_local` in each zone, then adds `delta = dom_mean − oth_mean` to oth_zone's band pixels. Clips to [0, 255]. Degenerate case (< 10 content pixels in either zone's band): returns oth_zone unchanged.

2. **Wired before S15 in single-pose branch**: `_oth_matched = _seam_color_match(dom_zone, oth_zone, path_local, _sp_soft_px + 4)`, then `_sp_zone = _single_pose_soft_edge(dom_zone, _oth_matched, ...)`. The `+4` margin ensures the normalization band is slightly wider than the blend band, so the blend ramp fades into a already-matched colour profile. `take_oth` (non-overlap) pixels still use the ORIGINAL `oth_zone`.

3. **7 unit tests** (`TestSeamColorMatch`): output shape/dtype, zero band unchanged, band pixels at dom mean, outside-band unchanged, identical zones no shift, degenerate zone unchanged, per-channel delta applied independently.

**Combined S15+S16 effect**: residual seam step = within-band colour variance (typically < 5 lum), down from `post_warp_diff` (~22–50 lum). Well below human perceptual threshold (~10 lum).

| Metric | S15 | S16 |
|--------|-----|-----|
| Tests passing (anim suite) | 170 | 177 |
| Worst-case seam step | ±50% post_warp_diff | within-band variance (~5 lum) |

---

### 2.22 Per-Pixel DSFN Blend Ramp + Adaptive Boundary Search (session 17)

**Files:** `backend/src/anim/compositing.py`, `backend/test/anim/test_compositing.py`

**Objective:** Improve Laplacian blend quality on mixed-content zones (background + character in same column) and reduce boundary search computation for pure vertical-scroll sequences.

**Changes shipped:**

1. **Per-pixel DSFN blend ramp** (`_soft_seam_weight`): Removed the `col_sim = sim_diffused.mean(axis=0)` column-aggregation step. `ramp` is now `(zone_h, W)` float32 derived directly from `sim_diffused`, giving each pixel its own blend width. Before S17, all rows in a column shared the same ramp derived from the column's mean similarity — a character-edge row at the bottom of an otherwise-background column was forced into a wide blend. After S17, that row gets a narrow ramp (its own low similarity) while the background rows above get wide ramps.

2. **Adaptive boundary search range** (`_find_optimal_boundaries`): `_effective_range = 100` when `ptp(tx_spreads) < 5.0` (pure vertical scroll), else `SEARCH_RANGE=250`. Saves ~60% of candidate evaluations for sparse sequences. Zero quality impact: optimal boundary is always within ±50px of midpoint for pure vertical scroll.

**6 unit tests** (`TestSoftSeamWeight`): shape/dtype, values in [0,1], weight≈0.5 at seam for identical frames, weight≈1.0 far above seam, weight≈0.0 far below seam, similar frames → wider blend zone than different frames.

| Metric | S16 | S17 |
|--------|-----|-----|
| Tests passing (anim suite) | 177 | 183 |
| DSFN ramp granularity | per-column mean | per-pixel (full 2D) |
| Boundary search (pure vertical) | ±250px | ±100px (−60% candidates) |

---

### 2.23 Per-Pair Coherence Gate + §1.4A Adaptive Gain Clamp (session 18)

**Files:** `backend/src/anim/compositing.py`, `backend/test/anim/test_compositing.py`

**Objective:** Improve photometric normalization accuracy by (1) only skipping normalization for frames directly in bad adjacent pairs (not the entire sequence), and (2) widening the Stage 11 gain clamp to cover residuals left by Stage 4.5.

**Changes shipped:**

1. **`_coherence_skip_mask(order, frame_lums, coherence_limit=20.0) → List[bool]`**: New standalone helper. Returns a per-frame bool array. For each adjacent pair in canvas order whose luminance diff exceeds `coherence_limit`, marks both frames as skip-normalization. Other frames remain unaffected. Previously a single bad pair triggered a global `_skip_normalization = True` that excluded every frame in the sequence.

2. **`_adaptive_gain_clamp(ref_lum, frame_lum) → float`** (§1.4A): New standalone helper. Dark scenes (`ref_lum < 80`) clip gain to `[0.82, 1.22]` (±18%); normal scenes clip to `[0.88, 1.14]` (±14%). Replaces the hardcoded `np.clip(..., 0.93, 1.07)` (±7%). Stage 4.5 applies ±14–20% before warping; for frames where Stage 4.5 hit its ceiling, the after-warp residual can be 6–12% — the wider Stage 11 clamp bridges this fully.

3. **Normalization block updated**: `_composite_foreground` now calls `_coherence_skip_mask()` and `_adaptive_gain_clamp()`. Print reports per-pair skip count.

**11 unit tests**: `TestAdaptiveGainClamp` (5): normal clamp at 0.88/1.14, dark clamp at 0.82/1.22, unclamped small correction, threshold at 80, zero frame_lum protection. `TestCoherenceSkipMask` (6): all-good none skipped, bad pair both skipped, good frames after bad pair not skipped, None lum pair ignored, exactly-at-limit not skipped, non-identity order correct.

| Metric | S17 | S18 |
|--------|-----|-----|
| Tests passing (anim suite) | 183 | 194 |
| Coherence guard scope | global skip (all frames) | per-pair (bad pair only) |
| Stage 11 gain clamp | ±7% fixed | ±14% (normal) / ±18% (dark) |

---

### 2.24 §1.6A Tiered Seam Cost (session 19)

**Files:** `backend/src/anim/compositing.py`, `backend/test/anim/test_compositing.py`

**Objective:** Give the DP seam path-finder a gradient between the character body and clean background, instead of treating the edge buffer zone equally to the interior.

**Change shipped:** In `_build_seam_cost_map`, Tier 2 (edge buffer) cost changed from `1.0` → `0.5`:

```python
# Before S19
cost = np.maximum(cost, (dilated > 0).astype(np.float32))

# After S19
cost = np.maximum(cost, (dilated > 0).astype(np.float32) * 0.5)
```

Energy levels with `sem_weight=200`:
- fg body interior: 1.0 × 200 = 200
- edge buffer (bg pixels within `dilate_px` of fg boundary): 0.5 × 200 = 100
- clean background: 0.0 × 200 = 0 (+ photometric energy 10–50)

Before S19 the edge buffer cost was also 200 — identical to body interior. The DP had no incentive to route through the buffer toward background. After S19 the buffer costs 100 (same order as photometric background energy), creating a gradient that pulls the DP toward background corridors.

`_build_seam_cost_map` added to `__all__` and is now directly importable.

**7 unit tests** (`TestSeamCostMap`): all-bg=0, all-fg=1, edge-buffer=0.5, pure-bg-far=0, fg interior stays 1.0 (not lowered), None masks=0, union of two frames both cost 1.0.

| Metric | S18 | S19 |
|--------|-----|-----|
| Tests passing (anim suite) | 194 | 201 |
| Seam DP Tier 2 (edge buffer) cost | 1.0 (= interior) | 0.5 (half interior) |
| DP gradient levels | 2 (fg / bg) | 3 (interior / buffer / bg) |

---

### 2.25 bg-Mask-Aware DSFN Ramp (session 20)

**Files:** `backend/src/anim/compositing.py`, `backend/test/anim/test_compositing.py`

**Objective:** Prevent background similarity from diffusing (via Gaussian blur) into character-vs-character overlap pixels and widening the blend ramp to a ghosting-inducing width.

**Change shipped:** In `_soft_seam_weight`, after `cv2.GaussianBlur`, add:

```python
if bg_mask_a is not None and bg_mask_b is not None:
    both_fg = (~bg_mask_a.astype(bool)) & (~bg_mask_b.astype(bool))
    if both_fg.any():
        sim_diffused[both_fg] = 0.0
```

`bg_mask_a`/`bg_mask_b` (True=background) were already passed at every call site via `warped_bg[fi_a/fi_b]` slices, but the function body never used them. Without this fix: Gaussian diffusion with σ=20px can pull fg-vs-fg similarity up to ~0.5 if adjacent to background → ramp ≈ 50–100px → double-image ghost across mismatched character poses. With the fix: fg-vs-fg pixels are always forced to `sim=0 → ramp=min_ramp_bg=10px` (narrow cut, no ghost).

Background pixels on the fg boundary edge retain their diffused similarity — the fix only affects pixels where BOTH frames classify the pixel as foreground.

**2 unit tests** (`TestSoftSeamWeight`): `test_bg_mask_fg_fg_narrows_blend`, `test_bg_mask_none_result_unchanged`.

| Metric | S19 | S20 |
|--------|-----|-----|
| Tests passing (anim suite) | 201 | 203 |
| DSFN at fg-vs-fg pixels | diffused bg sim bleeds in | forced sim=0 (narrow ramp) |
| bg_mask params | passed but unused | used post-diffusion |

---

### §2.26 — Gradient-Domain Poisson Seam Blend (S21)

**File:** `backend/src/anim/compositing.py` — `_poisson_seam_blend()`

**Motivation:** The Laplacian+DSFN blend (`else` branch in the blend loop) leaves a residual brightness step of 2–6 lum units at the seam cut even after normalization. This is the irreducible gap between the two adjacent frames' luminance values after gain clamping. Poisson blending solves this by minimising the gradient difference with the source frame, finding pixel intensities that produce a continuous intensity field with no discontinuity.

**Implementation:**
1. Hard partition: `hard[:r, col] = fa_zone[:r, col]`, `hard[r:, col] = fb_zone[r:, col]`
2. Seam band mask: 255 in `[max(1, r-20), min(zone_h-1, r+21)]` × `[1, W-2]` for each column — clipped to avoid touching the `cv2.seamlessClone` destination border requirement
3. `cv2.seamlessClone(fb_zone, hard, seam_mask, (cx, cy), NORMAL_CLONE)`: fb gradients in the band, anchored to hard-partition boundary values
4. Selectively apply: `out[(seam_mask > 0) & apply_mask] = cloned[...]`

**Gate:** `ASP_POISSON_SEAM=1` (default OFF). Only fires in the normal `else` branch — single-pose and ToonCrafter seams are unaffected. Runtime cost: ~1–3 s/seam on CPU (OpenCV Poisson solver is CPU-only).

```python
if _POISSON_SEAM:
    blended = _poisson_seam_blend(fa_zone, fb_zone, path_local, apply)
```

**5 unit tests** (`TestPoissonSeamBlend`): shape/dtype, rows above band match fa, rows below band match fb, path-near-bottom no crash, empty apply_mask returns hard partition.

| Metric | S20 | S21 |
|--------|-----|-----|
| Tests passing (anim suite) | 203 | 208 |
| Normal seam blend | Laplacian+DSFN | Laplacian+DSFN (default) or Poisson (opt-in) |
| Brightness step at seam | residual 2–6 lum | 0 lum (gradient-matched) |

---

### §2.27 — Gain-Adaptive Feather Minimum (S22)

**File:** `backend/src/anim/compositing.py` — `_gain_to_min_feather()`

**Motivation:** §1.4A gain clamp bounds per-frame corrections to [0.82–1.22]. For an adjacent pair where frame A was corrected by ×1.18 and frame B by ×0.90, the residual mismatch is 0.28 — producing a visible 10–20 lum horizontal band. A wider feather blends this band. §1.6B formalises this as a minimum feather that scales with `|gain_A − gain_B|`.

**Implementation:**
- `frame_gains: List[float] = [1.0] * N` — tracks applied gain per frame alongside the normalization loop
- `max_feathers: List[int]` — cached from the overlap-cap loop (avoids recomputing `nat_overlap` in §1.6B)
- §1.6B pass after overlap-cap: `min_fk = _gain_to_min_feather(abs(frame_gains[fi_a] - frame_gains[fi_b]))`, widens `feathers[k]` when below `min_fk`, re-applies overlap cap

```python
def _gain_to_min_feather(gain_diff: float) -> int:
    return min(120, max(40, int(gain_diff * 300)))
```

Floor=40px (below FEATHER_MIN=80) → only activates when `gain_diff > 0.267` (extreme pairs). Cap=120px → prevents excessive blur. Typical adjacent pairs (diff < 0.13) are unaffected.

**Also shipped S22:**
- Dead code removed: `_normalize_warped_to_median` (30 lines, per-channel gain, never called, hue-shift risk)
- Roadmap housekeeping: §0.5A/B, §1.1C, §1.4A, §1.5A/C/E, §1.6A/B/C marked ✅

**6 unit tests** (`TestGainToMinFeather`): zero→40, small→40 (floor), mid=60 (linear), large→120 (cap), at-boundary→40, just-above=42.

| Metric | S21 | S22 |
|--------|-----|-----|
| Tests passing (anim suite) | 208 | 214 |
| Dead code | `_normalize_warped_to_median` (unused) | removed |
| Gain-adaptive feather | none | `_gain_to_min_feather` wires into feather pipeline |

---

### §2.28 — §1.7B OpenCV INPAINT_TELEA Border Fill Fallback (S23)

**File:** `backend/src/anim/canvas.py` — `_telea_fill_gaps()`; `backend/src/anim/pipeline.py` — P1.8 block

**Motivation:** The P1.8 inpainting block in `pipeline.py` already attempts diffusion inpainting when post-crop coverage < 95%. In practice, `mfsr.inpaint_gaps` raises an import error in standard environments (GPU diffusion dependencies not installed by default). Before S23, the `except` block silently left black corner triangles in outputs from diagonal-scroll sequences — the intended fill path existed but the fallback was absent.

**Implementation:**

1. **`_telea_fill_gaps(canvas, gap_mask) → np.ndarray`** added to `canvas.py`:
   ```python
   def _telea_fill_gaps(canvas, gap_mask):
       if not gap_mask.any():
           return canvas
       return cv2.inpaint(canvas, gap_mask.astype(np.uint8), inpaintRadius=3, flags=cv2.INPAINT_TELEA)
   ```
   Fast neighbor-propagation fill. Zero new dependencies. Added to `__all__`.

2. **Pipeline wiring** (`pipeline.py` P1.8 `except` block): replaces the silent "keeping canvas as-is" log with a `_telea_fill_gaps(canvas, _gap_mask)` call. Double-guarded with an inner `except` for degenerate (fully-black) canvases.

3. **Import**: `_telea_fill_gaps` added to `from .canvas import (...)` in `pipeline.py`.

**Scope:** Gap fills < 50 px wide — typical for the 10–30 px black corner triangles from diagonal-scroll warps. Larger gaps will show TELEA smearing; those cases should use §1.7A (diffusion) or the §1.7C inner-rect crop path.

**5 unit tests** (`TestTelaeFillGaps` in `test_canvas.py`):
- `test_no_gap_returns_unchanged` — all-zero gap_mask → output identical to input
- `test_shape_preserved` — output shape matches input
- `test_dtype_preserved` — uint8 in → uint8 out
- `test_corner_gap_no_longer_black` — 4×4 black corner with 150-valued surroundings → `max() > 0` after fill
- `test_valid_region_unchanged_outside_band` — pixels ≥8 rows and cols from the gap band are not modified

| Metric | S22 | S23 |
|--------|-----|-----|
| Tests passing (anim suite) | 214 | 219 |
| Black-border fallback | silent (canvas unchanged) | `cv2.INPAINT_TELEA` fill |
| New dependencies | — | none |

---

### §2.29 — §1.4B Continuous Adaptive Gain Clamp (S24)

**File:** `backend/src/anim/compositing.py` — `_adaptive_gain_clamp()`

**Motivation:** S18 introduced `_adaptive_gain_clamp` with a binary threshold at ref_lum=80: dark scenes use [0.82, 1.22], normal scenes use [0.88, 1.14]. The jump from 0.82 to 0.88 at the threshold is a 0.06 discontinuity in a smooth quantity — a frame at ref=79 gets significantly wider correction than a frame at ref=80, even though their photometric residuals are nearly identical. §1.4B replaces the binary threshold with a linear interpolation.

**Implementation:**

```python
# Before (S18 binary — §1.4A):
lo, hi = (0.82, 1.22) if ref_lum < 80.0 else (0.88, 1.14)

# After (S24 continuous — §1.4B):
clamp_width = 0.26 - 0.12 * (ref_lum / 255.0)
lo = 1.0 - clamp_width
hi = 1.0 + clamp_width
```

**Clamp surface at key values:**

| ref_lum | S18 lo/hi | §1.4B lo/hi |
|---------|-----------|------------|
| 0 | 0.82/1.22 | 0.74/1.26 |
| 50 | 0.82/1.22 | 0.764/1.236 |
| 80 (boundary) | 0.88/1.14 | 0.778/1.222 |
| 128 | 0.88/1.14 | 0.800/1.200 |
| 200 | 0.88/1.14 | 0.834/1.166 |
| 255 | 0.88/1.14 | 0.860/1.140 |

The upper anchor (hi=1.14 at ref=255) is preserved from S18 normal. The lower anchor (hi=1.26 at ref=0) is slightly wider than S18 dark (1.22), consistent with the extrapolated trend.

**Test changes:**
- 5 existing `TestAdaptiveGainClamp` tests updated to use continuous formula helpers `_lo(ref)` / `_hi(ref)`
- Test 4 renamed `test_continuous_no_jump_at_ref_80` — now verifies `|f(79.9) - f(80.0)| < 0.001` instead of testing the old discontinuity
- 3 new tests: `test_bright_ref_hi_matches_anchor` (ref=255 → 1.14), `test_clamp_width_monotone_decreasing` (lo(50) < lo(200)), `test_mid_ref_continuous_formula` (ref=128 exact)

| Metric | S23 | S24 |
|--------|-----|-----|
| Tests passing (anim suite) | 219 | 222 |
| Gain clamp surface | binary (ref<80 / ref≥80) | continuous (linear interp) |
| Discontinuity at ref=80 | 0.06 step in lo | eliminated |

---

### §2.30 — §3.9 Fix: Unified `_compute_aligned_ssim` (S25)

**File:** `backend/benchmark/bench_anime_stitch.py`

**Problem:** Two `_compute_aligned_ssim` definitions co-existed in the benchmark file — a dead S8 EUCLIDEAN version (line 168) silently overridden at module level by a later S9 TRANSLATION-only version (line 377). Python's last-definition-wins semantics meant all benchmark calls to `_compute_gt_metrics` were computing TRANSLATION-only ECC with loose convergence (50 iter, 0.01 tol) — not the EUCLIDEAN alignment with tighter criteria that was documented in S8.

Additionally, `_compute_gt_metrics` called `_compute_aligned_ssim` twice (lines 434 and 437); the first result (`aligned_ssim_val`) was unused.

**Changes shipped:**

1. **Dead S8 definition removed** (`bench_anime_stitch.py` lines 168-204): the EUCLIDEAN version with `(200, 1e-4)` criteria but no `gaussFiltSize`, no GT-centric resize, and `WARP_INVERSE_MAP` flag.

2. **Active (formerly line-377) definition upgraded**:

| Property | S9 (before S25) | S25 |
|---|---|---|
| Motion model | `cv2.MOTION_TRANSLATION` | `cv2.MOTION_EUCLIDEAN` |
| Iterations | 50 | 200 |
| Tolerance | 0.01 | 1e-4 |
| gaussFiltSize | 5 ✅ | 5 ✅ |
| Resize reference | GT dims ✅ | GT dims ✅ |
| borderMode | REPLICATE ✅ | REPLICATE ✅ |

3. **Redundant call removed**: `_compute_gt_metrics` now calls `_compute_aligned_ssim` once, assigning directly to `aligned_ssim`.

**Significance:** `aligned_ssim_vs_gt` has been computing TRANSLATION-only alignment in all benchmark runs since S9. With S25, small rotation residuals from the panorama assembly (typically 0.3–1.5°) are now correctly aligned before SSIM comparison. For test27 (known scale mismatch): aligned SSIM previously 0.748 (translation); EUCLIDEAN will handle the slight rotation in that dataset's alignment as well.

**5 unit tests** (`TestComputeAlignedSsim` in `test_bench_metrics.py`):
- `test_identical_images_returns_one` — SSIM(img, img) ≈ 1.0
- `test_returns_float` — isinstance check (not numpy scalar)
- `test_shifted_image_high_ssim_after_alignment` — 5px-shifted checkerboard → score > 0.70 after ECC
- `test_different_images_score_below_one` — structurally unrelated images → < 0.99
- `test_score_in_valid_range` — result ∈ [0, 1]

| Metric | S24 | S25 |
|--------|-----|-----|
| Tests passing (anim suite) | 222 | 227 |
| `_compute_aligned_ssim` motion model | TRANSLATION (silent bug) | EUCLIDEAN (correct) |
| ECC convergence | 50 iter / 0.01 tol | 200 iter / 1e-4 tol |
| Dead code | S8 EUCLIDEAN definition | removed |
| `_compute_gt_metrics` calls | 2 (one unused) | 1 |

---

### §2.37 — §1.2A Pre-bundle Static Edge Rejection (S32)

**File:** `backend/src/anim/pipeline.py` — `_reject_static_edges()` + wired into `_filter_edges()`
**Constant:** `backend/src/constants/anim.py` — `STATIC_EDGE_MIN_DISP_PX = 50`

**Problem addressed:** The existing min-step guard in `_filter_edges` rejects adjacent edges where the primary-axis displacement < `MIN_EXPECTED_STEP=25px`. Two failure modes escape it:
1. Skip edges (j > i+1) with small 2D displacement — not filtered
2. Both-axes-small edges (e.g., dx=20px, dy=30px for vertical sequence) — primary-axis check uses y, so x=20px is irrelevant; only dy=30px is checked and passes

These near-zero-2D edges corrupted the direction consensus median when many edges were near-zero (the median itself becomes small, making the filter circuluar).

**Fix:**
```python
def _reject_static_edges(edges, min_disp_px=50):
    return [
        e for e in edges
        if abs(e["M"][0, 2]) >= min_disp_px or abs(e["M"][1, 2]) >= min_disp_px
    ]
```
Called at the very start of `_filter_edges()`, before the geometric consistency filter. An edge is KEPT if EITHER axis meets the threshold (preserving horizontal-scroll edges where |dx|>>|dy|).

**5 unit tests** (`TestRejectStaticEdges` in `test_filter_edges.py`):
- `test_normal_edges_all_kept` — dy=300px → all kept
- `test_both_axes_below_threshold_rejected` — dx=10, dy=10 → dropped
- `test_one_axis_above_threshold_kept` — dx=80, dy=10 → kept (diagonal scroll)
- `test_skip_edge_with_small_displacement_rejected` — skip edge j=i+3, dx=20, dy=30 → dropped
- `test_empty_edge_list` — [] → []

| Metric | S31 | S32 |
|--------|-----|-----|
| Tests passing (anim suite) | 257 | 262 |
| Static-edge pre-filter | none | `_reject_static_edges` on ALL edges |
| Threshold | — | 50px per-axis (BOTH must be below to reject) |
| Position in filter chain | — | before geometric consistency filter |

---

### §2.38 — Sessions 33–58 Compact Summary

| Session | Item | File | Description |
|---------|------|------|-------------|
| S33 | §3.15A SemanticStitch column barrier | `compositing.py` | fg-dominated columns (>50%) raised to cost=2.0, forcing DP seam into background corridors. `TestSeamCostColumnFilter` (+5 tests, 272 total). |
| S33 | §3.14 scroll-axis detection wired | `pipeline.py` / `canvas.py` | `_detect_scroll_axis` called after Stage 9; horizontal scroll → SCANS fallback. `TestDetectScrollAxisModule` (+5 tests). |
| S34 | §1.2C adaptive min-step threshold | `pipeline.py` | `_compute_adaptive_min_disp(edges)` = `max(50, 0.10 × median_adjacent_step)`; wired into `_filter_edges` before `_reject_static_edges`. `ADAPTIVE_MIN_DISP_FRAC=0.10` in `constants/anim.py`. +5 tests, 277 total. |
| S35 | §3.8A ghosting metric v2 | `bench_anime_stitch.py` | `_ghosting_score_v2(img)` — FFT autocorrelation of column-mean gradient; secondary peak at lag D = ghost signature. Score [0–100]. Added as `ghosting_siqe` in `_compute_all_metrics`. +5 tests, 282 total. |
| S35 | §1.7C housekeeping | `canvas.py` | `_crop_to_valid` already implements content-aware crop. Marked de facto done in roadmap. |
| S36 | §0.5C adaptive min-gap | `validation.py` | `_compute_adaptive_min_gap(affines)` = `max(20.0, canvas_span/(N×3))`; wired as `min_step` in Stage 7b's first `_validate_affines` call. +5 tests, 287 total. |
| S37 | §2.9C high-conf edge re-solve | `pipeline.py` | `_filter_high_conf_edges(edges, min_weight=0.65)` — Retry 0 for ratio failures; re-solves with LoFTR-only edges. `HIGH_CONF_EDGE_THRESH=0.65`. §3.14A housekeeping (canvas already 2D affine). +5 tests, 292 total. |
| S38 | §1.11C response-based hold refine | `frame_selection.py` | `_refine_hold_ids_by_response(hold_ids, responses, 0.85)` — post-hoc merges hold blocks for cross-hold pairs with `phaseCorrelate response >= 0.85`. Wired step 3b. `HIGH_HOLD_RESPONSE_THRESH=0.85`. +5 tests, 297 total. |
| S39 | §1.2D temporal variance pre-filter | `frame_selection.py` | `_temporal_variance_filter(thumbs, paths, sigma_threshold)` — drops static interior frames pre-matching via triplet mean variance. Default OFF (`ASP_TEMPORAL_VAR_THRESH=0.0`). `TEMPORAL_VAR_THRESH=1e-3`. Wired step 1a. +5 tests, 302 total. |
| S40 | §1.4C bg-only gain clamp override | `compositing.py` | `_bg_gain_unclamped(ref_lum, frame_lum, override_threshold=0.20)` — lifts gain clamp for bg pixels when ideal correction is cut > 20%. Replaces `_adaptive_gain_clamp` in normalization loop. +5 tests, 307 total. |
| S41 | §1.9C on-demand SCANS frame reload | `pipeline.py` | `_reload_scans_frames(paths)` — `_load_frames` + `_normalise_widths` on demand. `ASP_SCANS_RELOAD=1` skips Stage-2 snapshot; both dedup syncs guarded with `if scans_frames else []`; all 5 fallback sites use `_sf = scans_frames or _reload_scans_frames(image_paths)`. Saves ~87 MB on success path. +5 tests, 312 total. |
| S42 | §1.8B config schema validation | `config.py` | `_CONFIG_SCHEMA` (14 `ASP_*` keys with type+range) + `validate_asp_config(config, *, strict=False)` — type/range checks, unknown keys warn, strict mode raises. Wired into `load_asp_config(validate=False, strict=False)`. Zero new deps. +5 tests, 317 total. |
| S43 | §3.4A dHash hold detection | `frame_selection.py` | `_compute_dhash(thumb, hash_size=8)` + `_detect_hold_blocks_dhash(thumbs, distance_threshold=4)`. INTER_AREA resize eliminates DCT noise before horizontal gradient binarisation. `ASP_HOLD_DHASH_THRESH=4` to enable (default 0=MAD fallback). `HOLD_DHASH_THRESHOLD=4` in constants; added to schema. +5 tests, 322 total. |
| S44 | §1.5D seam path cache | `compositing.py` / `pipeline.py` | `_make_seam_cache_key(frame_keys, k, cost_flags)` + `_get_seam_cost_flags()`. `_composite_foreground` accepts `frame_keys` + `seam_path_cache` optional params; cache checked before zone array allocation; populated after DP. `AnimeStitchPipeline` stores `self._seam_path_cache: Dict = {}` and passes it at Stage 11 with `frame_keys=tuple(image_paths)`. Eliminates DP executor latency on 2nd+ RLHF iterations. +5 tests, 327 total. |
| S45 | §1.1B spanning-tree consensus pre-filter | `bundle_adjust.py` | `_spanning_tree_inlier_filter(edges, num_frames, inlier_threshold=50.0)` — builds max-weight spanning tree (Kruskal, highest-weight-first), BFS-propagates reference translations from frame 0, rejects edges where sqrt((pred_dx−obs_dx)²+(pred_dy−obs_dy)²) > 50px. Spanning-tree edges always pass (residual=0 by construction). Falls back to original edges on disconnected graph or < max(2,N-1) inliers. Wired at top of `_bundle_adjust_affine` before DOF setup. `_ST_INLIER_THRESHOLD=50.0`. +5 tests, 332 total. |
| S46 | §1.4D multi-scale gain map | `compositing.py` / `constants/anim.py` | `_multiscale_gain_map(frame, reference, bg_mask, sigma=30, gain_min=0.5, gain_max=2.0)` — per-pixel gain via Gaussian-blurred luminance ratio (bg-only source; fg zeroed before blur). `_MULTISCALE_GAIN` flag (default OFF, `ASP_MULTISCALE_GAIN=1`). Replaces scalar `_bg_gain_unclamped` in bg normalization loop; median gain → `frame_gains[i]` for §1.6B. `MULTISCALE_GAIN_SIGMA=30.0` constant; `ASP_MULTISCALE_GAIN` added to `_CONFIG_SCHEMA`. +5 tests, 337 total. |
| S47 | §0.5D adaptive rotation/scale thresholds | `validation.py` / `pipeline.py` | `_compute_adaptive_rot_scale(affines) → (float, float)` — returns loose thresholds (0.15) when frame-to-frame σ < `_ROT_SCALE_CONSISTENCY_THRESH=0.02` (systematic camera property: constant zoom/tilt), tight (0.10) when σ ≥ 0.02 (BA noise). Decision independent for rotation and scale. Constants: `_ROT_TIGHT=0.10`, `_ROT_LOOSE=0.15`, `_SC_TIGHT=0.10`, `_SC_LOOSE=0.15`. Wired into Stage 7b initial validation and Retry 0 re-validation; log updated to show threshold values. Targets test5 (zoom-pan: max_rot≈0.111, scale_dev≈0.121, σ≈0). Exported in `__all__`. +5 tests, 342 total. |
| S48 | §1.3E similarity-mode matching | `matching.py` / `config.py` | `_extract_similarity(M) → (2,3) float32` — closed-form Procrustes projection of full 2×3 affine to best-fit 4-DOF similarity: `a_sym=(a+d)/2`, `b_sym=(b-c)/2` → `[[a_sym, b_sym, tx], [-b_sym, a_sym, ty]]`. Shear discarded. `_SIMILARITY_MODE` flag (default OFF, `ASP_SIMILARITY_MODE=1`); in `_match_pair`, replaces translation-only strip when enabled. `ASP_SIMILARITY_MODE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. New test file `test_matching.py::TestExtractSimilarity`. +5 tests, 347 total. |
| S49 | §1.4E background CDF histogram matching | `compositing.py` / `config.py` | `_bg_histogram_lut(src_pixels, ref_pixels) → float32[256]` — CDF-matching LUT via `np.searchsorted(ref_cdf, src_cdf, side="left")`. `_apply_bg_histogram_match(frame, reference, bg_mask) → uint8(H,W,3)` — per-channel LUT application to background region; fg unchanged. `_HISTOGRAM_MATCH` flag (default OFF, `ASP_HISTOGRAM_MATCH=1`); wired as third normalization branch between `_MULTISCALE_GAIN` and scalar path. Representative median gain computed for §1.6B feather widening. `ASP_HISTOGRAM_MATCH` added to `_CONFIG_SCHEMA`. Both functions exported in `__all__`. +5 tests, 352 total. |
| S50 | §1.4F per-frame exposure outlier rejection | `compositing.py` / `constants/anim.py` / `config.py` | `_reject_exposure_outliers(frame_lums, max_deviation_lum) → List[bool]` — median bg-lum computed from all valid frame lums; returns True for frames with `|lum − median| > threshold`. Fallback all-False when < 3 valid frames. `_EXPOSURE_OUTLIER_THRESH` flag (default 0.0=off, `ASP_EXPOSURE_OUTLIER_THRESH=60.0`); OR'd into `_skip_norm` after `_coherence_skip_mask`. `EXPOSURE_OUTLIER_THRESH=60.0` constant; `ASP_EXPOSURE_OUTLIER_THRESH` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 357 total. |
| S51 | §1.13 scene-change edge pre-filter | `pipeline.py` / `constants/anim.py` / `config.py` | `_reject_scene_change_edges(edges, frames, max_luma_diff)` — computes 64×64 thumbnail mean grayscale luma for each pair of frames (i, j); rejects edge when `|lum(i)−lum(j)| > max_luma_diff`. Safe fallback for out-of-bounds frame indices (kept). Gate disabled by default (`_SCENE_CHANGE_LUMA_THRESH=0.0`; set `ASP_SCENE_CHANGE_LUMA_THRESH=60.0` to enable). Wired as first check in `_filter_edges` before §1.2A+C static-edge rejection. `SCENE_CHANGE_LUMA_THRESH=60.0` constant; `ASP_SCENE_CHANGE_LUMA_THRESH` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 362 total. |
| S52 | §1.12 Kendall-τ translation monotonicity | `validation.py` | `_check_translation_monotonicity(affines, primary_axis, min_tau_abs=0.4) → (bool, float)` — Kendall τ between temporal frame indices and primary-axis translations; |τ|=1 for monotone (forward or backward), |τ|≈0 for random permutations; wired as 5th check in `_validate_affines` for vertical/horizontal scrolls (skips diagonal); failure reason `"monotonicity={tau:.2f}"` → Retry 1 (adj-only BA); `_MONO_TAU_MIN=0.4`; requires ≥4 frames; exported in `__all__`. +5 tests, 367 total. |
| S53 | §3.8B per-seam SIQE ghost map | `bench_anime_stitch.py` | `_compute_per_seam_ghost_scores(img, n_strips, band_px=100) → List[float]` — divides output image into `n_strips` equal-height zones; evaluates `_ghosting_score_v2` in ±`band_px` band at each inter-zone seam boundary; returns `n_strips-1` float scores [0–100]; `[]` when `n_strips≤1`. `_compute_all_metrics` extended with `n_strips=1` param; result dict adds `ghost_seam_scores` (List[float]) and `ghost_seam_max` (Optional[float]). Backward compatible. +5 tests, 372 total. |
| S54 | §1.3C scale normalisation before BA | `pipeline.py` / `constants/anim.py` | `_normalize_frame_scales(frames, edges, scale_thresh=0.05) → (List[np.ndarray], List[Dict])` — extracts per-edge scale `s_ij=sqrt(a²+b²)` from matched affines; BFS spanning tree from frame 0 propagates absolute per-frame scale; resizes frames by `1/scale[i]` (Lanczos-4); resets edge M 2×2 block to identity and divides tx/ty by `scale[i]`; no-op when dev<thresh or graph disconnected. `SCALE_NORM_THRESH=0.05` constant; `_SCALE_NORM_THRESH` flag (default 0.0=off, `ASP_SCALE_NORM_THRESH=0.05`). Exported in `__all__`. +5 tests, 377 total. |
| S55 | §1.14 per-seam Bhattacharyya colour distance | `bench_anime_stitch.py` | `_seam_bhattacharyya_distances(img, n_strips, band_px=50) → List[float]` — greyscale histogram similarity (`1 − HISTCMP_BHATTACHARYYA`) for `band_px`-row windows above/below each seam boundary; returns `n_strips-1` scores [0,1]; 1.0=identical distributions, <0.5=severe colour mismatch. `_compute_all_metrics` extended with `seam_color_scores` and `seam_color_min`; backward compatible. New §1.14 roadmap section added. +5 tests, 381 total (+1 pre-existing skip). |
| S56 | §1.14B seam colour-similarity pipeline gate | `compositing.py` / `pipeline.py` / `constants/anim.py` / `config.py` | `_seam_color_similarity(img, k, n_strips, band_px=50) → float` — single-seam Bhattacharyya scorer; returns 1.0 for trivially thin bands. `_check_seam_color_gate(img, n_strips, thresh) → Optional[int]` — returns worst seam index below threshold or None; exported in `__all__`. `_SEAM_COLOR_GATE` flag (default 0.0=off, `ASP_SEAM_COLOR_GATE=0.55`). `SEAM_COLOR_GATE_THRESH=0.55` in constants. Stage 11.2 gate in `pipeline.py`: after `_composite_foreground`, calls gate → SCANS fallback on failure (same `_sf = scans_frames or _reload_scans_frames(image_paths)` pattern). `ASP_SEAM_COLOR_GATE` added to `_CONFIG_SCHEMA`. +5 tests, 387 total (+1 pre-existing skip). |
| S57 | §1.13B per-channel (BGR) scene-change gate | `pipeline.py` / `constants/anim.py` / `config.py` | `_reject_scene_change_edges(..., use_bgr=True)` — extended with `use_bgr: bool = False` param; per-channel thumbnail means via `t.reshape(-1,3).mean(axis=0)`, `max(|ΔB|,|ΔG|,|ΔR|)` vs threshold; catches chroma-shifted scene changes that grayscale misses. `_SCENE_CHANGE_BGR_THRESH` flag (default 0.0=off, `ASP_SCENE_CHANGE_BGR_THRESH=60.0`); `SCENE_CHANGE_BGR_THRESH=60.0` in constants; wired as second pass in `_filter_edges` after §1.13A; `ASP_SCENE_CHANGE_BGR_THRESH` in `_CONFIG_SCHEMA`; backward compatible. +5 tests, 392 total (+1 pre-existing skip). |
| S58 | §1.15 edge graph connectivity validation | `pipeline.py` | `_check_edge_graph_connectivity(edges, n_frames) → bool` — iterative path-compression Union-Find; returns True iff all frames 0..n_frames-1 reachable from frame 0; out-of-bounds indices skipped; trivially True for n_frames ≤ 1. Pre-BA gate in `run()` after `if not edges:` guard → SCANS fallback on disconnection. Saves full Retry 0–5 chain on over-pruned edge graphs. Exported in `__all__`. +5 tests, 397 total (+1 pre-existing skip). |
| S59 | §1.14C per-channel BGR Bhattacharyya seam gate | `compositing.py` / `pipeline.py` / `config.py` | `_seam_color_similarity_bgr(img, k, n_strips, band_px=50) → float` — per-channel (B,G,R) normalised 256-bin histograms, returns `min(score_B, score_G, score_R)`; 2-D greyscale input falls back to greyscale path. `_check_seam_color_gate` extended with `use_bgr: bool = False` — routes to BGR fn when True. `_SEAM_COLOR_GATE_BGR` flag (default OFF, `ASP_SEAM_COLOR_GATE_BGR=1`). Stage 11.2 in `pipeline.py` passes `use_bgr=_SEAM_COLOR_GATE_BGR`. `ASP_SEAM_COLOR_GATE_BGR` added to `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 402 total. |
| S60 | §1.16 MST weight gate | `pipeline.py` / `constants/anim.py` / `config.py` | `_compute_mst_weight(edges, n_frames) → float` — Kruskal max-weight spanning tree via iterative path-compression Union-Find; returns `total_tree_weight/(N-1)`; 0.0 for n_frames≤1 or no edges. Pre-BA gate: `_MST_MIN_WEIGHT` flag (default 0.0=off, `ASP_MST_MIN_WEIGHT=0.35`); low-confidence all-TM/PC graphs (weight~0.15–0.3) below 0.35 → SCANS fallback before wasted retry chain. `MST_MIN_WEIGHT=0.35` in constants; `ASP_MST_MIN_WEIGHT` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 407 total. |
| S61 | §1.17 Canvas span utilisation gate | `pipeline.py` / `constants/anim.py` / `config.py` | `_compute_canvas_span_utilization(affines) → float` — actual dominant-axis span / (median_adjacent_step × (N−1)); 1.0 for N<2 or zero expected span. Post-BA gate after §3.14 scroll-axis check: `_CANVAS_SPAN_MIN_UTIL` flag (default 0.0=off, `ASP_CANVAS_SPAN_MIN_UTIL=0.3`); oscillating BA solutions (frames alternating between two y positions) produce span≪expected → SCANS fallback. `CANVAS_SPAN_MIN_UTIL=0.3` in constants; `ASP_CANVAS_SPAN_MIN_UTIL` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 412 total. |
| S62 | §1.18 Adaptive single-pose escalation threshold | `compositing.py` / `constants/anim.py` / `config.py` | `_adaptive_sp_threshold(feather_width, base=22.0, min=12.0, ref=80) → float` — `max(min_threshold, base×(ref/max(fw,1)))`; fw=80→22.0 (baseline), fw≥147→12.0 (floor). Replaces hardcoded `_POST_DIFF_THRESHOLD = 22.0` at compositing.py escalation gate. `_ADAPTIVE_SP_THRESH` flag (default OFF, `ASP_ADAPTIVE_SP_THRESH=1`). Addresses Class A benchmark failure: 300px feathers + post_warp_diff 15–22 lum → no escalation → 600px ghost band. With adaptive threshold floor=12.0 these cases now escalate to single-pose. `ADAPTIVE_SP_THRESH_BASE/MIN/REF` in constants; `ASP_ADAPTIVE_SP_THRESH` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 417 total. |
| S63 | §1.19 Foreground-density-aware feather cap | `compositing.py` / `constants/anim.py` / `config.py` | `_fg_density_feather_cap(feathers, boundaries, warped_bg, order, cap_px, fg_thresh=0.60) → np.ndarray` — checks fg fraction in ±feather[k] canvas-space band around boundaries[k] for both adjacent frames; caps feather to cap_px when max fg_frac > fg_thresh. None masks → no-op. `_FG_FEATHER_CAP` flag (default 0=off, `ASP_FG_FEATHER_CAP=60`); `_FG_FEATHER_THRESH` flag (default 0.60). Wired after §1.6B gain feathers, before Stage 8.5 FG registration. Pre-registration complement to §1.18 (which fires post-registration). `FG_FEATHER_CAP=60`, `FG_FEATHER_THRESH=0.60` in constants; 2 entries in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 422 total. |
| S64 | §1.20 Tight-step preemptive single-pose escalation | `compositing.py` / `constants/anim.py` / `config.py` | `_compute_seam_step_size(fi_a, fi_b, affines) → float` — `max(|ty_b−ty_a|, |tx_b−tx_a|)`; inf for out-of-range. `_TIGHT_STEP_PX` flag (default 0=off, `ASP_TIGHT_STEP_PX=30`). Wired inside FG registration loop BEFORE `register_foreground_at_seam`: when step < threshold, skip ARAP, pick dominant by fg count in ±20px boundary band, set `seam_single_pose[k]`. Addresses Class C (test57): min_gap=10.8px seams preemptively single-posed. `TIGHT_STEP_PX=30` in constants; `ASP_TIGHT_STEP_PX` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 427 total. |
| S75 | §1.31 Seam FG penetration escalation | `compositing.py` / `constants/anim.py` / `config.py` | `_seam_fg_penetration(path, fa_zone, fb_zone) → float` — samples `path[x]` per column; fg = any channel > 0 in either zone; returns fraction in [0,1]. Blend loop: after §1.28, if `_SEAM_FG_PENETRATION_MAX > 0 and penetration > threshold and k not in seam_single_pose` → single-pose (dom by fg px count). `_SEAM_FG_PENETRATION_MAX` flag (default 0.0=off, recommend 0.7). `SEAM_FG_PENETRATION_MAX=0.7`; schema; `__all__`. +5 tests, 482 total. |
| S74 | §1.30 Minimum zone height guard | `compositing.py` / `constants/anim.py` / `config.py` | `_zone_is_degenerate(zone_h, min_height=20) → bool` — True when `zone_h < min_height` (min_height=0 disables). Wired in `_composite_foreground` after fa_zone/fb_zone allocation, before DP: if degenerate and no prior SP decision, escalates to single-pose (dom by fg px count). `_ZONE_MIN_HEIGHT` flag (default 0=off, recommend 20). `ZONE_MIN_HEIGHT=20` in constants; schema; `__all__`. +5 tests, 477 total. |
| S73 | §1.29 Static input detection gate | `pipeline.py` / `constants/anim.py` / `config.py` | `_detect_static_input(frames, max_mad, thumb_size=64) → bool` — resizes each frame to 64×64 greyscale; checks all consecutive pairs have MAD < max_mad (short-circuits on first differing pair). Stage 1.5 gate in `run()`: if True, writes frame 0 to output and returns early. `_STATIC_INPUT_MAX_MAD` flag (default 0.0=off, recommend 2.0). `STATIC_INPUT_MAX_MAD=2.0` in constants; schema; `__all__`. +5 tests, 472 total. |
| S72 | §1.28 Seam path instability escalation | `compositing.py` / `constants/anim.py` / `config.py` | `_seam_path_std(path) → float` — `float(np.std(path))`; 0.0 for empty. Blend loop: if std > `_SEAM_INSTABILITY_THRESH` and no prior SP decision, escalates to single-pose (dom by fg px count). `_SEAM_INSTABILITY_THRESH` flag (default 0.0=off, `ASP_SEAM_INSTABILITY_THRESH=20.0`). `SEAM_INSTABILITY_THRESH=20.0`; schema; `__all__`. +5 tests, 467 total. |
| S71 | §1.27 Background coverage gate for normalisation | `compositing.py` / `constants/anim.py` / `config.py` | `_has_sufficient_bg(bg_sel, min_px=200) → bool` — `np.count_nonzero(bg_sel) >= max(1, min_px)`; None → False. Formalises hardcoded `>=200` floor in normalisation loop. `_BG_NORM_MIN_PX` flag (default 0 → built-in 200-px). `BG_NORM_MIN_PX=200` in constants; schema; `__all__`. +5 tests, 462 total. |
| S70 | §1.26 Seam path boundary clamp | `compositing.py` / `constants/anim.py` / `config.py` | `_clamp_seam_path(path, zone_h, margin=3) → np.ndarray` — `np.clip(path, margin, zone_h-1-margin)`. Prevents seam routing to zone top/bottom where feather has no blending headroom → hard edge. No-op when margin≤0 or zone too small. `_SEAM_MARGIN` flag (default 0=off, `ASP_SEAM_MARGIN=3`). After §1.25 in `_seam_cut()`. `SEAM_MARGIN=3` in constants; schema; `__all__`. +5 tests, 457 total. |
| S69 | §1.25 Seam path smoothing | `compositing.py` / `constants/anim.py` / `config.py` | `_smooth_seam_path(path, window=5) → np.ndarray` — 1-D `scipy.ndimage.median_filter` on DP traceback path. Removes single-pixel jitter (column oscillation → diagonal aliasing bands). window≤1 = no-op; even window → next odd. `_SEAM_SMOOTH_WINDOW` flag (default 0=off, `ASP_SEAM_SMOOTH_WINDOW=5`). Wired at end of `_seam_cut()`. `SEAM_SMOOTH_WINDOW=5` in constants; schema entry; `__all__`. +5 tests, 452 total. |
| S68 | §1.24 Post-composite seam-step gate | `pipeline.py` / `constants/anim.py` / `config.py` | `_measure_max_seam_step(canvas, n_strips, band_px=10, guard=3) → float` — samples mean greyscale luma in band_px rows above/below each inter-strip boundary (±guard guard rows). Returns max |above−below|; 0.0 for n_strips≤1 or too-small canvas. Stage 11.3 gate: `_SEAM_STEP_GATE` flag (0.0=off, `ASP_SEAM_STEP_GATE=25.0`); SCANS fallback if max_step > threshold. `SEAM_STEP_GATE_THRESH=25.0` in constants; `ASP_SEAM_STEP_GATE` in schema; `__all__`. +5 tests, 447 total. |
| S67 | §1.23 SemanticStitch hard corridor barrier | `compositing.py` / `constants/anim.py` / `config.py` | `_seam_corridor_exists(cost, fg_thresh=0.5) → bool` — True iff some-but-not-all columns are fg-dominated (corridor exists). `_build_seam_cost_map` extended with `barrier_cost=None` param: when corridor exists, uses 1e6 (hard, `ASP_SEAM_HARD_BARRIER=1`) or 2.0 (soft, S33 default). Graceful fallback: no corridor → 2.0 unchanged. `SEAM_HARD_BARRIER_COST=1e6` in constants; 2 schema entries; `_seam_corridor_exists` in `__all__`. +5 tests, 442 total. |
| S66 | §1.22 Adaptive single-pose soft-edge width | `compositing.py` / `constants/anim.py` / `config.py` | `_adaptive_sp_soft_px(feather_width, base_px=6, max_px=30, ref_px=80) → int` — `min(max_px, max(base_px, base_px*feather_width//ref_px))`; feather=80→6, feather=160→12, feather=300→22, cap=30; degenerate feather≤0 → base_px. `_ADAPTIVE_SP_SOFT` flag (default OFF, `ASP_ADAPTIVE_SP_SOFT=1`). Wired in single-pose blend branch at line ~1849: `_sp_soft_px_base = ASP_SP_SOFT_PX; _sp_soft_px = _adaptive_sp_soft_px(feather) if _ADAPTIVE_SP_SOFT else _sp_soft_px_base`. Eliminates visible step when §1.18 escalates wide (160–300px) feathers. `SP_SOFT_BASE/MAX/REF_PX` in constants; `ASP_ADAPTIVE_SP_SOFT` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 437 total. |
| S65 | §1.21 Post-composite seam luminance equalisation | `compositing.py` / `constants/anim.py` / `config.py` | `_seam_lum_equalize(canvas, boundaries, band_px=20, min_step=5.0) → np.ndarray` — samples mean greyscale luma in band_px-row reference bands above/below each boundary (±3-row guard); applies linear additive ramp over band_px rows below boundary when step > min_step. Equal BGR correction. `_SEAM_LUM_EQ` flag (default OFF, `ASP_SEAM_LUM_EQ=1`). Wired before `return result` in `_composite_foreground`. Targets Class D (test27 SC=26.7). `SEAM_LUM_EQ_BAND_PX=20/MIN_STEP=5.0` in constants; `ASP_SEAM_LUM_EQ` in `_CONFIG_SCHEMA`. Exported in `__all__`. +5 tests, 432 total. |

---

### §2.36 — §1.3B PANORAMA Stitcher Fallback (S31)

**File:** `backend/src/anim/canvas.py` — `_panorama_stitch_fallback()` + wired into `pipeline.py`

**Problem addressed:** When `_validate_affines` rejects the BA solution after Retries 1–3, the pipeline fell back directly to SCANS mode. SCANS (mode=1) is the scan-line stitcher designed for flat scenes; it ignores scale and rotation. For sequences with `scale_dev > 0.05` or `max_rotation > 0.03`, SCANS was never the right fallback — PANORAMA (mode=0) uses cylindrical/spherical projection and handles these exactly.

**Fix:**
```python
# In pipeline.py, between Retry 3 and SCANS:
try:
    return _panorama_stitch_fallback(scans_frames, output_path)
except Exception as _pano_e:
    logger.info(f"[Stitch]   PANORAMA fallback failed ({_pano_e}); using SCANS.")
# SCANS fallback as before...
```

**New function `_panorama_stitch_fallback(frames, output_path)` in `canvas.py`:**
- Calls `cv2.Stitcher_create(mode=0)` (PANORAMA)
- Applies `setRegistrationResol(0.8)` matching the SCANS path
- On non-OK status: raises `RuntimeError` so caller falls through
- On success: applies `_largest_valid_rect` inner-rect crop and saves to `output_path`
- Added to `canvas.py __all__` and imported in `pipeline.py`

**5 unit tests** (`TestPanoramaStitchFallback` in `test_canvas.py`):
- `test_returns_pil_image_on_success` — mock OK → PIL.Image returned
- `test_raises_runtime_error_on_non_ok_status` — mock ERR_NEED_MORE_IMGS → RuntimeError
- `test_saves_file_on_success` — mock OK → output file exists
- `test_uses_panorama_mode_zero` — `cv2.Stitcher_create(mode=0)` called once
- `test_output_dimensions_match_pano` — result width/height > 0

| Metric | S30 | S31 |
|--------|-----|-----|
| Tests passing (anim suite) | 252 | 257 |
| Affine-fail fallback chain | Retry3 → SCANS | Retry3 → PANORAMA → SCANS |
| PANORAMA handles | — | scale/rotation failures |
| Regression risk | — | zero (PANORAMA exceptions caught) |

---

### §2.35 — §1.1D Adaptive GNC f_scale (S30)

**File:** `backend/src/anim/bundle_adjust.py` — `_compute_adaptive_f_scale()` + adaptive re-solve in `_bundle_adjust_affine()`

**Problem addressed:** The GNC Cauchy loss uses `f_scale=10.0` (hardcoded, overridable via `ASP_BA_F_SCALE`). For sequences with uniformly elevated matching noise (MPEG artefacts, slight zoom, moderate blur), ALL edges land at 20–40 px residuals. The fixed scale treats them as half-outliers (50% downweighted at 10 px). The BA converges to a solution dominated by the regularisation terms rather than the edge constraints.

**Fix:**
After the initial LM solve:
1. Extract preliminary affines from `x_opt`
2. Compute per-edge residuals (same formula as outlier rejection prong 1)
3. `adaptive_scale = max(_BA_F_SCALE, 2.0 × median_residual_px)`
4. If `adaptive_scale > _BA_F_SCALE × 1.5` → warm-start re-solve with the wider scale
5. Outlier rejection (two-pronged) runs on the refined affines as before

**New function (module-level):**
```python
def _compute_adaptive_f_scale(
    edges: List[Dict],
    affines: List[np.ndarray],
    floor: float = 5.0,
) -> float:
    res_mags = [sqrt((pred_dx - obs_dx)^2 + (pred_dy - obs_dy)^2) for e in edges]
    return max(floor, 2.0 * median(res_mags))
```

**5 unit tests** (`TestAdaptiveFScale` in `test_bundle_adjust.py`):
- `test_floor_dominates_for_perfect_solution` — perfect BA chain → residuals ≈ 0 → floor=10.0
- `test_widens_when_solution_does_not_fit_edges` — manual mismatch (affines predict 0, edges say 100px) → adaptive=200
- `test_empty_edges_returns_floor` — no edges → floor=7.5
- `test_floor_respected_for_tiny_residuals` — 2×median < floor → floor returned
- `test_single_edge_computes_correctly` — 1 edge, 80px mismatch → adaptive=160

| Metric | S29 | S30 |
|--------|-----|-----|
| Tests passing (anim suite) | 247 | 252 |
| BA f_scale | fixed 10.0 | adaptive (data-driven, floor=10.0) |
| Re-solve triggered when | never | median_residual > 7.5px |
| BA outlier rejection | unchanged | unchanged (runs on refined affines) |

---

### §2.34 — §1.10A RLHF Post-run Quality Gate (S29)

**File:** `backend/benchmark/bench_anime_stitch.py` — `_compute_rlhf_score()`, `_get_reward_model()`, `_RLHF_FLAG_THRESHOLD`

**What was added:**

1. **`_RLHF_FLAG_THRESHOLD = 0.6`** — module-level constant. Outputs with `rlhf_score < 0.6` are flagged for manual review in the feedback tab.
2. **`_get_reward_model()`** — lazy singleton loader for `StitchRewardModel`. Returns `None` on any import or initialisation failure (graceful degradation when model weights are absent).
3. **`_compute_rlhf_score(img_bgr: np.ndarray) → Optional[float]`** — calls `StitchRewardModel.predict(img_bgr)` and returns a float in [0, 1], or `None` on empty input or model unavailability.
4. **`_compute_all_metrics` updated** — new keys `rlhf_score` (float or None) and `rlhf_flagged` (bool) added to every per-image metrics dict. The call to `_compute_rlhf_score` is the single lazy entry point; the model is loaded once and reused for all subsequent calls in a benchmark run.

**Interface (§1.10A):**
```python
_RLHF_FLAG_THRESHOLD = 0.6

def _compute_rlhf_score(img_bgr: np.ndarray) -> Optional[float]:
    if img_bgr is None or img_bgr.size == 0:
        return None
    model = _get_reward_model()   # lazy singleton
    if model is None:
        return None
    return float(model.predict(img_bgr))   # [0, 1]

# In _compute_all_metrics:
rlhf = _compute_rlhf_score(img)
{...
 "rlhf_score": round(rlhf, 4) if rlhf is not None else None,
 "rlhf_flagged": (rlhf is not None and rlhf < _RLHF_FLAG_THRESHOLD),
}
```

**5 unit tests** (`TestComputeRlhfScore` in `test_bench_metrics.py`):
- `test_returns_float_or_none_for_valid_image` — valid BGR image → float or None
- `test_empty_image_returns_none` — zero-size array → None without raising
- `test_score_in_valid_range_when_model_available` — if score is not None → 0 ≤ score ≤ 1
- `test_rlhf_flagged_when_score_below_threshold` — mocked score 0.3 → `rlhf_flagged=True`
- `test_rlhf_not_flagged_when_score_at_or_above_threshold` — mocked score 0.6 → `rlhf_flagged=False`

**Why now:** The reward model CNN already existed (`rlhf/reward_model.py`). The only missing piece was the wiring into the benchmark. Without this, collected feedback data could not propagate to benchmark verdict. With it, `rlhf_flagged` marks each test's output for the feedback-collection tab, and the `rlhf_score` field appears in benchmark JSON for later Bayesian optimisation (§1.10B).

| Metric | S28 | S29 |
|--------|-----|-----|
| Tests passing (anim suite) | 242 | 247 |
| Benchmark metrics per test | 9 keys | 11 keys (+ rlhf_score, rlhf_flagged) |
| RLHF model wired to benchmark | ✗ | ✅ |
| Feedback loop closed (infrastructure) | ✗ | ✅ |

---

### §2.33 — §1.9A Spatial Dedup scans_frames Sync (S28)

**File:** `backend/src/anim/pipeline.py` — `_spatial_dedup_frames()` + `run()` refactor

**Bug fixed:** The post-Stage-6 spatial dedup while-loop updated `frames`, `bg_masks`, `image_paths`, and `edges` on each pass but never synced `scans_frames`. Every SCANS fallback path triggered after the spatial dedup (lines 840, 868, 1003, 1110, 1174 of the old code) therefore received the full pre-dedup frame set — including the near-static frames the spatial dedup had just discarded. This was semantically wrong even if benign in practice (near-duplicate frames add marginal overlapping content to the scan stitch).

**Root cause:** `scans_frames` IS set at Stage 2 (pre-BiRefNet, line 549) — the roadmap's claim of "BiRefNet-preprocessed frames for SCANS" was stale. The pre-Stage-5 luma dedup (line 716) already syncs `scans_frames`. The gap was specifically the post-Stage-6 spatial dedup block.

**Fix:**
1. Extracted the while-loop body into `_spatial_dedup_frames(frames, scans_frames, bg_masks, image_paths, edges, min_displacement_px)` — a pure module-level function returning updated lists + `n_dropped`
2. Added `[scans_frames[i] for i in keep_idx]` to the drop block
3. `run()` while-loop refactored to call the function: `while n_dropped > 0`

**Function summary:**
```python
def _spatial_dedup_frames(frames, scans_frames, bg_masks, image_paths, edges,
                          min_displacement_px) -> (..., int):
    # Detects dominant scroll axis from adj-edge displacements
    # Builds drop set: j-targets with |displacement| < min_displacement_px
    # Returns all lists filtered to keep_idx + n_dropped
    # KEY: scans_frames synced alongside frames (§1.9A)
```

**5 unit tests** (`TestSpatialDedupFrames` in `test_pipeline.py`):
- `test_no_drop_when_displacement_above_threshold` — no drops when all edges ≥ min_px
- `test_drops_near_static_adjacent_frame` — sub-threshold edge → frame dropped
- `test_scans_frames_synced_with_frames_after_drop` — §1.9A: scans_frames tracks frames
- `test_edges_reindexed_after_drop` — edge i/j remapped after mid-sequence drop
- `test_first_frame_never_dropped` — frame 0 (anchor) is never a j-drop target

| Metric | S27 | S28 |
|--------|-----|-----|
| Tests passing (anim suite) | 237 | 242 |
| scans_frames post-spatial-dedup | stale (pre-dedup set) | synced (§1.9A) |
| Spatial dedup testability | embedded in run() | standalone pure function |

---

### §2.32 — §1.8A TOML Pipeline Config Loader (S27)

**File:** `backend/src/anim/config.py` — `load_asp_config()`

**Motivation:** All ASP runtime tuning is currently done via env vars (`ASP_NEAR_DUP_LUMA`, `ASP_HOLD_THRESHOLD`, `ASP_SP_SOFT_PX`, etc.). Env vars work for ad-hoc experiments but are transient — they disappear when the shell closes and cannot be reproduced by reading the benchmark output directory. §1.8A adds a persistent, readable config file that can travel alongside test datasets.

**Implementation:**

```python
def load_asp_config(path=None, *, override_env=True) -> Dict[str, Any]:
    """Load asp_config.toml; write each key to os.environ via setdefault."""
    config_path = Path(path) if path else Path("asp_config.toml")
    if not config_path.exists():
        return {}
    with open(config_path, "rb") as fh:
        raw = tomllib.load(fh)
    flat = {}
    for value in raw.values():
        if isinstance(value, dict):
            flat.update(value)
    if override_env:
        for key, val in flat.items():
            os.environ.setdefault(key, "1" if isinstance(val, bool) and val else
                                 "0" if isinstance(val, bool) else str(val))
    return flat
```

Key design decisions:
- **`setdefault` semantics**: explicit env vars always win over the config file; the file is a default, not a constraint
- **Section-agnostic merge**: all TOML sections are flattened into one dict — sections are for human organisation only
- **`override_env=False` dry-run**: allows config preview or testing without touching process state
- **Zero dependencies**: uses Python 3.11 stdlib `tomllib`; no extra package required

**Example `asp_config.toml`:**
```toml
[frame_selection]
ASP_NEAR_DUP_LUMA = 5.0
ASP_HOLD_THRESHOLD = 0.03

[compositing]
ASP_SP_SOFT_PX = 6
ASP_POISSON_SEAM = 0
```

**5 unit tests** (`TestLoadAspConfig` in `test_config.py`):
- `test_missing_file_returns_empty_dict` — nonexistent path → `{}`
- `test_valid_config_sets_env_var` — single-key TOML → value written to env
- `test_existing_env_var_not_overwritten` — pre-set env var unchanged after load
- `test_multi_section_keys_flattened` — two sections → all keys in flat dict
- `test_override_env_false_does_not_write_env` — dry-run: returned dict populated, env unchanged

| Metric | S26 | S27 |
|--------|-----|-----|
| Tests passing (anim suite) | 232 | 237 |
| Runtime config mechanism | env vars only | env vars + `asp_config.toml` |
| Dependencies added | — | none |

---

### §2.31 — §1.2B Near-Duplicate Luma Post-Filter (S26)

**File:** `backend/src/anim/frame_selection.py` — `_near_dup_luma_filter()`; `backend/src/constants/anim.py` — `NEAR_DUP_LUMA_THRESH`

**Motivation:** The greedy forward-selection in `smart_select_frames` guarantees at least `min_step_px=50px` of camera advance per selected frame. But three classes of near-duplicate redundancy remained unaddressed:
1. **Hold block duplicates** — covered by §1.11 hold detection (S6)
2. **Pixel-identical frames** — covered by the pre-stage-5 luma dedup in `pipeline.py` (`diff < 3.0`)
3. **Near-static consecutive selected frames** — camera moved slightly (≥ 50px nominal) but pixel content is nearly identical because the character fills the frame horizontally, masking the background advance. These frames add noise to bundle adjustment and the temporal median without contributing new canvas content.

`_near_dup_luma_filter` addresses class 3 by comparing consecutive SELECTED frames at thumbnail scale. Unlike the pre-stage-5 dedup which runs on full-res frames inside the pipeline, this filter runs in `smart_select_frames` before any GPU work begins.

**Implementation:**

```
_near_dup_luma_filter(selected_thumbs, selected_paths, threshold=5.0):
  keep = [0]
  for i in 1..N-1:
    g_cur, g_prev = grayscale thumbnails of frame i and keep[-1]
    diff = mean(|g_cur - g_prev|)
    if diff >= threshold:
      keep.append(i)
  if keep[-1] != N-1: keep.append(N-1)  # always keep last
  return [selected_paths[i] for i in keep]
```

**Constants change:** `NEAR_DUP_LUMA_THRESH = 3.0` added to `constants/anim.py` and imported in `pipeline.py`, replacing the hardcoded magic number `3.0` in the pre-stage-5 dedup block.

**Default OFF:** `ASP_NEAR_DUP_LUMA=0.0` (disabled). Enable with `ASP_NEAR_DUP_LUMA=5.0`. The default corpus doesn't need it — typical selected frames are ≥ 50px apart and produce > 5-luma units of mean content change. The filter is safeguarded by two invariants: (1) if threshold=0 or ≤2 frames, returns input unchanged; (2) last frame is always retained (canvas extent preservation).

**5 unit tests** (`TestNearDupLumaFilter` in `test_frame_selection.py`):
- `test_disabled_at_zero_threshold` — threshold=0 returns input unchanged
- `test_all_identical_keeps_first_and_last` — 5× same-lum frames → only first + last survive (2 frames)
- `test_all_different_keeps_all` — large luma steps → no drops
- `test_two_frames_passes_unchanged` — ≤2 frames always bypassed
- `test_middle_near_dup_dropped_first_last_kept` — middle near-dup dropped; first and last always present

| Metric | S25 | S26 |
|--------|-----|-----|
| Tests passing (anim suite) | 227 | 232 |
| Near-dup filter (selected list) | none | `_near_dup_luma_filter` (default OFF) |
| Pre-stage-5 dedup threshold | hardcoded `3.0` | `NEAR_DUP_LUMA_THRESH` constant |

---

## 3. Benchmark Results — Current State

### 3.1 5-Test Verification Corpus

| Test | Before all fixes | After all fixes | Simple stitch | GT verdict | Key characteristic |
|------|---------------:|---------------:|-------------:|-----------|-------------------|
| test04 | 0.633 | **0.742** (+0.109) | 0.738 | comparable | High-animation; render-gate SCANS fallback |
| test08 | 0.731 | **0.737** (+0.006) | 0.813 | simple_better | Extreme arm motion; 9/13 seams single-pose |
| test09 | 0.785 | **0.787** (+0.002) | 0.757 | **asp_better** | Canonical case; clean after all fixes |
| test27 | 0.705 | **0.709** (+0.004) | 0.677 | **asp_better** | 2× scale mismatch vs GT; ASP wins on content |
| test57 | 0.738 | **0.743** (+0.005) | 0.756 | comparable | Moderate animation; comparable to simple |

### 3.2 96-Test Full Corpus (session 4 run — all features active)

*Run: `anime_stitch_20260604_025208.json`. Runtime: 2.5h. All session 1–4 features active.*

- **True ASP composites**: 52/96 (54.2%) — up from 44/96 (45.8%) before foreground assembly features (+8 tests)
- **Render-gate fallback**: 31/96 (32.3%) — down from 39/96 (40.6%), 8 fewer SCANS fallbacks
- **Affine validation fallback**: 13/96 (13.5%) — unchanged
- **GT verdict (55 tests with GT)**: asp_better=7 (12.7%), comparable=22 (40.0%), simple_better=26 (47.3%)
- **Avg ASP SSIM vs GT**: 0.6666 vs simple stitch 0.6938
- **Best ASP scores**: test17=0.887 (+0.031 vs simple), test84=0.821 (+0.052), test44=0.770 (+0.061)
- **Avg time per dataset**: 95s (was ~120s before seam-band cropping optimisation)

**Interpretation:** The 8 additional true ASP composites (44→52) come from tests that previously triggered the composite gate (strip_banding > 30 or seam_coherence > 38). These tests now pass the gate because the foreground assembly (A5+A6+ARAP) produces cleaner composites. The GT SSIM improvement is minimal in aggregate because: (1) the per-test improvements (+0.002 to +0.004) are below noise at the corpus scale, and (2) the 8 newly-saved tests fall into the "comparable" verdict bucket (ASP≈simple), not "asp_better." The corpus-wide SSIM gap vs simple stitch (−0.027) persists because the animation timing mismatch bottleneck affects all tests equally.

The 5-test corpus (with session-1 and session-2 features) shows improvements of +0.002 to +0.109. These improvements will propagate to the full corpus but haven't been measured yet.

---

## 4. What Was Tried But Didn't Work

### 4.1 Two-Channel Frame Selection (peripheral heuristic — REGRESSED)

**Idea:** Phase-correlate only the peripheral (outer-border) region of thumbnails, treating it as "background" that gives a clean camera-displacement signal uncorrupted by character animation.

**Failure:** The character is not reliably in the centre; in many scenes (especially portrait-oriented close-ups like test27) the character fills the frame edge-to-edge. The peripheral region contains the character too, making the correlation noisier than whole-frame. Test27 dropped from 0.708 to 0.676, test57 dropped from 0.745 to 0.720.

**Better approach needed:** Real background separation (BiRefNet masks) is required, but running BiRefNet *before* selection doubles the BiRefNet compute cost and changes which frames are selected, which also caused regressions. The right solution is to run BiRefNet once, use the masks both for selection and for the full pipeline — requiring architectural restructuring of the benchmark.

---

### 4.2 Two-Channel Selection with BiRefNet Masks (changes frame timing — REGRESSED)

**Idea:** Run BiRefNet on 5 probe frames to build a background-weight mask at thumbnail scale, then use background-only phase correlation for camera displacement.

**Failure:** BiRefNet is correct — background pixels give a cleaner signal — but the *side-effect* is that it selects different frames at different timing. Those frames show the character in different animation phases than the original selection, which diverges from the GT reference timing. Test04 dropped from 0.742 to 0.604. BiRefNet double-running also adds ~8s overhead per dataset.

**Root cause:** The frame selection and the GT reference selection are coupled. You can't independently optimize frame selection without also changing what the "ideal" output looks like relative to the GT.

---

### 4.3 Global Reference Pose Warp (catastrophic on noisy flow — REGRESSED)

**Idea:** Instead of independent pairwise midpoint warps (each pair warps to their own midpoint, which can drift across a chain of seams), warp all frames toward a single central reference frame. Frames close to the reference get α=0 (no warp); frames far get α→1 (full warp toward reference).

**Failure:** At α=1.0 (frames adjacent to the reference), a 5px RAFT flow error becomes a 5px wrong displacement on the character. For flat anime regions where RAFT is imprecise (uniform skin tones, minimal texture gradient), this amplification is destructive. Test27 (mostly flat skin/costume) dropped catastrophically from 0.709 to 0.558.

**What would make it work:** Flow accuracy comparable to the animation residual magnitude. Currently, for 20px animation residuals, RAFT errors are ~2-5px (10–25% of signal). At α=1.0, these errors become the dominant artifact. Reliable flow would require either much finer-grained flow estimation or a confidence-weighted alpha that caps at safe values for uncertain regions.

---

### 4.4 Character Bounding-Box Crop (wrong axis — REGRESSED)

**Idea:** After assembly, crop the panorama to the bounding box of the foreground character across all frames, removing excess background-only regions. This would reduce the 2× scale mismatch between test27's output (1877×2135) and its GT (963×1280).

**Failure:** For a *vertical* pan (camera moves top-to-bottom), the character appears at different horizontal positions in different frames. The union of foreground bounding boxes across all frames covers the left column of all frames, causing the crop to remove 44% of the *width* (the right-side locker background that is essential to the composition). Test27 dropped from 0.709 to 0.558.

**Root cause:** For vertical pans, excess canvas is in the *vertical* direction (top/bottom), not horizontal. The crop must respect scroll axis. Additionally, for character bodies where every row has character content (portrait-style test27), there is NO excess vertical canvas — the character fills the full height. The scale mismatch is fundamental: we assemble more frames than the GT shows.

---

### 4.5 ARAP Asymmetric Cell Sizes (no measurable improvement)

**Tried:** `cell_size=8` (finer cells), `cell_size=32` (coarser), `n_iter=3` vs `n_iter=2`.

**Finding:** No measurable SSIM change across any combination. The ARAP regularisation is geometrically correct (smooth flow, reduced line bending) but the SSIM metric doesn't detect the improvement because: (a) line-art bending was already minor with DIS, (b) the dominant SSIM loss comes from pose differences, not flow distortion.

---

### 4.6 Lowering `post_warp_diff` Threshold (marginal, mixed)

**Tried:** Threshold=35 (original), 22 (current), 15, 20.

**Finding:** threshold=22 gives +0.002 on test08 (5 seams escalated to single-pose instead of blending), neutral on test09, -0.001 to -0.003 on test57. Lowering further hurts test57 more than it helps test08. The optimal value is scene-dependent: high-motion scenes (test08) benefit from aggressive single-pose escalation; moderate-motion scenes (test57) do not.

---

### 4.7 Lowering `max_residual` to 50px (mixed, minimal)

**Tried:** Default 90px, reduced to 50px.

**Finding:** test08 +0.001, test57 -0.003. More seams switch from "warped (but imperfect)" to "single-pose". The improvement on test08 comes from preventing blends between poses that are >50px apart; the regression on test57 comes from seams that would have produced acceptable blends now taking an arbitrary single pose.

---

### 4.10 Composite Gate Calibration (gate is correct)

**Diagnostic (session 4):** Added `ASP_GATE_SC` and `ASP_GATE_SB` env vars to override the composite gate thresholds (default 38 and 30). Setting both to 99 disables the gate entirely, allowing the ASP composite to be measured directly.

**Finding for test04:** With gate disabled, ASP composite gives GT-SSIM=0.716 vs SCANS fallback 0.742. The gate IS CORRECT — SCANS produces a better output for test04. Strip_banding=32.8 for test04 (barely above 30 threshold), but even this slightly-banded ASP composite is worse than SCANS. No reason to raise the threshold.

---

### 4.9 ARAP Push Phase (correctly implemented, zero measurable SSIM impact)

**Implemented (session 4):** Full Sýkora 2009 Push → Regularise algorithm now active. Push runs before Regularise and provides better per-cell displacement estimates via SAD block matching.

**Finding:** Zero measurable GT-SSIM improvement across all 5 test cases (test09: 0.787, test27: 0.709, test08: 0.736, test57: 0.743). This is consistent with the existing analysis that "flow quality is not the bottleneck." The SSIM ceiling is determined by animation timing mismatch (frame selection), not by flow estimation quality. The Push phase is correct and will help when the INITIAL flow from RAFT/DIS is genuinely wrong due to flat regions — but the current test corpus doesn't have such cases dominating.

---

### 4.8 Gradient-Based Pose-Consistent Frame Selection (confounded by background — DISABLED)

**Idea (§6.1 of the Upgrade Research report):** For each v1-selected frame, check if a nearby frame (±2 slots) has better gradient-magnitude similarity to the previous selected frame. The "on twos" principle: frames where the character holds the same pose share similar gradient patterns. This would select pose-consistent frames, reducing animation residuals at seams without needing to warp.

**Implementation:** Two-pass architecture. Pass 1: v1 greedy selection (first-past-threshold). Pass 2: local refinement. Uses `_fg_center_diff()` — Sobel gradient magnitude L1 on the central 50% crop of two thumbnails.

**Failure:** Gradient similarity in the central 50% crop is confounded by background structure. The background (lockers, walls, furniture) also has edges, and those edges CHANGE as the camera pans through different positions. The gradient L1 therefore measures both "different character pose" AND "different background structure visible" — both raise the score. In test27 (locker scene), the lockers' vertical edges dominate the central crop, and frames at similar scroll positions (similar locker patterns) score low even if the character is in a completely different pose.

**Quantified regression:**
- test04: 0.742 → 0.699 (-0.043, SCANS fallback, different frame selection → different SCANS output)
- test27: 0.708 → 0.682 (-0.026, composite gate failed due to strip_banding from clustering)
- test09: 0.787 → 0.784 (-0.003, minor but wrong direction)

Only test08 improved (+0.004) — a scene where the character dominates the frame and the background is simpler.

**Root cause:** Without a pose-estimation model (DWPose, ViTPose, or similar), any image-level similarity metric is confounded by background content. The gradient proxy conflates "same pose" with "same scroll position." A proper implementation requires pose embedding from a model trained to ignore background.

**Current state (updated S8):** Gradient metric replaced by DINOv2 cosine distance via `_compute_dinov2_features()` (see §2.11). DINOv2 features are background-agnostic by training and represent semantic pose rather than pixel statistics. Still disabled by default (`ASP_POSE_WINDOW_PX=0`) due to GT-coupling wall (§5.1), but no longer confounded by background structure. Enable via `ASP_POSE_WINDOW_PX=80`.

---

### 4.9 Naive Temporal Median on Foreground (ghosting — fixed by A5)

**Problem:** The original temporal median averaged the character's different animation poses into a translucent ghost background plate. Stage 11 then tried to composite over a plate that already had the ghost.

**Fix (A5):** Foreground-excluded median. The ghost is now prevented at source. This was the single most impactful fix, but its benefit is mostly visible qualitatively (cleaner background plate) rather than in SSIM numbers (because Stage 11 always overwrites the character region anyway).

---

### 4.9 Laplacian Sharpness as Quality Metric (fundamentally wrong — replaced)

**Problem:** The original benchmark used `cv2.Laplacian().var()` as a "sharpness" proxy for quality. This metric inflates when there are hard seam edges (which are high-frequency content). A catastrophically banded output with 5 harsh horizontal colour discontinuities scored 2–3× higher "sharpness" than a clean image.

**Fix:** Replaced by **seam_coherence** (std of per-row mean luminance; lower = less banding) and **GT-SSIM** (structural similarity vs reference panoramas). The old metric actively misled development for multiple sessions.

---

## 5. Current Limitations and Bottlenecks

### 5.1 Fundamental: Animation Timing Mismatch with GT Reference

**The primary SSIM ceiling** for tests 09/27/57 at ~0.787/0.709/0.745 is not from compositing quality — it's from frame selection timing.

The ground-truth panoramas were assembled at some specific temporal selection of frames. Our `_smart_select_frames` selects frames based on camera displacement, which at 50px/frame and 24fps video gives frames spaced ~300ms apart. Over 300ms, an animating character moves 10–35px. The midpoint warp halves this to 5–17px residual at each seam. The residual → SSIM penalty.

**No compositing improvement can close this gap without changing which frames are selected.** The aligned SSIM (after ECC correction for global scale/framing) is 0.832 for test09 and 0.748 for test27 — those are the true content-quality ceilings given our current frame selection.

---

### 5.2 Render-Gate Fallback Rate: 41%

39/96 tests trigger the composite quality gate because the Stage-9 temporal median plate already shows severe horizontal banding before Stage 11 runs. These are scenes where:
- The character fills most of the frame (minimal background area)
- Character animation is large (multiple distinct poses across selected frames)
- A5's bg-only median sees few background pixels, so the fallback (geometric median of all poses) averages different animation states

These 39 tests fall back to SCANS simple stitch, which always produces a coherent (if limited) output. The ASP pipeline provides no value for them.

**Root cause:** These scenes are exactly the ones where the animation speed is high relative to the camera pan. There's no way to assemble a multi-frame body without encountering pose mismatches.

---

### 5.3 `simple_better` at 42% (with GT)

On the 55 tests with ground truth, the simple stitch produces better output by GT-SSIM in 23 cases (41.8%). These are cases where:
- The simple stitch happens to select frames that match the GT's temporal reference
- Our multi-frame assembly introduces more seam artifacts than a clean single-frame capture
- The GT represents a narrower crop/shorter pan than we attempt to assemble

---

### 5.4 test08: Simple Stitch Dominates (0.813 vs 0.737)

test08 shows a character with extreme arm motion (full extension through a 90° arc across the frame). No temporal interval is short enough to avoid large pose changes at the seam. The simple stitch wins by picking adjacent frames (42ms apart) where the arm barely moves, staying within one coherent animation phase.

The ASP's multi-frame approach is fundamentally at a disadvantage here: assembling from 14 frames spanning the full arm motion arc necessarily creates large-residual seams. The single-pose fallback helps (+0.006 vs pre-feature) but can't match the coherence of a 2-frame adjacent stitch.

---

### 5.5 Scale Mismatch for test27 (0.709 raw vs 0.748 aligned)

test27's GT is 963×1280 (portrait); our output is 1877×2135 (2× larger). The benchmark resizes to the minimum common dimension for SSIM, meaning our 2× output is downscaled 2×, introducing blur. This 0.039 raw-vs-aligned gap is purely from scale, not content.

We assemble 19 frames spanning the full character body from feet to head (~1000px vertical travel). The GT shows only the middle portion (~200px vertical travel). There's no general way to detect this at runtime without knowing what the GT reference shows.

---

## 6. Avenues for Further Improvement

*Sessions 6–10 completed: Hold detection (S6), GNC robust loss (S6), SLIC SGM proxy (S6), Stage 12.5 content trim (S7), DINOv2 pose metric (S8), LSD collinearity in ARAP (S8), Aligned-SSIM (S8), ToonCrafter seam synthesis (S9), Seam DP vectorization §1.5A (S10). Remaining priorities below.*

### Priority 1: Pose-Consistent Frame Selection (highest expected impact, requires pose model)

**Problem:** The SSIM ceiling is determined by animation timing between selected frames. test09's aligned SSIM is 0.832 but raw SSIM is 0.787 — the 0.045 gap is from framing, not content quality.

**Session 3 status:** Attempted with gradient-based proxy metric. Failed — gradient similarity in the central crop is confounded by background structure changes. See §4.8 for the full failure analysis.

**What's needed for this to work:** A proper pose estimation model that produces background-agnostic pose embeddings:
- **DWPose / ViTPose**: 2D whole-body pose estimation, extracts joint positions. Two frames with the same joint positions = same animation pose, regardless of background.
- **DINO / CLIP features on foreground mask**: General visual features from a ViT model, applied only to the BiRefNet-masked foreground region. More background-invariant than gradient-based metrics.
- **Optical flow on foreground-only pixels**: Compute fg-only RAFT flow between candidate and last selected; frames with fg flow < threshold are in the same pose.

**Correct implementation path:**
1. Run BiRefNet on all frames FIRST (before selection) — eliminates the double-BiRefNet issue
2. Use background-only phase correlation for camera displacement
3. For each camera-qualifying candidate, compute foreground-only optical flow to last selected frame
4. Among candidates within the step window, pick the one with the smallest foreground flow magnitude
5. This gives frames pose-similar to previous anchor without background contamination

**Expected gain:** Reduce animation residuals from 10–85px toward <20px for most seams. Would push test09 toward the 0.832 aligned-SSIM ceiling.

**Infrastructure in place:** `backend/src/anim/frame_selection.py` has the two-pass architecture ready to accept any pose similarity metric via `_fg_center_diff()`. Replacing the gradient computation with foreground-only flow or pose embedding is the only change needed.

---

### ~~Priority 2: Vertical-Pan Content Crop~~ — DONE (Stage 12.5, session 7)

Implemented as `_CONTENT_TRIM_ENABLED` block in `pipeline.py`. Scroll-axis-aware, pads 20px. See §2.14. `ASP_CONTENT_TRIM=1` (default ON).

---

### ~~Priority 3: ARAP Push Phase~~ — DONE (session 4)

`_arap_push()` implemented in `fg_register.py`. See §2.3 and §4.9 for impact analysis.

---

### Priority 4: Segment-Guided Flow (AnimeInterp SGM)

**Problem:** RAFT fails on large uniform colour regions (the aperture problem) — there's no gradient to track. DIS also fails. Both give similar wrong estimates.

**Solution:** Instead of pixel-level flow, compute flow at the *colour-segment* level. Group pixels by colour (trapped-ball segmentation or simple k-means), find segment centroid correspondences across frames, then propagate a consistent flow to all pixels within each segment. This is exactly what AnimeInterp's Segment-Guided Matching module does.

**Why this would help:** Anime character bodies are large flat-colour patches. Skin, costume, hair — each is a distinct colour cluster. Matching clusters across frames (by colour similarity and position) gives a reliable correspondence even where per-pixel flow fails completely.

**Implementation path:** 
1. K-means colour clustering on the seam-band crop (k=8–16 colours)
2. For each cluster in frame_a, find the best-matching cluster in frame_b (L2 in colour + position space)
3. Use cluster centroid displacement as the flow for all pixels in that cluster
4. Apply ARAP regularisation to smooth across cluster boundaries

---

### Priority 5: Global Reference Pose (with confidence gating)

**Previous attempt failed** due to flow noise amplification at α=1.0.

**How to make it work:**
- Compute RAFT flow *confidence* (available as the consistency check between forward and backward flow)
- For each pixel, set `alpha = min(raw_alpha, confidence × max_alpha)` where `confidence ∈ [0,1]` from flow agreement
- High-confidence pixels (strong texture, reliable flow) can warp more aggressively; low-confidence pixels (flat colour) warp less

This would give the global reference benefit (reducing drift accumulation) without catastrophic errors in flat regions.

**Alternative:** Use the ARAP per-cell rigid transform (which is already reliable and smooth) rather than raw pixel flow for the global reference. The per-cell ARAP median is less noisy than per-pixel flow, so α=1.0 on a per-cell level would be safer.

---

### ~~Priority 6: LSD Collinearity Constraint in ARAP~~ — DONE (session 8)

Implemented in `_arap_regularise()` with boundary-cell filter and 50% magnitude guard. See §2.3 for full design details and `TestArapRegulariseLSDCollinearity` in `test_fg_register.py`.

---

### Priority 7: Full 96-Test Re-Run After Feature Integration

**All session-1 and session-2 features have been applied to the benchmark only on the 5-test subset.** The 96-test corpus numbers (from June 1) predate all character-movement features. A full re-run would:
- Update the corpus-wide GT-SSIM statistics
- Measure how many tests move from `simple_better` to `asp_better` after the improvements
- Identify whether the render-gate fallback rate (41%) changes

**Expected:** The 8 tests currently `asp_better` should stay asp_better and possibly gain SSIM. Some of the 23 `simple_better` tests may move to comparable. The 39 render-gate fallbacks are unlikely to change (fundamental scene type issue).

---

### Priority 8: Longer-Term Research

- **~~ToonCrafter ghost-fill~~ (DONE S9)**: Wired to worst single-pose seam via `ASP_TOONCRAFTER_SEAM=1`. See §2.15.
- **Flow confidence weighting in the Laplacian blend**: where RAFT confidence is low (flat regions), use a wider blend zone or fall back to single-pose. Currently the blend zone width depends only on photometric similarity, not on flow reliability.
- **Fine-tune RAFT on LinkTo-Anime**: The 2506.02733 dataset provides GT optical flow for 2D animation (from 3D-rendered anime-style content). Fine-tuning RAFT or SEA-RAFT on this dataset would give flow that's reliable specifically on flat cel-shaded regions — the exact failure mode.
- **Unsupervised deep image stitching (UDIS++ / NIS)**: End-to-end neural frameworks that learn registration and fusion jointly. No heuristic pipeline stages. Would require training data and significant engineering but could subsume many pipeline stages.

---

## 7. Summary Table

| Aspect | Current state (S15) | Primary bottleneck | Next step |
|--------|--------------|-------------------|----------|
| **Frame selection** | 50px min_step, hold detection (S6), DINOv2 pose metric (S8) | GT-coupling wall prevents enabling Pass 2 by default | Enable `ASP_POSE_WINDOW_PX=80` once GT-coupling resolved |
| **Flow estimation** | RAFT (pretrained) + DIS fallback, seam-band crops; SLIC SGM proxy (S6, experimental) | Aperture problem on flat cels: RAFT = DIS in accuracy | Segment-guided flow (AnimeInterp SGM); RAFT fine-tune on LinkTo-Anime |
| **ARAP regularisation** | Per-cell median translation; Push → Regularise (S4); LSD collinearity boundary-cells + 50% mag guard (S8) | LSD has zero measurable SSIM impact; Push has zero impact (flow quality not bottleneck) | RAFT confidence-gating for blend width |
| **Bundle adjustment** | GNC Cauchy robust loss, f_scale=10.0 (S6) | Outlier matches still affect BA before edge filter | — |
| **Midpoint warp** | Symmetric α=0.5; post_warp_diff escalation at 22; ToonCrafter worst-seam (S9, `ASP_TOONCRAFTER_SEAM=1`) | Halves but doesn't eliminate pose gap | Global reference with RAFT confidence gating |
| **Canvas trim** | Stage 12.5 scroll-axis content trim, 20px padding (S7) | Partially closes scale gap for test27 | — |
| **FG-excluded median** | Background-only plate (A5) | Always-fg fallback still ghosts in foreground-heavy scenes | Segment-medoid fallback |
| **Seam blend** | DSFN per-pixel ramp (S17) + semantic routing + both-content Laplacian + adaptive feather (S12) + single-pose soft-edge ±6px + band color match (S15+S16) + Poisson opt-in S21 (`ASP_POISSON_SEAM=1`) | Residual within-band variance (~5 lum); non-overlap silhouette step | RAFT confidence-weighted blend width |
| **Seam DP** | Parallel pre-computation via `ThreadPoolExecutor(max_workers=4)` (S12) | GIL limits true parallelism for NumPy-heavy paths | Rust port of `_seam_cut` |
| **Fallback (gate)** | Comparative render gate (2.0× SCANS baseline, floor sc=38/sb=35) + GhostGate (floor=40) | 4% trigger rate (4/96 genuine) — S11 reduced from 53% to 4% | — |
| **GT-SSIM (5 tests)** | test09: 0.787 asp_better, test27: 0.709 asp_better, test57: 0.743 | Animation timing mismatch; midpoint-warp 50% residual | Pose-consistent frame selection → reduce residuals to <10px |
| **Metrics** | SSIM + seam_coherence + aligned_ssim_vs_gt (S8) + seam_visibility (S14, no-reference) | raw SSIM penalises scale mismatch (test27 0.039 bias) | — |
| **Tests** | 322 passing in anim suite (S43: §3.4A dHash hold detection; S22–S43 cumulatively +108 tests) | — | §1.10B Bayesian parameter search (needs calibrated reward model) |

---

## 4. Benchmark Results — 2026-06-10 (S61)

**5-test quick-check run on asp_test04/08/09/27/57. All tests use full ASP pipeline (no SCANS fallback triggered).**

### 4.1 Summary Table

| Test | GT SSIM ASP | GT SSIM Sim | Align SSIM ASP | Align SSIM Sim | Verdict | Ghosting ASP | Ghosting Sim | SIQE Ghost ASP | SIQE Ghost Sim | SC ASP | SC Sim | Frames |
|------|-------------|-------------|----------------|----------------|---------|-------------|-------------|----------------|----------------|--------|--------|--------|
| test04 | 0.683 | 0.738 | 0.711 | 0.748 | simple_better | 37.87 | 21.42 | 18.0 | 58.31 | 26.4 | 26.4 | 25 |
| test08 | 0.733 | 0.810 | 0.741 | 0.823 | simple_better | 56.60 | 46.01 | 24.8 | 81.21 | 17.8 | 12.5 | 14 |
| test09 | 0.781 | 0.747 | 0.795 | 0.792 | **comparable** | 28.46 | 21.17 | 48.43 | 78.99 | 22.8 | 20.2 | 22 |
| test27 | 0.660 | 0.680 | 0.694 | 0.753 | simple_better | 30.63 | 23.23 | 53.37 | 79.63 | 26.7 | 24.8 | 21 |
| test57 | 0.724 | 0.755 | 0.742 | 0.800 | simple_better | 40.93 | 24.10 | 25.97 | 82.86 | 25.0 | 21.5 | 27 |

*SC = seam_coherence (lower is better). Ghosting = 2nd-order vertical gradient score (higher = local double-edges). SIQE Ghost = §3.8A FFT autocorrelation double-edge score (higher = periodic strip ghost).*

**Average GT SSIM gap (ASP − Simple) over 5 tests: −0.030** (vs −0.027 at S4 full-run baseline on 22 tests).

### 4.2 Metric Disambiguation: ghosting_score vs ghosting_siqe

A striking pattern emerged: the two ghosting metrics disagree on WHICH pipeline is worse:

- **`ghosting_score` (2nd-order Sobel):** ASP is worse on ALL 5 tests (37.9 vs 21.4, 56.6 vs 46.0, etc.)
- **`ghosting_siqe` (§3.8A FFT autocorrelation):** ASP is BETTER on ALL 5 tests (18 vs 58, 25 vs 81, etc.)

**Interpretation:** The two metrics detect structurally different artifacts:
- `ghosting_score` measures **local double-edges** — blending two animation poses creates a zone with many nearby parallel edges. ASP's Laplacian blend across pose-mismatched strips creates these. Simple stitch doesn't blend, so no local double-edges.
- `ghosting_siqe` measures **periodic strip repetition** — simple stitch's regular hard cuts every N pixels create a periodically repeating luminance pattern. ASP's semantically-routed seams are irregular, so the autocorrelation finds no strong periodic peak.

**Conclusion:** Both metrics are correct about what they measure. ASP has **local double-edge ghosts** at seam boundaries (bad). Simple stitch has **periodic strip banding** across the whole image (also bad, but at a different scale). GT SSIM favors simple stitch because the reference was created with a non-blending method — it has no local double-edges.

### 4.3 Per-Test Failure Mode Analysis

**test04 (25 frames, spacing_ratio=2.195):**
- High ghosting (37.87) despite correct alignment (valid BA, no fallback)
- Gain range [0.80, 1.17] = 47% spread — the gain normalization is working but still producing strip color variation (SC=26.4)
- Root cause: wide feather (300px) × moderate post_warp_diff (likely 10–20 lum range) = large ghost zones at most seams

**test08 (14 frames, spacing_ratio=1.785, diagonal scroll):**
- Worst GT SSIM gap (−0.077). Ghosting_score=56.60 — highest of the 5 tests.
- 2D diagonal scroll: the alignment health shows valid=True but the canvas is 2075×1838 — nearly square. ASP processes this as vertical strips on a near-square canvas, which is geometrically wrong for diagonal scrolling.
- Root cause: the 2D/diagonal scroll means adjacent frames have both ty and tx displacement. The vertical-strip compositor handles ty but tx displacement means each frame's background shifts horizontally too. The temporal median becomes incoherent horizontally.

**test09 (22 frames, spacing_ratio=1.229 — tightest):**
- The one success: GT SSIM ASP=0.781 > Simple=0.747. Aligned SSIM=0.795 > 0.792.
- This is the canonical clean vertical pan: min_gap=51.7px, max_rotation=0.0001, pure vertical scroll.
- ghosting_score=28.46 (below 30 threshold) — moderate, not flagged as severe.

**test27 (21 frames, spacing_ratio=1.875):**
- GT SSIM 0.660 vs 0.680. Color_entropy ASP=6.72 vs Simple=7.47 — ASP output is more washed-out.
- Gain range [1.01, 1.05] = only 4% spread — minimal gain correction needed. Yet SC is 26.7, indicating the banding isn't from gain mismatch but from ARAP warp residuals.
- Root cause: moderate ghosting_score=30.63 (just above threshold). The warp residuals leave visible seam steps that the color_entropy measurement confirms.

**test57 (27 frames, spacing_ratio=3.379 — highest ratio):**
- spacing_ratio=3.379 is high, meaning max inter-frame step is 3.4× min step — irregular scroll speed. min_gap=10.8px is very tight.
- This irregular spacing is the likely cause of ghosting_score=40.93: frames with small steps have a very dense temporal median but high animation residuals (character moved a lot for a small camera advance).

### 4.4 Remaining Failure Modes Taxonomy

| Class | Tests affected | Current handling | Gap |
|-------|---------------|-----------------|-----|
| **A: Local double-edge ghost at seam** | All 5 | Single-pose escalation at 22 lum; Poisson seam opt-in | 300px feather + 15–22 lum post_warp_diff = long ghost zone |
| **B: 2D/diagonal scroll** | test08 | Alignment gate (fires at 75th-pct |dx|>50px) | Gate didn't fire here (min_gap 33.5px, ratio 1.785); canvas is wide+short but still processed as vertical strips |
| **C: Irregular scroll speed** | test57 | Spacing ratio in validation (max ratio 3.5 allowed) | Dense-step frames have animation residual >> camera advance |
| **D: Color entropy loss (washed-out bg)** | test27 | Background photometric normalization (gain+histogram matching) | ARAP warp residuals wash out after symmetric midpoint blend |
| **E: GT-coupling framing mismatch** | All 5 | Aligned SSIM partially decouples framing | Still −0.030 average gap after alignment correction |

### 4.5 Next Most Impactful Improvements

**Priority 1 — Address Class A (local double-edge ghost):**
The 300px feather × moderate post_warp_diff creates the ghost zone. Two approaches:
- **§1.18 Adaptive single-pose threshold**: scale the 22-lum escalation threshold DOWN when feather_width is large. For feather=300px, use threshold=12 lum (less than half of 22). This directly cuts the ghost zone for wide-feather seams. Testable function, no new dependencies.
- **Lower the global `_POST_DIFF_THRESHOLD` from 22 to 15**: simpler but global change, not adaptive.

**Priority 2 — Address Class B (2D diagonal scroll):**
test08's `ghosting_score=56.60` suggests a structural misfit. The alignment gate fired correctly in S5 and rescued test08 (0.736→0.809), but it seems that run used a different alignment configuration. Investigate whether the current alignment gate is still calibrated correctly for test08.

**Priority 3 — AnimeInterp SGM for flat regions (§3.1A):**
The aperture problem on flat cel-shaded regions is the root cause of poor flow on test09 despite good alignment. SGM addresses this specifically. Research prototype on test09's worst seam.

**Priority 4 — StabStitch++ trajectory smoothing (§3.x):**
For test57 (irregular scroll speed), smoothing the affine trajectory before canvas construction would regularize the frame placement and reduce the tight-step animation ghost problem.

---

## §5 Phase 2: Next-Generation Architecture (2026-06-13)

*Research basis: `reports/Upgrading Anime Stitch Pipeline.md` — covers direct video ingestion, multi-modal HITL, data serialization, and downstream fine-tuning. Full implementation spec in `reports/ASP_High_Value_Issues_Report.md` Issues 9 & 10.*

### 5.1 Direct Video Ingestion & Multi-Modal Hybrid Pipeline (Issue 9)

**Sprint 5 — Video Ingestion Foundation (~1w)**

The current architecture requires FFmpeg pre-extraction of all frames before pipeline execution. Issue 9 replaces this with native PyAV ingestion:

- **`VideoIngestionStream`** (`backend/src/anim/video_ingestion.py`) — wraps `av.open()`. Exposes proxy stream (I-frame-only at ¼-res for fast selection pass) and full-res frame decode via `get_frame(idx)`. `decimate_duplicates(mad_threshold)` drops telecine pull-down duplicates on the proxy tensor stream before `smart_select_frames()`.
- **`AnimeStitchPipeline.run()`** extended to accept `video_path: str | None` alongside `image_paths`.
- **Pass 1**: decode all frames at ¼ resolution via I-frame seeking → run `smart_select_frames()` on proxy thumbnails
- **Pass 2**: decode only the N≈18 selected frames at full resolution via precise PTS seek
- Storage reduction: 3–5× (no more 500–800 MB frame dumps); selection latency: <15s for 300-frame inputs

**Sprint 5B — Hybrid 4K/1080p compositing (Issue 9C)**

`hires_keyframes: Dict[int, str]` parameter in `pipeline.run()`. All heavy computation (BA, BiRefNet, LoFTR, SAM-2, ARAP) runs on 1080p video. Locked affines mapped to 4K keyframes in a new Stage 12.8 upsample pass. Near-4K output quality at 1080p compute cost.

### 5.2 Near-Perfect Multi-Modal HITL Architecture (Issue 10)

**Sprint 6 — Grounded Multi-Modal HITL (~1w)**

Extends the S79 HITL checkpoint infrastructure with foundation model prompting:

- **`grounding.py`** — GroundingDINO text → bounding box wrapper. Called from `masking.py` and `compositing.py` (seam exclusion).
- **`_compute_fg_masks_grounded_sam2(frames, text_prompt, ...)`** in `masking.py` — text → DINO bbox → SAM-2 video propagation. Replaces the BiRefNet → static bbox → SAM-2 chain with a natural language interface.
- **Click refinement overlay** in `stitch_tab.py` HITL checkpoint: left-click = positive prompt, right-click = negative prompt, SAM-2 re-propagates corrected segment (~0.5s).
- **Natural language seam routing**: text → DINO exclusion mask → `cost[mask] = 1e6` barrier in `_build_seam_cost_map()`.

**Sprint 7 — Data Serialization (Dataset Harvesting, ~1w)**

Every HITL interaction serializes to two formats:
1. **COCO JSON** (`COCOAnnotationBuilder` in `backend/src/anim/data_serialization.py`) — `images`/`annotations` arrays with RLE masks or polygon contours (pycocotools). Stored at `~/.image-toolkit/hitl_annotations/session_{timestamp}.json`.
2. **Label Studio JSON** — `predictions` (pre-correction SAM-2 mask) + `annotations` (human-accepted mask). Captures the model-vs-human delta for RLHF preference pairs.

**Sprint 9+ — Progressive Automation (data-gated)**

- **SAM-2 fine-tuning** (requires 100+ COCO sessions): frozen ViT-H encoder + fine-tuned mask decoder on anime-domain annotations. Target: correct delineation of magical effects, thin hair strands, multi-character overlaps without prompting.
- **Pose contrastive fine-tuning** (requires 500+ selection pairs): frame-selection override (rejected, accepted, random-other) → triplet loss on DWPose/ViTPose embedding space.
- **PPO compositing optimization** (requires calibrated reward model from Issue 6A): PPO agent over ASP parameter space (`feather_width`, seam cost weights, blend method). Replaces static `asp_config.toml` with per-test adaptive configuration.

### 5.3 Benchmark Results — test07 & test97 (2026-06-13)

*JSON: `backend/benchmark/results/anime_stitch_20260613_181512.json`*

**test07** (182 raw frames → 28 selected, "Akane wa Tsumare Somerareru - 01", vertical scroll):
- ASP: SC=23.6, sharpness=111.75, coverage=0.857, ghosting_score=51.82, ghosting_siqe=22.98, output=1593×3841
- Simple: SC=43.2, sharpness=38.81, coverage=0.875, ghosting_score=27.83, ghosting_siqe=91.65, output=1104×1776
- Verdict: **comparable** — ASP has far better seam coherence (23.6 vs 43.2) and periodic-banding score (siqe 22.98 vs 91.65), but higher local ghosting (51.82 vs 27.83). New 182-frame dataset replaces old 11-frame test07.

**test97** (90 raw frames → 16 selected, "Akane wa Tsumare Somerareru - 02", horizontal/diagonal scroll):
- ASP: SC=10.6, sharpness=77.32, coverage=0.861, ghosting_score=39.19, ghosting_siqe=33.2, output=2505×1859
- Simple: SC=14.3, sharpness=59.53, coverage=0.982, ghosting_score=38.58, ghosting_siqe=61.79, output=1520×1552
- Verdict: **simple_better** (driven by ASP coverage 86% vs 98%). ASP has better seam coherence (10.6 vs 14.3) and periodic banding (siqe 33.2 vs 61.79) but loses on coverage — ASP crops more black regions from the horizontal scroll.

**Key finding from test97:** The horizontal-scroll canvas (2505px wide) produces an ASP panorama with heavy black column gaps along the left and right edges (covered=86%). The simple stitch auto-crops to the valid region (coverage=98%). The `_crop_to_valid()` function in `canvas.py` needs to be more aggressive for horizontal scroll outputs. Or coverage needs to be tracked differently for horizontal vs vertical panoramas.

---

## Session 139 Summary

**S139 (2026-06-18):** §1.83 Seam Band Noise Asymmetry + §1.84 Seam RMS Contrast Ratio + §1.85 Multi-Gate Ensemble Combiner shipped. `_seam_noise_mismatch`/`_check_seam_noise_gate` (Stage 11.16), `_seam_rms_contrast_ratio`/`_check_seam_rms_contrast_gate` (Stage 11.17), `_seam_gate_vote_counts`/`_check_seam_ensemble_gate` (Stage 11.18) added to `compositing.py`. §1.83 uses Immerkær Laplacian-std noise estimator. §1.84 uses coefficient-of-variation ratio. §1.85 accumulates per-seam gate votes (all §1.56–§1.84 gates) firing when worst seam ≥ min_votes; correct polarity per gate direction. All wired in pipeline.py with module-level flags. 15 new tests → **928 backend tests (2 skipped)**. Stale §3.16A (shipped S121) removed from pending matrix.

---

## Session 122 Summary

**S122 (2026-06-15):** §1.56 Post-Composite Chroma Seam Correction shipped. `_seam_chroma_equalize` added to `compositing.py` — LAB a/b ramp complement to §1.21 luma equalisation; 5 new tests; 772 backend tests total.

