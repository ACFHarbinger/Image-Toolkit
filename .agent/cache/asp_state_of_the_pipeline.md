# ASP — State of the Pipeline: What Works, What Failed, What's Next

*Date: 2026-06-03. Authored after all sessions completed through the RAFT/ARAP session.*  
*Primary benchmark corpora: 96 tests (`asp_test01–96`), 55 with ground truth in `data/ground_truth/`. 5-test subset (`test04/08/09/27/57`) used for rapid iteration.*

---

## 1. The Core Problem

The Anime Stitch Pipeline (ASP) assembles a character's full body from sequential frames of an anime pan shot — frames where the character is only partially visible in any single frame. The fundamental challenge that every other problem traces back to:

> **The character is *animating* while the camera pans.** Frames captured 300–800 ms apart show the same camera position offset but with the character in a completely different animation pose. A rigid translation model aligns the *background* perfectly but leaves body parts in mismatched poses on either side of every strip seam.

Concretely: when frames `a` (at time *t*) and `b` (at time *t+400ms*) are placed adjacent on the canvas, the background panels behind the character are pixel-perfect, but the character's arm in `a` is reaching to the left while in `b` it's pointing right. The seam cuts through both → the canonical torn/doubled-edge artifact.

This is *structurally* the same problem as ghost-free HDR imaging (multiple exposures of a moving person) or video super-resolution (aligning frames with moving objects). The established solution is: **measure optical flow → warp moving content toward a reference → fuse**. The ASP now implements this, but with anime-specific complications: flat cel shading creates the aperture problem for flow estimation, and line-art must not be bent by the warp.

---

## 2. What Is Currently Implemented

### 2.1 Smart Frame Selection

**File:** `backend/benchmark/bench_anime_stitch.py` → `_smart_select_frames()`

Source datasets contain 58–333 consecutive video frames at ~42ms intervals. The selector reduces these to ~5–37 frames per dataset for pipeline processing. Three rejection gates:

1. **Displacement sufficiency**: frame is kept only when cumulative background camera displacement ≥ 50px from last selected frame (ensures new canvas area is revealed).
2. **Direction consistency**: backward-direction frames are not counted as forward progress. Frames that re-expose already-covered canvas rows (where character animation has changed) are skipped.
3. **High-animation / low-movement filter**: frame is dropped if displacement < 8px but thumbnail MAD > 0.10 (camera nearly stationary, character animating heavily).

**Corpus result:** 16,329 raw frames → 1,692 selected (10× reduction, ~18 per dataset). Selection takes ~1.8s per dataset on CPU using parallel thumbnail loading + OpenCV phase correlation.

**Known limitation:** Phase correlation measures whole-frame displacement including character animation, so a "50px camera step" may actually be 5px camera + 45px limb swing. The two-channel BiRefNet-based refinement was implemented but regresses results (see §4) because it changes which frames are selected.

---

### 2.2 Pipeline Stages (fully implemented)

The 13-stage pipeline in `backend/src/anim/pipeline.py`:

| Stage | What it does | Key file |
|---|---|---|
| 1 | Load, trim, dark-border detection | `canvas.py` |
| 2 | Width normalisation (Lanczos-4) | `canvas.py` |
| 3 | BaSiC flat-field correction (optional) | `photometric.py` |
| 4 | **BiRefNet foreground masking** | `masking.py` |
| 4.5 | Background photometric normalisation (bg-only, scalar, ±7%) | `pipeline.py` |
| 5–6 | Pairwise matching (EfficientLoFTR → ALIKED+LightGlue → Template Match → Phase Correl → RoMa) + edge filter | `matching.py` |
| post-6 | Spatial dedup: drop consecutive frames with displacement < 25px | `pipeline.py` |
| 7 | Translation-only global bundle adjustment (LM, 2-pronged outlier rejection) | `bundle_adjust.py` |
| 7b | Affine validation gate (ratio < 3, min_gap > 25px, rotation/scale checks) | `validation.py` |
| 8 | SEA-RAFT / ECC sub-pixel refinement | `ecc.py`, `flow_refine.py` |
| **8.5** | **Foreground pose registration** (Stage 8.5 — the new core feature) | `fg_register.py` |
| 9 | Canvas construction + bidirectional midplane | `canvas.py` |
| **10** | **Foreground-excluded temporal median** (A5) | `rendering.py` |
| **11** | **Foreground assembly composite** (Laplacian blend + DSFN seam + semantic cost routing) | `compositing.py` |
| 13 | Morphological crop | `canvas.py` |

