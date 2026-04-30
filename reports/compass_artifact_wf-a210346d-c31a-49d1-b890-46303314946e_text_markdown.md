# Image Stitching Methods for Anime Screenshots: A Comprehensive Technical Analysis

## TL;DR

- **Anime flat-color art systematically breaks the SIFT → RANSAC → homography → distance-transform-blend pipeline** because gradient detectors find keypoints only along thin line-art curves, producing collinear/clustered correspondences that yield ill-conditioned, often catastrophically wrong homographies; the resulting wrong offsets are then fed into a soft-blend canvas that adds, rather than hides, the misalignment as ghosts (bad1) or warped doubles (bad2). The "good" sequential/ECC result works because **direct, area-based, translation-only alignment (Phase Correlation + ECC `MOTION_TRANSLATION` + template-match validation)** ignores the absence of texture and finds the global intensity peak instead.
- **The right pipeline for anime panning shots is Overmix-style:** Y-channel only, trim broadcast-safe borders, cut the sequence into shots, run integer-pixel phase correlation as a global initializer, refine with ECC `MOTION_TRANSLATION` (or `MOTION_EUCLIDEAN` if a slight rotation is suspected), gate every pair by NCC/ECC ρ-score, render with median (or hard-cut graph-cut + multi-band Laplacian) blending — never with naive distance-transform feathering when alignment confidence is low. SIFT/ORB should be a *fallback* only, and modern detector-free matchers (LoFTR, DKM/RoMa, SuperPoint+LightGlue) should be used only when the scene is genuinely 2D-affine-violating (parallax/zoom).
- **Deep learning helps surgically, not as a replacement.** LoFTR/DKM/RoMa solve the keypoint-starvation problem of SIFT on flat-color art and are the best "rescue" matchers when correlation fails. BiRefNet foreground/background segmentation is genuinely useful for anime stitching because Japanese panning shots commonly use multi-plane parallax (foreground and background pan at different speeds) — segmenting and stitching layers separately removes a whole class of ghosts. The arXiv 2509.09501 Manga Region-Wise Correspondence work is a region-not-pixel matcher and is *not* a drop-in replacement for stitching alignment.

---

## Key Findings

1. **Direct (area-based) registration beats feature-based registration on anime.** ECC and phase correlation operate on pixel intensities over the whole window. They are insensitive to whether texture exists and never produce a "wrong cluster" of correspondences — the worst they do is produce a low correlation score, which can be detected and rejected. SIFT/ORB/AKAZE on anime line art produce many keypoints but they are **biased and spatially correlated**, which is far more dangerous than producing few keypoints because RANSAC silently returns a high-inlier-count but geometrically meaningless transform.

2. **RANSAC with collinear inliers is degenerate, not just inaccurate.** The 4-point homography DLT has a rank-deficient design matrix when the four points are (nearly) collinear; the literature on SupeRANSAC, QDEGSAC and related work explicitly identifies this and recommends sample-degeneracy checks. On anime line art, *most* of the keypoints lie on 1-D contours, so the 4-point sample is collinear with high probability, and the resulting H is unstable in the direction perpendicular to the line — precisely the failure mode visible in your bad2 image (a small dy/dx error magnified into a warped/inverted overlay).

3. **8-DOF homography is the wrong model for 2D camera pans.** Panned anime shots are pure translations (occasionally with a tiny zoom/rotation). Estimating 8 DOF from biased features lets the extra 6 DOF absorb noise as "wave" warping and vertical drift. OpenCV's `Stitcher::SCANS` mode and `AffineBestOf2NearestMatcher`/`BundleAdjusterAffinePartial` exist precisely for this case (4-DOF similarity); but for the TV-anime case even 4 DOF is too many and `MOTION_TRANSLATION` (2 DOF) is preferred.

4. **Distance-transform feathering is hostile to misaligned input.** Feathering's whole job is to make seams invisible by softly blending overlapping content; if the geometry is wrong, the soft blend turns the mistake into a transparent ghost spread over hundreds of pixels (your bad1). Hard-cut seam finders (graph-cut / dynamic programming) and multi-band Laplacian blending suppress small misalignment, but **no blender can rescue an alignment error larger than the multi-band low-frequency wavelength**. The correct fix is at the alignment stage, not the blend stage.

