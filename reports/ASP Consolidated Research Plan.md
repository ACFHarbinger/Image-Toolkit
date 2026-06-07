# ASP Consolidated Research Plan
### Anime Stitch Pipeline — Algorithmic Frontiers, Implementation Roadmap, and Quality Framework

> **Synthesis of all five ASP research documents (2026-06-07). Primary basis: *Anime Stitch Pipeline Research Plan.md*.  
> Supplemented by: *ML Research*, *Upgrade Research*, *Research Survey*, *HITL & Morphological Integration*.**

---

## 1. Executive Summary

The Anime Stitch Pipeline (ASP) assembles character panoramas from sequential frames of animated pan shots. Animation's two domain-specific properties — **flat textureless cel-shading** (defeats standard optical flow) and **discrete pose updates "on twos/threes"** (creates temporal discontinuities) — cause complete failure of all photorealistic CV tools.

**Current benchmark (96-test corpus, 55 with ground truth):**

| Outcome | Proportion |
|---|---|
| ASP better than simple stitch | 14.5% |
| Comparable | 43.6% |
| Simple stitch better | 41.8% |
| Fallback to SCANS (render gate fired) | 40.6% (39/96) |
| Validation failure (BA outlier dominance) | 13.5% (13/96) |

**The four highest-leverage upgrades (ordered by expected impact):**
1. Pose-consistent frame selection — replaces phase-correlation heuristic with background-subtracted Overmix-style cel clustering + DP optimizer
2. GNC robust bundle adjustment — replaces static residual pruning with Geman–McClure surrogate GNC
3. SAM-2 video segmentation — replaces per-frame BiRefNet with temporally consistent video predictor
4. AnimeInterp SGM + LinkTo-Anime-finetuned SEA-RAFT — solves aperture problem on flat fills

**The single deepest architectural insight** (from the Research Survey): anime stitching is not a stitching problem with motion noise. It is a **frame-selection-conditioned multi-cel reconstruction problem**. Re-architecting the frame selector is likely to do more for the 40.6% fallback rate than any single optical-flow upgrade.

---

## 2. Current 13-Stage Pipeline Architecture

| Stage | Module | Algorithmic Function |
|---|---|---|
| 1 | Trim & Detect | Canvas initialization, letterbox detection, dark-border trim |
| 2 | Width Normalization | Lanczos-4 resize to unified coordinate space |
| 3 | Photometric Correction | BaSiC flat-field correction for luminance gradients |
| 4 | Semantic Masking | BiRefNet foreground isolation (pixel-level) |
| 5 | Background Normalization | Scalar photometric adjustment on BG-only pixels |
| 6 | Matching & Filtering | EfficientLoFTR + ALIKED+LightGlue + Phase Correlation + RoMa; spatial dedup gate |
| 7 | Bundle Adjustment | Translation-only Levenberg-Marquardt with GNC Cauchy loss (S6) + adaptive f_scale (S30) |
| 8 | Validation Gate | Min gap, aspect ratio, off-diagonal rotation checks; retry chain → PANORAMA fallback (S31) → SCANS |
| 9 | Sub-pixel Refinement | SEA-RAFT + ECC maximization |
| 10 | Foreground Registration | RAFT flow on seam-band crop + ARAP regularization + symmetric midpoint warp |
| 11 | Canvas Construction | Bidirectional midplane projection |
| 12 | Background Assembly | Foreground-excluded temporal median |
| 13 | Compositing & Blending | Laplacian blend + DSFN adaptive ramp + DP seam + Poisson (S21) |

**Stage 2.1 (frame selection) is the primary failure point**: the smart selector uses raw spatial displacement with phase correlation, which conflates character animation with camera panning. A character occupying 60%+ of screen space causes the selector to accept frames with incompatible poses, mathematically guaranteeing a Stage 9 Render Quality Gate failure.

---

## 3. Failure Mode Taxonomy

### Category A — Render Quality Gate (40.6% of corpus)
**Trigger:** seam coherence > 35 or inter-strip color diff > 25 luminance units  
**Root cause:** phase correlation measures whole-frame displacement. Character animation inflates the displacement estimate, selecting frames with incompatible poses (arms up vs. arms down). Subsequent ARAP cannot bridge 300–800 ms morphological gaps.  
**Fix vector:** § 5.1 Pose-consistent frame selection.

### Category B — Bundle Adjustment Outlier Dominance (13.5% of corpus)
**Trigger:** affine validation dimension ratio > 2× (e.g., 11.1× in test13, 4.2× in test64)  
**Root cause:** a single erroneous LoFTR match stays within the 3.0× median residual threshold, corrupting the median itself and hijacking the LM solver.  
**Fix vector:** § 5.5 GNC-TLS bundle adjustment.

### Category C1 — Seam Cutting Character (subset of successful renders)
**Trigger:** seam gradient > 12 on the seam visibility metric  
**Root cause:** DP seam optimization uses only local cost; foreground BiRefNet penalty insufficient when character spans full strip width.  
**Fix vector:** § 5.8 OBJ-GSP + SemanticStitch hard barrier.

