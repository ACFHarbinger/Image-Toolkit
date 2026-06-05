# Improving the Anime Stitch Pipeline (ASP): A Research Survey on Frame Selection, Flat-Region Flow, Robust Bundle Adjustment, Semantic Seams, and Pose-Aware Ghost Elimination

**TL;DR**
- The four highest-leverage upgrades, in order of expected impact on the 14.5%-beats-naive / 40.6%-fallback benchmark, are: **(1)** replace the phase-correlation frame selector with an Overmix-style frame-difference cluster + foreground-pose-embedding selector solved by dynamic programming, **(2)** integrate AnimeInterp's Segment-Guided Matching (SGM) and fine-tune SEA-RAFT on the LinkTo-Anime dataset (395 sequences / 24,230 training frames) to solve the aperture problem on flat cel-shaded regions, **(3)** complete the Sýkora 2009 ARAP with a DeepLSD-driven line-collinearity energy term (this term is NOT in the original Sýkora 2009 paper — it must be added as a novel extension), and **(4)** replace residual pruning in bundle adjustment with Graduated Non-Convexity using a Geman–McClure or Truncated-Least-Squares surrogate (Yang et al. RA-L 2020).
- For seam routing and ghost elimination, SAM-2-driven hard barriers (SemanticStitch-style) plus OBJ-GSP triangular-mesh shape preservation on the foreground, combined with "single-pose graph-cut" frame selection (one frame per strip column), is the right structural fix; ToonCrafter (24 s per 320×512 clip at 50 DDIM steps on A100) is a generative fallback for the residual hard cases, not a default — its authors warn that "due to the variety of generative video prior, the success rate is not guaranteed."
- For horizontal/diagonal scrolls, generalise the translation-only BA to 2-D translation per frame (and optionally a small global rotation) and adopt the StabStitch++ (TPAMI 2025) bidirectional virtual-midplane warp formulation with an L1-trend-filter trajectory smoothing prior across all strip seams.

---

## Key Findings

The ASP pipeline's symptoms — strip-seam pose mismatches, ghosting in flat regions, residual ghosting at large pose gaps, character-cutting seams, diagonal-pan failures — map almost one-to-one onto known failure modes in three adjacent literatures (anime optical flow, robust SLAM/SfM, learning-based stitching) and one practitioner tradition (Overmix and its 11-year accumulated lessons). The single biggest finding is that **anime stitching is not a stitching problem with motion noise; it is a frame-selection-conditioned multi-cel reconstruction problem** — Overmix's "Cluster animation" aligner and AnimeInterp's segment-piecewise flow both encode this perspective explicitly, whereas a standard SfM/optical-flow pipeline fights it. Re-architecting ASP's frame selector to operate on cel clusters is likely to do more for the 40.6% fallback rate than any single optical-flow upgrade.

The second finding is that several user-identified bottlenecks have direct off-the-shelf solutions of differing maturity: GNC for bundle adjustment is well-trodden and drops into Levenberg–Marquardt in ~100 lines; OBJ-GSP (AAAI 2025) and SemanticStitch (Visual Computer 2025) directly address the "seam cuts through character" problem; ProPainter (ICCV 2023) handles flow-guided foreground removal/background completion; and SAM-2 (43.8 FPS for Hiera-B+ on a single A100, per Ravi et al. arXiv 2408.00714) supersedes BiRefNet for video-temporal masks. By contrast, deep stitchers (UDIS++, SRStitcher) are NOT directly applicable without retraining because their TPS warps and diffusion priors are tuned to natural-photography parallax, not anime cel-shaded pose mismatch.

The third finding is empirical: **Overmix has independently discovered and shipped many of the techniques the academic literature is now formalising** — median renders, static-difference logo masks, animation clustering, iterative JPEG-aware super-resolution, sub-pixel alignment via integer upscaling, brute-force translational search restricted to a Movement-bounded window. ASP should adopt Overmix's median-fusion and animation-cluster ideas wholesale; both are cheap and orthogonal to the ML upgrades.

---

## Details

### A) AnimeInterp Segment-Guided Matching (SGM) — CVPR 2021, arXiv 2104.02495

AnimeInterp (Li Siyao et al., CUHK / SenseTime / Rutgers, CVPR 2021) targets exactly the ASP's flat-region aperture problem: cel-shaded animation lacks the local texture gradients that standard optical-flow networks rely on. SGM is its first-stage coarse-flow module. The algorithm: (1) **segment** each frame into colour pieces via SLIC-style super-pixelation gated by a Laplacian-of-Gaussian contour detector — every closed region of near-uniform colour becomes one segment; (2) **describe** each segment by a feature vector concatenating colour histogram, segment centroid, segment area, and a deep CNN feature pooled inside the segment; (3) **globally match** segments across frame pairs using a Hungarian-style assignment that minimises an L2 cost in the feature space, with a one-to-many fallback when a region splits across frames; (4) **propagate** a piece-wise flow by assigning every pixel inside a source segment the centroid-to-centroid displacement of its match. The output is a coarse, piece-wise-constant flow field used as initialisation for a Recurrent Flow Refinement (RFR) transformer.

The CVPR 2021 paper reports an overall PSNR gain of 0.34 dB over the best prior method across the full ATD-12K test set, with the supplemental noting that "for specific motion categories e.g. 'Walking', AnimeInterp can improve over 0.4 dB." A dedicated SGM-only ablation on the Hard split is not reported in the published paper; the dB attribution to SGM specifically should be considered unverified until reproduced.

For ASP integration, SGM is the missing primitive for **foreground pose registration on hair, skin, and costume fills**. Pipeline modification: between LoFTR and RAFT, run SGM on the BiRefNet (or SAM-2) foreground crop pair to produce a piece-wise initial flow, then warm-start SEA-RAFT with this flow (SEA-RAFT supports flow initialisation natively). For ARAP control points lying inside flat regions, use the SGM segment-centroid displacement directly rather than the RAFT flow at that pixel. The official reference implementation is at https://github.com/lisiyao21/AnimeInterp; SGM is in `models/sgm.py` and is pure PyTorch with no exotic CUDA. SGM's segmentation step is sensitive to anti-aliasing — Overmix's experience suggests disabling chroma upscaling before segmentation, or using a LineArtDetector pre-process.