5. **Anime has specific signal pathologies that make alignment harder than natural images:** (a) per-frame brightness micro-shifts from the post-Pokémon-Shock (1997) Japanese broadcast safety guidelines that automatically dim/dampen any flashing; (b) chroma subsampling (4:2:0 in MPEG-2/H.264 broadcast and Blu-ray) that puts color information on a half-resolution grid offset from luma — using all RGB channels for alignment is therefore worse than using Y' only (this is exactly why Overmix switched to Y-only after 2014); (c) MPEG quantization noise that produces sub-pixel "wobble" in flat color regions; (d) on-screen TV-station logos, subtitles and dark-edge borders that are *not* part of the panning content and must be excluded from the registration ROI.

6. **Modern detector-free matchers solve the texture-starvation problem but not the model problem.** LoFTR (CVPR 2021), Efficient LoFTR (CVPR 2024), DKM (CVPR 2023) and RoMa (CVPR 2024) all explicitly target low-texture regions where "feature detectors usually struggle to produce repeatable interest points." They produce dense / semi-dense matches and DINOv2-pretrained backbones (RoMa) are robust to the appearance gap between natural-image training data and anime drawings. SuperPoint+LightGlue is a sparse-matching learned alternative that is much faster but inherits SuperPoint's biased detection on cartoon imagery.

7. **The Overmix design (spillerrec, 2013–2024) is still the closest reference implementation** for this exact problem and converged on a few principles after a decade of iteration: align on Y' only; horizontal/vertical translation only with sub-pixel precision via 4× upscaling; render with averaging/median across all frames to suppress MPEG noise and JPEG/H.264 quantization; explicit support for foreground/background separation when planes pan at different speeds; explicit dump-tools to bypass video player chroma resampling. Overmix's stated weakness is exactly the case where naïve feature-based methods fail: "It works nicely well for non moving images but can't seem to get it to work on anime images that have the view moving around."

---

## Details

### 1. Why each "bad" image failed (technical post-mortem)

**Image 1 (stitch2.png — GOOD, sharpness 15.6, max ΔY ≈ 2.4):** Sequential / template-matching + ECC. Brightness jump near zero across seam means the global gain has not changed and exposure compensation isn't required. Sharpness ~15 is consistent with a single non-blurred image — there is no double-exposure ghost. ECC `MOTION_TRANSLATION` finds the 2-DOF (tx, ty) that maximizes the normalized correlation between template and warped input, which is robust to anime-style flat regions because the correlation peak depends on the entire intensity field, not on a few feature points.

**Image 2 (bad1, purple girl, sharpness 43.6, max ΔY ≈ 153):** This signature — abnormally high sharpness *and* a 100+ unit brightness discontinuity — is the canonical "two well-aligned-individually frames placed at the wrong global offset, then alpha-blended". The SIFT BFS pipeline:
- (a) found keypoints, but they clustered on the high-contrast outline of the character against a flat purple background;
- (b) RANSAC's 4-point sample drew points all sitting on the outline → a (near-)collinear configuration → degenerate DLT → returned a homography with high inlier count but with an arbitrary scale factor in the direction normal to the line;
- (c) the resulting (dx, dy) was off by tens of pixels;
- (d) the distance-transform-weighted feather summed both frames at every pixel of the overlap region with weights that were similar (each frame is far from its own boundary in the overlap interior). Two slightly-different copies of the character were therefore added at ~50% each → **transparent ghost overlay**. The high "sharpness" is an artifact of *edge doubling*, not real sharpness; the 153 ΔY brightness jump is the discontinuity at the edge of the (mis-)overlap region where one frame's content suddenly disappears.

**Image 3 (bad2, baseball, sharpness 26.3, max ΔY ≈ 109):** Different failure mode of the same SIFT pipeline. Here the homography wasn't catastrophic in (dx, dy) but had non-zero off-diagonal entries — the extra 6 DOF (vs the correct 2-DOF translation) absorbed the bias of the line-clustered features and produced a small rotation + perspective warp. When that warped second frame was blended onto the canvas, you got a "warped/inverted ghost overlay": the content roughly aligns near the keypoint cluster (where RANSAC optimized) and diverges progressively away from it (geometric drift). The sharpness 26 is again edge doubling, milder than bad1 because the geometric error is smoother.

In both bad cases, the *blender is not at fault* — distance-transform feathering simply faithfully reports the alignment error.

### 2. Comparison table of methods