### Category C2 — SSIM Remaining Gap (structural ceiling)
**Observation:** aligned SSIM > raw SSIM by 0.04–0.05 on average (framing gap). Remaining gap 0.17–0.25 is driven by animation timing — the ASP selects a different pose than the studio GT composite.  
**Fix vector:** § 5.1 Pose-consistent selection + § 5.9 ToonCrafter generative seam synthesis.

---

## 4. Priority Roadmap

### Phase 1 — Highest Impact, Lowest Complexity (implement first)

| # | Item | Section | Complexity | Expected Impact |
|---|---|---|---|---|
| 1 | Pose-consistent frame selection (Overmix-style cel clustering + DP) | 5.1 | Medium | **Large** — directly fixes Category A |
| 2 | GNC-TLS bundle adjustment (replace static residual pruning) | 5.5 | Low (~100 lines) | **Medium** — directly fixes Category B |
| 3 | Median background + JPEG-aware iterative refinement | 5.1 | Low | Medium |
| 4 | SAM-2 as BiRefNet replacement (video predictor, one bbox prompt) | 5.2 | Low | Medium — temporal mask consistency |

**Decision threshold:** if Phase 1 raises ASP-beats-naive from 14.5% → ≥35% and lowers fallback from 40.6% → ≤25%, Phase 2 is justified.

### Phase 2 — Medium Complexity, Large Impact

| # | Item | Section | Complexity | Expected Impact |
|---|---|---|---|---|
| 5 | AnimeInterp SGM + LinkTo-Anime-finetuned SEA-RAFT | 5.3 | Medium | **Large** — solves aperture problem in flat regions |
| 6 | OBJ-GSP + SemanticStitch seam routing hard barrier | 5.8 | Low (cost term + SAM-2) | **Medium-Large** — fixes character-cutting seams |
| 7 | Sýkora 2009 full ARAP + DeepLSD collinearity energy | 5.4 | Medium | Medium — costume edges, prop outlines |
| 8 | ProPainter background completion after foreground masking | 5.9 | Medium | Medium — improves BG quality, reduces median bleeding |

### Phase 3 — High Complexity, Fallback-Only

| # | Item | Section | Complexity | Expected Impact |
|---|---|---|---|---|
| 9 | ToonCrafter midpoint synthesis for unresolvable pose gaps | 5.9 | Medium-High | **Large on fallback subset** — generative completion |
| 10 | StabStitch++ bidirectional midplane + 2D trajectory smoothing | 5.7 | Medium | **Large for diagonal/horizontal scrolls** |

**If after Phase 1 failures concentrate in "alignment crashes":** try EDM as drop-in LoFTR replacement (§ 5.6) before deeper changes.  
**If after Phase 2 failures concentrate in "character moves between strips":** Phase 3K (ToonCrafter) becomes critical.  
**If after Phase 2 failures concentrate in "diagonal pan failed":** Phase 3G+N (StabStitch++) is critical.

---

## 5. Detailed Module Specifications

### 5.1 Frame Selection and Hold Detection

**Problem:** The current `_smart_select_frames()` uses raw phase correlation displacement ≥ 50px + direction consistency + a "high-animation/low-movement" filter. Phase correlation conflates character animation with camera panning, producing a "temporal collage" rather than a spatially coherent panorama.

#### 5.1.1 Overmix Animated Aligner (Practitioner Baseline)
Overmix (spillerrec, GPL-3.0) — closest existing analogue to ASP. Key findings:
- Brute-force SAD/SSD translational search over bounded window (no SIFT/SURF)
- "Animated aligner": computes pixel-difference between consecutive aligned frames. Static spans → low diff; animation transitions → spikes. Threshold line segments frames into clusters (one per drawn cel)
- **Sub-pixel precision**: integer-upscaling images to 4× before alignment, ordinary pixel-based alignment, then divide result
- **Median render**: per-pixel median across all aligned frames — robust to outlier-pixel artifacts
- **Jpeg-aware iterative render**: starts from average, repeatedly DCTs the estimate within each input's 8×8 grid and replaces quantised coefficients matching the observation — recovers detail MPEG compression destroys

**ASP improvement on Overmix approach:**
1. Compute frame-difference on **background-subtracted** images (using SAM-2 foreground mask), so character animation doesn't pollute the camera-motion signal
2. Use **both** signals: background-difference for camera-motion estimation; foreground-difference clustering for pose-consistent selection

#### 5.1.2 DINOv2 + SigLIP Submodular Frame Selection
Addresses animation "holds" and context saturation under a strict frame budget `k`:
- **Query Relevance Space (SigLIP)**: how strongly a frame aligns with target action or prompt
- **Semantic Representativeness Space (DINOv2)**: `ℓ²`-normalized embeddings for facility-location coverage objective — adding a frame is rewarded only if its embedding occupies a different latent region
- Minimises a monotone submodular surrogate: `L = L_SigLIP_relevance + L_DINOv2_coverage`
- Greedy maximisation guarantees `(1 − 1/e)` approximation factor
- Proven superior to uniform sampling on MLVU and LongVideoBench

**Already partially implemented in ASP (S8 DINOv2 frame selection). Enable with `ASP_POSE_WINDOW_PX=80`.**

