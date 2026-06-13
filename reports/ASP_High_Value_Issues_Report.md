# ASP Quality Report — Highest-Value Issues & Implementation Options

*Generated: 2026-06-13. Based on sessions 1–75, 482 unit tests passing, 96-test corpus.*  
*Last full benchmark: S4 (2026-06-04). Per-test improvements since S4 are in individual session notes but the corpus-wide delta has not been re-measured.*  
*Implementation status last updated: 2026-06-13 (S79–S80). Status legend: ✅ = shipped and wired, 🔧 = partially implemented, ⬜ = not yet started.*

---

## Executive Summary

The Anime Stitch Pipeline now produces true ASP composites for ~92/96 tests (down from 44/96 at S0). The pipeline's defensive infrastructure — gates, retry chains, fallbacks, seam refinements — is mature. The remaining quality gap is **structural**, not parametric: the corpus-wide GT-SSIM of ASP (0.667) still trails simple stitch (0.694), and in tests with ground truth, ASP wins outright only ~14% of the time.

**The gap will not close by adding more gates or seam cost terms.** The 50+ sessions of refinement since S11 have improved visual quality but haven't moved the GT-SSIM needle materially because none of them address the two root causes:

1. **Frame selection picks the wrong frames** — phase correlation conflates character animation with camera panning, selecting frames where the character is in incompatible animation states. No amount of compositing can fix a torn body that was torn before the pipeline started.
2. **Flow estimation fails on flat cel regions** — RAFT, DIS, and ARAP Push all produce chaotic or zero vectors on uniform-color skin/cloth/sky, so the midpoint warp cannot bridge the animation gap even when the right frames ARE selected.

Everything below is ordered by expected impact on those two root causes — and by impact on the HITL (human-in-the-loop) pipeline, which can bypass both.

---

## Failure Taxonomy (current)

| Category | Tests affected | Root cause | Fixed? |
|---|---|---|---|
| A — Frame selection picks wrong animation states | ~30–40 tests | Phase correlation measures whole-frame displacement incl. character | **Partially — §1A Otsu bg-only corr (S80), HITL selection dialog (S79)** |
| B — BA outlier dominance / affine validation | ~5–8 tests | Bad LoFTR match hijacks spanning tree consensus | **Mostly fixed (S37/S45/S60)** |
| C1 — Seam cuts through character bodies | Subset of 92 composites | DP seam routes into character when no background corridor exists | **Partially fixed (S33/S67)** |
| C2 — SSIM ceiling from animation timing | All tests with GT | ASP picks a different frame than GT reference → mismatched pose | **HITL path fixed (S79 selection dialog)** |
| D — Aperture problem on flat regions | Any test with flat-color character fills | RAFT/DIS gradient-based flow fails on uniform color | **Partially fixed — AnimeInterp SGM VGG-19 (S79)** |
| E — Background plate median ghosting | High-character-coverage tests | Character fills >70% of frame → temporal median can't find pure-bg sample | **Partially fixed — BG completion NN fill (S80), SAM-2 masking (S79)** |

---

## Issue 1 — Pose-Consistent Frame Selection [HIGHEST IMPACT]

**Impact: Fixes Category A (30–40 tests). All compositing improvements are irrelevant if wrong frames are selected.**

### Root Cause

`smart_select_frames()` uses phase correlation on the whole frame. When a character occupies 60%+ of the screen and is mid-swing, the displacement signal includes `T_camera + A_limb_swing`. The selector treats a 45px limb swing + 5px camera move as a "50px camera advance" and accepts the frame. The next selected frame is then from 400ms later, showing the same camera position but a completely different arm pose → torn body at the seam.

This is the single root cause of the render quality gate firing on 39/96 tests at S0. Most of those tests now pass the gate through gate widening and retries (S11), but they pass by producing a *worse* composite — the seams still exist; we just stopped rejecting them. Visual inspection would likely confirm that many "comparable" tests are visually inferior to simple stitch.

### Options

**Option A — Background-Only Phase Correlation [High Impact, Medium Effort]**

Use BiRefNet masks (already computed at Stage 4) *before* frame selection to black out the foreground before running phase correlation. The background pixels give a clean camera-displacement signal.

*Why this hasn't been done:* Running BiRefNet before selection doubles the per-dataset cost and changes which frames are selected, which causes GT-coupling regressions (tested in S3–S5, always regressed). The fix is architectural: run BiRefNet ONCE on all frames before anything else, then use those masks for both selection and the pipeline proper.

- **Files to change:** `frame_selection.py` → `smart_select_frames()`, `bench_anime_stitch.py` → `_smart_select_frames()`, `pipeline.py` → Stage 4 moved to before Stage 1.
- **Effort:** ~2d (primarily benchmark restructuring; the phase correlation call is one line)
- **Expected impact:** Large. Tests where the character fills 60%+ of the frame (Category A majority) would get a clean camera signal and stop selecting incompatible animation states.
- **Cons:** BiRefNet costs 0.3–0.8s per frame; 333 frames × 0.6s = ~3 min added overhead. Mitigate with stride-sampled masks (every 5th frame for selection phase, all frames for pipeline).

**Option B — ViTPose / DWPose Pose Similarity Metric [High Impact, Medium Effort]**

Use a pose estimator (ViTPose-Base finetuned on AnimePose, or DWPose) to extract 2D joint coordinates from each frame. In Pass 2 of the two-pass selector, prefer frames where the joint-to-joint distance vs the previous selected frame is minimal. Background-agnostic by construction.

- **Files to change:** `frame_selection.py` → `_compute_dinov2_features()` → replace or augment with pose embedding
- **Effort:** ~2d (DWPose is pip-installable; fine-tuning for anime not required — it generalises well to cel-shaded characters)
- **Expected impact:** Large on tests where the character has a clear human skeleton. Moderate on chibi/deformed characters where joint detection fails.
- **Cons:** DWPose adds ~70ms/frame inference on GPU. AnimePose fine-tune would improve coverage on non-realistic characters.
- **Resources:** DWPose (ECCV 2023): `github.com/IDEA-Research/DWPose`

**Option C — Overmix-Style Animated Aligner [High Impact, High Effort]**

Compute per-frame pixel difference on BACKGROUND-SUBTRACTED consecutive frames (character masked out). Static periods → low diff; animation transitions → spikes. Threshold spikes to identify "cel boundaries" — frames where the animation pose changes. Select one frame per animation-hold block (using the existing `_detect_hold_blocks` infrastructure), so all selected frames come from the same animation state.

This is the practitioner-proven approach used by Overmix (`spillerrec/Overmix`), adapted with proper BiRefNet masking.

- **Files to change:** `frame_selection.py` → major rewrite of selection loop
- **Effort:** ~3d
- **Expected impact:** Very large. Directly addresses the animation-hold structure of the problem. Hold detection (S6/S43) already identifies these blocks; the selector just needs to respect them.
- **Cons:** For continuous-animation scenes (no holds), all frames may show high diff; selector falls back to displacement-only criterion.

**Option D — Foreground-Masked DINOv2 (Incremental, Default-On) [Medium Impact, Low Effort]** ✅ *Shipped S79*

DINOv2 frame selection is already implemented (S8) but disabled by default due to GT-coupling regressions. The regression happened because DINOv2 on the full frame is still confounded by background content. The fix: crop to the BiRefNet foreground bounding box before passing to DINOv2, making the embedding purely pose-driven.

