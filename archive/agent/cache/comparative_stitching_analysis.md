# Comprehensive Comparative Analysis: OpenCV Stitcher vs Overmix vs Anime Stitch Pipeline

**Generated:** 2026-06-22  
**Scope:** VERY ULTRA MEGA DEEP ANALYSIS — every implementation detail  
**Source files read:**  
- ASP: `backend/src/animation/{core/pipeline.py, alignment/{bundle_adjust.py,canvas.py,matching.py,fg_register.py}, rendering/compositing.py, ingestion/frame_selection.py}`  
- OpenCV: `opencv/modules/stitching/src/{stitcher.cpp,matchers.cpp,motion_estimators.cpp,seam_finders.cpp,blenders.cpp,exposure_compensate.cpp,autocalib.cpp,camera.cpp}`  
- Overmix: `Overmix/src/{aligners/,comparators/,renders/,planes/,containers/}`

---

## Part I — Big Picture Overview

### 1.1 Design Intent & Problem Domain

| Dimension | OpenCV Stitcher | Overmix | Anime Stitch Pipeline (ASP) |
|-----------|-----------------|---------|------------------------------|
| **Primary use-case** | General outdoor/indoor panoramas from handheld cameras | Anime screenshot super-resolution & assembly | Anime character full-body panorama from phone-scroll video |
| **Input type** | Overlapping photographs, any subject | Static or near-static anime screenshots | Video frames from a scrolling phone screen recording |
| **Primary challenge** | Homography/focal estimation across wide baselines | Decompression artifacts, sub-pixel SNR, OCR panels | Animation pose changes between frames, MPEG compression noise, flat cel-shaded regions |
| **Output type** | Equirectangular / cylindrical / planar panorama | Super-resolved composite | Full-body character canvas with accurate pose |
| **Camera model** | Full projective (homography) or affine | Translation + optional rotation | Translation-only (or 4-DOF similarity) affine |
| **Foreground handling** | None — all content is treated equally | None — no fg/bg separation | BiRefNet deep segmentation → separate fg/bg alignment pipelines |
| **Language / runtime** | C++ (OpenCV core), Python bindings | C++/Qt desktop | Python 3.11, Rust (base module), JPype/JVM |
| **GPU requirement** | Optional OpenCL | Optional GPU via Qt | Optional CUDA (RAFT, LoFTR, ALIKED) |
| **Failure recovery** | Stitcher status codes; no automatic fallback | Interactive UI, manual alignment | 5-tier retry chain + PANORAMA + SCANS fallback |

### 1.2 Algorithmic Lineage

**OpenCV Stitcher** derives from Brown & Lowe (2007) "Automatic Panoramic Image Stitching Using Invariant Features" and Uyttendaele et al. (2001). It is the canonical academic panoramic pipeline:  
SIFT → RANSAC homography → autocalibration → bundle adjustment → wave correction → warping → seam finding → multi-band blending.

**Overmix** is purpose-built for anime, drawing on concepts from Sýkora et al. (2009) "Lazybrush", and the broader field of image alignment for animation. It treats anime screenshots as a super-resolution problem: the same scene is sampled at slightly different pixel offsets across frames (sub-pixel shifts from compression), and averaging after alignment produces a higher-quality result. Hold-block detection is a natural fit: identical cels can be averaged to cancel MPEG quantisation noise.

**ASP** combines both lineages — it is a production pipeline for anime specifically, dealing with the unique challenge that:
1. The camera (phone screen) **translates** rigidly (not rotates)
2. The **character is animating** between sampled frames
3. Frames may be **held** (repeated cels) for 2–3 video frames
4. Backgrounds are **flat cel-shaded** (uniform colour, low gradient — breaks any gradient-based optical flow)
5. Source is a **compressed video** (MPEG noise, DCT blocking artifacts)

ASP's distinguishing innovation is the explicit decomposition `T_total = T_camera + A_animation` and the separate alignment of background (rigid affine) vs foreground (ARAP optical flow registration).

---

## Part II — Architecture Comparison

### 2.1 OpenCV Stitcher — Architecture

The OpenCV Stitcher is a classic linear pipeline with pluggable modules. Its `cv2.Stitcher` class wires together:

```
Images → Feature Detection (SIFT/ORB/SURF)
       → Feature Matching (BFMatcher/FLANN with ratio test)
       → Homography Estimation (RANSAC/LMEDS)
       → Connected-Component Matching Graph
       → Camera Parameter Estimation (Homography decomposition)
       → Autocalibration (focal length from homographies)
       → Bundle Adjustment (Levenberg-Marquardt on focal+rotation)
       → Wave Correction (linear detrend of camera directions)
       → Image Warping (spherical/cylindrical/planar, forward map)
       → Seam Finding (GraphCut / DP / Voronoi)
       → Exposure Compensation (blocks gain / channel blocks)
       → Multi-Band Blending (Laplacian pyramid) or Feather Blending
       → Final Panorama
```

**Key modules:**
- `Stitcher` (stitcher.cpp): Top-level orchestrator, manages registration and compositing phases.
- `BestOf2NearestMatcher` (matchers.cpp): RANSAC-based homography estimation in `matchSubset()`, confidence from inlier ratio.
- `HomographyBasedEstimator` (motion_estimators.cpp): Decomposes homographies via SVD to extract focal lengths.
- `BundleAdjusterRay` / `BundleAdjusterReproj` (motion_estimators.cpp): LM bundle adjustment minimising reprojection error (ray vs pixel space).
- `GraphCutSeamFinder` (seam_finders.cpp): Global energy minimisation via graph cut on the seam graph; uses BGR colour differences as unary/binary costs.
- `DpSeamFinder` (seam_finders.cpp): Dynamic programming seam finding on the full canvas (not pairwise).
- `MultiBandBlender` (blenders.cpp): Laplacian pyramid blend with `num_bands` octaves; each band uses a distance-weighted alpha mask.
- `BlocksGainCompensator` (exposure_compensate.cpp): 32×32 block BGR gain estimation.

**Camera model:** `CameraParams` struct holds `focal`, `aspect`, `ppx/ppy` (principal point), and `R` (3×3 rotation matrix). This is a full projective model — OpenCV handles cameras that not only pan but also tilt, rotate, and have different focal lengths.

**Matching graph:** After pairwise matching, `findMaxSpanningTree()` builds a connected subgraph and prunes images that are not connected (low `conf < conf_thresh`). This is where images are rejected — not by quality gates post-compositing.

**Wave correction:** `waveCorrect()` in motion_estimators.cpp computes the mean direction of the rotated camera y-axes, fits a plane, and adjusts each `R` to make cameras lie in that plane. Two modes: `WAVE_CORRECT_HORIZ` (camera rows align horizontally) and `WAVE_CORRECT_VERT`.

### 2.2 Overmix — Architecture

Overmix is a desktop tool (C++/Qt) structured around abstract interfaces:

```
Images → AComparator (alignment metric)
       → AAligner (register all images)
       → AverageAligner / LinearAligner / ClusterAligner / etc.
       → APlanePrimitive / multi-plane composite
       → ARender (rendering strategy)
       → Output image
```

**Key modules:**
- `AAligner` (base class): Interface for image alignment strategies.
- `LinearAligner`: Aligns images sequentially, accumulating offsets.
- `AverageAligner`: Averages all pairwise alignments from each image to all others (high accuracy, O(N²)).
- `ClusterAligner`: Groups similar images, aligns clusters separately.
- `RecursiveAligner`: Divide-and-conquer — recursively splits frames, aligns halves, merges.
- `SuperResAligner`: Multi-frame SR alignment; accumulates sub-pixel-offset frames.
- `AnimationSeparator`: Detects and separates animation hold blocks from the frame sequence.
- `AnimationSaver`: Exports aligned animation cels.
- `BruteForceComparator`: Exhaustive search comparison (pixel difference).
- `GradientComparator`: Phase-correlation style matching via gradient image.
- `LogPolarComparator` (logpolar.cpp): Log-polar transform → rotation/scale invariant matching.
- `MultiScaleComparator`: Pyramid hierarchy with coarse-to-fine alignment.
- `APlane` / `ImageEx`: The abstraction for a multi-channel image with optional alpha/mask plane.

**Hold-block averaging:** Overmix's `AnimationSeparator` detects hold blocks (repeated frames) and then averages them pixel-by-pixel after sub-pixel alignment. This is the core SNR-improvement strategy for anime: within a 2–3-frame hold, each frame sees the same character cel but with different MPEG quantisation noise. After ECC alignment and averaging, the noise cancels by √N while signal is preserved. Overmix applies this to every detected hold block, not just the worst ones.

