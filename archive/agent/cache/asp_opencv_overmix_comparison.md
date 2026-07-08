# Deep Comparative Analysis: OpenCV Stitcher vs Overmix vs ASP
*Generated 2026-06-22 — based on full C++ / Python source reads*

---

## Table of Contents
1. [Executive Summary — Big Picture](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Stage-by-Stage Comparison](#3-stage-by-stage-comparison)
   - 3.1 Input & Frame Selection
   - 3.2 Photometric Pre-processing
   - 3.3 Feature Detection & Description
   - 3.4 Pairwise Matching
   - 3.5 Bundle Adjustment / Global Pose Estimation
   - 3.6 Canvas Construction & Warping
   - 3.7 Seam Finding
   - 3.8 Exposure Compensation
   - 3.9 Blending
   - 3.10 Post-processing & Quality Control
4. [Domain Specialisation Matrix](#4-domain-specialisation-matrix)
5. [Algorithmic Gap Analysis (OpenCV vs ASP)](#5-algorithmic-gap-analysis)
6. [Algorithmic Gap Analysis (Overmix vs ASP)](#6-overmix-vs-asp-gap-analysis)
7. [Strength / Weakness Summary Table](#7-strength-weakness-summary-table)
8. [Implementation Roadmap Candidates](#8-implementation-roadmap-candidates)

---

## 1. Executive Summary

All three systems solve the same fundamental problem — compositing multiple partially-overlapping images into a single coherent panorama — but are radically different in their assumptions, target domains, and architectural choices.

**OpenCV Stitcher** (`opencv/modules/stitching/`) is a *general-purpose panorama engine* designed for real-world photography at arbitrary orientations. It assumes rich texture (for SIFT/ORB/BRISK feature matching), 2-D or spherical homography camera models, and targets the "tourist panorama" problem. Its seam finder uses global graph-cut energy minimisation (GCGraph), its blender uses Laplacian pyramids, and its exposure compensator uses a dense per-block gain map. It is extremely well-engineered for its domain and difficult to beat for natural images.

**Overmix** (`Overmix/src/`) is a *super-resolution / frame-averaging engine* designed for anime screen-capture or scanner output. Its core innovation is treating the individual frames as independent noisy samples of the same scene (micro-shifted by hand-shake or scanning jitter) and averaging them pixel-by-pixel with alpha compositing to recover sub-pixel resolution. Alignment is done by brute-force MAD / gradient minimisation on raw pixel values (no keypoints). There is no seam — all frames are blended together with pixel-wise averaging. The output is a single high-resolution reconstructed image, not a panorama.

**Anime Stitch Pipeline (ASP)** (`backend/src/animation/`) is a *domain-specific panorama engine* for anime vertical-scroll captures. It inherits the panorama objective from OpenCV but operates under extremely different constraints: minimal texture (flat cel shading), animated foreground characters that change pose between frames, uniform lighting (no parallax, no lens distortion), and highly structured scroll motion. Its innovations are (1) foreground/background separation via BiRefNet so seams are routed in background regions, (2) ARAP-based foreground pose registration to align character poses at seam boundaries, (3) a 1-D DP seam cutter guided by a semantic cost map, and (4) an exhaustive suite of pre/post-composite quality gates to detect failure modes and fall back to a simple scan-stitch algorithm.

---

## 2. System Architecture Overview

### 2.1 OpenCV Stitcher

```
Input images
    │
    ▼
Feature detection (SIFT/ORB/BRISK/AKAZE) on all images at registr_resol_=0.6
    │
    ▼
Pairwise feature matching (BestOf2NearestMatcher / BestOf2NearestRangeMatcher)
 ├── FLANN kNN (k=2) → Lowe ratio filter → cross-check dedup
 └── RANSAC homography → inlier re-match → confidence score
    │
    ▼
Camera model estimation (HomographyBasedEstimator / AffineBasedEstimator)
 ├── PANORAMA: focalsFromHomography() → max spanning tree BFS → R matrices
 └── SCANS: estimateAffinePartial2D() per pair
    │
    ▼
Bundle Adjustment (BundleAdjusterRay / BundleAdjusterAffinePartial)
 ├── Levenberg-Marquardt (LM) on 4-param (focal+rvec) or 4-param (a,b,tx,ty)
 ├── Numeric Jacobian (step=1e-3)
 └── Post-BA: waveCorrect() removes accumulated rotation drift
    │
    ▼
Warping (SphericalWarper / AffineWarper) at seam_est_resol_=0.1
    │
    ▼
Exposure compensation (BlocksGainCompensator 32×32 blocks + Gaussian smoothing)
    │
    ▼
Seam finding (GraphCutSeamFinder — min-cut in 2D overlap per pair)
    │
    ▼
Warping at compose_resol_=ORIG_RESOL then exposure apply
    │
    ▼
Blending (MultiBandBlender — Laplacian pyramid N bands)
    │
    ▼
Output panorama
```

**Code path**: `Stitcher::stitch()` → `Stitcher::estimateTransform()` → `Stitcher::composePanorama()` in `stitcher.cpp`.

### 2.2 Overmix

```
Input images (scan captures / screen recordings)
    │
    ▼
Image loading → ImageContainer (groups of images per frame/animation-layer)
    │
    ▼
Alignment: RecursiveAligner (divide-and-conquer)
 ├── Halve sequence recursively until pairs
 ├── AComparator::findOffset() per pair:
 │    ├── GradientComparator: hierarchical grid search over (tx,ty) candidates
 │    │    └── GradientPlane::findMinimum() with QtConcurrent parallel diff
 │    ├── MultiScaleComparator: recursive 2× pyramid then 4-neighbour refinement
 │    ├── BruteForceComparator: exhaustive grid scan of [−mov, +mov]² range
 │    └── LogPolarComparator: rotation+scale+translation via log-polar FFT
 ├── AverageRender intermediate (alpha-weighted pixel mean) for pairwise merge
 └── LinearAligner post-pass: least-squares fit to remove positional wobble
    │
    ▼
AverageRender::render() — final pixel-average compositing
 ├── SumPlane: accumulates (pixel × alpha) and alpha sums per canvas position
 ├── Alpha propagation per channel (Gaussian scale for chroma channels)
 ├── Optional rotation + zoom (Transformations::rotation)
 └── Mitchell-filter rescaling at output
    │
    ▼
StatisticsRender alternatives: median / min / max / difference pixel functions
    │
    ▼
Output: upscaled super-resolved reconstruction
```

**Code path**: `RecursiveAligner::align()` → `RecursiveAligner::combine()` → `AverageRender::render()`.

AnimationSeparator is orthogonal: it clusters frames into temporal groups by finding the threshold that maximises sign changes across the pairwise-error distribution (a 1-D change-point detection heuristic), then distributes frames across named layers for static-background averaging.

### 2.3 ASP (Anime Stitch Pipeline)

```
Input: N frame paths (anime scroll captures)
    │
    ▼ Stage 1
Load frames (_load_frames) + sort by numeric suffix (_sort_frames_by_index)
 └── Static input gate (§1.29): MAD < 2 luma → copy frame 0 as output
    │
    ▼ Stage 2
Width normalisation (_normalise_widths): crop/pad all frames to median width
    │
    ▼ Stage 3 [optional]
BaSiCWrapper photometric flat-field correction + vignetting removal
    │
    ▼ Stage 4
Foreground masking:
 ├── BiRefNetWrapper → per-frame binary fg/bg mask (SAM2 optional)
 └── §1.37: bg coverage gate — if < 5% bg pixels → SCANS fallback
    │
    ▼ Stage 4.5
Background photometric normalisation:
 ├── Per-frame bg median color → global median → per-frame gain vector
 ├── Adaptive clamp: dark scene [0.80,1.25], normal [0.88,1.14]
 ├── Continuous gain clamp (§1.4B S24): clamp_width = 0.26 − 0.12*(ref_lum/255)
 ├── Coherence skip gate (§1.18): per-pair bad-diff detection
 ├── Gain-adaptive feather minimum (§1.6B): widens feather when gain_diff>0.267
 ├── Per-segment k-means color gain (P2.6): 8-cluster per-region correction
 └── Multi-scale / histogram-match alternatives [optional §1.4D/E]
    │
    ▼ Stage 4.7 [optional §3.13]
ProPainter background completion: inpaint fg-masked pixels with bg estimates
    │
    ▼ Stage 5-6
Pairwise matching (_pairwise_match):
 ├── Matcher priority: JamMa (4K) → EfficientLoFTR → kornia LoFTR → ALIKED+LG → RoMa
 ├── Phase correlation (_phase_correlate) on bg-masked, highpassed frame pairs
 ├── Template matching fallback (_template_match)
 ├── Skip-pair edges (non-adjacent pairs for redundancy)
 ├── Post-match gates: scene-change luma (§1.13), MST weight (§1.16),
 │   adjacency coverage (§1.43), sign consistency (§1.47), displacement CV (§1.48),
 │   adjacent min weight (§1.49), triangular consistency (§2.14)
 └── Scale normalisation (§1.3C): inter-frame zoom correction
    │
    ▼ Stage 7
Bundle adjustment (_bundle_adjust_affine):
 ├── §1.1B Spanning-tree inlier filter (Kruskal + BFS reference propagation)
 ├── §1.17 GNC-TLS outer loop (8 iterations, Geman-McClure weights)
 ├── §1.1C LM with Cauchy loss (f_scale=10px via scipy least_squares)
 ├── §1.1D Adaptive GNC f_scale (2× median residual, re-solve if >1.5×)
 └── §4.3 Wave correction: subtract linear drift from tx/ty sequences
    │
    ▼ Stage 7b
Affine validation (_validate_affines):
 ├── Retry 0 (§2.9C): high-conf edge re-solve (weight≥0.65, N-1 HC edges)
 ├── Retry 1-5: successively relaxed min_step / max_ratio thresholds
 ├── §1.50 BA max residual gate, §1.52 BA weighted mean residual gate
 ├── §1.55 BA rotation gate (|angle| > threshold → SCANS)
 └── §1.60 TX sequence oscillation gate
    │
    ▼ Stage 8
Sub-pixel refinement:
 ├── SEA-RAFT optical flow (_flow_refine) [optional]
 └── ECC affine refinement (_ecc_refine) [optional]
    │
    ▼ Stage 8.8 [optional]
Hires keyframe substitution (upscaled frames for compose resolution)
    │
    ▼ Stage 9
Canvas construction (_compute_canvas):
 ├── Warp all frames with affines → compute bounding box
 ├── T_global shift: midplane normalisation
 ├── Gates: §1.44 max adjacent gap, §1.45 canvas width ratio, §1.51 min overlap,
 │   §1.53 canvas memory MB, §1.62 canvas aspect ratio
 └── §3.14 Scroll axis detection → horizontal scroll → SCANS fallback
    │
    ▼ Stage 10
Temporal renderer (_render_laplacian / _render_median):
 ├── Warp frames into canvas space using affines
 ├── Temporal median render (ghost removal for animated fg characters)
 ├── Valid mask tracking (which canvas pixels are covered)
 └── Gates: §1.39 render coverage, §1.54 render luma std
    │
    ▼ Stage 10.2 [optional §5A/C]
Background zero-coverage fill (inpaint uncovered canvas regions)
    │
    ▼ Stage 10.5
Multi-frame canvas coverage gate (§0 item 2):
 ├── _compute_row_coverage: fraction of rows covered by ≥2 frames
 └── pct_multi < ASP_COV_MIN_MULTI_PCT (0.30) → SCANS fallback
    │
    ▼ Stage 10.8-10.9
Pre-composite bg luma gates: spread (§1.71) and monotonicity (§1.73)
    │
    ▼ Stage 11
Foreground composite (_composite_foreground):
 ├── _find_optimal_boundaries: ±250 row search for minimum seam step
 ├── Adaptive feathering: similarity → feather width (FEATHER_MIN=80, MAX=300)
 ├── _build_seam_cost_map: fg interior (cost=1.0), fg edge buffer (0.5), bg (0.0)
 │   + §3.15A column barrier (cost=2.0) for fg-dominated columns
 │   + §1.65 fg erosion: shrink Tier-1 ring to push seam one ring outward
 ├── _seam_cut (1-D DP, left→right monotone path):
 │   energy = diff + grad(diff) + edge_weight*(edges_i + edges_j) + sem_cost
 │   + §1.125 seam transition penalty (midline prior)
 │   forward pass: min_filter1d(size=3) per column
 │   traceback: slice-argmin
 ├── §1.5D seam path cache (keyed by frame paths + seam flags)
 ├── §1.2 Parallel seam DP (ThreadPoolExecutor, max 4 workers)
 ├── §1.6C Poisson seam blend [optional]: cv2.seamlessClone ±20px band
 ├── _laplacian_blend: N-band pyramid blend with found path
 ├── FG registration at seam (ARAP + LSD collinearity + DINOv2 frame selection):
 │   ├── register_foreground_at_seam (_arap_regularise)
 │   ├── SLIC-SGM proxy for initial flow [optional §S6]
 │   ├── Stage 12.5: content trim (scroll-axis-aware fg extent crop)
 │   ├── Adaptive feather refinement (§S12): seam_post_diffs < 8 → widen 1.5×
 │   └── Single-pose escalation: post_warp_diff > 22 lum → hard partition
 ├── Bg-only normalization (§1.4C bg gain unclamped, §1.4B continuous clamp)
 ├── §1.17 Per-pixel DSFN ramp (sim_diffused drives blend width per pixel)
 ├── §1.20 bg-mask-aware sim forcing (fg-vs-fg region: sim=0, 10px ramp)
 ├── §S15/S16 single-pose soft edge + seam color matching
 └── §S17 adaptive boundary search (100 range for pure vertical scroll)
    │
    ▼ Post-stage 11 quality gates
 ├── §1.24 seam step gate (|above−below| luma)
 ├── §1.14B Bhattacharyya color gate, §1.14C BGR variant
 ├── §1.66 NCC structural coherence gate
 ├── §1.21 seam luma equalisation + §1.56 chroma equalisation [optional]
 └── §1.10A RLHF quality score (reward model inference)
    │
    ▼ TELEA fill (§1.7B): inpaint gaps < 50px with cv2.INPAINT_TELEA
    │
    ▼ _crop_to_valid: content-aware bounding-box crop
    │
    ▼ Super-resolution [optional]: upscale_anime()
    │
    ▼ Output: panorama image
```

**SCANS fallback chain**: Retry 0 → Retry 1-5 → `_panorama_stitch_fallback` (cv2.Stitcher_create PANORAMA mode) → `_scan_stitch_fallback` (direct vertical concatenation).

---

## 3. Stage-by-Stage Comparison

### 3.1 Input & Frame Selection

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV** | All images; user-provided order irrelevant | `findFeatures()` works image-agnostic; `BestOf2NearestMatcher` finds topology automatically |
| **Overmix** | All frames loaded; `AnimationSeparator` clusters into temporal layers | Clustering uses pairwise error + threshold search (max sign-change criterion) |
| **ASP** | Temporal ordering mandatory; numeric-suffix sort (§1.63) | `smart_select_frames`: hold detection (MAD / dHash §S43), DINOv2 feature frames (§S8), temporal variance filter (§S39), near-dup luma filter (§S26) |

**Analysis**: OpenCV is topology-agnostic — it works even when images are supplied in random order because the matcher discovers which pairs overlap. ASP mandates temporal order because it exploits the monotone scroll assumption. Overmix is intermediate: order matters for `AnimationSeparator` but not for `AverageRender`.

ASP's frame-selection pipeline is unique: it actively *removes* redundant frames before matching to reduce BA graph complexity and eliminate hold blocks (repeated frames due to MPEG hold) that corrupt phase correlation.

### 3.2 Photometric Pre-processing

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV** | None before matching; exposure only after seam finding | `BlocksGainCompensator` + Gaussian smoothing applied per-block post-seam |
| **Overmix** | None | Alpha compositing handles transparency; no gain correction |
| **ASP Stage 3** | BaSiC flat-field correction + vignetting (optional) | `BaSiCWrapper` removes shading artifacts from repeated scanning |
| **ASP Stage 4.5** | Per-frame bg scalar gain + per-segment k-means gain | Global median bg color → per-frame gain vectors; clamp continuous (§1.4B); k-means segment correction (P2.6) |
| **ASP §1.4D/E** | Multi-scale spatially-varying gain / CDF histogram matching | Gaussian-blur-derived per-pixel gain map (§1.4D); 256-entry CDF LUT (§1.4E) |

**Analysis**: OpenCV defers photometric correction until after seam finding, then applies it globally using `BlocksGainCompensator`. The 32×32 block size captures spatially-varying exposure. ASP applies photometric correction *before* matching, which ensures phase correlation operates on normalised frames. However, ASP's gain normalisation before matching is a scalar (or per-segment scalar), not a per-pixel block map — this is one of the key gaps driving the `strip_banding_score` failures where ASP is 25 luma units worse than OpenCV.

The ASP §1.4D multi-scale gain (enabled via `ASP_MULTISCALE_GAIN=1`) is closer to OpenCV's blocks approach, but uses a Gaussian-blur-derived field rather than a discrete 32×32 block grid. The discrete block grid with iterative Gaussian smoothing (OpenCV) gives better spatial control.

### 3.3 Feature Detection & Description

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV PANORAMA** | SIFT (default) / ORB / BRISK / AKAZE | `OrbFeaturesFinder`, `SiftFeaturesFinder` wrappers; all images at `registr_resol_=0.6×` |
| **OpenCV SCANS** | SIFT (default) | Same; fewer candidates needed because affine model is simpler |
| **Overmix** | No keypoints — raw pixel differences | GradientComparator: hierarchical grid search; MultiScaleComparator: recursive 2× downsample + 4-neighbour search |
| **ASP** | EfficientLoFTR / kornia LoFTR / ALIKED+LightGlue / RoMa / JamMa (4K) | Dense matcher (LoFTR returns point correspondences not descriptors); falls back to phase correlation + template matching |

**Analysis**: OpenCV's sparse keypoint approach (SIFT/ORB) works well for natural images with rich texture but fails on anime frames where cel shading provides almost no SIFT-detectable corners. This is why `cv2.Stitcher_create(SCANS)` often fails on anime input — there are insufficient feature matches.

ASP addresses this by using dense matchers (EfficientLoFTR operates on grayscale image patches without explicit corner detection) plus phase correlation (which finds the global translation peak in frequency domain). Overmix goes further: it uses raw pixel MAD/L2 difference over the entire overlap region, making it completely texture-agnostic, but this limits it to small displacements (brute-force over small motion range).

### 3.4 Pairwise Matching

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV** | `BestOf2NearestMatcher` | FLANN kNN (k=2) → Lowe ratio (1−match_conf) → RANSAC findHomography → confidence = inliers / (8 + 0.3×total) |
| **Overmix GradientComparator** | Hierarchical grid search + QtConcurrent parallel | `findMinimum()`: divide search area recursively, evaluate `simpleAlpha()` (weighted L1/L2) per candidate; DiffCache memoises evaluated positions; striped parallelism via QtConcurrent::map |
| **Overmix MultiScaleComparator** | Recursive 2× pyramid + 4-neighbour | `findOffset(img/2, img/2, hint/2)` recurse to base; check 4 sub-pixel candidates at each level; return min-error offset |
| **ASP** | Multi-matcher ensemble | Phase correlation (FFT-based) on bg-masked highpass pair → `_phase_correlate()`; EfficientLoFTR dense match → median displacement; template match fallback; all as edge dict with `weight` confidence |

**Analysis**: OpenCV's matching confidence is normalized (`inliers / (8 + 0.3×total)`) which makes it comparable across pairs of different sizes. ASP assigns weight from phase correlation peak response (in [0,1]) or LoFTR inlier fraction (via spread filter §1.36).

OpenCV uses RANSAC to reject outlier matches — estimating a full homography internally. ASP's phase correlation produces a single 2D translation peak, which is inherently RANSAC-free (the FFT response integrates all bg pixel contributions). This makes ASP's matching more robust to partial-frame fg character overlap (because bg pixels dominate the phase-correlation signal after masking).

Overmix's GradientComparator is the only approach that explicitly uses `Difference::simpleAlpha()` — an alpha-weighted L1/L2 per-pixel difference accounting for per-image transparency masks. This is important for MFSR (multiple captures of the same scene at slightly different positions) but irrelevant for scroll panoramas.

The `BestOf2NearestRangeMatcher` in OpenCV (used when `range_width > 0`) limits matching to `range_width` adjacent pairs, exactly like ASP's "adjacent + skip-pair" strategy. OpenCV's approach is simpler: a window parameter; ASP's is more explicit with separate edge lists for adj vs. skip pairs.

### 3.5 Bundle Adjustment / Global Pose Estimation

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV BundleAdjusterRay** | 4-param LM on unit sphere | params=[focal,rx,ry,rz]; error = sqrt(f1*f2) × (ray1 − ray2); normalise to centre image; wave-correct |
| **OpenCV BundleAdjusterAffinePartial** | 4-param LM similarity | params=[a,b,tx,ty]; H = [[a,-b,tx],[b,a,ty]]; 2D transfer error |
| **OpenCV HomographyBasedEstimator** | Algebraic focal estimation | `focalsFromHomography()` → median; max spanning tree BFS for initial R |
| **Overmix LinearAligner** | Least-squares linear fit to positions | Fit `pos[i] = a*i + b` independently for x and y; replace positions with fit values; removes wobble |
| **ASP §1.1C+1.17** | 6-DOF LM + GNC-TLS outer loop | params=[a,b,tx,c,d,ty] per frame; Cauchy loss (scipy); GNC outer: 8 Geman-McClure iterations; §1.1B spanning-tree inlier pre-filter; §1.1D adaptive f_scale |

**Analysis**: This is where the systems diverge most fundamentally.

**OpenCV BundleAdjusterRay** models camera rotation on a unit sphere — appropriate for a rotating camera (tourist panorama) but wrong for a translating camera (scroll capture). The rotation model accumulates spherical errors that map to pixel-space affine errors in the warping stage.

**OpenCV BundleAdjusterAffinePartial** is the right model for scroll capture (it solves for the 4-param similarity a,b,tx,ty that is the OpenCV SCANS mode BA). It correctly captures scale and in-plane rotation without modelling camera rotation in 3D space.

**ASP's BA** solves a full 6-DOF affine per frame (all 6 parameters of the 2×3 affine matrix) using scipy `least_squares` with Cauchy loss. This is more general than the 4-param similarity (it allows shear) but uses a per-edge cost function based on translation components (`e["M"][:2,2]`). The GNC-TLS outer loop (Geman-McClure weights, §1.17) is a significant robustness improvement over both OpenCV and Overmix: edges with large residuals are down-weighted each iteration, effectively approximating truncated-least-squares.

**Overmix LinearAligner** is the simplest: just fit a line to position vs. index. This assumes the scroll is uniform (constant speed), which is often true for manga scan captures but not for gameplay recordings with variable scroll speed.

The **spanning-tree inlier filter (§1.1B)** in ASP is conceptually similar to OpenCV's max-spanning-tree BFS for initialising rotation, but ASP uses it for *pre-filtering* (removing edges whose observed displacement disagrees with the spanning-tree prediction by >50px) while OpenCV uses it for *initialisation* (setting the initial rotation from the tree traversal).

**Wave correction** (`waveCorrect()` in OpenCV) removes accumulated linear rotation drift from the solved rotation matrices by projecting them onto the space of wave-corrected rotations. ASP's §4.3 wave correction is the translation-domain analogue: subtract a linear fit to the tx/ty sequence to remove drift.

### 3.6 Canvas Construction & Warping

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV** | `RotationWarper` derivatives (Spherical, Affine, Cylindrical) | `warp(img, K, R, INTER_LINEAR, BORDER_REFLECT)` at compose scale; `warper->buildMaps()` pre-computes remap tables |
| **Overmix** | `SumPlane` — accumulate weighted pixel sums | Canvas grows dynamically (`resizeToFit()`); sub-pixel positioning via scan-line pointer arithmetic; optional rotation via `Transformations::rotation()` |
| **ASP** | `cv2.warpAffine` with affine matrices from BA | `_compute_canvas()`: compute bounding box from all affine-transformed corners; allocate canvas; warp each frame into it; TELEA fill gaps (§1.7B) |

**Analysis**: OpenCV's warping is the most sophisticated — different warpers implement different camera projections (spherical, cylindrical, transverse mercator, stereographic, etc.) each with proper map construction. The remap tables (`buildMaps`) are pre-computed for efficiency.

Overmix's `SumPlane` is unique in that it handles sub-pixel offsets natively via floating-point scan-line indexing. There is no explicit warp — pixel positions are fractional and the accumulator does bilinear interpolation implicitly.

ASP uses integer-affine warps (`cv2.warpAffine`) which is appropriate for the affine model. The canvas is constructed geometrically from BA affines without explicit projection correction. This is correct for the flat-scan assumption (no lens distortion, no spherical projection needed).

The `_detect_scroll_axis()` (§3.14) function in ASP is a quality gate specific to the scroll assumption — if the scroll axis is horizontal rather than vertical, it falls back to SCANS. OpenCV has no such scroll-axis assumption.

### 3.7 Seam Finding

This is the most important stage for output quality and where the three systems differ most dramatically.

| System | Approach | Dimensionality | Cost Function |
|--------|----------|----------------|---------------|
| **OpenCV VoronoiSeamFinder** | Distance transform, per-pixel nearest image | 2D per image | `dist1 < dist2` — no energy minimisation |
| **OpenCV DpSeamFinder** | DP on connected components | 2D, component-local | `COLOR`: L2 colour diff; `COLOR_GRAD`: L2/(gradient magnitude) |
| **OpenCV GraphCutSeamFinder** | Global min-cut (s-t graph cut) per pair | 2D full overlap ROI | `COST_COLOR_GRAD`: `(||img1−img2||₂ + ||img1+−img2+||₂) / (dx1+dx1++dx2+dx2++ε) + ε` |
| **Overmix** | No seam — pixel averaging | N/A | All frames contribute; seam is everywhere |
| **ASP** | 1-D DP seam (monotone left→right scan) | 1D (rows = seam y at each column x) | `diff + 0.5*|grad(diff)| + edge_weight*(|∇img1|+|∇img2|) + sem_weight*sem_cost + transition_pen` |

**GraphCut deep-dive**: OpenCV's `GraphCutSeamFinder` is a 2D global optimisation over the overlap ROI. Each pixel is a graph node with edges to its 4-neighbours. Terminal weights: if pixel (y,x) is in image 1's valid region, it gets a terminal weight `terminal_cost_=10000` toward the source (image 1); if in image 2's region, toward the sink (image 2). N-link weight is `(||c1-c2|| + ||c1+-c2+||) / (dx1+dx1++dx2+dx2++eps) + eps` — colour similarity normalised by gradient magnitude. High-gradient pixels are *cheap* to cut through (the denominator is large), so the seam prefers to run through high-gradient (textured) regions where a colour step would be hidden by existing edge information.

The `bad_region_penalty_=1000` is added to N-link weights where either image has a mask pixel equal to 0 (outside the valid region) — this ensures the seam avoids masked-out regions.

This approach has three critical advantages over ASP's 1D DP:
1. **2D routing**: the seam can move in any direction (up, down, left, right) — it can double back to avoid an obstacle. ASP's monotone left→right scan cannot double back.
2. **Gradient normalisation**: dividing by gradient magnitude means the seam naturally prefers textured regions (high gradient = cheap cut). ASP adds `edge_weight*(|∇img1|+|∇img2|)` which *penalises* high-gradient regions (wants to avoid edges), which is the opposite semantic for natural images but correct for anime where edges mark character outlines.
3. **Global optimisation**: the s-t max-flow ensures the minimum-energy seam globally. ASP's DP is optimal left-to-right but cannot look ahead.

**ASP seam cost map** (`_build_seam_cost_map`): the fg-interior cost (1.0 × 200 = 200 energy units vs. ~10-50 for background) is the ASP analogue of OpenCV's `bad_region_penalty_`. The column-barrier (§3.15A, 2.0 × 200 = 400 energy) is stronger. The tiered structure (0.5 for edge buffer, 1.0 for interior) creates a spatial gradient that the 1D DP can follow.

**Key insight**: ASP's 1D DP is fundamentally limited for this problem. The seam at each boundary is a function of a single variable (y-offset at each column x), but the true minimum-energy seam for a 2D overlap region may require the seam to route around a character limb that extends across multiple columns. OpenCV's graph-cut can do this; ASP's DP cannot.

### 3.8 Exposure Compensation

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV GainCompensator** | Global scalar gain per image | Symmetric linear system; Cholesky solve; alpha=0.01, beta=100 |
| **OpenCV BlocksGainCompensator** | 32×32 block gain per image | Run GainCompensator on all blocks jointly; smooth with separable [0.25,0.5,0.25] kernel × nr_gain_filtering_iterations times; resize gain_map with INTER_LINEAR at apply time |
| **OpenCV BlocksChannelsCompensator** | Per-channel per-block gains | 3 independent GainCompensators (B,G,R) |
| **Overmix** | None | Alpha compositing compensates naturally for partial coverage |
| **ASP Stage 4.5** | Per-frame scalar + per-segment gain | See §3.2 above; applied before matching |
| **ASP §1.4D** | Gaussian-blur per-pixel gain field | `MULTISCALE_GAIN=1`: blur-derived spatially-varying gain |
| **ASP §1.4E** | CDF histogram matching | 256-entry LUT per channel; `HISTOGRAM_MATCH=1` |

**Analysis**: OpenCV's `BlocksGainCompensator` with 32×32 blocks is the gold standard for photometric correction in panoramas. The iterative Gaussian smoothing is key — it prevents discontinuous block boundaries while allowing spatially-varying gain. The joint linear system couples all block gains across all images, ensuring global consistency.

ASP's §1.4D multi-scale gain is the closest equivalent, but it uses a Gaussian-blur-derived field (spatially smooth by construction) rather than a block grid (which allows sharp spatial gain changes within the smoothing kernel radius). The Gaussian field in §1.4D is less expressive than the block grid + smoothing combination.

The `strip_banding_score` being 25 luma units worse in ASP than simple_stitch (where simple_stitch uses OpenCV's BlocksGainCompensator) is largely explained by this gap: ASP's pre-matching scalar gain cannot fix spatially-varying illumination that varies within a frame.

### 3.9 Blending

| System | Approach | Key Detail |
|--------|----------|------------|
| **OpenCV FeatherBlender** | Distance-transform weight ramp | `createWeightMap()`: distanceTransform + 1/(sharpness × dist) clip; linear blend in seam region |
| **OpenCV MultiBandBlender** | Laplacian pyramid | `createLaplacePyr()`: `pyr[i] = pyr[i] − pyrUp(pyr[i+1])`, base = pyrDown; Gaussian pyramid for weights; accumulate `dst += lap × gauss_weight`; restore with `restoreImageFromLaplacePyr()`; CUDA / OpenCL paths |
| **Overmix AverageRender** | Pixel-wise weighted average | `sum += pixel × alpha; count += alpha`; final = sum/count; Mitchell-filter rescaling; no seam blend at all |
| **Overmix StatisticsRender** | Median / min / max / difference | `median_pixel()` nth_element; used for noise reduction and error visualisation |
| **ASP _laplacian_blend** | Laplacian pyramid on DP seam path | N bands (LAPLACIAN_BANDS constant); applies at the DP-computed seam path; Gaussian weight pyramid for smooth transition |
| **ASP §1.6C Poisson blend** | cv2.seamlessClone NORMAL_CLONE | ±20px band around seam path; fallback to hard-partition on cv2.error |

**Analysis**: ASP's Laplacian blend and OpenCV's MultiBandBlender use the same underlying algorithm but differ in how the weight maps are constructed. OpenCV's weight map is a distance-transform ramp from the seam (widest at the seam, tapering to 0 at image edges) — it's a 2D smooth blend across the entire image. ASP's Laplacian blend is localised to the DP seam path and uses the `feather` width as the blend radius.

OpenCV's MultiBandBlender accumulates *all* images simultaneously into a pyramid, then reconstructs. ASP applies the blend pairwise (adjacent strips one at a time). The simultaneous accumulation in OpenCV allows the pyramid to smooth out gradients from multiple overlapping images at once, which is better for heavily overlapping panoramas.

The Poisson seam blend (§1.6C) is the most novel ASP contribution: `cv2.seamlessClone(NORMAL_CLONE)` solves `‖∇out − ∇fb‖²` with Dirichlet boundary conditions, producing a zero-brightness-step seam. OpenCV uses Laplacian pyramids to achieve the same effect implicitly (each pyramid level redistributes energy smoothly). For sharp colour steps the Poisson approach is mathematically superior.

Overmix's pixel averaging is appropriate for its domain (multiple captures of the same scene) but produces ghosting when applied to images with any spatial offset error — even a 1-pixel error creates a blurred double-image.

### 3.10 Post-processing & Quality Control

| System | Approach |
|--------|----------|
| **OpenCV** | Wave correction (R matrices); crop to inner/outer ROI |
| **Overmix** | LinearAligner drift removal; `StatisticsRender` error visualisation |
| **ASP** | 30+ quality gates (§1.x–§4.x) before/during/after each stage; SCANS/PANORAMA fallback chain; RLHF reward model (§1.10A); seam luma/chroma equalisation (§1.21/§1.56); content-aware crop; TELEA inpainting |

**Analysis**: ASP's quality gate system is unique — no comparable automatic fallback infrastructure exists in OpenCV or Overmix. This reflects the harder problem: anime scroll stitching has many more failure modes (hold blocks, horizontal scroll, static input, fg-dominated scenes, degenerate BA, etc.) that must be detected and handled gracefully.

OpenCV assumes the user has pre-screened the input; it will produce output even from pathological inputs (though the output may be garbage). ASP's gate system means it falls back to progressively simpler methods rather than producing visually wrong output.

---

## 4. Domain Specialisation Matrix

| Capability | OpenCV PANORAMA | OpenCV SCANS | Overmix | ASP |
|-----------|-----------------|--------------|---------|-----|
| **Target domain** | Rotating camera, natural photos | Translating scanner/camera | Super-res, animated frames | Anime vertical scroll |
| **Texture requirement** | High (SIFT needs corners) | High (SIFT) | None (pixel diff) | Low (LoFTR + phase corr) |
| **Handles fg characters** | No (no fg/bg sep) | No | No | Yes (BiRefNet + ARAP) |
| **Handles variable scroll speed** | N/A | Partial | No (linear fit) | Yes (BA + validation) |
| **Hold block detection** | No | No | No | Yes (§1.125, dHash §S43) |
| **Sub-pixel alignment** | No (integer warp) | No | Yes (SumPlane) | Yes (ECC §8, SEA-RAFT §8) |
| **2D seam routing** | Yes (GraphCut) | Yes (GraphCut) | N/A | No (1D DP) |
| **Spatially-varying exposure** | Yes (32×32 blocks) | No (NoExposureComp in SCANS) | N/A | Partial (§1.4D opt-in) |
| **Camera rotation model** | Yes (spherical) | No (similarity) | No | No (affine) |
| **Lens distortion** | Yes (warpers) | No | No | No |
| **Temporal rendering** | No | No | Yes (avg/median pixel) | Yes (median render §10) |
| **GPU acceleration** | Yes (CUDA, OpenCL) | Yes | Partial (QtConcurrent) | No |
| **Fallback strategy** | None | None | None | Yes (Retry 0-5 + SCANS + PANORAMA) |

---

## 5. Algorithmic Gap Analysis (OpenCV vs ASP)

The benchmark showed: simple_better=46, comparable=41, asp_better=9 across 97 tests. The primary failure categories and their OpenCV vs. ASP root causes:

### Gap 1: Seam Finder — 1D DP vs 2D Graph Cut

**OpenCV**: `GraphCutSeamFinder` — 2D energy minimisation, gradient-normalised cost, bidirectional routing.

**ASP**: `_seam_cut()` — monotone left→right 1D DP, gradient-penalising cost (not normalising), semantic cost map.

**Consequence**: When a character limb extends across multiple columns, ASP's DP cannot route around it (it would need to reverse direction), so it either bisects the limb (ghosting) or routes through a suboptimal path. OpenCV's graph-cut routes freely.

**Cost function semantic inversion**: OpenCV's `COST_COLOR_GRAD` divides colour difference by gradient magnitude — *cheap* to cut through high-gradient regions. ASP *adds* gradient-derived penalty (`edge_weight * (|∇img1| + |∇img2|)`) — *expensive* to cut through high-gradient regions. OpenCV's semantic is: "cut through an edge in the image because an edge there will hide the seam." ASP's semantic is: "avoid cutting through character outlines." Both are correct for their domains (natural images vs. anime fg avoidance), but the opposite choices make ASP semantically different.

**Mitigation already in ASP**: The semantic cost map (`_build_seam_cost_map`) achieves the fg-avoidance goal more cleanly than the energy term. §3.15A column barrier (cost=2.0) and §1.65 fg erosion push the seam toward background corridors.

**Recommended roadmap**: Implement a **2D graph-cut seam finder** for the overlap zone between adjacent strips, using `GCGraph`-style s-t max-flow. The fg semantic cost map can be incorporated as terminal weights (fg pixels → high source weight = "belongs to strip A", bg pixels → low terminal weight = "can be cut here"). This replaces the 1D DP entirely and should directly address the ghosting_score and seam_visibility failures.

### Gap 2: BlocksGainCompensator — Global vs. Scalar

**OpenCV**: 32×32 block gain per image, joint linear system, iterative Gaussian smoothing, INTER_LINEAR resize at apply time.

**ASP Stage 4.5**: Per-frame scalar or per-segment k-means scalar. §1.4D Gaussian-blur field (opt-in).

**Consequence**: ASP cannot correct spatially-varying exposure within a single frame. The `strip_banding_score` being 25 luma units worse reflects this.

**Mitigation already in ASP**: S160 implemented `_blocks_gain_compensate()` and `_blocks_lum_compensate()` (§4.1/§4.4). If these match OpenCV's block-level approach, they should close most of this gap.

**Recommended roadmap**: Wire `_blocks_gain_compensate()` as the default post-matching normalisation (replacing or supplementing Stage 4.5's scalar). Tune block size and smoothing iterations to match OpenCV's `BlocksGainCompensator` parameterisation.

### Gap 3: MultiBandBlender — Simultaneous vs. Pairwise

**OpenCV**: `MultiBandBlender::feed()` accumulates ALL images simultaneously into the Laplacian pyramid. The final blend takes all contributing images' weighted contributions at each pyramid level.

**ASP**: `_laplacian_blend()` applies the pyramid blend pairwise (strip i vs. strip i+1), then composites the result into the canvas.

**Consequence**: In regions where three or more strips overlap, OpenCV's simultaneous accumulation produces a smooth transition across all three. ASP's pairwise approach applies the blend from the left, then the blend from the right, with the results composited. The transition quality degrades when the pairwise blends interact.

**Recommended roadmap**: Implement multi-strip Laplacian blend that feeds all overlapping strips simultaneously for each seam zone. This is complex but directly mirrors OpenCV's approach.

### Gap 4: Bundle Adjustment — 2D Affine vs. Similarity (4-DOF)

**OpenCV SCANS**: `BundleAdjusterAffinePartial` — 4-DOF similarity `[[a,-b,tx],[b,a,ty]]`. This is the minimal parameterisation for scroll capture (translation + uniform scale + rotation).

**ASP**: 6-DOF full affine `[[a,b,tx],[c,d,ty]]` with shear. More parameters → more degrees of freedom → potentially overfitting to noisy phase-correlation measurements.

**Consequence**: For clean scroll sequences (pure translation), the extra shear DOF in ASP's BA introduces unnecessary noise. For some failure cases (affine shear from perspective tilt in hand-held capture), the extra DOF is beneficial.

**Recommended roadmap**: Add `ASP_SIMILARITY_MODE` to the BA (already exists in matching.py §1.3E for per-pair affines — extend to BA solver). When enabled, constrain `c = -b`, `d = a` in the LM residual function.

### Gap 5: Feature Matching — No Explicit RANSAC in PC Path

**OpenCV**: Every pairwise match goes through `findHomography(RANSAC)` — geometric verification removes spurious matches.

**ASP**: Phase correlation produces a single peak (no RANSAC needed — it's a correlation integral). LoFTR matches use spread filter (§1.36) and bg-ratio filter (§1.38) as proxies for RANSAC.

**Consequence**: LoFTR matches on anime may be dominated by texture-confused fg keypoints (the same character appears in both frames in different positions but gets matched to background). ASP's §1.38 bg-ratio filter mitigates this.

**Recommended roadmap**: Add RANSAC geometric verification to LoFTR matches using `cv2.estimateAffine2D(RANSAC)`, similar to `AffineBestOf2NearestMatcher`. This filters LoFTR matches that don't agree on a consistent affine transformation.

---

## 6. Overmix vs. ASP Gap Analysis

### Gap O1: Super-resolution via Averaging

Overmix's key advantage over both OpenCV and ASP is pixel averaging across many aligned frames, which achieves sub-pixel resolution reconstruction. `AverageRender::render()` accumulates `sum += pixel × alpha` and `count += alpha` then divides, effectively computing a weighted mean over many noisy observations of each pixel. The Mitchell-filter rescaling then produces the final image at arbitrary output resolution.

ASP's temporal median render (`_render_median`) is different: it takes the *median* across frames per-pixel to remove the animated foreground character (who appears at different positions in different frames). The median is more robust to outliers (the character appears in at most ~30% of frames for any given canvas row) but does not provide sub-pixel resolution.

**Implication for ASP**: For background-only regions (where the character never appears), ASP could use pixel averaging (like Overmix's `AverageRender`) instead of the median for better background quality. The RLHF reward model could distinguish bg-vs-fg regions and apply averaging selectively.

### Gap O2: No Seam = No Seam Artifact

Overmix has zero seam artifacts because there is no seam — all frames are averaged. ASP's seam artifacts (ghosting, visibility steps, banding) are fundamental to the pairwise-compositing approach. The only way to eliminate them entirely is to switch to pixel averaging for bg regions, which requires reliable fg masking.

### Gap O3: Multi-Frame Multi-Resolution

Overmix explicitly handles multi-resolution / multi-frame super-resolution via the Gaussian/Laplacian-scale spacing parameters in `SumPlane` (`spacing.x`, `spacing.y`, `offset.x`, `offset.y`). ASP has `mfsr_mode` (§mfsr) but it is a separate post-processing step, not integrated into the core compositing.

### Gap O4: Rotation & Zoom Handling

Overmix's `AverageRender` explicitly handles per-image rotation and zoom via `Transformations::rotation()` — each `ImageItem` stores `rotation()` and `zoom()` values. ASP's affine model captures rotation and scale in the 2×2 block but does not explicitly decouple them; the `_SIMILARITY_MODE` (§1.3E) does this per-pair but not through the full BA.

---

## 7. Strength / Weakness Summary Table

### OpenCV Stitcher
| Strength | Weakness |
|----------|----------|
| 2D graph-cut seam finding (best quality for natural images) | Requires rich texture for feature matching |
| BlocksGainCompensator (spatially-varying exposure) | SCANS mode uses NoExposureCompensator |
| MultiBandBlender (simultaneous multi-image pyramid) | No fg/bg separation — seam bisects any content |
| waveCorrect() for rotation drift | No fallback strategy (garbage output on failure) |
| GPU acceleration (CUDA/OpenCL) | Complex API; hard to integrate domain constraints |
| Full warper library (spherical, cylindrical, etc.) | Wrong model for pure-translation scroll capture |

### Overmix
| Strength | Weakness |
|----------|----------|
| No seam = no seam artifacts | Only works when all frames show the same scene content |
| Sub-pixel super-resolution via averaging | Cannot handle animated fg (average produces ghosting) |
| Alpha compositing (transparency-aware) | No global pose estimation (pairwise only) |
| GradientComparator hierarchical search (no texture needed) | Brute-force — O(N²) in motion range; slow for large displacements |
| Qt parallel evaluation (QtConcurrent) | No exposure compensation |

### ASP
| Strength | Weakness |
|----------|----------|
| BiRefNet fg/bg separation — seam routes in bg | 1D DP seam cannot route around 2D obstacles |
| ARAP foreground registration at seam boundaries | ARAP is slow and complex; fails when fg is in extreme poses |
| GNC-TLS outer loop — robust to outlier edges | 6-DOF affine over-parameterised for translation-only scroll |
| 30+ quality gates + multi-level fallback chain | Many gates default OFF; must be tuned per-dataset |
| EfficientLoFTR / ALIKED dense matching | No RANSAC geometric verification on LoFTR matches |
| Seam path cache (§1.5D) — efficient RLHF loop | No 2D seam routing |
| Adaptive feathering by photometric similarity | Scalar exposure compensation only (block version opt-in) |
| Domain-specific: anime cel shading = flat bg | Over-engineered for simple cases (lots of flags defaulting OFF) |

---

## 8. Implementation Roadmap Candidates

These are concrete algorithmic improvements for the ASP, ranked by expected impact and implementation complexity.

### Priority 1 — 2D Graph-Cut Seam Finder

**Expected impact**: Eliminates ghosting_score and seam_visibility failures (93.8% and 88.5% of tests worse than simple_stitch).

**Implementation sketch**:
```python
# backend/src/animation/rendering/seam_graphcut.py
import cv2
import numpy as np
from typing import Optional

def graphcut_seam(
    zone_a: np.ndarray,          # (H, W, 3) uint8
    zone_b: np.ndarray,          # (H, W, 3) uint8
    bg_mask_a: Optional[np.ndarray],   # (H, W) uint8 bg=255
    bg_mask_b: Optional[np.ndarray],
    terminal_cost: float = 10000.0,
    bad_region_penalty: float = 1000.0,
) -> np.ndarray:
    """
    s-t graph-cut seam: returns (H, W) uint8 ownership mask
    where 0 = take from zone_a, 255 = take from zone_b.
    
    Implementation:
    1. Build GCGraph<float>: N = H*W nodes + source/sink
    2. For each pixel (y,x):
       - terminal: source weight = (bg_mask_a > 127)*terminal_cost
                   sink weight   = (bg_mask_b > 127)*terminal_cost
    3. For each horizontal edge (y,x)-(y,x+1):
       - color_diff = ||zone_a[y,x]-zone_b[y,x]|| + ||zone_a[y,x+1]-zone_b[y,x+1]||
       - grad = |dx_a[y,x]| + |dx_a[y,x+1]| + |dx_b[y,x]| + |dx_b[y,x+1]| + eps
       - weight = color_diff / grad + eps
    4. Add bad_region_penalty to edges adjacent to bg=0 pixels
    5. maxFlow() → min-cut → ownership mask
    """
    # cv2 does not expose GCGraph; use PyMaxflow (pip install PyMaxflow)
    # or implement via cv2.grabCut infrastructure or networkx/scipy.sparse
    ...
```

Since `cv2.GCGraph` is not exposed in Python, this requires either PyMaxflow library, or implementing the s-t max-flow using `scipy.sparse` + a push-relabel algorithm. Alternatively, `cv2.grabCut` uses the same GCGraph internally and could be adapted.

### Priority 2 — RANSAC Geometric Verification on LoFTR Matches

**Expected impact**: Reduces BA outlier edges; improves §1.1B spanning tree quality; addresses Category B failures (single corrupt edge dominates BA).

**Implementation**: After `_match_pair()` returns LoFTR correspondences, run `cv2.estimateAffine2D(src_pts, dst_pts, method=cv2.RANSAC, ransacReprojThreshold=20.0)` and keep only inlier correspondences. Recompute median displacement from inliers only. This is already partially handled by §1.36 (spread filter) and §1.38 (bg-ratio filter) but RANSAC provides full geometric verification.

### Priority 3 — BlocksGainCompensator as Default

**Expected impact**: Reduces strip_banding_score (97.9% of tests worse). The `_blocks_gain_compensate()` function (§4.1/§4.4, S160) should be wired as the default Stage 4.5 normalisation, replacing or supplementing the scalar gain.

**Implementation**: Already implemented in S160. Ensure it runs by default (not behind a flag) and tune block_size (32) and smoothing iterations to match OpenCV's parameterisation.

### Priority 4 — 4-DOF Similarity Constraint in BA

**Expected impact**: Reduces BA drift for clean pure-translation scroll sequences. The extra shear DOF in ASP's 6-DOF affine adds noise for scroll-capture inputs.

**Implementation**: Add `_similarity_mode` flag to `_bundle_adjust_affine()`. When enabled, constrain residual computation to 4-DOF: `a_sym = (params[0]+params[3])/2`, `b_sym = (params[1]-params[2])/2`, matrix = `[[a_sym,-b_sym,params[4]],[b_sym,a_sym,params[5]]]`.

### Priority 5 — Background Pixel Averaging (MFSR for bg regions)

**Expected impact**: Improves background quality in regions where the fg character never appears (noise reduction via averaging, as in Overmix).

**Implementation**: After Stage 10 temporal median render, identify canvas pixels covered by ≥3 frames where `bg_mask=255` in all contributing frames. Replace those pixels with the per-pixel mean across frames (not median). This is Overmix's `AverageRender` applied selectively to bg-only regions.

### Priority 6 — waveCorrect() for ty Sequence

**OpenCV's** `waveCorrect()` applies a rotation-matrix projection. The ASP §4.3 wave correction subtracts a linear fit from the tx/ty sequences. This is correct for translation; the improvement would be to use OpenCV's actual `waveCorrect` for rotation components if the similarity-mode BA is used.

### Priority 7 — cv2.Stitcher as Fallback Before SCANS

Already implemented (§1.3B `_panorama_stitch_fallback`, S31). Ensure this is always tried before `_scan_stitch_fallback` in the fallback chain. The PANORAMA mode of cv2.Stitcher uses GraphCutSeamFinder and MultiBandBlender automatically.

---

## Appendix: Key Implementation Reference

### OpenCV Files
- `opencv/modules/stitching/src/stitcher.cpp` — pipeline orchestration
- `opencv/modules/stitching/src/seam_finders.cpp` — `GraphCutSeamFinder::Impl::findInPair()` (lines ~350-440)
- `opencv/modules/stitching/src/blenders.cpp` — `MultiBandBlender::feed()`, `blend()`
- `opencv/modules/stitching/src/exposure_compensate.cpp` — `BlocksCompensator::feedWithStrategy()`
- `opencv/modules/stitching/src/motion_estimators.cpp` — `BundleAdjusterRay`, `BundleAdjusterAffinePartial`, `waveCorrect()`
- `opencv/modules/stitching/src/matchers.cpp` — `CpuMatcher::match()`, `BestOf2NearestMatcher::match()`

### Overmix Files
- `Overmix/src/aligners/RecursiveAligner.cpp` — divide-and-conquer alignment
- `Overmix/src/aligners/LinearAligner.cpp` — drift removal
- `Overmix/src/aligners/AnimationSeparator.cpp` — temporal clustering
- `Overmix/src/comparators/GradientPlane.cpp` — `findMinimum()` hierarchical search
- `Overmix/src/comparators/MultiScaleComparator.cpp` — recursive 2× pyramid
- `Overmix/src/comparators/BruteForceComparator.cpp` — exhaustive grid
- `Overmix/src/renders/AverageRender.cpp` — `SumPlane::addAlphaPlane()`, `average()`
- `Overmix/src/planes/basic/difference.cpp` — `Difference::simpleAlpha()`
- `Overmix/src/containers/ImageContainer.cpp` — offset cache management

### ASP Files
- `backend/src/animation/core/pipeline.py` — 13+ stage orchestration (run() from line ~2797)
- `backend/src/animation/rendering/compositing.py` — `_seam_cut()`, `_build_seam_cost_map()`, `_composite_foreground()`, `_poisson_seam_blend()`
- `backend/src/animation/alignment/bundle_adjust.py` — GNC-TLS BA
- `backend/src/animation/alignment/canvas.py` — `_compute_canvas()`, `_scan_stitch_fallback()`, `_panorama_stitch_fallback()`
- `backend/src/animation/alignment/fg_register.py` — ARAP foreground registration
- `backend/src/animation/alignment/matching.py` — `_pairwise_match()`, `_phase_correlate()`
- `backend/src/animation/ingestion/frame_selection.py` — `smart_select_frames()`