#### 5.1.3 Pose-Consistent DP Frame Selector
Multi-objective selector combining three signals:
1. **Camera-motion magnitude**: phase correlation on background-masked image (foreground subtracted before cross-correlation)
2. **Pose-consistency score**: ViTPose-Base finetuned on AnimePose data, or Sýkora Push residual against a reference frame as a pose-distance proxy; cluster frames so all selected belong to the same cluster
3. **Foreground-crop SSIM / mutual information**: between adjacent candidate frames — high SSIM = same animation state

**Selector solves:** for each strip column, pick the frame from a candidate window that maximises `(foreground-SSIM with neighbouring selections) − λ · (background-displacement penalty)`. This is a shortest-path problem on a DAG (frame × column → cost), solvable in O(NC·k²) by standard DP.

---

### 5.2 Foreground Segmentation — SAM-2

**Current:** BiRefNet per-frame — no temporal consistency, mask jitter creates seam-pixel inconsistencies.

**Upgrade:** SAM-2 video predictor (Meta AI, Ravi et al. arXiv:2408.00714)
- Streaming-memory transformer that propagates a session memory across video frames
- Hiera-B+ runs at **43.8 FPS on A100**; Hiera-L at 30.2 FPS
- Single bounding box / point prompt on frame 1 propagates a consistent mask across the entire pan
- Trained on SA-V (51K diverse videos, 643K spatio-temporal masklets)
- On clean cel-shaded characters: excellent (strong outline priors)
- On translucent effects (hair tips, magical glows): use SAM-2 ∪ BiRefNet union mask as fallback

**Integration:** `replace BiRefNet with SAM-2 video predictor, prompted with a bbox from BiRefNet → bbox or user click. Use SAM-2 masks for both foreground/background decoupling AND seam-cost barrier in graph-cut.`

---

### 5.3 Optical Flow and the Aperture Problem

**Problem:** Cel-shaded animation has zero-gradient interiors. Standard networks (RAFT, PWC-Net, FlowFormer) hallucinate chaotic vectors inside uniform color regions.

#### 5.3.1 AnimeInterp Segment-Guided Matching (SGM)
(Li Siyao et al., CVPR 2021, arXiv:2104.02495; code: `github.com/lisiyao21/AnimeInterp`, SGM in `models/sgm.py`, pure PyTorch)

**Algorithm:**
1. **Segment** each frame via SLIC-style super-pixelation gated by Laplacian-of-Gaussian contour detector → every closed near-uniform-colour region becomes one segment
2. **Describe** each segment: colour histogram + centroid + area + deep CNN feature (VGG-19 pooled at `relu1_2, relu2_2, relu3_4, relu4_4`) → `d`-dimensional feature vector
3. **Globally match** segments across frames via Hungarian assignment minimising L2 cost in feature space; one-to-many fallback for region splits
4. **Propagate** piece-wise flow: every pixel inside a source segment gets the centroid-to-centroid displacement of its match
5. **Matching Degree Matrix** `M = α·Affinity + β·DistancePenalty + γ·SizePenalty` (empirical: `β=0.25`, `γ=0.25`)

**ASP integration:** Between LoFTR and RAFT, run SGM on the SAM-2 foreground crop pair. Use SGM output as warm-start initialisation for SEA-RAFT (SEA-RAFT supports flow initialisation natively). For ARAP control points in flat regions, use SGM segment-centroid displacement directly.

**Note:** SGM segmentation is sensitive to anti-aliasing — disable chroma upscaling before segmentation, or use LineArtDetector pre-process.

**Complexity:** Medium. **Expected impact:** Large on aperture failures — eliminates systematic flow-zero failures on skin/hair regions.

#### 5.3.2 LinkTo-Anime SEA-RAFT Fine-tuning
(Feng et al., arXiv:2506.02733, 2025 — Macau UST/CUHK)

- 22+ open-source 3D character models with Mixamo skeletons, toon-shaded (flat fills + ink contours)
- Ground-truth pixel-perfect forward/backward optical flow, occlusion masks, and skeleton annotations
- 395 sequences; 24,230 training frames, 720 val, 4,320 test; both coloured and line-drawing variants

**Recipe:** Take SEA-RAFT-L checkpoint (Sintel+FlyingThings); fine-tune on LinkTo-Anime training split for ~50k steps; freeze feature pyramid for first 10k steps to prevent catastrophic forgetting. Evaluate on LinkTo-Anime test set EPE + ATD-12K validation + held-out ASP corpus.

**Note:** LinkTo-Anime is 3D-rendered, not hand-drawn. Cross-validate on ATD-12K (real animation studio frames) to catch domain gap. Combine: pretrain on LinkTo-Anime (largest, geometry-correct), fine-tune on ATD-12K (real animation distribution).

#### 5.3.3 SAIN — Sketch-Aware Interpolation Network
For uncolored line art (before colorization stage):
- Multi-stream U-Transformer with integrated self-attention + cross-attention
- Region-level, stroke-level, and pixel-level guidance
- Trained on STD-12K (30 sketch animation series)
- Use when ASP must interpolate raw line-art before the colorization stage

---

### 5.4 ARAP Foreground Registration

**Current state:** ARAP is implemented in ASP. Sýkora 2009 Push+Regularise algorithm with RAFT flow.