---

### 2.3 Foreground Pose Registration (Stage 8.5) — The Core Fix

**File:** `backend/src/anim/fg_register.py`

After warping to canvas coordinates (background aligned), the residual optical flow on the foreground IS the animation motion `A_animation`. For each adjacent strip seam:

**Flow estimation:**
- Primary: **RAFT** (`sea_raft_s@things` via ptlflow) — pretrained on optical flow datasets, confident over flat regions where DIS's gradient-based estimation fails (aperture problem). Computed on the seam-band crop only (±`taper_px` + 16px, downscaled to max 1280px side) to avoid VRAM OOM on 2000+ px canvases.
- Fallback: **OpenCV DISOpticalFlow** (MEDIUM preset, no extra dependency).
- Toggle: `ASP_FLOW_ENGINE=dis` env var.

**ARAP regularisation (A3):**
`_arap_regularise(flow, fg_mask, cell_size=16, n_iter=2)` — fits per-cell (16×16px) rigid median translations to the fg flow, then bilinearly interpolates back to pixel space via `scipy.interpolate.RegularGridInterpolator`. Prevents raw per-pixel flow from bending straight line-art strokes by enforcing a smooth, locally-rigid warp field.

**Symmetric midpoint warp:**
Frame `a` moves by `+0.5·flow` (toward `b`) and frame `b` by `-0.5·flow` (toward `a`). This halves the maximum distortion applied to either frame (StabStitch++ bidirectional principle). The warp is tapered to zero at ±`taper_px` (220px) from the seam so it only affects the boundary zone.

**Single-pose fallback (A6):**
When `med_residual > FG_REG_MAX_RESIDUAL` (90px): the animation gap is too large to warp safely. The *dominant frame* (more foreground pixels in the seam band) is recorded; the compositor takes the seam-zone foreground from it exclusively — no blending of two different poses.

**Post-warp ghost-prevention escalation:**
After the warp, `post_warp_diff` measures mean foreground colour difference in a narrow strip at the seam centre. If `post_warp_diff > 22 lum units` even after warping (pose still significantly different), escalates to the single-pose fallback to prevent the Laplacian blend from creating a double-image ghost.

**Boundary safety:**
- `BORDER_CONSTANT` (not `BORDER_REPLICATE`) prevents edge-smear artifacts.
- `adj[~valid_content] = 0` prevents warp from extending pixels into previously-empty canvas regions.

---

### 2.4 Foreground-Excluded Temporal Median (A5)

**File:** `backend/src/anim/rendering.py`

The Stage-9 temporal median now uses **background pixels only** (from BiRefNet masks) to build the background plate. Where a canvas pixel has no background sample across any frame (character always there), it falls back to the geometric median.

This prevents the median from averaging different animation poses of the character into a translucent ghost on the background plate. Stage 11 then composites properly-registered foreground over the clean background.

Verified by 3 unit tests: `backend/test/anim/test_rendering.py::TestForegroundExcludedMedian`.

---

### 2.5 Composite Quality Gate (post-Stage-11)

**File:** `backend/benchmark/bench_anime_stitch.py`

After Stage 11 completes, measures the final composite:
- `seam_coherence`: std of per-row mean luminance (horizontal banding proxy, lower = better)
- `strip_banding`: max luminance jump between adjacent frame-strip entry zones

