# Anime Stitching Pipeline Optimization Report
## Comprehensive Analysis & Improvement Roadmap

*Date: 2026-05-07*

---

## Table of Contents

1. [Codebase Architecture Overview](#1-codebase-architecture-overview)
2. [Frame Extraction Deep Dive](#2-frame-extraction-deep-dive)
3. [Stitching Pipeline Deep Dive](#3-stitching-pipeline-deep-dive)
4. [The Spillerrec / Overmix Lessons](#4-the-spillerrec--overmix-lessons)
5. [Why Anime Breaks Photometric Assumptions](#5-why-anime-breaks-photometric-assumptions)
6. [Current Gaps & Known Failure Modes](#6-current-gaps--known-failure-modes)
7. [Optimization Proposals by Stage](#7-optimization-proposals-by-stage)
8. [New Ideas to Explore](#8-new-ideas-to-explore)
9. [Priority Matrix & Roadmap](#9-priority-matrix--roadmap)

---

## 1. Codebase Architecture Overview

### Entry Points

| Component | Location | Role |
|---|---|---|
| `FrameExtractionWorker` | `gui/src/helpers/video/frame_extractor_worker.py` | Frame extraction QRunnable (standard + smart FFmpeg modes) |
| `ImageExtractorTab` | `gui/src/tabs/core/image_extractor_tab.py` | PySide6 UI for frame extraction, cut management, video playback |
| `AnimeStitchPipeline` | `backend/src/core/anime_stitch_pipeline.py` | 14-stage stitching pipeline (the algorithmic core) |
| `StitchWorker` | `gui/src/helpers/models/stitch_worker.py` | QThread wrapper around `AnimeStitchPipeline` with progress signals |
| `StitchTab` | `gui/src/tabs/models/gen/stitch_tab.py` | Primary stitching UI (auto + manual modes) |
| `HybridStitchPanel` | `gui/src/tabs/models/gen/hybrid_stitch_panel.py` | Human-in-the-loop panel (control points, TPS warp, seam painter) |
| `LoFTRWrapper` | `backend/src/models/loftr_wrapper.py` | kornia LoFTR dense matching (320×448, outdoor pretrained) |
| `BaSiCWrapper` | `backend/src/models/basic_wrapper.py` | ALM-based photometric correction (flat-field + per-frame baselines) |
| `BiRefNetWrapper` | `backend/src/models/birefnet_wrapper.py` | Foreground segmentation (ToonOut / BiRefNet weights) |

### Data Flow

```
Video file
    → FrameExtractionWorker (OpenCV or FFmpeg)
    → [Manual cut exclusion, frame interval, smart dedup]
    → PNG frames on disk (8-bit or 16-bit)
    
PNG frames
    → AnimeStitchPipeline.run()
        1. _load_frames() + _trim_dark_border()
        2. _normalise_widths()            [Lanczos4]
        3. _apply_basic()                 [BaSiCWrapper: spatial flat-field only]
        4. _compute_fg_masks()            [BiRefNetWrapper → 255=bg mask]
        5. _pairwise_match()              [LoFTR → template → phase-corr fallback]
        6. _bundle_adjust_affine()        [scipy Levenberg-Marquardt, translation-only]
        7. _ecc_refine()                  [cv2.findTransformECC MOTION_TRANSLATION, 4-level pyramid]
        8. _compute_canvas()              [global T offset]
        9. _render_median|first|blend()   [Overmix temporal median OR Laplacian blend]
       10. _composite_foreground()        [best single frame's foreground pasted back]
       11. _crop_to_valid()               [largest inscribed non-black rectangle]
    → PIL Image → PNG/WEBP output
```

---

## 2. Frame Extraction Deep Dive

### 2.1 Standard Mode (`cv2.VideoCapture`)

```python
# gui/src/helpers/video/frame_extractor_worker.py:84
cap = cv2.VideoCapture(self.video_path)
cap.set(cv2.CAP_PROP_POS_MSEC, self.start_ms)
# ...
frame = cv2.resize(frame, self.target_resolution, interpolation=cv2.INTER_LANCZOS4)
cv2.imwrite(save_path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
```

**What it does correctly:**
- Saves lossless PNG with compression level 3 (good balance of speed vs size)
- `INTER_LANCZOS4` for resizing (correct choice for high-quality downscaling)
- Manual cut exclusion via `cuts_ms` list

**Critical deficiencies:**
1. **VLC-style chroma resampling:** `cv2.VideoCapture` decodes using the system's default codec (FFmpeg-based on Linux, but applies software chroma upsampling). For YUV 4:2:0 content (every broadcast and Blu-ray anime), chroma is interpolated from a half-resolution grid. The upsampling filter varies by OpenCV build and may produce frame-to-frame chroma inconsistency — exactly the source of the color banding that Overmix's dump-tools were designed to bypass.

2. **8-bit pipeline only:** `cv2.imread` returns uint8. For Hi10p (10-bit) sources, this discards 2 bits. Smart mode correctly uses `-pix_fmt rgb48be`, but standard mode doesn't have an equivalent.

3. **No IVTC (Inverse Telecine):** SD anime is broadcast at 29.97 fps via 3:2 pulldown from 23.976 fps masters. Without de-telecining, roughly 40% of extracted frames are blended (B+C or C+D fields) — these interlaced/blended frames are mathematically inappropriate as stitching inputs and will confuse every alignment algorithm.

4. **No shot-cut detection:** When a user selects a time range manually, there is no automatic detection of scene cuts within that range. If two separate panning shots are included, all alignment methods will produce wrong results.

5. **No content-aware frame selection:** The `frame_interval` parameter simply takes every N-th frame regardless of content change. For a fast pan, this may skip critical coverage; for a slow pan, it extracts many near-identical frames that waste memory in the median stack.

### 2.2 Smart Mode (FFmpeg)

```python
# gui/src/helpers/video/frame_extractor_worker.py:159-178
if "mpdecimate" in self.smart_method:
    filters.append("mpdecimate")
elif "scene" in self.smart_method:
    filters.append(f"select='gt(scene,{val})'")
# ...
cmd.extend(["-pix_fmt", "rgb48be"])   # ✓ 16-bit
cmd.extend(["-vsync", "vfr"])
```

**What it does correctly:**
- `rgb48be` for 16-bit pixel depth (prevents 10-bit banding)
- `mpdecimate` for near-duplicate removal
- Proper Lanczos scaling via `scale={w}:{h}:flags=lanczos`
- VFR output with `-vsync vfr -frame_pts 1`

**Critical deficiencies:**
1. **`mpdecimate` is not selective for stitching:** It removes exact/near-duplicates (good for dedup), but for a panning shot you need nearly every frame (every pixel contributes to the Overmix median stack). `mpdecimate` should only be used for pre-selection, not for stitching inputs.

2. **`scene` detection is per-frame absolute difference:** `gt(scene, 0.4)` keeps frames where the scene score exceeds the threshold. This is designed for scene-cut detection, not for selecting stitching frames within a pan. It will aggressively drop frames in a uniform-background pan.

3. **No IVTC filter:** FFmpeg has `fieldmatch+decimate` (IVTC) which can reconstruct the original 24fps progressive frames from 29.97fps telecined content. Not wired up.

4. **No `yadif` or `bwdif` for interlaced sources:** Interlaced anime (common for pre-2005 TV rips) will have comb artifacts in extracted frames unless deinterlaced.

5. **No `-color_primaries`/`-color_trc`/`-colorspace` tagging:** FFmpeg needs to know BT.601 (SD/DVD) vs BT.709 (HD/Blu-ray) to apply correct color matrix. Without this, the decoded RGB values may have wrong gamma.

---

## 3. Stitching Pipeline Deep Dive

### 3.1 Stage 1 — Load & Dark-Border Trim

```python
# backend/src/core/anime_stitch_pipeline.py:134-167
def _trim_dark_border(arr, pct=0.20):
    row_m = gray.mean(axis=1)
    col_m = gray.mean(axis=0)
    thr_r = max(med_r * pct, 4.0)   # 20% of median brightness
```

**Assessment:** Well-designed. The 20% threshold is generous enough to catch true dark bars without clipping content. However:

- Doesn't distinguish between dark-bar borders (which should be trimmed) and intentionally dark frames (e.g., a scene taking place at night where the entire frame legitimately has low brightness). For a genuinely dark scene, `med_r` is low and `thr_r` could be near 4.0, causing no trimming when some trimming was appropriate.
- Doesn't trim station logos, subtitle bands, or timecode overlays — these are static overlays at fixed positions that confuse all alignment methods.

### 3.2 Stage 2 — Width Normalisation

```python
# Line 657-666
target_w = frames[0].shape[1]
img = cv2.resize(img, (target_w, nh), interpolation=cv2.INTER_LANCZOS4)
```

**Assessment:** Correct approach (Lanczos4, aspect-ratio preserving). The choice to lock to frame 0's width is correct. The only concern: if frame 0 itself has a different aspect ratio from the source material (e.g., extracted from an anamorphic stream), all subsequent frames will be wrong.

### 3.3 Stage 3 — BaSiC Photometric Correction

```python
# Line 669-705
def _apply_basic(self, frames):
    # We deliberately do NOT apply the per-frame dimming baseline (b_i) correction.
    # The spatial flat-field F (vignette/shading) is the only correction here.
    return [self._basic.apply_correction(img, baseline_override=1.0) for img in frames]
```

**The deliberate omission of b_i correction is theoretically motivated** (applying b_i would make all frames equally bright, destroying the natural brightness continuity that the seam algorithm relies on), **but creates a downstream problem:**

In `_render_median`, there is **no color/brightness matching at all**. The raw median of unmatched frames from a broadcast-dimmed sequence will produce a blended composite where some canvas regions are consistently darker than others (where dimmed frames dominate the median). The `_render_laplacian` path does a global per-channel gain match on the overlap region:

```python
# Line 1448-1452
for c in range(3):
    gain = ref_img[overlap, c].mean() / (src[overlap, c].mean() + 1e-6)
    out[..., c] = np.clip(src[..., c] * gain, 0, 255)
```

This is a single global scalar per channel — better than nothing, but insufficient for spatially varying lighting (e.g., a VFX overlay that enters from one side of the frame).

**The `BaSiCWrapper.fit()` already correctly detects and reports dimmed frames:**
```python
# basic_wrapper.py:133-135
b_median = b.median().clamp(min=1e-6)
b = b / b_median
# dim_frames = [i for i, bi in enumerate(baselines) if bi < 0.75]
```

This information is computed but discarded at the pipeline level. Feeding it into a per-frame pre-correction step before the median render would eliminate Pokémon-Shock dimming artifacts.

### 3.4 Stage 4 — BiRefNet Foreground Masking

```python
# Line 708-754
# dilate_px=16 (safety margin), erode_px=8 (boundary sharpening)
bg = self._birefnet.get_background_mask(img, dilate_px=16, erode_px=8)
```

**Assessment:** Using BiRefNet with 16px safety dilation is appropriate and conservative. The mask is used both to guide LoFTR matching (exclude character regions from correspondence) and to drive foreground compositing. 

**Issues:**
- Uses generic BiRefNet weights ("outdoor"/"general"), not ToonOut fine-tuned weights. ToonOut achieves 99.5% pixel accuracy on anime vs ~95% for base BiRefNet. This matters for thin hair wisps and stylized transparent effects.
- No temporal consistency: each frame is processed independently. A character at the edge of a frame might get a different mask quality than the same character in an adjacent frame, creating temporal inconsistencies in the foreground composite.
- Dilation of 16px is aggressive — on small frames (e.g., 720p) this erodes a significant fraction of the background near characters, reducing available background pixels for LoFTR matching.

### 3.5 Stage 5 — Pairwise Matching (The Algorithmic Heart)

The matching hierarchy is:
1. `AnimeStitchNet` (trained DL model, if checkpoint provided)
2. `LoFTR + MAGSAC++ → estimateAffinePartial2D with RANSAC`
3. Template matching (multi-strip voting, parabolic sub-pixel)
4. Phase correlation (high-pass Y', masked)

#### LoFTR path

```python
# loftr_wrapper.py:76-80
_LOFTR_H = 320
_LOFTR_W = 448
g1r = cv2.resize(gray1, (_LOFTR_W, _LOFTR_H), interpolation=cv2.INTER_AREA)
```

**Issues:**
- Fixed 320×448 resolution. Original frames might be 1920×1080 (aspect 1.78) vs LoFTR target aspect 1.4. This 27% aspect distortion may be problematic for matches near the edges. A proper fix would crop to the target aspect before resizing, or use EfficientLoFTR which handles variable input sizes better.
- "outdoor" pretrained weights are trained on MegaDepth/ScanNet — photographic outdoor and indoor scenes. Anime imagery is out-of-distribution. While LoFTR's transformer is generally robust to domain shift (the reports confirm this), a fine-tuned variant on anime pairs (e.g., from ATD-12K or custom mining) would improve match quality on very flat backgrounds.
- After LoFTR produces the 4-DOF affine via `estimateAffinePartial2D`, the rotation and scale are **immediately discarded** (line 926-930):
  ```python
  M_transl = np.eye(2, 3, dtype=np.float32)
  M_transl[0, 2] = M[0, 2]   # only translation extracted
  M_transl[1, 2] = M[1, 2]
  M = M_transl
  ```
  For pure 2D pans this is exactly right. But for sources with even 0.2° camera rotation (common in hand-held-style anime or with parallax between foreground layers), this silently discards correctable micro-rotation and accumulates geometric drift.

#### Template matching path

```python
# Line 983-1073
strip_starts = [H - slice_h, H - slice_h - slice_h//2, H - slice_h - slice_h]
for strip_y in strip_starts:
    res = cv2.matchTemplate(roi, tmpl, cv2.TM_CCORR_NORMED, mask=mask_strip)
    # ... parabolic sub-pixel refinement
    dy_candidate = ry_sub - strip_y
```

**Assessment:** Well-implemented multi-strip voting with sub-pixel refinement. The correct `dy` formula is applied. The mask-aware template matching (using `mask_strip`) is a good touch that the stock OpenCV implementation doesn't do by default.

**Issues:**
- Only searches the bottom quarter of frame i for the template, then looks in the top `max_search_frac` of frame j. This assumes the pan direction is top-to-bottom. For horizontal pans, the strip/search geometry needs to be rotated.
- Strip texture check `tmpl.std() < 2.0` is very conservative — a sky gradient with std=3.0 will pass, but the template is essentially just a smooth gradient and will produce a spurious match.
- Threshold `_MIN_TEMPLATE_SCORE = 0.55` seems low for anime where identical flat regions can produce spurious matches at exactly 1.0 even when misaligned (because the template is pure flat color).

#### Phase correlation path

```python
# Line 1086-1105
g_i = _highpass(_luma(img_i)).astype(np.float32)
shift, response = cv2.phaseCorrelate(g_i, g_j)
```

**Issues:**
- `cv2.phaseCorrelate` does not apply a Hann window by default. The literature (and Overmix's implementation) strongly recommends a Hann window to suppress the cross-correlation sidelobes from image edges. Without it, the dominant frequency in the phase spectrum is often the DC component from frame edges, not the actual translation.
- The `_highpass` filter uses `sigma=3.0` Gaussian subtraction. For 1080p frames, this cuts out low spatial frequencies below ~15 pixels period. Useful for suppressing flat backgrounds, but may be too aggressive for thin line art (which is already at high frequency and gets partially cancelled).
- Response threshold of `_PC_CONF_THRESHOLD = 0.08` is very low — the normalized phase correlation response on a good match typically peaks at 0.3–0.8. A threshold of 0.15–0.20 would reject more false positives.

### 3.6 Stage 6 — Bundle Adjustment

```python
# Line 378-473
# Translation-only Levenberg-Marquardt
def residuals(x):
    ti, tj = x[i*2:i*2+2], x[j*2:j*2+2]
    diff = (pts_i + ti) - (pts_j + tj)   # global translation only
```

**Assessment:** The decision to enforce translation-only BA is theoretically correct for 2D pans and prevents the "fan/spiral" distortion that occurs when rotation/scale drift accumulates over a long sequence. This mirrors the Brown-Lowe 2007 approach for scanner-like inputs.

**Issues:**
- The BA uses `scipy.optimize.least_squares` with L2 loss. A Huber or cauchy loss would be more robust to a small number of LoFTR false matches that slip through RANSAC.
- The anchor `reg = 0.3` is a fixed regularizer for frame 0. For sequences where frame 0 is not actually the leftmost/topmost frame (e.g., when `find_optimal_sequence` returns a non-trivially ordered list), this may bias the solution.
- BA uses the LoFTR-estimated pts_i but `pts_j = pts_i + M[:2, 2]` (line 935) — i.e., pts_j is synthesized from the translation, not the actual LoFTR-matched background points. This means the BA is fitting to the initial translation estimate, not to the actual feature correspondences in j. The correct formulation would use the actual matched pts_j from LoFTR and discard pts synthesized from M.

### 3.7 Stage 7 — ECC Sub-Pixel Refinement

```python
# Line 1126-1248
for lvl in range(_ECC_PYRAMID_LEVELS - 1, -1, -1):  # 4-level pyramid (8x → 4x → 2x → 1x)
    _, M_s = cv2.findTransformECC(r_s, s_s, M_s, cv2.MOTION_TRANSLATION, criteria, ecc_m_s)
```

**Assessment:** This is one of the strongest parts of the pipeline. MOTION_TRANSLATION prevents the 6-DOF drift that plagued the old SIFT approach. The 4-level pyramid avoids local minima from MPEG noise.

**Issues:**
- `gaussFiltSize=5` in `findTransformECC` corresponds to a 5×5 Gaussian pre-blur. The documentation recommends this for noisy images. However, 5 pixels is quite aggressive for 720p anime where thin line art is only 1-2 pixels wide — the blur will smear the alignment signal. A value of 3 might be better for clean BD sources.
- ECC refines relative translation from i-1 to i sequentially, meaning errors accumulate. A better approach would be to refine absolute translations by running ECC against a common reference frame for each frame (when the panorama is not too large).
- The safety clamp `_ECC_MAX_DRIFT = 80.0` is in pixels. For a 4K source, 80 pixels is only 2% of the frame width — appropriate. But for 480p (SD anime), 80 pixels is 17% of the frame width — much too permissive.

### 3.8 Stage 9 — Rendering

#### Median renderer

```python
# Line 1305-1404
# chunk-based, handles N=1 and N>1 separately
for y0 in range(0, H, chunk_size):
    # ... stack frames, compute nanmedian
```

**Assessment:** Memory-efficient chunked implementation. The special case for `count == 1` (single sample, no true median needed) is a smart optimization.

**Critical issue — no color matching in median renderer:** The `_render_median` function simply takes the raw median of all warped frames without any per-frame brightness normalization. If frames 5-10 in a sequence were broadcast-dimmed by 20%, the panorama will have a visible brightness discontinuity in the canvas region where only those frames contribute. The `_apply_basic` stage was intended to handle this but was deliberately set to `baseline_override=1.0` to avoid breaking seam boundaries. This creates a subtle trap: the flat-field correction happens, but the dimming correction doesn't, and the median render has no fallback.

**The fix:** Before stacking frames in the median render, apply a per-frame global gain correction using `self._basic.baselines` (which are computed and stored but never used in rendering).

#### Laplacian blend renderer

```python
# Line 1440-1494
for c in range(3):
    gain = ref_img[overlap, c].mean() / (src[overlap, c].mean() + 1e-6)
# ...
weight = (d2**4) / (d1**4 + d2**4 + 1e-9)  # distance transform blend
canvas = _laplacian_blend(img, canvas, weight, self.bands)
```

**Issues:**
- The weight `(d2^4)/(d1^4 + d2^4)` is essentially a feathering function computed from distance transforms — not a proper seam finder. The `_seam_dp()` function exists in the file but is never called from `_render_laplacian`. The DP seam function would produce better results by routing the seam through flat color regions (anime's key advantage).
- Global gain matching `src[overlap, c].mean() / ref[overlap, c].mean()` can be severely wrong when the overlap region contains a moving character (who occupies the overlap but whose color shouldn't drive the gain estimate). Should use the background mask to restrict the gain computation to background-only pixels.
- Only matches against `ref_idx = 0` (frame 0). For long sequences, frame N may be very different in exposure from frame 0. A chain-of-pairs gain propagation (each frame matched to its predecessor) would be more stable.

### 3.9 `find_optimal_sequence` — The Legacy SIFT Method

```python
# Line 1603-1713
sift = cv2.SIFT_create(nfeatures=1200)
# ...
M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
# ...
dist = np.sqrt(M[0, 2]**2 + M[1, 2]**2)
if dist < 0.15 * max(q_h, q_w): continue
```

This static method uses SIFT + full homography — the very approach the pipeline was designed to move away from. It is used when the UI automatically discovers the best sequence from a pool of candidate frames. Using the old approach here means:
- All the SIFT-on-flat-color failures (collinear keypoints, degenerate homography) can occur during sequence ordering, producing a wrong ordering that then feeds the new pipeline with frames in the wrong sequence.
- The distance metric `dist = sqrt(M[0,2]^2 + M[1,2]^2)` uses the homography's translation component — but the homography may have incorrect perspective parameters that contaminate the translation estimate.

---

## 4. The Spillerrec / Overmix Lessons

Spillerrec's decade-long Overmix project (2013–2024) converged on principles that this pipeline has largely adopted, but with some important nuances:

### 4.1 What Overmix Got Right (And We've Implemented)

| Overmix Principle | Our Implementation | Notes |
|---|---|---|
| Y'-only alignment | Phase correlation on Y'; ECC on Y' | ✓ Both fallbacks use luma |
| Temporal median for denoising | `_render_median` | ✓ Chunk-based |
| Translation-only model | BA + ECC with MOTION_TRANSLATION | ✓ Strict translation-only BA |
| Foreground/background separation | BiRefNet masking | ✓ 16px safety dilation |
| Dark border trimming | `_trim_dark_border` | ✓ 20% threshold |
| Multiple matching methods | LoFTR → template → phase corr | ✓ Well-designed fallback chain |

### 4.2 The Animation Frame Separation Problem

The key insight from Spillerrec's 2014 retrospective that is **not implemented** in the current pipeline:

> *"Some scenes contain a repeating animation, while doing vertical/horizontal movement. Especially H-titles seems have much of this, but can also be found as mouth movement and similar. While still in its early stages, I have successfully managed to separate the animation into its individual frames and stitch those, using a manual global threshold."*

**What this means concretely:** In Japanese animation, especially visual novel adaptations and adult titles, a pan shot may overlay a cyclic animation (e.g., mouth opening/closing, chest/hair movement from breathing, blinking, looped walk cycle) on top of a static panning background. The animation typically cycles every 2-4 frames (Japanese animation was historically "animated on twos" — one drawing held for 2 frames).

The Overmix technique:
1. Detect frame-to-frame difference in a fixed region of the image
2. Use a **global threshold** on this difference to classify each frame into one of the animation "phases"
3. Median-stack only frames within the same animation phase
4. Produce one background panorama per phase, then take the best

**Why the current median render fails here:** If frames alternate between pose A and pose B in a 1:1 cycle, the temporal median of both will produce a 50% ghost (both poses superimposed at half opacity in the flat-color character region). The BiRefNet foreground mask helps but only if the mask quality is high enough — for a subtle mouth animation or a small animation in the mid-ground, BiRefNet may not reliably detect it.

**Spillerrec's acknowledged weakness:** *"I doubt it would currently work with minor animations, such as changes with the mouth, noise would probably mess it up. So I'm considering investigating other ways of calculating the difference, perhaps using the edge-detected image instead, or doing local differences."*

This is prescient: edge-image comparison is more stable than raw pixel difference for low-magnitude animations, because it is insensitive to overall brightness and focuses on structural change.

### 4.3 Overmix's Sub-Pixel Super-Resolution Trick

Overmix's technique for achieving super-resolution: align frames to a 4× canvas, take the median, then optionally apply deconvolution. We have the median rendering but not the 4× upscale canvas step. The current pipeline renders at 1:1 scale. This means the sub-pixel shifts between frames (which encode high-frequency information recoverable by SR) are lost.

---

## 5. Why Anime Breaks Photometric Assumptions

### 5.1 Flat Regions Kill Traditional Detectors

SIFT, SURF, Harris, and FAST all rely on local gradient richness. An anime background segment of pure sky (#4a9ad4) is a completely flat region — zero gradient, zero detected keypoints. When SIFT does find keypoints, they cluster on the single-pixel-wide black ink outlines. This creates the **collinear keypoint problem**: all selected matches lie approximately on a 1D manifold (the outline curve), making the RANSAC DLT design matrix rank-deficient.

The current pipeline correctly avoids this through LoFTR (which operates on the global Transformer context, not local gradients) and template matching (which is area-based, not point-based). However, `find_optimal_sequence` still uses SIFT and is vulnerable to this failure.

### 5.2 Anti-Aliased Line-Art Gradients

Anime line art is typically rendered with sub-pixel anti-aliasing: a pure black stroke has a 1-2 pixel wide transition zone of grays. When SIFT or AKAZE's nonlinear scale-space analyses these transitions, the gradient direction is well-defined but the precise location of the "edge" varies by sub-pixel amounts depending on the rendering pass. This introduces a systematic bias: the keypoint position for the same edge feature is not perfectly consistent between frames, leading to a fixed sub-pixel offset bias that neither RANSAC nor ECC can fully correct (ECC can, if initialized close enough).

**Implication:** For cartoon/anime content, even the best classical sub-pixel refinement has a systematic floor determined by the anti-aliasing grid. This is why Overmix's 4× upscale trick (which spreads the AA transition over a larger pixel grid before refinement) genuinely improves alignment quality.

### 5.3 Bimodal Histograms Violate Gaussian Assumptions

Reinhard's (2001) `lαβ` color transfer assumes each channel is approximately Gaussian. An anime frame has a bimodal histogram: a large mode at the flat background color, a smaller mode at the character/foreground color, with the line art forming thin tail populations. When `_render_laplacian` applies a single global gain to match frame means, it is computing the gain that makes two non-Gaussian distributions overlap at their means — which may actually make the distributions *diverge* if the two modes shift differently between frames (e.g., if the character has entered the frame and changed the mean substantially).

**Fix:** Region-stratified color transfer — apply Reinhard or histogram matching **per palette cluster**. With k=6-8 clusters (typical for an anime background), each cluster corresponds to one material (sky, ground, foliage, character skin, character hair, etc.) and its histogram is approximately Gaussian. Matching per cluster is mathematically valid.

### 5.4 Chroma Subsampling Artifacts

YUV 4:2:0 gives chroma resolution of W/2 × H/2. When decoded to RGB by any software player, chroma is upsampled using some filter (nearest-neighbor in VLC, bilinear in most others). For a pure-red region (high R, zero G and B in the source), chroma upsampling determines whether the boundary of that region is sharp or has a 1-2 pixel bleed. This bleed varies between frames because the chroma upsampling interacts with the 8×8 DCT block boundaries differently depending on the block quantization. Result: using RGB for alignment is strictly worse than using Y' only, because the chroma channel adds noise at MPEG block boundaries that doesn't correlate between frames.

**Current implementation:** The ECC refine and phase correlation both use Y' only (correct). LoFTR runs on grayscale (luma) (correct). Template matching uses `_luma()` (correct). But the BaSiC flat-field estimation runs on all 3 channels when `luma_only=False` is used via the legacy API path.

### 5.5 Pokémon-Shock Broadcast Dimming

Post-1997, all Japanese terrestrial broadcasts automatically apply frame-level dimming when the Harding analyzer detects potentially epileptic patterns. The dimmer applies a scalar multiplier to the entire YUV signal — equivalent to a per-frame `b_i` in BaSiC notation. `BaSiCWrapper.fit()` correctly detects and stores these baselines but the pipeline deliberately doesn't apply them (see Stage 3 analysis). The pipeline correctly detects which frames were dimmed (baselines < 0.75) but doesn't compensate for this in the final median render, leading to a darker region in the canvas where dimmed frames are the sole contributors.

---

## 6. Current Gaps & Known Failure Modes

### 6.1 Failure Mode Table

| Scenario | Root Cause | Where It Fails | Severity |
|---|---|---|---|
| Cyclic animation (mouth, hair) during pan | No animation phase separation | Median render ghost | High |
| Broadcast-dimmed frames | BaSiC b_i not applied in median render | Canvas brightness discontinuity | High |
| Horizontal pan (not vertical) | Template matching assumes vertical pan geometry | Template match finds wrong dy | High |
| IVTC-needed SD source | No de-telecine in extraction | Blended frames enter stitching | High |
| Multi-plane parallax | Translation-only model | Foreground/background split ghost | Medium |
| Very flat frame (all sky) | LoFTR conf < 0.4 with no structure → template match also fails | Falls to phase correlation; may fail too | Medium |
| VFX overlay (glowing effects) | Neither BaSiC nor gain compensation handles it | Visible lighting inconsistency | Medium |
| Sequence ordering | `find_optimal_sequence` uses SIFT+homography | Wrong frame order → pipeline corrupted | Medium |
| Hi10p source in standard mode | OpenCV reads 16-bit PNG as 8-bit | 2-bit precision loss | Low-Medium |
| LoFTR coordinate distortion | 27% aspect distortion at 320×448 resize | Systematic offset in matches | Low |

### 6.2 Missing Components

- **Animation frame separation** — no phase-detection clustering before median stacking
- **IVTC / de-telecine** — not available in either extraction mode
- **Block-based gain compensation** — only global gain; VFX overlays are spatially varying
- **Region-stratified color transfer** — only global gain; bimodal histograms make this unreliable
- **Hann window in phase correlation** — missing, degrades response quality
- **DP seam finder in blend renderer** — `_seam_dp()` is defined but never called
- **4× super-resolution canvas** — Overmix's sharpness recovery technique not wired up
- **Deconvolution** — sharpness recovery after temporal averaging
- **AKAZE fallback** — no intermediate between LoFTR and template match for cases where LoFTR is unavailable
- **Logo/subtitle mask** — static overlays not excluded from alignment
- **Shot-cut detection** — no NCC-based consecutive-frame cut detector at extraction or pre-stitch time

---

## 7. Optimization Proposals by Stage

### 7.1 Frame Extraction Improvements

#### 7.1.1 IVTC Support (High Priority)

Add VapourSynth-based IVTC as an optional extraction mode:

```python
# Proposed FFmpeg filter chain for telecined content
filters = ["fieldmatch=order=tff", "decimate"]   # TFF or BFF depending on source
# or VapourSynth: vspipe with tivtc/vivtc
```

For sources where IVTC is uncertain, add a per-frame interlace detection pass: compare top/bottom fields — if the inter-field difference exceeds a threshold at high-frequency components, the frame is interlaced.

#### 7.1.2 NCC-Based Shot Cut Detection

Before extraction, run a quick NCC sweep on heavily downsampled (64px wide) consecutive frames:

```python
# Proposed pre-filter
def detect_cuts(cap, start_ms, end_ms, ncc_drop_thresh=0.4):
    """Returns list of (cut_start_ms, cut_end_ms) pairs."""
    prev_thumb = None
    cuts = []
    while ...:
        thumb = cv2.resize(frame, (64, 36))
        if prev_thumb is not None:
            ncc = cv2.matchTemplate(prev_thumb, thumb, cv2.TM_CCORR_NORMED)[0,0]
            if ncc < ncc_drop_thresh:
                cuts.append(current_ms)
        prev_thumb = thumb
    return cuts
```

This is fast (64px images) and provides auto-populated cuts for the `cuts_ms` list.

#### 7.1.3 Correct Color Matrix for BT.601 vs BT.709

```python
# Smart extraction: add color space metadata
cmd.extend([
    "-vf", f"{','.join(filters)},colorspace=all=bt709:iall=bt601:fast=1"
    # Only if source is SD (BT.601); HD sources are typically already BT.709
])
```

### 7.2 Pre-Processing Stage Improvements

#### 7.2.1 Apply BaSiC b_i Correction in the Median Renderer

```python
# In _render_median, before stacking:
if self._basic is not None and self._basic.baselines is not None:
    for i in range(N):
        b_i = float(self._basic.baselines[i])
        if abs(b_i - 1.0) > 0.05:  # only correct significantly dimmed/brightened frames
            frames[i] = self._basic.apply_correction(frames[i], baseline_override=b_i)
```

This corrects broadcast dimming before the median stack, which is safe because we're not trying to match across seams — we're just normalizing the temporal stack.

#### 7.2.2 Static Overlay Detection & Masking

After dark-border trimming, detect static overlays (logos, subtitles, Nico Nico comments) by temporal analysis:

```python
def _detect_static_overlays(frames):
    """Returns a (H,W) uint8 mask; 0 = dynamic (safe), 255 = static overlay (exclude from alignment)."""
    # Temporal standard deviation: high std = changing content = good for alignment
    # Low std = static overlay OR background (both should be treated differently)
    # Cross-reference with position: corners/edges = likely logo; center = likely dynamic
    stack = np.stack([f.astype(np.float32) for f in frames[:min(len(frames), 30)]])
    temporal_std = stack.std(axis=0).mean(axis=2)   # (H, W)
    # Low std AND located in corners/edges → static overlay
    ...
```

### 7.3 Feature Matching Improvements

#### 7.3.1 Animation Phase Separation (Critical New Feature)

This addresses Spillerrec's animation-in-pan problem. The algorithm:

**Step 1 — Animation Region Detection:**
Compute per-pixel temporal standard deviation across the frame stack (already done above for overlay detection but with a different purpose). Regions with std that is low (background, static) vs. high but spatially coherent (repeating animation) can be distinguished.

**Step 2 — Phase Clustering:**
For each pair of consecutive frames, compute the absolute difference in the detected "animation region." Cluster frames by their animation phase using a global threshold on this difference:

```python
def cluster_animation_frames(frames, bg_masks, animation_region_mask):
    """
    Groups frames by animation phase using edge-image comparison.
    Returns list of frame-index groups, one per animation phase.
    
    Spillerrec's technique: compare edge-detected images instead of raw pixels
    to avoid noise corruption on the threshold.
    """
    N = len(frames)
    # Use edge image for comparison (Spillerrec's proposed improvement)
    edge_frames = [cv2.Canny(frame[animation_region_mask], 50, 150) for frame in frames]
    
    # Build distance matrix between animation phases
    diffs = np.zeros((N, N))
    for i in range(N):
        for j in range(i+1, N):
            diff = cv2.absdiff(edge_frames[i], edge_frames[j]).mean()
            diffs[i,j] = diffs[j,i] = diff
    
    # Cluster by threshold (Spillerrec: manual global threshold; we can automate via Otsu)
    thresh = cv2.threshold(diffs.ravel().astype(np.uint8), 0, 255, cv2.THRESH_OTSU)[0]
    # ... agglomerative clustering with distance threshold
    # Return groups: frames in each group have the same animation phase
    return groups
```

**Step 3 — Per-Phase Stitching:**
Run the full median-render pipeline separately for each animation phase group. The resulting panoramas can be optionally combined (taking the best-quality one) or used for in-betweening.

This is the most impactful single addition to the pipeline for content with repeating animations.

#### 7.3.2 Hann Window for Phase Correlation

```python
# In _phase_correlate:
hann = cv2.createHanningWindow(g_i.shape[::-1], cv2.CV_32F)
shift, response = cv2.phaseCorrelate(g_i * hann, g_j * hann)
```

This suppresses edge discontinuity artifacts and typically doubles the response quality. A one-line fix.

#### 7.3.3 AKAZE Fallback Between LoFTR and Template Matching

AKAZE uses nonlinear diffusion scale space (M-LDB descriptors), which respects cartoon edges better than DoG-based SIFT. Add it to the fallback chain:

```python
# In _match_pair, between LoFTR and template:
if M is None:
    M, mean_conf = self._akaze_match(img_i, img_j, m_i, m_j)
```

```python
@staticmethod
def _akaze_match(img_i, img_j, m_i, m_j):
    """AKAZE fallback matcher with collinearity rejection."""
    akaze = cv2.AKAZE_create()
    kp1, des1 = akaze.detectAndCompute(_luma(img_i), m_i)
    kp2, des2 = akaze.detectAndCompute(_luma(img_j), m_j)
    if des1 is None or des2 is None or len(des1) < 8:
        return None, 0.0
    
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(bf.match(des1, des2), key=lambda m: m.distance)[:200]
    
    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches])
    
    # Collinearity check: reject if convex hull area / num_points is too small
    if _is_collinear(pts1):
        return None, 0.0
    
    M, inliers = cv2.estimateAffinePartial2D(
        pts1, pts2, method=cv2.USAC_MAGSAC,
        ransacReprojThreshold=2.0, confidence=0.999
    )
    if M is None or (inliers is not None and inliers.sum() < 12):
        return None, 0.0
    return M.astype(np.float32), float(inliers.sum()) / len(matches)
```

#### 7.3.4 Fix `find_optimal_sequence` to Use Phase Correlation + ECC

The sequence ordering function should use the same matching hierarchy as the main pipeline, not SIFT. A simple replacement:

```python
@staticmethod
def find_optimal_sequence_v2(ref_path, candidates, ...):
    """Uses phase correlation for coarse overlap estimation."""
    for p in candidates:
        img_i, img_j = cv2.imread(ref_path), cv2.imread(p)
        # Downsample to 256px wide for speed
        scale = 256 / img_i.shape[1]
        s_i = cv2.resize(_luma(img_i), (256, int(img_i.shape[0]*scale)))
        s_j = cv2.resize(_luma(img_j), (256, int(img_j.shape[0]*scale)))
        shift, response = cv2.phaseCorrelate(
            _highpass(s_i), _highpass(s_j)
        )
        if response > 0.15:
            dist = np.sqrt(shift[0]**2 + shift[1]**2)
            # Use response as confidence, dist as overlap extent
```

### 7.4 Bundle Adjustment & ECC Improvements

#### 7.4.1 Use Actual LoFTR pts_j in BA

Currently BA synthesizes pts_j from the translation:
```python
pts_j = pts_i + M[:2, 2]   # WRONG: uses initial estimate, not actual matches
```

Fix: pass actual matched background points from LoFTR through the edge dict.

#### 7.4.2 Adaptive ECC Drift Cap

Scale `_ECC_MAX_DRIFT` with frame dimensions:
```python
_ECC_MAX_DRIFT = max(20.0, min(80.0, 0.05 * max(H, W)))
# 5% of larger dimension, clamped to [20, 80] px
```

#### 7.4.3 ECC on Y' Only, Not RGB

Currently `_ecc_refine` calls `_luma()` — this is correct. But it uses `cv2.INTER_AREA` for downsampling which is correct for downsizing. The ECC Gaussian filter `gaussFiltSize=5` should be reduced to 3 for clean BD sources.

### 7.5 Rendering Improvements

#### 7.5.1 Wire Up `_seam_dp` in `_render_laplacian`

The function exists but isn't called. Add it before the Laplacian blend:

```python
# In _render_laplacian, replace distance transform blend with DP seam:
for i in range(1, N):
    overlap = (canvas_m > 0) & (m_i > 0)
    if overlap.any():
        # Find the predominant pan direction
        is_vertical = (overlap.sum(axis=0).mean() > overlap.sum(axis=1).mean())
        seam_path = _seam_dp(canvas.astype(np.uint8), img.astype(np.uint8), horizontal=is_vertical)
        # Create a hard binary mask from the seam path
        seam_mask = _seam_path_to_mask(seam_path, H, W, is_vertical)
        # Laplacian blend with seam mask (sharp seam, smooth low-frequency)
        canvas = _laplacian_blend(img.astype(np.uint8), canvas.astype(np.uint8), seam_mask, self.bands)
```

#### 7.5.2 Region-Stratified Color Transfer

Replace the global gain match in `_render_laplacian` with palette-cluster matching:

```python
def _match_colors_stratified(src, ref, src_m, ref_m, k=6):
    """
    Apply Reinhard color transfer per palette cluster.
    Only operates on background-masked pixels.
    """
    src_bg = src[src_m > 0].reshape(-1, 3).astype(np.float32)
    ref_bg = ref[ref_m > 0].reshape(-1, 3).astype(np.float32)
    
    # k-means on Lab space (more perceptually uniform than RGB)
    src_lab = cv2.cvtColor(src_bg.reshape(1,-1,3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1,3)
    ref_lab = cv2.cvtColor(ref_bg.reshape(1,-1,3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1,3)
    
    # Cluster source
    _, src_labels, src_centers = cv2.kmeans(src_lab.astype(np.float32), k, ...)
    # Match ref clusters to source clusters by centroid distance (Hungarian)
    # Apply Reinhard per matched cluster pair
    ...
```

This is the key fix for bimodal-histogram color correction that global gain cannot handle.

#### 7.5.3 16-Bit Intermediate Rendering

For BD sources (where frames are extracted as 16-bit PNGs), render the canvas in float32 and only quantize at the final save:

```python
# Render in float32 throughout; apply dithering on final save
canvas = np.zeros((H, W, 3), dtype=np.float32)
# ...median/blend operations in float32...
# Final output:
canvas_16bit = np.clip(canvas, 0, 65535).astype(np.uint16)
# Save as 16-bit PNG using cv2.imwrite with IMWRITE_PNG_COMPRESSION
```

This prevents banding in flat anime gradients (a well-known artifact when 8-bit averaging introduces posterization).

### 7.6 Post-Processing / Upsampling

#### 7.6.1 Deconvolution for MPEG Blur Recovery

After temporal averaging, the result is sharper than any single source frame but still has MPEG encoding softness. A blind or Wiener deconvolution with a small kernel (3×3 to 7×7) can recover some high-frequency content:

```python
import cv2
def deconvolve_wiener(img, kernel_size=5, noise_level=0.01):
    """Simple Wiener deconvolution. Better than sharpening without ringing."""
    # Estimate PSF from the image (or use fixed Gaussian PSF for MPEG)
    psf = cv2.getGaussianKernel(kernel_size, 0) @ cv2.getGaussianKernel(kernel_size, 0).T
    # Wiener: H_w = H*/(|H|^2 + K), K = noise_level
    # ... implemented via DFT
```

#### 7.6.2 Anime-Specific Super-Resolution as Final Step

Wire up Real-ESRGAN-anime or waifu2x as an optional final step:

```python
# Post-processing: if upscale factor > 1, apply AnimeJaNai/waifu2x
if pipeline_config.get("upscale_factor", 1) > 1:
    from backend.src.models.esrgan_wrapper import EsrganWrapper
    canvas = EsrganWrapper().upscale(canvas, factor=pipeline_config["upscale_factor"])
```

---

## 8. New Ideas to Explore

### 8.1 Temporal Phase Coherence for Animation Detection

**Idea:** Instead of a threshold-based frame classifier, use Fourier analysis on the per-pixel temporal signal to detect and isolate cyclic animations.

For each pixel (x, y), the temporal signal `s(t)` over N frames should be near-constant for background pixels and oscillatory for animation pixels. The dominant frequency of `s(t)` for animation pixels will match the animation cycle (typically 2-4 frames, i.e., 6-12 Hz at 24fps). A per-pixel DFT can identify:
- DC component magnitude → background contribution
- Peak non-DC frequency → animation frequency (if any)

This gives a **continuous** classification instead of a binary threshold, and allows reconstruction of the animation-phase-decomposed background directly from the frequency domain rather than requiring hard clustering.

**Implementation sketch:**
```python
def temporal_phase_decomposition(frames, affines, canvas_h, canvas_w):
    """
    Warp all frames to the canvas. For each canvas pixel, compute
    the temporal DFT. The DC component gives the background; 
    the dominant AC frequency gives the animation cycle.
    Returns: background (DC), animation_phases [(freq, phase_images)]
    """
    N = len(frames)
    # Warp all frames to canvas coordinates
    warped = [cv2.warpAffine(f, M, (canvas_w, canvas_h)) for f, M in zip(frames, affines)]
    stack = np.stack(warped, axis=0).astype(np.float32)  # (N, H, W, 3)
    
    # Per-pixel FFT along temporal axis
    spectrum = np.fft.rfft(stack, axis=0)  # (N//2+1, H, W, 3)
    
    # Background = DC component
    background = np.abs(spectrum[0]) / N
    
    # Dominant AC frequency per pixel
    ac_power = np.abs(spectrum[1:]).max(axis=0)  # (H, W, 3)
    animation_mask = ac_power > threshold  # high AC power = animation
    
    return background, animation_mask, spectrum
```

### 8.2 Trapped-Ball Segmentation for Region-Level Matching

Traditional feature matching operates at the pixel level. For anime, the natural unit is the **color region** (the filled area between ink outlines). Trapped-ball segmentation (SIGGRAPH Asia 2024 *Fast Leak-Resistant Segmentation*) reliably decomposes line art into its filled regions.

**Application to stitching:**
1. Run trapped-ball on a representative frame to get region labels
2. For each region, compute a "region descriptor" (centroid, color mode, area, bounding box)
3. Match regions across frames by multi-feature similarity (color + spatial proximity)
4. Use region centroid displacements as robust correspondences for the BA

This is more robust than pixel matches on flat-color art because regions are large enough to localize reliably, and their color mode is stable across frames (unlike individual pixel values which vary with MPEG noise).

### 8.3 MSER for Flat-Color Blob Detection

Maximally Stable Extremal Regions (MSER) detects flat-color blobs rather than corners/edges. For anime backgrounds, MSER would find the large uniform patches (sky, walls, ground) and provide their bounding rectangles as candidate correspondence regions. This directly exploits the anime-specific signal structure (large flat regions) that other detectors treat as a nuisance.

```python
mser = cv2.MSER_create(_min_area=500, _max_area=50000)
regions, _ = mser.detectRegions(luma_frame)
# For each region: compute centroid, color mode, area
# Match across frames by centroid proximity + color similarity
```

MSER combined with AKAZE on the line-art edges gives complementary coverage: MSER covers the flat regions (where all classical detectors fail), AKAZE covers the high-contrast edges. Together they produce a well-distributed spatial set of correspondences.

### 8.4 LoFTR Confidence Map as a Seam-Cost Weight

LoFTR produces a per-match confidence score. Currently we use this for inlier filtering but discard it afterwards. Instead, project the LoFTR confidence map onto the canvas (interpolating between match locations) and use it as an additional term in the seam energy:

```
E_seam(path) = Σ_pixels [ color_diff(pixel) + gradient_diff(pixel) - λ * loftr_conf(pixel) ]
```

Routing the seam through regions of **high LoFTR confidence** ensures the seam passes through areas where the registration is known to be accurate, reducing residual seam artifacts.

### 8.5 VapourSynth Integration for Broadcast Dimming Reversal

The reports cite Python tools operating alongside VapourSynth to detect and reverse broadcast dimming via temporal analysis of peak luminance. This could be implemented as a pre-processing pass:

```python
def detect_dimming_profile(frames):
    """
    Detect broadcast-dimming using peak luminance tracking.
    Returns per-frame dimming factor (1.0 = no dimming, 0.7 = 30% dimmed).
    """
    peak_luminances = [_luma(f).max() for f in frames]
    # Smooth to find the undimmed reference level
    undimmed_ref = np.percentile(peak_luminances, 90)  # 90th percentile = typical undimmed
    dimming_factors = np.array(peak_luminances) / undimmed_ref
    return np.clip(dimming_factors, 0.5, 1.0)   # clamp to reasonable range

def undim_frame(frame, factor):
    return np.clip(frame.astype(np.float32) / factor, 0, 255).astype(np.uint8)
```

This is a standalone pre-processing step that doesn't depend on VapourSynth and provides the `b_i` corrections that BaSiC detects but doesn't apply.

### 8.6 Differentiable Stitching Awareness (AnimeStitchNet)

The pipeline already has a stub for `AnimeStitchNet` (from `backend/src/models/stitch_net.py`). The idea of a lightweight CNN or transformer trained specifically on anime frame pairs to predict the translation offset is promising:

- **Training signal:** Synthetic panning pairs generated from anime background art with known ground-truth offsets, augmented with MPEG noise, broadcast dimming, and character overlays
- **Network output:** (dx, dy) or a confidence-weighted translation distribution
- **Inference speed:** A 2-layer CNN on 128×128 crops can run in <10ms on CPU
- **Key advantage:** The network can be trained to ignore MPEG block boundaries and character regions without explicit masking

This is the "zero-shot" solution to the anime stitching problem: skip all the explicit photometric assumptions and just train the model to predict the right offset directly from the image pair. The existing `AnimeStitchNet` structure in `backend/src/models/stitch_net.py` and the training pipeline in `backend/src/pipeline/stitch_trainer.py` provide the scaffolding to realize this.

### 8.7 Parallax Layer Separation with Optical Flow

For scenes with obvious multi-plane parallax (foreground trees moving faster than background mountains), the current pipeline can only align one layer. BiRefNet gives the foreground/background split, but the background itself may have multiple depth layers.

A flow-based approach:
1. Run RAFT or GMFlow between consecutive frame pairs (GPU)
2. Cluster the flow vectors by magnitude and direction (DBSCAN or k-means)
3. Each cluster corresponds to one depth layer moving at the same speed
4. Run independent translation estimation for each layer
5. Composite the layers in depth order

This is expensive (optical flow on all pairs) but produces the highest quality result for complex multi-plane compositions.

### 8.8 Deep Seam Prediction (DSeam)

Replace the DP seam finder with a learned seam predictor trained on anime stitching pairs:

- DSeam (arXiv 2302.05027) achieves 15× faster seam finding than GraphCut with equal or better quality
- For anime, fine-tune on pairs where the ground-truth seam is routed through flat-color regions (avoiding line art)
- The selection consistency loss ensures seams are stable under small alignment perturbations

### 8.9 Palette-Consistent Frame Stacking

For the temporal median render, frames don't just need photometric normalization — they need **palette consistency**. Anime production uses a strict color chart (sakuga.fandom: "settei") where the same character/background is always rendered with the same few colors. If MPEG quantization has shifted a color by 2-3 units, the median will produce a slightly different color than any individual frame had.

**Solution:** Before stacking, apply a palette-snap to each frame:
```python
def palette_snap(frame, reference_palette, tolerance=8):
    """Snap each pixel to the nearest palette entry if within tolerance."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
    for color in reference_palette:
        color_lab = cv2.cvtColor(np.array([[color]]).astype(np.uint8), cv2.COLOR_BGR2LAB)[0,0].astype(np.float32)
        dist = np.linalg.norm(lab - color_lab, axis=2)
        snap_mask = dist < tolerance
        lab[snap_mask] = color_lab
    return cv2.cvtColor(lab.clip(0,255).astype(np.uint8), cv2.COLOR_LAB2BGR)
```

After palette-snapping, the median of N copies of the same color is exactly that color. This is the anime-specific equivalent of the Pokémon-Shock correction — it recovers the clean flat color from MPEG-noisy frames before averaging.

---

## 9. Priority Matrix & Roadmap

### Priority 1 — High Impact, Relatively Low Complexity

| Improvement | File | Lines Changed | Impact |
|---|---|---|---|
| Hann window in phase correlation | `anime_stitch_pipeline.py:1096` | 2 lines | Medium — improves PC reliability |
| Apply BaSiC b_i in median render | `anime_stitch_pipeline.py:1317` | ~15 lines | High — eliminates dimming seams |
| Wire up `_seam_dp` in blend renderer | `anime_stitch_pipeline.py:1456` | ~20 lines | High — proper seam vs. feather |
| Fix pts_j synthesis in BA | `anime_stitch_pipeline.py:935` | ~5 lines | Medium — more accurate BA |
| Adaptive ECC drift cap | `anime_stitch_pipeline.py:1149` | 2 lines | Low — edge case fix |
| Background-masked gain in laplacian | `anime_stitch_pipeline.py:1447` | ~5 lines | Medium — prevents character-driven gain |
| IVTC filter in smart extraction | `frame_extractor_worker.py:159` | ~5 lines | High — critical for SD anime |
| Auto shot-cut detection | `frame_extractor_worker.py` | ~30 lines | High — prevents wrong sequence |

### Priority 2 — High Impact, Moderate Complexity

| Improvement | New File/Function | Prerequisite |
|---|---|---|
| Animation phase separation (Spillerrec technique) | `_cluster_animation_frames()` in pipeline | BiRefNet mask quality, edge-based comparison |
| Region-stratified color transfer | `_match_colors_stratified()` | k-means on Lab, Hungarian matching |
| AKAZE fallback in matching chain | `_akaze_match()` in pipeline | Collinearity check, USAC_MAGSAC |
| Fix `find_optimal_sequence` to use phase corr | Replace SIFT in static method | Phase correlation infrastructure |
| Broadcast dimming reversal pre-processing | `detect_dimming_profile()` pre-stage | Peak luminance tracking |

### Priority 3 — Research & High Complexity

| Improvement | Dependencies | Notes |
|---|---|---|
| Temporal phase coherence (Fourier animation detection) | FFT memory budget | Most principled solution to animation problem |
| Trapped-ball region matching | SIGGRAPH Asia 2024 implementation | Requires anime-specific segmentation library |
| EfficientLoFTR upgrade | kornia >=0.7.x | Drop-in replacement; better speed profile |
| ToonOut fine-tuned BiRefNet | Hugging Face weights | 4.2 percentage point accuracy improvement |
| 4× super-resolution canvas (Overmix technique) | Memory: 16× canvas size | Exceptional quality but memory-expensive |
| AnimeStitchNet training pipeline | Custom dataset, GPU training | Long-term: replaces whole matching chain |
| Palette-snap pre-processing | Color extraction from settei | Niche but very effective for BD sources |
| Deconvolution post-processing | scipy.signal or pytorch | Requires careful PSF estimation |

---

## References

1. Spillerrec, "Stitching anime screenshots in overdrive" (2013): https://spillerrec.dk/2013/02/stitching-anime-screenshots-in-overdrive/
2. Spillerrec, "A year of overmixing" (2014): https://spillerrec.dk/2014/01/a-year-of-overmixing/
3. Spillerrec, Overmix category: https://spillerrec.dk/category/software/programs/overmix/
4. Brown & Lowe, "Automatic Panoramic Image Stitching using Invariant Features", IJCV 2007
5. Sun et al., "LoFTR: Detector-Free Local Feature Matching with Transformers", CVPR 2021
6. Zaragoza et al., "As-Projective-As-Possible Image Stitching with Moving DLT", CVPR 2013
7. Boykov & Jolly, "Interactive Graph Cuts", ICCV 2001
8. Agarwala et al., "Interactive Digital Photomontage", SIGGRAPH 2004
9. Burt & Adelson, "A Multiresolution Spline", ACM TOG 1983
10. Pérez, Gangnet & Blake, "Poisson Image Editing", SIGGRAPH 2003
11. Schaefer, McPhail & Warren, "Image Deformation Using Moving Least Squares", SIGGRAPH 2006
12. ToonOut (Muratori & Seytre), arXiv:2509.06839, 2025
13. EfficientLoFTR, CVPR 2024
14. Region-Wise Correspondence Prediction between Manga Line Art Images, arXiv:2509.09501
15. DSeam: Deep Seam Prediction for Image Stitching, arXiv:2302.05027
