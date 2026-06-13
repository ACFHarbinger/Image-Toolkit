# Anime Stitch Pipeline — Context Prompt

**Intent:** Initialize a high-context session for working on `AnimeStitchPipeline`. Load all architectural knowledge, known bugs, and test infrastructure before making any changes.

---

## The Prompt

You are an expert computer vision engineer working on the `AnimeStitchPipeline` in Image-Toolkit. This is a 13-stage research pipeline that stitches sequential anime/manga frame captures into vertical panoramas.

### Architecture in one sentence

Frames → BaSiC photometric correction → BiRefNet foreground masking → LoFTR/TemplateMatch pairwise matching → bundle adjustment → ECC sub-pixel refinement → canvas geometry → temporal median render → (optional MFSR) → hard-partition foreground composite → crop.

### Key source files

| File | Stage | What it does |
|------|-------|-------------|
| `backend/src/anim/pipeline.py` | Orchestrator | Full 13-stage flow; also `_filter_edges`, coverage gate |
| `backend/src/anim/compositing.py` | Stage 11 | Hard-partition composite — primary source of seam improvements |
| `backend/src/anim/rendering.py` | Stage 9 | Temporal median render with per-pixel gain |
| `backend/src/anim/bundle_adjust.py` | Stage 7 | Global bundle adjustment (LM, GNC cauchy loss) |
| `backend/src/anim/matching.py` | Stages 5–6 | Pairwise LoFTR + TemplateMatch |
| `backend/src/anim/canvas.py` | Stage 8 | Canvas geometry, `_compute_canvas`, `_crop_to_valid`, TELEA fill |
| `backend/src/anim/masking.py` | Stage 4 | BiRefNet foreground masks |
| `backend/src/anim/ecc.py` | Stage 8 | ECC sub-pixel refinement |
| `backend/src/anim/fg_register.py` | Stage 8.5 | Flow-guided foreground pose registration (ARAP-Push) |
| `backend/src/anim/frame_selection.py` | Pre-pipeline | Smart frame selection — hold detection, DINOv2, near-dup filter |
| `backend/src/anim/config.py` | Config | §1.8A TOML config loader (`load_asp_config`) |
| `backend/src/anim/validation.py` | Post-7 | Affine health check; min_gap threshold = 25px |
| `backend/src/constants/anim.py` | Constants | Centralised pipeline constants (FEATHER_MAX, FEATHER_MIN, etc.) |
| `backend/src/core/image_merger.py` | Reference | Simple stitch (`_merge_images_scan_stitch`) — the quality target |

### Full architecture reference

Read `docs/ARCHITECTURE.md` — it has complete Mermaid diagrams for both the simple stitch and the 13-stage pipeline with all parameters and branch conditions.

### Research context

Read the consolidated research reference before proposing algorithmic changes:
- `reports/Image_Stitching_Research.md` — the complete, single-source stitching reference (merges all 14 prior reports). Covers geometric foundations, Perfect-vs-Scan-Stitch audit, feature matching, optical flow, spatially-varying warps, the foreground-assembly paradigm (§8), photometric correction, segmentation, seam-finding, blending, background reconstruction, the 14-stage pipeline spec, evaluation, and failure/fallback taxonomy.
- For generation work: `reports/Image_Generation_Research.md`.

### Overmix reference implementation

`Overmix/src/` contains a production C++ image stitching tool. Key files to consult:
- `aligners/RecursiveAligner.cpp` — hierarchical alignment (robust to bad pairwise matches)
- `aligners/AverageAligner.cpp` — average-frame-based alignment
- `comparators/MultiScaleComparator.cpp` — multi-scale matching comparator
- `renders/AverageRender.cpp` — weighted average rendering
- `renders/StatisticsRender.cpp` — median/statistics-based rendering

---

## Current State (2026-06-13, Session 84)

