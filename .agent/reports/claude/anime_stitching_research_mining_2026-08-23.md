# Research mining: 2D Anime Frame Stitching guide + bibliography + new vendor submodules — 2026-08-23

Sources read in full: `docs/moon/research/2D Anime Frame Stitching.md` (365 lines,
content ends ~line 178, rest is citation list + embedded image blobs — no
further substance past that); `docs/moon/bibliography/pami14.pdf` (confirmed:
Zaragoza et al., *As-Projective-As-Possible Image Stitching with Moving DLT*,
the APAP paper); `docs/moon/bibliography/2302.08207v2.pdf` (confirmed: Nie et
al., *Parallax-Tolerant Unsupervised Deep Image Stitching*, UDIS++/UDIS2);
`docs/moon/bibliography/download.pdf` (confirmed: Zhang et al. 2009,
*Vectorizing Cartoon Animations*, TVCG — the trapped-ball segmentation paper
research.md cites); `docs/moon/bibliography/photomontage.pdf` not read in
depth — title-confirmed as Agarwala et al. *Interactive Digital Photomontage*,
which is the graph-cut/Min-Cut seam formulation ASP's Stage 7 seam cut
**already implements**; nothing new there. Vendor READMEs read for
`vendor/APAP`, `vendor/MoVerse`, `vendor/UDIS2`.

## Setup problem, not a research idea

