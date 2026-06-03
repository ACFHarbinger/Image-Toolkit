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
| `backend/src/anim/pipeline.py` | Orchestrator | Full 13-stage flow; also `_filter_edges` |
| `backend/src/anim/compositing.py` | Stage 11 | Hard-partition composite — **primary source of seam issues** |
| `backend/src/anim/rendering.py` | Stage 9 | Temporal median render with per-pixel gain |
| `backend/src/anim/bundle_adjust.py` | Stage 7 | Global bundle adjustment (LM) |
| `backend/src/anim/matching.py` | Stages 5–6 | Pairwise LoFTR + TemplateMatch |
| `backend/src/anim/canvas.py` | Stage 8 | Canvas geometry, `_compute_canvas`, `_crop_to_valid` |
| `backend/src/anim/masking.py` | Stage 4 | BiRefNet foreground masks |
| `backend/src/anim/ecc.py` | Stage 8 | ECC sub-pixel refinement |
| `backend/src/anim/validation.py` | Post-7 | Affine health check; **min_gap threshold = 25px (was 50px)** |
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

## ⚠️ Critical Context — Animated Video vs. Static Scroll

**The pipeline was designed for scrolling static artwork (manga panels) but the 94-test corpus consists of animated video sequences.** Visual inspection of outputs (2026-06-01) reveals the pipeline is failing on the majority of cases with severe horizontal color banding and body-part duplication at strip seams.

**Root cause:** Characters move independently of the camera with every frame. Phase correlation on whole frames cannot separate camera displacement from character animation displacement. When frames at different animation states are stacked vertically, each strip shows a different character pose at the same canvas region — producing a temporal collage rather than a spatial panorama.

**The CV sharpness metric (Laplacian variance) is completely wrong for this use case** — hard seam edges register as "high sharpness". Do NOT trust the benchmark's `asp_better` verdict field. Use `seam_gradient` and the new `seam_coherence` metric as quality proxies. Visual inspection remains the ground truth.

**Visually confirmed good outputs (true asp_better):** asp_test28, asp_test58 (were asp_test27, asp_test57 in old numbering). Only ~10–15% of the 96 tests produce genuinely better output than the simple stitch.

---

## Known Issues Summary (94-test corpus, 2026-06-01)

### Alignment failures (25 fallbacks)

| Category | Count | Description |
|----------|------:|-------------|
| `min_gap < 25px` (near-duplicate clustering) | ~10 | Frames placed too close on canvas — genuine co-location |
| `min_gap 25–50px` (borderline — now pass) | ~13 | Previously rejected with 50px threshold; now accepted |
| `ratio > 3.0` (catastrophic bundle) | 2 | test13 (ratio=10.6), test88 (ratio=4.0) |

### Compositing failures (most ASP-succeeded tests)

Visual quality breakdown of the 69 ASP-succeeded tests:

| Category | Approx. count | Seam∇ proxy | Example tests |
|----------|--------------|-------------|---------------|
| Catastrophic — severe color banding, duplicate body parts | ~20–30 | >10 | test04, test08, test11, test25, test36, test85 |
| Poor — visible seams, color mismatch | ~20–25 | 7–10 | test01, test15, test60, test93 |
| Moderate — seams visible but usable | ~10–15 | 4–7 | test17, test34 |
| Good — genuine panorama improvement | ~5–10 | <5 | test27, test57 |

### Most impactful fixes (in priority order)

1. **Background-only phase correlation** in frame selector — use BiRefNet-masked background pixels so character animation doesn't corrupt the camera displacement estimate
2. **Canvas coverage check** — before compositing, verify median frame coverage ≥ 2 per canvas row; if not, fall back to SCANS (temporal median can't work with single-frame rows)
3. **Strip color coherence gate** — if adjacent strips differ by >20 luminance units, skip per-strip photometric normalization (Stage 11 amplifies color mismatch)
4. **Lower min_gap to 25px + vector magnitude** in `validation.py` — already implemented

---

## Test Corpus (96 datasets, asp_test01–asp_test96)

Datasets are in `data/asp_testXX/` (zero-padded). Frames are consecutive video frames (~42ms intervals) smart-selected by phase-correlation to ~18 frames/dataset (50px step target).

**Numbering note:** Two new tests were added after the initial 94-test benchmark run:
- `asp_test25` — new sequence (*Akane wa Tsumare Somerareru - 02*, ~223 frames)
- Old `asp_test25` → `asp_test26`, …, old `asp_test94` → `asp_test95` (each +1)
- `asp_test96` — new sequence (*Ajisai no Chiru Koro ni - 01*, ~139 frames)

**Ground truth images:** 55 of 96 tests have a reference panorama in `data/ground_truth/asp_testXX.{png,jpg,jpeg}`. These are used by the benchmark for SSIM/PSNR comparison vs. GT — the most reliable quality signal available.

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
pytest backend/test/anim/ -q          # all tests (~7s, no GPU)
pytest backend/test/anim/ -k "canvas" # run a specific module
```

| File | Covers |
|------|--------|
| `test_bundle_adjust.py` | Stage 7 LM solver — frame clustering, anchor frame, outlier edges |
| `test_filter_edges.py`  | `_filter_edges` — wrong-sign, gross outliers, geometric consistency |
| `test_canvas.py`        | `_compute_canvas`, `_crop_to_valid` — overcrop, horizontal scroll |
| `test_affine_validation.py` | `_validate_affines` spec — ratio, min_gap, rotation, scale |
| `test_compositing.py`   | `_diff_to_feather`, `_global_gain_normalize`, `_composite_foreground` |
| `test_rendering.py`     | `_render_median`, `_render_first`, ghosting detection, baselines |

---

## Constraints

- NEVER skip MFSR by default in the production pipeline — only skip it in test scripts. The GUI exposes an "enable MFSR" toggle.
- Do NOT add `QPixmap`, Qt, or GUI imports inside any `backend/src/anim/` file.
- Keep `_composite_foreground` signature unchanged — called by pipeline, GUI worker, and test scripts.
- Gains applied in `_render_median` and `_composite_foreground` are independent — do not confuse them.
- `has_content = src.max(axis=2) > 0` must stay at `> 0` — dark pixels with max=1–10 are real content.
- Stage 11 uses `INTER_LINEAR`, not `INTER_LANCZOS4` — Lanczos4 produces halos at silhouette edges.

My first task is: read the anime pipeline issues and analysis reports in `.agent/cache/*.md`, then read the pipeline source code in `backend/src/anim/`, then understand the current visual failures and architectural root causes, and propose or implement the fixes described in the priority list above.
