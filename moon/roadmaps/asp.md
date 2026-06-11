# ASP Roadmap — Anime Stitch Pipeline: Quality & Reliability

*Last updated: 2026-06-11. Session 63 complete: §2.3 Canvas Layout Inspector (read-only viewer) — `_parse_canvas_json(path) → dict` normalises stage08_canvas_info.json (canvas_h, canvas_w, frame_h, frame_w defaults to 0 when absent, affines_final parsed as float lists); `_canvas_frame_corners(affine_2x3, frame_h, frame_w) → List[Tuple]` transforms 4 corners of a frame using full 2×3 affine; `CanvasLayoutInspectorDialog(QDialog)` in `stitch_tab.py` renders N frame rectangles on canvas as colour-coded `QPainterPath` polygons (8-colour rotating palette), canvas border in scene, stats label shows N-frames and WxH canvas, table with Frame/tx/ty per frame, "Load JSON…" button for standalone use; `⬗ Canvas` button in Stitch action row, enabled after a run with save_intermediate=True when stage08_canvas_info.json exists; `stitch_worker.py` extended to save `frame_h`/`frame_w` in canvas_info JSON; 9 new tests in `test_stitch_tab.py` (TestParseCanvasJson ×3, TestCanvasFrameCorners ×3, TestCanvasLayoutInspectorDialog ×3); visual render verified with 3-frame synthetic fixture. 422 tests passing. Session 62 complete: §2.2 Edge Graph Inspector (read-only viewer) — `_parse_edge_json(path) → List[dict]` normalises stage05_edges.json (drops records missing i/j, fills dx/dy/conf/method defaults); `_edge_graph_node_positions(n, radius=150.0) → List[Tuple]` places N nodes evenly on a circle (12-o'clock first); `EdgeGraphInspectorDialog(QDialog)` in `stitch_tab.py` shows N frame nodes in a circle connected by confidence-coloured LoFTR edges (green ≥ 0.7, yellow ≥ 0.5, red < 0.5), edge thickness 1+conf×4px, tooltip shows i→j/conf/dx/dy/method, alongside a QTableWidget sorted by conf ascending (worst-first), stats label shows frame count/edge count/low-conf count; "Load JSON…" button for standalone use; `⬡ Edges` button in Stitch action row, enabled after a run with save_intermediate=True when stage05_edges.json exists; 11 new tests in `test_stitch_tab.py` (TestParseEdgeJson ×4, TestEdgeGraphNodePositions ×4, TestEdgeGraphInspectorDialog ×3). 413 tests passing. Visual check pending first real stitch run with save_intermediate=True. Session 61 complete: §1.17 GNC-TLS bundle adjustment — `_gnc_weights_geman_mcclure(residuals_sq, mu, c_sq) → ndarray` in `bundle_adjust.py`; Geman-McClure per-edge weights `wᵢ=(μc²/(μc²+rᵢ²))²`; `_GNC_OUTER=8` env-var (default ON, `ASP_GNC_OUTER=0` to disable); outer continuation loop in `_bundle_adjust_affine` starts with μ₀=max_sq/(2c²) (convex), anneals μ÷=1.4 per iteration, terminates on convergence or μ<1e-2; per-edge weights injected via `_gnc_ws` mutable list in `residuals()` closure (√w multiplier → w×r² cost); `loss='linear'` during GNC, `loss='cauchy'`+adaptive f_scale fallback when `ASP_GNC_OUTER=0`; `GNC_C_PX=10.0`, `GNC_MU_ANNEAL=1.4`, `GNC_MAX_OUTER=8` in `constants/anim.py`; `ASP_GNC_OUTER` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_bundle_adjust.py::TestGNCWeightsGemanMcclure`. 412 tests passing. Session 60 complete: §1.16 MST weight gate — `_compute_mst_weight(edges, n_frames) → float` in `pipeline.py`; max-weight spanning tree (Kruskal + iterative path-compression Union-Find); returns `total_weight/(N-1)`; 0.0 for n_frames≤1 or no edges. Pre-BA gate in `run()` after §1.15 connectivity check: `_MST_MIN_WEIGHT` flag (default 0.0=off, `ASP_MST_MIN_WEIGHT=0.35`); LoFTR edges~0.6–0.9, TM/PC~0.15–0.3; threshold 0.35 fires on all-TM/PC graphs; `MST_MIN_WEIGHT=0.35` in constants; `ASP_MST_MIN_WEIGHT` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_pipeline.py::TestComputeMstWeight`. 407 tests passing. Session 59 complete: §1.14C per-channel BGR Bhattacharyya seam gate — `_seam_color_similarity_bgr(img, k, n_strips, band_px=50) → float` in `compositing.py`; computes per-channel (B,G,R) normalised 256-bin histograms; returns `min(score_B, score_G, score_R)`; falls back to greyscale for 2-D inputs; `_check_seam_color_gate` extended with `use_bgr: bool = False` param routing to new function; `_SEAM_COLOR_GATE_BGR` flag (default OFF, `ASP_SEAM_COLOR_GATE_BGR=1`); Stage 11.2 gate in `pipeline.py` passes `use_bgr=_SEAM_COLOR_GATE_BGR`; `ASP_SEAM_COLOR_GATE_BGR` added to `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_compositing.py::TestSeamColorSimilarityBgr`. 402 tests passing. Session 58 complete: §1.15 edge graph connectivity validation — `_check_edge_graph_connectivity(edges, n_frames) → bool` in `pipeline.py`; iterative path-compression Union-Find; returns True iff all frames 0..n_frames-1 in one connected component; pre-BA gate in `run()`: disconnected graph → SCANS fallback immediately (avoids wasted retry chain); exported in `__all__`; 5 new tests in `test_pipeline.py::TestCheckEdgeGraphConnectivity`. 397 tests passing. Session 57 complete: §1.13B per-channel (BGR) scene-change gate — `_reject_scene_change_edges(..., use_bgr=True)` extended in `pipeline.py`; per-channel (B,G,R) thumbnail means, `max(|ΔB|,|ΔG|,|ΔR|)` vs threshold; catches chroma-shifted scene changes that grayscale luma misses (warm orange vs cool blue at same luma); `_SCENE_CHANGE_BGR_THRESH` flag (default 0.0=off, `ASP_SCENE_CHANGE_BGR_THRESH=60.0`); `SCENE_CHANGE_BGR_THRESH=60.0` in constants; `ASP_SCENE_CHANGE_BGR_THRESH` in `_CONFIG_SCHEMA`; backward compatible (default `use_bgr=False`); 5 new tests in `test_pipeline.py::TestRejectSceneChangeEdgesBgr`. 392 tests passing. Session 56 complete: §1.14B seam colour-similarity pipeline gate — `_seam_color_similarity(img, k, n_strips, band_px=50) → float` + `_check_seam_color_gate(img, n_strips, thresh) → Optional[int]` in `compositing.py`; evaluates Bhattacharyya histogram similarity for each inter-strip seam; returns worst seam index below *thresh* or None; `_SEAM_COLOR_GATE` float flag (default 0.0=off, `ASP_SEAM_COLOR_GATE=0.55`); Stage 11.2 gate wired in `pipeline.py` after `_composite_foreground` → SCANS fallback on worst-seam failure; `SEAM_COLOR_GATE_THRESH=0.55` in constants; `ASP_SEAM_COLOR_GATE` in `_CONFIG_SCHEMA`; both functions exported in `__all__`; 5 new tests in `test_compositing.py::TestSeamColorGate`. 387 tests passing. Session 55 complete: §1.14 per-seam Bhattacharyya colour-distance metric — `_seam_bhattacharyya_distances(img, n_strips, band_px=50) → List[float]` in `bench_anime_stitch.py`; computes greyscale histogram similarity (`1 − HISTCMP_BHATTACHARYYA`) for `band_px`-row windows above/below each seam boundary; returns `n_strips-1` scores [0,1]; 1.0=identical distributions, <0.5=severe colour mismatch; `_compute_all_metrics` extended with `seam_color_scores` and `seam_color_min`; backward compatible; 5 new tests in `test_bench_metrics.py::TestSeamBhattacharyyaDistances`. 381 tests passing. Session 54 complete: §1.3C scale normalisation before BA — `_normalize_frame_scales(frames, edges, scale_thresh=SCALE_NORM_THRESH) → (List[np.ndarray], List[Dict])` in `pipeline.py`; extracts per-edge scale `s_ij=sqrt(a²+b²)` from matched affines; BFS spanning tree propagates absolute per-frame scale; resizes frames by `1/scale[i]` (Lanczos-4); resets edge M diagonal to 1.0 and divides tx/ty by `scale[i]`; no-op when scale_dev < scale_thresh or graph disconnected; `SCALE_NORM_THRESH=0.05` in constants; `_SCALE_NORM_THRESH` flag (default 0.0=off, `ASP_SCALE_NORM_THRESH=0.05` to enable); exported in `__all__`; 5 new tests in `test_pipeline.py::TestNormalizeFrameScales`. 377 tests passing. Session 53 complete: §3.8B per-seam SIQE ghost map — `_compute_per_seam_ghost_scores(img, n_strips, band_px=100) → List[float]` in `bench_anime_stitch.py`; divides output image into `n_strips` equal-height zones; evaluates `_ghosting_score_v2` in ±`band_px` band at each inter-zone seam boundary; returns `n_strips-1` scores; `[]` when `n_strips≤1`; `_compute_all_metrics` extended with `n_strips=1` param, adds `ghost_seam_scores` and `ghost_seam_max` to result dict; backward compatible; 5 new tests in `test_bench_metrics.py::TestPerSeamGhostScores`. 372 tests passing. Session 52 complete: §1.12 Kendall-τ translation monotonicity check — `_check_translation_monotonicity(affines, primary_axis, min_tau_abs=0.4) → (bool, float)` in `validation.py`; computes |Kendall τ| between temporal frame indices and primary-axis translations; |τ|=1 for monotone sequences (forward and backward), |τ|≈0 for random permutations; fires for scroll_axis ∈ {vertical, horizontal}; wired as 5th check in `_validate_affines` after rotation/scale; failure reason `"monotonicity={tau:.2f} < 0.4"` falls through to Retry 1 (adj-only BA); `_MONO_TAU_MIN=0.4` constant; exported in `__all__`; requires ≥ 4 frames; 5 new tests in `test_affine_validation.py::TestTranslationMonotonicity`. 367 tests passing. Session 51 complete: §1.13 scene-change edge pre-filter — `_reject_scene_change_edges(edges, frames, max_luma_diff)` in `pipeline.py`; computes 64×64 thumbnail mean grayscale luma for frames i and j; rejects edge when `|lum(i)−lum(j)| > max_luma_diff`; safe-fallback for out-of-bounds indices; `_SCENE_CHANGE_LUMA_THRESH` flag (default 0.0=off, `ASP_SCENE_CHANGE_LUMA_THRESH=60.0`); wired as first check in `_filter_edges` before §1.2A+C static-edge rejection; `SCENE_CHANGE_LUMA_THRESH=60.0` in `constants/anim.py`; `ASP_SCENE_CHANGE_LUMA_THRESH` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_pipeline.py::TestRejectSceneChangeEdges`. 362 tests passing. Session 50 complete: §1.4F per-frame exposure outlier rejection — `_reject_exposure_outliers(frame_lums, max_deviation_lum) → List[bool]` in `compositing.py`; computes median bg-lum across all frames with valid lum, returns True for any frame with `|lum − median| > max_deviation_lum`; fallback all-False when < 3 valid frames; `_EXPOSURE_OUTLIER_THRESH` flag (default 0.0=off, `ASP_EXPOSURE_OUTLIER_THRESH=60.0`); wired after `_coherence_skip_mask` in normalization loop via OR; `EXPOSURE_OUTLIER_THRESH=60.0` in `constants/anim.py`; `ASP_EXPOSURE_OUTLIER_THRESH` in `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in `test_compositing.py::TestRejectExposureOutliers`. 357 tests passing. Session 49 complete: §1.4E background CDF histogram matching — `_bg_histogram_lut(src_pixels, ref_pixels) → float32[256]` + `_apply_bg_histogram_match(frame, reference, bg_mask) → uint8(H,W,3)` in `compositing.py`; CDF-matching LUT via `np.searchsorted(ref_cdf, src_cdf)`; per-channel application to background pixels; foreground unchanged; `_HISTOGRAM_MATCH` flag (default OFF, `ASP_HISTOGRAM_MATCH=1`); wired as third branch in normalization loop between `_MULTISCALE_GAIN` and scalar fallback; `ASP_HISTOGRAM_MATCH` added to `_CONFIG_SCHEMA`; both functions exported in `__all__`; 5 new tests in `test_compositing.py::TestBgHistogramLut`. 352 tests passing. Session 48 complete: §1.3E similarity-mode matching — `_extract_similarity(M) → (2,3) float32` in `matching.py`; closed-form Procrustes projection of full affine to best-fit 4-DOF similarity (`a_sym=(a+d)/2`, `b_sym=(b-c)/2` → `[[a_sym, b_sym, tx], [-b_sym, a_sym, ty]]`); shear discarded; `_SIMILARITY_MODE` flag (default OFF, `ASP_SIMILARITY_MODE=1`); in `_match_pair`, similarity projection replaces translation-only strip when flag enabled; `ASP_SIMILARITY_MODE` added to `_CONFIG_SCHEMA`; exported in `__all__`; 5 new tests in new `test_matching.py::TestExtractSimilarity`. 347 tests passing. Session 47 complete: §0.5D adaptive rotation/scale thresholds — `_compute_adaptive_rot_scale(affines) → (float, float)` in `validation.py`; returns loose thresholds (0.15) when frame-to-frame σ < 0.02 (systematic camera property), tight (0.10) when σ ≥ 0.02 (BA noise); constants `_ROT_TIGHT=0.10`, `_ROT_LOOSE=0.15`, `_SC_TIGHT=0.10`, `_SC_LOOSE=0.15`, `_ROT_SCALE_CONSISTENCY_THRESH=0.02`; wired into Stage 7b initial validation and Retry 0; log message updated to show per-run threshold; exported in `__all__`; 5 new tests in `test_affine_validation.py::TestAdaptiveRotScale`. 342 tests passing. Session 46 complete: §1.4D multi-scale spatially-varying gain normalisation — `_multiscale_gain_map(frame, reference, bg_mask, sigma=30, gain_min=0.5, gain_max=2.0) → float32(H,W)` in `compositing.py`; Gaussian-blurred luminance ratio; fg pixels zeroed before blur so background gains propagate without character-colour contamination; `_MULTISCALE_GAIN` flag (default OFF, `ASP_MULTISCALE_GAIN=1` to enable); replaces scalar `_bg_gain_unclamped` in bg normalization loop; median gain stored as `frame_gains[i]` for §1.6B downstream; `MULTISCALE_GAIN_SIGMA=30.0` in `constants/anim.py`; `ASP_MULTISCALE_GAIN` added to `_CONFIG_SCHEMA`; 5 new tests in `test_compositing.py::TestMultiscaleGainMap`. 337 tests passing. Session 45 complete: §1.1B spanning-tree consensus pre-filter — `_spanning_tree_inlier_filter(edges, num_frames, inlier_threshold=50.0)` in `bundle_adjust.py`; Kruskal max-weight spanning tree → BFS reference propagation from frame 0 → any edge with |obs_dx−pred_dx|²+|obs_dy−pred_dy|² > 50² removed; spanning-tree edges always pass (residual=0 by construction); disconnected-graph + min-inlier-count fallbacks; wired at top of `_bundle_adjust_affine` before DOF setup; `_ST_INLIER_THRESHOLD=50.0` constant; exported in `__all__`; 5 new tests in `test_bundle_adjust.py::TestSpanningTreeInlierFilter`. 332 tests passing. Session 44 complete: §1.5D seam path cache — `_make_seam_cache_key(frame_keys, k, cost_flags)` + `_get_seam_cost_flags()` in `compositing.py`; `_composite_foreground` extended with `frame_keys` + `seam_path_cache` optional params; cache checked before zone array allocation and populated after DP; `AnimeStitchPipeline` stores `self._seam_path_cache: Dict = {}` and passes it at Stage 11 with `frame_keys=tuple(image_paths)`; eliminates DP executor latency on RLHF re-runs; 5 new tests in `test_compositing.py::TestSeamPathCache`. 327 tests passing. Session 43 complete: §3.4A dHash animation hold detection — `_compute_dhash(thumb, hash_size=8)` + `_detect_hold_blocks_dhash(thumbs, distance_threshold=4)` in `frame_selection.py`; INTER_AREA resize eliminates MPEG DCT block noise before directional comparison; `_HOLD_DHASH_THRESHOLD` config (default 0=off, `ASP_HOLD_DHASH_THRESH=4` to enable); `HOLD_DHASH_THRESHOLD=4` in `constants/anim.py`; added to `_CONFIG_SCHEMA`; wired as alternative to MAD in step 1b of `smart_select_frames`; 5 new tests in `test_frame_selection.py::TestDetectHoldBlocksDhash`. 322 tests passing. Session 42 complete: §1.8B config schema validation — `_CONFIG_SCHEMA` (14 known `ASP_*` keys with type + range spec) + `validate_asp_config(config, *, strict=False) → List[str]` in `config.py`; unknown keys emit `UserWarning`; type/range violations returned as strings (or raised when `strict=True`); wired into `load_asp_config(validate=False, strict=False)`; exported in `__all__`; 5 new tests in `test_config.py::TestValidateAspConfig`. 317 tests passing. Session 41 complete: §1.9C on-demand SCANS frame reload — `_reload_scans_frames(paths)` in `pipeline.py`; returns `_normalise_widths(_load_frames(paths))`; `_SCANS_RELOAD = os.environ.get("ASP_SCANS_RELOAD","0") != "0"` flag skips Stage-2 snapshot when enabled; Stage-2 `list(frames)` → `[] if _SCANS_RELOAD else list(frames)`; both dedup sync sites guarded with `if scans_frames else []`; all 5 fallback call sites use `_sf = scans_frames or _reload_scans_frames(image_paths)`; 5 new tests in `test_pipeline.py::TestReloadScansFrames`. 312 tests passing. Session 40 complete: §1.4C background-only gain clamp override — `_bg_gain_unclamped(ref_lum, frame_lum, override_threshold=0.20)` in `compositing.py`; returns raw ideal gain when clamp would cut correction by > 20%; wired into bg-only normalization loop replacing `_adaptive_gain_clamp`; 5 new tests in `test_compositing.py::TestBgGainUnclamped`. 307 tests passing. Session 39 complete: §1.2D temporal variance pre-filter — `_temporal_variance_filter(thumbs, paths, sigma_threshold)` in `frame_selection.py`; drops interior frames with mean triplet variance < threshold (default disabled: `ASP_TEMPORAL_VAR_THRESH=0.0`); `TEMPORAL_VAR_THRESH=1e-3` in `constants/anim.py`; wired as step 1a in `smart_select_frames` before hold detection; 5 new tests in `test_frame_selection.py::TestTemporalVarianceFilter`. 302 tests passing. Session 38 complete: §1.11C response-based hold refinement — `_refine_hold_ids_by_response(hold_ids, responses, threshold)` in `frame_selection.py`; post-hoc merges hold blocks for cross-hold pairs with `phaseCorrelate response >= 0.85`; wired as step 3b in `smart_select_frames` after the phase-correlation loop; `HIGH_HOLD_RESPONSE_THRESH=0.85` in `constants/anim.py`; 5 new tests in `test_frame_selection.py::TestRefineHoldIdsByResponse`. 297 tests passing. Session 37 complete: §2.9C high-confidence edge re-solve — `_filter_high_conf_edges(edges, min_weight)` in `pipeline.py`; keeps edges with `weight >= HIGH_CONF_EDGE_THRESH (0.65)`; wired as Retry 0 in Stage 7b for ratio failures; `HIGH_CONF_EDGE_THRESH=0.65` in `constants/anim.py`; 5 new tests in `test_pipeline.py::TestFilterHighConfEdges`. §3.14A housekeeping: `_compute_canvas` already uses full 2D affine placement. 292 tests passing. Session 36 complete: §0.5C adaptive min-gap threshold — `_compute_adaptive_min_gap(affines)` in `validation.py`; returns `max(20.0, canvas_span / (N × 3))`; wired as `min_step` for the first `_validate_affines` call in Stage 7b of `pipeline.py`; 5 new tests in `test_affine_validation.py::TestAdaptiveMinGap`. 287 tests passing. Session 35 complete: §3.8A double-edge autocorrelation ghosting metric — `_ghosting_score_v2(img)` in `bench_anime_stitch.py`; FFT-based autocorrelation of column-mean gradient profile; secondary peak at lag D directly measures repeated-edge structure (ghost signature); score [0–100], 30+ = ghost likely; added as `ghosting_siqe` in `_compute_all_metrics`; original `ghosting_score` kept for GhostGate calibration; 5 new tests in `test_bench_metrics.py::TestGhostingScoreV2`. §1.7C housekeeping: `_crop_to_valid` in `canvas.py` already implements content-aware bounding-box crop (§1.7C marked de facto done). 282 tests passing. Session 34 complete: §1.2C adaptive min-step threshold — `_compute_adaptive_min_disp(edges)` module-level function in `pipeline.py`; returns `max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC * median_adjacent_step)` using dominant-axis displacements; wired into `_filter_edges` before `_reject_static_edges`; `ADAPTIVE_MIN_DISP_FRAC=0.10` added to `constants/anim.py`; exported in `__all__`; 5 new tests in `test_filter_edges.py::TestComputeAdaptiveMinDisp`. 277 tests passing. Session 33 complete: §3.15A SemanticStitch column-level fg-domination barrier — `_build_seam_cost_map()` in `compositing.py` now raises fg-dominated columns (>50% fg-interior coverage) to cost=2.0, forcing the DP into background-corridor columns; fallback when no corridor exists; 5 new tests in `test_compositing.py::TestSeamCostColumnFilter`. §3.14 scroll-axis detection wired into pipeline — `_detect_scroll_axis` imported and called after Stage 9; 'horizontal' scroll type triggers explicit SCANS fallback with diagnostic log (belt-and-suspenders with alignment gate); 5 new tests in `test_canvas.py::TestDetectScrollAxisModule` validating the exported module function. 272 tests passing. Session 32 complete: §1.2A pre-bundle static edge rejection — `_reject_static_edges(edges, min_disp_px)` module-level function in `pipeline.py`; drops edges where both |dx| and |dy| are below `STATIC_EDGE_MIN_DISP_PX=50`; wired at the start of `_filter_edges()` before the geometric consistency filter; `STATIC_EDGE_MIN_DISP_PX=50` constant added to `constants/anim.py`; exported in `__all__`; 5 new tests in `test_filter_edges.py`. 262 tests passing. Session 31 complete: §1.3B PANORAMA stitcher fallback — `_panorama_stitch_fallback(frames, output_path)` in `canvas.py`; uses `cv2.Stitcher_create(mode=0)` for affine-validation failures before SCANS; raises `RuntimeError` on failure so caller falls through; wired into `pipeline.py` between Retry 3 and `_scan_stitch_fallback`; added to `__all__`; 5 new tests in `test_canvas.py`. 257 tests passing. Session 30 complete: §1.1D adaptive GNC f_scale — `_compute_adaptive_f_scale(edges, affines, floor)` in `bundle_adjust.py`; derives data-driven Cauchy loss scale as `max(floor, 2.0 × median_residual_px)`; conditional re-solve in `_bundle_adjust_affine` when adaptive_scale > _BA_F_SCALE × 1.5; warm-started from initial solution; `__all__` added; 5 new tests in `test_bundle_adjust.py`. 252 tests passing. Session 29 complete: §1.10A RLHF post-run quality gate — `_compute_rlhf_score(img_bgr)` + `_get_reward_model()` lazy singleton + `_RLHF_FLAG_THRESHOLD=0.6` added to `bench_anime_stitch.py`; `_compute_all_metrics` now emits `rlhf_score` (float or None) and `rlhf_flagged` (bool) for every test; `StitchRewardModel.predict()` wired as the inference call; 5 new tests in `test_bench_metrics.py`. 247 tests passing. Session 28 complete: §1.9A spatial dedup scans_frames sync — `_spatial_dedup_frames(frames, scans_frames, bg_masks, image_paths, edges, min_displacement_px)` extracted as a testable module-level function in `pipeline.py`; one-line fix adds `[scans_frames[i] for i in keep_idx]` to the dedup block so all SCANS fallbacks use the same frame subset as the main compositing path; `run()` while-loop refactored to call the new function; 5 new tests in `test_pipeline.py`. 242 tests passing. Session 27 complete: §1.8A TOML config loader — `load_asp_config(path, *, override_env=True)` in new `backend/src/anim/config.py`; reads `asp_config.toml` via stdlib `tomllib`, merges all sections into flat dict, writes each key to `os.environ` via `setdefault`; zero new deps; `override_env=False` dry-run mode; 5 new tests. 237 tests passing. Session 26 complete: §1.2B near-dup luma post-filter — `_near_dup_luma_filter(selected_thumbs, selected_paths, threshold)` in `frame_selection.py`; wired as step 8 in `smart_select_frames` (default disabled: `ASP_NEAR_DUP_LUMA=0.0`); `NEAR_DUP_LUMA_THRESH=3.0` constant extracted from pipeline.py magic number; 5 new tests. 232 tests passing. Session 25 complete: §3.9 fix — unified `_compute_aligned_ssim`; removed dead S8 EUCLIDEAN definition (was silently overridden by S9 TRANSLATION version); surviving definition upgraded to MOTION_EUCLIDEAN with (200 iter, 1e-4 tol, gaussFiltSize=5, GT-centric resize, BORDER_REPLICATE); redundant double call in `_compute_gt_metrics` removed; 5 new tests. 227 tests passing. Session 24 complete: §1.4B continuous adaptive gain clamp — `clamp_width = 0.26 − 0.12 × (ref_lum/255)` replaces S18 binary ref<80 threshold; smooth surface from ±26% (pure-black) to ±14% (pure-white); 5 updated tests + 3 new. 222 tests passing. Session 23 complete: §1.7B OpenCV INPAINT_TELEA border fill (`_telea_fill_gaps`) — fast fallback for residual black corners when diffusion inpainting fails; wired into P1.8 except block in `pipeline.py`; zero new dependencies. 5 new tests. 219 tests passing. Session 22 complete: §1.6B gain-adaptive feather minimum (`_gain_to_min_feather`) — `max(40, int(gain_diff×300))` capped at 120px applied as floor after overlap-cap; `frame_gains` tracked in normalization loop; dead code `_normalize_warped_to_median` removed; roadmap housekeeping (§0.5A/B, §1.1C, §1.4A, §1.5A/C/E, §1.6A/B/C marked ✅). 6 new tests. 214 tests passing. Session 21 complete: §1.6C gradient-domain Poisson seam blend (`_poisson_seam_blend`) — `cv2.seamlessClone(NORMAL_CLONE)` in ±20px band around DP seam path; eliminates brightness step at hard cuts without ghosting; gated by `ASP_POISSON_SEAM=1`. 5 new tests. 208 tests passing. Session 20 complete: bg-mask-aware DSFN ramp (`_soft_seam_weight`) — `sim_diffused[both_fg]=0.0` after Gaussian blur prevents background similarity diffusing into fg-vs-fg overlap; bg_mask params were previously passed but unused. 2 new tests. 203 tests passing. Session 19 complete: §1.6A tiered seam cost (`_build_seam_cost_map`) — Tier 2 edge-buffer cost lowered 1.0→0.5, creating gradient interior=1.0→buffer=0.5→background=0.0 for DP routing. 7 new tests. 201 tests passing. Session 18 complete: per-pair coherence gate (`_coherence_skip_mask`) + §1.4A adaptive gain clamp (`_adaptive_gain_clamp`) — normalization skips only frames in bad adjacent pairs (not all frames), gain clamp widens from ±7% to ±14%/±18% for normal/dark scenes. 11 new tests. 194 tests passing. Session 17 complete: per-pixel DSFN blend ramp (`_soft_seam_weight` — ramp now (zone_h,W) not (1,W)), adaptive boundary search range (±100px when tx_spread<5px). 6 new tests. 183 tests passing. Session 16 complete: `_seam_color_match()` — per-channel mean shift of oth_zone toward dom_zone in seam band before S15 blend, reducing color step from post_warp_diff lum to within-band variance (~5 lum). 7 new tests. 177 tests passing. Session 15 complete: `_single_pose_soft_edge()` — narrow ±6px path-guided linear feather at single-pose seam cuts, smoothing hard color step without ghosting. 7 new tests. 170 tests passing. Session 14: `_seam_visibility_score()` no-reference quality metric in benchmark — worst-case adjacent-row luminance jump, wired into `_compute_all_metrics`, 8 new tests. 163 tests passing. Session 13: Multi-frame canvas coverage gate (Stage 10.5) — `_compute_row_coverage()` helper + SCANS fallback when <30% of rows have ≥2-frame coverage. §0 item 2 complete. 155 tests passing. Session 12: Adaptive feather refinement (post_warp_diff < 8 → widen 1.5×, > 16 → narrow 0.75×) + parallel seam DP pre-computation (ThreadPoolExecutor, max 4 workers). 149 tests passing (anim suite). Session 11: Fallback elimination — comparative render gate (2.0× SCANS baseline), alignment gate → advisory, validation retry chain extended to 5 retries, GhostGate absolute floor (40.0), `seam_post_diffs` init bug fixed. SCANS fallbacks: 51 → 4 genuine (tests 54, 59, 73, 89). Session 10: Seam DP vectorized via `minimum_filter1d` (§1.5A ✅), dead S8 DINOv2 definition removed, `_TOONCRAFTER_SEAM_ENABLED` NameError fixed, test import errors fixed, `TestDINOv2Features` rewritten for S9 API. 141 tests passing. Session 9: ToonCrafter seam synthesis wired to worst single-pose seam (§3.6). Session 8: DINOv2 submodular frame selection (§3.3), LSD collinearity in ARAP (§0.1/A3), Aligned-SSIM metric (§3.9). Session 7: Stage 12.5 scroll-axis foreground-extent trim (§2.6). Session 6: perceptual-hash hold detection (§1.11), GNC robust loss for BA (§1.1), SLIC SGM proxy (§3.1). 107 tests passing (was 90 at S5 start). Session 5: alignment stability gate (+0.074 on test08, +0.049 on test25), fg pixel L1 pose metric (+0.010 on test27 with pose-on), 8 new unit tests (90 total). Session 4: ARAP Push phase (full Sýkora 2009). Session 3: pose-consistent frame selection infrastructure. Session 2: RAFT+ARAP+post_warp_diff. Session 1: foreground assembly pipeline.*  
*Corpus: 96 tests; 55 have ground truth. **Avg SSIM ASP vs GT: 0.667 vs simple stitch 0.694** — simple stitch is 3.9% closer to reference on average (session 4 full-run baseline).*  
*True ASP composites: 52/96 (54.2%). Alignment gate (2D motion): test08 0.736→0.809, test25 +0.049. Render quality gate: 31 fallbacks (32.3%). Affine validation: 13 fallbacks (13.5%).*  
*GT verdicts (S4 baseline): asp_better=7 (12.7%), simple_better=26 (47.3%), comparable=22 (40.0%). Best: test17=0.887, test84=0.821. S5 key: test08 now asp_better (0.809 vs simple 0.805).*  
*Root cause: Animated video scenes vs. static-scroll design assumption. Phase correlation measures whole-frame displacement including character animation.*  
*Previous baseline (22 tests, 2026-05-31): 22/22 metric success, avg sharpness 33.14.*

*Research basis (consolidated): [`reports/ASP Consolidated Research Plan.md`](../../reports/ASP%20Consolidated%20Research%20Plan.md) — full synthesis of ML survey, practitioner lessons (Overmix, Hugin, ICE), HITL architecture, structured research plan, and technical survey. Covers failure taxonomy (A/B/C1/C2), Phase 1/2/3 priority roadmap, module specs (frame selection, SAM-2, SGM/SEA-RAFT, ARAP, GNC-BA, background separation, stitching, seam routing, ProPainter, NR-IQA), synergy maps, HITL DAG breakpoints, dataset registry (LinkTo-Anime, ATD-12K, AnimeRun, etc.), and S6–S32 implementation status. Also see [`reports/Image_Stitching_Research.md`](../../reports/Image_Stitching_Research.md) for foreground-assembly paradigm and 13-stage spec.*

---

## How to Use This Document

Each section lists the pain point, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping before committing. Items tagged **[Long-term]** are aspirational or depend on external data collection.

---

## 0. CRITICAL: Pipeline Fundamentally Broken for Animated Video Scenes [Priority 0]

**Established by visual inspection (2026-06-01):** After inspecting actual output images, the pipeline is producing catastrophically bad results on the majority of ASP-succeeded tests. The CV metrics (sharpness, ghosting, SSIM) completely mask this — the benchmark reports 65% "asp_better" when visual reality is approximately the opposite.

**What the failures look like:** Multiple horizontal strips with completely mismatched colors, duplicated body parts at seam boundaries, exposed character poses at different animation states in adjacent strips. The simple stitch, despite less coverage, is visually coherent and usable.

**Root cause:** The pipeline was designed for scrolling static art (manga panels). The test datasets are animated video where characters move independently of the camera. Phase correlation on whole frames cannot separate camera movement from character animation. The temporal median requires ≥3 frames per canvas row to suppress animation artifacts; with 50px frame steps across 1080px frames, most canvas rows have only 1 frame.

**Required fixes before any other work:**
1. Background-only phase correlation in frame selector (run BiRefNet first)
2. Multi-frame canvas coverage check before compositing (fall back to SCANS if median coverage < 2 frames/row) — ✅ DONE (Stage 10.5, `_compute_row_coverage()`, `ASP_COV_MIN_MULTI_PCT=0.30`)
3. Replace sharpness metric with seam coherence metric (row-mean luminance variance) — ✅ DONE
4. Seam validation gate after composite (if adjacent strips differ >15 lum units, reject and use SCANS) — ✅ DONE (render gate)

**Deeper root cause (established 2026-06-03, see `reports/Image_Stitching_Research.md` §8):** Items 1–4 are *symptom mitigations*. The true gap is that the pipeline has **no mechanism to register the deforming foreground across frames.** The character animates while the camera pans, so body parts land in two different poses on either side of every strip seam. Fixing this requires the foreground-assembly stage in §0.1 below — that is the actual solution; everything else raises the floor without raising the ceiling.

---

## 0.1 Foreground Pose Registration — The Core Fix [Priority 0]

**Pain point:** Even ASP's best cases (test09) show torn/doubled character edges at strip seams. The translation-only camera model aligns the *background* perfectly but cannot represent the *non-rigid articulated motion* of the character animating between the frames being stitched. This is the dominant artifact and the reason ASP loses to simple-stitch on ground-truth SSIM (0.669 vs 0.695).

**Key reframing:** This is **multi-frame fusion of moving content** — structurally identical to ghost-free HDR (DDFNet) and video-SR alignment (FDAN). The proven recipe is: estimate optical flow → warp moving content toward a reference → fuse. Applied to the foreground, with anime adaptations (segment-guided flow for flat regions, ARAP/LSD to protect line art).

**Core idea:** Keep the rigid translation model for the background. Add a flow-guided, ARAP-regularised **foreground registration stage** that decomposes foreground motion into `F_fg = T_camera + A_animation`, subtracts the known camera translation, and warps out the residual animation motion so body parts line up across seams. The body is still assembled from multiple frames — each frame's foreground is just re-posed to a common reference before compositing.

### Options

**A — Flow-guided foreground re-posing (recommended core)**
SEA-RAFT dense flow over the fg overlap zone → subtract `T_camera` → symmetric midpoint warp of both strips' foreground toward the mean pose. Similarity-regularised warp first, upgrade to full ARAP later.
- Pros: Directly fixes seam tears. Reuses BiRefNet masks. Overlap-zone-only crops keep it fast.
- Cons: Dense flow tears on flat cel regions (mitigate with segment-guided flow). High implementation effort.
- Refs: SC-AOF (Sensors 2024), DDFNet (Sensors 2022), SEA-RAFT (ECCV 2024).

**B — ARAP cartoon registration (Sýkora 2009)**
Locally-optimal block matching + as-rigid-as-possible shape regularisation + LSD line term. Purpose-built for registering hand-drawn characters across animation poses without bending line art.
- Pros: The canonical method for this exact sub-problem. Preserves line art.
- Cons: Highest implementation complexity. Needs careful energy tuning.
- Ref: Sýkora, Dingliana & Collins, NPAR 2009.

**C — Single-pose-per-component fallback (Eden-Uyttendaele-Szeliski 2006)**
When flow confidence is low (fast action, motion blur), do not warp/average — select one coherent pose per connected foreground component and route the seam around it through background via graph cut.
- Pros: Guarantees one clean instance of each body part. Strictly better than ghost-blending.
- Cons: May drop canvas coverage where a component spans a seam.
- Ref: Eden et al., CVPR 2006.

**Recommendation:** Ship **A with a similarity warp + C as the low-confidence fallback** first; validate on test09. Add **B (full ARAP)** as the quality upgrade once A is proven. Restrict Stage 10 temporal median to background pixels only (near-free correctness fix — stops the median from ghosting the foreground at all).

**Implementation order:** (A5) background-only median → (A1) SEA-RAFT wrapper → (A2) fg/bg flow decomposition → (A4) symmetric midpoint warp → (A6) confidence-gated fallback → (A3) full ARAP. See the consolidated report §2–§4 for the full method (ARAP Push/Regularise phases, LSD collinearity term, two-channel selection).

**Status (2026-06-03 → 2026-06-03 session 2):**
- ✅ **A2/A4** — flow-guided symmetric midpoint warp (DIS or RAFT), seam-band cropping (±taper_px+16px around seam), BORDER_CONSTANT boundary fix, `~valid_content` masking.
- ✅ **A1** — **ptlflow installed**; `sea_raft_s@things` (or best available pretrained RAFT variant) loads lazily on GPU. Flow computed on seam-band crops at max_side=1280 to avoid OOM. Falls back to DIS when ptlflow unavailable. Toggle: `ASP_FLOW_ENGINE=dis` to force DIS.
- ✅ **A3** — **ARAP regularisation** implemented: `_arap_regularise()` in `fg_register.py` fits per-cell (16×16px) rigid median transforms to the fg flow, then bilinearly interpolates smooth per-pixel flow. Prevents raw flow from bending straight line-art strokes. Uses `scipy.interpolate.RegularGridInterpolator`.
- ✅ **A5** — foreground-excluded temporal median in `rendering.py` (background-only plate).
- ✅ **A6** — confidence-gated single-pose fallback when animation residual > `FG_REG_MAX_RESIDUAL`.
- ✅ **Boundary fixes** — BORDER_CONSTANT (no edge-smear), `~valid` masking (no content extension), both-content Laplacian (no ringing at canvas edges).
- ✅ **BiRefNet two-channel selector** — implemented with real BiRefNet masks (not peripheral heuristic); disabled by default (`ASP_TWO_CHANNEL_SELECT=0`) due to overhead and frame-selection regressions. Enable for targeted testing.
- ✅ **LSD collinearity term** (session 8) — `_arap_regularise()` in `fg_register.py` now accepts `image=` and `image_offset=` params. Runs `cv2.createLineSegmentDetector` on the seam-band crop; for fg/bg boundary cells where a line is detected and the projection retains ≥50% of the original flow magnitude, projects the cell's flow onto the line direction (nulling the cross-line bending component). Only fires on boundary cells to avoid corrupting rigid-body translation in the character interior.
- ⬜ **Segment-guided flow (AnimeInterp SGM)** — per-colour-segment centroid flow for scenes where RAFT also fails (very flat, large uniform regions).
- ✅ **ARAP Push phase** — Sýkora's full Push→Regularise algorithm implemented (session 4). `_arap_push()` in `fg_register.py`: per-cell SAD block matching via `cv2.matchTemplate`, 15% improvement threshold, 24px search range, 16×16 cell grid. Push → Regularise is the complete Sýkora 2009 algorithm. Benchmark finding: zero measurable GT-SSIM improvement (flow quality is not the bottleneck; ceiling is animation timing).
- ✅ **Alignment stability gate** (session 5) — Pre-render gate in `pipeline.py` and benchmark: fires when 75th-pct |dx_steps| > 50px (2D/diagonal motion). Falls back to SCANS on normalised frames immediately. test08: +0.074, test25: +0.049.
- ✅ **SLIC SGM proxy** (session 6) — `_slic_sgm_proxy()` in `fg_register.py`: SLIC superpixel centroid tracking replaces RAFT/DIS flow for fg pixels in flat cel-shaded regions. Addresses aperture problem without VGG-19 forward passes. Enable via `ASP_SGM_PROXY=1`.
- ✅ **Perceptual-hash hold detection** (session 6) — `_detect_hold_blocks()` in `frame_selection.py`: detects animation "on twos/threes" holds by thumbnail pixel MAD. Compresses frame universe, surfaces natural pose-change boundaries. Enable via `ASP_HOLD_THRESHOLD=0.025`.
- ✅ **GNC robust loss** (session 6) — `bundle_adjust.py`: upgrade `least_squares` to `loss='cauchy'` + `f_scale=10.0`. Makes BA robust against outlier edges that survive the post-solve residual pruning.

**Benchmark note (2026-06-03, session 2):** RAFT + ARAP + post_warp_diff escalation → SSIM essentially flat vs session 1 (test09: 0.787, test27: 0.709). Experiments tried and their outcomes:
- **Global reference pose (asymmetric alpha)**: catastrophic regression on test27 (-0.151) due to flow noise amplification at α=1.0 seams. Reverted.
- **Character bounding-box crop**: incorrectly cuts horizontal extent for vertical pans (cuts locker background). Reverted.
- **post_warp_diff threshold=22**: marginal +0.002 on test08, -0.001 on test57. Kept.
- **max_residual=50**: consistent +0.001 on test08 (9/13 seams single-pose); no improvement on others.
- **ARAP cell_size=8, n_iter=3**: no measurable SSIM change.

**The SSIM ceiling** for the current corpus is determined by animation timing between selected frames vs the GT reference, not by flow quality or regularisation. RAFT and DIS give identical residual estimates. The midpoint warp halves the pose gap; the remaining half is what limits SSIM.

---

## 0.2 Pose-Consistency-Aware Frame Selection [Priority 1 — Infrastructure Built, Disabled]

**Pain point:** The smart selector uses whole-frame phase correlation, so a "50px displacement" can be 5px camera + 45px limb swing — it picks pose-incoherent frames, maximising the motion §0.1 must later correct.

**Session 3 status (2026-06-03):** Infrastructure shipped but disabled. Two-pass selector implemented in `backend/src/anim/frame_selection.py` and `_smart_select_frames()` in benchmark. Pass 2 uses gradient-magnitude L1 on central-crop thumbnails as a pose proxy. Benchmarking showed this proxy is confounded by background structure (lockers, walls), causing regressions of -0.043 (test04) and -0.026 (test27). Disabled by default (`ASP_POSE_WINDOW_PX=0`).

**What's needed to make this work:** Foreground-only pose similarity — either:
- DWPose/ViTPose joint positions (background-agnostic by design)
- RAFT optical flow on BiRefNet-masked foreground only (similar to but decoupled from Stage 8.5 flow)
- DINO/CLIP features extracted from the foreground mask crop

**Correct implementation path:**
1. Run BiRefNet once on ALL frames before selection (deduplicates the current double-run overhead)
2. Use background-only phase correlation for camera displacement
3. For each camera-qualifying candidate, compute foreground flow vs last selected frame
4. Pick candidate with smallest foreground flow magnitude within the selection window

**Current state (session 8 & 9):** DINOv2 (`dinov2_vits14`) cosine distance metric implemented; model cached as module-level singleton (no reload per test, batch inference). Hold-block penalty in Pass 2 ensures cross-hold candidates are preferred. Session 9: model now processes all frames in one batched forward pass instead of per-frame loops. Enabled with `ASP_POSE_WINDOW_PX=80`. Aligned-SSIM built into the benchmark to decouple framing bias from GT-SSIM.

---

## 0.5 min_gap Threshold Calibration [Priority 2 — Quick Win]

**Pain point:** On the 94-test corpus, 23 of 25 fallbacks (92%) are caused by `min_gap < 50px`. Note: fixing this will produce more ASP-succeeded tests, but those tests will exhibit the same compositing failures described in §0 until that is fixed first. This is not a quality fix — it only changes the fallback rate.

### Options

**A — Lower static threshold to 25px [Quick Win]** ✅ **Shipped (pre-S6)**
Change `MIN_GAP_PX` in `validation.py` from 50 to 25. Immediately rescues ~9 datasets.
- Pros: One-line change. Proven safe — genuine co-located frames have gaps < 5px.
- Cons: Fixed threshold; doesn't adapt to canvas resolution.

**B — Vector magnitude gap (multi-axis) [Quick Win]** ✅ **Shipped (pre-S6)**
Replace `min(|dy|)` with `min(sqrt(dy² + dx²))` for the gap computation. Fixes 6 datasets with diagonal scroll where dy=40px but actual displacement=100px.
- Pros: Physically correct for diagonal scrolls. One-line change.
- Cons: Slightly more complex formula.

**C — Adaptive threshold based on selected frame density** ✅ **Shipped S36**
`_compute_adaptive_min_gap(affines)` in `validation.py` — returns `max(20.0, canvas_span / (N × 3))` where `canvas_span` is the dominant-axis displacement range (`max(dy_span, dx_span)`). Canvas height is not required; the displacement span is a sufficient proxy (it equals canvas_span - frame_h, but frame_h is constant across frames). Wired into Stage 7b of `pipeline.py` as the `min_step` for the first `_validate_affines` call. Log message updated. `_compute_adaptive_min_gap` exported in `__all__`. 5 new tests in `test_affine_validation.py::TestAdaptiveMinGap`.
- Pros: Content-aware; slow-scroll sequences benefit (floor=20px rescues tight-but-valid gaps); fast-scroll/4K now applies a proportionally higher threshold.
- Cons: Span proxy slightly underestimates canvas height by one frame_h, but this is a bounded error (< 5% for typical frame/canvas ratios).

**D — Adaptive rotation/scale thresholds** ✅ **Shipped S47**
`_compute_adaptive_rot_scale(affines) → (max_rotation, max_scale_dev)` in `validation.py`. When frame-to-frame σ of rotation (or scale) < `_ROT_SCALE_CONSISTENCY_THRESH=0.02`, returns loose threshold `0.15` (was hardcoded `0.10`). Consistent rotation/scale signals a systematic camera property (lens barrel distortion, constant zoom); inconsistent values signal BA noise. Wired into Stage 7b initial validation and Retry 0. Constants: `_ROT_TIGHT=0.10`, `_ROT_LOOSE=0.15`, `_SC_TIGHT=0.10`, `_SC_LOOSE=0.15`. Exported in `__all__`. 5 new tests in `test_affine_validation.py::TestAdaptiveRotScale`.
- Targets test5 (zoom-pan: max_rot≈0.111, scale_dev≈0.121 — just above the 0.10 tight ceiling, below 0.15).
- σ≈0 for a true zoom-pan sequence (all frames share the same lens distortion) → loose threshold returned → validation passes without any retry.

**Recommendation:** Implement B first (zero risk, fixes multi-axis scrolls), then A (lower threshold). Combined, these should bring the success rate to ~83% (78/94).

---

## 1.1 Bundle Adjustment Hardening

**Pain point (updated 2026-06-01):** On the 94-test corpus, ratio failures are nearly eliminated — only 2/25 fallbacks (8%) are ratio > 3.0, vs 58% in the pre-Phase-3 corpus. The 2-pronged outlier rejection added in Phase 3 is working well on real-world data. New concern: heuristics tuned for the current corpus may still fail on datasets with >40% true outliers.

### Options

**A — Post-solve residual pruning (current approach)**
After the initial Levenberg-Marquardt solve, compute per-edge predicted-vs-actual translation; reject edges where `|residual| > 3 × median`; re-solve. Simple, fast (~0.15s), proven on the 22-test corpus.
- Pros: Already implemented. Zero new dependencies.
- Cons: Median threshold is corpus-tuned; may fail on datasets with >40% outliers.

**B — RANSAC before LM (consensus pre-filter)** ✅ **Shipped S45**
`_spanning_tree_inlier_filter(edges, num_frames, inlier_threshold=50.0)` in `bundle_adjust.py`. Builds a maximum-weight spanning tree (Kruskal greedy, highest-weight-first), BFS-propagates a reference translation from frame 0, and rejects any edge whose observed dx/dy disagrees with the reference by > 50 px. Spanning-tree edges always pass (residual = 0 by construction). Falls back to original edges when the graph is disconnected or fewer than `max(2, N-1)` inliers survive. Wired at the top of `_bundle_adjust_affine` before DOF setup. 5 tests in `test_bundle_adjust.py::TestSpanningTreeInlierFilter`.
- Implementations: classic RANSAC, MAGSAC++ (adaptive threshold), LO-RANSAC (local optimisation after each model draw). **Shipped:** spanning-tree deterministic consensus (zero random seed, O(E log E), no new dependencies).
- Pros: More principled than post-solve pruning. Especially robust when >30% of edges are bad. Deterministic — no random seed, reproducible results.
- Cons: Significantly slower. MAGSAC++ adds a dependency (poselib or custom impl).
- Reference: [RANSAC variants survey](https://arxiv.org/abs/1905.00604)

**C — Graduated Non-Convexity (GNC) robust loss** ✅ **Shipped S6**
Replace the L2 residual in the LM cost function with a robust loss (Geman-McClure, Cauchy, or Welsch) that automatically down-weights outlier edges during optimisation. The weight schedule is annealed from convex to non-convex so the solver never gets stuck in a local minimum induced by outliers.
- Implementation: `scipy.optimize.least_squares(method='trf', loss='cauchy', f_scale=...)` — can be a one-line swap if the Jacobian is compatible with scipy's interface.
- Pros: No separate rejection step. Theoretical guarantees at up to 70–80% outlier rate (Yang et al., 2019; FracGM 2025 improves convergence further). Generalises better to unseen data.
- Cons: Loss hyperparameter (f_scale) needs tuning. Slower than Option A.
- Reference: [GNC for Spatial Perception (arXiv 1909.08605)](https://arxiv.org/abs/1909.08605)

**D — Adaptive Graduated Non-Convexity (AGNC) ✅ DONE (S30, simplified)**
Simplified AGNC: `_compute_adaptive_f_scale(edges, affines, floor)` in `bundle_adjust.py` — after initial solve, computes `max(floor, 2.0 × median_residual_px)` from the preliminary affines. If adaptive_scale > _BA_F_SCALE × 1.5, re-solves with the data-derived scale (warm-started). For clean data the floor dominates (behaviour unchanged); for uniformly noisy data (median ~30px) the scale widens to ~60px so legitimate edges are not over-penalised. 5 tests in `test_bundle_adjust.py`.
- Implementation: `scipy.optimize.least_squares(method='trf', loss='cauchy', f_scale=...)` with a wrapper that tunes `f_scale` adaptively based on residual distribution between LM iterations.
- Pros: Optimal convergence guarantee (no fixed schedule to tune). Immune to outlier-dominated medians that break Option A. Best-in-class for extreme cases (ratio failures like test13 at 11.1×).
- Cons: More complex than C. Requires monitoring LM iteration state (scipy doesn't expose this natively — needs a custom `jac_sparsity` callback or wrapping in a custom optimizer).
- References: [SAC-GNC (IEEE Xplore 2026)](https://ieeexplore.ieee.org/document/11445542), [GNC arXiv 1909.08605](https://arxiv.org/abs/1909.08605), [Adaptive GNC (OpenReview)](https://openreview.net/forum?id=cIKQp84vqN)

**E — FracGM (fractional programming for Geman-McClure)**
Reformulates the non-convex Geman-McClure minimisation as a convex dual + linear system. 2025 state-of-the-art for robust rotation/translation estimation.
- Pros: Faster convergence than GNC, empirically better at extreme outlier ratios.
- Cons: New dependency; implementation complexity. Overkill unless D shows plateau.
- Reference: 2025 FracGM paper.

**F — Learned outlier scoring (RLHF-guided)**
Train a small MLP on (edge residuals → is_outlier) using feedback from the existing RLHF infrastructure. Replaces hand-tuned threshold with a learned one.
- Pros: Self-improving with accumulated feedback.
- Cons: Requires labelled outlier data from the feedback loop (see §1.10). Not viable until the RLHF loop is closed.

**Recommendation:** Ship C (GNC Cauchy loss, `loss='cauchy', f_scale=10.0`) immediately — it's a one-line scipy change and eliminates the worst outlier failures. Prototype D (AGNC) as the quality ceiling; the adaptive schedule removes the `f_scale` tuning burden. Skip B (RANSAC) and E (FracGM) until C/D show a plateau.

---

## 1.2 Near-Zero / Zero-Translation Edge Filter

**Pain point:** Tests 4, 9, 16, 21 failed `min_gap < 50px` due to co-located or near-static frames placed at the same canvas row, causing temporal median collapse.

### Options

**A — Pre-bundle static edge rejection [Quick Win] ✅ DONE (S32)**
`_reject_static_edges(edges, min_disp_px)` in `pipeline.py`. `STATIC_EDGE_MIN_DISP_PX=50` in `constants/anim.py`. Called at the top of `_filter_edges()` before the geometric consistency filter. 5 tests in `test_filter_edges.py`.
- Pros: Fast, zero dependencies, one-line change.
- Cons: Fixed 50px threshold doesn't scale with canvas resolution or scroll speed.

**B — Near-duplicate frame deduplication via perceptual distance** ✅ **Shipped S26**
Before matching, compare each frame to the previous using mean luma difference, SSIM, or histogram distance. Drop frames below a threshold.
- `_near_dup_luma_filter` in `frame_selection.py` — post-filter on the selected list using mean abs grayscale diff. Default OFF (`ASP_NEAR_DUP_LUMA=0.0`). `NEAR_DUP_LUMA_THRESH=3.0` constant extracted from pipeline.py pre-stage-5 dedup.
- First frame always kept; last frame always retained (canvas extent preservation).
- Pros: Removes the bad source upstream; cleaner than downstream rejection.
- Cons: SSIM adds ~5ms per frame pair (acceptable). Threshold may need tuning per content type.

**C — Adaptive min-step threshold** ✅ **Shipped S34**
Estimate expected inter-frame step as `canvas_height / N_frames`. Flag edges where step < 10% of expected. Automatically scales to different resolutions and scroll speeds.
- `_compute_adaptive_min_disp(edges)` in `pipeline.py` — returns `max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC * median_adjacent_step)` on the dominant scroll axis. Wired into `_filter_edges` before `_reject_static_edges`. `ADAPTIVE_MIN_DISP_FRAC=0.10` constant in `constants/anim.py`. 5 new tests in `test_filter_edges.py::TestComputeAdaptiveMinDisp`.
- Pros: Content-adaptive; handles 1080p and 4K equally well.
- Cons: Estimate can be wrong for non-uniform scroll (e.g., scene transitions).

**D — Temporal variance filter (motion energy)** ✅ **Shipped S39**
`_temporal_variance_filter(thumbs, paths, sigma_threshold)` in `frame_selection.py`. Stacks (i-1, i, i+1) thumbnail triplet; drops interior frame i when mean per-pixel variance < sigma_threshold (in [0,1]² space). `TEMPORAL_VAR_THRESH=1e-3` in `constants/anim.py`. Default disabled: `ASP_TEMPORAL_VAR_THRESH=0.0`. Wired as step 1a in `smart_select_frames`.
- Pros: Catches static frames before matching runs — prevents zero-displacement edges from entering the edge graph. Complements §1.2A/B/C which act on edges or selected frames.
- Cons: Slightly higher compute than SSIM. Requires storing three frames in memory simultaneously.

**Recommendation:** Implement B first (cleanest fix, removes the bad source). Follow with C to make the residual threshold content-adaptive. B and C are complementary; D is a research-track alternative.

---

## 1.3 Scale and Rotation Handling

**Pain point:** test5 (scale_dev=0.121, max_rotation=6.35°) represents zoom-and-pan sequences that the translation-only canvas model cannot handle. The affine validator correctly rejects these, but the rejection discards a potentially valid output.

### Options

**A — Full 2×3 affine warp per frame**
When `max_scale_dev > 0.05` or `max_rotation > 0.03`, replace translation-only placement with per-frame `cv2.warpAffine`. Allows scale and rotation compensation.
- Pros: Handles all affine distortions. Directly addresss the failure mode.
- Cons: Higher compute; introduces resampling blur near edges (proportional to warp magnitude). Requires per-frame affine estimation (currently only global stats are computed).

**B — OpenCV Stitcher PANORAMA fallback [Quick Win] ✅ DONE (S31)**
`_panorama_stitch_fallback(frames, output_path)` in `canvas.py`. Uses `cv2.Stitcher_create(mode=0)`; raises `RuntimeError` on failure. Wired into `pipeline.py` between Retry 3 and SCANS — catches all exceptions so SCANS remains the ultimate safety net. 5 tests in `test_canvas.py`.
- The existing `simple_stitch` path in `image_merger.py` already uses this — the change is routing the affine-rejection fallback here instead of SCANS.
- Pros: Reuses existing infrastructure. Handles arbitrary affine distortions with no new code.
- Cons: PANORAMA stitcher is slower and sometimes produces barrel distortion on vertical scroll sequences.

**C — Scale normalisation before bundle adjustment** ✅ **Shipped S54**
`_normalize_frame_scales(frames, edges, scale_thresh=0.05)` in `pipeline.py`. Extracts per-edge scale `s_ij = sqrt(a²+b²)` from matched affines; BFS spanning tree from frame 0 propagates absolute per-frame scale factors; resizes frames by `1/scale[i]` (Lanczos-4); resets edge M diagonal to 1.0, divides tx/ty by `scale[i]`. No-op when scale deviation < threshold or graph is disconnected. `SCALE_NORM_THRESH=0.05` in constants; `ASP_SCALE_NORM_THRESH=0.05` to enable (default OFF). 5 tests in `test_pipeline.py::TestNormalizeFrameScales`.
- Pros: All downstream stages (canvas, rendering, compositing) receive geometrically consistent frames without any per-stage changes. Complementary to §1.3E (S48) and §0.5D (S47).
- Cons: Lanczos-4 introduces mild ringing on very high-contrast edges at large scale ratios (>30%). Frames after normalisation have different heights, which breaks Stage 2's width-only normalisation invariant — wire after width normalisation.

**D — Homography (projective) warp per frame**
Extend A to full 8-DOF projective warp. Handles perspective (slight 3D parallax) in addition to affine.
- Pros: Broadest coverage.
- Cons: Projective warp on scroll sequences tends to over-fit small parallax into large geometric distortions. High risk of quality degradation on simple sequences.

**E — Similarity transform (scale + rotation + translation)** ✅ **Shipped S48**
`_extract_similarity(M) → (2,3) float32` in `matching.py`. Closed-form Procrustes projection: `a_sym=(M[0,0]+M[1,1])/2`, `b_sym=(M[0,1]-M[1,0])/2` → `[[a_sym, b_sym, tx], [-b_sym, a_sym, ty]]`. Shear discarded (feature matchers cannot reliably distinguish shear from perspective). `_SIMILARITY_MODE` flag (default OFF, `ASP_SIMILARITY_MODE=1` to enable). In `_match_pair`, similarity projection replaces translation-only strip when flag enabled. `ASP_SIMILARITY_MODE` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 new tests in `test_matching.py::TestExtractSimilarity`.
- Complementary to §0.5D (S47): validation accepts systematic rotation/scale (`σ<0.02` → loose 0.15 threshold); similarity mode provides the correct matched affine for validation to accept.

**Recommendation:** B is lowest effort (reuses existing code path). E is the most physically appropriate model for zoom-pan sequences. Implement B as immediate fallback; prototype E as a dedicated zoom-scroll mode.

---

## 1.4 Gain Clamp Widening for Dark Scenes

**Pain point:** 17/22 tests hit the `[0.88, 1.14]` gain clamp. Dark scenes (ref_lum < 70) have proportionally larger gain swings, leaving some frames under-corrected.

### Options

**A — Conditional clamp based on ref_lum [Quick Win]** ✅ **Shipped S18**
Use `[0.82, 1.22]` when `ref_lum < 80`, `[0.88, 1.14]` otherwise.
- Pros: One-line config change. Targeted fix for dark scenes.
- Cons: Binary threshold; doesn't smoothly scale with luminance level.

**B — Continuous clamp scaling** ✅ **Shipped S24**
Linearly interpolate clamp width between dark and bright anchors: `clamp_width = 0.26 - 0.12 × (ref_lum / 255)`. Smooth, no discontinuity at a single threshold.
- Pros: More principled than A.
- Cons: Requires tuning two anchor values instead of one.

**C — Per-frame adaptive clamp (background mask only)** ✅ **Shipped S40**
`_bg_gain_unclamped(ref_lum, frame_lum, override_threshold=0.20)` in `compositing.py`. When `_adaptive_gain_clamp` would cut the ideal correction by >20%, returns raw ideal gain for bg pixels. Wired into the bg-only normalization loop; foreground pixels were already excluded at the application site. 5 tests in `test_compositing.py::TestBgGainUnclamped`.
- Pros: Eliminates residual banding when a dark/bright frame's ideal correction exceeds the clamp. Symmetric (brightening and darkening both covered).
- Cons: Background clipping possible for extreme gain (5×+); `np.clip(0,255)` handles this.

**D — Multi-scale gain (tone-mapping inspired)** ✅ **Shipped S46**
`_multiscale_gain_map(frame, reference, bg_mask, sigma=30.0, gain_min=0.5, gain_max=2.0)` in `compositing.py`. Computes per-pixel gain = `ref_blurred / (frame_blurred + ε)` where both are Gaussian-blurred background luminance maps (σ=30px). Foreground pixels are zeroed before the blur so character luminance does not contaminate the bg model. Applied via `gain_map[bg_sel, np.newaxis]` (bg only, fg untouched). `_MULTISCALE_GAIN` flag (default OFF, `ASP_MULTISCALE_GAIN=1`). `MULTISCALE_GAIN_SIGMA=30.0` in `constants/anim.py`. 5 tests in `test_compositing.py::TestMultiscaleGainMap`.
- Pros: Handles non-uniform scene lighting (half-dark/half-bright panels). Zero new deps.
- Cons: ~2ms overhead per 1080p frame (vs ~0.1ms for scalar gain). Default OFF.

**E — Background histogram matching** ✅ **Shipped S49**
`_bg_histogram_lut(src_pixels, ref_pixels) → float32[256]` + `_apply_bg_histogram_match(frame, reference, bg_mask) → uint8(H,W,3)` in `compositing.py`. CDF-matching LUT built via `np.searchsorted(ref_cdf, src_cdf, side="left")` — for each source intensity `v`, maps to the smallest reference intensity `u` where `CDF_ref(u) ≥ CDF_src(v)`. Per-channel application to background region (fg pixels unchanged). Identity-LUT fallback for degenerate masks (< 10 bg pixels). `_HISTOGRAM_MATCH` flag (default OFF, `ASP_HISTOGRAM_MATCH=1`). Wired as third branch in normalization loop between `_MULTISCALE_GAIN` and scalar path. Roadmap note "needs CLAHE / opencv-contrib" was incorrect — `cv2.createCLAHE()` is in base OpenCV, but standard CDF matching is cleaner and zero-overhead. 5 tests in `test_compositing.py::TestBgHistogramLut`.
- Pros: Handles non-linear tonal mismatch (S-curve exposure differences). Zero new deps (pure numpy). Does not cause hue shifts (per-channel, not luminance-only).
- Cons: ~0.5ms overhead per frame. Mutual-exclusive with `_MULTISCALE_GAIN` (multiscale takes priority). For simple multiplicative gain differences, scalar path is equally effective.

**F — Per-frame exposure outlier rejection** ✅ **Shipped S50**
`_reject_exposure_outliers(frame_lums, max_deviation_lum) → List[bool]` in `compositing.py`. Computes the median bg-lum across all frames with valid lum values; returns True for any frame where `|lum − median| > max_deviation_lum`. Frames with None lum are never rejected. Fallback: all-False when < 3 valid frames (unreliable median). `_EXPOSURE_OUTLIER_THRESH` flag (default 0.0=off, `ASP_EXPOSURE_OUTLIER_THRESH=60.0`). Wired after `_coherence_skip_mask` in normalization loop via logical-OR — skipped frames still contribute warped pixel content, only gain correction is suppressed. `EXPOSURE_OUTLIER_THRESH=60.0` in `constants/anim.py`. `ASP_EXPOSURE_OUTLIER_THRESH` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_compositing.py::TestRejectExposureOutliers`.
- Pros: Complements §1.4C (`_bg_gain_unclamped`): C aggressively corrects large-gain frames; F suppresses correction entirely for extreme outliers where correction would overshoot. Handles flash frames, accidental HDR blending, and scene-change frames that slip past hold detection.
- Cons: Default OFF — no effect unless `ASP_EXPOSURE_OUTLIER_THRESH > 0`. Threshold requires per-source tuning (60 lum = 24% brightness at ref=250, 75% at ref=80).

**Recommendation:** A is a one-line config change, ship immediately. B as a follow-on smoothing pass. E ✅ shipped S49. F ✅ shipped S50.

---

## 1.5 Stage 11 Composite Performance

**Pain point:** Stage 11 (hard-partition composite) averages 24.5s, peaking at 41.9s, accounting for ~35% of total ASP runtime. Seam DP and feather computation are the primary bottlenecks.

### Options

**A — Vectorise seam DP with NumPy** ✅ **Shipped S10**
The per-row minimum-cost path accumulation is now handled by `scipy.ndimage.minimum_filter1d(size=3, mode='constant', cval=np.inf)` — replaces the Python row-by-row loop and `left`/`right` array allocations. Traceback uses slice-argmin. Expected speedup: 5–10×.

**B — CUDA seam DP via PyTorch scatter/gather**
Implement the DP on GPU using PyTorch operations.
- Pros: Fastest possible; ~50–100× speedup on a 3090 Ti.
- Cons: Requires GPU. Adds kernel complexity. DP is inherently sequential by row — parallelisable only column-wise within each row.

**C — Restrict seam search window [Quick Win]** ✅ **Shipped S17**
Current ±250px window scans 500 columns per row. Reduce to ±100px for sequences with `dx_cv < 5` (low horizontal drift). Auto-detect from bundle adjustment output. Reduces DP grid by 60%.
- Pros: Drop-in optimisation, no algorithm change.
- Cons: May clip optimal seam path on high-drift sequences.

**D — Cache seam path across RLHF iterations** ✅ **Shipped S44**
`_make_seam_cache_key(frame_keys, k, cost_flags)` + `_get_seam_cost_flags()` in `compositing.py`. Key: `(tuple(image_paths), k, (_POISSON_SEAM, _TOONCRAFTER_SEAM))`. `_composite_foreground` accepts `frame_keys` + `seam_path_cache` optional params; cache checked before zone array allocation, populated after DP. `AnimeStitchPipeline` stores `self._seam_path_cache: Dict = {}` and passes it at Stage 11. Memory: ~4 KB per seam path (W×int32). Net speedup for RLHF re-runs: eliminates DP executor latency entirely on 2nd+ call.

**E — Parallel seam computation per strip** ✅ **Shipped S12**
When the panorama has M non-overlapping seam zones (between adjacent frame pairs), compute the M seams in parallel using `concurrent.futures.ThreadPoolExecutor`. The GIL is released during NumPy operations.
- Pros: Linear speedup proportional to M for multi-frame panoramas.
- Cons: Requires refactoring to identify independent seam zones.

**Recommendation:** A is the highest-leverage change (no dependencies). Combine with C for sequences where it applies. D is free win for RLHF iteration speed.

---

## 1.6 Ghosting Reduction in Composite Zone

**Pain point:** ASP-succeeded tests consistently have higher ghosting than simple stitch (8/10 tests). Stage 11's hard-partition seam reintroduces ghost-like edge artefacts when seams bisect character bodies.

### Options

**A — Increase foreground penalty weight in seam DP** ✅ **Shipped S19 (tiered cost)**
The `sem_cost` term in `_seam_cut` (P2.4) already routes seams away from BiRefNet-masked foreground. Increase the foreground penalty multiplier (current: partial implementation) to fully deter seams through character regions.
- Pros: Minimal code change. Directly addresses the seam-through-character problem.
- Cons: Very high penalty may force seams into narrow background corridors that cause visible aliasing.

**B — Adaptive feather width** ✅ **Shipped S22**
Make `_FADE_ROWS` a function of `|gain_A - gain_B|` across the seam. Wider feather when gain difference is large.
- Proposed formula: `fade = max(40, int(|gain_diff| × 300))`, capped at 120px.
- Pros: Smooth transitions reduce perceptual ghosting near boundaries.
- Cons: Wide feathers on high-gain-difference boundaries may blur the seam zone visibly.

**C — Poisson blending at seam zone [Quick Win]** ✅ **Shipped S21**
Replace the linear feather with gradient-domain seamless cloning (`cv2.seamlessClone`) in a ±20px band around the seam. Eliminates the brightness step even when gain correction is at its limits.
- Pros: OpenCV built-in. Medium effort, measurable improvement.
- Cons: `cv2.seamlessClone` is CPU-only and can be slow on large seam zones (~1–3s extra). Restrict to final-output mode.

**D — ToonCrafter synthetic frame fill**
In high-overlap zones (tight scroll, e.g., test22 at 90px steps), use `anim/anim_fill.py` (ToonCrafter) to generate synthetic intermediate frames that fill the overlap region, reducing ghosting by interpolation rather than blending.
- Pros: Best visual quality. Eliminates ghosting structurally.
- Cons: High compute cost (GPU inference per fill region). Best reserved for `final_quality=True` mode.

**E — Edge-aware guided filter at seam**
Apply a guided filter (using one of the frame strips as guide) to the feather transition band. Preserves sharp edges at character outlines while blending smoothly in texture regions.
- Pros: Faster than Poisson blending. Preserves line art.
- Cons: `cv2.ximgproc.guidedFilter` requires `opencv-contrib`. One additional dependency.

**Recommendation:** A is first priority. C as a [Quick Win] for seam-zone smoothness in final-output mode. B and E as follow-on improvements. D reserved for premium output mode.

---

## 1.7 RecDiffusion Border Rectangling

**Pain point:** Hard 30px edge crop leaves irregular black borders on outputs with diagonal or non-uniform scroll motion.

### Options

**A — Route through `sr_stitcher.inpaint_borders()` [available now]**
`anim/sr_stitcher.py` (P3.4) already implements seam+border inpainting via diffusers. Replace the hard `_crop_to_valid` with a call to `sr_stitcher.inpaint_borders()` when `sr_mode=True`.
- Pros: Reuses existing infrastructure. Best quality.
- Cons: Adds diffusion inference time (5–30s depending on border area). Requires `sr_mode=True`.

**B — OpenCV INPAINT_TELEA fallback** ✅ **Shipped S23**
Use `cv2.inpaint(src, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)` for border fill. Faster than diffusion; quality is lower but avoids the diffusion dependency in standard mode.
- Pros: Zero new dependencies. Fast (~0.5s for typical borders).
- Cons: Visible smearing artefacts on large border regions (>50px). Not suitable for borders spanning characters.

**C — Content-aware minimal bounding crop [Quick Win]** ✅ **De facto implemented**
`_crop_to_valid(canvas, valid_mask)` in `canvas.py` already computes the minimal bounding box of valid (non-black) pixels and crops to that. When valid_ratio ≥ 80% the simple row/col bounding-box is used; when < 80% (diagonal scroll → parallelogram valid region) it falls back to `_largest_valid_rect` for the maximum inscribed rectangle. No action required.
- Pros: Always safe. No artefacts.
- Cons: Output may be smaller than a perfectly filled output. Doesn't eliminate the invalid region, just removes it.

**D — ControlNet inpainting with border context**
Use a ControlNet-guided inpainting model conditioned on the known content near the border. Produces style-consistent fills for anime content.
- Pros: Best visual quality for complex borders.
- Cons: Requires a compatible ControlNet model. Significantly more complex than A.

**E — Stable Diffusion 3 outpainting**
Route border rectangling through the existing SD3 integration. Outpaint the border region given the valid interior as context.
- Pros: High-quality fills. SD3 integration already exists.
- Cons: Slow, expensive for small border corrections.

**Recommendation:** C immediately (no dependencies, always safe). A as enhanced path when `sr_mode=True`. Skip D/E — A subsumes them with existing infrastructure.

---

## 1.8 ASP Pipeline Configuration File

**Pain point:** Many pipeline constants (gain clamp, `_FADE_ROWS`, `min_gap_threshold`, ECC pyramid levels) are hardcoded in `constants.py` or inline in `pipeline.py`. Tuning requires code edits.

### Options

**A — TOML config per pipeline run [Quick Win] ✅ DONE (S27)**
`load_asp_config(path, *, override_env=True)` in `backend/src/anim/config.py`. Reads `asp_config.toml` via stdlib `tomllib`, merges all sections into a flat dict, writes each key to `os.environ` via `setdefault`. Env vars always win. Zero new dependencies. 5 unit tests (`test_config.py`).
- Pros: No new dependencies. Enables rapid iteration. Config can be committed alongside test datasets.
- Cons: Config schema must be kept in sync with `constants.py`.

**B — JSON Schema–validated config ✅ DONE (S42)**
`_CONFIG_SCHEMA` dict (14 known `ASP_*` keys → type + range spec) + `validate_asp_config(config, *, strict=False)` in `config.py`. Returns list of violation messages; `strict=True` raises `ValueError`. Unknown keys emit `UserWarning` (forward-compat). Wired via `load_asp_config(validate=False, strict=False)`. Zero new deps — inline schema replaces external `jsonschema`. 5 tests in `test_config.py::TestValidateAspConfig`. 317 tests passing.
- Pros: Better developer experience; validation at load time; clears §1.10B pre-condition.
- Cons: Schema must be manually updated when new `ASP_*` keys are added.

**C — GUI settings panel for ASP params**
Expose the most-tuned constants as sliders/checkboxes in the StitchTab UI. Persisted in `QSettings`.
- Pros: Best UX for non-developer users.
- Cons: Significant UI effort. Best deferred until pipeline stabilises.

**D — Per-dataset profile system**
Save a successful pipeline config alongside each output panorama. Load it on re-processing the same dataset. Enables experimentation without losing working configurations.
- Pros: Natural version control for pipeline settings.
- Cons: Profile discovery and UI to select profiles adds complexity.

**E — Environment variable overrides (12-factor style)**
Allow any config key to be overridden via `ASP_GAIN_CLAMP_LOW=0.82 python main.py ...`. Useful for CI and scripting without a config file.
- Pros: Zero new dependencies. Works with any launcher.
- Cons: Poor discoverability. Better as a complement to A than a replacement.

**Recommendation:** A first (unblocks research iteration). B adds minimal overhead and prevents config mistakes. C when pipeline stabilises. D as a follow-on to C.

---

## 1.9 Fallback Path Purity

**Pain point:** When ASP falls back to SCANS, it runs on BiRefNet-preprocessed, ECC-normalised frames rather than original source frames. Tests 13 and 16 showed sharpness degradation of ~14–15 points vs running SCANS on originals.

### Options

**A — Pass original frames to SCANS fallback [Quick Win] ✅ DONE (S28)**
`scans_frames` was already set at Stage 2 (pre-BiRefNet) — the original pain point was written before this placement was fixed. Remaining bug: the post-Stage-6 spatial dedup updated `frames` but never synced `scans_frames`. Fixed by extracting `_spatial_dedup_frames()` (module-level, testable) and adding the one-line sync. 5 new tests in `test_pipeline.py`. See CHANGELOG for full rationale.
- Pros: Minimal change. Eliminates the desync between fallback path and main pipeline.
- Cons: Doubles the frame memory footprint during the pipeline run (originals + processed).

**B — Dual path from Stage 1**
Fork the pipeline at Stage 1: one path applies preprocessing; the other keeps originals. Merge only at the fallback decision point.
- Pros: Enables per-stage fallback decisions (e.g., use ECC-normalised for matching but originals for compositing).
- Cons: Increases complexity. Higher memory cost.

**C — On-demand reload from disk ✅ DONE (S41)**
On fallback trigger, reload original frames from disk rather than holding them in memory.
`_reload_scans_frames(paths)` in `pipeline.py` — calls `_load_frames(paths)` then `_normalise_widths()`; wired into all 5 fallback sites via `_sf = scans_frames or _reload_scans_frames(image_paths)`. `ASP_SCANS_RELOAD=1` skips the Stage-2 `list(frames)` snapshot; both dedup syncs guarded with `if scans_frames else []`. Saves ~87 MB for 14-frame 1080p on the success path. 5 new tests in `test_pipeline.py::TestReloadScansFrames`. 312 tests passing.
- Pros: Zero extra memory during successful pipeline runs.
- Cons: Adds disk I/O latency at fallback time (~0.5–2s for 14 frames). Acceptable for a fallback path.

**Recommendation:** A for immediate fix. C as a memory-efficient alternative if frame counts exceed available RAM.

---

## 1.10 RLHF Loop Integration

**Pain point:** RLHF infrastructure exists (`rlhf/` module, `StitchFeedbackTab`, reward model CNN, DRL agent) but is not wired into the main pipeline evaluation loop. Collected feedback cannot improve future runs automatically.

### Options

**A — Post-run quality gate ✅ DONE (S29)**
`_compute_rlhf_score(img_bgr)` in `bench_anime_stitch.py`. Lazy-loads `StitchRewardModel` via `_get_reward_model()` singleton. `_compute_all_metrics` now emits `rlhf_score` (float or None) and `rlhf_flagged` (bool, threshold=0.6). 5 tests. 247 tests passing.
- Pros: Closes the feedback loop without requiring the DRL agent to be production-ready.
- Cons: Reward model must be calibrated before its scores are meaningful. Currently uses random weights.

**B — Parameter search with reward signal (offline Bayesian optimisation)**
Use the reward model as the objective for Bayesian optimisation (e.g., `optuna` or `scikit-optimize`) over gain clamp, feather width, and seam cost weights. Run offline on the 22-test corpus.
- Pros: Most promising path to measurable quality improvement from existing infrastructure. Automatic hyperparameter tuning.
- Cons: Requires a well-calibrated reward model and sufficient feedback data.

**C — Online DRL agent for ECC/registration [Long-term]**
Wire the DRL agent (`rlhf_trainer.py`) into Stage 8 (ECC sub-pixel refinement) to adaptively adjust pyramid levels and convergence criteria based on the reward signal.
- Pros: Fully adaptive pipeline; improves with every run.
- Cons: Requires significantly more feedback data than currently available. Training instability risk.

**D — Active learning: select uncertain outputs for human review**
Use the reward model's confidence score to identify outputs where the model is least certain. Prioritise those for human review in the feedback tab.
- Pros: Maximises the information gain per labelling effort.
- Cons: Requires uncertainty estimation from the reward model (e.g., MC dropout).

**Recommendation:** A is the immediate next step. B is the most promising quality improvement from existing infrastructure. D maximises feedback ROI. C is a [Long-term] item contingent on sufficient feedback volume.

---

## 2.0 ASP Human-in-the-Loop Augmentation [Priority: Medium — Unique Multiplier]

**Context — What the Hybrid Stitch Panel Does and Does NOT Cover**

The existing `HybridStitchPanel` (`gui/src/tabs/models/gen/hybrid_stitch_panel.py`, 2143 lines) is a complete manual panorama studio: sequence reordering, point-to-point homography, per-frame color correction, seam painting, mesh warp, and final render. It is excellent for static panorama content. However it is architecturally **separate from the ASP pipeline** — it builds a sequence and emits it to the Stitch tab, where `AnimeStitchPipeline` runs fully automatically. User interactions in the Hybrid panel do not reach any of the stages that make ASP hard: BiRefNet fg masks, ARAP flow registration, per-seam post_warp_diff decisions, temporal median coverage, or the gt-coupled frame selector.

**The core gap:** Every failure mode unique to animated video — torn character edges, pose-residual ghosting, the GT-coupling problem in frame selection — requires a human to see and act on intermediate pipeline state that is currently only logged to the console. The pipeline already computes the right diagnostics (`post_warp_diff` per seam, `residual_px` per boundary, BiRefNet mask coverage, seam coherence, frame selection scores); it just never surfaces them in the UI.

**Design principle:** Intercept, not replace. The ASP pipeline should run as normal and emit its rich intermediate state through `StitchWorker` signals. An **ASP Reviewer panel** in the Edit tab receives these signals, displays stage-specific visualisations, and optionally writes override files back to `StitchWorker` before the next stage runs. Nothing changes in the pipeline code itself; the worker gains pause/resume hooks.

**Why this matters more than any single algorithmic improvement:**
- The GT-coupling wall (§0.2) means automated frame selection cannot reliably improve GT-SSIM. A user who can *see* the pose residuals per seam and move one frame can directly close the 0.045 framing gap that all sessions 1–5 failed to close automatically.
- The 31/96 render-gate fallbacks include cases where the gate fires on 1–2 bad seams; a user who can escalate those seams to single-pose would rescue the composite.
- Many "simple_better" cases exist because the user assembled more canvas than the GT shows (test27: 2× scale mismatch). A user who sees the final canvas overlay can trim excess rows/cols before the metric is measured.

---

### 2.1 Frame Selection Assistant [Quick Win]

**Pain point:** `_smart_select_frames()` picks frames silently. When it picks a frame where the character is mid-swing (large fg pixel L1 score vs the previous selection), the user has no recourse — the pipeline commits to those frames before any GPU work.

**Options**

**A — Selection Review Dialog [Quick Win]**
After frame selection completes but before matching begins, show a modal strip of thumbnail tiles (96 px wide, scrollable horizontally). Each tile shows the frame, its canvas advance (px), and a colour-coded "pose diff" bar (fg pixel L1 vs previous frame: green ≤ 0.2, yellow 0.2–0.5, red > 0.5). User can:
- Click any tile to exclude it (greyed-out with strikethrough)
- Drag tiles to reorder
- Click "Add frame…" to insert from disk
- Click "Accept" to proceed or "Re-run Auto" to recompute
- Single toggle: "Show only frames with high pose diff (> 0.4)" to filter to problem frames

*Implementation:* `SelectionReviewDialog` — modal `QDialog`, spawned from `StitchWorker.stage_selection_complete` signal. Returns `List[str]` (approved paths) when accepted. ~300 LOC.
- Pros: Directly addresses the GT-coupling problem. User can manually pick the frame closest to the GT's temporal reference.
- Cons: Adds one user interaction step; can be bypassed by "Accept All" default.

**B — Inline Sequence Editor in Stitch Tab**
Replace the plain path list in the Stitch tab with the `SequenceManager` widget from `HybridStitchPanel` (already implemented: thumbnails, drag-drop, add/remove). Add pose-diff colour coding as a `QLabel` overlay on each thumbnail.
- Pros: Reuses 100% existing widget code. No new dialog.
- Cons: Runs before the pipeline computes pose diffs, so initial display is uncoloured until a previous run has cached scores.

**C — Continuous Live Preview [Research]**
Stream video thumbnails from the source file and let the user scrub a timeline to mark keyframes manually before any processing. Purpose-built for anime where "on twos" holds are visually obvious.
- Pros: Most powerful; user can directly exploit animation-hold structure.
- Cons: Requires video file (not just extracted frames); adds timeline UI complexity.

**Recommendation:** A immediately (modal dialog, minimal code, maximum control). B as a follow-on to make the Stitch tab's input area richer. C deferred until video-file input is supported.

---

### 2.2 Edge Graph Inspector & Editor [Quick Win] [Read-Only Viewer ✅ Session 62]

**Shipped (Session 62):** `EdgeGraphInspectorDialog` — read-only viewer with circular node layout, confidence-coloured edges, edge table, and `⬡ Edges` button wired into the Stitch tab. Visual check pending first real stitch run with `save_intermediate=True`. Interactive re-solve (delete/add/re-bundle) deferred as §2.2B below.

**Pain point:** The matching step (Stages 5–6, `_pairwise_match()` → `_filter_edges()`) builds a graph of frame-pair correspondences. Bad edges (LoFTR false matches on character-heavy frames) cause the bundle-adjust to pull frames into wrong positions. The user currently cannot see which edges survived or why, and cannot delete the ones causing the pull.

**Options**

**A — Graph Visualisation with Delete/Add [Quick Win]**
After bundle adjustment, emit the edge graph via `StitchWorker.stage_edges_ready(edges: List[dict])`. Display as a node-link diagram where:
- Each node = one selected frame (thumbnail at 64 px)
- Each edge = a match, coloured by weight (dark green = LoFTR 0.9, yellow = TM 0.4, red = low-weight)
- Thickness proportional to match count
- Dashed = edges that were rejected by `_filter_edges`
- Click an edge → show side-by-side frame pair with matched keypoint overlays
- Right-click an edge → "Delete edge" (marks it for exclusion before re-solve)
- Right-click two nodes → "Add edge" (runs LoFTR on that pair on demand)
- "Re-solve Bundle" button → re-runs `_bundle_adjust_affine` with the edited edge set

*Implementation:* `EdgeGraphWidget` using `QGraphicsScene` (same Qt primitives already used in the Hybrid panel's canvas). ~400 LOC.
- Pros: Directly debuggable for the 2/25 bundle-adjustment failures. User sees exactly which edges are pulling frames.
- Cons: Requires re-running bundle adjust on edit; adds ~0.15s latency per re-solve (acceptable).

**B — Edge Table (Tabular View)**
Emit edges as a `QTableWidget` with columns: Frame-i, Frame-j, Method, Weight, Residual-post-solve, Status (inlier/outlier). Sortable by residual. Click to preview. Delete via row selection.
- Pros: Simpler than graph view. Better for data-focused users.
- Cons: Less intuitive for understanding spatial relationships.

**C — Automatic Bad-Edge Highlighting Only**
No manual deletion; just highlight edges above a residual threshold in red after bundle adjust, with a tooltip explaining why they might be bad. Non-interactive.
- Pros: Near-zero implementation (post-process the existing log output).
- Cons: Doesn't give the user any control.

**Recommendation:** A for maximum utility (builds on existing `QGraphicsScene` patterns). B as a lighter alternative that can be shipped faster. C as an immediate intermediate step while A is being built.

---

### 2.3 Anchor Frame & Canvas Layout Inspector [Priority: Medium] [Read-Only Viewer ✅ Session 63]

**Shipped (Session 63):** `CanvasLayoutInspectorDialog` — read-only viewer showing N frame rectangles at their final canvas positions as colour-coded polygons, stats label (N frames · W×H canvas), Frame/tx/ty table, and `⬗ Canvas` button wired into the Stitch tab. Visual render verified with synthetic 3-frame fixture. Interactive anchor override and overlap-zone heatmap deferred as §2.3B.

**Pain point:** The pipeline chooses the reference frame for bundle adjustment (the anchor) implicitly — usually the frame with the most/best edges. A wrong anchor causes the whole canvas to be skewed relative to a natural reference. The user can't override it, and the current UI doesn't show which frame IS the anchor.

**Options**

**A — Anchor Selector + Canvas Preview**
After bundle adjustment, emit `StitchWorker.stage_canvas_ready(affines, canvas_h, canvas_w, anchor_frame_idx)`. Show:
- A "Canvas Layout" thumbnail: all frames drawn as semi-transparent coloured rectangles on their canvas positions, with the anchor frame highlighted in gold
- Dropdown: "Anchor frame: [frame name]" with the option to change it
- Changing the anchor → re-computes affines (translating all by the delta), re-draws layout (fast, no matching re-run)
- Each frame rectangle is drag-nudgeable (±10px in x/y) for manual fine-tuning of placement
- "Show overlap zones" toggle: colour-codes rows by coverage count (red = 1 frame only, green = 3+)

*Implementation:* `CanvasLayoutWidget` — `QGraphicsScene` with rectangle items per frame. Re-solve for anchor change is just a matrix translation, ~2ms. ~350 LOC.
- Pros: Directly addresses systematic canvas tilt from bad anchor choice. Also surfaces single-frame coverage zones (informing the user where the temporal median will fail).
- Cons: Nudging individual frames bypasses the bundle-adjustment constraint; user could create geometrically inconsistent canvas.

**B — Anchor Override Only (No Visual)**
Add a "Lock anchor to frame N" checkbox in the Stitch tab's settings panel. Pipeline uses the locked anchor. No canvas visualisation.
- Pros: Two-line implementation.
- Cons: User can't see what the anchor currently is or what the canvas looks like.

**Recommendation:** A is the right target; B as an immediate interim. The overlap-zone heatmap from A is also directly useful for diagnosing render-gate failures (it shows exactly which rows will have single-frame coverage → median collapse → banding).

---

### 2.4 Seam Registration Inspector [Highest Impact]

**Pain point:** Stage 8.5 (`register_foreground_at_seam`) runs on every frame boundary and logs `residual_px`, `post_warp_diff`, and whether it fell back to single-pose. This data is printed to the console but never shown in the UI. For the 31% of tests that pass the render gate but are still "simple_better", the path to improvement is: identify the 1–2 seams with the worst residual, understand why (fast animation vs bad flow on flat region), and either escalate them to single-pose or override the warp.

**Options**

**A — Per-Seam Diagnostic Panel [High Impact]**
After Stage 8.5 completes, emit `StitchWorker.stage_fg_registered(seam_infos: List[dict])` where each dict has `{residual_px, post_warp_diff, fallback, dominant_frame, flow_vis}`. Display as:
- A vertical strip of "seam cards", one per boundary, sorted by post_warp_diff descending
- Each card shows: seam index, boundary position in canvas, residual (px), post_warp_diff (lum units), fallback status (⚠ single-pose / ✓ blended / ✗ skipped)
- Thumbnail crop: the ±50px band around the seam in the blended output
- Optional: flow arrow overlay (sampled RAFT vectors) so user can see what the flow engine computed
- Per-seam overrides:
  - "Force single-pose" toggle (escalates that seam to dominant frame, bypasses blend)
  - "Force blend" toggle (overrides post_warp_diff escalation)
  - "Skip registration" toggle (use raw unwarped frames for this seam — sometimes cleaner)
- "Re-composite" button → re-runs Stage 11 with the override set, shows updated output (fast, ~1s)

*Implementation:* `SeamDiagnosticPanel` — `QScrollArea` of `SeamCard` widgets. The Re-composite path calls `_composite_foreground()` directly with the override dict. ~500 LOC.
- Pros: Directly addresses the "1–2 bad seams pulling GT-SSIM down" failure mode. User can escalate seams that the post_warp_diff=22 threshold misses. Reuses the existing Stage 11 composite function.
- Cons: Requires storing intermediate per-seam state between pipeline runs. `StitchWorker` needs to persist `seam_infos` until the user triggers re-composite.

**B — Seam Overlay on Output Image**
Draw coloured lines on the final composite at each seam boundary position, coloured by post_warp_diff (green < 10, yellow 10–22, red > 22). Click a line → show the seam card. Read-only; no overrides.
- Pros: Near-zero implementation (post-process the composite image with overlay).
- Cons: Shows the symptom, not the cause. Still no control.

**C — Seam Painter Integration (Reuse HybridStitch)**
After Stage 8.5, load the warped frames into the existing `SeamPainterWidget` from `HybridStitchPanel`. User paints hard constraints, runs DP seam, then Stage 11 uses the painted seam mask.
- Pros: Reuses 100% existing code. HybridStitch's `SeamPainterWidget` already does exactly this.
- Cons: The HybridStitch seam painter doesn't know about ASP's fg masks — it would route the seam ignoring foreground, potentially cutting through the character. Needs `fg_penalty` cost term wired in.

**Recommendation:** A for full control (most impactful, addresses the core post_warp_diff blind spot). C as an intermediate step that reuses existing code but needs the fg-penalty extension. B as a "diagnostic only" first pass that can be shipped in a day.

---

### 2.5 Temporal Median Coverage Map [Quick Win]

**Pain point:** The render-gate fallback (31/96 tests) fires because the temporal median background plate is severely banded. Banding occurs when canvas rows have only 1 contributing frame (no temporal averaging possible). The user currently has no way to see the coverage map before committing to the render.

**Options**

**A — Coverage Heatmap Widget [Quick Win]**
After Stage 9 (temporal median render), emit `StitchWorker.stage_render_ready(canvas, coverage_map)` where `coverage_map[y] = number of frames contributing to row y`. Display:
- Vertical bar chart (or heatmap overlay on canvas thumbnail): red = 1 frame, amber = 2 frames, green = 3+ frames
- Superimpose on a thumbnail of the rendered canvas
- "Coverage warning" label: "N rows with single-frame coverage — render gate likely to fire"
- Overlay toggle: show/hide on the main canvas preview

*Implementation:* Simple `QLabel` with `QPixmap` colour coding. ~80 LOC.
- Pros: Tells the user in advance whether the render gate will fire. They can then choose to add a frame at that canvas position (via the Selection Assistant in §2.1) before re-running.
- Cons: Requires re-running the pipeline after adding frames; no in-place fix.

**B — Auto-suggest Missing Frames**
If coverage_map shows rows with < 2-frame coverage, automatically suggest candidate source frames (from the unselected pool) that would fill those rows. Show them in the Selection Assistant dialog.
- Pros: Closes the loop — tells user not just "there's a gap" but "add frame N to fix it".
- Cons: Requires keeping the full unselected frame pool in memory (~100 frames × 1920×1080 ≈ 600 MB); needs memory-mapped or on-demand loading.

**Recommendation:** A immediately (trivial implementation, high diagnostic value). B as a follow-on quality-of-life improvement.

---

### 2.6 Output Scale & Crop Assistant [✅ Stage 12.5 shipped — Session 7]

**Pain point:** test27 assembles a canvas 2× taller than the GT reference (1877×2135 vs 963×1280). The pipeline has no mechanism to suggest a crop. The user has no visual indication that their output is at a different scale than expected.

**Session 7 implementation (Stage 12.5):** Scroll-axis-aware foreground-extent trim inserted in `pipeline.py` between Stage 11 (foreground composite) and Stage 13 (boundary crop). Detects scroll axis from affine ty/tx range; warps `~bg_masks[i]` for each frame into canvas space using `cv2.warpAffine` + `INTER_NEAREST`; unions the fg masks; trims canvas rows (vertical scroll) or columns (horizontal scroll) to the fg-covered extent plus 20px padding. Guard: `ASP_CONTENT_TRIM=1` (default on when bg_masks available). `valid_mask` is trimmed in sync so Stage 13 `_crop_to_valid` still works correctly.

**Options**

**A — Scroll-Axis-Aware Content Crop ✅ (implemented as Stage 12.5)**
After Stage 11, trim canvas in the dominant scroll direction using warped fg union.
- Pros: Directly fixes test27's scale mismatch. More general than hardcoding 30px edge crop.
- Cons: "Foreground content extent" can be ambiguous for scenes where character is always present across all rows.

**B — Output Resolution Presets**
Let user specify target height (e.g., "1280px" or "2× source height") before running. Pipeline crops to fit.
- Pros: Simple, deterministic.
- Cons: Doesn't adapt to content — may crop character or leave excess background.

**Recommendation:** A (content-aware, directly addresses test27 class of failures). B as a fallback for users who know their target dimensions.

---

### 2.7 Architecture: StitchWorker Staged Execution [Implementation Foundation]

All of §2.1–§2.6 depend on a single architectural change: `StitchWorker` must support **stage checkpoints** — points where it emits intermediate state, optionally waits for user review, and accepts override inputs before continuing.

**Current architecture:** `StitchWorker.run()` executes all 13 stages sequentially in one thread. Signals are emitted only for progress updates and final completion. No pause/resume; no intermediate state exposed to the UI.

**Proposed architecture:**

```python
class StitchWorker(QRunnable):
    # New signals (all carry stage-specific payloads)
    stage_selection_done    = Signal(list)          # List[str] selected paths + scores
    stage_edges_ready       = Signal(list)          # List[edge dicts] with weights/residuals
    stage_canvas_ready      = Signal(object)        # affines, canvas_h/w, anchor_idx
    stage_render_ready      = Signal(object, object) # canvas image, coverage_map
    stage_fg_registered     = Signal(list)          # List[seam_info dicts]
    stage_complete          = Signal(object)        # final output image

    # Override inputs (set by UI before resume)
    def set_frame_selection_override(self, paths: list) -> None: ...
    def set_edge_override(self, deleted_edges, added_pairs) -> None: ...
    def set_anchor_override(self, anchor_idx: int) -> None: ...
    def set_seam_overrides(self, seam_overrides: dict) -> None: ...
    def resume(self) -> None: ...  # unblocks a QWaitCondition
```

Each checkpoint:
1. Emits the signal with its payload
2. Blocks on a `QWaitCondition` if the UI has "Pause at [stage]" enabled
3. Reads any overrides that were set during the pause
4. Continues with the (optionally modified) data

**Implementation cost:** ~200 LOC in `StitchWorker`, zero changes to the pipeline's algorithmic code. Each UI panel (§2.1–§2.6) connects to the relevant signal and calls `set_*_override()` + `resume()`.

**Pause policy:** All pauses are **opt-in** via a "Review at each stage" checkbox in the Stitch tab settings. Default is fully automatic (no pauses) — existing users are unaffected. "Review mode" enables one or more specific stage pauses independently.

---

### 2.8 ASP-to-HybridStitch Handoff [Long-term]

When the full ASP pipeline run produces an output the user is unsatisfied with, they should be able to **export the pipeline state to the HybridStitch panel** for manual refinement, rather than starting from scratch.

**What this handoff would export:**
- The ordered list of selected frames → `HybridStitchPanel._sequence`
- The per-pair affines from bundle adjustment → `HybridStitchPanel._homographies`
- The per-frame photometric corrections from BaSiC/gain normalisation → `HybridStitchPanel._corrections`
- The fg-registration warped frames (if saved as intermediates) → as the pair images for the Control Point Editor
- The seam coherence map → pre-loaded into the Seam Painter as initial painted constraints

**Implementation:** A single "Export to Hybrid Stitch →" button in the Stitch tab's output panel. The `EditTab._on_hybrid_handoff()` slot populates the `HybridStitchPanel` state from the `StitchWorker`'s last run.

**Gap:** HybridStitch's `RenderPanel` doesn't support BiRefNet-aware fg compositing or ARAP-registered warps. For full fidelity, the handoff would need to bring the fg-registered frames (post-Stage 8.5) rather than the raw frames, so the Hybrid panel sees "already pose-aligned" inputs and just handles final blending. This is feasible since `fg_register.py`'s warped outputs are already written to `stage_dir/` as PNG intermediates.

---

## 3.0 ML-Driven Pipeline Modernisation [Research Phase — from ML Research Report]

*Source: [`reports/ASP Consolidated Research Plan.md`](../../reports/ASP%20Consolidated%20Research%20Plan.md) — consolidated 2026-06-07. Each subsection maps a specific finding from the research plan to the current pipeline stage it targets, the files it touches, and the expected quality delta. Phase priority framework in the consolidated plan: Phase 1 (pose-consistent frame selection, GNC-TLS BA, median background + JPEG-aware refinement, SAM-2 masking), Phase 2 (AnimeInterp SGM + LinkTo-Anime SEA-RAFT, OBJ-GSP seam barrier, full Sýkora 2009 ARAP, ProPainter), Phase 3 (ToonCrafter quality-gated, StabStitch++ trajectory smoothing).*

The report's central thesis: cel animation breaks every assumption that drives classical CV pipelines (gradient-based flow, RANSAC on whole-frame features, pixel-level quality metrics). The next generation of improvements requires either (a) anime-specific classical methods that bypass those assumptions entirely, or (b) deep/generative models whose priors capture the latent structure of hand-drawn character motion. The sections below are ordered by expected impact-to-effort ratio and dependency on existing infrastructure.

---

### 3.1 AnimeInterp SGM: Segment-Guided Matching for Flat-Region Correspondence [Research — Highest Aperture-Problem Impact]

**Pain point (links to §0.1):** RAFT, DIS, and ARAP Push all produce chaotic flow vectors on large flat-color regions — the aperture problem is fundamental, not a parameter issue. The ARAP Push phase (session 4) confirmed zero SSIM improvement because block-matching also fails on uniform color patches. We need a method that treats flat regions as geometric entities, not texture patches.

**What AnimeInterp SGM does:** Extracts line-art contours via Laplacian filter → "trapped-ball" filling produces a rigid segmentation map where each contiguous color region gets a unique ID → VGG-19 features are pooled per-segment → correspondence is solved via a **Matching Degree Matrix** combining:
- Feature affinity (normalized VGG cosine similarity)
- Distance penalty (rejects matches whose centroid displacement exceeds 15% of image diagonal)
- Size penalty (rejects matches where segment area changes drastically)

The optimal shift is derived from centroid displacement, then combined with local variational deformation to produce a dense flow field for the whole textureless region. The aperture problem is completely sidestepped — no gradient required.

**How it applies:** Replace or augment `_arap_push()` in `fg_register.py`. SGM provides the coarse per-cell displacement; the existing `_arap_regularise()` would then smooth the SGM-derived field instead of the raw RAFT flow. SGM runs on the fg-masked overlap crops (already cropped at ±taper_px+16px), so input size is manageable.

**Options**

**A — SGM as primary flow for fg overlap [Research]**
Replace RAFT/DIS flow estimation for the fg registration crop with SGM. RAFT is only reliable on textured regions; SGM is reliable everywhere else. Could combine: use RAFT where confidence is high (gradients exist), use SGM where confidence is low (flat regions).
- Pros: Directly solves the aperture problem. Proven on anime at CVPR 2021.
- Cons: SGM requires VGG-19 forward passes on the crops → 15–30ms per seam on GPU. 13 seams → +0.3–0.4s per dataset. Needs trapped-ball segmentation (OpenCV watershed as proxy).
- Code: [AnimeInterp CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/papers/Siyao_Deep_Animation_Video_Interpolation_in_the_Wild_CVPR_2021_paper.pdf), [GitHub](https://github.com/lisiyao21/AnimeInterp)

**B — SLIC superpixel centroid tracking as SGM proxy [Quick Win]**
SLIC superpixels (available in `skimage.segmentation.slic`) can approximate the segment structure without VGG feature extraction. Centroid tracking across seam pairs gives coarse per-cell displacement. Less robust than true SGM but implementable in 50 LOC.
- Pros: No new model weights. ~2ms per seam.
- Cons: SLIC on flat color without texture guidance may not segment correctly (same color = one huge superpixel). Less robust than VGG-based SGM.

**C — AnimeInterp full architecture for frame interpolation [Long-term]**
Beyond fg registration: use SGM + ConvGRU (§3.2) to generate synthetic intermediate frames between selected frames, filling in animation gaps entirely. This would replace the midpoint warp with a learned interpolation.
- Cons: Requires ATD-12K fine-tuning for best quality. GPU inference time ~500ms per synthetic frame.

**D — LinkTo-Anime fine-tuned SEA-RAFT as drop-in flow engine [Research]**
The LinkTo-Anime dataset (arXiv 2506.02733) is the first GT optical-flow corpus for cel-shaded anime (395 sequences, 24,230 training frames). SEA-RAFT (ICCV 2025) is the current top-performing flow architecture. Fine-tuning SEA-RAFT on LinkTo-Anime produces an anime-specific flow engine loadable via `ASP_FLOW_ENGINE=sea_raft_anime` — a direct drop-in for the existing engine swap in `_load_flow_engine()`.
- Pros: Addresses the domain gap at the data level. SEA-RAFT's recurrent refinement outperforms RAFT on textured regions and is more robust than SGM on ambiguous animation poses.
- Cons: ~24GB VRAM for fine-tuning on the full LinkTo-Anime dataset. Inference time similar to RAFT (~30ms/seam on GPU). Model weights ~100MB after fine-tuning.

**Recommendation:** B immediately as a diagnostic check (does centroid-level flow actually improve post_warp_diff?). A if B shows meaningful seam residual reduction on test09/test27. D as a research track running parallel to A once LinkTo-Anime training weights become available. C is the long-term ceiling but depends on A being validated first.

---

### 3.2 ConvGRU Recurrent Flow Refinement for Kinematic Accuracy [Research]

**Pain point (links to §0.1):** Even when coarse correspondence is correct (SGM), there are null/sparse regions in the flow field (SGM drops low-confidence matches via mutual consistency check). These gaps create warp artifacts at segment boundaries. The current fallback for sparse flow is `_arap_regularise()` which is a spatial smoothing — it doesn't respect the temporal structure of the motion.

**What ConvGRU RFR does:** A ConvGRU (Convolutional Gated Recurrent Unit) iteratively refines the coarse SGM flow by:
1. Building a pixel-wise confidence mask from `|warped_A - warped_B|` (high diff = low confidence)
2. Over T iterations, correlating feature tensors from source and bilinearly-sampled target to estimate residual flow corrections
3. Accumulating residuals to bend the linear coarse flow into an accurate non-linear trajectory

Trained on ATD-12K (12,000 animation triplets with extreme exaggeration).

**How it applies:** As a post-processing step after `_arap_push()` (or SGM if §3.1A is implemented): use the ConvGRU to fill null regions and sharpen the flow field before `_arap_regularise()`. The ConvGRU runs on the fg-masked seam crop (same input as RAFT today), replacing the RAFT pass entirely for animated-content inputs.

**Options**

**A — Drop-in RAFT replacement with AnimeInterp flow [Research]**
AnimeInterp's SGM+ConvGRU pipeline produces a dense refined flow field as output. In `fg_register.py`, the `_load_flow_engine()` function already supports swappable engines (RAFT vs DIS via `ASP_FLOW_ENGINE`). Add `ASP_FLOW_ENGINE=animeinterp` path that loads the SGM+ConvGRU weights and runs on the seam crop.
- Pros: Minimal code change (follows existing engine swap pattern). Full AnimeInterp pipeline handles both coarse and fine flow.
- Cons: Requires ATD-12K pretrained weights (~180MB). VGG + ConvGRU inference: ~40ms per seam.

**B — ConvGRU as confidence-guided gap-filler on top of RAFT [Research]**
Keep RAFT for high-texture regions, use a lightweight ConvGRU-style network only in low-confidence zones (where RAFT confidence < threshold). Hybrid approach.
- Cons: Requires a custom confidence-thresholding pipeline. More engineering than A.

**Recommendation:** A is cleaner. The existing `ASP_FLOW_ENGINE` switch makes A a drop-in experiment.

---

### 3.3 DINOv2 + SigLIP Submodular Frame Selection [✅ Option A shipped — Session 8]

**Pain point (links to §0.2):** The fg pixel L1 pose metric (session 5) is background-invariant but still GT-coupled: substituting frame N for frame N+1 diverges from GT's temporal reference even when both show the same character pose (same "on twos" hold). The GT-coupling causes -0.024 regressions on some tests when pose selection is enabled.

**Session 8 implementation:** `_compute_dinov2_features()` added to `frame_selection.py`. Loads `dinov2_vits14` via `torch.hub.load` with module-level `_DINOV2_CACHE`; batch inference on grayscale thumbnails → (N, 384) L2-normalised float32 features. In Pass 2 of `smart_select_frames()`, DINOv2 cosine distance replaces `_fg_center_diff()` when features are available; falls back to pixel L1 when DINOv2 is unavailable. Enable via `ASP_POSE_WINDOW_PX=80` (same flag). 2 new tests in `TestDINOv2Features`.

**What DINOv2 Submodular Selection does (from "Adaptive Greedy Frame Selection for Long Video Understanding", arXiv 2603.20180):**
1. **DINOv2 facility-location coverage:** Embeds all frames via DINOv2 ViT-B/14. Defines a facility-location objective that penalises redundancy — adding frame i to the selected set is only rewarded if its DINOv2 embedding occupies a significantly different region in latent space from already-selected frames. Frames in the same "on twos" hold will have nearly identical embeddings → the objective naturally clusters them and picks one representative.
2. **SigLIP relevance term:** Optional query-conditioned relevance (useful if we want to bias toward frames containing a specific character pose or action).
3. **Greedy with (1-1/e) approximation guarantee:** Submodular maximisation gives formal quality bounds; the greedy algorithm is fast (O(N·K) in frame count N, selection count K).

**Key insight for ASP:** This method was designed explicitly for video with temporal redundancy (animation holds are exactly the "frame redundancy" it penalises). Applied to our frame selector:
- Step 1: Extract DINOv2 embeddings for all source frames (batch inference on thumbnails)
- Step 2: Apply facility-location greedy to select K most-diverse frames
- Step 3: Among the diverse candidates, apply the camera advance constraint (≥50px min step)

This directly resolves GT-coupling because DINOv2 embeddings are *background-aware* but also *animation-hold-aware*: frames in the same hold are treated as identical, and the selection picks the one with the right camera advance regardless of which specific frame the GT used.

**How it applies:** Replaces or augments `_smart_select_frames()` in `frame_selection.py`. The DINOv2 embedding pass replaces the thumbnail phase-correlation pass for pose scoring. Camera advance estimation still uses phase correlation.

**Options**

**A — DINOv2 facility-location as primary pose metric [Research]**
In Pass 2 of `_smart_select_frames()`, replace `_fg_center_diff()` with DINOv2 cosine distance. The facility-location objective score replaces the current "≥10% improvement" threshold.
- GPU inference: DINOv2 ViT-S/14 on 256px thumbnails: ~5ms/frame batched. For 30 frames: ~150ms total. Acceptable.
- Pretrained weights: Available via `torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')` — no fine-tuning needed.
- Pros: Background-invariant by design. Explicitly handles animation holds. Formal approximation guarantee.
- Cons: Adds DINOv2 dependency; ~150ms overhead per dataset. Still GT-coupled if DINOv2 disagrees with GT's frame choices (but hold-awareness reduces this risk significantly).

**B — Apply on foreground-masked crops only [Research]**
Before DINOv2 embedding, mask out background pixels (using BiRefNet masks already computed in the pipeline). This makes DINOv2 embeddings purely character-pose-driven, entirely eliminating background structure from the score.
- Pros: Strongest GT-decoupling. Character in different poses → clearly different DINOv2 embeddings.
- Cons: Requires BiRefNet to run before frame selection (currently BiRefNet runs after selection). Adds ~2s overhead.

**C — SigLIP query-aware selection for specific poses [Long-term]**
Let the user specify a target pose in natural language ("character standing, arms raised"). SigLIP relevance term biases selection toward frames matching that description.
- Cons: Requires user input; not fully automatic. Long-term feature.

**Recommendation:** A immediately. B as the quality-maximizing refinement. The key implementation risk is that DINOv2 on masked-foreground crops (Option B) requires BiRefNet to run first, which changes the frame selection timing and may reintroduce the frame-timing regression seen in session 3 with BiRefNet two-channel selection. Start with A (unmasked DINOv2) and verify it doesn't regress before adding masking.

---

### 3.4 FD-Means Animation Hold Detection [Quick Win — preprocessing]

**Pain point:** The frame selector runs phase correlation on all N source frames before discarding holds. For a 300-frame source with many holds, this wastes N-K phase correlation pairs that could be compressed without loss.

**What FD-Means does:** Feature-level deduplication that clusters animation frames into "hold blocks" — runs of identical or near-identical frames. Uses deep structural embeddings (perceptual hash or DINOv2 distance) to detect when consecutive frames share the same cel even if minor compression artifacts differ. Each hold is compressed to a single token (one frame representative + duration metadata).

**How it applies:** Add a hold-detection preprocessing step at the start of `_smart_select_frames()`. Before any phase correlation:
1. Compute perceptual hash (or DINOv2 distance) for consecutive frame pairs
2. Cluster consecutive frames with distance < threshold into "hold blocks"
3. Pass only one representative per hold block to the phase correlation stage

This reduces the number of frames processed by the rest of the pipeline by a factor of 2–3× for typical anime, and explicitly surfaces hold boundaries as natural pose-change points.

**Options**

**A — Perceptual hash hold detection [Quick Win] ✅ DONE (S43)**
`_compute_dhash(thumb, hash_size=8)` + `_detect_hold_blocks_dhash(thumbs, distance_threshold=4)` in `frame_selection.py`. INTER_AREA resize to (9×8) eliminates MPEG DCT block noise before horizontal gradient binarisation. Hamming distance threshold 4. `ASP_HOLD_DHASH_THRESH=4` to enable; default 0=off (MAD fallback). `HOLD_DHASH_THRESHOLD=4` in `constants/anim.py`; added to `_CONFIG_SCHEMA`. 5 tests in `test_frame_selection.py::TestDetectHoldBlocksDhash`. 322 tests passing.
- Pros: Zero new dependencies (~3ms for 300 frames). INTER_AREA resize is structurally immune to DCT block noise; within-hold distance stays 0–2 even for aggressive H.264 compression.
- Cons: ~3× slower than MAD. Threshold requires tuning for unusual sources (anime-original BD vs streaming rip).

**B — DINOv2 cosine distance hold detection [Research]**
If §3.3 is implemented (DINOv2 already loaded for frame selection), reuse the embeddings for hold detection. Threshold: cosine distance < 0.05 = same hold.
- Pros: Robust to compression noise. No extra inference cost if DINOv2 runs for §3.3.
- Cons: Adds DINOv2 dependency if §3.3 is not implemented.

**C — FD-Means clustering [Research]**
Use the `fastdup` library's internal FD-Means cluster algorithm, which is specifically designed for video frame deduplication with peak function clustering (avoids random K-Means initialization).
- Pros: Production-tested on video datasets.
- Cons: New dependency; adds `fastdup` which is a large package.

**Recommendation:** A immediately (near-zero cost, directly useful). B as a free addition if §3.3 lands. C only if A proves insufficient for compressed sources.

---

### 3.5 CamFlow Hybrid Motion Basis for Camera Displacement [Research]

**Pain point (links to §0.2):** Phase correlation on whole-frame thumbnails conflates camera pan (`T_camera`) with character animation (`A_animation`). A 50px "displacement" may be 5px camera + 45px arm swing. The fg pixel L1 metric partially decouples pose from camera, but the phase correlation estimate is still noisy for scenes with large foreground characters.

**What CamFlow does (ICCV 2025, [paper](https://openaccess.thecvf.com/content/ICCV2025/papers/Li_Estimating_2D_Camera_Motion_with_Hybrid_Motion_Basis_ICCV_2025_paper.pdf)):**
Estimates 2D camera motion via a Motion Estimation Transformer (MET) that combines:
1. **12 physical polynomial bases** derived analytically from the 2D projection equation (translation, scaling, affine shear, perspective)
2. **K stochastic Gaussian SVD bases** to capture residual non-linear motion that escapes the polynomial bases

The two base sets are weighted by the MET; an uncertainty mask rejects unreliable (foreground-dominated) regions. Training uses SAM-masked dynamic objects to create a "camera-only" ground truth. The resulting camera estimate is sub-pixel accurate even with large foreground subjects.

**How it applies:** Replace the `cv2.phaseCorrelate()` call in `_smart_select_frames()` (frame_selection.py) with a CamFlow inference pass. CamFlow runs on thumbnail pairs (256px) and outputs a 2×3 camera matrix rather than a (dx, dy) pair — this gives us a cleaner separation of camera rotation/scale from character motion.

**Options**

**A — CamFlow as drop-in phase-correlation replacement [Research]**
The `_smart_select_frames()` function currently computes `(dx_t, dy_t), response = cv2.phaseCorrelate(a, b)`. Replace with `flow_matrix = camflow.estimate(a, b); dx_t, dy_t = flow_matrix[0,2], flow_matrix[1,2]`. CamFlow outputs the dominant camera translation directly.
- Estimated inference: MET on 256px thumbnail pairs: ~10ms/pair on GPU. For 30 pairs: 300ms. Acceptable.
- Pros: Formally decouples camera from foreground. ICCV 2025 state-of-the-art.
- Cons: New model weights (~50MB MET). Not yet available as a pip package — requires building from paper code.

**B — Deep homography with foreground masking [Research]**
Alternative to CamFlow: use a deep homography estimator (from "Deep Homography Estimation for Dynamic Scenes", CVPR 2020) that jointly predicts a temporal dynamics mask alongside the homography matrix. The network identifies high-temporal-variance regions (character) and excludes them, forcing estimation from static background.
- Pros: This CVPR 2020 model has available pretrained weights and a simpler architecture than CamFlow.
- Cons: Less robust to multi-plane parallax than CamFlow. Not designed for anime specifically.

**C — Background-only phase correlation via BiRefNet mask [Infrastructure Built, Disabled]**
Already implemented as `ASP_TWO_CHANNEL_SELECT=1` in `frame_selection.py`. Uses BiRefNet bg mask for background-only phase correlation. Currently disabled because it changes frame timing and caused regressions.
- Cons: The frame-timing regression remains unsolved. Re-enabling after §3.3 (DINOv2 selection) may behave differently since pose selection is handled separately.

**Recommendation:** B first (available weights, simpler implementation). A as the quality ceiling once the CamFlow code is published. C is a free experiment if §3.3 is implemented (BiRefNet already runs before selection in that scenario).

---

### 3.6 ToonCrafter Seam Synthesis — Wiring the Generative Fallback [✅ Option B shipped — Session 9]

**Pain point (links to §1.6, Phase 6.3):** When `post_warp_diff > 22 lum units`, Stage 8.5 escalates to "single-pose fallback" — a clean but informationally incomplete solution (shows one character pose at the seam, hiding the other). The seam zone is left with a visible hard boundary. ToonCrafter can *synthesize* a coherent intermediate pose that eliminates the boundary entirely.

**Session 9 implementation (Option B):** `_TOONCRAFTER_SEAM_ENABLED = os.environ.get("ASP_TOONCRAFTER_SEAM", "0") != "0"` added to `compositing.py`. `seam_post_diffs: dict` tracks `post_warp_diff` per seam during the fg-register loop. After the loop, the worst single-pose-escalated seam (`max(seam_single_pose, key=lambda k: seam_post_diffs.get(k, 0.0))`) triggers `_generate_canonical_cel(crop_a_tc, crop_b_tc, device)` from `anim_fill.py`. The canonical cel is stored in `seam_canonical_crops[worst_k]`; in the Laplacian blend loop it replaces the hard dominant-frame partition for fg pixels. Falls back gracefully to single-pose when ToonCrafter is unavailable.

**Current state:** `anim/anim_fill.py` already implements ToonCrafter integration. It is referenced in `§1.6` as Option D and in `pipeline.py` as `if self.use_tooncrafter`. It IS now wired to single-pose seam escalation in `compositing.py` (session 9).

**What changes:** In `compositing.py`, when `post_diff > _POST_DIFF_THRESHOLD` (line ~619), instead of recording `seam_single_pose[k] = dom`:
1. Extract the ±50px seam-band crop from both warped frames (frame_a, frame_b around the seam)
2. Call `anim_fill.tooncrafter_ghost_fill()` on the crop pair
3. The synthesized intermediate frame replaces the hard-partition boundary with a generated transitional pose
4. Insert the synthesized crop into the composite output

**Options**

**A — ToonCrafter on every single-pose-escalated seam [Research]**
Run ToonCrafter synthesis for every seam where `post_diff > 22`. Each seam synthesis: ~24s on A100, ~10GB VRAM with fp16. For 13 seams in test08: 5 single-pose escalations × 24s = 2 minutes extra. Only viable with `final_quality=True` mode flag.
- Pros: Eliminates single-pose discontinuities entirely. Maximum quality.
- Cons: 2+ minutes extra per dataset with many high-residual seams. Not suitable for standard mode.

**B — ToonCrafter only for the worst seam (highest post_diff) [Quick Win toward Research]**
Apply synthesis only to the single seam with the largest `post_warp_diff` in each dataset. For test27, this would be boundary B2 (post_diff=9.7) — already below threshold so no synthesis needed. For test08 (many seams near threshold), synthesis would target the worst seam only.
- Time: 1 seam × 24s = 24s overhead in final-quality mode. Manageable.
- Pros: Focused quality improvement with bounded time overhead.
- Cons: Other seams still use hard partition.

**C — ToonCrafter crop-scale optimisation [Research]**
Current ToonCrafter operates at 512×320. Our seam crops are typically 600×(narrow band ~100px). Resize to 512×100 (preserving aspect), run inference, resize back. This would reduce VRAM to ~3GB and inference to ~8s.
- Cons: Low vertical resolution may reduce synthesis quality. Requires testing.

**Recommendation:** Wire Option B into `compositing.py` behind `ASP_TOONCRAFTER_SEAM=1` env var (default off). Measure SSIM impact on the 5-test corpus. If test08 improves, escalate to Option A for final-quality mode. Option C is worth prototyping alongside B since it drastically reduces the per-seam cost.

---

### 3.7 UDIS++ / UDTATIS Diffusion-Based Seam Composition [Long-term — End-to-End Replacement]

**Pain point (links to §1.6):** The current Laplacian blend (Stage 11) stitches the seam zone using a multi-band pyramid blend. For large pose differences that survive after ARAP registration, the blend creates visible double-edge ghosting. A generative model that hallucinates coherent bridging pixels would eliminate this class of artifact.

**What UDIS++/UDTATIS does:** Two-stage pipeline:
1. **Unsupervised geometric warping** (EfficientLOFTR + spatial transformer): Aligns frame pair without supervision, using a mesh-based local deformation field (parallax-tolerant, unlike our global translation model)
2. **Diffusion-based composition**: The warped overlap region is passed through a denoising diffusion process with multi-scale feature fusion, continuity constraints, and adaptive normalisation. The seam line is literally hallucinated away.

**How it applies:** UDIS++ would replace Stage 11 entirely — the current `_composite_foreground()` in `compositing.py` (hard-partition + Laplacian blend) is replaced by UDIS++ inference on the warped frame pair. UDIS++ handles both alignment and compositing in one pass.

**Options**

**A — UDIS++ for the seam composition step (after our ARAP warp) [Research]**
Keep our ARAP fg registration for pose alignment (Stage 8.5). Then feed the ARAP-warped frames into UDIS++ only for the composition step (replacing the Laplacian blend). This is a hybrid: our pose registration + learned composition.
- Pros: UDIS++ open-source code available on [GitHub](https://github.com/nie-lang/UDIS2). Pre-trained weights available.
- Cons: UDIS++ was trained on natural images — significant domain gap for anime. Would need fine-tuning on anime data for reliable quality.

**B — UDTATIS with EfficientLOFTR (cartoon-specific) [Research]**
UDTATIS integrates EfficientLOFTR (already in our matching stack) and a diffusion composer. The EfficientLOFTR feature extraction may generalise better to anime than VGG-based alternatives.
- Cons: Less established than UDIS++. Tested on terahertz imagery; anime applicability unclear.

**C — RDIStitcher: pure inpainting paradigm [Long-term]**
Completely replaces geometric warping + Laplacian blend with a T2I diffusion model that treats the entire seam as an inpainting problem. Self-supervised via pseudo-stitched training pairs (artificially misaligned images). Zero-shot at inference time.
- Pros: Maximum generative flexibility. No feature matching required.
- Cons: RDIStitcher inference: ~15–30s on consumer GPU. Not viable for standard mode. `final_quality=True` mode only.

**Recommendation:** A as a research prototype (UDIS++ code is available, integration is well-defined). C as the long-term aspirational target since it entirely removes the need for hand-crafted seam-finding. B if UDIS++ shows too much domain gap on anime.

---

### 3.8 SIQE No-Reference Ghosting Detection [Quick Win — metric upgrade]

**Pain point (links to §1.6, §1.10):** The current `_ghosting_score()` metric computes local variance of a Laplacian pyramid — a proxy that correlates weakly with perceptual ghosting. The ghosting gate (§2.0's ghosting ratio gate, ratio=1.92–2.06 borderline for test82) is unreliable at borderline values due to SCANS non-determinism.

**What SIQE does:** The Stitched Image Quality Evaluator uses:
1. Multi-scale steerable pyramid decomposition (2 scales × 6 orientations = 12 subbands)
2. Gaussian Mixture Model fitted to the pyramid subband statistics of pristine panoramas
3. Ghosting localisation via optical flow energy variance across the panorama
4. 94.36% precision vs mean subjective human opinion

**How it applies:** Replace `_ghosting_score()` in `bench_anime_stitch.py` with SIQE. The ghosting gate (`ASP_GATE_GHOST`) becomes more reliable. Additionally, SIQE can spatially localise ghosting (output: map of ghost probability per pixel), enabling targeted per-seam intervention rather than a global fallback decision.

**Options**

**A — Double-edge autocorrelation ghosting metric** ✅ **Shipped S35**
`_ghosting_score_v2(img)` in `bench_anime_stitch.py` — FFT-based autocorrelation of the column-mean gradient-magnitude profile. Detects the secondary peak at displacement D that a ghost (shifted copy) creates. Score in [0–100]: 0=no ghost, 30+=ghost likely. Added as `ghosting_siqe` metric in `_compute_all_metrics`; original `ghosting_score` kept for GhostGate calibration. 5 tests in `test_bench_metrics.py::TestGhostingScoreV2`. Zero new deps.
- Unlike the double-Sobel proxy, this metric is specifically sensitive to *repeated* edge patterns at a fixed displacement — the signature of a misaligned character copy — while being insensitive to high-frequency texture that is not ghost-related.
- Pros: Pure numpy FFT (~0.5ms for 2000px), zero new deps. Directly measures double-edge periodicity.
- Cons: Does not achieve full SIQE accuracy (no GMM, no steerable pyramid orientation analysis). For the full SIQE, see Option B below.

**B — Full SIQE (steerable pyramid + GMM) [Research]**
Implement the full steerable pyramid + GMM pipeline. The GMM is fitted offline on pristine stitched anime panoramas (the 52/96 ASP-succeeded tests as positive examples). SIQE achieves 94.36% precision vs mean subjective human opinion.
- Pros: 94.36% precision. Best-in-class for panoramic ghosting.
- Cons: Steerable pyramid needs `pyrtools` or custom implementation; GMM fitting requires clean corpus.

**B — SIQE spatial ghost map → per-seam ghost gate** ✅ **Shipped S53**
`_compute_per_seam_ghost_scores(img, n_strips, band_px=100)` in `bench_anime_stitch.py`. Divides output image into equal-height zones, evaluates `_ghosting_score_v2` in ±`band_px` bands at each seam boundary. Returns `n_strips-1` scores in [0–100]. Wired into `_compute_all_metrics` via `n_strips` param; result dict adds `ghost_seam_scores` (List[float]) and `ghost_seam_max` (Optional[float]). Backward compatible (default `n_strips=1`). 5 tests in `test_bench_metrics.py::TestPerSeamGhostScores`.
- Pros: Surgical localisation — identifies the worst seam without the global-fallback blunt instrument. < 5ms overhead for N=12 seams.
- Note: Uses `_ghosting_score_v2` (FFT autocorrelation proxy), not full SIQE (steerable pyramid + GMM). Full SIQE is a future option if per-seam recalibration targets it.

**Recommendation:** A as the first step (replaces the current imprecise metric). B as a high-value follow-on once A is validated — it would close the gap between "good composite with 1 bad seam" and the current "SCANS fallback for any quality gate failure."

---

### 3.9 SI-FID: Stitched-Image Fréchet Distance for Reference-Free Evaluation [Research]

**Pain point:** GT-SSIM is a biased evaluation metric — it penalises any temporal deviation from the GT's frame choices regardless of actual composite quality. We need a reference-free metric that reflects perceptual stitch quality.

**What SI-FID does (arXiv 2404.13905):**
- A neural network is trained via contrastive learning on images with artificially injected stitching artifacts (parallax shearing, hue misalignment, structural ghosts)
- The network projects pristine and corrupted images into a separable latent space
- SI-FID computes the Fréchet distance between the generated output's feature distribution and the learned pristine distribution
- **25% higher rank correlation with subjective human opinions** compared to competing objective metrics

**How it applies:**
1. **Evaluation:** Replace or supplement GT-SSIM in the benchmark with SI-FID for tests without ground truth (41 of 96 tests currently have no GT)
2. **Optimization target:** If SI-FID is reliable on anime, use it as the objective for RLHF parameter search (§1.10) — this completely sidesteps the GT-coupling problem in §0.2
3. **Render gate:** SI-FID score could replace or augment the `seam_coherence` + `strip_banding` composite gate with a perceptually grounded metric

**Options**

**A — SI-FID as supplementary benchmark metric [Research]**
Add SI-FID computation to the benchmark alongside GT-SSIM. Compare rankings — if SI-FID rank-orders tests the same way human inspection would, it becomes trustworthy for the 41 GT-less tests.
- Implementation: Train (or obtain) the SI-FID network. Available at [arXiv 2404.13905](https://arxiv.org/abs/2404.13905). If no pretrained weights for anime, fine-tune on the 52/96 ASP-succeeded outputs vs SCANS outputs.

**B — SI-FID as RLHF optimization objective [Research]**
Replace GT-SSIM in the Bayesian parameter search (§1.10) with SI-FID. This enables optimizing pipeline parameters without GT-coupling bias. The search becomes: find parameters that maximise SI-FID across the 96-test corpus (including the 41 without GT).
- Pros: Solves GT-coupling fundamentally by switching the objective function.
- Cons: SI-FID needs to be validated on anime before being trusted as an optimization target.

**Recommendation:** A first to validate SI-FID's utility on anime. B only after A confirms it agrees with human inspection on the available GT tests.

---

### 3.10 MLLM Semantic Quality Scoring [Research — Autonomous Quality Assurance]

**Pain point (links to §1.10):** The current automated quality assessment (seam_coherence, strip_banding, ghosting ratio) detects photometric artifacts but cannot detect semantic failures — a character with a severed torso, four arms, or mismatched body orientation. These failures exist in the corpus and pass all current gates.

**What MLLM SIQS/MICQS does:** Uses a vision-language model (Qwen-VL, GPT-4V, or similar) to:
- **Single-Image Quality Score (SIQS):** Asks "Does this panoramic image show a coherent character? Are there any duplicated limbs, cut-off body parts, or mismatched poses?" → confidence score 0–1
- **Multi-Image Comparative Quality Score (MICQS):** Given two outputs (ASP vs simple stitch), asks "Which shows a more coherent, complete character body?" → preference score
- Flags any output with SIQS < 0.5 for human review or automatic regeneration with a different random seed

**How it applies:** Post-pipeline MLLM check as an additional quality gate in the benchmark. For production use, integrate into `StitchWorker` as an optional final-pass check (`ASP_MLLM_QA=1`).

**Options**

**A — Local MLLM via llama.cpp or ollama [Research]**
Run Qwen2-VL-7B (or similar) locally via `ollama pull qwen2-vl` or `llama-server`. No API cost. ~10–20s per image for 7B model on CPU, ~2s on GPU.
- GPU: RTX 3090 Ti has 24GB — Qwen2-VL-7B fits in 14GB at 4-bit, leaving 10GB for the ASP pipeline.
- Cons: Significant VRAM competition with BiRefNet + RAFT during pipeline run. Must run sequentially.

**B — MLLM as benchmark-only metric (no production integration) [Research]**
Run MLLM scoring as a post-hoc batch evaluation step on benchmark outputs, not inline with pipeline execution. Eliminates VRAM conflict entirely.
- Pros: Simplest integration. Runs after benchmark completes.
- Cons: No real-time quality gating during production use.

**C — Structured prompt for anime-specific artifact detection [Research]**
Rather than generic quality scoring, design a structured prompt that asks specific anime-composite questions: "Does the character's body look split at the waist? Are there any doubled hands or feet visible? Does the background appear to have horizontal colour bands?"
- Pros: Anime-domain specificity reduces false positives from generic "quality" judgements.
- Cons: Requires prompt engineering and validation against the corpus.

**Recommendation:** B first (benchmark evaluation, no VRAM conflict). Validate MLLM scores against human inspection on the 55 GT-scored tests. If scores correlate well with GT-SSIM verdict (asp_better/simple_better), promote to Option A for production use.

---

## 1.11 Animation Hold Detection — Preprocessing [✅ Option A shipped — session 6]

**Pain point (links to §0.2, §3.4):** The frame selector processes all N source frames (58–333) through phase correlation before any frames are discarded. For typical anime with ~3-frame holds, 70% of phase correlation pairs are within the same hold block (identical camera position, same character cel). These redundant correlations add latency and, more importantly, mask natural pose-change boundaries.

**What hold detection adds:**
1. **Speed:** Run thumbnail phase correlation only between consecutive hold-block representatives (one per unique cel). For 300-frame source with 3-frame average holds → reduces correlation pairs from 299 to ~99 (3× speedup for the selection phase).
2. **Quality:** Hold boundaries are exactly the "on twos" pose-change points identified by Sýkora 2009. The selected frames should cross exactly one hold boundary per step — if they don't, the seam spans a hold (same pose, no ARAP correction needed) or multiple holds (large animation gap, warp will fail).
3. **Diagnostic:** Hold block count directly predicts ARAP workload: tests with 15+ hold-block transitions in their selected frames will have large animation residuals.

**Options**

**A — Thumbnail pixel MAD hold detection [Quick Win — implemented session 6]**
Compare consecutive thumbnail mean absolute differences. If MAD < threshold (default 0.025 of [0,1] range), the frame is in the same hold as the previous. No new dependencies.
- File: `frame_selection.py` → `_detect_hold_blocks()` + `ASP_HOLD_THRESHOLD` env var
- Pros: Zero new dependencies. Fast (~1ms for 300 frames). Works even on compressed broadcast captures where exact pixel equality fails.
- Cons: Threshold needs tuning for heavily-compressed sources (MPEG blocking noise can inflate MAD).

**B — DINOv2 cosine distance hold detection [Research]**
If §3.3 (DINOv2) is implemented, reuse embeddings: cosine distance < 0.05 = same hold. Robust to compression noise.
- Cons: Requires DINOv2 (adds overhead if §3.3 not otherwise implemented).

**C — Phase correlation magnitude threshold** ✅ Shipped S38
If two consecutive frames have phase correlation response > 0.85 (near-perfect correlation), they're in the same hold. Already available from the existing phase correlation pass — zero extra cost.
- Cons: MPEG blocks can corrupt high-response pairs at scene boundaries.

**Recommendation:** A immediately (already implemented, `ASP_HOLD_THRESHOLD=0.025`). C as a free upgrade using the existing `responses` array in `smart_select_frames()`. B if §3.3 is implemented.

> **✅ Session 7 — Phase-correlation skip SHIPPED:** Hold threshold default changed from `0.0` to `0.025` (enabled by default). Within-hold frame pairs now return `(dx=0, dy=0, response=1.0, MAD=0.0)` without running `cv2.phaseCorrelate`, achieving the §1.11 3× speedup for typical anime with ~3-frame holds. The `high_anim_mad` gate is protected from false positives (within-hold MAD=0.0 never triggers it). `ASP_HOLD_THRESHOLD=0` to disable.

> **✅ Session 38 — §1.11C SHIPPED:** `_refine_hold_ids_by_response(hold_ids, responses, 0.85)` added to `frame_selection.py`. Wired as step 3b in `smart_select_frames` after the phase-correlation loop completes. Cross-hold pairs with `phaseCorrelate response >= 0.85` have their blocks merged; IDs renumbered consecutively. `HIGH_HOLD_RESPONSE_THRESH=0.85` in `constants/anim.py`. Override: `ASP_HIGH_HOLD_RESPONSE`. 5 new tests. 297 tests passing.

---

## 1.12 Translation Monotonicity Validation ✅ Shipped S52

**Pain point:** The four existing `_validate_affines` checks (ratio, min_gap, rotation, scale) operate on the *sorted spatial* order. They cannot detect uniformly-spaced frames in the **wrong temporal order** — e.g., a BA solution where skip edges misplace frame 3 to a position before frames 1 and 2. Such solutions have ratio ≈ 1.0 and pass all existing checks, but produce catastrophic composites (wrong frame pairs fused, seam zones misidentified).

**Option A — Kendall τ ordering check [Quick Win] ✅ Shipped S52**
`_check_translation_monotonicity(affines, primary_axis, min_tau_abs=0.4)` in `validation.py`. Computes Kendall τ between temporal frame indices [0…N-1] and primary-axis translations. |τ|=1 for perfectly monotone sequences (forward **and** backward scroll both pass), |τ|≈0 for random permutations. Returns `(is_monotone, tau_abs)`. Wired as the 5th check in `_validate_affines` (after rotation/scale) for `scroll_axis ∈ {vertical, horizontal}`. Failure reason `"monotonicity={tau:.2f} < 0.4"` falls through to Retry 1 (adj-only BA), the natural recovery since skip edges are the primary cause of frame misordering. `_MONO_TAU_MIN=0.4` constant. Requires ≥ 4 frames (shorter sequences skip the check). Exported in `__all__`. 5 tests in `TestTranslationMonotonicity`. 367 tests passing.
- Pros: O(N²) pair-counting loop, negligible for N ≤ 30. Zero new dependencies.
- Cons: Does not catch misordering on diagonal scroll sequences (skipped to avoid dominant-axis ambiguity).

**Option B — Spearman ρ (rank correlation)**
Equivalent to Kendall τ for binary concordance / discordance, but uses rank differences. Both capture the same information; Kendall τ is preferred because it is directly interpretable as (concordant − discordant) / total pairs.

**Recommendation:** A is complete and shipped. B adds no value over A.

---

## 1.13 Scene-Change Edge Pre-Filter ✅ Shipped S51

**Pain point:** When a source video contains a scene cut (or a severe lighting discontinuity that hold detection missed), the pairwise matcher still attempts to produce a translation for the cross-cut pair. The match will have low confidence and a spurious displacement. If that edge survives into bundle adjustment it introduces a wrong constraint that displaces all other frames.

**Option A — Global mean-luma gate [Quick Win] ✅ Shipped S51**
`_reject_scene_change_edges(edges, frames, max_luma_diff)` in `pipeline.py`. Computes mean grayscale luminance of each frame on a 64×64 thumbnail; rejects any edge where `|lum(i) − lum(j)| > max_luma_diff`. `_SCENE_CHANGE_LUMA_THRESH` module-level flag (default 0.0 = disabled, `ASP_SCENE_CHANGE_LUMA_THRESH=60.0` to enable). Wired as the first check in `_filter_edges`, before §1.2A+C static edge rejection. `SCENE_CHANGE_LUMA_THRESH=60.0` in `constants/anim.py`. `ASP_SCENE_CHANGE_LUMA_THRESH` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_pipeline.py::TestRejectSceneChangeEdges`. 362 tests passing.
- Pros: ~0.5ms per edge; zero new dependencies; safe by default (disabled until enabled).
- Cons: Threshold requires per-source tuning; does not catch illumination changes smaller than the threshold.

**Option B — Per-channel mean delta** ✅ **Shipped S57**
`_reject_scene_change_edges(..., use_bgr=True)` in `pipeline.py`. Per-channel (B, G, R) thumbnail means via `t.reshape(-1,3).mean(axis=0)`; `max(|ΔB|, |ΔG|, |ΔR|)` vs `max_luma_diff` threshold. Catches warm-orange vs cool-blue scene changes that grayscale misses (same luma ≈120, channel delta ≈200). `_SCENE_CHANGE_BGR_THRESH` flag (default 0.0=off, `ASP_SCENE_CHANGE_BGR_THRESH=60.0`). `SCENE_CHANGE_BGR_THRESH=60.0` in constants. `ASP_SCENE_CHANGE_BGR_THRESH` in `_CONFIG_SCHEMA`. Backward compatible (`use_bgr=False` default). Wired as second pass in `_filter_edges` after §1.13A. 5 tests in `test_pipeline.py::TestRejectSceneChangeEdgesBgr`. 392 tests passing.
- Max-delta metric (not Euclidean) keeps the threshold in the same [0,255] unit as §1.13A — no recalibration needed.

**Option C — CLIP embedding distance**
Compute CLIP visual embeddings and reject edges where cosine distance > 0.4 (typical threshold for scene-change detection). Semantically grounded — detects scene changes even when luma is similar.
- Cons: Requires CLIP (adds ~200MB dependency); overkill for luma-based scene cuts.

**Recommendation:** A is sufficient for the vast majority of scene-cut failures (most cuts involve a large brightness change). Implement B if A produces false negatives on colour-only scene changes. Skip C unless a pure-scene-embedding-quality gate is needed.

---

## 1.14 Per-Seam Colour-Distribution Banding Metric [Quick Win — diagnostic]

**Pain point (links to §1.4, §1.6, §1.16):** The existing per-seam diagnostics (`seam_visibility_score`, `ghost_seam_scores`) both operate in the *spatial* domain. Neither catches distributional colour mismatch — two adjacent strips can have similar mean luminance and identical local gradients but completely different histogram shapes (e.g., one dominated by a bright background gradient, the other by a dark character body), producing a perceptible tonal shift that spatial metrics miss.

**Option A — Bhattacharyya histogram similarity [Quick Win] ✅ Shipped S55**
`_seam_bhattacharyya_distances(img, n_strips, band_px=50)` in `bench_anime_stitch.py`. For each inter-strip seam boundary, computes greyscale histograms of the `band_px`-row window above and below; returns `1 − cv2.compareHist(HISTCMP_BHATTACHARYYA)`. Score in [0,1]: 1.0=identical distributions (clean seam), <0.5=severe colour mismatch (hard banding). `_compute_all_metrics` extended with `seam_color_scores` (List[float]) and `seam_color_min` (Optional[float]). Zero new deps. 5 tests in `test_bench_metrics.py::TestSeamBhattacharyyaDistances`.
- Complements `ghost_seam_scores` (repeated-edge periodicity) and `seam_visibility_score` (peak luminance jump). Bhattacharyya captures *distribution shape* divergence that those metrics miss.
- `band_px=50` (narrower than §3.8B's 100px) — 50 rows is sufficient for histogram characterisation.

**Option B — Colour-banding pipeline gate** ✅ **Shipped S56**
`_seam_color_similarity(img, k, n_strips, band_px=50)` + `_check_seam_color_gate(img, n_strips, thresh)` in `compositing.py`. `_SEAM_COLOR_GATE` flag (default 0.0=off, `ASP_SEAM_COLOR_GATE=0.55`). `SEAM_COLOR_GATE_THRESH=0.55` in constants. Stage 11.2 gate in `pipeline.py`: after `_composite_foreground`, calls `_check_seam_color_gate(canvas, N, _SEAM_COLOR_GATE_THRESH)` — on failure logs worst seam index and triggers `_scan_stitch_fallback`. `ASP_SEAM_COLOR_GATE` added to `_CONFIG_SCHEMA`. Both functions exported in `__all__`. 5 tests in `test_compositing.py::TestSeamColorGate`. 387 tests passing.
- Gate fires at thresh=0.55 (45% histogram divergence), the natural break between "tight single-colour zones" and "distinct-luminance-distribution strips". Default OFF preserves all existing corpus results.
- Does not re-run Stage 11 with wider feather (that would require seam-specific re-compositing infrastructure); instead triggers SCANS via the same `_sf = scans_frames or _reload_scans_frames(image_paths)` pattern as all other post-Stage-10 fallbacks.

**Option C — Per-channel (BGR) histogram comparison [Research]**
Extend Option A to compute per-channel histograms and return the minimum across channels. Detects hue shifts (e.g., warm interior strip vs cool exterior strip) that greyscale misses.
- Pros: More sensitive to chroma banding from different character colour palettes.
- Cons: 3× compute; Bhattacharyya on hue channels is less stable for near-black regions.

**Recommendation:** A is shipped (diagnostic baseline). B as the action gate once threshold is calibrated on the corpus. C if chroma-only banding is identified as a common failure mode.

---

## 1.15 Edge Graph Connectivity Validation [Quick Win] ✅ Shipped S58

**Pain point:** The §1.13A/B scene-change gates and §1.2A/C static-edge filters can, in edge cases, remove enough edges to partition the frame graph into disconnected components. Bundle adjustment then assigns unconstrained translations to isolated frames, producing bad affines that consume the full Retry 0–5 chain before landing on SCANS.

**Option A — Union-Find pre-BA connectivity check** ✅ **Shipped S58**
`_check_edge_graph_connectivity(edges, n_frames) → bool` in `pipeline.py`. Iterative path-compression Union-Find over all valid edges. Returns False when any frame 0..n_frames-1 is not reachable from frame 0. Wired immediately after the `if not edges:` guard in `run()`: disconnected graph → `_scan_stitch_fallback` with diagnostics log. O(E·α(N)) — negligible overhead. Exported in `__all__`. 5 tests in `test_pipeline.py::TestCheckEdgeGraphConnectivity`. 397 tests passing.
- Same Union-Find algorithm as §1.1B (spanning-tree pre-filter) — no new algorithmic machinery. The gate converts a guaranteed retry-chain waste into an immediate clean fallback.

---

## 1.16 Minimum Spanning Tree Weight Gate [Quick Win] ✅ Shipped S60

**Pain point:** §2.9C retry 0 (`_filter_high_conf_edges`) fires *after* BA has already been attempted with the full edge graph. When the graph is dominated by TM/PC fallback edges (weight~0.15–0.3 — phase-correlation or template-matching fallbacks, not LoFTR) the BA will produce poor translations regardless of the retry chain; the retry chain is wasted.

**Option A — MST weight pre-BA gate** ✅ **Shipped S60**
`_compute_mst_weight(edges, n_frames) → float` in `pipeline.py`. Builds max-weight spanning tree (Kruskal + iterative path-compression Union-Find) and returns `total_tree_weight / (N-1)`. Gate fires before Stage 7 BA when mean MST weight < `_MST_MIN_WEIGHT` (default 0.0=off, `ASP_MST_MIN_WEIGHT=0.35`). `MST_MIN_WEIGHT=0.35` constant in `constants/anim.py`. `ASP_MST_MIN_WEIGHT` added to `_CONFIG_SCHEMA`. Exported in `__all__`. 5 tests in `test_pipeline.py::TestComputeMstWeight`. 407 tests passing.
- LoFTR edges weight~0.6–0.9; TM/PC fallbacks~0.15–0.3; threshold 0.35 fires on all-TM/PC graphs.
- O(E log E) sort when enabled; zero overhead when disabled (default).
- Complementary to §1.15 (connectivity): §1.15 fires on disconnected graphs, §1.16 fires on weakly connected but low-confidence graphs.

---

## 1.17 GNC-TLS Bundle Adjustment [Quick Win] ✅ Shipped S61

**Pain point:** Category B failures (13.5% of corpus; test13 ratio=11.1×, test54=3.5×, test64=4.2×, test66=3.1×, test70=4.1×, test73=3.8×, test89=4.0×) arise when a single catastrophically bad LoFTR match inflates the 3×-median outlier threshold, shielding itself from rejection. The §1.1B spanning-tree pre-filter removes edges inconsistent with the MST reference, but cannot catch a bad edge that *is* the MST edge (highest-weight wrong match corrupts the BFS reference). The §1.1C Cauchy one-shot solve down-weights but cannot fully suppress edges with >50px residual once they contaminate the global median. A theoretically superior approach is graduated non-convexity (Yang et al. 2020): start with a convex surrogate (all edges weighted ≈1) and progressively anneal toward the truncated-LS cost, giving outlier edges exponentially smaller weights over 8 outer iterations.

**Option A — GNC-TLS outer continuation loop** ✅ **Shipped S61**
`_gnc_weights_geman_mcclure(residuals_sq, mu, c_sq) → ndarray` in `bundle_adjust.py` (Yang et al., IEEE RA-L 2020, arXiv:1909.08605). Geman-McClure per-edge weights `wᵢ = (μc² / (μc² + rᵢ²))²`. Outer loop in `_bundle_adjust_affine` initialises μ₀ = max_sq/(2c²) (convex boundary), then per-iteration: (1) compute per-edge squared translation disagreement, (2) update Geman-McClure weights, (3) LM step with `loss='linear'` and weights injected via `√w` multiplier in the `residuals()` closure, (4) anneal μ ÷= 1.4. Terminates when ‖Δx‖ < 1e-3 or μ < 0.01. `_GNC_OUTER=8` default (set `ASP_GNC_OUTER=0` to revert to §1.1C Cauchy+adaptive re-solve). `GNC_C_PX=10.0`, `GNC_MU_ANNEAL=1.4`, `GNC_MAX_OUTER=8` in `constants/anim.py`. `ASP_GNC_OUTER` in `_CONFIG_SCHEMA`. `_gnc_weights_geman_mcclure` exported in `__all__`. 5 tests in `test_bundle_adjust.py::TestGNCWeightsGemanMcclure`: unit-weights-large-mu, zero-residual-weight-one, high-residual-suppressed, weights-in-valid-range, higher-residual-lower-weight. **412 tests passing.**
- Default **ON** (not a gate): changes BA output on every run that has any edge residual > 0.
- Tolerates up to ~70–80% outlier edges vs. ~50% for RANSAC-style Cauchy rejection.
- Post-solve outlier rejection (§1.1 prong-1 + prong-2) remains unchanged as the backstop.
- Category B full-corpus impact pending benchmark; synthetic suite confirms no regression on existing tests.

---

## 2.9 BigWarp / Fourier-Mellin Manual Registration Fallback [Priority: High HITL]

**Pain point (links to §2.2, §1.1):** Despite AGNC and dual-pronged outlier rejection, pathological scenes (test13: 11.1× ratio) still trigger affine validation failures. The user has no manual override path — the pipeline either succeeds or falls back to SCANS. A human who can see the two failing frames could align them in 30 seconds.

**What BigWarp / Fourier-Mellin offers (§6.3 of Advanced Morphological Integration report):**
- **BigWarp-style landmark registration:** User clicks corresponding points on two frame thumbnails (structural background vertices — corners of lockers, architectural intersections). The pipeline overrides the LoFTR-failed edge with the user-defined affine/TPS transform. The bundle adjustment re-solves with the corrected edge.
- **Fourier-Mellin transform:** When only translation is unknown (the camera is purely translating), the user crops a static background region (avoiding the character), and Fourier-Mellin cross-correlates the magnitude spectra → sub-pixel translation. Available via DIPLib or custom FFT implementation. Faster than manual landmark placement.

**Options**

**A — Landmark Editor Dialog [Quick Win toward Research]**
When affine validation fails for an edge (i→j), emit `StitchWorker.stage_edge_failed(i, j, reason)`. Show a dialog with:
- Side-by-side thumbnails of frames i and j
- Click-to-add landmark pairs (minimum 2 for translation, 3 for affine, 4 for TPS)
- "Re-solve with this edge" button → injects the user-defined transform into the bundle adjustment
*Implementation:* ~300 LOC on top of `StitchWorker.set_edge_override()` from §2.7.

**B — Fourier-Mellin crop-and-align [Quick Win]**
Add a "Crop and align" button to the affine validation failure dialog: user rubber-bands a static background region, the pipeline computes Fourier-Mellin cross-correlation on that crop only (bypassing the character entirely), and injects the result as the edge transform.
- Pros: No landmark-clicking required for pure-translation scenes. Sub-pixel accuracy.
- Cons: Fails on scenes with scale/rotation; the crop must be entirely background.

**C — Auto-retry with tighter LoFTR threshold** ✅ **Shipped S37**
`_filter_high_conf_edges(edges, min_weight=HIGH_CONF_EDGE_THRESH)` in `pipeline.py` — keeps only edges with `weight >= 0.65` (LoFTR-quality; excludes TM/PC fallbacks at 0.15–0.55). Wired as "Retry 0" in Stage 7b: fires on `ratio=...` failures when ≥ N-1 HC edges survive. `HIGH_CONF_EDGE_THRESH=0.65` added to `constants/anim.py`. Exported in `pipeline.py __all__`. 5 tests in `test_pipeline.py::TestFilterHighConfEdges`.
- Pros: Zero UI work. Catches cases where 1-2 TM/PC fallback edges corrupt the bundle.
- Cons: If the bad edge is also LoFTR-quality (high confidence, wrong match), Retry 0 doesn't help; Retry 1 (adj-only) is the next line of defense.

**Recommendation:** C immediately (pure algorithmic, catches the easy cases). A for the remaining affine failures that C can't fix. B as an ergonomic shortcut for broadcast-quality (pure-translation) sources.

---

## 2.10 SAM2Flow / FlowVid Interactive Optical Flow Kinematics [Research — HITL]

**Pain point (links to §0.1, §2.4):** When `post_warp_diff > 22 lum units`, Stage 8.5 escalates to single-pose fallback — a clean but informationally incomplete solution. For extreme cases (character turning 180°, limb moving through 90° arc), no analytical flow engine can register the two poses. A human who can draw a trajectory arrow from the character's position in frame A to its position in frame B would resolve this instantly.

**What SAM2Flow / FlowVid does (§7.3 of Advanced Morphological Integration report):**
- **SAM2Flow:** Extends SAM 2's video object tracking to optical flow estimation. User specifies regions of interest and trajectory hints via click+drag prompts. The system propagates these sparse human annotations as definitive spatial control anchors across the frame sequence. Originally designed for textureless fluid dynamics (in vivo microcirculation), directly applicable to flat cel-shaded anime.
- **FlowVid:** User draws directional arrows on the seam-zone canvas. The FlowVid network uses these as ControlNet-style spatial anchors in a diffusion model, generating coherent frame-to-frame transitions even across 180° rotations. Inference: 512×512 at 1.5 min on A100 (3.1× faster than CoDeF, 10.5× faster than TokenFlow).

**Options**

**A — SAM2Flow seam-zone annotation [Research]**
After Stage 8.5 single-pose escalation, emit `StitchWorker.stage_seam_flow_failed(seam_info)`. The SeamDiagnosticPanel (§2.4) presents the seam crop with a "Draw trajectory" tool. User drags arrows → SAM2Flow uses these as anchors → the pipeline re-runs Stage 8.5 with the user-corrected flow.
- Pros: Directly resolves 180° rotation failures that RAFT/DIS and ARAP cannot.
- Cons: Requires SAM2Flow model weights. High VRAM during interactive use.

**B — FlowVid ControlNet trajectory synthesis [Research]**
For seams where single-pose fallback fires, open a FlowVid-powered "synthesize transition" dialog. User sketches the character's motion arc → FlowVid generates a synthetic intermediate frame that bridges the two poses → Stage 11 composites the synthetic frame instead of the hard-partition.
- Pros: Generates geometrically coherent content, not just a better warp.
- Cons: 1.5 min inference per seam. Anime domain gap (FlowVid was trained on natural video).

**C — User-drawn flow field (no model) [Quick Win]**
A simpler manual tool: the user draws displacement arrows on the seam thumbnail, and these are directly converted to a sparse flow field that overrides RAFT/DIS. The ARAP regularise step then smooths the user-drawn field to per-pixel resolution.
- Pros: No model weights. Zero latency. User sees exactly what flow they're injecting.
- Cons: Requires dense coverage of the character region by user annotations.

**Recommendation:** C immediately (leverages the existing SeamDiagnosticPanel from §2.4, no model). A once SAM2Flow model weights are available publicly. B for final-quality mode where the synthesis overhead is acceptable.

---

## 2.11 Intelligent Scissors Seam Routing [Quick Win — replaces DP seam]

**Pain point (links to §1.6, Category C1 failures):** The Stage 11 DP seam optimizer uses a per-pixel cost function but routes seams through character bodies when the background corridor is too narrow. The BiRefNet semantic cost only penalizes seams through character pixels — it doesn't guarantee a background-only path when the character fills the frame.

**What Intelligent Scissors does (§8.1 of Advanced Morphological Integration report):**
Transforms the seam into a shortest-path problem on a graph where nodes are pixels and edges are weighted by:
1. **Line-art gradient magnitude** — high cost at dark line-art boundaries (the character's outline)
2. **BiRefNet foreground probability** — exponential cost inside the character mask
3. **Laplacian zero-crossing** — prefer paths through uniform flat regions (background)

The user provides waypoints: clicking a sequence of points forces the algorithm to route through the background space the user designates. Dijkstra's algorithm computes the exact least-cost path through each waypoint gate, guaranteeing the seam never bisects the user-designated zones.

**Options**

**A — Intelligent Scissors dialog in SeamDiagnosticPanel [Quick Win]**
Add a "Route seam" tool to §2.4's SeamDiagnosticPanel. User clicks waypoints on the seam-zone preview. The pipeline re-runs the DP seam using these waypoints as hard constraints (nodes with cost=0 that must be included in the path). Re-composite takes ~1s.
*Implementation:* `cv2.GrabCut`-style waypoint injection into the existing `_seam_cut()` DP in `compositing.py`. ~200 LOC.
- Pros: Directly resolves Category C1 failures where seam bisects the character. Reuses the existing seam-finding code (adds waypoints, not a replacement).
- Cons: Requires user attention for each failing seam.

**B — Graph-cut with character-exclusion zone**
Automatically exclude the entire BiRefNet foreground region from the seam path by setting fg pixels to cost=∞. The DP is then forced into background-only columns. For scenes where the character fills the frame edge-to-edge, this may produce a seam through a background-free zone at the very edge.
- Pros: Fully automatic. Eliminates the need for user waypoints in most cases.
- Cons: When the character spans the full width (test09-type portrait shots), there IS no all-background path — the cost=∞ constraint makes the DP infeasible, requiring fallback to a minimum-cost through-character path.

**C — Multi-path seam voting [Research]**
Compute K candidate seam paths with different random seed initializations, evaluate each by seam_gradient and BiRefNet fg_overlap, select the one with the best combined score. No user interaction.
- Pros: Better than single-path DP without UI overhead.
- Cons: K× computation cost. Still limited by what the cost function can express.

**Recommendation:** B immediately (automatic fg exclusion zone, one change to `_seam_cut()` cost array). A for cases where B fails (character fills full width). C as a research-track alternative to A.

> **✅ Session 7 — B SHIPPED:** `_build_seam_cost_map()` in `compositing.py` now uses a two-tier cost: Tier 1 sets `cost=1.0` for every fg-interior pixel (with `sem_weight=200` → 200 energy barrier vs bg ~10–50), forcing the seam through background-only corridors. Tier 2 retains the dilated-edge avoidance zone. Graceful degradation when no all-background path exists. No env var needed — active by default whenever BiRefNet masks are available.

---

## 3.11 SAM 2 — Interactive Masking Upgrade [Research — HITL]

**Pain point (links to §4):** BiRefNet provides good-enough foreground masks for automated pipeline runs but fails on complex topologies: flowing hair, thin props (swords, staffs), fragmented line-art between limbs, and transparent overlay elements. These failures propagate through all downstream stages (ARAP flow, seam routing, temporal median).

**What SAM 2 offers (§5.1 of Advanced Morphological Integration report):**
SAM 2 introduces a streaming memory mechanism that propagates a single user-corrected mask across the entire video sequence. In the ASP context:
1. Pipeline generates initial BiRefNet masks for all selected frames.
2. On any frame where the mask is visually incorrect, user draws a bounding box or clicks missed pixels — SAM 2 refines the mask and propagates the correction across the full sequence.
3. The corrected masks replace BiRefNet masks for Stage 4.5 (photometric norm), Stage 8.5 (ARAP flow), and Stage 12 (temporal median plate).

**Options**

**A — SAM 2 as interactive mask correction [Research]**
Add a "Mask review" step after Stage 4 (BiRefNet masking), emitting masks via `StitchWorker.stage_masks_ready(masks)`. The MaskReviewPanel shows each frame's mask. User can click/drag to correct; SAM 2 propagates. Pipeline resumes with corrected masks.
- Implementation: `backend/src/models/sam2_wrapper.py` wrapping `sam2.build_sam2()`. ~200 LOC.
- Pros: Eliminates the most common failure mode (wrong mask → wrong flow → wrong composite).
- Cons: SAM 2 model weights (~300MB). Requires GPU for streaming memory. Adds a pipeline pause.

**B — SAM 2 as drop-in BiRefNet replacement [Research]**
Replace Stage 4 BiRefNet with SAM 2 auto-mode (no user prompts). SAM 2's auto-segmentation is significantly more accurate on complex topologies than BiRefNet's saliency-based approach.
- Cons: SAM 2 auto-mode is slower than BiRefNet and requires user confirmation for each frame. Interactive mode is the key advantage.

**Recommendation:** A in HITL review mode (§2.7 staged execution). B as a research experiment on a subset of the failing corpus. BiRefNet remains the default for automated runs.

---

## 3.12 Overmix Sub-Pixel Averaging — Maximal Frame Ingestion Philosophy [Research]

**Pain point (links to §0.2, §3.4):** The ASP aggressively reduces frame count (300 → ~18) before any processing. Overmix's research (§3 of Advanced Morphological Integration report) shows that for broadcast-quality compressed anime, this discards the MPEG compression-averaging benefit: by ingesting all frames within each hold block and sub-pixel-averaging them, the resulting background plate has 3–4× better SNR than any individual frame.

**What Overmix does (§3.1 of Advanced Morphological Integration report):**
1. **Pose-group subsetting:** Manually (or automatically via hold detection §1.11) group frames into hold blocks — runs of 2-4 consecutive frames with the same character cel.
2. **Sub-pixel alignment within hold:** Phase correlate consecutive frames within the hold → register them at sub-pixel precision → stack-average in 16-bit linear color space. MPEG DCT blocks on a static background average toward the true signal (compression noise cancels out by √N).
3. **Hold-averaged frames as pipeline inputs:** Each hold block produces one high-SNR representative frame. The bundle adjustment runs on these representatives, not on any individual compressed frame.

**How it applies to ASP:**
Replace the `_smart_select_frames()` first-past-threshold approach with:
1. Hold detection (§1.11) → group all N frames into K hold blocks
2. Within each hold block, sub-pixel-average the block (using the existing `flow_refine.py` ECC infrastructure for alignment)
3. Ensure K consecutive hold blocks cover the full canvas → run the greedy selection on hold-averaged representatives

**Options**

**A — Hold-block averaging preprocessing [Research]**
After `_detect_hold_blocks()`, for each block, align frames within the block using ECC and average into a 16-bit composite. Pass the composites to phase correlation instead of raw frames.
- Pros: Better SNR → better LoFTR feature extraction → fewer BA outliers. Directly addresses MPEG block noise in compressed sources.
- Cons: K×M ECC alignments (K holds × M frames/hold). Adds ~0.5s per hold block. Only beneficial for MPEG-compressed sources (streaming rips).

**B — Motion-compensated temporal average [Research]**
Use the existing RAFT/DIS flow infrastructure to align frames within each hold block before averaging. More accurate than ECC for holds with slight camera jitter.
- Cons: RAFT inference per frame pair within each hold. ~2–3s per hold block.

**C — Perceptual-hash deduplication only [Quick Win — already in §1.11]**
Keep the first frame of each hold block as the representative (no averaging). Hold detection alone reduces noise by removing near-duplicate frames from the selection, even without averaging.
- Already implemented via `ASP_HOLD_THRESHOLD=0.025`.

**Recommendation:** C immediately (already done via §1.11). A for broadcast/streaming sources where MPEG noise is significant. B as the quality ceiling once A is validated.

---

### 3.13 ProPainter Background Completion [Research — Highest Background Plate Impact]

**Pain point (links to §0, Stage 4.5):** Stage 4.5's temporal median produces the background plate by suppressing foreground pixels across N frames. When the character occupies >40% of any canvas row, that row has fewer than 3 background samples → the median is dominated by character pixels → ghosting bleeds into the background plate. For high-coverage scenes (test08, test09, test27), this is the primary cause of "strip ghosting" even when all seams are correctly found.

**What ProPainter does (ICCV 2023, [GitHub](https://github.com/sczhou/ProPainter)):**
1. **Recurrent Flow Completion (RFC):** Completes dense flow vectors in masked (fg) regions from adjacent background pixels.
2. **Dual-Domain Propagation (DDP):** Propagates pixel values from background regions to masked areas using both spatial (nearby-pixel) and temporal (adjacent-frame) paths simultaneously.
3. **Masked Transformer Refinement (MTR):** Sparse-attention transformer fills remaining gaps by attending over the full frame sequence, restricted to unmasked (bg) reference pixels.

Output: background-completed frames where every foreground pixel is replaced by a plausible background estimate. Deterministic (no diffusion randomness). ~192 FPS at 432×240 on consumer GPU.

**How it applies:** Insert after Stage 4 (BiRefNet masking) as Stage 4.7:
1. BiRefNet fg masks → ProPainter inpainting regions
2. ProPainter runs on all K selected frames → background-completed variants
3. Completed frames feed Stage 5 (phase correlation) for cleaner camera motion estimates
4. Completed frames replace raw frames in Stage 4.5 (temporal median) → background plate has 100% coverage per row

**Options**

**A — ProPainter as Stage 4.7 pre-processing [Research]**
Run ProPainter on the selected frames before Stage 5. Pass completed frames to both the temporal median (Stage 4.5) and phase correlation (Stage 5).
- Estimated inference: ~5 FPS at 1080p → ~3.6s per 18-frame sequence. Acceptable for quality mode.
- Pros: Directly eliminates background plate ghosting. Zero change to downstream stages.
- Cons: Requires CUDA and ~4GB VRAM at 1080p. Inpainting quality depends on BiRefNet mask quality — wrong masks → wrong fill.
- `ASP_PROPAINTER=1` flag (default OFF).

**B — ProPainter on temporal median frame only [Quick Win]**
Run ProPainter once on the ghosted Stage 4.5 output to inpaint ghost regions. Requires a ghost-probability map (SIQE §3.8 or seam_visibility_score §S14) to define the inpainting region.
- Pros: Single pass instead of N per-frame passes. ~0.5s.
- Cons: Post-hoc inpainting of a ghosted composite is harder than pre-processing clean frames.

**C — Dedicated background separation pipeline [Long-term]**
Fully decouple foreground and background pipelines: ProPainter produces a clean background video for the temporal median; the character pipeline uses ARAP-registered fg crops; merge at compositing time.
- Cons: Major refactoring of Stage 4.5 → Stage 12 pipeline.

**Recommendation:** A gated by `ASP_PROPAINTER=1` for quality mode. B as a cheap triage once SIQE (§3.8) provides ghost maps. C as the long-term architectural target for high-quality production runs.

---

### 3.14 Horizontal and Diagonal Scroll — 2D Canvas Support [Engineering — Unblocks Category F/H]

**Pain point (links to Category F/H in debug guide):** `_compute_canvas()` in `canvas.py` places all frames on the same x-column (uses only `ty`). Horizontal camera drift (`tx` range > 200px) is silently discarded. For datasets with combined horizontal+vertical scroll (diagonal pan), the canvas geometry is wrong before any compositing begins. Category F (test7: tx range ~500px) and Category H (test20: ty≈0, tx: 1857→0px) are permanent failures under the current canvas model.

**Current state:** The debug guide (Categories F and H) documents diagnostics. The temporary mitigation is SCANS fallback. No roadmap item for implementing true 2D canvas support previously existed.

**What 2D canvas support requires:**
1. `_compute_canvas(affines)` uses both `affines[i][0][2]` (tx) and `affines[i][1][2]` (ty) to place each frame at its correct 2D position.
2. For pure horizontal scroll (Category H), the seam-cut DP must run vertically — vertical strips rather than horizontal bands.
3. For diagonal scroll (Category F), strip geometry is a parallelogram; both DP seam routing and feathering in `compositing.py` must handle 2D strip regions.
4. The `_compute_row_coverage()` gate (Stage 10.5) must be extended to a 2D coverage map.

**Options**

**A — tx-aware canvas placement [Engineering — Step 1]** ✅ **De facto implemented**
`_compute_canvas()` in `canvas.py` already uses full `M[:2, :2] @ corners.T + M[:2, 2:3]` — i.e., the complete affine matrix including both tx and ty. Canvas width correctly reflects horizontal drift. `_detect_scroll_axis` is wired (S33); `horizontal` scroll → SCANS fallback. No action required for §3.14A.
- Estimated effort: ~20 LOC. Low risk.

**B — Horizontal-strip mode for pure horizontal scroll (Category H) [Engineering]**
When `scroll_type='horizontal'`, sort frames by tx, run DP seam cut along vertical lines in `compositing.py`.
- Estimated effort: ~300 LOC. New seam cost direction in `_build_seam_cost_map` and vertical scan in `_seam_cut`.

**C — Full 2D strip compositing for diagonal scroll (Category F) [Research]**
Generalised compositing where each frame's overlap region is a quadrilateral. Seam-cut operates in 2D with DP extended to a shortest-path on an unconstrained grid.
- Estimated effort: 500–800 LOC. Major refactor of `compositing.py`.

**Recommendation:** A immediately (low-risk canvas geometry fix, unblocks test7). B for the Category H corpus (test20 and similar). C as a long-term research track after B is validated.

---

### 3.15 OBJ-GSP + SemanticStitch Mesh-Based Seam Barrier [Research — Character-Preserving Seam Routing]

**Pain point (links to §1.6, §2.11, Category C1):** The §2.11B foreground cost barrier and §1.6A tiered cost map penalize seams through characters but cannot guarantee topology preservation when the character occupies most of the overlap width. When the character spans from column 0 to column W-50 and the only background corridor is at the very edge, the DP routes to that edge — producing a seam through an image border rather than through character-free space.

**What OBJ-GSP does (AAAI 2025):** Represents the overlap region as a triangular mesh. Semantic segmentation labels each triangle as character or background. Character triangles have infinite barrier cost and must be preserved as topological units — no seam can split a triangle cluster belonging to a single character body.

**What SemanticStitch does (Visual Computer 2025):** Two-pass approach: (1) identify all background-only columns in the overlap, (2) constrain the DP to only visit those columns. Reduces to zero the probability of a through-character seam for scenes where a background corridor exists.

**Options**

**A — SemanticStitch two-pass column filter [Quick Win]**
Pre-filter: columns where fg_mask coverage > 50% → set cost=∞ in seam DP. If no all-background column path exists, fall back to minimum-cost through-character path.
- Estimated effort: ~30 LOC addition to `_build_seam_cost_map()`. Zero new deps.
- Pros: Guaranteed background-only seam when corridor exists. Graceful fallback.

**B — OBJ-GSP triangular mesh constraint [Research]**
Build a triangular mesh on the overlap region from the BiRefNet fg boundary polygon (cv2.findContours + Delaunay triangulation). Character mesh triangles are marked with infinite barrier; Dijkstra routes around them on a mesh graph.
- Pros: Topology-preserving by construction. Character body as a geometric unit, not a pixel cost.
- Cons: Requires polygon triangulation (~50 LOC with scipy.spatial.Delaunay). Mesh graph Dijkstra is slower than the current vectorized DP.

**C — Hard-barrier seam with Intelligent Scissors waypoints [HITL]**
Extend §2.11A (Intelligent Scissors waypoints) with the SemanticStitch hard barrier: user-placed waypoints combined with the automatic column filter create a dual constraint system.
- Cons: Requires user interaction. Appropriate as an override tool in SeamDiagnosticPanel (§2.4), not as an automated step.

**Recommendation:** A immediately (trivial addition, backward-compatible). B once A is validated on the Category C1 failure corpus. C as the HITL complement to A/B for edge cases.

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| 1.1 Bundle Adjustment Hardening | [#11-bundle-adjustment-hardening](#11-bundle-adjustment-hardening) |
| 1.2 Near-Zero Edge Filter | [#12-near-zero--zero-translation-edge-filter](#12-near-zero--zero-translation-edge-filter) |
| 1.3 Scale and Rotation | [#13-scale-and-rotation-handling](#13-scale-and-rotation-handling) |
| 1.4 Gain Clamp Widening | [#14-gain-clamp-widening-for-dark-scenes](#14-gain-clamp-widening-for-dark-scenes) |
| 1.5 Stage 11 Performance | [#15-stage-11-composite-performance](#15-stage-11-composite-performance) |
| 1.6 Ghosting Reduction | [#16-ghosting-reduction-in-composite-zone](#16-ghosting-reduction-in-composite-zone) |
| 1.7 Border Rectangling | [#17-recdiffusion-border-rectangling](#17-recdiffusion-border-rectangling) |
| 1.8 Config File | [#18-asp-pipeline-configuration-file](#18-asp-pipeline-configuration-file) |
| 1.9 Fallback Path Purity | [#19-fallback-path-purity](#19-fallback-path-purity) |
| 1.10 RLHF Loop | [#110-rlhf-loop-integration](#110-rlhf-loop-integration) |
| 2.1 Frame Selection Assistant | [#21-frame-selection-assistant-quick-win](#21-frame-selection-assistant-quick-win) |
| 2.2 Edge Graph Inspector | [#22-edge-graph-inspector--editor-quick-win](#22-edge-graph-inspector--editor-quick-win) |
| 2.3 Anchor & Canvas Layout | [#23-anchor-frame--canvas-layout-inspector-priority-medium](#23-anchor-frame--canvas-layout-inspector-priority-medium) |
| 2.4 Seam Registration Inspector | [#24-seam-registration-inspector-highest-impact](#24-seam-registration-inspector-highest-impact) |
| 2.5 Coverage Map | [#25-temporal-median-coverage-map-quick-win](#25-temporal-median-coverage-map-quick-win) |
| 2.6 Crop Assistant | [#26-output-scale--crop-assistant-priority-medium---test27-fix](#26-output-scale--crop-assistant-priority-medium---test27-fix) |
| 2.7 StitchWorker Staged Execution | [#27-architecture-stitchworker-staged-execution-implementation-foundation](#27-architecture-stitchworker-staged-execution-implementation-foundation) |
| 2.8 HybridStitch Handoff | [#28-asp-to-hybridstitch-handoff-long-term](#28-asp-to-hybridstitch-handoff-long-term) |
| 3.1 AnimeInterp SGM — Aperture Problem | [#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact](#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |
| 3.2 ConvGRU Recurrent Flow Refinement | [#32-convgru-recurrent-flow-refinement-for-kinematic-accuracy-research](#32-convgru-recurrent-flow-refinement-for-kinematic-accuracy-research) |
| 3.3 DINOv2 + SigLIP Submodular Selection | [#33-dinov2--siglip-submodular-frame-selection-priority-high--directly-addresses-gt-coupling](#33-dinov2--siglip-submodular-frame-selection-priority-high--directly-addresses-gt-coupling) |
| 3.4 FD-Means Hold Detection | [#34-fd-means-animation-hold-detection-quick-win--preprocessing](#34-fd-means-animation-hold-detection-quick-win--preprocessing) |
| 3.5 CamFlow Hybrid Motion Basis | [#35-camflow-hybrid-motion-basis-for-camera-displacement-research](#35-camflow-hybrid-motion-basis-for-camera-displacement-research) |
| 3.6 ToonCrafter Seam Synthesis | [#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium](#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium) |
| 3.7 UDIS++ / UDTATIS Diffusion Composition | [#37-udis--udtatis-diffusion-based-seam-composition-long-term--end-to-end-replacement](#37-udis--udtatis-diffusion-based-seam-composition-long-term--end-to-end-replacement) |
| 3.8 SIQE Ghosting Metric | [#38-siqe-no-reference-ghosting-detection-quick-win--metric-upgrade](#38-siqe-no-reference-ghosting-detection-quick-win--metric-upgrade) |
| 3.9 SI-FID Stitching Quality | [#39-si-fid-stitched-image-fréchet-distance-for-reference-free-evaluation-research](#39-si-fid-stitched-image-fréchet-distance-for-reference-free-evaluation-research) |
| 3.10 MLLM Semantic Quality Scoring | [#310-mllm-semantic-quality-scoring-research--autonomous-quality-assurance](#310-mllm-semantic-quality-scoring-research--autonomous-quality-assurance) |
| 1.11 Animation Hold Detection | [#111-animation-hold-detection--preprocessing-quick-win--session-6](#111-animation-hold-detection--preprocessing-quick-win--session-6) |
| 2.9 BigWarp / Fourier-Mellin Fallback | [#29-bigwarp--fourier-mellin-manual-registration-fallback-priority-high-hitl](#29-bigwarp--fourier-mellin-manual-registration-fallback-priority-high-hitl) |
| 2.10 SAM2Flow / FlowVid Interactive Flow | [#210-sam2flow--flowvid-interactive-optical-flow-kinematics-research--hitl](#210-sam2flow--flowvid-interactive-optical-flow-kinematics-research--hitl) |
| 2.11 Intelligent Scissors Seam Routing | [#211-intelligent-scissors-seam-routing-quick-win--replaces-dp-seam](#211-intelligent-scissors-seam-routing-quick-win--replaces-dp-seam) |
| 3.11 SAM 2 Interactive Masking | [#311-sam-2--interactive-masking-upgrade-research--hitl](#311-sam-2--interactive-masking-upgrade-research--hitl) |
| 3.12 Overmix Sub-Pixel Averaging | [#312-overmix-sub-pixel-averaging--maximal-frame-ingestion-philosophy-research](#312-overmix-sub-pixel-averaging--maximal-frame-ingestion-philosophy-research) |
| 3.13 ProPainter Background Completion | [#313-propainter-background-completion-research--highest-background-plate-impact](#313-propainter-background-completion-research--highest-background-plate-impact) |
| 3.14 Horizontal/Diagonal Scroll 2D Canvas | [#314-horizontal-and-diagonal-scroll--2d-canvas-support-engineering--unblocks-category-fh](#314-horizontal-and-diagonal-scroll--2d-canvas-support-engineering--unblocks-category-fh) |
| 3.15 OBJ-GSP + SemanticStitch Seam Barrier | [#315-obj-gsp--semanticstitch-mesh-based-seam-barrier-research--character-preserving-seam-routing](#315-obj-gsp--semanticstitch-mesh-based-seam-barrier-research--character-preserving-seam-routing) |
