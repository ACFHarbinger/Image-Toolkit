# Image Stitching Pipelines — Architecture Reference

This document provides detailed Mermaid diagrams for the two anime/scan stitching pipelines:

- **`_merge_images_scan_stitch`** — lightweight OpenCV SCANS-mode baseline (10 steps)
- **`perfect_stitch` / `AnimeStitchPipeline`** — 13-stage research pipeline with deep-learning models, bundle adjustment, temporal rendering, and hard-partition compositing

The diagrams are intentionally verbose: every algorithmic parameter, conditional branch, model, and fallback path is documented.

> **Mermaid compatibility:** All diagrams target v8.8.0. `direction` inside subgraphs and `~~~` links require v9+ and are not used here.

---

## 1. High-Level Pipeline Comparison

### 1a. `_merge_images_scan_stitch` (simple)

```mermaid
flowchart TD
    S1["Read images - cv2.imread"] --> S2["cv2.Stitcher - mode=SCANS 1"]
    S2 --> S3["setRegistrationResol 0.8"]
    S3 --> S4["stitch()"]
    S4 --> S5["BGR to RGB - Save output"]
```

### 1b. `perfect_stitch` / `AnimeStitchPipeline` (13 stages)

```mermaid
flowchart TD
    A1["Stage 1: Load + dark-border trim"] --> A2["Stage 2: Lanczos width normalise"]
    A2 --> A3["Stage 3: BaSiC photometric correction"]
    A3 --> A4["Stage 4: BiRefNet foreground masking"]
    A4 --> A45["Stage 4.5: Background photometric normalise"]
    A45 --> A56["Stages 5-6: Pairwise feature matching"]
    A56 --> A7["Stage 7: Global bundle adjustment - LM"]
    A7 --> A8["Stage 8: ECC sub-pixel refinement"]
    A8 --> A9["Stage 9: Canvas geometry sizing"]
    A9 --> A10["Stage 10: Temporal renderer - median / first / blend"]
    A10 --> MFSR["Optional MFSR super-resolution pass"]
    MFSR --> A11["Stage 11: Hard-partition foreground composite"]
    A11 --> A13["Stage 13: Morphological boundary crop"]
    A13 --> DONE["Save PNG / WEBP"]
```

---

## 2. `_merge_images_scan_stitch` — Detailed Flowchart

**Source:** `backend/src/core/image_merger.py:129`

This method wraps OpenCV's built-in SCANS stitcher with minimal preprocessing. It is also used as the fallback inside `AnimeStitchPipeline` when no valid feature edges are found.

```mermaid
flowchart TD
    IN["image_paths: List[str] / output_path: str"] --> NOCL
    NOCL["cv2.ocl.setUseOpenCL(False)\nPrevents malloc corruption in OpenCL path"] --> L1

    L1["for path in image_paths:\n  img = cv2.imread(path)"] --> L2{"img is None\nor img.size == 0?"}
    L2 -- "yes" --> L3["warn + skip"]
    L2 -- "no" --> L4["append to cv_images"]
    L3 --> VALID
    L4 --> VALID

    VALID{"len(cv_images) < 2?"} -- "yes" --> ERR["raise ValueError:\nNeed at least 2 valid images"]
    VALID -- "no" --> C1

    C1["try: cv2.Stitcher_create(mode=1)\nSCANS mode - affine/flat transforms"] --> C2
    C2["except AttributeError:\ncv2.createStitcher(True)\nLegacy OpenCV fallback"] --> RESOL

    RESOL["stitcher.setRegistrationResol(0.8)\nHardcoded: 0.8 - default is 0.6\nHigher = more keypoints = better for small overlaps"] --> STITCH

    STITCH["status, pano = stitcher.stitch(cv_images)"] --> CLEANUP
    CLEANUP["cv2.destroyAllWindows()\nForce-release highgui / Qt resources"] --> CHECK

    CHECK{"status == cv2.Stitcher_OK?"} -- "no" --> ERRMAP
    CHECK -- "yes" --> CONV

    ERRMAP["Map error code:\n  ERR_NEED_MORE_IMGS\n  ERR_HOMOGRAPHY_EST_FAIL\n  ERR_CAMERA_PARAMS_ADJUST_FAIL\nraise RuntimeError"]

    CONV["cv2.cvtColor(pano, BGR to RGB)\nImage.fromarray(pano_rgb)"] --> SAVE
    SAVE["merged_image.save(output_path)\nreturn Image"]
```

### Key Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Stitcher mode | `1` (SCANS — affine/flat) | Hardcoded |
| Registration resolution | `0.8` | Hardcoded (OpenCV default is 0.6) |
| OpenCL | Disabled | Hardcoded (prevents malloc corruption) |
| Feature detector | ORB/AKAZE (OpenCV default) | Inside OpenCV |
| Matcher | BFMatcher / FLANN | Inside OpenCV |
| Homography | RANSAC | Inside OpenCV |

---

## 3. `perfect_stitch` / `AnimeStitchPipeline` — Full Pipeline

**Entry point:** `backend/src/core/image_merger.py:737`
**Orchestrator:** `backend/src/anim/pipeline.py:87`

### 3.1 Parameter Resolution Chain