The pipeline has received 87 sessions of improvements (S1–S87). 584 unit tests in `backend/test/anim/` (2 skipped: pyav); S84 added 5 GUI tests in `gui/test/test_stitch_tab.py::TestStitchWorkerVideoPath`. SCANS fallbacks reduced from 51/96 → 4/96 genuine fallbacks. Key improvements shipped across sessions:

**Frame selection & pre-processing (S6–S43):**
- Hold detection (`_detect_hold_blocks`, `_detect_hold_blocks_dhash`), DINOv2 frame selection, temporal variance pre-filter, near-dup luma filter, dHash animation hold detection, scene-change edge rejection, response-based hold refinement

**Bundle adjustment & matching (S6–S45):**
- GNC-TLS robust loss (Geman-McClure continuation), adaptive GNC f_scale, spanning-tree inlier filter, adaptive min-step threshold, static edge rejection, scale normalization, high-confidence edge re-solve (Retry 0), adaptive rotation/scale thresholds, MST weight gate, edge graph connectivity check, per-channel BGR scene-change gate, Kendall-τ monotonicity check

**Canvas & alignment (S13–S61):**
- Multi-frame canvas coverage gate (Stage 10.5), PANORAMA stitcher fallback, TELEA border fill, scroll-axis detection wired, canvas span utilization gate, adaptive min-gap threshold, adaptive boundary search

**Compositing & seam quality (S10–S46):**
- Seam DP vectorization (§1.5A), parallel seam pre-computation, seam path cache (§1.5D), tiered seam cost, per-pixel DSFN ramp, bg-mask-aware DSFN, Poisson seam blend, seam color match, single-pose soft-edge, per-DSFN ramp, seam color similarity gate (BGR), seam path smoothing, seam path boundary clamp, seam hard corridor barrier, adaptive SP soft-edge width, adaptive SP escalation threshold, fg-density feather cap, tight-step preemptive escalation, post-composite luma equalization, seam-step post-composite gate, zone minimum height guard, seam path instability escalation, seam FG penetration escalation, SemanticStitch column barrier, GNC-TLS compositing, multi-scale spatially-varying gain, gain-adaptive feather minimum

**Photometric normalization (S18–S49):**
- Continuous adaptive gain clamp (§1.4B), per-pair coherence gate, bg-gain unclamped override, histogram CDF matching, per-frame exposure outlier rejection, bg-only normalization coverage floor, background zero-coverage fill (`bg_complete.py`)

**Masking & segmentation (S79–S83):**
- SAM-2 wired via `_USE_SAM2` flag (S79 + S80), Grounded SAM-2 (Issue 10A1), BiRefNet two-channel selector, foreground-masked DINOv2, Otsu bg mask for phase correlation (`_otsu_bg_mask_pair`, S80)
- S83 — `_compute_fg_masks_sam2_stateful()` + `_cleanup_sam2_state()` in `masking.py` — live SAM-2 predictor+state kept alive across HITL boundary (uses `mkdtemp`, no `reset_state`/`del`); `AnimeStitchPipeline` stores `_sam2_predictor/_sam2_inference_state/_sam2_tmp_dir/_sam2_frame_h/_sam2_frame_w`; `_cleanup_sam2_state()` method frees GPU+disk after checkpoint 1.5 dialog closes; HITL checkpoint 1.5 data dict now includes live state keys so `_refine_cb` in `stitch_tab.py` calls `_refine_masks_with_clicks` with the real predictor

**Config & infra (S27–S44):**
- TOML config loader (`asp_config.toml`, auto-loaded), config schema validation (14 `ASP_*` keys), config → env injection with `setdefault`, `_reload_scans_frames` (on-demand SCANS reload)