**Complexity:** medium (port from public code, plug into existing flow stage). **Expected impact:** large on the aperture problem — should eliminate systematic flow-zero failures on big skin/hair regions, with corresponding gains on ARAP control-point quality and fallback-gate avoidance.

### B) LinkTo-Anime dataset — arXiv 2506.02733 (Feng et al., Macau UST / CUHK, 2025)

LinkTo-Anime is the first ground-truth optical-flow dataset specifically rendered for **cel-shaded anime character motion** (not natural footage, not the synthetic-but-realistic Sintel/Spring). Construction: 22+ open-source 3D character models (Mixamo + Aplaybox), animated with Mixamo skeleton clips, manual model refinement plus toon shading (flat colour fills + ink-line contours), rasterised from multiple viewpoints. Because rendering is from a 3D engine, **pixel-perfect forward/backward optical flow, occlusion masks, and Mixamo skeletons are GT**. The dataset comprises 395 sequences totalling 24,230 training frames, 720 validation, and 4,320 test frames; both coloured and line-drawing variants are provided. The paper benchmarks RAFT, GMA, FlowFormer, and SEA-RAFT and reports that all of them have substantially higher EPE on LinkTo-Anime than on Sintel — confirming a real domain gap.

Recipe for ASP: take a SEA-RAFT-L checkpoint trained on Sintel+FlyingThings; fine-tune on LinkTo-Anime training split for ~50k steps with standard SEA-RAFT loss; freeze the feature pyramid for the first 10k steps to avoid catastrophic forgetting on natural imagery. Evaluate on the LinkTo-Anime test set EPE plus an ATD-12K-derived validation set, plus a held-out subset of the ASP 96-test corpus. The Mixamo skeleton GT is also useful for the pose-consistent frame selector (M).

**Complexity:** low-to-medium. **Expected impact:** medium-large on aperture failures, especially when combined with SGM (A).

### C) Sýkora 2009 full ARAP — and post-2009 improvements

The actual reference is **Sýkora, Dingliana, Collins, "As-Rigid-As-Possible Image Registration for Hand-Drawn Cartoon Animations," NPAR '09** (DOI 10.1145/1572614.1572619; full text https://dcgi.fel.cvut.cz/home/sykorad/Sykora09-NPAR.pdf). **The LSD collinearity term is NOT in the original 2009 paper** — Sýkora 2009 uses only Push (block matching) + Regularise (per-square rigid transform + centroid averaging). The full original algorithm:

1. **Embed** the source image in a coarse square lattice (typically ~16-px squares at PAL resolution) respecting the articulated foreground.
2. **Push phase**: for every lattice point, find the translation `t*` that minimises SAD over a local neighbourhood `N` within search area `M`: `t* = argmin_{t ∈ M} Σ_{p ∈ N} |S(p+t) − T(p)|`. Sýkora uses |N|=16 px, |M|=48 px with the Li–Salari 1995 early-termination heuristic. **No shape constraint** in this step — points move independently.
3. **Regularise phase**: per lattice square, compute the optimal 2D rigid transform via the Schaefer 2006 closed form: `R* = (1/μ) Σ ( p̂ᵢ / p̂ᵢ⊥ ) · ( q̂ᵢᵀ q̂ᵢ⊥ᵀ )`, with `p̂ᵢ = pᵢ − p_c`, `q̂ᵢ = qᵢ − q_c`, and `μ = √( (Σ q̂ᵢ p̂ᵢᵀ)² + (Σ q̂ᵢ p̂ᵢ⊥ᵀ)² )`. Transform each square's points, then **each lattice point is replaced by the centroid of its transformed instances across all incident squares**. Iterate 5–20 times — more iterations smoothly trade local flexibility for global rigidity. As the paper notes: "Initially the shape is flexible but when the number of iterations increases the deformation gradually approaches pure translation."
4. **Stopping criterion**: monitor `d_avg = (1/|P|) Σ ||pᵢ − qᵢ||` (NOT the SAD, which can plateau spuriously during a large non-overlapping deformation). Stop when `d_avg` has not changed materially in 20 iterations.
5. **Extensions** explicitly given in the paper: for similarity transformations replace eq. (4) with `μ = Σ p̂ᵢ p̂ᵢᵀ`; for affine replace `R*, t*` with `A = (Σ p̂ᵢᵀ p̂ᵢ)⁻¹ Σ p̂ⱼᵀ q̂ⱼ`. These are unstable on large displacements and should be used only as final refinement.

**Post-2009 improvements**: **Hao, Chen, Wu 2019, "Efficient PatchMatch-Based Image Registration and Retargeting for Cartoon Animation"** (Springer LNCS, DOI 10.1007/978-3-030-24274-9_58) replaces brute-force block matching in Push with PatchMatch (10–50× speed-up at comparable quality). Where line/collinearity constraints appear in ARAP-cartoon literature is in shape-deformation work (Igarashi 2005, Sorkine-Hornung 2007, "As-rigid-as-possible surface modeling," SGP 2007), not Sýkora's registration line.

**Adding an LSD term to ASP**: detect line segments via DeepLSD (Pautrat et al. ECCV 2022, MIT-licensed, robust on anime ink lines) on both source and target; match line segments by descriptor + endpoint geometry; for each matched line pair `(ℓ_src, ℓ_tgt)` with `ℓ_tgt` having normal `n` and offset `d`, add penalty `λ_lsd · Σ_{pᵢ ∈ ℓ_src} (n · (R* pᵢ + t*) − d)²` to the per-square local solve in the Regularise step. Use `λ_lsd ≈ 0.1` × rigidity weight, tuned on a held-out validation set. A reference implementation of the basic Sýkora algorithm is available via the project page http://dcgi.fel.cvut.cz/~sykorad/deform.html (linked to a TVPaint plug-in).

**Complexity:** medium (the basic Sýkora algorithm is already in ASP; LSD integration is a straightforward additive energy term, but tuning `λ_lsd` requires care). **Expected impact:** moderate — LSD constraints mainly help on **costume edges and prop outlines** that have strong ink lines but flat fills, exactly the case where Push is ambiguous.

### D) Graduated Non-Convexity (GNC) for robust bundle adjustment