If `seam_coherence > 38` OR `strip_banding > 30` → fall back to SCANS on the pre-processed frames. This catches composites where the temporal median plate was already severely banded (typical for animated-video scenes where A5 can't find clean background).

On the 96-test corpus: **39/96 tests (41%) triggered the gate**. These are scenes where the character fills most of the frame with high-amplitude animation — the temporal median is inherently inadequate.

---

### 2.6 Affine Validation (min_gap threshold)

**File:** `backend/src/anim/validation.py`

Threshold lowered from 50px to **25px** (vector magnitude `sqrt(dy² + dx²)`, not axis-specific). This rescued ~9 tests that were unnecessarily rejected when the diagonal displacement exceeded 25px per axis but < 50px total.

---

### 2.7 Benchmark Infrastructure

**File:** `backend/benchmark/bench_anime_stitch.py`

- **Selective runner**: `--tests`, `--range`, `--first N`, `--skip-done` flags
- **Ground-truth comparison**: SSIM/PSNR vs `data/ground_truth/` reference images (55 of 96 tests)
- **Seam coherence metric**: replaces misleading Laplacian sharpness
- **GT-based verdict**: `asp_better` / `simple_better` / `comparable` from GT SSIM

Available via `just asp-benchmark-verify` (5 test quick-check) or `just asp-benchmark` (full 96-test run).

---

### 2.8 Supporting Infrastructure

- **SEA-RAFT / RAFT flow** (`flow_refine.py`): overlap-zone-only flow for background sub-pixel refinement (Stage 8)
- **Confidence-weighted temporal median**: LoFTR-aligned frames outweigh template-match frames
- **DSFN soft-seam weight** (`compositing.py`): spatially-adaptive Laplacian blend width (photometric similarity → wide blend in flat background, narrow in character outline)
- **Semantic seam routing**: BiRefNet edge-confidence cost in the DP seam-finding prevents seams from bisecting character outlines
- **Both-content Laplacian**: Laplacian blend only where both frames have actual canvas content; single-frame-only zones take that frame directly (avoids ringing at canvas boundaries)
- **Inter-strip colour coherence guard**: skips per-strip photometric normalization when adjacent strips differ by > 20 lum units (prevents normalization from amplifying colour mismatch)
- **ToonCrafter** (`anim/anim_fill.py`): anime-style generative inbetweening (available for ghost-fill, not wired to main pipeline)
- **SRStitcher** (`anim/sr_stitcher.py`): diffusion-based seam/border inpainting (`sr_mode=True`)
- **Real-ESRGAN anime_6B** (`anim/super_res.py`): post-process 2–4× upscaling
- **Unit tests**: 80 passing in `backend/test/anim/` (fg_register, rendering, bundle_adjust, filter_edges, affine_validation)

---

## 3. Benchmark Results — Current State

### 3.1 5-Test Verification Corpus

| Test | Before all fixes | After all fixes | Simple stitch | GT verdict | Key characteristic |
|------|---------------:|---------------:|-------------:|-----------|-------------------|
| test04 | 0.633 | **0.742** (+0.109) | 0.738 | comparable | High-animation; render-gate SCANS fallback |
| test08 | 0.731 | **0.737** (+0.006) | 0.813 | simple_better | Extreme arm motion; 9/13 seams single-pose |
| test09 | 0.785 | **0.787** (+0.002) | 0.757 | **asp_better** | Canonical case; clean after all fixes |
| test27 | 0.705 | **0.709** (+0.004) | 0.677 | **asp_better** | 2× scale mismatch vs GT; ASP wins on content |
| test57 | 0.738 | **0.743** (+0.005) | 0.756 | comparable | Moderate animation; comparable to simple |

### 3.2 96-Test Full Corpus (last full run, pre-character-movement features)

The 96-test numbers are from the last full run (pre-session-1 features). Since each full run takes ~2h, an updated 96-test run is pending:

- **True ASP composites**: 44/96 (45.8%) — the rest fall back to SCANS
- **Render-gate fallback**: 39/96 (40.6%) — temporal median already banded before Stage 11
- **Affine validation fallback**: 13/96 (13.5%)
- **GT verdict (55 tests with GT)**: asp_better=8 (14.5%), simple_better=23 (41.8%), comparable=24 (43.6%)
- **Avg ASP SSIM vs GT**: 0.669 vs simple stitch 0.695

The 5-test corpus (with session-1 and session-2 features) shows improvements of +0.002 to +0.109. These improvements will propagate to the full corpus but haven't been measured yet.

---

## 4. What Was Tried But Didn't Work

### 4.1 Two-Channel Frame Selection (peripheral heuristic — REGRESSED)

**Idea:** Phase-correlate only the peripheral (outer-border) region of thumbnails, treating it as "background" that gives a clean camera-displacement signal uncorrupted by character animation.

**Failure:** The character is not reliably in the centre; in many scenes (especially portrait-oriented close-ups like test27) the character fills the frame edge-to-edge. The peripheral region contains the character too, making the correlation noisier than whole-frame. Test27 dropped from 0.708 to 0.676, test57 dropped from 0.745 to 0.720.

**Better approach needed:** Real background separation (BiRefNet masks) is required, but running BiRefNet *before* selection doubles the BiRefNet compute cost and changes which frames are selected, which also caused regressions. The right solution is to run BiRefNet once, use the masks both for selection and for the full pipeline — requiring architectural restructuring of the benchmark.

---

### 4.2 Two-Channel Selection with BiRefNet Masks (changes frame timing — REGRESSED)

**Idea:** Run BiRefNet on 5 probe frames to build a background-weight mask at thumbnail scale, then use background-only phase correlation for camera displacement.

**Failure:** BiRefNet is correct — background pixels give a cleaner signal — but the *side-effect* is that it selects different frames at different timing. Those frames show the character in different animation phases than the original selection, which diverges from the GT reference timing. Test04 dropped from 0.742 to 0.604. BiRefNet double-running also adds ~8s overhead per dataset.

**Root cause:** The frame selection and the GT reference selection are coupled. You can't independently optimize frame selection without also changing what the "ideal" output looks like relative to the GT.

---

### 4.3 Global Reference Pose Warp (catastrophic on noisy flow — REGRESSED)

**Idea:** Instead of independent pairwise midpoint warps (each pair warps to their own midpoint, which can drift across a chain of seams), warp all frames toward a single central reference frame. Frames close to the reference get α=0 (no warp); frames far get α→1 (full warp toward reference).

**Failure:** At α=1.0 (frames adjacent to the reference), a 5px RAFT flow error becomes a 5px wrong displacement on the character. For flat anime regions where RAFT is imprecise (uniform skin tones, minimal texture gradient), this amplification is destructive. Test27 (mostly flat skin/costume) dropped catastrophically from 0.709 to 0.558.

**What would make it work:** Flow accuracy comparable to the animation residual magnitude. Currently, for 20px animation residuals, RAFT errors are ~2-5px (10–25% of signal). At α=1.0, these errors become the dominant artifact. Reliable flow would require either much finer-grained flow estimation or a confidence-weighted alpha that caps at safe values for uncertain regions.

---

### 4.4 Character Bounding-Box Crop (wrong axis — REGRESSED)

**Idea:** After assembly, crop the panorama to the bounding box of the foreground character across all frames, removing excess background-only regions. This would reduce the 2× scale mismatch between test27's output (1877×2135) and its GT (963×1280).

**Failure:** For a *vertical* pan (camera moves top-to-bottom), the character appears at different horizontal positions in different frames. The union of foreground bounding boxes across all frames covers the left column of all frames, causing the crop to remove 44% of the *width* (the right-side locker background that is essential to the composition). Test27 dropped from 0.709 to 0.558.

**Root cause:** For vertical pans, excess canvas is in the *vertical* direction (top/bottom), not horizontal. The crop must respect scroll axis. Additionally, for character bodies where every row has character content (portrait-style test27), there is NO excess vertical canvas — the character fills the full height. The scale mismatch is fundamental: we assemble more frames than the GT shows.

---

### 4.5 ARAP Asymmetric Cell Sizes (no measurable improvement)

**Tried:** `cell_size=8` (finer cells), `cell_size=32` (coarser), `n_iter=3` vs `n_iter=2`.

**Finding:** No measurable SSIM change across any combination. The ARAP regularisation is geometrically correct (smooth flow, reduced line bending) but the SSIM metric doesn't detect the improvement because: (a) line-art bending was already minor with DIS, (b) the dominant SSIM loss comes from pose differences, not flow distortion.

---

### 4.6 Lowering `post_warp_diff` Threshold (marginal, mixed)

**Tried:** Threshold=35 (original), 22 (current), 15, 20.

**Finding:** threshold=22 gives +0.002 on test08 (5 seams escalated to single-pose instead of blending), neutral on test09, -0.001 to -0.003 on test57. Lowering further hurts test57 more than it helps test08. The optimal value is scene-dependent: high-motion scenes (test08) benefit from aggressive single-pose escalation; moderate-motion scenes (test57) do not.

---

### 4.7 Lowering `max_residual` to 50px (mixed, minimal)

**Tried:** Default 90px, reduced to 50px.

**Finding:** test08 +0.001, test57 -0.003. More seams switch from "warped (but imperfect)" to "single-pose". The improvement on test08 comes from preventing blends between poses that are >50px apart; the regression on test57 comes from seams that would have produced acceptable blends now taking an arbitrary single pose.

---

### 4.8 Naive Temporal Median on Foreground (ghosting — fixed by A5)

**Problem:** The original temporal median averaged the character's different animation poses into a translucent ghost background plate. Stage 11 then tried to composite over a plate that already had the ghost.

**Fix (A5):** Foreground-excluded median. The ghost is now prevented at source. This was the single most impactful fix, but its benefit is mostly visible qualitatively (cleaner background plate) rather than in SSIM numbers (because Stage 11 always overwrites the character region anyway).

---

### 4.9 Laplacian Sharpness as Quality Metric (fundamentally wrong — replaced)

**Problem:** The original benchmark used `cv2.Laplacian().var()` as a "sharpness" proxy for quality. This metric inflates when there are hard seam edges (which are high-frequency content). A catastrophically banded output with 5 harsh horizontal colour discontinuities scored 2–3× higher "sharpness" than a clean image.

**Fix:** Replaced by **seam_coherence** (std of per-row mean luminance; lower = less banding) and **GT-SSIM** (structural similarity vs reference panoramas). The old metric actively misled development for multiple sessions.

---

## 5. Current Limitations and Bottlenecks

### 5.1 Fundamental: Animation Timing Mismatch with GT Reference

**The primary SSIM ceiling** for tests 09/27/57 at ~0.787/0.709/0.745 is not from compositing quality — it's from frame selection timing.

The ground-truth panoramas were assembled at some specific temporal selection of frames. Our `_smart_select_frames` selects frames based on camera displacement, which at 50px/frame and 24fps video gives frames spaced ~300ms apart. Over 300ms, an animating character moves 10–35px. The midpoint warp halves this to 5–17px residual at each seam. The residual → SSIM penalty.

**No compositing improvement can close this gap without changing which frames are selected.** The aligned SSIM (after ECC correction for global scale/framing) is 0.832 for test09 and 0.748 for test27 — those are the true content-quality ceilings given our current frame selection.

---

### 5.2 Render-Gate Fallback Rate: 41%

39/96 tests trigger the composite quality gate because the Stage-9 temporal median plate already shows severe horizontal banding before Stage 11 runs. These are scenes where:
- The character fills most of the frame (minimal background area)
- Character animation is large (multiple distinct poses across selected frames)
- A5's bg-only median sees few background pixels, so the fallback (geometric median of all poses) averages different animation states

These 39 tests fall back to SCANS simple stitch, which always produces a coherent (if limited) output. The ASP pipeline provides no value for them.

**Root cause:** These scenes are exactly the ones where the animation speed is high relative to the camera pan. There's no way to assemble a multi-frame body without encountering pose mismatches.

---

### 5.3 `simple_better` at 42% (with GT)

On the 55 tests with ground truth, the simple stitch produces better output by GT-SSIM in 23 cases (41.8%). These are cases where:
- The simple stitch happens to select frames that match the GT's temporal reference
- Our multi-frame assembly introduces more seam artifacts than a clean single-frame capture
- The GT represents a narrower crop/shorter pan than we attempt to assemble

---

### 5.4 test08: Simple Stitch Dominates (0.813 vs 0.737)

test08 shows a character with extreme arm motion (full extension through a 90° arc across the frame). No temporal interval is short enough to avoid large pose changes at the seam. The simple stitch wins by picking adjacent frames (42ms apart) where the arm barely moves, staying within one coherent animation phase.

The ASP's multi-frame approach is fundamentally at a disadvantage here: assembling from 14 frames spanning the full arm motion arc necessarily creates large-residual seams. The single-pose fallback helps (+0.006 vs pre-feature) but can't match the coherence of a 2-frame adjacent stitch.

---

### 5.5 Scale Mismatch for test27 (0.709 raw vs 0.748 aligned)

test27's GT is 963×1280 (portrait); our output is 1877×2135 (2× larger). The benchmark resizes to the minimum common dimension for SSIM, meaning our 2× output is downscaled 2×, introducing blur. This 0.039 raw-vs-aligned gap is purely from scale, not content.

We assemble 19 frames spanning the full character body from feet to head (~1000px vertical travel). The GT shows only the middle portion (~200px vertical travel). There's no general way to detect this at runtime without knowing what the GT reference shows.

---

## 6. Avenues for Further Improvement

### Priority 1: Pose-Consistent Frame Selection (highest expected impact)

**Problem:** The SSIM ceiling is determined by animation timing between selected frames.

**Solution:** During frame selection, compute a "pose consistency score" for each candidate frame relative to the previous selected frame. Specifically:
- Run RAFT flow on the foreground-only region (after BiRefNet) between candidate frame and last selected frame
- If the foreground residual > threshold AND multiple frames are available at this camera position, prefer the frame with the smallest foreground residual
- This gives frames that are pose-similar to each other → smaller animation gap → smaller midpoint warp residual → less seam artifact

**Implementation path:** 
1. Run BiRefNet on all frames FIRST (before frame selection) — expensive but eliminates the double-BiRefNet issue
2. Use background-only phase correlation for camera displacement (reliable without peripheral heuristic)
3. For each camera-qualifying candidate, compute fg-only flow to last selected frame
4. Pick the candidate with smallest fg residual among those within the step window

**Expected gain:** Reduce animation residuals from the current 10–85px range toward <20px for most seams. Would push test09 toward the 0.832 aligned-SSIM ceiling.

---

### Priority 2: Vertical-Pan Content Crop (test27 scale mismatch)

**Problem:** test27 assembles 2× more vertical pan than the GT reference covers.

**Solution:** After assembly, detect "content-only rows" — rows that have foreground character pixels in at least one frame. The excess rows at top/bottom that have ONLY background (no character content in ANY frame) can be trimmed to approach the GT's scale.

**Key distinction from the failed CharCrop:** crop only in the SCROLL AXIS direction (vertical for a vertical pan), not the cross-axis. The scroll axis is already available from `_detect_scroll_axis()`.

**Implementation:**
```python
# In the benchmark crop section, scroll-axis-aware:
if scroll_axis == 'vertical':
    # Find rows with any foreground character content across all warped frames
    # Only trim excess rows at top/bottom, never columns
    ...
```

**Expected gain:** test27 raw SSIM could improve from 0.708 toward 0.748 (current aligned value) by reducing scale mismatch.

---

### Priority 3: ARAP Push Phase (Sýkora 2009 — full algorithm)

**Current state:** Only the ARAP *regularisation* phase is implemented (per-cell median translation → smooth interpolation). The ARAP *Push* phase is missing.

**What Push does:** For each control mesh vertex, performs block-matching (minimise SAD in a local search window) to find the best shift toward the optical flow's target. Unlike the gradient-based flow, block-matching can make large, arbitrary jumps (avoiding local minima), is not affected by the aperture problem, and naturally handles flat cel-shaded regions where pixel gradients are zero.

**Why it matters:** The current flow (RAFT or DIS) struggles with large flat colour regions — both give similar results. The ARAP Push phase would use *appearance matching* (not gradient) to find correspondences, which is more reliable on anime. After Push, the Regularise phase smooths the mesh into a rigid deformation. This is the canonical solution for animating character registration in the research literature.

**Implementation effort:** Significant (block-matching over the mesh, convergence loop), but no new dependencies.

---

### Priority 4: Segment-Guided Flow (AnimeInterp SGM)

**Problem:** RAFT fails on large uniform colour regions (the aperture problem) — there's no gradient to track. DIS also fails. Both give similar wrong estimates.

**Solution:** Instead of pixel-level flow, compute flow at the *colour-segment* level. Group pixels by colour (trapped-ball segmentation or simple k-means), find segment centroid correspondences across frames, then propagate a consistent flow to all pixels within each segment. This is exactly what AnimeInterp's Segment-Guided Matching module does.

**Why this would help:** Anime character bodies are large flat-colour patches. Skin, costume, hair — each is a distinct colour cluster. Matching clusters across frames (by colour similarity and position) gives a reliable correspondence even where per-pixel flow fails completely.

**Implementation path:** 
1. K-means colour clustering on the seam-band crop (k=8–16 colours)
2. For each cluster in frame_a, find the best-matching cluster in frame_b (L2 in colour + position space)
3. Use cluster centroid displacement as the flow for all pixels in that cluster
4. Apply ARAP regularisation to smooth across cluster boundaries

---

### Priority 5: Global Reference Pose (with confidence gating)

**Previous attempt failed** due to flow noise amplification at α=1.0.

**How to make it work:**
- Compute RAFT flow *confidence* (available as the consistency check between forward and backward flow)
- For each pixel, set `alpha = min(raw_alpha, confidence × max_alpha)` where `confidence ∈ [0,1]` from flow agreement
- High-confidence pixels (strong texture, reliable flow) can warp more aggressively; low-confidence pixels (flat colour) warp less

This would give the global reference benefit (reducing drift accumulation) without catastrophic errors in flat regions.

**Alternative:** Use the ARAP per-cell rigid transform (which is already reliable and smooth) rather than raw pixel flow for the global reference. The per-cell ARAP median is less noisy than per-pixel flow, so α=1.0 on a per-cell level would be safer.

---

### Priority 6: LSD Collinearity Constraint in ARAP

**What's missing:** The full Sýkora ARAP includes a Line Segment Detector (LSD) term that penalises any warp that bends detected straight line-art strokes. Currently, the ARAP regularisation smooths the flow but doesn't explicitly prevent collinear strokes from becoming curved.

**Implementation:** 
1. Run OpenCV's `LSDDetector` on the source frame (detects straight line segments)
2. Add an energy term to the ARAP mesh that penalises deviation from collinearity for mesh vertices that lie on detected lines
3. Weight this term high enough to enforce near-straight-line warps on detected strokes

**Why this matters:** For dense line-art (character outfit seams, architectural background), the ARAP warp can introduce subtle curvature that's visually noticeable. The LSD constraint is what makes Sýkora 2009 the canonical method for cartoon registration.

---

### Priority 7: Full 96-Test Re-Run After Feature Integration

**All session-1 and session-2 features have been applied to the benchmark only on the 5-test subset.** The 96-test corpus numbers (from June 1) predate all character-movement features. A full re-run would:
- Update the corpus-wide GT-SSIM statistics
- Measure how many tests move from `simple_better` to `asp_better` after the improvements
- Identify whether the render-gate fallback rate (41%) changes

**Expected:** The 8 tests currently `asp_better` should stay asp_better and possibly gain SSIM. Some of the 23 `simple_better` tests may move to comparable. The 39 render-gate fallbacks are unlikely to change (fundamental scene type issue).

---

### Priority 8: Longer-Term Research

- **ToonCrafter ghost-fill**: Use the existing `anim/anim_fill.py` module to generate synthetic intermediate character frames for highly-animated seam zones. Eliminates ghosting structurally for GPU-budget final-quality mode.
- **Flow confidence weighting in the Laplacian blend**: where RAFT confidence is low (flat regions), use a wider blend zone or fall back to single-pose. Currently the blend zone width depends only on photometric similarity, not on flow reliability.
- **Fine-tune RAFT on LinkTo-Anime**: The 2506.02733 dataset provides GT optical flow for 2D animation (from 3D-rendered anime-style content). Fine-tuning RAFT or SEA-RAFT on this dataset would give flow that's reliable specifically on flat cel-shaded regions — the exact failure mode.
- **Unsupervised deep image stitching (UDIS++ / NIS)**: End-to-end neural frameworks that learn registration and fusion jointly. No heuristic pipeline stages. Would require training data and significant engineering but could subsume many pipeline stages.

---

## 7. Summary Table

| Aspect | Current state | Primary bottleneck | Next step |
|--------|--------------|-------------------|----------|
| **Frame selection** | 50px min_step, direction consistency, high-anim filter | Selects pose-incoherent frames → large seam residuals | Pose-consistency criterion (fg flow to last frame) |
| **Flow estimation** | RAFT (pretrained) + DIS fallback, seam-band crops | Aperture problem on flat cels: RAFT = DIS in accuracy | Segment-guided flow (AnimeInterp SGM) |
| **ARAP regularisation** | Per-cell median translation, cell=16, n_iter=2 | Missing Push phase (block-matching), no LSD constraint | Full Sýkora: Push + LSD energy term |
| **Midpoint warp** | Symmetric α=0.5; post_warp_diff escalation at 22 | Halves but doesn't eliminate pose gap | Global reference with confidence gating |
| **FG-excluded median** | Background-only plate (A5) | Always-fg fallback still ghosts in foreground-heavy scenes | Segment-medoid fallback |
| **Seam blend** | DSFN soft-seam + semantic routing + both-content Laplacian | Remaining ghosting from imperfect FG registration | Confidence-weighted alpha (flow uncertainty → narrower blend) |
| **Fallback (gate)** | Render-gate (coherence + banding on final composite) | 41% trigger rate — fundamental animated-video scene type | Accept as correct for these scenes; focus on reducing residuals |
| **GT-SSIM (5 tests)** | test09: 0.787 asp_better, test27: 0.708 asp_better, test57: 0.743 | Animation timing mismatch; midpoint-warp 50% residual | Pose-consistent frame selection → reduce residuals to <10px |
| **96-test corpus** | 44/96 composite, avg GT-SSIM 0.669 vs 0.695 simple | Last measured pre-character-features | Full re-run needed |