#### 5.4.1 Full Sýkora 2009 Algorithm
(NPAR '09, DOI:10.1145/1572614.1572619)

1. **Embed** source image in coarse square lattice (~16px squares), respecting foreground articulation
2. **Push phase:** for every lattice point, find `t* = argmin_{t ∈ M} Σ_{p ∈ N} |S(p+t) − T(p)|`. `|N|=16px`, `|M|=48px`. No shape constraint — points move independently.
3. **Regularise phase:** per lattice square, compute optimal 2D rigid transform via Schaefer 2006 closed form. Each lattice point replaced by the centroid of its transformed instances across all incident squares. Iterate 5–20 times.
4. **Stopping criterion:** monitor `d_avg = (1/|P|) Σ ||pᵢ − qᵢ||` (NOT SAD — can plateau spuriously). Stop when `d_avg` unchanged over 20 iterations.

**Speed-up:** Replace brute-force block matching in Push with PatchMatch (Hao et al. 2019, 10–50× speed-up at comparable quality).

#### 5.4.2 DeepLSD Collinearity Extension (Novel)
**NOTE: This term is NOT in the original Sýkora 2009 paper — it must be added as a novel extension.**

- Detect line segments via DeepLSD (Pautrat et al., ECCV 2022, MIT-licensed, robust on anime ink lines) on both source and target
- Match line segment pairs by descriptor + endpoint geometry
- For each matched pair `(ℓ_src, ℓ_tgt)` with `ℓ_tgt` having normal `n` and offset `d`, add penalty to the per-square Regularise step:
  `λ_lsd · Σ_{pᵢ ∈ ℓ_src} (n · (R* pᵢ + t*) − d)²`
- Use `λ_lsd ≈ 0.1 × rigidity weight`
- **Expected impact:** moderate — mainly helps on costume edges and prop outlines with strong ink lines but flat fills

---

### 5.5 Robust Bundle Adjustment

**Current state:** GNC Cauchy loss with adaptive f_scale (S30). Already well-improved. Further upgrade: GNC-TLS.

#### 5.5.1 GNC-TLS / Geman–McClure (Full Implementation)
(Yang et al., IEEE RA-L 2020, arXiv:1909.08605 — canonical GNC-TLS reference)

**Mechanism:** Parameterise surrogate `ρ_μ(rᵢ)` starting (μ→∞) as convex quadratic, annealed (μ↓) toward Truncated Least Squares `ρ(r) = min(r², c²)` or Geman-McClure `ρ(r) = r²/(r² + c²)`.

For ASP translation-only BA:
1. Initialise `μ₀` such that `2μ₀c² ≥ max(rᵢ²)` — initial problem is effectively convex
2. For each outer iteration: one LM step on the weighted problem `Σ wᵢⱼ rᵢⱼ²`
3. Update `wᵢⱼ` in closed form (Geman-McClure: `wᵢ = (μ·c² / (μ·c² + rᵢ²))²`)
4. Divide μ by 1.4; terminate when `‖Δx‖ < tol` or `μ < μ_min`
5. Set `c ≈ 3σ` (Yang et al. recommend `c = 1.0` for normalised pixel coords with `σ ≈ 0.3px`)

**Advantages over current Cauchy loss:** continuation schedule explicitly avoids local minima from bad initialisation. Tolerates 70–80% outliers vs. RANSAC-style 50%.

**Reference implementation:** TEASER++ (`github.com/MIT-SPARK/TEASER-plusplus`) ships a GNC solver in C++/Python.

#### 5.5.2 Adaptive GNC (AGNC)
(Cho et al. 2023, arXiv:2308.11444; Peng et al. 2023 riSAM, arXiv:2310.06765)

Extends GNC by **dynamically adjusting the annealing schedule** based on continuous monitoring of the Hessian positive definiteness and multi-task sampling of multiple annealing choices per iteration. Prevents premature collapse to local minima. Empirical claim: maintains perfect stability at 99% outlier rate.

---

### 5.6 Background Separation and Camera Modeling

#### 5.6.1 OmnimatteZero — Training-Free Layer Decomposition
(arXiv:2503.18033, SIGGRAPH Asia 2025)
- Training-free generative approach at **0.04 s/frame on A100**
- Encodes original video + clean background into diffusion latent space; computes latent difference to isolate foreground; self-attention maps inpaint associated effects (shadows, reflections)
- Use to strip animated character + shadow from a complex pan-shot, leaving pristine background for global motion estimation

#### 5.6.2 CamFlow — Hybrid Motion Basis Decomposition
(Li et al., ICCV 2025, arXiv:2507.22480)
- Replaces single-layer homography with a deep Motion Estimation Transformer (MET)
- **Physical Motion Bases:** 12 polynomial bases from Taylor expansion of 3D→2D camera projection (translation, rotation, scaling, affine)
- **Stochastic Motion Bases:** `k` random matrices via Gaussian distribution, SVD for orthogonal principal components — absorbs multi-plane depth parallax
- Hybrid Laplace distribution loss for training stability
- Evaluated on GHOF-Cam benchmark (SAM-masked dynamic objects)

#### 5.6.3 JamMa / EDM — Improved Feature Matching
**EDM** (Li et al., ICCV 2025 Highlight, arXiv:2503.05122): deeper CNN backbone + Correlation Injection Module + bidirectional axis-based sub-pixel regression head. Drop-in LoFTR replacement.  
**JamMa** (Lu & Du, CVPR 2025, arXiv:2503.03437): Joint Mamba state-space model replacing LoFTR's quadratic Transformer; <50% params and FLOPs.  
**Recommendation:** try EDM first (bidirectional sub-pixel head directly benefits translation-only BA).

#### 5.6.4 SVD Rank Analysis + Panoramic RPCA — Classical Trajectory-Based Separation
(Zhang et al., Stanford, cs.stanford.edu/~haotianz/background/background.pdf; arXiv:1712.06229)

Classical mathematical alternative to CamFlow for fg/bg separation — no deep model required.

**SVD Rank Analysis:**
- Video is divided into overlapping local temporal windows. For any rigid-motion object with `m` feature trajectories across a temporal window of width `n`, positions form a trajectory matrix `T` of shape `(2m × n)`.
- Background trajectory matrices are low-rank (rank < 4) because rigid camera motion is governed by the affine projection equation. Foreground trajectory matrices have higher rank due to combined camera + character articulation motion.
- SVD of `T` → count singular values above threshold `ε` → background features have rank < 4; character features have rank ≥ 4.
- A directed graph of feature clusters (nodes = local clusters, edges weighted by shared features + joint matrix rank) finds the minimal-rank path = background camera motion.

**Panoramic RPCA (OptShrink):**
- Models registered video as sum of three matrices: low-rank `L` (background), smooth total-variation `S` (dynamic foreground), sparse `E` (outliers/noise).
- OptShrink estimator computes optimal shrinkage of singular values for non-square, low-rank recovery. More accurate than standard nuclear-norm minimization.
- Applicable when BiRefNet fails on complex scenes: provides mathematically guaranteed background estimation even without semantic segmentation.

**ASP integration:** Run SVD rank analysis on the selected frame pairs before phase correlation. Background-only features (rank < 4 clusters) are passed to LoFTR for alignment; foreground features are flagged for ARAP registration. Provides a fallback when BiRefNet masks are unreliable (masked regions unclear, transparent overlays).

**Priority:** Lower than CamFlow (§5.6.2) and SAM-2 (§5.2) — use only when BiRefNet fails AND CamFlow is unavailable. Zero new model weights; pure classical CV.

---

### 5.7 Canvas Construction and Stitching

#### 5.7.1 StabStitch++ — Bidirectional Virtual Midplane
(Nie et al., TPAMI 2025, arXiv:2505.05001; code: `github.com/nie-lang/StabStitch2`)

- **Virtual midplane bidirectional warp:** rather than warp A onto B, project both onto a virtual middle plane via differentiable bidirectional decomposition — evenly distributes projective distortion
- **Warp smoothing model:** L1-trend-filter trajectory across all strip seams simultaneously — `‖∇²T‖₁` regularisation (anime pans are piecewise-constant velocity)
- Processes multi-video stitching online at 28.3 FPS (RTX 4090 on StabStitch-D)

**ASP integration:**
1. Reformulate BA to estimate a single 2D translation trajectory `T(t)` across all input frames; derive per-strip-pair warps from differences along `T(t)`
2. Regularise with `‖∇²T‖₁`
3. Bidirectional midplane projection eliminates asymmetric distortion of current "warp one strip to neighbour" approach

#### 5.7.2 Horizontal/Diagonal Scroll Support
**Current limitation:** `_compute_canvas` uses only ty; tx drift is discarded.

**Fix:**
1. Full 2D phase correlation for displacement estimation (not projected onto vertical axis)
2. Generalise BA to estimate (tx, ty) per frame
3. Orient strip seams perpendicular to estimated camera-motion direction per pair
4. Detect scroll axis: if `ty_range < 0.1 × tx_range`, apply horizontal strip mode or fall back to SCANS
5. For rotation/scale: augment LM state with global rotation per frame, strong prior toward zero

#### 5.7.3 RDIStitcher / SRStitcher — Diffusion-Based Fusion
(RDIStitcher arXiv:2411.10309; SRStitcher arXiv:2404.14951/NeurIPS 2024)

- **RDIStitcher:** reformulates the entire stitch as a generative inpainting problem using T2I diffusion. Self-supervised on pseudo-stitched images. Aggressive modification in the overlap zone eliminates parallax breaks.
- **SRStitcher:** Weight Mask Guided Reverse Process (WMGRP) — weighted initial mask preserves original warped structure; weighted inpainting mask controls generative modification intensity across diffusion timesteps
- **NOTE:** Not directly applicable to anime without retraining — diffusion priors tuned to natural-photography parallax. Adopt selectively: use the loss formulation idea (`L_align + λ·L_distortion`) to regularise ASP's foreground warp; use generative prior **only at the seam region** with ToonCrafter as the generator instead of Stable Diffusion.

#### 5.7.4 UDIS++ and UDTATIS
- **UDIS++** (Nie et al., ICCV 2023): joint unsupervised warp (mesh-based local deformation) + composition
- **UDTATIS:** integrates EfficientLOFTR + diffusion models in composition stage for texture-barren imagery
- Same domain-mismatch caveat as RDIStitcher — borrow the joint alignment + distortion loss formulation, not the whole model

---

### 5.8 Seam Routing — Semantic Integrity

#### 5.8.1 OBJ-GSP — Triangular Mesh Shape Preservation
(Cai & Yang, AAAI 2025, arXiv:2402.12677; code: `github.com/RussRobin/OBJ-GSP`)
- SAM segments → triangular meshes within each object during warping
- Each object's mesh balances projective + similarity transformations, keeping object shapes intact
- StitchBench released on HuggingFace

**ASP integration:** OBJ-GSP-style triangular-mesh shape-preservation prior on BiRefNet/SAM-2 foreground — let the character foreground mesh balance similarity-vs-projective in the warp.

#### 5.8.2 SemanticStitch — Hard Seam Barrier
(Jin et al., arXiv:2511.12084, The Visual Computer 2025; code: `github.com/Pokerman8/OAIV-Coherence`)
- Loss function that **emphasises semantic integrity of salient objects** in seam-cut optimisation
- Hard barrier: set cost of cutting through any pixel inside a SAM-2 foreground mask to `~10⁶×` the photometric cost — forces graph-cut to route around the character
- Where seam **must** cross the character (vertical pan, character occupies full strip width): don't seam-blend at all — pick the single best frame for that strip column (combined with pose-consistent frame selection)

**Complexity:** Low (cost-term modification + SAM-2). **Expected impact:** Medium-Large on character-cutting issue.

#### 5.8.3 Graph-Cut with Intelligent Scissors Fallback (HITL)
- Graph-Cut: panoramic canvas as pixel-node graph; Dijkstra shortest-path weighted against high-contrast structural edges (character silhouette ink lines)
- Intelligent Scissors: user-guided spatial waypoints to force seam through empty background space
- Guarantees seam does not compromise character anatomy

---

### 5.9 Generative Compositing and Background Completion

#### 5.9.1 ToonCrafter — Generative Midpoint Synthesis
(Xing et al., SIGGRAPH Asia 2024/ACM TOG 43(6), arXiv:2405.17933; code: `github.com/Doubiiu/ToonCrafter`)

**Mechanism:**
- Adapts live-action image-to-video diffusion priors (DynamiCrafter) to cartoon domain via **toon rectification learning** — forces latent space to boundary-and-flat-color aesthetics
- **Dual-reference-based 3D VAE decoder:** injects high-frequency ink-line details from uncompressed source frames into the decoding phase
- **Sparse sketch guidance:** human-drawn intermediate sketches as ControlNet anchors
- **Inference cost:** ~24s per 320×512 clip at 50 DDIM steps on A100; ~10–17GB VRAM with fp16 optimisation

**ASP use case:** When two adjacent strips have character poses that ARAP cannot bridge without ghosting (post-warp seam diff > 22 lum), synthesise an intermediate frame conditioned on the two adjacent strip character crops, then use it as the seam transition source.

**⚠ Critical caveats:**
- Authors' README: "*due to the variety of generative video prior, the success rate is not guaranteed.*"
- **Always gate output** by LPIPS or CLIP similarity to input strips — mandatory quality check
- **Fallback for hard cases only (~40% fallback subset)**, not a default
- Already wired in ASP as `ASP_TOONCRAFTER_SEAM=1` (default OFF) for worst single-pose seam per test

#### 5.9.2 ProPainter — Background Completion
(Zhou et al., ICCV 2023, arXiv:2309.03897; code: `github.com/sczhou/ProPainter`)
- Video inpainting via dual-domain (image + feature) flow-guided propagation + mask-guided sparse video Transformer
- **~192 FPS** on NVIDIA V100; +1.46 dB PSNR over FuseFormer/FGT
- **Use ProPainter, not VidPanos** — ProPainter is deterministic and doesn't hallucinate new content into flat-colour backgrounds

**Pipeline with ProPainter:**
1. SAM-2 foreground mask per frame
2. Align frames with translation-only BA
3. Project to panoramic canvas with foreground masked out
4. ProPainter on masked panoramic video to complete background
5. Collapse temporal axis with existing temporal-median

---

### 5.10 Quality Assessment (No-Reference)

#### 5.10.1 SIQE — Ghosting Detection
- Multi-scale steerable pyramids (2 scales, 6 orientations → 12 subbands) decompose target image
- Ghosting manifests as unnatural high-frequency edges in tight spatial clusters
- GMM models pyramid statistics → quantifies probability of structural inconsistency
- Local optical-flow variance establishes perceptual geometric error gradient
- **94.36% precision vs. mean human opinion** in empirical studies

#### 5.10.2 SI-FID / DiFPS — Reference-Free Distribution Score
- **SI-FID:** contrastive training with artificial stitching noise injections → Fréchet distance between generated vs. pristine image feature distributions. Rank correlation coefficient ≥25% higher than competing NR-IQA indicators.
- **DiFPS (DINOv2 Features Perception Similarity):** uses DINOv2 semantic completeness rather than patch similarity — evaluates geometric completeness

#### 5.10.3 DLNR-SIQA — Localized Artifact Detection
(Ullah et al., Sensors 2020)
- Fine-tuned Mask R-CNN segments and localises discrete stitching error regions
- Quality score derived from morphological characteristics and pixel volume of error segments
- **Provides precise pixel coordinates** of ghosting and seam artifacts vs. single global score

#### 5.10.4 MLLM-Based Quality Scoring
- **SIQS (Single-Image Quality Score):** VLM-based assessment detecting semantic contradictions (severed torsos, four arms)
- **MICQS (Multi-Image Comparative Quality Score):** multi-image comparison using LMMs
- Frameworks: `mllmmetrics.py` (RDIStitcher), Qwen-VL, GLM as backends
- **Captures catastrophic logical failures** that statistical metrics like SI-FID overlook

---

## 6. Algorithmic Synergy Maps

| Upstream Algorithm | Output / State | Downstream Receiver | Synergy Mechanism |
|---|---|---|---|
| **SAM-2 Video Predictor** | Temporally consistent foreground masks per frame | **Phase correlation + BGM frame selector** | Background-subtracted phase correlation eliminates character-animation contamination of displacement estimate |
| **Pose-consistent frame selector** | Frame subset where adjacent frames share the same drawn cel | **ARAP foreground registration** | Near-identical poses → ARAP warp residuals drop from 22–50 lum to <8 lum → feather widening (S12) triggers → clean seam |
| **GNC-TLS bundle adjustment** | Outlier-free translation affines | **PANORAMA fallback / Validation Gate** | Fewer outlier-poisoned affines → fewer BA failures → fallback rate drops |
| **AnimeInterp SGM flow** | Piece-wise constant flow field on foreground | **SEA-RAFT** | SGM output warm-starts SEA-RAFT with a noise-free coarse field → RAFT refines without collapsing on flat regions |
| **SAM-2 mask** | Per-frame character mask with temporal consistency | **SemanticStitch hard barrier** | DP seam cost `10⁶×` inside mask guarantees seam routes around character |
| **DLNR-SIQA error segments** | Pixel coordinates and morphological volume of stitch errors | **ToonCrafter or ProPainter** | Error segment maps serve as targeted masks for localised re-synthesis without disturbing surrounding healthy pixels |
| **ToonCrafter midpoint synthesis** | Hallucinated in-between frame for unresolvable pose gap | **Seam compositing** | Seam transitions to synthesised content rather than blending mismatched poses → eliminates double-image ghost |

---

## 7. Reference Datasets

| Dataset | Purpose | Scale | Key Properties |
|---|---|---|---|
| **ATD-12K** (AnimeInterp, CVPR 2021) | Anime interpolation GT | 12,000 triplets | Easy/Medium/Hard splits by motion magnitude; GT for SGM/RFR evaluation |
| **AnimeRun** (NeurIPS 2022) | 2D-styled cartoon correspondence | 30 clips | Full optical flow + region-level segment matching labels; boundary-aware evaluation |
| **LinkTo-Anime** (arXiv:2506.02733, 2025) | Cel-shaded anime character optical flow | 395 sequences; 24,230 train frames | Mixamo skeletons + toon shading; pixel-perfect GT flow + occlusion masks + skeleton annotations |
| **STD-12K** | Sketch-aware inbetweening | 30 sketch animation series | Pre-colorization interpolation; diverse artistic styles |
| **PaintBucket-Character** (CVPR 2024) | Colorisation + segment GT | 22 Mixamo character models | Anti-aliasing disabled; semantic labels per colour; shading annotations |
| **Sakuga-42M** | Large-scale foundation model training | ~42M frames | Extreme non-linear motion (sakuga); professional animation quality |
| **StabStitch-D** | Video stitching trajectory evaluation | — | Used by StabStitch++ at 28.3 FPS (RTX 4090) |

---

## 8. Human-in-the-Loop Architecture (Optional Path)

When full automation is insufficient, a **stateful HITL middleware** resolves Category A/B/C failures through expert intervention:

**Architecture:** Event-driven DAG with explicit static breakpoints at high-risk stages (Stage 7 BA, Stage 10 Foreground Registration). Async execution via `asyncio` + persistent checkpointer (SQLite/Redis). Complete pipeline state serialised into immutable configuration dict with unique thread_id. Non-blocking WebSocket to frontend GUI on suspension.

**HITL Intervention Vectors:**

| Pipeline Stage | Autonomous Engine | Interactive Upgrade | Human Vector |
|---|---|---|---|
| Stage 2.1: Selection | Phase Correlation gate | Overmix-style Pose Grouping | Timeline GUI subset selection |
| Stage 4: Masking | BiRefNet | SAM-2 video predictor | Bbox and point click prompts |
| Stage 7: BA | GNC-TLS | BigWarp / Fourier-Mellin transform | Manual landmark correspondences on background elements |
| Stage 10: Flow | ARAP + RAFT | SAM2Flow / FlowVid | Interactive arrow/scribble trajectory hints |
| Stage 13: Seam | DP graph-cut | Intelligent Scissors | Spatial waypoints to snap seam into empty background space |

**Path to full automation (RLHF):**
- **Short term:** Online adaptation using user-refined outputs as pseudo-GT; Active Learning (ActiveFreq) to prioritise most informative mislabeled regions
- **Mid term:** RL for semantic masking (LENS); RL-based keypoint selection using epipolar constraints; imitation learning from user flow annotations (DTWIL)
- **Long term:** RLHF end-to-end LVDM with Reasoning Reward Models (CoT verifier), multi-modal visual expert (Qwen2.5-VL), and Flow-DPO for direct preference optimisation

---

## 9. Current Implementation Status (Session 32, 2026-06-07)

Key upgrades already in ASP as of S32 (262 tests passing):

| Session | Item | Status |
|---|---|---|
| S6 | Hold detection (`_detect_hold_blocks`) | ✅ |
| S6 | GNC Cauchy loss in BA (`loss='cauchy', f_scale=10.0`) | ✅ |
| S6 | SLIC SGM proxy (enable: `ASP_SGM_PROXY=1`) | ✅ |
| S8 | DINOv2 frame selection (enable: `ASP_POSE_WINDOW_PX=80`) | ✅ |
| S8 | LSD collinearity in ARAP (`_arap_regularise`) | ✅ |
| S8 | Aligned-SSIM benchmark metric | ✅ |
| S9 | ToonCrafter seam synthesis (enable: `ASP_TOONCRAFTER_SEAM=1`) | ✅ (default OFF) |
| S10 | Seam DP vectorisation (5–10× speedup) | ✅ |
| S14 | Seam visibility score in benchmark | ✅ |
| S17 | Per-pixel DSFN ramp + adaptive boundary search | ✅ |
| S20 | bg-mask-aware DSFN ramp | ✅ |
| S21 | Poisson seam blend (enable: `ASP_POISSON_SEAM=1`) | ✅ (default OFF) |
| S24 | Continuous adaptive gain clamp | ✅ |
| S27 | TOML config loader (`asp_config.toml`) | ✅ |
| S29 | RLHF post-run quality gate | ✅ |
| S30 | Adaptive GNC f_scale in BA | ✅ |
| S31 | PANORAMA stitcher fallback | ✅ |
| S32 | Pre-bundle static edge rejection (`_reject_static_edges`) | ✅ |

**Next priority items (from roadmap):**
- §1.10B Bayesian parameter search with reward signal (requires calibrated reward model)
- §M Pose-consistent frame selection redesign (Phase 1 highest-leverage item not yet implemented)
- §J SAM-2 replacement for BiRefNet (Phase 1)
- §A AnimeInterp SGM integration (Phase 2)
- §N Horizontal/diagonal scroll support (Phase 3)

---

## 10. Decision Thresholds and Do-Not-Adopt List

### Decision Thresholds
- If Phase 1 (frame selection + GNC + SAM-2) raises ASP-beats-naive from 14.5% → **≥35%** and lowers fallback from 40.6% → **≤25%**: Phase 2 is justified
- If after Phase 1 failures concentrate in "alignment crashes/drifts": try **EDM** as drop-in LoFTR replacement before deeper changes
- If after Phase 2 residual failures concentrate in "character moves between strips": **ToonCrafter** (Phase 3K) becomes critical
- If after Phase 2 residual failures concentrate in "diagonal pan failed": **StabStitch++ + 2D BA** (Phase 3G+N) is critical

### Do Not Adopt
- **UDIS++/SRStitcher wholesale without retraining** — TPS warps and diffusion priors tuned to natural-photo parallax, not anime cel-shaded pose mismatch
- **VidPanos for background** — generative overkill; ProPainter is the right tool (deterministic, no hallucination risk)
- **JamMa over EDM** — EDM has the bidirectional sub-pixel head that translation-only BA actually benefits from
- **Alpha warp > 0.5 on RAFT flow** — amplifies flow noise directly proportional to alpha; confirmed catastrophic in Global Reference Asymmetric Alpha Warp experiment (test27 SSIM: 0.709 → 0.558)
- **Foreground bounding-box content crop without scroll-axis awareness** — crops 44% of image width on vertical pans (confirmed failure on test27)

### Known Caveats
- **ToonCrafter is non-deterministic.** Authors warn: "*due to the variety of generative video prior, the success rate is not guaranteed.*" LPIPS/CLIP quality-gating is mandatory.
- **SAM-2 on anime: not officially benchmarked.** Community reports positive on clean characters, mixed on translucent effects. Run 20-clip validation against BiRefNet before full replacement.
- **GNC convergence depends on μ scheduling:** too-fast annealing → local minima. Yang et al. 2020 schedule (1.4× per outer iter) is a safe default.
- **LinkTo-Anime is 3D-rendered, not hand-drawn.** Cross-validate on ATD-12K to catch domain gap.
- **Overmix is GPL-3.0.** Algorithmic ideas may be re-implemented but code may not be linked into a non-GPL ASP.
- **LSD collinearity term is NOT in original Sýkora 2009.** It is a novel extension that must be tuned on a held-out validation set.
- **"SGM raises PSNR by 0.6–1.0 dB" is unverified.** The CVPR 2021 paper reports 0.34 dB overall; dedicated SGM-only ablation on the Hard split was not located. Treat per-module attribution as needing reproduction.