The classical reference is **Black & Rangarajan 1996, "On the unification of line processes, outlier rejection, and robust statistics with applications in early vision," IJCV 19(1)**; the modern resurrection is **Yang, Antonante, Tzoumas, Carlone, "Graduated Non-Convexity for Robust Spatial Perception: From Non-Minimal Solvers to Global Outlier Rejection," IEEE RA-L 2020** (arXiv 1909.08605, the canonical reference for GNC-TLS), with **Zach 2014** "Robust bundle adjustment revisited" (ECCV) using a half-quadratic lifting reformulation, and recent refinements **Cho et al. 2023 Adaptive GNC** (arXiv 2308.11444) and **Peng et al. 2023 Efficient GNC for Pose Graph Optimization (riSAM / EGNC-PGO)** (arXiv 2310.06765) which adaptively schedule the non-convexity parameter μ.

Mechanism: parameterise a family of surrogates `ρ_μ(rᵢ)` starting (μ→∞) as the convex quadratic `ρ_∞(r) = r²` and annealed (μ↓) toward a strongly non-convex target — **Truncated Least Squares** (GNC-TLS, `ρ(r) = min(r², c²)`) or **Geman–McClure** (`ρ(r) = r²/(r² + c²)`). The Black–Rangarajan duality gives a closed-form weight `wᵢ(μ)` per measurement; optimisation alternates a weighted nonlinear-least-squares solve (which fits cleanly into LM) with a weight update `wᵢ ← argmin_w [w · rᵢ² + Φ_μ(w)]`. For Geman–McClure this evaluates to `wᵢ = (μ·c² / (μ·c² + rᵢ²))²`. Anneal μ multiplicatively (factor 1.4–2.0 per outer iteration).