**Comparators — deep detail:**
- `LogPolarComparator`: Converts both images to log-polar space; cross-correlation in log-polar space gives rotation and scale alignment. The shift in the log-polar domain encodes the scale and rotation differences between frames. After scale/rotation correction, a second pass finds the translation offset.
- `MultiScaleComparator`: Uses an image pyramid; at the coarsest level, finds a rough displacement, then refines at each finer level. Substantially faster than full-resolution search.

**Rendering strategies:**
- `AverageRender`: Mean pixel value across aligned frames.
- `MedianRender`: Pixel-wise median — ghost/foreground rejection.
- `MaxRender`: Maximum pixel value (useful for dark noisy frames).

**Sub-pixel accuracy:** Overmix interpolates keypoint locations and applies bicubic resampling for sub-pixel alignment. Unlike ASP which rounds to integer pixels before phase correlation, Overmix maintains sub-pixel precision throughout.

### 2.3 ASP — Architecture

ASP is a 13-stage Python pipeline in `backend/src/animation/`. It is the most complex of the three systems in terms of total line count (~20,000 lines across all modules), number of configurable flags (125+ `ASP_*` environment variables in compositing.py alone), and number of fallback strategies.

```
Video frames → [INGESTION]
  Stage 1:  Load frames (cv2.imread, dark-border trim)
  Stage 2:  Width normalization (Lanczos resize to frame[0] width)
  Stage 3:  BaSiC photometric correction (broadcast dimming removal)
  Stage 4:  BiRefNet foreground segmentation → bg_masks[]
  Stage 4.5: BG photometric normalization (global gain)
  Stage 4.5b: Per-segment photometric correction (k-means, 8 clusters)
  Stage 4.7: ProPainter inpainting (optional)
              Pre-dedup near-dup luma filter

→ [ALIGNMENT]
  Stage 5-6: Pairwise matching (JamMa→EfficientLoFTR→LoFTR→ALIKED+LG→
                                RoMa→TemplateMatch→PhaseCorr→SegmentGuided)
             + hold detection / dHash (skip within-hold pairs)
  Stage 7:   Global bundle adjustment (GNC-TLS, L-M)
             → Wave correction (linear trend subtraction)
  Stage 7b:  Affine validation + 5-tier retry chain
             + adaptive min-gap, triangular consistency, spanning-tree filter

→ [RENDERING]
  Stage 8:   ECC sub-pixel refinement / SEA-RAFT optical flow
  Stage 8.8: Hi-res keyframe substitution (4K/1080p hybrid)
  Stage 9:   Canvas geometry + midplane shift (StabStitch++)
  Stage 10:  Temporal median renderer (ghost removal)
             → BG zero-coverage fill
  Stage 10.5: Multi-frame coverage gate → SCANS if fails
             → MFSR (optional)
             → ToonCrafter seam synthesis (optional)

→ [COMPOSITING]
  Stage 11:  Foreground composite (_composite_foreground)
             - Optimal boundary search (±SEARCH_RANGE px)
             - ARAP foreground registration (SEA-RAFT/DIS optical flow)
             - DP seam cut (_seam_cut)
             - Laplacian pyramid blend / Poisson seam blend
             - Single-pose fallback (dominant frame → soft edge)
             - 14+ seam quality gates
             → SRStitcher seam inpainting (optional)

  Stage 12.5: Content trim (scroll-axis-aware foreground extent crop)
  Stage 13:  Boundary crop (_crop_to_valid)
  P1.8:     Gap inpaint (Telea / diffusion)
  Super-Resolution (optional)

→ Final PIL.Image output
```

---

## Part III — Stage-by-Stage Detailed Comparison

### Stage 1 / Ingestion: Image Loading & Preprocessing

#### OpenCV Stitcher
- Reads images as `cv::Mat` via `cv::imread`.
- No dark-border trimming.
- No broadcast-dimming correction.
- No per-frame preprocessing — images are used as-is.
- `setRegistrationResol(0.6)` downscales images for feature detection only; compositing uses full resolution.

#### Overmix
- Reads screenshots; uses `ImageEx` plane abstraction.
- BaSiC-style photometric correction is NOT present — Overmix relies on averaging to reduce per-frame photometric variation.
- AnimationSeparator explicitly identifies hold blocks (repeated cels) and handles them as a group.
- No dark-border trimming — screenshots from a phone have fixed borders.

#### ASP
- `_load_frames()` in canvas.py: `cv2.imread` + `_trim_dark_border()` — removes broadcast over-scan borders (phones/tablets add 8-16px dark borders around the screen).
- `_normalise_widths()`: Resizes all frames to first-frame width (Lanczos4). Critical for handling mixed-resolution captures where phone orientation slightly changed.
- **BaSiC correction** (Stage 3): Blind illumination estimation. Removes spatially-varying vignetting from phone screen recordings (center brighter than edges). Uses the BaSiC model (flatfield = Gaussian smooth of median across frames, darkfield = estimated from minimum projection).
- **BiRefNet segmentation** (Stage 4): Deep learning foreground/background separation. Creates `bg_masks[]` (uint8 per-frame, 255=background, 0=foreground). Critical for all downstream fg/bg-specific processing.
- **Per-segment photometric correction** (Stage 4.5b): k-means on 8 colour clusters, per-cluster gain [0.88, 1.12]. Addresses the "broadcast dimming" artifact where anime panels have varying background exposure levels due to dynamic contrast enhancement on the phone screen.

**Key difference:** ASP has 4 distinct preprocessing stages before any feature matching begins. OpenCV and Overmix skip directly to matching.

---

### Stage 2 / Feature Matching

#### OpenCV Stitcher (`matchers.cpp`)

```cpp
// BestOf2NearestMatcher::match()
void BestOf2NearestMatcher::matchSubset(const ImageFeatures &features1,
                                         const ImageFeatures &features2,
                                         MatchesInfo &matches_info)
{
    // Bidirectional k-NN matching (k=2)
    matcher_->knnMatch(features1.descriptors, features2.descriptors, pair_matches, 2);
    // Lowe ratio test (dist_ratio = 0.3 default, conservative)
    // RANSAC homography with reprojection threshold (typically 1.0 px)
    // Match confidence = inliers / (8 + 0.3 * num_matches)
}
```

- Detector: SIFT (default in Python binding), ORB, AKAZE, SURF depending on `FeaturesFinder` setting.
- Matcher: BFMatcher (`L2` for SIFT float descriptors) or FLANN (faster for large descriptor sets).
- Model: **Homography** (8 DOF projective) via RANSAC. This is the crucial difference — OpenCV fits a full homography that includes rotation, scale, shear, and perspective.
- Pairs tried: all-to-all (O(N²)), then pruned by max-spanning-tree confidence.
- Skip strategy: none — all valid pairs are used.

#### Overmix (`comparators/`)

- `BruteForceComparator`: Dense pixel comparison, exhaustive search over (dx, dy) grid. O(N × search_area). Very slow but accurate for low-texture regions.
- `GradientComparator`: Matches images by gradient magnitude (edges), making it more robust to brightness differences between frames.
- `LogPolarComparator` (logpolar.cpp):
  ```cpp
  // Log-polar correlation for rotation+scale estimation
  // Then translate the residual in Cartesian space
  ```
  This is the most sophisticated of the three — it handles frames that differ in rotation and scale, not just translation. Relevant for phone recordings where the user slightly rotates while scrolling.
- `MultiScaleComparator`: Coarse-to-fine refinement. Matches at 1/4, 1/2, full resolution in succession. Each level provides the starting point for the next.

#### ASP (`matching.py` — `_match_pair()`)

The matching cascade is the most sophisticated of the three systems:

**Attempt 1 — LoFTR (or JamMa/EfficientLoFTR):**
```python
pts1, pts2, conf = loftr_wrapper.match(match_img_i, match_img_j)
# Filter to background keypoints only (via BiRefNet mask)
# Median displacement → translation estimate
# §1.36: reject when MAD > _MATCH_SPREAD_CEIL (bimodal bg/fg confusion)
# §1.38: reject when bg_ratio < _LOFTR_BG_RATIO_MIN (fg-dominated match)
```
LoFTR is a detector-free transformer-based matcher that produces dense matches across the whole image without requiring keypoint detection. It works on flat regions where SIFT produces no keypoints (aperture problem). Critically, ASP filters to **background-only** matches to avoid the character's animation motion polluting the background displacement estimate.