**HITL (S79–S84):**
- `QWaitCondition`/`QMutex` staged execution; 4 HITL signals + pause points; `SelectionReviewDialog`, `EdgeReviewDialog`, `CanvasInspectorDialog`, `CoverageHeatmapDialog`; all 4 in `gui/src/dialogs/`
- S81 — HITL checkpoint 1.5 (mask review): `sig_review_masks` + `set_mask_override()` in `stitch_worker.py`; `MaskReviewDialog` in `gui/src/dialogs/mask_review_dialog.py` with `_ClickOverlay` (left=pos/right=neg SAM-2 prompts) + `_RefinementWorker(QThread)`
- S81 — `backend/src/anim/grounding.py` (new): lazy GroundingDINO wrapper (`_detect_objects`, `_detect_best_box`, `_detect_exclusion_mask`); graceful ImportError fallback; `GROUNDING_DINO_CKPT`/`CFG` env vars
- S81 — `masking.py`: `_compute_fg_masks_grounded_sam2()` (text prompt → DINO bbox → SAM-2 propagation) + `_refine_masks_with_clicks()` (pos/neg click re-propagation)
- S81 — `backend/src/anim/data_serialization.py` (new): `COCOAnnotationBuilder` (fg segmentation, seam-exclusion, frame-selection annotations; RLE via pycocotools, polygon fallback; atomic write) + `LabelStudioExporter` (model predictions + human annotations for RLHF preference learning) + `create_session_serializers()` factory
- S81 — `_build_seam_cost_map()` / `_composite_foreground()` gain `exclusion_masks` param — NL seam routing: cost=1e6 hard barrier where mask>127, forcing DP seam away from named objects
- S82 — `exclusion_masks` threaded end-to-end: `AnimeStitchPipeline.exclusion_masks` instance attr → Stage 11 → `_composite_foreground`; `StitchWorker.set_exclusion_masks()` + HITL checkpoint 1.5 wiring; `MaskReviewDialog` seam-exclusion section (GroundingDINO detect button + `sig_exclusion_masks_accepted` signal); COCO+LS auto-save at checkpoint 1.5 (→ `~/.image-toolkit/hitl_annotations/`)
- S82 — `backend/src/anim/video_ingestion.py` (new, Issue 9): `VideoIngestionStream` + `ingest_video()` — PyAV proxy-first decode at ¼ res, telecine-drop dedup, uniform/keyframe/smart selection, full-res seek-based per-frame decode; `ASP_VIDEO_PROXY_SCALE/MAX_FRAMES/TELECINE_MAD/KEYFRAMES_ONLY` env vars; graceful `pip install av` fallback
- S83 — Live SAM-2 state preservation across HITL checkpoint boundary: `_compute_fg_masks_sam2_stateful()` stateful variant returns `(masks, predictor, state, tmp_dir, H, W)`; `AnimeStitchPipeline._compute_fg_masks()` stores tuple on `self`; checkpoint 1.5 data dict passes live state; `_refine_cb` in `stitch_tab.py` now calls `_refine_masks_with_clicks(predictor, state, ...)` for real; `_cleanup_sam2_state()` frees GPU/disk after dialog closes; 10 new tests in `test_masking.py`
- S84 — Video ingestion HITL + "From Video" GUI mode: `sig_review_video = Signal(object)` (checkpoint 0); `_hitl_video_pause()` blocks on `_hitl_mutex`; `StitchWorker.run()` ingests video via `ingest_video()` into `mkdtemp` before pipeline, emits `sig_review_video` in HITL mode, applies `frame_override`; `SelectionReviewDialog` configurable `title` param; `stitch_tab.py` "From Video Source" checkbox + `_video_input_widget` + `_on_hitl_review_video()`; 5 new GUI tests in `TestStitchWorkerVideoPath`
- S85 — HITL Checkpoint 3.5 seam boundary editor: `_compute_initial_boundaries(affines, frames) → np.ndarray` extracted to `compositing.py` (`__all__`); `_composite_foreground()` + `AnimeStitchPipeline._composite_foreground()` gain `preset_boundaries: Optional[np.ndarray] = None`; `StitchWorker` `sig_review_boundaries` + `set_boundary_override()` + checkpoint 3.5 block between Stage 10/11; `boundary_editor_dialog.py` (new) — `_DraggableLine(QGraphicsLineItem)` + `BoundaryEditorDialog` with draggable N-1 seam lines + "Reset to Auto" + `adjusted_boundaries()`; `stitch_tab._on_hitl_review_boundaries()`; 5 new tests `TestComputeInitialBoundaries`
- S86 — HITL Checkpoint 4.5 post-composite seam painter: `paint_mask: Optional[np.ndarray]` param in `_composite_foreground()` appended to `_eff_exclusion` list (canvas-space uint8, zone-sliced identically to `exclusion_masks`); `AnimeStitchPipeline._composite_foreground()` wrapper updated; `StitchWorker` `sig_review_composite` + `set_paint_mask()` + re-composite while-loop at checkpoint 4.5 (breaks on accept, re-runs with new mask on `SeamPainterDialog.RECOMPOSITE=2`); `seam_painter_dialog.py` (new) — `_PaintCanvas(QLabel)` with alpha-overlay left-drag paint / right-drag erase, `paint_mask_preview()` → uint8 alpha channel, `full_resolution_mask()` upscales via `INTER_NEAREST`; `stitch_tab._on_hitl_review_composite()`; 5 new tests `TestPaintMask`; total backend/test/anim/ suite: 577 tests (2 skipped)
- S87 — HITL Checkpoint 5 final output RLHF feedback: `StitchWorker` `sig_review_output = Signal(object)` + `set_output_feedback(overall_rating, annotations)` + `"output"` in signal map + checkpoint 5 block after Stage 13 (lazy-imports `FeedbackStore`/`StitchAnnotation`, calls `add_from_image()`, logs result); `final_output_review_dialog.py` (new) — `_AddFlawDialog` (flaw_type QComboBox from `RLHF_FLAW_TYPES` + severity QDoubleSpinBox) + `FinalOutputReviewDialog` (canvas preview + overall-quality slider 0–10 in 0.5 steps + flaw annotation QListWidget + Save/Skip); `stitch_tab._on_hitl_review_output()` wired; 7 new tests in `test_rlhf_feedback.py` (FeedbackStore add/iter/count/roundtrip/from_image/empty/malformed) → **584 tests passing**

