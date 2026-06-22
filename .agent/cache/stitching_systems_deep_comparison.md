# Deep Comparative Analysis: OpenCV Stitcher · Overmix · Anime Stitch Pipeline

*Date: 2026-06-22. Analysed codebases: `opencv/modules/stitching/` (C++), `Overmix/src/` (C++/Qt), `backend/src/animation/` (Python 3.11). This document supersedes `asp_opencv_overmix_comparison.md` and `comparative_stitching_analysis.md`.*

---

## Part I — Executive Overview

### 1.1 Design Intent and Target Domain

| Dimension | OpenCV Stitcher | Overmix | Anime Stitch Pipeline (ASP) |
|---|---|---|---|
| **Primary use-case** | General outdoor/indoor panoramas from handheld/tripod cameras | Anime screenshot super-resolution & noise-cancelling composite | Anime character full-body panorama from phone-scroll video |
| **Input type** | Overlapping photographs, arbitrary subject matter | Static or near-static anime screenshots from video/scan | Sequential video frames from a vertically-scrolling phone screen recording |
| **Primary challenge** | Focal estimation across wide baselines, lens distortion, rotation | JPEG/MPEG quantisation noise, sub-pixel shifts, chroma subsampling | Animated character changing pose between frames, MPEG hold blocks, flat cel-shaded regions |
| **Output type** | Equirectangular / cylindrical / planar panorama | Super-resolved noise-cancelled composite image | Full-body character canvas with accurate foreground pose |
| **Camera model** | Full projective (8-DOF homography) or 4-DOF similarity | Pure 2D translation (sub-pixel) | 2-DOF translation or 4-DOF similarity affine |
| **Foreground handling** | None — all content treated equally | None — no fg/bg separation; median render rejects transients | Explicit: BiRefNet deep segmentation → separate fg/bg alignment pipelines |
| **Language / runtime** | C++ (OpenCV core), Python bindings via `cv2` | C++/Qt5 desktop application | Python 3.11, Rust (`base` module via PyO3), JPype/JVM for crypto |
| **GPU requirement** | Optional OpenCL / CUDA | Optional via Qt (WebGPU in newer versions) | Optional CUDA (SEA-RAFT, LoFTR, ALIKED, BiRefNet) |
| **Failure recovery** | Stitcher status codes; no automatic fallback | Interactive UI, manual re-alignment | 5-tier automated retry chain + PANORAMA fallback + SCANS fallback |

### 1.2 Fundamental Architecture Differences

**OpenCV Stitcher** derives directly from Brown & Lowe (2007) "Automatic Panoramic Image Stitching Using Invariant Features." It is a classic academic pipeline: sparse keypoints → RANSAC homography → global bundle adjustment → wave correction → warping → seam finding → multi-band blending. Every stage has a pluggable abstract interface (`FeaturesFinder`, `FeaturesMatcher`, `Estimator`, `BundleAdjuster`, `WarperCreator`, `SeamFinder`, `ExposureCompensator`, `Blender`). The design prioritises generality: it handles arbitrary camera orientations, focal lengths, and scene content.

**Overmix** treats anime screenshot assembly as a *super-resolution problem*, not a panorama problem. Its core insight is that multiple JPEG-compressed frames of the same scene position contain complementary sub-pixel samples (from the chroma grid offset and compression noise). After sub-pixel alignment, pixel averaging cancels quantisation noise by √N and the output exceeds the resolution of any individual frame. Overmix does not find seams — all frames are alpha-composited with pixel averaging. This works perfectly when all frames show identical content (hold blocks, static backgrounds) and produces ghosting when frames differ.

**ASP** explicitly models the composite problem as `T_total = T_camera + A_animation`: a rigid background camera translation plus a non-rigid foreground character animation. It performs these alignments separately — background via phase correlation + bundle adjustment, foreground via ARAP optical flow registration at seam boundaries. This decomposition is the unique technical contribution that neither OpenCV nor Overmix makes.

### 1.3 Pipeline Diagrams

#### OpenCV Stitcher (code path: `stitcher.cpp` → `Stitcher::stitch()`)
```
Input images
    ↓ [estimateTransform()]
Feature detection at registr_resol_=0.6
  └─ SIFT/ORB/BRISK/AKAZE via FeaturesFinder::find()
    ↓
Pairwise feature matching — BestOf2NearestMatcher::match()
  ├─ FLANN kNN (k=2) → Lowe ratio test (1−match_conf)
  ├─ RANSAC findHomography() → inlier mask
  └─ confidence = inliers / (8 + 0.3 × num_matches)
    ↓
Connected component graph — findMaxSpanningTree()
  └─ Prune images where conf < conf_thresh_ (default 1.0)
    ↓
Camera estimation — HomographyBasedEstimator / AffineBasedEstimator
  ├─ PANORAMA: focalsFromHomography() → median focal → calibrateRotatingCamera() → R matrices
  └─ SCANS: estimateAffinePartial2D() per pair → 4-DOF similarity
    ↓
Bundle Adjustment — BundleAdjusterRay / BundleAdjusterAffinePartial
  ├─ LM (CvLevMarq) with numeric Jacobian (step=1e-3)
  ├─ params: [focal, aspect, ppx, ppy, r1, r2, r3] × N = 7N vars
  └─ waveCorrect(rmats, WAVE_CORRECT_HORIZ) post-BA
    ↓
Warping at seam_est_resol_=0.1 — SphericalWarper / AffineWarper
  └─ buildMaps() → remap tables; warp all images to canvas
    ↓
Exposure compensation — BlocksGainCompensator(32, 32)
  └─ feedWithStrategy() → apply() gain maps
    ↓
Seam finding — GraphCutSeamFinder("COST_COLOR_GRAD")
  └─ GCGraph s-t min-cut per image pair overlap
    ↓
    ↓ [composePanorama()]
Warping at compose_resol_=ORIG
    ↓
Exposure apply
    ↓
Blending — MultiBandBlender(num_bands)
  └─ feed(img, mask, tl) → blend() → dst
    ↓
Output panorama
```

#### Overmix (code path: `RecursiveAligner::align()` → `AverageRender::render()`)
```
Input images (anime screenshots / scan captures)
    ↓
Load → ImageEx [Plane<int16> per channel, PlaneInfo subsampling, ColorSpace(Transform, Transfer)]
    ↓
[Optional] AnimationSeparator — detect hold blocks
  ├─ pairwise error[i] = findOffset(i, i+1) MAD score
  ├─ threshold = midpoint that maximises sign-change count
  └─ greedy group assignment by threshold
    ↓
[Optional] Deteleciner — 3:2 pulldown / interlace detection
    ↓
Alignment: RecursiveAligner (divide-and-conquer tournament tree)
  ├─ split [begin,end) → [begin,mid) + [mid,end)
  ├─ recurse each half → produces composite representative
  ├─ combine(repr_left, repr_right): AComparator::findOffset() with hint
  │   ├─ GradientComparator: GradientPlane::findMinimum() hierarchical grid + DiffCache + QtConcurrent
  │   ├─ MultiScaleComparator: recursive 2× downsample + 4-neighbour sub-pixel refinement
  │   └─ BruteForceComparator: exhaustive grid over [-mov,mov]²
  └─ shift [mid,end) by inter-half offset; update center_left/center_right
    ↓
[Optional] LinearAligner post-pass — LS fit pos[i] = a·i + b, remove drift wobble
    ↓
Rendering: AverageRender::render()
  ├─ SumPlane: sum[y][x] += pixel × alpha; count[y][x] += alpha
  ├─ Sub-pixel sampling via spacing/offset (SR mode: fractional positions)
  └─ average[y][x] = sum[y][x] / count[y][x]
OR StatisticsRender::MEDIAN — nth_element per canvas pixel (ghost rejection)
OR FloatRender — B-spline (B=1,C=0) kernel reconstruction from fractional positions (true SR)
OR RobustSrRender — Eigen sparse DHF + L1 sub-gradient descent
    ↓
Output: super-resolved composite (no seam — all frames averaged)
```

#### ASP (code path: `core/pipeline.py` → `AnimeStitchPipeline.run()`)
```
Input: N frame paths (anime vertical-scroll video frames)
    ↓ Stage 1
_load_frames() → cv2.imread + _trim_dark_border() + sort by numeric suffix
  └─ static gate (§1.29): MAD < 2 lum → copy frame 0
    ↓ Stage 2
_normalise_widths(): Lanczos4 resize all to median width
    ↓ Stage 3 [optional]
BaSiCWrapper: blind flatfield/vignetting correction
    ↓ Stage 4
BiRefNetWrapper → bg_masks[] (255=background, 0=foreground per pixel)
  └─ §1.37 bg coverage gate: <5% bg pixels → SCANS fallback
    ↓ Stage 4.5
Background photometric normalisation:
  ├─ global scalar gain per frame (bg median → ref median ratio)
  ├─ §1.4B continuous clamp: clamp_width = 0.26 − 0.12×(ref_lum/255)
  ├─ §1.4C bg-only unclamped: raw gain when clamped would cut >20%
  ├─ §1.18 per-pair coherence gate: only bad pairs skip normalisation
  ├─ §1.4D [opt] Gaussian-blur per-pixel gain field
  ├─ §1.4E [opt] CDF histogram matching LUT
  └─ §1.98 [opt] 1D Gaussian smooth over frame_gains[]
    ↓ Stage 4.7 [optional]
ProPainter background completion + near-dup luma pre-filter
    ↓ Stage 5-6
Pairwise matching (_match_pair cascade):
  1. JamMa (4K) → EfficientLoFTR → kornia LoFTR
  2. ALIKED + LightGlue
  3. Template match (TM_CCORR_NORMED)
  4. Masked phase correlation (bg-only, highpass + Hanning)
  5. Unmasked phase correlation
  6. Segment-guided (k-means color + region centroid)
  7. RoMa v2 (DINOv2 dense warp)
  + Hold detection: MAD / dHash → skip within-hold pairs
  + Post-match gates: §1.36 spread, §1.38 bg-ratio, §1.43 coverage,
                      §1.47 sign consistency, §1.48 CV, §1.49 adj-min,
                      §2.14 triangular consistency
    ↓ Stage 7
Bundle adjustment (_bundle_adjust_affine):
  ├─ §1.1B spanning-tree inlier pre-filter (Kruskal + BFS, 50px threshold)
  ├─ §1.17 GNC-TLS outer loop: 8× Geman-McClure (μ₀=max(r²)/2c², anneal ×1/1.4)
  ├─ §1.1C LM inner: scipy least_squares Cauchy loss, f_scale=10px
  ├─ §1.1D adaptive f_scale: re-solve if adaptive_scale > 1.5× initial
  └─ §4.3 wave correction: np.polyfit(1) subtract linear drift from tx/ty
    ↓ Stage 7b
Affine validation + retry chain:
  Retry 0: §2.9C high-conf edges only (weight≥0.65, N-1 edges needed)
  Retry 1: adjacent-only BA (drop skip-pair edges)
  Retry 2: sequential greedy 3-pass
  Retry 3: relaxed min_step (§0.5C adaptive floor=20px)
  Retry 4: min_step=3.0, max_ratio=10.0
  Retry 5: min_step=0.5, max_ratio=50.0
  → _panorama_stitch_fallback (cv2.Stitcher PANORAMA mode)
  → _scan_stitch_fallback (direct vstack)
    ↓ Stage 8
[Optional] SEA-RAFT optical flow sub-pixel refinement
[Optional] ECC affine refinement (_ecc_refine)
    ↓ Stage 9
Canvas construction (_compute_canvas):
  ├─ Bounding box from affine-transformed corners
  ├─ Midplane shift (StabStitch++ bidirectional warp)
  └─ Gates: §1.44 max gap, §1.45 canvas width ratio, §1.51 min overlap,
            §1.53 canvas MB, §1.62 aspect ratio, §3.14 scroll axis
    ↓ Stage 10
Temporal median render (_render_median):
  ├─ cv2.warpAffine each frame into canvas (INTER_LINEAR)
  └─ per-pixel median across frames → ghost-removes animated fg
    ↓ Stage 10.2-10.5
BG zero-coverage fill + multi-frame coverage gate (§0/§13)
    ↓ Stage 11
Foreground composite (_composite_foreground):
  ├─ _find_optimal_boundaries (±250px search for min seam step)
  ├─ §1.17 adaptive boundary search (100px for pure vertical scroll)
  ├─ _build_seam_cost_map (fg interior=1.0, edge buffer=0.5, bg=0.0,
                           column barrier=2.0, hard barrier=1e6)
  ├─ 24+ pre-DP escalation gates → single-pose if fired
  ├─ _seam_cut (1D DP, monotone left→right):
  │     energy = diff + 0.5·|∇diff| + edge_weight·(|∇img1|+|∇img2|) + sem_cost
  │     + §1.125 seam transition penalty (midline prior)
  │     forward: scipy.ndimage.minimum_filter1d(size=3)
  │     traceback: slice-argmin
  ├─ FG registration: ARAP push+regularise (SEA-RAFT/DIS flow → ARAP)
  ├─ _fb_for_blend chain: _zone_chroma_align → _zone_lum_norm →
  │     _zone_sat_norm → _zone_contrast_eq → _zone_hue_eq
  ├─ _laplacian_blend (N-band pyramid on seam path)
  ├─ [opt] _poisson_seam_blend (cv2.seamlessClone ±20px)
  ├─ Single-pose: _single_pose_soft_edge + _seam_color_match
  └─ Per-pixel DSFN ramp (sim_diffused, bg-mask-aware S20)
    ↓ Post-composite: 15 quality audit gates
    ↓ TELEA inpainting (§1.7B), _crop_to_valid
    ↓ [optional] Super-resolution (mfsr/), SRStitcher
    ↓
Output: PIL.Image panorama
```