Columns: Anime flat-color = handles uniform regions; Exposure robust = robust to per-frame intensity changes; Zoom/rot = handles non-translation; Cost = relative compute; Ghost risk = if alignment is wrong, how badly does the method fail.

| Method | Anime flat-color | Exposure-robust | Zoom/rot | Cost | Ghost risk if wrong | Notes for anime panels |
|---|---|---|---|---|---|---|
| **SIFT + RANSAC + Homography** | ✗ (clusters on lines) | ~ (descriptor partly invariant) | ✓ | Med | **High** (silent wrong H) | Default in OpenCV's Stitcher PANORAMA. Worst for anime flat color. |
| **ORB + RANSAC** | ✗ (FAST corners rare in flat regions) | ✗ (brightness sensitive) | ✓ | Low | High | Fastest but most brittle on anime. |
| **AKAZE / KAZE** | ~ (nonlinear diffusion → fewer line bias) | ✓ | ✓ | Med | Med | Slightly better than SIFT on cartoons; still keypoint-biased. |
| **OpenCV SCANS mode (affine BestOf2Nearest)** | ✗ (still keypoint-based) | ✓ | partial (4-DOF) | Med | Med | Right model class for scanner-like inputs but still needs features. |
| **Phase Correlation (DFT)** | ✓ (global, not feature-based) | ✓✓ (phase normalizes magnitude) | ✗ (translation only without log-polar) | Low | **Low** (peak height detectable) | Ideal global initializer for 2D pans. |
| **ECC `MOTION_TRANSLATION`** | ✓ | ✓ (zero-mean correlation) | ✗ | Low | Low | Refines phase-correlation initial guess to sub-pixel. |
| **ECC `MOTION_EUCLIDEAN`** | ✓ | ✓ | ✓ (rot+trans) | Low-med | Low | Use when zoom/rot is suspected and DOF needs to be limited. |
| **ECC `MOTION_AFFINE` / `MOTION_HOMOGRAPHY`** | ~ (more DOF can drift) | ✓ | ✓ | Med | Med | Avoid for pure pans — over-parameterized. |
| **Template matching (NCC)** | ~ (works if template has any structure) | ✓ | ✗ | Low | Low | Good gating signal; weak alone. |
| **Optical flow (Farneback / DeepFlow)** | ✓ (dense) | ~ | ✓ (per-pixel) | Med-High | Med | Overkill for global pans; useful for parallax planes. |
| **SuperPoint + LightGlue** | ~ (better than SIFT on cartoons but biased) | ✓ | ✓ | Med (GPU) | Med | Useful when ECC fails on a multi-shot stitch. |
| **LoFTR / Efficient LoFTR** | ✓✓ (designed for low-texture) | ✓ | ✓ | High (GPU) | Low-med | Best learned matcher for anime-like flat regions. |
| **DKM / RoMa (DINOv2)** | ✓✓ (DINOv2 features cover stylized art) | ✓✓ | ✓ | High (GPU) | Low | State-of-the-art robustness on hard pairs (CVPR 2023/2024). |
| **Manga Region-Wise Correspondence (arXiv 2509.09501)** | ✓ (designed on line art) | n/a | n/a | High (GPU) | n/a (not pixel-level) | Region-level matcher for colorization; not a stitching aligner. |
| **Overmix (recursive aligner + 4× upscale)** | ✓✓ | ✓ | ✗ (translation only) | Med | Low | Reference implementation for anime panning shots. |
| **UDIS / UDIS++ (deep stitching)** | ~ | ✓ | ✓ | High | Med | Trained on natural images; domain shift on anime. |

Ghosting risk is the *combined* probability of the alignment producing visually-bad output, assuming a downstream blend that doesn't itself add ghosts. With multi-band Laplacian + graph-cut seam, you can absorb a few pixels of error; with naïve distance-transform feathering you cannot.

### 3. Recommended pipeline for anime screenshot stitching (2025/2026)

The pipeline below assumes the input is a sequence of frames extracted from a panning shot in an anime episode. It is ordered for reliability first, speed second.

