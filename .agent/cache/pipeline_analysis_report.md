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

## 6. Next Session Priorities

**Highest impact (require new capabilities):**
1. **Pose-consistency frame selection** — select frames whose character pose is closest to the GT reference (need GT at runtime or pose similarity metric without GT). Without this, the SSIM ceiling cannot be raised.
2. **Vertical-pan content crop** — for test27, compute how many canvas rows have character content vs how many are "excess pan beyond character extent." Crop the excess rows to match GT scale.

**Medium impact (incremental improvements):**
3. **ARAP Push phase** — add Sýkora's block-matching Push to improve per-cell rigid transform quality over median. Reduces residual errors in flat regions.
4. **Segment-guided flow** — use colour-segment centroids (AnimeInterp SGM) as additional flow constraints for flat anime regions where RAFT gives noisy estimates.
5. **Lowered max_residual to 50** — for test08-class scenes with extreme motion (>50px residuals), single-pose gives cleaner results than warped blend.

**Infrastructure:**
6. **Full 96-test re-run** with all session 1+2 features to update corpus-wide statistics.