**`vendor/APAP` is not the APAP repo.** `diff -rq` against `vendor/UDIS2`
shows identical content (only `.git` differs) — it's a duplicate clone of
UDIS2, not `EadCat/APAP-Image-Stitching` (the actual Python/OpenCV Moving-DLT
implementation research.md cites, ref #12). Flag this to Harbinger; nothing
below depends on fixing it, but the real APAP repo isn't actually vendored
yet.

## Ranked ideas (impact × feasibility, my judgment)

### 1. Trapped-ball segmentation for background-plate masking (Vectorizing Cartoon Animations, Zhang 2009)
**Stage:** Stage 4 (replaces or supplements BiRefNet mask generation).
**Targets:** crop loss, `no_valid_edges`/`disconnected_edge_graph` caused by
BiRefNet mask noise on flat-cel-shaded regions, and indirectly the content-
plausibility problem (a cleaner, more complete background plate makes every
downstream signal — matching, blending, content checks — more reliable).
**Why it's different from what's already tried:** BiRefNet is a general
learned foreground segmenter; trapped-ball is deterministic, animation-
specific, and explicitly designed to work even when line art has gaps
(unlike naive edge-based masks) — exactly ASP's chroma-subsampling/
compression-artifact problem (research.md §"Video Compression and Chroma
Subsampling"). This paper's specific contribution over the earlier Sýkora
trapped-ball method is robustness to *imperfect, non-closed* outlines, which
is the anime-video (not clean vector art) case ASP actually faces. It also
reconstructs **one consistent background plate for the entire frame
sequence** (not per-frame), which is directly the crop-loss/coverage problem
— today's pipeline builds the canvas incrementally per adjacent pair; this
paper's method solves for the whole-sequence background in one shot.
**Feasibility:** Classical CV (flood-fill with a "ball" radius parameter,
Canny edge dilation) — no new heavy deps, implementable in OpenCV directly.
Medium effort: needs per-frame edge maps + the flood-fill/ball logic, tunable
radius parameter (paper flags style-sensitivity as its main limitation).
**This is the single highest-value idea in this pass** — it's classical,
cheap, and targets three separate known ASP problems at once (mask quality,
crop loss, content-check reliability) rather than one.

### 2. Shot boundary detection as a Stage-1 pre-filter (research.md §"Video Shot Boundary Detection")
**Stage:** Stage 1, before any matching.
**Targets:** whatever fraction of `no_valid_edges`/`disconnected_edge_graph`
failures are actually caused by attempting to stitch across a hard cut, wipe,
or dissolve rather than a genuine pan — this is currently indistinguishable
from a real matching failure in ASP's telemetry.
**Confirmed gap:** grepped `submodules/ASP/backend/src` for shot-boundary/
histogram-dissimilarity logic — nothing exists. ASP has no explicit check
that a frame sequence is one continuous shot before trying to register it.
**Feasibility:** trivial — HSV histogram dissimilarity between adjacent
frames (research.md's formula), a single threshold, no learned model, no new
deps. This is a half-day instrumentation task, not a research project.
**Recommend pairing with #1**: run this first, since it's nearly free and
would immediately clarify how many of the current disconnected-graph
failures are actually "this was never one continuous pan to begin with"
rather than a real registration problem — which changes how much effort #1
and today's CleanCP/overlap work are worth chasing further.

### 3. UDIS2's learned composition mask, as a Stage-7 alternative to graph-cut (2302.08207v2.pdf, vendor/UDIS2)
**Stage:** Stage 7/11 (composition), alternative to the existing Agarwala-
style graph-cut + `ASP_MULTIBAND_BLEND`.
**Targets:** parallax ghosting/tearing at multi-plane boundaries — the paper's
own stated failure mode for graph-cut-only pipelines is exactly ASP's
multi-plane-parallax problem (research.md §"Multi-Plane Parallax and Non-Rigid
Shifts").
**Why it's different:** graph-cut picks a *hard* per-pixel source label along
a minimum-energy seam; UDIS2's composition network predicts *soft*
per-pixel blend masks driven by a learned model trained specifically to
suppress parallax artifacts without the blur that naive averaging causes —
a genuinely different mechanism, not a re-hash of Laplacian blending (already
implemented) or graph-cut (already implemented).
**Feasibility: low, flag but don't prioritize.** No pretrained checkpoints
are vendored (checked `vendor/UDIS2` for `.pth`/checkpoint files — none);
this would need training on UDIS-D or a natural-image domain, then likely a
domain-gap problem going from photographic training data to flat-cel-shaded
anime. Worth a small experiment (run the pretrained-from-scratch model on a
couple of ASP's worst parallax cases to see if it's even in the right
ballpark) before committing more effort — not a default-off flag you can
build in an afternoon like #1/#2.

### 4. DINOv2/DIFT semantic matching as a fallback matcher for connectivity gaps
**Stage:** Stage 5/6 (matching), as an additional matcher candidate alongside
LoFTR/ALIKED+LightGlue/RoMa.
**Targets:** the exact `no_valid_edges` cases already identified today
(2 of the current real known-good failures: `test35`, `test52`) — pairs
where none of the existing matchers find correspondences on flat-cel-shaded
regions.
**Why it's different:** research.md notes DINOv2/DIFT capture *semantic*
correspondence (e.g. "the corner of a building roof") even when low-level
gradients are absent, which is a different failure mode than what
LoFTR/RoMa target (those still rely on local texture/gradient signal, just
more robustly than SIFT/ORB). Not yet confirmed whether RoMa (already in
ASP's matcher list) already covers this — RoMa is itself a semantic/dense
matcher, so there's real risk this idea is redundant with what's already
tried. **Flag for the team to check RoMa's actual failure characteristics on
`test35`/`test52` before spending effort here** — if RoMa is already
semantically-aware and still fails on these, a DINOv2 matcher probably
won't help either, and this idea should be dropped rather than implemented
blind.
**Feasibility:** DINOv2 is a heavy dependency (ViT backbone) but widely
available pretrained; feasible as an isolated new-matcher-candidate
experiment, same shape as today's other default-off matcher work.

### 5. MoVerse — flagged as NOT practically adoptable right now
**Why it's tempting:** its panoramic-generation stage does gap-filling/
inpainting of unseen background regions from a single image, which sounds
relevant to ASP's occluded-background-fill problem (research.md's closing
note on "structure-aware inpainting" for foreground-occluded gaps).
**Why to deprioritize:** MoVerse is a photorealistic-scene 3D world-model
pipeline (panoramic diffusion → 3D Gaussian scaffold → autoregressive video),
requiring 24GB+ VRAM and built for photographic/3D-consistent scenes, not
flat 2D cel line art with no depth. The domain mismatch is large and the
compute cost is high for what would likely be a single sub-feature
(inpainting). Not recommended as a real work item this cycle — noting it
only so nobody re-discovers and re-scopes it later without this context.

## Explicitly not proposed (already covered today or in research.md as things ASP already does)
- Graph-cut/Min-Cut seam selection (photomontage.pdf) — already ASP's Stage 7.
- Multi-band Laplacian blending — implemented today (`ASP_MULTIBAND_BLEND`).
- MAGSAC++ RANSAC — implemented today, verified no-op.
- APAP/Moving-DLT localized homography — conceptually close to what
  background-masked matching + per-pair BA already do; the *actual* APAP
  repo isn't vendored (see setup problem above) so this can't be adapted
  directly yet regardless.