---

## Part II — Data Model and Representation

### 2.1 OpenCV: CameraParams, ImageFeatures, MatchesInfo

**`CameraParams`** (camera.hpp):
```cpp
struct CameraParams {
    double focal;     // focal length in pixels
    double aspect;    // aspect ratio (pixel_height / pixel_width)
    double ppx, ppy;  // principal point
    Mat R;            // 3×3 rotation matrix (float64)
    Mat t;            // 3×1 translation (usually ignored in rotating-camera panoramas)
};
```
This struct encodes a full projective camera. Bundle adjustment optimises `[focal, aspect, ppx, ppy, rvec(3)]` = 7 parameters per camera.

**`ImageFeatures`** (matchers.hpp):
```cpp
struct ImageFeatures {
    int img_idx;
    Size img_size;
    std::vector<KeyPoint> keypoints;
    UMat descriptors;  // GPU-accessible descriptor matrix
};
```
Uses `UMat` (transparent CPU/GPU memory) for OpenCL acceleration of descriptor matching.

**`MatchesInfo`** (matchers.hpp):
```cpp
struct MatchesInfo {
    int src_img_idx, dst_img_idx;
    std::vector<DMatch> matches;
    std::vector<uchar> inliers_mask;
    int num_inliers;
    Mat H;              // 3×3 homography (PANORAMA) or 2×3 affine (SCANS)
    double confidence;  // inliers / (8 + 0.3 × matches.size())
};
```

**`GCGraph<float>`** (seam_finders.cpp): Internal graph structure for max-flow. Each pixel in the overlap region is a node. Edges: terminal edges (to source/sink) encode image ownership priors; N-link edges encode cut cost derived from colour+gradient.

### 2.2 Overmix: Plane<int16>, ImageEx, AContainer, PlaneInfo

**`Plane<short>` (= `color_type = short`, int16)**: The fundamental pixel buffer. Row-major with `scan_line(y)` accessor. All arithmetic is integer-domain — no floating-point for pixel values. Range `[0, color::WHITE]` where WHITE = 4095 or 65535 depending on bit depth. Conversion: `color::asDouble(v)` normalises to [0,1]; `color::fromDouble(d)` denormalises.

Key `Plane` operations:
- **Scaling**: SCALE_NEAREST / SCALE_LINEAR / SCALE_MITCHELL (B=1/3,C=1/3) / SCALE_CATROM (B=0,C=0.5) / SCALE_SPLINE (B=1,C=1) / SCALE_LANCZOS_3/5/7. Non-nearest kernels call `scale_generic_alpha(alpha, size, window, filter_func, offset)` where `offset` is a fractional sub-pixel phase — enables SR sub-pixel-aware scaling.
- **Edge detection**: Robert cross (1×2), Sobel (3×3), Prewitt (3×3), Laplacian (3×3 and 5×5), Laplacian-of-Gaussian `edge_laplacian_ex(sigma, k, size)`.
- **Blurring**: Box blur, Gaussian blur via `weighted_sum(kernel)`.
- **Deconvolution**: Richardson-Lucy `deconvolve_rl(amount, iterations, creep_plane, creep_amount)` — iterative blind deblurring for JPEG artifact removal.
- **Arithmetic**: `add`, `subtract`, `difference`, `divide`, `multiply`, `mix`, `overlay(p, p_alpha, this_alpha)` (alpha-composited blend).
- **DCT**: `DctPlane` — FFTW `FFTW_REDFT10` (DCT-II) / `FFTW_REDFT01` (DCT-III). Used for `PatternRemove` and JPEG DCT-domain rendering.
- **FFT**: `FourierPlane` — FFTW `fftw_plan_dft_r2c_2d`. Stores Hermitian half-spectrum. Methods: `reduce(w,h)` (spectral low-pass), `remove(w,h)` (high-pass), `blur(dev_x,dev_y)` (Gaussian in frequency domain), `asPlane()` (log-magnitude visualisation with DC-shift).

**`ImageEx`**: Holds `vector<PlaneInfo>` + separate alpha `Plane` + `ColorSpace`. Each `PlaneInfo` stores a `Plane` and a `Size<int> subsampling` offset encoding chroma subsampling (e.g., subsampling={2,2} for 4:2:0 Cb and Cr planes). `ColorSpace` has two independent fields:
- `Transform`: GRAY / RGB / YCbCr_601 / YCbCr_709 / JPEG (YCbCr_601 without studio-swing) / BAYER (R,G1,B,G2 four-plane raw) / UNKNOWN
- `Transfer` (gamma): LINEAR / SRGB / REC709 / UNKNOWN

`ImageEx::diff(img, x, y)` computes MAD at offset (x,y) over the luma plane — the core alignment metric.
`ImageEx::apply(func, args...)` restricts processing to luma when in YCbCr space.

YCbCr conversion `color::ycbcrToRgb(kr, kg, kb, gamma, swing)`:
- BT.601: kr=0.299, kg=0.587, kb=0.114
- BT.709: kr=0.2126, kg=0.7152, kb=0.0722
- Studio swing: Y∈[16,235], Cb/Cr∈[16,240] → [0,1]
- JPEG: BT.601 without studio swing
- Gamma: `gamma_lookup[i] = linear2sRgb(ycbcr2linear(v))` — corrects double-gamma in interlaced TV captures

**`AContainer`**: Abstract image collection. Interface: `count()`, `image(i)`, `alpha(i)`, `rawPos(i)`, `frame(i)`, `zoom(i)`, `rotation(i)`, `mask(i)`, `getComparator()`, `findOffset(i,j)` (invokes comparator; cached in `hasCachedOffset/getCachedOffset`). `ContainerImageRef<T>` is a C++ range-for proxy.

**`ImageContainer`**: Concrete `AContainer` holding owned `ImageEx` objects. Frame IDs used by `AnimationSeparator` to group same-camera-position images.

### 2.3 ASP: numpy arrays, affine dicts, edge graph, bg_masks

ASP has no custom pixel type — all images are `np.ndarray[uint8, (H,W,3)]` (BGR, OpenCV convention). Key data structures:

**`frames`**: `List[np.ndarray]` — loaded video frames, all normalised to same width.
**`bg_masks`**: `List[np.ndarray[uint8]]` — per-frame binary masks, 255=background pixel, 0=foreground pixel. Produced by BiRefNet or SAM2. The most important data structure — used at every subsequent stage.
**`edges`**: `List[dict]` — pairwise matching results. Each dict has:
```python
{
  "i": int, "j": int,          # frame indices (i < j)
  "dx": float, "dy": float,    # observed displacement in pixels
  "weight": float,             # matching confidence [0,1]
  "M": np.ndarray[float,(3,3)], # affine matrix from this edge
  "type": str,                  # "adjacent" | "skip"
}
```
**`affines`**: `List[np.ndarray[float,(2,3)]]` — per-frame affine matrices from BA. `affines[i]` maps frame i pixel (x,y) to canvas pixel (x',y'): `[x', y', 1]^T = M · [x, y, 1]^T`.
**`canvas`**: `np.ndarray[uint8,(H_canvas, W_canvas, 3)]` — output canvas after warping all frames.
**`warped_frames`**: `List[np.ndarray]` — individual frames warped into canvas space.
**`seam_post_diffs`**: `Dict[int, float]` — per-boundary (key=seam index k) post-ARAP luminance difference. Drives adaptive feather (§1.12), gain-adaptive feather minimum (§1.6B), adaptive SP soft edge (§1.124).
**`seam_path_cache`**: `Dict[Tuple, np.ndarray]` — keyed by `(tuple(image_paths), k, (_POISSON_SEAM, _TOONCRAFTER_SEAM))`. Eliminates re-computation on RLHF iterations (§1.5D).

---

## Part III — Stage-by-Stage Comparison

### Stage A: Input and Frame Selection / Grouping

#### OpenCV
Accepts images in any order (topology discovered from matching). `Stitcher::stitch(images)` → `estimateTransform()` applies feature detection to all images at `registr_resol_=0.6` (60% of original resolution). No frame selection — all supplied images are used. Images rejected only if `confidence < conf_thresh_` in the matching graph.

#### Overmix
All frames loaded as `ImageEx` via Qt image loading. Frame ordering matters for `AnimationSeparator` but not for `AverageRender`. Key: **`AnimationSeparator`** performs automatic hold-block detection:
1. Compute `error[i] = findOffset(i, i+1)` MAD score for all adjacent pairs.
2. For each midpoint value `(sorted_errors[k-1] + sorted_errors[k]) / 2` between adjacent sorted errors: count sign changes in the original (temporal) error sequence at this threshold.
3. Select threshold maximising sign-change count — this is the most discriminating split of the bimodal error distribution (same-frame pairs have near-zero error; different-frame pairs have high error).
4. Greedy group assignment: `if error(last_in_group, candidate) < threshold → same group; else new group`.
`threshold_factor` (default 1.0) scales the found threshold.

This is the only system with automatic frame-grouping. OpenCV assumes pre-grouped input. ASP has an analogous `AnimationSeparator`-inspired hold detector but uses MAD threshold (default `ASP_HOLD_THRESHOLD=0.025`) or dHash Hamming distance (≤4, `ASP_HOLD_DHASH_THRESH=4`).

#### ASP
`smart_select_frames()` in `ingestion/frame_selection.py`:
1. **§S39 temporal variance filter** (`_temporal_variance_filter`): drop interior frames with mean per-pixel triplet variance < threshold (default OFF, `ASP_TEMPORAL_VAR_THRESH=0`).
2. **§S6/§S43 hold detection** (step 1b): `_detect_hold_blocks` (MAD) or `_detect_hold_blocks_dhash` (INTER_AREA resize + horizontal gradient binarisation, Hamming ≤ 4).
3. **§S38 response-based hold refinement** (`_refine_hold_ids_by_response`): merge hold blocks where cross-hold phaseCorrelate response ≥ 0.85 (near-identical frames split by MPEG noise).
4. **§S8 DINOv2 frame selection**: `_compute_dinov2_features(frames_paths)` — module-level `_DINOV2_CACHE[device]`. Enable: `ASP_POSE_WINDOW_PX=80`.
5. **§S26 near-dup luma post-filter** (`_near_dup_luma_filter`): mean abs grayscale diff at thumbnail scale < `ASP_NEAR_DUP_LUMA` (default 0.0 OFF).

**Key difference**: ASP is the only system that actively *removes* redundant frames before matching. This reduces BA graph complexity and eliminates within-hold pairs that corrupt phase correlation.

---

### Stage B: Photometric / Color Pre-processing

#### OpenCV
No preprocessing before matching. `BlocksGainCompensator` is applied *after* seam finding in `composePanorama()`. The 32×32 block gain correction therefore operates on warped images in canvas space, correcting for residual photometric differences after matching.

#### Overmix
No explicit photometric correction. Per-plane alpha compositing implicitly normalises coverage. Does not address exposure drift across the sequence. However, the YCbCr pipeline (with studio-swing and gamma tables) correctly handles the colour encoding of anime screenshots — this is a form of photometric preprocessing that OpenCV (BGR only) and ASP (BGR + limited YCbCr) do not match.

#### ASP
Four photometric correction stages before any matching:
- **Stage 3 (BaSiC)**: `BaSiCWrapper.correct(frames)` — blind illumination model. Flatfield = Gaussian smooth of across-frame median; darkfield from minimum projection. Removes phone screen vignetting (center brighter than edges).
- **Stage 4.5 (global scalar gain)**: `ref_lum = median(bg_pixels[ref_frame])`. Per-frame: `gain = ref_lum / frame_lum`. Clamped by `_adaptive_gain_clamp()` (§1.4B S24): `clamp_width = 0.26 − 0.12×(ref_lum/255)` (ranges ±26% for dark scenes, ±14% for bright).
- **Stage 4.5b (per-segment k-means)**: 8-cluster k-means colour quantisation; per-cluster gain [0.88, 1.12]. Corrects dynamic contrast enhancement (phone screens brighten/dim panels).
- **§4.1/§4.4 blocks gain** (S160, applied at seam zone): `_blocks_gain_compensate(fa_zone, fb_zone, block_size=32)` — BGR ratio per 32×32 block, bilinear resize, clamp [0.5, 2.0]. `_blocks_lum_compensate` uses LAB L-channel scalar to avoid colour cast from near-zero channel means.