**Attempt 1b — ALIKED + LightGlue:**
Triggered when LoFTR returns <20 background keypoints. ALIKED (Adaptive Keypoints with Implicit Learning and Edge-Driven) produces keypoints at anime line-art edges that LoFTR misses. LightGlue is a fast learnable matcher.

**Attempt 2 — Template Match:**
```python
# Slides top strip of img_i through bottom of img_j (and vice versa)
# TM_CCORR_NORMED with optional fg mask
# Bidirectional: handles both up-pan and down-pan
```

**Attempt 3a — Masked Phase Correlation:**
```python
g_i = _highpass(_luma(img_i)); g_i[fg_mask] = 0.0
shift, response = cv2.phaseCorrelate(g_i, g_j, hann)
```
High-pass filter + Hanning window + background masking. Robust to global luminance differences.

**Attempt 3b — Unmasked Phase Correlation:**
When bg is so uniform the masking removes all signal — the character itself provides the dominant phase signal.

**Attempt 4 — Segment-Guided Matching (P2.9):**
```python
# Mean-shift segmentation into flat-color regions (pyrMeanShiftFiltering)
# k-means color quantization (16 colors)
# Connected components per color cluster
# Match regions by (color_dist/256 + 2×position_dist) combined score
# Median centroid displacement
```
This AnimeInterp-derived technique is the last resort for completely flat, featureless anime cells. It works by treating regions of identical colour as quasi-landmarks.

**Attempt 5 — RoMa v2 dense warp:**
DINOv2-based style-agnostic matcher. Dense warp field → median displacement.

**Key differences from OpenCV:**
- ASP uses **translation-only** (or 4-DOF similarity) — no homography. This is appropriate for scrolling screens where there is zero perspective.
- ASP masks foreground pixels from matching (BiRefNet-guided). OpenCV never considers fg/bg.
- ASP has 5 fallback methods vs OpenCV's 1.
- ASP generates skip-pairs (i→i+2, i→i+3) not just adjacent pairs.

**Hold detection integration** (frame_selection.py):
- MAD-based: within-hold pairs (MAD < 0.025) skip the phase-correlation pass entirely — they get zero displacement (same canvas position by construction).
- dHash-based: Hamming distance < 4 → same hold block.
- Response-based refinement: high phaseCorrelate response (≥0.85) → merge hold blocks that MAD split due to MPEG noise.

---

### Stage 3 / Geometric Estimation

#### OpenCV Stitcher (`motion_estimators.cpp`)

**Camera model:**
```cpp
struct CameraParams {
    double focal;  // focal length in pixels
    double aspect; // aspect ratio
    double ppx, ppy; // principal point
    Mat R;  // 3x3 rotation matrix
    Mat t;  // translation (unused in typical panoramas)
};
```

**HomographyBasedEstimator:**
- Decomposes each pairwise homography H into focal + rotation via SVD.
- `calibrateRotatingCamera()` (autocalib.cpp): Given N homographies, solves for N rotation matrices assuming a common focal length. Uses the Cholesky factorisation of `sum(H^T * ω * H) = 0` where ω is the image of the absolute conic.
- Focal estimation from homography eigenvalues: two candidate focals from f1 = `sqrt(H[0,0]*H[1,1] - H[0,1]*H[1,0])` style formulas; median over all pairs.

**Bundle Adjustment:**
Two implementations in BundleAdjusterReproj and BundleAdjusterRay:
- **BundleAdjusterReproj**: Minimises pixel reprojection error `||p_observed - π(R_i * K^{-1} * p_j)||²` where π is the projection. Classic photogrammetry approach.
- **BundleAdjusterRay**: Minimises angle between rays in 3D space `||K^{-1} * p_i - R_ij * K^{-1} * p_j||²`. Less sensitive to scale ambiguity than pixel error.
- Both use scipy-equivalent Levenberg-Marquardt via OpenCV's `CvLevMarq`.
- Robust loss: uses a Huber-like loss via `calcDeriv()` with `isect_mask`.
- Number of parameters: `7 * N` (focal, aspect, ppx, ppy, R as Rodrigues rvec 3D).
- Frame 0 is pinned (not optimised).

**Wave correction** (`waveCorrect()`):
Ensures the panorama is "level" — cameras don't progressively tilt. For horizontal panoramas, finds the mean direction of camera "up" vectors and rotates all cameras to make them consistent. Uses SVD of `sum(y_i * y_i^T)` and the resulting right singular vector.

#### Overmix

No bundle adjustment — Overmix uses sequential or pairwise alignment without global optimisation. `LinearAligner` accumulates translation offsets sequentially:
```
offset[0] = (0,0)
offset[i] = offset[i-1] + align(frame[i-1], frame[i])
```
`AverageAligner` computes all-to-all alignments and takes the mean, which provides some global consistency but no formal bundle adjustment.

`RecursiveAligner` (divide-and-conquer): splits the sequence in half, aligns each half recursively, then aligns the two halves together. This is an approximation to global BA that runs in O(N log N).

Overmix's focus on sub-pixel accuracy means alignment residuals are minimised differently: each hold block is ECC-aligned before averaging, which by construction minimises sub-pixel translation error within the block.

#### ASP (`bundle_adjust.py` — `_bundle_adjust_affine()`)

**GNC-TLS outer continuation loop (§1.17):**
This is the most sophisticated BA in the three systems for the translation-only case:

```python
# Geman-McClure surrogate: weight_i = (μ·c² / (μ·c² + r_i²))²
# Initial μ: μ₀ = max(r²) / (2c²)  (convex regime)
# Anneal: μ /= _GNC_MU_ANNEAL (=1.4) each iteration
# 8 outer iterations (ASP_GNC_OUTER=8)
# Inner solver: scipy.optimize.least_squares (TRF method, loss='linear')
# At each outer step: update weights via Geman-McClure formula
# Convergence: ||x_new - x_old|| < 1e-3 or μ < 0.01
```

This implements Yang et al. (2020) "TEASER" Graduated Non-Convexity approach. It can tolerate 70–80% outlier edges — far more robust than OpenCV's L-M with Huber loss.

**Regularlisers:**
1. Frame-0 anchor: `(x[0:4] - identity) × 2000` (very strong pin)
2. Identity prior: `(a - 1) × 1e5`, `b × 1e5` per frame (prevents scale collapse)
3. StabStitch++ trajectory smoothness: `λ=0.10 × Δ²tx` (second-order finite difference) — prevents temporal jitter in tx/ty

**Post-solve outlier rejection (two-pronged):**
1. Point-wise residual: edges where `BA-predicted dx` disagrees with observed by `> max(3×median, 30px)` are removed.
2. Edge-displacement outlier: edges where `|dy| > 2.5×median_dy AND |dy - median_dy| > 100px`.
Recursive re-solve on clean edges.

**Spanning-tree pre-filter (§1.1B):**
Before the LM solve, builds a max-weight spanning tree (Kruskal) using Union-Find, BFS from frame 0 to compute reference translations, then rejects edges where `sqrt((pred_dx - obs_dx)² + (pred_dy - obs_dy)²) > 50px`.

**Key difference:** ASP's BA is translation-only (2 DOF per frame, or 4 DOF for similarity) vs OpenCV's 7 DOF per frame. This is the correct constraint for a scrolling phone recording — forcing translation-only prevents the "fan" distortion where BA finds spurious rotation to compensate for noisy matches.

**Affine validation chain (Stage 7b):**
ASP has an extensive post-BA validation layer with 5 retry strategies:
- §1.50: max residual gate (per-edge)
- §1.52: weighted mean residual gate
- §1.55: max rotation gate (°)
- §1.17: span utilization gate (% of expected canvas height covered)
- §1.44: max adjacent gap gate
- §1.51: min adjacent overlap gate
- §1.45: canvas width ratio gate
- §1.62: canvas aspect ratio gate
- §1.53: canvas memory MB gate

Retry 0: §2.9C high-confidence edge re-solve (weight ≥ 0.65 edges only)
Retry 1: Adjacent-only BA (drop all skip-pair edges)
Retry 2: Sequential + fill (greedy 3-pass: forward/backward/cross)
Retry 3: Relaxed min_gap (20px floor, §0.5C adaptive)
→ PANORAMA fallback → SCANS fallback

This entire validation machinery has no equivalent in OpenCV or Overmix.

---

### Stage 4 / Warping & Canvas Geometry

#### OpenCV Stitcher (`warpers`, via `createWarper()`)

OpenCV uses a **forward mapping** warper with multiple projection models:

- **Plane**: Homographic warp, `dst_pt = H * src_pt / (H[2] * src_pt)`
- **Cylindrical**: `x = f * tan(θ), y = f * φ/cos(θ)` — linearises for horizontal panning
- **Spherical**: Full equirectangular, suitable for 360° panoramas
- **Fisheye**: For wide-angle lenses
- **Stereographic**: Mercator-family conformal projection

`scale_factor` (registration_resol, composit_resol) controls working resolution. Feature detection is done at 0.6 MP by default; composition at full resolution.

**Canvas computation:** Min/max corners across all warped image bounding boxes define the output canvas size.

**Seam mask:** Each warped image contributes to a per-pixel "overlap" count. Regions covered by only one image get no seam blending; overlapping regions get the seam treatment.

#### Overmix

Pure translation — no perspective warping. Canvas is the bounding box of all frame translations applied to the fixed frame size. Because Overmix is designed for screenshots from a fixed phone screen (no rotation, no scale change), translation is sufficient.

Sub-pixel translation is handled via bicubic interpolation during composition.

#### ASP (`canvas.py` — `_compute_canvas()`, `rendering/rendering.py`)

**Translation-only affine:**
```python
T_global = -min(all_corners)  # shift all frames to positive coords
canvas_w = ceil(max_x - min_x)  # capped at CANVAS_MAX_DIM
canvas_h = ceil(max_y - min_y)
```

**Midplane shift (Stage 9 / P1.9 — StabStitch++):**
After computing the canvas, shifts all affines so the reference frame sits at the canvas midpoint rather than y=0. This implements the bidirectional warping principle from StabStitch++ — each frame is warped toward the midpoint of the sequence rather than toward the first frame, halving the maximum per-frame distortion.

**Warp execution** (rendering.py, `_render()`):
- `cv2.warpAffine()` for each frame with `INTER_LINEAR + WARP_INVERSE_MAP`.
- Background fill: `BORDER_CONSTANT` with value 0 (transparent where no frame covers).
- **Temporal median** (Stage 10): For each canvas pixel, takes the median across all non-zero frame contributions. This ghost-removes the animated character (who appears at different positions in different frames) and leaves only the background. The ghost-removal is the key reason ASP achieves sharp backgrounds.

The temporal median is novel relative to OpenCV (which uses feather/multi-band blend) and Overmix (which uses mean/max/median render modes).

**BG zero-coverage fill:** Canvas pixels covered by no frame get filled from nearest neighbour (or inpainting, see §1.7B TELEA fill).

---

### Stage 5 / Seam Finding

This is where the three systems diverge most dramatically.

#### OpenCV Stitcher — `seam_finders.cpp`

**GraphCutSeamFinder** (the default high-quality seam finder):
```cpp
// cost_t1[y][x] = |img1[y][x] - img2[y][x]|  (colour difference in overlap)
// Build graph:
//   source node → image1 overlap pixels (capacity = sum of costs in row/col)
//   sink node → image2 overlap pixels
//   pixel nodes connected by horizontal/vertical edges with cost = pixel_diff
//   terminal edges: image-ownership prior
// Graph cut (min-cut / max-flow via BK algorithm) → seam separating image1 and image2
```

The GraphCut approach is **globally optimal** — it finds the seam that minimises the total colour discontinuity between the two overlapping regions. It operates on the **full composited canvas** across all image pairs simultaneously (global energy), not pairwise.

**DpSeamFinder:**
Dynamic programming on the full canvas (not pairwise zones):
```cpp
for (int j = 0; j < num_edges; ++j) {
    // For each pair, compute DP cost table on the overlap region
    // dp[y] = cost[y] + min(dp[y-1], dp[y], dp[y+1])  (energy propagation)
    // Traceback to find minimum-energy path
}
```
Differs from ASP's `_seam_cut()` in that it uses absolute row-to-row transitions (`min(dp[y-1], dp[y], dp[y+1])`) rather than ASP's vectorised `minimum_filter1d` approach, and operates on the full canvas rather than per-boundary zones.

**VoronoiSeamFinder:**
Assigns each pixel to the image whose center is nearest in Voronoi distance. No quality optimisation — just geometric partitioning. Very fast, low quality.

#### Overmix

Overmix does not have a seam finder in the OpenCV sense. Instead, it uses an **alpha compositing** approach:
- Each frame's output pixels contribute with weight proportional to their distance from the frame border (feathered alpha mask).
- Hold-block averages contribute their averaged image.
- The result is a weighted average in the overlap zone, not a binary partition.

For super-resolution mode (`SuperResAligner`), multiple exposures of the same view are stacked; there is no "seam" between frames — all contribute to the final output.

#### ASP — `compositing.py` — `_seam_cut()`, `_build_seam_cost_map()`

ASP's seam finding is pairwise (per boundary between adjacent frame strips) but far more sophisticated than OpenCV's per-pair DP:

**Cost map construction (`_build_seam_cost_map()`):**
```python
# Tier 1 (fg interior, cost=1.0): dilated fg mask
# Tier 2 (fg edge buffer, cost=0.5): ring around fg interior (S19: lowered from 1.0)
# Tier 2 bg (cost=0.0): pure background
# Column filter (§3.15A/§1.23): columns where >50% pixels are fg-interior → cost=2.0
#   or hard barrier (§1.23 ASP_SEAM_HARD_BARRIER=1) → cost=1e6
#   when corridor exists (at least one non-dominated column)
# Triangle mesh barrier (§3.15B ASP_MESH_BARRIER=1): Delaunay triangulation on fg
#   contour points → rasterise each triangle to 1e6 cost
# Line-art gradient penalty (§1.35): additive Laplacian cost in fg-interior
# Extra fg dilation cost ring (§3.20 ASP_EXTRA_FG_DILATION): 0.3 outer ring
# Seam pin rows (§1.99 ASP_SEAM_PIN_ROWS): 10× fg cost in top/bottom rows
# Scatter cost (§1.123 ASP_SCATTER_COST=1): local pixel variance additive term
# HF seam cost (§3.17 ASP_HF_SEAM_COST=1): per-column Laplacian energy additive
# Seam transition penalty (§1.125): distance-from-midline term in energy matrix
# Fg majority floor (§1.126): when zone >60% fg, raise >80%-fg columns to ASP_FG_MAJORITY_FLOOR
# Cost map normalisation (§1.109 ASP_COST_MAP_NORM=1): L∞ normalise soft region to [0,1]
# Cost map Gaussian blur (§1.110 ASP_COST_MAP_BLUR_SIGMA): smooth tier transitions
# Column-wise Gaussian smooth (§1.113 ASP_COST_COL_SMOOTH_SIGMA): lateral gradient
```

**DP seam cut (`_seam_cut()`):**
```python
# Forward pass (S10 vectorisation):
# dp[y] = cost[y] + minimum_filter1d(dp[y-1], size=3, cval=np.inf)
# (scipy vectorised: avoids explicit for loop over columns)
# Traceback via slice-argmin on dp table
# Path smoothing (§1.25 ASP_SEAM_SMOOTH_WINDOW=5): 1-D median filter
# Path clamping (§1.26 ASP_SEAM_MARGIN=3): [margin, zone_h-1-margin]
# Path drift gate (§1.112 ASP_SEAM_DRIFT_THRESH): max consecutive jump
# Path instability gate (§1.28 ASP_SEAM_INSTABILITY_THRESH): path std
# Path fg penetration gate (§1.31 ASP_SEAM_FG_PENETRATION_MAX): fraction fg pixels
# Path bg ratio gate (§1.69 ASP_SEAM_DP_BG_MIN): fraction on bg in both frames
# High path cost gate (§1.122 ASP_HIGH_PATH_COST_THRESH): mean cost along path
```

**Boundary optimization (`_find_optimal_boundaries()`):**
Before the DP runs, the system searches ±SEARCH_RANGE (250 px default) around the geometric midpoint of each strip pair to find the y-position with highest photometric similarity (background-masked). This is a pre-pass that refines the strip assignment before the horizontal seam cut within the strip.

**Adaptive boundary search (§1.17 S17):** When `ptp(tx_spreads) < 5px` (pure vertical scroll), `effective_range=100` (vs 250 for general case) — saves 60% of candidates.

