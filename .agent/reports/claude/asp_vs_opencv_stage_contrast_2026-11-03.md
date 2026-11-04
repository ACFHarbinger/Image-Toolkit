# ASP vs OpenCV SCANS — stage-by-stage contrast (2026-11-03)

Goal: reach or beat OpenCV's SCANS stitcher by finding which ASP stage loses
and re-implementing it. Two single-case runs so far (asp_test04, asp_test12)
on the new rig (2× RTX 3090 Ti, 123 GB). Corpus run requested from Codex.

## Setup changes

- **Bench was broken since the 2026-10-26 relocation.** `bench_anime_stitch.py`
  and `run_hugin.py` loaded `asp_backend` from `middleware/benchmark/src`,
  which no longer exists. Now `middleware/src/stitching`. Bench imports again.
  (`bench_asp_stages.py` and ~25 other files still `import asp_backend` without
  a loader; not fixed here.)
- `alignment/canvas.py`: the SCANS retry ladder is now `_scan_stitch_attempts(n)`,
  shared by `_scan_stitch_fallback` and the harness so the baseline is exactly
  what the bench scores. `test_scan_fallback.py` + `test_canvas.py`: 51 passed.
- New harness `middleware/benchmark/asp/contrast_opencv.py` (one dataset per call):
  - OpenCV side: the bench's ladder via `estimateTransform`/`composePanorama`,
    keeping `component()` and `cameras()`; plus a `cv2.detail` replica of the
    front half (ORB, `AffineBestOf2NearestMatcher`, `leaveBiggestComponent`) for
    keypoint counts and the all-pairs confidence matrix.
  - ASP side: product `AnimeStitchPipeline.run()` with spies on
    `_pairwise_match_with` and `_filter_edges` (edges mapped to frame paths).
  - Factorial: OpenCV composer replica (graph-cut COST_COLOR at 0.1 MP, no
    exposure comp, 5-band multiband) fed either OpenCV's or ASP's poses.
  - `--inject-opencv-edges`: second ASP run with OpenCV's matcher swapped in.
  - Replica validation: per-frame placement equals the OpenCV warper exactly
    (`AffineWarper` forward map is `[Aᵀ | −Aᵀt/workScale]` — a transpose, not an
    inverse). Seams land slightly differently, so the replica scores 0.005–0.009
    GT SSIM below the Stitcher; ASP-pose rows are compared to the replica row.

## Stage map

| OpenCV SCANS | ASP |
|---|---|
| — | load, width normalise, BaSiC, BiRefNet FG mask, BG photometric |
| — | near-static dedup |
| ORB at 0.8 MP | LoFTR/EfficientLoFTR (+template/PC fallback), FG-masked |
| **all pairs** matched | **spans 1–3 only** (+ opt-in overlap proposals) |
| — | spatial dedup (<`SPATIAL_DEDUP_PX`), edge filter, connectivity gate |
| **keep biggest component with conf ≥ 1, drop the rest** | gap-fill / recovery, else **fall back** |
| AffineBasedEstimator + partial-affine BA | affine BA (C++), wave correction, affine validation (`min_gap`, ratio) |
| — | ECC/sub-pixel refine |
| **graph-cut seams + multiband** (one source frame per region) | temporal median renderer + FG composite |
| largest valid rectangle | content trim, crop, inpaint |

## Results

GT SSIM via the bench's `_compute_aligned_ssim`. Outputs:
`~/Downloads/Data/Tests/asp-contrast-2026-11-03/<case>/`.

| case | OpenCV | OpenCV poses + replica | ASP poses + replica | ASP own | OpenCV matcher → ASP |
|---|---|---|---|---|---|
| asp_test04 (25 fr) | 0.773 | 0.768 | **0.777** | 0.709 (raw) | — |
| asp_test12 (18 fr) | **0.817** | 0.808 | n/a | 0.577 (fallback) | 0.722 (raw) |