**Key difference**: ASP applies photometric correction before matching (so phase correlation operates on normalised frames). OpenCV applies it after seam finding (global canvas). Overmix relies on averaging. The strip_banding_score failure (97.9% of tests worse) is partially attributable to ASP's global scalar gain being insufficient for spatially-varying illumination within a single frame.

---

### Stage C: Feature Detection and Description

#### OpenCV
`FeaturesFinder::find(image, features)`:
- Default (Python): `SIFT_create()` (128-dim float descriptor)
- Alternatives: `ORB_create()` (32-byte binary), `BRISK_create()`, `AKAZE_create()`
- Applied at `registr_resol_=0.6×` for speed; descriptors at this resolution
- `UMat` storage enables OpenCL acceleration for FLANN matching

SIFT requires high-gradient corners/edges for reliable keypoints. Flat cel-shaded anime provides few such regions — this is why `cv2.Stitcher_create(SCANS).stitch(frames)` fails on anime: too few SIFT matches.

#### Overmix
No keypoint detection — raw pixel differences. Alignment metric is `Difference::simpleAlpha(p1, p2, x, y)`:
- Crops overlapping region at offset (x,y)
- `sum += |p1(i) − p2(i)| × alpha1(i) × alpha2(i)` (L1) or `sum += (p1(i) − p2(i))² × weight` (L2 with `use_l2=true`)
- OpenMP `#pragma omp parallel for reduction(+:sum)`
- Returns `sum / total_weight`; NaN if overlap < 10% of pixels (avoids degenerate tiny overlaps)
- `stride` parameter: subsample every N-th pixel for speed

This is completely texture-agnostic — works on flat cel-shaded regions where all keypoint-based methods fail. The trade-off: only reliable for small displacements (brute-force over `[-max, max]²` where `max = movement × img_width`).

#### ASP
Multi-method cascade in `alignment/matching.py`:
1. **EfficientLoFTR / kornia LoFTR**: detector-free transformer. Produces dense matches on image patch pairs without explicit corner detection. Works on flat regions via self-attention. Filtered to background keypoints only via `bg_masks`.
2. **ALIKED + LightGlue**: ALIKED produces keypoints at anime line-art edges. Triggered when LoFTR returns < 20 background matches.
3. **Template match** (`TM_CCORR_NORMED`): slides top strip of img_i through bottom of img_j. Bidirectional.
4. **Masked phase correlation**: `_phase_correlate(bg_masked_highpass_a, bg_masked_highpass_b, hann_window)` → `(shift, response)`. Global FFT-based peak; no local descriptor.
5. **Segment-guided** (`_segment_guided_match`): k-means (16 colours) → connected components → match regions by `color_dist/256 + 2×position_dist`. Last resort for fully flat frames.
6. **RoMa v2**: DINOv2-based dense warp; semantic matching.

Post-match filters: `§1.36` spread filter (MAD > `_MATCH_SPREAD_CEIL` → bimodal, reject), `§1.38` bg-ratio filter (bg_ratio < `_LOFTR_BG_RATIO_MIN` → fg-dominated, reject).

**Advantage over OpenCV**: bg-filtered matching eliminates the character's animation motion from the displacement estimate. **Advantage over Overmix**: works on large displacements (via FFT phase correlation). **Advantage of Overmix over both**: sub-pixel L1 difference is the gold standard for accuracy when displacement is small.

---

### Stage D: Pairwise Matching and Graph Construction

#### OpenCV — `matchers.cpp` — `BestOf2NearestMatcher`
```
For each pair (i, j):
  BFMatcher::knnMatch(desc1, desc2, k=2) → [m1, m2] per descriptor
  Lowe ratio: keep m1 if m1.distance / m2.distance < 1 − match_conf (default 0.3)
  RANSAC findHomography(src_pts, dst_pts, RANSAC, reproj_thresh=1.0)
  → inliers_mask, H
  confidence = num_inliers / (8 + 0.3 × num_matches)
  (8 = minimum DOF for homography; normalization makes conf comparable across sizes)
All-to-all matching (O(N²)); with BestOf2NearestRangeMatcher: range_width adjacent pairs only
findMaxSpanningTree: Prim's on confidence graph; prune images with conf < conf_thresh_
```

#### Overmix — `GradientComparator`/`GradientPlane`/`MultiScaleComparator`
```
GradientComparator:
  GradientPlane::findMinimum(search_area):
    divide area into (level×2+2)² probe points
    per probe: Difference::simpleAlpha with precision = sqrt(h_offset) stride
    parallel evaluation via QtConcurrent::map
    DiffCache memoises (x, y, precision) → avoids recomputing same positions
    recurse into sub-area around best probe with level-1
    base case: evaluate every integer point in area

MultiScaleComparator:
  img_half = simple2xDownscale(img)  # 2×2 box filter
  base = MultiScaleComparator::findOffset(img_half/2, hint/2)
  baseOffset = base.distance × 2
  check 4 candidates: {baseOffset, baseOffset+(0,1), baseOffset+(1,0), baseOffset+(1,1)}
  return min-error candidate
  (recursion depth = floor(log2(min(W,H))))
```

`IndependentAligner` provides multi-pair matching with Jacobi refinement:
- For each pair (i,j) within `range`: `container.findOffset(i,j)` → cache
- Jacobi 10 iterations: `offset[i] = mean of (cached_offset(j,i) + offset[j]) for all j with cache`
- Converges to LS solution of over-determined pairwise constraint system
- Sub-pixel rounding: `setRawPos(i, (offsets[i]×2).round() / 2.0)` — 0.5-pixel granularity

#### ASP
Builds an edge graph. Adjacent edges: all (i, i+1) pairs. Skip-pair edges: (i, i+2), (i, i+3) for redundancy. Within-hold pairs: zero displacement, zero weight, skipped. Post-match gates prune edges with inconsistent or weak displacements. Remaining edges fed to BA.

**Key structural difference**: OpenCV matches all-to-all and prunes by confidence graph. ASP pre-limits to adjacent+skip but has 7 fallback matching methods per pair. Overmix matches nearest-N pairs only (IndependentAligner `range` parameter).

---

### Stage E: Geometric Estimation (Camera Model / Affine / Translation)

#### OpenCV — `motion_estimators.cpp`

**Camera model**: Full projective. `CameraParams.R` is a 3×3 rotation matrix; `CameraParams.focal` and `aspect` define the intrinsics. For the rotating-camera panorama assumption, `K = [[focal, 0, ppx],[0, focal×aspect, ppy],[0,0,1]]` and the mapping between images i and j is `H_ij = K_j · R_j · R_i^{-1} · K_i^{-1}`.

**`HomographyBasedEstimator`**:
1. Estimates each pairwise H from `MatchesInfo.H`.
2. `focalsFromHomography(H, f0, f1, f0ok, f1ok)`: extracts two focal candidates from the homography eigenstructure (based on constraints from the image of the absolute conic).
3. Median focal across all valid estimates → `focal`.
4. `calibrateRotatingCamera(Hs)` (autocalib.cpp): Given N homographies, solves for N rotation matrices assuming common focal. Uses SVD of the accumulated outer product of `H^T · ω · H` where ω is the image of the absolute conic `diag(1/f², 1/f², -1)`.
5. Max spanning tree BFS initialises `R[i]` from the spanning tree traversal.

**`AffineBasedEstimator`** (SCANS mode):
- Per pair: `estimateAffinePartial2D(src_pts, dst_pts, RANSAC)` → 2×3 affine (4-DOF: tx, ty, rotation, scale), constrained similarity.

#### Overmix
No global camera model. `LinearAligner` least-squares: `a = (n·Σi·pos[i] − Σi·Σpos[i]) / (n·Σi² − (Σi)²)`, `b = (Σi²·Σpos[i] − Σi·Σi·pos[i]) / (n·Σi² − (Σi)²)`. Replaces positions with `a·i + b`. This is correct for uniform-speed scroll but cannot handle variable-speed scroll. `RecursiveAligner` achieves O(N log N) global consistency without explicit camera model.

#### ASP — `alignment/bundle_adjust.py`
**6-DOF affine BA** (or 4-DOF with `ASP_SIMILARITY_MODE=1`):
- Parameters: `[a, b, tx, c, d, ty]` per frame × N = 6N total (frame 0 pinned to identity).
- Residual function: for each edge (i→j) with observed displacement (dx_obs, dy_obs):
  ```
  M_ij = affines[j] · inv(affines[i])
  r_x = M_ij[0,2] − dx_obs
  r_y = M_ij[1,2] − dy_obs
  ```
- **GNC-TLS outer loop** (§1.17, Yang et al. 2020 "TEASER"):
  ```
  μ₀ = max(r²) / (2c²)   [c = GNC_CLAMP_SCALE = 10px]
  Geman-McClure weight: w_i = (μ·c² / (μ·c² + r_i²))²
  8 outer iterations; anneal: μ ← μ/1.4 each step
  Inner: scipy.least_squares(method='trf', loss='linear', f_scale=10.0)
  ```
  Tolerates 70-80% outlier edges.
- **Regularisers**: frame-0 anchor (weight=2000), identity prior on `a,d` (weight=1e5), shear prior on `b,c` (weight=1e5), StabStitch++ trajectory smoothness `λ·(tx[i]-2·tx[i-1]+tx[i-2])²`.
- **§1.1B spanning-tree pre-filter**: Kruskal max-weight spanning tree + BFS reference propagation `tx_ref[nbr] = tx_ref[curr] + dtx`. Reject edges where `sqrt((pred_dx−obs_dx)²+(pred_dy−obs_dy)²) > 50px`. Fallback if disconnected graph or <N-1 survivors.
- **§1.1D adaptive f_scale**: `_compute_adaptive_f_scale(edges, affines, floor)` → `max(floor, 2.0 × median_residual_px)`. Re-solve warm-started if `adaptive_scale > _BA_F_SCALE × 1.5`.

---

### Stage F: Bundle Adjustment / Global Position Refinement

#### OpenCV — `BundleAdjusterRay` / `BundleAdjusterAffinePartial`

**`BundleAdjusterRay`**:
Minimises angle between rays in 3D space. For matched keypoint pair (p_i in image i, p_j in image j):
```
r_ij = sqrt(f_i·f_j) × ||K_i^{-1}·p_i − R_i·R_j^T·K_j^{-1}·p_j||²
```
Numeric Jacobian with step=1e-3. `CvLevMarq` (Levenberg-Marquardt via OpenCV) handles the optimisation. Parameters: `[log(focal_i), log(aspect_i), ppx_i, ppy_i, rvec_i(3)]` = 7 per camera. Frame 0 pinned. Post-BA: `waveCorrect()`.

**`BundleAdjusterAffinePartial`** (SCANS):
Minimises pixel transfer error under 4-DOF similarity `H=[[a,-b,tx],[b,a,ty]]`. Parameters: `[a, b, tx, ty]` per frame = 4N total.

**`waveCorrect(rmats, mode)`**:
```
y_dirs = [R_i · [0,1,0] for R_i in rmats]  // camera "up" directions
SVD of sum(y_i · y_i^T) → [U, S, V^T]
if mode=HORIZ: correction axis = V^T[2] (dominant up direction)
else: correction axis = V^T[1]
R_correction = rodrigues(axis × [0,1,0])
rmats[i] = R_correction × rmats[i] for all i
```
Ensures the panorama is level (camera "up" vectors all point the same way). No translation-domain equivalent exists in OpenCV — ASP's §4.3 wave correction (`np.polyfit` on tx/ty) is the translation analogue.

#### Overmix
`RecursiveAligner::combine(repr_left, repr_right)`: finds offset between two composite representatives using the configured comparator. No formal BA. `LinearAligner` post-pass is the only global optimisation: LS fit removes systematic drift.

`IndependentAligner` is the closest to BA: Jacobi 10-iteration convergence on the over-determined pairwise system. But it operates on scalar (dx, dy) pairs, not on a parametric camera model.

#### ASP
See Stage E above for the GNC-TLS + LM system. After BA: **§4.3 wave correction**:
```python
if ptp(tx_list) > WAVE_CORRECT_MIN_TX_RANGE:
    trend = np.polyfit(range(N), tx_list, deg=1)
    tx_list -= np.polyval(trend, range(N)) - tx_list[0]  # anchor at frame 0
# Similarly for ty
```

**Affine validation** (Stage 7b): Checks span, monotonicity, max residual, canvas aspect, etc. 5-tier retry chain follows failed validation.

---

