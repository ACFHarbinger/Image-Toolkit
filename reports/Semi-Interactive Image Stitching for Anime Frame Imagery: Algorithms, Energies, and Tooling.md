# Semi-Interactive Image Stitching for Anime Frame Imagery: Algorithms, Energies, and Tooling

## TL;DR

- **For anime-frame stitching, the dominant failure modes (ghosting, exposure/lighting drift, line-art warping) are best attacked with a hybrid pipeline that combines (a) detector-free or learned matching (LoFTR/SuperPoint+SuperGlue/LightGlue) with user-placed correspondences as hard constraints, (b) a content-preserving mesh warp regularized by user pins (CPW/APAP/MLS/TPS), and (c) graph-cut seam-finding with user-painted "must-include / must-exclude" terminals (Boykov–Jolly seeds, Agarwala-style image objectives), followed by multi-band Laplacian and/or Poisson blending.**
- **The interesting structural fact for anime is that classical photometric matchers (SIFT/SURF) silently fail on flat-color cels with sparse high-frequency content; AKAZE's nonlinear scale space, learned dense matchers (LoFTR), and segmentation-driven region matching (AnimeSegmentation/CartoonSegmentation, line-art trapped-ball, region-wise correspondence networks) are far better priors than rotation/scale-invariant point detectors. Color/exposure correction should be palette-aware rather than purely Gaussian-statistical (Reinhard) because anime has bimodal histograms in flat regions plus sharp line-art bands.**
- **All stages can be cast in a single energy-minimization framework with user input as either hard equality constraints (pinned mesh nodes, terminal-fixed graph nodes) or soft Lagrangian penalties; this is well-supported by mature open code (Hugin/PanoTools, OpenCV `stitching` module/`opencv::stitching` Rust bindings, Schaefer's MLS in Rust, OpenStitching Python, PTGui as a reference UI). Microsoft ICE was the most polished consumer tool but is now retired.**

---

## Key Findings

1. **User-assisted registration is most cleanly framed as a regularized scattered-data interpolation problem.** Thin-plate splines (TPS), moving least squares (MLS, Schaefer–McPhail–Warren 2006), and content-preserving warps (CPW, Liu et al. 2009) all admit a closed-form or sparse-quadratic solution where user-supplied control points become hard interpolation constraints and the regularizer (bending energy / similarity prior) shapes the rest. MLS in particular has a Rust crate (`mpizenberg/rust_mls`) that maps directly onto your stack.

2. **The 2004 Agarwala "Interactive Digital Photomontage" framework remains the canonical interactive seam-finding system.** It uses graph-cut to choose seams under user-painted "image objectives" (max-contrast, designated-source, designated-color, min-error) plus Pérez-style Poisson gradient-domain fusion. The Boykov–Jolly (2001) "interactive graph cuts" paper provides the formal mechanism — terminal-attached infinite-cost edges turn user strokes into hard constraints inside a min-cut/max-flow MRF.

3. **Ghosting is structurally caused by parallax + scene motion + insufficient locality of the warp.** The state of the art uses a seam-driven approach (Gao 2013, Zhang & Liu 2014 "Parallax-tolerant", Lin et al. 2016 SEAGULL) that generates multiple alignment hypotheses and picks the one with the cheapest seam, optionally iterating; APAP (Zaragoza et al. 2013) provides locally-projective Moving DLT warps that already substantially reduce ghosting before seaming. For dynamic content (animation movement between frames) Eden–Uyttendaele–Szeliski (CVPR 2006) two-stage graph cut and Davis (CVPR 1998) vertex-cover deghosting are the classical references; a user-painted "exclude this object from frame k" mask is exactly a hard t-link assignment in their MRFs.

4. **Anime imagery breaks photometric assumptions in three specific ways** — (a) huge flat regions kill SIFT/SURF/Harris-style detectors that rely on local gradient richness; (b) anti-aliased line-art bands have aliased gradients that confuse subpixel refinement; (c) bimodal/banded histograms violate the Gaussian assumption underlying Reinhard color transfer and Brown–Lowe gain compensation. Solutions: detector-free dense matching (LoFTR), AKAZE's nonlinear diffusion scale space (better behavior on cartoon edges than DoG), region-level matching using anime segmentation (SkyTNT/anime-segmentation, CartoonSegmentation, trapped-ball line-art segmentation), and *region-stratified* color transfer (apply Reinhard or histogram-matching per palette cluster, not globally).

5. **Color, exposure, and lighting drift across cels are best handled hierarchically:** (i) global gain/bias compensation per Brown–Lowe 2007 (least-squares fit of per-image gain `g_i` with overlap-mean equality + identity-prior regularization); (ii) per-block compensation (OpenCV `BlocksGainCompensator`); (iii) palette-aware local transfer using k-means or anime-segmentation-derived clusters; (iv) gradient-domain/Poisson blending (Pérez 2003) which guarantees C¹ continuity across the seam regardless of remaining bias. Multi-band Laplacian-pyramid blending (Burt–Adelson 1983) handles low-frequency lighting drift by allowing different band widths per spatial frequency.

6. **The whole stitching problem can be folded into one quadratic / MRF energy** with three coupled blocks: (a) a sparse-quadratic mesh-warp energy `E_warp(V) = E_align + λ_s E_smooth + λ_l E_line + λ_u E_user`, (b) a binary-label MRF `E_seam(L)` over the overlap, and (c) a per-channel sparse-linear Poisson system `Δf = div v` for blending. Each block has hard user-constraint slots: pinned vertices in the mesh, fixed t-links in the graph, fixed Dirichlet boundary samples in the Poisson system.

7. **Tooling for a Rust/Python implementation** is unusually good: `opencv::stitching` (Rust bindings) and OpenCV's `detail::` module expose the entire Brown–Lowe pipeline including `GainCompensator`, `BlocksGainCompensator`, `GraphCutSeamFinder`, `MultiBandBlender`; Hugin/PanoTools (`cpfind`, `nona`, `enblend`, `deghosting_mask`) provide a battle-tested CLI front-end; `mpizenberg/rust_mls` provides MLS warping in idiomatic Rust; `OpenStitching/stitching` is a clean Python wrapper. PTGui is the gold-standard interactive UX target.

---

## Details

### 1. Interactive registration and warping

#### 1.1 Thin-plate spline (TPS) with control-point hard constraints

Given `n` correspondences `{(p_i, q_i)}`, TPS minimizes the bending energy

  `J(f) = ∫∫ (f_xx² + 2 f_xy² + f_yy²) dx dy`

subject to interpolation `f(p_i) = q_i`. The closed-form solution decomposes into an affine part and a sum of radial basis functions `U(r) = r² log r`. Coefficients come from a `(n+3)×(n+3)` linear system. Soft constraints (regularized TPS) replace strict interpolation with `min ||f(p_i) - q_i||² + λ J(f)` and yield a smooth, point-wise pinned warp ideal for a user dragging keypoints in a UI; this is precisely what Anderson et al.'s `ir-tweak` (electron tomography) exposed and what Hugin's "Control Points" tab approximates.

#### 1.2 Moving Least Squares (Schaefer–McPhail–Warren, SIGGRAPH 2006)

For each output pixel `v`, solve a weighted least-squares for the best affine/similarity/rigid map `l_v` minimizing `Σ_i w_i(v) ||l_v(p_i) - q_i||²` with `w_i(v) = 1/||p_i - v||^(2α)`. As `v → p_i`, `w_i → ∞` and the warp interpolates the control point exactly — giving you exact hard constraints by construction without an explicit Lagrangian. The rigid variant preserves orientation and is excellent for line-art preservation. A native Rust implementation exists (`mpizenberg/rust_mls`) with a `rayon` parallel feature.

#### 1.3 Content-Preserving Warp (CPW; Liu et al. 2009) and APAP (Zaragoza et al. CVPR 2013)

Discretize the source image into a grid mesh `V ∈ ℝ^(N×2)`. Define

  `E(V̂) = E_data + λ_s E_similarity + λ_l E_line + λ_u E_user`

- `E_data = Σ_k ||T_k V̂_k - q_k||²` — every correspondence k expressed as a bilinear combination `T_k` of its containing-quad's vertices must land on its target.
- `E_similarity` (Liu et al.) constrains every quad to undergo a similarity-only deformation, preventing local shears/skews — this is essential for anime line-art aesthetics.
- `E_line` (Lin et al. SPW, Du CVPR 2022) penalizes deviation from collinearity for detected line segments.
- `E_user`: pin user-supplied vertices to user-supplied targets with infinite weight (or solve the equality-constrained QP).

Total energy is sparse-quadratic in V̂; solve once per image with a sparse Cholesky (e.g., Eigen / `sprs` in Rust / `scipy.sparse.linalg`).

APAP (Moving DLT) is the projective analogue: at every grid vertex it solves a weighted SVD of the Direct Linear Transform with weights `w_i(v) = max(exp(-||p_i - v||²/σ²), γ)`, producing a smoothly-varying homography field. Reference: Zaragoza et al. *As-Projective-As-Possible Image Stitching with Moving DLT*, CVPR 2013. Open Python implementation: `EadCat/APAP-Image-Stitching`. In practice for anime (mostly planar/parallax-free panning), a global homography is often sufficient if the matches are clean; APAP shines under camera-pan-with-perspective situations.

#### 1.4 User-guided dense correspondences

Classic optical-flow methods that take sparse user matches as initialization: **EpicFlow** (Revaud et al. CVPR 2015) does sparse-to-dense interpolation using an *edge-aware geodesic distance* — replace its DeepMatching front-end with `(your detector matches) ∪ (user matches)` and you get a dense flow field that respects motion boundaries (ideal for character-vs-background separation in anime). **InterpoNet** is a learned successor. For modern learned flow, **RAFT** (Teed & Deng ECCV 2020) and **GMFlow** (CVPR 2022) with user constraints can be enforced by adding an L2 penalty to the cost-volume update or by clamping the predicted flow at user-pinned pixels.

For anime specifically, AnimeRun and LinkTo-Anime are publicly available cel-rendered optical-flow datasets you could fine-tune on. Off-the-shelf flow models trained on Sintel/KITTI degrade on flat-color cels, so fine-tuning or hint-injection is essential.

### 2. Seam finding under user guidance

#### 2.1 The Agarwala 2004 framework (Interactive Digital Photomontage)

The pixelwise label MRF is

  `E(L) = Σ_p C_d(p, L(p)) + Σ_(p,q)∈N C_i(p, q, L(p), L(q))`

- Data term `C_d` encodes the user's *image objective* at pixel p — e.g., "designated-source" (= 0 if `L(p) = k_user_chose`, else ∞), "max-contrast", "min-error w.r.t. reference". Painting a stroke effectively rewrites `C_d` over a region.
- Interaction term `C_i` is the seam cost. Two standard forms: `||I_{L(p)}(p) - I_{L(q)}(p)|| + ||I_{L(p)}(q) - I_{L(q)}(q)||` (color matching across boundary), or the gradient-augmented variant from Kwatra et al. SIGGRAPH 2003 *Graphcut Textures*.

Solved with α-expansion (Boykov–Veksler–Zabih 2001) for >2 sources, or vanilla min-cut/max-flow for binary cases. The Boykov–Kolmogorov 2004 max-flow algorithm is the workhorse; `gco-v3.0` and OpenCV's `GraphCutSeamFinder` are usable backends.

#### 2.2 Encoding user guidance as hard constraints

- **"This pixel must come from frame k"**: set `t-link(p, source_k) = ∞`, all other `t-link(p, source_j) = 0`. Boykov & Jolly (ICCV 2001) showed this preserves global optimality.
- **"The seam must pass through (or avoid) this curve"**: set the corresponding n-link capacities to 0 (must-cut) or ∞ (must-not-cut). Generalized hard constraints (Malmberg–Strand–Nyström 2011) handle the resulting feasibility issues.
- **"Exclude this moving character from the panorama"**: paint a mask M; set every pixel in M for the contaminated frame to `t-link = ∞` to the *other* source. This is the user-driven analogue of the Davis (CVPR 1998) and Eden et al. (CVPR 2006) automatic deghosting.

#### 2.3 Multi-band and Poisson blending

After seam selection, three blending choices, each with user-constraint slots:

- **Feathering / alpha blending** — fast, but blurs and ghosts at large parallax.
- **Multi-band Laplacian-pyramid blending** (Burt & Adelson 1983, *A Multiresolution Spline*) — build Gaussian pyramids of the binary masks, Laplacian pyramids of the images, blend each level with a band-appropriately-blurred mask, collapse. Low frequencies get long blend zones (handles lighting drift), high frequencies get short blend zones (preserves anime line art). OpenCV's `MultiBandBlender` implements this. User-painted soft masks replace the hard binary mask at the input.
- **Poisson / gradient-domain blending** (Pérez–Gangnet–Blake SIGGRAPH 2003) — solve `Δf = div v` over the destination region Ω with Dirichlet boundary `f|∂Ω = f*|∂Ω`. The guidance vector field `v` can be (a) the source gradient (seamless cloning), (b) max(source, dest) gradient (mixed cloning, preserves edges), or (c) user-painted (for inserting/removing structure). This is exactly the Agarwala 2004 step-2 fusion. Closed-form via sparse SPD solver (`Eigen::SimplicialLDLT`, or convolution-with-Green's-function for rectangular Ω, ref. arXiv:1902.00176).

### 3. Ghosting mitigation specific to anime frames

For anime frames extracted via FFmpeg (`ffmpeg -i input.mkv -vf fps=1 frame_%04d.png` or every-frame `frame_%06d.png`), ghosting arises from:

- **Character motion between adjacent panning frames** — the camera pans across a fixed background but the character moves. Use anime segmentation (SkyTNT/anime-segmentation ISNet; CartoonSegmentation/AnimeInstanceSegmentation Mask-R-CNN; `jerryli27/AniSeg`) to produce per-frame foreground masks, then either (a) treat foreground as exclusion regions in the seam MRF, or (b) median-stack background-only pixels over time after homography registration (the classical Davis 1998 sprite-decomposition idea, also patented and reflected in US 7940264).
- **Parallax (multi-plane backgrounds, common in animation)** — adopt the seam-driven recipe: generate `K` warp hypotheses (global homography, APAP, dual-homography for distant+ground planes per Gao et al. 2011), seam-cut each, pick the warp whose seam cost is lowest. SEAGULL (Lin et al. ECCV 2016) iterates between seam estimation and local mesh refinement. For an interactive UI, pre-compute the seam costs of all hypotheses and let the user click the preferred one.
- **Line-art doubling** — small misalignments produce visible edge ghosts because anime edges are crisp. The fix is *line-aware warping* (penalize bending of detected lines in `E_line`) plus *seam routing along edges*: in `C_i`, weight seam costs by `(1 - edge_strength)` so the seam is cheap to place along strong edges where doubling is invisible, and expensive across flat color regions where any tear shows.

Exposure-robust descriptors: BRIEF/ORB are intensity-pattern-only and break under exposure shifts; AKAZE uses Modified-Local-Difference-Binary descriptors over a *nonlinear diffusion scale space* and is significantly more robust on cartoon-style edges than DoG-based SIFT (cf. MDPI *AKAZE-GMS-PROSAC* 2025). For HDR/exposure-bracketed input, use radiance-space matching (Eden et al. CVPR 2006). MSER (Maximally Stable Extremal Regions) detects flat-color blob regions which are exactly the dominant anime feature and complements line/corner detectors.

### 4. Color and exposure correction across panels

#### 4.1 Brown–Lowe 2007 global gain compensation

For images `i = 1...n` with overlap regions `R_ij` and per-image scalar gain `g_i`, minimize

  `E(g) = Σ_(i,j) Σ_(p ∈ R_ij) (g_i I_i(p) - g_j I_j(p))² / (2σ_N²) + Σ_i (1 - g_i)² / (2σ_g²)`

The second term is a Gaussian prior pulling gains toward 1 (preventing the trivial all-zero solution). It's a tiny linear system in `g`. Apply in linear (gamma-corrected) RGB. Per-channel gives color correction; per-channel-per-block gives `BlocksGainCompensator` which handles spatially varying lighting drift.

#### 4.2 Reinhard et al. 2001 color transfer — and its caveats for anime

Convert source S and target T to `lαβ` (Ruderman). Match per-channel mean and std:

  `c'_S = (σ^c_T / σ^c_S) (c_S - μ^c_S) + μ^c_T`

This works for natural images because `lαβ` channels are decorrelated and approximately Gaussian. **It does *not* work well on anime** because (a) the histogram is bimodal/multimodal (sharp peaks at flat-color modes plus tails along line art), and (b) global statistics get dominated by background area. Two practical fixes:

- **Region-stratified Reinhard**: cluster both source and target with k-means in `Lab` (k = 4–8 per palette inspection), greedy-match clusters by centroid distance, apply Reinhard *per matched cluster pair*. This is what the PyImageSearch follow-up suggests and what `GISCT`/`NCT` (Wang 2006) generalizes.
- **Histogram matching with user-selected reference regions**: build empirical CDFs over user-painted "this region should look like that region" pairs, apply per-channel CDF matching. Robust to non-Gaussianity.

#### 4.3 Palette-based color harmonization (anime-specific)

Anime cels have 8–32 unique colors in a typical character (binarization of cel paint). Workflow: (i) run trapped-ball segmentation (Zhang et al. 2009; SIGGRAPH Asia 2024 *Fast Leak-Resistant Segmentation for Anime Line Art*) on the line-art layer to get region IDs; (ii) extract a per-frame palette via mode-finding inside each region; (iii) build a bipartite matching across frames of palette entries (Hungarian on Lab distance with anime-segmentation as a structural prior); (iv) apply per-region constant offsets so matched palette entries align across frames. This is *much* more faithful than continuous color transfer for cel animation.

#### 4.4 Lighting inconsistency

For background/scenic shots with smooth lighting gradients across pans, model lighting per image as a low-order polynomial or RBF surface `L_i(x,y)` and jointly solve for `{g_i, L_i}` minimizing overlap discrepancy. This is the per-block compensator generalized to a smooth field. Equivalent in spirit to vignetting/exposure calibration (Goldman & Chen ICCV 2005).

### 5. Anime-specific feature matching

Empirical observations from the literature:

- **SIFT/SURF/Harris** rely on rich local gradients; on anime, "good features" cluster on character faces and clutter, leaving large background regions unmatched. Failure rate on flat skies, walls, gradients is essentially 100%.
- **AKAZE** (Alcantarilla et al. 2013) computes features in a *nonlinear* diffusion scale space (PDE-based) which respects edges rather than blurring across them — empirically the best classical detector for cartoon edges. Use with M-LDB descriptors (binary, fast Hamming match).
- **ORB/BRISK** are intensity-pattern-only; competitive on rotation/in-plane changes but fragile under exposure changes (relevant for cross-cut scene changes).
- **SuperPoint** (DeTone–Malisiewicz–Rabinovich CVPRW 2018) — self-supervised CNN keypoints, much denser detection than SIFT in low-texture regions.
- **SuperGlue** (Sarlin et al. CVPR 2020) — graph-neural-network matcher with self/cross-attention and a Sinkhorn-normalized assignment matrix; jointly does matching + outlier rejection. Outdoor pretrained weights generalize surprisingly well to non-photographic content but a fine-tune on anime pairs (e.g., from ATD-12K, AnimeRun, or PaintBucket-Character) is recommended.
- **LightGlue** (Lindenberger–Sarlin–Pollefeys ICCV 2023) — faster, adaptive-depth SuperGlue successor; the integration target most modern tools use.
- **LoFTR** (Sun et al. CVPR 2021) — *detector-free*, semi-dense; produces matches in low-texture regions where keypoint detectors fail entirely. This is the single most relevant matcher for anime stitching. Coarse-to-fine: low-resolution Transformer-based dense matching → fine-level subpixel refinement. *Efficient LoFTR* (CVPR 2024) gets sparse-like speed.
- **Region-wise correspondence networks** (arXiv:2509.09501 *Region-Wise Correspondence Prediction between Manga Line Art Images*) operate at the segment level, which is the natural unit for anime. Combine with patch-based and rule-based positional/color matching for unmatched regions.

A pragmatic recipe: **LoFTR for dense matches → RANSAC/MAGSAC++ for global homography → APAP/CPW for local refinement → user inspects, drags pins, system re-solves.**

### 6. Unified energy formulation with user constraints

A clean way to organize the whole pipeline mathematically:

**Stage A — Mesh warp** (once per source, except the reference). Variables: warped vertex positions `V̂ ∈ ℝ^(N×2)`. Energy:

  `E_warp(V̂) = α_d Σ_k ||T_k V̂ - q_k||² + α_s E_sim(V̂) + α_l E_line(V̂) + α_h Σ_(i ∈ U_hard) ||V̂_i - u_i||²`

with `α_h → ∞` for hard pins (or use a Lagrange-multiplier KKT system to enforce the equality exactly). Sparse SPD QP; closed-form via Cholesky.

**Stage B — Label MRF for seam.** Variables: per-pixel labels `L: Ω → {1,...,n}`. Pairwise CRF energy:

  `E_seam(L) = Σ_p C_d(p, L(p)) + Σ_(p,q)∈N C_i(p, q, L(p), L(q))`

User strokes set `C_d(p, k) = -∞` (forced choice) or `+∞` (forbidden). User-drawn polylines set `C_i = 0` along the line (must-cut) or `+∞` (must-not-cut). Solve with α-expansion.

**Stage C — Photometric harmonization.** Variables: per-image gains `g_i` (or per-block, or polynomial field). Quadratic in `g`:

  `E_photo(g) = Σ_(i,j) Σ_(p ∈ R_ij) σ_N⁻²(g_i I_i - g_j I_j)² + Σ_i σ_g⁻² (1 - g_i)²`

**Stage D — Poisson blending.** Variables: per-channel pixel values `f` inside the union region. Linear:

  `(Δf)(p) = (div v)(p) ∀ p ∈ Ω, f|∂Ω = f*|∂Ω`

User-supplied "color hint" pixels become additional Dirichlet constraints inside Ω.

In principle one can co-optimize `(V̂, L, g, f)` jointly (this is approximately what generative-stitching networks like UDIS++ and recent diffusion-based work do), but in practice the alternating-block formulation above converges quickly and is what every production tool implements.

### 7. Notable software and frameworks

| Tool | Role for your project | Notes |
|---|---|---|
| **Hugin / PanoTools** (`cpfind`, `nona`, `enblend`, `enfuse`, `deghosting_mask`) | Reference open-source pipeline; mature manual control-point UI; CLI-scriptable | GPL; written in C++; `.pto` project file is a clean text format you can generate from Python/Rust |
| **PTGui / PTGui Pro** | Best-in-class commercial control-point UX | Closed; useful as a UX benchmark for a Rust-native UI |
| **Microsoft ICE** | Was the most polished automatic stitcher; supported Deep Zoom output and structured-grid panoramas | **Project retired in 2021**; binaries only on the Internet Archive. No anti-ghosting, no mask painting. Cited as inspiration only. |
| **OpenCV `stitching` module** (`cv::Stitcher`, `cv::detail::*`) | Direct programmatic access to Brown–Lowe pipeline, `GraphCutSeamFinder`, `BlocksGainCompensator`, `MultiBandBlender` | Available in both Python (`cv2`) and Rust (`opencv` crate, `opencv::stitching`) |
| **OpenStitching `stitching`** (Python) | Pythonic wrapper around OpenCV stitcher with a clean tutorial and per-stage hooks | MIT; ideal for prototyping |
| **`mpizenberg/rust_mls`** | Rust implementation of Schaefer 2006 MLS warping | Optional rayon parallelism; perfect for the warp-pinning UI |
| **OpenPano** | Educational C++ implementation of the full Brown–Lowe pipeline | Good source to mine for understanding |
| **APAP-Image-Stitching** (Python, EadCat) | Reference implementation of Moving DLT | Single-pair only |
| **`magicleap/SuperGluePretrainedNetwork`, `zju3dv/LoFTR`, `cvg/LightGlue`** | Modern learned matchers | All PyTorch; ONNX export possible for Rust deployment via `ort` or `tch-rs` |
| **`SkyTNT/anime-segmentation`, `CartoonSegmentation/CartoonSegmentation`, `jerryli27/AniSeg`** | Anime foreground/character/instance masks | ISNet, U2Net, Mask R-CNN backbones; Hugging Face hosted weights |

A practical Rust+Python architecture: heavy ML inference (LoFTR, anime-segmentation) in Python/PyTorch via gRPC or ONNX; UI, mesh-warp QP solver, graph-cut seam finder, Poisson blender in Rust (use `nalgebra-sparse` + `sprs` for sparse solves, `pathfinding` or a direct max-flow port for graph cut, `image` crate for I/O).

---

## Caveats

- **The "Generative Photomontage" (Lseancs 2024) and many recent learning-based stitchers (UDIS++, NIS, LiftProj 2025, *Seamlessly Natural* arXiv:2601.01257)** are promising but operate as black boxes with no clean user-constraint slots. Some of the very recent arXiv preprints surfaced here (the 2601.xxxxx and 2602.xxxxx IDs) are not yet peer-reviewed; treat their numerical claims with appropriate skepticism. A semi-interactive system needs the *interpretable energy decomposition* described above; learned methods are best slotted in as *priors* (e.g., as initialization, or as a learned data-term cost) rather than as the entire pipeline.
- **No standard benchmark exists for anime panorama stitching specifically.** ATD-12K, AnimeRun, PaintBucket-Character and LinkTo-Anime are correspondence/colorization datasets, not stitching datasets. You will likely need to build your own evaluation set.
- **FFmpeg-extracted frames have decoding subtleties**: VFR sources produce duplicate frames; B/P-frame seeking with `-ss` before vs after `-i` differs; lossy codecs introduce blocking artifacts that confuse subpixel matchers. Prefer `-i source -vsync 0 -q:v 1 frame_%06d.png` for frame-accurate, full-quality extraction; consider deinterlacing (`-vf yadif`) and color-space-correct gamma handling for old SD anime.
- **Microsoft ICE is retired and unavailable from Microsoft;** it cannot be used in a production pipeline today even though it appears in many tutorials.
- **For anime line art specifically**, *no* purely generic stitcher gives line-faithful results out of the box. Plan to invest in (a) a line-detection pre-pass (SIGGRAPH Asia 2024 trapped-ball, LineArtDetector from MangaNinja), (b) a line-preserving warp regularizer in `E_warp`, and (c) seam routing that prefers strong edges. Without these three, you will see line-art doubling/tearing even with otherwise-perfect alignment.
- **Color/lighting correction must run in linear (de-gammaed) RGB**, not sRGB; this is a frequent silent bug in stitching code. After applying gain compensation in linear space, re-apply the source gamma before display.
- **Seminal references are stable** (Brown–Lowe 2007, Agarwala 2004, Pérez 2003, Burt–Adelson 1983, Boykov–Jolly 2001, Schaefer 2006, Zaragoza 2013, Lin 2016 SEAGULL, Sun 2021 LoFTR, Sarlin 2020 SuperGlue) and worth reading in the order given above before implementing — the math composes cleanly across them, which is *not* true of more recent learning-based work.