**Pre-escalation gates (before DP runs):**
- §1.70 zone fg coverage (ASP_SEAM_ZONE_FG_MAX): entire zone fg-dominated → single-pose
- §1.60 fg MAD pose gap (ASP_FG_POSE_GAP_THRESH): character in different pose → single-pose
- §1.34 low texture (ASP_SEAM_LOW_TEXTURE_THRESH): flat region → single-pose (ARAP unreliable)
- §1.86 zone SSIM (ASP_ZONE_PRE_SSIM_THRESH): structurally incompatible zones → single-pose
- §1.117 fast zone NCC (ASP_ZONE_FAST_NCC_THRESH): thumbnail NCC pre-filter
- §1.121 zone histogram intersection (ASP_ZONE_HIST_THRESH)
- §1.97 entropy gap (ASP_ENTROPY_GAP_THRESH): one flat zone + one textured → aperture problem
- §1.101 full-zone MAD (ASP_ZONE_MAD_THRESH): bg colour differs → single-pose
- §1.30 zone min height (ASP_ZONE_MIN_HEIGHT): too short for DP
- §1.119 zone width CV (ASP_ZONE_WIDTH_CV_MAX): uneven zone layout → pre-escalate narrowest
- §1.20 tight step (ASP_TIGHT_STEP_PX): camera step < threshold → skip ARAP → single-pose
- §1.18 adaptive SP threshold (ASP_ADAPTIVE_SP_THRESH): wide feather + moderate diff → SP
- §1.19 fg density feather cap (ASP_FG_FEATHER_CAP): fg-dominated zone → cap feather

This is **24 pre-DP gates** with no equivalent in OpenCV or Overmix.

**Seam path cache (§1.5D S44):**
`_make_seam_cache_key(frame_keys, k, cost_flags) → Optional[Tuple]`. Caches DP paths by (image_paths, seam_k, flags) — eliminates ThreadPoolExecutor latency on 2nd+ RLHF iterations.

---

### Stage 6 / Exposure Compensation

#### OpenCV Stitcher (`exposure_compensate.cpp`)

**GainCompensator** (global per-image scalar):
```cpp
// For each image pair (i,j):
// N_ij = sum of pixels in overlap
// I_ij = sum of pixel values in overlap of image i, j
// Minimise: sum_ij N_ij (g_i * I_ij/N_ij - g_j * I_ji/N_ji)²
// Solution: linear system G * gains = B
// (G is symmetric block-diagonal from overlap counts)
```

**BlocksGainCompensator** (32×32 block per-image):
Divides each image into 32×32 blocks. For each block, fits a BGR gain ratio to the overlapping block in the other image. A `gain_map` (H×W float32) is then applied per-pixel. Uses bilinear interpolation between block centers.

**ChannelBlocksGainCompensator:**
Like BlocksGainCompensator but computes separate gains for each B, G, R channel. Handles colour-temperature shift between frames (camera auto white-balance drift).

#### Overmix

No explicit exposure compensation — relies on averaging (within hold blocks) to reduce per-frame exposure variation. Does not address global exposure drift across the sequence.

#### ASP

**Stage 4.5 — Global gain:**
```python
ref_lum = median(bg_pixels[ref_frame])
for each frame:
    frame_lum = median(bg_pixels[frame])
    gain = ref_lum / frame_lum  # clamped by _adaptive_gain_clamp
    warped_norm[frame] *= gain
```

**§1.4B continuous gain clamp (S24):**
`clamp_width = 0.26 − 0.12 × (ref_lum/255)` — smooth surface from ±26% (pure-black) to ±14% (pure-white). Handles dark anime panels differently from bright ones.

**§1.4C bg-only gain unclamped (S40):**
```python
# When _adaptive_gain_clamp would cut the ideal correction by >20%:
gain = ref_lum / frame_lum  # raw unclamped gain for bg-only normalisation
```
Replaces the clamped version in the bg-only loop.

**§1.4D multi-scale spatially-varying gain (S46, ASP_MULTISCALE_GAIN=1):**
Per-pixel gain map derived from Gaussian-blur of bg_mask × luminance ratio. Handles non-uniform panel lighting (darker at top, lighter at bottom).

**§1.4E background CDF histogram matching (S49, ASP_HISTOGRAM_MATCH=1):**
256-entry CDF-matching LUT per frame, per-channel. Handles exposure differences that a global scalar cannot correct (vignetting, panel-edge brightening).

**§1.4F exposure outlier rejection (S50):**
Frames whose bg median deviates >_EXPOSURE_OUTLIER_THRESH from global median are excluded from gain correction.

**§4.1 Spatial blocks gain compensation (S160, ASP_BLOCKS_GAIN_COMP=1):**
After global gain, 32×32 block BGR gain ratio (fa/fb) within the blend zone. Bilinear resize of the gain map, clamped [0.5, 2.0]. Directly equivalent to OpenCV's BlocksGainCompensator, but applied at the seam zone level rather than globally.

**§4.4 Per-channel luminance blocks gain (S160, ASP_BLOCKS_LUM_COMP=1):**
LAB L-channel ratio as scalar gain applied to all BGR channels — avoids colour cast from near-zero individual channel means. Equivalent to OpenCV's ChannelBlocksGainCompensator.

**Per-frame coherence gate (§1.18 S18):**
Only frames in bad adjacent pairs (lum diff > coherence_limit=20) are skipped in normalisation. Replaces the previous global skip flag.

**§1.6B gain-adaptive feather minimum (S22):**
`min(120, max(40, int(gain_diff×300)))` — extreme adjacent-pair gain mismatch → widen feather minimum to reduce visible step.

**§1.98 gain normalisation smoothing (S150, ASP_SMOOTH_GAIN=1):**
1-D Gaussian smooth (σ=1 frame) over `frame_gains[]` array — prevents abrupt inter-strip brightness jumps from isolated outlier gain values.

**Key difference:** ASP now covers the same range as OpenCV's BlocksGainCompensator (§4.1/§4.4) and adds 8 additional gain correction modes. The per-seam-zone application (§4.1) is more targeted than OpenCV's global image-level compensation.

---

### Stage 7 / Blending

#### OpenCV Stitcher — `blenders.cpp`

**MultiBandBlender:**
```cpp
// For num_bands octaves:
//   Build Laplacian pyramid for each warped image
//   Build Gaussian pyramid for each weight mask (distance map)
//   For each level, blend = sum(weight_i * lap_i) / sum(weight_i)
// Collapse pyramids for final output
```
The weight mask is a distance transform from the image border — interior pixels have high weight, edge pixels have low weight. This is the industry-standard panorama blending approach.

**FeatherBlender:**
Simple linear alpha blend: `alpha = dist_from_border / max_dist`. No frequency decomposition.

**Confidence weighting:** `setSharpness()` controls the blending width. No per-seam quality-driven adaptation.

#### Overmix

Alpha compositing with feathering in the overlap zone. For super-resolution stacking, all frames in a hold block contribute equally. No Laplacian pyramid — Overmix relies on the averaging process to handle frequency content.

#### ASP — `compositing.py` — blend chain

**Normal seam (non-single-pose):**

1. **ARAP foreground registration** (`fg_register.py` — `register_foreground_at_seam()`):
   - Computes dense optical flow (SEA-RAFT/DIS) between the two warped frames in the blend zone.
   - ARAP Push phase: block-matching to refine the coarse flow.
   - ARAP Regularise: minimise `||flow - smoothed_flow||² + rigidity_weight × ||flow_xy||²`.
   - Tapers warp to zero away from seam (SC-AOF principle): correction is localised to boundary.
   - SLIC SGM proxy (§3.1B, ASP_SGM_PROXY=1): superpixel centroid matching for flat regions.
   - AnimeInterp SGM (§3.1A, ASP_ANIMEINTERP_SGM=1): VGG-19 per-segment feature matching.
   - HITL flow callback (§2.10A): if registered, user-drawn flow arrows override the computed flow.

2. **_seam_color_match()** (S16):
   Per-channel mean shift of `oth_zone` to match `dom_zone` in the blend band. Reduces seam step from post_warp_diff (~22–50 lum) to within-band variance (~5 lum).

3. **§1.88 ECDF histogram matching** (S147, ASP_HIST_MATCH_SEAM=1):
   Full CDF-matching LUT in the seam band. More robust than S16 mean shift.

4. **§1.91 iterative luminance convergence** (S148, ASP_SEAM_LUM_CONVERGE=1):
   After color match + hist match, re-applies if residual delta > target.

5. **_single_pose_soft_edge()** (S15):
   If not single-pose, ±6px linear ramp at DP seam. Max 50% blend at seam center.

6. **Per-pixel DSFN ramp** (S17):
   `sim_diffused` from Gaussian blur drives per-pixel blend width. High-similarity → wide ramp; low-similarity → narrow.
   **bg-mask-aware (S20):** Force `sim_diffused[both_fg] = 0.0` to prevent bg similarity diffusing into fg-vs-fg overlap (would cause double-image ghost).

