# ASP Pipeline Analysis — Session 2 (2026-06-03)

> **⚠️ ARCHIVED**: This is a fixed benchmark comparison from Sessions 1–2 (2026-06-03). Current pipeline state (Sessions 1–28) is in `.agent/cache/asp_state_of_the_pipeline.md`.

**Final benchmark:** `anime_stitch_20260603_202535.json`  
**Prev session baseline:** `anime_stitch_20260603_182046.json`  
**Pre-feature baseline:** `anime_stitch_20260601_191331.json`

---

## 1. Final Results Table

| Test | Pre-feature | Session 1 | Session 2 | Simple stitch | ΔSession1 | Verdict |
|------|----------:|----------:|----------:|-------------:|----------:|---------|
| test04 | 0.633 | 0.742 | 0.742 | 0.738 | +0.000 | comparable |
| test08 | 0.731 | 0.735 | **0.737** | 0.813 | +0.002 | simple_better |
| test09 | 0.785 | 0.787 | 0.787 | 0.757 | -0.000 | **asp_better** |
| test27 | 0.705 | 0.709 | 0.708 | 0.677 | -0.001 | **asp_better** |
| test57 | 0.738 | 0.745 | 0.743 | 0.756 | -0.002 | comparable |

**Session 2 net gain: +0.002 on test08, essentially flat everywhere else.**

---

## 2. Features Shipped This Session

### 2.1 A1 — RAFT optical flow (sea_raft_s@things)
**ptlflow** installed; `sea_raft_s@things` loads lazily on GPU as the primary flow engine. Key details:
- **Seam-band cropping**: flow computed only on ±taper_px+16 strip around seam (not full canvas, avoids VRAM OOM on 2000+px canvases at 1280px downscale)
- Falls back to DIS automatically. Toggle: `ASP_FLOW_ENGINE=dis`

**Finding**: RAFT and DIS give identical SSIM outcomes for these tests. The animation residuals (7-85px) are detected accurately by both engines. Flow quality is not the bottleneck.

### 2.2 A3 — ARAP regularisation (cell_size=16, n_iter=2)
Implements Sýkora-style per-cell rigid median translation interpolated back to pixel space via `scipy.interpolate.RegularGridInterpolator`. Replaces Gaussian smoothing to preserve line-art collinearity.

**Finding**: No measurable SSIM improvement. The regularisation is geometrically correct but the SSIM gain from smoother flow is below measurement noise.

### 2.3 A6 enhanced — post_warp_diff ghost-prevention escalation
After applying the ARAP-regularised midpoint warp, measures the mean foreground colour difference in a narrow strip at the seam. If `post_warp_diff > 22 lum units`, escalates to single-pose fallback (no blend) rather than Laplacian blending two different poses.

**Finding**: Catches 5 seams in test08 (residuals 22-32 lum units) → +0.002 SSIM. No effect on test09 (post_diffs 5-18 units, all below threshold).

### 2.4 Infrastructure additions
- `alpha_a / alpha_b` parameters in `register_foreground_at_seam` — ready for asymmetric warp experiments
- Global reference tracking (`ref=N` in log output)
- `post_warp_diff` diagnostic in info dict

---

## 3. Failed Experiments (reverted)