**asp_test04 — compositing is the whole gap.** ASP's poses through OpenCV's
composer beat OpenCV itself (0.777 vs 0.773) and the replica's OpenCV-pose
row (+0.009). ASP's own render of the same poses is 0.068 lower. Visually: colour
cast with halos (photometric stages) and horizontal band tearing across
animated regions (median renderer mixes frames). The replica picks one frame
per region and blends seams, and is clean. Pose disagreement is median 17.6 px
and max 40.9 px, but ASP's poses score better under the same composer.

**asp_test12 — registration fails first, compositing second.**
- OpenCV keeps only **5 of 18** frames (its confident component) and still wins.
- All 18 pairs OpenCV trusts are **3–13 frames apart**. ASP proposes spans
  1–3, matched 2 of those 18, and kept 1 after filtering.
- ASP also dropped 8/18 frames in spatial dedup, BA pruned an edge, affine
  validation failed (`min_gap` 3.85 px < 32.1 px), and the run fell back to
  **OpenCV PANORAMA (spherical)**, publishing a 19104×896 warped strip.
- With OpenCV's matcher injected, ASP produces raw output at 0.722, which still
  shows ghosting and band breaks from the renderer.

## What to re-implement, in order

1. **Compositing (stages 10–11).** Replace temporal-median + FG composite with
   seam selection (one owner frame per region) + multiband, as OpenCV does.
   Measured +0.068 on test04 from the composer swap alone. ASP already has
   `rendering/compositing/_graphcut.py`, off by default (`ASP_GRAPHCUT_SEAM`).
   Given this result, its earlier failure was probably wiring (feathering,
   ownership, photometric input), not the method. Also test it without
   BaSiC/BG normalisation: the replica used raw frames.
2. **Pair proposal + component policy (stages 5–6, 7 gate).** Match beyond
   span 3 (all pairs, or a cheap global screen then dense match; the new GPUs
   make this affordable). When the graph is disconnected, keep the largest
   confident component and drop the rest instead of falling back.
3. **Fallback chain.** Do not publish the PANORAMA (spherical) result on a
   scroll case when SCANS succeeds; it was the worst output here.
4. **Spatial dedup / `min_gap` validation** interact with 2: dedup removed
   frames OpenCV registered; revisit after 2.

## Caveat on the single-case results above

`vendor/BiRefNet` was an uninitialised submodule on this rig, so the
asp_test04/asp_test12 runs above had no FG masks. Fixed with
`git submodule update --init vendor/BiRefNet`. The corpus runs below have masks.

## Corpus results (97 cases, 55 with GT; 51 scored on both sides)

Outputs: `~/Downloads/Data/Tests/asp-contrast-corpus-2026-11-03/` (baseline)
and `asp-seam-corpus-2026-11-03/` (seam renderer); each has `aggregate.md`.
OpenCV took `scans-0.8` on all 97.

| ASP variant | ASP − OpenCV, mean (median) | ASP > OpenCV |
|---|---|---|
| baseline (median + FG composite) | −0.064 (−0.061) | 4/51 |
| OpenCV matcher injected | −0.064 (−0.063) | 7/53 |
| **seam renderer** (`ASP_RENDERER=seam`) | **−0.019 (−0.013)** | **16/51** |

- Baseline: ASP poses through the replica composer beat ASP's own render on
  36/38 raw cases (+0.064 mean). Compositing was the whole average gap.
- Injecting OpenCV's matcher changes the mean by −0.001; it does turn 12
  fallback cases into raw ASP (67 → 79). Matching decides which path a case
  takes, not the average quality.
- ASP identity is the same in both runs: 67 raw, 26 SCANS, 4 safe.
- asp_test32 aborted once in the baseline (OpenCL `CL_INVALID_COMMAND_QUEUE`
  from a bundled OpenCV 4.10 inside the PANORAMA fallback, with 4 GPU jobs
  running); it passed with `OPENCV_OPENCL_RUNTIME=disabled`.

### Seam renderer (`rendering/rendering/seam.py`, branch `feat/asp-seam-renderer`)

Port of the replica composer: graph-cut COST_COLOR seams at 0.1 MP, 5-band
multiband, raw (uncorrected) frames, Stage 11 FG composite skipped. Default
off. A first corpus pass had a valid-mask bug: ROI masks overwrote instead of
unioning, so tilted frames left black rows that the crop then cut. Fixed and
covered by a regression test (fails on the old code).