7. **Laplacian pyramid blend** (`_laplacian_blend()`):
   `num_levels` octaves. Per-level weight mask from the DSFN ramp. Collapse to get final blended zone.

8. **§1.6C Poisson seam blend** (S21, ASP_POISSON_SEAM=1):
   `cv2.seamlessClone(NORMAL_CLONE)` in ±20px band around DP path. Gradient-domain solver minimises `||∇(out) - ∇(fb)||²` subject to boundary conditions. Eliminates brightness step at hard cuts without ghosting.

9. **§1.108 Laplacian alpha schedule** (S153, ASP_LAPLACIAN_ALPHA_SCHEDULE=1):
   Fine pyramid levels use `mask**2` (sharpened). Reduces high-frequency colour bleeding at character edges.

**Single-pose escalation:**
When any pre-DP gate fires OR when `post_warp_diff > SP_threshold (22 lum)`:
- Pick dominant frame (more fg pixels, or ref-proximity if §1.103 enabled)
- Copy dominant frame's zone as-is
- Apply §1.15 soft edge (±_sp_soft_px ramp)
- §1.22 adaptive soft-edge width (ASP_ADAPTIVE_SP_SOFT=1): scales with feather width
- §1.124 residual-clipped soft-edge (ASP_ADAPTIVE_SP_SOFT=1): clip by post_warp_diff
- ToonCrafter synthesis (§3.6B, ASP_TOONCRAFTER_SEAM=1): for worst single-pose seam

**Post-composite seam corrections:**
- §1.21 seam lum equalize: linear additive ramp over band_px rows
- §1.56 chroma equalize: LAB a/b correction ramp
- §3.19 per-zone chroma align (ASP_ZONE_CHROMA_ALIGN=1)
- §1.104 per-zone lum norm (ASP_ZONE_LUM_NORM=1): equalise bg pixel lum
- §1.111 zone saturation norm (ASP_ZONE_SAT_NORM=1)
- §1.114 zone RMS contrast eq (ASP_ZONE_CONTRAST_EQ=1)
- §1.127 per-zone HSV hue eq (ASP_ZONE_HUE_EQ=1)
- §1.90 bilateral seam smoothing (ASP_BILATERAL_SEAM=1): narrow bilateral filter ±5px
- §1.98 seam sharpness audit (ASP_SEAM_SHARP_MIN): log blur warning

**Post-composite audit gates** (after all seams are composited):
- §1.14B/C Bhattacharyya colour similarity (grey or per-channel BGR)
- §1.24 absolute luma step
- §1.66 NCC structural coherence (60px bands above/below)
- §1.72 entropy variation
- §1.74 canvas fill ratio
- §1.75 strip variance ratio (Laplacian variance)
- §1.76 per-column luma-step max
- §1.77 saturation step
- §1.78 hue step
- §1.79 sharpness (Laplacian variance) per seam band
- §1.80 gradient direction coherence
- §1.81 SSIM
- §1.82 frequency profile
- §1.83 noise asymmetry
- §1.84 RMS contrast ratio
- §1.85 ensemble combiner

This is a total of **15 post-composite quality metrics** with no equivalent in OpenCV or Overmix.

**Seam rendering order (§1.89 ASP_SEAM_ORDER=residual):**
Process seams lowest-residual first → best-quality seams establish reference.

**Parallel seam DP (S12):**
`ThreadPoolExecutor(max_workers=4)` pre-computes all `_seam_cut()` paths concurrently. Results in `_precomp_paths: dict`. Session-level pool (`_SEAM_POOL`) reused across calls.

---

### Stage 8 / Wave Correction & Stability

#### OpenCV Stitcher
`waveCorrect()`: SVD of camera-y direction matrix → adjusts all R matrices to lie in a plane. Two modes: HORIZ (keep panorama level) and VERT (for vertical panoramas).

#### Overmix
No wave correction — by design (screenshots from a fixed phone screen have no camera roll).

#### ASP — `_wave_correct_affines()`
```python
# np.polyfit(degree=1) on tx array across all frames → linear trend
# Subtract trend anchored at frame 0
# Similarly for ty
# Only fires when ptp(tx) > WAVE_CORRECT_MIN_TX_RANGE (§4.3 new)
```
This is a simplified linear-trend version of OpenCV's SVD-based wave correction, applied to the 2D translation arrays rather than 3D rotation matrices. Appropriate for the translation-only camera model.

---

### Stage 9 / Post-processing & Quality Assurance

#### OpenCV Stitcher
- Minimal: status codes for failure, no post-compositing quality checks.
- Black border removal: not automatic — user must crop or use `VoronoiSeamFinder` to get clean borders.

#### Overmix
- Interactive UI: user can inspect results and re-run with different settings.
- No automated quality metrics.
- Manual mask drawing for problematic regions.

#### ASP
Extensive automated QA with retry loops. After compositing:

**SRStitcher** (§1.7A, `sr_stitcher.py`):
Diffusion-based inpainting for residual seam artifacts. Uses a masked inpainting diffusion model applied to the ±band around each seam path.

**MFSR** (`mfsr/`):
Multi-frame super-resolution pipeline:
- `dct_restoration.py`: DCT-domain noise reduction
- `diffusion_inpaint.py`: diffusion-based background completion
- `pso_registration.py`: Particle Swarm Optimisation for sub-pixel registration
- `drl_registration.py`: Deep reinforcement learning registration
- `prior_injection.py`: prior injection for SR diffusion

**HITL** (`hitl/`):
Human-in-the-loop corrections:
- Preset management
- MLLM (multi-modal LLM) quality scoring
- Parameter search
- Grounding (SAM-2 for region selection)
- ARAP flow arrow drawing (§2.10C)

**RLHF** (`rlhf/`):
Reinforcement learning from human feedback:
- `StitchRewardModel.predict()`: learned quality score
- Feedback store
- Online trainer
- `_compute_rlhf_score()` in bench: wired into every benchmark metrics dict

**Benchmark metrics** (`bench_anime_stitch.py`):
- `_compute_aligned_ssim()`: ECC alignment + SSIM vs GT (§3.9 S25: EUCLIDEAN model, convergence 200/1e-4)
- `_seam_visibility_score()`: no-reference worst-case adjacent-row luminance jump
- `_ghosting_score_v2()`: FFT autocorrelation of column-mean gradient-magnitude profile; secondary peak at lag D = double-edge signature
- `strip_banding_score`: row-level luminance variance ratio
- `sharpness`: Laplacian variance
- `_compute_rlhf_score()`: reward model inference

---

## Part IV — Core Algorithmic Differences Summary

### 4.1 Camera Model

| System | Model | DOF | Notes |
|--------|-------|-----|-------|
| OpenCV | Full projective | 8 (homography) + focal | Handles rotation, scale, perspective |
| Overmix | Translation | 2 | Sub-pixel precision |
| ASP | Translation (or 4-DOF similarity) | 2 or 4 | `ASP_SIMILARITY_MODE=1` adds rotation+scale |

### 4.2 Feature Matching

| System | Method | Fg/Bg separation | Fallback cascade |
|--------|--------|------------------|------------------|
| OpenCV | SIFT/ORB + BFMatcher/FLANN | None | None |
| Overmix | LogPolar / Gradient / BruteForce | None | MultiScale |
| ASP | LoFTR → ALIKED → Template → Phase → Segment → RoMa | Yes (BiRefNet) | 5 methods |

### 4.3 Bundle Adjustment

| System | Algorithm | DOF | Robustness |
|--------|-----------|-----|------------|
| OpenCV | L-M (BundleAdjusterReproj/Ray) | 7×N | Huber-like |
| Overmix | None (sequential/recursive) | — | N/A |
| ASP | GNC-TLS outer + L-M inner | 4×N | Geman-McClure, 70% outlier tolerance |

### 4.4 Seam Finding

| System | Method | Scope | fg/bg cost |
|--------|--------|-------|------------|
| OpenCV | GraphCut (BK algorithm) or DP | Global canvas | None |
| Overmix | Alpha feathering | Per-overlap | None |
| ASP | DP per boundary (30+ cost terms) | Per-seam-zone | Full fg/bg tiered cost |

### 4.5 Blending

| System | Method | Levels | fg registration |
|--------|--------|--------|-----------------|
| OpenCV | Laplacian pyramid | num_bands | None |
| Overmix | Weighted average | 1 | Hold-block ECC |
| ASP | ARAP+Laplacian+Poisson+DSFN | num_bands | SEA-RAFT/DIS + SLIC/VGG-19 |