This is a targeted 10-line change to `_compute_dinov2_features()` that could be A/B tested quickly.

- **Files changed:** `frame_selection.py` → `_compute_dinov2_features()` — Otsu threshold bbox crop added before PIL tensor conversion. Falls back to full frame if crop is degenerate (<32px). Shipped S79.
- **Expected impact:** Medium. Might break the GT-coupling regression. Worth trying as the fastest Path A before committing to Options B/C.
- **Cons:** Still coupled to BiRefNet mask quality. For tests where BiRefNet fails (hair, transparency), the crop will be wrong.

**Option E — HITL Selection Review Dialog [Guaranteed Impact, Low Effort]** ✅ *Shipped S79*

After `smart_select_frames()`, show a modal `QDialog` with scrollable thumbnail tiles. Each tile shows the frame image, its canvas advance in pixels, and a colour-coded "pose diff" bar (DINOv2 cosine distance to the previous selection). User can exclude tiles, drag to reorder, add frames, and toggle a "show only high-pose-diff frames" filter.

This is the only option that guarantees improvement — a human looking at 20 thumbnail tiles can pick the best poses in 30 seconds. It also directly closes the GT-coupling problem: the user sees the composite reference and can match poses visually.

- **Files changed:** `gui/src/dialogs/selection_review_dialog.py` (new, 210 lines). Wired into `StitchWorker` via `sig_review_frames` / `_on_hitl_review_frames` slot in `stitch_tab.py`. Pause/resume via `QWaitCondition`. Shipped S79.
- **Expected impact:** Very large for HITL pipeline. Zero change to fully automated pipeline (dialog bypassed in batch mode).

**Recommendation (automated):** D ✅ done. A as next automated fix (Option A Otsu bg-only corr now partially shipped S80). C for the long-term redesign.
**Recommendation (HITL):** E ✅ done. 4B (seam inspector) is next priority for HITL quality.

---

## Issue 2 — Aperture Problem on Flat Cel Regions [HIGH IMPACT]

**Impact: Fixes Category D. Prerequisite for the foreground assembly to actually work on flat-color characters.**

### Root Cause

RAFT, DIS, and ARAP Push are all gradient-based flow estimators. On flat-color anime regions (skin, plain costume panels, sky), there are NO intensity gradients → the flow estimator has zero signal → it either hallucinates chaotic vectors or returns zero. The midpoint warp then applies noise-driven displacements or leaves the seam uncorrected. This is the fundamental reason sessions 2–10 saw zero SSIM improvement from flow quality improvements — the problem was always that the flow was wrong in the flat regions, not that the warp or regularization was wrong.

ARAP Push (S4) was supposed to fix this via block-matching, but block-matching also fails on uniform color (any shift produces equal SAD cost → random matching). The SLIC SGM proxy (S6) is the right approach but too coarse-grained for fine animation timing.

### Options

**Option A — AnimeInterp SGM (Full Implementation) [Very High Impact, Medium Effort]** ✅ *Shipped S79*

Replace `_arap_push()` in `fg_register.py` with the AnimeInterp Segment-Guided Matching algorithm:
1. Segment each frame's seam-band crop using Laplacian-of-Gaussian contour detection + watershed ("trapped-ball" filling) → each closed uniform-color region gets a unique segment ID
2. Describe each segment via VGG-19 features pooled at `relu1_2, relu2_2, relu3_4, relu4_4`
3. Match segments across the two frames using a Matching Degree Matrix: `M = α·VGGAffinity + β·DistancePenalty + γ·SizePenalty` (Hungarian assignment)
4. Each pixel's flow = centroid displacement of its matched segment pair
5. Feed SGM flow into `_arap_regularise()` as the initial estimate

The SLIC SGM proxy (S6) approximated step 1–4 with colour-only SLIC and centroid matching, skipping VGG-19 feature extraction. That approximation was too coarse for fine animation transitions.

- **Files changed:** `fg_register.py` → `_get_vgg19_feat()` lazy singleton + `_animeinterp_sgm()` (SLIC segmentation → VGG-19 conv3_4 mean-pool L2-normalised per-segment features → cosine+distance combined matching → centroid-displacement flow). Enable: `ASP_ANIMEINTERP_SGM=1`. Falls back to `_slic_sgm_proxy` when VGG-19 unavailable. Shipped S79.
- **Expected impact:** Large. This is the only known method that sidesteps the aperture problem entirely. CVPR 2021 validation on anime.
- **Cons:** VGG-19 forward pass: ~15–30ms per seam crop on GPU. 15 seams → 0.3–0.5s overhead. No anime fine-tuning required (VGG features generalise from ImageNet to anime outlines).
- **Code reference:** `github.com/lisiyao21/AnimeInterp` → `models/sgm.py`

**Option B — LinkTo-Anime Fine-Tuned SEA-RAFT [Very High Impact, High Effort]**

Fine-tune SEA-RAFT (currently installed via ptlflow) on the LinkTo-Anime dataset (arXiv 2506.02733, released 2025): 395 sequences, 24,230 training frames of 3D-toon-shaded characters with GT pixel-perfect optical flow. Load the fine-tuned checkpoint via `ASP_FLOW_ENGINE=sea_raft_anime`.

This produces a flow engine that has seen hundreds of cel-shading examples during training and learns which features are reliable on flat regions, rather than hallucinating gradients.

- **Files to change:** `flow_refine.py` / `fg_register.py` → add `sea_raft_anime` engine path; new `scripts/train_sea_raft_anime.sh`
- **Effort:** ~1w (download LinkTo-Anime, run fine-tuning on 3090 Ti, evaluate on ASP corpus)
- **Expected impact:** Very large if the domain gap from 3D-rendered to hand-drawn cel shading is small. Cross-validate on ATD-12K (real animation studio frames) to measure gap.
- **Cons:** Requires ~24GB VRAM for full fine-tuning (use gradient checkpointing on 24GB 3090 Ti). Alternatively: LoRA-style fine-tuning of only the feature pyramid (top 3 layers) to stay within VRAM. Training time: ~12h on 3090 Ti.

**Option C — ConvGRU Recurrent Flow Refinement [Medium Impact, High Effort]**

After SGM gives the coarse per-segment flow, use AnimeInterp's ConvGRU component to iteratively refine the flow field in null regions (pixels not covered by any segment match). The GRU's hidden state propagates confidence across the image, filling zero-confidence zones guided by the confident regions.

- **Files to change:** `fg_register.py` → after `_sgm_match()`, add `_convgru_refine(flow, confidence_mask)` 
- **Effort:** ~1w (depends on Option A being done first)
- **Expected impact:** Medium. The GRU adds ~40ms/seam but produces more coherent flow fields than raw SGM alone.
- **Dependency:** Requires Option A. Train on ATD-12K (1200 clips, available).

**Option D — SAM-2 Segment-Guided Flow (Replace BiRefNet + Flow) [High Impact, Medium Effort]**

Use SAM-2's video predictor to produce consistent segment IDs across all frames from a single bounding-box prompt. Treat each SAM-2 segment as a rigid body: its centroid-to-centroid displacement between adjacent frames is the flow vector for all pixels in that segment. No VGG-19 required — SAM-2's own memory tokens track appearance.