```mermaid
flowchart LR
    D["Hard-coded defaults\nin perfect_stitch()"] --> Y["stitch.yaml\nbackend/config/core/stitch.yaml"]
    Y --> K["Explicit kwargs\ncall-site overrides"]
    K --> FINAL["Resolved params\npassed to AnimeStitchPipeline(**params)"]
```

### Default Parameter Values

| Parameter | Default | Type | Description |
|-----------|---------|------|-------------|
| `use_basic` | `False` | bool | Enable BaSiC flat-field correction |
| `use_birefnet` | `True` | bool | Enable BiRefNet foreground masking |
| `use_loftr` | `True` | bool | Enable LoFTR dense matching |
| `use_ecc` | `False` | bool | Enable ECC sub-pixel refinement |
| `renderer` | `"median"` | str | `"median"` / `"first"` / `"blend"` |
| `composite_fg` | `True` | bool | Hard-partition foreground composite |
| `motion_model` | `"translation"` | str | `"translation"` (2-DOF) / `"affine"` (4-DOF) |
| `edge_crop` | `80` | int | Pixels to crop from all sides at output |
| `laplacian_bands` | `8` | int | Bands for multi-band blend renderer |
| `mfsr_mode` | `False` | bool | Enable MFSR super-resolution pass |
| `mfsr_n_dct_iter` | `20` | int | DCT restoration iterations |
| `mfsr_use_prior` | `True` | bool | Enable prior injection in MFSR |
| `mfsr_use_diffusion` | `False` | bool | Enable diffusion inpainting in MFSR |
| `stitch_net_ckpt` | `""` | str | Path to AnimeStitchNet checkpoint |

---

### 3.2 Stage 1 — Frame Loading and Dark-Border Trim

**Module:** `backend/src/anim/canvas.py:17` (`_load_frames`)
**Helper:** `backend/src/anim/stateless.py` (`_trim_dark_border`)

```mermaid
flowchart TD
    P["image_paths: List[str]"] --> R
    R["cv2.imread(path)"] --> NIL{"img is None?"}
    NIL -- "yes" --> SKIP["warn + skip frame"]
    NIL -- "no" --> TRIM["_trim_dark_border(img)\nDetects broadcast letterbox bars\nScans rows/cols for rows where\nmean pixel is below dark threshold\nCrops until non-dark content found"]
    TRIM --> APP["append to frames list"]
    SKIP --> CHECK
    APP --> CHECK
    CHECK{"len(frames) < 2?"} -- "yes" --> ERR["raise ValueError"]
    CHECK -- "no" --> NEXT["Stage 2"]
```

---

### 3.3 Stage 2 — Width Normalisation

**Module:** `backend/src/anim/canvas.py:30` (`_normalise_widths`)

```mermaid
flowchart TD
    IN["frames: List[ndarray]"] --> TW["target_w = frames[0].shape[1]"]
    TW --> CHECK{"w != target_w?"}
    CHECK -- "yes" --> RESIZE["cv2.resize\nInterpolation: INTER_LANCZOS4\nnh = round(h x target_w / w)\nPreserves aspect ratio"]
    CHECK -- "no" --> KEEP["keep as-is"]
    RESIZE --> OUT["Stage 3"]
    KEEP --> Out["Stage 3"]
```

---

### 3.4 Stage 3 — BaSiC Photometric Correction

**Module:** `backend/src/anim/photometric.py`
**Activated by:** `use_basic=True`

```mermaid
flowchart TD
    GATE{"use_basic == True\nAND _BASIC_OK?"} -- "no" --> SKIP["Stage 3 skipped"]
    GATE -- "yes" --> B1

    B1["BaSiCWrapper.fit(frames, luma_only=True)\nReturns: flat_field, dark, baselines\nbaselines = per-frame dimming scalar\nBroadcast dimming if b_i less than 0.75"] --> B2

    B2["Apply spatial flat-field ONLY\nbaseline_override=1.0\nPer-frame b_i correction intentionally skipped:\nApplying it destroys inter-frame brightness\ncontinuity causing colour seams at boundaries\nDeferred to _render_median at Stage 10"] --> V1

    V1["Sample luma from 5 evenly-spaced frames\nDownsample to 320px wide\nUse 75th percentile across stack"] --> V2

    V2["Fit quadratic vignette model:\nG(r) = 1 / (1 + k * r^2)\nvia scipy.least_squares\nbounds: k in range 0 to 0.5"] --> V3{"k_val less than 0.01?"}

    V3 -- "yes" --> V4["No vignette detected - skip correction"]
    V3 -- "no" --> V5["k_val *= 0.7 (soften)\nk_val *= 0.4 (conservative clamp)\nFinal effective multiplier: 0.28x\ngain_map = 1 + k_val * r_norm^2\nApply per-channel to all frames"]
    V4 --> NEXT["Stage 4\nbaselines list passed to Stage 10"]
    V5 --> NEXT
```

---

### 3.5 Stage 4 — BiRefNet Foreground Masking

**Module:** `backend/src/anim/masking.py` (`_compute_fg_masks`)
**Constants:** `_FOREGROUND_DILATION=16`, `_FOREGROUND_EROSION=8`