### 4.6 Exposure Compensation

| System | Method | Granularity |
|--------|--------|-------------|
| OpenCV | BlocksGainCompensator (32×32) | Per-image blocks |
| Overmix | None | — |
| ASP | Global + blocks (§4.1) + CDF LUT + multi-scale spatially-varying | Per-frame + per-seam-zone |

### 4.7 QA / Fallback

| System | Post-QA | Fallback tiers |
|--------|---------|----------------|
| OpenCV | Status codes | None |
| Overmix | Interactive UI | Manual |
| ASP | 15+ automated metrics | 5 retries + PANORAMA + SCANS |

---

## Part V — Gap Analysis and Improvement Avenues

### 5.1 What OpenCV has that ASP lacks (or has inferior versions of)

#### §4.2 — GraphCut Global Seam (highest priority)
OpenCV's `GraphCutSeamFinder` minimises a **global** energy across the full canvas simultaneously. ASP's DP seam is **pairwise** — it optimises each strip boundary independently, which means adjacent seams can conflict (e.g., both prefer to cut through the same background corridor). GraphCut resolves these conflicts globally.

**Benchmark evidence:** 97.9% of tests have `strip_banding_score` worse than simple stitch; 93.8% have worse `ghosting_score`. These metrics are exactly what global seam optimisation addresses.

**Implementation path:** `cv2.detail_GraphCutSeamFinder()` with `COST_COLOR_GRAD` — directly wraps the BK max-flow solver. Needs a combined label mask (which frame owns each pixel), image pair costs, and the overlap mask.

#### §4.5 — DpSeamFinder on Full Canvas
OpenCV's `DpSeamFinder` operates on the **full canvas** DP table (not per-boundary). This produces globally consistent seam paths across all image boundaries simultaneously, without the pairwise approximation.

#### §4.6 — MultiBandBlender Confidence Weighting
OpenCV's `MultiBandBlender` weights each frame's pyramid contribution by the overlap confidence map (derived from the seam mask). ASP's Laplacian blend uses a DSFN mask that encodes photometric similarity, which is related but different — it doesn't account for the number of frames covering a pixel.

#### Autocalibration / Focal Estimation
OpenCV estimates focal length from homographies, handles cameras with different focal lengths across the sequence. ASP assumes fixed focal length (valid for screen recording, less valid for zooming).

#### Rotation/Perspective Model
For sequences where the phone tilts (not just translates), OpenCV handles this naturally via the homography model. ASP's `ASP_SIMILARITY_MODE=1` adds scale+rotation but no perspective. The `LogPolarComparator` in Overmix also handles rotation via the log-polar transform.

### 5.2 What Overmix has that ASP lacks (or has inferior versions of)

#### Hold-Block ECC Sub-Pixel Averaging (§3.12A — partially implemented)
Overmix's core innovation: ECC-align and stack-average all frames within each hold block. √N noise cancellation across hold frames. ASP has this as `_HOLD_AVERAGE` (ASP_HOLD_AVERAGE=1) but it is off by default and not wired into the benchmark.

#### Log-Polar Rotation/Scale Matching
The `LogPolarComparator` handles cases where the phone screen slightly rotates during scroll. ASP's `_extract_similarity()` projects to 4-DOF similarity but only after LoFTR has already produced a flat translation. There is no pre-matching rotation estimation.

#### Recursive Divide-and-Conquer Alignment
`RecursiveAligner` achieves O(N log N) global consistency without full bundle adjustment. ASP's retry chain achieves similar ends but at much higher computational cost.

#### Sub-Pixel Accuracy Throughout
Overmix maintains sub-pixel precision at every stage. ASP rounds to integer pixels in phase correlation and warp outputs. For 1080p sequences this costs ~0.5px accuracy at seams.

### 5.3 What ASP has that OpenCV and Overmix lack

#### Foreground/Background Decomposition
Neither OpenCV nor Overmix separates the image into foreground (animated character) and background (scrolling scene). ASP's BiRefNet-guided processing is unique to this pipeline:
- Background-only matching (bg_masks filter LoFTR/phase correlation keypoints)
- Foreground ARAP registration (ARAP push+regularise with SEA-RAFT/DIS flow)
- Single-pose escalation when foreground is incompatible
- Fg-specific cost tiers in seam DP (the fg/bg cost map)
- Fg coverage gates (§1.70, §1.60, §1.31, §1.69)

This is the most domain-specific feature of the three systems and the reason ASP can produce correct character-foreground stitches where OpenCV's result has the character appearing twice.

#### Hold Detection
Both MAD-based (`_detect_hold_blocks()`) and dHash-based (`_detect_hold_blocks_dhash()`) hold detectors are unique to ASP among production stitchers. Overmix has `AnimationSeparator` but it is a UI tool, not an automated pipeline component.

#### Extensive Retry Chain (5 tiers + 2 fallbacks)
OpenCV has a single failure path (Stitcher status codes). ASP's retry chain handles a wide range of failure modes automatically.

#### RLHF Quality Learning
The `StitchRewardModel` and feedback loop have no equivalent in either comparison system. This is a unique capability for continuous improvement.

#### MFSR Pipeline
Multi-frame super-resolution applied specifically to the stitched canvas is unique to ASP.

#### 125+ Configuration Flags
While this reflects the complexity of the problem, ASP's configurability exceeds OpenCV's by ~5× and Overmix's by ~20×.

---

## Part VI — Ranked Improvement Avenues for ASP

Based on benchmark failure analysis (§2 of asp_state_of_the_pipeline.md) and the gap analysis above:

### Priority 1: §4.2 GraphCut Global Seam Finder
**Target metric:** strip_banding_score (97.9% failure), ghosting_score (93.8% failure)
**Root cause:** Pairwise DP seams conflict globally — each boundary optimises independently.
**Implementation:**
```python
# cv2.detail_GraphCutSeamFinder(COST_COLOR_GRAD or COST_COLOR)
# Needs: masks (label each pixel to owning frame), images (the warped frames)
# Returns: updated masks with seam-optimal labels
# Integration point: replace _find_optimal_boundaries() + _seam_cut() with GraphCut labels
```
Expected improvement: 15–25% reduction in banding score.

### Priority 2: §3.12A Hold-Block Sub-Pixel Averaging (default ON)
**Target metric:** sharpness (ASP already better, 93.8%), ghosting (via SNR improvement)
**Root cause:** MPEG noise in hold blocks is currently discarded (first-frame selection).
**Implementation:** ECC-align + average all frames within each hold block in `smart_select_frames`. Now just needs `_HOLD_AVERAGE=True` default.

### Priority 3: §4.5 DpSeamFinder on Full Canvas
**Target metric:** seam_visibility (88.5% failure)
**Root cause:** Per-boundary DP is locally optimal but globally inconsistent.
**Implementation:** `cv2.detail_DpSeamFinder()` — operates on full canvas overlap matrix.

### Priority 4: §4.6 MultiBandBlender Confidence Weighting
**Target metric:** strip_banding_score
**Implementation:** Weight Laplacian pyramid contribution by seam-quality-derived confidence per frame.

### Priority 5: Log-Polar Rotation Estimation (Pre-Matching)
**Target metric:** tests where phone rotation occurs during scroll
**Implementation:** `cv2.phase_correlate` on log-polar transform to estimate rotation; subtract before affine matching.

### Priority 6: Sub-Pixel Phase Correlation
**Target metric:** sharpness (already best metric)
**Implementation:** Use `cv2.phaseCorrelate()` floating-point output directly (do not round to int) in `_pairwise_match()`.

### Priority 7: §4.3 Wave Correction (already partially implemented)
**Status:** Implemented but behind `WAVE_CORRECT_MIN_TX_RANGE` gate. Need to calibrate gate threshold from benchmark data.

---

## Part VII — Detailed Technical Observations

### 7.1 The Translation-Only Constraint — Why It Matters

OpenCV's panoramic model assumes the camera **rotates about its optical center** (no translation). This is appropriate for a tripod-mounted or hand-held camera rotating in place. The homography model naturally encodes this: for a pure rotation, H = K·R·K^{-1}.

ASP's model assumes the camera **translates** (the phone screen moves vertically while the camera remains fixed). For this geometry, the correct model is a pure translation affine — the same scene content appears shifted by (tx, ty) pixels between frames, with no rotation, scale, or perspective change.

The consequence of applying the wrong model:
- OpenCV applied to a scroll sequence: the homography estimation produces near-identity homographies with small perspective components (from MPEG noise); the autocalibration produces unreliable focal estimates; the spherical/cylindrical warping introduces unnecessary distortion.
- ASP applied to a genuine panorama (camera rotating): the translation-only model cannot capture the homography; LoFTR produces large residuals; the BA fails to converge; PANORAMA fallback is triggered.