This combines Issues 3 (SAM-2 segmentation) and 2 (aperture problem) into one fix.

- **Files to change:** `masking.py` → replace BiRefNet with SAM-2 video predictor; `fg_register.py` → use SAM-2 segment IDs for flow
- **Effort:** ~1w
- **Expected impact:** Very large. SAM-2 provides temporally consistent masks AND a natural segment vocabulary that works on flat-color regions without VGG features.
- **Resources:** `github.com/facebookresearch/sam2` (MIT license, installable via pip)

**Recommendation:** A immediately (highest impact, reuses existing ASP structure). D as the architectural upgrade that also fixes Issue 3.

---

## Issue 3 — SAM-2 Video Segmentation (Replacing BiRefNet) [HIGH IMPACT]

**Impact: Fixes mask jitter, enabling consistent temporal median, better seam cost routing, and SGM-compatible segments.**

### Root Cause

BiRefNet runs independently on each frame with no cross-frame consistency. A pixel on the character's hair may be classified as foreground on frame 12 but background on frame 13 (BiRefNet uncertainty zone). This mask jitter causes:
- Temporal median to bleed character pixels into the background plate
- DSFN seam cost map to have noisy foreground boundaries
- Stage 8.5 fg_register to warp the wrong pixels

SAM-2 (arXiv:2408.00714) runs as a streaming video predictor: one bounding box or point click on frame 1 propagates a consistent mask across the entire sequence via a memory bank of object tokens. On cel-shaded characters (clean outlines, solid fills), SAM-2 achieves near-perfect tracking without any fine-tuning.

### Options

**Option A — SAM-2 Video Predictor with BiRefNet Bbox Prompt [High Impact, Medium Effort]** ✅ *Shipped S79–S80*

1. Run BiRefNet on frame 1 only → extract character bounding box (or centre-of-mass click)
2. Pass the bbox as a prompt to SAM-2 video predictor
3. Stream remaining frames through SAM-2 → consistent mask sequence
4. Use SAM-2 masks in all downstream stages (temporal median, seam cost, fg_register)