```mermaid
flowchart TD
    GATE{"use_birefnet == True\nAND _BIREFNET_OK?"} -- "no" --> NONE["Return None for each frame\nAll pixels treated as background"]
    GATE -- "yes" --> A1

    A1{"hasattr(wrapper,\nget_background_mask)?"} -- "New API" --> NEW
    A1 -- "Legacy API" --> LEG

    NEW["wrapper.get_background_mask(img,\n  dilate_px=16,\n  erode_px=8)\nResult: 255=background, 0=foreground\n_FOREGROUND_DILATION=16px safety margin\n_FOREGROUND_EROSION=8px boundary sharpening"]

    LEG["wrapper.get_mask(img) returns 255=foreground\nbg = bitwise_not(fg)\nManual dilation with elliptical kernel\nKernel size: 2*16+1 = 33px"]

    NEW --> OFFLOAD
    LEG --> OFFLOAD

    OFFLOAD["Offload BiRefNet from GPU\ntorch.cuda.empty_cache()\nFree VRAM before matching stage"] --> NEXT["bg_masks: List[Optional[ndarray]]\nStage 4.5"]
```

---

### 3.6 Stage 4.5 — Background Photometric Normalisation

**Module:** `backend/src/anim/pipeline.py:420` (inline in `run()`)

```mermaid
flowchart TD
    IN["frames + bg_masks"] --> S1

    S1["For each frame: sample pixels where bg_mask greater than 127\ncompute mean BGR colour"] --> S2{"len bg_pixels >= 1000?"}
    S2 -- "yes" --> S3["bg_frame_means[i] = pixel_mean"]
    S2 -- "no" --> S4["bg_frame_means[i] = None"]
    S3 --> COUNT
    S4 --> COUNT

    COUNT{"valid means >= 3?"} -- "no" --> SKIP["Skip normalisation"]
    COUNT -- "yes" --> N1

    N1["ref_mean = np.median(valid_means, axis=0)\nRobust median eliminates\nanime cel flicker / temporal brightness variation"] --> N2

    N2["For each frame with valid mean:\ngain = ref_mean / bg_frame_mean[i]\ngain = clip(gain, 0.88, 1.14)\nGain clamp prevents over-correction"] --> N3{"gain approx 1.0?"}

    N3 -- "no" --> N4["frames[i] = clip(frame * gain, 0, 255)"]
    N3 -- "yes" --> SKIP2["skip - no change needed"]
    N4 --> NEXT["Stages 5-6"]
    SKIP2 --> NEXT
```

---

### 3.7 Stages 5-6 — Pairwise Feature Matching

**Module:** `backend/src/anim/matching.py`

#### 3.7.1 Edge Graph Construction

```mermaid
flowchart TD
    N["N frames"] --> P1["Adjacent pairs i to i+1\nN-1 pairs"]
    N --> P2["Skip-1 pairs i to i+2\nN-2 pairs"]
    N --> P3["Skip-2 pairs i to i+3\nN-3 pairs"]
    P1 --> MATCH["_match_pair(i, j) for each pair"]
    P2 --> MATCH
    P3 --> MATCH
    MATCH --> FILTER["_filter_edges(edges)\nGeometric consistency + Direction consensus"]
    FILTER --> RESULT["edges: List[Dict]\nkeys: i, j, M 2x3, pts_i, pts_j, weight"]
```

#### 3.7.2 Per-Pair Matching Fallback Chain

```mermaid
flowchart TD
    START["_match_pair(frames, bg_masks, i, j)"] --> CROP

    CROP["Edge Crop pre-match distortion removal:\nec_h = H * 0.05  _MATCH_EDGE_CROP=0.05\nec_w = W * 0.05\nCrop 5% from all sides before matching"] --> ATT1

    ATT1["Attempt 1: LoFTR Dense Matching\nloftr_wrapper.match(img_i_c, img_j_c)\nReturns: pts1, pts2, conf"] --> L2{"len pts1 >= 30?"}
    L2 -- "no" --> ATT2_START
    L2 -- "yes" --> L3["Filter: keep only bg points\nboth masks greater than 127\n_MIN_LOFTR_INLIERS=20 required after filter"]
    L3 --> L4{"motion_model?"}
    L4 -- "translation" --> L5["dx = median(pts2[:,0] - pts1[:,0])\ndy = median(pts2[:,1] - pts1[:,1])\nM = [[1,0,dx],[0,1,dy]]"]
    L4 -- "affine" --> L6["cv2.estimateAffine2D\n  pts1, pts2\n  method=cv2.RANSAC\n  ransacReprojThreshold=5.0\nRequire at least 15 RANSAC inliers"]
    L5 --> DXCHECK{"dx valid?\nabs(dx) less than W * 0.01\n_MAX_DX_DRIFT_RATIO=0.01\nVertical pans have near-zero horizontal drift"}
    L6 --> DXCHECK
    DXCHECK -- "no" --> ATT2_START
    DXCHECK -- "yes" --> SUCCESS["M found - skip remaining attempts"]

    ATT2_START["Attempt 2: Template Match Fallback\n_template_match(img_i_c, img_j_c, mask_i, mask_j, H_c)"] --> T2
    T2["Bidirectional search:\nConfig A: bottom of i in top of j  dy greater than 0 downward pan\nConfig B: top of i in bottom of j  dy less than 0 upward pan\nslice_h=256  template strip height\nmax_search_frac=0.8  ROI = 80% of frame height\nmax_dy_frac=0.70  reject abs dy greater than 70% of H\nEnforces minimum 30% frame overlap\ndirection_sign=0 bidirectional by default\ncv2.matchTemplate TM_CCORR_NORMED with mask"] --> T4{"conf greater than 0.6\nAND conf greater than _MIN_TEMPLATE_SCORE 0.85?"}
    T4 -- "yes" --> SUCCESS2["M found"]
    T4 -- "no" --> ATT3A

    ATT3A["Attempt 3a: Masked Phase Correlation\ng_i = _highpass(_luma(img_i_c))\ng_j = _highpass(_luma(img_j_c))\nHigh-pass filter isolates edges removes DC\nZero out foreground pixels mask == 0\nPrevents moving characters biasing shift\nHanning window\ncv2.phaseCorrelate(g_i, g_j, hann)\nReturns shift=(dx,dy), response"] --> PC4{"response greater than 0.25\nabs(dx) less than W * 0.01?"}
    PC4 -- "yes" --> SUCCESS3["M found"]
    PC4 -- "no" --> ATT3B

    ATT3B["Attempt 3b: Unmasked Phase Correlation\nSame as 3a but use_mask=False\nCharacter provides dominant phase signal\nwhen background is uniform\nMinimum response: _PC_CONF_THRESHOLD=0.05"] --> PU2{"response greater than 0.15\nabs(dx) less than W * 0.01?"}
    PU2 -- "yes" --> SUCCESS4["M found"]
    PU2 -- "no" --> FAIL["All methods failed - edge dropped"]

    SUCCESS --> BUILD["Build edge dict:\nEnforce translation-only M\nrotation and scale locked to identity\nBuild pts_i / pts_j anchor points\nweight = mean_conf"]
    SUCCESS2 --> BUILD
    SUCCESS3 --> BUILD
    SUCCESS4 --> BUILD
```