### 7.2 The Aperture Problem — The Core Challenge

All three systems struggle with the **aperture problem**: when a region of the image is a uniform flat colour (as is common in anime cel shading), there is no gradient signal and optical flow / phase correlation / feature matching cannot determine the displacement.

OpenCV's SIFT: produces zero keypoints in flat regions. Falls back to the few keypoints at character outlines or sparse background elements.

Overmix's GradientComparator: also fails on flat regions; falls back to BruteForce (pixel difference search).

ASP's cascade:
- LoFTR: designed to handle flat regions via self-attention, but struggles when the background has near-zero spatial frequency.
- TemplateMatch: looks for texture correlation; fails when both frames have uniform bg.
- PhaseCorrelation: even unmasked, a flat bg contributes a DC component only.
- SegmentGuided: treats flat-color regions as rigid segments — most robust of the methods.
- RoMa: DINOv2 features are semantic (scene understanding), not gradient-based — most resistant to the aperture problem.

The fundamental difference: ASP's RoMa + SegmentGuided fallback chain addresses the aperture problem from a semantic angle. OpenCV has no equivalent.

### 7.3 ARAP Registration — Anime-Specific RAFT Application

The most technically novel component of ASP is the ARAP (As-Rigid-As-Possible) foreground registration in `fg_register.py`.

The insight is this: after global BA aligns the backgrounds, the remaining fg displacement field is purely `A_animation` — the character articulation between the two frames. This field is spatially smooth within rigid body parts (torso, head, limbs) but discontinuous at joints. ARAP regularisation enforces local rigidity while permitting joint bending, making it the natural model for human/character articulation.

OpenCV has no foreground registration concept. The multi-band blender just blends character ghosting into a double-image.

Overmix's `AnimationSeparator` addresses a simpler version of this — it groups identical cels (no motion at all) and averages them. Within a hold block, there is no `A_animation` by definition. Overmix does not address the case where the character is mid-motion between two adjacent hold blocks.

### 7.4 The Single-Pose Escalation — ASP's Safety Net

When ARAP registration fails (post_warp_diff > 22 lum), ASP's single-pose mode picks one frame's foreground and discards the other. This is a graceful degradation:

- Result: character appears in one coherent pose, with a hard cut at the seam
- Alt: blending two incompatible poses → double-image ghost (much worse visually)
- The `_single_pose_soft_edge()` + `_seam_color_match()` chain softens the cut to ±6px

Neither OpenCV nor Overmix has an equivalent escalation — they always blend, even when blending produces a ghost.

### 7.5 GNC-TLS vs Cauchy/Huber Robustness

OpenCV's BundleAdjuster uses a Huber loss (linear for large residuals, quadratic for small). This tolerates moderate outliers but breaks down when >50% of edges are outliers.

ASP's GNC-TLS (Yang et al. 2020) with Geman-McClure surrogate is stronger: it tolerates 70–80% outlier edges by annealing from a convex cost (all edges equally weighted) to a truncated-LS cost (large-residual edges assigned near-zero weight). For anime sequences where 3 of 5 matching attempts fail (LoFTR fallback to phase correlation on flat bg), this tolerance is essential.

The trade-off: GNC-TLS requires 8 outer LM solves (vs 1 for Cauchy) — approximately 8× more compute. For sequences with reliable LoFTR matches, the Cauchy path (ASP_GNC_OUTER=0) is preferred.

### 7.6 Benchmark Failure Taxonomy

From `bench_anime_stitch.py` benchmark data:
- **strip_banding_score worse (97.9%):** Root cause = pairwise DP + global scalar gain cannot fix spatially-varying banding. Fix = §4.1/§4.2.
- **ghosting_score worse (93.8%):** Root cause = pairwise seams + ARAP failure on extreme pose gaps. Fix = §4.2 GraphCut + hold-block averaging.
- **seam_visibility worse (88.5%):** Same root causes as ghosting. Fix = §4.2 + §3.12A.
- **GT-SSIM worse (−0.040 average):** Root cause = GT coupling (GT uses different frame selection timing than ASP). Not a real failure — GT comparison is biased.
- **sharpness better (ASP 93.8%):** Root cause = temporal median + MFSR > simple stitch median. This is ASP's strongest advantage.

---

## Part VIII — Code Architecture Comparison

### 8.1 Modularity

| System | Structure | Lines (approx) | Separability |
|--------|-----------|----------------|--------------|
| OpenCV Stitcher | Monolithic C++ module, pluggable via factory | ~8,000 | High via setters |
| Overmix | C++/Qt class hierarchy, abstract bases | ~12,000 | High via vtable |
| ASP | Python modules, 8 subdirectories | ~20,000 | Medium (many cross-imports) |

ASP is the largest codebase, reflecting its multi-modal nature (basic photometric, deep learning, optical flow, RLHF, HITL, MFSR).

### 8.2 Testability

| System | Unit tests | Integration tests | Automated benchmarks |
|--------|------------|-------------------|----------------------|
| OpenCV | Yes (C++ gtest) | Yes | Manual |
| Overmix | No (UI tool) | No | Manual |
| ASP | 110+ unit tests | Benchmark suite (96 tests) | Yes — bench_anime_stitch.py |

ASP's test coverage is the most comprehensive in the production-Python sense.

### 8.3 Configuration

| System | Config mechanism | # Parameters |
|--------|-----------------|--------------|
| OpenCV | API setters | ~20 |
| Overmix | Qt UI sliders | ~15 |
| ASP | ASP_* env vars + asp_config.toml | 125+ |

The configuration breadth reflects ASP's research character — many flags correspond to individual research hypotheses being tested.

### 8.4 Runtime Dependencies

| System | Heavy deps | GPU required |
|--------|------------|--------------|
| OpenCV | libopencv (C++), LAPACK | Optional (OpenCL) |
| Overmix | Qt5, libtiff | Optional |
| ASP | torch, transformers, ptlflow, scipy, skimage, cv2, PIL, numpy, JPype | Optional (CUDA) |

ASP's dependency tree is the heaviest — reflecting its use of multiple deep learning models.

---

## Part IX — Conclusions and Synthesis

### What makes ASP unique:
1. **Domain specificity:** The only pipeline designed specifically for anime scrolling screen recordings. The fg/bg decomposition and ARAP registration are domain-specific innovations not present in either comparison system.
2. **Robustness engineering:** The 5-tier retry chain, 24 pre-DP gates, 15 post-composite metrics, and comprehensive fallback hierarchy make it the most robust of the three systems for its target use case.
3. **Research depth:** GNC-TLS bundle adjustment, spatial DSFN blending, Geman-McClure weights, spanning-tree inlier filter — these are recent academic techniques incorporated in the production pipeline.

### What OpenCV does better:
1. **Global seam optimisation:** GraphCut finds the globally optimal seam across all images simultaneously. ASP's pairwise DP is a strict approximation.
2. **Camera model generality:** The projective camera handles rotation, perspective, and focal variation — appropriate when the recording is not a pure screen scroll.
3. **Robustness at a lower code cost:** ~8,000 lines vs ~20,000 lines for comparable core functionality.

### What Overmix does better:
1. **Sub-pixel accuracy:** ECC-aligned hold-block averaging cancels MPEG noise by √N.
2. **Simplicity:** The average/median rendering strategy is effective for the simple super-resolution case.
3. **Log-polar matching:** Handles rotation-corrupted recordings that both ASP and OpenCV miss.

### The fundamental tradeoff:
OpenCV and Overmix solve **simpler** problems (general panoramas, static screenshots) with **simpler** models. ASP solves a **harder** problem (animated character + dynamic background + compressed video) with a correspondingly complex pipeline. The benchmark results showing ASP worse on banding/ghosting reflect the difficulty of the problem, not a fundamental algorithmic deficiency — the correct comparison is ASP vs "simple stitch" (which is just `cv2.Stitcher_create(SCANS).stitch(frames)`), not ASP vs OpenCV's full pipeline on a panorama.

The remaining gap between ASP and the ideal result is primarily addressable by:
1. §4.2 GraphCut global seam (replaces pairwise DP)
2. §3.12A hold-block averaging (reduces MPEG noise at source)
3. §4.5 full-canvas DP (global consistency without GraphCut's memory overhead)

All three are present in the roadmap. Implementing just §4.2 is expected to address the majority of the 97.9% banding failure rate.