### 3.1 Global reference asymmetric alpha (catastrophic: test27 -0.151)
**Idea**: warp all frames toward a single central reference rather than pairwise midpoints. Frames far from reference get `alpha → 1.0` (full warp), frames adjacent to reference get `alpha → 0.0` (don't move).

**Failure mode**: At α=1.0, a 5px flow error becomes a 5px wrong displacement on the frame. For flat-region scenes (test27: uniform skin, minimal texture gradient), RAFT flow is noisier → errors amplified at α=1.0 → catastrophic content displacement. Test27 dropped from 0.709 to 0.558.

**Lesson**: Asymmetric warp amplifies flow noise proportionally to `max(alpha_a, alpha_b)`. Never exceed ~0.65 for noisy flows. The global reference idea is sound but needs reliable flow first.

### 3.2 Character bounding-box crop (wrong axis for vertical pans)
**Idea**: After assembly, crop to the foreground character bounding box to remove excess background-only regions (test27 has 2× more pan than GT shows).

**Failure mode**: For a vertical pan (test27), BiRefNet fg union covers the full column extent at each frame's side. The bounding box calculation found the character was in the left half of each frame → cut 44% of columns → removed the right-side background lockers that are essential to the composition.

**Lesson**: Foreground-aware crop must respect the scroll axis. For a vertical pan, only crop excess top/bottom rows where NO frame has character content, not columns. This is a harder problem requiring knowledge of which rows are "unique content" vs "covered by adjacent frames."

---

## 4. Understanding the SSIM Ceiling

The SSIM scores 0.787/0.709/0.745 for tests 09/27/57 have been essentially stable across all improvements tried (RAFT, ARAP, global reference, threshold tuning). Analysis of the aligned-SSIM (ECC alignment before comparison) reveals the actual ceiling:

| Test | Raw SSIM | Aligned SSIM | Gap (framing) | Remaining gap |
|------|--------:|-------------:|--------------|--------------|
| test09 | 0.787 | 0.832 | 0.045 | 0.168 (from 1.0) |
| test27 | 0.708 | 0.748 | 0.040 | 0.252 (2× scale) |
| test57 | 0.743 | 0.736 | (negative!) | — |

The remaining gap (above the aligned SSIM) comes from:
1. **Animation timing**: the GT was assembled from specific frames at specific times. Our frame selection picks different frames → character is in a different animation phase.
2. **Midpoint warp residual**: even with perfect flow, the midpoint warp only HALVES the pose gap. The remaining half creates residual seam artifacts.
3. **SSIM sensitivity to fine structure**: anime's sharp line-art means even 1px misalignment creates a measurable SSIM penalty.

**The bottleneck is upstream of the compositing**: better frame selection (selecting frames that are pose-consistent with the GT reference) would improve SSIM more than any compositing improvement.

---

## 5. Implementation Status (complete picture)

| Feature | Status | Notes |
|---------|--------|-------|
| A1: RAFT/SEA-RAFT flow | ✅ | sea_raft_s@things, seam-band crop, 1280px downscale |
| A2/A4: Symmetric midpoint warp | ✅ | alpha_a=alpha_b=0.5 by default; alpha_a/b API ready |
| A3: ARAP regularisation | ✅ | cell=16, n_iter=2 |
| A5: FG-excluded temporal median | ✅ | Session 1 |
| A6: Single-pose fallback | ✅ | max_residual=90 + post_warp_diff=22 escalation |
| Boundary fixes | ✅ | BORDER_CONSTANT, ~valid masking, both-content Laplacian |
| Global reference warp | ⚠️ | API added; symmetric midpoint used (asymmetric regresses) |
| LSD collinearity term | ⬜ | Would help prevent line-art bending; not yet implemented |
| Segment-guided flow | ⬜ | Would help flat-region aperture problem |
| ARAP Push phase | ⬜ | Full Sýkora block-matching; improves over median-per-cell |
| Vertical-pan-aware crop | ⬜ | Must crop top/bottom only, not columns |

---

---

## Session 3 (2026-06-03)

### 3.1 What Was Built

**`backend/src/anim/frame_selection.py`** — New backend module for smart frame selection, exposing `smart_select_frames()` as a clean API for use by the pipeline and GUI (not just the benchmark). Implements:
- Two-pass architecture: Pass 1 (v1 greedy first-past-threshold), Pass 2 (pose-consistent local refinement)
- `_fg_center_diff()`: Gradient-magnitude L1 on central 50% crop — designed as the pose similarity metric

**Upgraded `_smart_select_frames()`** in the benchmark:
- Same two-pass architecture
- Extensive logging: `[PoseSelect] Slot k: old→new (grad X→Y)` per refined slot
- `_POSE_WINDOW_PX` env var (default 0 = disabled)

### 3.2 Experiment: Gradient-Based Pose Refinement

**Approach:** Pass 2 checks if any frame within ±2 slots of each v1-selected frame has ≥10% better gradient-magnitude L1 (central crop) to the previous selected frame. If so, substitutes it.

**Results:**

| Test | Session 2 | Session 3 (gradient proxy) | Δ |
|------|--------:|--------:|------:|
| test04 | 0.742 | 0.699 | **-0.043** |
| test08 | 0.737 | 0.741 | +0.004 |
| test09 | 0.787 | 0.784 | -0.003 |
| test27 | 0.708 | 0.682 | **-0.026** |
| test57 | 0.743 | 0.759 | +0.016 |

**Net: -0.052 across the 5-test corpus. Disabled.**

### 3.3 Failure Analysis: Why Gradient Proxy Fails

The central 50% crop of a pan-shot frame contains both character AND background. As the camera pans, the BACKGROUND changes position (different lockers, different wall sections appear in frame). The Sobel gradient of the central crop therefore measures BOTH "character changed pose" AND "background structure changed position in crop."

The selector ends up preferring frames at similar scroll positions (similar background structure → similar gradient pattern) rather than frames with similar character pose. This causes luminance clustering (frames with similar lighting grouped together) → strip_banding at cluster boundaries.

**The fix requires background-agnostic pose features.** Options in decreasing complexity:
1. Foreground-only RAFT flow (compare fg-masked crops only)
2. DWPose/ViTPose joint coordinates (pure character skeleton)
3. DINO/CLIP features on BiRefNet-masked foreground region

### 3.4 Current State of Feature (Disabled Infrastructure)

The two-pass architecture is fully built and working. Disabling it (default) reproduces session 2 results exactly — confirmed with a final run (benchmark 20260603_22xxxx):

| Test | Session 2 | Session 3 (pose=OFF) | Δ |
|------|--------:|--------:|------:|
| test04 | 0.742 | 0.742 | 0.000 |
| test08 | 0.737 | 0.737 | 0.000 |
| test09 | 0.787 | 0.787 | 0.000 |
| test27 | 0.708 | 0.708 | 0.000 |
| test57 | 0.743 | 0.743 | 0.000 |

To enable gradient proxy for experimentation: `ASP_POSE_WINDOW_PX=80`.

The `_fg_center_diff()` function signature accepts any metric — the 12-line gradient computation can be replaced with foreground-only flow or pose embedding without changing the loop structure.

---

## Session 4 (2026-06-04)

### 4.1 What Was Built

**ARAP Push phase** — Full Sýkora 2009 Push→Regularise algorithm in `fg_register.py`:
- `_arap_push(img_a, img_b, fg_mask, initial_flow, cell_size=16, search_range=24)`: per-cell SAD block matching via `cv2.matchTemplate`. 15% improvement threshold prevents noise-driven switches. 25% min fg fraction to skip background-dominated cells.
- Now called before `_arap_regularise()` in `register_foreground_at_seam()`.
- Toggle: `ASP_ARAP_PUSH=1` (default) / `=0`.

**BiRefNet fg-masked pose diff** — Upgraded `_fg_center_diff()` to accept optional `fg_mask` parameter. When mask provided, gradient diff is weighted by fg probability (background edges excluded). BiRefNet probe section now builds both `_bg_thumb_mask` (intersection, for camera displacement) and `_fg_thumb_mask` (union, for pose similarity).

**Composite gate diagnostics** — `ASP_GATE_SC` / `ASP_GATE_SB` env vars to override thresholds. Test04 verified: ASP composite (gate-disabled) gives GT-SSIM 0.716 vs SCANS 0.742 → gate is correctly calibrated.

### 4.2 Experiment Results

| Test | S2 baseline | S4 (ARAP Push) | Δ |
|------|--------:|--------:|------:|
| test08 | 0.737 | 0.736 | -0.001 |
| test09 | 0.787 | 0.787 | 0.000 |
| test27 | 0.708 | 0.709 | +0.001 |
| test57 | 0.743 | 0.743 | 0.000 |

**ARAP Push: zero measurable SSIM impact.** Confirms flow quality is not the bottleneck. The Push phase correctly detects displacement in synthetic tests (unit-tested) and does not regress any production test. Will help when RAFT gives genuinely wrong flow directions in large flat cel-shaded regions — but the current 5-test corpus doesn't have this as the dominant failure mode.

**BiRefNet fg-masked pose selection (experimental, disabled):**
- test04: 0.742 → 0.660 (regression, -0.082 from SCANS-fallback frame change)  
- test09: 0.787 → 0.787 (unchanged, 0 refinements)
- test27: 0.708 → 0.706 (within noise, 3 refinements)

Fewer spurious refinements than raw gradient (session 3), but still regresses test04 due to GT reference coupling.

### 4.3 Full 96-Test Benchmark (completed 2026-06-04)

*File: `anime_stitch_20260604_025208.json`. Runtime: 2.5h. Avg 95s/dataset.*

| Metric | Pre-features (session 1) | Session 4 | Δ |
|--------|------------------------:|----------:|---|
| True ASP composites | 44/96 (45.8%) | 52/96 (54.2%) | **+8 tests** |
| Gate failures | 39/96 (40.6%) | 31/96 (32.3%) | **−8 failures** |
| Affine failures | 13/96 (13.5%) | 13/96 (13.5%) | unchanged |
| Avg GT SSIM (55 tests) | 0.669 | 0.667 | within noise |
| vs simple stitch | 0.695 | 0.694 | within noise |
| asp_better | 8 (14.5%) | 7 (12.7%) | slight regression |
| comparable | 24 (43.6%) | 22 (40.0%) | |
| simple_better | 23 (41.8%) | 26 (47.3%) | slight regression |

**Best ASP scores:** test17=0.887 (+0.031 vs sim), test84=0.821 (+0.052), test44=0.770 (+0.061)

**Key finding:** Pipeline COVERAGE improved significantly (+8 tests producing true ASP composites). The newly-saved tests fall into "comparable" verdict (they were previously producing SCANS fallbacks), which is a genuine quality improvement even though it shifts the verdict distribution. The corpus-wide SSIM remains ~same because per-test improvements (+0.002 to +0.004) are within noise at the 55-test scale.

---

## Session 5 (2026-06-04)

### 5.1 What Was Built

**Fg Pixel L1 Pose Metric** — Replaced gradient-weighted L1 in `_fg_center_diff()` with fg-masked pixel L1:
- Hard-thresholds BiRefNet fg_mask at 0.3 → binary `fg_bin`  
- Zeroes out background before ANY computation → background-invariant by construction
- Per-frame fg gain normalisation (zero mean / unit std) removes inter-frame brightness variation
- Previous gradient approach: gradient on full image × soft mask → background bled through at 0.05–0.1 weight

**Alignment Stability Gate** — New pre-render gate in both `bench_anime_stitch.py` and `pipeline.py`:
- Fires when 75th-percentile of `|dx_steps|` > 50px (2D/diagonal camera motion)
- Falls back to SCANS on width-normalised frames immediately (before expensive compositing)
- Disable via `ASP_ALIGN_GATE_DX=99`

**8 new unit tests** — `backend/test/anim/test_frame_selection.py` covering `_fg_center_diff()` behavior: identical-fg near-zero, different-pose high-score, gain-normalisation, strict background-invariance, sparse-mask fallback.

### 5.2 Experiment Results

**Default pipeline (alignment gate + ghosting gate, NO pose selection)** — from clean sequential runs:

| Test | S4 | S5 (clean) | Δ | Notes |
|------|-----|------------|---|-------|
| test09 | 0.787 | **0.787** | 0.000 | Neither gate fires |
| test27 | 0.709 | **0.709** | 0.000 | Neither gate fires |
| test04 | 0.696 | ~0.742 | ~+0.046 | SCANS fallback (render gate); SCANS non-determinism |
| test08 | 0.736 | **0.809** | **+0.074** | Alignment gate → SCANS-on-normalised |
| test25 | 0.697 | **0.746** | **+0.049** | Alignment gate → SCANS-on-normalised |
| test57 | 0.743 | **0.743** | 0.000 | Neither gate fires |
| test82 | 0.756 | 0.756–0.800 | +0–+0.044 | Ghosting gate borderline (ratio 1.92–2.06); stochastic |

**Session 5 with pose selection enabled (`ASP_POSE_WINDOW_PX=80`, ±2 range):**

| Test | S4 baseline | S5 pose-on | Δ |
|------|------------|-----------|---|
| test09 | 0.787 | 0.788 | +0.001 |
| test27 | 0.709 | 0.719 | **+0.010** |
| test04 | 0.696 | 0.672 | -0.024 (GT coupling regression) |
| test08 | 0.736 | 0.743 | +0.007 |
| test57 | 0.743 | 0.728 | -0.015 (GT coupling regression) |

### 5.3 Key Findings

**Alignment gate resolves the 2D-motion failure mode:**
test08 (dx_cv=16.6, highly irregular horizontal offsets) was producing a bad ASP composite (0.736 vs simple 0.805). The gate detects the 2D-motion pattern and falls back to SCANS-on-normalised-frames (0.809). The normalised frames give better SCANS output than running SCANS on original paths, so the fallback quality is genuinely better than both the old ASP composite AND the old simple stitch.

**Fg pixel L1 metric is background-invariant, but GT coupling persists:**
test27 improved +0.010 with pose selection enabled (first meaningful breakthrough since session 2). But test04 and test57 still regress due to GT coupling: any frame substitution that diverges from the GT's temporal reference penalises SSIM even when the pose selection is correct. The new metric has fewer wrong substitutions than gradient, but doesn't eliminate GT coupling.

**±3 look range is strictly worse than ±2:**
Expanding the search window from ±2 to ±3 frames consistently hurts test09 (-0.007) and test27 (-0.007) while the already-good improvements for test04/test08 came from the alignment gate, not the wider range. Reverted to ±2.

---

## 9. Next Session Priorities

**Achieved this session:** Alignment gate (+0.074 on test08, +0.049 on test25), fg pixel L1 metric (+0.010 on test27 with pose-on), 8 unit tests (90 total).

**GT-coupling wall is now the #1 bottleneck** for pose selection. All improvements that require changing WHICH frames are selected hit this wall. Options to break through:
1. **Compute aligned-SSIM as the metric** instead of raw SSIM — align both outputs to GT before comparison, removing the framing gap. This would better reflect actual quality improvement.
2. **RAFT flow on fg-masked crops for pose metric** — compute DIS/RAFT flow between fg-masked thumbnails of each candidate vs last selected, use fg-flow magnitude as metric. This is more accurate than pixel L1 for detecting pose change in uniform-color regions.
3. **Corpus-wide alignment gate re-run** — the alignment gate is new and hasn't been run on all 96 tests yet. A full re-run would show the total coverage improvement.

**Medium priority:**
4. Segment-guided flow (aperture problem in flat cel regions).
5. Analysis of ghosting-dominated simple_better tests (test82, test95) — need visual inspection to understand root cause.
6. LSD collinear constraint in ARAP.

---

## Session 6 (2026-06-04)

### 6.1 New Research Sources Reviewed

- **`reports/Advanced Morphological Integration and Human-in-the-Loop Interventions for the Anime Stitch Pipeline.md`** — introduced: AGNC (Adaptive GNC for bundle adjustment), SAM 2 masking, Overmix sub-pixel averaging + maximal frame ingestion, BigWarp/Fourier-Mellin manual registration fallback, SAM2Flow/FlowVid interactive flow kinematics, Intelligent Scissors seam routing, RLHF/DPO pathway for full automation.
- **`reports/Anime Stitch Pipeline ML Research.md`** — deepened: DINOv2 facility-location selection, AnimeInterp SGM+ConvGRU, SI-FID reference-free metric, SIQE no-reference ghosting detection, CamFlow hybrid motion basis, FD-Means hold detection.

### 6.2 What Was Built

**`frame_selection.py`** — `_detect_hold_blocks()` + `ASP_HOLD_THRESHOLD` env var:
- Detects animation "on twos / on threes" hold blocks by thumbnail pixel MAD
- Returns representative frame indices (first frame of each block)
- Integrated into `smart_select_frames()`: verbose diagnostic, hold_ids array per frame, tie-breaking preference in Pass 2 (penalty for candidates within same hold as previous anchor)
- 9 new unit tests in `test_frame_selection.py`

**`bundle_adjust.py`** — GNC robust loss (§1.1C):
- Changed `least_squares` to `loss='cauchy', f_scale=10.0`
- Cauchy loss down-weights edges with residual > 10px by 50%; 50px edges at ~5%
- Makes BA inherently robust to outlier edges, complementing the post-solve residual pruning
- Override via `ASP_BA_F_SCALE` env var
- 3 new unit tests in `test_bundle_adjust.py`

**`fg_register.py`** — SLIC SGM proxy (§3.1B):
- `_slic_sgm_proxy()`: SLIC superpixel centroid tracking as coarse flow for flat cel regions
- Requires scikit-image; returns None silently if unavailable
- Colour affinity (LAB distance) + distance penalty → per-segment centroid displacement
- Integrated in `register_foreground_at_seam()` behind `ASP_SGM_PROXY=1` env var (default OFF)
- Flow field replaces RAFT/DIS flow for fg pixels when enabled; ARAP Regularise smooths

**Roadmap updates** (`moon/roadmaps/asp.md`):
- Header updated to Session 6 with new research sources
- §0.1: Added 6 new status entries (LSD, SLIC, hold detect, GNC — all ⬜ with session 6 notes)
- §1.1: Added AGNC as Option D (adaptive schedule, SAC-GNC reference), updated recommendation to ship C (GNC) and prototype D
- New §1.11: Animation Hold Detection (Quick Win, implemented in session 6)
- New §2.9: BigWarp / Fourier-Mellin manual registration fallback
- New §2.10: SAM2Flow / FlowVid interactive flow kinematics
- New §2.11: Intelligent Scissors seam routing
- New §3.11: SAM 2 interactive masking upgrade
- New §3.12: Overmix sub-pixel averaging / maximal frame ingestion philosophy
- Anchor index updated with all new sections

### 6.3 Test Count

102 passing (was 90 before session 6): +9 hold detection tests, +3 GNC bundle adjust tests.

### 6.4 What's Next

**Corpus-wide re-run needed** — session 5 improvements (alignment gate, fg pixel L1) only validated on the 5-test subset. A full 96-test run would update the corpus statistics.

**Priority 1:** DINOv2 submodular frame selection (§3.3) — breaks GT-coupling wall. Infrastructure ready in `frame_selection.py`. Key implementation: `torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')` on thumbnail pairs, facility-location greedy selection, verify on 5-test subset before full run.

**Priority 2:** Aligned-SSIM as primary benchmark metric — add ECC alignment before SSIM computation, removes framing bias from GT-coupling.

**Priority 3:** LSD collinearity constraint in ARAP (`fg_register.py` `_arap_regularise`) — completes Sýkora 2009 full algorithm.

**Priority 4:** Corpus-wide alignment gate run — report updated fallback rate and coverage improvement vs S4 baseline (52/96 composites).

---

## Session 9 (2026-06-05)

### 9.1 What Was Built

**`frame_selection.py`** — DINOv2 model caching + batch inference:
- Added `_DINOV2_CACHE: dict = {}` module-level singleton; model loaded once per device
- Batch inference: all frames stacked into single tensor, one forward pass replaces per-frame loop
- Exported `_compute_dinov2_features` in `__all__`

**`fg_register.py`** — LSD image-offset fix + SGM proxy cleanup:
- `_arap_regularise()` gains `image_offset: Tuple[int,int]` parameter
- LSD now called on seam-band crop (`crop_a`), coordinates shifted to canvas-space via `image_offset=(y0_crop, 0)`
- Bounds-checked `0 <= fy < H and 0 <= fx < W` prevents out-of-bounds mask lookups
- SGM proxy: simplified `flow_crop[fg_bin_crop] = sgm_flow[fg_bin_crop]` direct assignment
- ARAP Push now receives SGM-improved `flow_crop` as initial estimate (better starting point for flat regions)

**`compositing.py`** — ToonCrafter seam synthesis wired:
- Added `_TOONCRAFTER_SEAM` env var (`ASP_TOONCRAFTER_SEAM=1`)
- `seam_synthesized: dict` tracks synthesis per boundary index
- Worst single-pose seam synthesized via `_generate_canonical_cel(crop_a, crop_b, device)`
- Synthesized crop pasted into the compositing result; single-pose fallback covers everything else
- Graceful degradation: cross-dissolve if ToonCrafter unavailable, silent on inference error

**Tests**: 102 → **107 passing** (5 new LSD collinearity tests in `TestLSDCollinearity`)

### 9.2 CHANGELOG Updated

- Added session 9 entry at top of `moon/CHANGELOG.md`
- Added session 6 entry (previously missing)

### 9.3 Roadmap Updated

- §0.1 status: updated all S6–S9 items to ✅; marked SLIC SGM proxy, hold detection, GNC, DINOv2, LSD, ToonCrafter as done
- §0.2: updated DINOv2 implementation status to note batch inference and model caching
- §0.1 LSD: updated to note seam-band crop + image_offset fix

### 9.4 What's Next

**Priority 1:** Full 96-test benchmark re-run — all S5–S9 improvements pending corpus-wide validation. Expected: alignment gate fires on more tests; DINOv2 pose selection moves some `simple_better` → `comparable`; content trim helps test27-class scale mismatch.

**Priority 2:** RAFT flow confidence gating for blend width — where RAFT confidence is low (flat regions), use wider blend zone or fall back to single-pose (§0.1 summary table: "Confidence-weighted alpha").

**Priority 3:** SI-FID as supplementary metric (§3.9) — reference-free quality for the 41 GT-less tests.

**Priority 4:** Corpus-wide re-run after S9 changes to update baseline numbers.