#### 3.7.3 Edge Filter

```mermaid
flowchart TD
    EDGES["raw edges list"] --> G1

    G1["Geometric Consistency Filter:\nBuild adj_map: i to dx,dy for adjacent edges i to i+1"] --> G2["For each skip-pair edge i to j where j greater than i+1:\nsum adjacent dx,dy from i to j"]
    G2 --> G3{"diff_x less than 15.0\nAND diff_y less than 15.0?"}
    G3 -- "yes" --> G4["Keep edge"]
    G3 -- "no" --> G5["Reject: inconsistency"]
    G4 --> DIR
    G5 --> DIR

    DIR["Direction Consensus Filter - requires 3 or more adjacent edges:\nCollect dy values from all adjacent edges\nmedian_dy = np.median(adj_dys)\nconsensus_sign = sign(median_dy)"] --> D2

    D2["Estimate velocity from filename timestamps:\n_ts_pat: _(digits)ms pattern in filename\nvel_px_per_ms = median(dy_e / interval_ms)"] --> D3

    D3["For each adjacent edge i to i+1:\nwrong_sign: sign(dy) != consensus_sign\ngross_outlier: abs(dy) greater than 2 x abs(median_dy)\n              AND abs(dy - median_dy) greater than 200px\nvelocity outlier: abs(dy - expected) greater than max(15%, 15px)"] --> OUTCHECK{"outlier detected?"}

    OUTCHECK -- "yes" --> D4["Replacement priority:\n1. velocity estimate: M_fix dy = vel_px_per_ms * interval, weight=0.55\n2. directed template match direction_sign=consensus_sign, weight=conf*0.7\n3. median fallback: M_fix dy = median_dy, weight=original*0.3"]
    OUTCHECK -- "no" --> D5["Keep edge as-is"]
    D4 --> RESULT["Filtered edges - Stage 7"]
    D5 --> RESULT
```

---

### 3.8 Stage 7 — Global Bundle Adjustment

**Module:** `backend/src/anim/bundle_adjust.py` (`_bundle_adjust_affine`)

```mermaid
flowchart TD
    IN["edges, N frames, motion_model"] --> DOF{"motion_model == affine?"}

    DOF -- "yes" --> D2["4-DOF Partial Affine\nparams per frame: a, b, tx, ty\nMatrix: [[a, b, tx], [-b, a, ty]]\nPreserves aspect ratio\nPrevents fan / spiral distortion"]
    DOF -- "no" --> D3["2-DOF Translation only\nparams per frame: tx, ty\nMatrix: [[1,0,tx],[0,1,ty]]"]

    D2 --> INIT
    D3 --> INIT

    INIT["Initialisation x0:\nAll frames: identity a=1, b=0, tx=0, ty=0\nSequential forward pass:\n  for f in 1 to N:\n    tx_f = tx_(f-1) - M_raw[0,2]\n    ty_f = ty_(f-1) - M_raw[1,2]\nCanvas convention: ty_j = ty_i - dy\n(dy = y_j - y_i measured by LoFTR / PC)"] --> OPT

    OPT["scipy.optimize.least_squares\n  residuals, x0\n  method=trf\n  ftol=1e-6, xtol=1e-6, gtol=1e-6\n  max_nfev = iterations * N\n  iterations=200 hardcoded"] --> RES

    RES["Residual function:\nData term: (p_i_global - p_j_global) * weight\nAnchor term: (x[0:4] - identity) * 2000.0\n  Frame 0 pinned at identity reg_anchor=2000\nIdentity prior: (a_f - 1.0) * 1e5\n                (b_f - 0.0) * 1e5\n  Keeps a approx 1, b approx 0 globally"] --> OUT

    OUT["List of ndarray(2,3) - one per frame\nStage 8"]
```