### Stage G: Wave Correction / Drift Removal

| System | Method | Math | Fires when |
|---|---|---|---|
| **OpenCV** | SVD of camera-y directions | `R_correction = rodrigues(dominant_up × [0,1,0])` | Always (post-BA) |
| **Overmix** | None | — | Never |
| **ASP §4.3** | `np.polyfit(deg=1)` on tx/ty | `tx -= trend(t) − tx[0]` | `ptp(tx) > WAVE_CORRECT_MIN_TX_RANGE` |

OpenCV's wave correction operates in 3D rotation space (corrects camera tilt in 3D). ASP's correction operates in 2D translation space (removes linear drift in the pixel-domain tx/ty sequence). Both are appropriate to their respective camera models.

---

### Stage H: Canvas Construction and Image Warping

#### OpenCV
Uses `RotationWarper` derivatives with full projection models. `SphericalWarper.warp(img, K, R, interp_mode, border_mode)` maps each output pixel `(u,v)` to input pixel via:
```
# Spherical: direction = R^T · K^{-1} · [u, v, 1]^T → normalize → project
# u_sphere = f · atan2(d[0], d[2]); v_sphere = f · atan2(-d[1], sqrt(d[0]²+d[2]²))
```
`buildMaps(src_size, K, R, scale, xmap, ymap)` pre-computes pixel remap tables for efficiency. Canvas size = bounding box of all warped image corners.

Seam estimation is done at `seam_est_resol_=0.1` (10% of original resolution) for speed; compositing is at full resolution.

#### Overmix
`SumPlane` with fractional position tracking. No explicit warp — each frame's pixel at position `(x,y)` contributes to canvas output pixel at `(x + offset_x, y + offset_y)` with sub-pixel interpolation via spacing/offset fields:
```cpp
// For sub-pixel SR mode (spacing < 1.0):
sum[iy + round(pos.y)][ix + round(pos.x)] += pixel × alpha
// FloatRender: spline kernel weight for fractional positions
w = spline(||(output_pos - input_pos_in_output_coords)||)  // B-spline B=1, C=0
```

#### ASP
`alignment/canvas.py` — `_compute_canvas(frames, affines, bg_masks)`:
1. Compute warped corners: for each frame i, apply affines[i] to all 4 corners.
2. Canvas bounds = `[min_x, max_x] × [min_y, max_y]` across all corners.
3. `T_global = -[min_x, min_y]` shift makes all coords positive.
4. Cap at `CANVAS_MAX_DIM` (memory protection).
5. **Midplane shift** (StabStitch++): shift all affines so reference frame sits at canvas midpoint, halving maximum per-frame distortion.
6. Gates: §1.53 canvas MB limit, §1.62 aspect ratio, §1.45 width ratio, §3.14 scroll axis.

Warp execution (`rendering/rendering.py`):
```python
for i, frame in enumerate(frames):
    warped = cv2.warpAffine(frame, affines[i][:2,:], (canvas_w, canvas_h),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    warped_frames.append(warped)
```
Integer affines only — no sub-pixel warp. This loses ~0.5px accuracy compared to Overmix's fractional positioning.