**Benchmark infra:**
- `_compute_rlhf_score`, `_ghosting_score_v2` (autocorrelation double-edge), `seam_bhattacharyya_distances`, per-seam SIQE ghost scores, `_compute_aligned_ssim` (MOTION_EUCLIDEAN)

**Current test corpus: 97 tests (asp_test01–asp_test97)**
- asp_test97 added 2026-06-13 ("Akane wa Tsumare Somerareru - 02", 90 frames, horizontal-ish scroll, 16 frames selected)
- asp_test07 replaced 2026-06-13 (new "Akane wa Tsumare Somerareru - 01" dataset, 182 frames, 28 frames selected)
- Ground truth available for 55/97 tests

**Benchmark results (2026-06-13, test07 + test97 only):**
- test07: SC=23.6 (ASP) vs 43.2 (simple); verdict=comparable; sharpness 111.75 vs 38.81; ghosting_siqe 22.98 vs 91.65; 28 frames, 1593×3841 output
- test97: SC=10.6 (ASP) vs 14.3 (simple); verdict=simple_better (coverage 86% vs 98%); ghosting_siqe 33.2 vs 61.79; 16 frames, 2505×1859 output

**The CV sharpness metric (Laplacian variance) is inverted** — hard seam edges inflate sharpness. Use `seam_coherence` as primary quality proxy (≤18 good, 18–28 moderate, >28 severe). `ghosting_siqe` (§3.8A autocorrelation) is more reliable than `ghosting_score` for detecting double-edges.

**Visually confirmed good outputs:** asp_test28, asp_test58.

---

## Phase 2 Architecture (Issue 9 & 10 — Next Generation)

