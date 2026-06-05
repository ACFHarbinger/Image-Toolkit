# ASP — State of the Pipeline: What Works, What Failed, What's Next

*Date: 2026-06-05. Updated through Session 9.*  
*Primary benchmark corpora: 96 tests (`asp_test01–96`), 55 with ground truth in `data/ground_truth/`. 5-test subset (`test04/08/09/27/57`) used for rapid iteration.*

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
| 7b | Affine validation gate (ratio < 3, min_gap > 25px, rotation/scale checks) | `validation.py` |
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
- **Unit tests**: **107 passing** in `backend/test/anim/` (fg_register, rendering, bundle_adjust, filter_edges, affine_validation; 2 ARAP Push tests added S4; 8 frame_selection tests added S5; 8 hold+GNC+SLIC tests added S6; 2 DINOv2 tests added S8; 3 LSD collinearity tests added S8/S9; 2 ToonCrafter tests added S9)

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

*Sessions 6–9 completed: Hold detection (S6), GNC robust loss (S6), SLIC SGM proxy (S6), Stage 12.5 content trim (S7), DINOv2 pose metric (S8), LSD collinearity in ARAP (S8), Aligned-SSIM (S8), ToonCrafter seam synthesis (S9). Remaining priorities below.*

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

| Aspect | Current state (S9) | Primary bottleneck | Next step |
|--------|--------------|-------------------|----------|
| **Frame selection** | 50px min_step, hold detection (S6), DINOv2 pose metric (S8) | GT-coupling wall prevents enabling Pass 2 by default | Enable `ASP_POSE_WINDOW_PX=80` once GT-coupling resolved |
| **Flow estimation** | RAFT (pretrained) + DIS fallback, seam-band crops; SLIC SGM proxy (S6, experimental) | Aperture problem on flat cels: RAFT = DIS in accuracy | Segment-guided flow (AnimeInterp SGM); RAFT fine-tune on LinkTo-Anime |
| **ARAP regularisation** | Per-cell median translation; Push → Regularise (S4); LSD collinearity boundary-cells + 50% mag guard (S8) | LSD has zero measurable SSIM impact; Push has zero impact (flow quality not bottleneck) | RAFT confidence-gating for blend width |
| **Bundle adjustment** | GNC Cauchy robust loss, f_scale=10.0 (S6) | Outlier matches still affect BA before edge filter | — |
| **Midpoint warp** | Symmetric α=0.5; post_warp_diff escalation at 22; ToonCrafter worst-seam (S9, `ASP_TOONCRAFTER_SEAM=1`) | Halves but doesn't eliminate pose gap | Global reference with RAFT confidence gating |
| **Canvas trim** | Stage 12.5 scroll-axis content trim, 20px padding (S7) | Partially closes scale gap for test27 | — |
| **FG-excluded median** | Background-only plate (A5) | Always-fg fallback still ghosts in foreground-heavy scenes | Segment-medoid fallback |
| **Seam blend** | DSFN soft-seam + semantic routing + both-content Laplacian | Remaining ghosting from imperfect FG registration | RAFT confidence-weighted blend width |
| **Fallback (gate)** | Render-gate (coherence + banding on final composite) | 41% trigger rate — fundamental animated-video scene type | Accept as correct for these scenes |
| **GT-SSIM (5 tests)** | test09: 0.787 asp_better, test27: 0.709 asp_better, test57: 0.743 | Animation timing mismatch; midpoint-warp 50% residual | Pose-consistent frame selection → reduce residuals to <10px |
| **Metrics** | SSIM + seam_coherence + aligned_ssim_vs_gt (S8) | raw SSIM penalises scale mismatch (test27 0.039 bias) | SI-FID supplementary metric |
| **Tests** | 107 passing | — | Full 96-test re-run after S6–S9 feature integration |