---

### 3.9 Stage 8 — ECC Sub-Pixel Refinement

**Module:** `backend/src/anim/ecc.py` (`_ecc_refine`)
**Activated by:** `use_ecc=True`

```mermaid
flowchart TD
    GATE{"use_ecc == True?"} -- "no" --> SKIP["Stage 8 skipped\nKeep BA affines as-is"]
    GATE -- "yes" --> ITER

    ITER["For each frame i in 1 to N relative to i-1:\nref = _luma(frames[i-1])\nsrc = _luma(frames[i])\nmask = bg_masks[i-1]\nCompute relative transform init:\n  tx_rel = M_prev[0,2] - M_i[0,2]\n  ty_rel = M_prev[1,2] - M_i[1,2]"] --> PYR

    PYR["Gaussian Pyramid ECC coarse to fine:\nfor lvl in range(_ECC_PYRAMID_LEVELS-1, -1, -1):\n  _ECC_PYRAMID_LEVELS=4\n  scale = 2^lvl\n  r_s = resize(ref, 1/scale, INTER_AREA)\n  s_s = resize(src, 1/scale, INTER_AREA)\n  M_s = M_cur scaled by 1/scale"] --> P2

    P2["cv2.findTransformECC\n  r_s, s_s, M_s\n  cv2.MOTION_TRANSLATION\n  criteria: EPS|COUNT, _ECC_MAX_ITER=80, _ECC_EPS=1e-4\n  ecc_mask=bg_mask_scaled\n  gaussFiltSize=5\nScale result back: tx_s *= scale\nPropagate to next finer level"] --> CLAMP

    CLAMP{"abs(tx_new - tx_ba) greater than 80px\nOR abs(ty_new - ty_ba) greater than 80px?\n_ECC_MAX_DRIFT=80px"} -- "yes" --> CL2["Reject ECC result\nKeep BA result unchanged"]
    CLAMP -- "no" --> CL3["Accept ECC refined global affine"]
    CL2 --> OUT["Refined affines - Stage 9"]
    CL3 --> OUT
```

---

### 3.10 Stage 9 — Canvas Construction

**Module:** `backend/src/anim/canvas.py:43` (`_compute_canvas`)

```mermaid
flowchart TD
    IN["frames + affines"] --> CORNERS["For each frame i:\ncorners = [[0,0],[w,0],[w,h],[0,h]]\nwarped = M[:2,:2] @ corners.T + M[:2,2]\nCollect all warped corners"]
    CORNERS --> BBOX["min_xy = all_corners.min(axis=0)\nmax_xy = all_corners.max(axis=0)"]
    BBOX --> TG["T_global = -min_xy\ncanvas_w = ceil(max_xy[0] - min_xy[0])\ncanvas_h = ceil(max_xy[1] - min_xy[1])"]
    TG --> CAP["canvas_w = min(canvas_w, 32768)\ncanvas_h = min(canvas_h, 32768)\n_CANVAS_MAX_DIM=32768 OOM guard"]
    CAP --> OFFSET["Apply T_global to all affines:\naffines[i][0,2] += T_global[0]\naffines[i][1,2] += T_global[1]"]
    OFFSET --> NEXT["canvas_h, canvas_w - Stage 10"]
```

---

### 3.11 Stage 10 — Temporal Renderer

**Module:** `backend/src/anim/rendering.py`

```mermaid
flowchart TD
    DISP{"renderer param?"} -- "median" --> MED["_render_median()"]
    DISP -- "first" --> FIRST["_render_first()"]
    DISP -- "blend" --> BLEND["_render_laplacian()"]
    MED --> OUT["canvas, valid_mask, warped_corr, warped_fgs\nOptional MFSR - Stage 11"]
    FIRST --> OUT
    BLEND --> OUT
```

#### Median Renderer (default — Overmix temporal denoising)

```mermaid
flowchart TD
    M1["Sequential colour correction\n_compute_sequential_color_gains:\n  N_STRIPES=12 horizontal stripes per overlap\n  STRIPE_H=40 rows per stripe\n  MIN_BG_PX=200 bg pixels required\n  Robust: median ratio across stripes\n  Gain clamp: 0.88 to 1.12\n  Bias clamp: -20 to 20\n  MAX_SAFE_GAIN_DEV=0.14 suppress large corrections"] --> M2

    M2["Chunk rendering memory-safe:\nchunk_size = min(1024, 1GB / N*W*3)\nFor y0 to H in chunks:\n  warpAffine each frame into chunk\n    flags=INTER_LANCZOS4\n    borderMode=BORDER_CONSTANT\n  Apply BaSiC baselines if available:\n    scale = min(1/max(b_i, 0.5), 1.25)\n  Apply colour gain and bias correction\n  stack shape: N, chunk_h, W, 3"] --> M3

    M3["Pixel aggregation:\ncount==1: take single sample directly\ncount greater than 1: np.nanmedian(stack_f32, axis=0)\n  NaN-mask excludes unwarped pixels"] --> M4

    M4["Fade-in/out correction:\n_FADE_ROWS=250 rows each side of frame entry/exit\n_LANCZOS_BLEED=8px extension for Lanczos kernel bleed\nAlpha ramp: 0 to 1 entry or 1 to 0 exit\nBlend: (1-alpha)*med_without_i + alpha*med_with_i\nEliminates horizontal seam on new frame entry"] --> M5

    M5["Animation detection skipped if ty_span greater than 25% canvas H:\nPer-pixel FFT along temporal axis\nAC/DC power ratio: ratio = AC / (DC + AC)\nanim_mask: ratio greater than ac_threshold=0.25\nMorphological open+close with 5x5 ellipse kernel\nRequire min_anim_pixels=500\nRe-render animation region from majority phase group:\n  Edge-signature KMeans clustering\n  n_clusters = max(2, min(8, N//2))\n  n_init=5, random_state=0"]
```