1. **Frame extraction without resampling.** Use `ffmpeg` directly (or Overmix's dump-tools) to extract every frame at full chroma fidelity. Avoid using a video player's "screenshot" feature — `mpv` and especially VLC apply runtime resamplers that introduce per-frame wobble. For Hi10p sources, preserve 10-bit; convert only at the end.

2. **Crop broadcast borders and overlays.** Trim a small margin (e.g. 4–8 px on each side) to remove dark-edge artifacts from MPEG block-edge replication. Detect and mask station logos, subtitles, and the on-screen "viewer warning" caption that may persist. A simple temporal-median subtraction on the trimmed sequence reveals static overlays.

3. **Convert to Y' (luma) only.** RGB alignment under-weights the luma channel and lets chroma subsampling artifacts dominate the registration error. Use BT.709 or BT.601 luma depending on source flag.

4. **Detect scene cuts.** Compute pairwise NCC on consecutive frames at a small downsample (256 px wide) — a frame-to-frame correlation drop below ~0.5 indicates a cut. Stitch only within a single shot.

5. **Classify the shot type.** Compute NCC over a coarse (dx, dy) grid; if the peak is sharp and of similar magnitude across consecutive pairs → pure pan. If the peak is broad / shifting in scale → zoom or perspective; switch to a learned matcher (step 7b).

6. **Detect overlap order.** Build a graph of frame-pairs by NCC peak height; threshold to discard pairs with peak < 0.7. Retain only sequential edges (typical for a pan); reject "BFS over all pairs" because anime sequences have repeating background that would create wrong long-range edges.

7. **Pairwise alignment (the core step):**
   - **a) Pan/static (default):** Phase Correlation (windowed Hann/Hamming) → integer (dx, dy). Refine with ECC `MOTION_TRANSLATION`, initialised from phase-correlation result, on a Y'-only image, with 5–10 iterations and 1e-6 termination. Validate by computing ECC ρ and NCC on the resulting overlap; reject if ρ < 0.95 (anime should easily exceed 0.97 on the same shot).
   - **b) Zoom/rotation/parallax:** Try ECC `MOTION_EUCLIDEAN` first; if it fails, switch to LoFTR or RoMa (recommended) → run RANSAC for affine (4-DOF) — *not* full homography — using `cv2.estimateAffinePartial2D`. Reject if residual > 1.5 px.
   - **c) Reject and skip** if both fail; do not feed unreliable transforms into the canvas.

8. **Optional: foreground/background separation.** Anime panning shots frequently use multi-plane parallax (Studio Ghibli–style backgrounds move slower than midground). Use **BiRefNet** (`BiRefNet-portrait` / `BiRefNet-general`) to segment the foreground; align background and foreground stacks separately; composite at the end. This is the right place for BiRefNet in the pipeline — not as a deghoster after-the-fact but as a layer separator before alignment.

9. **Global bundle adjustment.** Once all pairwise (dx, dy) are obtained with confidences, solve a small weighted least-squares for the per-frame absolute offset. For pure translations this is trivial.

10. **Sub-pixel resampling.** Use Lanczos-3 resampling to a 4× canvas, blend, then downsample — Overmix's super-resolution trick. This minimizes sub-pixel blur.

11. **Per-frame exposure normalization.** Compute global mean/median per-frame on the overlap; fit and remove a per-frame gain (BlocksGainCompensator from OpenCV is often overkill for anime — a single global gain per frame is usually enough since anime broadcast artifacts are a uniform brightness shift). Use **block-based** compensation only if the source has fade-in/out or post-Pokémon-Shock dimming on flashing frames.

12. **Render: median first, average if few frames.** Median across N≥5 frames is the most robust to credits, MPEG noise, and outlier subtitle pixels. With N<5, fall back to average. Avoid alpha-feathering when alignment confidence is high — a hard cut produces sharper output.

13. **Seam finishing.** If frame intensities still mismatch slightly after step 11, apply graph-cut seam finder (`cv::detail::GraphCutSeamFinder`, COST_COLOR_GRAD) to find a low-gradient cut path, and apply a narrow multi-band Laplacian blend (3–5 bands) only along that seam. Distance-transform feathering should be the *last* resort, used only over a few-pixel ribbon, and only when alignment ρ ≥ 0.99.

14. **Output 16-bit intermediate, 8-bit dithered final.** Like Overmix, render in ≥16-bit and dither down to avoid banding in flat anime gradients.

### 4. Code-level recommendations

#### Fix `_merge_images_scan_stitch` (the SIFT BFS pipeline)

The current pipeline's failures come from four compounding problems. Address each:

```python
# (a) Replace the BFS-over-all-pairs with a sequential or NCC-confidence-graph order.
def order_frames_by_ncc(frames):
    # Compute NCC on heavily downsampled frames between every pair
    # Keep only edges with peak > 0.7 and above-threshold sharpness
    # Build a chain (MST or sequential ordering on x)
    ...

# (b) Restrict the geometric model. For anime panning shots:
M, mask = cv2.estimateAffinePartial2D(  # 4-DOF: rot+scale+trans
    src_pts, dst_pts,
    method=cv2.USAC_MAGSAC,           # MAGSAC++ is far more robust than vanilla RANSAC
    ransacReprojThreshold=2.0,
    maxIters=10000,
    confidence=0.9999,
)
# Or, even better, force translation only:
# M = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)

# (c) Add degeneracy check on the sample.
def is_collinear(pts, tol=2.0):
    # Fit line via SVD; return True if max perpendicular distance < tol
    ...
# Reject SIFT matches whose convex hull area / point count is tiny (line-clustered).

# (d) Validate post-RANSAC. Compute NCC/ECC ρ on the overlap region of the warped image
# vs the canvas; if ρ < 0.95, reject this pair and fall back to ECC translation,
# then to phase correlation, then skip.

# (e) Replace SIFT with a feature stack tried in order:
#     1) Phase correlation + ECC translation  (default)
#     2) ECC Euclidean                          (if 1 fails on this pair)
#     3) AKAZE (less line-biased than SIFT)
#     4) LoFTR / RoMa via Kornia                (if all classical fails)

# (f) Replace distance-transform feathering with confidence-aware blending:
if alignment_rho > 0.99:
    blend = "hard_cut_with_graphcut_seam"
elif alignment_rho > 0.95:
    blend = "narrow_multiband_laplacian_3band"
else:
    skip_pair()  # do not blend a low-confidence alignment at all
```

#### Improve `perfect_stitch` (the ECC + template matching path)

This path is already the right architecture; tighten it with:

```python
# 1. Pre-warm ECC with phase correlation, not zeros.
shift, response = cv2.phaseCorrelate(np.float32(prev_y), np.float32(curr_y),
                                     window=cv2.createHanningWindow(prev_y.shape[::-1], cv2.CV_32F))
warp = np.array([[1, 0, shift[0]], [0, 1, shift[1]]], dtype=np.float32)

# 2. Run ECC on Y' only, MOTION_TRANSLATION first.
try:
    rho, warp = cv2.findTransformECC(
        templateImage=prev_y, inputImage=curr_y,
        warpMatrix=warp, motionType=cv2.MOTION_TRANSLATION,
        criteria=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT, 100, 1e-6),
        inputMask=valid_mask)  # valid_mask excludes logos/subs/dark borders
except cv2.error:
    rho = 0.0

# 3. Two-stage: if pure translation rho < 0.99, try EUCLIDEAN.
if rho < 0.99:
    warp3 = np.eye(2, 3, dtype=np.float32)
    warp3[:2, :2] = warp[:2, :2]   # keep translation guess
    rho, warp = cv2.findTransformECC(prev_y, curr_y, warp3, cv2.MOTION_EUCLIDEAN, ...)

# 4. Validate with template-match NCC on the predicted overlap.
overlap_score = cv2.matchTemplate(prev_y[overlap_box], curr_y_warped[overlap_box],
                                  cv2.TM_CCOEFF_NORMED).max()
if overlap_score < 0.97:
    flag_and_skip()

# 5. Detect scene cuts BEFORE stitching: any consecutive-frame NCC drop > 0.4
#    means the two frames are from different shots.

# 6. Multi-resolution: do alignment on a 0.5x downsample first, then refine
#    at full resolution; this both speeds up and avoids local minima from MPEG noise.
```

### 5. Should BiRefNet (or similar) foreground segmentation be in the pipeline?

**Yes, but as a layer-separator before alignment, not as a deghoster after blending.** The fundamental cause of "ghost overlay" in your bad images is wrong geometry, which BiRefNet cannot fix. However, BiRefNet *does* solve a different anime-specific problem that classical pipelines handle poorly:

- **Multi-plane parallax in panning shots.** Anime production routinely pans the camera over a static composite where foreground and background cels move at different rates (a common 2D-animation cost-saving). A single global (dx, dy) cannot align both planes simultaneously, and any blend will ghost at least one of them.
- **Solution:** Run BiRefNet (or any high-quality anime-trained segmentation network — there are multiple anime-specific segmentation models and BiRefNet's `general` and `portrait` variants generalize well to stylized art) to obtain a per-frame foreground mask. Stitch foreground and background stacks independently, each with its own (dx, dy) trajectory. Composite at the end.
- **Bonus:** The same masks let you mask out moving foreground content (e.g. a talking character) from background averaging, which is one of Overmix's stated goals ("separation of foreground and background in slides where foreground and background moves with different speeds").

BiRefNet is *not* the right tool for "removing the ghost" after the fact — that requires fixing alignment.

### 6. The arXiv 2509.09501 paper (Region-Wise Correspondence on manga line art)

Worth citing for context but not directly applicable as a stitching aligner. The paper introduces a **patch-level transformer that predicts region correspondences** between two raw manga line-art images, with a downstream edge-aware clustering step that lifts patch-level scores to pixel-precise region masks. The intended downstream tasks are **automatic colorization and in-betweening**, not panoramic stitching. It is structurally similar to LoFTR's coarse-to-fine architecture but trained specifically on line-art and outputs region-to-region correspondences (not pixel correspondences) at ~96% accuracy on its benchmark. For stitching, use LoFTR/RoMa instead — they output pixel correspondences with high confidence even on cartoon-style images thanks to DINOv2 features. The Manga Region-Wise method is interesting if you ever need to *transfer* color or annotations across stitched frames, but is the wrong abstraction layer for finding a (dx, dy) offset.

### 7. The Pokémon Shock connection (why per-frame brightness shifts exist)

After the 16 December 1997 broadcast of "Dennō Senshi Porygon" hospitalized hundreds of children with photosensitive seizures, Japanese broadcasters introduced what became known as the "Pokémon Rules": red flashes capped at 3 Hz, any color flashing capped at 5 Hz, total flash duration capped at 2 s. In practice this meant Japanese animation studios apply automated brightness-clamping passes during post-production (and broadcasters apply runtime dimming on the air signal). The result is that consecutive frames of the *same* underlying drawing can have small but real intensity differences when the algorithm engages. This is one (often-cited but rarely-quantified) source of the per-frame brightness shifts you see on stitched outputs and is the technical reason exposure compensation is mandatory for TV-source anime even when the animators didn't intend any change. Your "good" stitch's max ΔY ≈ 2.4 is consistent with no dimming engaged on any frame; values above ~10 typically indicate the scene includes a flash/fade and BlocksGainCompensator (or per-frame global gain matching) is required.

---

## Caveats

- Several specific numeric thresholds above (NCC > 0.7 for valid pairs, ρ > 0.95 for good ECC convergence, ρ > 0.99 for hard-cut blending) are practical defaults observed in OpenCV/Overmix work; they should be tuned per-show because line densities and color saturation vary substantially between animation studios and eras.
- I could not locate published benchmark numbers for SuperPoint/LightGlue, LoFTR, DKM or RoMa specifically *on anime imagery* — the qualitative claim that detector-free transformer matchers outperform SIFT on flat regions is well-supported in the LoFTR, DKM and RoMa papers but the specific transfer to anime is by analogy (low-texture indoor MegaDepth/ScanNet imagery is the closest published benchmark). Empirical validation on your actual frames is recommended.
- The "Pokémon Rules" affect *all* Japanese animation post-1998, but the magnitude of automated brightness clamping varies per studio and per broadcast network; this is widely discussed in animation-production circles but is not the subject of a formal published quantification I could find.
- The `arXiv 2509.09501` Manga Region-Wise paper is recent (Sep 2025, latest revision Nov 2025) and a v3 preprint; results have not yet been independently reproduced in published comparisons.
- The "BFS over all pairs" failure mode I describe for `_merge_images_scan_stitch` is inferred from the user's description; without seeing the actual code, the specific implementation detail (whether it builds an MST, a star, or a path) may vary, but the recommendation to use sequential / NCC-confidence-graph ordering applies regardless.
- Where I describe Overmix design decisions, I rely primarily on the project's own GitHub README and the spillerrec.dk blog posts (2013–2014); the codebase has continued evolving and some of the algorithmic specifics (recursive aligner, sub-pixel via 4× upscale) are stated by the author but not formally evaluated against modern matchers in any peer-reviewed comparison.
- Any deep-learning matcher (LoFTR, DKM, RoMa, SuperPoint+LightGlue, BiRefNet) is a single GPU-bound model; for a CPU-only stitching tool the recommendation is to keep ECC + phase correlation as the primary path and treat learned matchers as optional GPU rescue paths.