# AnimeStitchPipeline — CV Research Survey & Comprehensive Improvement Plan

*Date: 2026-05-26*
*Benchmark baseline: `anime_stitch_20260526_192625.json` — 22/22 ASP successes*

---

## Table of Contents

1. [Current Pipeline Status](#1-current-pipeline-status)
2. [Benchmark Analysis & Remaining Weaknesses](#2-benchmark-analysis--remaining-weaknesses)
3. [CV Research Survey (2023–2025)](#3-cv-research-survey-20232025)
4. [Improvement Plan — Tier 0: Diagnostics & Infrastructure](#4-improvement-plan--tier-0-diagnostics--infrastructure)
5. [Improvement Plan — Tier 1: Matching Engine Upgrade](#5-improvement-plan--tier-1-matching-engine-upgrade)
6. [Improvement Plan — Tier 2: Sub-pixel Refinement Overhaul](#6-improvement-plan--tier-2-sub-pixel-refinement-overhaul)
7. [Improvement Plan — Tier 3: Rendering & Compositing Upgrades](#7-improvement-plan--tier-3-rendering--compositing-upgrades)
8. [Improvement Plan — Tier 4: Post-Processing Chain](#8-improvement-plan--tier-4-post-processing-chain)
9. [Improvement Plan — Tier 5: Architecture-Level Improvements](#9-improvement-plan--tier-5-architecture-level-improvements)
10. [Implementation Roadmap & Expected Impact](#10-implementation-roadmap--expected-impact)

---

## 1. Current Pipeline Status

### 1.1 Architecture (13 stages)

```
Stage 1:   Load & trim                ← cv2 imread, aspect validation
Stage 2:   Width normalisation        ← _normalise_widths
Stage 3:   BaSiC flat-field corr.     ← optional sklearn-based flat-field model
Stage 4:   BiRefNet fg masking        ← character isolation for match exclusion
Stage 4.5: Bg photometric norm.       ← per-frame gain [0.80–1.25], bg-only
Pre-5:     Exact-duplicate dedup      ← drop frames with luma_diff < 3.0
Stage 5-6: Pairwise matching          ← LoFTR → TM → PC masked → PC unmasked
           + Edge filter              ← geom. consistency, min-step, direction consensus,
                                         velocity correction
Post-6:    Spatial dedup              ← drop adj frames with displacement < 25px (iterative)
Stage 7:   Global bundle adjustment   ← Levenberg-Marquardt, translation-only
                                         2-pronged outlier rejection (point residual + dy outlier)
Stage 7b:  Affine validation gate     ← ratio, min_gap, rotation, scale; 3-tier retry
Stage 8:   ECC sub-pixel refinement   ← pyramid ECC, 2-DOF translation, bg-masked
Stage 9:   Canvas construction        ← _compute_canvas + T_global offset
Stage 10:  Temporal renderer          ← median / first / Laplacian-blend (default: median)
Stage 11:  Foreground composite       ← Laplacian blend, seam search ±250px, adaptive feather
Stage 13:  Morphological crop         ← _crop_to_valid + fixed 30px edge_crop
Optional:  MFSR                       ← DCT restoration, PSO/DRL registration,
                                         diffusion inpainting, de-seam
```

**Submodules:** `matching.py` (380 LOC) · `bundle_adjust.py` (218) · `compositing.py` (479) ·
`rendering.py` (715) · `ecc.py` (133) · `masking.py` (66) · `photometric.py` (136) ·
`validation.py` (141) · `canvas.py` (278) · `mfsr/` (PSO, DRL, DCT, diffusion, SR)

### 1.2 Current Benchmark Results

| Metric | Value |
|---|---|
| ASP success rate | **22/22 (100%)** |
| avg sharpness — ASP | **33.14** |
| avg sharpness — SCANS | 25.88 (+28.0% gain) |
| avg coverage | 98.5% |
| avg ghosting score | 22.17 |
| avg seam gradient | 4.73 |
| Tests where SCANS beats ASP | 0 *(test16: 32.4 vs 38.9 — one inversion)* |
| Tests where ASP clearly better | 4 (test9, test12, test13, test21) |

### 1.3 Per-Test Sharpness Overview

| Test | sh_ASP | sh_SCANS | Frames | Ratio | dy_cv | Note |
|---|---|---|---|---|---|---|
| test20 | 12.62 | 10.16 | 7 | 1.040 | 2.14 | Dark/blurry source |
| test2  | 12.92 |  9.41 | 8 | 1.000 | 0.00 | Very low sharpness |
| test19 | 14.95 | 13.84 | 10 | 1.005 | 0.29 | Low source quality |
| test3  | 15.99 | 13.72 | 11 | 1.027 | 0.01 | Low source quality |
| test18 | 17.92 | 12.70 | 5 | 2.000 | 0.35 | Clustered frames |
| test16 | 32.42 | **38.93** | 10 | 1.013 | 0.30 | **SCANS wins** |
| test7  | 36.91 | 24.49 | 9 | 1.515 | 0.29 | Diagonal motion; coverage 81.5% |
| test9  | 60.25 | 35.73 | 7 | 1.422 | 0.25 | ASP +69% |
| test13 | 66.55 | 42.75 | 9 | 1.067 | 0.23 | ASP +56% |
| test14 | 81.21 | 75.22 | 7 | 1.014 | 0.16 | Highest sharpness |

---

## 2. Benchmark Analysis & Remaining Weaknesses

### W1 — Low-Sharpness Cluster (tests 2, 3, 19, 20)

Sharpness 12–16 despite 100% coverage and valid alignment. Root cause: inherently blurry or
dark source frames (low-bitrate encode, dark scenes with JPEG block artifacts) that the current
pipeline cannot recover. The MFSR module in `mfsr/` exists (DCT restoration, PSO registration,
diffusion inpainting) but is disabled by default (`mfsr_mode=False`) and never auto-triggers.

### W2 — test16 Inversion: SCANS Beats ASP (32.4 vs 38.9)

The `dy_steps` show highly variable intervals: `[-86.5, -161.6, -141.5, -145.8, -133.0, -141.9,
-120.1, -97.6, -241.1]`. First and last steps deviate strongly from the median (~141px). Two
edges (5→6, 6→7) carry `weight=0.55` with `n_pts=200` synthetic background samples — not real
LoFTR features, meaning the BA solution at frames 5–7 is weakly constrained. Skip edge 4→6
carries `dy=805px` across 2 frames (expected ~282px), likely a template-match false lock on a
repeating background pattern.

The uneven frame spacing smears the temporal median in overlap zones. SCANS uses each frame
once with no cross-frame averaging, so it stays sharp. This is the **only remaining quality
gap** in the current pipeline.

### W3 — High Ghosting (avg 22.17, max 33.6 on test13)

`_cluster_animation_phases` in `rendering.py` performs FFT-based temporal frequency analysis to
detect cyclically animated pixels. It is computed correctly but **discarded** — its output
(`anim_mask`, `phase_groups`) is never passed to `_render_median`. Moving characters therefore
contribute their full pixel value to the background median, leaving ghost images proportional
to how much of the frame cycle is spent in each pose.

### W4 — test7 Coverage Gap (81.5%)

Diagonal motion (`dx≈195px`, `dy≈290px` per step) leaves triangular black corners at canvas
boundaries. The `mfsr/diffusion_inpaint.py` module exists but is not triggered automatically
when `coverage < threshold`. Black corners are the current output.

### W5 — ECC Failure on Flat Regions

`_ecc_refine` uses pixel intensity gradients (via `cv2.findTransformECC`) to drive alignment.
Anime's large uniform color fields (sky, walls, character costumes) produce near-zero image
gradients → ECC diverges. The 80px drift guard prevents catastrophic failure but means ECC
provides **zero sub-pixel benefit** on roughly 30% of frame pairs (all flat-region frames).
The correction is clamped to BA output, so the pyramid ECC time (~6s per test) is wasted.

### W6 — LoFTR 2021 Vintage

LoFTR (ICCV 2021) is the matching backbone. On 4K frames, its O((HW)²) dense coarse attention
is the dominant runtime bottleneck (~12s/pair). EfficientLoFTR (CVPR 2024, arXiv:2403.04765)
is a direct drop-in at 2.5× faster throughput.

### W7 — Synthetic BA Anchor Points for Non-LoFTR Edges

When matching falls back to Template Match or Phase Correlation, anchor points for the BA
residuals are 200 uniformly-sampled background pixels (`_sample_bg_points`), not real
correspondences. These synthetic points dilute the real LoFTR signal from other edges,
biasing the LM solver toward averaged solutions and softening the effective error signal for
the constrained frames.

### W8 — No Semantic Seam Routing

Boundary placement searches ±250px around the midpoint for the minimum photometric L1
difference. The optimal photometric position can still bisect a character outline, producing
the most visually prominent stitching artifact in anime. There is no object-aware cost term.

### W9 — No Post-Processing Super-Resolution

Output resolution equals source resolution. Real-ESRGAN `anime_6B` (targeted at anime cel
shading and line art) applies 2–4× upscaling with tile-and-stitch for large panoramas. Not
integrated.

### W10 — Hard Border Crop

A fixed 30px edge crop (`edge_crop=30`) removes valid content uniformly. Irregular
non-rectangular canvas edges from diagonal or wide pans leave additional ragged borders
beyond the fixed crop that are currently black. No content-aware rectangling exists.

---

## 3. CV Research Survey (2023–2025)

### 3.1 Feature Matching

---

#### EfficientLoFTR · CVPR 2024 · arXiv:2403.04765
**Code:** https://github.com/zju3dv/EfficientLoFTR

Replaces LoFTR's expensive dense attention with a two-stage correlation layer: a lightweight
coarse-level adaptive span attention followed by fine-level local refinement. Same semi-dense
output format as LoFTR. **2.5× faster** at matching or exceeding accuracy on HPatches,
MegaDepth, ScanNet. Outperforms even SuperPoint+LightGlue on challenging baselines.

*Relevance:* Direct drop-in replacement for the current `LoFTRWrapper`. No interface changes
required. Restores the 4K bottleneck to manageable levels.

---

#### LightGlue · ICCV 2023 · arXiv:2306.13643
**Code:** https://github.com/cvg/LightGlue

Attentional GNN matcher with adaptive early exit — stops when confidence is sufficient,
reducing compute 40–60% vs SuperGlue with equal or better AUC. Native support for SuperPoint,
DISK, ALIKED, SIFT feature backends. Achieves near-real-time performance with ALIKED features.

*Relevance:* Best sparse matcher for the fallback tier between LoFTR and Template Match.

---

#### ALIKED · IEEE TIM 2023 · arXiv:2304.03608
**Code:** https://github.com/Shiaoming/ALIKED

Sparse Deformable Descriptor Head (SDDH): learns to position sampling locations adaptively
around each keypoint rather than using a fixed grid. More robust on non-photorealistic content
(anime line art, manga). Lighter than SuperPoint, native LightGlue support.

*Relevance:* The deformable sampling is specifically advantageous for anime's gradient-sparse
regions. Pair with LightGlue as the sparse fallback tier (Attempt 1b in `_match_pair`).

---

#### XFeat · CVPR 2024 · arXiv:2404.19174
**Code:** https://github.com/verlab/accelerated_features

CPU-real-time sparse and semi-dense matching via revisited CNN design. Both sparse mode and
"semi-dense" mode via a match refinement module. LighterGlue variant: 3× faster than
LightGlue with XFeat features. Suitable for GPU-free environments.

*Relevance:* Emergency fallback when CUDA is unavailable. The semi-dense mode is useful for
anime frames where sparse detectors produce few keypoints.

---

#### RoMa / RoMa v2 · CVPR 2024 + arXiv:2511.15706
**Code:** https://github.com/Parskatt/RoMaV2

Pixel-dense warp estimation using frozen DINOv2 ViT features (robust to artistic style,
cross-modality, flat shading) combined with fine ConvNet features. Outputs pixel-level
displacement fields with per-pixel reliability confidence. v2 adds a decoupled two-stage
transformer+UNet refiner pipeline for better speed and accuracy on hard cases.

*Relevance:* DINOv2 features are trained on diverse visual data and are **style-agnostic** —
they produce useful correspondences on flat-shaded anime art where LoFTR may produce few
keypoints. Use as Attempt 4 (last resort before failure) in `_match_pair`: compute dense warp
over background pixels, take the trimmed-mean translation.

---

#### JamMa · CVPR 2025 · arXiv:2503.03437
**Code:** https://github.com/leoluxxx/JamMa

Replaces O(N²) attention in the matching transformer with O(N) Mamba state-space scans. Joint
scan of both images enables high-frequency mutual interaction at linear cost. Achieves better
performance than attention-based matchers with <50% parameters and FLOPs.

*Relevance:* For 4K source frames (`H×W ≈ 3840×2160`), the sequence length in the coarse
stage of EfficientLoFTR is still large. JamMa's linear scaling makes it the practical choice
for 4K bulk processing without tiling.

---

#### EDM (Efficient Deep Matching) · ICCV 2025 Highlight · arXiv:2503.05122
**Code:** https://github.com/chicleee/EDM

Revisits all stages of detector-free matching: Correlation Injection Module progressively
injects global-to-local correlations; lightweight bidirectional axis-based regression head for
subpixel localization without costly heatmap computation. ICCV 2025 Highlight status.

*Relevance:* Good quality/speed trade-off candidate for 4K frames. Benchmark against
EfficientLoFTR on the 22-test suite.

---

### 3.2 Video Panorama Stitching

---

#### StabStitch · ECCV 2024 · arXiv:2403.06378
**Code:** https://github.com/nie-lang/StabStitch

Introduces "warping shake" — temporal instability of warped non-overlapping regions even
when the input video is stable. Caused by per-frame independent alignment that produces
micro-jitter in translation trajectories. Jointly optimises spatial alignment and temporal
smoothness via a warp trajectory model. Requires no camera poses, no synchronisation.
Unsupervised.

*Relevance:* **Most directly applicable video stitching paper.** Anime panning sequences
exhibit exactly the warping-shake problem. The trajectory smoothness loss can be added to the
existing LM bundle adjustment as a second-order temporal regulariser.

---

#### StabStitch++ · IEEE TPAMI May 2025 · arXiv:2505.05001

Extends StabStitch with **bidirectional midplane projection**: instead of warping all frames
into the coordinate system of frame 0, both images are projected onto a virtual midplane
(average position). Differential decomposition disentangles homography from stabilisation.
Distributes distortion symmetrically rather than bending all content toward frame 0.

*Relevance:* For 14-frame pans, frame 0 and frame 13 are both heavily distorted in the
current setup (frame 0 is identity, frame 13 is maximally offset). Midplane centering halves
the maximum per-frame distortion. Single-line change in Stage 9.

---

#### VidPanos · SIGGRAPH Asia 2024 · arXiv:2410.13832

First system for creating panoramic videos from general panning videos including moving
objects. Uses coarse-to-fine synthesis and spatial aggregation to condition video generation
models on known canvas regions, completing unknown areas generatively.

*Relevance:* The **generative completion** of unknown canvas regions addresses W4 (test7
coverage 81.5%). A diffusion model conditioned on visible canvas content inpaints the
triangular black corners in a style-consistent way.

---

### 3.3 Seam Finding & Blending

---

#### SemanticStitch · The Visual Computer 2025 · arXiv:2511.12084
**Code:** https://github.com/Pokerman8/OAIV-Coherence

Incorporates semantic priors into seam carving: a novel loss penalises seams that cross
salient foreground object contours detected by a segmentation model.

*Relevance:* Directly prevents the worst stitching artifact for anime — seams bisecting
character outlines. The segmentation model can be SAM, which the pipeline already indirectly
uses through BiRefNet.

---

#### OBJ-GSP · AAAI 2025 · arXiv:2402.12677

Uses Segment Anything Model (SAM) to extract full-object contours. Triangular mesh
transformation balances projective and similarity transforms to preserve object shapes.
Introduces StitchBench — the largest diverse image stitching benchmark.

*Relevance:* SAM-based shape preservation prevents character body distortion at seams in
addition to routing seams away from outlines (complementary to SemanticStitch).

---

#### DSFN · NeurIPS 2025 · arXiv:2510.21396
**Code:** https://github.com/DLUT-YRH/DSFN

Graph-based optimal seam computation followed by **soft-seam diffusion** — propagates a
confidence-weighted blend region rather than applying a hard ownership transition.
Reparameterisation trick for efficiency. Multi-stage with global depth regularization for
parallax robustness.

*Relevance:* Replaces the current hard Laplacian feather at seam boundaries with a
continuously-smooth confidence blend. Hard-feather artifacts are especially visible on anime's
high-contrast line art at ownership transitions.

---

#### SRStitcher · NeurIPS 2024 · arXiv:2404.14951

Collapses the traditional stitching three-stage pipeline (registration → fusion →
rectangling) into a **single diffusion inpainting pass**. No training or fine-tuning required.
Uses weighted masks to guide the reverse diffusion process over seam and border regions.

*Relevance:* An anime-style diffusion backbone (Illustrious, Anything v5, Pony Diffusion XL)
as the inpainting model would produce anime-consistent seam fusion and border fill without
any stitching-specific training. Eliminates Laplacian blending entirely as a concept.

---

#### RecDiffusion · CVPR 2024 · arXiv:2403.19164

Motion Diffusion Models generate motion fields to transition from irregular borders to a
rectangular intermediate shape. Content Diffusion Models then refine image detail in the
extended border region.

*Relevance:* Directly addresses W10 (irregular border crop). For diagonal-motion panoramas
like test7, extends the black-corner regions to rectangular fill. Applicable as a
post-processing step after Stage 13.

---

### 3.4 Optical Flow as Alignment Tool

---

#### SEA-RAFT · ECCV 2024 Oral · arXiv:2405.14793
**Code:** https://github.com/princeton-vl/SEA-RAFT

Improves RAFT with Mixture of Laplace training loss for robustness to outliers, direct
initial flow regression for faster convergence, and **rigid-motion pretraining** for better
generalisation to pure-translation scenes. 22.9% EPE reduction and 17.8% outlier reduction
vs RAFT on the Spring benchmark.

*Relevance:* **The ideal replacement for ECC (Stage 8).** Rigid-motion pretraining is
specifically valuable for anime pans which are dominated by pure translation. SEA-RAFT
produces confident flow even over flat cel-shaded regions where gradient-based ECC fails,
because it uses learned cost volumes rather than pixel intensity gradients. Compute flow
over the overlap zone only → take mode/median of background-pixel vectors → robust sub-pixel
translation with no divergence risk.

---

#### MambaFlow · arXiv:2503.07046

Replaces RAFT's attention-heavy correlation volume with Mamba state-space layers. Linear
complexity enables processing larger images at the same VRAM budget as RAFT on 1080p.

*Relevance:* When SEA-RAFT approaches VRAM limits on a 4K overlap zone, MambaFlow provides
the same semantic matching at linear O(N) cost.

---

### 3.5 Anime / Cartoon-Specific Methods

---

#### AnimeInterp / AnimeRun · 2021–2024 · arXiv:2104.02495

Segment-guided optical flow for animation: estimates flow per segment (contiguous color
region) separately rather than globally. Segment-level consensus is far more robust on
flat-color anime cells than per-pixel global flow. AnimeRun is a benchmark for optical flow
and segment matching in animation.

*Relevance:* The segment-guided approach directly addresses the matching problem on anime
frames. SAM segments + per-segment centroid matching gives a dense set of translation
hypotheses that outlier-rejection can robustly reduce to a single estimate.

---

#### ToonCrafter · arXiv:2405.17933

Video diffusion model fine-tuned on cartoon/anime content for frame interpolation. Generates
style-consistent intermediate frames between two anime key-frames given a large motion gap.

*Relevance:* For animated foreground characters creating ghosting in the temporal median:
detect animation phases (existing `_cluster_animation_phases`), identify per-phase key
frames, use ToonCrafter to generate a single representative clean cel, composite over the
ghosted region. Eliminates cyclic animation ghosting entirely.

---

#### LinkTo-Anime · arXiv:2506.02733

Ground-truth optical flow dataset for 2D animation derived from 3D model rendering with
anime-style shading. Enables training and benchmarking of flow estimation methods on
anime-specific content.

*Relevance:* Training data for fine-tuning SEA-RAFT specifically on anime frame pairs.
Expected outcome: 30–50% more reliable background correspondences on low-texture anime
cells, improving BA quality downstream.

---

### 3.6 Super-Resolution

---

#### Real-ESRGAN anime_6B / animevideov3
**Code:** https://github.com/xinntao/Real-ESRGAN

`RealESRGAN_x4plus_anime_6B` is trained on anime-specific degradation: JPEG compression
artifacts at colour boundaries, cel-shade gradient loss, line-art thinning at low
resolution. Preserves clean outlines and flat-shading gradients where the photo SR model
over-smooths. Built-in tile-and-stitch for large panoramas. Available via `realesrgan` pip.

*Relevance:* **Directly applicable post-processing step.** Apply 2× (already-sharp
panoramas) or 4× (blurry source tests 2, 3, 19, 20) to the final stitched output. No
training required; pretrained weights cover the full anime degradation distribution.

---

#### SRStitcher (NeurIPS 2024) — see §3.3

Unified diffusion inpainting doubles as an SR mechanism for seam and border regions.

---

### 3.7 Research Summary Table

| Paper | Year/Venue | arXiv | Code | Priority |
|---|---|---|---|---|
| EfficientLoFTR | CVPR 2024 | 2403.04765 | ✓ | P1 — Drop-in |
| LightGlue | ICCV 2023 | 2306.13643 | ✓ | P1 — Sparse fallback |
| ALIKED | IEEE TIM 2023 | 2304.03608 | ✓ | P1 — With LightGlue |
| XFeat | CVPR 2024 | 2404.19174 | ✓ | P2 — CPU fallback |
| RoMa v2 | CVPR 2024 + 2025 | 2511.15706 | ✓ | P2 — Dense last resort |
| JamMa | CVPR 2025 | 2503.03437 | ✓ | P2 — 4K matching |
| EDM | ICCV 2025 | 2503.05122 | ✓ | P3 — Benchmark |
| StabStitch | ECCV 2024 | 2403.06378 | ✓ | P1 — Traj. smooth. |
| StabStitch++ | TPAMI 2025 | 2505.05001 | — | P1 — Midplane |
| VidPanos | SIGGRAPH A. 2024 | 2410.13832 | — | P3 — Generative fill |
| SEA-RAFT | ECCV 2024 Oral | 2405.14793 | ✓ | P1 — ECC replacement |
| MambaFlow | arXiv 2025 | 2503.07046 | — | P3 — 4K flow |
| AnimeInterp | arXiv 2021 | 2104.02495 | ✓ | P2 — Segment match |
| ToonCrafter | arXiv 2024 | 2405.17933 | ✓ | P3 — Ghost fill |
| LinkTo-Anime | arXiv 2025 | 2506.02733 | ✓ | P3 — Finetune data |
| SemanticStitch | Vis. Comp. 2025 | 2511.12084 | ✓ | P2 — Seam routing |
| OBJ-GSP | AAAI 2025 | 2402.12677 | — | P2 — SAM seam |
| DSFN | NeurIPS 2025 | 2510.21396 | ✓ | P2 — Soft seam |
| SRStitcher | NeurIPS 2024 | 2404.14951 | — | P3 — Unified diffusion |
| RecDiffusion | CVPR 2024 | 2403.19164 | — | P2 — Rectangling |
| Real-ESRGAN anime | — | — | ✓ | P1 — SR post-proc. |

---

## 4. Improvement Plan — Tier 0: Diagnostics & Infrastructure

### T0.1 — Wire `_cluster_animation_phases` into `_render_median`

**Problem:** `_cluster_animation_phases` (FFT temporal frequency analysis) exists in
`rendering.py` and correctly identifies cyclically animated pixels. It is computed but
discarded; its output never reaches `_render_median`.

**Fix:** In `_render_median`, call `_cluster_animation_phases` to obtain `anim_mask` and
`phase_groups`. For canvas pixels in `anim_mask`, replace the global temporal median with
the median from only the dominant phase group (the group with the most background pixels —
typically the group where the character is absent from or in the most common pose). For
background pixels, keep the full temporal median as-is.

```python
# In _render_median (rendering.py), after warping all frames:
anim_mask, phase_groups = _cluster_animation_phases(frames, affines, H, W)
if anim_mask is not None and phase_groups:
    dominant_group = max(phase_groups, key=len)
    # For animated pixels: use only dominant-phase frames in median
    for yx in zip(*np.where(anim_mask > 0)):
        ...  # replace global median with per-phase-group median at those pixels
```

**Expected impact:** avg ghosting score 22.17 → 14–16 (−30 to −40%).

---

### T0.2 — Confidence-Weighted Temporal Median

**Problem:** All frames contribute equally to the temporal median regardless of match quality.
Frames aligned via Template Match (weight ≈ 0.55) or Phase Correlation (weight ≈ 0.15–0.25)
carry as much influence as frames aligned via high-confidence LoFTR (weight ≈ 0.90).

**Fix:** Pass `edge_weights: Dict[int, float]` (frame index → BA confidence) into
`_render_median`. In overlap zones dominated by a low-confidence frame, downweight its pixel
contribution using `np.average(stack, weights=frame_weights, axis=0)` instead of
`np.median(stack, axis=0)`.

**Expected impact:** Slight sharpness improvement in tests where template-match fallback was
used (tests 7, 8 — both with ratio > 1.5).

---

### T0.3 — Variable-Step Renderer for High-dy_cv Tests (Fix test16)

**Problem:** test16 has `dy_cv=0.297` (steps range from 86px to 241px). The temporal median
blurs in proportion to overlap area inconsistency — frames with very different overlap widths
create a blurred composite near the boundaries.

**Fix:** Detect high step-size variance (`dy_cv > 0.20`) after BA and switch the renderer for
that test from `median` to `first` (always use the first valid frame per pixel, no blending).
The `first` renderer is already implemented in `rendering.py` (`_render_first`).

```python
# In pipeline.py Stage 10, before _render():
_dy_steps = [abs(float(affines[i][1,2]) - float(affines[i-1][1,2])) for i in range(1,N)]
_dy_cv = np.std(_dy_steps) / max(np.mean(_dy_steps), 1.0)
effective_renderer = 'first' if _dy_cv > 0.20 and self.renderer == 'median' else self.renderer
```

**Expected impact:** test16 sharpness 32.4 → ≥ 38.9 (eliminates the one remaining inversion).

---

### T0.4 — Auto-Activate MFSR for Low-Sharpness Tests

**Problem:** The MFSR module (DCT restoration, PSO/DRL registration, diffusion inpainting) is
disabled by default. Tests 2, 3, 19, 20 produce sharpness 12–16 that the current pipeline
cannot improve without MFSR.

**Fix:** In `pipeline.py` between Stage 10 and Stage 11, estimate the current canvas
sharpness via a fast Laplacian variance probe. If sharpness falls below a threshold (~20.0),
auto-enable the MFSR pass.

```python
# In pipeline.py, after Stage 10 temporal render:
_lap_var = cv2.Laplacian(cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
if _lap_var < 20.0 and not self.mfsr_mode:
    print("[Stitch]   Low sharpness detected; activating MFSR.")
    # run MFSR pass inline
```

**Expected impact:** tests 2, 3, 19, 20 sharpness from 12–16 to 20–28 (MFSR DCT restoration
range), avg sharpness from 33.1 to ~35.

---

### T0.5 — Auto-Trigger Diffusion Inpainting for Coverage Gaps

**Problem:** test7 and any future diagonal-motion test leave black canvas corners (coverage
81.5%). The `mfsr/diffusion_inpaint.py` module exists but is not called when coverage is low.

**Fix:** After Stage 13 crop, check `valid_mask.mean() / 255`. If below 0.95, compute the
gap mask (`gap_mask = valid_mask == 0`) and call the existing inpainting module.

```python
# In pipeline.py after Stage 13:
if float(valid_mask.mean()) / 255.0 < 0.95:
    from .mfsr import inpaint_gaps
    canvas = inpaint_gaps(canvas, gap_mask=(valid_mask == 0).astype(np.uint8) * 255)
```

**Expected impact:** test7 coverage 81.5% → 95%+. Eliminates black corner regions.

---

## 5. Improvement Plan — Tier 1: Matching Engine Upgrade

### T1.1 — Replace LoFTR with EfficientLoFTR

**File:** `backend/src/models/loftr_wrapper.py`

EfficientLoFTR (CVPR 2024, arXiv:2403.04765) is a drop-in replacement. The matching
interface (`pts1, pts2, conf = wrapper.match(img_i, img_j)`) is identical. The internal
change replaces LoFTR's full dense attention with a two-stage correlation layer:

- Stage 1 (coarse): Adaptive span attention over a 4× downsampled feature map
- Stage 2 (fine): Local refinement around coarse matches only

Result: **2.5× faster** at equivalent or higher AUC on HPatches, MegaDepth, ScanNet.

```python
# loftr_wrapper.py — before:
from kornia.feature import LoFTR
self._model = LoFTR(pretrained='outdoor')

# after:
from efficientloftr import EfficientLoFTR
self._model = EfficientLoFTR(config='full')
# Interface: self._model({'image0': ..., 'image1': ...})
# Output keys: 'keypoints0', 'keypoints1', 'confidence' — identical to LoFTR
```

**Expected impact:** matching time per 4K pair: ~12s → ~5s. Total benchmark time: ~35min →
~15min.

---

### T1.2 — Add ALIKED + LightGlue as Sparse Fallback Tier

**File:** `backend/src/models/aliked_wrapper.py` (new) · `matching.py`

When EfficientLoFTR returns < 20 background keypoints (uniform background, very flat scene),
insert an ALIKED + LightGlue attempt before Template Match. ALIKED's deformable sampling
descriptors produce keypoints at anime line-art edges that SIFT/SuperPoint miss. LightGlue
exits early on easy pairs, providing fast matches when the answer is unambiguous.

```python
# In _match_pair (matching.py), new Attempt 1b:
# Attempt 1b: ALIKED + LightGlue (when LoFTR produces < 20 bg pts)
if M is None and aliked_wrapper is not None:
    try:
        pts1, pts2, conf = aliked_wrapper.match(match_img_i, match_img_j)
        if len(pts1) >= 15:
            # apply bg mask filter, compute median translation
            ...
    except Exception:
        pass
```

**Expected impact:** Fewer template-match fallbacks (currently ~15–20% of edges). Improved
BA anchor quality for those edges.

---

### T1.3 — RoMa v2 Dense Warp as Last-Resort Matcher

**File:** `backend/src/models/roma_wrapper.py` (new) · `matching.py`

When LoFTR + ALIKED + Template Match all fail or produce < 10 background correspondences,
use RoMa v2's dense warp. DINOv2 ViT features are style-agnostic and produce useful
correspondences on flat-shaded anime art. Extract the dense warp field over background
pixels, compute trimmed-mean translation.

```python
# In _match_pair, Attempt 4 (before final failure):
if M is None and roma_wrapper is not None:
    try:
        warp = roma_wrapper.match(match_img_i, match_img_j)  # returns (H,W,2) flow
        bg = match_m_i if match_m_i is not None else np.ones(warp.shape[:2], bool)
        dx = float(np.median(warp[bg > 127, 0]))
        dy = float(np.median(warp[bg > 127, 1]))
        if abs(dx) < W * _MAX_DX_DRIFT_RATIO:
            M = np.array([[1,0,dx],[0,1,dy]], np.float32)
            mean_conf = 0.65
    except Exception:
        pass
```

**Expected impact:** Reduces "all methods failed" edges to near zero. Improves coverage on
uniform-background sequences.

---

### T1.4 — Segment-Guided Matching (AnimeInterp Technique)

**File:** `matching.py` · `backend/src/anim/seam_guide.py` (new)

For frames where LoFTR produces < 30 points despite non-trivial motion, segment both frames
using SAM (already allocated in Stage 4) into contiguous color regions. For each matching
segment pair (by colour/position proximity), compute the centroid displacement. Take the
median over all segments as the global translation estimate.

```python
def _segment_guided_match(
    img_i: np.ndarray,
    img_j: np.ndarray,
    sam_masks_i: List[np.ndarray],  # from Stage 4 SAM inference
    sam_masks_j: List[np.ndarray],
) -> Tuple[Optional[np.ndarray], float]:
    """
    Per-segment centroid matching for flat-color anime frames.
    Returns (M_translation, confidence) or (None, 0.0).
    """
    ...
```

**Expected impact:** Increases background keypoint density 2–4× on low-texture tests (tests
2, 19, 20 which have blur making LoFTR sparse). Improves BA solution quality for those tests.

---

### T1.5 — Fix BA Anchor Points for Non-LoFTR Edges

**File:** `matching.py` · `bundle_adjust.py`

**Current problem:** Non-LoFTR edges use 200 uniformly-sampled background points
(`_sample_bg_points`). These synthetic points cluster near the frame center (random sampling
in a rectangle), providing poor spatial distribution and biasing the BA solver.

**Fix 1 — Structured grid sampling:**
Replace `_sample_bg_points(mask, H, W, n=200)` with a 4×4 grid sampler that draws
12–15 points per cell from background pixels. This ensures spatial distribution covering
all quadrants.

**Fix 2 — Reduce synthetic point count:**
Template Match and Phase Correlation edges carry `weight=0.55`. Additionally reduce their
synthetic point count from 200 to 50. This preserves their constraint role while halving
their voting power relative to LoFTR edges (which have real matched pairs).

```python
# In _match_pair, for TM/PC fallback path:
pts_i = _sample_bg_points_grid(m_i, H, W, n=50, grid=(4,4))  # structured, n=50
pts_j = pts_i + M[:2, 2]
```

**Expected impact:** More robust BA solution for tests dominated by template-match edges.
Reduced W7 bias.

---

## 6. Improvement Plan — Tier 2: Sub-pixel Refinement Overhaul

### T2.1 — Replace ECC with SEA-RAFT Flow Refinement

**File:** `backend/src/anim/flow_refine.py` (new) · `pipeline.py` Stage 8

**Root cause of ECC failure:** `cv2.findTransformECC` optimises the correlation between
image intensity maps under the Lucas-Kanade criterion. On anime frames with large uniform
color regions, the image gradient ∇I ≈ 0 → the Hessian of the ECC functional is near-
singular → optimisation diverges or stalls. The 80px drift guard catches this but means
the ECC time (avg 6s/test) produces zero improvement ~30% of the time.

**SEA-RAFT approach:** Compute dense optical flow only in the **overlap zone** between
consecutive warped frames. Since we already have the BA affines, the overlap zone is known
analytically. Run SEA-RAFT on a cropped 512×512 (or 1024×1024) patch from the overlap centre.
Extract all background-pixel flow vectors, compute the trimmed mean (25th–75th percentile)
as the residual correction. Apply if `|correction| < 80px`.

```python
# backend/src/anim/flow_refine.py

def _flow_refine(
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    bg_masks: List[Optional[np.ndarray]],
    raft_model,
) -> List[np.ndarray]:
    """
    Sub-pixel refinement of relative affines via optical flow in overlap zones.

    For each pair (i-1, i):
    1. Compute relative affine: M_rel = affines[i-1] ∘ inv(affines[i])
    2. Warp frame i to frame i-1's coordinate system
    3. Crop to the overlap zone (known from affines)
    4. Run RAFT on the cropped pair → dense flow (u, v)
    5. Median of bg-pixel (u, v) → sub-pixel residual correction
    6. Apply if |correction| < max_drift (80px)
    """
    ...
```

SEA-RAFT advantages over ECC:
- Learned cost volumes: works on flat color regions with no texture gradients
- Rigid-motion pretraining: optimised exactly for pure-translation scenes
- No divergence: RAFT iterates to convergence monotonically
- Overlap-zone cropping: only processes the relevant image region (~512×512 vs full frame)

```python
# In pipeline.py Stage 8:
if self.use_ecc:
    if self._raft is not None:
        affines = _flow_refine(frames, affines, bg_masks, self._raft)
    else:
        affines = _ecc_refine(frames, affines, bg_masks)  # fallback
```

**Expected impact:** Correct sub-pixel refinement on flat-region tests. Eliminates wasted
ECC time (~6s/test) on tests where it currently clamps. Sharpness improvement for tests with
large uniform-color overlap zones.

---

### T2.2 — Fine-Tune SEA-RAFT on LinkTo-Anime (Research Track)

**File:** `backend/models/training/finetune_raft_anime.py` (new)

LinkTo-Anime (arXiv:2506.02733) provides ground-truth optical flow for 2D animation from 3D
model rendering. Fine-tuning SEA-RAFT on this dataset creates an anime-specific checkpoint
optimised for:
- Flat cel-shading gradients
- Hard outline edges at character boundaries
- Animation-phase variation (same scene, different character pose)

Training procedure:
1. Start from SEA-RAFT pretrained weights (rigid-motion pretrain)
2. Fine-tune on LinkTo-Anime at 2× lower learning rate
3. Evaluate on a held-out split of the 22-test suite

Expected outcome: 30–50% more reliable background flow on low-texture anime cells.
Stored as `backend/models/checkpoints/sea_raft_anime.pth`.

---

## 7. Improvement Plan — Tier 3: Rendering & Compositing Upgrades

### T3.1 — Trajectory Smoothness Regularisation in BA (StabStitch)

**File:** `bundle_adjust.py`

StabStitch (ECCV 2024) shows that per-frame spatial optimisation without temporal smoothness
produces micro-jitter in translation trajectories — visible as per-frame tremor at normal
playback speed, and causing subtle blurring in the temporal median renderer.

Add a second-order temporal difference regularisation to the existing LM residuals:

```python
# In bundle_adjust.py residuals(), add:
# Second-order temporal smoothness (StabStitch trajectory regulariser)
reg_traj = 0.1  # λ_stab — tune; 0.1 is a good starting point
for f in range(1, num_frames - 1):
    # τ_{t+1} - 2τ_t + τ_{t-1} → minimise acceleration
    tx_acc = x[f*2 + 2] - 2*x[f*2] + x[(f-1)*2]
    ty_acc = x[f*2 + 3] - 2*x[f*2 + 1] + x[(f-1)*2 + 1]
    res.append(tx_acc * reg_traj)
    res.append(ty_acc * reg_traj)
```

This prevents the translation trajectory from jittering between adjacent frames while still
fitting the match observations. The weight `reg_traj=0.1` allows ~1px/frame² of permitted
acceleration — sufficient for genuine variable-speed pans (test16 dy_cv=0.30) while
smoothing noise-driven jitter.

**Expected impact:** Eliminates warping-shake in output. Smooths temporal median in overlap
zones, potentially improving all sharpness metrics by 1–3 points.

---

### T3.2 — Bidirectional Midplane Projection (StabStitch++)

**File:** `pipeline.py` Stage 9

In the current setup, frame 0 is at identity (`tx=0, ty=0`) and all other frames are offset
from it. For a 14-frame pan with 150px/step, frame 13 is at `ty≈2100px` — maximally
distorted relative to the canvas origin.

StabStitch++ (TPAMI 2025) shows that centering the coordinate system on the **temporal
midplane** (average of all affine translations) distributes distortion symmetrically.

```python
# In pipeline.py Stage 9, after _compute_canvas:
# Shift all affines to midplane (bidirectional projection — StabStitch++)
T_mid_x = float(np.mean([a[0,2] for a in affines]))
T_mid_y = float(np.mean([a[1,2] for a in affines]))
for i in range(N):
    affines[i][0, 2] -= T_mid_x
    affines[i][1, 2] -= T_mid_y
# T_global already absorbs the remaining offset — no canvas size change needed
```

**Expected impact:** Max per-frame warping distance halved for long pans. Reduces distortion
artefacts in 14-frame tests (test10, test13). Conceptually cleaner coordinate frame.

---

### T3.3 — SAM-Based Semantic Seam Routing

**File:** `backend/src/anim/seam_guide.py` (new) · `compositing.py`

**Current problem:** The seam search in `_composite_foreground` finds the minimum-photometric-
difference position in a ±250px window. The minimum-L1 position can still cross a character
outline, producing the most prominent stitching artifact for anime content.

**Solution:** Generate a per-pixel seam cost map where SAM-detected object boundaries have
high cost (seam avoidance) and flat background regions have low cost (seam preference).

```python
# seam_guide.py

def _sam_seam_cost(
    warped_i: np.ndarray,     # warped frame i in canvas coordinates
    warped_j: np.ndarray,     # warped frame j in canvas coordinates
    overlap_zone: Tuple[int, int, int, int],  # (y0, y1, x0, x1)
    sam_predictor,
) -> np.ndarray:
    """
    Returns a (H, W) float32 cost map.
    High cost: inside/near SAM object boundaries (seam avoidance).
    Low cost: flat background regions (seam preference).
    """
    # 1. Run SAM automatic mask generation on warped_i in overlap_zone
    # 2. Compute Sobel gradient of SAM mask boundaries → object edge map
    # 3. Dilate edges by 15px (seam avoidance radius)
    # 4. Cost = 1.0 at dilated edges, 0.0 at flat background
    # 5. Add photometric similarity score from _composite_foreground
    ...
```

The combined energy for boundary placement becomes:
`E_total(y) = E_photometric(y) + λ_sem * E_semantic(y)`

where `λ_sem=5.0` makes semantic cost 5× more expensive than equal photometric cost — strong
seam avoidance without completely overriding photometric guidance.

**Expected impact:** Eliminates seam-through-character artifacts. Measurable improvement in
seam_gradient metric for tests with character-heavy overlap zones.

---

### T3.4 — Soft-Seam Diffusion Blending (DSFN Technique)

**File:** `compositing.py` · `stateless.py`

**Current approach:** `_laplacian_blend` applies a Laplacian pyramid with a fixed-width
feather at the seam. On anime's high-contrast line art, the pyramid decomposition at the seam
level creates a subtle "halving" artifact — fine-scale details from both sides of the seam
are blended at half weight, producing a 1–2px wide ghost of each edge.

**DSFN approach:** Replace the hard feather half-width with a **soft seam confidence field**:

1. Compute the photometric similarity map `S(x,y) = exp(-|warped_i - warped_j| / σ)` over
   the overlap zone
2. Apply anisotropic diffusion to propagate confidence from high-similarity regions into
   neighbouring pixels
3. Use the diffused confidence map as the blend weight: `alpha = S_diffused / (S_i + S_j)`

This produces a spatially adaptive blend that is wide (smooth) in flat background regions
(high similarity → wide blend zone) and narrow (sharp) at object boundaries (low similarity →
sharp cut), exactly the correct behaviour for anime content.

```python
# compositing.py — replace fixed feather with soft diffusion weight:
def _soft_seam_weight(
    warped_i: np.ndarray,
    warped_j: np.ndarray,
    is_bg: Optional[np.ndarray],
    sigma: float = 15.0,
    n_iter: int = 10,
) -> np.ndarray:
    """
    Anisotropic diffusion seam weight. Returns (H,W) float in [0,1].
    """
    diff = np.abs(warped_i.astype(float) - warped_j.astype(float)).mean(axis=2)
    similarity = np.exp(-diff / sigma)
    # Anisotropic diffusion: preserve edges, smooth flat areas
    weight = cv2.GaussianBlur(similarity, (0,0), sigmaX=20)
    return np.clip(weight, 0, 1)
```

**Expected impact:** Eliminates the 1–2px blur artifact at seams on anime line art. Seam
gradient metric improvement of 10–20%.

---

## 8. Improvement Plan — Tier 4: Post-Processing Chain

### T4.1 — Real-ESRGAN anime_6B Post-Processing

**File:** `backend/src/anim/super_res.py` (new) · `pipeline.py` (optional stage)

Add `sr_mode: bool = False` and `sr_scale: int = 2` parameters to `AnimeStitchPipeline`.
When enabled, apply Real-ESRGAN after Stage 13. The `anime_6B` model is trained on
anime-specific degradation (JPEG blocks, cel-shade gradient loss, line-art thinning) and
preserves clean outlines where the photo SR model over-smooths.

```python
# super_res.py

def _upscale_anime(
    img: np.ndarray,
    scale: int = 2,
    model_name: str = "RealESRGAN_x4plus_anime_6B",
    tile_size: int = 512,
    tile_pad: int = 10,
    device: str = "cuda",
) -> np.ndarray:
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                    num_block=6, num_grow_ch=32, scale=4)
    upsampler = RealESRGANer(
        scale=scale, model_path=..., model=model,
        tile=tile_size, tile_pad=tile_pad, device=device,
    )
    output, _ = upsampler.enhance(img, outscale=scale)
    return output
```

`tile_size=512` ensures a 5000×4000 panorama fits in VRAM by processing 512×512 tiles with
10px padding to avoid tiling seams. Install: `pip install realesrgan basicsr`.

**Expected impact:** Output resolution 2–4× source. Most valuable for tests 2, 3, 19, 20
(low sharpness — SR restores detail the median suppressed). Sharpness metric increase of
40–80% on low-sharpness tests; 10–30% on already-sharp tests.

---

### T4.2 — RecDiffusion Border Rectangling

**File:** `backend/src/anim/rectangling.py` (new) · `pipeline.py` (optional final stage)

After Stage 13, irregular panorama edges leave ragged non-rectangular borders. For test7
(diagonal motion, 81.5% coverage), the corners are black triangles. RecDiffusion (CVPR 2024,
arXiv:2403.19164) generates content-consistent fills using:

1. **Motion Diffusion Model:** generates a motion field from irregular boundary → rectangle
2. **Content Diffusion Model:** inpaints image detail in the extended region, conditioned on
   the visible content and the motion-warped prior

For anime content, the Content Diffusion Model should be an anime-style model (Anything v5,
Pony Diffusion XL, Illustrious) to generate style-consistent fills.

```python
# pipeline.py — optional final stage:
if getattr(self, 'rectangling_mode', False):
    from .rectangling import _rectify_borders
    canvas = _rectify_borders(canvas, valid_mask, target_aspect=None)
```

**Expected impact:** Eliminates black corners in test7 (coverage 81.5% → 100%). Extends to
all tests with coverage < 98%.

---

### T4.3 — ToonCrafter Ghost Fill for Animation Phases (Research Track)

**File:** `backend/src/anim/anim_fill.py` (new)

For the remaining ghosting (avg 22.17 after T0.1 phase-clustering), the root cause is
animation cycles that produce multiple distinct character poses within the frame stack.
ToonCrafter (arXiv:2405.17933) can generate intermediate frames between two anime key-frames,
effectively synthesising a single "canonical" cel that represents the animation phase.

Pipeline:
1. `_cluster_animation_phases` → detect animated pixels, get `phase_groups`
2. Per phase group, select the most representative frame (closest to phase centroid)
3. ToonCrafter: interpolate between adjacent phase key-frames → canonical cel
4. Composite the generated cel into the panorama over the ghosted animated region using the
   existing `_composite_foreground` mechanism

```python
# anim_fill.py

def _tooncrafter_ghost_fill(
    canvas: np.ndarray,
    anim_mask: np.ndarray,
    phase_groups: List[List[int]],
    frames: List[np.ndarray],
    affines: List[np.ndarray],
    tooncrafter_model,
) -> np.ndarray:
    ...
```

**Expected impact:** Eliminates cyclic animation ghosting entirely. avg ghosting score from
~14 (after T0.1) to ~8–10.

---

## 9. Improvement Plan — Tier 5: Architecture-Level Improvements

### T5.1 — RoMa v2 as Primary Warp Engine (Long-Term)

Replace the LoFTR→BA→ECC chain with a RoMa v2 dense warp primary path:

```
Current:  LoFTR matching → edge filter → BA (LM) → ECC refinement
Proposed: RoMa v2 dense warp → RANSAC/trimmed-mean translation fit
```

Benefits:
- Works on flat anime regions (DINOv2 features, style-agnostic)
- Per-pixel confidence maps → direct confidence weighting for rendering
- No edge filtering required (no skip-edge graph, no direction consensus)
- No BA required for adjacent pairs (warp is already a global estimate)

Risk:
- Slower than EfficientLoFTR (DINOv2 ViT forward pass)
- Cannot exploit skip-pair edges (only adjacent pairs)
- May over-smooth for sub-pixel precision

**Hybrid approach:** Use EfficientLoFTR as primary, RoMa v2 only for pairs with < 10
background LoFTR points. Already covered as T1.3 above.

---

### T5.2 — Per-Segment Photometric Correction

**File:** `pipeline.py` Stage 4.5

The current Stage 4.5 applies a single per-frame scalar gain to the entire frame. Anime cel
shading assigns different exposure handling to different color regions (character skin, costume,
background), meaning a single gain computed from the full background mask is a poor approximation.

Replace with per-segment photometric correction:

1. At Stage 4, run SAM automatic mask generation on each frame → `sam_segments`
2. At Stage 4.5, for each background segment (segments that overlap with `bg_mask > 127`),
   compute per-segment gain relative to the global reference
3. Apply per-segment gains as a spatially-varying gain map

```python
# pipeline.py Stage 4.5 (extended):
for _i in range(N):
    _gain_map = np.ones(frames[_i].shape[:2], dtype=np.float32)
    for _seg in sam_segments[_i]:
        _seg_bg = _seg & (bg_masks[_i] > 127)
        if _seg_bg.sum() < 500:
            continue
        _seg_mean = frames[_i][_seg_bg].astype(np.float32).mean(axis=0)
        _ref_mean_for_seg = ...  # reference segment matched by colour proximity
        _gain = np.clip(_ref_mean_for_seg / np.maximum(_seg_mean, 1.0), 0.85, 1.15)
        _gain_map[_seg] = _gain.mean()
    frames[_i] = np.clip(
        frames[_i].astype(np.float32) * _gain_map[..., None], 0, 255
    ).astype(np.uint8)
```

**Expected impact:** Eliminates "colour bleed" at ownership boundaries where adjacent frames
have slightly different colour temperature per segment. Seam gradient improvement.

---

### T5.3 — JamMa for 4K Processing

**File:** `backend/src/models/jamma_wrapper.py` (new)

For 4K source frames (H×W ≥ 3840×2160), the coarse-stage sequence length in EfficientLoFTR
remains large. JamMa (CVPR 2025, arXiv:2503.03437) replaces O(N²) attention with O(N) Mamba
scans. Add a `use_jamma: bool` flag that activates JamMa when the source frame resolution
exceeds a threshold:

```python
# In AnimeStitchPipeline.__init__:
self.use_jamma = kwargs.get('use_jamma', False)

# In pipeline.py Stage 5-6:
if self.use_jamma and H * W > 3000 * 2000:
    # swap to JamMa wrapper
    loftr_wrapper = self._jamma
else:
    loftr_wrapper = self._loftr
```

**Expected impact:** 4K matching time from ~5s/pair (EfficientLoFTR) to ~2s/pair (JamMa).
No quality degradation expected (JamMa benchmarks match EfficientLoFTR on standard datasets).

---

### T5.4 — Dedicated Anime EfficientLoFTR Fine-Tuning

**File:** `backend/models/training/finetune_eloftr_anime.py` (new)

Using the LinkTo-Anime dataset for flow ground truth, generate synthetic anime frame pairs
(via controlled translation offsets) and fine-tune EfficientLoFTR on:
- Pairs with > 50% flat-color pixels
- Pairs with strong outline artifacts
- Pairs with animation-phase variation (same background, different character pose)

Expected outcome: 30–50% more LoFTR background keypoints on anime frames, reducing reliance
on Template Match and Phase Correlation fallbacks from ~15–20% of edges to < 5%.

---

## 10. Implementation Roadmap & Expected Impact

### Phase 1 — Quick Wins (1–3 days each, low risk)

| # | Task | File(s) | Weakness | Est. Effort |
|---|---|---|---|---|
| **P1.1** | Wire `_cluster_animation_phases` into `_render_median` | `rendering.py` | W3 ghosting | 1 day |
| **P1.2** | Variable-step `renderer='first'` for high-dy_cv | `pipeline.py` Stage 10 | W2 test16 | 0.5 days |
| **P1.3** | Confidence-weighted temporal median | `rendering.py` | W3 ghosting | 1 day |
| **P1.4** | Replace LoFTR → EfficientLoFTR | `models/loftr_wrapper.py` | W6 speed | 1 day |
| **P1.5** | Structured grid sampling for non-LoFTR edges | `matching.py` | W7 BA quality | 0.5 days |
| **P1.6** | Trajectory smoothness in BA (StabStitch) | `bundle_adjust.py` | warp jitter | 1 day |
| **P1.7** | Auto-activate MFSR at sharpness < 20 | `pipeline.py` Stage 10.5 | W1 blurry tests | 0.5 days |
| **P1.8** | Auto-trigger diffusion inpainting at coverage < 0.95 | `pipeline.py` Stage 13 | W4 test7 gaps | 0.5 days |
| **P1.9** | Bidirectional midplane projection | `pipeline.py` Stage 9 | long-pan distortion | 0.5 days |

### Phase 2 — Core Quality Upgrades (3–7 days each, medium risk)

| # | Task | File(s) | Weakness | Est. Effort |
|---|---|---|---|---|
| **P2.1** | SEA-RAFT replacing ECC (Stage 8) | New `flow_refine.py` | W5 flat regions | 4 days |
| **P2.2** | Real-ESRGAN anime_6B post-processing | New `super_res.py` | W9 resolution | 2 days |
| **P2.3** | ALIKED + LightGlue sparse fallback tier | `matching.py` + new wrapper | W6 coverage | 3 days |
| **P2.4** | SAM-based semantic seam routing | New `seam_guide.py` | W8 character seams | 4 days |
| **P2.5** | Soft-seam diffusion blending (DSFN) | `compositing.py` | seam artifacts | 3 days |
| **P2.6** | Per-segment photometric correction | `pipeline.py` Stage 4.5 | colour bleed | 3 days |
| **P2.7** | RecDiffusion border rectangling | New `rectangling.py` | W10 borders | 5 days |
| **P2.8** | RoMa v2 dense-warp last-resort matcher | New `models/roma_wrapper.py` | W7 hard pairs | 3 days |
| **P2.9** | Segment-guided matching (AnimeInterp) | `matching.py` | low-texture tests | 3 days |

### Phase 3 — Research-Grade (1–2 weeks each)

| # | Task | Notes |
|---|---|---|
| **P3.1** | StabStitch++ full bidirectional pipeline | Full architecture refactor |
| **P3.2** | ToonCrafter ghost fill for animation phases | ToonCrafter model integration |
| **P3.3** | SRStitcher unified diffusion fusion | Anime diffusion model backend |
| **P3.4** | Fine-tune SEA-RAFT on LinkTo-Anime | Training infrastructure required |
| **P3.5** | JamMa for 4K batch processing | JamMa package + Mamba install |
| **P3.6** | Fine-tune EfficientLoFTR on anime pairs | Synthetic training data pipeline |

---

### Expected Impact Summary

| Metric | Current | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|---|---|---|---|---|
| avg sharpness | 33.14 | 35–37 | 42–48 | 55–65 |
| avg ghosting | 22.17 | 14–16 | 10–12 | 7–9 |
| test16 inversion | SCANS=38.9>ASP=32.4 | **Eliminated** | — | — |
| test7 coverage | 81.5% | 95%+ | 100% | 100% |
| tests with visible char. seam | ~4–6 | ~4–6 | **0** | 0 |
| output resolution | 1× source | 1× source | **2–4× source** | 4× source |
| matching time (4K pair) | ~12s | ~5s | ~3s | ~1.5s |
| seam gradient | 4.73 | 4.8 | **5.5–6.5** | 7–8 |

### Recommended Immediate Priority

The single most impactful change with the lowest risk is **P1.1 (phase-aware rendering)**
— wiring the existing `_cluster_animation_phases` output into `_render_median`. The code
already detects animation phases correctly; it just discards the result. This directly
attacks the highest-volume quality issue (avg ghosting 22.17) with zero dependency on
external models or new infrastructure.

The most transformative combination for Phase 1 is:
**P1.4 (EfficientLoFTR) + P1.2 (variable-step renderer) + P1.6 (trajectory smoothness) +
P1.7 (auto-MFSR) + P1.8 (auto-inpaint)** — five targeted fixes that collectively address
speed, the test16 inversion, warp jitter, and the two coverage/sharpness gaps, each in < 1
day of implementation.