Issue 10 (Multi-modal HITL) is **implemented in S81–S87**. Issue 9 (Video ingestion) is implemented in S82 + S84.

| Module | Location | Status |
|--------|----------|--------|
| `VideoIngestionStream` | `backend/src/anim/video_ingestion.py` | ✅ **S82** — proxy-first decode, telecine dedup, smart/uniform/keyframe selection |
| `grounding.py` functions | `backend/src/anim/grounding.py` | ✅ **S81** — GroundingDINO wrapper + exclusion mask |
| `_compute_fg_masks_grounded_sam2` | `backend/src/anim/masking.py` | ✅ **S81** — text → DINO bbox → SAM-2 propagation |
| `_refine_masks_with_clicks` | `backend/src/anim/masking.py` | ✅ **S81** — pos/neg click SAM-2 re-propagation |
| `_compute_fg_masks_sam2_stateful` | `backend/src/anim/masking.py` | ✅ **S83** — live predictor+state preserved across HITL |
| `_cleanup_sam2_state` | `backend/src/anim/masking.py` | ✅ **S83** — GPU/disk cleanup after HITL dialog closes |
| `COCOAnnotationBuilder` | `backend/src/anim/data_serialization.py` | ✅ **S81** — COCO JSON + RLE/polygon encoding |
| `LabelStudioExporter` | `backend/src/anim/data_serialization.py` | ✅ **S81** — Label Studio tasks with RLHF delta |
| `MaskReviewDialog` | `gui/src/dialogs/mask_review_dialog.py` | ✅ **S81** — click overlay + refinement worker |
| `exclusion_masks` in compositing | `compositing.py` | ✅ **S81** — NL seam routing hard barrier |
| HITL checkpoint 0 (video review) | `gui/src/helpers/models/stitch_worker.py` | ✅ **S84** — `sig_review_video` + `_hitl_video_pause()` + "From Video" GUI |
| HITL checkpoint 3.5 (boundary editor) | `gui/src/dialogs/boundary_editor_dialog.py` | ✅ **S85** — draggable seam lines; `_compute_initial_boundaries` + `preset_boundaries` param |
| HITL checkpoint 4.5 (seam painter) | `gui/src/dialogs/seam_painter_dialog.py` | ✅ **S86** — paint/erase seam exclusion; `paint_mask` + `_eff_exclusion`; re-composite while-loop |
| HITL checkpoint 5 (RLHF feedback) | `gui/src/dialogs/final_output_review_dialog.py` | ✅ **S87** — quality slider + flaw annotations; `FeedbackStore.add_from_image()` after save |

**S81 Known limitation resolved (S83):** Live SAM-2 state is preserved across the HITL checkpoint boundary via `_compute_fg_masks_sam2_stateful()`. The predictor is passed through the checkpoint 1.5 data dict and `_refine_cb` in `stitch_tab.py` now calls `_refine_masks_with_clicks` with the live predictor when SAM-2 is active (`ASP_USE_SAM2=1`).

See `reports/ASP_High_Value_Issues_Report.md` Issues 9 & 10 and `reports/Upgrading Anime Stitch Pipeline.md` for the full spec.

---

## Known Issues Summary (96-test corpus, 2026-06-07 S27 baseline)

### SCANS fallbacks (4 genuine, down from 51/96)

| Test | Cause |
|------|-------|
| test54 | Genuine: min_gap below floor after validation retries |
| test59 | Genuine: bundle ratio failure |
| test73 | Genuine: extreme diagonal (dx_cv=25.3) |
| test89 | Genuine: ratio=4.0 bundle failure |

### Remaining compositing issues

Most ASP-succeeded tests now pass validation. Remaining seam quality issues:

| Category | Approx. count | Seam∇ proxy |
|----------|--------------|-------------|
| Catastrophic — severe color banding | ~5–10 | >12 |
| Poor — visible seams | ~10–15 | 7–12 |
| Moderate — seams visible but usable | ~20–25 | 4–7 |
| Good — genuine improvement | ~15–20 | <5 |