#### First-Frame-Wins Renderer

```mermaid
flowchart TD
    F1["Process frames in reverse order\nwarpAffine with INTER_LINEAR\nEach frame overwrites earlier frames\nFirst frame wins for each pixel\nNo blending - fastest renderer"]
```

#### Laplacian Blend Renderer

```mermaid
flowchart TD
    BL1["Sequential colour matching frame by frame:\ngain = ref_std / src_std, clip 0.85 to 1.18\nbias = ref_mean - src_mean * gain, clip -15 to 15\nRequires more than 5000 overlap pixels"] --> BL2
    BL2["Sequential ROI blending:\nfeather=40px border around overlap bounding box\nDistance transform soft weight map\nFG pixels forced to weight=1.0 hard paste"] --> BL3
    BL3["_laplacian_blend(img, canvas, weight_roi)\nlaplacian_bands=8 from perfect_stitch default\nlaplacian_bands=5 pipeline constant _LAPLACIAN_BANDS"]
```

---

### 3.12 Optional MFSR Super-Resolution Pass

**Module:** `backend/src/anim/mfsr/`
**Activated by:** `mfsr_mode=True`

```mermaid
flowchart TD
    GATE{"mfsr_mode == True?"} -- "no" --> SKIP["Skip MFSR\nKeep median canvas"]
    GATE -- "yes" --> R1

    R1["PSO Registration - pso_registration.py\nPSO_SWARM_SIZE=40\nPSO_MAX_ITER=150\nPSO_INERTIA=0.729\nPSO_C1=PSO_C2=1.494 cognitive/social\nPSO_VEL_CLAMP=0.2"] --> R2

    R2["DRL Registration - drl_registration.py\nDRL_STATE_SIZE=256\nDRL_ACTION_DIM=4: dx, dy, dscale, dtheta\nDRL_GAMMA=0.99\nDRL_LR=1e-4\nDRL_MEMORY_SIZE=10000\nDRL_BATCH_SIZE=64"] --> S1

    S1["DCT Restoration - dct_restoration.py\nDCT_BLOCK_SIZE=8\nmfsr_n_dct_iter default 20\nStandard JPEG luminance quantization table\nReverse-quantizes compression artifacts"] --> S2

    S2["Prior Injection - prior_injection.py\nmfsr_use_prior default True\nInjects spatial frequency priors"] --> S3{"mfsr_use_diffusion?"}

    S3 -- "yes" --> S4["Diffusion Inpainting - diffusion_inpaint.py\nFill canvas gaps via score-based diffusion"]
    S3 -- "no" --> S5["DE Seam Removal - de_seam.py\nDE_POP_SIZE=30\nDE_MAX_GEN=100\nDE_F=0.8 mutation scale\nDE_CR=0.9 crossover rate"]
    S4 --> S5
    S5 --> REFRESH["Refresh valid_mask\nvalid = canvas.max(axis=2) greater than 0\nStage 11"]
```

---

### 3.13 Stage 11 — Hard-Partition Foreground Composite (Deghost)

**Module:** `backend/src/anim/compositing.py` (`_composite_foreground`)
**Activated by:** `composite_fg=True AND use_birefnet=True`