- **Files changed:** `masking.py` → `_compute_fg_masks_sam2()` (S79). `pipeline.py` → `_USE_SAM2` flag, `AnimeStitchPipeline._compute_fg_masks()` routes through SAM-2 when `ASP_USE_SAM2=1` (S80). Requires `pip install sam2` + checkpoint at `$SAM2_CKPT`. Falls back to per-frame BiRefNet on any error.
- **Expected impact:** Large. Eliminates mask jitter. Hiera-B+ runs at 43.8 FPS on A100 (well under ASP's current frame rate of ~15s/frame on 3090 Ti).
- **Cons:** SAM-2 memory usage scales with sequence length. At 333 raw frames, memory bank may need periodic resetting. Use stride-sampled key frames only.

**Option B — BiRefNet + SAM-2 Union Mask [Medium Impact, Low Effort]**

Keep BiRefNet for each frame; run SAM-2 to get the mask; take the UNION (OR) of both. This preserves BiRefNet's per-frame accuracy while adding SAM-2's temporal consistency. Best for translucent/semi-transparent effects (hair tips, magical glows) where SAM-2 masks may be tight.

- **Effort:** ~1d (add SAM-2 call alongside BiRefNet in `masking.py`)
- **Expected impact:** Medium. Reduces jitter without fully replacing BiRefNet.

**Option C — SAM-2 with User Point Prompt (HITL Mode) [High Impact for HITL, Low Effort once A is done]**

In HITL mode, show frame 1 as a `QLabel` and let the user click on the character to place a SAM-2 prompt point. Pipeline uses SAM-2 tracking from that point. This is the ideal UX for cases where BiRefNet misidentifies the foreground object.

- **Effort:** ~1d after Option A is done (just add click capture to the stitch UI)
- **Expected impact:** Very large for HITL. User can fix any segmentation failure in 2 clicks.

**Recommendation:** A as the default-path upgrade. C as the HITL enhancement. B as a conservative interim if SAM-2 memory usage proves problematic.

---

## Issue 4 — HITL Staged Execution Architecture [CRITICAL FOR HYBRID PIPELINE] ✅ *Shipped S79*

**Impact: Enables all human-in-the-loop interventions. Prerequisite for §2.1–§2.6 from asp.md.**

### Current State (S79+)

`StitchWorker` now uses `QWaitCondition`/`QMutex` pause/resume architecture with 4 HITL pause checkpoints. All options below are shipped.

### Core Architecture Change (~200 LOC) ✅ *Shipped S79*

Add `QWaitCondition` pause points at 4 stage checkpoints in `StitchWorker`:

```python
# New signals
stage_selection_done   = Signal(list)       # List[FrameInfo] with path, canvas_advance_px, pose_diff_score
stage_edges_ready      = Signal(list)       # edge graph dict list
stage_render_ready     = Signal(object)     # (canvas_image, coverage_map array)
stage_fg_registered    = Signal(list)       # seam_info list with residual_px, post_warp_diff, fallback_status

# New override setters (called by UI before resume())
def set_frame_selection_override(self, paths: List[str]) -> None: ...
def set_edge_override(self, deleted, added) -> None: ...
def set_seam_overrides(self, overrides: Dict[int, str]) -> None: ...
def resume(self) -> None: ...  # unblocks QWaitCondition
```

All pauses are opt-in via a "Review mode" checkbox in the Stitch tab. Default: all pauses disabled (no change for existing users).

### HITL Options (post-architecture change)

**Option A — Frame Selection Review Dialog (~300 LOC) [Highest Priority for HITL]** ✅ *Shipped S79*

Modal dialog showing ~20 thumbnail tiles. Each tile displays:
- Frame thumbnail (96px wide)
- Canvas advance in pixels
- DINOv2 cosine-distance bar to previous frame (green/yellow/red)
- Lock/exclude toggle

User can exclude bad frames, drag-reorder, or click "Accept All" to proceed without review. Single toggle: "Show only high pose diff (>0.4)".

*Impact:* Directly closes the GT-coupling ceiling. A user can pick the pose closest to their target in 30 seconds — something the automated selector cannot do reliably.

**Option B — Seam Registration Inspector (~500 LOC) [Highest Impact for Final Quality]** ✅ *Shipped S79 (as EdgeReviewDialog)*

After Stage 8.5 (fg_register), show a vertical scrollable panel of "seam cards" sorted by `post_warp_diff` descending. Each card shows:
- Seam index and canvas position
- `residual_px` and `post_warp_diff` values
- Status: ✓ blended / ⚠ single-pose / ✗ skipped
- ±50px crop of the seam in the blended output
- Toggles: "Force single-pose", "Force blend", "Skip registration"

"Re-composite" button re-runs Stage 11 with overrides (~1s).

*Impact:* The `post_warp_diff=22` threshold escalation is a heuristic that misses many seams (both false positives and negatives). A user inspecting 8–15 seam cards can fix every misclassified seam in ~2 minutes.

**Option C — Coverage Heatmap Widget (~80 LOC) [Quick Win]** ✅ *Shipped S79*

After Stage 10 (temporal median), show a vertical bar chart coloured by row coverage: red=1 frame, amber=2, green=3+. A "coverage warning" label appears when > 30% of rows are single-frame.

*Impact:* Tells the user in advance if the render gate will fire and what to do about it (add a frame at that coverage gap).

**Option D — Canvas Layout Inspector (~350 LOC) [Already Partly Shipped — Session 63]** ✅ *Interactive nudge + heatmap shipped S79*

Show all N frames as semi-transparent coloured rectangles at their final canvas positions. Add an overlap-zone heatmap toggle (same colour scheme as Option C). Allow ±10px drag-nudge of individual frames for manual fine-tuning.

*Note: Read-only viewer was shipped in S63. The interactive nudge and heatmap overlay are the remaining additions.*

**Recommendation priority for HITL:**
1. Architecture change (QWaitCondition pauses) — prerequisite
2. Option A (frame selection review) — immediately closes the biggest quality gap
3. Option B (seam inspector) — fixes the remaining quality gap in true ASP composites
4. Option C (coverage heatmap) — prevents render gate surprises
5. Option D (canvas nudge) — useful but lower priority

---

## Issue 5 — Background Completion via ProPainter [MEDIUM IMPACT]

**Impact: Fixes background plate in tests where the character covers >70% of the frame.**

### Root Cause

The foreground-excluded temporal median (Stage 10, A5) works when each canvas row has at least 2 frames contributing background pixels. When the character is large and moves slowly, many canvas rows have 0 pure-background samples across ALL selected frames. The median degenerates to "frame 0's pixels here", creating visible strip boundaries where neighbouring frames have different background states.

Stage 10.5 (Coverage Gate, S13) catches the worst cases and falls back to SCANS, but "comparable" tests may have partial coverage failure that passes the gate yet still shows banding.

### Options

**Option A — ProPainter Video Inpainting [High Impact, Medium Effort]**

After Stage 10 (temporal median), identify canvas pixels with zero background samples (all frames have character there). Use ProPainter (ICCV 2023) to inpaint those regions using the surrounding temporal context. ProPainter uses a flow-guided recurrent network trained on video inpainting and handles large masked regions coherently.

- **Files to change:** New `backend/src/anim/bg_complete.py` → `complete_background(canvas, bg_coverage_mask)` called after Stage 10
- **Effort:** ~2d (ProPainter is pip-installable: `pip install propainter`; inference API is simple)
- **Expected impact:** Medium-Large. Directly targets the "character fills the frame" failure mode. On 3090 Ti: ~0.5–1s per 1080p canvas row that needs inpainting.
- **Cons:** ProPainter is trained on natural video, not cel animation. May produce blurry/unsharp fills that clash with anime's crisp line art. Safeguard: only apply to zero-coverage regions (character was always there — no reference background exists anyway).
- **Resources:** `github.com/sczhou/ProPainter` (MIT license)

**Option B — SRStitcher / Stable Diffusion Inpainting [High Quality, High Effort]**

Use the existing `sr_stitcher.py` → `inpaint_gaps()` for the zero-coverage background regions. SD-based inpainting at `sr_mode=True` produces anime-coherent fills.

- **Effort:** ~0.5d (sr_stitcher is already wired for border fills; extend to coverage-zero zones)
- **Expected impact:** High quality on small regions. Slow for large zero-coverage zones (5–30s per region).
- **Cons:** Inference cost. Best reserved for `final_quality=True` mode.

**Option C — Nearest-Neighbour Background Extrapolation [Low Quality, Low Effort]**

For canvas pixels with no background sample, copy the nearest same-column background pixel (extrapolate vertically). Produces clean fills for scenes with pure vertical pans and simple backgrounds (e.g., plain wall), but creates visible discontinuities on complex backgrounds.

- **Effort:** ~2h
- **Expected impact:** Low quality but zero inference cost. Useful as a fallback when ProPainter/SD are unavailable.

**Recommendation:** A for default mode (ProPainter is cheap and good enough for most cases). B for `final_quality=True`. C as the last-resort fallback.

---

## Issue 6 — RLHF Calibration + Bayesian Parameter Search [MEDIUM IMPACT]

**Impact: Enables self-improving pipeline once per-test feedback is accumulated.**

### Current State

The RLHF infrastructure is complete (S29): `StitchRewardModel`, `_compute_rlhf_score()`, `rlhf_score` and `rlhf_flagged` in every benchmark result dict. The reward model currently uses **random weights** — it produces scores but those scores have no semantic meaning.

The RLHF loop cannot improve the pipeline until the reward model is calibrated on human feedback.

### Options

**Option A — Manual Score Collection via Feedback Tab [Prerequisite]**

The `StitchFeedbackTab` already exists. Connect it to the benchmark output: for each output flagged `rlhf_flagged=True`, queue it for human rating (1–5 stars) in the feedback tab. Store ratings in a SQLite table. After 50+ ratings, retrain the reward model CNN.

- **Effort:** ~1d (wire feedback tab to benchmark JSON output; add retraining script)
- **Expected impact:** Prerequisite for everything below. No other option works without this.

**Option B — Bayesian Parameter Search via Optuna [High Impact once A is done]**

Use the calibrated reward model as the objective for `optuna.create_study(direction="maximize")` over the key compositing parameters:
- `ASP_SP_SOFT_PX` (0–30)
- `ASP_SEAM_HARD_BARRIER` (0/1)
- `ASP_FG_FEATHER_CAP` (40–120)
- `ASP_TIGHT_STEP_PX` (0–50)
- `ASP_SEAM_INSTABILITY_THRESH` (0–50)
- `ASP_ADAPTIVE_SP_THRESH` (0/1)
- `ASP_SEAM_LUM_EQ` (0/1)

Run on the 55 GT-tests over 50–100 Optuna trials (~12h on 3090 Ti). The reward model replaces the human oracle during search.

- **Effort:** ~2d after Option A
- **Expected impact:** Medium. Current compositing parameters were tuned manually on a small subset. Bayesian search over the full 55-test corpus may find configurations that outperform manual tuning.
- **Cons:** Optuna + reward model pipeline adds complexity. Must guard against reward model overfitting (the model's ratings may not perfectly correlate with GT SSIM on unseen tests).

**Option C — DPO / RLHF Fine-tune of SeamBlend [Long-term]**

Fine-tune the compositing decision functions (seam escalation threshold, feather width formula) using Direct Preference Optimization: show pairs of outputs to humans; the winning output's configuration gets upweighted. Requires 500+ human preference pairs.

- **Effort:** ~1w (pipeline + data collection)
- **Expected impact:** Very large if enough data is collected. Self-improving system.

**Recommendation:** A immediately (data collection is the bottleneck, not implementation). B after 50+ ratings. C as the long-term ceiling.

---

## Issue 7 — StabStitch++ for Diagonal / Multi-Axis Scroll [LOW-MEDIUM IMPACT on 4 Tests]

**Impact: Fixes the 4 confirmed genuine SCANS fallbacks (tests 54, 59, 73, 89) and any future diagonal-scroll tests.**

### Root Cause

The 4 confirmed genuine fallbacks after S11 are not solvable by any current gate or retry because the issue is upstream: the ASP canvas model is translation-only in one axis. Tests 54 (2D drift), 59 (high seam coherence), 73 (ratio failure on sequential chain), and 89 (extreme strip banding) all have 2D or curved camera motion that the translation-only BA cannot model.

**StabStitch++** (AAAI 2023) addresses this by computing a bidirectional midplane trajectory and fitting a 2D smooth motion basis to the camera path, accommodating non-linear and multi-axis scroll.

### Options

**Option A — StabStitch++ Trajectory Smoothing [Medium Effort, Targeted Impact]**

Replace the translation-only BA with StabStitch++'s 2D trajectory smoother for sequences where the alignment gate detects significant dx variation (>50px 75th-pct). The smoother computes a global reference frame and warps each input frame toward it, handling curved pans naturally.

- **Files to change:** New `backend/src/anim/stab_stitch.py` → `stab_stitch_pipeline(frames, affines)`; `pipeline.py` → call after BA failure
- **Effort:** ~1w
- **Expected impact:** Targeted — fixes diagonal scroll specifically. The 4 genuine fallbacks may or may not be StabStitch++-solvable (need per-test diagnosis).

**Option B — Per-Test Manual Route (HITL)**

For the 4 genuine fallback tests, use the Frame Selection Review Dialog (Issue 4, Option A) and Canvas Layout Inspector (Issue 4, Option D) to manually correct the frame arrangement and anchor, then re-run. This avoids implementing StabStitch++ for a small number of tests.

- **Effort:** ~1d UI work (most of it already shipped)
- **Expected impact:** High for those 4 specific tests. Not generalizable.

**Recommendation:** B first (4 tests, high leverage from HITL), then A if diagonal-scroll tests become more prevalent.

---

## Issue 8 — Seam Visibility Reduction (Residual Visual Artifacts) [MEDIUM IMPACT on Composite Quality]

**Impact: Improves visual quality of the ~88 tests that now produce composites, especially those rated "comparable".**

Despite 75 sessions of seam refinement, visual inspection of composites would likely reveal residual issues in many tests. The most common remaining artifacts after S75:

### 8A — Seam Aliasing Bands (Diagonal Stripe Artifacts)

Caused by the DP seam path oscillating between adjacent columns of equal cost, creating a sawtooth pattern visible as a diagonal stripe in the output.

- **Shipped:** `_smooth_seam_path()` with median filter (S69, window=5). **May need larger window (11–21) for heavy aliasing cases.** The window is configurable via `ASP_SEAM_SMOOTH_WINDOW`.
- **Option:** Enable by default with `ASP_SEAM_SMOOTH_WINDOW=5` and expose in the TOML config.

### 8B — Colour Discontinuity at Strip Boundaries (SC_A > SC_Simple)

The seam coherence metric (SC_A) is still higher than simple stitch for many tests, indicating colour jumps at strip boundaries even after photometric normalization.

- **Shipped options:** Histogram matching (S49, `ASP_HISTOGRAM_MATCH=1`), multiscale gain map (S46, `ASP_MULTISCALE_GAIN=1`), seam luminance equalisation (S65, `ASP_SEAM_LUM_EQ=1`). **None of these are on by default.**
- **Option A:** Enable `ASP_HISTOGRAM_MATCH=1` by default (histogram matching is the most general photometric correction and has minimal downside on well-behaved inputs).
- **Option B:** A/B test: run the full benchmark with each flag enabled individually and measure mean GT-SSIM change. The option with the highest positive delta becomes the new default.

### 8C — Poisson Seam Brightness Step

The Poisson seam blend (S21, `ASP_POISSON_SEAM=1`) eliminates the residual brightness step at the seam cut but adds 1–3s per seam. It's currently off by default.

- **Option:** Enable for final-quality mode only (`ASP_POISSON_SEAM=1` when `final_quality=True`).

### 8D — Single-Pose Seam Hard Edge

When `post_warp_diff > threshold`, the single-pose fallback creates a hard cut between the dominant frame's foreground and the other frame's background. This is visible as a pixel-step at the seam boundary.

- **Shipped:** `_single_pose_soft_edge()` (S15, 6px blend), `_seam_color_match()` (S16), adaptive soft-edge width (S66). **All active by default.**
- **Unshipped improvement:** Increase `ASP_SP_SOFT_PX` from 6 to 12–15 for wide-feather seams. The adaptive formula (S66) should handle this, but `ASP_ADAPTIVE_SP_SOFT=1` is still off by default.
- **Option:** Enable `ASP_ADAPTIVE_SP_SOFT=1` by default.

---

## Summary — Priority Matrix

| Issue | Pipeline | HITL | Effort | Expected GT-SSIM Delta | Prerequisite | Status |
|---|---|---|---|---|---|---|
| **1A — BG-only phase correlation (Otsu)** | ✅ | ✅ | 2d | +0.03–0.05 | None | ✅ S80 (`ASP_OTSU_BG_CORR=1`) |
| **1E — HITL selection dialog** | — | ✅ | 2d | +0.04–0.10 | §2.7 StitchWorker staged execution | ✅ S79 |
| **2A — AnimeInterp SGM** | ✅ | — | 3d | +0.01–0.03 | None (VGG-19 in torchvision) | ✅ S79 (`ASP_ANIMEINTERP_SGM=1`) |
| **2D — SAM-2 + segment flow** | ✅ | ✅ | 1w | +0.02–0.05 | SAM-2 installation | ⬜ Not started |
| **3A — SAM-2 video masking** | ✅ | ✅ | 2d | +0.01–0.02 | SAM-2 installation | ✅ S79–S80 (`ASP_USE_SAM2=1`) |
| **4 — StitchWorker staged execution** | — | ✅ | 2d | prerequisite only | None | ✅ S79 |
| **4B — Seam registration inspector** | — | ✅ | 3d | +0.03–0.08 | §4 architecture | ✅ S79 (EdgeReviewDialog) |
| **5A — ProPainter BG completion** | ✅ | — | 2d | +0.01–0.02 | ProPainter (`pip install`) | 🔧 S80 (NN fallback wired; ProPainter hook ready) |
| **6A — Feedback collection** | ✅ | — | 1d | prerequisite for Bayesian search | None | ⬜ Not started |
| **6B — Bayesian param search** | ✅ | — | 2d | +0.01–0.02 | 50+ human ratings | ⬜ Not started |
| **1D — Foreground-masked DINOv2** | ✅ | — | 4h | +0.005–0.02 | None (quickest experiment) | ✅ S79 |
| **8 — Enable latent flags** | ✅ | — | 2h | +0.005–0.01 | None (flag changes only) | ✅ S80 (`asp_config.toml` created) |

---

## Recommended Implementation Order

### Sprint 1 — Quick Experiments ✅ *Complete (S79–S80)*

1. ~~**1D**~~ ✅ S79 — DINOv2 with Otsu fg-bbox crop in `_compute_dinov2_features()`.
2. ~~**8**~~ ✅ S80 — `asp_config.toml` created with 8 recommended defaults (ADAPTIVE_SP_SOFT, SEAM_SMOOTH_WINDOW, ADAPTIVE_SP_THRESH, SEAM_MARGIN, SEAM_FG_PENETRATION_MAX, ZONE_MIN_HEIGHT, SEAM_INSTABILITY_THRESH, STATIC_INPUT_MAX_MAD).
3. **6A** — Wire feedback tab to benchmark JSON. ⬜ Not started — begin collecting ratings for `simple_better` tests.

### Sprint 2 — Architecture + Flow ✅ *Mostly Complete (S79–S80)*

4. ~~**2A**~~ ✅ S79 — AnimeInterp SGM VGG-19 in `fg_register.py`. Enable: `ASP_ANIMEINTERP_SGM=1`.
5. ~~**3A**~~ ✅ S79–S80 — SAM-2 masking in `masking.py`, wired via `ASP_USE_SAM2=1` in `pipeline.py`.
6. ~~**5A (partial)**~~ 🔧 S80 — Background zero-coverage NN fill wired as Stage 10.2 in `pipeline.py`. ProPainter hook implemented in `bg_complete.py`; activates when `pip install propainter` is done.

### Sprint 3 — HITL Infrastructure ✅ *Complete (S79)*

7. ~~**4 (architecture)**~~ ✅ S79 — `QWaitCondition` pause/resume in `StitchWorker`, 4 checkpoint signals.
8. ~~**1E**~~ ✅ S79 — `SelectionReviewDialog` shipped and wired.
9. ~~**4B**~~ ✅ S79 — `EdgeReviewDialog` (seam registration inspector) shipped and wired.

### Sprint 4 — Advanced Options (1 week each, highest ceiling)

10. **1A (BiRefNet architecture)** — Run BiRefNet on strided raw frames BEFORE selection; use per-frame masks for phase correlation. The Otsu approximation (S80) is a stepping stone; the full BiRefNet approach is still worth implementing for high-character-coverage test cases.
11. **2D** — SAM-2 + segment-guided flow (combines Issues 2 and 3 into one architectural change). ⬜ Not started.
12. **6B** — Bayesian parameter search via Optuna (requires 6A feedback data). ⬜ Not started.

---

---

## Issue 9 — Direct Video Ingestion & Multi-Modal Hybrid Pipeline [ARCHITECTURAL UPGRADE]

**Impact: Eliminates the FFmpeg pre-extraction bottleneck, enables native temporal continuity for flow estimation, and allows hybrid 4K-frame + compressed-video ingestion for maximum output quality.**

Based on: *"Next-Generation Anime Stitch Pipeline: Direct Video Ingestion and Multi-Modal Human-in-the-Loop Architectures"* (2026-06-13).

### Root Cause

The current pipeline requires an external FFmpeg pre-processing step to extract frames into static PNG files before execution. This architecture:
1. Fractures the video's temporal continuity, discarding native sub-frame timestamps and GOP structure
2. Bloats storage (333 frames × 1080p PNG ≈ 500–800MB per test)
3. Prevents native duplicate decimation (telecine-aware mpdecimate on the live tensor stream)
4. Prevents leveraging I-frame-only preview decoding for the fast first-pass frame selection

### Phase 1 — Native Video Ingestion (PyAV + Memory-Mapped Tensor)

**Option A — PyAV Direct Decoder [High Impact, Medium Effort]**

Replace the static-image input path with a `VideoIngestionStream` class wrapping `av.open()` (PyAV). The stream exposes:
- `seek(pts)` — precise presentation-timestamp seeking to the nearest I-frame, then sequential decode forward
- `get_frame(idx)` → `np.ndarray` — decode a specific frame index (cached if already decoded in the GOP window)
- `get_proxy_stream(scale=0.25)` → generator — I-frame-only low-resolution proxy for the fast selection pass

```python
# backend/src/anim/video_ingestion.py (new)
class VideoIngestionStream:
    def __init__(self, video_path: str, target_fps: float | None = None): ...
    def decimate_duplicates(self, mad_threshold: float = 0.01) -> List[int]: ...
    def get_frame(self, idx: int, full_res: bool = True) -> np.ndarray: ...
    def get_proxy_frames(self, stride: int = 5) -> List[np.ndarray]: ...
```

- **Files to create:** `backend/src/anim/video_ingestion.py`
- **Files to change:** `pipeline.py` → accept `video_path: str | None` alongside `image_paths: List[str]` in `AnimeStitchPipeline`; `frame_selection.py` → pass proxy frames to `smart_select_frames()`, then decode full-res for selected indices only
- **Effort:** ~3d
- **Expected impact:** 3–5× storage reduction; enables telecine-aware duplicate detection; unlocks native temporal index metadata for downstream flow estimators

**Option B — Hybrid Memory-Mapped Ingestion [Very High Impact, Medium-High Effort]**

Two-pass ingestion:
- Pass 1: Proxy pass — decode every 5th I-frame at ¼ resolution via `av.seek + decode`; run `smart_select_frames()` to determine optimal frame indices
- Pass 2: Full-res decode — `av.seek` to each selected PTS and decode only the N≈18 frames required

This eliminates the need to decode all 333 frames at full resolution, reducing VRAM/RAM pressure by ~18×.

- **Effort:** ~2d (builds on Option A)
- **Expected impact:** Very high for long sequences. Current 333-frame test datasets take ~2–4 min to load; proxy-pass reduces this to <15s

**Recommendation:** A as the foundation, B as the immediate optimization on top.

### Phase 2 — In-Stream Telecine Duplicate Decimation

**Option A — Native mpdecimate on Tensor Stream [High Impact, Low Effort after Phase 1]**

After `VideoIngestionStream.get_proxy_frames()`, run a frame-pair MAD scan to identify exact-duplicate frame pairs (telecine pull-down introduces repeated frames every 5th or 8th frame for 24fps→30fps broadcast). Drop duplicate frames before they reach `smart_select_frames()`.

```python
# backend/src/anim/video_ingestion.py
def decimate_duplicates(self, mad_threshold=0.01) -> List[int]:
    """Returns indices of unique frames (drops telecine duplicates)."""
    unique = [0]
    for i in range(1, len(self._proxy_cache)):
        if np.mean(np.abs(self._proxy_cache[i].astype(float) - self._proxy_cache[unique[-1]].astype(float))) > mad_threshold * 255:
            unique.append(i)
    return unique
```

- **Files to change:** `video_ingestion.py` → `decimate_duplicates()`; `frame_selection.py` → call decimation before `smart_select_frames()`
- **Effort:** ~1d
- **Expected impact:** Medium. Current `_detect_hold_blocks()` handles most telecine duplicates already, but native decimation catches subtler MPEG DCT noise patterns that MAD misses

### Phase 3 — Multi-Modal Hybrid Image-Video Registration

**Option A — Sparse 4K Keyframe + Compressed Video Ingestion [Highest Quality, High Effort]**

The user provides two inputs:
1. A compressed 1080p broadcast video of the anime pan shot (for fast tracking and flow estimation)
2. A sparse set of high-resolution 4K scans or AI-upscaled keyframes (for the final compositing)

The pipeline:
1. Runs all heavy computation (Phase 1/2 ingestion, frame selection, phase correlation, BiRefNet masking, LoFTR matching, bundle adjustment, ECC refinement, SAM-2 tracking, and ARAP flow estimation) on the **1080p video stream** — fast because 1080p is 4× smaller than 4K
2. Locks the geometric transformation grid (affines) from step 1
3. Maps those affines to the **4K keyframes** using the locked geometry
4. Runs Stage 11 compositing (Laplacian blend, Poisson seam, DSFN ramp) on the 4K pixels

```python
# backend/src/anim/pipeline.py — new signature addition
class AnimeStitchPipeline:
    def run(self,
            image_paths: List[str] | None = None,
            video_path: str | None = None,          # Phase 1: video ingestion
            hires_keyframes: Dict[int, str] | None = None,  # Phase 3: 4K maps
            output_path: str = ...) -> None: ...
```

- **Files to change:** `pipeline.py` → `run()` signature extension; `canvas.py` → `_compute_canvas()` operates on 1080p geometry, returns `affines`; new Stage 12.8 upsample pass
- **Effort:** ~1w
- **Expected impact:** Very high for 4K output quality. Final composite uses uncompressed 4K pixels with 1080p-computed geometry — best of both worlds

**Recommendation:** Phase 1A → Phase 2A → Phase 3A, in that order. Phase 1 is a prerequisite for everything else.

---

## Issue 10 — Near-Perfect Stitch via Multi-Modal HITL Architecture [LONG-TERM CEILING]

**Impact: Achieves near-perfect stitches by merging human artistic intuition with foundation model capabilities. Also builds a dataset harvesting engine for progressive automation.**

Based on: *"Next-Generation Anime Stitch Pipeline" §6–§8* (2026-06-13).

### Upgrade Path Overview

The current HITL infrastructure (S79 — `QWaitCondition` pause points, 4 review dialogs) is the foundation. This issue covers the three upgrade phases that transform the HITL pipeline from "human can review outputs" to "human guides foundation models in real-time":

1. **Multi-Modal Foundation Model Prompting** — Grounded SAM-2, natural language seam routing, click-based segmentation refinement
2. **Structured Data Serialization** — COCO JSON + Label Studio format for harvesting every human interaction as a training sample
3. **Downstream Fine-Tuning + RLHF** — Progressive automation by fine-tuning SAM-2, DWPose, and the reward model on collected data

### Phase A — Multi-Modal Prompting at HITL Checkpoints

**Option A1 — Grounded SAM-2 Segmentation from Natural Language [High Impact, Medium Effort]**

Replace the current BiRefNet → bounding-box → SAM-2 chain with Grounded SAM-2:
1. User types a natural language description: `"the girl with the blue sailor uniform and red hair"`
2. Grounding DINO detects the character region → returns a bounding box
3. SAM-2 propagates the segment across all frames using the DINO bbox as a prompt

```python
# backend/src/anim/masking.py — new function
def _compute_fg_masks_grounded_sam2(
    frames: List[np.ndarray],
    text_prompt: str,
    sam2_predictor,
    grounding_dino_model,
) -> List[np.ndarray]:
    """Grounded SAM-2: text → DINO bbox → SAM-2 video propagation."""
    ...
```

GUI integration: a `QLineEdit` in the HITL selection dialog for typing the character description before segmentation runs.

- **Files to change:** `masking.py` → `_compute_fg_masks_grounded_sam2()`; `stitch_tab.py` → text prompt input in HITL checkpoint dialog; new `backend/src/anim/grounding.py` for DINO wrapper
- **Effort:** ~3d (Grounded SAM-2 is pip-installable; DINO weights ~700MB)
- **Expected impact:** Very large for cases where BiRefNet misidentifies the foreground. User can fix any segmentation failure with a single sentence

**Option A2 — Interactive Click-Based Segmentation Refinement [High Impact, Low Effort after Issue 3A]**

After SAM-2 produces an initial mask, show the mask overlaid on frame 1 in a `QDialog`. User clicks:
- Left-click on missed foreground → adds a positive SAM-2 prompt point → mask expands
- Right-click on incorrectly included background → adds a negative prompt → mask shrinks
- SAM-2 re-propagates the corrected segment across all frames (~0.5s)

This is the FocalClick / interactive segmentation paradigm applied to the ASP masking stage.

- **Files to change:** `stitch_tab.py` → click-capture overlay on frame preview; `masking.py` → `_refine_mask_with_clicks(predictor, pos_clicks, neg_clicks)`
- **Effort:** ~2d
- **Expected impact:** Guarantees near-perfect segmentation. User investment: ~30 seconds per test

**Option A3 — Natural Language Seam Routing [Medium Impact, Medium Effort]**

Allow the user to type seam-routing constraints like `"route seam around the right arm"` or `"avoid the overlapping sword"`. A GroundingDINO detection on the seam zone converts the text to pixel-space exclusion masks, which are injected into the DP cost matrix as high-penalty regions.

```python
# backend/src/anim/compositing.py — cost injection
def _build_seam_cost_map(fa_zone, fb_zone, ..., exclusion_masks: List[np.ndarray] | None = None):
    if exclusion_masks:
        for mask in exclusion_masks:
            cost[mask.astype(bool)] = 1e6  # hard barrier
    ...
```

- **Effort:** ~2d (builds on A1's Grounding DINO wrapper)
- **Expected impact:** Medium. Primarily useful for tests where the character has an extended limb or weapon that the DP seam keeps cutting through

**Recommendation:** A1 → A2 → A3 in that order.

### Phase B — Structured Data Serialization (Dataset Harvesting)

**Option B1 — COCO JSON Annotation Serializer [Medium Effort, High Long-Term Value]**

Every human interaction during HITL execution serializes to COCO JSON format:
- Frame selection override → `images` + `annotations` (selected frame metadata)
- Segmentation correction clicks → `annotations` with RLE mask (pycocotools `encode`)
- Accepted SAM-2 masks → `annotations` with polygon contours

```python
# backend/src/anim/data_serialization.py (new)
class COCOAnnotationBuilder:
    def add_image(self, frame_path: str, temporal_id: int) -> int: ...
    def add_segmentation_mask(self, image_id: int, mask: np.ndarray, category: str) -> None: ...
    def add_seam_exclusion(self, image_id: int, bbox: List[int], text_prompt: str) -> None: ...
    def save(self, output_path: str) -> None: ...
```

Storage: `~/.image-toolkit/hitl_annotations/session_{timestamp}.json`

- **Effort:** ~2d (pycocotools is already installable)
- **Expected impact:** Builds the training dataset for SAM-2 fine-tuning over time. 100+ collected sessions → fine-tune on anime domain

**Option B2 — Label Studio Multi-Modal Export [Low Effort, Medium Long-Term Value]**

Generate Label Studio JSON alongside COCO JSON, capturing the full model-vs-human delta:
- `predictions` array: SAM-2's initial (pre-correction) mask
- `annotations` array: human's final (post-correction) accepted mask

This preserves exactly what the model got wrong, making it the ideal supervision signal for fine-tuning.

- **Effort:** ~1d (JSON schema composition; no external dependency)
- **Expected impact:** Enables structured RLHF data collection compatible with Label Studio's pairwise preference templates

**Recommendation:** B1 for segmentation training data. B2 for RLHF preference pairs.

### Phase C — Progressive Automation via Fine-Tuning + RLHF

**Option C1 — SAM-2 Anime Domain Fine-Tuning [High Impact, High Effort]**

After 100+ COCO sessions are collected, fine-tune SAM-2 using human-corrected masks:
1. **Frozen encoder**: ViT-H image encoder stays frozen (too large for standard VRAM, and ImageNet pretraining is domain-agnostic enough)
2. **Fine-tuned decoder**: Mask decoder and memory module are fine-tuned on anime-domain examples
3. **Training objective**: Binary cross-entropy on the corrected mask vs. the model's pre-correction prediction

Expected outcome: SAM-2 begins delineating semi-transparent magical effects, thin ahoge hair strands, and complex overlapping multi-character scenes — all failure modes of zero-shot SAM-2 on anime.

- **Files to create:** `scripts/finetune_sam2.py` (training loop); `backend/src/anim/sam2_anime.py` (fine-tuned checkpoint loader)
- **Effort:** ~1w per training run (requires 100+ COCO sessions first)
- **Data dependency:** Option B1 (COCO annotation serializer) must have collected 100+ sessions

**Option C2 — Pose Estimator Contrastive Fine-Tuning [Medium Impact, High Effort]**

Human frame selection overrides (from the SelectionReviewDialog) are logged as `(rejected_frame, accepted_frame)` pairs. These constitute contrastive pairs for fine-tuning DWPose / ViTPose:
- Rejected frame: `anchor = compute_embedding(rejected_frame)`
- Accepted frame: `positive = compute_embedding(accepted_frame)`
- Random other frame: `negative = compute_embedding(random_frame)`
- **Loss:** Triplet loss or InfoNCE on the pose embedding space

After 500+ such pairs, the model learns to rank anime poses by visual coherence, making `_compute_dinov2_features()` → `_pose_dist()` comparison more reliable.

- **Effort:** ~1w per training run (requires 500+ selection overrides first)
- **Data dependency:** Frame selection review usage in HITL mode

**Option C3 — PPO-based Compositing Parameter Optimization [Very High Impact, Very High Effort]**

After the reward model (Issue 6, S29) is calibrated on 50+ human ratings (Issue 6A):
1. Define the action space as the set of discrete ASP compositing parameters (feather width, seam cost weights, blend method, etc.)
2. Define the state as the current ASP output image encoded by the reward model's CNN backbone
3. Use Proximal Policy Optimization (PPO) to discover compositing configurations that maximize the reward model's score

The PPO agent replaces the current static `asp_config.toml` values with dynamically optimized per-test parameters.

- **Effort:** ~2w
- **Prerequisites:** Issue 6A (feedback collection), Issue 6 calibrated reward model, Issue 9A (fast re-rendering loop to evaluate PPO rollouts)
- **Expected impact:** Very large. PPO can explore the compositional parameter space in a way that no human could — finding non-obvious combinations (e.g., tight feather + histogram match + wide Poisson band) that work well together on specific input characteristics

**Recommendation:** C1 → C2 → C3, in strict order. Each phase depends on accumulated human data from the previous phase.

### Priority Matrix for Issues 9 & 10

| Phase | Feature | Effort | Prerequisite | Expected Impact |
|---|---|---|---|---|
| **9A** — PyAV video ingestion | `VideoIngestionStream` in `video_ingestion.py` | 3d | None | Storage 3–5×, proxy-pass speedup |
| **9B** — Telecine decimation | `decimate_duplicates()` in `video_ingestion.py` | 1d | 9A | Cleaner frame selection, fewer duplicate-frame seams |
| **9C** — Hybrid 4K/1080p | `hires_keyframes` param in `pipeline.run()` | 1w | 9A | Near-4K output quality at 1080p compute cost |
| **10A1** — Grounded SAM-2 | Text prompt → DINO bbox → SAM-2 propagation | 3d | Issue 3A (SAM-2 wired) | Near-perfect segmentation from one sentence |
| **10A2** — Click refinement | Positive/negative click overlay on frame 1 | 2d | 10A1 | Guaranteed segmentation quality |
| **10A3** — NL seam routing | Text → DINO exclusion mask → DP cost injection | 2d | 10A1 | Seam avoids character anatomy on command |
| **10B1** — COCO serializer | `COCOAnnotationBuilder` in `data_serialization.py` | 2d | None | Training dataset accumulation |
| **10B2** — Label Studio export | Label Studio JSON alongside COCO | 1d | 10B1 | RLHF preference pair dataset |
| **10C1** — SAM-2 fine-tune | Frozen encoder + fine-tuned decoder on anime masks | 1w/run | 10B1 + 100+ sessions | Anime-domain SAM-2 accuracy |
| **10C2** — Pose contrastive | DWPose/ViTPose contrastive fine-tune on selection pairs | 1w/run | 10B1 + 500+ pairs | Better pose-similarity metric |
| **10C3** — PPO compositing | PPO over parameter space with reward model as oracle | 2w | Issue 6A + C1 calibrated RM | Near-optimal per-test parameters |

### Recommended Implementation Sequence

**Sprint 5 — Video Ingestion Foundation (~1w)**
1. `9A` — `VideoIngestionStream` (PyAV) in `backend/src/anim/video_ingestion.py`
2. `9B` — `decimate_duplicates()` wired into frame selection pre-pass
3. Update `AnimeStitchPipeline` to accept `video_path` alongside `image_paths`

**Sprint 6 — Grounded Multi-Modal HITL (~1w)**
4. `10A1` — Grounded SAM-2 wrapper (`masking.py` + `grounding.py`)
5. `10A2` — Click-refinement overlay in `stitch_tab.py` HITL checkpoint
6. `10A3` — Natural language seam routing via DINO exclusion masks

**Sprint 7 — Data Serialization (~1w)**
7. `10B1` — `COCOAnnotationBuilder` in `backend/src/anim/data_serialization.py`
8. `10B2` — Label Studio JSON exporter
9. Wire serialization into all HITL checkpoints (frame selection, segmentation, seam routing)

**Sprint 8 — Hybrid 4K Pipeline (~1w)**
10. `9C` — `hires_keyframes` support in `pipeline.run()` + Stage 12.8 upsample pass

**Sprint 9+ — Progressive Automation (multi-week, data-gated)**
11. `10C1` — SAM-2 fine-tuning (requires 100+ COCO sessions from B1)
12. `10C2` — Pose contrastive fine-tuning (requires 500+ selection pairs)
13. `10C3` — PPO parameter optimization (requires calibrated reward model from Issue 6)

---

## Current Pipeline Flags — Recommended Default Changes

Several S42–S75 features were shipped OFF by default due to early uncertainty. Based on their implementations and the lack of regressions in subsequent sessions, the following should be enabled in `asp_config.toml` as new defaults:

```toml
[compositing]
# Smoother seam path — eliminates diagonal aliasing bands (no quality risk)
ASP_SEAM_SMOOTH_WINDOW = 5

# Adaptive SP soft-edge — wider blend for wide-feather seams (replaces fixed 6px)
ASP_ADAPTIVE_SP_SOFT = 1

# Adaptive SP escalation threshold — catches ghost bands from wide-feather seams
ASP_ADAPTIVE_SP_THRESH = 1

# Seam path boundary clamp — prevents seam at zone edge with no feather headroom
ASP_SEAM_MARGIN = 3

# Seam FG penetration escalation — catches seams that cut deeply into character
ASP_SEAM_FG_PENETRATION_MAX = 0.7

# Minimum zone height — prevents degenerate DP on tiny zones
ASP_ZONE_MIN_HEIGHT = 20

[frame_selection]
# Seam path instability escalation — catches noisy DP outputs
ASP_SEAM_INSTABILITY_THRESH = 20.0

[pipeline]
# Static input detection — early exit for still frames
ASP_STATIC_INPUT_MAX_MAD = 2.0
```

These are all low-risk changes (each has 5 unit tests, and the existing test suite would catch regressions). Run the 5-test benchmark after each batch to validate.
