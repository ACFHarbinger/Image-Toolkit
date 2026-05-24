# Anime Stitch Pipeline — Issue Summary & Improvement Roadmap

**Last updated:** 2026-05-24 (test4–test22 analysis added; paths migrated to data/asp_testX)  
**Relevant codebase:** `backend/src/anim/`  
**Test suite:** `backend/test/anim/` — 105 tests covering all issue categories (run with `pytest backend/test/anim/`)  
**Architecture reference:** `docs/ARCHITECTURE.md`  
**Research references:** `reports/` directory  
**Overmix reference implementation:** `Overmix/src/`  
**Pipeline scripts:** `archive/run_pipeline_v2.py`, `archive/build_stages.py`  
**Test datasets:** `data/asp_testX/` (formerly `/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/testX/`)

---

## 1. Task Overview

The goal is to make `AnimeStitchPipeline` (`backend/src/anim/pipeline.py`) produce stitched panoramas that match or exceed the quality of the simple `_merge_images_scan_stitch` method (`backend/src/core/image_merger.py`). The simple stitch uses OpenCV's built-in SCANS stitcher — it produces clean seam-free results but with ghosting/blur where frames overlap, and lower overall image quality due to no content-aware compositing.

The pipeline runs 13 stages (see `docs/ARCHITECTURE.md` for full flowchart). The primary failure modes identified across three test datasets are:

1. **Seam/brightness bands in Stage 11 composite** (`test1/` dataset — partially fixed)
2. **Ghosting and photometric collapse in Stage 9 temporal render** (`test3/` dataset)
3. **Complete alignment failure in Stages 5–8** (`test2/` dataset — broken affines)

---

## 2. Dataset Reference

| Dataset | Frames | Panorama size | Simple stitch size | Alignment ratio | Status |
|---------|--------|--------------|-------------------|-----------------|--------|
| `test1/` | 8  | 3604×3803 | — | 1.1× | Partially fixed — subtle brightness gradient |
| `test2/` | 10 | 3844×4077 | — | broken | Alignment catastrophically wrong |
| `test3/` | 11 | 3812×4914 | — | unknown | Broken Stage 9; composite has hard seam |
| `test4/` | 7  | 3818×3141 | 3841×3534 | **1.0×** | Good alignment; overcropped −393px height |
| `test5/` | 6  | 3781×3299 | 3864×4985 | 1.3× | Alignment degraded; ghosting; −1686px height |
| `test6/` | 9  | 3818×3423 | 3879×3147 | **1.4×** | **Best new dataset** — clean output |
| `test7/` | 14 | 4603×3138 | 5530×4386 | 4.7× | Alignment broken; diagonal scroll unsupported |
| `test8/` | 11 | 3620×4042 | 3874×3844 | 5.9× | Alignment catastrophically broken; worst output |
| `test9/` | 9  | 3783×2777 | 3859×4386 | 11.8× | Frame clustering; −1609px missing content |
| `test10/` | 14 | 3803×4582 | 7465×6872 | 3.2× | Large uneven gaps; Stage 9 ghosting; ss uses full perspective model |
| `test11/` | 7  | 3781×3795 | 3841×3636 | **1.1×** | **Clean output — positive baseline** |
| `test12/` | 6  | 3670×3700 | 3841×3965 | 2.9× | Borderline ratio; visually clean despite gaps |
| `test13/` | 9  | 3825×3023 | 3850×3238 | 2.3× | Uneven gaps; mild Stage 11 seam in lower half |
| `test14/` | 7  | 3828×3397 | 3859×2709 | **1.1×** | **Clean output; pipeline taller than ss (+688px)** |
| `test15/` | 7  | 3802×4196 | 3957×4896 | **1.1×** | **Clean output; ss has staircase borders** |
| `test16/` | 10 | 3788×3119 | 3874×3425 | 6.1× | Frame clustering (12px gaps) → catastrophic Stage 9 ghosting |
| `test17/` | 7  | 3833×2693 | 3924×3076 | 1.5× | Mild seam band at one boundary; slight diagonal drift |
| `test18/` | 6  | 3783×3709 | 3840×2181 | **1.1×** | Anomalous: good ty/tx but catastrophic Stage 9 — affine rotation issue |
| `test19/` | 10 | 3790×4197 | 3845×4369 | **1.1×** | **Clean output — positive baseline** |
| `test20/` | 7  | 5637×2101 | 6057×2168 | 1.8× | **Pure horizontal scroll** (tx=0–1857, ty≈0) — unsupported scroll axis |
| `test21/` | 10 | 3946×3339 | 4137×3758 | **1.0×** | 3 co-located frames (ty=0, tx=165) → top-strip ghosting |
| `test22/` | 11 | 3788×2930 | 3841×3062 | **1.0×** | **Clean output — positive baseline** |

Stage outputs are in `<dataset>/output/panorama_stages/`. Alignment ratio = max_gap / median_gap from `stage08_canvas_info.json`. Ratios > 3× indicate a broken bundle adjustment. Bold ratio = dataset produces acceptable output. Check `min_gap` as well — a ratio of 1.0× with `min_gap=0` still indicates co-located frames.

All dataset paths are `data/asp_testX/` relative to the repo root (e.g. `data/asp_test1/`, `data/asp_test8/`). Pipeline runner scripts are in `archive/` (`archive/run_pipeline_v2.py`, `archive/build_stages.py`).

---

## 3. Issue Category 1 — Seam / Brightness Bands at Stage 11 (Composite)

### 3.1 What the issue looks like