### Open roadmap items

- **§1.9A Fallback path purity** ✅ Fixed (S28) — `_spatial_dedup_frames()` syncs `scans_frames` after spatial dedup
- **§1.10A RLHF post-run quality gate** — call `reward_model.predict(output)` after each run; log score; flag < 0.6 for review
- **§2.x Diagnostics** — per-test pipeline trace, benchmark comparison dashboard

---

## Test Corpus (97 datasets, asp_test01–asp_test97)

Datasets are in `data/asp_testXX/` (zero-padded). Frames are consecutive video frames (~42ms intervals) smart-selected by phase-correlation to ~18 frames/dataset (50px step target).

**Numbering history:**
- Original 94-test benchmark corpus
- `asp_test25` added (*Akane wa Tsumare Somerareru - 02*, ~223 frames); old test25–94 shifted +1
- `asp_test96` added (*Ajisai no Chiru Koro ni - 01*, ~139 frames)
- `asp_test07` replaced 2026-06-13 with new "Akane wa Tsumare Somerareru - 01" dataset (182 frames)
- `asp_test97` added 2026-06-13 (*Akane wa Tsumare Somerareru - 02*, 90 frames, 16 selected)

**Ground truth images:** 55 of 97 tests have a reference panorama in `data/ground_truth/asp_testXX.{png,jpg,jpeg}`. These are used by the benchmark for SSIM/PSNR comparison vs. GT — the most reliable quality signal available.

Tests WITH ground truth: 1, 2, 4, 5, 6, 8, 9, 11, 12, 14, 15, 16, 17, 20, 25, 26, 27, 31, 32, 33, 34, 37, 42, 43, 44, 45, 46, 49, 50, 52, 54, 57, 58, 59, 65, 70, 72, 74, 76, 77, 78, 79, 80, 82, 83, 84, 85, 86, 88, 89, 90, 91, 92, 95, 96

### Representative dataset table (selected tests)

| Dataset | Frames | Seam∇ | Fallback? | Visual quality | Notes |
|---------|-------:|------:|-----------|---------------|-------|
| `asp_test01` | 16 | 9.05 | N | Poor | Hard color step mid-image |
| `asp_test03` | 5 | 6.86 | N | Moderate | Very few frames, limited compositing |
| `asp_test04` | 23 | 8.64 | N | **Catastrophic** | 4+ color strips, duplicate limbs |
| `asp_test07` | 11 | 7.59 | N | Moderate | Close-up, appears coherent |
| `asp_test08` | 14 | 10.12 | N | **Catastrophic** | Character 3× ghosted |
| `asp_test10` | 8 | 4.23 | N | Moderate | Few frames, low seam gradient |
| `asp_test11` | 11 | 10.25 | N | **Catastrophic** | Severe color banding |
| `asp_test13` | 14 | 4.89 | Y | SCANS | ratio=10.6 outlier bundle |
| `asp_test17` | 19 | 5.68 | N | Moderate | Subtle banding, mostly coherent |
| `asp_test18` | 19 | 1.56 | N | Likely ok | Composite bypassed (horizontal scroll detect) |
| `asp_test07` | 28 sel | SC=23.6 | N | Comparable | New dataset 2026-06-13 (182 raw frames); *Akane wa Tsumare Somerareru - 01* |
| `asp_test25` | NEW | — | — | New test | *Akane wa Tsumare Somerareru - 02* sequence; GT available |
| `asp_test26` | 11 | 10.35 | N | **Catastrophic** | Was old test25; extreme color break; GT available |
| `asp_test28` | 21 | 9.89 | N | ✅ **Good** | Was old test27; proper vertical panorama; GT available |
| `asp_test35` | 6 | 13.85 | N | Moderate | Was old test34; seam visible but extends scene; GT available |
| `asp_test37` | 26 | 3.92 | N | **Catastrophic** | Was old test36; swimsuit changes color per strip; GT available |
| `asp_test38` | 14 | 0.87 | Y | SCANS (clean) | Was old test37; very low seam — SCANS is good; GT available |
| `asp_test43` | 23 | 3.31 | Y | SCANS (clean) | Was old test42; low seam — SCANS is good; GT available |
| `asp_test48` | 9 | 1.50 | Y | SCANS (clean) | Was old test47; very low seam — SCANS is good |
| `asp_test58` | 27 | 5.82 | N | ✅ **Good** | Was old test57; clean extended coverage; GT available |
| `asp_test61` | 19 | 7.44 | N | Poor | Was old test60; banding but covers more than simple |
| `asp_test70` | 23 | 1.77 | Y | SCANS (clean) | Was old test69; very low seam — SCANS is good |
| `asp_test79` | 30 | 10.58 | N | Likely poor | Was old test78; slowest (289s), high seam; GT available |
| `asp_test86` | 29 | 8.76 | N | **Catastrophic** | Was old test85; multiple harsh color bands; GT available |
| `asp_test88` | 7 | 15.24 | N | Likely catastrophic | Was old test87; highest seam gradient |
| `asp_test89` | 22 | 4.52 | Y | SCANS | Was old test88; ratio=4.0 bundle failure; GT available |
| `asp_test91` | 17 | 1.78 | Y | SCANS (clean) | Was old test90; very low seam — SCANS is clean; GT available |
| `asp_test96` | NEW | — | — | New test | *Ajisai no Chiru Koro ni - 01* sequence; GT available |
| `asp_test97` | 16 sel | SC=10.6 | N | simple_better (coverage) | New 2026-06-13; *Akane wa Tsumare Somerareru - 02* (90 raw frames); horizontal scroll; 2505×1859 output |