```mermaid
flowchart TD
    IN["canvas temporal median\nframes, affines, bg_masks"] --> CENTERS

    CENTERS["Strip ownership ordering:\nstrip_center_ys[i] = affines[i][1,2] + frame_h[i] / 2\norder = argsort(strip_center_ys)\ninitial_boundaries = midpoints between sorted centres"] --> WARP

    WARP["Warp all N frames to full canvas:\ncv2.warpAffine(frame, affine, W,H\n  flags=INTER_LANCZOS4\n  borderMode=BORDER_CONSTANT)"] --> PASS1

    PASS1["Pass 1 Boundary Search pre-normalisation:\n_find_optimal_boundaries on raw frames\n_SEARCH_RANGE=250px each side of midpoint\n_SEARCH_SLAB=20 row height for scoring\nScore = 0.4 * bg_diff + 0.6 * total_diff\nbg pixels preferred: both masks agree\nMinimum 50 valid pixels to score\nBoundaries spaced at least 2*_SEARCH_SLAB apart"] --> LSNORM

    LSNORM["Global Brightness Normalisation:\nLeast-squares log-gain minimisation:\n  min sum_k w_k*(alpha_k - alpha_{k+1} - log_ratio_k)^2 + lambda*sum_i*alpha_i^2\n  lambda=5e2 regularisation\nPrefer bg pixels: both frames agree, mu greater than 50\nFallback: all-pixel at weight*0.8\nGains clamped 0.70 to 1.45\nApply per-frame gain in-place to warped_list"] --> PASS2

    PASS2["Pass 2: Re-run boundary search on normalised frames\nAdaptive feather lookup _FEATHER_TABLE:\n  diff <=  5.0: feather=300px\n  diff <= 10.0: feather=250px\n  diff <= 20.0: feather=200px\n  diff <= 35.0: feather=150px\n  diff <= 50.0: feather=100px\n  diff >  50.0: feather= 80px  _FEATHER_MIN\nCap: feather <= nat_overlap//2 AND <= _FEATHER_MAX=300"] --> SEAM

    SEAM["Per-boundary colour correction and DP seam paths:\nMeasure photometric calibration at overlap zone\nSLAB_HALF=25 rows each side of y_cut\nCompare SAME canvas rows in both frames\nPrefer bg pixels mu greater than 50, delta less than 12%\nGain clamp: GAIN_CLAMP_LOCAL = 0.72 to 1.40\nDP seam cut _seam_cut:\n  Energy = diff + 0.5*|grad(diff)|\n         + 15 * (edges_img1 + edges_img2)\n  edge_weight=15.0 avoids outlines in either frame\n  DP left to right pass on transposed matrix\n  Backtrack: minimum energy path\n  seam_path[x] = y-coordinate of cut at column x"] --> COMP

    COMP["Chunk composite CHUNK=512 rows:\nHard-partition rows outside seam zones:\n  strip_weights[owner_frame, y] = 1.0\n  weighted average by content presence\nSeam-zone rows:\n  Per-column cosine feather centred on DP path\n  d_seam = local_y - seam_path[x]\n  t_blend = clip(1 - abs(d_seam)/zone_half, 0, 1)\n  gain_fa = 1 + t_blend*(1/sqrt(gain_seam) - 1)\n  gain_fb = 1 + t_blend*(sqrt(gain_seam) - 1)\n  t_lin = clip((d_seam + zone_half)/(2*zone_half), 0, 1)\n  t_hf = 0.5*(1 - cos(pi*t_lin)) half-cosine\n  result = (1-t_hf)*fa_corr + t_hf*fb_corr"] --> RAMP

    RAMP["Post-composite seam colour ramp:\n_apply_canvas_seam_correction\nramp_half = min(250, half_above, half_below)\n_SEAM_MEAS_SLAB=40 rows for measurement\nTrigger: abs(delta) greater than _SEAM_STEP_THRESHOLD=1.5\nReject: ratio greater than _SEAM_MAX_RATIO=1.35 scene content\nGain clamp: _GAIN_CLAMP = 0.88 to 1.14\nApply cosine ramp over +/- ramp_half rows\nAbove seam: gain 1/sqrt(gains) at seam to 1.0 at far edge\nBelow seam: gain sqrt(gains) at seam to 1.0 at far edge"] --> OUT
    OUT["Updated canvas - Stage 13"]
```

---

### 3.14 Stage 13 — Boundary Crop

**Module:** `backend/src/anim/canvas.py:75` (`_crop_to_valid`)

```mermaid
flowchart TD
    IN["canvas + valid_mask"] --> C1["row_has_content = any(valid_mask > 0, axis=1)\ncol_has_content = any(valid_mask > 0, axis=0)\nr0..r1 = first and last row with content\nc0..c1 = first and last col with content\nO(H+W) projection-based crop"]
    C1 --> C2["canvas = canvas[r0:r1, c0:c1]"]
    C2 --> E1{"edge_crop > 0?"}
    E1 -- "yes" --> E2["canvas = canvas[ec:-ec, ec:-ec]\nDefault ec=80px in perfect_stitch\nDefault ec=30px in AnimeStitchPipeline init\nRemoves vignette and distortion from warped edges"]
    E1 -- "no" --> E3["skip edge crop"]
    E2 --> SAVE["cv2.cvtColor BGR to RGB\nImage.fromarray(rgb)\nout.save(output_path)\ngc.collect()"]
    E3 --> SAVE
```

---

## 4. Fallback Chain Summary

```mermaid
flowchart LR
    START["Frame pair i to j"] --> L1["LoFTR\n20+ bg inliers"]
    L1 -- "fail" --> L2["Template Match\nconf >= 0.85"]
    L2 -- "fail" --> L3["Phase Corr masked\nresponse >= 0.25"]
    L3 -- "fail" --> L4["Phase Corr unmasked\nresponse >= 0.15"]
    L4 -- "fail" --> L5["Edge dropped\npair skipped"]
    L5 -- "all pairs fail" --> L6["SCANS fallback\n_scan_stitch_fallback\nsame as _merge_images_scan_stitch"]
```

---

## 5. Module Dependency Map

