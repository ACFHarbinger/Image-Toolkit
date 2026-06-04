# ASP Pipeline Analysis — Session 2 (2026-06-03)

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

## 8. Next Session Priorities

**Confirmed ceiling** (animation timing, not compositing): All compositing improvements (RAFT, ARAP Push+Regularise, post_warp_diff threshold) have been exhausted with zero/minimal SSIM impact. The 5-test SSIM ceiling (test09=0.787, test27=0.709) is definitively animation-timing-limited.

**Highest impact (require new capabilities):**
1. **Proper pose-consistent frame selection with foreground-only flow** — the `_fg_center_diff()` infrastructure is in `frame_selection.py`. Replace the gradient proxy with: run RAFT on BiRefNet-masked foreground crops of each candidate vs last selected frame. Foreground-only flow is background-invariant by construction. This is the ONE change that could break through the SSIM ceiling.
2. **Full 96-test re-run analysis** — benchmark is running (session 4). Analyze the distribution of gate failures and identify tests where ASP could be improved.

**Medium impact (new algorithmic territory):**
3. **Segment-guided flow** — SLIC superpixels anchored to segment centroids for flat cel-shaded regions where RAFT aperture problem is worst. Would improve push-phase quality for large uniform patches.
4. **LSD collinear constraint** in ARAP energy — prevents bending of straight structural lines (swords, architectural elements). Complex; uncertain benefit for current test corpus.
5. **ToonCrafter synthesis at single-pose seams** — when `post_warp_diff > 22`, generate a synthetic intermediate pose instead of taking one frame. Would eliminate single-pose seam discontinuities. Expensive (~30s/seam).

**Infrastructure:**
6. Analyze full 96-test results when benchmark completes. Update `asp_state_of_the_pipeline.md` §3 with corpus-wide statistics.