**Seam∇ (seam_gradient)** is the best available diagnostic metric: `< 5` = likely clean or SCANS fallback; `5–8` = moderate seam; `> 8` = likely poor or catastrophic.

### Diagnostic snippet — check seam gradient across all datasets

```bash
source .venv/bin/activate && python3 -c "
import json, os
with open('backend/benchmark/results/anime_stitch_20260601_152735.json') as f:
    d = json.load(f)
for ds in sorted(d['datasets'], key=lambda x: x['metrics_asp'].get('seam_gradient', 0), reverse=True):
    ah = ds['affine_health']
    seam = ds['metrics_asp'].get('seam_gradient', 0)
    fb = 'FB' if ds['used_fallback'] else '  '
    print(f\"{ds['name']} {fb} seam={seam:.2f} ratio={ah['ratio']:.1f} gap={ah['min_gap_px']:.0f}px\")
"
```

---

## Benchmark: Selective Test Run

The benchmark (`backend/benchmark/bench_anime_stitch.py`) now supports selective test execution for fast iteration:

```bash
source .venv/bin/activate

# Run specific tests (fastest feedback)
python3 -m backend.benchmark.bench_anime_stitch --tests asp_test04 asp_test28 asp_test58

# Run a numeric range
python3 -m backend.benchmark.bench_anime_stitch --range 1-10

# Run comma-separated test numbers
python3 -m backend.benchmark.bench_anime_stitch --range 4,8,27,57

# First N tests
python3 -m backend.benchmark.bench_anime_stitch --first 5

# Skip already-processed datasets
python3 -m backend.benchmark.bench_anime_stitch --skip-done

# Re-run the known good and known bad tests for regression checking
python3 -m backend.benchmark.bench_anime_stitch --tests asp_test04 asp_test08 asp_test28 asp_test37 asp_test58 asp_test86
```

### Recommended test subsets