**Pipeline output (`test1/` — Image #1):** Visible horizontal brightness bands crossing the entire image. The most prominent band runs across the mid-upper area (~30–35% from top). The background (curtain) shows as a bright horizontal stripe that breaks the natural scene.

**Simple stitch (`test1/` — Image #2):** No horizontal bands. Natural scene brightness gradient top-to-bottom. Some blurriness and ghosting where the alpha-blended overlap zones average slightly different character positions, but no seam lines.

**Stage 11 composite before fixes (`test1/` — Image #3):** The bands are clearly introduced by Stage 11 — Stage 9 (temporal render) produces a clean multi-frame median, and Stage 11 compositing introduces the brightness discontinuities.

### 3.2 Root causes diagnosed and fixed

The following bugs were found and fixed in `backend/src/anim/compositing.py` during this session:

#### Bug 1 — `SEAM_THIN_HF=8` architecture mismatch
The feather zone was 300–500px wide (set by `_FEATHER_MAX`), but the blend alpha was computed with a fixed ±8px half-width (`SEAM_THIN_HF`). This created a 16px-wide cosine blend inside a 500px zone: the seam path wandered 300px per column, so the blend centerline zigzagged visibly as an irregular brightness discontinuity.

**Fix:** Replaced `SEAM_THIN_HF` with `zone_half_f = (y1_f - y0_f - 1) // 2` so the blend spans the full feather zone width.

#### Bug 2 — Per-column seam path used as blend alpha centerline
Even after the zone_half_f fix, using `d_seam = local_ys - seam_path[newaxis,:]` (per-column path) for `t_lin` caused the blend ramp to shift vertically per column by up to 313px. This created an irregular horizontal brightness boundary visible as a soft but clearly non-horizontal band.

**Fix:** Changed blend alpha to use flat horizontal distance: `d_flat = local_ys - float(y_cut)`. The DP seam path is still used for the gain correction taper (`t_blend`) which is content-aware, but the brightness ramp is purely horizontal.

#### Bug 3 — Per-zone `gain_seam` overcorrecting from scene content
The code measured background-pixel brightness ratios in a 50-row slab around `y_cut` in both frames, then used that ratio as a photometric correction gain (14–17% corrections). However, at the same canvas row, the two frames show different scene elements (different body parts from sequential animation frames). The "same rows" comparison captures scene content differences, not calibration offsets. After LS normalization the measured ratios were still 14–17% — treating the natural scene brightness gradient as calibration error.

**Fix:** Disabled per-zone `gain_seam` correction entirely (`gain_seam = np.ones(3)`). LS normalization with a tight clamp handles genuine small offsets; the wide feather blend handles the rest.

#### Bug 4 — LS normalization amplifying the scene gradient
The unclamped LS gains ranged from F7=0.818 to F0=1.253 (53% spread) across 8 frames from the same scene. The LS was treating the natural top-to-bottom scene lighting gradient as per-frame calibration error and amplifying it. With `_GAIN_CLAMP=(0.70, 1.45)`, corrections of up to 45% were applied to individual frames, creating large brightness steps at every boundary.

**Fix:** Tightened LS clamp from `(0.70, 1.45)` to `(0.95, 1.05)`. Only genuine ±5% calibration offsets are corrected.

#### Bug 5 — Post-composite seam ramp applied inside the feather zone
`_apply_canvas_seam_correction` applied a ±`ramp_half`-row ramp correction on top of the existing feather blend. With `ramp_half = min(250, half_above, half_below)` and B0/B1 only 169px apart, `ramp_half=84px`. The 84px ramp was applied inside the 500px feather zone, adding a narrow 12% brightness gradient on top of an already-smooth blend — creating a new visible band rather than fixing one.

**Fix:** Disabled `_apply_canvas_seam_correction` call at end of `_composite_foreground`.

#### Bug 6 — Boundary-spacing cap forcing non-overlapping feather zones
A cap was added to prevent feather zones from overlapping: `max_feather = min(gap_above, gap_below) // 2`. With B0 at y=988 and B1 at y=1157 (169px apart), both feathers were capped at 84px. This created two sequential 168px transitions (F7→F6, then F6→F5) instead of one smooth 3-frame blend, with F6 having only a ~1px "pure" ownership strip between them.

**Fix:** Removed boundary-spacing cap. Feather zones are now allowed to overlap; the num/denom accumulation in the composite loop averages them into a smooth multi-frame blend.

#### Bug 7 — Boundary search degenerate with `2*_FEATHER_MAX` guard
The search window guard was `int(optimised[k-1]) + 2 * _FEATHER_MAX + 1`. With `_FEATHER_MAX=300` and boundaries ~238px apart, `lo_limit > hi_limit` for all interior boundaries — the search was effectively disabled (all Δ=+0).

**Fix:** Changed guard to `2 * _SEARCH_SLAB` (40px), allowing meaningful search range.

#### Bug 8 — Seam ramp oscillations at tightly-packed boundaries
At B5/B6 (y=2270/2351, 81px apart), the 40px measurement slabs for each correction ramp extended into the adjacent boundary's feather zone, giving contaminated measurements. This produced alternating 12% darkening/brightening corrections creating visible oscillating bands.

**Fix:** Added `if ramp_half < 80: continue` guard in `_apply_canvas_seam_correction`.

#### Bug 9 — LS measuring at initial midpoints (character bodies)
LS was run with `initial_boundaries` (geometric midpoints between frame strip centers), which land inside character body areas where there are zero background pixels. All LS measurements returned `bg_diff=inf` or fell back to all-pixel estimates dominated by character content.

**Fix:** Two-pass boundary search: run `_find_optimal_boundaries` first (pass 1) to get positions where background IS visible, then run LS using those positions, then re-run boundary search (pass 2) on the normalized frames.

#### Bug 10 — Background pixel mask inverted in `_apply_canvas_seam_correction`
The measurement code used `~bm_top` (foreground pixels) instead of `bm_top` (background pixels). Background is photometrically stable across frames; character skin can legitimately differ between sequential frames.

**Fix:** Changed to `bm_top & top_all_valid` and `bm_bot & bot_all_valid`.

### 3.3 Remaining issue after fixes

After all fixes, the `test1/` pipeline output still has a subtle brightness gradient in the upper-middle area (around B0/B1 at y=988/1157). This is the **natural scene lighting** — the background curtain is genuinely darker in the upper panels (F7/F6) and lighter in the lower panels (F5/F4). The simple stitch shows the same gradient but it reads as natural because the alpha-gradient blend distributes it smoothly across all overlapping frames simultaneously.

The pipeline's hard-partition approach assigns rows to single frames, with feather zones only at boundaries. Even with overlapping feather zones, the "natural scene gradient" visible as darkening in F7/F6 territory cannot be fully hidden without either (a) accepting some brightness normalization or (b) using a much wider alpha-gradient blend like the simple stitch. This is a fundamental trade-off between sharpness (pipeline) and photometric smoothness (simple stitch).

### 3.4 Simple stitch as inspiration

The simple stitch's key advantage is **simultaneous multi-frame alpha blending over the full overlap zone** (~1895px for this dataset). Every row in the overlap region gets contributions from all frames covering it, weighted by their alpha gradients. This naturally smooths any scene brightness step. The simple stitch's drawbacks are:
- **Ghosting**: Different character positions from sequential frames average together, creating semi-transparent doubled edges
- **Blur**: The alpha averaging softens fine details
- **No content-aware boundary placement**: The seam always runs at the geometric midpoint

The pipeline's advantage is content-aware boundary placement via DP seam cuts, temporal median rendering to deghost characters, and hard-partition compositing for sharp results. The seam issues come from the compositing logic attempting too many photometric corrections that interfere with each other.

**Recommended hybrid approach (inspiration from simple stitch):**
1. Use the pipeline's DP seam path to select *which frame* owns each canvas pixel (hard partition)
2. Apply a wide alpha-gradient blend in the overlap zones (like simple stitch) rather than a feather zone with hard strip ownership outside it
3. Limit gain corrections to LS-only with tight ±5% clamp — no per-zone corrections

---

## 4. Issue Category 2 — Stage 9 Temporal Render Failure (`test3/` dataset)

### 4.1 What the issue looks like

**Stage 9 temporal render (`test3/`):** The output (`stage09_temporal_render.png`) shows the 11-frame composite partially collapsed. The upper portion is partially transparent/dark (letterbox effect visible), and the entire image has strong ghosting — multiple overlapping character positions with different transparencies. The background region on the right appears as a gray rectangle where frames are missing.

**Stage 11 composite (`test3/`):** The compositor partially recovers by applying the hard-partition ownership logic, but a visible hard seam runs horizontally across the middle of the image (~55% from top). The seam is a clear brightness discontinuity with visible content misalignment on either side.

**Final output (`test3/`):** Matches stage 11 — large visible horizontal seam in the middle.

**Simple stitch (`test3/` — Image #4):** Clean result showing 11 frames properly composited. Natural scene progression from top to bottom.

### 4.2 Canvas geometry

The `test3/` dataset has 11 frames with affines (`ty` values) evenly spaced ~280–290px apart — a well-ordered vertical strip panorama. However the stage 9 render shows heavy ghosting. The 11-frame median render should ghost-remove character motion, but the heavy visible ghosting suggests the affines themselves may have errors causing partial frame misalignment during warp.

### 4.3 Likely root causes

1. **Frame ordering in temporal render**: The render may not be correctly identifying the strip center for each frame to assign ownership zones, causing frames to overlap incorrectly in the median accumulation.

2. **`_render_median` gain clamp at ±12% per-pixel**: The rendering stage applies per-pixel gain correction (`np.clip(..., 0.88, 1.12)`) during median accumulation. With 11 frames having a scene brightness gradient, this may be over-darkening certain strips.

3. **Hard seam from misaligned frame boundary**: The boundary between frame6 (ty=1721.7) and frame7 (ty=2020.8) has a gap of ~299px between strip centers. The boundary search should place the composite boundary at ~y=1871. If the boundary lands on a content-rich area (character body crossing the boundary), the hard-partition transition creates a visible seam.

4. **BiRefNet mask quality**: If the foreground masks for `test3/` frames have errors (false foreground/background classification), the boundary search and LS normalization will use contaminated measurements.

### 4.4 Diagnostic steps for new agent

1. Examine `stage04_bgmask_frame*.png` files in `data/asp_test3/output/panorama_stages/` to verify mask quality
2. Check whether stage 9 ghosting occurs in the temporal render or was already present in normalized frames (`stage03_basic_corrected_frame*.png` or `stage02_normalised_frame*.png`)
3. Run `run_pipeline_v2.py`-style script with the `test3/` stage data to isolate Stage 11 from Stage 9

---

## 5. Issue Category 3 — Alignment Failure (`test2/` dataset)

### 5.1 What the issue looks like

**Stage 9 temporal render (`test2/`):** Catastrophically wrong. The top portion shows an upside-down/rotated partial frame with heavy ghosting. The lower portion shows the main character scene but with extreme brightness banding and the wrong frame arrangement. The image looks like frames were concatenated in random order rather than as a vertical scroll.

**Stage 11 composite (`test2/`):** A hard horizontal seam bisects the image at ~40% from top. The upper half shows a completely different scene orientation than the lower half, including what appears to be an upside-down version of part of the sequence.

**Final output (`test2/`):** Identical to stage 11 — completely garbled composite.

**Simple stitch (`test2/` — Image #6):** Shows a clean vertical panorama of what appears to be a different angle/position of the scene, demonstrating what the correct alignment should look like.

### 5.2 Root cause: Bundle adjustment failure

The `stage08_canvas_info.json` for `test2/` reveals the core problem:

```
rank0: frame2  ty=0.0
rank1: frame3  ty=56.2      ← only 56px below frame2 (catastrophically close)
rank2: frame5  ty=548.9
rank3: frame9  ty=723.8
rank4: frame7  ty=726.7     ← frame9 and frame7 are 3px apart
rank5: frame8  ty=727.0     ← frame8 is 0.3px from frame7
rank6: frame6  ty=781.8
rank7: frame4  ty=859.2
rank8: frame1  ty=1913.0    ← 1053px gap from frame4
rank9: frame0  ty=1919.2    ← frame1 and frame0 are 6px apart
```

The bundle adjustment (`_bundle_adjust_affine` in `backend/src/anim/bundle_adjust.py`) produced completely wrong frame ordering:
- Frames 7, 8, 9 are placed at nearly identical positions (3px / 0.3px apart) — they should be separate strips
- Frames 0, 1 are placed together at the far bottom (1913/1919px) with a 1053px gap above them
- Frame 2 and 3 are only 56px apart (should be ~300–400px for this image size)

This means the pairwise matching stage (Stage 5–6) produced incorrect matches — either wrong-direction matches (matching a frame against one that should be several positions away) or sign flips in the translation estimates.

### 5.3 Likely root causes

1. **Feature matching failure with `test2/` content**: The `test2/` frames appear to contain a scene with a dark background and significant inter-frame motion. LoFTR and template matching can produce incorrect direction estimates when:
   - Low-texture backgrounds (dark blue wall) dominate the match
   - Character positions change substantially between frames
   - Frames from different parts of the scroll are accidentally matched to each other

2. **`_filter_edges` not catching the wrong-direction matches**: The velocity consistency filter in `AnimeStitchPipeline._filter_edges` should reject matches whose translation direction is inconsistent with the majority. But if the majority of edges are wrong (e.g., if many frames match to the wrong neighbor), the filter will preserve the bad matches.

3. **Bundle adjustment (`_bundle_adjust_affine`) not robustly handling large outliers**: If several edges have wildly wrong translations, least-squares bundle adjustment will be pulled off by them. There is no RANSAC or robust estimation in the current bundle adjust.

4. **Frame ordering assumption**: The pipeline assumes frames are provided in a consistent order (top-to-bottom scroll). If the `test2/` source frames are not in that order, the initial `_pairwise_match` logic may connect them incorrectly.

### 5.4 Overmix reference for alignment

The `Overmix/src/aligners/` directory contains several relevant aligners:
- `RecursiveAligner.cpp` / `RecursiveAligner.hpp`: Hierarchical alignment that may be more robust to large initial misalignment
- `AverageAligner.cpp`: Uses average frame for alignment reference
- `MultiScaleComparator.cpp` / `MultiScaleComparator.hpp` in `comparators/`: Multi-scale comparison that is more robust to local content differences
- `BruteForceComparator.cpp`: Exhaustive search comparator for small search windows

Key insight from Overmix: `RecursiveAligner` builds a tree of frame pairs rather than a linear chain, which is more robust when adjacent-frame matches are ambiguous.

---

## 6. Issue Category 4 — Image Quality Degradation Beyond Seams

Beyond the seam/alignment issues, comparing simple stitch and pipeline outputs reveals quality differences:

### 6.1 Over-sharpening / contrast amplification

The pipeline's BaSiC correction (Stage 3) and per-pixel gain in `_render_median` (Stage 9) can amplify noise and create a slightly "plastic" or over-processed look compared to the simple stitch.

### 6.2 Color shift

The LS normalization (even with tight ±5% clamp) modifies per-frame color. With the `test3/` dataset having a cooler/bluer color palette, small gain corrections can push channels in inconsistent directions.

### 6.3 Hard edges at frame boundaries outside feather zones

With the hard-partition approach, rows outside all feather zones are assigned 100% to one frame. If that frame has any local brightness variation (vignetting, bloom effects), there is no blending to hide it. The simple stitch blends across the full overlap zone, naturally hiding per-frame local variations.

### 6.4 Checkerboard / block artifacts from MFSR (when enabled)

When `use_mfsr=True` is set, the DCT-based MFSR stage (Stage 10) introduces 8×8 block grid artifacts visible as a regular grid pattern across the entire image. This is especially visible in flat-color regions (anime cel shading). The `run_pipeline_v2.py` test script explicitly skips MFSR for this reason.

---

---

## 7. Test4–Test9 Dataset Analysis (new findings)

This section documents the per-dataset findings from comparing `panorama.png` vs `simple_stitch.png` for test4 through test9.

---

### 7.1 test4 (7 frames) — Good alignment, overcrop

**Affines:** Near-perfect. ty gaps ≈ [1, 250, 275, 272, 273, 269]px, median 271px, max/median **1.0×**. One degenerate pair: frame 4 (ty=0) and frame 6 (ty=1) are 1px apart.

**panorama.png (3818×3141):** Visually clean — correct scene order, no visible horizontal bands, no ghosting. Looks correct.

**simple_stitch.png (3841×3534):** Also clean and natural. 393px taller than the pipeline output.

**Diagnosis:** The 1px degenerate pair (frames 4/6) does not cause visible artifacts because ownership is assigned to the same strip. The primary problem is `_crop_to_valid` removing ~393px from the bottom. The canvas is computed correctly (3818×3201 according to stage08) but the final crop is too aggressive.

**Category: E (canvas overcrop)**

---

### 7.2 test5 (6 frames) — Alignment degraded, catastrophic Stage 9 ghosting

**Affines:** Degraded. ty gaps = [262, 334, 119, 152, 334]px, median 262px, max/median **1.3×**. Frames at ty=596, 715, 867 are only 119–152px apart instead of the expected ~262px — those pairs have compressed spacing from wrong LoFTR dy estimates.

**stage09_temporal_render.png:** Catastrophic — ALL 6 frames are transparently overlaid at wrong positions. The entire image is a washed-out translucent mess. Multiple ghost images of the same characters overlapping at different offsets. Background regions have coloured smear artifacts from channel averaging.

**panorama.png (3781×3299):** Hard horizontal seam band in the middle (at the mis-spaced boundary). Wrong-frame content visible on either side of the seam. Ghosting throughout from bad Stage 9.

**simple_stitch.png (3864×4985):** Clean, correct vertical composite. 1686px taller than pipeline output — significant content is missing from the panorama (the compressed frame spacing collapses the canvas extent).

**Root cause:** Wrong LoFTR dy estimates for certain frame pairs → bundle adjustment produces compressed/incorrect ty values → Stage 9 temporal render overlaps all frames simultaneously → catastrophic ghosting before Stage 11 even runs.

**Category: C (alignment failure) → cascades to B (Stage 9 ghosting) + E (height compression)**

---

### 7.3 test6 (9 frames) — Best new dataset, mostly clean output

**Affines:** Good. ty gaps = [174, 177, 178, 163, 238, 133, 137, 126]px, median 168px, max/median **1.4×**. Slightly elevated gap at boundary 4 (238 vs median 168) but still well within 3× threshold.

**panorama.png (3818×3423):** Relatively clean. Scene order correct, no hard seams, alignment looks right. Slight ghosting visible in feather zones (expected for overlapping content). Background blending is smooth.

**simple_stitch.png (3879×3147):** Clean and natural, slightly warmer white balance than pipeline. 276px shorter than pipeline — the pipeline captures more scene extent here (correct behaviour).

**Diagnosis:** This is the cleanest of all new test datasets. Demonstrates that when alignment succeeds the pipeline produces good results. Minor remaining issue: subtle ghosting at transition zones (feather blending not fully sharp compared to hard-partition ownership outside zones).

**Category: Mostly working** — provides the positive evidence baseline that fixing alignment is sufficient.

---

### 7.4 test7 (14 frames) — Alignment broken, diagonal scroll unsupported

**Affines:** BROKEN. ty values by frame index: [0, 49, 99, 130, 165, 335, 538, 465, 265, 816, 771, 821, 991, 1040] — **non-monotonic** (frames 6→7→8 go 538→465→265, decreasing). Gaps = [49, 49, 31, 36, 99, 70, 130, 73, 233, 44, 5, 170, 49]px, median 49px, max/median **4.7×**.

**panorama.png (4603×3138):** Severely garbled. Large diagonal shear-like bands where misplaced frames overlap. Ghost layers of wrong content at multiple positions. The upper-left quadrant shows a different scene state than the lower-right, with heavy semi-transparent overlap where they meet.

**simple_stitch.png (5530×4386):** Clean correct result — but notice it is **WIDER** than the pipeline output (5530 vs 4603px) and has characteristic staircase-step black borders at all four edges. This indicates a **diagonal scroll**: the camera was panning both down (ty) and slightly right (tx) simultaneously. The pipeline uses only ty for vertical strip composition and discards tx; the simple stitch uses OpenCV's full affine stitcher which handles both.

**Root cause 1 — Broken bundle adjustment:** With 14 frames, the probability of at least one bad LoFTR match polluting the bundle adjust is high. The current implementation has no outlier rejection.

**Root cause 2 — Diagonal scroll not handled:** The pipeline's canvas model (`_compute_canvas` in `canvas.py`) places frame strips at `ty` offsets only, discarding the horizontal component `tx`. For datasets with significant horizontal camera drift, this collapses all frames onto the same x-column, creating impossible alignment conditions for the downstream compositing stages.

**Category: C (alignment failure, non-monotonic order) + new failure mode F (diagonal/non-vertical scroll)**

---

### 7.5 test8 (11 frames) — Catastrophic frame clustering, worst output

**Affines:** SEVERELY BROKEN. ty values by frame index: [1085, 243, 762, 259, 1166, 1785, 0, 333, 726, 1263, 1806]. Multiple near-duplicate clusters:
- Frame 1 (ty=243) and Frame 3 (ty=259): **16px apart**
- Frame 2 (ty=762) and Frame 8 (ty=726): **36px apart**
- Frame 4 (ty=1166) and Frame 9 (ty=1263): 97px apart
- Frame 5 (ty=1785) and Frame 10 (ty=1806): **21px apart**

Gaps = [243, 16, 74, 393, 35, 323, 81, 97, 522, 20]px, median 89px, max/median **5.9×**. The large 522px gap (between ty=1263 and ty=1785) indicates a completely missing segment.

**stage09_temporal_render.png:** Complete catastrophe — the scene body parts appear 3–5 times at different semi-transparent positions. The render is a washed-out, wholly unrecognisable accumulation of all 11 frames overlaid at wrong positions.

**panorama.png (3620×4042):** The worst output of all datasets. Every anatomical feature appears repeated 3–5 times at different semi-transparent offsets across the entire canvas height. Hard horizontal seam bands mark the frame-cluster boundaries. Essentially unusable.

**simple_stitch.png (3874×3844):** Clean and correct.

**Root cause:** LoFTR produced near-zero dy matches for several frame pairs (same-scene or very similar consecutive frames matched with nearly zero translation). These 16–21px matches propagate through bundle adjustment, placing multiple frames at essentially the same canvas position. The resulting render has all those frames overlaid simultaneously at every canvas row — catastrophic ghosting.

**Category: C (alignment failure — catastrophic frame clustering) → B (Stage 9 ghosting)**

---

### 7.6 test9 (9 frames) — Frame clustering, large content gap, height loss

**Affines:** BROKEN. ty values by frame index: [680, 654, 628, 624, 471, 459, 451, 145, 0]. Monotonically decreasing (correct order) but extremely uneven spacing. Six frames clustered in ty range 451–680 (229px total span) with internal gaps of only 5–26px. One large gap of 305px between ty=145 (frame 7) and ty=451 (frame 6).

Gaps (sorted) = [145, 305, 8, 12, 153, 5, 26, 26]px, median 26px, max/median **11.8×** — worst alignment ratio of all datasets.

**panorama.png (3783×2777):** Hard horizontal ghost/seam band visible in the middle. Overall image is substantially shorter than expected.

**simple_stitch.png (3859×4386):** Much taller (4386 vs 2777) — **1609px of content is missing** from the pipeline output. Correct scene progression visible.

**Root cause:** The 6 clustered frames (451–680px range, 5–26px internal gaps) all collapse onto essentially the same canvas rows. The 305px gap between ty=145 and ty=451 means there is a large chunk of canvas (around y=145–451) that belongs to no frame, or only one frame with wrong position. `_crop_to_valid` removes both the sparse top region and any black rows, resulting in a panorama that is 1609px shorter than the ground truth.

The clustering pattern is the same failure mode as test8 — LoFTR finding near-zero translations for pairs that should have large offsets. Unlike test8, the frame sequence order is correct, but the magnitude of offsets is catastrophically wrong.

**Category: C (alignment failure — frame clustering with wrong magnitudes) + E (canvas height compression)**

---

### 7.7 Cross-Dataset Pattern Summary

| Pattern | Datasets | Root cause |
|---------|----------|------------|
| Good alignment (ratio < 2×) | test1, test4, test6 | LoFTR produced correct matches |
| Frame clustering (multiple frames < 30px apart) | test2, test8, test9 | LoFTR near-zero match for same-scene pairs |
| Non-monotonic frame ordering | test2, test7 | LoFTR wrong-direction match for some pairs |
| Height loss (panorama << simple_stitch) | test4, test5, test9 | Canvas compression from clustering or `_crop_to_valid` over-aggressiveness |
| Diagonal scroll (tx drift) | test7 | Pipeline discards tx component of affine |
| Stage 9 ghosting | test3, test5, test8 | Always downstream of bad affines |

**Key insight (updated after test10–22):** The claim "Stage 9 ghosting is always caused by bad affines" has one confirmed exception: test18 shows good ty/tx values (ratio=1.1×, min_gap=327) but catastrophic Stage 9 ghosting. This likely means the full affine matrix contains rotation or scale components that `_compute_canvas` ignores. The ty/tx health check is necessary but not sufficient.

---

## 7A. Test10–Test22 Dataset Analysis

---

### 7A.1 test10 (14 frames) — Uneven gaps, partial ghosting, ss uses perspective model

**Affines:** ty by frame idx: [2696, 2582, 2448, 2338, 2235, 1759, 1588, 1145, 991, 590, 423, 272, 143, 0] — monotonically decreasing (correct order). Gaps: [143, 129, 151, 167, **400**, 154, **443**, 170, **477**, 103, 109, 135, 114]px. Three large gaps of 400, 443, 477px vs median 151px → ratio=**3.2×**. tx_range=23px (negligible).

**stage09_temporal_render:** Moderate ghosting — 2–3 semi-transparent copies of the character overlaid at different vertical offsets. Not catastrophic but clearly not a clean median render. The three large gaps mean the three affected frame pairs have significant strip discontinuities.

**panorama.png (3803×4582):** Hard horizontal seam band through the torso area (~40% from top). Upper body (face, shoulders) is clean. Seam zone shows doubled/ghosted skin tones.

**simple_stitch.png (7465×6872):** Much larger than the pipeline output — WIDER and TALLER. The OpenCV stitcher used a full projective/perspective model (not just translation), producing a 7465px-wide panorama. With 14 frames and significant inter-frame camera motion, OpenCV computed lens distortion corrections and full homographies. The pipeline's translation-only model cannot match this quality level for datasets with perspective distortion.

**Diagnosis:** Two issues: (1) the three large gaps (3.2× ratio) cause ghosting at those boundaries; (2) the source frames have enough perspective distortion that OpenCV's full projective model produces significantly better alignment than translation-only. The pipeline needs either RANSAC outlier rejection to even the gaps, or homography-based matching for high-distortion datasets.

**Category: C (alignment — uneven gaps) + new sub-category: translation-only model insufficient for perspective-distorted sources**

---

### 7A.2 test11 (7 frames) — Clean output, positive baseline

**Affines:** Monotonic, ratio=**1.1×**, min_gap=59px. Good alignment.

**panorama.png (3781×3795):** Clean composite — correct scene order, no visible seams or ghosting. Very slight brightness variation in the lower portion but below objectionable threshold.

**simple_stitch.png (3841×3636):** Also clean. Pipeline output is 159px taller (captures more content). Quality comparable.

**Category: Positive baseline** — confirms the pipeline works on this dataset.

---

### 7A.3 test12 (6 frames) — Borderline ratio, visually clean

**Affines:** ratio=**2.9×**, min_gap=173px. The minimum gap of 173px is large enough that frame strips do not collapse.

**panorama.png (3670×3700):** Visually clean — no visible seams or ghosting. The scene (close-up, orange tones) is correctly composited.

**simple_stitch.png (3841×3965):** Also clean. 265px taller. Pipeline output looks slightly over-saturated compared to simple stitch.

**Diagnosis:** The 2.9× ratio is just below the 3× threshold and does not cause visible artifacts here. The minimum gap of 173px prevents frame clustering. Demonstrates that the 3× ratio threshold is approximately correct — ratios between 2× and 3× are borderline and may or may not produce visible artifacts depending on where the large gaps fall.

**Category: Borderline — monitoring only. Slight overcrop (−265px height).**

---

### 7A.4 test13 (9 frames) — Uneven gaps, mild seam

**Affines:** ty: [0, 184, 282, 363, 427, 519, 735, 840, 925]. Gaps: [184, 98, 81, 64, 92, **216**, 105, 85]px, median 92px, max 216px → ratio=**2.3×**. Frame 0→1 gap is 184px but frames 1–5 compress to 64–98px, then frame 5→6 jumps to 216px.

**panorama.png (3825×3023):** Mild seam/ghosting band at approximately 55% from top. The face and upper scene (golden background, close-up) are clean; the mid-lower area shows a faint doubled region at the 216px-gap boundary.

**simple_stitch.png (3850×3238):** Clean and natural. 215px taller.

**Diagnosis:** The 216px gap (2.3× median) creates a boundary where frame 5→6 is further apart than the others, causing the temporal median to partially ghost at that strip junction.

**Category: C (mild alignment degradation) → faint Stage 11 seam at the large-gap boundary**

---

### 7A.5 test14 (7 frames) — Clean output, pipeline captures more content

**Affines:** ratio=**1.1×**, min_gap=43px. Good alignment.

**panorama.png (3828×3397):** Clean — correct vertical composite, no visible seams or ghosting.

**simple_stitch.png (3859×2709):** Clean but 688px SHORTER than pipeline. The pipeline captures more of the scene extent (correct behaviour — the OpenCV stitcher cropped aggressively).

**Category: Positive baseline** — pipeline outperforms simple stitch on scene coverage here.

---

### 7A.6 test15 (7 frames) — Clean output, simple stitch has staircase borders

**Affines:** ratio=**1.1×**, min_gap=279px (very healthy). tx_range=22px (slight diagonal).

**panorama.png (3802×4196):** Visually excellent — outdoor scene (blue sky, character from behind), smooth composite, no visible seams.

**simple_stitch.png (3957×4896):** Shows same scene but with characteristic staircase-step black borders at all four edges from the slight horizontal drift. The pipeline output is cleaner (no black borders) despite being 700px shorter. This is a case where the pipeline's translation-based composition produces a better-looking result than OpenCV's staircase layout.

**Category: Positive baseline** — pipeline cleaner than simple stitch on this dataset.

---

### 7A.7 test16 (10 frames) — Catastrophic frame clustering

**Affines:** ty: [430, 0, 746, 843, 418, 370, 1021, 902, 807, 565]. Non-monotonic by frame index. Clusters: frames 5/0/4 at ty=370/430/418 (12–60px apart); frames 9/7/8 at ty=565/902/807 (59–97px apart). Gaps: [370, 48, **12**, 135, 181, 61, 36, 59, 119]px, min=**12px**, ratio=**6.1×**.

**stage09_temporal_render:** Catastrophic — all 10 frames transparently overlaid at wrong positions. The scene (legs/thighs close-up in a sandy environment) is completely unrecognisable. Pure washed-out smear.

**panorama.png (3788×3119):** Heavy ghosting throughout — every feature appears 3+ times at different semi-transparent offsets across the full canvas height. Essentially unusable.

**simple_stitch.png (3874×3425):** Clean and correct.

**Category: C (catastrophic frame clustering, min_gap=12px) → B (Stage 9 ghosting)**

---

### 7A.8 test17 (7 frames) — Mild seam, slight diagonal drift

**Affines:** ty: [0, 145, 221, 292, 374, 483, 596]. Monotonic. Gaps: [145, 75, 72, 82, 110, 112]px, median 82px, ratio=**1.5×**. tx values have moderate variation (0–52px). The first gap (145px) and last two gaps (110, 112px) are 1.7× the median, creating slightly uneven strip widths.

**panorama.png (3833×2693):** Visible horizontal seam band at ~65% from top (the boundary between the 145px-gap strip and the tighter 75px-gap strip). Upper portion (warm orange-lit fox-girl face/torso) is clean. The lower seam likely corresponds to the frame 0→1 boundary where the gap is nearly 2× larger than frames 1–3.

**simple_stitch.png (3924×3076):** Clean. 383px taller.

**Category: Mild C (uneven gaps, 1.5×) → Stage 11 seam at the largest-gap boundary. Not broken but visibly imperfect.**

---

### 7A.9 test18 (6 frames) — Anomalous: good ty/tx, catastrophic Stage 9

**Affines (ty/tx):** ty: [0, 425, 769, 1154, 1596, 1922]. Monotonic, gaps: [425, 344, 384, 442, 327]px. Excellent — ratio=**1.1×**, min_gap=327px. tx_range=2px (negligible).

**stage09_temporal_render:** Catastrophic ghosting despite the clean ty/tx values. Shows what appears to be an upside-down or heavily rotated perspective of the scene, with frame content warped at extreme angles. Multiple transparent layers overlaid with apparent large rotational offsets.

**panorama.png (3783×3709):** Hard horizontal seam band in middle. Upper portion (dark blue, close-up view) mostly correct. Lower half shows the ghosting from the bad Stage 9 render cascading into Stage 11.

**simple_stitch.png (3840×2181):** MUCH shorter than pipeline (2181 vs 3709px). The simple stitch only captured ~3 of the 6 frames. The pipeline's panorama captures more scene extent correctly.

**Critical diagnosis:** The ty and tx translation components look healthy, but the stage09 render is catastrophic. This breaks the assumption that "good ty/tx ⟹ good render". The most likely cause is that the full affine matrices contain significant **rotation or scale** components (aff[i][0][0], aff[i][0][1], aff[i][1][0], aff[i][1][1]) that `_compute_canvas` ignores when placing frames. If a frame is placed at the right (ty, tx) but with a 30° rotation, the warped frame will be skewed across a wide region of the canvas, causing frames to overlap even though their translation centres are correctly positioned.

**Diagnostic step:** Print the full 2×3 affine matrix for each frame:
```python
import json
with open('.../test18/output/panorama_stages/stage08_canvas_info.json') as f:
    d = json.load(f)
for i, a in enumerate(d['affines_final']):
    print(f'frame{i}: [[{a[0][0]:.3f},{a[0][1]:.3f},{a[0][2]:.1f}],[{a[1][0]:.3f},{a[1][1]:.3f},{a[1][2]:.1f}]]')
```
If any off-diagonal element (a[0][1] or a[1][0]) is > 0.05, the frame has significant rotation. If a[0][0] or a[1][1] deviate from 1.0 by > 5%, there is scale drift.

**Category: New — G (affine rotation/scale mismatch) — good translation but bad rotation in affine matrices**

---

### 7A.10 test19 (10 frames) — Clean output, positive baseline

**Affines:** ratio=**1.1×**, min_gap=110px. Good alignment.

**panorama.png (3790×4197):** Visually excellent — fox-girl on blue bedsheets, clean vertical composite, no seams or ghosting.

**simple_stitch.png (3845×4369):** Very similar quality. 172px taller.

**Category: Positive baseline.**

---

### 7A.11 test20 (7 frames) — Pure horizontal scroll (new failure mode)

**Affines:** ty by frame idx: [0, 0, 4, 2, 2, 3, 0] — essentially ALL frames at ty≈0. tx by frame idx: [1857, 1482, 1130, 942, 688, 315, 0] — tx ranges from 0 to 1857px. This is a **pure horizontal scroll** — the camera pans only horizontally.

**stage09_temporal_render:** Shows the horizontal composite with visible "horizontal" seam bands (which are actually the vertical strip boundaries being applied to side-by-side frames). The render treats this as a vertical panorama, so all strips are composited as if stacked top-to-bottom rather than left-to-right.

**panorama.png (5637×2101):** Wide landscape-format image with 2–3 horizontal light/dark bands crossing the full width. The figure (lying on bed, viewed from behind) is mostly recognisable but disrupted by the bands. The pipeline correctly generates a wider-than-tall canvas (5637×2101) because the canvas geometry is driven by tx offsets, but the compositing treats the strip boundaries as horizontal cuts — which is wrong for a horizontally-scrolling scene.

**simple_stitch.png (6057×2168):** Mostly clean horizontal panorama with natural blending. Slightly wider and the same height.

**Root cause:** The pipeline's compositing stages (Stage 9 temporal render, Stage 11 hard-partition composite) use the sorted ty values to assign canvas strip ownership. When all ty values are near-zero, the "strips" collapse to zero height and all frames are assigned to the same strip, causing the temporal render to overlap all frames simultaneously. The seam bands in the final panorama are not alignment seams — they are artefacts of the vertical-strip compositing model being applied to a scene where all frames have the same vertical position.

**Fix required:** Detect when `ty_range < 0.1 * tx_range` (primarily horizontal scroll) and switch to horizontal strip mode (sort by tx, assign canvas columns not rows). This is the horizontal analogue of the ty-based strip assignment currently implemented.

**Category: New — H (pure horizontal scroll) — unsupported scroll axis, requires horizontal strip compositing mode**

---

### 7A.12 test21 (10 frames) — Co-located frame triplet, partial ghosting

**Affines:** ty: [0, 177, 355, 532, 710, 887, 1064, 1242, 0, 0]. tx: [165, 132, 165, 132, 99, 66, 33, 0, 165, 165]. Frames 0, 8, and 9 all share ty=0, tx=165 — they are **co-located** at exactly the same canvas position. Frames 1–7 form a clean vertical sequence (steps of exactly 177px). ratio=**1.0×**, min_gap=**0** (the three co-located frames have 0px gaps).

**stage09_temporal_render:** Mostly correct in the middle region (frames 1–7 rendering cleanly), but the topmost strip (frames 0/8/9 all co-located at ty=0) shows heavy ghosting — three copies of the same scene fragment overlaid transparently at the same position. The dark border effect at canvas edges comes from the tx offsets being present in the affines.

**panorama.png (3946×3339):** The lower 7/8 of the image (frames 1–7) looks clean. The top 1/8 (frame 0/8/9 triplet strip) shows heavy ghosting and seam artefacts. Hard horizontal seam band marks the boundary between the ghosted top strip and the clean rest.

**simple_stitch.png (4137×3758):** Clean. 419px taller.

**Root cause:** Frames 0, 8, and 9 may be near-duplicate frames (same scene position, same content) that LoFTR matched to each other with zero translation. They land at exactly the same canvas position, and all three contribute to the temporal median at the same rows — causing the median of three identical/near-identical frames to be correct but the hard-partition composite to render them as three overlapping strips.

**Fix:** In `_filter_edges`, reject edges with `|dy| < min_step AND |dx| < min_step` (near-zero translation in both dimensions). Co-located duplicates must be deduplicated before bundle adjustment. Alternatively, in `_validate_affines`, check for `min_gap == 0` and flag the dataset for deduplication.

**Category: C (frame co-location — duplicate/near-duplicate frames at same canvas position)**

---

### 7A.13 test22 (11 frames) — Clean output, positive baseline

**Affines:** ratio=**1.0×**, min_gap=83px. Excellent alignment.

**panorama.png (3788×2930):** Visually clean composite — correct scene, no visible seams or ghosting. 132px shorter than simple stitch.

**simple_stitch.png (3841×3062):** Clean and comparable quality.

**Category: Positive baseline.**

---

### 7A.14 Cross-Dataset Pattern Summary (test10–22)

| Pattern | Datasets | Root cause |
|---------|----------|------------|
| **Good output (positive baselines)** | test11, test14, test15, test19, test22 | All: ratio < 2×, min_gap > 40px, no scroll-axis issues |
| Frame clustering (min_gap < 30px) | test16, test21 | LoFTR near-zero matches or duplicate source frames |
| Uneven gaps (2×–3.2× ratio) | test10, test13, test17 | Some frame pairs have large offsets; mild ghosting at those boundaries |
| Affine rotation/scale mismatch | test18 | Good ty/tx but off-diagonal affine components — `_compute_canvas` uses translation only |
| Pure horizontal scroll | test20 | ty≈0, tx dominates — pipeline's vertical strip model inapplicable |
| Perspective-distorted sources | test10 | OpenCV uses full projective model; pipeline uses translation-only |
| Borderline ratio, visually OK | test12 | 2.9× ratio but min_gap=173px prevents collapse |

**Updated key insight:** Two new confirmed failure modes beyond alignment:
1. **Category G — Affine rotation/scale**: `_compute_canvas` must check the full 2×3 affine matrix, not just (ty, tx). If off-diagonal elements or diagonal deviations from identity are large, the placed frames will overlap despite correct translation centres.
2. **Category H — Horizontal scroll**: When ty_range ≪ tx_range, the pipeline must switch to horizontal strip compositing. Current code always uses vertical strips.

**Updated positive baselines (total 7 datasets):** test4, test6, test11, test14, test15, test19, test22.

---

## 8. Comparison Table

| Issue | Affected datasets | Fixed? |
|-------|-------------------|--------|
| Seam/brightness bands (Stage 11) | t1 (subtle), t3 (hard), t5/t7/t8/t9/t13/t17/t18 (from bad aff or uneven gaps) | Partial (t1) |
| Stage 9 ghosting | t2, t3, t5, t7, t8, t9, t10, t16, t18, t21 | No |
| Alignment failure — wrong order/direction | t2, t7 | No |
| Alignment failure — frame clustering (min_gap < 30px) | t2, t8, t9, t16, t21 | No |
| Alignment failure — uneven gaps (2×–3.2×) | t5, t10, t13, t17 | No |
| Affine rotation/scale mismatch (good ty/tx, bad rotation) | t18 | No |
| Diagonal scroll (significant tx drift, partly vertical) | t7 | No (unimplemented) |
| Pure horizontal scroll (ty≈0, tx dominates) | t20 | No (unimplemented) |
| Co-located duplicate frames (same canvas position) | t21 | No |
| Canvas overcrop / height loss | t4 (−393px), t5 (−1686px), t9 (−1609px), t7 (−1248px) | No |
| Translation-only model insufficient (perspective distortion) | t10 | No (architectural) |
| MFSR block artifacts | all (when enabled) | Skip MFSR in tests |
| LS gain overcorrection | t1 | Fixed |
| Per-zone gain overcorrection | t1 | Fixed |

---

## 9. Recommended Next Steps for Fixing Agent

### Priority 1 (Highest): Fix bundle adjustment — affects test2, test5, test7, test8, test9

The dominant failure mode across all datasets is bad affines from bundle adjustment. Fixing it will cascade to fix Stage 9 ghosting in all affected datasets (ghosting is never independent — it is always downstream of bad affines).

**Step 1 — Add RANSAC-style outlier rejection in `bundle_adjust.py`:**
```python
# After initial LM solve, compute per-edge residuals
residuals = []
for e in edges:
    predicted_dy = affines[e['dst']][1,2] - affines[e['src']][1,2]
    residuals.append(abs(predicted_dy - e['dy']))
threshold = 3.0 * np.median(residuals)
clean_edges = [e for e, r in zip(edges, residuals) if r <= threshold]
if len(clean_edges) >= N - 1:
    affines = solve_bundle(clean_edges, N)
```

**Step 2 — Strengthen `_filter_edges` in `pipeline.py`:**
Reject any edge with `|dy| < min_expected_step` (e.g., 50px for a 1080p-tall frame). Near-zero dy matches are the root cause of frame clustering in test8/test9. Currently the filter only checks velocity consistency; it passes near-zero matches when all matches are bad.

**Step 3 — Add post-bundle-adjust affine validation:**
```python
def _validate_affines(affines, N, min_step=50, max_ratio=3.0):
    tys = sorted(aff[1, 2] for aff in affines)
    gaps = np.diff(tys)
    if len(gaps) == 0 or np.median(gaps) < min_step:
        return False
    return gaps.max() / np.median(gaps) <= max_ratio
```
If validation fails → fall back to `_merge_images_scan_stitch`. Do NOT let broken affines reach Stage 9.

**Step 4 — Reference `Overmix/src/aligners/RecursiveAligner.cpp`** for hierarchical frame-pair matching that builds a spanning tree rather than a linear chain, which is more robust when adjacent-frame matches are ambiguous.

Test datasets to verify on (order of severity): test8 → test9 → test2 → test7 → test5.

---

### Priority 2: Support diagonal scroll (tx drift) — test7

`test7` (14 frames) has significant horizontal camera drift: simple_stitch is 5530px wide vs pipeline's 4603px, and has staircase black borders. The pipeline's canvas model in `canvas.py` discards the tx component of each affine, placing all strips on the same x-column.

**Fix:** In `_compute_canvas`, use the full affine tx offset when placing each frame on the canvas. The compositing stage must use 2D strip regions rather than horizontal bands.

This is a significant architectural change. Until implemented, test7 will always fail regardless of alignment quality.

---

### Priority 3: Fix canvas height loss — test4, test5, test9

For datasets with panorama significantly shorter than simple_stitch:
- **test4** (−393px): Alignment is correct; `_crop_to_valid` is over-aggressive. Check the zero-row margin threshold.
- **test5** (−1686px), **test9** (−1609px): Primarily caused by bad affines compressing the canvas. Fixing Priority 1 will recover most of this.

---

### Priority 4: Fix `test3/` Stage 9 ghosting

After fixing Priority 1 (may not fully address test3 if its alignment is correct), investigate independently:
1. Check `stage04_bgmask_frame*.png` — verify masks are not inverted or empty
2. Check `stage08_canvas_info.json` affines for test3 — verify they are well-formed
3. Read `backend/src/anim/rendering.py` (`_render_median`) — examine gain clamp for 11 frames
4. Run `_render_median` with test3 stage data in isolation

---

### Priority 5: Improve `test1/` compositing (remaining subtle gradient)

The remaining subtle brightness gradient at B0/B1 (y=988/1157) is a natural scene lighting difference:
1. Treat B0+B1 as a merged 3-frame boundary when they are < `frame_height * 0.15` apart
2. Apply Laplacian pyramid blend in feather zones (see `reports/Advanced Methodologies*.md`)
3. Reference `Overmix/src/renders/AverageRender.cpp` for weighted average render

---

### Priority 3b: Validate full affine matrices, not just ty/tx — test18

The ty/tx translation health check is necessary but not sufficient. test18 has ratio=1.1× with min_gap=327px but catastrophic Stage 9 ghosting because the full affine matrices contain rotation/scale components that `_compute_canvas` ignores.

**Diagnostic:** Print the full 2×3 affine matrix for each frame and check off-diagonal elements:
```python
import json
with open('.../stage08_canvas_info.json') as f: d = json.load(f)
for i, a in enumerate(d['affines_final']):
    rot = (abs(a[0][1]) + abs(a[1][0])) / 2  # off-diagonal magnitude
    scale_dev = abs(a[0][0] - 1.0) + abs(a[1][1] - 1.0)  # deviation from identity
    if rot > 0.05 or scale_dev > 0.05:
        print(f'frame{i}: ROTATION/SCALE WARNING rot={rot:.3f} scale_dev={scale_dev:.3f}')
```

**Fix:** Extend `_validate_affines` to also reject frames with large rotation (`|a[0][1]| > 0.1` or `|a[1][0]| > 0.1`). These frames must be re-matched or excluded before Stage 9.

---

### Priority 3c: Detect and handle pure horizontal scroll — test20

When `ty_range < 0.1 * tx_range`, switch the compositing pipeline to horizontal strip mode:
- Sort frames by tx (not ty) for strip ownership
- Assign canvas columns (not rows) to each frame
- Run DP seam cut along vertical lines (not horizontal)

Until implemented, test20 will always produce spurious horizontal seam bands regardless of alignment quality.

---

### Priority 6: MFSR replacement

Replace DCT-based MFSR (8×8 block artifacts) with RealESRGAN from `backend/src/models/`, or keep disabled by default.

---

## 10. Key File Locations

| File | Purpose |
|------|---------|
| `backend/src/anim/compositing.py` | Stage 11 — hard-partition composite (primary focus of fixes) |
| `backend/src/anim/rendering.py` | Stage 9 — temporal median render |
| `backend/src/anim/bundle_adjust.py` | Stage 7 — global bundle adjustment (broken for many datasets) |
| `backend/src/anim/matching.py` | Stages 5–6 — pairwise feature matching |
| `backend/src/anim/pipeline.py` | Full pipeline orchestration + `_filter_edges` |
| `backend/src/anim/canvas.py` | Canvas geometry, `_compute_canvas`, `_crop_to_valid` |
| `backend/src/anim/masking.py` | BiRefNet foreground mask computation |
| `backend/src/core/image_merger.py` | Simple stitch (`_merge_images_scan_stitch`) for reference |
| `docs/ARCHITECTURE.md` | Full pipeline stage diagram with all parameters |
| `reports/Anime Image Stitching Pipeline Analysis.md` | Detailed analysis of the pipeline's design choices |
| `reports/Advanced Methodologies for Flawless Image Stitching in Digital Animation*.md` | Multi-scale blending, Laplacian pyramid, exposure correction methods |
| `Overmix/src/aligners/RecursiveAligner.cpp` | Hierarchical alignment reference |
| `Overmix/src/renders/AverageRender.cpp` | Weighted average rendering reference |

### Test datasets

| Dataset | Frames | Alignment | Primary issue |
|---------|--------|-----------|---------------|
| `test1/` | 8  | good (1.1×) | Subtle brightness gradient at B0/B1 |
| `test2/` | 10 | broken      | Wrong frame ordering (wrong-direction matches) |
| `test3/` | 11 | unknown     | Stage 9 ghosting + hard seam |
| `test4/` | 7  | good (1.0×) | `_crop_to_valid` overcropping −393px |
| `test5/` | 6  | degraded (1.3×) | Frame spacing compressed → Stage 9 ghosting |
| `test6/` | 9  | good (1.4×) | **Clean output** — positive baseline |
| `test7/` | 14 | broken (4.7×) | Non-monotonic order + diagonal scroll (tx drift) |
| `test8/` | 11 | broken (5.9×) | Catastrophic frame clustering (16–21px gaps) |
| `test9/` | 9  | broken (11.8×) | Severe frame clustering → −1609px height loss |
| `test10/` | 14 | degraded (3.2×) | Uneven gaps + ghosting + ss uses perspective model |
| `test11/` | 7  | **good (1.1×)** | Clean output — positive baseline |
| `test12/` | 6  | borderline (2.9×) | Visually clean; slight overcrop |
| `test13/` | 9  | degraded (2.3×) | Uneven gaps; mild seam at large-gap boundary |
| `test14/` | 7  | **good (1.1×)** | Clean; pipeline captures more content than ss |
| `test15/` | 7  | **good (1.1×)** | Clean; ss has staircase borders |
| `test16/` | 10 | broken (6.1×) | Frame clustering (min_gap=12px) → catastrophic ghosting |
| `test17/` | 7  | borderline (1.5×) | Mild seam at largest-gap boundary |
| `test18/` | 6  | anomalous (1.1×) | Good ty/tx but catastrophic Stage 9 — affine rotation issue |
| `test19/` | 10 | **good (1.1×)** | Clean output — positive baseline |
| `test20/` | 7  | broken (H scroll) | Pure horizontal scroll (ty≈0, tx=0–1857px) |
| `test21/` | 10 | partial (1.0×) | 3 co-located frames (ty=0) → top-strip ghosting |
| `test22/` | 11 | **good (1.0×)** | Clean output — positive baseline |

---

## 11. Test Script

To reproduce and iterate on compositing fixes without re-running the GPU-heavy stages:

```bash
# asp_test1/ dataset (8 frames, all stages pre-computed)
cd /home/pkhunter/Repositories/Image-Toolkit
source .venv/bin/activate
python3 archive/run_pipeline_v2.py
# Output: data/asp_test1/output/panorama_v2.png

# asp_test3/ dataset (11 frames) — edit STAGE_DIR and frame count in run_pipeline_v2.py

# For full pipeline re-run from alignment stages:
python3 archive/build_stages.py
```

Unit test suite (no GPU, ~7s):
```bash
pytest backend/test/anim/ -q
```