For the ASP translation-only bundle adjustment: replace residual pruning with a per-edge GNC weight `wᵢⱼ` on each LoFTR correspondence. (1) initialise `μ₀` such that `2μ₀c² ≥ max(rᵢ²)` — the initial problem is effectively convex; (2) at each outer iter, do one LM step on the weighted problem `Σ wᵢⱼ rᵢⱼ²`; (3) update `wᵢⱼ` in closed form; (4) divide μ by 1.4; (5) terminate when `‖Δx‖ < tol` or `μ < μ_min`. Set `c ≈ 3σ`; Yang et al. recommend `c = 1.0` for normalised pixel coordinates with `σ ≈ 0.3 px`. This robustly handles the "bad LoFTR match within 3× median" pathology — at low μ the bad match gets `w ≈ 0` automatically. Reference implementation: TEASER++ (https://github.com/MIT-SPARK/TEASER-plusplus) ships a GNC solver in C++/Python; riSAM is in GTSAM.

How it compares to alternatives: Huber/Cauchy/trimmed-LS use a fixed kernel, so they cannot recover from a bad initialisation if it sits in a flat-residual region; GNC's continuation explicitly avoids this. Compared to RANSAC, GNC is a global optimiser without sampling cost and tolerates 70–80% outliers per Yang et al.'s spatial-perception benchmarks.

**Complexity:** low (~100 lines on top of existing LM). **Expected impact:** medium — directly fixes the "bad match within 3× median" pathology and should reduce catastrophic-alignment failures by an order of magnitude.

### E) Ghost-free HDR and dynamic-scene stitching

Three paradigms dominate: **(1) Alignment-then-rejection / patch-based** — Sen et al. 2012, "Robust Patch-based HDR reconstruction of Dynamic Scenes" (ACM TOG 31(6) #203), iteratively aligns patches and rejects those whose photometric error exceeds an adaptive threshold; **(2) Flow-warp-then-fuse** — Kalantari & Ramamoorthi 2017, "Deep HDR Imaging of Dynamic Scenes" (ACM TOG 36(4)), uses optical flow to warp non-reference exposures to the reference then a CNN fuses; **(3) Generative / transformer attention** — Niu HDR-GAN, Liu et al. CA-ViT 2022 ("Ghost-free HDR Imaging with Context-aware Transformer," ECCV 2022), and Prabhakar et al. SHDR 2022 ("Segmentation-Guided Deep HDR Deghosting," arXiv 2207.01229) which segment motion regions with a CNN and merge static vs. dynamic regions with separate fusion networks.

The most directly relevant paradigm for ASP is the **segmentation-guided deghosting** (Prabhakar SHDR), because it mirrors ASP's BiRefNet foreground / temporal-median background architecture. The lesson is structural: **fuse static and moving regions with different rules**. Sen-style patch alignment is brittle at large pose gaps; Kalantari-style flow-warp is closest to current ASP but breaks at large displacements (exactly the ASP failure mode); generative is robust but trained on photographic LDR data and needs anime retraining.

Recommendation: borrow SHDR's partition strategy — SAM-2 segments the character, temporal-median fuses the background (already done), but moving-region rule should be **single-frame-pick rather than blend**. This is structurally identical to the user's "single-pose graph-cut selection" idea and is what Overmix's Cluster animation aligner does implicitly.

**Complexity:** medium (architectural). **Expected impact:** large — directly addresses ghosting.

### F) UDIS / UDIS++ / NIS / SRStitcher — unified deep stitchers

**UDIS** (Nie et al., IEEE TIP 2021); **UDIS++** (Nie et al., ICCV 2023, arXiv 2302.08207, code https://github.com/nie-lang/UDIS2) jointly learns (a) a coarse global homography, (b) a local thin-plate-spline warp with control points jointly optimising alignment + shape preservation, (c) an unsupervised seam-driven composition mask. **SRStitcher** (Xie et al., NeurIPS 2024, arXiv 2404.14951) reformulates fusion + rectangling as a **single inpainting task** driven by a frozen pre-trained Stable Diffusion model with weighted attention masks — no training of any new model. **NIS** is an umbrella term covering several 2022–2024 variants (notably Kim et al.). The 2024 follow-up RDIStitcher (arXiv 2411.10309) self-supervises a reference-driven inpainting variant on UDIS-D.

These are **not directly applicable to anime without retraining**: UDIS++'s TPS warp encodes natural-photo parallax priors, not cel-shaded pose mismatch; SRStitcher's diffusion prior hallucinates photographic textures into flat regions. Adopt selectively: (a) UDIS++'s **joint alignment + distortion loss** formulation (`L = L_align + λ · L_distortion` where `L_distortion` is the TPS bending energy plus a similarity-preservation prior on grid corners) to regularise ASP's foreground warp; (b) SRStitcher's idea of using a generative prior **only at the seam region** rather than for the whole composition — a precise replacement for the current Laplacian/DSFN seam blend in the foreground, using ToonCrafter (K) as the generator instead of Stable Diffusion.

**Complexity:** high if wholesale; low if borrowing the loss formulation. **Expected impact:** low-medium unless retrained.

### G) StabStitch / StabStitch++ — online video stitching with bidirectional warps

**StabStitch** (Nie et al., ECCV 2024, arXiv 2403.06378) and **StabStitch++** (Nie et al., TPAMI 2025, DOI 10.1109/TPAMI.2025.3568829, arXiv 2505.05001, code https://github.com/nie-lang/StabStitch2) target the "warping shake" problem: per-frame independent stitching warps look jittery when chained into video. Contributions: (1) a **virtual midplane bidirectional warp** — rather than warp image A to image B, project both onto a virtual middle plane via a differentiable bidirectional decomposition of the homography, evenly spreading projective distortion; (2) a stitching-trajectory formulation analogous to video-stabilisation camera-path smoothing, with a warp smoothing model that jointly encourages content alignment, trajectory smoothness, and online operation; (3) a hybrid loss that — unlike StabStitch which sacrificed alignment for stability — optimises both.

For ASP this is the right framework for **horizontal/diagonal scrolls and seam-to-seam jitter**. The bidirectional midplane warp formalises ASP's existing "symmetric midpoint warping" idea. Missing in ASP is **temporal smoothing**: ASP currently solves each strip seam in isolation, whereas StabStitch++ solves an L1-trend-filter on the warp trajectory across all strips simultaneously.

Integration: (a) reformulate BA to estimate a single 2-D translation trajectory `T(t)` for the camera across all input frames, then derive per-strip-pair warps from differences along `T(t)`; (b) regularise `T(t)` with `‖∇²T‖₁` — anime pans are usually piecewise-constant velocity by design; (c) bidirectional midplane projection eliminates the asymmetric distortion of the current "warp one strip to neighbour" approach.

**Complexity:** medium. **Expected impact:** medium, particularly large on diagonal-scroll bottleneck.

### H) JamMa (CVPR 2025) and EDM (ICCV 2025) — feature matching

**JamMa** (Lu & Du, CVPR 2025, arXiv 2503.03437, code https://github.com/leoluxxx/JamMa) replaces LoFTR's quadratic-cost Transformer with a Joint Mamba state-space model using a JEGO scan-merge strategy (Joint scan, Efficient skip steps, Global receptive field, Omnidirectional). Achieves better-than-LoFTR matching accuracy at <50% parameters and FLOPs, converging on a single GPU.

**EDM** (Li, Rao, Pan, ICCV 2025 Highlight, arXiv 2503.05122, code https://github.com/chicleee/EDM) revisits the entire detector-free matching pipeline: a deeper-but-thinner CNN backbone, a Correlation Injection Module that progressively injects feature correlations from global-to-local during multi-scale aggregation, and a **lightweight bidirectional axis-based regression head** that directly predicts sub-pixel correspondences without explicit keypoint heatmap localisation.

Both target efficiency-accuracy Pareto improvement vs. LoFTR/EfficientLoFTR/RoMa on ScanNet/MegaDepth/HPatches. Neither paper reports anime/cel-shaded benchmarks. JamMa's higher-receptive-field Mamba scan should help in flat regions (the matcher needs global context to disambiguate "this skin patch is on the shoulder vs. on the elbow"). EDM's bidirectional sub-pixel head is attractive for ASP because translation-only BA is sensitive to sub-pixel matching accuracy.

For ASP: **try EDM as a drop-in replacement for LoFTR**. The interface is essentially identical (image pair → correspondences with confidences). Re-run the benchmark; if EDM matches more flat-region points, GNC-BA (D) will produce tighter translations.

**Complexity:** low (drop-in). **Expected impact:** low-medium — bottleneck is not LoFTR's accuracy but its inability in flat regions, which neither paper directly addresses.

### I) DSFN / SemanticStitch / OBJ-GSP — semantic seam-finding

**OBJ-GSP** (Cai & Yang, AAAI 2025, arXiv 2402.12677, code https://github.com/RussRobin/OBJ-GSP) leverages SAM to extract object contours from both images, then constructs **triangular meshes within each object** during warping. The warp lets each object's mesh balance projective and similarity transformations, keeping object shapes intact. Authors release **StitchBench** (https://huggingface.co/datasets/RussRobin/StitchBench).

**SemanticStitch** (Jin et al., arXiv 2511.12084, The Visual Computer 2025, DOI 10.1007/s00371-025-04222-y, code https://github.com/Pokerman8/OAIV-Coherence) is the most directly relevant for the ASP seam-cutting issue: a deep learning framework with a **novel loss function that emphasises the semantic integrity of salient objects**, preventing seams from crossing them. The paper explicitly identifies the failure mode of traditional seam carving as "neglecting semantic information, causing disruptions in foreground continuity" — exactly the user's complaint. Two specialised real-world datasets are released.

**DSFN (NeurIPS 2025)** referenced in the user's prompt could not be conclusively identified in the gathered literature. The closest 2025 candidates are SemanticStitch and OBJ-GSP, both covered above. If DSFN refers to a specific paper the user has direct access to, its details should be verified independently.

For ASP, keep the graph-cut formulation but add: (a) **OBJ-GSP-style triangular-mesh shape-preservation prior** on the BiRefNet/SAM-2 foreground (let the foreground triangular mesh balance similarity-vs-projective in the warp); (b) **SemanticStitch-style hard barrier** in the seam cost — set the cost of cutting through any pixel inside a SAM-2 foreground mask to ~10⁶× the photometric cost, forcing the graph-cut to route around the character. Where the seam **must** cross the character (vertical pan, character occupies full strip width), don't seam-blend at all — pick the single best frame for that strip column (combine with F + M).

**Complexity:** low (cost-term modification + SAM-2). **Expected impact:** medium-large on the character-cutting issue.

### J) SAM-2 for foreground segmentation

SAM-2 (Meta AI, **Ravi et al. arXiv 2408.00714**, code https://github.com/facebookresearch/sam2) replaces SAM's per-image inference with a streaming-memory transformer that propagates a per-session memory across video frames. Per the official paper, "SAM 2 based on Hiera-B+ and Hiera-L runs at real-time speeds of **43.8 and 30.2 FPS, respectively**" on a single A100. Promptable with point/box/mask prompts; supports multi-object tracking; handles object occlusion and reappearance via the memory bank. Trained on **SA-V, consisting of 51K diverse videos and 643K high-quality spatio-temporal segmentation masks (masklets)** — predominantly photographic content.

For anime, SAM-2 quality varies. The official paper does not benchmark anime, and SA-V is photographic. Community experience (Roboflow's analysis blog at https://blog.roboflow.com/sam-2-video-segmentation/, multiple user threads) shows that SAM-2 handles **clean cel-shaded characters with strong outlines extremely well** — the contours are exactly the kind of edge prior SAM was designed to follow. Where SAM-2 underperforms BiRefNet is on (a) characters with translucent effects (hair tips, magical glows), (b) frames with heavy motion blur. The temporal-propagation advantage is large: a single bbox/click on frame 1 propagates a consistent mask across the entire pan, eliminating per-frame mask jitter that creates seam-pixel inconsistencies in ASP's current per-frame BiRefNet.

Concrete recommendation: **replace BiRefNet with SAM-2 video predictor**, prompted with a single bounding box on the first frame (extracted via BiRefNet → bbox or user click). Use SAM-2 masks both for foreground/background decoupling and for the seam-cost barrier (I). For translucent failures, fall back to SAM-2 ∪ BiRefNet union mask.

**Complexity:** low. **Expected impact:** medium — primarily improves mask temporal consistency.

### K) ToonCrafter — generative midpoint frame synthesis

**ToonCrafter** (Xing et al., SIGGRAPH Asia 2024 Journal Track / ACM TOG 43(6), arXiv 2405.17933, code https://github.com/Doubiiu/ToonCrafter) is a generative cartoon-interpolation model that **transcends correspondence-based interpolation**. It adapts live-action image-to-video diffusion priors (DynamiCrafter-style) to the cartoon domain via: (1) a **toon rectification learning** strategy that closes the live-action → cartoon domain gap without content leakage; (2) a **dual-reference-based 3D VAE decoder** using both endpoint frames as references to preserve detail; (3) sparse sketch guidance for user control. The official GitHub repo specifies inference cost of **"~24G & 24s (perframe_ae=True)"** for the 320×512 ToonCrafter_512 model at 50 DDIM steps on A100.

For ASP, ToonCrafter is the right tool for **the residual-ghosting bottleneck at large pose gaps**. Use case: when two adjacent strips show the character in detectably different poses (mouth open vs. closed, eyes open vs. closed) and ARAP cannot bridge the gap without ghosting, **synthesise an intermediate frame conditioned on the two adjacent strips' character crops** and use it as the seam region. The two strips become source/target conditioning, ToonCrafter generates the in-between frame for the seam location, and the seam transitions to the synthesised content rather than blending mismatched poses.

Caveats — the authors' own README explicitly warns: "*due to the variety of generative video prior, the success rate is not guaranteed.*" This is a **fallback for hard cases**, not a default — render-quality gating (LPIPS or CLIP similarity to input strips) is mandatory. The 24-s per-midpoint inference cost on A100 means it's reserved for the ~40% of datasets currently triggering fallback.

**Complexity:** medium-high (integration plus quality gating). **Expected impact:** large on the fallback subset — could convert the current "give up" fallback into a "generative completion" path.

### L) VidPanos and ProPainter — background completion

**VidPanos** (Ma et al., SIGGRAPH Asia 2024, arXiv 2410.13832, project https://vidpanos.github.io/) tackles a problem strikingly similar to ASP's: synthesising a panoramic video from a casually-captured panning video. Their approach is **space-time outpainting**: project the input video onto a panoramic canvas, then condition Lumiere (a diffusion video model) and/or Phenaki (token-based) to inpaint the unknown space-time volume. They demonstrate results on people, vehicles, and flowing water; test videos and benchmark colab are released. The relevant architectural insight: VidPanos explicitly **does not** try to register the foreground; it **synthesises** complete dynamic foreground in panoramic space.

**ProPainter** (Zhou et al., ICCV 2023, arXiv 2309.03897, code https://github.com/sczhou/ProPainter) is a video-inpainting model based on dual-domain (image + feature) flow-guided propagation plus a mask-guided sparse video Transformer. Per the paper: "a highly efficient recurrent network to complete flows for dual-domain propagation, which is over 40 times (∼192 fps) faster than SOTA method." It outperforms FuseFormer/FGT by 1.46 dB PSNR.

ProPainter vs. VidPanos: ProPainter is **lighter, deterministic, and doesn't hallucinate** — it only propagates what's already in the video, ideal for completing the background after foreground masking. VidPanos's generative prior is overkill for ASP and risks hallucinating spurious content into flat-colour anime backgrounds.

Recommendation: **use ProPainter, not VidPanos**, for the background pass. Pipeline: (1) SAM-2 foreground mask per frame; (2) align frames with translation-only BA; (3) project to panoramic canvas with foreground masked out; (4) ProPainter on the masked panoramic video to complete the background; (5) collapse the temporal axis with the existing temporal-median.

**Complexity:** medium. **Expected impact:** medium — improves background quality, indirectly improves seam quality because the median pass currently bleeds foreground residuals.

### M) Pose-consistent frame selection

Three threads in the literature: (1) **HDR reference frame selection** — Sen et al. 2012, Hu et al. 2013 — exposure + motion-stability heuristics; (2) **Video mosaicking keyframe selection** — Brown & Lowe 2007 maximise overlap subject to a min-displacement constraint; (3) **Pose embedding approaches** — HRNet/ViTPose for natural images; for anime, work like AnimePose / cartoon-specific keypoint estimators, or the Mixamo skeleton outputs from LinkTo-Anime (B).

The ASP-specific recipe should combine three signals into a multi-objective selector:
1. **Camera-motion magnitude**: phase correlation, but only on the **background-masked** image (subtract the SAM-2 foreground before phase correlation), so character animation doesn't pollute the displacement estimate.
2. **Pose-consistency score**: extract a character pose embedding per frame and cluster frames so all selected belong to the same cluster — this is exactly what Overmix's Cluster animation aligner does with a simpler frame-difference signal (see O). Stronger version: ViTPose-Base finetuned on AnimePose data, or alternatively the Sýkora 2009 Push residual against a reference frame as a pose-distance proxy.
3. **Foreground-crop SSIM / mutual information** between adjacent frame candidates — high SSIM = same animation state.

The selector solves: for each strip column, pick the frame from a candidate window that maximises `(foreground-SSIM with neighbouring selections) − λ · (background-displacement penalty)`. This is a shortest-path problem on a DAG (frame × column → cost), solvable in O(NC·k²) by standard DP.

**Complexity:** medium. **Expected impact:** large — this is one of the two changes most likely to move the 14.5% / 40.6% benchmark numbers, because the fallback gate fires precisely when poses are inconsistent.

### N) Horizontal/diagonal scrolls — multi-directional camera motion

Two paradigms: (1) **APAP / Moving DLT** (Zaragoza et al. CVPR 2013) does locally-adaptive 2D warps that handle non-axis-aligned motion natively, by estimating per-cell homographies weighted by spatial proximity; (2) **Pushbroom / X-slits** (Zomet et al. 2003, Seitz & Kim 2003) for line-camera-style multi-perspective panoramas — strictly more general than perspective panoramas, especially for long pans.

For ASP the fundamental fix is simpler: **generalise the translation-only bundle to estimate (tx, ty) per frame** rather than a single scrolling axis. The vertical-dominant assumption shows up in (a) phase correlation projecting onto the vertical axis (fix: full 2D phase correlation, area M); (b) strip seam logic assuming horizontal seams (fix: orient seams perpendicular to the estimated camera-motion direction per pair); (c) the median-background renderer assuming each pixel is covered by many frames (fix: handle 2D coverage; ProPainter inpaints any remaining holes — L). StabStitch++'s bidirectional midplane warp (G) is the natural temporal-smoothness regulariser for the 2D trajectory.

For rotation/scale, Sýkora 2009 itself notes the closed-form similarity/affine extensions. Overmix's April 2024 issues #160–163 confirm that even mature anime stitchers haven't solved rotation/scale; for ASP, translation + small rotation is probably sufficient — augment the LM state with a global rotation per frame, with a strong prior toward zero.

**Complexity:** low-medium. **Expected impact:** medium — fixes the entire diagonal-pan failure class.

### O) Overmix — practitioner lessons (the empirically richest source)

Overmix (spillerrec, GPL-3.0, https://github.com/spillerrec/Overmix; **208 stars** on the spillerrec/Overmix GitHub repository per the github.com/spillerrec profile page; stable v0.3.0 from June 2015, v0.4.0-alpha through May 2024) is the closest existing analogue to ASP. The design philosophy from the README: "*The idea behind Overmix is to increase the amount of images which is used to stitch it together, and use this to solve MPEG compression, color banding and on-screen text/logo issues.*" Unlike Hugin (2–3 photos), Overmix consumes **every** frame of a panning shot and treats stitching as a multi-frame reconstruction / super-resolution problem — a perspective ASP should fully embrace.

**Alignment algorithm.** Overmix does **not** use SIFT/SURF/phase-correlation. It uses a brute-force translational SAD/SSD search over a bounded window, restricted to translation only (no rotation/scale until issues #160/161, both open as of April 2024). Three aligner strategies (from the Merging-options wiki):

- **Ordered (default)** — "Aligns one image at a time, and rendering the full image each time to align against … Approx. O(n²)."
- **Recursive** — "Aligns images using a divide and conquer strategy, in the same manner as merge sort … Approx. O(n·log(n))."
- **Animated** — separates animated frames before aligning (see below).

An optional **"Use Edges"** mode aligns on a Sobel edge map; the author calls it "*mostly just there for experimentation.*" A **Movement slider** caps the maximum permissible offset, bounding the search window. Open issue #170 (May 2024) "Implement log-polar transform for Fourier images" confirms that even Overmix considers phase-correlation an unrealised TODO, not the current default.

**Sub-pixel precision** is achieved by integer-upscaling images before alignment (typically 2–4×). Author blog: "*To detect the sub-pixel alignment afterwards, the images were upscaled to 4x their size and ordinary pixel-based alignment was used.*" v0.3.0 added a memory optimisation where the Recursive aligner upscales only as needed.

**Foreground/background separation (the Animated aligner)** exploits anime's reduced frame-rate ("on twos"/"on threes"): typically 3 video frames share one drawn cel. The algorithm computes the **pixel-difference between consecutive aligned frames** — static spans yield low difference, animation transitions yield spikes. A horizontal threshold line is fit to "intersect as many blue lines as possible," segmenting frames into clusters where each cluster corresponds to one drawn cel (blog post "Animated stitches," Nov 2014, https://spillerrec.dk/2014/11/animated-stitches/). Each cluster is then stitched independently. The newer **"Cluster animation" WIP frame-separation algorithm** (v0.4.0-alpha) refines this with proper clustering rather than a single global threshold.

**This is the algorithm ASP should adopt for frame selection (M)**, but with two ASP-specific improvements: (a) compute the frame difference on **background-subtracted** images (using SAM-2 foreground), so character animation doesn't pollute the camera-motion signal — the opposite of Overmix, which uses the difference itself as the animation signal; (b) use **both** signals: background-difference for camera-motion estimation, foreground-difference clustering for pose-consistent selection.

**Rendering operators** (from the Rendering-options wiki and v0.4.0 release notes):

- **Average** (default, per-pixel mean — smooths compression artifacts but slightly blurs hard edges from sub-pixel misalignment).
- **Subpixel** (non-linear interpolation respecting sub-pixel positions — slow, experimental, still blurs slightly).
- **Difference** (debug — gamma-amplify to detect misalignment).
- **Static Difference** (detects pixels static across all frames → grayscale mask, used for TV logos / credits via the iterative algorithm at https://spillerrec.dk/2013/12/logo-detection-and-removal/).
- **Dehumidifier / Min** (picks the darkest pixel — "minimizes the effect of moving steam and rain," https://spillerrec.dk/2013/11/too-much-steam-in-your-anime/).
- **Statistics render** (v0.4.0; unifies median/difference/min/max — **Median is robust to outlier-pixel artifacts without blurring**).
- **Estimator** (iterative super-resolution-style).
- **Jpeg estimator** (`JpegRender.cpp` — iterative JPEG-aware reconstruction: starts from average, repeatedly DCTs the estimate within each input's 8×8 grid and replaces quantised coefficients matching the observation; recovers detail averaging loses — https://spillerrec.dk/2015/08/minimizing-jpeg-artifacts/).

**ASP should adopt: (a) Median render for background, (b) Jpeg-aware iterative refinement as a quality post-step** — anime sources are heavily MPEG-compressed and this recovers detail at no algorithmic risk.

**The "Average render with skip and offset" decensoring technique** (v0.4.0, https://spillerrec.dk/2015/07/removing-mosaic-censor/) builds an HR canvas and plots only the centre pixel of each mosaic tile at its corresponding HR location. Tile pitch and centre offset are the "skip and offset" parameters. Demonstrates that the multi-frame reconstruction perspective generalises in non-obvious ways.

**Pre/post processing wisdom** (Pre/Post wiki): IVTC de-telecine (better on YUV), **Richardson–Lucy deconvolution** ("Deviation 0.6–0.7, ~10 iterations") for slight blur removal, Lanczos scaling, GIMP-style level. ASP should add Richardson–Lucy as a quality post-step.

**Hi10p frame extraction.** Overmix ships a separate `dump-tools` repo (https://github.com/spillerrec/dump-tools) for extracting unique frames from 10-bit YUV video without lossy 8-bit conversion. README warning: "*VLC in particular causes bad results, but mpv can also cause screenshots to be in lower quality than what you see on the screen.*" If ASP currently uses mpv/VLC screenshots, switching to a 10-bit extractor improves input quality before any algorithm runs.

**Documented failure modes** (issues + wiki):
- **#40**: alpha/transparent regions during 2-D motion — transparent areas treated as black, pulling alignment off.
- **Lightness/brightness changes** cause visible horizontal bars in averages; only workaround is a hand-made gradient alpha mask. **No automatic exposure correction yet** — ASP should add per-frame histogram-match to the rolling median.
- **#3**: Dehumidifier handles YUV color incorrectly.
- **#19**: Recursive aligner with very large movements — movement window should adapt per recursive level.
- **Brute-force cost ambiguous on flat colour regions** — Movement slider must be tightened. **Directly confirms the user's aperture problem.**
- **#155**: line artifacts at frame boundaries with black-border columns (long-standing).
- **#170 (May 2024)**: log-polar Fourier registration proposed, not implemented.
- **#160–163 (April 2024)**: rotation/scaling support, all open.
- 2017 user comment: "*works nicely well for non moving images but can't seem to get it to work on anime images that have the view moving around*" — spillerrec replies "*the aligning method isn't perfect and might require you to mess with the settings.*"

**Community workarounds**: always dump via Overmix's built-in importer (not external screenshots); for 2-D pans enable both V+H, Precision ≥ 2–3×, Chroma-upscale; for animated chars use Animated/Cluster aligner accepting multi-cel; brightness mismatch → hand-made gradient alpha mask; TV logos → Static Difference → binarize → Use as mask → Average; steam/rain → Min/Dehumidifier; severe JPEG/MPEG noise → iterative JpegRender or waifu2x preprocess; 50+ frames → Recursive aligner.

**Project status caveat**: v0.3.0 stable is from June 2015; v0.4.0 has been "alpha" since September 2018. Cluster animation is explicitly WIP. The practitioner community has **not** converged on a solution — genuine room exists for ASP to advance the state of the art.

**Complexity:** low (most are tuning/config + small re-implementations). **Expected impact:** large in aggregate.

### P) Other practitioner tools and community lessons

Outside Overmix the landscape is sparse:
- **Hugin** (https://hugin.sourceforge.io/) — natural-photo panoramic stitcher with manual control-point tagging; anime users report ~50% success rate on static backgrounds with a manual masking step to remove characters before stitching.
- **ImageMagick** — `convert -evaluate-sequence median` for naive multi-frame fusion. Poor-man's Overmix without sub-pixel alignment.
- **AviSynth / VapourSynth MVTools2** — some users repurpose motion vectors for stitching alignment; not robust.
- **Fan community workflows** (r/anime, MyAnimeList forums, /a/ stitch threads): consensus is (a) extract via mpv or AvsP at 10-bit when possible, (b) Overmix or manual Photoshop layering with motion-aware masking, (c) for character-heavy pans, just pick the "best" pose frame and clone-stamp the missing background — the same single-pose-pick idea ASP is converging on.

Empirical bottom line: no fan tool except Overmix has serious algorithmic depth, and ASP already exceeds Overmix's algorithmic sophistication. **The community lesson is structural**: the manual workflow is "pick one frame per region; layer in Photoshop." ASP should automate exactly this — single-frame-pick + background completion + character single-pose selection — rather than chasing seamless blending.

**Complexity:** N/A. **Expected impact:** N/A (informational).

### Q) PaintBucket-Character and ATD-12K datasets

**ATD-12K** (AnimeInterp paper, CVPR 2021): 12,000 high-quality animation triplets (frame_t, frame_t+1, frame_t+2) curated from professional animation studios; the middle frame is interpolation ground truth. Test set split into Easy / Medium / Hard by motion magnitude and occlusion difficulty, with motion-category annotations. The de-facto benchmark for anime interpolation.

**PaintBucket-Character (PBC)** (Dai et al., "Learning Inclusion Matching for Animation Paint Bucket Colorization," CVPR 2024, arXiv 2403.18342, code https://github.com/ykdai/BasicPBC; follow-up arXiv 2410.19424): 22 character models from Mixamo and Aplaybox, rendered in Cinema 4D with **anti-aliasing disabled** to mimic real paint-bucket animation data. Provides rendered line arts, colorised counterparts, **shading annotations**, and **color design sheets** with semantic labels per colour. The rendering-to-line-art process produces clean, fully-closed contours with clearly separable semantic parts — easier to segment than hand-drawn line art.

For ASP, both datasets are useful primarily for **training/validation**:
- ATD-12K is the standard benchmark for SGM/RFR-style anime optical flow — use it to validate any SEA-RAFT fine-tune (B).
- PBC provides **segment-level GT correspondences** that can be used as a stronger training signal for SGM and for a SAM-2 anime fine-tune (J). The shading annotations are also useful for training a shading-aware mask distinguishing character body from cast shadow.

Combine with LinkTo-Anime: pretrain on LinkTo-Anime (largest, geometry-correct), fine-tune on ATD-12K (real animation distribution), evaluate on both.

**Complexity:** low-medium. **Expected impact:** medium — supporting data for module training.

---

## Recommendations

**Phase 1 (highest-impact, lowest-complexity — implement first):**
1. **Frame selection redesign** (M + O). Phase correlation on background-subtracted images (SAM-2 mask out foreground first). In parallel, cluster frames by Overmix-style Animated-aligner pixel-difference, restricted to foreground regions, to identify cel groups. DP-solve for the optimal frame per strip column maximising foreground SSIM continuity. **Threshold to revisit:** if the fallback rate stays above 25% after this change, escalate to ToonCrafter midpoint synthesis (K).
2. **GNC bundle adjustment** (D). Replace residual pruning with Geman–McClure-surrogate GNC, μ schedule 1.4× per outer iter. **Threshold:** if catastrophic alignment failures persist, switch from translation-only to translation+rotation BA (N).
3. **Median fusion + JPEG-aware refinement** for background (O). Re-implement Overmix's `JpegRender.cpp` algorithm (GPL — code not linkable; algorithm re-implementable).
4. **SAM-2 replacement for BiRefNet** (J). One bbox prompt on the first frame; use the video predictor for temporal-consistent masks (43.8 FPS on Hiera-B+ / A100).

**Phase 2 (medium-complexity, large-impact):**
5. **AnimeInterp SGM + LinkTo-Anime-finetuned SEA-RAFT** (A + B). Segment-piecewise initial flow + flat-region-aware refinement, applied only inside the SAM-2 foreground mask. Validate on ATD-12K + LinkTo-Anime + held-out ASP corpus.
6. **OBJ-GSP + SemanticStitch seam routing** (I). Hard barrier on foreground mask in graph-cut + triangular-mesh shape prior on character.
7. **Sýkora 2009 full ARAP + DeepLSD collinearity** (C). Add line-collinearity energy term with λ_lsd ≈ 0.1 × rigidity weight; tune on a 20-clip validation set.
8. **ProPainter background completion** after foreground masking (L).

**Phase 3 (high-complexity, fallback-only):**
9. **ToonCrafter midpoint synthesis** (K) for cases where Phase-1 frame selection still detects pose inconsistency at the seam. Gate output by LPIPS to the input strips. Budget ~24 s/midpoint at 320×512 on A100.
10. **StabStitch++ bidirectional midplane warp + 2D trajectory smoothing** (G + N). Re-architect bundle adjustment to estimate (tx, ty)(t) as a smooth trajectory rather than per-pair translations.

**Decision thresholds:**
- If Phase 1 raises ASP-beats-naive from 14.5% to ≥35% and lowers fallback from 40.6% to ≤25%, Phase 2 is justified.
- If after Phase 2 the residual failures concentrate in "character moves between strips," Phase 3K (ToonCrafter) becomes critical; if they concentrate in "diagonal pan failed," Phase 3 (N + G) is critical.
- If after Phase 1 the failures concentrate in "alignment crashes/drifts," try EDM (H) as a drop-in LoFTR replacement before any deeper changes.

**Do not adopt:**
- UDIS++/SRStitcher wholesale without retraining (F) — domain mismatch with anime cel-shaded content.
- VidPanos for background (L) — generative overkill; ProPainter is the right tool.
- JamMa over EDM (H) — EDM has the bidirectional sub-pixel head that translation-only BA actually benefits from.

---

## Caveats

- The 14.5% / 40.6% benchmark numbers depend on the 96-clip test corpus; the recommendations assume it is representative. A small-scale ablation on Phase 1 changes alone should be run before committing to Phase 2/3.
- **ToonCrafter is non-deterministic**. The authors' README explicitly warns: "*due to the variety of generative video prior, the success rate is not guaranteed.*" LPIPS or CLIP-similarity quality-gating is mandatory.
- **SAM-2's mask quality on anime is not officially benchmarked** — community reports are positive on clean characters but mixed on translucent effects. A 20-clip validation against BiRefNet is recommended before full replacement.
- **GNC convergence depends on μ scheduling**: too-fast annealing collapses to local minima; the Yang et al. 2020 schedule (1.4× per outer iter) is a safe default but should be re-tuned for the specific BA Jacobian.
- **Overmix is GPL-3.0**; algorithmic ideas may be re-implemented but code may not be linked into a non-GPL ASP.
- **The Sýkora 2009 paper does NOT include the LSD collinearity term** the user assumes — that term must be added as a novel extension. DeepLSD is MIT-licensed and integrates cleanly.
- **LinkTo-Anime is 3D-rendered**, not hand-drawn; flow models fine-tuned on it may not perfectly transfer to genuinely hand-drawn anime. Cross-validate on ATD-12K (real animation studio frames) to catch this.
- **The "SGM raises PSNR by 0.6–1.0 dB on ATD-12K Hard"** ablation cited in earlier drafts is **not confirmed by the CVPR 2021 paper** — the paper reports an overall PSNR gain of 0.34 dB over the best prior method across the full ATD-12K test set, with the supplemental noting "for specific motion categories e.g. 'Walking', AnimeInterp can improve over 0.4 dB." A dedicated SGM-only-vs-RFR-only ablation on the Hard split was not located; treat any per-module attribution as needing reproduction.
- **Several "2025" references** (StabStitch++, JamMa, EDM, OBJ-GSP, SemanticStitch, LinkTo-Anime) are recent enough that public benchmarks beyond the original papers' claims are limited; reported numbers should be independently reproduced before relied upon.
- The **DSFN (NeurIPS 2025)** seam-finding method referenced in the user's prompt could not be conclusively identified in the gathered literature — the closest 2025 candidates are SemanticStitch and OBJ-GSP. If DSFN refers to a specific paper the user has direct access to, its specifics should be verified independently.