| Purpose | Command |
|---------|---------|
| Quick sanity (2 good + 2 bad + 1 SCANS) | `--tests asp_test28 asp_test58 asp_test04 asp_test86 asp_test38` |
| Full catastrophic failures (new numbers) | `--range 4,8,11,26,37,86,88` |
| Borderline tests (near-50px threshold, new numbers) | `--range 38,59,72,74,80,81,85,90` |
| Tests with ground truth | `--range 1,2,4,5,6,8,9,11,12,14,15,16,17,20,25,26,27` |
| New tests only | `--tests asp_test25 asp_test96` |

---

## Quality target

The **simple stitch** (`_merge_images_scan_stitch`) is consistently the better output in most cases for this corpus. The pipeline's goal should be to match or exceed it. Right now it does NOT do so in the majority of tests.

Visual quality standard (in priority order):
1. No severe horizontal color bands (adjacent strips must match within ±15 luminance units)
2. No body-part duplication at strip seams
3. No ghosting (3+ frames per canvas row required for temporal median)
4. Natural brightness transitions at frame boundaries

### Fast iteration loop

Do NOT re-run GPU-heavy stages (BiRefNet, LoFTR) when iterating on compositing. Use the pre-computed stage outputs from any already-processed dataset:

```bash
# Check which datasets have pre-computed stages
ls data/asp_test27/output/panorama_stages/
# stage02_normalised_frame*.png, stage04_bgmask_frame*.png,
# stage08_canvas_info.json, stage09_temporal_render.png, stage11_fg_composite.png

# Run only compositing from saved stages (adapt run_pipeline_v2.py)
source .venv/bin/activate
python3 archive/run_pipeline_v2.py
```

### Unit test suite

```bash
source .venv/bin/activate
pytest backend/test/anim/ -q          # 567 tests (~30s, no GPU) — 2 skipped (pyav)
pytest backend/test/anim/ -k "canvas" # run a specific module
```

| File | Covers |
|------|--------|
| `test_bundle_adjust.py` | Stage 7 LM solver — frame clustering, anchor frame, outlier edges |
| `test_filter_edges.py`  | `_filter_edges` — wrong-sign, gross outliers, geometric consistency |
| `test_canvas.py`        | `_compute_canvas`, `_crop_to_valid` — overcrop, horizontal scroll, TELEA fill |
| `test_affine_validation.py` | `_validate_affines` spec — ratio, min_gap, rotation, scale |
| `test_compositing.py`   | `_diff_to_feather`, `_global_gain_normalize`, `_composite_foreground`, seam functions |
| `test_rendering.py`     | `_render_median`, `_render_first`, ghosting detection, baselines |
| `test_frame_selection.py` | `smart_select_frames`, hold detection, `_near_dup_luma_filter` |
| `test_fg_register.py`   | Stage 8.5 fg pose registration — ARAP Push, flow-guided alignment |
| `test_bench_metrics.py` | `_compute_aligned_ssim`, benchmark metric helpers |
| `test_config.py`        | §1.8A `load_asp_config` — TOML loading, env injection, setdefault precedence |
| `test_pipeline.py`      | §1.9A `_spatial_dedup_frames` — dedup logic, scans_frames sync, edge reindex |

---

## Constraints

- NEVER skip MFSR by default in the production pipeline — only skip it in test scripts. The GUI exposes an "enable MFSR" toggle.
- Do NOT add `QPixmap`, Qt, or GUI imports inside any `backend/src/anim/` file.
- Keep `_composite_foreground` signature unchanged — called by pipeline, GUI worker, and test scripts.
- Gains applied in `_render_median` and `_composite_foreground` are independent — do not confuse them.
- `has_content = src.max(axis=2) > 0` must stay at `> 0` — dark pixels with max=1–10 are real content.
- Stage 11 uses `INTER_LINEAR`, not `INTER_LANCZOS4` — Lanczos4 produces halos at silhouette edges.

My first task is: read the anime pipeline issues and analysis reports in `.agent/cache/*.md`, then read the pipeline source code in `backend/src/anim/`, then understand the current visual failures and architectural root causes, and propose or implement the fixes described in the priority list above.