**Temporal median** (Stage 10): per-pixel median across non-zero frame contributions. Ghost-removes animated foreground character who appears at different positions in different frames. Neither OpenCV nor Overmix uses temporal median in the compositing pipeline (Overmix has `StatisticsRender::MEDIAN` but it's a separate render mode, not wired into the primary compositing path).

---

### Stage I: Seam Finding (the most critical stage for quality)

This is where the three systems diverge most dramatically in both approach and quality.

#### OpenCV — `seam_finders.cpp`

**`GraphCutSeamFinder("COST_COLOR_GRAD")`** — the production seam finder:

For each image pair (src, dst) with overlap region:
1. Build `GCGraph<float>` with `H_overlap × W_overlap + 2` nodes (pixels + source + sink).
2. **N-link weights** (pixel-to-pixel edges, horizontal and vertical):
   ```
   diff1 = ||img1[y,x] − img2[y,x]||₂   // colour difference at this pixel in both images
   diff2 = ||img1[y,x+1] − img2[y,x+1]||₂   // colour difference at right/down neighbour
   grad1 = |img1[y,x,0]−img1[y,x+1,0]| + ... // gradient in image 1 at this edge
   grad2 = |img2[y,x,0]−img2[y,x+1,0]| + ... // gradient in image 2
   weight = (diff1 + diff2) / (grad1 + grad2 + ε) + ε
   ```
   **Semantic**: high-gradient pixels are *cheap* to cut through (denominator large) — the seam prefers textured edges where a colour step is hidden by existing image structure. This is opposite to ASP's seam cost!
3. **Terminal weights** (pixel → source/sink):
   - Source (= keep image src): `terminal_cost_ = 10000.0` if pixel is in src's valid region only
   - Sink (= keep image dst): `terminal_cost_ = 10000.0` if pixel is in dst's valid region only
   - Both valid: `0.0` (seam can pass through freely)
   - `bad_region_penalty_ = 1000.0` added to N-link weights adjacent to masked-out pixels
4. `GCGraph::maxFlow()` — Boykov-Kolmogorov max-flow algorithm (polynomial time in practice, near-linear for image grids).
5. Min-cut → binary ownership mask (which frame owns each pixel).

**Critical property**: The seam can route in ANY 2D direction — up, down, left, right, diagonally. It can double back to avoid an obstacle. It is globally optimal for the energy functional.

**`DpSeamFinder("COLOR_GRAD")`** — lighter-weight DP alternative:
```cpp
for col = 0..W-1:
    cost[0][col] = color_grad_cost(0, col)
    for row = 1..H-1:
        cost[row][col] = color_grad_cost(row, col) + min(cost[row-1][col-1:col+2])
traceback: argmin from bottom → seam path
```
This operates on the full canvas DP table (not per-boundary zones). Globally consistent seam paths across all image boundaries simultaneously.

**`VoronoiSeamFinder`**: Distance transform (nearest-image-center assignment). No energy minimisation. O(N×canvas_area) but very fast.

#### Overmix — No seam finding
Overlap regions are pixel-averaged. There is no seam because:
1. Background pixels are pixel-identical across frames (same painted cel) → averaging produces no artifact.
2. For hold blocks: same cel → MAD ≈ 0 → pure noise cancellation.
3. When frames differ (different animation frame): `StatisticsRender::MEDIAN` rejects the minority-frame pixels.

This "works" for Overmix's domain because the sub-pixel shifts between frames of the same scene are so small (<2px) that averaging is perceptually equivalent to a perfect seam. For large displacements (different camera positions), Overmix would produce ghosting — but that is what `AnimationSeparator` prevents by grouping such pairs as different frames.

#### ASP — `rendering/compositing.py`

**`_build_seam_cost_map(zone_a, bg_mask_a, zone_b, bg_mask_b)`**:
```
Tier 0 (background):   cost = 0.0  [bg in both frames]
Tier 2 (edge buffer):  cost = 0.5  [§3.20: ring around fg interior; lowered from 1.0 at S19]
Tier 1 (fg interior):  cost = 1.0  [dilated fg mask intersection]
Column barrier:        cost = 2.0  [§3.15A: columns where >50% pixels are fg-interior]
Hard barrier:          cost = 1e6  [§3.15B: mesh barrier / ASP_SEAM_HARD_BARRIER=1]
Additive modifiers:
  §1.123 scatter cost: + box_filter(3×3 pixel variance, normalised × SCATTER_COST_WEIGHT)
  §3.17 HF seam cost:  + per-column Laplacian energy
  §1.125 transition:   + row_dist_from_midline × SEAM_TRANSITION_PEN
  §1.126 fg majority:  raise >80%-fg columns to FG_MAJORITY_FLOOR when zone >60% fg
Post-processing:
  §1.109 cost norm:   L∞ normalise soft region to [0,1] (preserve barriers)
  §1.110 Gaussian:    scipy.ndimage.gaussian_filter(sigma=COST_MAP_BLUR_SIGMA)
  §1.113 col smooth:  per-column 1D Gaussian (sigma=COST_COL_SMOOTH_SIGMA)
```

**`_seam_cut(fa_zone, fb_zone, sem_cost, waypoints, transition_penalty)`**:
```python
# Point cost at each (row, col):
cost[r,c] = (|fa[r,c] − fb[r,c]|_L2
             + 0.5 × |grad(|fa−fb|)[r,c]|
             + edge_weight × (|∇fa[r,c]| + |∇fb[r,c]|)
             + sem_cost_weight × sem_cost[r,c])
# Incorporate transition_penalty (§1.125):
mid_row = H // 2
cost += |row − mid_row| / max(|row − mid_row|.max(), 1) × transition_penalty

# Forward DP (S10 vectorisation):
dp = np.full((H, W), np.inf)
dp[0] = cost[0]
for c in range(1, W):
    dp[c] = cost[:,c] + scipy.ndimage.minimum_filter1d(dp[:,c-1], size=3, cval=np.inf)

# Traceback:
path = [np.argmin(dp[:,-1])]
for c in range(W-2, -1, -1):
    r = path[-1]
    path.append(r + np.argmin(dp[max(0,r-1):min(H,r+2), c]) - min(1, r))
path = path[::-1]
```

**Semantic note**: ASP's seam energy *penalises* high-gradient regions (the edge terms add cost). OpenCV's seam energy *rewards* high-gradient regions (gradient in denominator reduces cost). Both approaches correctly avoid seaming through character outlines in their respective contexts: OpenCV's approach prefers textured edges (where a colour discontinuity is visually hidden by existing texture); ASP's approach prefers background low-gradient regions (where a colour step is less likely to exist than at character outline edges).

**24 pre-DP escalation gates** — unique to ASP:

| Gate | Condition | Fires when |
|---|---|---|
| §1.70 | zone fg coverage | zone is fg-dominated |
| §1.60 | fg MAD pose gap | character in different pose |
| §1.34 | low texture | flat region (ARAP unreliable) |
| §1.86 | zone SSIM | zones structurally incompatible |
| §1.117 | fast zone NCC | thumbnail NCC pre-filter |
| §1.121 | hist intersection | colour histograms incompatible |
| §1.97 | entropy gap | one flat zone + one textured |
| §1.101 | full-zone MAD | bg colour differs |
| §1.30 | zone min height | too short for DP |
| §1.119 | zone width CV | uneven zone layout |
| §1.125 | seam transition | seam path too steep |
| §1.95 | SP thresh fg scale | heavy fg coverage |
| §1.102 | SP momentum | previous seam was SP |
| §1.18 | adaptive SP | wide feather + moderate diff |
| §1.112 | seam path drift | path drifts too far from expected |
| §1.122 | high path cost | mean DP cost exceeds threshold |
| §1.126 | fg majority | zone is >60% fg |

Each gate has an `ASP_*` env flag (most default OFF). When any gate fires, the system escalates to single-pose mode (pick dominant frame's content, apply soft-edge blend ±sp_soft_px).

---

### Stage J: Exposure Compensation and Gain Correction

#### OpenCV — `exposure_compensate.cpp`

**`BlocksGainCompensator(bl_width=32, bl_height=32, nr_feeds=1, nr_iterations=2)`**:

`feedWithStrategy(images, masks, corners, blksize)`:
1. For each image pair (i, j):
   - Divide both warped images into bl_width×bl_height blocks (in canvas space).
   - For each overlapping block at position (b_y, b_x):
     ```
     N_ij[b] = count of pixels in overlap
     I_ij[b] = mean pixel value of image i in overlap at block b
     I_ji[b] = mean pixel value of image j in overlap at block b
     ```
2. Build per-block linear system: for each block b independently:
   ```
   Minimize: Σ_pairs N_ij[b] × (g_i[b] × I_ij[b] − g_j[b] × I_ji[b])²
             subject to: Σ g_i[b] = N_images (anchor)
   ```
   Solved via Cholesky factorisation. Parameters: α=0.01 (overlap weight), β=100 (anchor weight).
3. Iterative Gaussian smoothing of gain map: `gain_map = boxFilter(gain_map, kernel=[0.25, 0.5, 0.25])^T × [0.25, 0.5, 0.25]` applied `nr_gain_filtering_iterations` times.

`apply(index, corner, image, mask)`: bilinear-resize gain_map to image size (`INTER_LINEAR`), multiply image channels by gain.

**`BlocksChannelsCompensator`**: 3 independent `GainCompensator` instances (B, G, R). Handles white-balance drift.

#### Overmix
None. See Stage B.

#### ASP — multi-tier gain pipeline
See Stage B for the pre-matching global scalar gain stages. Additional seam-zone compensation:

**§4.1 `_blocks_gain_compensate(fa_zone, fb_zone, block_size=32)`** (S160):
```python
for by in range(0, H, block_size):
    for bx in range(0, W, block_size):
        block_a = fa_zone[by:by+block_size, bx:bx+block_size]
        block_b = fb_zone[by:by+block_size, bx:bx+block_size]
        for c in range(3):
            gain = mean(block_a[...,c]) / max(mean(block_b[...,c]), 1e-3)
            gain = clip(gain, 0.5, 2.0)
            fb_zone[by:by+block_size, bx:bx+block_size, c] *= gain
gain_map = resize(gain_map, (H,W), INTER_LINEAR)  # bilinear upsampling
```
Applied in the `_fb_for_blend` chain at seam zone level (not globally). More targeted than OpenCV's global image-level application.

**§4.4 `_blocks_lum_compensate(fa_zone, fb_zone, block_size=32)`** (S160):
Uses LAB L-channel scalar per block (avoids colour cast from near-zero BGR channel means). Equivalent to `BlocksChannelsCompensator` on luma only.

**`_zone_lum_norm(fa_zone, fb_zone)`** (§1.104): equalises mean luminance of non-black bg pixels between zones using a gain clamped to `ZONE_LUM_NORM_GAIN_CLAMP=2.0`.

---

### Stage K: Blending / Compositing

#### OpenCV — `blenders.cpp` — `MultiBandBlender`

`feed(img, mask, tl)`:
- Builds Laplacian pyramid for `img`: `lap[l] = img_l − pyrUp(img_{l+1})`, base = `pyrDown^n(img)`.
- Builds Gaussian pyramid for `mask` (distance-transform-based weight map).
- Accumulates into `dst_pyr_laplace_` and `dst_band_weights_`:
  ```
  dst_pyr_laplace_[l] += lap[l] × weight_pyr[l]
  dst_band_weights_[l] += weight_pyr[l]
  ```

`blend(dst, dst_mask)`:
- Per pyramid level: `dst_pyr_laplace_[l] /= dst_band_weights_[l]` (normalise by total weight).
- `restoreImageFromLaplacePyr()`: `img = img_coarsest; for l down: img = pyrUp(img) + lap[l]`.
- CUDA path: `cuda::GpuMat` + `cuda::pyrDown`/`pyrUp`.
- OpenCL path: `multibandblend.cl` kernel.

`FeatherBlender`: `createWeightMap(mask, sharpness)` = `distanceTransform(mask)` × sharpness, clipped to [0,1]. Linear alpha blend: `dst = Σ(img_i × weight_i) / Σweight_i`.

#### Overmix
`AverageRender::render()`:
```cpp
SumPlane::addAlphaPlane(plane, alpha, pos, spacing, offset):
  for iy, ix: // sub-pixel SR mode: sample at fractional positions
    sum[iy + pos.y][ix + pos.x] += pixel × asDouble(alpha)
    count[iy + pos.y][ix + pos.x] += alpha
SumPlane::average():
  out[y][x] = sum[y][x] / (count[y][x] / WHITE) if count > 0 else BLACK
```
No frequency decomposition. Mitchell-filter rescaling at output.

`FloatRender` (genuine SR):
```cpp
for output pixel (ix, iy):
  for input image j with fractional position:
    for nearby input pixels (x_in, y_in) within ±2 output pixels:
      dist = ||(ix,iy) - (x_in+offset_j.x, y_in+offset_j.y)||₂
      w = cubic_bspline_B1C0(dist)  // B=1, C=0 cubic
      sum += pixel × w; weight += w
  out[iy][ix] = sum / weight
```
This is signal-theory super-resolution: B-spline (B=1,C=0) has smooth frequency response without ringing, support ±2 pixels.

`RobustSrRender` (L1-SR):
```
DHF matrix construction: for each LR pixel at (i/scale, j/scale) in HR coords:
  4 HR pixels via bilinear: weights (a0*b0, a1*b0, a0*b1, a1*b1)
  sparse DHF entry: DHF[lr_pixel, hr_pixel] = weight
L1 sub-gradient descent:
  x_hr -= β × sign(x_hr × DHF - x_lr) × DHF^T
```
Robust to JPEG block noise (L1 does not square residuals, so outliers have bounded influence).

#### ASP — `rendering/compositing.py` — `_composite_foreground()`

**Normal seam blend sequence** (per boundary k, non-single-pose):

1. **_fb_for_blend chain** (zone colour normalisation before DP):
   - `_zone_chroma_align(fa_zone, fb_zone)` (§3.19): LAB a/b mean shift to match fa. Min shift: `ZONE_CHROMA_ALIGN_MIN_SHIFT=2.0`.
   - `_zone_lum_norm(fa_zone, fb_zone)` (§1.104): luminance equalisation with gain clamp.
   - `_zone_sat_norm(fa_zone, fb_zone)` (§1.111): HSV saturation equalisation, gain clamp `ZONE_SAT_NORM_GAIN_CLAMP=2.0`.
   - `_zone_contrast_eq(fa_zone, fb_zone)` (§1.114): RMS contrast equalisation, clamp `ZONE_CONTRAST_EQ_CLAMP=2.0`.
   - `_zone_hue_eq(fa_zone, fb_zone)` (§1.127): circular mean HSV hue shift, threshold 5°, clamp ±30°.

2. **ARAP foreground registration** (`alignment/fg_register.py`):
   `register_foreground_at_seam(frame_a, frame_b, fg_mask_a, fg_mask_b, bg_mask_a, bg_mask_b)`:
   - Dense flow: SEA-RAFT (if CUDA) or `cv2.DISOpticalFlow.MEDIUM_preset` (CPU)
   - ARAP push: block matching to refine coarse flow
   - ARAP regularise (`_arap_regularise`): `||flow − smoothed||² + rigidity_weight × ||flow_xy||²`
   - LSD collinearity (§S8/S9): `createLineSegmentDetector().detect(seam_band_crop)` with canvas-space offset
   - SC-AOF taper: warp decays to zero away from seam
   - SLIC-SGM proxy (§3.1B, `ASP_SGM_PROXY=1`): superpixel centroid matching for flat regions
   - DINOv2 frame selection (§S8): choose which frame to use as flow reference

3. **`_seam_color_match(dom_zone, oth_zone, path_local, band_px)`** (S16):
   Per-channel mean shift of oth_zone to match dom_zone in blend band. band_px = sp_soft_px + 4.

4. **`_single_pose_soft_edge(dom_zone, oth_zone, path_local, apply_mask, sp_soft_px)`** (S15):
   ±6px linear ramp at DP seam. Max 50% blend at seam center, 0% at band edge. Only where both frames have fg content.

5. **Per-pixel DSFN ramp** (S17): `sim_diffused` from Gaussian blur of similarity field drives per-pixel blend width. High-sim → wide; low-sim → narrow. `sim_diffused[both_fg]=0.0` (S20) prevents bg-similarity diffusing into fg-vs-fg (would cause double-image ghost).

6. **`_laplacian_blend(fa_zone, fb_zone, path_local, feather, num_levels)`**:
   Standard N-band Laplacian pyramid on the 1D seam path. Weight mask from DSFN ramp + §1.108 alpha schedule (`mask**2` for fine levels when `ASP_LAPLACIAN_ALPHA_SCHEDULE=1`).

7. **`_poisson_seam_blend(fa_zone, fb_zone, path_local, apply_mask)`** (S21, `ASP_POISSON_SEAM=1`):
   `cv2.seamlessClone(NORMAL_CLONE)` in ±20px band. Gradient-domain: minimises `||∇out − ∇fb||²` with Dirichlet boundary. Zero brightness step. Falls back to hard partition on `cv2.error`.

**Single-pose escalation** (when any gate fires or `post_warp_diff > SP_threshold`):
- Pick dominant frame (more fg pixels, or ref-proximity §1.103)
- Copy dominant zone as-is
- Apply `_single_pose_soft_edge` ±sp_soft_px
- §1.124 `_ADAPTIVE_SP_SOFT`: narrow to 3px if post_warp_diff >30, wide to 10px if <10
- `ASP_TOONCRAFTER_SEAM=1`: ToonCrafter synthesis for worst single-pose seam

---

### Stage L: Foreground / Semantic Layer Handling

**OpenCV**: None. All content treated equally. If the character appears in the overlap region, it will be blend at the seam position, creating a double-image ghost. No mechanism to detect or handle animated foreground.

**Overmix**: `StatisticsRender::MEDIAN` handles transient fg elements: if the character appears in only 1 of N frames at a given canvas pixel, the median over N frames will be the character-free value (background). This works when N ≥ 3 and the character covers <50% of frames at any given position. For N=2 frames, the median is not defined (it equals the mean), so ghosting still occurs.

`FocusStackingRender` selects the sharpest frame per-pixel, which can implicitly choose the most-character-free frame in some configurations.

**ASP**: The only system with explicit fg/bg decomposition:

1. **BiRefNet** (`ingestion/masking.py`): Deep learning matting model. Per-frame `bg_masks[i]` (255=bg, 0=fg). Optional SAM2 refinement. Used at every subsequent stage.

2. **Background-only matching**: LoFTR + phase correlation keypoints filtered to `bg_masks`. Character's animation displacement is excluded from the camera displacement estimate.

3. **Semantic cost map** (`_build_seam_cost_map`): fg interior gets cost=1.0, fg-dominated columns get cost=2.0 or hard barrier=1e6. The DP seam is steered away from the character.

4. **ARAP fg registration** (`alignment/fg_register.py`): At each seam boundary, computes a dense flow field for the fg region specifically, allowing ARAP to warp the character into a coherent pose at the seam. This is the most sophisticated fg-handling in any of the three systems.

5. **Single-pose escalation**: When ARAP fails (pose gap too large), picks the dominant frame's fg content rather than blending incompatible poses into a ghost.

6. **Temporal median** (Stage 10): Ghost-removes the character from the background canvas. The character's temporal median (across many frames) is background pixels — the animated character appears at only a fraction of canvas rows in any given frame.

7. **RLHF quality model** (`rlhf/reward_model.py`): `StitchRewardModel.predict(img_bgr)` — learned quality score that can detect fg-related artifacts.

---

### Stage M: Post-processing, QA, and Fallback Logic

**OpenCV**: `Stitcher` status codes (`OK=0, ERR_NEED_MORE_IMGS, ERR_HOMOGRAPHY_EST_FAIL, ERR_CAMERA_PARAMS_ADJUST_FAIL`). No automatic fallback — the pipeline fails and returns a status code. Wave correction and inner/outer ROI crop are the only automatic post-processing steps.

**Overmix**: Interactive — user can inspect output and re-run with different settings. `LinearAligner` post-pass removes drift. No automated quality metrics.

**ASP**: Extensive automated QA:

**Pre-composite gates** (Stage 10.8-10.9):
- §1.71 bg luma spread gate: high spread → SCANS
- §1.73 bg monotonicity gate: non-monotone bg → SCANS

**Seam-level gates** (after each `_seam_cut`):
- §1.112 path drift gate: consecutive path jump > `SEAM_DRIFT_THRESH`
- §1.69 DP bg ratio: path predominantly on fg → escalate
- §1.122 high path cost: mean cost > `HIGH_PATH_COST_THRESH`

**Post-composite audit** (after all seams composited):
15 quality metrics — Bhattacharyya colour similarity (§1.14B/C), absolute luma step (§1.24), NCC structural coherence (§1.66), entropy variation (§1.72), canvas fill ratio (§1.74), strip variance ratio (§1.75), per-column luma-step max (§1.76), saturation step (§1.77), hue step (§1.78), sharpness (§1.79), gradient direction coherence (§1.80), SSIM (§1.81), frequency profile (§1.82), noise asymmetry (§1.83), RMS contrast ratio (§1.84), ensemble combiner (§1.85).

**Benchmark metrics** (`bench_anime_stitch.py`):
- `strip_banding_score`: max row-wise luminance variance across strip transitions
- `ghosting_score`: FFT autocorrelation secondary peak (double-edge signature)
- `ghosting_siqe` (`_ghosting_score_v2`): column-mean gradient-magnitude autocorrelation
- `seam_visibility_score`: worst-case adjacent-row luminance jump
- `_compute_aligned_ssim()`: ECC EUCLIDEAN alignment + SSIM vs GT (200 iterations, 1e-4 convergence)
- `strip_self_ssim` (§3.30): per-strip top/bottom half NCC consistency
- `zone_coverage_fraction` (§3.29): total blend zone height / H
- `canvas_gain_uniformity` (§3.31): strip-wise luminance coefficient of variation
- `_compute_rlhf_score()`: reward model inference (random weights until feedback collected)

---

### Stage N: Super-Resolution

**OpenCV**: No SR in the stitching module. The output is at compose_resol_ (default: full resolution of input).

**Overmix**: This is Overmix's primary differentiator. Three SR paths:
1. **`FloatRender` with fractional positions**: B-spline kernel reconstruction. When images have sub-pixel offsets (from MPEG noise or scanning jitter), each image contributes information at different output grid positions. True SR by Papoulis-Gerchberg principle.
2. **`RobustSrRender`**: Eigen sparse DHF + L1 sub-gradient. Models the full degradation pipeline (downsampling + blur) as a matrix equation and inverts it with L1 regularisation. Most principled but slowest.
3. **`Waifu` (waifu2x)**: Neural SR for individual frames. `processYuv()` upscales luma only; chroma upsampled separately. `denoise` parameter (0-3) controls denoising level. The only ML component in Overmix.

`SuperResAligner` workflow: render initial SR estimate → re-align individual frames against SR result at HR resolution → update sub-pixel positions → re-render. Iterative refinement.

**ASP**: `mfsr/` subdirectory:
- `super_resolution.py`: main SR dispatcher
- `dct_restoration.py`: DCT-domain noise reduction
- `diffusion_inpaint.py`: diffusion-based background completion
- `drl_registration.py`: deep RL sub-pixel registration
- `pso_registration.py`: Particle Swarm Optimisation sub-pixel registration
- `prior_injection.py`: prior injection for SR diffusion

SR is optional (behind flags) and separate from the compositing pipeline. Not integrated into the core seam-finding/blending loop (unlike Overmix where SR is the primary purpose).

`SRStitcher` (`rendering/sr_stitcher.py`): diffusion-based seam inpainting — specifically targets residual seam artifacts rather than general SR.

---

## Part IV — Algorithmic Deep Dives

### 4.1 Seam Finding: 1D DP vs 2D Graph-Cut vs No-Seam

**The dimensionality difference is the most important algorithmic gap between ASP and OpenCV.**

**OpenCV `GraphCutSeamFinder`** — 2D global optimisation:
- The seam is a 2D **cut** in the image graph (a closed curve in 2D, not a 1D path).
- It can route in any direction: left, right, up, down, diagonally. It can double back around an obstacle.
- Energy: `E = Σ_cut_edges (colour_diff²/gradient_mag) + Σ_terminal `
- The BK max-flow algorithm solves this in polynomial time. For image grids, near-linear in practice.
- **For N images**: the seam between images i and i+1 is computed in the *same graph* as the seam between i+1 and i+2. The seams are globally consistent — the same background corridor is not claimed by two different seams.

**ASP `_seam_cut()`** — 1D monotone DP:
- The seam is a 1D **path**: one y-position for each x-column (or one x-position for each y-row in horizontal mode).
- It can only move ±1 row per column step. It cannot double back.
- Energy: per-pixel cost at each (row, col), plus 3-neighbor transition (left→up, straight, left→down).
- Each boundary k is solved independently. The seam for boundary k=1 does not know about the seam for boundary k=2 — they may both route through the same background corridor.
- **This is the root cause of the ghosting failures**: two pairwise seams competing for the same background pixels produce interference patterns (the strip transitions are visible because the seam paths for adjacent boundaries conflict).

**Proposed fix**: Replace `_seam_cut` with `cv2.detail_GraphCutSeamFinder("COST_COLOR_GRAD")` applied to the full canvas after Stage 10. The fg semantic cost can be incorporated as modified terminal weights:
```python
finder = cv2.detail_GraphCutSeamFinder(cv2.detail.GraphCutSeamFinder_COST_COLOR_GRAD)
# Build label masks (which frame "owns" each pixel before seam)
# Build overlap images (warped frames in canvas space) 
# Incorporate fg_cost via modified image values (inflate fg pixel values)
finder.find(warped_images, corners, seam_masks)
# seam_masks: per-image binary ownership
```
The fg cost map cannot be directly injected into `cv2.detail_GraphCutSeamFinder`'s internal energy — but the terminal weights can be modified by pre-inflating pixel values in fg regions (higher colour difference → higher cut cost → seam avoids fg). Or: use PyMaxflow for a custom implementation that accepts `sem_cost` as an additive terminal weight.

**Overmix — no seam**:
The "null seam" approach is optimal when the content is identical across frames (hold blocks) and becomes progressively worse as content diverges. For N frames of the same background, `AverageRender` achieves SNR = √N improvement over any single frame — no seam algorithm can match this. The constraint is that it requires content identity.

### 4.2 Blending: Laplacian+DSFN vs MultiBandBlender vs AverageRender/FloatRender

**OpenCV `MultiBandBlender`** accumulates *all* images simultaneously into a shared Laplacian pyramid. The weight masks are distance-transform ramps (widest in the image interior, narrowing to 0 at edges). Each pyramid level's blend is:
```
output_lap[l] = Σ_i (input_lap_i[l] × weight_i[l]) / Σ_i weight_i[l]
```
High-frequency details (fine pyramid levels) are blended over a narrow zone (sharp seam); low-frequency content (coarse levels) is blended over a wider zone (smooth gradient). This is the classic frequency-separation blending strategy.

**ASP `_laplacian_blend()`** applies the same pyramid algorithm but:
1. **Pairwise** (only two images at a time), not simultaneously over all N.
2. **1D seam path** constrains where the blend zone falls.
3. **DSFN weight mask** (similarity-diffused) replaces distance-transform ramps — high-similarity regions get wide blends, low-similarity regions get narrow.
4. **§1.108 alpha schedule**: fine pyramid levels use `weight**2` (sharpened masks) — reduces high-frequency colour bleeding at character outline edges.

The DSFN ramp is ASP's primary innovation in blending: by tying blend width to photometric similarity, ASP adaptively narrows the blend zone where the two frames disagree (avoiding ghosting from blending incompatible content) and widens it where they agree (producing smooth transitions). OpenCV's distance-transform ramp is spatially uniform — it blends the same way regardless of how similar the overlapping frames are.

**Overmix `FloatRender` / `AverageRender`**: No explicit blend zone. The B-spline kernel at each output pixel integrates all contributing input pixels within ±2 output pixels. For SR upsampling (scale > 1), this is the correct interpolation. For panorama compositing where frames have significant content differences, the B-spline kernel would produce ghosting — Overmix avoids this by ensuring frames in the same render group are from the same animation frame (via `AnimationSeparator`).

### 4.3 Exposure Compensation: Per-frame scalar vs BlocksGainCompensator(32×32) vs None

**OpenCV `BlocksGainCompensator`** solves for spatially-varying gain within each image at 32×32 block resolution. The key property is the **joint linear system**: all images and all blocks are optimised simultaneously. The gain of block (b_x, b_y) in image i is tied to the gain of the overlapping block in image j by the pairwise overlap constraint. After solving, Gaussian smoothing removes block boundary discontinuities.

Mathematical constraint per block b:
```
Minimize Σ_{pairs (i,j)} N_ij[b] × (g_i[b] × μ_ij[b] − g_j[b] × μ_ji[b])²
```
where `μ_ij[b]` = mean of image i's pixels in the overlap region at block b, `N_ij[b]` = pixel count.

This is a linear system in the gain variables `g_i[b]`. For each block b, the Cholesky factorisation solves it in O((N_images)³/3) ≈ milliseconds for typical N.

**ASP `_blocks_gain_compensate()`** (§4.1, S160) solves the same problem but per-seam-zone independently (not jointly across all images). This means the gain correction for seam k is not aware of the gain correction for seam k+1 — inconsistencies between adjacent seam zones can still produce visible steps. Full equivalence to OpenCV requires a canvas-space joint block gain solve.

**Root cause of strip_banding_score failure (97.9%)**: ASP's Stage 4.5 global scalar gain is per-frame (one number per frame) and cannot correct spatial within-frame variation. Phone screens have non-uniform illumination (vignetting, panel-edge brightening), and anime panels have varying contrast levels from the character's colour palette. The OpenCV `BlocksGainCompensator` addresses both by computing per-block gains that vary across the image.

### 4.4 Bundle Adjustment: LM pixel-space vs BundleAdjusterRay (unit sphere) vs Jacobi LS

**OpenCV `BundleAdjusterRay`**:
- Projects feature correspondences to unit sphere rays: `ray_i = K_i^{-1} · p_i / ||K_i^{-1} · p_i||`.
- Residual: `r_ij = sqrt(f_i · f_j) × ||ray_i − R_i · R_j^{-1} · ray_j||²`.
- Unit-sphere normalisation removes scale ambiguity inherent in pixel-domain reprojection error.
- `CvLevMarq`: gradient = -J^T·r; Hessian approximation = J^T·J; update = (J^T·J + λI)^{-1}·(-J^T·r).
- Numeric Jacobian (finite differences at step=1e-3).

**ASP GNC-TLS + LM**:
- Parameters: 6N affine DOF (or 4N with similarity constraint).
- Residual: `r = M_ij[0:2,2] − [dx_obs, dy_obs]` (transfer error in translation components).
- GNC outer loop re-weights residuals by Geman-McClure: `w_i = (μc²/(μc²+r_i²))²`.
- Inner LM: `scipy.least_squares(method='trf', loss='linear')` — efficient Trust Region Reflective.
- **Robustness comparison**: GNC-TLS tolerates 70-80% outlier edges; OpenCV's Huber-like loss (in `CvLevMarq`) tolerates ~30%. For anime with many failed LoFTR matches, GNC-TLS is essential.

**Overmix Jacobi convergence** (IndependentAligner):
- Not formal BA. Jacobi iterations: `pos[i] ← mean of {cached_offset(j,i) + pos[j]}`.
- Converges to least-squares solution of pairwise constraint system.
- No robustness against outlier matches (all cached offsets contribute equally).
- O(I × N × range) where I=10 Jacobi iterations.

### 4.5 Sub-pixel Alignment and Super-Resolution

**Overmix `FloatRender`**:
Genuine sub-pixel SR via B-spline kernel reconstruction. Signal-theory basis: if N images of the same scene are offset by sub-pixel amounts `δx_i, δy_i`, and these offsets are diverse (not all the same), then the N images collectively sample the scene at a finer grid than any individual image. The B-spline kernel reconstruction at the fine grid recovers the higher-resolution signal. This is the Papoulis-Gerchberg theorem applied to image upsampling.

For anime: MPEG compression introduces sub-pixel phase offsets at the 4:2:0 chroma grid boundary. Hold blocks of 2-3 frames each have sub-pixel offsets from MPEG motion compensation noise. After sub-pixel alignment and B-spline reconstruction, the output exceeds individual-frame quality.

**ASP ECC sub-pixel refinement** (Stage 8, `alignment/ecc.py`):
`cv2.findTransformECC(template, src, warp, MOTION_AFFINE, criteria=(200, 1e-5))` — ECC (Enhanced Correlation Coefficient) maximisation under affine warp model. Sub-pixel accurate but only refines the global affine — does not recover SR information from multiple frames.

**ASP SEA-RAFT** (Stage 8): Dense optical flow sub-pixel refinement. Refines individual frame warp but no SR.

**OpenCV**: Integer warps (`cv2.remap`, `warpAffine` at INTER_LINEAR). No sub-pixel SR.

### 4.6 Foreground/Background Semantic Decomposition

**ASP** is the only system that performs fg/bg decomposition:

The mathematical model: `T_total(x,y) = T_camera + A_animation(x,y)` where `T_camera` is a global rigid (affine) shift and `A_animation(x,y)` is a spatially-varying flow field from character articulation.

Stage 4 (BiRefNet) estimates the binary fg/bg mask `M_fg(x,y) ∈ {0,1}`.

Phase correlation estimate: `T_camera = argmax FFT^{-1}(FFT(bg_I_1 × (1−M_fg1)) × conj(FFT(bg_I_2 × (1−M_fg2))))`.

ARAP fg registration: `A_animation = ARAP_regularise(RAFT_flow(fg_zone_1, fg_zone_2))` where the flow is constrained to be as-rigid-as-possible while matching the optical flow.

**OpenCV**: No decomposition. If the character is in the overlap region of two images, the seam bisects the character. The GraphCut energy minimises the visible discontinuity at the seam but does not prevent the character from being split. For anime, where the character changes pose between adjacent frames, this produces a double-image ghost wherever the seam crosses the character.

**Overmix**: `StatisticsRender::MEDIAN` effectively separates "persistent content" (background that appears in most frames) from "transient content" (character that appears in a minority of frames at any given canvas position). The median over N frames rejects the character when N ≥ 3 and the character occupies <50% of frames at any canvas position. This is an implicit fg/bg separation that requires many overlapping frames — less robust than ASP's explicit BiRefNet segmentation.

### 4.7 Retry and Fallback Logic

**OpenCV**: Single-pass pipeline. Status codes only. If bundle adjustment fails to converge (`ERR_CAMERA_PARAMS_ADJUST_FAIL`), the pipeline returns failure with no output. No automatic fallback strategy.

**Overmix**: GUI-based. The user observes poor alignment and manually adjusts comparator parameters, or switches from `GradientComparator` to `MultiScaleComparator`, or adds a `LinearAligner` post-pass. No automated retry.

**ASP**: 5-tier automated retry + 2 fallbacks + per-stage gates:

```
Initial BA → _validate_affines → FAIL
  Retry 0: §2.9C filter to high-conf edges (weight≥0.65, N-1 edges min)
    → re-BA → re-validate → FAIL
  Retry 1: adjacent-only (drop all skip-pair edges)
    → re-BA → re-validate → FAIL
  Retry 2: sequential greedy 3-pass (forward/backward/cross)
    → re-validate → FAIL
  Retry 3: §0.5C adaptive min_step=20px floor
    → re-BA → re-validate → FAIL
  Retry 4: min_step=3.0, max_ratio=10.0 (very relaxed)
    → re-validate → FAIL
  Retry 5: min_step=0.5, max_ratio=50.0 (near-degenerate acceptance)
    → re-validate → FAIL
  → _panorama_stitch_fallback (cv2.Stitcher PANORAMA mode, uses GraphCut+MultiBand internally)
    → FAIL
  → _scan_stitch_fallback (direct np.vstack)
```

Per-stage early exits: §1.29 static input gate, §1.37 bg coverage gate, §1.44 max adjacent gap, §1.45 canvas width ratio, §3.14 scroll axis detection, §1.53 canvas MB, §1.62 canvas aspect, §0 multi-frame coverage.

---

## Part V — Capability Matrix

| Capability | OpenCV PANORAMA | OpenCV SCANS | Overmix | ASP |
|---|---|---|---|---|
| **Target domain** | Rotating camera, natural photos | Translating scanner | Anime screenshots (super-res) | Anime vertical scroll video |
| **Texture requirement** | High (SIFT) | High (SIFT) | None (pixel diff) | Low (LoFTR + phase corr) |
| **Feature matching** | SIFT/ORB sparse keypoints | SIFT sparse | Raw pixel MAD/L2 | LoFTR → ALIKED → PC → Segment → RoMa |
| **fg/bg separation** | None | None | Implicit (median filter) | Explicit (BiRefNet deep seg) |
| **Hold block detection** | None | None | AnimationSeparator (automatic) | MAD + dHash (automatic) |
| **Sub-pixel alignment** | No (integer warp) | No | Yes (SumPlane + FloatRender) | Partial (ECC, SEA-RAFT) |
| **Camera model** | Full projective (8-DOF) | 4-DOF similarity | 2-DOF translation | 2-DOF or 4-DOF similarity |
| **Bundle adjustment** | LM 7N DOF (ray space) | LM 4N DOF | None / Jacobi LS | GNC-TLS + LM (4N or 6N) |
| **Wave correction** | Yes (SVD rotation matrices) | No | No | Partial (polyfit linear tx/ty) |
| **Warping model** | Cylindrical/Spherical/Affine | Affine 4-DOF | Translation only (sub-pixel) | Affine (integer pixels) |
| **Seam finding type** | GraphCut 2D global | GraphCut 2D global | None (pixel average) | 1D DP pairwise |
| **Seam fg/bg cost** | None | None | N/A | 5-tier semantic cost map |
| **Exposure compensation** | BlocksGainCompensator (32×32) | None (SCANS default) | None | Global scalar + blocks (§4.1) + CDF LUT |
| **Blending** | MultiBandBlender (simultaneous) | MultiBandBlender | AverageRender / FloatRender | Laplacian+DSFN+Poisson (pairwise) |
| **Temporal rendering** | No | No | Median / Average render | Temporal median (Stage 10) |
| **ARAP fg registration** | No | No | No | Yes (SEA-RAFT/DIS + ARAP) |
| **Retry/fallback logic** | Status codes only | Status codes only | Interactive only | 5 tiers + PANORAMA + SCANS |
| **HITL** | No | No | Interactive UI | hitl/ module (ARAP arrows, SAM2, MLLM) |
| **RLHF** | No | No | No | rlhf/ module (reward model) |
| **Super-resolution** | No | No | FloatRender + RobustSr + Waifu | mfsr/ module (separate) |
| **Benchmark QA metrics** | None | None | None | 15 automated metrics + 96-test suite |
| **GPU support** | CUDA + OpenCL (UMat) | CUDA + OpenCL | WebGPU (newer) | Optional CUDA (RAFT, LoFTR) |
| **Language** | C++ (Python bindings) | C++ | C++/Qt5 | Python 3.11 + Rust core |
| **Approx LOC (stitching core)** | ~8,000 | ~8,000 | ~12,000 | ~20,000 |

---

## Part VI — Root Cause Analysis: Why ASP Loses to Simple Stitch

Benchmark: 97 tests, S142 ASP baseline vs `cv2.Stitcher_create(SCANS).stitch(frames)` simple stitch.

### Failure 1: strip_banding_score — 97.9% of tests worse (+25.4 lum units)

**What `strip_banding_score` measures**: Maximum luminance discontinuity at frame-strip transitions in the output panorama. Simple stitch (`np.vstack(frames)`) scores 0.0 by construction — no blending means no luminance step from blending.

**Root cause (primary)**: ASP's Stage 4.5 per-frame scalar gain cannot correct spatially-varying illumination within a frame. When the phone screen has non-uniform brightness (common: center brighter by 5-15%), frames at different vertical positions have different spatial luminance profiles. After scalar gain correction (which equalises the mean), the per-position luminance still differs — producing a visible step at the strip boundary.

**Root cause (secondary)**: ASP's pairwise Laplacian blend attempts to smooth the colour step, but the DSFN weight mask is driven by photometric similarity — when frames have substantial spatially-varying difference, the similarity is low, the blend zone narrows, and the hard-cut edge becomes more visible rather than less.

**Gap**: OpenCV's `BlocksGainCompensator(32,32)` corrects this at block level with iterative Gaussian smoothing. ASP §4.1 `_blocks_gain_compensate()` (S160) is functionally equivalent but: (a) applied per-seam-zone only (not globally), (b) not joint across all images (each zone solved independently). Full fix requires a canvas-space joint block gain solve before compositing.

**Recommended fix priority**: §4.1 blocks gain as default (not flag-gated) + extend to canvas-space joint solve.

### Failure 2: ghosting_score — 93.8% of tests worse (+11.7)

**What `ghosting_score` measures**: Double-edge signature detected via FFT autocorrelation of column-mean gradient-magnitude profile. A secondary peak at lag D = repeated gradient = character appearing at two different vertical positions (one from each contributing frame).

**Root cause (primary)**: Pairwise DP seams for adjacent boundaries k=1 and k=2 are solved independently. Both seams may route through the same background corridor — when strip 2's seam is positioned near strip 1's seam, the blend zones overlap. The character from strip 1 and the character from strip 2 are both partially visible, creating a double-image.

**Root cause (secondary)**: ARAP fg registration fails when the character's pose changes substantially between frames. Single-pose escalation prevents ghosting when it fires, but the pre-escalation gates (24 of them, most OFF by default) may not detect all pose-gap cases.

**Gap**: OpenCV's `GraphCutSeamFinder` solves seams for all image pairs jointly. Seam k=1 and k=2 compete for the same background pixels in a single global energy minimisation — they cannot both route through the same corridor because the min-cut allocates each pixel to exactly one image.

**Recommended fix priority**: §4.2 `cv2.detail_GraphCutSeamFinder("COST_COLOR_GRAD")` — the highest-impact single change possible.

### Failure 3: seam_visibility — 88.5% of tests worse (+19.4)

**What `seam_visibility_score` measures**: No-reference worst-case adjacent-row luminance jump. Simple stitch scores ~4.0 (the natural luminance variation between adjacent rows in a single frame). ASP scores ~23.4.

**Root cause**: Same as ghosting failure — pairwise DP seams produce visible colour steps at strip boundaries because:
1. The blend zone is too narrow (low similarity → narrow DSFN zone → sharp transition).
2. The seam path passes through fg-interior pixels despite the cost map (when all columns are fg-dominated).
3. The blocks gain compensation is not default-ON, so exposure differences at the seam are not corrected before blending.

**Recommended fix priority**: (1) §4.2 GraphCut seam, (2) §4.1 blocks gain as default, (3) §1.6C Poisson blend as default (currently flag-gated).

---

## Part VII — Improvement Roadmap (OpenCV/Overmix-informed)

Ranked by expected benchmark impact and implementation complexity.

### Priority 1: §4.2 GraphCut Global Seam Finder

**Target metrics**: ghosting_score (−11.7 gap), seam_visibility (−19.4 gap)
**Source**: OpenCV `GraphCutSeamFinder` (`seam_finders.cpp` lines ~350-440)

**What OpenCV does**: `GCGraph<float>` s-t max-flow over the full overlap ROI. N-link weight = `(colour_diff / gradient_mag) + ε`. Terminal weight = `10000` for single-image pixels. Solves globally across all image pairs.

**ASP implementation path**:
```python
# Option A: cv2.detail_GraphCutSeamFinder (if wrappable with custom costs)
finder = cv2.detail_GraphCutSeamFinder(cv2.detail.GraphCutSeamFinder_COST_COLOR_GRAD)
finder.find(warped_images, corners, label_masks)
# warped_images: List[np.ndarray] of all warped frames in canvas space (from Stage 10)
# corners: List[(x, y)] — top-left corner of each warped frame in canvas
# label_masks: binary per-image ownership masks (initialised to rectangular coverage)
# After find(): label_masks updated with globally optimal seam

# Option B: PyMaxflow custom graph (allows injecting fg semantic cost)
import maxflow
g = maxflow.Graph[float](H*W, H*W*2)
nodes = g.add_nodes(H*W)
# Add terminal edges weighted by bg_mask (fg pixels → high source weight)
# Add N-link edges weighted by colour+gradient cost + sem_cost
g.maxflow()
# Extract ownership from node labels
```

**Integration point**: Replace `_find_optimal_boundaries() + _seam_cut()` in `_composite_foreground()`. The GraphCut produces direct ownership masks (which frame owns each pixel) rather than a 1D path — the rendering loop needs to read from the ownership mask rather than the DP path.

**Expected impact**: Eliminates pairwise seam conflicts. Expected 20-40% reduction in ghosting_score and seam_visibility.

### Priority 2: §3.12A Hold-Block Sub-Pixel Averaging (default ON)

**Target metrics**: sharpness (already ASP-advantage), ghosting (indirectly via better bg quality)
**Source**: Overmix `AverageRender` + `AnimationSeparator` + `FloatRender`

**What Overmix does**: ECC-align all frames within each hold block; `AverageRender` produces `Σ(pixel × alpha) / Σalpha`. √N noise reduction.

**ASP implementation path**:
In `ingestion/frame_selection.py` → `smart_select_frames()`, after hold detection (step 1b):
```python
if ASP_HOLD_AVERAGE:  # make default True
    for hold_group in hold_groups:
        if len(hold_group) >= 2:
            # ECC sub-pixel align frames within group
            ref = hold_group[0]
            aligned = [cv2.findTransformECC(ref_gray, frame_gray, ...)]
            # Average aligned frames
            avg = np.mean([cv2.warpAffine(f, M, ...) for f, M in zip(hold_group, aligned)], axis=0)
            # Replace hold group with averaged frame
            select_from_hold = [avg]
```

**Expected impact**: √N SNR improvement within hold blocks. For 3-frame holds: √3 ≈ 1.73× noise reduction. Directly reduces the MPEG quantisation noise that drives false alarm rates in ARAP fg registration.

### Priority 3: §4.5 DpSeamFinder on Full Canvas

**Target metrics**: seam_visibility (−19.4 gap), ghosting (partial)
**Source**: OpenCV `DpSeamFinder` (`seam_finders.cpp`)

**What OpenCV does**: DP over the full canvas DP table simultaneously (not per-boundary). Each boundary's seam is aware of all other boundaries' paths.

**ASP implementation path**:
```python
finder = cv2.detail_DpSeamFinder("COLOR_GRAD")
finder.find(warped_images, corners, label_masks)
```
Lower memory overhead than GraphCut. Does not provide global optimality guarantee but provides global consistency (seams for k=1 and k=2 share the same DP table).

**Expected impact**: Moderate reduction in ghosting/seam_visibility from eliminated pairwise conflicts. Less effective than GraphCut (DP is still constrained to monotone paths) but zero new dependencies.

### Priority 4: §4.1 Blocks Gain Compensation as Default

**Target metrics**: strip_banding_score (−25.4 gap)
**Source**: OpenCV `BlocksGainCompensator` (`exposure_compensate.cpp`)

**What OpenCV does**: 32×32 block joint gain solve + iterative Gaussian smoothing.

**ASP action**: `_blocks_gain_compensate()` (§4.1) and `_blocks_lum_compensate()` (§4.4) already exist from S160. Change `_BLOCKS_GAIN_COMP` and `_BLOCKS_LUM_COMP` default from `"0"` to `"1"`. Tune `block_size=32` and add smoothing iterations equivalent to OpenCV's `[0.25, 0.5, 0.25]` kernel.

Additionally: move the block gain solve from per-seam-zone to canvas-space joint solve (process all warped frames simultaneously in canvas space), matching OpenCV's global approach.

**Expected impact**: Primary fix for strip_banding_score. Expected 30-50% reduction in banding.

### Priority 5: §4.6 MultiBandBlender Confidence Weighting

**Target metrics**: strip_banding_score (secondary)
**Source**: OpenCV `MultiBandBlender`

**What OpenCV does**: `feed(img, mask, tl)` accumulates all images simultaneously. The `mask` encodes seam confidence (derived from the seam finder's ownership mask + distance transform).

**ASP implementation path**:
In `_laplacian_blend()`, replace per-level weight mask from DSFN with a confidence-weighted mask:
```python
confidence = compute_confidence(seam_path, bg_mask_a, bg_mask_b, ecc_residuals)
# confidence ∈ [0,1] per pixel; high = reliable blend; low = uncertain
# Blend with: out = (fa × conf_a + fb × conf_b) / (conf_a + conf_b)
```
Alternatively, wire `cv2.detail_MultiBandBlender`:
```python
blender = cv2.detail_MultiBandBlender(num_bands=5)
blender.prepare(canvas_roi)
for i, (warped, mask, corner) in enumerate(zip(warped_images, seam_masks, corners)):
    blender.feed(warped.astype(np.int16), mask, corner)
blender.blend(result, result_mask)
```

### Priority 6: Log-Polar Rotation Estimation (Pre-Matching)

**Target metrics**: Tests where phone rotates during scroll (currently produces alignment failure → SCANS fallback)
**Source**: Overmix `LogPolarComparator` (partially implemented — transform exists)

**ASP implementation path**:
```python
# In _pairwise_match() before LoFTR attempt:
lp_a = cv2.logPolar(img_a_gray, center_a, M, cv2.INTER_LINEAR)
lp_b = cv2.logPolar(img_b_gray, center_b, M, cv2.INTER_LINEAR)
shift, response = cv2.phaseCorrelate(lp_a.astype(np.float32), lp_b.astype(np.float32))
rotation_deg = shift[1] * 360 / lp_a.shape[0]  # log-polar → rotation
scale_ratio = np.exp(shift[0] * np.log(M) / lp_a.shape[1])  # log-polar → scale
# If |rotation_deg| > 1.0: pre-rotate img_b before matching cascade
```

### Priority 7: Sub-Pixel Phase Correlation (No Integer Rounding)

**Target metrics**: sharpness (already ASP-best, marginal improvement)
**Source**: `cv2.phaseCorrelate()` returns float shift natively

**ASP action**: In `alignment/matching.py` → `_phase_correlate()`, do not round `shift` to integer before storing in the edge dict. Propagate float displacement through BA. In `alignment/canvas.py`, use `cv2.warpAffine` with `INTER_LANCZOS4` instead of `INTER_LINEAR` for sub-pixel accuracy.

Expected marginal improvement in sharpness; does not address the primary failure modes.

---

## Part VIII — What ASP Has That Neither Competitor Has

### 1. Explicit Foreground/Background Decomposition

BiRefNet-guided fg/bg separation drives every stage: background-only matching, fg-specific seam cost map (5 tiers), ARAP fg registration, fg-aware blend chain, single-pose escalation, temporal median for bg, RLHF quality scoring. This is the most domain-specific innovation and the reason ASP can produce correct results on sequences with animated characters that neither OpenCV nor Overmix can handle.

### 2. GNC-TLS Bundle Adjustment

Yang et al. (2020) Graduated Non-Convexity with Geman-McClure surrogate, tolerating 70-80% outlier edges. This robustness level is essential for anime sequences where LoFTR frequently fails on flat cel-shaded backgrounds and phase correlation is the fallback. OpenCV's LM with Huber loss tolerates ~30% outliers; Overmix has no formal BA at all.

### 3. Comprehensive Retry Chain

5-tier automated retry + PANORAMA + SCANS fallback. Each tier uses progressively relaxed validation thresholds. The user never sees a catastrophic failure — the worst case is a simple vertical stack (`_scan_stitch_fallback`), which is always correct even if visually crude.

### 4. 24 Pre-DP Seam Escalation Gates

The gate system detects cases where Laplacian blending would produce a ghost (incompatible fg poses, flat regions, low-quality zones) and preemptively switches to single-pose mode. This is a form of uncertainty quantification in the compositing pipeline — no other system attempts to detect in advance whether blending will produce an artifact.

### 5. RLHF Quality Learning

`StitchRewardModel` learns from human feedback which output characteristics constitute quality. The reward model is integrated into the benchmark pipeline (`_compute_rlhf_score`) and the HITL loop. This is a unique capability for continuous improvement without re-implementing algorithms.

### 6. HITL Correction System

`hitl/` module allows: ARAP flow arrow drawing (override computed flow for specific fg regions), SAM2 region selection (`grounding.py`), MLLM quality scoring (`mllm_scorer.py`), parameter search (`param_search.py`), preset management (`hitl_presets.py`). Neither OpenCV nor Overmix has an API-level HITL integration.

### 7. Multi-Mode Matching Cascade with 5 Fallbacks

The LoFTR → ALIKED → Template → Phase → Segment → RoMa cascade provides 5 independent fallback methods for a single frame pair. This means ASP can often produce a correct displacement estimate even when all conventional methods fail. OpenCV uses 1 method (SIFT+FLANN); Overmix uses 1-3 methods.

### 8. MFSR Module

`mfsr/` sub-pipeline with DCT restoration, diffusion inpainting, DRL sub-pixel registration, PSO sub-pixel registration, prior injection. Substantially more sophisticated than Overmix's `RobustSrRender` (L1 sparse) and OpenCV has no SR at all.

### 9. 15 Post-Composite Quality Audit Metrics

The automated quality gate suite (§1.14B through §1.85) provides a ground-truth-free assessment of compositing quality. This enables the retry logic and RLHF feedback loop. Neither OpenCV nor Overmix has automated post-composite quality assessment.

---

## Part IX — Summary and Conclusions

### Three Philosophies of Image Stitching

| System | Core philosophy | Optimal domain |
|---|---|---|
| OpenCV | General-purpose photogrammetric pipeline. Model the camera, solve for camera parameters, let global energy minimisation handle quality. | Any overlapping images with sufficient texture; rotating or translating camera; natural photos |
| Overmix | Super-resolution through averaging. Treat multiple captures as noisy samples of the same scene; average cancels noise. | Many near-identical frames (hold blocks); sub-pixel SR recovery; static backgrounds with MPEG noise |
| ASP | Domain-specific decomposition. Model the unique structure of anime scroll captures explicitly (T_camera + A_animation); route seams in background; handle fg character as a separate alignment problem. | Anime vertical-scroll screen recordings with animated character foreground |

### Where Each System Wins

**OpenCV wins at**: seam quality (global GraphCut), exposure correction (joint block gain), camera model generality, GPU acceleration, production maturity.

**Overmix wins at**: sub-pixel reconstruction quality within hold blocks (√N noise reduction), simplicity (no seam = no seam artifact for identical-frame groups), YCbCr/gamma pipeline correctness, JPEG DCT-domain operations.

**ASP wins at**: anime-specific domains (BiRefNet + ARAP + single-pose + hold detection), robustness engineering (5-tier retry, 24 pre-DP gates, 15 post-composite metrics), research depth (GNC-TLS, StabStitch++ midplane, RLHF), multi-modal matching cascade.

### The Remaining Gap

ASP's benchmark failures (97.9% strip banding, 93.8% ghosting, 88.5% seam visibility vs simple stitch) are not fundamental — they reflect specific algorithmic choices that are directly addressable:

1. **GraphCut seam (§4.2)** — replace pairwise 1D DP with global 2D min-cut. Eliminates the primary ghosting and seam visibility failures.
2. **Blocks gain as default (§4.1)** — replace scalar gain with 32×32 block gain. Eliminates the strip banding failures.
3. **Hold-block averaging (§3.12A as default)** — eliminate MPEG noise at source. Reduces ARAP false alarm rate, improving fg registration quality.

These three changes, informed by OpenCV and Overmix's design, would be expected to close the majority of the benchmark gap between ASP and the simple-stitch baseline — and, given ASP's fg/bg decomposition advantage, potentially push ASP above both OpenCV and simple-stitch on anime-specific test cases.

---

## Appendix A: Key File Reference

### OpenCV Stitching Module (`opencv/modules/stitching/`)
| File | Key contents |
|---|---|
| `src/stitcher.cpp` | `Stitcher::stitch()`, `estimateTransform()`, `composePanorama()` |
| `src/seam_finders.cpp` | `GraphCutSeamFinder::Impl::findInPair()`, `DpSeamFinder`, `VoronoiSeamFinder` |
| `src/blenders.cpp` | `MultiBandBlender::feed()`, `blend()`, `createLaplacePyr()` |
| `src/exposure_compensate.cpp` | `BlocksCompensator::feedWithStrategy()`, `apply()` |
| `src/motion_estimators.cpp` | `BundleAdjusterRay`, `BundleAdjusterAffinePartial`, `waveCorrect()`, `HomographyBasedEstimator` |
| `src/matchers.cpp` | `BestOf2NearestMatcher::match()`, `CpuMatcher::match()` |
| `src/autocalib.cpp` | `calibrateRotatingCamera()`, `focalsFromHomography()` |
| `src/camera.cpp` | `CameraParams` decomposition helpers |
| `include/opencv2/stitching/detail/seam_finders.hpp` | Class declarations, `GCGraph` interface |
| `include/opencv2/stitching/detail/blenders.hpp` | `MultiBandBlender`, `FeatherBlender` |
| `include/opencv2/stitching/detail/exposure_compensate.hpp` | `BlocksGainCompensator`, `BlocksChannelsCompensator` |

### Overmix (`Overmix/src/`)
| File | Key contents |
|---|---|
| `aligners/RecursiveAligner.cpp` | Divide-and-conquer tournament tree alignment |
| `aligners/LinearAligner.cpp` | LS drift removal |
| `aligners/IndependentAligner.cpp` | Jacobi multi-pair refinement |
| `aligners/AnimationSeparator.cpp` | Automatic hold-block grouping (max sign-change threshold) |
| `comparators/GradientPlane.cpp` | `findMinimum()` hierarchical grid + DiffCache + QtConcurrent |
| `comparators/MultiScaleComparator.cpp` | Recursive 2× pyramid + 4-point sub-pixel refinement |
| `comparators/BruteForceComparator.cpp` | Exhaustive grid `[-max,max]²` |
| `renders/AverageRender.cpp` | `SumPlane::addAlphaPlane()`, `average()` |
| `renders/FloatRender.cpp` | B-spline kernel reconstruction (genuine SR) |
| `planes/basic/difference.cpp` | `Difference::simpleAlpha()` — core L1/L2 pixel metric |
| `planes/basic/Plane.cpp` | Scaling kernels, deconvolution, edge detection |

### ASP (`backend/src/animation/`)
| File | Key contents |
|---|---|
| `core/pipeline.py` | `AnimeStitchPipeline.run()` — 13-stage orchestration + retry chain |
| `rendering/compositing.py` | `_composite_foreground()`, `_seam_cut()`, `_build_seam_cost_map()`, all blend functions |
| `alignment/bundle_adjust.py` | GNC-TLS + LM BA, `_spanning_tree_inlier_filter()`, `_compute_adaptive_f_scale()` |
| `alignment/canvas.py` | `_compute_canvas()`, `_panorama_stitch_fallback()`, `_scan_stitch_fallback()`, `_telea_fill_gaps()` |
| `alignment/fg_register.py` | ARAP push+regularise, `register_foreground_at_seam()` |
| `alignment/matching.py` | `_match_pair()` 7-method cascade, `_phase_correlate()` |
| `alignment/ecc.py` | `_ecc_refine()` sub-pixel affine refinement |
| `ingestion/frame_selection.py` | `smart_select_frames()`, hold detection (MAD + dHash), DINOv2 |
| `ingestion/masking.py` | BiRefNet wrapper, `bg_masks` computation |
| `rendering/photometric.py` | BaSiC correction, per-segment gain |
| `rendering/rendering.py` | `_render_median()` temporal median, `_render()` warp loop |
| `mfsr/` | SR sub-pipeline (PSO, DRL, DCT, diffusion) |
| `hitl/` | HITL correction system (ARAP arrows, SAM2, MLLM, presets) |
| `rlhf/` | Reward model, feedback store, online trainer |
| `backend/benchmark/bench_anime_stitch.py` | All benchmark metrics, GT comparison, RLHF score |
| `backend/src/constants/anim.py` | All default constants for ASP_* flags |

---

*End of document. Generated 2026-06-22. Based on full source reads of opencv/modules/stitching/ (C++), Overmix/src/ (C++/Qt), and backend/src/animation/ (Python 3.11).*