### Next failing stage: per-frame dark-border trim

`_load_frames` runs `_trim_dark_border` on each frame: edge rows below 35% of
the frame's median brightness are cut. On dark scenes it removes real content,
by a different amount per frame. 48/97 cases (28 with GT) lose >2% of some
frame's area; the worst are asp_test49 (up to 36%, also ASP's worst case vs
OpenCV), asp_test16 (25%, about 250 rows lost from the output) and asp_test15 (19%).
In 4 cases the top trim also varies, which misplaced frames in the harness's
`asp_geom+cv_comp` row (fixed: that row now composes ASP's own loaded frames).

Fix, `ASP_DARK_TRIM=sequence` (default stays `frame`): trim only
near-black (mean ≤ 24) bars shared by every frame, with one box for all
frames. It also feeds the SCANS fallback, so fallback cases gain too.

### Three-way result (49 GT cases all three runs completed)

| ASP variant | mean GT SSIM | ASP − OpenCV mean (median) | ASP > OpenCV |
|---|---|---|---|
| baseline | 0.661 | −0.064 (−0.061) | 4/49 |
| seam | 0.707 | −0.017 (−0.012) | 16/49 |
| **seam + sequence trim** | **0.720** | **−0.005 (−0.002)** | **18/49** |
| OpenCV SCANS | 0.725 | — | — |

Sequence trim vs seam alone: 17 better, 6 worse, 26 within ±0.002. Best:
asp_test49 +0.13, asp_test16/15/52 about +0.09. Worst: asp_test14 −0.048,
asp_test02 −0.021 (flips raw → SCANS). Output:
`~/Downloads/Data/Tests/asp-seam-seqtrim-corpus-2026-11-03/` (run with
`OPENCV_OPENCL_RUNTIME=disabled`).

**asp_test12 OOM.** In this variant ASP's PANORAMA fallback (native
`batch.canvas.panorama_stitch_fallback`, bundled OpenCV 4.10) was OOM-killed,
and again under a 60 GB cap. The baseline produced an 18208×752 strip on the
same case. The fallback has no output-size guard: a product risk on its own,
and another reason for item 3 (no PANORAMA on scroll cases).

## Remaining registration gap

With seam compositing, the worst raw cases are pose failures: ASP poses
through the replica composer still trail OpenCV by 0.09–0.12 on asp_test14,
49, 52 and 54. Next after the trim: pair proposal beyond span 3 and
keep-biggest-component (item 2 above).

## Defaults flipped + canvas-size guard (commit b1108dc36, `feat/asp-seam-renderer`)

- Defaults: renderer `seam` (pipeline, CLI, dispatch, image_merger, Qt merge tab first entry), `ASP_DARK_TRIM=sequence`. Env vars still override.
- Guard: OpenCV attempts now `estimateTransform` first, then predict the compose canvas (median focal, warp ROI union). Prediction matched the real canvas exactly on 8/8 composed stitches. A canvas over `CANVAS_MAX_DIM` or 4× the summed frame area (`ASP_PANORAMA_MAX_AREA_RATIO`) is refused, so the case goes to SCANS.
- The 3 PANORAMA cases, rerun with defaults under a 60 GB cap (`~/Downloads/Data/Tests/asp-defaults-pano-2026-11-03`):

| case | predicted PANORAMA canvas | before | after (SCANS) |
|---|---|---|---|
| asp_test12 | 60157×30083 | OOM | 0.762 |
| asp_test41 (no GT) | 59817×29931 | stretched partial crop | full scene |
| asp_test76 | 12594×6278 | 0.713 (6288×704 strip) | 0.785 |

- Tests: stitching suite 1318 passed. The 3 failures also fail on main (`test_audit_recomputes_strip_banding`, `test_compute_all_metrics_emits_strip_banding`, `test_severe_gradient_clip_routes_to_hugin`).
- Not done: a full-corpus rerun with defaults. Outside these 3 cases the defaults equal the seam+seqtrim run.