```mermaid
graph TD
    PS["perfect_stitch\nimage_merger.py"] --> ASP["AnimeStitchPipeline\npipeline.py"]
    ASP --> CAN["canvas.py\n_load_frames\n_normalise_widths\n_compute_canvas\n_crop_to_valid\n_scan_stitch_fallback"]
    ASP --> PHOTO["photometric.py\n_apply_basic\n_correct_vignetting"]
    ASP --> MASK["masking.py\n_compute_fg_masks"]
    ASP --> MATCH["matching.py\n_pairwise_match\n_match_pair\n_template_match\n_phase_correlate"]
    ASP --> BA["bundle_adjust.py\n_bundle_adjust_affine"]
    ASP --> ECC["ecc.py\n_ecc_refine"]
    ASP --> REND["rendering.py\n_render\n_render_median\n_render_first\n_render_laplacian\n_cluster_animation_phases"]
    ASP --> COMP["compositing.py\n_composite_foreground"]
    ASP --> MFSR["mfsr/\nrun_mfsr\npso_register\nde_seam\nrestore_dct\napply_prior\ninpaint_gaps\nRegistrationAgent"]
    ASP --> CONST["constants.py\nall thresholds"]
    PHOTO --> BW["BaSiCWrapper\nmodels/basic_wrapper.py"]
    MASK --> BRN["BiRefNetWrapper\nmodels/birefnet_wrapper.py"]
    MATCH --> LOFTR["LoFTRWrapper\nmodels/loftr_wrapper.py"]
    SS["_merge_images_scan_stitch\nimage_merger.py"] --> OCV["cv2.Stitcher\nmode=SCANS 1"]
```

---

## 6. Constants Quick Reference

All tunable constants live in `backend/src/anim/constants.py`.

### Core Stitching

| Constant | Value | Description |
|----------|-------|-------------|
| `_LAPLACIAN_BANDS` | `5` | Pyramid depth for multi-band blend |
| `_ECC_MAX_ITER` | `80` | ECC termination: max iterations |
| `_ECC_EPS` | `1e-4` | ECC termination: convergence epsilon |
| `_ECC_PYRAMID_LEVELS` | `4` | Gaussian pyramid levels for ECC |
| `_MIN_LOFTR_INLIERS` | `20` | Min bg inliers after LoFTR mask filter |
| `_MAX_DX_DRIFT_RATIO` | `0.01` | Max horizontal drift (1% of width) |
| `_MATCH_EDGE_CROP` | `0.05` | Pre-match edge trim fraction (5%) |
| `_MIN_TEMPLATE_SCORE` | `0.85` | Min TM_CCORR_NORMED confidence |
| `_PC_CONF_THRESHOLD` | `0.05` | Min phase-correlation response |
| `_CANVAS_MAX_DIM` | `32768` | Hard OOM cap on canvas |
| `_MEDIAN_MIN_SAMPLES` | `3` | Min valid samples for median render |
| `_FOREGROUND_DILATION` | `16` | BiRefNet mask dilation (px) |
| `_FOREGROUND_EROSION` | `8` | BiRefNet mask erosion (px) |
| `_SMOOTHSTEP_BLEND_PX` | `96` | Fallback blend height |

### Compositing (`compositing.py`)

| Constant | Value | Description |
|----------|-------|-------------|
| `_FEATHER_MAX` | `300` | Max feather half-width |
| `_FEATHER_MIN` | `80` | Min feather half-width |
| `_GAIN_CLAMP` | `(0.88, 1.14)` | Per-boundary photometric gain limit |
| `_SEQ_SAMPLE_HALF` | `40` | Rows each side for gain estimation |
| `_SEQ_MIN_PX` | `200` | Min pixels for reliable gain est. |
| `_SEARCH_RANGE` | `250` | Boundary search radius (px) |
| `_SEARCH_SLAB` | `20` | Row height for boundary scoring |
| `_SEAM_RAMP_HALF` | `250` | Post-composite ramp half-width |
| `_SEAM_MEAS_SLAB` | `40` | Rows for seam colour measurement |
| `_SEAM_STEP_THRESHOLD` | `1.5` | Min colour step to trigger ramp |
| `_SEAM_MAX_RATIO` | `1.35` | Max ratio before treating as content |

### MFSR Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `PSO_SWARM_SIZE` | `40` | PSO: swarm particle count |
| `PSO_MAX_ITER` | `150` | PSO: max iterations |
| `PSO_INERTIA` | `0.729` | PSO: inertia weight |
| `PSO_C1` / `PSO_C2` | `1.494` | PSO: cognitive/social coefficients |
| `PSO_VEL_CLAMP` | `0.2` | PSO: velocity clamp fraction |
| `DE_POP_SIZE` | `30` | DE: population size |
| `DE_MAX_GEN` | `100` | DE: max generations |
| `DE_F` | `0.8` | DE: mutation scale factor |
| `DE_CR` | `0.9` | DE: crossover rate |
| `DCT_BLOCK_SIZE` | `8` | DCT: block size (JPEG-standard) |
| `DCT_ITERATIONS` | `20` | DCT: default restoration iterations |
| `DRL_STATE_SIZE` | `256` | DRL: state feature dimension |
| `DRL_ACTION_DIM` | `4` | DRL: action space (dx,dy,dscale,dtheta) |
| `DRL_GAMMA` | `0.99` | DRL: discount factor |
| `DRL_LR` | `1e-4` | DRL: learning rate |
| `DRL_MEMORY_SIZE` | `10000` | DRL: replay buffer size |
| `DRL_BATCH_SIZE` | `64` | DRL: training batch size |
